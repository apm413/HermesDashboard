"""plugin_api.py — FastAPI роутер для Hermes Dashboard плагина.

Точка входа: `router` (APIRouter), монтируется Hermes на /api/plugins/hermes-dashboard/.
Также раздаёт статику UI из dist/ на корне (для standalone-режима через start.bat).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

# Внутренние модули плагина (рядом с plugin_api.py)
from log_tailer import LogTailerHub
from probers import probe_all
from budget import read_budget_snapshot
from parsers import parse_line, EVENT_PARSED
from system_metrics import get_system_metrics

LOG = logging.getLogger("hermes-dashboard")
LOG.setLevel(logging.INFO)

# Пути — задаются через env, чтобы можно было переопределить при тестах
HERMES_VIDEO_ROOT = Path(os.environ.get(
    "HERMES_VIDEO_ROOT",
    str(Path.home() / "HermeSvideo"),
))
TIER1_ROOT = Path(os.environ.get(
    "TIER1_ROOT",
    str(Path.home() / "Desktop" / "tier1-fresh"),
))

PLUGIN_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get(
    "HERMES_DASHBOARD_DB",
    str(Path.home() / ".hermes" / "plugins" / "hermes-dashboard" / "state.db"),
))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# SQLite state (последние прогоны, метрики)
# ----------------------------------------------------------------------------

_db_lock = threading.Lock()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _db_lock, _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            project TEXT NOT NULL,
            scenario_id TEXT,
            agent TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms INTEGER,
            detail TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_runs_project_ts ON runs(project, ts DESC);
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            project TEXT NOT NULL,
            agent TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
        """)


def _record_run(project: str, scenario_id: Optional[str], agent: str,
                status: str, duration_ms: Optional[int] = None,
                detail: Optional[str] = None) -> None:
    try:
        with _db_lock, _db() as c:
            c.execute(
                "INSERT INTO runs(ts, project, scenario_id, agent, status, duration_ms, detail) "
                "VALUES(?,?,?,?,?,?,?)",
                (time.time(), project, scenario_id, agent, status, duration_ms, detail),
            )
    except Exception as e:
        LOG.warning("record_run failed: %s", e)


def _record_event(project: str, agent: str, level: str, message: str) -> None:
    try:
        with _db_lock, _db() as c:
            c.execute(
                "INSERT INTO events(ts, project, agent, level, message) VALUES(?,?,?,?,?)",
                (time.time(), project, agent, level, message),
            )
    except Exception as e:
        LOG.warning("record_event failed: %s", e)


def _recent_runs(limit: int = 50) -> List[Dict[str, Any]]:
    with _db_lock, _db() as c:
        rows = c.execute(
            "SELECT * FROM runs ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def _recent_events(limit: int = 200) -> List[Dict[str, Any]]:
    with _db_lock, _db() as c:
        rows = c.execute(
            "SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------------------
# WS broadcast
# ----------------------------------------------------------------------------

class Broadcaster:
    """Минимальный WS-broadcaster: хранит список живых клиентов и шлёт всем."""

    def __init__(self) -> None:
        self._clients: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.append(ws)

    async def remove(self, ws: WebSocket) -> None:
        async with self._lock:
            try:
                self._clients.remove(ws)
            except ValueError:
                pass

    async def send(self, payload: Dict[str, Any]) -> None:
        text = json.dumps(payload, ensure_ascii=False)
        dead: List[WebSocket] = []
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self._clients.remove(ws)
                    except ValueError:
                        pass


BROADCASTER = Broadcaster()


def emit_event(project: str, agent: str, level: str, message: str,
               scenario_id: Optional[str] = None,
               status: Optional[str] = None) -> None:
    """Синхронный emit (вызывается из log_tailer). Шлёт в WS-loop через asyncio.run_coroutine_threadsafe."""
    _record_event(project, agent, level, message)
    payload = {
        "type": "event",
        "ts": time.time(),
        "project": project,
        "agent": agent,
        "level": level,
        "message": message,
        "scenario_id": scenario_id,
        "status": status,
    }
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(BROADCASTER.send(payload), loop)
        else:
            loop.run_until_complete(BROADCASTER.send(payload))
    except RuntimeError:
        # нет event loop в этом потоке — это OK, событие уже в БД
        pass


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------

router = APIRouter()
_hub: Optional[LogTailerHub] = None


def _start_hub() -> None:
    """Идемпотентный старт log-tailer (вызывается из Hermes webhook'а при импорте)."""
    global _hub
    if _hub is not None:
        return
    _init_db()
    _hub = LogTailerHub(
        hermes_video_root=HERMES_VIDEO_ROOT,
        tier1_root=TIER1_ROOT,
        on_event=emit_event,
        on_run=_record_run,
    )
    _hub.start()
    LOG.info("HermesDashboard started: %s | %s", HERMES_VIDEO_ROOT, TIER1_ROOT)


def _stop_hub() -> None:
    global _hub
    if _hub is not None:
        _hub.stop()
        _hub = None


# Hermes вызовет это сразу после импорта модуля (см. _mount_plugin_api_routes).
# В standalone-режиме (uvicorn) — стартуем сразу.
try:
    _start_hub()
except Exception as e:
    LOG.warning("hub deferred: %s", e)


@router.get("/snapshot")
async def snapshot() -> Dict[str, Any]:
    if _hub is None:
        raise HTTPException(503, "hub not started")
    return {
        "ts": time.time(),
        "active_runs": _hub.active_runs_snapshot(),
        "recent_runs": _recent_runs(50),
        "connections": await probe_all(HERMES_VIDEO_ROOT, TIER1_ROOT),
        "budget": read_budget_snapshot(HERMES_VIDEO_ROOT),
    }


@router.get("/runs")
async def runs(limit: int = 50) -> Dict[str, Any]:
    return {"runs": _recent_runs(limit)}


@router.get("/logs")
async def logs(limit: int = 200) -> Dict[str, Any]:
    return {"events": _recent_events(limit)}


@router.get("/connections")
async def connections() -> Dict[str, Any]:
    return {"connections": await probe_all(HERMES_VIDEO_ROOT, TIER1_ROOT)}


@router.get("/budget")
async def budget() -> Dict[str, Any]:
    return read_budget_snapshot(HERMES_VIDEO_ROOT)


@router.get("/system")
async def system_metrics() -> Dict[str, Any]:
    """CPU/RAM/Disk/Net через psutil, кеш 1 сек."""
    return get_system_metrics()


@router.get("/tokens")
async def tokens() -> Dict[str, Any]:
    """Token/cost counter: парсим usage из свежих логов.

    Очень грубая эвристика: каждый INFO/DEBUG лог = ~50 входных токенов
    и ~150 выходных. Если в логе есть явные маркеры '$' или 'tokens' —
    используем их. Это v0.1, потом заменим на parser tokenizer.usage.
    """
    return _parse_token_usage()


def _parse_token_usage() -> Dict[str, Any]:
    """Читает последние 500 строк из всех логов и эвристически считает токены."""
    import re
    from collections import defaultdict
    from pathlib import Path

    out: Dict[str, Any] = {"daily": {}, "total": {"in": 0, "out": 0, "calls": 0}, "by_agent": {}}
    # файлы, которые мы мониторим
    files = []
    for root in (HERMES_VIDEO_ROOT, TIER1_ROOT):
        for sub in ("logs", "logs/studio"):
            d = Path(root) / sub
            if d.exists():
                files.extend(d.glob("*.log"))

    rx_tokens = re.compile(r"(?:input|input_tokens|prompt_tokens|in)\s*[:=]\s*(\d+)", re.IGNORECASE)
    rx_completion = re.compile(r"(?:output|output_tokens|completion_tokens|out)\s*[:=]\s*(\d+)", re.IGNORECASE)
    rx_cost = re.compile(r"\$([\d.]+)", re.IGNORECASE)

    today = time.strftime("%Y-%m-%d")
    per_day_in: Dict[str, int] = defaultdict(int)
    per_day_out: Dict[str, int] = defaultdict(int)
    per_day_cost: Dict[str, float] = defaultdict(float)

    for f in files:
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()[-500:]
        except OSError:
            continue
        agent = f.stem
        in_t = 0; out_t = 0; cost = 0.0
        for ln in lines:
            # день по timestamp в начале строки
            mday = ln[:10] if len(ln) >= 10 and ln[4] == "-" else None
            if not mday:
                mday = today
            mi = rx_tokens.search(ln)
            mo = rx_completion.search(ln)
            mc = rx_cost.search(ln)
            if mi: in_t += int(mi.group(1))
            if mo: out_t += int(mo.group(1))
            if mc: cost += float(mc.group(1))
        if in_t or out_t or cost:
            out["by_agent"][agent] = {"in": in_t, "out": out_t, "cost": round(cost, 4)}
            out["total"]["in"]  += in_t
            out["total"]["out"] += out_t
            out["total"]["calls"] += 1
            # раскидываем по дням пропорционально (без точного дня = today)
            per_day_in[mday]  += in_t
            per_day_out[mday] += out_t
            per_day_cost[mday] += cost

    out["daily"] = {
        "labels": list(per_day_in.keys()),
        "input":  [per_day_in[d]   for d in per_day_in.keys()],
        "output": [per_day_out[d]  for d in per_day_in.keys()],
        "cost":   [round(per_day_cost[d], 4) for d in per_day_in.keys()],
    }
    return out


@router.post("/action")
async def action(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Управление: run-now для tier1, terminate-pod для HermeSvideo."""
    kind = payload.get("kind")
    if kind == "run-now":
        agent = payload.get("agent")
        return _run_now_tier1(agent)
    if kind == "terminate-pod":
        pod_id = payload.get("pod_id")
        return _terminate_pod(pod_id)
    if kind == "set-active":
        project = payload.get("project")
        if _hub:
            _hub.set_active_project(project)
        return {"ok": True, "active": project}
    raise HTTPException(400, f"unknown action: {kind}")


def _run_now_tier1(agent: Optional[str]) -> Dict[str, Any]:
    """Дёргаем один tier1-агент в фоне (subprocess, не блокируем запрос)."""
    import subprocess
    cmd = ["python", "-m", "studio.start_studio", "--agent", agent] if agent \
        else ["python", "-m", "studio.start_studio", "--once"]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(Path.home() / "Desktop"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "STUDIO_MOCK_MODE": "true"},
        )
        return {"ok": True, "pid": proc.pid, "cmd": " ".join(cmd)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _terminate_pod(pod_id: Optional[str]) -> Dict[str, Any]:
    """Дёргаем HermeSvideo infra_agent stop."""
    import subprocess
    if not pod_id:
        return {"ok": False, "error": "pod_id required"}
    try:
        proc = subprocess.run(
            ["python", "agents/infra_agent.py", "stop", pod_id],
            cwd=str(HERMES_VIDEO_ROOT),
            capture_output=True, text=True, timeout=15,
        )
        return {"ok": proc.returncode == 0,
                "stdout": proc.stdout[-500:], "stderr": proc.stderr[-500:]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ----------------------------------------------------------------------------
# Static UI (для standalone — start.bat)
# ----------------------------------------------------------------------------

PLUGIN_PARENT = Path(__file__).resolve().parent.parent
DIST_DIR = Path(__file__).resolve().parent / "dist"
VARIANTS_DIR = PLUGIN_PARENT / "screenshots" / "variants"


@router.get("/")
async def root_index():
    idx = DIST_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return JSONResponse({"error": "UI not built", "hint": "see README"}, status_code=500)


@router.get("/style.css")
async def css():
    css = DIST_DIR / "style.css"
    if css.exists():
        return FileResponse(str(css), media_type="text/css")
    raise HTTPException(404)


@router.get("/index.js")
async def js():
    js = DIST_DIR / "index.js"
    if js.exists():
        return FileResponse(str(js), media_type="application/javascript")
    raise HTTPException(404)


@router.get("/preview.html")
async def preview():
    p = DIST_DIR / "preview.html"
    if p.exists():
        return FileResponse(str(p))
    raise HTTPException(404)


@router.get("/comparison.html")
async def comparison():
    p = DIST_DIR / "comparison.html"
    if p.exists():
        return FileResponse(str(p))
    raise HTTPException(404)


@router.get("/mobile.html")
async def mobile():
    p = DIST_DIR / "mobile.html"
    if p.exists():
        return FileResponse(str(p))
    raise HTTPException(404)


@router.get("/tablet.html")
async def tablet():
    p = DIST_DIR / "tablet.html"
    if p.exists():
        return FileResponse(str(p))
    raise HTTPException(404)


@router.get("/screenshots/variants/{name}")
async def variant_css(name: str):
    p = VARIANTS_DIR / name
    if p.exists() and p.suffix == ".css":
        return FileResponse(str(p), media_type="text/css")
    raise HTTPException(404)


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    await BROADCASTER.add(ws)
    LOG.info("WS client connected: %s", ws.client)
    # Отправим последние N событий как историю
    for ev in list(reversed(_recent_events(50))):
        try:
            await ws.send_text(json.dumps({"type": "history", **ev}, ensure_ascii=False))
        except Exception:
            break
    try:
        while True:
            # Поддерживаем живой коннект — клиент может слать {"type":"ping"}
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if msg:
                    try:
                        obj = json.loads(msg)
                    except json.JSONDecodeError:
                        obj = {}
                    if obj.get("type") == "ping":
                        await ws.send_text(json.dumps({"type": "pong", "ts": time.time()}))
            except asyncio.TimeoutError:
                # keepalive
                await ws.send_text(json.dumps({"type": "keepalive", "ts": time.time()}))
    except WebSocketDisconnect:
        pass
    finally:
        await BROADCASTER.remove(ws)
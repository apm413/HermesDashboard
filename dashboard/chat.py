"""chat.py — приём команд от чат-панели Electron-обёртки и проброс в CLI агентов.

Поддерживает два режима:
- slash-команды (напр. /run seo, /post reddit) → вызов subprocess CLI
- свободный текст → последние события лога + system snapshot
"""
from __future__ import annotations

import asyncio
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Пути к проектам — overridable через переменные окружения.
# По умолчанию ожидается стандартное расположение C:\\Users\\<user>\\...
TIER1_ROOT = Path(os.environ.get(
    "HERMES_DASHBOARD_TIER1_ROOT",
    r"C:/Users/CarlosRi/Desktop/tier1-fresh"
))
TIER1_STUDIO_LINK = Path(os.environ.get(
    "HERMES_DASHBOARD_TIER1_STUDIO",
    r"C:/Users/CarlosRi/Desktop/studio"
))
HERMESVIDEO_ROOT = Path(os.environ.get(
    "HERMES_DASHBOARD_HERMESVIDEO_ROOT",
    r"C:/Users/CarlosRi/HermeSvideo"
))
HERMES_DASHBOARD_DIR = Path(__file__).parent.resolve()

# Реестр известных команд (для автокомплита в UI)
# agent = короткое имя для argparse start_studio.py --agent (если None → нет subprocess)
COMMANDS: List[Dict[str, str]] = [
    # tier1 (--agent принимает: seo, reddit, twitter, analytics)
    {"cmd": "tier1:once",        "agent": None,        "desc": "Прогнать все tier1-агенты один раз (mock mode)"},
    {"cmd": "tier1:seo",         "agent": "seo",          "desc": "Запустить SEO-куратор (tier1)"},
    {"cmd": "tier1:reddit",      "agent": "reddit",       "desc": "Опубликовать пост в Reddit (tier1, mock)"},
    {"cmd": "tier1:twitter",     "agent": "twitter",      "desc": "Опубликовать твит (tier1, mock)"},
    {"cmd": "tier1:analytics",   "agent": "analytics",    "desc": "Собрать аналитику tier1"},
    # hermesvideo
    {"cmd": "video:demo",        "agent": "orchestrator", "desc": "Сгенерировать демо-сценарий (HermeSvideo)"},
    {"cmd": "video:status",      "agent": "bootstrap",    "desc": "Проверить статус бюджета/ключей (HermeSvideo)"},
    {"cmd": "video:verify-keys", "agent": "verify_keys",   "desc": "Проверить API-ключи (HermeSvideo)"},
    {"cmd": "video:test-all",    "agent": "test_all",     "desc": "Smoke-тест всех агентов (HermeSvideo)"},
    # global
    {"cmd": "budget",            "agent": None,        "desc": "Текущий бюджет (через /budget endpoint)"},
    {"cmd": "system",            "agent": None,        "desc": "CPU/RAM/Disk снапшот"},
    {"cmd": "logs",              "agent": None,        "desc": "Последние 20 строк из логов обоих проектов"},
    {"cmd": "help",              "agent": None,        "desc": "Список команд"},
]

# Маппинг команд → (cwd, argv, env-overrides)
def _build_argv(cmd: str) -> Dict[str, Any]:
    """Возвращает {cwd, argv, env} для subprocess."""
    if cmd == "tier1:once":
        # Используем wrapper который регистрирует `studio` → tier1-fresh
        return {
            "cwd": str(HERMES_DASHBOARD_DIR),
            "argv": [sys.executable, "tier1_runner.py", "--once"],
            "env": {"STUDIO_MOCK_MODE": "true"},
        }
    if cmd.startswith("tier1:"):
        agent = next((c["agent"] for c in COMMANDS if c["cmd"] == cmd), None)
        if not agent:
            return None
        return {
            "cwd": str(HERMES_DASHBOARD_DIR),
            "argv": [sys.executable, "tier1_runner.py", "--agent", agent],
            "env": {"STUDIO_MOCK_MODE": "true"},
        }
    if cmd == "video:demo":
        return {
            "cwd": str(HERMESVIDEO_ROOT),
            "argv": [sys.executable, "agents/orchestrator.py", "demo"],
            "env": {"PYTHONPATH": str(HERMESVIDEO_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")},
        }
    if cmd == "video:status":
        # Запускаем bootstrap check — он покажет состояние системы
        return {
            "cwd": str(HERMESVIDEO_ROOT),
            "argv": [sys.executable, "agents/bootstrap.py", "check"],
            "env": {"PYTHONPATH": str(HERMESVIDEO_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")},
        }
    if cmd.startswith("video:"):
        agent = next((c["agent"] for c in COMMANDS if c["cmd"] == cmd), None)
        if not agent:
            return None
        return {
            "cwd": str(HERMESVIDEO_ROOT),
            "argv": [sys.executable, f"agents/{agent}.py"],
            "env": {"PYTHONPATH": str(HERMESVIDEO_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")},
        }
    return None


async def execute_command(cmd: str, *, timeout: int = 60) -> Dict[str, Any]:
    """Запускает subprocess и возвращает {ok, stdout, stderr, exit_code, cmd, duration_ms}."""
    if cmd not in {c["cmd"] for c in COMMANDS}:
        return {"ok": False, "error": f"unknown command: {cmd}"}

    spec = _build_argv(cmd)
    if spec is None:
        return {"ok": False, "error": f"no executor for {cmd}"}

    if not Path(spec["cwd"]).exists():
        return {"ok": False, "error": f"cwd not found: {spec['cwd']}"}

    env = {**os.environ, **spec["env"]}
    t0 = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *spec["argv"],
            cwd=spec["cwd"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "error": f"timeout after {timeout}s", "cmd": cmd}
        dt = int((time.time() - t0) * 1000)
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout_b.decode("utf-8", errors="replace")[-4000:],  # tail
            "stderr": stderr_b.decode("utf-8", errors="replace")[-2000:],
            "cmd": cmd,
            "argv": spec["argv"],
            "cwd": spec["cwd"],
            "duration_ms": dt,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "cmd": cmd}


async def chat_message(text: str) -> Dict[str, Any]:
    """Главная точка входа: принимает текст от пользователя, возвращает ответ.

    Сначала пробует распарсить как slash-команду, иначе — fallback
    на эхо + последние события."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty message"}

    if text in ("/help", "help", "?"):
        return {
            "ok": True,
            "type": "help",
            "commands": COMMANDS,
            "hint": "Кликни команду или набери /tier1:seo и т.п.",
        }

    # Команды, которые обрабатываются локально (не через subprocess)
    LOCAL_COMMANDS = {"budget", "system", "logs"}

    # Извлекаем cmd: из /cmd (slash) или из голого имени
    m = re.match(r"^/([a-zA-Z0-9_:\-]+)\b\s*(.*)$", text)
    cmd = m.group(1) if m else text  # для "budget" → "budget", для "/budget" → "budget"

    if cmd in {c["cmd"] for c in COMMANDS}:
        if cmd in LOCAL_COMMANDS:
            pass  # обработаем ниже как echo
        else:
            return {"ok": True, "type": "exec", **_friendly_exec(cmd, await execute_command(cmd))}

    if cmd == "budget":
        # Бюджет HermeSvideo через budget.py (синхронно, быстро)
        try:
            return {"ok": True, "type": "echo", "echo": _format_budget()}
        except Exception as e:
            return {"ok": False, "error": f"budget error: {e}"}

    if cmd == "system":
        try:
            return {"ok": True, "type": "echo", "echo": _format_system()}
        except Exception as e:
            return {"ok": False, "error": f"system error: {e}"}

    if cmd == "logs":
        try:
            return {"ok": True, "type": "echo", "echo": _format_logs()}
        except Exception as e:
            return {"ok": False, "error": f"logs error: {e}"}

    # Fallback: произвольный текст → эхо + system snapshot
    return {
        "ok": True,
        "type": "echo",
        "echo": text,
        "hint": "Это не slash-команда. Введи /help для списка.",
    }
def _friendly_exec(cmd: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Превращает exit=2 от bootstrap/verify_keys в понятный human-friendly месседж.

    Без этой обёртки Carlos увидел бы просто "exit=2" в чате и не понял бы,
    что не сконфигурированы .env-ключи для RunPod/Heleket/etc.
    """
    if result.get("exit_code") == 2 and cmd in ("video:status", "video:verify-keys"):
        stderr = (result.get("stderr") or "").strip()
        stdout = (result.get("stdout") or "").strip()
        # Ищем паттерны "missing"/"no key" — это значит .env пустой
        full = (stdout + stderr).lower()
        if "missing" in full or "no key" in full or "xxxx" in full or "не заполнен" in full:
            result["hint"] = (
                "HermeSvideo .env не сконфигурирован (нет реальных API-ключей). "
                "Скопируй `HermeSvideo/.env.template` → `HermeSvideo/.env` и заполни ключи."
            )
            result["ok"] = False
            result["expected"] = True  # Помечаем как "ожидаемая ошибка"
    return result


def _format_budget() -> str:
    """Читает budget из файла (быстро, без HTTP)."""
    from budget import read_budget_snapshot
    b = read_budget_snapshot(HERMESVIDEO_ROOT)
    return (
        f"Бюджет HermeSvideo:\n"
        f"  Дневной: ${b.get('daily_used', 0):.2f} / ${b.get('daily_limit', 3):.2f} "
        f"({b.get('daily_pct', 0):.0f}%)\n"
        f"  Месячный: ${b.get('monthly_used', 0):.2f} / ${b.get('monthly_limit', 45):.2f} "
        f"({b.get('monthly_pct', 0):.0f}%)\n"
        f"  Tier1: $0 (Ollama локально)"
    )


def _format_system() -> str:
    """Читает системные метрики."""
    from system_metrics import get_system_metrics
    m = get_system_metrics()
    disk = m["disks"][0] if m["disks"] else {}
    return (
        f"Система:\n"
        f"  CPU: {m['cpu_pct']:.1f}% ({m['cpu_count_logical']} ядер)\n"
        f"  RAM: {m['ram_used_gb']:.1f}/{m['ram_total_gb']:.1f} ГБ ({m['ram_pct']:.0f}%)\n"
        f"  Disk {disk.get('mount', '?')}: {disk.get('used_gb', 0):.0f}/{disk.get('total_gb', 0):.0f} ГБ "
        f"({disk.get('pct', 0):.0f}%)"
    )


def _format_logs() -> str:
    """Читает последние 20 строк напрямую из .log файлов обоих проектов."""
    from pathlib import Path as P
    import os

    lines = ["Последние события из логов:"]
    # 1) HermeSvideo logs (logs/<agent>.log)
    hv_logs = HERMESVIDEO_ROOT / "logs"
    found = []
    if hv_logs.exists():
        for f in sorted(hv_logs.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            try:
                content = f.read_text(encoding="utf-8", errors="replace").strip().splitlines()
                for ln in content[-3:]:
                    found.append(f"  [hv:{f.stem}] {ln[:120]}")
            except Exception:
                pass
    # 2) tier1 logs (../logs/studio/<agent>.log) — рядом с Desktop
    t1_logs = TIER1_ROOT.parent / "logs" / "studio"
    if t1_logs.exists():
        for f in sorted(t1_logs.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            try:
                content = f.read_text(encoding="utf-8", errors="replace").strip().splitlines()
                for ln in content[-3:]:
                    found.append(f"  [t1:{f.stem}] {ln[:120]}")
            except Exception:
                pass
    if not found:
        return "Логи пока пусты. Запусти агентов или подожди их работы."
    return "\n".join(lines + found[-20:])

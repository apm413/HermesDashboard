"""log_tailer.py — потоковый tail файлов логов обоих проектов.

HermeSvideo: ROOT/logs/<agent>.log  (orchestrator.log, video.log, infra.log, ...)
tier1:        PROJECT_ROOT/../logs/studio/*.log
                (в нашем случае: ~/Desktop/logs/studio/orchestrator.log и агенты)

Tail работает в отдельных потоках (daemon=True), эмитит события через on_event().
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from parsers import parse_line

LOG = logging.getLogger("hermes-dashboard.tail")
LOG.setLevel(logging.INFO)


class _FileTailer(threading.Thread):
    def __init__(self, path: Path, project: str, on_event: Callable,
                 on_run: Optional[Callable] = None,
                 active_filter: Optional[Callable[[str], bool]] = None) -> None:
        super().__init__(daemon=True, name=f"tail-{project}-{path.name}")
        self.path = path
        self.project = project
        self.on_event = on_event
        self.on_run = on_run
        self.active_filter = active_filter
        self._stop = threading.Event()
        self._buf = b""
        self._inode: Optional[int] = None
        self._pos: int = 0
        self._last_ts: Optional[float] = None  # for run-duration tracking
        self._scenario: Optional[str] = None
        self._first_lines_skipped = False  # чтобы не считать уже-пройденные как "новые"

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        # При первом старте — прочитать текущий EOF и встать туда (только НОВОЕ).
        if not self.path.exists():
            # Ждём, пока файл появится
            for _ in range(30):
                if self._stop.is_set():
                    return
                if self.path.exists():
                    break
                time.sleep(0.5)
            else:
                LOG.warning("log file never appeared: %s", self.path)
                return
        try:
            self._inode = self.path.stat().st_ino
            self._pos = self.path.stat().st_size  # встать на EOF
        except OSError:
            return

        # Bug-fix: если файл был пустой при старте (size=0) — мы встали на 0,
        # но когда туда запишут — нужно сразу подхватить. Поэтому:
        # если прошло N секунд, а pos всё ещё 0 и size > 0 — сбрасываем на 0 (re-read).
        start_wall = time.time()

        while not self._stop.is_set():
            try:
                self._read_new()
            except Exception as e:
                LOG.warning("tail read error %s: %s", self.path, e)
            # Heal: если файл был 0 при старте, а сейчас > 0 и мы ничего не прочитали — перечитать с начала
            if time.time() - start_wall > 2 and self._pos == 0:
                try:
                    sz = self.path.stat().st_size
                    if sz > 0:
                        # Это значит, что файл был пустой при нашем старте,
                        # а теперь там данные, которые мы НЕ должны терять.
                        LOG.info("heal: re-reading %s from start (was empty at boot)", self.path)
                        self._pos = 0
                        self._read_new()
                except OSError:
                    pass
            self._stop.wait(0.5)

    def _read_new(self) -> None:
        # Ротация: inode сменился — открыть заново с начала
        try:
            st = self.path.stat()
            if self._inode is not None and st.st_ino != self._inode:
                self._inode = st.st_ino
                self._pos = 0
                self._buf = b""
            self._inode = st.st_ino
        except FileNotFoundError:
            return

        # Читаем от self._pos
        try:
            with self.path.open("rb") as f:
                f.seek(self._pos)
                chunk = f.read()
        except OSError:
            return
        if not chunk:
            return
        self._buf += chunk
        self._pos += len(chunk)

        # Разделяем по строкам
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            try:
                text = line.decode("utf-8", errors="replace").rstrip("\r")
            except Exception:
                continue
            self._emit(text)

    def _emit(self, text: str) -> None:
        parsed = parse_line(text)
        if not parsed:
            return
        # Фильтр активного проекта
        if self.active_filter and not self.active_filter(self.project):
            return

        if parsed.scenario_id and not self._scenario:
            self._scenario = parsed.scenario_id
            self._last_ts = parsed.ts

        self.on_event(
            self.project,
            parsed.agent,
            parsed.level,
            parsed.message,
            scenario_id=parsed.scenario_id,
            status=parsed.status,
        )
        # Если встретили "done"/"failed" с тем же scenario_id — закрываем run
        if self.on_run and parsed.scenario_id and parsed.status in ("done", "failed", "waiting"):
            if self._last_ts is not None and self._scenario == parsed.scenario_id:
                duration_ms = int((parsed.ts - self._last_ts) * 1000)
                self.on_run(self.project, parsed.scenario_id, parsed.agent,
                            parsed.status, duration_ms, parsed.message[:200])
                self._last_ts = None
                self._scenario = None


class LogTailerHub:
    """Координирует tail всех файлов. Поддерживает активный фильтр проекта."""

    def __init__(self, hermes_video_root: Path, tier1_root: Path,
                 on_event: Callable, on_run: Optional[Callable] = None) -> None:
        self.hermes_video_root = hermes_video_root
        self.tier1_root = tier1_root
        self.on_event = on_event
        self.on_run = on_run
        self._tailers: List[_FileTailer] = []
        self._lock = threading.Lock()
        self._active: str = "all"  # "all" | "hermesvideo" | "tier1"

    def _filter(self, project: str) -> bool:
        if self._active == "all":
            return True
        if self._active == "hermesvideo" and project == "hermesvideo":
            return True
        if self._active == "tier1" and project == "tier1":
            return True
        return False

    def set_active_project(self, project: str) -> None:
        with self._lock:
            self._active = project

    def start(self) -> None:
        # HermeSvideo: logs/*.log (orchestrator, video, post-prod, publish, infra, ...)
        hv_logs = self.hermes_video_root / "logs"
        if hv_logs.exists():
            for p in sorted(hv_logs.glob("*.log")):
                self._spawn(p, "hermesvideo")

        # tier1: ~/Desktop/logs/studio/*.log
        # (tier1 config.py пишет в PROJECT_ROOT.parent / logs/studio = Desktop/logs/studio)
        t1_logs = self.tier1_root.parent / "logs" / "studio"
        if not t1_logs.exists():
            # fallback: tier1_root/logs/studio
            t1_logs = self.tier1_root / "logs" / "studio"
        if t1_logs.exists():
            for p in sorted(t1_logs.glob("*.log")):
                self._spawn(p, "tier1")

        # На случай если директории ещё не созданы — повторный poll каждые 10 сек
        self._start_rescan_thread()
        LOG.info("hub started: %d tailers", len(self._tailers))

    def _spawn(self, path: Path, project: str) -> None:
        with self._lock:
            # Не дублировать
            for t in self._tailers:
                if t.path == path:
                    return
            t = _FileTailer(path, project, self.on_event, self.on_run, self._filter)
            self._tailers.append(t)
            t.start()

    def _start_rescan_thread(self) -> None:
        def loop():
            while True:
                time.sleep(10)
                try:
                    if self.hermes_video_root.exists():
                        d = self.hermes_video_root / "logs"
                        if d.exists():
                            for p in d.glob("*.log"):
                                self._spawn(p, "hermesvideo")
                    t1 = self.tier1_root.parent / "logs" / "studio"
                    if not t1.exists():
                        t1 = self.tier1_root / "logs" / "studio"
                    if t1.exists():
                        for p in t1.glob("*.log"):
                            self._spawn(p, "tier1")
                except Exception as e:
                    LOG.warning("rescan: %s", e)
        th = threading.Thread(target=loop, daemon=True, name="hub-rescan")
        th.start()

    def stop(self) -> None:
        for t in self._tailers:
            t.stop()

    def active_runs_snapshot(self) -> List[Dict]:
        """Текущие «живые» сценарии = то, что видели последним и не закрыто."""
        runs: Dict[str, Dict] = {}
        with self._lock:
            tailers = list(self._tailers)
        for t in tailers:
            if t._scenario and t._last_ts is not None:
                runs[t._scenario] = {
                    "scenario_id": t._scenario,
                    "project": t.project,
                    "agent": t.name.split("-", 2)[-1],
                    "started_ts": t._last_ts,
                    "last_event_ts": t._last_ts,
                }
        return list(runs.values())
"""parsers.py — парсер строк логов для HermeSvideo и tier1.

Формат HermeSvideo (common.make_logger):
    '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    2026-09-01 13:47:43,984 [orchestrator] INFO: [1/7] plan

Формат tier1 (start_studio.logging.basicConfig):
    '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    2026-09-01 13:49:07,432 [__main__] INFO: seo_curator: ...

Эмитит типизированные события через emit_event().
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional


# Примеры:
#   2026-09-01 13:47:43,984 [orchestrator] INFO: [1/7] plan
#   2026-09-01 13:49:07,432 [__main__] INFO: seo_curator: published X
LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[,\.]\d{3})\s+"
    r"\[(?P<agent>[^\]]+)\]\s+"
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL):\s+"
    r"(?P<msg>.*)$"
)


@dataclass
class ParsedLine:
    ts: float
    agent: str
    level: str
    message: str
    scenario_id: Optional[str] = None
    stage: Optional[str] = None
    status: Optional[str] = None  # running | done | failed | waiting | skipped

    def to_event(self, project: str) -> dict:
        return {
            "type": EVENT_PARSED,
            "ts": self.ts,
            "project": project,
            "agent": self.agent,
            "level": self.level,
            "message": self.message,
            "scenario_id": self.scenario_id,
            "stage": self.stage,
            "status": self.status,
        }


EVENT_PARSED = "parsed_log"


def _ts_to_float(s: str) -> float:
    # 2026-09-01 13:47:43,984 -> epoch
    s = s.replace(",", ".")
    try:
        from datetime import datetime
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return time.time()


# Стейдж-маппинг HermeSvideo (orchestrator пишет "[N/7] STAGE")
STAGE_RE = re.compile(r"\[(\d)/7\]\s+(\w[\w-]*)")
RUN_PIPELINE_RE = re.compile(r"=== pipeline start:\s+(\S+)")
SCENARIO_RE = re.compile(r"\bscenario[_'\"\s]+([a-z0-9_-]+)\b", re.IGNORECASE)
STATUS_DONE = re.compile(r"\b(done|finished|completed|ok)\b", re.IGNORECASE)
STATUS_FAIL = re.compile(r"\b(failed|error|exception|traceback)\b", re.IGNORECASE)
STATUS_WAIT = re.compile(r"\b(waiting|awaiting|pending|approve)\b", re.IGNORECASE)


def classify(message: str) -> Optional[str]:
    if STATUS_FAIL.search(message):
        return "failed"
    if STATUS_DONE.search(message):
        return "done"
    if STATUS_WAIT.search(message):
        return "waiting"
    return "running"


def parse_line(raw: str) -> Optional[ParsedLine]:
    m = LINE_RE.match(raw.strip())
    if not m:
        return None
    msg = m.group("msg").strip()
    scenario = None
    sm = SCENARIO_RE.search(msg)
    if sm:
        scenario = sm.group(1)
    pm = RUN_PIPELINE_RE.search(msg)
    if pm:
        scenario = scenario or pm.group(1)
    stage_m = STAGE_RE.search(msg)
    stage = stage_m.group(2) if stage_m else None
    status = classify(msg)
    return ParsedLine(
        ts=_ts_to_float(m.group("ts")),
        agent=m.group("agent"),
        level=m.group("level"),
        message=msg,
        scenario_id=scenario,
        stage=stage,
        status=status,
    )
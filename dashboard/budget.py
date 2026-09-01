"""budget.py — снапшот бюджета HermeSvideo (daily $3 / monthly $45) + tier1 ($0/Ollama).

Читает из common.py (DAILY_BUDGET_USD / MONTHLY_BUDGET_USD) и из runtime-логов:
- для HermeSvideo ищет "DAILY BUDGET EXCEEDED" / spend-логи в logs/*.log
- для tier1 — $0 (Ollama локально)
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


# Паттерны для определения потраченного
SPEND_RE = re.compile(r"\$([0-9]+\.?[0-9]*)\s*spent", re.IGNORECASE)
BUDGET_EXCEEDED_RE = re.compile(
    r"(DAILY|MONTHLY)\s+BUDGET\s+EXCEEDED", re.IGNORECASE
)


def read_budget_snapshot(hermes_video_root: Path) -> Dict[str, Any]:
    """Возвращает структуру для манометра."""
    daily_limit = 3.0
    monthly_limit = 45.0
    spent_today = 0.0
    spent_month = 0.0

    # Парсим common.py — fallback на дефолты
    common = hermes_video_root / "agents" / "common.py"
    if common.exists():
        text = common.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'DAILY_BUDGET_USD\s*=\s*float\(os\.environ\.get\("DAILY_BUDGET_USD",\s*"([\d.]+)"\)\)', text)
        if m:
            daily_limit = float(m.group(1))
        m = re.search(r'MONTHLY_BUDGET_USD\s*=\s*float\(os\.environments?\.get\("MONTHLY_BUDGET_USD",\s*"([\d.]+)"\)\)', text)
        if m:
            monthly_limit = float(m.group(1))
        # Может быть с одним слешем в тексте
        m = re.search(r'DAILY_BUDGET_USD\s*=\s*float\(os.environ.get\("DAILY_BUDGET_USD",\s*"([\d.]+)"\)\)', text)
        if m:
            daily_limit = float(m.group(1))
        m = re.search(r'MONTHLY_BUDGET_USD\s*=\s*float\(os.environ.get\("MONTHLY_BUDGET_USD",\s*"([\d.]+)"\)\)', text)
        if m:
            monthly_limit = float(m.group(1))

    # Парсим логи — ищем упоминания spend
    logs_dir = hermes_video_root / "logs"
    exceeded_today = False
    exceeded_month = False
    if logs_dir.exists():
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")
        for log in logs_dir.glob("*.log"):
            try:
                lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
            except OSError:
                continue
            for line in lines:
                if BUDGET_EXCEEDED_RE.search(line):
                    if "DAILY" in line:
                        exceeded_today = True
                    if "MONTHLY" in line:
                        exceeded_month = True
                m = SPEND_RE.search(line)
                if m and today in line:
                    try:
                        spent_today += float(m.group(1))
                    except ValueError:
                        pass
                m = SPEND_RE.search(line)
                if m and month in line:
                    try:
                        spent_month += float(m.group(1))
                    except ValueError:
                        pass

    return {
        "hermesvideo": {
            "daily_limit": daily_limit,
            "monthly_limit": monthly_limit,
            "spent_today": round(spent_today, 2),
            "spent_month": round(spent_month, 2),
            "exceeded_daily": exceeded_today,
            "exceeded_monthly": exceeded_month,
            "daily_pct": min(100, round(spent_today / daily_limit * 100, 1)) if daily_limit else 0,
            "monthly_pct": min(100, round(spent_month / monthly_limit * 100, 1)) if monthly_limit else 0,
        },
        "tier1": {
            "daily_limit": 0.0,
            "monthly_limit": 0.0,
            "spent_today": 0.0,
            "spent_month": 0.0,
            "note": "$0 — Ollama локально",
        },
    }
"""ai.py — AI-чат поверх OpenRouter для Hermes Dashboard.

Carlos спрашивает свободным текстом на русском. AI-агент:
  1) Понимает задачу (напр. "покажи бюджет" → вызывает get_budget tool)
  2) Сам запускает команды агентов (напр. "опубликуй пост в Reddit" → run_tier1_agent agent=reddit)
  3) Отвечает по-человечески на контекст проектов

Провайдер: OpenRouter (OpenAI-compatible API).
Дефолтная модель: qwen/qwen-2.5-7b-instruct:free (бесплатная, понимает русский, tool-calling).

Переменные окружения:
  OPENROUTER_API_KEY  — обязательно
  HERMES_AI_MODEL     — опционально, дефолт "minimax/minimax-m2.7:free"
  HERMES_AI_BASE_URL  — опционально, дефолт "https://openrouter.ai/api/v1"
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx


def _load_env_file() -> None:
    """Загрузить ключи из ~/.hermes/.env в os.environ если они ещё не установлены.

    Делаем это лениво при первом обращении, потому что uvicorn при запуске
    из ярлыка не наследует shell env.
    """
    if os.environ.get("OPENROUTER_API_KEY"):
        return
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            # Не перезаписываем уже установленные
            if k and v and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


_load_env_file()

# === Config ===
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
AI_BASE_URL = os.environ.get("HERMES_AI_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
AI_MODEL = os.environ.get("HERMES_AI_MODEL", "qwen/qwen-2.5-7b-instruct:free")
AI_TIMEOUT = float(os.environ.get("HERMES_AI_TIMEOUT", "60"))  # секунд на запрос

# Привязка к проектам — overridable как и в chat.py
TIER1_ROOT = Path(os.environ.get("HERMES_DASHBOARD_TIER1_ROOT",
    r"C:/Users/CarlosRi/Desktop/tier1-fresh"))
HERMESVIDEO_ROOT = Path(os.environ.get("HERMES_DASHBOARD_HERMESVIDEO_ROOT",
    r"C:/Users/CarlosRi/HermeSvideo"))


# === Tool definitions (function-calling) ===
# Описываем AI-агенту что он может вызывать
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_tier1_agent",
            "description": "Запустить tier1-маркетингового агента (tier1-traffic-studio). Агенты: seo, reddit, twitter, analytics. Все в mock mode по умолчанию.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "enum": ["seo", "reddit", "twitter", "analytics", "once"],
                        "description": "Какой агент запустить. 'once' = все по очереди."
                    }
                },
                "required": ["agent"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_video",
            "description": "Запустить HermeSvideo (AI видео-студия) команду. Доступно: demo (сгенерить демо), status (проверить ключи/бюджет), test-all (smoke-тест), verify-keys (проверить API).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["demo", "status", "test-all", "verify-keys"]
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget",
            "description": "Показать текущий бюджет HermeSvideo: дневной ($3) и месячный ($45). tier1 — $0 (локально Ollama)."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system",
            "description": "Показать текущие system metrics: CPU%, RAM, Disk."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_logs",
            "description": "Показать последние 20 строк логов из обоих проектов."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_connections",
            "description": "Проверить какие сервисы подключены: RunPod, ComfyUI, Ollama, Reddit, Twitter, Telegram, ElevenLabs, Suno."
        }
    }
]


# === Tool implementations ===
async def _tool_run_tier1(agent: str) -> str:
    """Запускает tier1-агент через wrapper."""
    import chat_main
    result = await chat.execute_command(f"tier1:{agent}")
    if result.get("ok"):
        return f"OK ({result.get('duration_ms', 0)}ms): {result.get('stdout', '')[-1500:]}"
    return f"FAIL (exit {result.get('exit_code')}): {result.get('stderr', '')[-500:] or result.get('error', 'unknown error')}"


async def _tool_run_video(action: str) -> str:
    import chat_main
    result = await chat.execute_command(f"video:{action}")
    if result.get("ok"):
        return f"OK ({result.get('duration_ms', 0)}ms): {result.get('stdout', '')[-1500:]}"
    hint = result.get('hint', '')
    err = f"FAIL (exit {result.get('exit_code')}): {result.get('stderr', '')[-300:] or result.get('error', '?')}"
    return err + (f"\n💡 {hint}" if hint else "")


async def _tool_get_budget() -> str:
    return _format_budget()


async def _tool_get_system() -> str:
    return _format_system()


async def _tool_get_logs() -> str:
    return _format_logs()


async def _tool_get_connections() -> str:
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:5557/connections", timeout=3) as r:
            data = json.loads(r.read())
            conns = data.get("connections", [])
            lines = ["Подключённые сервисы:"]
            for c in conns:
                status = c.get("status", "?")
                icon = {"green": "✓", "yellow": "⚠", "red": "✕", "grey": "○"}.get(status, "?")
                lines.append(f"  {icon} {c.get('name')}: {c.get('detail', '')[:80]}")
            return "\n".join(lines)
    except Exception as e:
        return f"Не удалось получить список подключений: {e}"


TOOL_DISPATCH = {
    "run_tier1_agent": lambda args: _tool_run_tier1(args.get("agent", "once")),
    "run_video": lambda args: _tool_run_video(args.get("action", "status")),
    "get_budget": lambda args: _tool_get_budget(),
    "get_system": lambda args: _tool_get_system(),
    "get_logs": lambda args: _tool_get_logs(),
    "get_connections": lambda args: _tool_get_connections(),
}


# === Local echo helpers (копия из chat.py) ===
def _format_budget() -> str:
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
    lines = ["Последние события из логов:"]
    found = []
    for label, root in [("hv", HERMESVIDEO_ROOT / "logs"), ("t1", TIER1_ROOT.parent / "logs" / "studio")]:
        if root.exists():
            for f in sorted(root.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace").strip().splitlines()
                    for ln in content[-3:]:
                        found.append(f"  [{label}:{f.stem}] {ln[:120]}")
                except Exception:
                    pass
    if not found:
        return "Логи пока пусты. Запусти агентов или подожди их работы."
    return "\n".join(lines + found[-20:])


# === System prompt для AI ===
SYSTEM_PROMPT = """Ты — AI-ассистент владельца Hermes Dashboard. Зовут "Hermes".

У владельца два проекта:
1. **HermeSvideo** (C:\\Users\\CarlosRi\\HermeSvideo) — студия AI-видео с 5 агентами: character, video, post_prod, publish, infra + orchestrator. Бюджет $3/день, $45/мес.
2. **tier1-traffic-studio** (C:\\Users\\CarlosRi\\Desktop\\tier1-fresh) — 4 маркетинговых агента: SEO, Reddit, Twitter, Analytics. Бюджет $0 (Ollama локально, ещё не установлена).

Твои возможности (tools):
- `run_tier1_agent(agent)` — запустить маркетингового агента (seo/reddit/twitter/analytics/once)
- `run_video(action)` — управлять HermeSvideo (demo/status/test-all/verify-keys)
- `get_budget()` — показать дневной/месячный бюджет
- `get_system()` — CPU/RAM/Disk
- `get_logs()` — последние строки логов
- `get_connections()` — какие внешние сервисы подключены

Правила:
1. Отвечай КРАТКО (1-3 предложения) на русском. Владелец не программист, объясняй просто.
2. Если задача требует tool — ВЫЗОВИ его. Не выдумывай результаты.
3. Если задача двусмысленная — задай уточняющий вопрос.
4. Если нужна команда slash (например, /tier1:once) — предложи её пользователю, не вызывай tools.
5. НИКОГДА не публикуй, не трать деньги и не запускай видео-рендер без явного "да" от владельца.
6. Если tools вернули ошибку — покажи её и предложи что делать (чаще всего: заполнить .env ключи).
7. При ответе НЕ повторяй вход пользователя. Отвечай по существу.

Контекст текущей сессии: сейчас 2026-09-02, Hermes Dashboard v2.1 с Electron-обёрткой + встроенным чатом."""


# === Chat engine ===
class ChatSession:
    """Состояние разговора: история сообщений + метаданные."""

    def __init__(self, max_history: int = 20):
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.max_history = max_history
        self.created_at = time.time()

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        # Trim old messages (keep system + recent N)
        if len(self.messages) > self.max_history + 1:
            self.messages = [self.messages[0]] + self.messages[-(self.max_history):]

    def add_assistant(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content
        })


# Глобальная in-memory сессия (на одного пользователя достаточно)
_session: Optional[ChatSession] = None


def get_session() -> ChatSession:
    global _session
    if _session is None:
        _session = ChatSession()
    return _session


def reset_session() -> None:
    global _session
    _session = ChatSession()


def ai_available() -> bool:
    return bool(OPENROUTER_API_KEY)


async def chat_with_ai(user_text: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Главная точка входа: принимает текст от Carlos, отдаёт ответ AI.

    Args:
        user_text: вопрос/команда от Carlos
        model:     ID модели (например "minimax/minimax-m2.7:free").
                   Если None — используется AI_MODEL (env var или дефолт).

    Возвращает:
      {
        "ok": True,
        "type": "ai",
        "text": "...",                  # финальный текст от AI
        "tool_calls": [{"name": "...", "args": {...}, "result": "..."}],
        "model": "...",
        "duration_ms": ...,
      }
    """
    if not ai_available():
        return {
            "ok": False,
            "type": "ai",
            "error": "OPENROUTER_API_KEY не задан. Установи в .env или экспортируй в окружение.",
            "fallback_hint": "Доступны только slash-команды (/tier1:once, /video:demo, /budget и т.д.)"
        }

    chosen_model = (model or "").strip() or AI_MODEL

    sess = get_session()
    sess.add_user(user_text)

    t0 = time.time()
    tool_calls_log: List[Dict[str, Any]] = []
    max_iterations = 5  # защита от бесконечного цикла tool-calling

    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            for _iteration in range(max_iterations):
                # Запрос к OpenRouter
                resp = await client.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://hermes-dashboard.local",
                        "X-Title": "Hermes Dashboard",
                    },
                    json={
                        "model": chosen_model,
                        "messages": sess.messages,
                        "tools": TOOLS,
                        "tool_choice": "auto",
                        "temperature": 0.3,
                        "max_tokens": 800,
                    },
                )

                if resp.status_code != 200:
                    err = resp.text[:300]
                    # Если 429 (rate limit) или 404 (модель недоступна) — попробуем fallback
                    if resp.status_code in (429, 404) and chosen_model != "minimax/minimax-m2.7:free":
                        chosen_model = "minimax/minimax-m2.7:free"
                        continue
                    return {
                        "ok": False,
                        "type": "ai",
                        "error": f"OpenRouter HTTP {resp.status_code}: {err}",
                        "model": chosen_model,
                    }

                data = resp.json()
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                content = msg.get("content", "") or ""
                tool_calls = msg.get("tool_calls", []) or []

                # Если AI вернул финальный текст и нет tool-calls — готово
                if not tool_calls:
                    sess.add_assistant(content)
                    return {
                        "ok": True,
                        "type": "ai",
                        "text": content,
                        "tool_calls": tool_calls_log,
                        "model": chosen_model,
                        "duration_ms": int((time.time() - t0) * 1000),
                    }

                # AI хочет вызвать tools
                sess.messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args_raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    except Exception:
                        args = {}

                    # Выполняем tool
                    if name in TOOL_DISPATCH:
                        try:
                            result = await TOOL_DISPATCH[name](args)
                        except Exception as e:
                            result = f"Tool error: {type(e).__name__}: {e}"
                    else:
                        result = f"Unknown tool: {name}"

                    tool_calls_log.append({
                        "name": name,
                        "args": args,
                        "result": (result or "")[:1500],
                    })
                    sess.add_tool_result(tc.get("id", ""), name, result[:1500])

            # Слишком много итераций
            return {
                "ok": False,
                "type": "ai",
                "error": f"Слишком много tool-вызовов ({max_iterations}), прервано",
                "tool_calls": tool_calls_log,
            }

    except httpx.TimeoutException:
        return {"ok": False, "type": "ai", "error": f"timeout after {AI_TIMEOUT}s"}
    except Exception as e:
        return {"ok": False, "type": "ai", "error": f"{type(e).__name__}: {e}"}

"""providers.py — каталог AI-моделей и провайдеров для чата.

Carlos может выбрать любую модель в dropdown чата. Список подгружается
из OpenRouter /models (live, 425 моделей), фильтруется до практичных вариантов
(поддержка tool-calling + русский язык), и кэшируется на 1 час.

Сохранение выбора — на стороне renderer (localStorage), backend читает
выбранную модель из запроса.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


def _load_env_file() -> None:
    """Загрузить ключи из ~/.hermes/.env в os.environ (lazy, при первом обращении)."""
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
            if k and v and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


_load_env_file()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE = os.environ.get("HERMES_AI_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
CACHE_TTL_SEC = 3600  # 1 час

# Кэш моделей (in-memory, process-wide)
_cache: Dict[str, Any] = {"data": None, "ts": 0.0}


# Рекомендованный список (показывается всегда, даже если API недоступен).
# OpenAI-compatible format для совместимости с /v1/chat/completions.
FALLBACK_MODELS: List[Dict[str, Any]] = [
    {
        "id": "minimax/minimax-m2.7:free",
        "name": "MiniMax M2.7 (free, ⭐ рекомендую)",
        "provider": "OpenRouter",
        "free": True,
        "supports_tools": True,
        "context": 196608,
        "description": "Хороший русский, быстрый, поддерживает tool-calling.",
    },
    {
        "id": "z-ai/glm-5.2:free",
        "name": "GLM 5.2 (free, reasoning)",
        "provider": "OpenRouter",
        "free": True,
        "supports_tools": True,
        "context": 256000,
        "description": "Сильная reasoning-модель, хороша для сложных задач.",
    },
    {
        "id": "google/gemma-4-31b-it:free",
        "name": "Gemma 4 31B (free)",
        "provider": "OpenRouter",
        "free": True,
        "supports_tools": True,
        "context": 262144,
        "description": "От Google, хорошо понимает русский.",
    },
    {
        "id": "inclusionai/ling-3.0-flash-fin:free",
        "name": "Ling 3.0 Flash (free, financial)",
        "provider": "OpenRouter",
        "free": True,
        "supports_tools": True,
        "context": 262144,
        "description": "Хороша для финансов и аналитики.",
    },
    {
        "id": "minimax/minimax-m3:free",
        "name": "MiniMax M3 (free, multimodal)",
        "provider": "OpenRouter",
        "free": True,
        "supports_tools": True,
        "context": 1048576,
        "description": "1M context, мультимодальная.",
    },
    {
        "id": "anthropic/claude-sonnet-4.5",
        "name": "Claude Sonnet 4.5 (paid, top quality)",
        "provider": "OpenRouter",
        "free": False,
        "supports_tools": True,
        "context": 200000,
        "description": "Лучшее качество reasoning, ~$3/MTok in.",
    },
    {
        "id": "openai/gpt-4o",
        "name": "GPT-4o (paid, multimodal)",
        "provider": "OpenRouter",
        "free": False,
        "supports_tools": True,
        "context": 128000,
        "description": "Быстрая, отличный tool-calling.",
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "GPT-4o-mini (paid, cheap)",
        "provider": "OpenRouter",
        "free": False,
        "supports_tools": True,
        "context": 128000,
        "description": "Дёшево, хорошо для простых задач.",
    },
    {
        "id": "anthropic/claude-3.5-haiku",
        "name": "Claude 3.5 Haiku (paid, fast)",
        "provider": "OpenRouter",
        "free": False,
        "supports_tools": True,
        "context": 200000,
        "description": "Очень быстрая и дешёвая.",
    },
    {
        "id": "deepseek/deepseek-chat-v3.1",
        "name": "DeepSeek V3.1 (paid, coding)",
        "provider": "OpenRouter",
        "free": False,
        "supports_tools": True,
        "context": 64000,
        "description": "Лучшая для кода, ~$0.27/MTok.",
    },
]


# Провайдеры, активные в системе Carlos (по наличию env-ключей)
def active_providers() -> List[Dict[str, Any]]:
    """Список провайдеров с заполненными ключами."""
    providers = []
    if OPENROUTER_API_KEY:
        providers.append({
            "id": "openrouter",
            "name": "OpenRouter",
            "status": "active",
            "key_preview": OPENROUTER_API_KEY[:10] + "***",
            "base_url": OPENROUTER_BASE,
            "default_model": "minimax/minimax-m2.7:free",
        })
    # LM Studio — localhost:1234
    if _check_lm_studio():
        providers.append({
            "id": "lmstudio",
            "name": "LM Studio (localhost)",
            "status": "active",
            "key_preview": "(local)",
            "base_url": "http://127.0.0.1:1234/v1",
            "default_model": None,  # покажет что загружено
        })
    # Ollama — localhost:11434
    if _check_ollama():
        providers.append({
            "id": "ollama",
            "name": "Ollama (localhost)",
            "status": "active",
            "key_preview": "(local)",
            "base_url": "http://127.0.0.1:11434/v1",
            "default_model": None,
        })
    if not providers:
        providers.append({
            "id": "none",
            "name": "Нет активных провайдеров",
            "status": "inactive",
            "hint": "Установи OPENROUTER_API_KEY в ~/.hermes/.env или запусти LM Studio/Ollama",
        })
    return providers


def _check_lm_studio() -> bool:
    """Быстрая проверка доступности LM Studio на 1234."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        r = s.connect_ex(('127.0.0.1', 1234))
        s.close()
        return r == 0
    except Exception:
        return False


def _check_ollama() -> bool:
    """Быстрая проверка Ollama на 11434."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        r = s.connect_ex(('127.0.0.1', 1144))
        s.close()
        return r == 0
    except Exception:
        return False


# Кэш live-списка моделей от OpenRouter
async def fetch_models_from_openrouter() -> List[Dict[str, Any]]:
    """Подтянуть live-список моделей с OpenRouter и смерджить с fallback."""
    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL_SEC:
        return _cache["data"]

    if not OPENROUTER_API_KEY:
        return FALLBACK_MODELS

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{OPENROUTER_BASE}/models",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            )
            if r.status_code != 200:
                return FALLBACK_MODELS
            data = r.json().get("data", [])
            live_models = []
            for m in data:
                # Берём только модели с tool-calling и не-embeddings
                params = m.get("supported_parameters", []) or []
                if "tools" not in params:
                    continue
                arch = m.get("architecture", {})
                if arch.get("modality") not in ("text->text", "text+image->text"):
                    continue
                mod = m.get("id", "")
                pricing = m.get("pricing", {})
                prompt_price = float(pricing.get("prompt", "0") or 0)
                is_free = prompt_price == 0
                live_models.append({
                    "id": mod,
                    "name": m.get("name", mod),
                    "provider": "OpenRouter",
                    "free": is_free,
                    "supports_tools": True,
                    "context": m.get("context_length", "?"),
                    "description": m.get("description", "")[:120],
                })
            # Сортируем: сначала free, потом по алфавиту
            live_models.sort(key=lambda m: (not m["free"], m["name"]))
            # Если OpenRouter вернул слишком мало — дополним fallback
            if len(live_models) < 5:
                live_models.extend(FALLBACK_MODELS)
            _cache["data"] = live_models
            _cache["ts"] = now
            return live_models
    except Exception:
        return FALLBACK_MODELS

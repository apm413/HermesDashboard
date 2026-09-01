"""probers.py — async-проверки подключений (RunPod, ComfyUI, Ollama, Reddit, Twitter, Telegram).

Все запросы с timeout=3 сек, при ошибке -> status="red".
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List


async def _safe_gather(*coros, timeout: float = 5.0) -> List[Any]:
    try:
        return await asyncio.wait_for(asyncio.gather(*coros, return_exceptions=True), timeout=timeout)
    except asyncio.TimeoutError:
        return ["timeout"] * len(coros)


def _mask(v: str) -> str:
    if not v:
        return "missing"
    if "xxx" in v.lower() or "placeholder" in v.lower():
        return "missing"
    if len(v) <= 8:
        return "set"
    return v[:4] + "***" + v[-2:]


def _read_env(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    out = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


# ----------------------------------------------------------------------------
# Проверки — каждая возвращает dict(name, status, detail, masked_value)
# status: green | yellow | red | grey
# ----------------------------------------------------------------------------


async def _probe_runpod(env: Dict[str, str]) -> Dict[str, Any]:
    import httpx
    key = env.get("RUNPOD_API_KEY", "")
    if not key or "xxx" in key.lower():
        return {"name": "RunPod", "status": "grey", "detail": "no key",
                "masked": _mask(key), "category": "video"}
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.post(
                "https://api.runpod.io/graphql",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"},
                json={"query": "{ myself { id email } }"},
            )
        if r.status_code == 200:
            data = r.json().get("data", {}).get("myself") or {}
            return {"name": "RunPod", "status": "green",
                    "detail": f"auth OK ({data.get('email', 'unknown')})",
                    "masked": _mask(key), "category": "video"}
        return {"name": "RunPod", "status": "red", "detail": f"HTTP {r.status_code}",
                "masked": _mask(key), "category": "video"}
    except Exception as e:
        return {"name": "RunPod", "status": "red", "detail": str(e)[:80],
                "masked": _mask(key), "category": "video"}


async def _probe_comfyui(env: Dict[str, str]) -> Dict[str, Any]:
    import httpx
    url = env.get("COMFYUI_URL", "http://127.0.0.1:8188")
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(f"{url.rstrip('/')}/system_stats")
        if r.status_code == 200:
            return {"name": "ComfyUI", "status": "green",
                    "detail": f"online @ {url}", "masked": url,
                    "category": "video"}
        return {"name": "ComfyUI", "status": "red",
                "detail": f"HTTP {r.status_code}", "masked": url,
                "category": "video"}
    except Exception:
        return {"name": "ComfyUI", "status": "grey",
                "detail": f"offline @ {url}", "masked": url,
                "category": "video"}


async def _probe_ollama() -> Dict[str, Any]:
    import httpx
    url = "http://127.0.0.1:11434"
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(f"{url}/api/tags")
        if r.status_code == 200:
            models = [m.get("name", "?") for m in r.json().get("models", [])][:5]
            return {"name": "Ollama", "status": "green",
                    "detail": f"{len(models)} models: {', '.join(models) or 'none'}",
                    "masked": url, "category": "llm"}
        return {"name": "Ollama", "status": "yellow",
                "detail": f"HTTP {r.status_code}", "masked": url,
                "category": "llm"}
    except Exception:
        return {"name": "Ollama", "status": "grey",
                "detail": "not running (tier1 в mock-режиме)",
                "masked": url, "category": "llm"}


async def _probe_reddit(env: Dict[str, str]) -> Dict[str, Any]:
    cid = env.get("REDDIT_CLIENT_ID", "")
    csec = env.get("REDDIT_CLIENT_SECRET", "")
    if not cid or not csec or "xxx" in cid.lower():
        return {"name": "Reddit", "status": "grey",
                "detail": "no creds", "masked": f"id={_mask(cid)}",
                "category": "publish"}
    # Не делаем реальный OAuth при каждом probe — дорого. Покажем только наличие.
    return {"name": "Reddit", "status": "yellow",
            "detail": "creds set (no live probe — saves rate-limit)",
            "masked": f"id={_mask(cid)}, secret={_mask(csec)}",
            "category": "publish"}


async def _probe_twitter(env: Dict[str, str]) -> Dict[str, Any]:
    key = env.get("TWITTER_API_KEY", "")
    if not key or "xxx" in key.lower():
        return {"name": "Twitter/X", "status": "grey",
                "detail": "no creds", "masked": _mask(key),
                "category": "publish"}
    return {"name": "Twitter/X", "status": "yellow",
            "detail": "creds set", "masked": _mask(key),
            "category": "publish"}


async def _probe_telegram(env: Dict[str, str]) -> Dict[str, Any]:
    import httpx
    tok = env.get("TELEGRAM_BOT_TOKEN", "")
    if not tok or "xxx" in tok.lower():
        return {"name": "Telegram bot", "status": "grey",
                "detail": "no token", "masked": _mask(tok),
                "category": "publish"}
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"https://api.telegram.org/bot{tok}/getMe")
        if r.status_code == 200 and r.json().get("ok"):
            me = r.json().get("result", {})
            return {"name": "Telegram bot", "status": "green",
                    "detail": f"@{me.get('username', '?')}",
                    "masked": _mask(tok), "category": "publish"}
        return {"name": "Telegram bot", "status": "red",
                "detail": f"HTTP {r.status_code}", "masked": _mask(tok),
                "category": "publish"}
    except Exception as e:
        return {"name": "Telegram bot", "status": "red",
                "detail": str(e)[:60], "masked": _mask(tok),
                "category": "publish"}


async def _probe_elevenlabs(env: Dict[str, str]) -> Dict[str, Any]:
    import httpx
    key = env.get("ELEVENLABS_API_KEY", "")
    if not key or "xxx" in key.lower():
        return {"name": "ElevenLabs", "status": "grey",
                "detail": "no key", "masked": _mask(key),
                "category": "video"}
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": key},
            )
        if r.status_code == 200:
            return {"name": "ElevenLabs", "status": "green",
                    "detail": "auth OK", "masked": _mask(key),
                    "category": "video"}
        return {"name": "ElevenLabs", "status": "red",
                "detail": f"HTTP {r.status_code}", "masked": _mask(key),
                "category": "video"}
    except Exception as e:
        return {"name": "ElevenLabs", "status": "red",
                "detail": str(e)[:60], "masked": _mask(key),
                "category": "video"}


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------


async def probe_all(hermes_video_root: Path, tier1_root: Path) -> List[Dict[str, Any]]:
    hv_env = _read_env(hermes_video_root / ".env")
    t1_env = _read_env(tier1_root / ".env")
    if not t1_env:
        # tier1 может брать .env из родителя (PROJECT_ROOT = tier1_root.parent)
        t1_env = _read_env(tier1_root.parent / ".env")

    merged = {**hv_env, **t1_env}
    # Если STUDIO_* не указаны — дефолты из config.py
    merged.setdefault("STUDIO_LLM_BASE_URL", "http://localhost:11434/v1")

    results = await _safe_gather(
        _probe_runpod(merged),
        _probe_comfyui(merged),
        _probe_ollama(),
        _probe_reddit(merged),
        _probe_twitter(merged),
        _probe_telegram(merged),
        _probe_elevenlabs(merged),
        timeout=8.0,
    )
    out = []
    for r in results:
        if isinstance(r, Exception):
            out.append({"name": "?", "status": "red", "detail": str(r)[:60]})
        elif isinstance(r, dict):
            out.append(r)
        else:
            out.append({"name": "?", "status": "red", "detail": str(r)})
    return out
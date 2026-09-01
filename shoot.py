"""shoot.py — ручные скриншоты через Chrome headless с заданным viewport.

Обходит проблему browser_use harness с таймаутами — использует
нативный Chrome DevTools Protocol через Python.
"""
import asyncio
import json
import subprocess
import time
from pathlib import Path
import urllib.request

# Запустим headless chrome с remote debugging port
PORT = 9222
URL = "http://127.0.0.1:5557/"


def start_chrome(width, height):
    cmd = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new",
        "--disable-gpu",
        f"--window-size={width},{height}",
        f"--remote-debugging-port={PORT}",
        "--no-first-run",
        "--no-sandbox",
        "--user-data-dir=C:/Users/CarlosRi/AppData/Local/Temp/chrome-shoot",
        URL,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc


def get_debug_url():
    for _ in range(20):
        try:
            data = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1).read()
            j = json.loads(data)
            return j["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("chrome did not start")


async def take_screenshot(ws_url, out_path, width, height, full=False):
    """Через прямой CDP."""
    import websockets
    async with websockets.connect(ws_url, max_size=64*1024*1024) as ws:
        # Установить viewport
        await ws.send(json.dumps({
            "id": 1, "method": "Emulation.setDeviceMetricsOverride",
            "params": {"width": width, "height": height,
                       "deviceScaleFactor": 1, "mobile": False}
        }))
        await ws.recv()
        # Открыть новую страницу
        target_id = await ws.send(json.dumps({
            "id": 2, "method": "Target.createTarget",
            "params": {"url": URL}
        }))
        # ... это сложно через raw ws
        pass


import sys
import os


def shoot_simple(width, height, out_path, wait_seconds=5):
    """Самый простой путь — Chrome headless с --screenshot."""
    user_data = f"C:/Users/CarlosRi/AppData/Local/Temp/chrome-shot-{width}x{height}"
    cmd = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--window-size={width},{height}",
        f"--user-data-dir={user_data}",
        f"--screenshot={out_path}",
        "--virtual-time-budget=10000",
        URL,
    ]
    # Удалим старую папку чтобы Chrome не жаловался
    import shutil
    if Path(user_data).exists():
        try:
            shutil.rmtree(user_data, ignore_errors=True)
        except Exception:
            pass
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    return Path(out_path).exists()


if __name__ == "__main__":
    out_dir = Path(r"C:/Users/CarlosRi/HermesDashboard/screenshots")
    # Desktop 1440x900
    if shoot_simple(1440, 900, str(out_dir / "v3-1440.png")):
        print("v3-1440.png OK")
    # Tablet 768x1024
    if shoot_simple(768, 1024, str(out_dir / "v3-768.png")):
        print("v3-768.png OK")
    # Mobile 375x812
    if shoot_simple(375, 812, str(out_dir / "v3-375.png")):
        print("v3-375.png OK")
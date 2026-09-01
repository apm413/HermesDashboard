"""system_metrics.py — CPU/RAM/Disk/Net в реальном времени через psutil.

Все метрики собираются синхронно (psutil.cpu_percent интервал 0.1 сек),
занимают <5 мс, кешируются на 1 секунду чтобы не молотить CPU.
"""
from __future__ import annotations

import shutil
import time
from typing import Any, Dict

try:
    import psutil
except ImportError:
    psutil = None


_cache: Dict[str, Any] = {}
_cache_ts: float = 0.0
CACHE_TTL = 1.0  # секунды


def _now() -> float:
    return time.monotonic()


def get_system_metrics(force: bool = False) -> Dict[str, Any]:
    """Возвращает метрики: cpu%, ram%, disk% (root), per-mount, net counters."""
    global _cache, _cache_ts
    if not force and _cache and (_now() - _cache_ts) < CACHE_TTL:
        return _cache

    if psutil is None:
        return {"error": "psutil not installed", "hint": "pip install psutil"}

    out: Dict[str, Any] = {"ts": time.time()}

    # CPU — interval=None даёт мгновенный (с последнего вызова), None=non-blocking
    try:
        out["cpu_pct"] = psutil.cpu_percent(interval=None)
        out["cpu_count_logical"] = psutil.cpu_count(logical=True)
        out["cpu_count_physical"] = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True)
        out["load_avg"] = list(psutil.getloadavg()) if hasattr(psutil, "getloadavg") else None
    except Exception as e:
        out["cpu_error"] = str(e)

    # RAM
    try:
        vm = psutil.virtual_memory()
        out["ram_total_gb"]   = round(vm.total / 1024**3, 1)
        out["ram_used_gb"]    = round(vm.used  / 1024**3, 1)
        out["ram_available_gb"] = round(vm.available / 1024**3, 1)
        out["ram_pct"]        = vm.percent
    except Exception as e:
        out["ram_error"] = str(e)

    # Disk — корневой и по точкам монтирования
    try:
        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(part.mountpoint)
                if u.total == 0:
                    continue
                disks.append({
                    "mount": part.mountpoint,
                    "device": part.device,
                    "fstype": part.fstype,
                    "total_gb": round(u.total / 1024**3, 1),
                    "used_gb":  round(u.used  / 1024**3, 1),
                    "free_gb":  round(u.free  / 1024**3, 1),
                    "pct":      u.percent,
                })
            except (PermissionError, OSError):
                continue
        out["disks"] = disks
    except Exception as e:
        out["disk_error"] = str(e)

    # Net counters (не скорость — просто cumulative)
    try:
        n = psutil.net_io_counters()
        out["net"] = {
            "bytes_sent":     n.bytes_sent,
            "bytes_recv":     n.bytes_recv,
            "packets_sent":   n.packets_sent,
            "packets_recv":   n.packets_recv,
        }
    except Exception as e:
        out["net_error"] = str(e)

    # Uptime
    try:
        out["uptime_s"] = int(time.time() - psutil.boot_time())
    except Exception:
        pass

    _cache = out
    _cache_ts = _now()
    return out

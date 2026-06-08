"""Persistent cache mapping ``-s host:port`` handles to server URLs.

Stale-while-revalidate: the CLI returns the cached URL immediately and
spawns a daemon thread that re-runs mDNS discovery in the background to
refresh the entry for next time. The user never blocks on the refresh.

Failure of the cached URL (connection refused, wrong server) causes the
caller to invalidate the entry and fall back to a synchronous mDNS lookup
on the same invocation, so a wrong cache costs at most one extra RTT.

Disable entirely with ``FPB_NO_CACHE=1``.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_VERSION = 1
DEFAULT_TTL_S = 24 * 3600


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "fpbinject"


def _cache_file() -> Path:
    return _cache_dir() / "handles.json"


def _disabled() -> bool:
    return os.environ.get("FPB_NO_CACHE") in ("1", "true", "True", "yes")


def _read_all() -> dict:
    if _disabled():
        return {}
    path = _cache_file()
    try:
        with path.open("r") as f:
            blob = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(blob, dict) or blob.get("version") != CACHE_VERSION:
        return {}
    entries = blob.get("entries")
    return entries if isinstance(entries, dict) else {}


def _write_all(entries: dict) -> None:
    if _disabled():
        return
    cache_dir = _cache_dir()
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.debug("cache dir create failed: %s", exc)
        return
    payload = {"version": CACHE_VERSION, "entries": entries}
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="handles.", suffix=".tmp", dir=cache_dir)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, _cache_file())
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
    except OSError as exc:
        logger.debug("cache write failed: %s", exc)


def lookup(handle: str, ttl_s: int = DEFAULT_TTL_S) -> Optional[dict]:
    """Return the cached entry for ``handle`` if fresh, else None.

    Caller must still verify liveness — a fresh cache entry can still
    point at a server that died after the last write.
    """
    if _disabled() or not handle:
        return None
    entry = _read_all().get(handle)
    if not isinstance(entry, dict):
        return None
    cached_at = entry.get("cached_at", 0)
    if (time.time() - cached_at) > ttl_s:
        return None
    return entry


def store(handle: str, *, url: str, server_id: str = "") -> None:
    """Insert/update ``handle -> url`` and persist atomically."""
    if _disabled() or not handle or not url:
        return
    entries = _read_all()
    entries[handle] = {
        "url": url,
        "id": server_id,
        "cached_at": time.time(),
    }
    _write_all(entries)


def invalidate(handle: str) -> None:
    """Drop one entry. Called when the cached URL fails to connect."""
    if _disabled() or not handle:
        return
    entries = _read_all()
    if handle in entries:
        del entries[handle]
        _write_all(entries)


def spawn_refresh(target) -> threading.Thread:
    """Run ``target()`` on a daemon thread that won't block process exit."""
    t = threading.Thread(target=target, name="fpb-cache-refresh", daemon=True)
    t.start()
    return t

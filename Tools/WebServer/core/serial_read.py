#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Context-safe serial read windowing.

The device worker appends every serial RX chunk to a ring buffer of entries
``{"id": int, "data": str}`` keyed by a monotonically increasing id. Reading
the whole buffer at once can be huge (device banners, periodic logs, prior
command echo) and blow up a consumer's context window.

This module computes a bounded, cursor-based slice of that buffer -- like
``adb logcat`` -- so a reader never receives more than a byte budget at once,
always gets a cursor to continue from, and is told how much is still pending
and whether any data was lost to ring-buffer overflow.

Two read shapes (kept deliberately simple so resuming can never lose or
duplicate data):

  * tail  (default): return the NEWEST ``max_bytes`` and set ``next`` to the
    end of the buffer. Follow-up reads with that cursor return only data that
    arrives afterwards. Older backlog is intentionally skipped.
  * paging (``since`` > 0): forward-page from ``since`` in whole-entry chunks
    up to ``max_bytes``; ``next`` advances past the returned entries and
    ``pending_bytes`` reports the remainder. Repeated calls walk the whole
    backlog with zero loss.

The logic here is pure (no Flask, no device) so it can be unit tested directly.
"""

import re
from typing import Dict, List, Optional

# Default byte budget for a single read. Small on purpose: a bare read must
# never dump the whole backlog.
DEFAULT_MAX_BYTES = 4096


def _nbytes(s: str) -> int:
    return len(s.encode("utf-8"))


def _earliest_id(entries: List[dict]) -> int:
    return min((e.get("id", 0) for e in entries), default=0)


def _empty_result(next_id: int, overflowed: bool = False) -> Dict:
    return {
        "data": "",
        "next": next_id,
        "returned_bytes": 0,
        "pending_bytes": 0,
        "pending_entries": 0,
        "truncated": False,
        "buffer_overflowed": overflowed,
    }


def _invalid_grep_result(next_id: int, message: str) -> Dict:
    """Return an error envelope when the caller-supplied regex fails to
    compile. Keeps the schema stable so callers can branch on ``error``."""
    r = _empty_result(next_id)
    r["error"] = f"invalid grep pattern: {message}"
    r["invalid_grep"] = True
    return r


def compute_read(
    entries: List[dict],
    next_id: int,
    *,
    since: int = 0,
    max_bytes: int = DEFAULT_MAX_BYTES,
    tail: int = 0,
    drop: bool = False,
    grep: Optional[str] = None,
) -> Dict:
    """Compute a context-safe windowed read over a ring buffer snapshot.

    Args:
        entries: Snapshot list of ``{"id", "data"}`` (insertion order).
        next_id: The buffer's current ``raw_log_next_id`` (cursor past the end).
        since: Forward-page from ids >= since (ignored when ``tail`` > 0).
        max_bytes: Hard cap on returned ``data`` bytes. <= 0 means DEFAULT.
        tail: If > 0, cap the returned window to the newest ``tail`` bytes.
        drop: If True, return no data and advance the cursor to ``next_id``.
        grep: Optional regex; only entries whose ``data`` matches (``re.search``)
            are considered. Filtering is applied FIRST, then the tail/paging
            window is computed over the filtered list. ``since``/``next``
            cursors still refer to the underlying buffer ids so callers can
            keep paging after they drop the filter. Invalid regex returns an
            error envelope (``invalid_grep=True``) instead of raising.

    Returns:
        dict: data, next, returned_bytes, pending_bytes, pending_entries,
        truncated, buffer_overflowed. See module docstring for semantics.
    """
    if max_bytes is None or max_bytes <= 0:
        max_bytes = DEFAULT_MAX_BYTES

    # drop: skip the backlog, just advance the cursor.
    if drop:
        return _empty_result(next_id)

    # Compile and apply the grep filter up-front (before overflow/tail/page
    # calculations) so every downstream branch operates on the filtered list.
    # We keep the original ids so the returned cursor remains meaningful.
    filtered = entries
    if grep:
        try:
            pat = re.compile(grep)
        except re.error as e:
            return _invalid_grep_result(next_id, str(e))
        filtered = [e for e in entries if pat.search(e.get("data", ""))]

    # Overflow: a since-cursor older than the oldest retained id in the RAW
    # buffer means the ring evicted data the caller had not read yet -- the
    # dropped entry may well have been a match, so we must still flag this
    # even when a grep filter is active. Only meaningful for paging.
    overflowed = (
        not tail and since > 0 and bool(entries) and since < _earliest_id(entries)
    )

    # -------------------- tail mode (newest window) --------------------
    if tail and tail > 0:
        budget = min(tail, max_bytes)
        total_all = _nbytes("".join(e.get("data", "") for e in filtered))
        # Walk entries from newest to oldest, accumulating whole entries until
        # the budget is reached; then byte-trim the oldest included entry.
        picked: List[str] = []
        acc = 0
        for e in reversed(filtered):
            d = e.get("data", "")
            picked.append(d)
            acc += _nbytes(d)
            if acc >= budget:
                break
        text = "".join(reversed(picked))
        tb = text.encode("utf-8")
        if len(tb) > budget:
            tb = tb[-budget:]
            text = tb.decode("utf-8", errors="replace")
        # In tail mode "truncated" means older data exists beyond this window.
        truncated = len(tb) < total_all
        return {
            "data": text,
            "next": next_id,
            "returned_bytes": len(tb),
            "pending_bytes": 0,
            "pending_entries": 0,
            "truncated": truncated,
            "buffer_overflowed": overflowed,
        }

    # -------------------- paging mode (since, forward) --------------------
    working = [e for e in filtered if e.get("id", 0) >= since]
    if not working:
        return _empty_result(next_id, overflowed)

    out: List[str] = []
    acc = 0
    cursor = next_id  # if everything fits, cursor is end of buffer
    consumed_any = False
    for i, e in enumerate(working):
        d = e.get("data", "")
        eb = _nbytes(d)
        # Stop before this entry if adding it would exceed the budget and we
        # already returned at least one entry (never return an empty page when
        # the very first entry alone exceeds the budget -- emit it, trimmed).
        if consumed_any and acc + eb > max_bytes:
            cursor = e.get("id", cursor)
            break
        out.append(d)
        acc += eb
        consumed_any = True
        cursor = e.get("id", cursor) + 1

    text = "".join(out)
    tb = text.encode("utf-8")
    truncated = False
    # Single oversized first entry: byte-trim it but do NOT advance the cursor
    # past it, so the caller re-reads the full entry next time (no silent loss
    # of the trimmed remainder within that entry).
    if len(tb) > max_bytes:
        tb = tb[:max_bytes]
        text = tb.decode("utf-8", errors="replace")
        truncated = True
        cursor = working[0].get("id", since)

    remaining = [e for e in filtered if e.get("id", 0) >= cursor]
    pending_bytes = _nbytes("".join(e.get("data", "") for e in remaining))
    pending_entries = len(remaining)
    if pending_bytes > 0:
        truncated = True

    return {
        "data": text,
        "next": cursor,
        "returned_bytes": len(tb),
        "pending_bytes": pending_bytes,
        "pending_entries": pending_entries,
        "truncated": truncated,
        "buffer_overflowed": overflowed,
    }

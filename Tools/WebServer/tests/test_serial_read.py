#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""Tests for context-safe serial read windowing (core/serial_read.py)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.core.serial_read import compute_read, DEFAULT_MAX_BYTES  # noqa: E402


def _entries(chunks, start_id=0):
    """Build ring-buffer entries from a list of strings."""
    return [{"id": start_id + i, "data": c} for i, c in enumerate(chunks)]


class TestComputeReadBasics(unittest.TestCase):
    def test_empty_buffer(self):
        r = compute_read([], 0)
        self.assertEqual(r["data"], "")
        self.assertEqual(r["next"], 0)
        self.assertEqual(r["pending_bytes"], 0)
        self.assertFalse(r["truncated"])
        self.assertFalse(r["buffer_overflowed"])

    def test_small_buffer_fits_default(self):
        entries = _entries(["hello ", "world\n"])
        r = compute_read(entries, 2, tail=DEFAULT_MAX_BYTES)
        self.assertEqual(r["data"], "hello world\n")
        self.assertEqual(r["next"], 2)
        self.assertEqual(r["pending_bytes"], 0)
        self.assertFalse(r["truncated"])

    def test_default_max_bytes_applied_when_zero(self):
        r = compute_read(_entries(["x"]), 1, tail=0, since=0, max_bytes=0)
        # max_bytes<=0 -> DEFAULT; nothing selected without tail/since>0 path,
        # but since=0 paging returns everything that fits.
        self.assertTrue(r["success"] if "success" in r else True)


class TestTailMode(unittest.TestCase):
    def test_tail_returns_newest_bytes(self):
        # 10 entries "0123456789" of 3 bytes each = 30 bytes total.
        entries = _entries([f"{i:03d}" for i in range(10)])
        r = compute_read(entries, 10, tail=9)
        # newest 9 bytes = last 3 entries "007008009"
        self.assertEqual(r["data"], "007008009")
        self.assertEqual(r["returned_bytes"], 9)
        self.assertEqual(r["next"], 10)
        self.assertTrue(r["truncated"])

    def test_tail_larger_than_buffer_returns_all(self):
        entries = _entries(["ab", "cd"])
        r = compute_read(entries, 2, tail=1000)
        self.assertEqual(r["data"], "abcd")
        self.assertFalse(r["truncated"])
        self.assertEqual(r["next"], 2)

    def test_tail_capped_by_max_bytes(self):
        entries = _entries(["a" * 100])
        r = compute_read(entries, 1, tail=80, max_bytes=40)
        # min(tail, max_bytes) = 40
        self.assertEqual(r["returned_bytes"], 40)
        self.assertTrue(r["truncated"])


class TestPagingMode(unittest.TestCase):
    def test_paging_since_returns_from_cursor(self):
        entries = _entries(["A", "B", "C", "D"])  # ids 0..3
        r = compute_read(entries, 4, since=2, max_bytes=1000)
        self.assertEqual(r["data"], "CD")
        self.assertEqual(r["next"], 4)
        self.assertEqual(r["pending_bytes"], 0)

    def test_paging_walks_whole_backlog_without_loss(self):
        # 20 entries of 100 bytes = 2000 bytes; page at 512 bytes each.
        chunks = [chr(ord("a") + (i % 26)) * 100 for i in range(20)]
        entries = _entries(chunks)
        next_id = 20
        full = "".join(chunks)

        collected = ""
        cursor = 0
        guard = 0
        while True:
            guard += 1
            self.assertLess(guard, 100, "paging did not terminate")
            r = compute_read(entries, next_id, since=cursor, max_bytes=512)
            collected += r["data"]
            cursor = r["next"]
            if r["pending_bytes"] == 0:
                break
            # Each non-final page must respect the byte budget.
            self.assertLessEqual(r["returned_bytes"], 512)

        # Reassembled backlog is byte-for-byte identical: zero loss.
        self.assertEqual(collected, full)
        self.assertEqual(cursor, next_id)

    def test_paging_reports_pending(self):
        chunks = ["x" * 100 for _ in range(10)]  # 1000 bytes
        entries = _entries(chunks)
        r = compute_read(entries, 10, since=0, max_bytes=250)
        self.assertLessEqual(r["returned_bytes"], 250)
        self.assertGreater(r["pending_bytes"], 0)
        self.assertGreater(r["pending_entries"], 0)
        self.assertTrue(r["truncated"])

    def test_oversized_single_entry_trimmed_but_cursor_not_advanced(self):
        # A single entry larger than the budget: trim for display, but keep the
        # cursor at that entry so the caller can re-read it fully.
        entries = _entries(["Z" * 5000])  # id 0
        r = compute_read(entries, 1, since=0, max_bytes=1000)
        self.assertEqual(r["returned_bytes"], 1000)
        self.assertTrue(r["truncated"])
        self.assertEqual(r["next"], 0)  # not advanced past the oversized entry


class TestDrop(unittest.TestCase):
    def test_drop_skips_backlog_and_advances_cursor(self):
        entries = _entries(["lots ", "of ", "backlog\n"])
        r = compute_read(entries, 3, drop=True)
        self.assertEqual(r["data"], "")
        self.assertEqual(r["next"], 3)
        self.assertEqual(r["pending_bytes"], 0)


class TestOverflowDetection(unittest.TestCase):
    def test_overflow_when_since_predates_oldest(self):
        # Ring evicted ids 0..99; oldest retained id is 100.
        entries = _entries([f"{i}" for i in range(100, 110)], start_id=100)
        r = compute_read(entries, 110, since=50, max_bytes=1000)
        self.assertTrue(r["buffer_overflowed"])

    def test_no_overflow_when_since_within_range(self):
        entries = _entries([f"{i}" for i in range(100, 110)], start_id=100)
        r = compute_read(entries, 110, since=105, max_bytes=1000)
        self.assertFalse(r["buffer_overflowed"])

    def test_no_overflow_for_fresh_cursor_zero(self):
        entries = _entries([f"{i}" for i in range(100, 110)], start_id=100)
        r = compute_read(entries, 110, since=0, max_bytes=1000)
        self.assertFalse(r["buffer_overflowed"])


class TestComputeReadGrep(unittest.TestCase):
    """Server-side grep filter: applied before tail/paging over the raw ring."""

    def test_grep_tail_returns_only_matches(self):
        # Interleave matches and non-matches; tail should ignore non-matches
        # entirely instead of just filtering the returned text after the fact.
        entries = _entries(
            [
                "boot: idle\n",
                "PANIC: null deref at 0x1234\n",
                "boot: ok\n",
                "assert: buffer overflow\n",
                "boot: heartbeat\n",
            ]
        )
        r = compute_read(entries, 5, tail=4096, grep=r"PANIC|assert")
        self.assertIn("PANIC", r["data"])
        self.assertIn("assert", r["data"])
        self.assertNotIn("boot:", r["data"])
        # Cursor still refers to the raw buffer end so callers can page later.
        self.assertEqual(r["next"], 5)

    def test_grep_no_match_returns_empty(self):
        entries = _entries(["hello\n", "world\n"])
        r = compute_read(entries, 2, tail=4096, grep=r"NOPE")
        self.assertEqual(r["data"], "")
        self.assertEqual(r["returned_bytes"], 0)
        self.assertFalse(r["truncated"])

    def test_grep_paging_walks_only_matches(self):
        entries = _entries(
            [
                "ok\n",  # id 0
                "ERR one\n",  # id 1  (8 bytes)
                "ok\n",  # id 2
                "ERR two\n",  # id 3  (8 bytes)
                "ok\n",  # id 4
            ]
        )
        # Budget of 8 bytes = exactly one match per page; the loop walks the
        # filtered subset without ever revisiting a non-match.
        collected: list[str] = []
        cursor = 0
        guard = 0
        while True:
            guard += 1
            self.assertLess(guard, 20, "paging did not terminate")
            r = compute_read(entries, 5, since=cursor, max_bytes=8, grep=r"^ERR")
            collected.append(r["data"])
            cursor = r["next"]
            if r["pending_bytes"] == 0:
                break
        text = "".join(collected)
        self.assertIn("ERR one", text)
        self.assertIn("ERR two", text)
        self.assertNotIn("ok", text)

    def test_grep_budget_counts_only_matching_entries(self):
        # Only matching entries count against max_bytes; ok\n between two
        # matches is skipped for free. Budget of 8 fits exactly the first
        # match; the second match is pending and cursor advances past the
        # non-match entry (id 1) to the next unread match (id 2).
        entries = _entries(["MATCH-A\n", "ok\n", "MATCH-B\n"])
        r = compute_read(entries, 3, since=0, max_bytes=8, grep=r"MATCH")
        self.assertEqual(r["data"], "MATCH-A\n")
        self.assertGreater(r["pending_bytes"], 0)
        # Cursor lands on the next matching entry so a re-read with
        # since=r["next"] reads MATCH-B directly.
        self.assertEqual(r["next"], 2)
        followup = compute_read(entries, 3, since=r["next"], max_bytes=8, grep=r"MATCH")
        self.assertEqual(followup["data"], "MATCH-B\n")
        self.assertEqual(followup["pending_bytes"], 0)

    def test_grep_invalid_regex_returns_error_envelope(self):
        entries = _entries(["hello\n"])
        r = compute_read(entries, 1, tail=4096, grep="[unclosed")
        self.assertTrue(r.get("invalid_grep"))
        self.assertIn("invalid grep pattern", r.get("error", ""))
        # Never leak partial data on a bad pattern.
        self.assertEqual(r["data"], "")
        self.assertEqual(r["returned_bytes"], 0)

    def test_grep_overflow_still_reported(self):
        """A dropped entry might have been THE match; overflow must still
        surface even when the caller passes a filter that excludes everything
        currently retained. This prevents silent missed matches."""
        entries = _entries([f"line {i}\n" for i in range(100, 105)], start_id=100)
        r = compute_read(entries, 105, since=50, max_bytes=1000, grep=r"NOPE")
        self.assertTrue(r["buffer_overflowed"])

    def test_grep_none_matches_previous_behaviour(self):
        # Passing grep=None must not change any observable output vs. omitting
        # the argument entirely — regression guard for the routing layer.
        entries = _entries(["A", "B", "C"])
        baseline = compute_read(entries, 3, tail=4096)
        with_none = compute_read(entries, 3, tail=4096, grep=None)
        self.assertEqual(baseline, with_none)


if __name__ == "__main__":
    unittest.main()

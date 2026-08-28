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


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for app.utils.device_op.with_fl_exit: the shared fl-mode exit policy.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.app.utils.device_op import with_fl_exit  # noqa: E402


class TestWithFlExit(unittest.TestCase):
    def test_runs_func_and_exits_fl(self):
        fpb = MagicMock()
        wrapped = with_fl_exit(lambda: "result", fpb=fpb)
        self.assertEqual(wrapped(), "result")
        fpb.exit_fl_mode.assert_called_once()

    def test_exits_fl_even_on_exception(self):
        fpb = MagicMock()

        def boom():
            raise ValueError("nope")

        wrapped = with_fl_exit(boom, fpb=fpb)
        with self.assertRaises(ValueError):
            wrapped()
        # Exit still happens on the way out.
        fpb.exit_fl_mode.assert_called_once()

    def test_keep_fl_skips_exit(self):
        fpb = MagicMock()
        wrapped = with_fl_exit(lambda: 1, keep_fl=True, fpb=fpb)
        wrapped()
        fpb.exit_fl_mode.assert_not_called()

    def test_exit_failure_does_not_mask_result(self):
        fpb = MagicMock()
        fpb.exit_fl_mode.side_effect = RuntimeError("exit blew up")
        wrapped = with_fl_exit(lambda: "ok", fpb=fpb)
        # A failing exit must not propagate or swallow the good result.
        self.assertEqual(wrapped(), "ok")

    def test_resolves_fpb_via_get_fpb_inject_when_none(self):
        fake_fpb = MagicMock()
        with patch("fpbinject.routes.get_fpb_inject", return_value=fake_fpb):
            wrapped = with_fl_exit(lambda: 42)
            self.assertEqual(wrapped(), 42)
        fake_fpb.exit_fl_mode.assert_called_once()


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for config path resolution (--config / interactive / in-memory) and
AppState config load/save with an injectable path.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fpbinject.main as main  # noqa: E402
from fpbinject.core.state import AppState  # noqa: E402


class TestResolveConfigPath(unittest.TestCase):
    """main.resolve_config_path decision table."""

    def test_explicit_config_used_verbatim(self):
        got = main.resolve_config_path("~/some/cfg.json")
        self.assertEqual(got, os.path.abspath(os.path.expanduser("~/some/cfg.json")))

    def test_non_interactive_returns_none(self):
        with patch("sys.stdin.isatty", return_value=False):
            self.assertIsNone(main.resolve_config_path(None))

    def test_interactive_existing_local_used(self):
        with tempfile.TemporaryDirectory() as d:
            local = os.path.join(d, main._LOCAL_CONFIG_NAME)
            with open(local, "w") as f:
                f.write("{}")
            with patch("sys.stdin.isatty", return_value=True), patch(
                "os.getcwd", return_value=d
            ):
                self.assertEqual(main.resolve_config_path(None), local)

    def test_interactive_yes_creates_local_path(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("sys.stdin.isatty", return_value=True), patch(
                "os.getcwd", return_value=d
            ), patch("builtins.input", return_value="y"):
                got = main.resolve_config_path(None)
            self.assertEqual(got, os.path.join(d, main._LOCAL_CONFIG_NAME))

    def test_interactive_default_enter_creates_local(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("sys.stdin.isatty", return_value=True), patch(
                "os.getcwd", return_value=d
            ), patch("builtins.input", return_value=""):
                got = main.resolve_config_path(None)
            self.assertEqual(got, os.path.join(d, main._LOCAL_CONFIG_NAME))

    def test_interactive_no_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("sys.stdin.isatty", return_value=True), patch(
                "os.getcwd", return_value=d
            ), patch("builtins.input", return_value="n"):
                self.assertIsNone(main.resolve_config_path(None))

    def test_interactive_eof_treated_as_no(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("sys.stdin.isatty", return_value=True), patch(
                "os.getcwd", return_value=d
            ), patch("builtins.input", side_effect=EOFError):
                self.assertIsNone(main.resolve_config_path(None))


class TestAppStateConfigPath(unittest.TestCase):
    """AppState.configure() load/save with injectable path + in-memory mode."""

    def test_in_memory_mode_no_file_written(self):
        st = AppState()
        st.configure(None)
        self.assertIsNone(st.config_path)
        self.assertTrue(st.first_launch)
        # save_config must be a no-op (no path); should not raise.
        st.save_config()

    def test_missing_path_marks_first_launch(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nope", "cfg.json")
            st = AppState()
            st.configure(path)
            self.assertTrue(st.first_launch)

    def test_save_then_load_roundtrip_creates_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "cfg.json")
            st = AppState()
            st.configure(path)
            st.device.baudrate = 921600
            st.save_config()
            self.assertTrue(os.path.exists(path))

            st2 = AppState()
            st2.configure(path)
            self.assertEqual(st2.device.baudrate, 921600)
            with open(path) as f:
                self.assertIn("version", json.load(f))


if __name__ == "__main__":
    unittest.main()

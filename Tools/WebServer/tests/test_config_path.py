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
        with patch(
            "fpbinject.main._discover_existing_config", return_value=None
        ), patch("sys.stdin.isatty", return_value=False):
            self.assertIsNone(main.resolve_config_path(None))

    def test_discovered_config_reused_without_prompt(self):
        """An existing config is reused even when non-interactive."""
        with tempfile.TemporaryDirectory() as d:
            existing = os.path.join(d, "config.json")
            with open(existing, "w") as f:
                f.write("{}")
            with patch(
                "fpbinject.main._discover_existing_config", return_value=existing
            ), patch("sys.stdin.isatty", return_value=False):
                self.assertEqual(main.resolve_config_path(None), existing)

    def test_interactive_yes_creates_local_path(self):
        with tempfile.TemporaryDirectory() as d:
            with patch(
                "fpbinject.main._discover_existing_config", return_value=None
            ), patch("sys.stdin.isatty", return_value=True), patch(
                "os.getcwd", return_value=d
            ), patch(
                "builtins.input", return_value="y"
            ):
                got = main.resolve_config_path(None)
            self.assertEqual(got, os.path.join(d, main._LOCAL_CONFIG_NAME))

    def test_interactive_default_enter_creates_local(self):
        with tempfile.TemporaryDirectory() as d:
            with patch(
                "fpbinject.main._discover_existing_config", return_value=None
            ), patch("sys.stdin.isatty", return_value=True), patch(
                "os.getcwd", return_value=d
            ), patch(
                "builtins.input", return_value=""
            ):
                got = main.resolve_config_path(None)
            self.assertEqual(got, os.path.join(d, main._LOCAL_CONFIG_NAME))

    def test_interactive_no_returns_none(self):
        with patch(
            "fpbinject.main._discover_existing_config", return_value=None
        ), patch("sys.stdin.isatty", return_value=True), patch(
            "builtins.input", return_value="n"
        ):
            self.assertIsNone(main.resolve_config_path(None))

    def test_interactive_eof_treated_as_no(self):
        with patch(
            "fpbinject.main._discover_existing_config", return_value=None
        ), patch("sys.stdin.isatty", return_value=True), patch(
            "builtins.input", side_effect=EOFError
        ):
            self.assertIsNone(main.resolve_config_path(None))


class TestDiscoverExistingConfig(unittest.TestCase):
    """_discover_existing_config prefers new name, then legacy config.json."""

    def _discover(self):
        # conftest stubs _discover_existing_config for safety; use the
        # preserved original to exercise the real implementation here.
        return getattr(
            main, "_discover_existing_config_orig", main._discover_existing_config
        )()

    def test_prefers_dotfile_over_legacy(self):
        with tempfile.TemporaryDirectory() as d:
            dot = os.path.join(d, main._LOCAL_CONFIG_NAME)
            legacy = os.path.join(d, main._LEGACY_CONFIG_NAME)
            open(dot, "w").close()
            open(legacy, "w").close()
            with patch("os.getcwd", return_value=d):
                self.assertEqual(self._discover(), dot)

    def test_finds_legacy_config_json(self):
        with tempfile.TemporaryDirectory() as d:
            legacy = os.path.join(d, main._LEGACY_CONFIG_NAME)
            open(legacy, "w").close()
            with patch("os.getcwd", return_value=d), patch.object(
                main, "SCRIPT_DIR", d
            ):
                self.assertEqual(self._discover(), legacy)

    def test_none_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("os.getcwd", return_value=d), patch.object(
                main, "SCRIPT_DIR", d
            ):
                self.assertIsNone(self._discover())


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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for thin entry-point shims and the version module.

These files are otherwise skipped by coverage:

* ``fpb_cli.py`` (repo-root shim) is a bootstrap wrapper that is never
  imported by other tests, so its lines never execute under coverage.
* ``version.py`` only has module-level assignments that run at import time,
  which happens *before* ``coverage.start()``. Reloading it inside a test
  re-executes those lines while coverage is active.
"""

import importlib
import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestVersionModuleExecuted(unittest.TestCase):
    """Re-execute version.py under coverage and assert its contract."""

    def test_reload_executes_module_body(self):
        import fpbinject.version as version_mod

        reloaded = importlib.reload(version_mod)

        self.assertIsInstance(reloaded.VERSION_MAJOR, int)
        self.assertIsInstance(reloaded.VERSION_MINOR, int)
        self.assertIsInstance(reloaded.VERSION_PATCH, int)
        self.assertIsInstance(reloaded.VERSION_PRERELEASE, str)
        base = (
            f"{reloaded.VERSION_MAJOR}."
            f"{reloaded.VERSION_MINOR}."
            f"{reloaded.VERSION_PATCH}"
        )
        self.assertEqual(reloaded.VERSION_STRING, f"v{base}")
        self.assertEqual(reloaded.__version__, f"{base}{reloaded.VERSION_PRERELEASE}")


class TestRootFpbCliShim(unittest.TestCase):
    """Exercise the repo-root fpb_cli.py bootstrap + forwarding shim."""

    def _load_shim(self):
        """Import Tools/WebServer/fpb_cli.py as a standalone module object."""
        path = os.path.join(PARENT_DIR, "fpb_cli.py")
        spec = importlib.util.spec_from_file_location("_root_fpb_cli_shim", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_shim_exposes_main(self):
        module = self._load_shim()
        self.assertTrue(callable(module.main))

    def test_bootstrap_noop_when_package_present(self):
        # fpbinject is already importable in the test env, so the bootstrap
        # should take the early-return path without touching sys.modules.
        module = self._load_shim()
        before = sys.modules.get("fpbinject")
        module._bootstrap_fpbinject_package()
        self.assertIs(sys.modules.get("fpbinject"), before)

    def test_bootstrap_registers_when_package_missing(self):
        module = self._load_shim()
        saved = sys.modules.pop("fpbinject", None)
        saved_submods = {
            k: sys.modules.pop(k)
            for k in list(sys.modules)
            if k.startswith("fpbinject.")
        }
        saved_path = list(sys.path)
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            # Force the "package not installed" branch regardless of any
            # symlink/PYTHONPATH shortcut in the local dev environment.
            if name == "fpbinject" or name.startswith("fpbinject."):
                raise ModuleNotFoundError("No module named 'fpbinject'")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=fake_import):
                module._bootstrap_fpbinject_package()
            pkg = sys.modules.get("fpbinject")
            self.assertIsNotNone(pkg)
            self.assertIn(PARENT_DIR, list(getattr(pkg, "__path__", [])))
            self.assertIn(PARENT_DIR, sys.path)
        finally:
            # Restore the real package so later tests are unaffected.
            sys.modules.pop("fpbinject", None)
            if saved is not None:
                sys.modules["fpbinject"] = saved
            sys.modules.update(saved_submods)
            sys.path[:] = saved_path
            importlib.import_module("fpbinject")

    def test_shim_main_is_cli_main(self):
        # The shim does ``from fpbinject.cli.fpb_cli import main``, so its
        # ``main`` must be the very same callable as the CLI entry point.
        module = self._load_shim()
        from fpbinject.cli.fpb_cli import main as cli_main

        self.assertIs(module.main, cli_main)


if __name__ == "__main__":
    unittest.main()

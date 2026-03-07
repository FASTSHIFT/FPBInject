#!/usr/bin/env python3

"""Integration tests for GDB Session using real gdb-multiarch + test ELF.

These tests verify the full json-print pipeline end-to-end:
  GDBSession._write_mi → json-print GDB command → JSON parsing

Requires: gdb-multiarch installed, tests/fixtures/test_symbols.elf present.
Skipped automatically if either is missing.

Known values from test_symbols.c:
  g_point     = {x: 10, y: 20}
  g_padded    = {a: 1, b: 0xDEADBEEF, c: 0x1234, d: 0xFF}
  g_nested    = {inner: {a: 2, b: 0xCAFE, c: 3, d: 4}, id: 999}
  g_rect      = {origin: {0, 0}, size: {100, 200}}
  g_counter   = 42
  g_signed_var = -100
"""

import json
import os
import shutil
import subprocess
import unittest

# Paths
_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
_TEST_ELF = os.path.join(_FIXTURES_DIR, "test_symbols.elf")
_GDB_JSON_PRINT = os.path.join(
    os.path.dirname(__file__), "..", "core", "gdb_json_print.py"
)

# Check prerequisites
_HAS_GDB = shutil.which("gdb-multiarch") is not None
_HAS_ELF = os.path.exists(_TEST_ELF)
_HAS_SCRIPT = os.path.exists(_GDB_JSON_PRINT)

_SKIP_REASON = None
if not _HAS_GDB:
    _SKIP_REASON = "gdb-multiarch not found"
elif not _HAS_ELF:
    _SKIP_REASON = f"test ELF not found: {_TEST_ELF}"
elif not _HAS_SCRIPT:
    _SKIP_REASON = f"gdb_json_print.py not found: {_GDB_JSON_PRINT}"


# ── Shared GDB session (module-level singleton) ──────────────────────
# Both test classes share a single persistent GDB process to avoid the
# ~1s startup cost per test.  The session is created once and torn down
# after all tests in this module complete.

_shared_session = None


def _get_shared_session():
    """Lazily create and return the shared GDBSession."""
    global _shared_session
    if _shared_session is not None:
        return _shared_session

    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from core.gdb_session import GDBSession
    from pygdbmi.IoManager import IoManager

    session = GDBSession(_TEST_ELF)
    gdb_path = shutil.which("gdb-multiarch")
    session._proc = subprocess.Popen(
        [gdb_path, "--interpreter=mi3", "--nx", "-q"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    session._io = IoManager(
        session._proc.stdin,
        session._proc.stdout,
        session._proc.stderr,
        time_to_check_for_additional_output_sec=0.05,
    )
    session._io.get_gdb_response(timeout_sec=5.0, raise_error_on_timeout=False)
    session._write_mi("set architecture arm", timeout=5.0)
    resp = session._write_mi(f"file {_TEST_ELF}", timeout=30.0)
    assert resp is not None, "Failed to load ELF"
    session._write_mi(f"source {_GDB_JSON_PRINT}", timeout=5.0)
    session._has_json_print = True
    session._alive = True
    _shared_session = session
    return session


def tearDownModule():
    """Stop the shared GDB session after all tests."""
    global _shared_session
    if _shared_session is not None:
        _shared_session.stop()
        _shared_session = None


# ── Test class 1: json-print command output ──────────────────────────


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
class TestGDBJsonPrintIntegration(unittest.TestCase):
    """Integration tests: real GDB + json-print + test ELF.

    Uses the shared persistent GDB session for speed.
    """

    @classmethod
    def setUpClass(cls):
        cls.session = _get_shared_session()

    def _json_print(self, expr, max_depth=2):
        """Run json-print via the shared session and parse JSON output."""
        output = self.session.execute(f'json-print "{expr}" {max_depth}', timeout=10.0)
        if not output:
            return None
        output = output.strip()
        if output.startswith("{") or output.startswith("["):
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return None
        return None

    def test_g_point(self):
        """g_point = {x: 10, y: 20}"""
        result = self._json_print("g_point")
        self.assertIsNotNone(result)
        self.assertEqual(result["x"], 10)
        self.assertEqual(result["y"], 20)

    def test_g_padded(self):
        """g_padded = {a: 1, b: 0xDEADBEEF, c: 0x1234, d: 0xFF}"""
        result = self._json_print("g_padded")
        self.assertIsNotNone(result)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 0xDEADBEEF)
        self.assertEqual(result["c"], 0x1234)
        self.assertEqual(result["d"], 0xFF)

    def test_g_nested(self):
        """g_nested = {inner: {a: 2, b: 0xCAFE, c: 3, d: 4}, id: 999}"""
        result = self._json_print("g_nested")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 999)
        inner = result["inner"]
        self.assertIsInstance(inner, dict)
        self.assertEqual(inner["a"], 2)
        self.assertEqual(inner["b"], 0xCAFE)
        self.assertEqual(inner["c"], 3)
        self.assertEqual(inner["d"], 4)

    def test_g_rect(self):
        """g_rect = {origin: {0, 0}, size: {100, 200}}"""
        result = self._json_print("g_rect")
        self.assertIsNotNone(result)
        self.assertEqual(result["origin"]["x"], 0)
        self.assertEqual(result["origin"]["y"], 0)
        self.assertEqual(result["size"]["x"], 100)
        self.assertEqual(result["size"]["y"], 200)

    def test_g_union(self):
        """g_union = {as_u32: 0x12345678}"""
        result = self._json_print("g_union")
        self.assertIsNotNone(result)
        self.assertEqual(result["as_u32"], 0x12345678)

    def test_g_counter_scalar(self):
        """g_counter = 42 (scalar — json-print outputs plain number)."""
        output = self.session.execute('json-print "g_counter" 1', timeout=10.0)
        self.assertIsNotNone(output)
        self.assertIn("42", output)

    def test_g_const_point(self):
        """g_const_point = {x: 42, y: 84}"""
        result = self._json_print("g_const_point")
        self.assertIsNotNone(result)
        self.assertEqual(result["x"], 42)
        self.assertEqual(result["y"], 84)

    def test_pointer_cast_also_works(self):
        """Pointer cast expression works when target is accessible."""
        import re

        output = self.session.execute("info address g_point", timeout=5.0)
        self.assertIsNotNone(output)
        m = re.search(r"0x([0-9a-fA-F]+)", output)
        self.assertIsNotNone(m, "Could not find g_point address")
        addr = int(m.group(1), 16)

        result = self._json_print(f"*((struct Point *)0x{addr:x})")
        if result is not None:
            self.assertEqual(result.get("x"), 10)
            self.assertEqual(result.get("y"), 20)


# ── Test class 2: GDBSession high-level APIs ─────────────────────────


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
class TestGDBSessionIntegration(unittest.TestCase):
    """Integration tests using GDBSession class (no RSP connection).

    Uses the shared persistent GDB session for speed.
    """

    @classmethod
    def setUpClass(cls):
        cls.session = _get_shared_session()
        # Pre-cache symbol lookups to avoid repeated GDB queries
        cls._sym_cache = {}
        for sym in ("g_point", "g_padded", "g_nested", "g_rect", "g_driver"):
            info = cls.session.lookup_symbol(sym)
            if info:
                cls._sym_cache[sym] = info

    def _lookup(self, sym_name):
        """Get cached symbol info."""
        return self._sym_cache.get(sym_name)

    def test_lookup_g_point(self):
        """lookup_symbol returns correct info for g_point."""
        info = self._lookup("g_point")
        self.assertIsNotNone(info)
        self.assertGreater(info["addr"], 0)
        self.assertEqual(info["size"], 8)
        self.assertIn(info["type"], ("variable",))

    def test_struct_layout_g_point(self):
        """get_struct_layout returns correct members for g_point."""
        layout = self.session.get_struct_layout("g_point")
        self.assertIsNotNone(layout)
        self.assertEqual(len(layout), 2)
        names = [m["name"] for m in layout]
        self.assertIn("x", names)
        self.assertIn("y", names)

    def test_struct_layout_g_padded(self):
        """get_struct_layout returns correct members for g_padded."""
        layout = self.session.get_struct_layout("g_padded")
        self.assertIsNotNone(layout)
        names = [m["name"] for m in layout]
        self.assertIn("a", names)
        self.assertIn("b", names)
        self.assertIn("c", names)
        self.assertIn("d", names)

    def test_parse_struct_values_g_point(self):
        """parse_struct_values returns {x: 10, y: 20} for g_point."""
        info = self._lookup("g_point")
        self.assertIsNotNone(info)
        values = self.session.parse_struct_values("g_point", info["addr"], "Point")
        self.assertIsNotNone(values, "parse_struct_values returned None")
        self.assertEqual(values["x"], 10)
        self.assertEqual(values["y"], 20)

    def test_parse_struct_values_g_padded(self):
        """parse_struct_values returns correct values for g_padded."""
        info = self._lookup("g_padded")
        self.assertIsNotNone(info)
        values = self.session.parse_struct_values(
            "g_padded", info["addr"], "PaddedStruct"
        )
        self.assertIsNotNone(values, "parse_struct_values returned None")
        self.assertEqual(values["a"], 1)
        self.assertEqual(values["b"], 0xDEADBEEF)
        self.assertEqual(values["c"], 0x1234)
        self.assertEqual(values["d"], 0xFF)

    def test_parse_struct_values_g_nested(self):
        """parse_struct_values returns nested struct for g_nested."""
        info = self._lookup("g_nested")
        self.assertIsNotNone(info)
        values = self.session.parse_struct_values("g_nested", info["addr"], "Nested")
        self.assertIsNotNone(values, "parse_struct_values returned None")
        self.assertEqual(values["id"], 999)
        inner = values["inner"]
        self.assertIsInstance(inner, dict)
        self.assertEqual(inner["a"], 2)
        self.assertEqual(inner["b"], 0xCAFE)

    def test_parse_struct_values_g_rect(self):
        """parse_struct_values returns nested Points for g_rect."""
        info = self._lookup("g_rect")
        self.assertIsNotNone(info)
        values = self.session.parse_struct_values("g_rect", info["addr"], "Rect")
        self.assertIsNotNone(values, "parse_struct_values returned None")
        self.assertEqual(values["origin"]["x"], 0)
        self.assertEqual(values["origin"]["y"], 0)
        self.assertEqual(values["size"]["x"], 100)
        self.assertEqual(values["size"]["y"], 200)

    def test_read_symbol_value_g_point(self):
        """read_symbol_value returns correct raw bytes for g_point."""
        raw = self.session.read_symbol_value("g_point")
        self.assertIsNotNone(raw)
        self.assertEqual(len(raw), 8)
        x = int.from_bytes(raw[0:4], "little")
        y = int.from_bytes(raw[4:8], "little")
        self.assertEqual(x, 10)
        self.assertEqual(y, 20)

    def test_full_pipeline_g_padded(self):
        """Full pipeline: lookup → layout → values → verify all match."""
        info = self._lookup("g_padded")
        self.assertIsNotNone(info)
        layout = self.session.get_struct_layout("g_padded")
        self.assertIsNotNone(layout)
        values = self.session.parse_struct_values(
            "g_padded", info["addr"], "PaddedStruct"
        )
        self.assertIsNotNone(values)
        layout_names = {m["name"] for m in layout}
        value_keys = set(values.keys())
        self.assertEqual(layout_names, value_keys)

    def test_struct_layout_g_driver_func_ptr_names(self):
        """get_struct_layout parses function pointer member names correctly."""
        layout = self.session.get_struct_layout("g_driver")
        self.assertIsNotNone(layout)
        names = {m["name"] for m in layout}
        self.assertIn("init", names)
        self.assertIn("deinit", names)
        self.assertIn("reset_cb", names)
        self.assertNotIn(")", names)
        self.assertIn("id", names)
        self.assertIn("ctx", names)
        self.assertIn("flags", names)

    def test_parse_struct_values_g_driver(self):
        """parse_struct_values returns func ptrs for g_driver."""
        info = self._lookup("g_driver")
        self.assertIsNotNone(info)
        values = self.session.parse_struct_values("g_driver", info["addr"], "DriverDef")
        self.assertIsNotNone(values, "parse_struct_values returned None")
        self.assertEqual(values["id"], 0x42)
        self.assertEqual(values["flags"], 0x0F)
        self.assertEqual(values["init"]["_kind"], "func_ptr")
        self.assertNotEqual(values["init"]["_addr"], "0x00000000")
        self.assertEqual(values["deinit"]["_kind"], "func_ptr")
        self.assertEqual(values["reset_cb"]["_addr"], "0x00000000")

    def test_full_pipeline_g_driver(self):
        """Full pipeline for struct with function pointer members."""
        info = self._lookup("g_driver")
        self.assertIsNotNone(info)
        layout = self.session.get_struct_layout("g_driver")
        self.assertIsNotNone(layout)
        values = self.session.parse_struct_values("g_driver", info["addr"], "DriverDef")
        self.assertIsNotNone(values)
        layout_names = {m["name"] for m in layout}
        value_keys = set(values.keys())
        self.assertEqual(
            layout_names,
            value_keys,
            f"Layout names {layout_names} != value keys {value_keys}",
        )


if __name__ == "__main__":
    unittest.main()

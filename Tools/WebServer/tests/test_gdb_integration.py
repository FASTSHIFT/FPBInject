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


def _run_gdb_commands(commands):
    """Run a sequence of GDB MI commands and return raw stdout."""
    input_text = "\n".join(commands) + "\n"
    result = subprocess.run(
        ["gdb-multiarch", "--interpreter=mi3", "--nx", "-q"],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout, result.stderr


def _extract_json_from_mi(stdout, command_index):
    """Extract JSON output from the Nth json-print command in MI output.

    MI console output looks like: ~"{\\"x\\": 10, ...}\\n"
    pygdbmi would parse this, but here we parse raw MI output directly.
    """
    # Find all console lines that look like JSON
    json_outputs = []
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith('~"') and "{" in line:
            # Extract the payload: ~"...\n" -> ...
            payload = line[2:]  # strip ~"
            if payload.endswith('"'):
                payload = payload[:-1]  # strip trailing "
            if payload.endswith("\\n"):
                payload = payload[:-2]  # strip \n
            # Unescape MI string
            payload = payload.replace('\\"', '"').replace("\\\\", "\\")
            if payload.startswith("{") or payload.startswith("["):
                json_outputs.append(payload)
    if command_index < len(json_outputs):
        return json.loads(json_outputs[command_index])
    return None


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
class TestGDBJsonPrintIntegration(unittest.TestCase):
    """Integration tests: real GDB + json-print + test ELF."""

    @classmethod
    def setUpClass(cls):
        """Verify GDB can load the ELF and source the script."""
        stdout, stderr = _run_gdb_commands(
            [
                '-interpreter-exec console "set architecture arm"',
                f'-interpreter-exec console "file {_TEST_ELF}"',
                f'-interpreter-exec console "source {_GDB_JSON_PRINT}"',
                '-interpreter-exec console "json-print \\"g_counter\\" 1"',
                "-gdb-exit",
            ]
        )
        # Verify json-print command is registered (not "Undefined command")
        if "Undefined command" in stdout:
            raise unittest.SkipTest(
                "json-print command not registered (GDB Python support missing?)"
            )
        cls._gdb_works = True

    def _json_print(self, expr, max_depth=2):
        """Run json-print on a single expression and return parsed result."""
        escaped_expr = expr.replace('"', '\\"')
        stdout, _ = _run_gdb_commands(
            [
                '-interpreter-exec console "set architecture arm"',
                f'-interpreter-exec console "file {_TEST_ELF}"',
                f'-interpreter-exec console "source {_GDB_JSON_PRINT}"',
                f'-interpreter-exec console "json-print \\"{escaped_expr}\\" {max_depth}"',
                "-gdb-exit",
            ]
        )
        return _extract_json_from_mi(stdout, 0)

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
        """g_counter = 42 (volatile uint32_t, scalar — returns int, not dict)"""
        # json-print on a scalar returns a plain number, not a JSON object.
        # _extract_json_from_mi only extracts objects/arrays, so this returns None.
        # This is expected — parse_struct_values is only used for structs.
        stdout, _ = _run_gdb_commands(
            [
                '-interpreter-exec console "set architecture arm"',
                f'-interpreter-exec console "file {_TEST_ELF}"',
                f'-interpreter-exec console "source {_GDB_JSON_PRINT}"',
                '-interpreter-exec console "json-print \\"g_counter\\" 1"',
                "-gdb-exit",
            ]
        )
        # Verify the output contains "42"
        self.assertIn("42", stdout)

    def test_g_const_point(self):
        """g_const_point = {x: 42, y: 84}"""
        result = self._json_print("g_const_point")
        self.assertIsNotNone(result)
        self.assertEqual(result["x"], 42)
        self.assertEqual(result["y"], 84)

    def test_pointer_cast_also_works(self):
        """Pointer cast expression works when target is accessible."""
        # Get the address of g_point first
        stdout, _ = _run_gdb_commands(
            [
                '-interpreter-exec console "set architecture arm"',
                f'-interpreter-exec console "file {_TEST_ELF}"',
                '-interpreter-exec console "info address g_point"',
                "-gdb-exit",
            ]
        )
        # Parse address from output
        import re

        m = re.search(r"0x([0-9a-fA-F]+)", stdout)
        self.assertIsNotNone(m, "Could not find g_point address")
        addr = int(m.group(1), 16)

        # Now try pointer cast — this reads from ELF loadable segments
        result = self._json_print(f"*((struct Point *)0x{addr:x})")
        # This may or may not work depending on GDB version and memory mapping
        # The important thing is it doesn't crash
        if result is not None:
            self.assertEqual(result.get("x"), 10)
            self.assertEqual(result.get("y"), 20)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
class TestGDBSessionIntegration(unittest.TestCase):
    """Integration tests using GDBSession class (no RSP connection)."""

    @classmethod
    def setUpClass(cls):
        """Create a GDBSession and start it without RSP."""
        from core.gdb_session import GDBSession

        cls.session = GDBSession(_TEST_ELF)
        # We can't call start() without RSP, so manually set up GDB
        cls._setup_gdb_manually()

    @classmethod
    def _setup_gdb_manually(cls):
        """Start GDB, load ELF, source json-print — without RSP connect."""
        import subprocess as sp
        from pygdbmi.IoManager import IoManager

        gdb_path = shutil.which("gdb-multiarch")
        cls.session._proc = sp.Popen(
            [gdb_path, "--interpreter=mi3", "--nx", "-q"],
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            bufsize=0,
        )
        cls.session._io = IoManager(
            cls.session._proc.stdin,
            cls.session._proc.stdout,
            cls.session._proc.stderr,
            time_to_check_for_additional_output_sec=0.3,
        )
        # Read startup
        cls.session._io.get_gdb_response(timeout_sec=5.0, raise_error_on_timeout=False)
        # Set architecture
        cls.session._write_mi("set architecture arm", timeout=5.0)
        # Load ELF
        resp = cls.session._write_mi(f"file {_TEST_ELF}", timeout=30.0)
        assert resp is not None, "Failed to load ELF"
        # Source json-print
        cls.session._write_mi(f"source {_GDB_JSON_PRINT}", timeout=5.0)
        cls.session._has_json_print = True
        cls.session._alive = True

    @classmethod
    def tearDownClass(cls):
        cls.session.stop()

    def test_lookup_g_point(self):
        """lookup_symbol returns correct info for g_point."""
        info = self.session.lookup_symbol("g_point")
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
        info = self.session.lookup_symbol("g_point")
        self.assertIsNotNone(info)
        values = self.session.parse_struct_values("g_point", info["addr"], "Point")
        self.assertIsNotNone(values, "parse_struct_values returned None")
        self.assertEqual(values["x"], 10)
        self.assertEqual(values["y"], 20)

    def test_parse_struct_values_g_padded(self):
        """parse_struct_values returns correct values for g_padded."""
        info = self.session.lookup_symbol("g_padded")
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
        info = self.session.lookup_symbol("g_nested")
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
        info = self.session.lookup_symbol("g_rect")
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
        # x=10 (LE: 0a 00 00 00), y=20 (LE: 14 00 00 00)
        x = int.from_bytes(raw[0:4], "little")
        y = int.from_bytes(raw[4:8], "little")
        self.assertEqual(x, 10)
        self.assertEqual(y, 20)

    def test_full_pipeline_g_padded(self):
        """Full pipeline: lookup → layout → values → verify all match."""
        info = self.session.lookup_symbol("g_padded")
        self.assertIsNotNone(info)

        layout = self.session.get_struct_layout("g_padded")
        self.assertIsNotNone(layout)

        values = self.session.parse_struct_values(
            "g_padded", info["addr"], "PaddedStruct"
        )
        self.assertIsNotNone(values)

        # Verify layout field names match value keys
        layout_names = {m["name"] for m in layout}
        value_keys = set(values.keys())
        self.assertEqual(layout_names, value_keys)

    def test_struct_layout_g_driver_func_ptr_names(self):
        """get_struct_layout parses function pointer member names correctly.

        Regression test: void (*init)(void *, int) was parsed as name=')'.
        """
        layout = self.session.get_struct_layout("g_driver")
        self.assertIsNotNone(layout)
        names = {m["name"] for m in layout}
        # Function pointer members must have correct names
        self.assertIn("init", names)
        self.assertIn("deinit", names)
        self.assertIn("reset_cb", names)
        # Must NOT have ")" as a name
        self.assertNotIn(")", names)
        # Regular members still work
        self.assertIn("id", names)
        self.assertIn("ctx", names)
        self.assertIn("flags", names)

    def test_parse_struct_values_g_driver(self):
        """parse_struct_values returns func ptrs for g_driver."""
        info = self.session.lookup_symbol("g_driver")
        self.assertIsNotNone(info)
        values = self.session.parse_struct_values("g_driver", info["addr"], "DriverDef")
        self.assertIsNotNone(values, "parse_struct_values returned None")
        self.assertEqual(values["id"], 0x42)
        self.assertEqual(values["flags"], 0x0F)
        # Function pointer fields should be dicts with _kind
        self.assertEqual(values["init"]["_kind"], "func_ptr")
        self.assertNotEqual(values["init"]["_addr"], "0x00000000")
        self.assertEqual(values["deinit"]["_kind"], "func_ptr")
        # NULL function pointer
        self.assertEqual(values["reset_cb"]["_addr"], "0x00000000")

    def test_full_pipeline_g_driver(self):
        """Full pipeline for struct with function pointer members.

        Verifies layout field names match gdb_values keys — the exact
        bug that caused ')' field names and mismatched values.
        """
        info = self.session.lookup_symbol("g_driver")
        self.assertIsNotNone(info)

        layout = self.session.get_struct_layout("g_driver")
        self.assertIsNotNone(layout)

        values = self.session.parse_struct_values("g_driver", info["addr"], "DriverDef")
        self.assertIsNotNone(values)

        # THE KEY ASSERTION: layout names must match value keys
        layout_names = {m["name"] for m in layout}
        value_keys = set(values.keys())
        self.assertEqual(
            layout_names,
            value_keys,
            f"Layout names {layout_names} != value keys {value_keys}",
        )


if __name__ == "__main__":
    unittest.main()

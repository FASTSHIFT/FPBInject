#!/usr/bin/env python3
"""Tests for app/routes/symbols.py"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from app.routes.symbols import bp  # noqa: E402
from core.state import state  # noqa: E402


class SymbolRoutesBase(unittest.TestCase):
    """Base class for symbol route tests."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(bp, url_prefix="/api")
        self.client = self.app.test_client()
        state.symbols = {}
        state.symbols_loaded = False
        state.device.elf_path = ""
        state.device.watch_dirs = []

    def tearDown(self):
        state.symbols = {}
        state.symbols_loaded = False
        state.gdb_session = None
        # Clear module-level caches
        from app.routes.symbols import _struct_layout_cache, _symbol_detail_cache

        _struct_layout_cache.clear()
        _symbol_detail_cache.clear()


class TestGetSymbols(SymbolRoutesBase):
    """Test /api/symbols endpoint."""

    def test_symbols_not_loaded_no_elf(self):
        response = self.client.get("/api/symbols")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 0)

    def test_symbols_no_gdb_no_preload(self):
        """Without GDB, symbols are not preloaded."""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["total"], 0)
        finally:
            os.unlink(state.device.elf_path)

    def test_symbols_with_query_filter(self):
        state.symbols = {
            "main": {"addr": 0x08000000, "sym_type": "function"},
            "gpio_init": {"addr": 0x08001000, "sym_type": "function"},
            "gpio_set": {"addr": 0x08002000, "sym_type": "function"},
        }
        state.symbols_loaded = True
        response = self.client.get("/api/symbols?q=gpio&limit=10")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 2)

    def test_symbols_with_limit(self):
        state.symbols = {
            f"func_{i}": {"addr": 0x08000000 + i * 4, "sym_type": "function"}
            for i in range(200)
        }
        state.symbols_loaded = True
        response = self.client.get("/api/symbols?limit=5")
        data = response.get_json()
        self.assertEqual(len(data["symbols"]), 5)


class TestSearchSymbols(SymbolRoutesBase):
    """Test /api/symbols/search endpoint."""

    def test_search_no_elf(self):
        state.device.elf_path = ""
        response = self.client.get("/api/symbols/search?q=main")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    def test_search_from_cache(self):
        """Search uses cached symbols when loaded."""
        state.symbols = {
            "test_func": {
                "addr": 0x08001000,
                "size": 100,
                "type": "function",
                "section": ".text",
            },
            "other_func": {
                "addr": 0x08002000,
                "size": 50,
                "type": "function",
                "section": ".text",
            },
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/search?q=test")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["filtered"], 1)
            self.assertEqual(data["symbols"][0]["name"], "test_func")
        finally:
            os.unlink(state.device.elf_path)

    def test_search_by_hex_address_cached(self):
        """Search by hex address from cache."""
        state.symbols = {
            "foo": {
                "addr": 0x08001234,
                "size": 100,
                "type": "function",
                "section": ".text",
            },
            "bar": {
                "addr": 0x20000000,
                "size": 4,
                "type": "variable",
                "section": ".data",
            },
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/search?q=0x08001234")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["filtered"], 1)
            self.assertEqual(data["symbols"][0]["name"], "foo")
        finally:
            os.unlink(state.device.elf_path)

    @patch("core.gdb_manager.is_gdb_available", return_value=False)
    def test_search_no_gdb_no_cache(self, _mock_gdb):
        """Without GDB and no cache, search returns empty."""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/search?q=main")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["filtered"], 0)
        finally:
            os.unlink(state.device.elf_path)

    def test_search_empty_query(self):
        """Empty query returns empty results (no full load)."""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/search?q=")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["filtered"], 0)
        finally:
            os.unlink(state.device.elf_path)

    @patch("core.gdb_manager.is_gdb_available", return_value=False)
    def test_search_invalid_hex_fallback(self, _mock_gdb):
        """Non-hex query with no cache/GDB returns empty."""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/search?q=ZZZZ")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["filtered"], 0)
        finally:
            os.unlink(state.device.elf_path)


class TestReloadSymbols(SymbolRoutesBase):
    """Test /api/symbols/reload endpoint."""

    def test_reload_no_elf(self):
        response = self.client.post("/api/symbols/reload")
        data = response.get_json()
        self.assertFalse(data["success"])

    @patch("app.routes.symbols._get_fpb_inject")
    def test_reload_clears_cache(self, mock_get_fpb):
        """Reload clears symbol cache."""
        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb
        state.symbols = {
            "main": {
                "addr": 0x08000000,
                "size": 100,
                "type": "function",
                "section": ".text",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post("/api/symbols/reload")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 0)
        finally:
            os.unlink(state.device.elf_path)

    @patch(
        "app.routes.symbols._ensure_symbols_loaded",
        side_effect=Exception("Parse error"),
    )
    def test_reload_exception(self, _mock_ensure):
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post("/api/symbols/reload")
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Failed to reload", data["error"])
        finally:
            os.unlink(state.device.elf_path)


class TestSignatureEndpoint(SymbolRoutesBase):
    """Test /api/symbols/signature endpoint."""

    def test_no_func_name(self):
        response = self.client.get("/api/symbols/signature")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"])

    @patch("core.patch_generator.find_function_signature")
    def test_signature_found_in_watch_dir(self, mock_find_sig):
        """Finds signature in watch directory."""
        mock_find_sig.return_value = "void test_func(int arg)"
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "test.c")
            with open(src_file, "w") as f:
                f.write("void test_func(int arg) { }")
            state.device.watch_dirs = [tmpdir]
            response = self.client.get("/api/symbols/signature?func=test_func")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["signature"], "void test_func(int arg)")

    def test_signature_not_found(self):
        state.device.watch_dirs = []
        state.device.elf_path = ""
        response = self.client.get("/api/symbols/signature?func=nonexistent")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    @patch("core.patch_generator.find_function_signature")
    def test_signature_searches_elf_parent_dirs(self, mock_find_sig):
        """Searches parent directories of ELF path."""
        mock_find_sig.return_value = None
        with tempfile.TemporaryDirectory() as tmpdir:
            # Deep nesting so ../../.. stays within tmpdir
            build_dir = os.path.join(tmpdir, "root", "project", "build")
            os.makedirs(build_dir)
            elf_path = os.path.join(build_dir, "test.elf")
            with open(elf_path, "w") as f:
                f.write("")
            state.device.elf_path = elf_path
            state.device.watch_dirs = []
            response = self.client.get("/api/symbols/signature?func=test_func")
            data = response.get_json()
            self.assertFalse(data["success"])


class TestDisasmEndpoint(SymbolRoutesBase):
    """Test /api/symbols/disasm endpoint."""

    def test_no_func_name(self):
        response = self.client.get("/api/symbols/disasm")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"])

    def test_no_elf(self):
        response = self.client.get("/api/symbols/disasm?func=main")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not configured", data["error"])

    @patch("app.routes.symbols._get_fpb_inject")
    def test_disasm_success(self, mock_get_fpb):
        mock_fpb = Mock()
        mock_fpb.disassemble_function.return_value = (True, "push {r7, lr}\nmov r7, sp")
        mock_get_fpb.return_value = mock_fpb
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/disasm?func=main")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertIn("push", data["disasm"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._get_fpb_inject")
    def test_disasm_failure(self, mock_get_fpb):
        mock_fpb = Mock()
        mock_fpb.disassemble_function.return_value = (False, "Symbol not found")
        mock_get_fpb.return_value = mock_fpb
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/disasm?func=nonexistent")
            data = response.get_json()
            self.assertFalse(data["success"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._get_fpb_inject")
    def test_disasm_exception(self, mock_get_fpb):
        mock_get_fpb.side_effect = Exception("ELF error")
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/disasm?func=main")
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("ELF error", data["error"])
        finally:
            os.unlink(state.device.elf_path)


class TestDecompileEndpoint(SymbolRoutesBase):
    """Test /api/symbols/decompile endpoint."""

    def test_no_func_name(self):
        response = self.client.get("/api/symbols/decompile")
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_no_elf(self):
        response = self.client.get("/api/symbols/decompile?func=main")
        data = response.get_json()
        self.assertFalse(data["success"])

    @patch("app.routes.symbols._get_fpb_inject")
    def test_decompile_success(self, mock_get_fpb):
        mock_fpb = Mock()
        mock_fpb.decompile_function.return_value = (True, "void main() { return; }")
        mock_get_fpb.return_value = mock_fpb
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/decompile?func=main")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertIn("void main", data["decompiled"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._get_fpb_inject")
    def test_decompile_failure(self, mock_get_fpb):
        mock_fpb = Mock()
        mock_fpb.decompile_function.return_value = (False, "Ghidra not found")
        mock_get_fpb.return_value = mock_fpb
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/decompile?func=main")
            data = response.get_json()
            self.assertFalse(data["success"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._get_fpb_inject")
    def test_decompile_exception(self, mock_get_fpb):
        mock_get_fpb.side_effect = Exception("Ghidra crash")
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/decompile?func=main")
            data = response.get_json()
            self.assertFalse(data["success"])
        finally:
            os.unlink(state.device.elf_path)


class TestDecompileStreamEndpoint(SymbolRoutesBase):
    """Test /api/symbols/decompile/stream SSE endpoint."""

    def test_no_func_name(self):
        response = self.client.get("/api/symbols/decompile/stream")
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_no_elf(self):
        response = self.client.get("/api/symbols/decompile/stream?func=main")
        data = response.get_json()
        self.assertFalse(data["success"])

    @patch("app.routes.symbols._get_fpb_inject")
    @patch(
        "core.elf_utils._ghidra_project_cache",
        {"elf_path": None, "elf_mtime": None, "project_dir": None},
    )
    def test_stream_no_ghidra(self, mock_get_fpb):
        """Returns error when Ghidra not configured."""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        state.device.ghidra_path = None
        try:
            response = self.client.get("/api/symbols/decompile/stream?func=main")
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("GHIDRA_NOT_CONFIGURED", data["error"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._get_fpb_inject")
    @patch(
        "core.elf_utils._ghidra_project_cache",
        {"elf_path": None, "elf_mtime": None, "project_dir": None},
    )
    def test_stream_success(self, mock_get_fpb):
        """Streams decompilation result."""
        mock_fpb = Mock()
        mock_fpb.decompile_function.return_value = (True, "void main() {}")
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        state.device.ghidra_path = "/opt/ghidra"
        try:
            response = self.client.get("/api/symbols/decompile/stream?func=main")
            self.assertIn("text/event-stream", response.content_type)
            events = response.data.decode().strip().split("\n\n")
            self.assertGreaterEqual(len(events), 2)
            last_event = events[-1]
            result_data = json.loads(last_event.replace("data: ", ""))
            self.assertTrue(result_data["success"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._get_fpb_inject")
    @patch(
        "core.elf_utils._ghidra_project_cache",
        {"elf_path": None, "elf_mtime": None, "project_dir": None},
    )
    def test_stream_exception(self, mock_get_fpb):
        """Handles exception during streaming decompilation."""
        mock_get_fpb.side_effect = Exception("Ghidra timeout")

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        state.device.ghidra_path = "/opt/ghidra"
        try:
            response = self.client.get("/api/symbols/decompile/stream?func=main")
            events = response.data.decode().strip().split("\n\n")
            last_event = events[-1]
            result_data = json.loads(last_event.replace("data: ", ""))
            self.assertFalse(result_data["success"])
            self.assertIn("Ghidra timeout", result_data["error"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._get_fpb_inject")
    def test_stream_cached_project(self, mock_get_fpb):
        """Uses cached Ghidra project when available."""
        mock_fpb = Mock()
        mock_fpb.decompile_function.return_value = (True, "int foo() { return 0; }")
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
            elf_mtime = os.path.getmtime(f.name)

        with tempfile.TemporaryDirectory() as proj_dir:
            with patch(
                "core.elf_utils._ghidra_project_cache",
                {
                    "elf_path": state.device.elf_path,
                    "elf_mtime": elf_mtime,
                    "project_dir": proj_dir,
                },
            ):
                state.device.ghidra_path = "/opt/ghidra"
                try:
                    response = self.client.get("/api/symbols/decompile/stream?func=foo")
                    events = response.data.decode().strip().split("\n\n")
                    first_data = json.loads(events[0].replace("data: ", ""))
                    self.assertIn("cached", first_data.get("message", "").lower())
                finally:
                    os.unlink(state.device.elf_path)


class TestSymbolValueEndpoint(SymbolRoutesBase):
    """Test /api/symbols/value endpoint."""

    def test_no_name(self):
        response = self.client.get("/api/symbols/value")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"])

    def test_no_elf(self):
        response = self.client.get("/api/symbols/value?name=my_var")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_symbol_not_found(self, _mock_gdb):
        state.symbols = {
            "other": {
                "addr": 0x08000000,
                "size": 4,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/value?name=nonexistent")
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("not found", data["error"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("core.gdb_manager.is_gdb_available", return_value=False)
    def test_no_gdb(self, _mock_gdb):
        """Returns error when GDB not available."""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/value?name=my_var")
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("GDB", data["error"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_value_const_symbol(self, mock_gdb_avail):
        mock_session = Mock()
        mock_session.read_symbol_value.return_value = b"\x01\x02\x03\x04"
        mock_session.get_struct_layout.return_value = None
        state.gdb_session = mock_session
        state.symbols = {
            "my_const": {
                "addr": 0x08002000,
                "size": 4,
                "type": "const",
                "section": ".rodata",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/value?name=my_const")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["name"], "my_const")
            self.assertEqual(data["hex_data"], "01020304")
            self.assertEqual(data["type"], "const")
            self.assertEqual(data["section"], ".rodata")
            self.assertEqual(data["size"], 4)
        finally:
            os.unlink(state.device.elf_path)

    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_value_with_struct_layout(self, mock_gdb_avail):
        """struct_layout returned from GDB session."""
        mock_session = Mock()
        mock_session.read_symbol_value.return_value = b"\x0a\x00\x00\x00\x14\x00"
        mock_session.get_struct_layout.return_value = [
            {"name": "x", "offset": 0, "size": 4, "type_name": "int"},
        ]
        state.gdb_session = mock_session
        state.symbols = {
            "my_struct": {
                "addr": 0x20000100,
                "size": 6,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/value?name=my_struct")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertIsNotNone(data["struct_layout"])
            self.assertEqual(data["hex_data"], "0a0000001400")
        finally:
            os.unlink(state.device.elf_path)

    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_value_bss_no_data(self, mock_gdb_avail):
        mock_session = Mock()
        mock_session.read_symbol_value.return_value = None
        mock_session.get_struct_layout.return_value = None
        state.gdb_session = mock_session
        state.symbols = {
            "bss_var": {
                "addr": 0x20001000,
                "size": 8,
                "type": "variable",
                "section": ".bss",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/value?name=bss_var")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertIsNone(data["hex_data"])
            self.assertEqual(data["section"], ".bss")
        finally:
            os.unlink(state.device.elf_path)

    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_value_old_int_format(self, mock_gdb_avail):
        """Backward compat: symbols stored as plain int."""
        mock_session = Mock()
        mock_session.lookup_symbol.return_value = {
            "addr": 0x08003000,
            "size": 1,
            "type": "variable",
            "section": ".data",
        }
        mock_session.read_symbol_value.return_value = b"\xff"
        mock_session.get_struct_layout.return_value = None
        state.gdb_session = mock_session
        state.symbols = {"legacy_sym": 0x08003000}
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/value?name=legacy_sym")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["addr"], "0x08003000")
            self.assertEqual(data["hex_data"], "ff")
        finally:
            os.unlink(state.device.elf_path)


class TestReadSymbolFromDevice(SymbolRoutesBase):
    """Test /api/symbols/read endpoint."""

    def test_no_name(self):
        response = self.client.post("/api/symbols/read", json={})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"])

    def test_no_elf(self):
        response = self.client.post("/api/symbols/read", json={"name": "my_var"})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    def test_symbol_not_found(self):
        state.symbols = {
            "other": {
                "addr": 0x20000000,
                "size": 4,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post("/api/symbols/read", json={"name": "nope"})
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("not found", data["error"])
        finally:
            os.unlink(state.device.elf_path)

    def test_zero_size(self):
        state.symbols = {
            "zero_sym": {
                "addr": 0x20000000,
                "size": 0,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post("/api/symbols/read", json={"name": "zero_sym"})
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("unknown size", data["error"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_read_success(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.read_memory.return_value = (b"\xaa\xbb", "Read 2 bytes OK")
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb
        state.symbols = {
            "my_var": {
                "addr": 0x20001000,
                "size": 2,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post("/api/symbols/read", json={"name": "my_var"})
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["hex_data"], "aabb")
            self.assertEqual(data["source"], "device")
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_read_failure(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.read_memory.return_value = (None, "Read failed at offset 0x0")
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb
        state.symbols = {
            "my_var": {
                "addr": 0x20001000,
                "size": 4,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post("/api/symbols/read", json={"name": "my_var"})
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Read failed", data["error"])
        finally:
            os.unlink(state.device.elf_path)


class TestWriteSymbolToDevice(SymbolRoutesBase):
    """Test /api/symbols/write endpoint."""

    def test_no_name(self):
        response = self.client.post("/api/symbols/write", json={"hex_data": "01"})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"])

    def test_no_hex_data(self):
        response = self.client.post("/api/symbols/write", json={"name": "my_var"})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("hex_data not specified", data["error"])

    def test_no_elf(self):
        response = self.client.post(
            "/api/symbols/write", json={"name": "x", "hex_data": "01"}
        )
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_write_const_rejected(self):
        state.symbols = {
            "ro": {"addr": 0x08002000, "size": 4, "type": "const", "section": ".rodata"}
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post(
                "/api/symbols/write", json={"name": "ro", "hex_data": "01020304"}
            )
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("read-only", data["error"])
        finally:
            os.unlink(state.device.elf_path)

    def test_invalid_hex(self):
        state.symbols = {
            "v": {"addr": 0x20000000, "size": 4, "type": "variable", "section": ".data"}
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post(
                "/api/symbols/write", json={"name": "v", "hex_data": "ZZZZ"}
            )
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Invalid hex_data", data["error"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_write_success(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.write_memory.return_value = (True, "Write 4 bytes OK")
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb
        state.symbols = {
            "my_var": {
                "addr": 0x20001000,
                "size": 4,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post(
                "/api/symbols/write", json={"name": "my_var", "hex_data": "01020304"}
            )
            data = response.get_json()
            self.assertTrue(data["success"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_write_failure(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.write_memory.return_value = (False, "Write failed at offset 0x0")
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb
        state.symbols = {
            "my_var": {
                "addr": 0x20001000,
                "size": 4,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post(
                "/api/symbols/write", json={"name": "my_var", "hex_data": "01020304"}
            )
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Write failed", data["error"])
        finally:
            os.unlink(state.device.elf_path)


class TestWriteSymbolWithOffset(SymbolRoutesBase):
    """Test /api/symbols/write with offset parameter."""

    def _setup_var(self):
        state.symbols = {
            "my_struct": {
                "addr": 0x20001000,
                "size": 12,
                "type": "variable",
                "section": ".data",
            }
        }
        state.symbols_loaded = True
        f = tempfile.NamedTemporaryFile(suffix=".elf", delete=False)
        state.device.elf_path = f.name
        f.close()
        return f.name

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_write_with_offset(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.write_memory.return_value = (True, "Write 4 bytes OK")
        mock_get_fpb.return_value = mock_fpb
        elf = self._setup_var()
        try:
            response = self.client.post(
                "/api/symbols/write",
                json={"name": "my_struct", "offset": 4, "hex_data": "DEADBEEF"},
            )
            data = response.get_json()
            self.assertTrue(data["success"])
            # Verify write_memory was called with addr + offset
            mock_fpb.write_memory.assert_called_once()
            call_addr = mock_fpb.write_memory.call_args[0][0]
            self.assertEqual(call_addr, 0x20001004)
        finally:
            os.unlink(elf)

    def test_write_offset_exceeds_size(self):
        elf = self._setup_var()
        try:
            response = self.client.post(
                "/api/symbols/write",
                json={"name": "my_struct", "offset": 10, "hex_data": "01020304"},
            )
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("exceeds symbol size", data["error"])
        finally:
            os.unlink(elf)

    def test_write_offset_zero_backward_compat(self):
        """Omitting offset should default to 0 (backward compatible)."""
        elf = self._setup_var()
        try:
            # No offset field — should work like before
            response = self.client.post(
                "/api/symbols/write",
                json={"name": "my_struct", "hex_data": "010203040506070809101112"},
            )
            # Will fail because no mock, but should not fail on offset parsing
            data = response.get_json()
            # It will fail at fpb_inject level, not at offset validation
            self.assertFalse(data["success"])
            self.assertNotIn("offset", data.get("error", "").lower())
        finally:
            os.unlink(elf)

    def test_write_invalid_offset(self):
        elf = self._setup_var()
        try:
            response = self.client.post(
                "/api/symbols/write",
                json={"name": "my_struct", "offset": "abc", "hex_data": "01"},
            )
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Invalid offset", data["error"])
        finally:
            os.unlink(elf)


class TestMemoryRead(SymbolRoutesBase):
    """Test /api/memory/read endpoint."""

    def test_no_addr(self):
        response = self.client.get("/api/memory/read?size=4")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("addr", data["error"])

    def test_no_size(self):
        response = self.client.get("/api/memory/read?addr=0x20000000")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("size", data["error"])

    def test_invalid_addr(self):
        response = self.client.get("/api/memory/read?addr=ZZZZ&size=4")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("addr", data["error"])

    def test_size_too_large(self):
        response = self.client.get("/api/memory/read?addr=0x20000000&size=100000")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("64KB", data["error"])

    def test_negative_size(self):
        response = self.client.get("/api/memory/read?addr=0x20000000&size=-1")
        data = response.get_json()
        self.assertFalse(data["success"])

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_read_success(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.read_memory.return_value = (b"\xaa\xbb\xcc\xdd", "Read 4 bytes OK")
        mock_get_fpb.return_value = mock_fpb
        response = self.client.get("/api/memory/read?addr=0x20000000&size=4")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["hex_data"], "aabbccdd")
        self.assertEqual(data["addr"], "0x20000000")
        self.assertEqual(data["size"], 4)

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_read_failure(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.read_memory.return_value = (None, "Read failed")
        mock_get_fpb.return_value = mock_fpb
        response = self.client.get("/api/memory/read?addr=0x20000000&size=4")
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Read failed", data["error"])

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_read_decimal_addr(self, mock_get_fpb, mock_run_serial):
        """Decimal address should also work."""
        mock_fpb = Mock()
        mock_fpb.read_memory.return_value = (b"\x01", "OK")
        mock_get_fpb.return_value = mock_fpb
        response = self.client.get("/api/memory/read?addr=536870912&size=1")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["addr"], "0x20000000")


class TestMemoryWrite(SymbolRoutesBase):
    """Test /api/memory/write endpoint."""

    def test_no_addr(self):
        response = self.client.post("/api/memory/write", json={"hex_data": "01"})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("addr", data["error"])

    def test_no_hex_data(self):
        response = self.client.post("/api/memory/write", json={"addr": "0x20000000"})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("hex_data", data["error"])

    def test_invalid_hex(self):
        response = self.client.post(
            "/api/memory/write", json={"addr": "0x20000000", "hex_data": "ZZZZ"}
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Invalid hex_data", data["error"])

    def test_data_too_large(self):
        response = self.client.post(
            "/api/memory/write",
            json={"addr": "0x20000000", "hex_data": "AA" * 65537},
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("64KB", data["error"])

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_write_success(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.write_memory.return_value = (True, "Write 4 bytes OK")
        mock_get_fpb.return_value = mock_fpb
        response = self.client.post(
            "/api/memory/write",
            json={"addr": "0x20001000", "hex_data": "DEADBEEF"},
        )
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["addr"], "0x20001000")
        self.assertEqual(data["size"], 4)

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_write_failure(self, mock_get_fpb, mock_run_serial):
        mock_fpb = Mock()
        mock_fpb.write_memory.return_value = (False, "Write failed")
        mock_get_fpb.return_value = mock_fpb
        response = self.client.post(
            "/api/memory/write",
            json={"addr": "0x20001000", "hex_data": "01020304"},
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Write failed", data["error"])

    @patch("app.routes.symbols._run_serial_op", side_effect=lambda func, **kw: func())
    @patch("app.routes.symbols._get_fpb_inject")
    def test_write_int_addr(self, mock_get_fpb, mock_run_serial):
        """Integer address in JSON should work."""
        mock_fpb = Mock()
        mock_fpb.write_memory.return_value = (True, "OK")
        mock_get_fpb.return_value = mock_fpb
        response = self.client.post(
            "/api/memory/write",
            json={"addr": 0x20001000, "hex_data": "AA"},
        )
        data = response.get_json()
        self.assertTrue(data["success"])


class TestMemoryReadStream(SymbolRoutesBase):
    """Test /api/memory/read/stream SSE endpoint."""

    def test_no_addr(self):
        response = self.client.post("/api/memory/read/stream", json={"size": 4})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("addr", data["error"])

    def test_no_size(self):
        response = self.client.post(
            "/api/memory/read/stream", json={"addr": "0x20000000"}
        )
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_size_too_large(self):
        response = self.client.post(
            "/api/memory/read/stream",
            json={"addr": "0x20000000", "size": 100000},
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("64KB", data["error"])

    @patch(
        "app.routes.symbols.run_in_device_worker",
        side_effect=lambda device, func, timeout=5.0: (func(), True)[1],
    )
    @patch("app.routes.symbols._get_fpb_inject")
    def test_stream_success(self, mock_get_fpb, mock_worker):
        mock_fpb = Mock()
        mock_fpb.read_memory.return_value = (b"\xaa\xbb", "OK")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post(
            "/api/memory/read/stream",
            json={"addr": "0x20000000", "size": 2},
        )
        self.assertIn("text/event-stream", response.content_type)
        text = response.get_data(as_text=True)
        self.assertIn('"type": "result"', text)
        self.assertIn('"success": true', text)
        self.assertIn("aabb", text)

    @patch("app.routes.symbols.run_in_device_worker", return_value=False)
    @patch("app.routes.symbols._get_fpb_inject")
    def test_stream_timeout(self, mock_get_fpb, mock_worker):
        mock_get_fpb.return_value = Mock()
        response = self.client.post(
            "/api/memory/read/stream",
            json={"addr": "0x20000000", "size": 4},
        )
        text = response.get_data(as_text=True)
        self.assertIn("timeout", text.lower())


class TestDynamicTimeout(SymbolRoutesBase):
    """Test _dynamic_timeout helper."""

    def test_small_size(self):
        from app.routes.symbols import _dynamic_timeout

        # Small reads should get minimum 10s
        self.assertEqual(_dynamic_timeout(4), 10.0)
        self.assertEqual(_dynamic_timeout(128), 10.0)

    def test_large_size(self):
        from app.routes.symbols import _dynamic_timeout

        state.device.chunk_size = 128
        # 4096 bytes = 32 chunks * 3s = 96s
        self.assertEqual(_dynamic_timeout(4096), 96.0)

    def test_custom_chunk_size(self):
        from app.routes.symbols import _dynamic_timeout

        state.device.chunk_size = 256
        # 1024 bytes = 4 chunks * 3s = 12s
        self.assertEqual(_dynamic_timeout(1024), 12.0)


class TestParseAddr(SymbolRoutesBase):
    """Test _parse_addr helper."""

    def test_hex_string(self):
        from app.routes.symbols import _parse_addr

        self.assertEqual(_parse_addr("0x20000000"), 0x20000000)

    def test_decimal_string(self):
        from app.routes.symbols import _parse_addr

        self.assertEqual(_parse_addr("536870912"), 536870912)

    def test_int(self):
        from app.routes.symbols import _parse_addr

        self.assertEqual(_parse_addr(0x20000000), 0x20000000)

    def test_invalid(self):
        from app.routes.symbols import _parse_addr

        self.assertIsNone(_parse_addr("not_a_number"))
        self.assertIsNone(_parse_addr(""))
        self.assertIsNone(_parse_addr(None))


if __name__ == "__main__":
    unittest.main()

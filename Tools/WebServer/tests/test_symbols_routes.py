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


class TestGetSymbols(SymbolRoutesBase):
    """Test /api/symbols endpoint."""

    def test_symbols_not_loaded_no_elf(self):
        response = self.client.get("/api/symbols")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 0)

    @patch("app.routes.symbols._get_fpb_inject")
    def test_symbols_auto_load(self, mock_get_fpb):
        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {"main": 0x08000000, "foo": 0x08001000}
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["total"], 2)
            self.assertTrue(state.symbols_loaded)
        finally:
            os.unlink(state.device.elf_path)

    def test_symbols_with_query_filter(self):
        state.symbols = {
            "main": 0x08000000,
            "gpio_init": 0x08001000,
            "gpio_set": 0x08002000,
        }
        state.symbols_loaded = True
        response = self.client.get("/api/symbols?q=gpio&limit=10")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 2)

    def test_symbols_with_limit(self):
        state.symbols = {f"func_{i}": 0x08000000 + i * 4 for i in range(200)}
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

    @patch("app.routes.symbols._get_fpb_inject")
    def test_search_load_failure(self, mock_get_fpb):
        mock_get_fpb.side_effect = Exception("ELF parse error")
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.get("/api/symbols/search?q=main")
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Failed to load", data["error"])
        finally:
            os.unlink(state.device.elf_path)

    def test_search_by_name(self):
        state.symbols = {"main": 0x08000000, "test_func": 0x08001000}
        state.symbols_loaded = True
        response = self.client.get("/api/symbols/search?q=test")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 1)
        self.assertEqual(data["symbols"][0]["name"], "test_func")

    def test_search_by_hex_address(self):
        state.symbols = {"main": 0x08000000, "foo": 0x08001234}
        state.symbols_loaded = True
        response = self.client.get("/api/symbols/search?q=0x08001234")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 1)
        self.assertEqual(data["symbols"][0]["name"], "foo")

    def test_search_by_partial_hex(self):
        state.symbols = {"main": 0x08000000, "foo": 0x08001234}
        state.symbols_loaded = True
        response = self.client.get("/api/symbols/search?q=08001")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 1)

    def test_search_empty_query(self):
        state.symbols = {"a": 1, "b": 2}
        state.symbols_loaded = True
        response = self.client.get("/api/symbols/search?q=")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 2)

    def test_search_invalid_hex_fallback(self):
        state.symbols = {"0xDEAD_func": 0x08000000, "other": 0x08001000}
        state.symbols_loaded = True
        response = self.client.get("/api/symbols/search?q=ZZZZ")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 0)


class TestReloadSymbols(SymbolRoutesBase):
    """Test /api/symbols/reload endpoint."""

    def test_reload_no_elf(self):
        response = self.client.post("/api/symbols/reload")
        data = response.get_json()
        self.assertFalse(data["success"])

    @patch("app.routes.symbols._get_fpb_inject")
    def test_reload_success(self, mock_get_fpb):
        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {"main": 0x08000000}
        mock_get_fpb.return_value = mock_fpb
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name
        try:
            response = self.client.post("/api/symbols/reload")
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 1)
        finally:
            os.unlink(state.device.elf_path)

    @patch("app.routes.symbols._get_fpb_inject")
    def test_reload_exception(self, mock_get_fpb):
        mock_get_fpb.side_effect = Exception("Parse error")
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


if __name__ == "__main__":
    unittest.main()

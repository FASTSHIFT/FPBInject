#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the public SDK facade (fpbinject.Client).

Proxy methods are exercised against a mock HTTP server; offline methods and
mode guards use mocks. Verifies the SDK delegates correctly and that the
public surface matches the CLI capability set.
"""

import http.server
import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject import (  # noqa: E402
    Client,
    FPBError,
    ServerUnavailable,
    DiscoveredServer,
)
from fixtures.mock_http import MockHTTPHandler as _MockHTTPHandler  # noqa: E402


class TestClientConstruction(unittest.TestCase):
    def test_offline_mode_flags(self):
        c = Client.offline()
        self.assertFalse(c.connected)

    def test_offline_proxy_methods_raise(self):
        c = Client.offline()
        for call in (
            lambda: c.info(),
            lambda: c.serial_send("x"),
            lambda: c.file_list("/"),
            lambda: c.vserial_status(),
        ):
            with self.assertRaises(FPBError):
                call()

    def test_token_from_env(self):
        with patch.dict(os.environ, {"FPB_TOKEN": "envtok"}):
            c = Client("http://127.0.0.1:5500")
            self.assertEqual(c._proxy.token, "envtok")

    def test_explicit_token_wins(self):
        with patch.dict(os.environ, {"FPB_TOKEN": "envtok"}):
            c = Client("http://127.0.0.1:5500", token="explicit")
            self.assertEqual(c._proxy.token, "explicit")


class TestClientDiscover(unittest.TestCase):
    def _mk(self, handle, url):
        return DiscoveredServer(
            name=handle,
            host=handle.split(":")[0],
            port=5500,
            url=url,
            version="1",
            auth="none",
            handle=handle,
        )

    def test_discover_single(self):
        srv = self._mk("h1:5500", "http://h1:5500")
        with patch.object(Client, "list_servers", return_value=[srv]):
            c = Client.discover()
            self.assertEqual(c._proxy.base_url, "http://h1:5500")

    def test_discover_none_raises(self):
        with patch.object(Client, "list_servers", return_value=[]):
            with self.assertRaises(ServerUnavailable):
                Client.discover()

    def test_discover_ambiguous_raises(self):
        servers = [
            self._mk("h1:5500", "http://h1:5500"),
            self._mk("h2:5500", "http://h2:5500"),
        ]
        with patch.object(Client, "list_servers", return_value=servers):
            with self.assertRaises(ServerUnavailable):
                Client.discover()

    def test_discover_by_handle(self):
        servers = [
            self._mk("h1:5500", "http://h1:5500"),
            self._mk("h2:5500", "http://h2:5500"),
        ]
        with patch.object(Client, "list_servers", return_value=servers):
            c = Client.discover(handle="h2:5500")
            self.assertEqual(c._proxy.base_url, "http://h2:5500")


class TestClientProxyMethods(unittest.TestCase):
    """Delegate proxy methods against a mock WebServer."""

    @classmethod
    def setUpClass(cls):
        _MockHTTPHandler.responses = {
            "/api/status": {"success": True, "connected": True},
            "/api/fpb/info": {"success": True, "info": {"num_comparators": 6}},
            "/api/fpb/unpatch": {"success": True},
            "/api/fpb/mem-read": {"success": True, "data": "deadbeef"},
            "/api/fpb/mem-write": {"success": True},
            "/api/transfer/list": {"success": True, "entries": []},
            "/api/transfer/stat": {"success": True, "stat": {"size": 1}},
            "/api/transfer/delete": {"success": True},
            "/api/transfer/mkdir": {"success": True},
            "/api/transfer/rename": {"success": True},
            "/api/vserial/status": {"success": True, "enabled": False},
            "/api/vserial/start": {"success": True, "enabled": True},
            "/api/vserial/stop": {"success": True},
        }
        _MockHTTPHandler.sse_responses = {}
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHTTPHandler)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.t = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _client(self):
        return Client(self.base)

    def test_info(self):
        self.assertEqual(self._client().info()["info"]["num_comparators"], 6)

    def test_status(self):
        self.assertTrue(self._client().status()["success"])

    def test_connected_property(self):
        self.assertTrue(self._client().connected)

    def test_unpatch(self):
        self.assertTrue(self._client().unpatch(all=True)["success"])

    def test_mem_read(self):
        self.assertEqual(self._client().mem_read(0x2000, 4)["data"], "deadbeef")

    def test_mem_dump_writes_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "sub", "dump.bin")
            res = self._client().mem_dump(0x2000, 4, out)
            self.assertTrue(res["success"])
            self.assertEqual(open(out, "rb").read(), bytes.fromhex("deadbeef"))

    def test_file_list_and_stat(self):
        c = self._client()
        self.assertTrue(c.file_list("/data")["success"])
        self.assertEqual(c.file_stat("/x")["stat"]["size"], 1)

    def test_file_mutations(self):
        c = self._client()
        self.assertTrue(c.file_remove("/a")["success"])
        self.assertTrue(c.file_mkdir("/b")["success"])
        self.assertTrue(c.file_rename("/a", "/b")["success"])

    def test_vserial(self):
        c = self._client()
        self.assertFalse(c.vserial_status()["enabled"])
        self.assertTrue(c.vserial_start()["enabled"])
        self.assertTrue(c.vserial_stop()["success"])

    def test_wake_calls_file_stat(self):
        self.assertTrue(self._client().wake()["success"])


class TestClientOffline(unittest.TestCase):
    """Offline ELF methods delegate to FPBInject (mocked)."""

    def _client_with_mock_fpb(self, fpb):
        c = Client.offline()
        c._fpb = fpb
        return c

    def test_signature(self):
        fpb = MagicMock()
        fpb.get_signature.return_value = "void f(int)"
        c = self._client_with_mock_fpb(fpb)
        self.assertEqual(c.signature("fw.elf", "f"), "void f(int)")

    def test_disasm(self):
        fpb = MagicMock()
        fpb.disassemble_function.return_value = (True, "push {r0}\nbx lr")
        c = self._client_with_mock_fpb(fpb)
        out = c.disasm("fw.elf", "f")
        self.assertTrue(out["success"])
        self.assertIn("push", out["disasm"])

    def test_search(self):
        fpb = MagicMock()
        fpb.get_symbols.return_value = {"foo": 0x100, "bar": 0x200, "foobar": 0x300}
        c = self._client_with_mock_fpb(fpb)
        out = c.search("fw.elf", "foo")
        self.assertEqual(out["count"], 2)

    def test_get_symbols_filter_limit(self):
        fpb = MagicMock()
        fpb.get_symbols.return_value = {f"s{i}": i for i in range(10)}
        c = self._client_with_mock_fpb(fpb)
        out = c.get_symbols("fw.elf", filter="s", limit=3)
        self.assertEqual(len(out["symbols"]), 3)

    def test_analyze_missing_func_raises(self):
        fpb = MagicMock()
        fpb.get_symbols.return_value = {"foo": 0x100}
        c = self._client_with_mock_fpb(fpb)
        with self.assertRaises(FPBError):
            c.analyze("fw.elf", "nope")


class TestCapabilityParity(unittest.TestCase):
    """Every CLI subcommand should have a corresponding Client method."""

    def test_all_cli_subcommands_have_sdk_methods(self):
        mapping = {
            "analyze": "analyze",
            "disasm": "disasm",
            "decompile": "decompile",
            "signature": "signature",
            "search": "search",
            "get-symbols": "get_symbols",
            "compile": "compile",
            "info": "info",
            "test-serial": "test_serial",
            "inject": "inject",
            "unpatch": "unpatch",
            "mem-read": "mem_read",
            "mem-write": "mem_write",
            "mem-dump": "mem_dump",
            "serial-send": "serial_send",
            "serial-read": "serial_read",
            "file-list": "file_list",
            "file-stat": "file_stat",
            "file-download": "file_download",
            "file-upload": "file_upload",
            "file-remove": "file_remove",
            "file-mkdir": "file_mkdir",
            "file-rename": "file_rename",
            "connect": "connect",
            "disconnect": "disconnect",
            "vserial-start": "vserial_start",
            "vserial-status": "vserial_status",
            "vserial-stop": "vserial_stop",
        }
        for cli_cmd, method in mapping.items():
            self.assertTrue(
                hasattr(Client, method),
                f"Client missing method {method!r} for CLI '{cli_cmd}'",
            )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
Tests for remaining CLI-GUI coexistence phases.

Phase 1: DeviceStateBase inheritance
Phase 3: WebServer PortLock integration
Phase 4: mem-read / mem-write API routes
Proxy support for file_list, file_stat, file_download, mem_dump, test_serial
"""

import base64
import http.server
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from fpbinject.core.state import DeviceStateBase, DeviceState
from fpbinject.cli.fpb_cli import DeviceState as CLIDeviceState, FPBCLI
from fpbinject.cli.server_proxy import ServerProxy

# ============================================================
# Phase 1: DeviceStateBase inheritance tests
# ============================================================


class TestDeviceStateBaseInheritance(unittest.TestCase):
    """Verify both CLI and WebServer DeviceState inherit from DeviceStateBase."""

    def test_cli_device_state_is_subclass(self):
        self.assertTrue(issubclass(CLIDeviceState, DeviceStateBase))

    def test_webserver_device_state_is_subclass(self):
        self.assertTrue(issubclass(DeviceState, DeviceStateBase))

    def test_cli_device_state_has_base_fields(self):
        ds = CLIDeviceState()
        self.assertIsNone(ds.ser)
        self.assertIsNone(ds.elf_path)
        self.assertEqual(ds.ram_start, 0x20000000)
        self.assertEqual(ds.ram_size, 0x10000)
        self.assertEqual(ds.inject_base, 0x20001000)
        self.assertEqual(ds.upload_chunk_size, 128)
        self.assertEqual(ds.download_chunk_size, 1024)
        self.assertEqual(ds.transfer_max_retries, 10)

    def test_cli_device_state_has_connected(self):
        ds = CLIDeviceState()
        self.assertFalse(ds.connected)

    def test_webserver_device_state_has_base_fields(self):
        ds = DeviceState()
        self.assertIsNone(ds.ser)
        self.assertEqual(ds.ram_start, 0x20000000)

    def test_base_add_tool_log_is_noop(self):
        base = DeviceStateBase()
        base.add_tool_log("test")  # Should not raise


# ============================================================
# Phase 4: mem-read / mem-write API route tests
# ============================================================


class TestMemReadWriteRoutes(unittest.TestCase):
    """Test /api/fpb/mem-read and /api/fpb/mem-write routes."""

    def setUp(self):
        from fpbinject.app.routes.fpb import bp
        from flask import Flask

        self.app = Flask(__name__)
        self.app.register_blueprint(bp, url_prefix="/api")
        self.client = self.app.test_client()

    @patch("fpbinject.app.routes.fpb._run_serial_op")
    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_mem_read_hex(self, mock_helpers, mock_run):
        mock_helpers.return_value = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        mock_run.return_value = {
            "success": True,
            "addr": "0x20000000",
            "length": 16,
            "actual_length": 16,
            "hex_dump": "0x20000000: 00 01 02 03",
        }
        resp = self.client.post(
            "/api/fpb/mem-read",
            json={"addr": 0x20000000, "length": 16, "fmt": "hex"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])

    @patch("fpbinject.app.routes.fpb._run_serial_op")
    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_mem_write_success(self, mock_helpers, mock_run):
        mock_helpers.return_value = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        mock_run.return_value = {
            "success": True,
            "addr": "0x20000000",
            "length": 4,
            "message": "Wrote 4 bytes",
        }
        resp = self.client.post(
            "/api/fpb/mem-write",
            json={"addr": 0x20000000, "data": "DEADBEEF"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])

    def test_mem_write_invalid_hex(self):
        resp = self.client.post(
            "/api/fpb/mem-write",
            json={"addr": 0x20000000, "data": "ZZZZ"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Invalid hex", data["error"])

    @patch("fpbinject.app.routes.fpb._run_serial_op")
    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_mem_read_error(self, mock_helpers, mock_run):
        mock_helpers.return_value = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        mock_run.return_value = {"error": "Device timeout"}
        resp = self.client.post(
            "/api/fpb/mem-read",
            json={"addr": 0x20000000, "length": 16},
        )
        data = resp.get_json()
        self.assertFalse(data["success"])


# ============================================================
# Proxy support for new CLI commands
# ============================================================


class _MockHandler(http.server.BaseHTTPRequestHandler):
    """Mock HTTP handler for proxy tests."""

    responses = {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in self.responses:
            body = json.dumps(self.responses[path]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            self.rfile.read(content_length)
        path = self.path.split("?")[0]
        if path in self.responses:
            body = json.dumps(self.responses[path]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class TestServerProxyNewMethods(unittest.TestCase):
    """Test new ServerProxy methods: test_serial, file_list, file_stat, file_download."""

    @classmethod
    def setUpClass(cls):
        _MockHandler.responses = {
            "/api/status": {"success": True, "connected": True},
            "/api/fpb/test-serial": {
                "success": True,
                "recommended_upload_chunk_size": 128,
            },
            "/api/transfer/list": {
                "success": True,
                "entries": [{"name": "test.txt", "type": "file"}],
            },
            "/api/transfer/stat": {
                "success": True,
                "stat": {"size": 1024, "type": "file"},
            },
            "/api/transfer/download-sync": {
                "success": True,
                "data": base64.b64encode(b"hello world").decode(),
                "size": 11,
            },
            "/api/fpb/mem-read": {
                "success": True,
                "data": "48656C6C6F",
            },
        }
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _proxy(self):
        return ServerProxy(base_url=self.base_url)

    def test_test_serial(self):
        result = self._proxy().test_serial()
        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_upload_chunk_size"], 128)

    def test_file_list(self):
        result = self._proxy().file_list("/")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["entries"]), 1)

    def test_file_stat(self):
        result = self._proxy().file_stat("/test.txt")
        self.assertTrue(result["success"])
        self.assertEqual(result["stat"]["size"], 1024)

    def test_file_download(self):
        result = self._proxy().file_download("/test.txt")
        self.assertTrue(result["success"])
        self.assertEqual(result["size"], 11)


class TestCLIProxyNewCommands(unittest.TestCase):
    """Test CLI proxy mode for new commands."""

    @classmethod
    def setUpClass(cls):
        _MockHandler.responses = {
            "/api/status": {"success": True, "connected": True},
            "/api/fpb/test-serial": {
                "success": True,
                "recommended_upload_chunk_size": 128,
            },
            "/api/transfer/list": {
                "success": True,
                "path": "/",
                "entries": [{"name": "data", "type": "dir"}],
            },
            "/api/transfer/stat": {
                "success": True,
                "path": "/data/log.bin",
                "stat": {"size": 256, "type": "file"},
            },
            "/api/transfer/download-sync": {
                "success": True,
                "data": base64.b64encode(b"binary data here").decode(),
                "size": 16,
            },
            "/api/fpb/mem-read": {
                "success": True,
                "data": "AABBCCDD",
                "addr": "0x20000000",
                "length": 4,
                "actual_length": 4,
            },
        }
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHandler)
        cls.port = cls.server.server_address[1]
        cls.server_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _make_cli(self):
        return FPBCLI(port="/dev/ttyACM0", server_url=self.server_url)

    def test_proxy_test_serial(self):
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.test_serial()
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()

    def test_proxy_file_list(self):
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.file_list("/")
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()

    def test_proxy_file_stat(self):
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.file_stat("/data/log.bin")
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()

    def test_proxy_file_download(self):
        cli = self._make_cli()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            local_path = f.name
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.file_download("/data/log.bin", local_path)
            result = json.loads(buf.getvalue())
            self.assertTrue(result["success"])
            self.assertEqual(result["size"], 16)
            # Verify file was written
            with open(local_path, "rb") as f:
                self.assertEqual(f.read(), b"binary data here")
        finally:
            os.unlink(local_path)
            cli.cleanup()

    def test_proxy_mem_dump(self):
        cli = self._make_cli()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            local_path = f.name
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.mem_dump(0x20000000, 4, local_path)
            result = json.loads(buf.getvalue())
            self.assertTrue(result["success"])
            # Verify binary file
            with open(local_path, "rb") as f:
                self.assertEqual(f.read(), bytes.fromhex("AABBCCDD"))
        finally:
            os.unlink(local_path)
            cli.cleanup()


# ============================================================
# Phase 3: WebServer PortLock integration
# ============================================================


class TestWebServerPortLock(unittest.TestCase):
    """Test PortLock integration in WebServer connect/disconnect."""

    def test_connection_route_imports_port_lock(self):
        """Verify connection.py imports PortLock."""
        from fpbinject.app.routes import connection

        self.assertTrue(hasattr(connection, "PortLock"))

    def test_main_imports_port_lock(self):
        """Verify main.py imports PortLock."""
        import fpbinject.main as main

        self.assertTrue("PortLock" in dir(main) or hasattr(main, "PortLock"))

    def test_port_lock_context_manager(self):
        """PortLock works as context manager."""
        from fpbinject.utils.port_lock import PortLock

        with PortLock("/dev/test-ctx-mgr") as lock:
            self.assertIsNotNone(lock)
        # After exit, lock should be released

    def test_port_lock_context_manager_conflict(self):
        """PortLock context manager raises on conflict."""
        from fpbinject.utils.port_lock import PortLock, PortLockError

        lock1 = PortLock("/dev/test-ctx-conflict")
        self.assertTrue(lock1.acquire())
        try:
            with self.assertRaises(PortLockError):
                with PortLock("/dev/test-ctx-conflict"):
                    pass
        finally:
            lock1.release()

    def test_port_lock_is_locked(self):
        """is_locked returns correct state."""
        from fpbinject.utils.port_lock import PortLock

        lock = PortLock("/dev/test-is-locked")
        self.assertFalse(lock.is_locked())
        self.assertTrue(lock.acquire())
        # Another PortLock instance should see it as locked
        lock2 = PortLock("/dev/test-is-locked")
        self.assertTrue(lock2.is_locked())
        lock.release()
        self.assertFalse(lock2.is_locked())

    def test_port_lock_get_owner_pid_no_file(self):
        """get_owner_pid returns 'unknown' when no lock file."""
        from fpbinject.utils.port_lock import PortLock

        lock = PortLock("/dev/test-no-owner-file")
        self.assertEqual(lock.get_owner_pid(), "unknown")


if __name__ == "__main__":
    unittest.main()

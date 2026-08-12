#!/usr/bin/env python3
"""
Test cases for CLI-GUI coexistence features.

Tests the integration of ServerProxy and PortLock into FPBCLI.
"""

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
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from fpbinject.cli.fpb_cli import FPBCLI, FPBCLIError, main
from fpbinject.cli.server_proxy import ProxyAuthError
from fpbinject.utils.port_lock import PortLock


class _MockHandler(http.server.BaseHTTPRequestHandler):
    """Mock HTTP handler simulating WebServer API."""

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
        self.rfile.read(content_length) if content_length else b""
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


class TestFPBCLIProxyMode(unittest.TestCase):
    """Test FPBCLI proxy mode when WebServer is running."""

    @classmethod
    def setUpClass(cls):
        _MockHandler.responses = {
            "/api/status": {
                "success": True,
                "connected": True,
                "port": "/dev/ttyACM0",
            },
            "/api/fpb/info": {
                "success": True,
                "info": {"version": "1.0", "slots": 6},
            },
            "/api/fpb/inject": {"success": True, "result": "injected"},
            "/api/fpb/unpatch": {"success": True, "message": "unpatched"},
            "/api/fpb/mem-read": {"success": True, "hex_dump": "00 01 02"},
            "/api/fpb/mem-write": {"success": True, "message": "written"},
            "/api/connect": {"success": True, "port": "/dev/ttyACM0"},
            "/api/disconnect": {"success": True},
            "/api/serial/send": {"success": True, "sent": "test"},
            "/api/logs": {"raw_data": "output line\n", "raw_next": 1},
            "/api/fpb/test-serial": {
                "success": True,
                "recommended_upload_chunk_size": 128,
            },
        }
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHandler)
        cls.port = cls.server.server_address[1]
        cls.server_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _make_cli(self, port="/dev/ttyACM0"):
        """Create FPBCLI that will use proxy mode."""
        return FPBCLI(
            port=port,
            server_url=self.server_url,
        )

    def test_proxy_detected(self):
        """CLI detects running WebServer and enters proxy mode."""
        cli = self._make_cli()
        self.assertIsNotNone(cli._proxy)
        self.assertTrue(cli._device_state.connected)
        self.assertIsNone(cli._port_lock)
        cli.cleanup()

    def test_proxy_info(self):
        """info() works through proxy."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.info()
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        self.assertEqual(result["info"]["slots"], 6)
        cli.cleanup()

    def test_proxy_unpatch(self):
        """unpatch() works through proxy."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.unpatch(comp=0)
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()

    def test_proxy_inject(self):
        """inject() works through proxy."""
        cli = self._make_cli()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("/* FPB_INJECT */\nvoid test(void) {}\n")
            src = f.name
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.inject("test", src)
            result = json.loads(buf.getvalue())
            self.assertTrue(result["success"])
        finally:
            os.unlink(src)
            cli.cleanup()

    def test_proxy_mem_read(self):
        """mem_read() works through proxy."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.mem_read(0x20000000, 64)
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()

    def test_proxy_mem_write(self):
        """mem_write() works through proxy."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.mem_write(0x20000000, "DEADBEEF")
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()

    def test_proxy_connect(self):
        """connect() works through proxy."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.connect("/dev/ttyACM0")
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()

    def test_proxy_disconnect(self):
        """disconnect() works through proxy."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.disconnect()
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        self.assertFalse(cli._device_state.connected)
        cli.cleanup()

    def test_proxy_serial_send(self):
        """serial_send() works through proxy (no read_response to avoid sleep)."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.serial_send("test", read_response=False)
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()

    def test_proxy_serial_read(self):
        """serial_read() works through proxy."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.serial_read()
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        self.assertIn("log", result)
        cli.cleanup()

    def test_proxy_test_serial(self):
        """test_serial() works through proxy."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.test_serial()
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        cli.cleanup()


class TestFPBCLIDirectMode(unittest.TestCase):
    """Test --direct flag bypasses proxy detection."""

    @classmethod
    def setUpClass(cls):
        _MockHandler.responses = {
            "/api/status": {"success": True, "connected": True},
        }
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHandler)
        cls.port = cls.server.server_address[1]
        cls.server_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    @patch("fpbinject.cli.fpb_cli.serial.Serial")
    def test_direct_skips_proxy(self, mock_serial):
        """--direct flag forces direct serial connection."""
        mock_serial.return_value = MagicMock()
        cli = FPBCLI(
            port="/dev/test-direct-mode",
            direct=True,
            server_url=self.server_url,
        )
        self.assertIsNone(cli._proxy)
        self.assertTrue(cli._device_state.connected)
        self.assertIsNotNone(cli._port_lock)
        cli.cleanup()


class TestFPBCLIPortLockIntegration(unittest.TestCase):
    """Test port lock integration in FPBCLI."""

    def _mock_proxy_no_server(self):
        """Create a mock ServerProxy that simulates no server running + launch fails."""
        mock_proxy = MagicMock()
        mock_proxy.is_server_running.return_value = False
        mock_proxy.launch_server.return_value = False
        return mock_proxy

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    @patch("fpbinject.cli.fpb_cli.serial.Serial")
    def test_port_lock_acquired_on_connect(self, mock_serial, mock_proxy_cls):
        """Port lock is acquired when connecting directly."""
        mock_serial.return_value = MagicMock()
        mock_proxy_cls.return_value = self._mock_proxy_no_server()
        cli = FPBCLI(
            port="/dev/test-cli-lock-1",
            server_url="http://127.0.0.1:19999",
        )
        self.assertIsNotNone(cli._port_lock)
        cli.cleanup()

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    @patch("fpbinject.cli.fpb_cli.serial.Serial")
    def test_port_lock_released_on_cleanup(self, mock_serial, mock_proxy_cls):
        """Port lock is released on cleanup."""
        mock_serial.return_value = MagicMock()
        mock_proxy_cls.return_value = self._mock_proxy_no_server()
        cli = FPBCLI(
            port="/dev/test-cli-lock-2",
            server_url="http://127.0.0.1:19999",
        )
        cli.cleanup()
        self.assertIsNone(cli._port_lock)
        # Lock should be released - another lock should succeed
        lock2 = PortLock("/dev/test-cli-lock-2")
        self.assertTrue(lock2.acquire())
        lock2.release()

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    @patch("fpbinject.cli.fpb_cli.serial.Serial")
    def test_port_lock_conflict(self, mock_serial, mock_proxy_cls):
        """Second CLI on same port fails with FPBCLIError."""
        mock_serial.return_value = MagicMock()
        mock_proxy_cls.return_value = self._mock_proxy_no_server()
        cli1 = FPBCLI(
            port="/dev/test-cli-lock-3",
            server_url="http://127.0.0.1:19999",
        )
        mock_proxy_cls.return_value = self._mock_proxy_no_server()
        with self.assertRaises(FPBCLIError) as ctx:
            FPBCLI(
                port="/dev/test-cli-lock-3",
                server_url="http://127.0.0.1:19999",
            )
        self.assertIn("locked", str(ctx.exception).lower())
        cli1.cleanup()


class TestFPBCLINoPortNoProxy(unittest.TestCase):
    """Test CLI without port (offline mode) - no proxy, no lock."""

    def test_offline_no_proxy_no_lock(self):
        """Offline CLI has no proxy and no lock."""
        cli = FPBCLI()
        self.assertIsNone(cli._proxy)
        self.assertIsNone(cli._port_lock)
        self.assertFalse(cli._device_state.connected)
        cli.cleanup()

    def test_require_device_raises_offline(self):
        """_require_device raises when no proxy and not connected."""
        cli = FPBCLI()
        with self.assertRaises(FPBCLIError) as ctx:
            cli._require_device()
        self.assertIn("No device connected", str(ctx.exception))
        cli.cleanup()

    def test_write_local_helper(self):
        """_write_local creates dirs and writes data."""
        import tempfile

        cli = FPBCLI()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "sub", "file.bin")
            cli._write_local(path, b"\x01\x02\x03")
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"\x01\x02\x03")
        cli.cleanup()


class TestFPBCLIServerUrlArg(unittest.TestCase):
    """Test --server-url argument."""

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_custom_server_url_unreachable_no_port(self, mock_proxy_cls):
        """Remote URL, no port, unreachable server -> stays offline (no proxy)."""
        proxy = MagicMock()
        proxy.get_status.side_effect = OSError("unreachable")
        mock_proxy_cls.return_value = proxy
        cli = FPBCLI(server_url="http://192.168.1.100:8080")
        # No port + unreachable remote -> offline, proxy not retained
        self.assertIsNone(cli._proxy)
        cli.cleanup()


class TestMainNewArgs(unittest.TestCase):
    """Test new CLI arguments in main()."""

    @patch("fpbinject.cli.fpb_cli.FPBCLI")
    @patch("sys.argv", ["fpb_cli.py", "--direct", "--port", "/dev/ttyACM0", "info"])
    def test_direct_arg_passed(self, mock_cli_cls):
        """--direct argument is passed to FPBCLI."""
        from fpbinject.cli.connection_plan import ConnectionMode

        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        main()
        plan = mock_cli_cls.call_args.kwargs.get("plan")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.mode, ConnectionMode.DIRECT)
        self.assertEqual(plan.serial_port, "/dev/ttyACM0")

    @patch("fpbinject.cli.fpb_cli.FPBCLI")
    @patch(
        "sys.argv",
        [
            "fpb_cli.py",
            "--server-url",
            "http://myhost:9000",
            "--port",
            "/dev/ttyACM0",
            "info",
        ],
    )
    def test_server_url_arg_passed(self, mock_cli_cls):
        """--server-url argument is passed to FPBCLI."""
        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        main()
        plan = mock_cli_cls.call_args.kwargs.get("plan")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.server_url, "http://myhost:9000")


class _CursorMockHandler(http.server.BaseHTTPRequestHandler):
    """Mock HTTP handler that respects raw_since query parameter."""

    # Simulated log entries: list of {"id": int, "data": str}
    log_entries = []

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/status":
            body = json.dumps(
                {"success": True, "connected": True, "port": "/dev/ttyACM0"}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/logs":
            raw_since = int(qs.get("raw_since", [0])[0])
            entries = [e for e in self.log_entries if e["id"] >= raw_since]
            raw_data = "".join(e["data"] for e in entries)
            raw_next = (
                max(e["id"] for e in self.log_entries) + 1 if self.log_entries else 0
            )
            body = json.dumps({"raw_data": raw_data, "raw_next": raw_next}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(content_length) if content_length else b""
        self.do_GET()

    def log_message(self, format, *args):
        pass


class TestSerialReadSinceCursor(unittest.TestCase):
    """Test serial_read --since cursor for incremental reads."""

    @classmethod
    def setUpClass(cls):
        _CursorMockHandler.log_entries = [
            {"id": 0, "data": "line0\n"},
            {"id": 1, "data": "line1\n"},
            {"id": 2, "data": "line2\n"},
        ]
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _CursorMockHandler)
        cls.port = cls.server.server_address[1]
        cls.server_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _make_cli(self):
        return FPBCLI(port="/dev/ttyACM0", server_url=self.server_url)

    def test_serial_read_since_zero_returns_all(self):
        """serial_read(since=0) returns all log entries."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.serial_read(since=0)
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        self.assertIn("line0", result["raw_data"])
        self.assertIn("line1", result["raw_data"])
        self.assertIn("line2", result["raw_data"])
        self.assertEqual(result["raw_next"], 3)
        cli.cleanup()

    def test_serial_read_since_skips_old(self):
        """serial_read(since=2) returns only entries with id >= 2."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.serial_read(since=2)
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        self.assertNotIn("line0", result["raw_data"])
        self.assertNotIn("line1", result["raw_data"])
        self.assertIn("line2", result["raw_data"])
        self.assertEqual(result["raw_next"], 3)
        cli.cleanup()

    def test_serial_read_since_beyond_returns_empty(self):
        """serial_read(since=raw_next) returns empty raw_data."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.serial_read(since=3)
        result = json.loads(buf.getvalue())
        self.assertTrue(result["success"])
        self.assertEqual(result["raw_data"], "")
        self.assertEqual(result["raw_next"], 3)
        cli.cleanup()

    def test_serial_read_raw_next_in_output(self):
        """serial_read output always contains raw_next field."""
        cli = self._make_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.serial_read()
        result = json.loads(buf.getvalue())
        self.assertIn("raw_next", result)
        self.assertIsInstance(result["raw_next"], int)
        cli.cleanup()

    def test_serial_read_incremental_workflow(self):
        """Simulate incremental read: first read all, then only new."""
        cli = self._make_cli()

        # First read: get everything
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.serial_read(since=0)
        r1 = json.loads(buf.getvalue())
        cursor = r1["raw_next"]
        self.assertEqual(cursor, 3)

        # Add new entry
        _CursorMockHandler.log_entries.append({"id": 3, "data": "line3\n"})

        # Second read: only new data
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.serial_read(since=cursor)
        r2 = json.loads(buf.getvalue())
        self.assertIn("line3", r2["raw_data"])
        self.assertNotIn("line0", r2["raw_data"])
        self.assertEqual(r2["raw_next"], 4)

        # Restore
        _CursorMockHandler.log_entries.pop()
        cli.cleanup()


class TestFPBCLIIsRemoteUrl(unittest.TestCase):
    """Test the URL locality classifier."""

    def test_localhost_ip_is_local(self):
        from fpbinject.cli.fpb_cli import _is_local_url

        self.assertTrue(_is_local_url("http://127.0.0.1:5500"))

    def test_localhost_name_is_local(self):
        from fpbinject.cli.fpb_cli import _is_local_url

        self.assertTrue(_is_local_url("http://localhost:5500"))

    def test_ipv6_loopback_is_local(self):
        from fpbinject.cli.fpb_cli import _is_local_url

        self.assertTrue(_is_local_url("http://[::1]:5500"))

    def test_lan_ip_is_remote(self):
        from fpbinject.cli.fpb_cli import _is_local_url

        self.assertFalse(_is_local_url("http://192.168.1.20:5500"))

    def test_hostname_is_remote(self):
        from fpbinject.cli.fpb_cli import _is_local_url

        self.assertFalse(_is_local_url("http://buildbox:9000"))

    def test_malformed_url_is_local(self):
        # Unparseable -> treated as local (safe default, no remote restrictions).
        from fpbinject.cli.fpb_cli import _is_local_url

        self.assertFalse(_is_local_url("not a url"))


class TestFPBCLIRemoteMode(unittest.TestCase):
    """Test remote proxy mode: no auto-launch, no direct fallback."""

    def _mock_proxy(self, ok=True, connected=False):
        proxy = MagicMock()
        proxy.get_status.return_value = {"success": ok, "connected": connected}
        proxy.is_device_connected.return_value = connected
        proxy.connect.return_value = {"success": True}
        return proxy

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_remote_uses_proxy_without_launch(self, mock_proxy_cls):
        """Remote mode sets up proxy and never calls launch_server."""
        proxy = self._mock_proxy(ok=True, connected=True)
        mock_proxy_cls.return_value = proxy
        cli = FPBCLI(port="/dev/ttyACM0", server_url="http://192.168.1.20:5500")
        self.assertIs(cli._proxy, proxy)
        proxy.launch_server.assert_not_called()
        self.assertIsNone(cli._port_lock)
        cli.cleanup()

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_remote_no_port_attaches_proxy(self, mock_proxy_cls):
        """Remote mode works WITHOUT --port when the server has a device."""
        proxy = self._mock_proxy(ok=True, connected=True)
        mock_proxy_cls.return_value = proxy
        cli = FPBCLI(server_url="http://192.168.1.20:5500")
        # Proxy is engaged even though no --port was supplied.
        self.assertIs(cli._proxy, proxy)
        self.assertTrue(cli._device_state.connected)
        # No port given -> never asks the server to open one.
        proxy.connect.assert_not_called()
        cli.cleanup()

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_remote_passes_token(self, mock_proxy_cls):
        """Token is forwarded to ServerProxy in remote mode."""
        mock_proxy_cls.return_value = self._mock_proxy(ok=True, connected=True)
        cli = FPBCLI(
            port="/dev/ttyACM0",
            server_url="http://192.168.1.20:5500",
            token="secret-token",
        )
        _, kwargs = mock_proxy_cls.call_args
        self.assertEqual(kwargs.get("token"), "secret-token")
        cli.cleanup()

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_remote_unreachable_raises(self, mock_proxy_cls):
        """Remote mode raises if the server is not reachable (no local launch)."""
        proxy = MagicMock()
        proxy.get_status.side_effect = OSError("connection refused")
        mock_proxy_cls.return_value = proxy
        with self.assertRaises(FPBCLIError) as ctx:
            FPBCLI(port="/dev/ttyACM0", server_url="http://192.168.1.20:5500")
        self.assertIn("not reachable", str(ctx.exception))
        proxy.launch_server.assert_not_called()

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_remote_status_unsuccessful_raises(self, mock_proxy_cls):
        """Remote mode raises if /api/status returns success=False."""
        proxy = self._mock_proxy(ok=False)
        mock_proxy_cls.return_value = proxy
        with self.assertRaises(FPBCLIError) as ctx:
            FPBCLI(port="/dev/ttyACM0", server_url="http://192.168.1.20:5500")
        self.assertIn("not reachable", str(ctx.exception))

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_remote_auth_error_raises_cli_error(self, mock_proxy_cls):
        """ProxyAuthError during probe becomes a friendly FPBCLIError."""
        proxy = MagicMock()
        proxy.get_status.side_effect = ProxyAuthError("token required")
        mock_proxy_cls.return_value = proxy
        with self.assertRaises(FPBCLIError) as ctx:
            FPBCLI(port="/dev/ttyACM0", server_url="http://192.168.1.20:5500")
        self.assertIn("token", str(ctx.exception).lower())

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_remote_connects_device_when_disconnected(self, mock_proxy_cls):
        """Remote mode connects the device when not already connected (port given)."""
        proxy = self._mock_proxy(ok=True, connected=False)
        mock_proxy_cls.return_value = proxy
        cli = FPBCLI(port="/dev/ttyACM0", server_url="http://10.0.0.5:5500")
        proxy.connect.assert_called_once()
        self.assertTrue(cli._device_state.connected)
        cli.cleanup()

    def test_remote_with_direct_raises(self):
        """--direct combined with a remote URL is rejected."""
        with self.assertRaises(FPBCLIError) as ctx:
            FPBCLI(
                port="/dev/ttyACM0",
                direct=True,
                server_url="http://192.168.1.20:5500",
            )
        self.assertIn("direct", str(ctx.exception).lower())


class TestFPBCLILocalNoPortNoServer(unittest.TestCase):
    """Local, no port: stay offline (proxy not even constructed)."""

    @patch("fpbinject.cli.fpb_cli.ServerProxy")
    def test_offline_no_proxy_no_launch(self, mock_proxy_cls):
        """No port locally -> offline, no proxy retained, no auto-launch attempted."""
        proxy = MagicMock()
        proxy.is_server_running.return_value = False
        proxy.launch_server.return_value = False
        mock_proxy_cls.return_value = proxy
        cli = FPBCLI(server_url="http://127.0.0.1:19999")
        self.assertIsNone(cli._proxy)
        proxy.launch_server.assert_not_called()
        cli.cleanup()


class TestMainTokenArg(unittest.TestCase):
    """Test the --token argument wiring in main().

    These assert only that the token reaches the ConnectionPlan. Stub
    discovery so the env-token case (no -s/--server-url) resolves via the
    localhost fallback instantly instead of a ~3s mDNS browse.
    """

    def setUp(self):
        patchers = [
            patch("fpbinject.cli.fpb_cli.discover_sync", return_value=[]),
            patch("fpbinject.cli.fpb_cli.list_cli_servers", return_value=[]),
            patch("fpbinject.cli.fpb_cli._localhost_status_ok", return_value=False),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch("fpbinject.cli.fpb_cli.FPBCLI")
    @patch(
        "sys.argv",
        [
            "fpb_cli.py",
            "--server-url",
            "http://myhost:9000",
            "--token",
            "abc123",
            "--port",
            "/dev/ttyACM0",
            "info",
        ],
    )
    def test_token_arg_passed(self, mock_cli_cls):
        """--token argument is passed to FPBCLI."""
        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        main()
        plan = mock_cli_cls.call_args.kwargs.get("plan")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.token, "abc123")

    @patch("fpbinject.cli.fpb_cli.FPBCLI")
    @patch.dict(os.environ, {"FPB_TOKEN": "env-token"}, clear=False)
    @patch("sys.argv", ["fpb_cli.py", "--port", "/dev/ttyACM0", "info"])
    def test_token_from_env(self, mock_cli_cls):
        """--token defaults to the FPB_TOKEN environment variable.

        argparse computes ``default=os.environ.get("FPB_TOKEN")`` when
        add_argument runs inside main(), so the patched env is picked up.
        """
        mock_cli = MagicMock()
        mock_cli_cls.return_value = mock_cli
        main()
        plan = mock_cli_cls.call_args.kwargs.get("plan")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.token, "env-token")


if __name__ == "__main__":
    unittest.main()

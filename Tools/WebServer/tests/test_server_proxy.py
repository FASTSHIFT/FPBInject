#!/usr/bin/env python3
"""
Test cases for cli/server_proxy.py
"""

import http.server
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from fpbinject.cli.server_proxy import ServerProxy, ProxyAuthError, DEFAULT_SERVER_URL
from fixtures.mock_http import MockHTTPHandler as _MockHTTPHandler


class TestServerProxyInit(unittest.TestCase):
    """Test ServerProxy initialization."""

    def test_default_url(self):
        proxy = ServerProxy()
        self.assertEqual(proxy.base_url, DEFAULT_SERVER_URL)
        self.assertIsNone(proxy.token)

    def test_custom_url(self):
        proxy = ServerProxy(base_url="http://localhost:8080")
        self.assertEqual(proxy.base_url, "http://localhost:8080")

    def test_trailing_slash_stripped(self):
        proxy = ServerProxy(base_url="http://localhost:8080/")
        self.assertEqual(proxy.base_url, "http://localhost:8080")

    def test_with_token(self):
        proxy = ServerProxy(token="abc123")
        self.assertEqual(proxy.token, "abc123")


class TestServerProxyBuildUrl(unittest.TestCase):
    """Test URL building."""

    def test_simple_path(self):
        proxy = ServerProxy(base_url="http://localhost:5500")
        url = proxy._build_url("/api/status")
        self.assertEqual(url, "http://localhost:5500/api/status")

    def test_with_token(self):
        proxy = ServerProxy(base_url="http://localhost:5500", token="tok123")
        url = proxy._build_url("/api/status")
        self.assertEqual(url, "http://localhost:5500/api/status?token=tok123")

    def test_with_token_existing_query(self):
        proxy = ServerProxy(base_url="http://localhost:5500", token="tok123")
        url = proxy._build_url("/api/status?foo=bar")
        self.assertEqual(url, "http://localhost:5500/api/status?foo=bar&token=tok123")


class TestServerProxyWithMockServer(unittest.TestCase):
    """Integration tests with a real HTTP server."""

    @classmethod
    def setUpClass(cls):
        """Start a mock HTTP server."""
        _MockHTTPHandler.responses = {
            "/api/status": {"success": True, "connected": True, "port": "/dev/ttyACM0"},
            "/api/fpb/info": {
                "success": True,
                "info": {"version": "1.0", "slots": 6},
            },
            "/api/fpb/inject": {"success": True, "result": "injected"},
            "/api/fpb/unpatch": {"success": True, "message": "unpatched"},
            "/api/fpb/mem-read": {"success": True, "hex_dump": "00 01 02"},
            "/api/fpb/mem-write": {"success": True, "message": "written"},
            "/api/transfer/list": {"success": True, "path": "/data", "entries": []},
            "/api/transfer/stat": {
                "success": True,
                "path": "/data/test.bin",
                "stat": {"size": 512},
            },
            "/api/transfer/delete": {"success": True, "message": "OK"},
            "/api/transfer/mkdir": {"success": True, "message": "OK"},
            "/api/transfer/rename": {"success": True, "message": "OK"},
        }
        _MockHTTPHandler.sse_responses = {
            "/api/transfer/upload": [
                {"type": "progress", "uploaded": 5, "total": 5, "percent": 100.0},
                {"type": "result", "success": True, "message": "Uploaded 5 bytes"},
            ],
        }
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHTTPHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _proxy(self):
        return ServerProxy(base_url=self.base_url)

    def test_is_server_running(self):
        proxy = self._proxy()
        self.assertTrue(proxy.is_server_running())

    def test_is_device_connected(self):
        proxy = self._proxy()
        self.assertTrue(proxy.is_device_connected())

    def test_get_status(self):
        proxy = self._proxy()
        status = proxy.get_status()
        self.assertTrue(status["success"])
        self.assertEqual(status["port"], "/dev/ttyACM0")

    def test_info(self):
        proxy = self._proxy()
        result = proxy.info()
        self.assertTrue(result["success"])
        self.assertEqual(result["info"]["slots"], 6)

    def test_inject(self):
        proxy = self._proxy()
        # Create a temp source file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("/* FPB_INJECT */\nvoid test(void) {}\n")
            src_path = f.name
        try:
            result = proxy.inject(
                target_func="test",
                source_file=src_path,
            )
            self.assertTrue(result["success"])
        finally:
            os.unlink(src_path)

    def test_inject_nonexistent_source(self):
        """inject with nonexistent source file still sends request."""
        proxy = self._proxy()
        result = proxy.inject(
            target_func="test",
            source_file="/nonexistent/file.c",
        )
        # Server still responds (source_content will be empty)
        self.assertTrue(result["success"])

    def test_unpatch(self):
        proxy = self._proxy()
        result = proxy.unpatch(comp=0)
        self.assertTrue(result["success"])

    def test_unpatch_all(self):
        proxy = self._proxy()
        result = proxy.unpatch(all_patches=True)
        self.assertTrue(result["success"])

    def test_mem_read(self):
        proxy = self._proxy()
        result = proxy.mem_read(0x20000000, 64)
        self.assertTrue(result["success"])

    def test_mem_write(self):
        proxy = self._proxy()
        result = proxy.mem_write(0x20000000, "DEADBEEF")
        self.assertTrue(result["success"])

    def test_file_list(self):
        proxy = self._proxy()
        result = proxy.file_list("/data")
        self.assertTrue(result["success"])

    def test_file_stat(self):
        proxy = self._proxy()
        result = proxy.file_stat("/data/test.bin")
        self.assertTrue(result["success"])

    def test_file_remove(self):
        proxy = self._proxy()
        result = proxy.file_remove("/data/old.bin")
        self.assertTrue(result["success"])

    def test_file_mkdir(self):
        proxy = self._proxy()
        result = proxy.file_mkdir("/data/newdir")
        self.assertTrue(result["success"])

    def test_file_rename(self):
        proxy = self._proxy()
        result = proxy.file_rename("/data/old.bin", "/data/new.bin")
        self.assertTrue(result["success"])

    def test_file_upload(self):
        proxy = self._proxy()
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"hello")
            tf.flush()
            local_path = tf.name
        try:
            result = proxy.file_upload(local_path, "/data/test.bin")
            self.assertTrue(result["success"])
        finally:
            os.unlink(local_path)


class TestFileUploadEdgeCases(unittest.TestCase):
    """Test file_upload proxy edge cases (no result event, invalid JSON)."""

    @classmethod
    def setUpClass(cls):
        """Start a mock server that returns SSE without a result event."""
        _MockHTTPHandler.responses = {}
        _MockHTTPHandler.sse_responses = {
            "/api/transfer/upload": [
                {"type": "progress", "uploaded": 3, "total": 3, "percent": 100.0},
                # No "result" event
            ],
        }
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHTTPHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_file_upload_no_result_event(self):
        """file_upload returns fallback when SSE has no result event."""
        proxy = ServerProxy(base_url=self.base_url)
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"abc")
            tf.flush()
            local_path = tf.name
        try:
            result = proxy.file_upload(local_path, "/data/test.bin")
            self.assertTrue(result["success"])
            self.assertEqual(result["message"], "Upload request sent")
        finally:
            os.unlink(local_path)


class TestFileUploadInvalidSSE(unittest.TestCase):
    """Test file_upload proxy with invalid SSE JSON."""

    class _BadSSEHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length:
                self.rfile.read(content_length)
            # Return SSE with invalid JSON line
            body = 'data: {not valid json}\n\ndata: {"type": "result", "success": true, "message": "OK"}\n\n'
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, format, *args):
            pass

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), cls._BadSSEHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_file_upload_skips_invalid_json(self):
        """file_upload skips invalid JSON lines and finds the valid result."""
        proxy = ServerProxy(base_url=self.base_url)
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"data")
            tf.flush()
            local_path = tf.name
        try:
            result = proxy.file_upload(local_path, "/data/test.bin")
            self.assertTrue(result["success"])
            self.assertEqual(result["message"], "OK")
        finally:
            os.unlink(local_path)


class TestServerProxyNoServer(unittest.TestCase):
    """Test behavior when no server is running."""

    def test_is_server_running_false(self):
        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        self.assertFalse(proxy.is_server_running())

    def test_is_device_connected_false(self):
        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        self.assertFalse(proxy.is_device_connected())

    def test_info_raises(self):
        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        with self.assertRaises(URLError):
            proxy.info()


class TestServerProxyWithToken(unittest.TestCase):
    """Test token authentication in proxy."""

    @classmethod
    def setUpClass(cls):
        _MockHTTPHandler.responses = {
            "/api/status": {"success": True, "connected": False},
        }
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHTTPHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_token_appended_to_url(self):
        proxy = ServerProxy(base_url=self.base_url, token="secret")
        # is_server_running makes a GET to /api/status?token=secret
        self.assertTrue(proxy.is_server_running())

    def test_device_not_connected(self):
        proxy = ServerProxy(base_url=self.base_url)
        self.assertFalse(proxy.is_device_connected())


if __name__ == "__main__":
    unittest.main()


class TestServerProxyLaunchServer(unittest.TestCase):
    """Test launch_server and ensure_server logic."""

    def test_launch_server_main_not_found(self):
        """launch_server returns False when main.py doesn't exist."""
        from unittest.mock import patch

        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        with patch("os.path.exists", return_value=False):
            self.assertFalse(proxy.launch_server())

    def test_launch_server_popen_fails(self):
        """launch_server returns False when Popen raises."""
        from unittest.mock import patch

        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        with patch("os.path.exists", return_value=True), patch(
            "subprocess.Popen", side_effect=OSError("fail")
        ):
            self.assertFalse(proxy.launch_server())

    def test_launch_server_process_dies(self):
        """launch_server returns False when subprocess exits immediately."""
        from unittest.mock import patch, MagicMock

        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # Process exited with code 1
        mock_proc.returncode = 1

        with patch("os.path.exists", return_value=True), patch(
            "subprocess.Popen", return_value=mock_proc
        ):
            self.assertFalse(proxy.launch_server())
        self.assertIsNone(proxy._server_process)

    def test_launch_server_timeout(self):
        """launch_server returns False when server doesn't respond in time."""
        from unittest.mock import patch, MagicMock
        import fpbinject.cli.server_proxy as sp_mod

        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Process still running

        orig_timeout = sp_mod._LAUNCH_TIMEOUT
        sp_mod._LAUNCH_TIMEOUT = 0.1  # Very short timeout
        sp_mod._LAUNCH_POLL_INTERVAL = 0.05
        try:
            with patch("os.path.exists", return_value=True), patch(
                "subprocess.Popen", return_value=mock_proc
            ):
                self.assertFalse(proxy.launch_server())
            mock_proc.terminate.assert_called_once()
        finally:
            sp_mod._LAUNCH_TIMEOUT = orig_timeout
            sp_mod._LAUNCH_POLL_INTERVAL = 0.3

    def test_launch_server_success(self):
        """launch_server returns True when server becomes reachable."""
        from unittest.mock import patch, MagicMock

        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        call_count = [0]

        def fake_is_running():
            call_count[0] += 1
            return call_count[0] >= 2  # Succeed on second poll

        with patch("os.path.exists", return_value=True), patch(
            "subprocess.Popen", return_value=mock_proc
        ), patch.object(proxy, "is_server_running", side_effect=fake_is_running):
            self.assertTrue(proxy.launch_server())

    def test_ensure_server_already_running(self):
        """ensure_server returns True immediately if server is running."""
        from unittest.mock import patch

        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        with patch.object(proxy, "is_server_running", return_value=True):
            self.assertTrue(proxy.ensure_server())

    def test_ensure_server_launches(self):
        """ensure_server calls launch_server when not running."""
        from unittest.mock import patch

        proxy = ServerProxy(base_url="http://127.0.0.1:19876")
        with patch.object(proxy, "is_server_running", return_value=False), patch.object(
            proxy, "launch_server", return_value=True
        ) as mock_launch:
            self.assertTrue(proxy.ensure_server())
            mock_launch.assert_called_once()


class TestServerProxySerialAndConnection(unittest.TestCase):
    """Test serial_send, serial_read, connect, disconnect proxy methods."""

    @classmethod
    def setUpClass(cls):
        _MockHTTPHandler.responses = {
            "/api/status": {"success": True, "connected": True},
            "/api/connect": {"success": True, "port": "/dev/ttyACM0"},
            "/api/disconnect": {"success": True},
            "/api/serial/send": {"success": True, "sent": "hello"},
            "/api/logs": {"raw_data": "line1\nline2\n", "raw_next": 100},
        }
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHTTPHandler)
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

    def test_connect(self):
        result = self._proxy().connect("/dev/ttyACM0")
        self.assertTrue(result["success"])

    def test_disconnect(self):
        result = self._proxy().disconnect()
        self.assertTrue(result["success"])

    def test_serial_send(self):
        result = self._proxy().serial_send("hello")
        self.assertTrue(result["success"])

    def test_serial_read(self):
        result = self._proxy().serial_read(raw_since=0)
        self.assertIn("raw_data", result)
        self.assertEqual(result["raw_data"], "line1\nline2\n")


class TestPidFileFunctions(unittest.TestCase):
    """Test PID file management functions."""

    def setUp(self):
        from fpbinject.cli.server_proxy import _WEBSERVER_DIR

        self.webserver_dir = _WEBSERVER_DIR
        self.test_port = 19999
        self.pid_path = os.path.join(
            self.webserver_dir, f".cli_server_{self.test_port}.pid"
        )
        # Clean up before each test
        if os.path.exists(self.pid_path):
            os.remove(self.pid_path)

    def tearDown(self):
        if os.path.exists(self.pid_path):
            os.remove(self.pid_path)

    def test_pid_file_path(self):
        from fpbinject.cli.server_proxy import _pid_file_path

        path = _pid_file_path(5500)
        self.assertTrue(path.endswith(".cli_server_5500.pid"))
        self.assertIn(self.webserver_dir, path)

    def test_pid_file_path_custom_port(self):
        from fpbinject.cli.server_proxy import _pid_file_path

        path = _pid_file_path(8080)
        self.assertTrue(path.endswith(".cli_server_8080.pid"))

    def test_get_cli_server_pid_no_file(self):
        from fpbinject.cli.server_proxy import get_cli_server_pid

        self.assertIsNone(get_cli_server_pid(self.test_port))

    def test_get_cli_server_pid_stale(self):
        """PID file exists but process is dead — should clean up."""
        from fpbinject.cli.server_proxy import get_cli_server_pid

        with open(self.pid_path, "w") as f:
            f.write("999999999")  # Very unlikely to be a real PID
        self.assertIsNone(get_cli_server_pid(self.test_port))
        self.assertFalse(os.path.exists(self.pid_path))

    def test_get_cli_server_pid_alive(self):
        """PID file with our own PID — should return it."""
        from fpbinject.cli.server_proxy import get_cli_server_pid

        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))
        self.assertEqual(get_cli_server_pid(self.test_port), os.getpid())

    def test_get_cli_server_pid_invalid_content(self):
        from fpbinject.cli.server_proxy import get_cli_server_pid

        with open(self.pid_path, "w") as f:
            f.write("not-a-number")
        self.assertIsNone(get_cli_server_pid(self.test_port))

    def test_remove_pid_file(self):
        from fpbinject.cli.server_proxy import _remove_pid_file

        with open(self.pid_path, "w") as f:
            f.write("12345")
        _remove_pid_file(self.test_port)
        self.assertFalse(os.path.exists(self.pid_path))

    def test_remove_pid_file_nonexistent(self):
        from fpbinject.cli.server_proxy import _remove_pid_file

        # Should not raise
        _remove_pid_file(self.test_port)

    def test_stop_cli_server_no_server(self):
        from fpbinject.cli.server_proxy import stop_cli_server

        result = stop_cli_server(self.test_port)
        self.assertFalse(result["success"])
        self.assertIn(str(self.test_port), result["error"])

    def test_stop_cli_server_stale_pid(self):
        from fpbinject.cli.server_proxy import stop_cli_server

        with open(self.pid_path, "w") as f:
            f.write("999999999")
        result = stop_cli_server(self.test_port)
        self.assertFalse(result["success"])

    def test_stop_cli_server_success(self):
        """Start a real subprocess and stop it."""
        import subprocess
        from fpbinject.cli.server_proxy import stop_cli_server

        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(self.pid_path, "w") as f:
            f.write(str(proc.pid))

        result = stop_cli_server(self.test_port)
        self.assertTrue(result["success"])
        self.assertIn(str(proc.pid), result["message"])
        self.assertFalse(os.path.exists(self.pid_path))
        # Ensure process is dead
        proc.wait(timeout=5)

    def test_list_cli_servers_empty(self):
        from fpbinject.cli.server_proxy import list_cli_servers

        # No PID files for our test port
        servers = list_cli_servers()
        # Filter to our test port only
        test_servers = [s for s in servers if s["port"] == self.test_port]
        self.assertEqual(len(test_servers), 0)

    def test_list_cli_servers_with_entry(self):
        from fpbinject.cli.server_proxy import list_cli_servers

        # Write a PID file with our own PID (alive)
        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))
        servers = list_cli_servers()
        test_servers = [s for s in servers if s["port"] == self.test_port]
        self.assertEqual(len(test_servers), 1)
        self.assertEqual(test_servers[0]["pid"], os.getpid())


class TestGetPortOwner(unittest.TestCase):
    """Test get_port_owner function from main.py."""

    def test_port_not_in_use(self):
        from fpbinject.main import get_port_owner

        result = get_port_owner(19876)  # Very unlikely to be in use
        self.assertIsNone(result)

    def test_port_in_use(self):
        """Bind a port and check get_port_owner finds us."""
        import socket
        from fpbinject.main import get_port_owner

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 19877))
        sock.listen(1)
        try:
            result = get_port_owner(19877)
            if result is not None:
                # On Linux with /proc, should find our PID
                self.assertEqual(result["pid"], os.getpid())
                self.assertIn("name", result)
                self.assertIn("cmdline", result)
        finally:
            sock.close()


class _TokenCapturingHandler(http.server.BaseHTTPRequestHandler):
    """Mock handler that records the X-Auth-Token header and token query."""

    last_header_token = None
    last_query = None

    def _handle(self):
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        _TokenCapturingHandler.last_header_token = self.headers.get("X-Auth-Token")
        _TokenCapturingHandler.last_query = parse_qs(parsed.query)
        body = json.dumps({"success": True, "connected": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            self.rfile.read(content_length)
        self._handle()

    def log_message(self, format, *args):
        pass


class TestServerProxyTokenTransmission(unittest.TestCase):
    """Verify the token is sent both as header and query param."""

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _TokenCapturingHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_sends_token_header(self):
        _TokenCapturingHandler.last_header_token = None
        proxy = ServerProxy(base_url=self.base_url, token="hdr-token")
        proxy.get_status()
        self.assertEqual(_TokenCapturingHandler.last_header_token, "hdr-token")

    def test_get_sends_token_query(self):
        proxy = ServerProxy(base_url=self.base_url, token="qry-token")
        proxy.get_status()
        self.assertEqual(_TokenCapturingHandler.last_query.get("token"), ["qry-token"])

    def test_post_sends_token_header(self):
        _TokenCapturingHandler.last_header_token = None
        proxy = ServerProxy(base_url=self.base_url, token="post-token")
        proxy.connect("/dev/ttyACM0")
        self.assertEqual(_TokenCapturingHandler.last_header_token, "post-token")

    def test_no_token_no_header(self):
        _TokenCapturingHandler.last_header_token = None
        proxy = ServerProxy(base_url=self.base_url)
        proxy.get_status()
        self.assertIsNone(_TokenCapturingHandler.last_header_token)


class _ForbiddenHandler(http.server.BaseHTTPRequestHandler):
    """Mock handler that always returns 403 Forbidden."""

    def _deny(self):
        body = json.dumps({"success": False, "error": "Forbidden"}).encode()
        self.send_response(403)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._deny()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            self.rfile.read(content_length)
        self._deny()

    def log_message(self, format, *args):
        pass


class TestServerProxyAuthError(unittest.TestCase):
    """Verify 403/401 responses become ProxyAuthError."""

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _ForbiddenHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_raises_auth_error(self):
        proxy = ServerProxy(base_url=self.base_url)
        with self.assertRaises(ProxyAuthError):
            proxy.get_status()

    def test_post_raises_auth_error(self):
        proxy = ServerProxy(base_url=self.base_url)
        with self.assertRaises(ProxyAuthError):
            proxy.connect("/dev/ttyACM0")

    def test_is_server_running_false_on_forbidden(self):
        """is_server_running swallows the auth error and returns False."""
        proxy = ServerProxy(base_url=self.base_url)
        self.assertFalse(proxy.is_server_running())

    def test_auth_error_message_mentions_token(self):
        proxy = ServerProxy(base_url=self.base_url)
        try:
            proxy.info()
            self.fail("expected ProxyAuthError")
        except ProxyAuthError as e:
            self.assertIn("token", str(e).lower())

    def test_file_upload_raises_auth_error(self):
        """file_upload also surfaces auth errors."""
        proxy = ServerProxy(base_url=self.base_url)
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"data")
            tf.flush()
            local_path = tf.name
        try:
            with self.assertRaises(ProxyAuthError):
                proxy.file_upload(local_path, "/data/test.bin")
        finally:
            os.unlink(local_path)

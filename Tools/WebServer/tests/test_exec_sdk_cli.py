#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the exec command on the client side: ServerProxy.exec_cmd, the SDK
facade (Client.exec_cmd) and the CLI (`fpbinject exec`).
"""

import contextlib
import http.server
import io
import json
import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject import (  # noqa: E402
    AuthError,
    Client,
    DeviceNotConnected,
    FPBError,
    ServerUnavailable,
)
from fpbinject.cli.errors import FPBCLIError  # noqa: E402
from fpbinject.cli.fpb_cli import FPBCLI, main  # noqa: E402
from fpbinject.cli.server_proxy import ProxyAuthError, ServerProxy  # noqa: E402
from fpbinject.core import exec_client  # noqa: E402

OK = {
    "success": True,
    "ret": 0,
    "output": "x\n",
    "replayed": False,
    "started": True,
    "output_truncated": False,
    "elapsed_ms": 1.0,
    "error_code": "",
    "error": "",
}


class _RecordingHandler(http.server.BaseHTTPRequestHandler):
    """Fake WebServer recording the last exec request."""

    last = {}
    status = 200
    body = OK

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        type(self).last = {
            "path": self.path.split("?")[0],
            "json": json.loads(raw.decode() or "{}"),
            "content_type": self.headers.get("Content-Type"),
            "token": self.headers.get("X-Auth-Token"),
        }
        payload = json.dumps(type(self).body).encode()
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class ServerCase(unittest.TestCase):
    def setUp(self):
        _RecordingHandler.last = {}
        _RecordingHandler.status = 200
        _RecordingHandler.body = dict(OK)
        self.server = http.server.HTTPServer(("127.0.0.1", 0), _RecordingHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class TestServerProxyExec(ServerCase):
    def test_posts_json_to_exec_endpoint(self):
        proxy = ServerProxy(self.url, token="tok")
        result = proxy.exec_cmd("ls -l", timeout=4, ack_timeout=0.5, max_retries=2)
        self.assertEqual(result, OK)
        last = _RecordingHandler.last
        self.assertEqual(last["path"], "/api/fpb/exec")
        self.assertEqual(last["content_type"], "application/json")
        self.assertEqual(last["token"], "tok")
        self.assertEqual(
            last["json"],
            {"cmd": "ls -l", "timeout": 4, "ack_timeout": 0.5, "max_retries": 2},
        )

    def test_max_retries_omitted_when_none(self):
        ServerProxy(self.url).exec_cmd("ls")
        self.assertNotIn("max_retries", _RecordingHandler.last["json"])

    def test_timeout_omitted_when_not_given(self):
        ServerProxy(self.url).exec_cmd("ls")
        self.assertNotIn("timeout", _RecordingHandler.last["json"])

    def test_http_timeout_covers_long_commands(self):
        proxy = ServerProxy(self.url)
        with patch.object(proxy, "_post", return_value=OK) as post:
            proxy.exec_cmd("sleep 100", timeout=100, ack_timeout=1, max_retries=3)
        self.assertGreaterEqual(
            post.call_args.kwargs["timeout"],
            exec_client.worst_case_seconds(100, 1, 3),
        )
        self.assertGreater(post.call_args.kwargs["timeout"], 100)

    def test_http_timeout_covers_default_wait(self):
        proxy = ServerProxy(self.url)
        with patch.object(proxy, "_post", return_value=OK) as post:
            proxy.exec_cmd("ls")
        self.assertGreater(post.call_args.kwargs["timeout"], exec_client.DEFAULT_WAIT_S)

    def test_http_timeout_assumes_max_retries_when_server_decides(self):
        proxy = ServerProxy(self.url)
        with patch.object(proxy, "_post", return_value=OK) as post:
            proxy.exec_cmd("ls", timeout=10)
        self.assertGreaterEqual(
            post.call_args.kwargs["timeout"],
            exec_client.worst_case_seconds(10, 1.0, exec_client.MAX_RETRIES_LIMIT),
        )

    def test_bad_request_body_returned(self):
        _RecordingHandler.status = 400
        _RecordingHandler.body = {
            "success": False,
            "error": "cmd must be a non-empty string",
            "error_code": "bad_request",
        }
        result = ServerProxy(self.url).exec_cmd("ls")
        self.assertEqual(result["error_code"], "bad_request")

    def test_unsupported_media_type_body_returned(self):
        _RecordingHandler.status = 415
        _RecordingHandler.body = {"success": False, "error_code": "bad_request"}
        self.assertFalse(ServerProxy(self.url).exec_cmd("ls")["success"])

    def test_other_http_errors_propagate(self):
        _RecordingHandler.status = 500
        with self.assertRaises(HTTPError):
            ServerProxy(self.url).exec_cmd("ls")

    def test_auth_errors_become_proxy_auth_error(self):
        _RecordingHandler.status = 403
        with self.assertRaises(ProxyAuthError):
            ServerProxy(self.url).exec_cmd("ls")

    def test_unparsable_error_body_propagates(self):
        proxy = ServerProxy(self.url)
        err = HTTPError("http://x", 400, "Bad", {}, io.BytesIO(b"not json"))
        with patch.object(proxy, "_post", side_effect=err):
            with self.assertRaises(HTTPError):
                proxy.exec_cmd("ls")


class TestClientExecProxyMode(unittest.TestCase):
    def test_delegates_to_proxy(self):
        c = Client("http://127.0.0.1:1")
        with patch.object(c._proxy, "exec_cmd", return_value=OK) as m:
            result = c.exec_cmd("ls", timeout=3, ack_timeout=0.5, max_retries=2)
        self.assertEqual(result, OK)
        m.assert_called_once_with("ls", 3, 0.5, 2)

    def test_defaults(self):
        c = Client("http://127.0.0.1:1")
        with patch.object(c._proxy, "exec_cmd", return_value=OK) as m:
            c.exec_cmd("ls")
        m.assert_called_once_with("ls", None, 1.0, None)

    def test_protocol_failure_returned_not_raised(self):
        c = Client("http://127.0.0.1:1")
        failure = dict(OK, success=False, error_code="unknown_state")
        with patch.object(c._proxy, "exec_cmd", return_value=failure):
            self.assertEqual(c.exec_cmd("sleep 9")["error_code"], "unknown_state")

    def test_invalid_arguments_raise_without_request(self):
        c = Client("http://127.0.0.1:1")
        with patch.object(c._proxy, "exec_cmd") as m:
            for kwargs in (
                {"cmd": ""},
                {"cmd": "ls", "timeout": 0},
                {"cmd": "ls", "ack_timeout": -1},
                {"cmd": "ls", "max_retries": -1},
                {"cmd": "ls", "max_retries": 99},
            ):
                with self.assertRaises(FPBError, msg=str(kwargs)):
                    c.exec_cmd(**kwargs)
        m.assert_not_called()

    def test_auth_error_mapped(self):
        c = Client("http://127.0.0.1:1")
        with patch.object(c._proxy, "exec_cmd", side_effect=ProxyAuthError("no")):
            with self.assertRaises(AuthError):
                c.exec_cmd("ls")

    def test_unreachable_server_mapped(self):
        c = Client("http://127.0.0.1:1")
        with patch.object(c._proxy, "exec_cmd", side_effect=ConnectionRefusedError()):
            with self.assertRaises(ServerUnavailable):
                c.exec_cmd("ls")

    def test_offline_mode_has_no_device(self):
        with self.assertRaises(DeviceNotConnected):
            Client.offline().exec_cmd("ls")

    def test_end_to_end_over_http(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), _RecordingHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            _RecordingHandler.body = dict(OK, output="from server\n")
            c = Client(f"http://127.0.0.1:{server.server_address[1]}")
            result = c.exec_cmd("echo hi", timeout=2)
            self.assertEqual(result["output"], "from server\n")
            self.assertEqual(_RecordingHandler.last["json"]["cmd"], "echo hi")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class TestClientExecDirectMode(unittest.TestCase):
    def _direct_client(self):
        from contextlib import contextmanager

        fake_lock = MagicMock()
        fake_lock.acquire.return_value = True
        with patch("fpbinject.utils.port_lock.PortLock", return_value=fake_lock):
            with patch("fpbinject.cli.fpb_cli.DeviceState") as state_cls:
                dev_state = MagicMock()
                dev_state.connected = True
                state_cls.return_value = dev_state
                with patch("fpbinject.fpb_inject.FPBInject") as fpb_cls:
                    fpb = MagicMock()

                    @contextmanager
                    def fl_session():
                        try:
                            yield fpb
                        finally:
                            fpb.exit_fl_mode()

                    fpb.fl_session.side_effect = fl_session
                    fpb_cls.return_value = fpb
                    client = Client.direct("/dev/ttyACM0")
        return client, fpb

    def test_runs_in_process_inside_fl_session(self):
        client, fpb = self._direct_client()
        fpb.exec_cmd.return_value = dict(OK)
        result = client.exec_cmd("ls", timeout=3, ack_timeout=0.5, max_retries=1)
        self.assertEqual(result, OK)
        fpb.exec_cmd.assert_called_once_with(
            "ls", timeout=3, ack_timeout=0.5, max_retries=1
        )
        fpb.fl_session.assert_called()
        fpb.exit_fl_mode.assert_called()

    def test_default_retries_left_to_the_core(self):
        client, fpb = self._direct_client()
        fpb.exec_cmd.return_value = dict(OK)
        client.exec_cmd("ls")
        self.assertIsNone(fpb.exec_cmd.call_args.kwargs["max_retries"])

    def test_invalid_arguments_raise(self):
        client, fpb = self._direct_client()
        with self.assertRaises(FPBError):
            client.exec_cmd("")
        fpb.exec_cmd.assert_not_called()

    def test_requires_connected_device(self):
        client, fpb = self._direct_client()
        client._device_state.connected = False
        with self.assertRaises(DeviceNotConnected):
            client.exec_cmd("ls")


class TestCapabilityParity(unittest.TestCase):
    def test_cli_exec_has_sdk_method(self):
        self.assertTrue(hasattr(Client, "exec_cmd"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def run_cli(method, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = method(*args, **kwargs)
    return result, buf.getvalue()


class TestCliExec(unittest.TestCase):
    def setUp(self):
        self.cli = FPBCLI(verbose=False)
        self.addCleanup(self.cli.cleanup)

    def test_proxy_mode_prints_json_and_returns_true(self):
        self.cli._proxy = MagicMock()
        self.cli._proxy.exec_cmd.return_value = dict(OK)
        ok, out = run_cli(self.cli.exec_cmd, "ls", 4.0)
        self.assertTrue(ok)
        self.assertEqual(json.loads(out), OK)
        self.cli._proxy.exec_cmd.assert_called_once_with("ls", timeout=4.0)

    def test_proxy_failure_returns_false_but_prints_result(self):
        self.cli._proxy = MagicMock()
        failure = dict(OK, success=False, error_code="unknown_state", error="stuck")
        self.cli._proxy.exec_cmd.return_value = failure
        ok, out = run_cli(self.cli.exec_cmd, "sleep 99")
        self.assertFalse(ok)
        self.assertEqual(json.loads(out)["error_code"], "unknown_state")

    def test_direct_mode_runs_in_fl_session(self):
        from contextlib import contextmanager

        self.cli._proxy = None
        self.cli._device_state.connected = True
        fpb = MagicMock()
        fpb.exec_cmd.return_value = dict(OK)

        @contextmanager
        def fl_session():
            yield fpb

        fpb.fl_session.side_effect = fl_session
        self.cli._fpb = fpb
        ok, out = run_cli(self.cli.exec_cmd, "ls", 2.0)
        self.assertTrue(ok)
        fpb.exec_cmd.assert_called_once_with("ls", timeout=2.0)
        fpb.fl_session.assert_called_once()

    def test_no_device_prints_error(self):
        self.cli._proxy = None
        self.cli._device_state.connected = False
        with self.assertRaises(FPBCLIError):
            self.cli.exec_cmd("ls")

    def test_invalid_argument_becomes_cli_error(self):
        self.cli._proxy = MagicMock()
        self.cli._proxy.exec_cmd.side_effect = exec_client.ExecArgumentError("bad")
        with self.assertRaises(FPBCLIError):
            self.cli.exec_cmd("ls")

    def test_transport_error_is_reported_as_failure(self):
        self.cli._proxy = MagicMock()
        self.cli._proxy.exec_cmd.side_effect = ConnectionRefusedError("down")
        ok, out = run_cli(self.cli.exec_cmd, "ls")
        self.assertFalse(ok)
        self.assertFalse(json.loads(out)["success"])
        self.assertIn("down", json.loads(out)["error"])


class TestCliMainExec(unittest.TestCase):
    def setUp(self):
        for target, value in (
            ("fpbinject.cli.connection_resolver.discover_sync", []),
            ("fpbinject.cli.connection_resolver.list_cli_servers", []),
            ("fpbinject.cli.connection_resolver._localhost_status_ok", False),
        ):
            p = patch(target, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def _run_main(self, argv, exec_result):
        with patch("sys.argv", ["fpb_cli.py"] + argv):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as cli_cls:
                cli = MagicMock()
                cli.exec_cmd.return_value = exec_result
                cli_cls.return_value = cli
                try:
                    main()
                    code = 0
                except SystemExit as e:
                    code = e.code
        return cli, code

    def test_dispatch_with_default_timeout(self):
        cli, code = self._run_main(["exec", "ls -l /data"], True)
        cli.exec_cmd.assert_called_once_with("ls -l /data", None)
        self.assertEqual(code, 0)

    def test_dispatch_with_timeout_option(self):
        cli, _ = self._run_main(["exec", "sleep 3", "--timeout", "30"], True)
        cli.exec_cmd.assert_called_once_with("sleep 3", 30.0)

    def test_failure_sets_exit_code(self):
        _, code = self._run_main(["exec", "ls"], False)
        self.assertEqual(code, 1)

    def test_cleanup_runs_on_failure(self):
        cli, _ = self._run_main(["exec", "ls"], False)
        cli.cleanup.assert_called()


if __name__ == "__main__":
    unittest.main()

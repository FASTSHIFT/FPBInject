#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for virtual serial passthrough CLI + proxy support.

Covers:
- ServerProxy.vserial_status/start/stop HTTP wrappers (against a mock server).
- FPBCLI.vserial dispatch and the proxy-required guard for headless usage.
"""

import http.server
import io
import json
import sys
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from fpbinject.cli.server_proxy import ServerProxy  # noqa: E402
from fpbinject.cli.connection_plan import ConnectionPlan, ConnectionMode  # noqa: E402
from fpbinject.cli.fpb_cli import FPBCLI  # noqa: E402
from fixtures.mock_http import MockHTTPHandler as _MockHTTPHandler  # noqa: E402


class TestServerProxyVSerial(unittest.TestCase):
    """ServerProxy virtual-serial HTTP wrappers against a mock server."""

    @classmethod
    def setUpClass(cls):
        _MockHTTPHandler.responses = {
            "/api/vserial/status": {
                "success": True,
                "enabled": True,
                "slave": "/dev/pts/7",
                "symlink": "/tmp/fpb-tty0",
            },
            "/api/vserial/start": {
                "success": True,
                "enabled": True,
                "slave": "/dev/pts/7",
                "symlink": "/tmp/fpb-tty0",
            },
            "/api/vserial/stop": {"success": True},
        }
        _MockHTTPHandler.sse_responses = {}
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _MockHTTPHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _proxy(self):
        return ServerProxy(base_url=self.base_url)

    def test_vserial_status(self):
        result = self._proxy().vserial_status()
        self.assertTrue(result["success"])
        self.assertEqual(result["slave"], "/dev/pts/7")

    def test_vserial_start(self):
        result = self._proxy().vserial_start(symlink="/tmp/fpb-tty0")
        self.assertTrue(result["success"])
        self.assertTrue(result["enabled"])

    def test_vserial_start_omits_none_params(self):
        # Should not raise when optional params are None.
        result = self._proxy().vserial_start()
        self.assertTrue(result["success"])

    def test_vserial_stop(self):
        result = self._proxy().vserial_stop()
        self.assertTrue(result["success"])


def _make_cli_offline():
    """Build an FPBCLI with an OFFLINE plan (no proxy attached)."""
    plan = ConnectionPlan(mode=ConnectionMode.OFFLINE, source="test")
    return FPBCLI(plan=plan)


class TestCLIVSerialProxyGuard(unittest.TestCase):
    """vserial-* commands require proxy mode (headless PTY host)."""

    def _run(self, method_name, *args):
        cli = _make_cli_offline()
        buf = io.StringIO()
        with redirect_stdout(buf):
            getattr(cli, method_name)(*args)
        return json.loads(buf.getvalue())

    def test_start_requires_proxy(self):
        out = self._run("vserial_start")
        self.assertFalse(out["success"])
        self.assertIn("requires a running WebServer", out["error"])

    def test_stop_requires_proxy(self):
        out = self._run("vserial_stop")
        self.assertFalse(out["success"])
        self.assertIn("requires a running WebServer", out["error"])

    def test_status_requires_proxy(self):
        out = self._run("vserial_status")
        self.assertFalse(out["success"])
        self.assertIn("requires a running WebServer", out["error"])


class TestCLIVSerialDispatch(unittest.TestCase):
    """vserial-* CLI methods forward to the proxy."""

    def _cli_with_mock_proxy(self):
        cli = _make_cli_offline()
        cli._proxy = MagicMock()
        cli._proxy.vserial_status.return_value = {"success": True, "enabled": False}
        cli._proxy.vserial_start.return_value = {"success": True, "enabled": True}
        cli._proxy.vserial_stop.return_value = {"success": True}
        return cli

    def _run(self, cli, method_name, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            getattr(cli, method_name)(*args)
        return json.loads(buf.getvalue())

    def test_status_dispatch(self):
        cli = self._cli_with_mock_proxy()
        out = self._run(cli, "vserial_status")
        self.assertTrue(out["success"])
        cli._proxy.vserial_status.assert_called_once()

    def test_start_dispatch_passes_params(self):
        cli = self._cli_with_mock_proxy()
        out = self._run(cli, "vserial_start", "/tmp/mytty")
        self.assertTrue(out["success"])
        cli._proxy.vserial_start.assert_called_once_with(symlink="/tmp/mytty")

    def test_stop_dispatch(self):
        cli = self._cli_with_mock_proxy()
        out = self._run(cli, "vserial_stop")
        self.assertTrue(out["success"])
        cli._proxy.vserial_stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()

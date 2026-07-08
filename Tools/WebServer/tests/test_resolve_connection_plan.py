#!/usr/bin/env python3
"""Tests for resolve_connection_plan() — the new single resolver.

Pins the precedence ladder (Decision Matrix in Discovery.md). Each test
fixes ONE row of the matrix so a regression points at the exact rule.
"""

import argparse
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.connection_plan import (  # noqa: E402
    CommandPolicy,
    ConnectionMode,
)


def _import_resolver():
    from cli.fpb_cli import resolve_connection_plan  # noqa: E402

    return resolve_connection_plan


def _ns(**kwargs):
    """argparse.Namespace with defaults that mirror build_parser().

    For convenience, ``server_url=URL`` is mapped to ``server=URL`` (URL is
    one of the three forms ``-s`` accepts) so existing test bodies remain
    readable. ``server_url_legacy`` exercises the deprecated --server-url path.
    """
    if "server_url" in kwargs:
        kwargs.setdefault("server", kwargs.pop("server_url"))
    defaults = dict(
        command="info",
        command_policy=CommandPolicy.DEVICE,
        server=None,
        server_url_legacy=None,
        no_discovery=False,
        token=None,
        port=None,
        baudrate=115200,
        direct=False,
        verbose=False,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _fake_server(host="192.168.1.20", port=5500, version="1.6.6", auth="token"):
    from cli.discover import FPBServer

    return FPBServer(
        name=f"fake-{host}-{port}",
        host=host,
        port=port,
        version=version,
        auth=auth,
        device="none",
        path="/api",
        url=f"http://{host}:{port}",
        id=f"fpb:fake-{host}-{port}",
        handle=f"{host}:{port}",
    )


class TestOfflineAndAdmin(unittest.TestCase):
    """Policies that never produce a connection."""

    def test_offline_command_returns_offline_plan(self):
        resolve = _import_resolver()
        plan = resolve(_ns(command="analyze", command_policy=CommandPolicy.OFFLINE))
        self.assertEqual(plan.mode, ConnectionMode.OFFLINE)
        self.assertIsNone(plan.server_url)

    def test_server_admin_command_returns_offline_plan(self):
        resolve = _import_resolver()
        plan = resolve(
            _ns(command="server-stop", command_policy=CommandPolicy.SERVER_ADMIN)
        )
        self.assertEqual(plan.mode, ConnectionMode.OFFLINE)
        self.assertIsNone(plan.server_url)


class TestDirectMode(unittest.TestCase):
    """--direct produces a DIRECT plan with the user's --port."""

    def test_direct_with_port(self):
        resolve = _import_resolver()
        plan = resolve(_ns(direct=True, port="/dev/ttyACM0", baudrate=921600))
        self.assertEqual(plan.mode, ConnectionMode.DIRECT)
        self.assertEqual(plan.serial_port, "/dev/ttyACM0")
        self.assertEqual(plan.baudrate, 921600)
        self.assertIsNone(plan.server_url)


class TestInvalidFlagCombos(unittest.TestCase):
    """Rejected at resolve time so the user sees one clear error, not a silent no-op."""

    def test_direct_with_server_url_rejected(self):
        from cli.fpb_cli import FPBCLIError

        resolve = _import_resolver()
        with self.assertRaises(FPBCLIError) as cm:
            resolve(
                _ns(direct=True, server_url="http://1.2.3.4:5500", port="/dev/ttyACM0")
            )
        self.assertIn("--direct", str(cm.exception))
        self.assertIn("--server-url", str(cm.exception))

    def test_direct_without_port_for_device_command_rejected(self):
        from cli.fpb_cli import FPBCLIError

        resolve = _import_resolver()
        with self.assertRaises(FPBCLIError) as cm:
            resolve(_ns(direct=True, port=None, command_policy=CommandPolicy.DEVICE))
        self.assertIn("--direct", str(cm.exception))
        self.assertIn("--port", str(cm.exception))


class TestExplicitServerUrl(unittest.TestCase):
    """--server-url and FPB_SERVER_URL bypass discovery."""

    def test_explicit_localhost_url_local_mode(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server_url="http://127.0.0.1:5500"))
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)
        self.assertEqual(plan.server_url, "http://127.0.0.1:5500")
        self.assertEqual(plan.source, "flag")

    def test_explicit_remote_url_remote_mode(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server_url="http://192.168.1.20:5500", token="t"))
        self.assertEqual(plan.mode, ConnectionMode.REMOTE_PROXY)
        self.assertEqual(plan.server_url, "http://192.168.1.20:5500")
        self.assertEqual(plan.token, "t")

    @patch.dict(os.environ, {"FPB_SERVER_URL": "http://192.168.1.30:5501"}, clear=False)
    def test_env_url_used_when_no_flag(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server=None))
        self.assertEqual(plan.mode, ConnectionMode.REMOTE_PROXY)
        self.assertEqual(plan.server_url, "http://192.168.1.30:5501")
        self.assertEqual(plan.source, "legacy-env")

    @patch.dict(os.environ, {}, clear=True)
    def test_explicit_url_does_not_call_discovery(self):
        resolve = _import_resolver()
        with patch("cli.fpb_cli.discover_sync") as mock_disc:
            resolve(_ns(server_url="http://1.2.3.4:5500"))
        mock_disc.assert_not_called()


class TestImplicitLocalShortCircuit(unittest.TestCase):
    """No URL/env: prefer single PID server, then localhost probe, then mDNS."""

    @patch.dict(os.environ, {}, clear=True)
    def test_single_pid_server_short_circuits_discovery(self):
        resolve = _import_resolver()
        with patch(
            "cli.fpb_cli.list_cli_servers",
            return_value=[{"port": 5599, "pid": 1234}],
        ), patch("cli.fpb_cli.discover_sync") as mock_disc:
            plan = resolve(_ns())
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)
        self.assertEqual(plan.server_url, "http://127.0.0.1:5599")
        self.assertEqual(plan.source, "pid")
        mock_disc.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_localhost_default_probe_short_circuits_discovery(self):
        resolve = _import_resolver()
        with patch("cli.fpb_cli.list_cli_servers", return_value=[]), patch(
            "cli.fpb_cli._localhost_status_ok", return_value=True
        ), patch("cli.fpb_cli.discover_sync") as mock_disc:
            plan = resolve(_ns())
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)
        self.assertEqual(plan.server_url, "http://127.0.0.1:5500")
        self.assertEqual(plan.source, "localhost-default")
        mock_disc.assert_not_called()


class TestNoDiscoveryFlag(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_discovery_falls_back_to_default_localhost(self):
        resolve = _import_resolver()
        with patch("cli.fpb_cli.list_cli_servers", return_value=[]), patch(
            "cli.fpb_cli._localhost_status_ok", return_value=False
        ), patch("cli.fpb_cli.discover_sync") as mock_disc:
            plan = resolve(_ns(no_discovery=True))
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)
        self.assertEqual(plan.server_url, "http://127.0.0.1:5500")
        mock_disc.assert_not_called()


class TestMdnsBranches(unittest.TestCase):
    """When implicit localhost/PID short-circuits don't fire, run mDNS."""

    @patch.dict(os.environ, {}, clear=True)
    def test_zero_results_falls_back_to_localhost_default(self):
        resolve = _import_resolver()
        with patch("cli.fpb_cli.list_cli_servers", return_value=[]), patch(
            "cli.fpb_cli._localhost_status_ok", return_value=False
        ), patch("cli.fpb_cli.discover_sync", return_value=[]):
            plan = resolve(_ns())
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)
        self.assertEqual(plan.server_url, "http://127.0.0.1:5500")

    @patch.dict(os.environ, {}, clear=True)
    def test_one_local_result_returns_local_proxy(self):
        resolve = _import_resolver()
        with patch("cli.fpb_cli.list_cli_servers", return_value=[]), patch(
            "cli.fpb_cli._localhost_status_ok", return_value=False
        ), patch(
            "cli.fpb_cli.discover_sync",
            return_value=[_fake_server(host="127.0.0.1", port=5500)],
        ):
            plan = resolve(_ns())
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)
        self.assertEqual(plan.server_url, "http://127.0.0.1:5500")
        self.assertEqual(plan.source, "mdns")

    @patch.dict(os.environ, {}, clear=True)
    def test_one_remote_result_returns_remote_proxy(self):
        resolve = _import_resolver()
        with patch("cli.fpb_cli.list_cli_servers", return_value=[]), patch(
            "cli.fpb_cli._localhost_status_ok", return_value=False
        ), patch(
            "cli.fpb_cli.discover_sync",
            return_value=[_fake_server(host="192.168.1.20", port=5500)],
        ):
            plan = resolve(_ns())
        self.assertEqual(plan.mode, ConnectionMode.REMOTE_PROXY)
        self.assertEqual(plan.server_url, "http://192.168.1.20:5500")

    @patch.dict(os.environ, {}, clear=True)
    def test_two_results_raises_ambiguous_server_error(self):
        from cli.fpb_cli import AmbiguousServerError

        resolve = _import_resolver()
        servers = [
            _fake_server(host="10.0.0.10", port=5500),
            _fake_server(host="10.0.0.11", port=5500),
        ]
        with patch("cli.fpb_cli.list_cli_servers", return_value=[]), patch(
            "cli.fpb_cli._localhost_status_ok", return_value=False
        ), patch("cli.fpb_cli.discover_sync", return_value=servers):
            with self.assertRaises(AmbiguousServerError) as cm:
                resolve(_ns())
        self.assertEqual(cm.exception.exit_code, 2)
        self.assertIn("10.0.0.10:5500", str(cm.exception))
        self.assertIn("10.0.0.11:5500", str(cm.exception))
        self.assertIn("-s ", str(cm.exception))


class TestPlanProperties(unittest.TestCase):
    """Plans expose allow_launch / allow_direct_fallback consistently."""

    def test_local_plan_with_serial_port_allows_launch_and_direct_fallback(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server_url="http://127.0.0.1:5500", port="/dev/ttyACM0"))
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)
        self.assertEqual(plan.serial_port, "/dev/ttyACM0")
        self.assertTrue(plan.allow_launch)
        self.assertTrue(plan.allow_direct_fallback)

    def test_remote_plan_never_allows_launch_or_direct(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server_url="http://192.168.1.20:5500", port="/dev/ttyACM0"))
        self.assertEqual(plan.mode, ConnectionMode.REMOTE_PROXY)
        self.assertFalse(plan.allow_launch)
        self.assertFalse(plan.allow_direct_fallback)


if __name__ == "__main__":
    unittest.main()

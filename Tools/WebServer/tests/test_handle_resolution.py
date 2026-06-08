#!/usr/bin/env python3
"""Tests for the -s/--server / FPB_SERVER handle resolution.

Pins the user-facing ergonomics: one flag accepts URL, host:port, or host.
"""

import argparse
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.connection_plan import CommandPolicy, ConnectionMode  # noqa: E402
from cli.discover import (  # noqa: E402
    FPBServer,
    classify_handle,
    find_by_handle,
)


def _ns(**kwargs):
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


def _server(host, port, name=None, handle=None):
    return FPBServer(
        name=name or f"FPBInject on {host}:{port}._fpbinject._tcp.local.",
        host=host,
        port=port,
        version="1.6.6",
        auth="token",
        device="none",
        path="/api",
        url=f"http://{host}:{port}",
        id=f"fpb:{host}-{port}",
        handle=handle or f"{host}:{port}",
    )


class TestClassifyHandle(unittest.TestCase):
    """Three distinct shapes of -s value."""

    def test_url_with_scheme(self):
        self.assertEqual(classify_handle("http://1.2.3.4:5500"), "url")
        self.assertEqual(classify_handle("https://x.y.z:5500/api"), "url")

    def test_host_port(self):
        self.assertEqual(classify_handle("bench:5501"), "host_port")
        self.assertEqual(classify_handle("192.168.1.20:5500"), "host_port")

    def test_host_only(self):
        self.assertEqual(classify_handle("bench"), "host")
        self.assertEqual(classify_handle("bench.local"), "host")

    def test_host_port_with_non_numeric_port_falls_back_to_host(self):
        # ipv6-ish or weird strings: not host:port.
        self.assertEqual(classify_handle("foo:bar"), "host")


class TestFindByHandle(unittest.TestCase):
    """Filter discovered list by user-supplied handle."""

    def setUp(self):
        self.servers = [
            _server("bench", 5500),
            _server("bench", 5501),
            _server("lab", 5500),
        ]

    def test_host_port_exact(self):
        matches = find_by_handle(self.servers, "bench:5501")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].port, 5501)

    def test_host_only_matches_all_with_that_host(self):
        matches = find_by_handle(self.servers, "bench")
        self.assertEqual(len(matches), 2)

    def test_host_only_unique_returns_one(self):
        matches = find_by_handle(self.servers, "lab")
        self.assertEqual(len(matches), 1)

    def test_no_match(self):
        self.assertEqual(find_by_handle(self.servers, "nope"), [])


def _import_resolver():
    from cli.fpb_cli import resolve_connection_plan  # noqa: E402

    return resolve_connection_plan


class TestServerFlagResolves(unittest.TestCase):
    """End-to-end: -s handle goes through resolver and produces correct URL."""

    @patch.dict(os.environ, {}, clear=True)
    def test_url_in_s_flag_used_verbatim(self):
        resolve = _import_resolver()
        with patch("cli.fpb_cli.discover_sync_by_handle") as mock_disc:
            plan = resolve(_ns(server="http://1.2.3.4:5500"))
        self.assertEqual(plan.server_url, "http://1.2.3.4:5500")
        self.assertEqual(plan.mode, ConnectionMode.REMOTE_PROXY)
        mock_disc.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_host_port_resolved_via_mdns(self):
        resolve = _import_resolver()
        with patch(
            "cli.fpb_cli.discover_sync_by_handle",
            return_value=[_server("127.0.0.1", 5501, handle="bench:5501")],
        ):
            plan = resolve(_ns(server="bench:5501"))
        self.assertEqual(plan.server_url, "http://127.0.0.1:5501")
        self.assertEqual(plan.mode, ConnectionMode.LOCAL_PROXY)

    @patch.dict(os.environ, {}, clear=True)
    def test_host_only_unique_resolves(self):
        resolve = _import_resolver()
        with patch(
            "cli.fpb_cli.discover_sync_by_handle",
            return_value=[_server("127.0.0.1", 5500, handle="bench:5500")],
        ):
            plan = resolve(_ns(server="bench"))
        self.assertEqual(plan.server_url, "http://127.0.0.1:5500")

    @patch.dict(os.environ, {}, clear=True)
    def test_host_only_ambiguous_raises(self):
        from cli.fpb_cli import FPBCLIError

        resolve = _import_resolver()
        with patch(
            "cli.fpb_cli.discover_sync_by_handle",
            return_value=[
                _server("127.0.0.1", 5500, handle="bench:5500"),
                _server("127.0.0.1", 5501, handle="bench:5501"),
            ],
        ):
            with self.assertRaises(FPBCLIError) as cm:
                resolve(_ns(server="bench"))
        self.assertIn("ambiguous", str(cm.exception))

    @patch.dict(os.environ, {}, clear=True)
    def test_handle_no_match_raises(self):
        from cli.fpb_cli import FPBCLIError

        resolve = _import_resolver()
        with patch("cli.fpb_cli.discover_sync_by_handle", return_value=[]):
            with self.assertRaises(FPBCLIError) as cm:
                resolve(_ns(server="nope:5500"))
        self.assertIn("No FPBInject server matches", str(cm.exception))


class TestFpbServerEnv(unittest.TestCase):
    """FPB_SERVER env var goes through the same handle resolution."""

    @patch.dict(os.environ, {"FPB_SERVER": "http://1.2.3.4:5500"}, clear=False)
    def test_env_url(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server=None))
        self.assertEqual(plan.server_url, "http://1.2.3.4:5500")

    @patch.dict(os.environ, {"FPB_SERVER": "bench:5501"}, clear=False)
    def test_env_handle_resolved(self):
        resolve = _import_resolver()
        with patch(
            "cli.fpb_cli.discover_sync_by_handle",
            return_value=[_server("127.0.0.1", 5501, handle="bench:5501")],
        ):
            plan = resolve(_ns(server=None))
        self.assertEqual(plan.server_url, "http://127.0.0.1:5501")


class TestServerFlagWinsOverEnv(unittest.TestCase):
    @patch.dict(os.environ, {"FPB_SERVER": "http://env.host:7777"}, clear=False)
    def test_flag_overrides_env(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server="http://flag.host:8888"))
        self.assertEqual(plan.server_url, "http://flag.host:8888")


class TestLegacyServerUrlDeprecation(unittest.TestCase):
    """--server-url and FPB_SERVER_URL still work but warn under -v."""

    @patch.dict(os.environ, {}, clear=True)
    def test_legacy_flag_still_works(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server_url_legacy="http://legacy.host:5500"))
        self.assertEqual(plan.server_url, "http://legacy.host:5500")

    @patch.dict(os.environ, {}, clear=True)
    def test_legacy_flag_warns_under_verbose(self):
        import io
        from contextlib import redirect_stderr

        resolve = _import_resolver()
        err = io.StringIO()
        with redirect_stderr(err):
            resolve(_ns(server_url_legacy="http://legacy.host:5500", verbose=True))
        self.assertIn("deprecated", err.getvalue())

    @patch.dict(os.environ, {"FPB_SERVER_URL": "http://legacy.env:5500"}, clear=False)
    def test_legacy_env_still_works(self):
        resolve = _import_resolver()
        plan = resolve(_ns(server=None, server_url_legacy=None))
        self.assertEqual(plan.server_url, "http://legacy.env:5500")


class TestNewFlagWinsOverLegacy(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_s_flag_wins_over_server_url(self):
        resolve = _import_resolver()
        plan = resolve(
            _ns(
                server="http://new.host:5500",
                server_url_legacy="http://old.host:5500",
            )
        )
        self.assertEqual(plan.server_url, "http://new.host:5500")


if __name__ == "__main__":
    unittest.main()

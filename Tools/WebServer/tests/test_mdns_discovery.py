#!/usr/bin/env python3
"""Test cases for mDNS discovery (cli.discover) and CLI integration.

Covers scenarios:
  S2 single-result attach
  S3 zero-result fallback to localhost
  S4 multi-result list+exit-2
  S5 explicit --server-url / FPB_SERVER_URL bypass
  S6 --no-discovery bypass
  S7 offline subcommand zero-delay (no discovery call)
  S8 'discover' subcommand emits JSON list
  Plus the underlying discover() async semantics.
"""

import argparse
import asyncio
import io
import json
import os
import sys
import time
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _import_discover():
    from cli.discover import discover, discover_sync, FPBServer  # noqa: E402

    return discover, discover_sync, FPBServer


def _import_cli_helpers():
    """Lazy import of CLI helpers added by T8 (resolve_server_url, cmd_discover).

    These live in cli.fpb_cli; importing eagerly would break tests during the
    RED phase before T8 wires them in.
    """
    from cli.fpb_cli import resolve_server_url, cmd_discover  # noqa: E402

    return resolve_server_url, cmd_discover


def _fake_async_browser_factory(service_names_to_emit):
    """Build a stub AsyncServiceBrowser class that fires Added events for
    each service name as soon as it is constructed.

    The real AsyncServiceBrowser signature: AsyncServiceBrowser(zc, types, handlers=...).
    """
    from zeroconf import ServiceStateChange

    class _StubBrowser:
        def __init__(self, zc, types, handlers=None):
            self.zc = zc
            self.types = types
            handler_list = handlers or []
            for h in handler_list:
                for name in service_names_to_emit:
                    h(
                        zeroconf=zc,
                        service_type="_fpbinject._tcp.local.",
                        name=name,
                        state_change=ServiceStateChange.Added,
                    )

        async def async_cancel(self):
            return None

    return _StubBrowser


def _fake_async_service_info_factory(props_by_name):
    """Build a stub AsyncServiceInfo class that returns canned TXT/port/ip.

    props_by_name maps service-name -> dict(port=..., addresses=[bytes], properties={k: bytes})
    """

    class _StubInfo:
        def __init__(self, type_, name):
            self.type_ = type_
            self.name = name
            self._spec = props_by_name.get(name)

        async def async_request(self, zc, timeout_ms):
            return self._spec is not None

        @property
        def port(self):
            return self._spec["port"]

        @property
        def properties(self):
            return self._spec["properties"]

        def parsed_scoped_addresses(self):
            return self._spec.get("addresses", ["127.0.0.1"])

    return _StubInfo


# ---- discover() async semantics (S2/S3/S4 module-level) ----------------------


class TestDiscoverAsync(unittest.TestCase):
    """discover() async semantics — uses patched zeroconf classes."""

    def test_discover_zero_results(self):
        discover, _, _ = _import_discover()
        Browser = _fake_async_browser_factory([])
        Info = _fake_async_service_info_factory({})
        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ):
            servers = asyncio.run(discover(timeout=0.05))
        self.assertEqual(servers, [])

    def test_discover_one_result(self):
        _, _, FPBServer = _import_discover()
        discover, _, _ = _import_discover()
        name = "FPB._fpbinject._tcp.local."
        Browser = _fake_async_browser_factory([name])
        Info = _fake_async_service_info_factory(
            {
                name: {
                    "port": 5500,
                    "addresses": ["192.168.1.20"],
                    "properties": {
                        b"txtvers": b"1",
                        b"version": b"1.6.6",
                        b"auth": b"token",
                        b"device": b"none",
                        b"path": b"/api",
                    },
                }
            }
        )
        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ):
            servers = asyncio.run(discover(timeout=0.1))
        self.assertEqual(len(servers), 1)
        s = servers[0]
        self.assertEqual(s.host, "192.168.1.20")
        self.assertEqual(s.port, 5500)
        self.assertEqual(s.version, "1.6.6")
        self.assertEqual(s.auth, "token")
        self.assertEqual(s.device, "none")
        self.assertEqual(s.path, "/api")
        self.assertEqual(s.url, "http://192.168.1.20:5500")

    def test_discover_many_results(self):
        discover, _, _ = _import_discover()
        names = [f"FPB-{i}._fpbinject._tcp.local." for i in range(3)]
        Browser = _fake_async_browser_factory(names)
        Info = _fake_async_service_info_factory(
            {
                n: {
                    "port": 5500 + i,
                    "addresses": [f"10.0.0.{10 + i}"],
                    "properties": {
                        b"txtvers": b"1",
                        b"version": b"1.6.6",
                        b"auth": b"token",
                        b"device": b"none",
                        b"path": b"/api",
                    },
                }
                for i, n in enumerate(names)
            }
        )
        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ):
            servers = asyncio.run(discover(timeout=0.1))
        self.assertEqual(len(servers), 3)


# ---- resolve_server_url() precedence ladder (S2/S3/S4/S5/S6/S7) --------------


def _ns(**kwargs):
    """Build an argparse.Namespace with the fields resolve_server_url cares about.

    Defaults match what build_parser will populate; tests override per scenario.
    """
    from cli.connection_plan import CommandPolicy

    if "requires_server" in kwargs:
        # Back-compat for callers using the legacy boolean.
        kwargs.setdefault(
            "command_policy",
            (
                CommandPolicy.DEVICE
                if kwargs.pop("requires_server")
                else CommandPolicy.OFFLINE
            ),
        )
    defaults = dict(
        command=None,
        server_url=None,
        no_discovery=False,
        command_policy=CommandPolicy.DEVICE,
        token=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _fake_server(host="192.168.1.20", port=5500, version="1.6.6"):
    _, _, FPBServer = _import_discover()
    return FPBServer(
        name=f"fake-{host}",
        host=host,
        port=port,
        version=version,
        auth="token",
        device="none",
        path="/api",
        url=f"http://{host}:{port}",
        id=f"fpb:fake-{host}-{port}",
        handle=f"{host}:{port}",
    )


class TestResolveServerUrl(unittest.TestCase):
    """Precedence ladder for resolve_server_url()."""

    def test_explicit_server_url_bypasses_discovery(self):
        # S5: explicit flag wins, never browses
        resolve_server_url, _ = _import_cli_helpers()
        with patch("cli.fpb_cli.discover_sync") as mock_disc:
            url = resolve_server_url(
                _ns(server_url="http://1.2.3.4:9999", requires_server=True)
            )
        self.assertEqual(url, "http://1.2.3.4:9999")
        mock_disc.assert_not_called()

    @patch.dict(os.environ, {"FPB_SERVER_URL": "http://env.host:7777"}, clear=False)
    def test_env_server_url_used_when_no_flag(self):
        # S5 via env
        resolve_server_url, _ = _import_cli_helpers()
        with patch("cli.fpb_cli.discover_sync") as mock_disc:
            url = resolve_server_url(_ns(server_url=None, requires_server=True))
        self.assertEqual(url, "http://env.host:7777")
        mock_disc.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_offline_subcommand_skips_discovery(self):
        # S7: requires_server=False short-circuits, no 1s delay
        resolve_server_url, _ = _import_cli_helpers()
        with patch("cli.fpb_cli.discover_sync") as mock_disc:
            t0 = time.monotonic()
            url = resolve_server_url(_ns(server_url=None, requires_server=False))
            elapsed = time.monotonic() - t0
        self.assertIsNone(url)
        mock_disc.assert_not_called()
        self.assertLess(elapsed, 0.1, f"S7 delay budget exceeded: {elapsed:.3f}s")

    @patch.dict(os.environ, {}, clear=True)
    def test_no_discovery_flag_falls_back_to_localhost(self):
        # S6
        resolve_server_url, _ = _import_cli_helpers()
        with patch("cli.fpb_cli.discover_sync") as mock_disc:
            url = resolve_server_url(
                _ns(server_url=None, no_discovery=True, requires_server=True)
            )
        from cli.server_proxy import DEFAULT_SERVER_URL

        self.assertEqual(url, DEFAULT_SERVER_URL)
        mock_disc.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_zero_results_falls_back_to_localhost(self):
        # S3
        resolve_server_url, _ = _import_cli_helpers()
        with patch("cli.fpb_cli.discover_sync", return_value=[]):
            url = resolve_server_url(_ns(server_url=None, requires_server=True))
        from cli.server_proxy import DEFAULT_SERVER_URL

        self.assertEqual(url, DEFAULT_SERVER_URL)

    @patch.dict(os.environ, {}, clear=True)
    def test_one_result_returned_silently(self):
        # S2
        resolve_server_url, _ = _import_cli_helpers()
        with patch("cli.fpb_cli.discover_sync", return_value=[_fake_server(port=5500)]):
            url = resolve_server_url(_ns(server_url=None, requires_server=True))
        self.assertEqual(url, "http://192.168.1.20:5500")

    @patch.dict(os.environ, {}, clear=True)
    def test_two_results_lists_and_exits_2(self):
        # S4
        resolve_server_url, _ = _import_cli_helpers()
        servers = [
            _fake_server(host="10.0.0.10", port=5500),
            _fake_server(host="10.0.0.11", port=5500),
        ]
        with patch("cli.fpb_cli.discover_sync", return_value=servers):
            err = io.StringIO()
            with redirect_stderr(err):
                with self.assertRaises(SystemExit) as cm:
                    resolve_server_url(_ns(server_url=None, requires_server=True))
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("10.0.0.10:5500", err.getvalue())
            self.assertIn("10.0.0.11:5500", err.getvalue())
            self.assertIn("-s ", err.getvalue())


# ---- cmd_discover() JSON output (S8) ----------------------------------------


class TestCmdDiscoverJson(unittest.TestCase):
    """`fpb_cli.py discover` emits a valid JSON list."""

    def test_discover_subcommand_outputs_json_list(self):
        _, cmd_discover = _import_cli_helpers()
        servers = [
            _fake_server(host="10.0.0.10", port=5500),
            _fake_server(host="10.0.0.11", port=5501),
        ]
        with patch("cli.fpb_cli.discover_sync", return_value=servers):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cmd_discover(_ns(timeout=0.1, json=True))
        self.assertEqual(rc, 0)
        parsed = json.loads(out.getvalue())
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertIn("url", parsed[0])
        self.assertIn("version", parsed[0])
        self.assertIn("auth", parsed[0])
        self.assertIn("handle", parsed[0])
        self.assertIn("id", parsed[0])

    def test_discover_subcommand_empty_emits_empty_list(self):
        _, cmd_discover = _import_cli_helpers()
        with patch("cli.fpb_cli.discover_sync", return_value=[]):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cmd_discover(_ns(timeout=0.1, json=True))
        self.assertEqual(rc, 0)
        parsed = json.loads(out.getvalue())
        self.assertEqual(parsed, [])


if __name__ == "__main__":
    unittest.main()

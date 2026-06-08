#!/usr/bin/env python3
"""Speed contract tests for discover() early-return.

A `host:port` handle lookup must short-circuit as soon as the matching
service is resolved -- it MUST NOT wait the full discovery timeout.
"""

import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.discover import (  # noqa: E402
    FPBServer,
    discover,
    discover_sync_by_handle,
)


def _server(host, port, handle=None):
    return FPBServer(
        name=f"FPBInject on {handle or host + ':' + str(port)}._fpbinject._tcp.local.",
        host=host,
        port=port,
        version="1.6.6",
        auth="none",
        device="none",
        path="/api",
        url=f"http://{host}:{port}",
        id="fpb:test",
        handle=handle or f"{host}:{port}",
    )


def _slow_browser_factory(service_names, fire_after=0.05):
    """Stub AsyncServiceBrowser that fires Added events ``fire_after``
    seconds after construction, simulating an mDNS reply."""
    from zeroconf import ServiceStateChange

    class _StubBrowser:
        def __init__(self, zc, types, handlers=None):
            self.zc = zc
            self._handlers = handlers or []
            self._task = asyncio.get_event_loop().create_task(self._fire())

        async def _fire(self):
            await asyncio.sleep(fire_after)
            for h in self._handlers:
                for n in service_names:
                    h(
                        zeroconf=self.zc,
                        service_type="_fpbinject._tcp.local.",
                        name=n,
                        state_change=ServiceStateChange.Added,
                    )

        async def async_cancel(self):
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    return _StubBrowser


def _fast_info_factory(props_by_name):
    """AsyncServiceInfo stub with instant async_request."""

    class _StubInfo:
        def __init__(self, type_, name):
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
            return list(self._spec.get("addresses", []))

    return _StubInfo


_PROPS = {
    b"txtvers": b"1",
    b"version": b"1.6.6",
    b"auth": b"none",
    b"device": b"none",
    b"path": b"/api",
    b"id": b"fpb:test",
}


class TestEarlyReturnByHandle(unittest.TestCase):
    """``-s host:port`` exits as soon as the match is resolved."""

    def test_host_port_handle_short_circuits_well_under_timeout(self):
        name = "FPBInject on bench:5500._fpbinject._tcp.local."
        Browser = _slow_browser_factory([name], fire_after=0.05)
        Info = _fast_info_factory(
            {
                name: {
                    "port": 5500,
                    "addresses": ["127.0.0.1"],
                    "properties": dict(_PROPS),
                }
            }
        )
        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ):
            t0 = time.monotonic()
            servers = discover_sync_by_handle("bench:5500", timeout=3.0)
            elapsed = time.monotonic() - t0
        self.assertEqual(len(servers), 1)
        self.assertLess(
            elapsed,
            1.0,
            f"discover_sync_by_handle should short-circuit; took {elapsed:.2f}s",
        )

    def test_host_port_no_match_waits_full_timeout(self):
        # When the requested handle isn't on the LAN, the loop has no signal
        # to short-circuit on, so it must wait the full budget. Other servers
        # that happen to be visible are still returned (the caller filters
        # via find_by_handle).
        name = "FPBInject on other:5500._fpbinject._tcp.local."
        Browser = _slow_browser_factory([name], fire_after=0.05)
        Info = _fast_info_factory(
            {
                name: {
                    "port": 5500,
                    "addresses": ["127.0.0.1"],
                    "properties": dict(_PROPS),
                }
            }
        )
        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ):
            t0 = time.monotonic()
            servers = discover_sync_by_handle("nope:9999", timeout=0.3)
            elapsed = time.monotonic() - t0
        self.assertGreaterEqual(elapsed, 0.25)
        self.assertTrue(all(s.handle != "nope:9999" for s in servers))


class TestEarlyMatchPredicate(unittest.TestCase):
    """``discover()`` early_match predicate stops the loop on first hit."""

    def test_early_match_stops_loop(self):
        names = [f"FPBInject on srv{i}:5500._fpbinject._tcp.local." for i in range(3)]
        Browser = _slow_browser_factory(names, fire_after=0.05)
        Info = _fast_info_factory(
            {
                n: {
                    "port": 5500 + i,
                    "addresses": [f"127.0.0.{i + 1}"],
                    "properties": dict(_PROPS),
                }
                for i, n in enumerate(names)
            }
        )

        def is_first(s):
            return s.handle == "srv0:5500"

        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ):
            t0 = time.monotonic()
            servers = asyncio.run(discover(timeout=3.0, early_match=is_first))
            elapsed = time.monotonic() - t0
        self.assertGreaterEqual(len(servers), 1)
        self.assertLess(
            elapsed, 1.0, f"early_match should short-circuit; took {elapsed:.2f}s"
        )


if __name__ == "__main__":
    unittest.main()

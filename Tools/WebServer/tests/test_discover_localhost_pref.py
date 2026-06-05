#!/usr/bin/env python3
"""Tests for the localhost-preference rule in cli.discover.

When mDNS returns multiple addresses for the same service, the resolver
must prefer loopback > local-interface > other, AND normalize same-host
results to 127.0.0.1 so the CLI never tries to talk to its own host via
a LAN IP (which would trigger remote auth checks unnecessarily).
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.discover import (  # noqa: E402
    _address_sort_key,
    _is_loopback,
    _is_same_host,
    discover,
)


class TestAddressSortKey(unittest.TestCase):
    """Loopback < local interface < other."""

    def test_loopback_beats_local_interface(self):
        local_ips = frozenset({"127.0.0.1", "10.0.0.5"})
        self.assertLess(
            _address_sort_key("127.0.0.1", local_ips),
            _address_sort_key("10.0.0.5", local_ips),
        )

    def test_local_interface_beats_remote(self):
        local_ips = frozenset({"127.0.0.1", "10.0.0.5"})
        self.assertLess(
            _address_sort_key("10.0.0.5", local_ips),
            _address_sort_key("192.168.1.20", local_ips),
        )

    def test_remote_addresses_sorted_lexicographically(self):
        local_ips = frozenset({"127.0.0.1"})
        addrs = ["192.168.1.30", "192.168.1.20"]
        sorted_addrs = sorted(addrs, key=lambda a: _address_sort_key(a, local_ips))
        self.assertEqual(sorted_addrs[0], "192.168.1.20")


class TestSameHostDetection(unittest.TestCase):
    def test_loopback_is_same_host(self):
        self.assertTrue(_is_loopback("127.0.0.1"))
        self.assertTrue(_is_same_host("127.0.0.1", frozenset()))

    def test_local_interface_ip_is_same_host(self):
        self.assertTrue(_is_same_host("10.0.0.5", frozenset({"10.0.0.5"})))

    def test_remote_ip_is_not_same_host(self):
        self.assertFalse(_is_same_host("192.168.1.99", frozenset({"10.0.0.5"})))


def _fake_async_browser_factory(service_names):
    from zeroconf import ServiceStateChange

    class _StubBrowser:
        def __init__(self, zc, types, handlers=None):
            handler_list = handlers or []
            for h in handler_list:
                for n in service_names:
                    h(
                        zeroconf=zc,
                        service_type="_fpbinject._tcp.local.",
                        name=n,
                        state_change=ServiceStateChange.Added,
                    )

        async def async_cancel(self):
            return None

    return _StubBrowser


def _fake_async_service_info_factory(spec_by_name):
    class _StubInfo:
        def __init__(self, type_, name):
            self.type_ = type_
            self.name = name
            self._spec = spec_by_name.get(name)

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


_MIN_PROPS = {
    b"txtvers": b"1",
    b"version": b"1.6.6",
    b"auth": b"token",
    b"device": b"none",
    b"path": b"/api",
}


class TestDiscoverLocalhostNormalization(unittest.TestCase):
    """End-to-end: a service announcing 127.0.0.1 + a LAN IP comes back as 127.0.0.1."""

    def test_loopback_wins_when_advertised_alongside_lan_ip(self):
        name = "FPB._fpbinject._tcp.local."
        Browser = _fake_async_browser_factory([name])
        Info = _fake_async_service_info_factory(
            {
                name: {
                    "port": 5500,
                    "addresses": ["10.221.101.4", "127.0.0.1"],
                    "properties": dict(_MIN_PROPS),
                }
            }
        )
        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ):
            servers = asyncio.run(discover(timeout=0.05))
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].host, "127.0.0.1")
        self.assertEqual(servers[0].url, "http://127.0.0.1:5500")

    def test_lan_ip_normalized_to_localhost_when_matches_local_interface(self):
        name = "FPB._fpbinject._tcp.local."
        Browser = _fake_async_browser_factory([name])
        # Only LAN IP advertised; but it matches a local interface IP.
        Info = _fake_async_service_info_factory(
            {
                name: {
                    "port": 5501,
                    "addresses": ["10.0.0.5"],
                    "properties": dict(_MIN_PROPS),
                }
            }
        )
        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ), patch(
            "cli.discover._local_interface_ips",
            return_value=frozenset({"127.0.0.1", "10.0.0.5"}),
        ):
            servers = asyncio.run(discover(timeout=0.05))
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].host, "127.0.0.1")

    def test_truly_remote_ip_kept_as_is(self):
        name = "FPB._fpbinject._tcp.local."
        Browser = _fake_async_browser_factory([name])
        Info = _fake_async_service_info_factory(
            {
                name: {
                    "port": 5500,
                    "addresses": ["192.168.99.99"],
                    "properties": dict(_MIN_PROPS),
                }
            }
        )
        with patch("cli.discover.AsyncServiceBrowser", Browser), patch(
            "cli.discover.AsyncServiceInfo", Info
        ), patch(
            "cli.discover._local_interface_ips",
            return_value=frozenset({"127.0.0.1", "10.0.0.5"}),
        ):
            servers = asyncio.run(discover(timeout=0.05))
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].host, "192.168.99.99")


if __name__ == "__main__":
    unittest.main()

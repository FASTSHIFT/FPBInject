"""mDNS discovery for FPBInject WebServer.

Browses ``_fpbinject._tcp.local.`` and returns the list of reachable servers.
Used by ``fpb_cli.py`` so device commands can find a server on the LAN
without prior knowledge of host or port.

The protocol (service type, TXT records) is documented in
``Tools/WebServer/Docs/Discovery.md``.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import Optional

from zeroconf import IPVersion, ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_fpbinject._tcp.local."

DEFAULT_TIMEOUT_S = 3.0
RESOLVE_TIMEOUT_MS = 2000


def _local_interface_ips() -> frozenset[str]:
    """IPv4 addresses bound on this host (loopback + every NIC).

    Used so a service advertising ``10.0.0.5:5500`` from THIS host gets
    classified as local rather than remote, preventing the "why is the CLI
    asking for a token to talk to a server I just started?" trap.

    Tries ``ifaddr`` (already a transitive dep of ``zeroconf``) so we get
    every interface, then falls back to ``socket.getaddrinfo(hostname)``
    for environments where ``ifaddr`` is unavailable.
    """
    ips: set[str] = {"127.0.0.1"}

    try:
        import ifaddr
        for adapter in ifaddr.get_adapters():
            for ip in adapter.ips:
                if isinstance(ip.ip, str):
                    ips.add(ip.ip)
    except Exception:
        pass

    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        for info in infos:
            ips.add(info[4][0])
    except OSError:
        pass

    return frozenset(ips)


def _is_loopback(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr).is_loopback
    except ValueError:
        return False


def _address_sort_key(addr: str, local_ips: frozenset[str]) -> tuple[int, str]:
    """Loopback (0) < local-interface (1) < other (2)."""
    if _is_loopback(addr):
        return (0, addr)
    if addr in local_ips:
        return (1, addr)
    return (2, addr)


def _is_same_host(addr: str, local_ips: frozenset[str]) -> bool:
    return _is_loopback(addr) or addr in local_ips


@dataclass(frozen=True)
class FPBServer:
    """A single discovered FPBInject WebServer.

    ``url`` is convenience derived from ``host:port``; the auth token (if any)
    is NOT carried by mDNS and must be supplied separately by the user.
    """

    name: str
    host: str
    port: int
    version: str
    auth: str
    device: str
    path: str
    url: str


def _decode_txt_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode()
        except UnicodeDecodeError:
            return ""
    return str(value)


async def _resolve(aiozc: AsyncZeroconf, name: str) -> Optional[FPBServer]:
    info = AsyncServiceInfo(SERVICE_TYPE, name)
    if not await info.async_request(aiozc.zeroconf, RESOLVE_TIMEOUT_MS):
        return None
    addresses = info.parsed_scoped_addresses() or []
    if not addresses:
        return None
    port = int(info.port or 0)
    if port <= 0:
        return None

    local_ips = _local_interface_ips()
    sorted_addrs = sorted(addresses, key=lambda a: _address_sort_key(a, local_ips))
    raw_host = sorted_addrs[0]
    host = "127.0.0.1" if _is_same_host(raw_host, local_ips) else raw_host

    props = info.properties or {}
    decoded = {
        (k.decode() if isinstance(k, bytes) else str(k)): _decode_txt_value(v)
        for k, v in props.items()
    }
    return FPBServer(
        name=name,
        host=host,
        port=port,
        version=decoded.get("version", ""),
        auth=decoded.get("auth", ""),
        device=decoded.get("device", ""),
        path=decoded.get("path", ""),
        url=f"http://{host}:{port}",
    )


async def discover(timeout: float = DEFAULT_TIMEOUT_S) -> list[FPBServer]:
    """Browse the LAN for FPBInject servers.

    Returns the list of resolved servers (deduplicated by service name) seen
    within ``timeout`` seconds. Always closes its Zeroconf instance.
    """
    found: dict[str, FPBServer] = {}
    pending: list[asyncio.Task] = []

    async with AsyncZeroconf(ip_version=IPVersion.V4Only) as aiozc:
        loop = asyncio.get_event_loop()

        def _on_state_change(zeroconf, service_type, name, state_change):
            if state_change is not ServiceStateChange.Added:
                return
            pending.append(loop.create_task(_collect(aiozc, name, found)))

        browser = AsyncServiceBrowser(
            aiozc.zeroconf, [SERVICE_TYPE], handlers=[_on_state_change]
        )
        try:
            await asyncio.sleep(timeout)
        finally:
            try:
                await browser.async_cancel()
            except Exception as exc:
                logger.debug("AsyncServiceBrowser cancel failed: %s", exc)

        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    return sorted(found.values(), key=lambda s: (s.host, s.port))


async def _collect(aiozc: AsyncZeroconf, name: str, found: dict) -> None:
    try:
        server = await _resolve(aiozc, name)
        if server is not None and name not in found:
            found[name] = server
    except Exception as exc:
        logger.debug("resolve(%s) failed: %s", name, exc)


def discover_sync(timeout: float = DEFAULT_TIMEOUT_S) -> list[FPBServer]:
    """Blocking wrapper around :func:`discover`.

    Convenient for synchronous callers (the CLI dispatcher); runs its own
    event loop via ``asyncio.run``.
    """
    return asyncio.run(discover(timeout))

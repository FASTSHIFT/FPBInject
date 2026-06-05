"""mDNS discovery for FPBInject WebServer.

Browses ``_fpbinject._tcp.local.`` and returns the list of reachable servers.
Used by ``fpb_cli.py`` so device commands can find a server on the LAN
without prior knowledge of host or port.

The protocol (service type, TXT records) is documented in
``Tools/WebServer/Docs/Discovery.md``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from zeroconf import IPVersion, ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_fpbinject._tcp.local."

DEFAULT_TIMEOUT_S = 1.0
RESOLVE_TIMEOUT_MS = 1500


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
    host = addresses[0]
    port = int(info.port or 0)
    if port <= 0:
        return None
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

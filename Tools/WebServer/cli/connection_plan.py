"""Connection-plan data model for the CLI.

Single source of truth for what mode the CLI is operating in and what server
URL / token / serial port it should use. The resolver builds a
``ConnectionPlan`` once; the connector consumes it once. There is no other
decision-making code path between the two.

See ``Tools/WebServer/Docs/Discovery.md`` for the precedence rules and
``Docs/CLI.md`` for the user-facing description.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CommandPolicy(Enum):
    """How a subcommand interacts with the server / device.

    Subparsers attach exactly one of these via ``set_defaults`` so the
    resolver and the dispatcher don't keep parallel hard-coded sets.
    """

    OFFLINE = "offline"  # ELF analysis only; never connects
    DEVICE = "device"  # needs a connected device to succeed
    SERVER_ADMIN = "server_admin"  # talks to a specific server only (server-stop)


class ConnectionMode(Enum):
    """Runtime mode after resolution."""

    OFFLINE = "offline"
    LOCAL_PROXY = "local_proxy"
    REMOTE_PROXY = "remote_proxy"
    DIRECT = "direct"


@dataclass(frozen=True)
class ConnectionPlan:
    """Output of ``resolve_connection_plan(args)``.

    Every field is final. The connector reads but never mutates it.

    ``allow_launch``: only set for LOCAL_PROXY when the server URL is the
    default localhost endpoint. Auto-launch never crosses hosts.

    ``allow_direct_fallback``: only set for LOCAL_PROXY plans that already
    carry a ``serial_port`` -- preserves the legacy "auto-launch fails ->
    direct serial" behavior, scoped to that one path.

    ``source``: short string describing which resolver branch produced the
    plan, surfaced when ``--verbose``. Examples: ``"flag"``, ``"env"``,
    ``"localhost-default"``, ``"pid"``, ``"mdns"``, ``"direct"``,
    ``"offline-command"``.
    """

    mode: ConnectionMode
    server_url: Optional[str] = None
    token: Optional[str] = None
    serial_port: Optional[str] = None
    baudrate: int = 115200
    allow_launch: bool = False
    allow_direct_fallback: bool = False
    source: str = ""
    cache_handle: Optional[str] = None

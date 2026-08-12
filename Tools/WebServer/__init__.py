"""FPBInject — runtime code injection for ARM Cortex-M via the FPB unit.

This package bundles the WebServer, CLI, and supporting modules. The physical
layout lives under ``Tools/WebServer/`` and is mapped to the import name
``fpbinject`` via setuptools ``package-dir`` (see pyproject.toml).

Public SDK::

    from fpbinject import Client
    client = Client.discover(token="...")
    client.serial_send("help\\r\\n")
"""

from fpbinject.version import __version__
from fpbinject.client import (
    Client,
    FPBError,
    AuthError,
    ServerUnavailable,
    DeviceNotConnected,
    DiscoveredServer,
)

__all__ = [
    "__version__",
    "Client",
    "FPBError",
    "AuthError",
    "ServerUnavailable",
    "DeviceNotConnected",
    "DiscoveredServer",
]

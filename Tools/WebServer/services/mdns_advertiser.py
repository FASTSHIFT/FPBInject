"""mDNS / DNS-SD advertiser for the FPBInject WebServer.

Publishes the running server as ``_fpbinject._tcp.local.`` so that
``fpb_cli.py`` clients can discover it without prior knowledge of host or
port. The TXT-record contract is documented in
``Tools/WebServer/Docs/Discovery.md`` — in particular, the auth token MUST
NEVER be published in TXT records.

Lifecycle:
    advertiser = MdnsAdvertiser(port=5500, version="1.6.6", auth_mode="token")
    advertiser.register()
    try:
        # ... run server ...
    finally:
        advertiser.unregister()

The class also installs ``atexit`` and (optionally) SIGINT/SIGTERM handlers
so that an interrupted server still emits a "goodbye" packet rather than
leaving a stale entry that survives until the mDNS TTL expires.
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import socket
import uuid
from pathlib import Path
from typing import Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_fpbinject._tcp.local."
TXT_SCHEMA_VERSION = "1"

_SERVER_ID_FILE = Path(__file__).resolve().parent.parent / ".fpbinject_server_id"


def _load_or_create_server_id() -> str:
    """Return a stable per-installation UUID, persisted next to WebServer/.

    The id survives port/hostname changes and lets the CLI keep the same
    handle for the same server. Wiping ``.fpbinject_server_id`` is the only
    way to mint a new identity.
    """
    try:
        if _SERVER_ID_FILE.exists():
            text = _SERVER_ID_FILE.read_text().strip()
            if text:
                return text
    except OSError as exc:
        logger.debug("read server-id failed: %s", exc)
    new_id = f"fpb:{uuid.uuid4()}"
    try:
        _SERVER_ID_FILE.write_text(new_id + "\n")
    except OSError as exc:
        logger.warning("persist server-id failed (%s); using volatile id", exc)
    return new_id


class MdnsAdvertiser:
    """Register the WebServer as an mDNS service for LAN discovery.

    Args:
        port: TCP port the server is listening on.
        version: server application version (goes into TXT ``version``).
        auth_mode: ``"token"`` if auth is enabled, ``"none"`` if running with
            ``--no-auth``. Reflects advertised intent, not effective state;
            see ``Discovery.md`` for the contract.
        path: API base path; reserved for future protocol revs.
        install_signal_handlers: ``True`` always installs SIGINT/SIGTERM
            handlers; ``False`` never installs; ``None`` (default) installs
            unless the ``PYTEST_CURRENT_TEST`` env var is set.
    """

    def __init__(
        self,
        *,
        port: int,
        version: str,
        auth_mode: str,
        path: str = "/api",
        install_signal_handlers: Optional[bool] = None,
    ) -> None:
        if auth_mode not in ("token", "none"):
            raise ValueError(f"auth_mode must be 'token' or 'none', got {auth_mode!r}")
        self._port = port
        self._version = version
        self._auth_mode = auth_mode
        self._path = path
        self._install_signal_handlers = install_signal_handlers

        self._zc: Optional[Zeroconf] = None
        self._info: Optional[ServiceInfo] = None
        self._registered = False
        self._prev_sigint = None
        self._prev_sigterm = None

    def _build_info(self) -> ServiceInfo:
        hostname = socket.gethostname() or "fpbinject"
        instance = f"FPBInject on {hostname}:{self._port}"
        properties = {
            "txtvers": TXT_SCHEMA_VERSION,
            "version": self._version,
            "auth": self._auth_mode,
            "device": "none",
            "path": self._path,
            "id": _load_or_create_server_id(),
        }
        return ServiceInfo(
            type_=SERVICE_TYPE,
            name=f"{instance}.{SERVICE_TYPE}",
            addresses=None,
            port=self._port,
            properties=properties,
            server=f"{hostname}.local.",
        )

    def _should_install_signal_handlers(self) -> bool:
        if self._install_signal_handlers is True:
            return True
        if self._install_signal_handlers is False:
            return False
        return os.environ.get("PYTEST_CURRENT_TEST") is None

    def _install_signal_chain(self) -> None:
        def _handler_for(sig):
            def _handler(signum, frame):
                try:
                    self.unregister()
                finally:
                    prev = (
                        self._prev_sigint
                        if sig == signal.SIGINT
                        else self._prev_sigterm
                    )
                    if callable(prev) and prev not in (signal.SIG_DFL, signal.SIG_IGN):
                        prev(signum, frame)
                    else:
                        raise SystemExit(128 + int(signum))

            return _handler

        self._prev_sigint = signal.signal(signal.SIGINT, _handler_for(signal.SIGINT))
        self._prev_sigterm = signal.signal(signal.SIGTERM, _handler_for(signal.SIGTERM))

    def register(self) -> None:
        """Create the Zeroconf instance and announce the service.

        Idempotent: a second call is a no-op.
        """
        if self._registered:
            return
        try:
            self._zc = Zeroconf(ip_version=IPVersion.V4Only)
            self._info = self._build_info()
            self._zc.register_service(self._info)
            self._registered = True
            atexit.register(self.unregister)
            if self._should_install_signal_handlers():
                self._install_signal_chain()
            logger.info(
                "mDNS advertised on %s port=%d auth=%s",
                SERVICE_TYPE,
                self._port,
                self._auth_mode,
            )
        except Exception as exc:
            logger.warning("mDNS register failed: %s", exc)
            self._registered = False
            if self._zc is not None:
                try:
                    self._zc.close()
                except Exception:
                    pass
                self._zc = None
            self._info = None

    def update_device_state(self, state: str) -> None:
        """Update the ``device`` TXT field at runtime.

        v1 contract: this method is shipped + tested, but not currently called
        from ``main.py`` — see Discovery.md "v1 limitations".
        """
        if not self._registered or self._zc is None or self._info is None:
            return
        if state not in ("none", "connected"):
            raise ValueError(f"state must be 'none' or 'connected', got {state!r}")
        new_props = {
            "txtvers": TXT_SCHEMA_VERSION,
            "version": self._version,
            "auth": self._auth_mode,
            "device": state,
            "path": self._path,
        }
        try:
            self._info._set_properties(new_props)
            self._zc.update_service(self._info)
        except Exception as exc:
            logger.warning("mDNS update_service failed: %s", exc)

    def unregister(self) -> None:
        """Send mDNS goodbye and close the Zeroconf instance.

        Idempotent: a second call is a no-op.
        """
        if not self._registered:
            return
        self._registered = False
        try:
            if self._zc is not None and self._info is not None:
                self._zc.unregister_service(self._info)
        except Exception as exc:
            logger.warning("mDNS unregister_service failed: %s", exc)
        try:
            if self._zc is not None:
                self._zc.close()
        except Exception:
            pass
        self._zc = None
        self._info = None

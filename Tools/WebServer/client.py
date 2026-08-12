#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPBInject public Python SDK.

A single, stable facade over the WebServer proxy (device operations),
mDNS discovery, and offline ELF analysis. External code should use this
instead of importing ``cli.*`` / ``core.*`` internals.

    from fpbinject import Client

    client = Client.discover(token="...")     # auto-find a WebServer
    client.serial_send("help\\r\\n")
    print(client.serial_read()["raw_data"])

    off = Client.offline(toolchain_path="/opt/tc/bin")
    print(off.signature("firmware.elf", "target_function"))

Return values are the raw JSON dicts from the WebServer REST API (or plain
dicts for offline analysis), keeping parity with the CLI / REST surface.
"""

import os
from typing import Any, Dict, List, Optional

__all__ = [
    "Client",
    "FPBError",
    "AuthError",
    "ServerUnavailable",
    "DeviceNotConnected",
    "DiscoveredServer",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class FPBError(Exception):
    """Base class for all SDK errors."""


class AuthError(FPBError):
    """Raised when the WebServer rejects a request (HTTP 401/403)."""


class ServerUnavailable(FPBError):
    """Raised when no WebServer is reachable."""


class DeviceNotConnected(FPBError):
    """Raised when an operation needs a connected device but none is."""


class DiscoveredServer:
    """A WebServer found via mDNS (public, stable shape)."""

    __slots__ = ("name", "host", "port", "url", "version", "auth", "handle")

    def __init__(self, name, host, port, url, version, auth, handle):
        self.name = name
        self.host = host
        self.port = port
        self.url = url
        self.version = version
        self.auth = auth
        self.handle = handle

    def __repr__(self):
        return f"<DiscoveredServer {self.handle} {self.url}>"


# ---------------------------------------------------------------------------
# Client facade
# ---------------------------------------------------------------------------
class Client:
    """Unified entry point for FPBInject capabilities.

    Proxy mode (default): device/file/serial/inject operations are sent to a
    running WebServer over HTTP. Offline mode: only ELF analysis / compile.
    """

    DEFAULT_URL = "http://127.0.0.1:5500"

    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        token: Optional[str] = None,
        *,
        timeout: int = 30,
        _offline: bool = False,
        _toolchain_path: Optional[str] = None,
    ):
        self._offline_mode = _offline
        self._toolchain_path = _toolchain_path
        self._proxy = None
        self._fpb = None
        if not _offline:
            from fpbinject.cli.server_proxy import ServerProxy

            token = token if token is not None else os.environ.get("FPB_TOKEN")
            self._proxy = ServerProxy(base_url=base_url, token=token)

    # -- alternate constructors --------------------------------------------
    @classmethod
    def discover(
        cls,
        token: Optional[str] = None,
        *,
        timeout: float = 3.0,
        handle: Optional[str] = None,
    ) -> "Client":
        """Find a WebServer via mDNS and connect to it.

        handle=None: use the single server on the LAN (error if ambiguous).
        handle="host:port" or "host": select a specific server.
        """
        servers = cls.list_servers(timeout=timeout)
        if handle:
            matches = [s for s in servers if handle in (s.handle, s.host, s.url)]
            if not matches:
                raise ServerUnavailable(f"No WebServer matched handle {handle!r}")
            chosen = matches[0]
        else:
            if not servers:
                raise ServerUnavailable("No FPBInject WebServer found via mDNS")
            if len(servers) > 1:
                listing = ", ".join(s.handle for s in servers)
                raise ServerUnavailable(
                    f"Multiple servers found ({listing}); pass handle= to pick one"
                )
            chosen = servers[0]
        return cls(base_url=chosen.url, token=token, timeout=timeout)

    @classmethod
    def offline(cls, *, toolchain_path: Optional[str] = None) -> "Client":
        """Offline mode: ELF analysis / compile only, no server/device."""
        return cls(_offline=True, _toolchain_path=toolchain_path)

    @staticmethod
    def list_servers(timeout: float = 3.0) -> List["DiscoveredServer"]:
        """List WebServers visible via mDNS (like ``fpb_cli discover``)."""
        try:
            from fpbinject.cli.discover import discover_sync
        except Exception:
            return []
        out = []
        for s in discover_sync(timeout=timeout):
            out.append(
                DiscoveredServer(
                    name=getattr(s, "name", ""),
                    host=getattr(s, "host", ""),
                    port=getattr(s, "port", 0),
                    url=getattr(s, "url", ""),
                    version=getattr(s, "version", ""),
                    auth=getattr(s, "auth", ""),
                    handle=getattr(s, "handle", ""),
                )
            )
        return out

    # -- lifecycle ----------------------------------------------------------
    def ensure_server(self) -> bool:
        """Auto-launch a local WebServer if none is running (proxy mode)."""
        self._require_proxy()
        return self._proxy.ensure_server()

    @property
    def connected(self) -> bool:
        if self._offline_mode or self._proxy is None:
            return False
        try:
            return self._proxy.is_device_connected()
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        """Full WebServer status dict."""
        self._require_proxy()
        return self._call(self._proxy.get_status)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    # -- internal helpers ---------------------------------------------------
    def _require_proxy(self):
        if self._offline_mode or self._proxy is None:
            raise FPBError(
                "This operation requires proxy mode (a WebServer). "
                "Use Client(...) or Client.discover(...), not Client.offline()."
            )

    def _get_fpb(self):
        """Lazily build an offline FPBInject instance for ELF analysis."""
        if self._fpb is None:
            from fpbinject.fpb_inject import FPBInject
            from fpbinject.core.state import DeviceStateBase

            state = DeviceStateBase()
            if self._toolchain_path:
                state.toolchain_path = self._toolchain_path
            self._fpb = FPBInject(state)
            if self._toolchain_path:
                self._fpb.set_toolchain_path(self._toolchain_path)
        return self._fpb

    def _call(self, fn, *args, **kwargs):
        """Invoke a proxy method, mapping transport errors to SDK errors."""
        from fpbinject.cli.server_proxy import ProxyAuthError

        try:
            return fn(*args, **kwargs)
        except ProxyAuthError as e:
            raise AuthError(str(e)) from e
        except (OSError,) as e:  # URLError/socket errors subclass OSError
            raise ServerUnavailable(str(e)) from e

    # =====================================================================
    # Offline: ELF analysis / compile
    # =====================================================================
    def analyze(self, elf: str, func: str) -> Dict[str, Any]:
        fpb = self._get_fpb()
        symbols = fpb.get_symbols(elf)
        if func not in symbols:
            raise FPBError(f"Function {func!r} not found in {elf}")
        info = symbols[func]
        addr = info["addr"] if isinstance(info, dict) else info
        ok, disasm = fpb.disassemble_function(elf, func)
        return {
            "success": True,
            "func_name": func,
            "addr": hex(addr),
            "signature": fpb.get_signature(elf, func),
            "asm_lines": len(disasm.split("\n")) if disasm else 0,
        }

    def disasm(self, elf: str, func: str) -> Dict[str, Any]:
        ok, text = self._get_fpb().disassemble_function(elf, func)
        if not ok or not text:
            raise FPBError(f"Could not disassemble {func!r}")
        return {"success": True, "func_name": func, "disasm": text}

    def decompile(self, elf: str, func: str) -> Dict[str, Any]:
        ok, text = self._get_fpb().decompile_function(elf, func)
        if not ok:
            raise FPBError(f"Decompilation failed: {text}")
        return {"success": True, "func_name": func, "decompiled": text}

    def signature(self, elf: str, func: str) -> Optional[str]:
        return self._get_fpb().get_signature(elf, func)

    def search(self, elf: str, pattern: str, limit: int = 20) -> Dict[str, Any]:
        symbols = self._get_fpb().get_symbols(elf)
        matches = [
            {"name": n, "addr": hex(i["addr"] if isinstance(i, dict) else i)}
            for n, i in symbols.items()
            if pattern.lower() in n.lower()
        ]
        return {
            "success": True,
            "pattern": pattern,
            "count": len(matches),
            "symbols": matches[:limit],
        }

    def get_symbols(
        self, elf: str, filter: Optional[str] = None, limit: int = 0
    ) -> Dict[str, Any]:
        symbols = self._get_fpb().get_symbols(elf)
        if filter:
            f = filter.lower()
            symbols = {k: v for k, v in symbols.items() if f in k.lower()}
        items = [
            {"name": n, "addr": hex(i["addr"] if isinstance(i, dict) else i)}
            for n, i in sorted(symbols.items())
        ]
        if limit > 0:
            items = items[:limit]
        return {"success": True, "count": len(items), "symbols": items}

    def compile(
        self,
        source: str,
        *,
        elf: Optional[str] = None,
        base_addr: int = 0x20001000,
        compile_commands: Optional[str] = None,
    ) -> Dict[str, Any]:
        with open(source, "r", encoding="utf-8") as f:
            content = f.read()
        binary, symbols, error = self._get_fpb().compile_inject(
            source_content=content,
            base_addr=base_addr,
            elf_path=elf,
            compile_commands_path=compile_commands,
            source_ext=os.path.splitext(source)[1],
            original_source_file=os.path.abspath(source),
        )
        if error:
            raise FPBError(f"Compilation error: {error}")
        return {
            "success": True,
            "binary_size": len(binary) if binary else 0,
            "base_addr": hex(base_addr),
            "symbols": {n: hex(a) for n, a in (symbols or {}).items()},
        }

    # =====================================================================
    # Proxy: device info / inject / memory
    # =====================================================================
    def info(self) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.info)

    def test_serial(
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.test_serial, start_size, max_size, timeout)

    def inject(
        self,
        target_func: str,
        source: str,
        *,
        elf: Optional[str] = None,
        compile_commands: Optional[str] = None,
        patch_mode: str = "trampoline",
        comp: int = -1,
    ) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(
            self._proxy.inject,
            target_func=target_func,
            source_file=source,
            elf_path=elf,
            compile_commands=compile_commands,
            patch_mode=patch_mode,
            comp=comp,
        )

    def unpatch(self, comp: int = 0, all: bool = False) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.unpatch, comp=comp, all_patches=all)

    def mem_read(self, addr: int, length: int, fmt: str = "hex") -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.mem_read, addr, length, fmt)

    def mem_write(self, addr: int, hexdata: str) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.mem_write, addr, hexdata)

    def mem_dump(self, addr: int, length: int, out_path: str) -> Dict[str, Any]:
        """Read a memory region and write raw bytes to a local file.

        Composed from mem_read (raw format) since the server exposes no
        single dump endpoint.
        """
        self._require_proxy()
        res = self._call(self._proxy.mem_read, addr, length, "raw")
        if not res.get("success"):
            return res
        hexstr = res.get("data") or res.get("hex") or ""
        data = bytes.fromhex(hexstr) if hexstr else b""
        parent = os.path.dirname(out_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(data)
        return {"success": True, "addr": hex(addr), "size": len(data), "path": out_path}

    # =====================================================================
    # Proxy: serial
    # =====================================================================
    def serial_send(self, data: str) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.serial_send, data)

    def serial_read(self, since: int = 0) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.serial_read, since)

    def wake(self) -> Dict[str, Any]:
        """Wake a sleeping device (some devices ignore serial_send while
        in deep sleep; a transfer op like file_stat wakes them)."""
        return self.file_stat("/")

    # =====================================================================
    # Proxy: files
    # =====================================================================
    def file_list(self, path: str = "/") -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.file_list, path)

    def file_stat(self, path: str) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.file_stat, path)

    def file_download(self, remote: str, local: str) -> Dict[str, Any]:
        self._require_proxy()
        res = self._call(self._proxy.file_download, remote)
        if res.get("success") and res.get("data"):
            import base64

            data = base64.b64decode(res["data"])
            parent = os.path.dirname(local)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(local, "wb") as f:
                f.write(data)
            return {
                "success": True,
                "remote": remote,
                "local": local,
                "size": len(data),
            }
        return res

    def file_upload(self, local: str, remote: str) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.file_upload, local, remote)

    def file_remove(self, path: str) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.file_remove, path)

    def file_mkdir(self, path: str) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.file_mkdir, path)

    def file_rename(self, old: str, new: str) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.file_rename, old, new)

    # =====================================================================
    # Proxy: connection / virtual serial
    # =====================================================================
    def connect(self, port: str, baudrate: int = 115200) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.connect, port, baudrate)

    def disconnect(self) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.disconnect)

    def vserial_start(self, symlink: Optional[str] = None) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.vserial_start, symlink)

    def vserial_status(self) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.vserial_status)

    def vserial_stop(self) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.vserial_stop)

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

    # Direct mode: talk to the device over serial, no WebServer needed.
    with Client.direct("/dev/ttyACM0") as dev:
        print(dev.info())
        dev.inject("digitalWrite", "patch.c", elf="firmware.elf")

    off = Client.offline(toolchain_path="/opt/tc/bin")
    print(off.signature("firmware.elf", "target_function"))

Three ways to reach a device:
  * Proxy   -- ``Client(url)`` / ``Client.discover()``: ops go through a
    running WebServer over HTTP. Supports everything incl. vserial.
  * Direct  -- ``Client.direct(port)``: opens the serial port locally and
    drives the core classes. No server process. vserial is unavailable.
  * Offline -- ``Client.offline()``: ELF analysis / compile only.

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
        _direct_port: Optional[str] = None,
        _direct_baudrate: int = 115200,
        _toolchain_path: Optional[str] = None,
    ):
        self._offline_mode = _offline
        self._direct_port = _direct_port
        self._toolchain_path = _toolchain_path
        self._proxy = None
        self._fpb = None
        self._device_state = None
        self._port_lock = None
        if _direct_port is not None:
            # Direct mode: open the serial port locally and drive the core
            # FPBInject/FileTransfer classes -- no WebServer involved.
            self._connect_direct(_direct_port, _direct_baudrate)
        elif not _offline:
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

    @classmethod
    def direct(
        cls,
        port: str,
        baudrate: int = 115200,
        *,
        toolchain_path: Optional[str] = None,
    ) -> "Client":
        """Direct mode: open the serial port and drive the device without a
        WebServer.

        This is the SDK equivalent of ``fpbinject --port <port> --direct``.
        It covers device info, inject/unpatch, memory, serial, and file
        operations plus all offline ELF analysis. It does NOT support the
        virtual serial passthrough (``vserial_*``): a PTY must be hosted by
        a long-lived process, which a transient direct client cannot be.

        The port is locked for the lifetime of the client; call ``close()``
        (or use the client as a context manager) to release it.
        """
        return cls(
            _direct_port=port,
            _direct_baudrate=baudrate,
            _toolchain_path=toolchain_path,
        )

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
        if self._direct_port is not None:
            return bool(self._device_state is not None and self._device_state.connected)
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

    def close(self) -> None:
        """Release resources. In direct mode, close the serial port and
        release the port lock. No-op for proxy/offline modes."""
        if self._device_state is not None:
            try:
                self._device_state.disconnect()
            except Exception:
                pass
        if self._port_lock is not None:
            try:
                self._port_lock.release()
            except Exception:
                pass
            self._port_lock = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- internal helpers ---------------------------------------------------
    def _connect_direct(self, port: str, baudrate: int) -> None:
        """Open the serial port directly, guarded by a PortLock.

        Mirrors the CLI's ``--direct`` path: acquire the same cross-process
        PortLock so the SDK won't fight a running server or another CLI over
        the same device, then open the port via the CLI DeviceState.
        """
        from fpbinject.cli.fpb_cli import DeviceState
        from fpbinject.fpb_inject import FPBInject
        from fpbinject.utils.port_lock import PortLock

        lock = PortLock(port)
        if not lock.acquire():
            owner = lock.get_owner_pid()
            raise FPBError(
                f"Serial port {port} is locked by another process "
                f"(PID: {owner}). Stop it or use a different port."
            )
        self._port_lock = lock
        state = DeviceState()
        if self._toolchain_path:
            state.toolchain_path = self._toolchain_path
        try:
            state.connect(port, baudrate)
        except Exception as e:
            lock.release()
            self._port_lock = None
            raise DeviceNotConnected(str(e)) from e
        self._device_state = state
        self._fpb = FPBInject(state)
        if self._toolchain_path:
            self._fpb.set_toolchain_path(self._toolchain_path)

    def _require_proxy(self):
        if self._proxy is None:
            hint = (
                "Use Client(...) or Client.discover(...)"
                if not self._direct_port
                else "This feature needs a WebServer; direct mode cannot host it"
            )
            raise FPBError(f"This operation requires proxy mode (a WebServer). {hint}.")

    def _require_device(self):
        """Direct mode only: ensure a serial device is connected."""
        if self._device_state is None or not self._device_state.connected:
            raise DeviceNotConnected("No serial device connected in direct mode.")

    def _get_fpb(self):
        """Lazily build an FPBInject instance for offline ELF analysis.

        In direct mode the instance is already bound to the live serial
        device; reuse it so analysis and device ops share one object.
        """
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

    def _ft(self):
        """Build a FileTransfer bound to the direct-mode device."""
        from fpbinject.core.file_transfer import FileTransfer

        st = self._device_state
        return FileTransfer(
            self._fpb,
            upload_chunk_size=st.upload_chunk_size,
            download_chunk_size=st.download_chunk_size,
            max_retries=st.transfer_max_retries,
        )

    # =====================================================================
    # Device: info / inject / memory (proxy or direct)
    # =====================================================================
    def info(self) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.info)
        self._require_device()
        info, error = self._fpb.info()
        if error:
            raise FPBError(f"Failed to get info: {error}")
        return {"success": True, "info": info}

    def test_serial(
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.test_serial, start_size, max_size, timeout)
        self._require_device()
        return self._fpb.test_serial_throughput(
            start_size=start_size, max_size=max_size, timeout=timeout
        )

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
        if self._proxy is not None:
            return self._call(
                self._proxy.inject,
                target_func=target_func,
                source_file=source,
                elf_path=elf,
                compile_commands=compile_commands,
                patch_mode=patch_mode,
                comp=comp,
            )
        self._require_device()
        with open(source, "r", encoding="utf-8") as f:
            source_content = f.read()
        if elf:
            self._device_state.elf_path = elf
        if compile_commands:
            self._device_state.compile_commands_path = compile_commands
        success, result = self._fpb.inject(
            source_content=source_content,
            target_func=target_func,
            patch_mode=patch_mode,
            comp=comp,
            source_ext=os.path.splitext(source)[1],
            original_source_file=os.path.abspath(source),
        )
        return {"success": success, "result": result}

    def unpatch(self, comp: int = 0, all: bool = False) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.unpatch, comp=comp, all_patches=all)
        self._require_device()
        success, msg = self._fpb.unpatch(comp=comp, all=all)
        return {
            "success": success,
            "message": msg,
            "comp": "all" if all else comp,
        }

    def mem_read(self, addr: int, length: int, fmt: str = "hex") -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.mem_read, addr, length, fmt)
        data = self._direct_read_memory(addr, length)
        return {
            "success": True,
            "addr": hex(addr),
            "length": length,
            "actual_length": len(data),
            "data": data.hex(),
        }

    def mem_write(self, addr: int, hexdata: str) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.mem_write, addr, hexdata)
        self._require_device()
        try:
            data = bytes.fromhex(hexdata)
        except ValueError as e:
            raise FPBError(f"Invalid hex data: {hexdata!r}") from e
        self._fpb.enter_fl_mode()
        try:
            success, error = self._fpb.write_memory(addr, data)
        finally:
            self._fpb.exit_fl_mode()
        if not success:
            raise FPBError(f"Memory write failed: {error}")
        return {"success": True, "addr": hex(addr), "length": len(data)}

    def _direct_read_memory(self, addr: int, length: int) -> bytes:
        """Direct-mode raw memory read (FL-mode wrapped)."""
        self._require_device()
        self._fpb.enter_fl_mode()
        try:
            data, msg = self._fpb.read_memory(addr, length)
        finally:
            self._fpb.exit_fl_mode()
        if data is None:
            raise FPBError(f"Memory read failed: {msg}")
        return data

    def mem_dump(self, addr: int, length: int, out_path: str) -> Dict[str, Any]:
        """Read a memory region and write raw bytes to a local file."""
        if self._proxy is not None:
            res = self._call(self._proxy.mem_read, addr, length, "raw")
            if not res.get("success"):
                return res
            hexstr = res.get("data") or res.get("hex") or ""
            data = bytes.fromhex(hexstr) if hexstr else b""
        else:
            data = self._direct_read_memory(addr, length)
        parent = os.path.dirname(out_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(data)
        return {"success": True, "addr": hex(addr), "size": len(data), "path": out_path}

    # =====================================================================
    # Device: serial (proxy or direct)
    # =====================================================================
    def serial_send(self, data: str) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.serial_send, data)
        self._require_device()
        ser = self._device_state.ser
        ser.write((data + "\n").encode())
        ser.flush()
        return {"success": True, "sent": data}

    def serial_read(self, since: int = 0, *, timeout: float = 1.0) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.serial_read, since)
        self._require_device()
        import time as _time

        ser = self._device_state.ser
        new_data = ""
        start = _time.time()
        while _time.time() - start < timeout:
            if ser.in_waiting:
                new_data += ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                _time.sleep(0.05)
            elif new_data:
                break
            else:
                _time.sleep(0.1)
        return {"success": True, "raw_data": new_data, "new_data": new_data}

    def wake(self) -> Dict[str, Any]:
        """Wake a sleeping device (some devices ignore serial_send while
        in deep sleep; a transfer op like file_stat wakes them)."""
        return self.file_stat("/")

    # =====================================================================
    # Device: files (proxy or direct)
    # =====================================================================
    def file_list(self, path: str = "/") -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.file_list, path)
        self._require_device()
        success, entries = self._ft().flist(path)
        if not success:
            raise FPBError(f"Failed to list directory: {path}")
        return {"success": True, "path": path, "entries": entries}

    def file_stat(self, path: str) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.file_stat, path)
        self._require_device()
        success, stat = self._ft().fstat(path)
        if not success:
            raise FPBError(f"Failed to stat: {stat.get('error', 'unknown')}")
        return {"success": True, "path": path, "stat": stat}

    def file_download(self, remote: str, local: str) -> Dict[str, Any]:
        if self._proxy is not None:
            res = self._call(self._proxy.file_download, remote)
            if res.get("success") and res.get("data"):
                import base64

                data = base64.b64decode(res["data"])
            else:
                return res
        else:
            self._require_device()
            success, data, msg = self._ft().download(remote)
            if not success:
                raise FPBError(f"Download failed: {msg}")
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

    def file_upload(self, local: str, remote: str) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.file_upload, local, remote)
        self._require_device()
        with open(local, "rb") as f:
            data = f.read()
        success, msg = self._ft().upload(data, remote)
        if not success:
            raise FPBError(f"Upload failed: {msg}")
        return {
            "success": True,
            "local": local,
            "remote": remote,
            "size": len(data),
            "message": msg,
        }

    def file_remove(self, path: str) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.file_remove, path)
        self._require_device()
        success, msg = self._ft().fremove(path)
        if not success:
            raise FPBError(f"Failed to remove: {msg}")
        return {"success": True, "path": path, "message": msg}

    def file_mkdir(self, path: str) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.file_mkdir, path)
        self._require_device()
        success, msg = self._ft().fmkdir(path)
        if not success:
            raise FPBError(f"Failed to mkdir: {msg}")
        return {"success": True, "path": path, "message": msg}

    def file_rename(self, old: str, new: str) -> Dict[str, Any]:
        if self._proxy is not None:
            return self._call(self._proxy.file_rename, old, new)
        self._require_device()
        success, msg = self._ft().frename(old, new)
        if not success:
            raise FPBError(f"Failed to rename: {msg}")
        return {"success": True, "old": old, "new": new, "message": msg}

    # =====================================================================
    # Connection (proxy asks the server to open/close the port; direct mode
    # owns the port for its whole lifetime, so use the client factory /
    # close() instead of these).
    # =====================================================================
    def connect(self, port: str, baudrate: int = 115200) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.connect, port, baudrate)

    def disconnect(self) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.disconnect)

    # =====================================================================
    # Virtual serial passthrough (proxy only).
    #
    # A PTY (/dev/pts/N) must be hosted by a long-lived process. A direct
    # client is transient -- the node would vanish when it exits -- so these
    # require a running WebServer. This is the same limitation the CLI
    # documents for ``--direct``.
    # =====================================================================
    def vserial_start(self, symlink: Optional[str] = None) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.vserial_start, symlink)

    def vserial_status(self) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.vserial_status)

    def vserial_stop(self) -> Dict[str, Any]:
        self._require_proxy()
        return self._call(self._proxy.vserial_stop)

    # =====================================================================
    # Server administration (static: no client instance required).
    # =====================================================================
    @staticmethod
    def stop_server(port: int = 5500) -> Dict[str, Any]:
        """Stop a CLI-launched WebServer background process on ``port``.

        Mirrors ``fpbinject server-stop``. Returns a dict with ``success``
        and a ``message``/``error``. Only affects servers this machine's
        CLI auto-launched (tracked by PID file); a manually run server is
        left untouched.
        """
        from fpbinject.cli.server_proxy import stop_cli_server

        return stop_cli_server(port)

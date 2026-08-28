#!/usr/bin/env python3
"""
FPBInject CLI - Lightweight command-line interface for AI integration

Usage (installed console script shown as ``fpbinject``; when run from
source the program name is ``fpb_cli.py``):
  fpbinject analyze <elf_path> <func_name>
  fpbinject disasm <elf_path> <func_name>
  fpbinject decompile <elf_path> <func_name>
  fpbinject signature <elf_path> <func_name>
  fpbinject search <elf_path> <pattern>
  fpbinject compile <source_file> [--output <out>]
  fpbinject inject <elf_path> <comp_num> <source_file> [--verify]
  fpbinject unpatch <elf_path> <comp_num>
  fpbinject --version
  fpbinject --help

Output: JSON format for easy AI parsing
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Import from existing WebServer modules
sys.path.insert(0, str(Path(__file__).parent))
from fpbinject.version import __version__ as FPB_VERSION  # noqa: E402
from fpbinject.fpb_inject import FPBInject  # noqa: E402
from fpbinject.core.state import DeviceStateBase  # noqa: E402
from fpbinject.utils.port_lock import PortLock  # noqa: E402
from fpbinject.cli.server_proxy import (  # noqa: E402
    ServerProxy,
    ProxyAuthError,
    DEFAULT_SERVER_URL,
    DEFAULT_PORT,
    list_cli_servers,
)

try:  # Optional: discovery requires the zeroconf package.
    from fpbinject.cli.discover import (  # noqa: E402
        discover_sync,
        discover_sync_by_handle,
        FPBServer,
    )
except Exception:  # pragma: no cover
    discover_sync = None
    discover_sync_by_handle = None
    FPBServer = None

from fpbinject.cli.connection_plan import (  # noqa: E402
    CommandPolicy,
    ConnectionMode,
    ConnectionPlan,
)

try:
    import serial

    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


class FPBCLIError(Exception):
    """CLI-specific error. ``exit_code`` defaults to 1.

    Raise the ``AmbiguousServerError`` subclass when more than one server
    matches a discovery handle so main() can exit ``2`` (the documented
    ladder code for "needs disambiguation").
    """

    exit_code = 1


class AmbiguousServerError(FPBCLIError):
    """Multi-match on discovery handle / mDNS browse; exits ``2``."""

    exit_code = 2


class DeviceState(DeviceStateBase):
    """Device state for CLI - can work with or without serial connection"""

    def __init__(self):
        super().__init__()
        self.connected = False

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect to device via serial port"""
        if not HAS_SERIAL:
            raise RuntimeError(
                "pyserial not installed. Install with: pip install pyserial"
            )
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            self.connected = True
            return True
        except Exception as e:
            self.connected = False
            raise RuntimeError(f"Failed to connect to {port}: {e}")

    def disconnect(self):
        """Disconnect from device"""
        if self.ser:
            self.ser.close()
            self.ser = None
        self.connected = False


class FPBCLI:
    """Lightweight CLI wrapper for FPBInject.

    Operates in proxy mode whenever a WebServer is reachable: device
    operations are forwarded via HTTP API. The serial port belongs to the
    server, so ``--port`` is optional in proxy mode — it is only used to ask
    the server to open a port when no device is connected yet.

    - Local server already running: attach to it (``--port`` optional).
    - Local, no server, ``--port`` given: auto-launch a server, else fall
      back to opening the serial port directly.
    - Remote ``--server-url``: pure proxy, no auto-launch, no direct fallback.
    - No ``--port`` and no server: stay offline (ELF analysis / compile only).

    Pass ``direct=True`` to bypass the proxy and open the serial port
    directly (legacy / escape-hatch mode).
    """

    def __init__(
        self,
        verbose: bool = False,
        port: Optional[str] = None,
        baudrate: int = 115200,
        elf_path: Optional[str] = None,
        compile_commands: Optional[str] = None,
        tx_chunk_size: int = 0,
        tx_chunk_delay: float = 0.002,
        max_retries: int = 10,
        direct: bool = False,
        server_url: Optional[str] = None,
        token: Optional[str] = None,
        plan: Optional[ConnectionPlan] = None,
    ):
        self.verbose = verbose
        self.setup_logging()
        self._device_state = DeviceState()
        self._device_state.elf_path = elf_path
        self._device_state.compile_commands_path = compile_commands
        self._device_state.serial_tx_fragment_size = tx_chunk_size
        self._device_state.serial_tx_fragment_delay = tx_chunk_delay
        self._device_state.transfer_max_retries = max_retries
        self._fpb = FPBInject(self._device_state)

        self._proxy = None
        self._port_lock = None
        # Suppress stderr transfer notices/progress (set from --quiet).
        self._quiet = False

        if plan is None:
            plan = self._legacy_kwargs_to_plan(
                direct=direct,
                server_url=server_url,
                token=token,
                port=port,
                baudrate=baudrate,
            )
        self._connect_from_plan(plan)

    @staticmethod
    def _legacy_kwargs_to_plan(
        *,
        direct: bool,
        server_url: Optional[str],
        token: Optional[str],
        port: Optional[str],
        baudrate: int,
    ) -> ConnectionPlan:
        """Translate the historical __init__ kwargs into a ConnectionPlan.

        Preserves the old behavior used by 65+ tests:
        - direct=True opens the serial port directly.
        - server_url=None or localhost + port: local proxy with auto-launch
          and direct-serial fallback enabled.
        - server_url=None and no port: pure offline (no probe).
        - non-local server_url: remote proxy, no auto-launch, no fallback.
        """
        if direct:
            if server_url and not _is_local_url(server_url):
                raise FPBCLIError(
                    "--direct cannot be combined with a remote --server-url. "
                    "Direct mode opens a local serial port; remote control must "
                    "go through the WebServer proxy."
                )
            return ConnectionPlan(
                mode=ConnectionMode.DIRECT,
                serial_port=port,
                baudrate=baudrate,
                source="legacy-direct",
            )

        if server_url is None:
            if port is None:
                return ConnectionPlan(
                    mode=ConnectionMode.OFFLINE, source="legacy-offline"
                )
            url = DEFAULT_SERVER_URL
            return ConnectionPlan(
                mode=ConnectionMode.LOCAL_PROXY,
                server_url=url,
                token=token,
                serial_port=port,
                baudrate=baudrate,
                allow_launch=True,
                allow_direct_fallback=True,
                source="legacy-local-default",
            )

        if _is_local_url(server_url):
            return ConnectionPlan(
                mode=ConnectionMode.LOCAL_PROXY,
                server_url=server_url,
                token=token,
                serial_port=port,
                baudrate=baudrate,
                allow_launch=bool(port),
                allow_direct_fallback=bool(port),
                source="legacy-local-explicit",
            )

        return ConnectionPlan(
            mode=ConnectionMode.REMOTE_PROXY,
            server_url=server_url,
            token=token,
            serial_port=port,
            baudrate=baudrate,
            allow_launch=False,
            allow_direct_fallback=False,
            source="legacy-remote",
        )

    def _connect_from_plan(self, plan: ConnectionPlan) -> None:
        """Single connection executor — consumes a ConnectionPlan.

        If the plan came from the handle cache and the connect raises,
        the cache entry is invalidated so the next invocation re-runs
        mDNS rather than re-trying the dead URL.
        """
        if plan.mode is ConnectionMode.OFFLINE:
            return

        if plan.mode is ConnectionMode.DIRECT:
            if plan.serial_port:
                self._direct_connect(plan.serial_port, plan.baudrate)
            return

        try:
            if plan.mode is ConnectionMode.REMOTE_PROXY:
                self._connect_remote(plan)
            else:
                self._connect_local(plan)
        except FPBCLIError:
            if plan.cache_handle:
                invalidate_cached_handle(plan.cache_handle)
            raise

    def _connect_local(self, plan: ConnectionPlan) -> None:
        proxy = ServerProxy(base_url=plan.server_url, token=plan.token)

        if proxy.is_server_running():
            self._attach_proxy(proxy, plan.serial_port, plan.baudrate)
            if self.verbose:
                logging.info(f"Using WebServer proxy mode ({plan.server_url})")
            return

        if not plan.serial_port:
            return

        if plan.allow_launch:
            if self.verbose:
                logging.info("WebServer not running, auto-launching...")
            if proxy.launch_server():
                self._attach_proxy(proxy, plan.serial_port, plan.baudrate)
                if self.verbose:
                    logging.info(
                        f"WebServer launched, proxy mode active ({plan.server_url})"
                    )
                return

        if plan.allow_direct_fallback:
            if self.verbose:
                logging.warning("Auto-launch failed, falling back to direct mode")
            self._direct_connect(plan.serial_port, plan.baudrate)

    def _connect_remote(self, plan: ConnectionPlan) -> None:
        proxy = ServerProxy(base_url=plan.server_url, token=plan.token)
        try:
            status = proxy.get_status()
        except ProxyAuthError as e:
            raise FPBCLIError(str(e))
        except Exception:
            if plan.serial_port:
                raise FPBCLIError(
                    f"Remote WebServer not reachable: {plan.server_url}. "
                    "Check the URL/port and that the server is running."
                )
            return

        if not status.get("success", False):
            if plan.serial_port:
                raise FPBCLIError(
                    f"Remote WebServer not reachable: {plan.server_url}. "
                    "Check the URL/port and that the server is running."
                )
            return

        self._attach_proxy(proxy, plan.serial_port, plan.baudrate)
        if self.verbose:
            logging.info(f"Using remote WebServer proxy ({plan.server_url})")

    def _attach_proxy(
        self, proxy: ServerProxy, port: Optional[str], baudrate: int
    ) -> None:
        """Attach to a reachable WebServer as a proxy.

        If the server has no device connected and a ``port`` was supplied,
        ask the server to open that port. ``port`` is optional: when the
        server already has a device, no port is needed.
        """
        self._proxy = proxy
        try:
            connected = proxy.is_device_connected()
            if not connected and port:
                result = proxy.connect(port, baudrate)
                connected = result.get("success", False)
            self._device_state.connected = connected
        except ProxyAuthError as e:
            raise FPBCLIError(str(e))

    def _direct_connect(self, port: str, baudrate: int):
        """Open serial port directly (legacy / escape-hatch mode)."""
        lock = PortLock(port)
        if not lock.acquire():
            owner = lock.get_owner_pid()
            raise FPBCLIError(
                f"Serial port {port} is locked by another process "
                f"(PID: {owner}). "
                f"Stop the other process or use a different port."
            )
        self._port_lock = lock
        self._device_state.connect(port, baudrate)
        if self.verbose:
            logging.info(f"Connected to {port} (direct mode)")

    def setup_logging(self):
        """Setup logging based on verbosity"""
        level = logging.DEBUG if self.verbose else logging.WARNING
        logging.basicConfig(
            level=level,
            format="%(levelname)s: %(message)s",
            stream=sys.stderr,  # Errors to stderr, JSON to stdout
        )

    def output_json(self, data: Dict[str, Any]) -> None:
        """Output result as JSON to stdout"""
        print(json.dumps(data, indent=2, ensure_ascii=False))

    def output_error(
        self,
        message: str,
        error: Optional[Exception] = None,
        hint: Optional[str] = None,
    ) -> None:
        """Output error as JSON"""
        error_data = {"success": False, "error": message}
        if hint:
            error_data["hint"] = hint
        if error and self.verbose:
            error_data["exception"] = str(error)
        self.output_json(error_data)

    # Hint appended to serial-loss-flavored failures, pointing at `doctor`.
    _SERIAL_LOSS_HINT = (
        "serial loss/timeout? run `fpbinject doctor` for copy-paste tuning "
        "flags, or raise --transfer-max-retries"
    )

    @staticmethod
    def _looks_like_serial_loss(message: str) -> bool:
        msg = (message or "").lower()
        return any(
            k in msg
            for k in (
                "crc",
                "timeout",
                "mismatch",
                "retries",
                "read failed",
                "write failed",
            )
        )

    def _require_device(self) -> None:
        """Raise if no device connection (proxy or direct) is available."""
        if not self._proxy and not self._device_state.connected:
            raise FPBCLIError("No device connected. Use --port to specify serial port.")

    @staticmethod
    def _write_local(local_path: str, data: bytes) -> None:
        """Write binary data to a local file, creating directories as needed."""
        local_dir = os.path.dirname(local_path)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)

    def analyze(self, elf_path: str, func_name: str) -> None:
        """Analyze function in ELF file"""
        try:
            symbols = self._fpb.get_symbols(elf_path)

            if func_name not in symbols:
                raise FPBCLIError(f"Function '{func_name}' not found")

            info = symbols[func_name]
            addr = info["addr"] if isinstance(info, dict) else info
            # Get disassembly for analysis
            success, disasm = self._fpb.disassemble_function(elf_path, func_name)
            signature = self._fpb.get_signature(elf_path, func_name)

            self.output_json(
                {
                    "success": True,
                    "analysis": {
                        "func_name": func_name,
                        "addr": hex(addr),
                        "signature": signature,
                        "asm_lines": len(disasm.split("\n")) if disasm else 0,
                    },
                }
            )
        except Exception as e:
            self.output_error(f"Analysis failed: {str(e)}", e)

    def disasm(self, elf_path: str, func_name: str) -> None:
        """Get disassembly for function"""
        try:
            success, disasm = self._fpb.disassemble_function(elf_path, func_name)

            if not success or not disasm:
                raise FPBCLIError(f"Could not disassemble '{func_name}'")

            self.output_json(
                {
                    "success": True,
                    "func_name": func_name,
                    "disasm": disasm,
                    "language": "arm_asm",
                }
            )
        except Exception as e:
            self.output_error(f"Disassembly failed: {str(e)}", e)

    def decompile(self, elf_path: str, func_name: str) -> None:
        """Decompile function using Ghidra"""
        try:
            success, decompiled = self._fpb.decompile_function(elf_path, func_name)
            if not success:
                raise FPBCLIError(f"Decompilation failed: {decompiled}")

            self.output_json(
                {
                    "success": True,
                    "func_name": func_name,
                    "decompiled": decompiled,
                    "language": "c",
                    "note": "This is machine-generated pseudo-code. Verify before using.",
                }
            )
        except Exception as e:
            self.output_error(f"Decompilation failed: {str(e)}", e)

    def signature(self, elf_path: str, func_name: str) -> None:
        """Get function signature"""
        try:
            sig = self._fpb.get_signature(elf_path, func_name)

            self.output_json(
                {"success": True, "func_name": func_name, "signature": sig}
            )
        except Exception as e:
            self.output_error(f"Signature retrieval failed: {str(e)}", e)

    def search(self, elf_path: str, pattern: str) -> None:
        """Search for functions by pattern"""
        try:
            symbols = self._fpb.get_symbols(elf_path)

            matches = [
                {
                    "name": name,
                    "addr": hex(info["addr"]) if isinstance(info, dict) else hex(info),
                    "type": (
                        info.get("sym_type", "other")
                        if isinstance(info, dict)
                        else "other"
                    ),
                }
                for name, info in symbols.items()
                if pattern.lower() in name.lower()
            ]

            self.output_json(
                {
                    "success": True,
                    "pattern": pattern,
                    "count": len(matches),
                    "symbols": matches[:20],
                }
            )
        except Exception as e:
            self.output_error(f"Search failed: {str(e)}", e)

    def get_symbols(self, elf_path: str, pattern: str = "", limit: int = 0) -> None:
        """Get all symbols from ELF file via nm"""
        try:
            symbols = self._fpb.get_symbols(elf_path)

            if pattern:
                pat = pattern.lower()
                symbols = {k: v for k, v in symbols.items() if pat in k.lower()}

            result_list = [
                {
                    "name": name,
                    "addr": hex(info["addr"]) if isinstance(info, dict) else hex(info),
                    "type": (
                        info.get("sym_type", "other")
                        if isinstance(info, dict)
                        else "other"
                    ),
                }
                for name, info in sorted(symbols.items(), key=lambda x: x[0])
            ]

            if limit > 0:
                result_list = result_list[:limit]

            self.output_json(
                {
                    "success": True,
                    "count": len(result_list),
                    "total": len(symbols),
                    "symbols": result_list,
                }
            )
        except Exception as e:
            self.output_error(f"Get symbols failed: {str(e)}", e)

    def compile(
        self,
        source_file: str,
        elf_path: Optional[str] = None,
        base_addr: int = 0x20001000,
        compile_commands: Optional[str] = None,
    ) -> None:
        """Compile patch source code"""
        try:
            source_path = Path(source_file)
            if not source_path.exists():
                raise FPBCLIError(f"Source file not found: {source_file}")

            # Read source content
            with open(source_file, "r", encoding="utf-8") as f:
                source_content = f.read()

            # Determine source extension
            source_ext = source_path.suffix

            # Compile using FPBInject
            binary_data, symbols, error = self._fpb.compile_inject(
                source_content=source_content,
                base_addr=base_addr,
                elf_path=elf_path,
                compile_commands_path=compile_commands,
                verbose=self.verbose,
                source_ext=source_ext,
                original_source_file=str(source_path.absolute()),
            )

            if error:
                raise FPBCLIError(f"Compilation error: {error}")

            if not binary_data:
                raise FPBCLIError("Compilation produced no output")

            # Output result
            self.output_json(
                {
                    "success": True,
                    "binary_size": len(binary_data),
                    "base_addr": hex(base_addr),
                    "symbols": {
                        name: hex(addr) for name, addr in (symbols or {}).items()
                    },
                    "binary_hex": (
                        binary_data.hex()
                        if len(binary_data) < 1024
                        else binary_data[:1024].hex() + "..."
                    ),
                }
            )

        except Exception as e:
            self.output_error(f"Compilation failed: {str(e)}", e)

    def inject(
        self,
        target_func: str,
        source_file: str,
        elf_path: Optional[str] = None,
        compile_commands: Optional[str] = None,
        patch_mode: str = "trampoline",
        comp: int = -1,
        verify: bool = False,
    ) -> None:
        """Inject patch to device (requires serial connection)"""
        try:
            source_path = Path(source_file)
            if not source_path.exists():
                raise FPBCLIError(f"Source file not found: {source_file}")

            # Proxy mode: forward to WebServer
            if self._proxy:
                result = self._proxy.inject(
                    target_func=target_func,
                    source_file=source_file,
                    elf_path=elf_path,
                    compile_commands=compile_commands,
                    patch_mode=patch_mode,
                    comp=comp,
                )
                self.output_json(result)
                return

            # Offline: no device — compile-only validation
            if not self._device_state.connected:
                with open(source_file, "r", encoding="utf-8") as f:
                    source_content = f.read()

                elf = elf_path or getattr(self._device_state, "elf_path", None)
                if not elf:
                    prog = os.path.basename(sys.argv[0]) or "fpbinject"
                    raise FPBCLIError(
                        "No device connected and no ELF path provided.\n"
                        f"Use: {prog} inject <target_func> <source.c> --elf <elf_path> --compile-commands <path>\n"
                        "Or connect to device first using the WebServer interface."
                    )

                binary_data, symbols, error = self._fpb.compile_inject(
                    source_content=source_content,
                    base_addr=0x20001000,
                    elf_path=elf,
                    compile_commands_path=compile_commands,
                    source_ext=source_path.suffix,
                    original_source_file=str(source_path.absolute()),
                )

                if error:
                    raise FPBCLIError(f"Compilation error: {error}")

                self.output_json(
                    {
                        "success": False,
                        "error": "No device connected",
                        "note": "Patch compiled successfully but device not connected. Use WebServer to inject.",
                        "compiled": {
                            "binary_size": len(binary_data) if binary_data else 0,
                            "symbols": {
                                name: hex(addr)
                                for name, addr in (symbols or {}).items()
                            },
                            "target_func": target_func,
                        },
                    }
                )
                return

            # Direct mode: device connected locally
            with open(source_file, "r", encoding="utf-8") as f:
                source_content = f.read()

            if elf_path:
                self._device_state.elf_path = elf_path
            if compile_commands:
                self._device_state.compile_commands_path = compile_commands

            success, result = self._fpb.inject(
                source_content=source_content,
                target_func=target_func,
                patch_mode=patch_mode,
                comp=comp,
                source_ext=source_path.suffix,
                original_source_file=str(source_path.absolute()),
            )

            self.output_json(
                {
                    "success": success,
                    "result": result,
                    "verify_status": None,
                }
            )

        except Exception as e:
            self.output_error(f"Injection failed: {str(e)}", e)

    def unpatch(self, comp: int = 0, all_patches: bool = False) -> None:
        """Remove patch from device"""
        try:
            if self._proxy:
                result = self._proxy.unpatch(comp=comp, all_patches=all_patches)
                self.output_json(result)
                return

            self._require_device()
            success, msg = self._fpb.unpatch(comp=comp, all=all_patches)
            self.output_json(
                {
                    "success": success,
                    "message": msg,
                    "comp": comp if not all_patches else "all",
                }
            )
        except Exception as e:
            self.output_error(f"Unpatch failed: {str(e)}", e)

    def info(self) -> None:
        """Get device FPB info"""
        try:
            if self._proxy:
                result = self._proxy.info()
                self.output_json(result)
                return

            self._require_device()
            info, error = self._fpb.info()
            if error:
                raise FPBCLIError(f"Failed to get info: {error}")

            result = {"success": True, "info": info}

            # Check build time mismatch
            device_build_time = info.get("build_time") if info else None
            elf_build_time = None
            if self._device_state.elf_path and os.path.exists(
                self._device_state.elf_path
            ):
                elf_build_time = self._fpb.get_elf_build_time(
                    self._device_state.elf_path
                )

            if device_build_time or elf_build_time:
                build_time_mismatch = bool(
                    device_build_time
                    and elf_build_time
                    and device_build_time.strip() != elf_build_time.strip()
                )
                result["device_build_time"] = device_build_time
                result["elf_build_time"] = elf_build_time
                result["build_time_mismatch"] = build_time_mismatch
                if build_time_mismatch:
                    logging.warning(
                        f"Build time mismatch! Device: '{device_build_time}', ELF: '{elf_build_time}'"
                    )

            self.output_json(result)
        except Exception as e:
            self.output_error(f"Info failed: {str(e)}", e)

    def test_serial(
        self,
        start_size: int = 16,
        max_size: int = 4096,
        timeout: float = 2.0,
        trials: int = 8,
        min_success_rate: float = 1.0,
    ) -> None:
        """Test serial throughput to find max single-transfer size."""
        try:
            if self._proxy:
                self.output_json(
                    self._proxy.test_serial(
                        start_size, max_size, timeout, trials, min_success_rate
                    )
                )
                return

            self._require_device()
            self.output_json(
                self._fpb.test_serial_throughput(
                    start_size=start_size,
                    max_size=max_size,
                    timeout=timeout,
                    trials=trials,
                    min_success_rate=min_success_rate,
                )
            )
        except Exception as e:
            self.output_error(f"Serial test failed: {str(e)}", e)

    @staticmethod
    def _doctor_suggestions(result: dict) -> list:
        """Turn a test-serial result into copy-paste tuning suggestions.

        Returns a list of {reason, command, params} dicts. Pure/static so it
        can be unit tested without a device.
        """
        suggestions = []
        if not result or not result.get("success"):
            return suggestions

        # PC->device fragmentation needed (slow/lossy serial driver).
        if result.get("fragment_needed"):
            fsize = result.get("recommended_fragment_size", 64)
            fdelay = result.get("recommended_fragment_delay", 0.005)
            suggestions.append(
                {
                    "reason": "PC->device serial loss detected; fragment TX writes",
                    "params": {
                        "serial-tx-fragment-size": fsize,
                        "serial-tx-fragment-delay": fdelay,
                    },
                    "command": (
                        f"--serial-tx-fragment-size {fsize} "
                        f"--serial-tx-fragment-delay {fdelay}"
                    ),
                }
            )

        # Recommended chunk sizes from the probe.
        up = result.get("recommended_upload_chunk_size")
        if up:
            suggestions.append(
                {
                    "reason": "use the probed max reliable upload chunk size",
                    "params": {"upload-chunk-size": up},
                    "command": f"--upload-chunk-size {up}",
                }
            )
        down = result.get("recommended_download_chunk_size")
        if down:
            suggestions.append(
                {
                    "reason": "use the probed max reliable download chunk size",
                    "params": {"download-chunk-size": down},
                    "command": f"--download-chunk-size {down}",
                }
            )
        return suggestions

    def doctor(
        self,
        start_size: int = 16,
        max_size: int = 512,
        timeout: float = 2.0,
        trials: int = 8,
    ) -> None:
        """Diagnose serial reliability and print copy-paste tuning commands.

        Runs the throughput probe, then translates its recommendations into
        ready-to-use flags so a serial-loss situation has an obvious next step.
        """
        try:
            if self._proxy:
                result = self._proxy.test_serial(
                    start_size, max_size, timeout, trials, 1.0
                )
            else:
                self._require_device()
                result = self._fpb.test_serial_throughput(
                    start_size=start_size,
                    max_size=max_size,
                    timeout=timeout,
                    trials=trials,
                    min_success_rate=1.0,
                )

            suggestions = self._doctor_suggestions(result)
            combined = " ".join(s["command"] for s in suggestions).strip()
            self.output_json(
                {
                    "success": bool(result.get("success")),
                    "probe": result,
                    "suggestions": suggestions,
                    "apply_command": combined,
                    "hint": (
                        "re-run your transfer with: " + combined
                        if combined
                        else "serial looks healthy; no tuning needed"
                    ),
                }
            )
        except Exception as e:
            self.output_error(f"doctor failed: {str(e)}", e)

    def file_list(self, path: str = "/") -> None:
        """List directory contents on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_list(path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, entries = ft.flist(path)
            if not success:
                raise FPBCLIError(f"Failed to list directory: {path}")
            self.output_json({"success": True, "path": path, "entries": entries})
        except Exception as e:
            self.output_error(f"file_list failed: {str(e)}", e)

    def file_stat(self, path: str) -> None:
        """Get file/directory stat on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_stat(path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, stat = ft.fstat(path)
            if not success:
                raise FPBCLIError(f"Failed to stat: {stat.get('error', 'unknown')}")
            self.output_json({"success": True, "path": path, "stat": stat})
        except Exception as e:
            self.output_error(f"file_stat failed: {str(e)}", e)

    def file_download(self, remote_path: str, local_path: str) -> None:
        """Download a file from device to local path"""
        try:
            if self._proxy:
                self._transfer_notice("downloading", remote_path, 0)
                try:
                    result = self._proxy.file_download(remote_path)
                except KeyboardInterrupt:
                    # Client is going away mid-transfer: tell the server to
                    # cancel so it stops and releases the transaction lock.
                    self._cancel_proxy_transfer()
                    raise
                if result.get("success") and result.get("data"):
                    import base64

                    data = base64.b64decode(result["data"])
                    self._write_local(local_path, data)
                    self.output_json(
                        {
                            "success": True,
                            "remote_path": remote_path,
                            "local_path": local_path,
                            "size": len(data),
                            "message": f"Downloaded {len(data)} bytes via proxy",
                        }
                    )
                else:
                    self.output_json(result)
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
                max_retries=self._device_state.transfer_max_retries,
            )
            # Best-effort size lookup for the notice; never let it break the
            # actual download (e.g. stat unsupported or mocked in tests).
            size_hint = 0
            try:
                stat_ok, stat = ft.fstat(remote_path)
                if stat_ok and isinstance(stat, dict):
                    size_hint = stat.get("size", 0)
            except Exception:
                size_hint = 0
            self._transfer_notice("downloading", remote_path, size_hint)
            success, data, msg = ft.download(
                remote_path, progress_cb=self._make_progress_printer()
            )
            if not success:
                raise FPBCLIError(f"Download failed: {msg}")
            self._write_local(local_path, data)
            self.output_json(
                {
                    "success": True,
                    "remote_path": remote_path,
                    "local_path": local_path,
                    "size": len(data),
                    "message": msg,
                }
            )
        except Exception as e:
            hint = (
                self._SERIAL_LOSS_HINT if self._looks_like_serial_loss(str(e)) else None
            )
            self.output_error(f"file_download failed: {str(e)}", e, hint=hint)

    def file_upload(self, local_path: str, remote_path: str) -> None:
        """Upload a local file to device"""
        try:
            if self._proxy:
                try:
                    _sz = os.path.getsize(local_path)
                except OSError:
                    _sz = 0
                self._transfer_notice("uploading", remote_path, _sz)
                try:
                    result = self._proxy.file_upload(local_path, remote_path)
                except KeyboardInterrupt:
                    # Client is going away mid-transfer: tell the server to
                    # cancel so it stops and releases the transaction lock.
                    self._cancel_proxy_transfer()
                    raise
                self.output_json(result)
                return

            self._require_device()
            with open(local_path, "rb") as f:
                data = f.read()

            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
                max_retries=self._device_state.transfer_max_retries,
            )
            self._transfer_notice("uploading", remote_path, len(data))
            success, msg = ft.upload(
                data, remote_path, progress_cb=self._make_progress_printer()
            )
            if not success:
                raise FPBCLIError(f"Upload failed: {msg}")
            self.output_json(
                {
                    "success": True,
                    "local_path": local_path,
                    "remote_path": remote_path,
                    "size": len(data),
                    "message": msg,
                }
            )
        except Exception as e:
            hint = (
                self._SERIAL_LOSS_HINT if self._looks_like_serial_loss(str(e)) else None
            )
            self.output_error(f"file_upload failed: {str(e)}", e, hint=hint)

    def file_remove(self, path: str) -> None:
        """Remove a file on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_remove(path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, msg = ft.fremove(path)
            if not success:
                raise FPBCLIError(f"Failed to remove: {msg}")
            self.output_json({"success": True, "path": path, "message": msg})
        except Exception as e:
            self.output_error(f"file_remove failed: {str(e)}", e)

    def file_mkdir(self, path: str) -> None:
        """Create a directory on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_mkdir(path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, msg = ft.fmkdir(path)
            if not success:
                raise FPBCLIError(f"Failed to mkdir: {msg}")
            self.output_json({"success": True, "path": path, "message": msg})
        except Exception as e:
            self.output_error(f"file_mkdir failed: {str(e)}", e)

    def file_rename(self, old_path: str, new_path: str) -> None:
        """Rename a file or directory on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_rename(old_path, new_path))
                return

            self._require_device()
            from fpbinject.core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
            )
            success, msg = ft.frename(old_path, new_path)
            if not success:
                raise FPBCLIError(f"Failed to rename: {msg}")
            self.output_json(
                {
                    "success": True,
                    "old_path": old_path,
                    "new_path": new_path,
                    "message": msg,
                }
            )
        except Exception as e:
            self.output_error(f"file_rename failed: {str(e)}", e)

    def mem_read(self, addr: int, length: int, fmt: str = "hex") -> None:
        """Read memory from device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.mem_read(addr, length, fmt))
                return

            self._require_device()
            self._fpb.enter_fl_mode()
            try:
                data, msg = self._fpb.read_memory(addr, length)
            finally:
                self._fpb.exit_fl_mode()

            if data is None:
                raise FPBCLIError(f"Memory read failed: {msg}")

            result = {
                "success": True,
                "addr": f"0x{addr:08X}",
                "length": length,
                "actual_length": len(data),
            }
            if fmt == "hex":
                lines = []
                for i in range(0, len(data), 16):
                    chunk = data[i : i + 16]
                    hex_part = " ".join(f"{b:02X}" for b in chunk)
                    ascii_part = "".join(
                        chr(b) if 0x20 <= b < 0x7F else "." for b in chunk
                    )
                    lines.append(f"0x{addr + i:08X}: {hex_part:<48s} {ascii_part}")
                result["hex_dump"] = "\n".join(lines)
            elif fmt == "raw":
                result["data"] = data.hex()
            elif fmt == "u32":
                result["words"] = [
                    f"0x{int.from_bytes(data[i:i+4], 'little'):08X}"
                    for i in range(0, len(data) - 3, 4)
                ]
            self.output_json(result)
        except Exception as e:
            self.output_error(f"Memory read failed: {str(e)}", e)

    def mem_write(self, addr: int, data_hex: str) -> None:
        """Write memory to device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.mem_write(addr, data_hex))
                return

            self._require_device()
            try:
                data = bytes.fromhex(data_hex)
            except ValueError:
                raise FPBCLIError(
                    f"Invalid hex data: '{data_hex}'. Use hex string like 'DEADBEEF'."
                )

            self._fpb.enter_fl_mode()
            try:
                success, error = self._fpb.write_memory(addr, data)
            finally:
                self._fpb.exit_fl_mode()

            if not success:
                raise FPBCLIError(f"Memory write failed: {error}")
            self.output_json(
                {
                    "success": True,
                    "addr": f"0x{addr:08X}",
                    "length": len(data),
                    "message": f"Wrote {len(data)} bytes to 0x{addr:08X}",
                }
            )
        except Exception as e:
            self.output_error(f"Memory write failed: {str(e)}", e)

    def mem_dump(self, addr: int, length: int, output_file: str) -> None:
        """Dump memory region to binary file"""
        try:
            if self._proxy:
                result = self._proxy.mem_read(addr, length, fmt="raw")
                if result.get("success") and result.get("data"):
                    data = bytes.fromhex(result["data"])
                    self._write_local(output_file, data)
                    self.output_json(
                        {
                            "success": True,
                            "addr": f"0x{addr:08X}",
                            "length": len(data),
                            "output_file": output_file,
                            "message": f"Dumped {len(data)} bytes to {output_file}",
                        }
                    )
                else:
                    self.output_json(result)
                return

            self._require_device()
            self._fpb.enter_fl_mode()
            try:
                data, msg = self._fpb.read_memory(addr, length)
            finally:
                self._fpb.exit_fl_mode()

            if data is None:
                raise FPBCLIError(f"Memory read failed: {msg}")
            self._write_local(output_file, data)
            self.output_json(
                {
                    "success": True,
                    "addr": f"0x{addr:08X}",
                    "length": len(data),
                    "output_file": output_file,
                    "message": f"Dumped {len(data)} bytes to {output_file}",
                }
            )
        except Exception as e:
            self.output_error(f"Memory dump failed: {str(e)}", e)

    def serial_send(
        self, data: str, read_response: bool = True, timeout: float = 1.0
    ) -> None:
        """Send data to device serial port."""
        try:
            if self._proxy:
                result = self._proxy.serial_send(data)
                if result.get("success") and read_response:
                    import time as _time

                    _time.sleep(timeout)
                    log_resp = self._proxy.serial_read(raw_since=0)
                    result["response"] = log_resp.get("raw_data", "").strip()
                self.output_json(result)
                return

            self._require_device()
            ser = self._device_state.ser
            ser.write((data + "\n").encode())
            ser.flush()

            response = ""
            if read_response:
                import time as _time

                start = _time.time()
                while _time.time() - start < timeout:
                    if ser.in_waiting:
                        response += ser.read(ser.in_waiting).decode(
                            "utf-8", errors="replace"
                        )
                        _time.sleep(0.05)
                    else:
                        if response:
                            break
                        _time.sleep(0.1)

            self.output_json(
                {"success": True, "sent": data, "response": response.strip()}
            )
        except Exception as e:
            self.output_error(f"Serial send failed: {str(e)}", e)

    def serial_read(
        self,
        timeout: float = 1.0,
        lines: int = 50,
        since: int = 0,
        max_bytes: int = 4096,
        tail: int = 0,
        drop: bool = False,
    ) -> None:
        """Read serial output, context-safe (adb-logcat style).

        Bounded by ``max_bytes`` so a large backlog never blows up the
        consumer's context. Defaults to a tail read; page the rest with
        ``--since <next>`` or skip it with ``--drop``.
        """
        try:
            if self._proxy:
                # Default (no since, no explicit tail) -> tail read so we never
                # dump the whole backlog on first call.
                effective_tail = tail
                if since == 0 and tail == 0 and not drop:
                    effective_tail = max_bytes
                win = self._proxy.serial_read_window(
                    since=since,
                    max_bytes=max_bytes,
                    tail=effective_tail,
                    drop=drop,
                )
                self._emit_serial_window(win)
                return

            self._require_device()
            import time as _time

            ser = self._device_state.ser
            new_data = ""
            start = _time.time()
            while _time.time() - start < timeout:
                if ser.in_waiting:
                    new_data += ser.read(ser.in_waiting).decode(
                        "utf-8", errors="replace"
                    )
                    _time.sleep(0.05)
                else:
                    if new_data:
                        break
                    _time.sleep(0.1)

            # Apply the same byte budget in direct mode: keep the newest
            # max_bytes so a burst of output cannot blow up the context.
            data_bytes = new_data.encode("utf-8")
            truncated = False
            if max_bytes > 0 and len(data_bytes) > max_bytes:
                data_bytes = data_bytes[-max_bytes:]
                new_data = data_bytes.decode("utf-8", errors="replace")
                truncated = True

            log_lines = [ln for ln in new_data.split("\n") if ln.strip()][-lines:]
            out = {
                "success": True,
                "new_data": new_data,
                "log": log_lines,
                "log_count": len(log_lines),
                "returned_bytes": len(data_bytes),
                "truncated": truncated,
            }
            if truncated:
                out["hint"] = (
                    "output exceeded --max-bytes and was tail-trimmed; "
                    "increase --max-bytes if you need more"
                )
            self.output_json(out)
        except Exception as e:
            self.output_error(f"Serial read failed: {str(e)}", e)

    def _emit_serial_window(self, win: dict) -> None:
        """Emit a context-safe windowed read result (proxy mode).

        Builds a bounded JSON payload and attaches an actionable ``hint`` so
        the caller knows how to page or skip the remaining backlog.
        """
        data = win.get("data", "")
        pending = win.get("pending_bytes", 0)
        out = {
            "success": True,
            "data": data,
            "next": win.get("next", 0),
            "returned_bytes": win.get("returned_bytes", len(data.encode("utf-8"))),
            "pending_bytes": pending,
            "pending_entries": win.get("pending_entries", 0),
            "truncated": win.get("truncated", False),
            "buffer_overflowed": win.get("buffer_overflowed", False),
        }
        hints = []
        if pending and pending > 0:
            hints.append(
                f"{pending} bytes still buffered; read more with "
                f"--since {out['next']}, or skip with --drop"
            )
        if out["buffer_overflowed"]:
            hints.append(
                "buffer overflowed: some earlier data was evicted before this "
                "cursor and is lost"
            )
        if hints:
            out["hint"] = "; ".join(hints)
        self.output_json(out)

    def connect(self, port: str, baudrate: int = 115200) -> None:
        """Connect to device (via proxy or direct)."""
        try:
            if self._proxy:
                result = self._proxy.connect(port, baudrate)
                self._device_state.connected = result.get("success", False)
                self.output_json(result)
                return

            if self._device_state.connected:
                self.output_json({"success": True, "message": "Already connected"})
                return

            self._direct_connect(port, baudrate)
            self.output_json({"success": True, "port": port})
        except Exception as e:
            self.output_error(f"Connect failed: {str(e)}", e)

    def disconnect(self) -> None:
        """Disconnect from device."""
        try:
            if self._proxy:
                result = self._proxy.disconnect()
                self._device_state.connected = False
                self.output_json(result)
                return

            self._device_state.disconnect()
            if self._port_lock:
                self._port_lock.release()
                self._port_lock = None
            self.output_json({"success": True})
        except Exception as e:
            self.output_error(f"Disconnect failed: {str(e)}", e)

    def _require_proxy_for_vserial(self) -> None:
        """Virtual serial is only available in proxy mode.

        The PTY device node lives in the long-lived WebServer process, so
        it persists after this short-lived CLI invocation exits. This is
        exactly what a headless (no-desktop) host needs: the server hands
        out /dev/pts/N and any local serial tool (minicom, pyserial) opens
        it. Direct mode has no persistent process and therefore cannot host
        a virtual serial device.
        """
        if not self._proxy:
            raise FPBCLIError(
                "Virtual serial requires a running WebServer (proxy mode). "
                "The PTY must be hosted by the long-lived server process; a "
                "one-shot direct CLI cannot keep the device node alive.\n"
                "Start a server first (it auto-launches headless when you run "
                "a device command with --port), then retry."
            )

    def vserial_start(self, symlink: Optional[str] = None) -> None:
        """Create the virtual serial device on the server (proxy mode only)."""
        try:
            self._require_proxy_for_vserial()
            self.output_json(self._proxy.vserial_start(symlink=symlink))
        except Exception as e:
            self.output_error(f"Virtual serial start failed: {str(e)}", e)

    def vserial_stop(self) -> None:
        """Remove the virtual serial device on the server (proxy mode only)."""
        try:
            self._require_proxy_for_vserial()
            self.output_json(self._proxy.vserial_stop())
        except Exception as e:
            self.output_error(f"Virtual serial stop failed: {str(e)}", e)

    def vserial_status(self) -> None:
        """Query the virtual serial device status (proxy mode only)."""
        try:
            self._require_proxy_for_vserial()
            self.output_json(self._proxy.vserial_status())
        except Exception as e:
            self.output_error(f"Virtual serial status failed: {str(e)}", e)

    # Approximate serial throughput for ETA hints (bytes/sec). Matches the
    # ~55 KB/s figure used elsewhere (capture timeout math, docs).
    _SERIAL_BYTES_PER_SEC = 55000

    def _transfer_notice(self, verb: str, name: str, size: int) -> None:
        """Print a one-line predictive notice to stderr before a transfer.

        Serial transfers are slow; without this an AI sees a long silence and
        assumes the tool hung. Progress (below) and the final JSON confirm
        liveness. Suppressed when --quiet.
        """
        if getattr(self, "_quiet", False):
            return
        eta = size / self._SERIAL_BYTES_PER_SEC if size else 0
        print(
            f"[transfer] {verb} {name} ({size} bytes over serial "
            f"~{self._SERIAL_BYTES_PER_SEC // 1000} KB/s, ~{eta:.0f}s); "
            f"progress on stderr, JSON on stdout when done",
            file=sys.stderr,
            flush=True,
        )

    def _make_progress_printer(self):
        """Return a progress_cb that prints a throttled \\r line to stderr.

        Returns None when --quiet so callers can pass it through unchanged.
        """
        if getattr(self, "_quiet", False):
            return None
        import time as _time

        state = {"last": 0.0}

        def cb(done: int, total: int) -> None:
            now = _time.time()
            # Throttle to ~5 Hz; always show the final 100% tick.
            if now - state["last"] < 0.2 and (not total or done < total):
                return
            state["last"] = now
            pct = f"{(done / total * 100):5.1f}%" if total else "  ?  "
            print(
                f"\r[transfer] {pct}  {done}/{total} bytes",
                end="",
                file=sys.stderr,
                flush=True,
            )
            if total and done >= total:
                print("", file=sys.stderr, flush=True)  # newline at completion

        return cb

    def _cancel_proxy_transfer(self):
        """Best-effort: tell the server to cancel an in-flight transfer.

        Called when the CLI is interrupted mid-transfer so the server-side
        transfer stops and releases the file transaction lock instead of
        running to completion with no client to receive the result.
        """
        if not self._proxy:
            return
        try:
            self._proxy.transfer_cancel()
        except Exception:
            # Never mask the original interrupt/error with a cancel failure.
            pass

    def cleanup(self):
        """Cleanup resources"""
        self._device_state.disconnect()
        if self._port_lock:
            self._port_lock.release()
            self._port_lock = None

    def server_stop(self, port: int = DEFAULT_PORT) -> None:
        """Stop a CLI-launched WebServer on the given port."""
        from fpbinject.cli.server_proxy import stop_cli_server, list_cli_servers

        if port == DEFAULT_PORT:
            # If user didn't specify, try to find any running CLI server
            servers = list_cli_servers()
            if len(servers) == 1:
                port = servers[0]["port"]
            elif len(servers) > 1:
                self.output_json(
                    {
                        "success": False,
                        "error": "Multiple CLI servers running, specify --port",
                        "servers": servers,
                    }
                )
                return

        self.output_json(stop_cli_server(port))


def _is_local_url(url: str) -> bool:
    """True if ``url`` points at this host (loopback or local interface IP)."""
    from urllib.parse import urlparse

    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    if not host:
        return False
    if host in ("localhost",):
        return True
    try:
        from fpbinject.cli.discover import _is_loopback, _local_interface_ips

        if _is_loopback(host):
            return True
        return host in _local_interface_ips()
    except Exception:
        return host == "127.0.0.1"


def _localhost_status_ok(port: int = DEFAULT_PORT, timeout: float = 0.3) -> bool:
    """Quick TCP probe — does http://127.0.0.1:port answer /api/status?"""
    import urllib.request

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/status", timeout=timeout
        ) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _classify_url(url: str, *, token: Optional[str], source: str) -> ConnectionPlan:
    if _is_local_url(url):
        return ConnectionPlan(
            mode=ConnectionMode.LOCAL_PROXY,
            server_url=url,
            token=token,
            source=source,
        )
    return ConnectionPlan(
        mode=ConnectionMode.REMOTE_PROXY,
        server_url=url,
        token=token,
        source=source,
    )


def _attach_serial_port(
    plan: ConnectionPlan, port: Optional[str], baudrate: int
) -> ConnectionPlan:
    """Return a new plan with serial_port/baudrate filled and launch flags set
    according to whether the plan is local + has a serial port."""
    if not port:
        return plan
    is_local = plan.mode is ConnectionMode.LOCAL_PROXY
    return ConnectionPlan(
        mode=plan.mode,
        server_url=plan.server_url,
        token=plan.token,
        serial_port=port,
        baudrate=baudrate,
        allow_launch=is_local,
        allow_direct_fallback=is_local,
        source=plan.source,
        cache_handle=plan.cache_handle,
    )


def _with_cache_handle(
    plan: ConnectionPlan, cache_handle: Optional[str]
) -> ConnectionPlan:
    """Return a new plan tagged with the cache handle (so a connect failure
    can invalidate the right entry)."""
    if cache_handle is None:
        return plan
    return ConnectionPlan(
        mode=plan.mode,
        server_url=plan.server_url,
        token=plan.token,
        serial_port=plan.serial_port,
        baudrate=plan.baudrate,
        allow_launch=plan.allow_launch,
        allow_direct_fallback=plan.allow_direct_fallback,
        source=plan.source,
        cache_handle=cache_handle,
    )


def _resolve_handle_to_url(value: str, *, source: str) -> str:
    """Turn a user-supplied -s/FPB_SERVER value into a server URL.

    Three forms accepted:
      * URL (anything containing ``://``) -> used verbatim.
      * ``host:port`` handle -> cache lookup, falls back to mDNS browse.
      * ``host`` only        -> mDNS browse, must match exactly one server
                                 (multiple matches -> exit 2 with hints).

    Cache contract for ``host:port``:

      * Hit: return the cached URL immediately (no mDNS), AND spawn a
        daemon thread that re-runs the mDNS lookup to refresh the entry.
        The user does not block on the refresh.
      * Miss / expired / FPB_NO_CACHE=1: synchronous mDNS, then store.

    A cached URL that turns out to be unreachable triggers a connection
    error inside the connector; ``invalidate_cached_handle`` lets the
    caller wipe the bad entry and try again.

    The ``source`` string ("-s flag" / "FPB_SERVER env") is only used in
    error messages.
    """
    from fpbinject.cli.discover import classify_handle, find_by_handle
    from fpbinject.cli import handle_cache

    kind = classify_handle(value)
    if kind == "url":
        return value

    if discover_sync_by_handle is None:
        raise FPBCLIError(
            f"Cannot resolve {source} '{value}': zeroconf not installed. "
            "Pass a full URL instead."
        )

    if kind == "host_port":
        cached = handle_cache.lookup(value)
        if cached and cached.get("url"):
            handle_cache.spawn_refresh(lambda: _refresh_handle_cache(value))
            return cached["url"]

    servers = discover_sync_by_handle(value)
    matches = find_by_handle(servers, value)
    if not matches:
        prog = os.path.basename(sys.argv[0]) or "fpbinject"
        raise FPBCLIError(
            f"No FPBInject server matches {source} '{value}'. "
            f"Run '{prog} discover' to list visible servers."
        )
    if len(matches) > 1:
        msg = [f"{source} '{value}' is ambiguous; matches multiple servers:"]
        for s in matches:
            msg.append(f"  {s.handle}  {s.url}")
        msg.append("Be more specific (use 'host:port' form).")
        raise AmbiguousServerError("\n".join(msg))

    chosen = matches[0]
    if kind == "host_port":
        handle_cache.store(value, url=chosen.url, server_id=chosen.id)
    return chosen.url


def _refresh_handle_cache(value: str) -> None:
    """Background-thread entrypoint: re-run mDNS for ``value`` and update cache.

    Errors are swallowed because this is a best-effort refresh; the next
    foreground call will fall back to a synchronous lookup.
    """
    from fpbinject.cli.discover import find_by_handle
    from fpbinject.cli import handle_cache

    try:
        servers = discover_sync_by_handle(value, timeout=1.5)
        matches = find_by_handle(servers, value)
        if len(matches) == 1:
            chosen = matches[0]
            handle_cache.store(value, url=chosen.url, server_id=chosen.id)
        elif not matches:
            handle_cache.invalidate(value)
    except Exception:
        pass


def invalidate_cached_handle(value: str) -> None:
    """Public hook so the connector can drop a bad cache entry."""
    from fpbinject.cli import handle_cache

    handle_cache.invalidate(value)


def resolve_connection_plan(args) -> ConnectionPlan:
    """Single resolver: return the ConnectionPlan for ``args``.

    Precedence (first hit wins):
        1. command_policy in {OFFLINE, SERVER_ADMIN} -> OFFLINE plan
        2. --direct flag                              -> DIRECT plan
        3. -s / --server                              -> resolve handle, classify URL
        4. FPB_SERVER env                             -> resolve handle, classify URL
        5. --server-url (legacy)                      -> classify URL (deprecation warning)
        6. FPB_SERVER_URL env (legacy)                -> classify URL
        7. Single CLI-launched local PID              -> LOCAL_PROXY 127.0.0.1:<pid_port>
        8. http://127.0.0.1:5500 reachable            -> LOCAL_PROXY default
        9. --no-discovery                             -> LOCAL_PROXY default fallback
       10. mDNS browse:
             0 results  -> LOCAL_PROXY default
             1 result   -> classify (already normalized to 127.0.0.1 if same-host)
             2+ results -> stderr list + sys.exit(2)

    Local plans gain ``allow_launch`` and ``allow_direct_fallback`` only
    when ``--port`` is present (preserves the legacy "auto-launch failed
    -> direct serial" path while keeping it scoped).
    """
    policy = getattr(args, "command_policy", CommandPolicy.DEVICE)
    if policy in (CommandPolicy.OFFLINE, CommandPolicy.SERVER_ADMIN):
        return ConnectionPlan(mode=ConnectionMode.OFFLINE, source="offline-command")

    port = getattr(args, "port", None)
    baudrate = getattr(args, "baudrate", 115200)
    token = getattr(args, "token", None)
    verbose = getattr(args, "verbose", False)

    if getattr(args, "direct", False):
        if getattr(args, "server", None) or getattr(args, "server_url_legacy", None):
            raise FPBCLIError(
                "--direct cannot be combined with --server / --server-url; "
                "direct mode bypasses the WebServer."
            )
        if not port:
            raise FPBCLIError("--direct requires --port for device commands.")
        return ConnectionPlan(
            mode=ConnectionMode.DIRECT,
            serial_port=port,
            baudrate=baudrate,
            source="direct",
        )

    server_handle = getattr(args, "server", None)
    if server_handle:
        url = _resolve_handle_to_url(server_handle, source="-s flag")
        from fpbinject.cli.discover import classify_handle

        cache_key = (
            server_handle if classify_handle(server_handle) == "host_port" else None
        )
        plan = _classify_url(url, token=token, source="flag")
        plan = _attach_serial_port(plan, port, baudrate)
        return _with_cache_handle(plan, cache_key)

    env_handle = os.environ.get("FPB_SERVER")
    if env_handle:
        url = _resolve_handle_to_url(env_handle, source="FPB_SERVER env")
        from fpbinject.cli.discover import classify_handle

        cache_key = env_handle if classify_handle(env_handle) == "host_port" else None
        plan = _classify_url(url, token=token, source="env")
        plan = _attach_serial_port(plan, port, baudrate)
        return _with_cache_handle(plan, cache_key)

    legacy_url = getattr(args, "server_url_legacy", None)
    if legacy_url:
        if verbose:
            print(
                "warning: --server-url is deprecated; use -s / --server instead.",
                file=sys.stderr,
            )
        return _attach_serial_port(
            _classify_url(legacy_url, token=token, source="legacy-flag"), port, baudrate
        )

    legacy_env_url = os.environ.get("FPB_SERVER_URL")
    if legacy_env_url:
        if verbose:
            print(
                "warning: FPB_SERVER_URL is deprecated; use FPB_SERVER instead.",
                file=sys.stderr,
            )
        return _attach_serial_port(
            _classify_url(legacy_env_url, token=token, source="legacy-env"),
            port,
            baudrate,
        )

    pid_servers = list_cli_servers()
    if len(pid_servers) == 1:
        pid_port = pid_servers[0]["port"]
        url = f"http://127.0.0.1:{pid_port}"
        return _attach_serial_port(
            _classify_url(url, token=token, source="pid"), port, baudrate
        )

    if _localhost_status_ok(DEFAULT_PORT):
        return _attach_serial_port(
            _classify_url(DEFAULT_SERVER_URL, token=token, source="localhost-default"),
            port,
            baudrate,
        )

    if getattr(args, "no_discovery", False) or discover_sync is None:
        return _attach_serial_port(
            _classify_url(DEFAULT_SERVER_URL, token=token, source="localhost-fallback"),
            port,
            baudrate,
        )

    servers = discover_sync()
    if not servers:
        return _attach_serial_port(
            _classify_url(DEFAULT_SERVER_URL, token=token, source="localhost-fallback"),
            port,
            baudrate,
        )
    if len(servers) == 1:
        s = servers[0]
        if verbose:
            print(
                f"Using discovered server {s.url} (version={s.version})",
                file=sys.stderr,
            )
        return _attach_serial_port(
            _classify_url(s.url, token=token, source="mdns"), port, baudrate
        )

    lines = [
        "Multiple FPBInject servers discovered; pass -s <handle> to choose:",
    ]
    for s in servers:
        lines.append(
            f"  -s {s.handle}    version={s.version}  auth={s.auth}  device={s.device}"
        )
    raise AmbiguousServerError("\n".join(lines))


def resolve_server_url(args):
    """Resolve the WebServer URL the CLI should talk to.

    Precedence ladder (first hit wins):
        1. ``args.server_url`` (--server-url flag)
        2. ``FPB_SERVER_URL`` env var
        3. Non-server-needing subcommand
           (``command_policy in {OFFLINE, SERVER_ADMIN}``) -> None
        4. ``--no-discovery`` flag -> DEFAULT_SERVER_URL fallback
        5. mDNS browse: 0 -> fallback, 1 -> use, 2+ -> exit 2

    Exit codes:
        0 ok, 2 ambiguous (multi-result without --server-url).
    """
    if getattr(args, "server_url", None):
        return args.server_url
    env_url = os.environ.get("FPB_SERVER_URL")
    if env_url:
        return env_url
    policy = getattr(args, "command_policy", CommandPolicy.DEVICE)
    if policy in (CommandPolicy.OFFLINE, CommandPolicy.SERVER_ADMIN):
        return None
    if getattr(args, "no_discovery", False):
        return DEFAULT_SERVER_URL
    if discover_sync is None:
        return DEFAULT_SERVER_URL
    servers = discover_sync()
    if not servers:
        return DEFAULT_SERVER_URL
    if len(servers) == 1:
        s = servers[0]
        if getattr(args, "verbose", False):
            print(
                f"Using discovered server {s.url} (version={s.version})",
                file=sys.stderr,
            )
        return s.url
    print(
        "Multiple FPBInject servers discovered; pass -s <handle> to choose:",
        file=sys.stderr,
    )
    for s in servers:
        print(
            f"  -s {s.handle}    version={s.version}  auth={s.auth}  device={s.device}",
            file=sys.stderr,
        )
    sys.exit(2)


def cmd_discover(args):
    """``discover`` subcommand: human table by default, JSON with ``--json``."""
    if discover_sync is None:
        if getattr(args, "json", False):
            print("[]")
        else:
            print("(zeroconf not installed; cannot discover)", file=sys.stderr)
        return 1

    timeout = getattr(args, "timeout", 3.0)
    servers = discover_sync(timeout=timeout)

    if getattr(args, "json", False):
        payload = [
            {
                "name": s.name,
                "host": s.host,
                "port": s.port,
                "url": s.url,
                "version": s.version,
                "auth": s.auth,
                "device": s.device,
                "path": s.path,
                "id": s.id,
                "handle": s.handle,
            }
            for s in servers
        ]
        print(json.dumps(payload, indent=2))
        return 0

    if not servers:
        print("No FPBInject servers found.", file=sys.stderr)
        return 0

    rows = [("HANDLE", "URL", "AUTH", "DEVICE", "VERSION")]
    for s in servers:
        rows.append((s.handle, s.url, s.auth or "?", s.device or "?", s.version or "?"))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)))
    return 0


def main():
    # Program name as actually invoked: "fpbinject" for the installed console
    # script, "fpb_cli.py" when run from source. Keep the examples in sync.
    prog = os.path.basename(sys.argv[0]) or "fpbinject"
    epilog = f"""
Examples:
  # ELF analysis works offline — no device, no --port:
  {prog} analyze firmware.elf digitalWrite
  {prog} search firmware.elf gpio
  {prog} compile patch.c --elf firmware.elf --compile-commands build/compile_commands.json

  # Local device commands — first time, --port triggers auto-launch:
  {prog} --port /dev/ttyACM0 info
  {prog} --port /dev/ttyACM0 inject digitalWrite patch.c --elf firmware.elf

  # Once a local server has the device connected, --port is no longer needed:
  {prog} info
  {prog} file-stat /etc/init.d/rcS

  # Remote control — the device lives on the server, so no --port needed:
  {prog} --server-url http://192.168.1.20:5500 --token TOKEN info
  # Only pass --port to tell the remote server which port to open if it has none:
  {prog} --server-url http://192.168.1.20:5500 --token TOKEN --port /dev/ttyACM0 connect

Notes:
  The serial port belongs to the WebServer, not the CLI. In proxy mode (local
  or remote) --port is optional whenever the server already has a connected
  device; it is only required to open a port when no device is connected yet,
  or for direct/auto-launch on a fresh local environment.
  --token (or FPB_TOKEN env) is required for remote servers.
  Output is JSON on stdout; pipe to jq for filtering.
  Run '{prog} <command> --help' for command-specific options.
        """
    description = (
        "FPBInject CLI - Lightweight interface for binary patching.\n"
        "\n"
        "Before you start (mental model):\n"
        "  1. Analysis (analyze/search/disasm) is OFFLINE - no device, no --port.\n"
        "  2. The serial port belongs to the WebServer; once a device is\n"
        "     connected, device commands need NO --port (--baudrate defaults to\n"
        "     115200, rarely changed).\n"
        "  3. Serial transfers/reads are slow & windowed: progress on stderr,\n"
        "     small tail by default - a long-but-progressing op is NOT a hang.\n"
        "  4. Stuck on serial loss? run `%(prog)s doctor`.\n"
        "  5. Multi-step automation? use the Python SDK (see Docs/SDK.md).\n"
    ) % {"prog": prog}
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )

    # Global options
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stderr transfer notices/progress (stdout JSON only).",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {FPB_VERSION}"
    )
    # Serial/connection and transfer flags (--port, --baudrate, --data-bits,
    # --serial-tx-fragment-size, ...) are generated from the shared config
    # schema so the CLI and the server expose the same options and names.
    from fpbinject.core.arg_schema import add_connection_args

    add_connection_args(parser)
    parser.add_argument("--elf", help="Path to ELF file")
    parser.add_argument("--compile-commands", help="Path to compile_commands.json")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Force direct serial connection (skip WebServer proxy detection).",
    )
    parser.add_argument(
        "-s",
        "--server",
        type=str,
        default=None,
        help="Server to talk to. Accepts a discovery handle (e.g. "
        "'bench:5501'), a hostname when unique on the LAN, or a full URL. "
        "Falls back to FPB_SERVER env var, then auto-discovery.",
    )
    parser.add_argument(
        "--server-url",
        dest="server_url_legacy",
        type=str,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-discovery",
        action="store_true",
        help=f"Disable mDNS auto-discovery and fall back to {DEFAULT_SERVER_URL}.",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("FPB_TOKEN"),
        help="Auth token for the WebServer. Required when the server returns "
        "401/403. Can also be set via the FPB_TOKEN environment variable.",
    )

    parser.set_defaults(command_policy=CommandPolicy.DEVICE)
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze function")
    analyze_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    analyze_parser.add_argument("elf_path", help="Path to ELF file")
    analyze_parser.add_argument("func_name", help="Function name to analyze")

    # disasm command
    disasm_parser = subparsers.add_parser("disasm", help="Get disassembly")
    disasm_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    disasm_parser.add_argument("elf_path", help="Path to ELF file")
    disasm_parser.add_argument("func_name", help="Function name")

    # decompile command
    decomp_parser = subparsers.add_parser("decompile", help="Decompile function")
    decomp_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    decomp_parser.add_argument("elf_path", help="Path to ELF file")
    decomp_parser.add_argument("func_name", help="Function name")

    # signature command
    sig_parser = subparsers.add_parser("signature", help="Get function signature")
    sig_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    sig_parser.add_argument("elf_path", help="Path to ELF file")
    sig_parser.add_argument("func_name", help="Function name")

    # search command
    search_parser = subparsers.add_parser("search", help="Search functions")
    search_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    search_parser.add_argument("elf_path", help="Path to ELF file")
    search_parser.add_argument("pattern", help="Search pattern")

    # get-symbols command
    symbols_parser = subparsers.add_parser(
        "get-symbols", help="Get all symbols from ELF file (via nm)"
    )
    symbols_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    symbols_parser.add_argument("elf_path", help="Path to ELF file")
    symbols_parser.add_argument(
        "--filter", default="", help="Filter pattern (case-insensitive)"
    )
    symbols_parser.add_argument(
        "--limit", type=int, default=0, help="Max results (0=unlimited)"
    )

    # compile command
    compile_parser = subparsers.add_parser("compile", help="Compile patch source")
    compile_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    compile_parser.add_argument("source_file", help="Source C file")
    compile_parser.add_argument(
        "--addr",
        type=lambda x: int(x, 0),
        default=0x20001000,
        help="Base address (default: 0x20001000)",
    )

    # info command (requires device)
    subparsers.add_parser("info", help="Get device FPB info (requires device)")

    # test-serial command (requires device)
    test_serial_parser = subparsers.add_parser(
        "test-serial",
        help="Test serial throughput to find max transfer size (requires device)",
    )
    test_serial_parser.add_argument(
        "--start-size",
        type=int,
        default=16,
        help="Starting test size in bytes (default: 16)",
    )
    test_serial_parser.add_argument(
        "--max-size",
        type=int,
        default=4096,
        help="Maximum test size in bytes (default: 4096)",
    )
    test_serial_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Timeout per test in seconds (default: 2.0)",
    )
    test_serial_parser.add_argument(
        "--trials",
        type=int,
        default=8,
        help="Round-trips sampled per size for reliability (default: 8)",
    )
    test_serial_parser.add_argument(
        "--min-success-rate",
        type=float,
        default=1.0,
        help="Success fraction required to accept a size (default: 1.0)",
    )

    # doctor command (requires device) — diagnose serial loss + suggest tuning
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnose serial reliability and print copy-paste tuning flags "
        "(requires device)",
    )
    doctor_parser.add_argument(
        "--start-size", type=int, default=16, help="Starting probe size (default: 16)"
    )
    doctor_parser.add_argument(
        "--max-size", type=int, default=512, help="Maximum probe size (default: 512)"
    )
    doctor_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Timeout per probe in seconds (default: 2.0)",
    )
    doctor_parser.add_argument(
        "--trials",
        type=int,
        default=8,
        help="Round-trips sampled per size (default: 8)",
    )

    # inject command (requires device)
    inject_parser = subparsers.add_parser(
        "inject", help="Inject patch to device (requires device)"
    )
    inject_parser.add_argument("target_func", help="Target function name to replace")
    inject_parser.add_argument("source_file", help="Source C file")
    inject_parser.add_argument(
        "--mode",
        choices=["trampoline", "debugmon", "direct"],
        default="trampoline",
        help="Patch mode (default: trampoline)",
    )
    inject_parser.add_argument(
        "--comp", type=int, default=-1, help="FPB comparator slot (-1 for auto)"
    )
    inject_parser.add_argument(
        "--verify", action="store_true", help="Verify patch after injection"
    )

    # unpatch command (requires device)
    unpatch_parser = subparsers.add_parser(
        "unpatch", help="Remove patch (requires device)"
    )
    unpatch_parser.add_argument(
        "--comp", type=int, default=0, help="FPB comparator slot to unpatch"
    )
    unpatch_parser.add_argument("--all", action="store_true", help="Remove all patches")

    # mem-read command (requires device)
    memread_parser = subparsers.add_parser(
        "mem-read", help="Read memory from device (requires device)"
    )
    memread_parser.add_argument(
        "addr", type=lambda x: int(x, 0), help="Memory address (hex: 0x20000000)"
    )
    memread_parser.add_argument(
        "length", type=lambda x: int(x, 0), help="Number of bytes to read"
    )
    memread_parser.add_argument(
        "--fmt",
        choices=["hex", "raw", "u32"],
        default="hex",
        help="Output format: hex (dump), raw (hex string), u32 (32-bit words)",
    )

    # mem-write command (requires device)
    memwrite_parser = subparsers.add_parser(
        "mem-write", help="Write memory to device (requires device)"
    )
    memwrite_parser.add_argument(
        "addr", type=lambda x: int(x, 0), help="Memory address (hex: 0x20000000)"
    )
    memwrite_parser.add_argument(
        "data", help="Hex data to write (e.g., DEADBEEF01020304)"
    )

    # mem-dump command (requires device)
    memdump_parser = subparsers.add_parser(
        "mem-dump", help="Dump memory region to file (requires device)"
    )
    memdump_parser.add_argument(
        "addr", type=lambda x: int(x, 0), help="Start address (hex: 0x20000000)"
    )
    memdump_parser.add_argument(
        "length", type=lambda x: int(x, 0), help="Number of bytes to dump"
    )
    memdump_parser.add_argument("output", help="Output binary file path")

    # serial-send command (requires device)
    serial_send_parser = subparsers.add_parser(
        "serial-send", help="Send data to device serial port (requires device)"
    )
    serial_send_parser.add_argument("data", help="String to send to device")
    serial_send_parser.add_argument(
        "--no-read",
        action="store_true",
        help="Don't read response after sending",
    )
    serial_send_parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Response read timeout in seconds (default: 1.0)",
    )

    # serial-read command (requires device)
    serial_read_parser = subparsers.add_parser(
        "serial-read", help="Read recent serial output (requires device)"
    )
    serial_read_parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="How long to wait for data in seconds (default: 1.0)",
    )
    serial_read_parser.add_argument(
        "--lines",
        type=int,
        default=50,
        help="Max number of log lines to return (default: 50)",
    )
    serial_read_parser.add_argument(
        "--since",
        type=int,
        default=0,
        help="Cursor from a previous 'next' for incremental paging (default: 0). "
        "Walks the backlog without loss.",
    )
    serial_read_parser.add_argument(
        "--max-bytes",
        dest="max_bytes",
        type=int,
        default=4096,
        help="Hard cap on returned data bytes (default: 4096). Keeps a large "
        "backlog from blowing up your context.",
    )
    serial_read_parser.add_argument(
        "--tail",
        type=int,
        default=0,
        help="Return only the newest N bytes (adb logcat -t style); ignores --since.",
    )
    serial_read_parser.add_argument(
        "--drop",
        action="store_true",
        help="Skip the buffered backlog and just advance the cursor "
        "(adb logcat -c style); returns the new 'next'.",
    )

    # file-list command (requires device)
    file_list_parser = subparsers.add_parser(
        "file-list", help="List directory contents on device (requires device)"
    )
    file_list_parser.add_argument(
        "path", nargs="?", default="/", help="Directory path on device (default: /)"
    )

    # file-stat command (requires device)
    file_stat_parser = subparsers.add_parser(
        "file-stat", help="Get file/directory info on device (requires device)"
    )
    file_stat_parser.add_argument("path", help="File or directory path on device")

    # file-download command (requires device)
    file_download_parser = subparsers.add_parser(
        "file-download", help="Download file from device (requires device)"
    )
    file_download_parser.add_argument(
        "remote_path", help="Source file path on device (e.g., /data/log.bin)"
    )
    file_download_parser.add_argument(
        "local_path", help="Destination path on local machine (e.g., /tmp/log.bin)"
    )

    # file-upload command (requires device)
    file_upload_parser = subparsers.add_parser(
        "file-upload", help="Upload local file to device (requires device)"
    )
    file_upload_parser.add_argument(
        "local_path", help="Source file path on local machine"
    )
    file_upload_parser.add_argument(
        "remote_path", help="Destination path on device (e.g., /data/log.bin)"
    )

    # file-remove command (requires device)
    file_remove_parser = subparsers.add_parser(
        "file-remove", help="Remove file on device (requires device)"
    )
    file_remove_parser.add_argument("path", help="File path to remove on device")

    # file-mkdir command (requires device)
    file_mkdir_parser = subparsers.add_parser(
        "file-mkdir", help="Create directory on device (requires device)"
    )
    file_mkdir_parser.add_argument("path", help="Directory path to create on device")

    # file-rename command (requires device)
    file_rename_parser = subparsers.add_parser(
        "file-rename", help="Rename file or directory on device (requires device)"
    )
    file_rename_parser.add_argument("old_path", help="Current path on device")
    file_rename_parser.add_argument("new_path", help="New path on device")

    # connect command
    subparsers.add_parser("connect", help="Connect to device (requires device)")

    # disconnect command
    disconnect_parser = subparsers.add_parser(
        "disconnect", help="Disconnect from device"
    )
    disconnect_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)

    # vserial-start command — create virtual serial passthrough (proxy mode only)
    vserial_start_parser = subparsers.add_parser(
        "vserial-start",
        help="Create virtual serial passthrough on the server (requires server)",
    )
    vserial_start_parser.add_argument(
        "--symlink",
        default=None,
        help="Stable symlink path for the virtual serial device. Omit to use "
        "the server config (default 'auto': derived from the port name, "
        "e.g. /dev/ttyACM0 -> /tmp/fpb-ttyACM0). Pass a path to override.",
    )

    # vserial-stop command — remove virtual serial passthrough
    subparsers.add_parser(
        "vserial-stop",
        help="Remove virtual serial passthrough on the server (requires server)",
    )

    # vserial-status command — query virtual serial passthrough
    subparsers.add_parser(
        "vserial-status",
        help="Query virtual serial passthrough status (requires server)",
    )

    # discover command — list FPBInject WebServers visible via mDNS
    discover_parser = subparsers.add_parser(
        "discover", help="List FPBInject WebServers visible via mDNS"
    )
    discover_parser.set_defaults(command_policy=CommandPolicy.OFFLINE)
    discover_parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Discovery timeout in seconds (default: 3.0).",
    )
    discover_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the default human table.",
    )

    # server-stop command
    server_stop_parser = subparsers.add_parser(
        "server-stop", help="Stop a CLI-launched WebServer background process"
    )
    server_stop_parser.set_defaults(command_policy=CommandPolicy.SERVER_ADMIN)
    server_stop_parser.add_argument(
        "--server-port",
        type=int,
        default=0,
        help="Port of the CLI server to stop (default: auto-detect or 5500)",
    )

    args = parser.parse_args()

    if not args.command:
        # Banner + help only on the no-command path so real command output
        # (JSON on stdout) is never contaminated.
        from fpbinject.banner import print_banner

        print_banner("CLI")
        parser.print_help()
        sys.exit(1)

    if args.command == "discover":
        sys.exit(cmd_discover(args))

    elf_path = args.elf
    if hasattr(args, "elf_path") and args.elf_path:
        elf_path = args.elf_path

    # CLI has no config layer: turn unset schema flags into concrete defaults.
    from fpbinject.core.arg_schema import fill_missing_defaults

    fill_missing_defaults(args)

    try:
        plan = resolve_connection_plan(args)
        cli = FPBCLI(
            verbose=args.verbose,
            port=args.port,
            baudrate=args.baudrate,
            elf_path=elf_path,
            compile_commands=args.compile_commands,
            tx_chunk_size=args.serial_tx_fragment_size,
            tx_chunk_delay=args.serial_tx_fragment_delay,
            max_retries=args.transfer_max_retries,
            direct=args.direct,
            server_url=plan.server_url,
            token=args.token,
            plan=plan,
        )
    except FPBCLIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(e.exit_code)
    args.server_url = plan.server_url
    cli._quiet = getattr(args, "quiet", False)

    try:
        if args.command == "analyze":
            cli.analyze(args.elf_path, args.func_name)
        elif args.command == "disasm":
            cli.disasm(args.elf_path, args.func_name)
        elif args.command == "decompile":
            cli.decompile(args.elf_path, args.func_name)
        elif args.command == "signature":
            cli.signature(args.elf_path, args.func_name)
        elif args.command == "search":
            cli.search(args.elf_path, args.pattern)
        elif args.command == "get-symbols":
            cli.get_symbols(args.elf_path, args.filter, args.limit)
        elif args.command == "compile":
            # Use global --elf and --compile-commands
            cli.compile(args.source_file, elf_path, args.addr, args.compile_commands)
        elif args.command == "info":
            cli.info()
        elif args.command == "test-serial":
            cli.test_serial(
                args.start_size,
                args.max_size,
                args.timeout,
                args.trials,
                args.min_success_rate,
            )
        elif args.command == "inject":
            cli.inject(
                args.target_func,
                args.source_file,
                elf_path,
                args.compile_commands,
                args.mode,
                args.comp,
                args.verify,
            )
        elif args.command == "unpatch":
            cli.unpatch(args.comp, args.all)
        elif args.command == "mem-read":
            cli.mem_read(args.addr, args.length, args.fmt)
        elif args.command == "mem-write":
            cli.mem_write(args.addr, args.data)
        elif args.command == "mem-dump":
            cli.mem_dump(args.addr, args.length, args.output)
        elif args.command == "serial-send":
            cli.serial_send(args.data, not args.no_read, args.timeout)
        elif args.command == "serial-read":
            cli.serial_read(
                args.timeout,
                args.lines,
                args.since,
                args.max_bytes,
                args.tail,
                args.drop,
            )
        elif args.command == "doctor":
            cli.doctor(args.start_size, args.max_size, args.timeout, args.trials)
        elif args.command == "file-list":
            cli.file_list(args.path)
        elif args.command == "file-stat":
            cli.file_stat(args.path)
        elif args.command == "file-download":
            cli.file_download(args.remote_path, args.local_path)
        elif args.command == "file-upload":
            cli.file_upload(args.local_path, args.remote_path)
        elif args.command == "file-remove":
            cli.file_remove(args.path)
        elif args.command == "file-mkdir":
            cli.file_mkdir(args.path)
        elif args.command == "file-rename":
            cli.file_rename(args.old_path, args.new_path)
        elif args.command == "connect":
            cli.connect(args.port, args.baudrate)
        elif args.command == "disconnect":
            cli.disconnect()
        elif args.command == "vserial-start":
            cli.vserial_start(args.symlink)
        elif args.command == "vserial-stop":
            cli.vserial_stop()
        elif args.command == "vserial-status":
            cli.vserial_status()
        elif args.command == "server-stop":
            port = args.server_port if args.server_port else DEFAULT_PORT
            cli.server_stop(port)
    except FPBCLIError as e:
        cli.output_error(str(e))
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        cli.output_error(f"Unexpected error: {str(e)}", e)
        sys.exit(1)
    finally:
        cli.cleanup()


if __name__ == "__main__":
    main()

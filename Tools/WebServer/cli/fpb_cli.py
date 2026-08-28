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

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Import from existing WebServer modules
sys.path.insert(0, str(Path(__file__).parent))
from fpbinject.fpb_inject import FPBInject  # noqa: E402
from fpbinject.core.state import DeviceStateBase  # noqa: E402
from fpbinject.utils.port_lock import PortLock  # noqa: E402
from fpbinject.cli.server_proxy import (  # noqa: E402
    ServerProxy,
    ProxyAuthError,
    DEFAULT_SERVER_URL,
    DEFAULT_PORT,
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
    ConnectionMode,
    ConnectionPlan,
)

try:
    import serial

    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


# Error types + connection/discovery helpers were extracted to keep this
# module under the file-size limit. Re-export so existing imports
# (from fpbinject.cli.fpb_cli import ...) keep working.
from fpbinject.cli.errors import FPBCLIError, AmbiguousServerError  # noqa: E402,F401
from fpbinject.cli.connection_resolver import (  # noqa: E402,F401
    _is_local_url,
    _localhost_status_ok,
    _classify_url,
    _attach_serial_port,
    _with_cache_handle,
    _resolve_handle_to_url,
    _refresh_handle_cache,
    invalidate_cached_handle,
    resolve_connection_plan,
    resolve_server_url,
    cmd_discover,
)

# Argparse construction lives in cli.arg_parser (extracted for file size).
from fpbinject.cli.arg_parser import build_parser  # noqa: E402,F401
from fpbinject.cli.commands_file_mem import FileMemCommandsMixin  # noqa: E402


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


class FPBCLI(FileMemCommandsMixin):
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
        grep: Optional[str] = None,
    ) -> None:
        """Read serial output, context-safe (adb-logcat style).

        Bounded by ``max_bytes`` so a large backlog never blows up the
        consumer's context. Defaults to a tail read; page the rest with
        ``--since <next>`` or skip it with ``--drop``. Pass ``grep`` for
        a server-side regex filter (proxy mode only — direct mode falls
        back to a local ``re.search`` over the freshly-read tail).
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
                    grep=grep,
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
            # Direct mode has no server-side ring; apply grep locally over
            # the freshly-read tail so the CLI flag behaves the same either
            # way. Invalid regex surfaces as a structured error.
            if grep:
                import re as _re

                try:
                    pat = _re.compile(grep)
                except _re.error as re_err:
                    self.output_json(
                        {
                            "success": False,
                            "invalid_grep": True,
                            "error": f"invalid grep pattern: {re_err}",
                        }
                    )
                    return
                log_lines = [ln for ln in log_lines if pat.search(ln)]
                new_data = "\n".join(log_lines)
                data_bytes = new_data.encode("utf-8")
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
        the caller knows how to page or skip the remaining backlog. Passes
        through ``invalid_grep`` / ``error`` if the server rejected the
        regex, so callers can branch on ``success`` without re-parsing text.
        """
        data = win.get("data", "")
        pending = win.get("pending_bytes", 0)
        # Server flips success to false on invalid grep; propagate faithfully.
        out = {
            "success": win.get("success", True),
            "data": data,
            "next": win.get("next", 0),
            "returned_bytes": win.get("returned_bytes", len(data.encode("utf-8"))),
            "pending_bytes": pending,
            "pending_entries": win.get("pending_entries", 0),
            "truncated": win.get("truncated", False),
            "buffer_overflowed": win.get("buffer_overflowed", False),
        }
        if win.get("invalid_grep"):
            out["invalid_grep"] = True
            out["error"] = win.get("error", "invalid grep pattern")
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

    def _transfer_notice(self, verb: str, name: str, size: int) -> None:
        """Print a one-line predictive notice to stderr before a transfer.

        Serial transfers are slow; without this an AI sees a long silence and
        assumes the tool hung. Progress (below) and the final JSON confirm
        liveness. Actual speed depends on the baudrate, link quality and
        tuning, so we do NOT hard-code a ~KB/s figure here; the live
        progress line reports the measured speed/ETA once bytes flow.
        Suppressed when --quiet.
        """
        if getattr(self, "_quiet", False):
            return
        size_str = f"{size} bytes" if size else "unknown size"
        print(
            f"[transfer] {verb} {name} ({size_str}); speed depends on "
            "serial link, live progress on stderr, JSON on stdout when done",
            file=sys.stderr,
            flush=True,
        )

    @staticmethod
    def _fmt_speed(bps: float) -> str:
        if bps <= 0:
            return "  ?   "
        if bps >= 1_000_000:
            return f"{bps / 1_000_000:5.2f}MB/s"
        if bps >= 1_000:
            return f"{bps / 1_000:5.1f}KB/s"
        return f"{bps:5.0f} B/s"

    @staticmethod
    def _fmt_eta(seconds: float) -> str:
        if seconds < 0 or seconds != seconds:  # NaN/negative
            return "  ?  "
        if seconds >= 3600:
            return f"{seconds / 3600:4.1f}h"
        if seconds >= 60:
            return f"{seconds / 60:4.1f}m"
        return f"{seconds:4.0f}s"

    def _make_progress_printer(self):
        """Return a progress_cb that renders a live progress line on stderr.

        Speed and ETA come from real byte deltas (EWMA), no hard-coded
        baudrate assumption. Behaviour depends on whether stderr is a TTY:

        - TTY: rewrites the same line in place at ~5 Hz using ``\\r`` plus the
          ANSI erase-to-end-of-line sequence, so a shorter follow-up never
          leaves stale characters. A final newline closes the line at 100%.
        - Non-TTY (pipes, log files, CI): ``\\r`` has no effect, so we throttle
          hard (~1 line every 2 s + a final 100% tick) and end each line with
          a newline, so downstream tools see one line per update instead of a
          rapidly-appended 5 Hz stream.

        Suppressed entirely when --quiet.
        """
        if getattr(self, "_quiet", False):
            return None
        import time as _time

        state = {
            "printed": 0.0,  # last print wall-time
            "sample_t": 0.0,  # last sample wall-time
            "sample_bytes": 0,  # bytes seen at last sample
            "start_t": 0.0,  # first callback wall-time
            "ewma_bps": 0.0,  # exponential-moving-average speed
            "final_done": False,  # emitted the final line yet?
        }

        def cb(done: int, total: int) -> None:
            # Read the current stderr each call so tests that redirect stderr
            # after building the callback (or that swap it during a run) see
            # the right TTY behaviour.
            stream = sys.stderr
            is_tty = bool(getattr(stream, "isatty", lambda: False)())
            # 5 Hz for TTY overwrites, ~0.5 Hz for pipes so logs don't balloon.
            min_interval = 0.2 if is_tty else 2.0

            now = _time.time()
            if state["start_t"] == 0.0:
                state["start_t"] = now
                state["sample_t"] = now
                state["sample_bytes"] = done

            # Refresh EWMA on every callback so speed follows real rate.
            dt = now - state["sample_t"]
            if dt >= 0.05:
                inst = (done - state["sample_bytes"]) / dt if dt > 0 else 0.0
                if state["ewma_bps"] <= 0:
                    state["ewma_bps"] = inst
                else:
                    # Alpha 0.3: responsive without being twitchy.
                    state["ewma_bps"] = 0.7 * state["ewma_bps"] + 0.3 * inst
                state["sample_t"] = now
                state["sample_bytes"] = done

            final = bool(total) and done >= total
            if final and state["final_done"]:
                return  # suppress duplicate 100% ticks
            if not final and now - state["printed"] < min_interval:
                return
            state["printed"] = now

            pct = f"{(done / total * 100):5.1f}%" if total else "  ?  "
            if final:
                elapsed = max(now - state["start_t"], 1e-3)
                avg = done / elapsed
                speed_str = self._fmt_speed(avg)
                eta_str = " done"
            else:
                speed_str = self._fmt_speed(state["ewma_bps"])
                remaining = (total - done) if total else 0
                eta = remaining / state["ewma_bps"] if state["ewma_bps"] > 0 else -1
                eta_str = "ETA " + self._fmt_eta(eta) if eta >= 0 else "ETA   ?  "

            line = f"[transfer] {pct}  {done}/{total} B  {speed_str}  {eta_str}"
            if is_tty:
                # \r + ESC[K: return to column 0 and clear to end-of-line so
                # shorter follow-ups don't leave leftover characters.
                print(f"\r{line}\x1b[K", end="", file=stream, flush=True)
                if final:
                    print("", file=stream, flush=True)
                    state["final_done"] = True
            else:
                # Non-TTY: single line per update, terminated normally.
                print(line, file=stream, flush=True)
                if final:
                    state["final_done"] = True

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
        # Local re-import so tests can patch server_proxy.list_cli_servers
        # after the module is loaded; keep list_cli_servers late-bound.
        from fpbinject.cli.server_proxy import (
            stop_cli_server,
            list_cli_servers,
        )

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


def main():
    # Program name as actually invoked: "fpbinject" for the installed console
    # script, "fpb_cli.py" when run from source. Keep the examples in sync.
    prog = os.path.basename(sys.argv[0]) or "fpbinject"
    parser = build_parser(prog)
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
                grep=getattr(args, "grep", None),
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

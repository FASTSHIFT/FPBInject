#!/usr/bin/env python3
"""
FPBInject CLI - Lightweight command-line interface for AI integration

Usage:
  fpb_cli.py analyze <elf_path> <func_name>
  fpb_cli.py disasm <elf_path> <func_name>
  fpb_cli.py decompile <elf_path> <func_name>
  fpb_cli.py signature <elf_path> <func_name>
  fpb_cli.py search <elf_path> <pattern>
  fpb_cli.py compile <source_file> [--output <out>]
  fpb_cli.py inject <elf_path> <comp_num> <source_file> [--verify]
  fpb_cli.py unpatch <elf_path> <comp_num>
  fpb_cli.py --version
  fpb_cli.py --help

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
from fpb_inject import FPBInject  # noqa: E402
from core.state import DeviceStateBase  # noqa: E402
from utils.port_lock import PortLock  # noqa: E402
from cli.server_proxy import ServerProxy, DEFAULT_SERVER_URL, DEFAULT_PORT  # noqa: E402

try:
    import serial

    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


class FPBCLIError(Exception):
    """CLI specific errors"""

    pass


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

    By default operates in pure-proxy mode: all device operations are
    forwarded to the WebServer via HTTP API.  If the WebServer is not
    running it is auto-launched as a background subprocess.

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
        server_url: str = DEFAULT_SERVER_URL,
    ):
        self.verbose = verbose
        self.setup_logging()
        # Create device state (used for offline ELF operations & direct mode)
        self._device_state = DeviceState()
        self._device_state.elf_path = elf_path
        self._device_state.compile_commands_path = compile_commands
        self._device_state.serial_tx_fragment_size = tx_chunk_size
        self._device_state.serial_tx_fragment_delay = tx_chunk_delay
        self._device_state.transfer_max_retries = max_retries
        self._fpb = FPBInject(self._device_state)

        # Proxy and lock state
        self._proxy = None
        self._port_lock = None

        if direct and port:
            # --direct: bypass proxy, open serial directly
            self._direct_connect(port, baudrate)
            return

        if port:
            # Default: pure-proxy mode
            proxy = ServerProxy(base_url=server_url)

            # 1) If server already running, use it
            if proxy.is_server_running():
                self._proxy = proxy
                self._device_state.connected = proxy.is_device_connected()
                # If server is up but device not connected, connect via proxy
                if not self._device_state.connected:
                    result = proxy.connect(port, baudrate)
                    self._device_state.connected = result.get("success", False)
                if self.verbose:
                    logging.info(f"Using WebServer proxy mode ({server_url})")
                return

            # 2) Server not running — auto-launch it
            if self.verbose:
                logging.info("WebServer not running, auto-launching...")
            if proxy.launch_server():
                self._proxy = proxy
                # Server just started, connect device via proxy
                result = proxy.connect(port, baudrate)
                self._device_state.connected = result.get("success", False)
                if self.verbose:
                    logging.info(
                        f"WebServer launched, proxy mode active ({server_url})"
                    )
                return

            # 3) Auto-launch failed — fall back to direct mode
            if self.verbose:
                logging.warning("Auto-launch failed, falling back to direct mode")
            self._direct_connect(port, baudrate)

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

    def output_error(self, message: str, error: Optional[Exception] = None) -> None:
        """Output error as JSON"""
        error_data = {"success": False, "error": message}
        if error and self.verbose:
            error_data["exception"] = str(error)
        self.output_json(error_data)

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
                    raise FPBCLIError(
                        "No device connected and no ELF path provided.\n"
                        "Use: fpb_cli.py inject <target_func> <source.c> --elf <elf_path> --compile-commands <path>\n"
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
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> None:
        """Test serial throughput to find max single-transfer size."""
        try:
            if self._proxy:
                self.output_json(self._proxy.test_serial(start_size, max_size, timeout))
                return

            self._require_device()
            self.output_json(
                self._fpb.test_serial_throughput(
                    start_size=start_size, max_size=max_size, timeout=timeout
                )
            )
        except Exception as e:
            self.output_error(f"Serial test failed: {str(e)}", e)

    def file_list(self, path: str = "/") -> None:
        """List directory contents on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_list(path))
                return

            self._require_device()
            from core.file_transfer import FileTransfer

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
            from core.file_transfer import FileTransfer

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
                result = self._proxy.file_download(remote_path)
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
            from core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
                max_retries=self._device_state.transfer_max_retries,
            )
            success, data, msg = ft.download(remote_path)
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
            self.output_error(f"file_download failed: {str(e)}", e)

    def file_upload(self, local_path: str, remote_path: str) -> None:
        """Upload a local file to device"""
        try:
            if self._proxy:
                result = self._proxy.file_upload(local_path, remote_path)
                self.output_json(result)
                return

            self._require_device()
            with open(local_path, "rb") as f:
                data = f.read()

            from core.file_transfer import FileTransfer

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
                max_retries=self._device_state.transfer_max_retries,
            )
            success, msg = ft.upload(data, remote_path)
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
            self.output_error(f"file_upload failed: {str(e)}", e)

    def file_remove(self, path: str) -> None:
        """Remove a file on device"""
        try:
            if self._proxy:
                self.output_json(self._proxy.file_remove(path))
                return

            self._require_device()
            from core.file_transfer import FileTransfer

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
            from core.file_transfer import FileTransfer

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
            from core.file_transfer import FileTransfer

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
        self, timeout: float = 1.0, lines: int = 50, since: int = 0
    ) -> None:
        """Read recent serial output from device."""
        try:
            if self._proxy:
                log_resp = self._proxy.serial_read(raw_since=since)
                raw = log_resp.get("raw_data", "")
                raw_next = log_resp.get("raw_next", 0)
                log_lines = [ln for ln in raw.split("\n") if ln.strip()][-lines:]
                self.output_json(
                    {
                        "success": True,
                        "log": log_lines,
                        "log_count": len(log_lines),
                        "raw_data": raw,
                        "raw_next": raw_next,
                    }
                )
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

            log_lines = [ln for ln in new_data.split("\n") if ln.strip()][-lines:]
            self.output_json(
                {
                    "success": True,
                    "new_data": new_data,
                    "log": log_lines,
                    "log_count": len(log_lines),
                }
            )
        except Exception as e:
            self.output_error(f"Serial read failed: {str(e)}", e)

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

    def cleanup(self):
        """Cleanup resources"""
        self._device_state.disconnect()
        if self._port_lock:
            self._port_lock.release()
            self._port_lock = None

    def server_stop(self, port: int = DEFAULT_PORT) -> None:
        """Stop a CLI-launched WebServer on the given port."""
        from cli.server_proxy import stop_cli_server, list_cli_servers

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
    parser = argparse.ArgumentParser(
        description="FPBInject CLI - Lightweight interface for binary patching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a function (no device needed)
  fpb_cli.py analyze firmware.elf digitalWrite

  # Get disassembly (no device needed)
  fpb_cli.py disasm firmware.elf digitalRead | jq .disasm

  # Search functions (no device needed)
  fpb_cli.py search firmware.elf "gpio"

  # Get all symbols (no device needed)
  fpb_cli.py get-symbols firmware.elf --filter "gpio" --limit 50

  # Compile patch (no device needed)
  fpb_cli.py compile my_patch.c --elf firmware.elf --compile-commands build/compile_commands.json

  # Get device info (requires device)
  fpb_cli.py --port /dev/ttyACM0 info

  # Inject patch (requires device)
  fpb_cli.py --port /dev/ttyACM0 --elf firmware.elf --compile-commands build/compile_commands.json \\
      inject digitalWrite patch.c

  # Remove patch (requires device)
  fpb_cli.py --port /dev/ttyACM0 unpatch --comp 0

  # Remove all patches (requires device)
  fpb_cli.py --port /dev/ttyACM0 unpatch --all

  # List files on device (requires device)
  fpb_cli.py --port /dev/ttyACM0 file-list /data

  # Get file info on device (requires device)
  fpb_cli.py --port /dev/ttyACM0 file-stat /data/log.bin

  # Download file from device (requires device)
  fpb_cli.py --port /dev/ttyACM0 file-download /data/log.bin ./log.bin

  # Upload file to device (requires device)
  fpb_cli.py --port /dev/ttyACM0 file-upload ./firmware.bin /data/firmware.bin

  # Remove file on device (requires device)
  fpb_cli.py --port /dev/ttyACM0 file-remove /data/old.bin

  # Create directory on device (requires device)
  fpb_cli.py --port /dev/ttyACM0 file-mkdir /data/logs

  # Rename file on device (requires device)
  fpb_cli.py --port /dev/ttyACM0 file-rename /data/old.bin /data/new.bin
        """,
    )

    # Global options
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")
    parser.add_argument("--port", "-p", help="Serial port (e.g., /dev/ttyACM0, COM3)")
    parser.add_argument(
        "--baudrate",
        "-b",
        type=int,
        default=115200,
        help="Serial baudrate (default: 115200)",
    )
    parser.add_argument("--elf", help="Path to ELF file")
    parser.add_argument("--compile-commands", help="Path to compile_commands.json")
    parser.add_argument(
        "--tx-chunk-size",
        type=int,
        default=0,
        help="TX chunk size for serial commands (0=disabled). Workaround for slow serial drivers.",
    )
    parser.add_argument(
        "--tx-chunk-delay",
        type=float,
        default=0.005,
        help="Delay between TX chunks in seconds (default: 0.005). Only used when --tx-chunk-size > 0.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=10,
        help="Maximum retry attempts for file transfer operations (default: 10).",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Force direct serial connection (skip WebServer proxy detection).",
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default=DEFAULT_SERVER_URL,
        help=f"WebServer URL for proxy mode (default: {DEFAULT_SERVER_URL}).",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze function")
    analyze_parser.add_argument("elf_path", help="Path to ELF file")
    analyze_parser.add_argument("func_name", help="Function name to analyze")

    # disasm command
    disasm_parser = subparsers.add_parser("disasm", help="Get disassembly")
    disasm_parser.add_argument("elf_path", help="Path to ELF file")
    disasm_parser.add_argument("func_name", help="Function name")

    # decompile command
    decomp_parser = subparsers.add_parser("decompile", help="Decompile function")
    decomp_parser.add_argument("elf_path", help="Path to ELF file")
    decomp_parser.add_argument("func_name", help="Function name")

    # signature command
    sig_parser = subparsers.add_parser("signature", help="Get function signature")
    sig_parser.add_argument("elf_path", help="Path to ELF file")
    sig_parser.add_argument("func_name", help="Function name")

    # search command
    search_parser = subparsers.add_parser("search", help="Search functions")
    search_parser.add_argument("elf_path", help="Path to ELF file")
    search_parser.add_argument("pattern", help="Search pattern")

    # get-symbols command
    symbols_parser = subparsers.add_parser(
        "get-symbols", help="Get all symbols from ELF file (via nm)"
    )
    symbols_parser.add_argument("elf_path", help="Path to ELF file")
    symbols_parser.add_argument(
        "--filter", default="", help="Filter pattern (case-insensitive)"
    )
    symbols_parser.add_argument(
        "--limit", type=int, default=0, help="Max results (0=unlimited)"
    )

    # compile command
    compile_parser = subparsers.add_parser("compile", help="Compile patch source")
    compile_parser.add_argument("source_file", help="Source C file")
    compile_parser.add_argument(
        "--addr",
        type=lambda x: int(x, 0),
        default=0x20001000,
        help="Base address (default: 0x20001000)",
    )

    # info command (requires device)
    subparsers.add_parser("info", help="Get device FPB info (requires --port)")

    # test-serial command (requires device)
    test_serial_parser = subparsers.add_parser(
        "test-serial",
        help="Test serial throughput to find max transfer size (requires --port)",
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

    # inject command (requires device)
    inject_parser = subparsers.add_parser(
        "inject", help="Inject patch to device (requires --port)"
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
        "unpatch", help="Remove patch (requires --port)"
    )
    unpatch_parser.add_argument(
        "--comp", type=int, default=0, help="FPB comparator slot to unpatch"
    )
    unpatch_parser.add_argument("--all", action="store_true", help="Remove all patches")

    # mem-read command (requires device)
    memread_parser = subparsers.add_parser(
        "mem-read", help="Read memory from device (requires --port)"
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
        "mem-write", help="Write memory to device (requires --port)"
    )
    memwrite_parser.add_argument(
        "addr", type=lambda x: int(x, 0), help="Memory address (hex: 0x20000000)"
    )
    memwrite_parser.add_argument(
        "data", help="Hex data to write (e.g., DEADBEEF01020304)"
    )

    # mem-dump command (requires device)
    memdump_parser = subparsers.add_parser(
        "mem-dump", help="Dump memory region to file (requires --port)"
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
        "serial-send", help="Send data to device serial port (requires --port)"
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
        "serial-read", help="Read recent serial output (requires --port)"
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
        help="Cursor from previous raw_next for incremental reads (default: 0)",
    )

    # file-list command (requires device)
    file_list_parser = subparsers.add_parser(
        "file-list", help="List directory contents on device (requires --port)"
    )
    file_list_parser.add_argument(
        "path", nargs="?", default="/", help="Directory path on device (default: /)"
    )

    # file-stat command (requires device)
    file_stat_parser = subparsers.add_parser(
        "file-stat", help="Get file/directory info on device (requires --port)"
    )
    file_stat_parser.add_argument("path", help="File or directory path on device")

    # file-download command (requires device)
    file_download_parser = subparsers.add_parser(
        "file-download", help="Download file from device (requires --port)"
    )
    file_download_parser.add_argument(
        "remote_path", help="Source file path on device (e.g., /data/log.bin)"
    )
    file_download_parser.add_argument(
        "local_path", help="Destination path on local machine (e.g., /tmp/log.bin)"
    )

    # file-upload command (requires device)
    file_upload_parser = subparsers.add_parser(
        "file-upload", help="Upload local file to device (requires --port)"
    )
    file_upload_parser.add_argument(
        "local_path", help="Source file path on local machine"
    )
    file_upload_parser.add_argument(
        "remote_path", help="Destination path on device (e.g., /data/log.bin)"
    )

    # file-remove command (requires device)
    file_remove_parser = subparsers.add_parser(
        "file-remove", help="Remove file on device (requires --port)"
    )
    file_remove_parser.add_argument("path", help="File path to remove on device")

    # file-mkdir command (requires device)
    file_mkdir_parser = subparsers.add_parser(
        "file-mkdir", help="Create directory on device (requires --port)"
    )
    file_mkdir_parser.add_argument("path", help="Directory path to create on device")

    # file-rename command (requires device)
    file_rename_parser = subparsers.add_parser(
        "file-rename", help="Rename file or directory on device (requires --port)"
    )
    file_rename_parser.add_argument("old_path", help="Current path on device")
    file_rename_parser.add_argument("new_path", help="New path on device")

    # connect command
    subparsers.add_parser("connect", help="Connect to device (requires --port)")

    # disconnect command
    subparsers.add_parser("disconnect", help="Disconnect from device")

    # server-stop command
    server_stop_parser = subparsers.add_parser(
        "server-stop", help="Stop a CLI-launched WebServer background process"
    )
    server_stop_parser.add_argument(
        "--server-port",
        type=int,
        default=0,
        help="Port of the CLI server to stop (default: auto-detect or 5500)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Determine ELF path - can come from global --elf or command-specific arg
    elf_path = args.elf
    if hasattr(args, "elf_path") and args.elf_path:
        elf_path = args.elf_path

    cli = FPBCLI(
        verbose=args.verbose,
        port=args.port,
        baudrate=args.baudrate,
        elf_path=elf_path,
        compile_commands=args.compile_commands,
        tx_chunk_size=args.tx_chunk_size,
        tx_chunk_delay=args.tx_chunk_delay,
        max_retries=args.max_retries,
        direct=args.direct,
        server_url=args.server_url,
    )

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
            cli.test_serial(args.start_size, args.max_size, args.timeout)
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
            cli.serial_read(args.timeout, args.lines, args.since)
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
        elif args.command == "server-stop":
            port = args.server_port if args.server_port else DEFAULT_PORT
            cli.server_stop(port)
    except FPBCLIError as e:
        cli.output_error(str(e))
        sys.exit(1)
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

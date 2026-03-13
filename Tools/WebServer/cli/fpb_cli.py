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

try:
    import serial

    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


class FPBCLIError(Exception):
    """CLI specific errors"""

    pass


class DeviceState:
    """Device state for CLI - can work with or without serial connection"""

    def __init__(self):
        self.ser = None
        self.elf_path = None
        self.compile_commands_path = None
        self.connected = False
        self.ram_start = 0x20000000
        self.ram_size = 0x10000  # 64KB default
        self.inject_base = 0x20001000
        self.cached_slots = None  # Cache for slot state
        self.slot_update_id = 0
        self.upload_chunk_size = 128  # Default chunk size for upload
        self.download_chunk_size = 1024  # Default chunk size for download
        self.serial_tx_fragment_size = 0  # 0 = disabled, >0 = fragment size for TX
        self.serial_tx_fragment_delay = 0.002  # Delay between TX fragments (seconds)
        self.transfer_max_retries = 10  # Max retries for file transfer

    def add_tool_log(self, message):
        """Stub for compatibility with FileTransfer log callbacks."""
        pass

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
    """Lightweight CLI wrapper for FPBInject"""

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
    ):
        self.verbose = verbose
        self.setup_logging()
        # Create device state
        self._device_state = DeviceState()
        self._device_state.elf_path = elf_path
        self._device_state.compile_commands_path = compile_commands
        self._device_state.serial_tx_fragment_size = tx_chunk_size
        self._device_state.serial_tx_fragment_delay = tx_chunk_delay
        self._device_state.transfer_max_retries = max_retries
        self._fpb = FPBInject(self._device_state)

        # Connect to serial if port specified
        if port:
            self._device_state.connect(port, baudrate)
            if self.verbose:
                logging.info(f"Connected to {port}")

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

            # Check if device is connected
            if not self._device_state.connected:
                # Still provide useful info even without connection
                with open(source_file, "r", encoding="utf-8") as f:
                    source_content = f.read()

                # Try to compile to verify the patch is valid
                elf = elf_path or getattr(self._device_state, "elf_path", None)
                if not elf:
                    raise FPBCLIError(
                        "No device connected and no ELF path provided.\n"
                        "Use: fpb_cli.py inject <target_func> <source.c> --elf <elf_path> --compile-commands <path>\n"
                        "Or connect to device first using the WebServer interface."
                    )

                # Compile to validate
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

            # Device is connected - perform actual injection
            with open(source_file, "r", encoding="utf-8") as f:
                source_content = f.read()

            # Set ELF path if provided
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
                    "verify_status": None,  # TODO: implement verify
                }
            )

        except Exception as e:
            self.output_error(f"Injection failed: {str(e)}", e)

    def unpatch(self, comp: int = 0, all_patches: bool = False) -> None:
        """Remove patch from device"""
        try:
            if not self._device_state.connected:
                raise FPBCLIError(
                    "No device connected. Use --port to specify serial port."
                )

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
            if not self._device_state.connected:
                raise FPBCLIError(
                    "No device connected. Use --port to specify serial port."
                )

            info, error = self._fpb.info()
            if error:
                raise FPBCLIError(f"Failed to get info: {error}")

            # Check build time mismatch
            build_time_mismatch = False
            device_build_time = info.get("build_time") if info else None
            elf_build_time = None

            if self._device_state.elf_path and os.path.exists(
                self._device_state.elf_path
            ):
                elf_build_time = self._fpb.get_elf_build_time(
                    self._device_state.elf_path
                )

            if device_build_time and elf_build_time:
                if device_build_time.strip() != elf_build_time.strip():
                    build_time_mismatch = True

            result = {"success": True, "info": info}

            if device_build_time or elf_build_time:
                result["device_build_time"] = device_build_time
                result["elf_build_time"] = elf_build_time
                result["build_time_mismatch"] = build_time_mismatch

            if build_time_mismatch:
                logging.warning(
                    f"Build time mismatch! Device: '{device_build_time}', "
                    f"ELF: '{elf_build_time}'"
                )

            self.output_json(result)

        except Exception as e:
            self.output_error(f"Info failed: {str(e)}", e)

    def test_serial(
        self, start_size: int = 16, max_size: int = 4096, timeout: float = 2.0
    ) -> None:
        """
        Test serial throughput to find max single-transfer size.

        Uses x2 stepping to probe device's receive buffer limit.
        """
        try:
            if not self._device_state.connected:
                raise FPBCLIError(
                    "No device connected. Use --port to specify serial port."
                )

            result = self._fpb.test_serial_throughput(
                start_size=start_size, max_size=max_size, timeout=timeout
            )

            self.output_json(result)

        except Exception as e:
            self.output_error(f"Serial test failed: {str(e)}", e)

    def file_list(self, path: str = "/") -> None:
        """List directory contents on device"""
        try:
            if not self._device_state.connected:
                raise FPBCLIError("No device connected.")
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
            if not self._device_state.connected:
                raise FPBCLIError("No device connected.")
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
            if not self._device_state.connected:
                raise FPBCLIError("No device connected.")
            from core.file_transfer import FileTransfer
            import os

            ft = FileTransfer(
                self._fpb,
                upload_chunk_size=self._device_state.upload_chunk_size,
                download_chunk_size=self._device_state.download_chunk_size,
                max_retries=self._device_state.transfer_max_retries,
            )
            success, data, msg = ft.download(remote_path)
            if not success:
                raise FPBCLIError(f"Download failed: {msg}")

            # Ensure local directory exists
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)

            with open(local_path, "wb") as f:
                f.write(data)

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

    def mem_read(self, addr: int, length: int, fmt: str = "hex") -> None:
        """Read memory from device"""
        try:
            if not self._device_state.connected:
                raise FPBCLIError(
                    "No device connected. Use --port to specify serial port."
                )

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
                # Classic hex dump with ASCII
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
                words = []
                for i in range(0, len(data) - 3, 4):
                    val = int.from_bytes(data[i : i + 4], "little")
                    words.append(f"0x{val:08X}")
                result["words"] = words

            self.output_json(result)

        except Exception as e:
            self.output_error(f"Memory read failed: {str(e)}", e)

    def mem_write(self, addr: int, data_hex: str) -> None:
        """Write memory to device"""
        try:
            if not self._device_state.connected:
                raise FPBCLIError(
                    "No device connected. Use --port to specify serial port."
                )

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
            if not self._device_state.connected:
                raise FPBCLIError(
                    "No device connected. Use --port to specify serial port."
                )

            self._fpb.enter_fl_mode()
            try:
                data, msg = self._fpb.read_memory(addr, length)
            finally:
                self._fpb.exit_fl_mode()

            if data is None:
                raise FPBCLIError(f"Memory read failed: {msg}")

            out_dir = os.path.dirname(output_file)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            with open(output_file, "wb") as f:
                f.write(data)

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

    def cleanup(self):
        """Cleanup resources"""
        self._device_state.disconnect()


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

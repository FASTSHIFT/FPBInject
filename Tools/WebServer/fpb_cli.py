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
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Import from existing WebServer modules
sys.path.insert(0, str(Path(__file__).parent))
from fpb_inject import FPBInject

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
        self.chunk_size = 128  # Default chunk size for upload
        self.tx_chunk_size = 0  # 0 = disabled, >0 = chunk size for TX
        self.tx_chunk_delay = 0.005  # Delay between TX chunks (seconds)

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
        tx_chunk_delay: float = 0.005,
    ):
        self.verbose = verbose
        self.setup_logging()
        # Create device state
        self._device_state = DeviceState()
        self._device_state.elf_path = elf_path
        self._device_state.compile_commands_path = compile_commands
        self._device_state.tx_chunk_size = tx_chunk_size
        self._device_state.tx_chunk_delay = tx_chunk_delay
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

            # symbols is a dict: {name: addr}
            if func_name not in symbols:
                raise FPBCLIError(f"Function '{func_name}' not found")

            addr = symbols[func_name]
            # Get disassembly for analysis
            success, disasm = self._fpb.disassemble_function(elf_path, func_name)
            signature = self._fpb.get_signature(elf_path, func_name)

            self.output_json(
                {
                    "success": True,
                    "analysis": {
                        "func_name": func_name,
                        "addr": hex(addr) if isinstance(addr, int) else addr,
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
        """Decompile function using angr"""
        try:
            # Try to decompile using angr
            try:
                success, decompiled = self._fpb.decompile_function(elf_path, func_name)
                if not success:
                    raise FPBCLIError(f"Decompilation failed: {decompiled}")
            except ImportError:
                raise FPBCLIError("angr not installed. Install with: pip install angr")

            self.output_json(
                {
                    "success": True,
                    "func_name": func_name,
                    "decompiled": decompiled,
                    "language": "c",
                    "note": "This is AI-generated pseudo-code. Verify before using.",
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

            # Simple pattern matching - symbols is dict {name: addr}
            matches = [
                {"name": name, "addr": hex(addr) if isinstance(addr, int) else addr}
                for name, addr in symbols.items()
                if pattern.lower() in name.lower()
            ]

            self.output_json(
                {
                    "success": True,
                    "pattern": pattern,
                    "count": len(matches),
                    "symbols": matches[:20],  # Limit to 20 results
                }
            )
        except Exception as e:
            self.output_error(f"Search failed: {str(e)}", e)

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

            self.output_json({"success": True, "info": info})

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
    info_parser = subparsers.add_parser(
        "info", help="Get device FPB info (requires --port)"
    )

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

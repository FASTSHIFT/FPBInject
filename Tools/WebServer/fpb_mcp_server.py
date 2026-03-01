#!/usr/bin/env python3
"""
FPBInject MCP Server

Exposes FPBInject CLI capabilities as MCP tools for AI agent integration.
Wraps the existing FPBCLI class - no code duplication.

Usage:
    # stdio mode (for IDE integration)
    python fpb_mcp_server.py

    # Or via uvx (after publishing)
    uvx fpbinject-mcp-server
"""

import io
import json
import os
import sys
import contextlib
from pathlib import Path
from typing import Optional

# Self-contained path setup: add this file's directory to sys.path
# so imports work regardless of cwd or PYTHONPATH
_SERVER_DIR = Path(__file__).resolve().parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))
os.chdir(_SERVER_DIR)

from mcp.server.fastmcp import FastMCP  # noqa: E402

# Import the CLI class directly
from cli.fpb_cli import FPBCLI  # noqa: E402

mcp = FastMCP(
    "FPBInject",
    instructions="ARM Cortex-M runtime code injection via FPB hardware unit. "
    "Use offline tools (analyze, disasm, search, compile_patch) without a device. "
    "Use connect() first, then inject/unpatch/info for device operations.",
)

# Shared device state - persists across tool calls within a session
_cli_instance: Optional[FPBCLI] = None


def _capture_cli_output(func, *args, **kwargs) -> dict:
    """Run a CLI method and capture its JSON stdout output."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        func(*args, **kwargs)
    output = buf.getvalue().strip()
    if output:
        return json.loads(output)
    return {"success": False, "error": "No output from CLI"}


def _get_cli(
    port: Optional[str] = None,
    baudrate: int = 115200,
    elf_path: Optional[str] = None,
    compile_commands: Optional[str] = None,
) -> FPBCLI:
    """Get or create CLI instance. Reuses connection if possible."""
    global _cli_instance
    if _cli_instance is None:
        _cli_instance = FPBCLI(
            verbose=False,
            port=port,
            baudrate=baudrate,
            elf_path=elf_path,
            compile_commands=compile_commands,
        )
    else:
        # Update paths if provided
        if elf_path:
            _cli_instance._device_state.elf_path = elf_path
        if compile_commands:
            _cli_instance._device_state.compile_commands_path = compile_commands
        # Connect if port given and not already connected
        if port and not _cli_instance._device_state.connected:
            _cli_instance._device_state.connect(port, baudrate)
    return _cli_instance


# ============================================================
# Offline Tools (no device required)
# ============================================================


@mcp.tool()
def analyze(elf_path: str, func_name: str) -> dict:
    """Analyze a function in an ARM ELF binary.

    Returns function address, signature, and assembly line count.

    Args:
        elf_path: Path to the ELF firmware file
        func_name: Name of the function to analyze
    """
    cli = _get_cli(elf_path=elf_path)
    return _capture_cli_output(cli.analyze, elf_path, func_name)


@mcp.tool()
def disasm(elf_path: str, func_name: str) -> dict:
    """Get ARM disassembly of a function.

    Args:
        elf_path: Path to the ELF firmware file
        func_name: Name of the function to disassemble
    """
    cli = _get_cli(elf_path=elf_path)
    return _capture_cli_output(cli.disasm, elf_path, func_name)


@mcp.tool()
def decompile(elf_path: str, func_name: str) -> dict:
    """Decompile a function to pseudo-C using Ghidra.

    Requires Ghidra to be installed and configured.

    Args:
        elf_path: Path to the ELF firmware file
        func_name: Name of the function to decompile
    """
    cli = _get_cli(elf_path=elf_path)
    return _capture_cli_output(cli.decompile, elf_path, func_name)


@mcp.tool()
def signature(elf_path: str, func_name: str) -> dict:
    """Get the C function signature from DWARF debug info.

    Args:
        elf_path: Path to the ELF firmware file
        func_name: Name of the function
    """
    cli = _get_cli(elf_path=elf_path)
    return _capture_cli_output(cli.signature, elf_path, func_name)


@mcp.tool()
def search(elf_path: str, pattern: str) -> dict:
    """Search for functions in an ELF binary by name pattern.

    Returns up to 20 matching symbols with addresses.

    Args:
        elf_path: Path to the ELF firmware file
        pattern: Search pattern (case-insensitive substring match)
    """
    cli = _get_cli(elf_path=elf_path)
    return _capture_cli_output(cli.search, elf_path, pattern)


@mcp.tool()
def compile_patch(
    source_file: str,
    elf_path: str,
    compile_commands: str,
    base_addr: int = 0x20001000,
) -> dict:
    """Compile a patch source file for offline validation.

    Verifies the patch compiles correctly without needing a device.
    Source file must contain /* FPB_INJECT */ marker.

    Args:
        source_file: Path to the C/C++ patch source file
        elf_path: Path to the ELF firmware file
        compile_commands: Path to compile_commands.json
        base_addr: Base address for patch code (default: 0x20001000)
    """
    cli = _get_cli(elf_path=elf_path, compile_commands=compile_commands)
    return _capture_cli_output(
        cli.compile, source_file, elf_path, base_addr, compile_commands
    )


# ============================================================
# Online Tools (device required)
# ============================================================


@mcp.tool()
def connect(port: str, baudrate: int = 115200) -> dict:
    """Connect to a device via serial port.

    Must be called before using inject, unpatch, or info tools.

    Args:
        port: Serial port path (e.g., /dev/ttyACM0, COM3)
        baudrate: Serial baudrate (default: 115200)
    """
    try:
        cli = _get_cli(port=port, baudrate=baudrate)
        connected = cli._device_state.connected
        return {
            "success": connected,
            "port": port,
            "baudrate": baudrate,
            "message": "Connected" if connected else "Connection failed",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def disconnect() -> dict:
    """Disconnect from the current device."""
    global _cli_instance
    if _cli_instance:
        _cli_instance.cleanup()
        _cli_instance = None
    return {"success": True, "message": "Disconnected"}


@mcp.tool()
def info(
    port: Optional[str] = None,
    elf_path: Optional[str] = None,
) -> dict:
    """Get device FPB hardware info and slot status.

    Shows available FPB slots, active patches, and memory usage.

    Args:
        port: Serial port (uses existing connection if omitted)
        elf_path: ELF path for build time comparison (optional)
    """
    cli = _get_cli(port=port, elf_path=elf_path)
    return _capture_cli_output(cli.info)


@mcp.tool()
def inject(
    target_func: str,
    source_file: str,
    elf_path: Optional[str] = None,
    compile_commands: Optional[str] = None,
    port: Optional[str] = None,
    patch_mode: str = "trampoline",
    comp: int = -1,
) -> dict:
    """Inject a patch to replace a function on the device.

    Compiles the source, uploads binary via serial, and configures FPB
    hardware to redirect calls from target_func to the patched version.

    Source file must contain /* FPB_INJECT */ marker.

    Args:
        target_func: Name of the function to replace
        source_file: Path to the C/C++ patch source file
        elf_path: Path to the ELF firmware file
        compile_commands: Path to compile_commands.json
        port: Serial port (uses existing connection if omitted)
        patch_mode: Patch mode - trampoline, debugmon, or direct (default: trampoline)
        comp: FPB slot number, -1 for auto-assign (default: -1)
    """
    cli = _get_cli(port=port, elf_path=elf_path, compile_commands=compile_commands)
    return _capture_cli_output(
        cli.inject,
        target_func,
        source_file,
        elf_path,
        compile_commands,
        patch_mode,
        comp,
    )


@mcp.tool()
def unpatch(
    port: Optional[str] = None,
    comp: int = 0,
    all_patches: bool = False,
) -> dict:
    """Remove a patch from the device.

    Args:
        port: Serial port (uses existing connection if omitted)
        comp: FPB slot number to unpatch (default: 0)
        all_patches: Remove all patches if True (default: False)
    """
    cli = _get_cli(port=port)
    return _capture_cli_output(cli.unpatch, comp, all_patches)


@mcp.tool()
def test_serial(
    port: Optional[str] = None,
    start_size: int = 16,
    max_size: int = 4096,
) -> dict:
    """Test serial throughput to find optimal transfer parameters.

    Probes the device's receive buffer limit using increasing packet sizes.

    Args:
        port: Serial port (uses existing connection if omitted)
        start_size: Starting test size in bytes (default: 16)
        max_size: Maximum test size in bytes (default: 4096)
    """
    cli = _get_cli(port=port)
    return _capture_cli_output(cli.test_serial, start_size, max_size)


# ============================================================
# Serial I/O Tools
# ============================================================

# Ring buffer for captured serial output
_serial_log: list = []
_SERIAL_LOG_MAX = 500


def _append_serial_log(data: str):
    """Append data to serial log ring buffer."""
    if not data:
        return
    import time as _time

    _serial_log.append({"time": _time.time(), "data": data})
    if len(_serial_log) > _SERIAL_LOG_MAX:
        del _serial_log[: len(_serial_log) - _SERIAL_LOG_MAX]


@mcp.tool()
def serial_read(
    port: Optional[str] = None,
    timeout: float = 1.0,
    lines: int = 50,
) -> dict:
    """Read recent serial output from the device.

    Reads any pending data from the serial port buffer and returns it.
    Also returns recent history from the log buffer.
    Use this to see device printf output, boot messages, or patch logs.

    Args:
        port: Serial port (uses existing connection if omitted)
        timeout: How long to wait for new data in seconds (default: 1.0)
        lines: Max number of recent log lines to return (default: 50)
    """
    import time as _time

    cli = _get_cli(port=port)
    ser = cli._device_state.ser

    if not ser or not cli._device_state.connected:
        return {"success": False, "error": "Not connected to device"}

    # Read any pending data from serial buffer
    new_data = ""
    try:
        start = _time.time()
        while _time.time() - start < timeout:
            if ser.in_waiting:
                chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                new_data += chunk
                _time.sleep(0.05)  # Small delay to accumulate more data
            else:
                if new_data:
                    break  # Got data and no more pending
                _time.sleep(0.1)
    except Exception as e:
        return {"success": False, "error": f"Read error: {e}"}

    if new_data:
        # Split into lines and log each
        for line in new_data.split("\n"):
            line = line.strip()
            if line:
                _append_serial_log(line)

    # Return recent log entries
    recent = _serial_log[-lines:]
    return {
        "success": True,
        "new_data": new_data,
        "log": [entry["data"] for entry in recent],
        "log_count": len(recent),
        "total_buffered": len(_serial_log),
    }


@mcp.tool()
def serial_send(
    data: str,
    port: Optional[str] = None,
    read_response: bool = True,
    timeout: float = 1.0,
) -> dict:
    """Send a string to the device via serial port.

    Sends raw data followed by newline. Optionally reads back the response.
    Use this for NuttX shell commands or any serial interaction.

    WARNING: Sending 'fl' commands directly may interfere with FPB protocol state.
    Use the dedicated inject/unpatch/info tools for FPB operations instead.

    Args:
        data: String to send to the device
        port: Serial port (uses existing connection if omitted)
        read_response: Whether to read response after sending (default: True)
        timeout: Response read timeout in seconds (default: 1.0)
    """
    import time as _time

    cli = _get_cli(port=port)
    ser = cli._device_state.ser

    if not ser or not cli._device_state.connected:
        return {"success": False, "error": "Not connected to device"}

    try:
        # Exit fl mode first to avoid protocol interference
        if hasattr(cli._fpb, "_protocol") and cli._fpb._protocol._in_fl_mode:
            cli._fpb._protocol.exit_fl_mode()

        _append_serial_log(f">>> {data}")

        ser.write((data + "\n").encode())
        ser.flush()

        response = ""
        if read_response:
            start = _time.time()
            while _time.time() - start < timeout:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    response += chunk
                    _time.sleep(0.05)
                else:
                    if response:
                        break
                    _time.sleep(0.1)

            for line in response.split("\n"):
                line = line.strip()
                if line:
                    _append_serial_log(line)

        return {
            "success": True,
            "sent": data,
            "response": response.strip(),
        }
    except Exception as e:
        return {"success": False, "error": f"Send error: {e}"}


if __name__ == "__main__":
    mcp.run()

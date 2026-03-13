#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
GDB integration manager for FPBInject Web Server.

Provides functions to start/stop the GDB RSP Bridge + GDB Session pair,
and a helper to check if GDB is available for symbol queries.
"""

import logging
import os
import threading
import time

from core.elf_utils import get_memory_regions
from core.gdb_bridge import GDBRSPBridge
from core.gdb_session import GDBSession
from core.state import ToolLogHandler

logger = logging.getLogger(__name__)

# Handler instance for forwarding GDB logs to frontend
_gdb_tool_log_handler = None

# Default RSP port (0 = auto-assign)
DEFAULT_RSP_PORT = 0


def start_gdb(state, read_memory_fn=None, write_memory_fn=None) -> bool:
    """Start GDB RSP Bridge + GDB Session for the current ELF.

    This sets up:
    1. A GDB RSP Bridge (TCP server) that translates GDB memory requests to fl commands
    2. A GDB subprocess that loads the ELF and connects to the bridge

    Args:
        state: AppState instance
        read_memory_fn: Callable(addr, length) -> (bytes|None, str)
            If None, a stub that returns zeros is used (offline mode).
        write_memory_fn: Callable(addr, bytes) -> (bool, str)
            If None, a stub that returns OK is used (offline mode).

    Returns:
        True if GDB started successfully
    """
    device = state.device
    elf_path = device.elf_path

    if not elf_path:
        logger.warning("Cannot start GDB: no ELF path configured")
        return False

    if not os.path.exists(elf_path):
        logger.warning(f"Cannot start GDB: ELF not found: {elf_path}")
        return False

    # Stop existing session if any
    stop_gdb(state)

    # Use offline stubs if no serial functions provided
    if read_memory_fn is None:

        def read_memory_fn(addr, length):
            return (b"\x00" * length, "offline stub")

    if write_memory_fn is None:

        def write_memory_fn(addr, data):
            return (True, "offline stub")

    t_start = time.time()
    logger.info("Starting GDB integration...")

    try:
        # Phase 1: Start RSP Bridge
        bridge = GDBRSPBridge(
            read_memory_fn=read_memory_fn,
            write_memory_fn=write_memory_fn,
            listen_port=DEFAULT_RSP_PORT,
            cache_line_size=getattr(device, "download_chunk_size", 1024),
        )
        _apply_elf_memory_regions(bridge, elf_path)
        port = bridge.start()
        state.gdb_bridge = bridge

        # Phase 2: Start GDB Session
        session = GDBSession(
            elf_path=elf_path,
            toolchain_path=device.toolchain_path,
        )
        if not session.start(rsp_port=port):
            logger.error("GDB session failed to start, cleaning up bridge")
            bridge.stop()
            state.gdb_bridge = None
            return False

        state.gdb_session = session

        # Attach log handler to forward GDB session logs to frontend OUTPUT
        global _gdb_tool_log_handler
        _gdb_tool_log_handler = ToolLogHandler(device, level=logging.INFO)
        logging.getLogger("core.gdb_session").addHandler(_gdb_tool_log_handler)

        # Phase 3: Start external GDB server (for CLI/IDE connections)
        # Pass None explicitly so it creates real serial callbacks,
        # not the offline stubs used by the internal bridge.
        start_external_gdb_server(state)

        elapsed = time.time() - t_start
        logger.info(f"GDB integration ready in {elapsed:.2f}s")
        return True

    except Exception as e:
        logger.error(f"Failed to start GDB integration: {e}")
        stop_gdb(state)
        return False


def stop_gdb(state):
    """Stop GDB Session, RSP Bridge, and external GDB server."""
    global _gdb_tool_log_handler
    if _gdb_tool_log_handler:
        logging.getLogger("core.gdb_session").removeHandler(_gdb_tool_log_handler)
        _gdb_tool_log_handler = None

    if state.gdb_session:
        try:
            state.gdb_session.stop()
        except Exception as e:
            logger.debug(f"Error stopping GDB session: {e}")
        state.gdb_session = None

    if state.gdb_bridge:
        try:
            state.gdb_bridge.stop()
        except Exception as e:
            logger.debug(f"Error stopping GDB bridge: {e}")
        state.gdb_bridge = None

    stop_external_gdb_server(state)


def is_gdb_available(state) -> bool:
    """Check if GDB session is alive and ready for queries."""
    return state.gdb_session is not None and state.gdb_session.is_alive


def _apply_elf_memory_regions(bridge, elf_path):
    """Parse ELF PT_LOAD segments and apply as bridge memory regions.

    Falls back to DEFAULT_MEMORY_REGIONS if ELF parsing fails or
    no PT_LOAD segments are found.
    """
    if not elf_path:
        return

    regions = get_memory_regions(elf_path)
    if regions:
        bridge.set_memory_regions(regions)
    else:
        logger.info(
            "Using default ARM Cortex-M memory regions (ELF parse returned none)"
        )


# ------------------------------------------------------------------
# External GDB Server (for CLI / IDE connections)
# ------------------------------------------------------------------


def start_external_gdb_server(state, read_memory_fn=None, write_memory_fn=None) -> bool:
    """Start an external-facing GDB RSP Bridge for CLI/IDE connections.

    This creates a separate RSP Bridge instance on a fixed port so that
    external GDB clients (command-line gdb, VS Code Cortex-Debug, CLion, etc.)
    can connect and interact with device memory via standard GDB commands.

    If no read/write functions are provided, automatically creates callbacks
    that route through the DeviceWorker to access real device memory via serial.

    Args:
        state: AppState instance
        read_memory_fn: Callable(addr, length) -> (bytes|None, str)
        write_memory_fn: Callable(addr, bytes) -> (bool, str)

    Returns:
        True if the external GDB server started successfully
    """
    device = state.device
    port = getattr(device, "external_gdb_port", 3333)

    if not port:
        logger.info("External GDB server disabled (port=0)")
        return False

    if state.external_gdb_bridge and state.external_gdb_bridge.is_running:
        logger.info(
            f"External GDB server already running on port {state.external_gdb_bridge.port}"
        )
        return True

    # If no callbacks provided, create ones that route through DeviceWorker
    # to access real device memory via serial protocol.
    if read_memory_fn is None or write_memory_fn is None:
        logger.info("[ExtGDB] Creating serial memory callbacks (real device access)")
        read_memory_fn, write_memory_fn = _create_serial_memory_callbacks(state)
    else:
        logger.info("[ExtGDB] Using provided memory callbacks (may be offline stubs)")

    try:
        bridge = GDBRSPBridge(
            read_memory_fn=read_memory_fn,
            write_memory_fn=write_memory_fn,
            listen_port=port,
            cache_line_size=getattr(device, "download_chunk_size", 1024),
        )
        _apply_elf_memory_regions(bridge, device.elf_path)
        actual_port = bridge.start()
        state.external_gdb_bridge = bridge
        logger.info(f"External GDB RSP server listening on port {actual_port}")
        return True
    except Exception as e:
        logger.error(f"Failed to start external GDB server: {e}")
        return False


def _create_serial_memory_callbacks(state):
    """Create memory read/write callbacks that go through DeviceWorker.

    These callbacks serialize serial access through the fpb-worker thread,
    so they are safe to call from the RSP bridge's client-handling thread.

    Returns:
        (read_memory_fn, write_memory_fn) tuple
    """
    from services.device_worker import run_in_device_worker

    def read_memory_fn(addr, length):
        """Read device memory via serial, routed through DeviceWorker."""
        device = state.device
        if device.ser is None:
            logger.warning(f"[ExtGDB] read 0x{addr:08X}+{length}: NOT CONNECTED")
            return (None, "Not connected")

        logger.info(
            f"[ExtGDB] read 0x{addr:08X}+{length}: dispatching to DeviceWorker..."
        )
        result = {"data": None, "msg": "timeout"}

        def do_read():
            try:
                from routes import get_fpb_inject

                fpb = get_fpb_inject()
                result["data"], result["msg"] = fpb.read_memory(addr, length)
                if result["data"] is not None:
                    logger.info(
                        f"[ExtGDB] read 0x{addr:08X}+{length}: OK, got {len(result['data'])} bytes"
                    )
                else:
                    logger.warning(
                        f"[ExtGDB] read 0x{addr:08X}+{length}: FAILED - {result['msg']}"
                    )
            except Exception as e:
                result["data"] = None
                result["msg"] = str(e)
                logger.error(f"[ExtGDB] read 0x{addr:08X}+{length}: EXCEPTION - {e}")

        if not run_in_device_worker(device, do_read, timeout=10.0):
            logger.error(f"[ExtGDB] read 0x{addr:08X}+{length}: DeviceWorker TIMEOUT")
            return (None, "DeviceWorker timeout")

        return (result["data"], result["msg"])

    def write_memory_fn(addr, data):
        """Write device memory via serial, routed through DeviceWorker."""
        device = state.device
        if device.ser is None:
            logger.warning(f"[ExtGDB] write 0x{addr:08X}+{len(data)}: NOT CONNECTED")
            return (False, "Not connected")

        logger.info(
            f"[ExtGDB] write 0x{addr:08X}+{len(data)}: dispatching to DeviceWorker..."
        )
        result = {"ok": False, "msg": "timeout"}

        def do_write():
            try:
                from routes import get_fpb_inject

                fpb = get_fpb_inject()
                result["ok"], result["msg"] = fpb.write_memory(addr, data)
                logger.info(
                    f"[ExtGDB] write 0x{addr:08X}+{len(data)}: {'OK' if result['ok'] else 'FAILED'} - {result['msg']}"
                )
            except Exception as e:
                result["ok"] = False
                result["msg"] = str(e)
                logger.error(
                    f"[ExtGDB] write 0x{addr:08X}+{len(data)}: EXCEPTION - {e}"
                )

        if not run_in_device_worker(device, do_write, timeout=10.0):
            return (False, "DeviceWorker timeout")

        return (result["ok"], result["msg"])

    return read_memory_fn, write_memory_fn


def stop_external_gdb_server(state):
    """Stop the external GDB RSP Bridge."""
    if state.external_gdb_bridge:
        try:
            state.external_gdb_bridge.stop()
        except Exception as e:
            logger.debug(f"Error stopping external GDB server: {e}")
        state.external_gdb_bridge = None


def get_external_gdb_port(state) -> int:
    """Get the actual port of the external GDB server, or 0 if not running."""
    if state.external_gdb_bridge and state.external_gdb_bridge.is_running:
        return state.external_gdb_bridge.port
    return 0


def start_gdb_async(state, read_memory_fn=None, write_memory_fn=None):
    """Start GDB in a background thread (non-blocking).

    Useful for starting GDB during connection setup without blocking the response.
    """

    def _start():
        ok = start_gdb(state, read_memory_fn, write_memory_fn)
        if ok:
            logger.info("GDB background startup completed successfully")
        else:
            logger.warning("GDB background startup failed")

    thread = threading.Thread(target=_start, name="gdb-startup", daemon=True)
    thread.start()
    return thread

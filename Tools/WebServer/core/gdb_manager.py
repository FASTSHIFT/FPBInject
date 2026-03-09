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
        )
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
        _gdb_tool_log_handler = ToolLogHandler(device, prefix="GDB", level=logging.INFO)
        logging.getLogger("core.gdb_session").addHandler(_gdb_tool_log_handler)

        elapsed = time.time() - t_start
        logger.info(f"GDB integration ready in {elapsed:.2f}s")
        return True

    except Exception as e:
        logger.error(f"Failed to start GDB integration: {e}")
        stop_gdb(state)
        return False


def stop_gdb(state):
    """Stop GDB Session and RSP Bridge."""
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


def is_gdb_available(state) -> bool:
    """Check if GDB session is alive and ready for queries."""
    return state.gdb_session is not None and state.gdb_session.is_alive


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

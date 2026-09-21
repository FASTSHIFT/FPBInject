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

from fpbinject.core.elf_utils import get_memory_regions
from fpbinject.core.gdb_bridge import GDBRSPBridge
from fpbinject.core.gdb_session import GDBSession
from fpbinject.core.state import ToolLogHandler
from fpbinject.utils.net import get_port_owner, is_port_available, kill_port_owner

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
        if not is_port_available("127.0.0.1", port):
            owner = get_port_owner(port)
            if owner:
                logger.error(f"❌ GDB server port {port} is already in use!")
                logger.error(f"   Process: {owner['name']} (PID {owner['pid']})")
                logger.error(f"   Command: {owner['cmdline']}")
                logger.warning(f"   Killing stale process PID {owner['pid']}...")
            else:
                logger.error(f"❌ GDB server port {port} is in use by unknown process")

            if not kill_port_owner(port):
                logger.error(f"   Failed to free port {port}. Options:")
                if owner:
                    logger.error(f"     kill {owner['pid']}")
                logger.error("     Change port in config (external_gdb_port)")
                return False

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


# Idle window before we exit fl mode after the last GDB access. GDB tends
# to burst many small reads together (register/variable refresh, stack
# unwind); wrapping each read in its own fl_session() thrashes the device
# by re-entering/exiting fl for every access. Instead we enter fl on the
# first access, then only exit once GDB has been silent for this long.
GDB_FL_IDLE_EXIT_SEC = 0.5


class _GDBFLIdleExit:
    """Lazy fl-mode exit driven by GDB access idleness.

    Each memory read/write calls ``mark_active()``. A soft timer on the
    DeviceWorker's TimerManager polls the last-activity timestamp; once
    GDB has been quiet for ``idle_sec``, the timer callback (already on
    the worker thread) calls ``exit_fl_mode`` directly. Any new access
    resets the deadline, so a burst of reads counts as one session and
    no extra thread is spawned.
    """

    def __init__(self, get_fpb, timer_manager, idle_sec=GDB_FL_IDLE_EXIT_SEC):
        self._get_fpb = get_fpb
        self._tm = timer_manager
        self._idle_sec = idle_sec
        self._last_active = 0.0
        self._armed = False
        self._timer = None
        # Guards _armed / _timer against the RSP thread (mark_active, stop)
        # and the worker thread (_tick) racing on timer registration/removal.
        self._lock = threading.Lock()

    def mark_active(self):
        # Called from the RSP bridge thread.
        with self._lock:
            self._last_active = time.monotonic()
            if self._armed or self._tm is None:
                return
            self._armed = True
            if self._timer is None:
                # Poll interval == idle window: worst-case exit fires one
                # window after the last access.
                self._timer = self._tm.add(
                    self._idle_sec, self._tick, name="gdb-fl-idle-exit"
                )
            else:
                self._timer.enabled = True
                self._timer.reset()

    def _tick(self):
        # Runs on the worker thread, serialized with all other serial ops.
        with self._lock:
            if not self._armed:
                return
            if time.monotonic() - self._last_active < self._idle_sec:
                return  # still active, keep polling
            self._armed = False
            if self._timer is not None:
                self._timer.enabled = False
        # Call exit_fl_mode outside the lock: it does serial I/O and can take
        # a few hundred ms; keeping the lock held would stall mark_active().
        try:
            self._get_fpb().exit_fl_mode()
        except Exception as e:
            logger.debug(f"[ExtGDB] idle exit_fl_mode error: {e}")

    def stop(self):
        with self._lock:
            self._armed = False
            timer = self._timer
            self._timer = None
        if timer is not None and self._tm is not None:
            self._tm.remove(timer)


def _create_serial_memory_callbacks(state):
    """Create memory read/write callbacks that go through DeviceWorker.

    These callbacks serialize serial access through the fpb-worker thread,
    so they are safe to call from the RSP bridge's client-handling thread.

    Enters fl on demand (send_cmd handles that idempotently) and exits fl
    lazily via ``_GDBFLIdleExit`` once GDB has been silent for a short window.
    This avoids the enter/exit churn caused by GDB's burst of small reads.

    Returns:
        (read_memory_fn, write_memory_fn) tuple
    """
    from fpbinject.routes import get_fpb_inject
    from fpbinject.services.device_worker import (
        get_device_timer_manager,
        run_in_device_worker,
    )

    idle_exit = _GDBFLIdleExit(get_fpb_inject, get_device_timer_manager(state.device))
    # Attach so stop_external_gdb_server can shut the watcher down.
    state.external_gdb_idle_exit = idle_exit

    def read_memory_fn(addr, length):
        """Read device memory via serial, routed through DeviceWorker."""
        device = state.device
        if device.ser is None:
            logger.warning(f"[ExtGDB] read 0x{addr:08X}+{length}: NOT CONNECTED")
            return (None, "Not connected")

        idle_exit.mark_active()
        result = {"data": None, "msg": "timeout"}

        def do_read():
            try:
                result["data"], result["msg"] = get_fpb_inject().read_memory(
                    addr, length
                )
            except Exception as e:
                result["data"] = None
                result["msg"] = str(e)
                logger.error(f"[ExtGDB] read 0x{addr:08X}+{length}: EXCEPTION - {e}")

        if not run_in_device_worker(device, do_read, timeout=10.0):
            logger.error(f"[ExtGDB] read 0x{addr:08X}+{length}: DeviceWorker TIMEOUT")
            return (None, "DeviceWorker timeout")

        # Refresh the idle deadline after the call so the exit fires N ms
        # after the last completed access, not after the request was queued.
        idle_exit.mark_active()
        return (result["data"], result["msg"])

    def write_memory_fn(addr, data):
        """Write device memory via serial, routed through DeviceWorker."""
        device = state.device
        if device.ser is None:
            logger.warning(f"[ExtGDB] write 0x{addr:08X}+{len(data)}: NOT CONNECTED")
            return (False, "Not connected")

        idle_exit.mark_active()
        result = {"ok": False, "msg": "timeout"}

        def do_write():
            try:
                result["ok"], result["msg"] = get_fpb_inject().write_memory(addr, data)
            except Exception as e:
                result["ok"] = False
                result["msg"] = str(e)
                logger.error(
                    f"[ExtGDB] write 0x{addr:08X}+{len(data)}: EXCEPTION - {e}"
                )

        if not run_in_device_worker(device, do_write, timeout=10.0):
            return (False, "DeviceWorker timeout")

        idle_exit.mark_active()
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

    idle_exit = getattr(state, "external_gdb_idle_exit", None)
    if idle_exit is not None:
        try:
            idle_exit.stop()
        except Exception as e:
            logger.debug(f"Error stopping GDB idle exit watcher: {e}")
        state.external_gdb_idle_exit = None


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

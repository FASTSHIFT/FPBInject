#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Connection API routes for FPBInject Web Server.

Provides endpoints for serial port connection management and configuration.
"""

import logging
import os

from flask import Blueprint, jsonify, request

from core.state import state
from services.device_worker import run_in_device_worker, start_worker, stop_worker
from utils.port_lock import PortLock

logger = logging.getLogger(__name__)

bp = Blueprint("connection", __name__)


def _get_helpers():
    """Lazy import to avoid circular dependency."""
    from routes import get_fpb_inject
    from services.file_watcher_manager import (
        restart_file_watcher,
        stop_file_watcher,
        start_elf_watcher,
    )
    from fpb_inject import scan_serial_ports, serial_open
    from core.state import state, tool_log

    def log_info(msg):
        tool_log(state.device, "INFO", msg)

    def log_success(msg):
        tool_log(state.device, "SUCCESS", msg)

    def log_error(msg):
        tool_log(state.device, "ERROR", msg)

    return (
        log_info,
        log_success,
        log_error,
        get_fpb_inject,
        restart_file_watcher,
        stop_file_watcher,
        scan_serial_ports,
        serial_open,
        start_elf_watcher,
    )


def _start_elf_watcher(elf_path):
    """Start ELF file watcher."""
    *_, start_elf_watcher = _get_helpers()
    start_elf_watcher(elf_path)


def _start_vserial(device):
    """Create and start the virtual serial passthrough service."""
    from services.virtual_serial import VirtualSerialService

    if device.vserial is None:
        device.vserial = VirtualSerialService(device)

    symlink = getattr(device, "vserial_symlink", "/tmp/fpb-tty0")
    success, error = device.vserial.start(symlink=symlink)
    if success:
        status = device.vserial.status()
        logger.info(f"Virtual serial ready: {status.get('slave')}")
    else:
        logger.warning(f"Virtual serial start failed: {error}")
    return success, error


def _stop_vserial(device):
    """Stop the virtual serial passthrough service if running."""
    if device.vserial is not None:
        device.vserial.stop()


@bp.route("/ports", methods=["GET"])
def api_get_ports():
    """Get available serial ports."""
    *_, scan_serial_ports, _, _ = _get_helpers()
    ports = scan_serial_ports()
    return jsonify({"success": True, "ports": ports})


@bp.route("/connect", methods=["POST"])
def api_connect():
    """Connect to a serial port."""
    _, log_success, log_error, get_fpb_inject, _, _, _, serial_open, _ = _get_helpers()

    data = request.json or {}
    port = data.get("port")
    baudrate = data.get("baudrate", 115200)
    timeout = data.get("timeout", 2)
    data_bits = data.get("data_bits", 8)
    parity = data.get("parity", "none")
    stop_bits = data.get("stop_bits", 1)
    flow_control = data.get("flow_control", "none")
    dtr = data.get("dtr_on_connect", False)
    rts = data.get("rts_on_connect", False)

    if not port:
        return jsonify({"success": False, "error": "Port not specified"})

    device = state.device

    # Start worker first
    start_worker(device)

    result = {"error": None}

    def do_connect():
        if device.ser:
            try:
                device.ser.close()
            except Exception:
                pass
            device.ser = None

        ser, error = serial_open(
            port,
            baudrate,
            timeout,
            data_bits=data_bits,
            parity=parity,
            stop_bits=stop_bits,
            flow_control=flow_control,
            dtr=dtr,
            rts=rts,
        )
        if error:
            result["error"] = error
        else:
            device.ser = ser
            device.port = port
            device.baudrate = baudrate
            device.timeout = timeout
            device.data_bits = data_bits
            device.parity = parity
            device.stop_bits = stop_bits
            device.flow_control = flow_control
            device.dtr_on_connect = dtr
            device.rts_on_connect = rts

    if not run_in_device_worker(device, do_connect, timeout=5.0):
        return jsonify(
            {"success": False, "error": "Connect timeout", "error_code": "timeout"}
        )

    if result["error"]:
        # Parse error_code from bracketed prefix, e.g. "[permission_denied] ..."
        error_msg = result["error"]
        error_code = "unknown_error"
        if error_msg.startswith("["):
            end = error_msg.find("]")
            if end > 0:
                error_code = error_msg[1:end]
                error_msg = error_msg[end + 2 :]  # strip "[code] " prefix
        return jsonify({"success": False, "error": error_msg, "error_code": error_code})

    device.auto_connect = True
    state.save_config()

    # Start virtual serial passthrough if enabled
    if getattr(device, "vserial_enable", False):
        _start_vserial(device)

    # Acquire port lock
    lock = PortLock(port)
    if lock.acquire():
        state.port_lock = lock
    else:
        logger.warning(f"Could not acquire port lock for {port}")

    # Setup toolchain if configured
    fpb = get_fpb_inject()
    if device.toolchain_path:
        fpb.set_toolchain_path(device.toolchain_path)

    log_success(f"Connected to {port} @ {baudrate}")
    return jsonify({"success": True, "port": port})


@bp.route("/disconnect", methods=["POST"])
def api_disconnect():
    """Disconnect from serial port."""
    log_info, _, _, _, _, _, _, _, _ = _get_helpers()

    device = state.device

    def do_disconnect():
        if device.ser:
            try:
                device.ser.close()
            except Exception:
                pass
            device.ser = None

    run_in_device_worker(device, do_disconnect, timeout=2.0)

    # Stop virtual serial passthrough before stopping the worker
    _stop_vserial(device)

    stop_worker(device)

    # Release port lock
    if hasattr(state, "port_lock") and state.port_lock:
        state.port_lock.release()
        state.port_lock = None

    # Stop GDB integration
    from core.gdb_manager import stop_gdb

    stop_gdb(state)

    device.auto_connect = False
    device.inject_active = False
    state.save_config()

    log_info("Disconnected from serial port")
    return jsonify({"success": True})


@bp.route("/status", methods=["GET"])
def api_status():
    """Get current device status."""
    device = state.device

    connected = False
    try:
        connected = device.ser is not None and device.ser.isOpen()
    except Exception:
        pass

    # Get external GDB server port
    from core.gdb_manager import get_external_gdb_port

    external_gdb_port = get_external_gdb_port(state)

    return jsonify(
        {
            "success": True,
            "connected": connected,
            "port": device.port,
            "baudrate": device.baudrate,
            "elf_path": device.elf_path,
            "toolchain_path": device.toolchain_path,
            "compile_commands_path": device.compile_commands_path,
            "watch_dirs": device.watch_dirs,
            "patch_mode": device.patch_mode,
            "upload_chunk_size": device.upload_chunk_size,
            "download_chunk_size": device.download_chunk_size,
            "auto_connect": device.auto_connect,
            "auto_compile": device.auto_compile,
            "enable_decompile": device.enable_decompile,
            "patch_source_path": device.patch_source_path,
            "inject_active": device.inject_active,
            "last_inject_target": device.last_inject_target,
            "last_inject_func": device.last_inject_func,
            "last_inject_time": device.last_inject_time,
            "device_info": device.device_info,
            "external_gdb_port": external_gdb_port,
            "vserial": device.vserial.status() if device.vserial else None,
        }
    )


@bp.route("/vserial/status", methods=["GET"])
def api_vserial_status():
    """Get virtual serial passthrough status."""
    device = state.device
    if device.vserial is None:
        return jsonify({"success": True, "enabled": False, "slave": None})
    status = device.vserial.status()
    status["success"] = True
    return jsonify(status)


@bp.route("/vserial/start", methods=["POST"])
def api_vserial_start():
    """Start virtual serial passthrough at runtime."""
    device = state.device

    connected = False
    try:
        connected = device.ser is not None and device.ser.isOpen()
    except Exception:
        pass
    if not connected:
        return jsonify({"success": False, "error": "Connect to a serial port first"})

    success, error = _start_vserial(device)
    if success:
        device.vserial_enable = True
        state.save_config()
        status = device.vserial.status()
        status["success"] = True
        return jsonify(status)
    return jsonify({"success": False, "error": error})


@bp.route("/vserial/stop", methods=["POST"])
def api_vserial_stop():
    """Stop virtual serial passthrough at runtime."""
    device = state.device
    _stop_vserial(device)
    device.vserial_enable = False
    state.save_config()
    return jsonify({"success": True})


@bp.route("/config", methods=["GET"])
def api_get_config():
    """Get current device configuration."""
    from core.config_schema import PERSISTENT_KEYS

    device = state.device
    config_data = {key: getattr(device, key) for key in PERSISTENT_KEYS}
    config_data["first_launch"] = state.first_launch
    return jsonify(config_data)


@bp.route("/config/schema", methods=["GET"])
def api_get_config_schema():
    """Get configuration schema for frontend dynamic rendering."""
    from core.config_schema import get_schema_as_dict

    return jsonify(get_schema_as_dict())


@bp.route("/config", methods=["POST"])
def api_config():
    """Update device configuration."""
    from core.config_schema import PERSISTENT_KEYS

    _, _, _, get_fpb_inject, _restart_file_watcher, _stop_file_watcher, _, _, _ = (
        _get_helpers()
    )

    data = request.json or {}
    device = state.device

    # Update all config values from request
    for key in PERSISTENT_KEYS:
        if key in data:
            setattr(device, key, data[key])

    # Special handling for certain config changes
    if "elf_path" in data:
        # Reload symbols in background to avoid blocking config response
        state.symbols = {}
        state.symbols_loaded = False
        logger.info("ELF path changed, symbols will be loaded on next access")

        # Start ELF file watcher
        _start_elf_watcher(device.elf_path)

        # Start GDB integration in background (non-blocking)
        from core.gdb_manager import start_gdb_async

        start_gdb_async(state)

    if "toolchain_path" in data:
        fpb = get_fpb_inject()
        fpb.set_toolchain_path(device.toolchain_path)

    if "watch_dirs" in data:
        # Restart file watcher if needed
        _restart_file_watcher()

    if "auto_compile" in data:
        # Start or stop file watcher based on auto_compile setting
        if device.auto_compile:
            _restart_file_watcher()
        else:
            _stop_file_watcher()

    if "patch_source_path" in data:
        # Load patch source content if file exists
        if device.patch_source_path and os.path.exists(device.patch_source_path):
            try:
                with open(device.patch_source_path, "r") as f:
                    device.patch_source_content = f.read()
            except Exception:
                pass

    state.save_config()
    return jsonify({"success": True})

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Connection API routes for FPBInject Web Server.

Provides endpoints for serial port connection management and configuration.
"""

import os

from flask import Blueprint, jsonify, request

from core.state import state
from services.device_worker import run_in_device_worker, start_worker, stop_worker

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
    from core.state import state

    def add_tool_log(msg):
        state.device.add_tool_log(msg)

    return (
        add_tool_log,
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


@bp.route("/ports", methods=["GET"])
def api_get_ports():
    """Get available serial ports."""
    _, _, _, _, scan_serial_ports, _, _ = _get_helpers()
    ports = scan_serial_ports()
    return jsonify({"success": True, "ports": ports})


@bp.route("/connect", methods=["POST"])
def api_connect():
    """Connect to a serial port."""
    add_tool_log, get_fpb_inject, _, _, _, serial_open, _ = _get_helpers()

    data = request.json or {}
    port = data.get("port")
    baudrate = data.get("baudrate", 115200)
    timeout = data.get("timeout", 2)

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

        ser, error = serial_open(port, baudrate, timeout)
        if error:
            result["error"] = error
        else:
            device.ser = ser
            device.port = port
            device.baudrate = baudrate
            device.timeout = timeout

    if not run_in_device_worker(device, do_connect, timeout=5.0):
        return jsonify({"success": False, "error": "Connect timeout"})

    if result["error"]:
        add_tool_log(f"[ERROR] Connection failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    device.auto_connect = True
    state.save_config()

    # Setup toolchain if configured
    fpb = get_fpb_inject()
    if device.toolchain_path:
        fpb.set_toolchain_path(device.toolchain_path)

    add_tool_log(f"[SUCCESS] Connected to {port} @ {baudrate}")
    return jsonify({"success": True, "port": port})


@bp.route("/disconnect", methods=["POST"])
def api_disconnect():
    """Disconnect from serial port."""
    add_tool_log, _, _, _, _, _, _ = _get_helpers()

    device = state.device

    def do_disconnect():
        if device.ser:
            try:
                device.ser.close()
            except Exception:
                pass
            device.ser = None

    run_in_device_worker(device, do_disconnect, timeout=2.0)
    stop_worker(device)

    device.auto_connect = False
    device.inject_active = False
    state.save_config()

    add_tool_log("[INFO] Disconnected from serial port")
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
            "chunk_size": device.chunk_size,
            "auto_connect": device.auto_connect,
            "auto_compile": device.auto_compile,
            "enable_decompile": device.enable_decompile,
            "patch_source_path": device.patch_source_path,
            "inject_active": device.inject_active,
            "last_inject_target": device.last_inject_target,
            "last_inject_func": device.last_inject_func,
            "last_inject_time": device.last_inject_time,
            "device_info": device.device_info,
        }
    )


@bp.route("/config", methods=["GET"])
def api_get_config():
    """Get current device configuration."""
    from core.config_schema import PERSISTENT_KEYS

    device = state.device
    return jsonify({key: getattr(device, key) for key in PERSISTENT_KEYS})


@bp.route("/config/schema", methods=["GET"])
def api_get_config_schema():
    """Get configuration schema for frontend dynamic rendering."""
    from core.config_schema import get_schema_as_dict

    return jsonify(get_schema_as_dict())


@bp.route("/config", methods=["POST"])
def api_config():
    """Update device configuration."""
    from core.config_schema import PERSISTENT_KEYS

    _, get_fpb_inject, _restart_file_watcher, _stop_file_watcher, _, _, _ = (
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
        # Reload symbols
        if device.elf_path and os.path.exists(device.elf_path):
            fpb = get_fpb_inject()
            state.symbols = fpb.get_symbols(device.elf_path)
            state.symbols_loaded = True

        # Start ELF file watcher
        _start_elf_watcher(device.elf_path)

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

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Logs API routes for FPBInject Web Server.

Provides endpoints for serial logs, tool logs, and raw serial data.
"""

from flask import Blueprint, jsonify, request

from core.state import state
from services.device_worker import run_in_device_worker

bp = Blueprint("logs", __name__)


def _build_slot_response(device, app_state):
    """Build slot response using shared helper."""
    from routes import get_fpb_inject
    from utils.helpers import build_slot_response

    return build_slot_response(device, app_state, get_fpb_inject)


@bp.route("/log", methods=["GET"])
def api_log():
    """Get serial communication log."""
    since_id = request.args.get("since", 0, type=int)
    device = state.device

    log_snapshot = list(device.serial_log)
    logs = [entry for entry in log_snapshot if entry["id"] >= since_id]
    next_id = device.log_next_id

    return jsonify({"success": True, "logs": logs, "next_index": next_id})


@bp.route("/log/clear", methods=["POST"])
def api_log_clear():
    """Clear serial communication log."""
    device = state.device

    def do_clear():
        device.serial_log = []
        device.log_next_id = 0

    if device.worker and device.worker.is_running():
        run_in_device_worker(device, do_clear, timeout=1.0)
    else:
        do_clear()

    return jsonify({"success": True})


@bp.route("/logs", methods=["GET"])
def api_logs():
    """Get combined tool logs, raw serial data, and slot updates for frontend."""
    tool_since = request.args.get("tool_since", 0, type=int)
    raw_since = request.args.get("raw_since", 0, type=int)
    slot_since = request.args.get("slot_since", 0, type=int)
    device = state.device

    # Get tool logs (format: {id, message})
    tool_snapshot = list(device.tool_log)
    tool_logs = []
    for entry in tool_snapshot:
        if entry["id"] >= tool_since:
            tool_logs.append(entry.get("message", ""))
    tool_next = device.tool_log_next_id

    # Get raw serial data
    raw_snapshot = list(device.raw_serial_log)
    raw_entries = [entry for entry in raw_snapshot if entry["id"] >= raw_since]
    # Combine raw data into a single string
    raw_data = "".join(entry.get("data", "") for entry in raw_entries)
    raw_next = device.raw_log_next_id

    # Check for slot updates (decoupled from request logic)
    slot_update_id = device.slot_update_id
    slot_data = None
    if slot_update_id > slot_since:
        # Slot info has been updated, include it in response
        slot_data = _build_slot_response(device, state)

    response = {
        "success": True,
        "tool_logs": tool_logs,
        "tool_next": tool_next,
        "raw_data": raw_data,
        "raw_next": raw_next,
        "slot_update_id": slot_update_id,
    }

    # Only include slot_data if there are updates
    if slot_data is not None:
        response["slot_data"] = slot_data

    return jsonify(response)


@bp.route("/raw_log", methods=["GET"])
def api_raw_log():
    """Get raw serial communication log (TX/RX)."""
    since_id = request.args.get("since", 0, type=int)
    device = state.device

    log_snapshot = list(device.raw_serial_log)
    logs = [entry for entry in log_snapshot if entry["id"] >= since_id]
    next_id = device.raw_log_next_id

    return jsonify({"success": True, "logs": logs, "next_index": next_id})


@bp.route("/raw_log/clear", methods=["POST"])
def api_raw_log_clear():
    """Clear raw serial communication log."""
    device = state.device

    def do_clear():
        device.raw_serial_log = []
        device.raw_log_next_id = 0

    if device.worker and device.worker.is_running():
        run_in_device_worker(device, do_clear, timeout=1.0)
    else:
        do_clear()

    return jsonify({"success": True})


@bp.route("/serial/send", methods=["POST"])
def api_serial_send():
    """Send raw data to serial port (for interactive terminal)."""
    data = request.json or {}
    raw_data = data.get("data", "")

    if not raw_data:
        return jsonify({"success": False, "error": "No data provided"})

    device = state.device
    if device.ser is None:
        return jsonify({"success": False, "error": "Serial port not opened"})

    worker = device.worker
    if worker and worker.is_running():
        # Write raw data directly
        worker.enqueue("write", raw_data)
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Worker not running"})


@bp.route("/log_file/start", methods=["POST"])
def api_log_file_start():
    """Start recording logs to file."""
    from services.log_recorder import log_recorder

    data = request.json or {}
    path = data.get("path", "")

    if not path:
        return jsonify({"success": False, "error": "No path provided"})

    device = state.device
    success, error = log_recorder.start(path)

    if success:
        device.log_file_enabled = True
        device.log_file_path = path
        state.save_config()

    return jsonify({"success": success, "error": error})


@bp.route("/log_file/stop", methods=["POST"])
def api_log_file_stop():
    """Stop recording logs to file."""
    from services.log_recorder import log_recorder

    device = state.device
    success, error = log_recorder.stop()

    if success:
        device.log_file_enabled = False
        state.save_config()

    return jsonify({"success": success, "error": error})


@bp.route("/log_file/status", methods=["GET"])
def api_log_file_status():
    """Get log file recording status."""
    from services.log_recorder import log_recorder

    device = state.device
    return jsonify(
        {
            "success": True,
            "enabled": log_recorder.enabled,
            "path": log_recorder.path,
            "config_enabled": device.log_file_enabled,
            "config_path": device.log_file_path,
        }
    )


@bp.route("/command", methods=["POST"])
def api_command():
    """Send raw command to device."""
    data = request.json or {}
    command = data.get("command", "")

    if not command:
        return jsonify({"success": False, "error": "Missing command"})

    device = state.device
    if device.ser is None:
        return jsonify({"success": False, "error": "Serial port not opened"})

    if not command.endswith("\n"):
        command += "\n"

    worker = device.worker
    if worker and worker.is_running():
        worker.enqueue("write", command)
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Worker not running"})

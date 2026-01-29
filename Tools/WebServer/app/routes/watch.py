#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
File Watching API routes for FPBInject Web Server.

Provides endpoints for file watcher status and auto-inject monitoring.
"""

from flask import Blueprint, jsonify, request

from core.state import state

bp = Blueprint("watch", __name__)


# Import file watcher helpers
def _get_file_watcher_helpers():
    """Lazy import to avoid circular dependency."""
    from services.file_watcher_manager import start_file_watcher, stop_file_watcher

    return start_file_watcher, stop_file_watcher


@bp.route("/watch/status", methods=["GET"])
def api_watch_status():
    """Get file watcher status."""
    changes = state.get_pending_changes()
    return jsonify(
        {
            "success": True,
            "watching": state.file_watcher is not None,
            "watch_dirs": state.device.watch_dirs,
            "pending_changes": changes,
            "auto_compile": state.device.auto_compile,
        }
    )


@bp.route("/watch/start", methods=["POST"])
def api_watch_start():
    """Start file watching."""
    _start_file_watcher, _ = _get_file_watcher_helpers()

    data = request.json or {}
    dirs = data.get("dirs", state.device.watch_dirs)

    if not dirs:
        return jsonify({"success": False, "error": "No directories to watch"})

    state.device.watch_dirs = dirs
    state.save_config()

    success = _start_file_watcher(dirs)
    return jsonify({"success": success})


@bp.route("/watch/stop", methods=["POST"])
def api_watch_stop():
    """Stop file watching."""
    _, _stop_file_watcher = _get_file_watcher_helpers()

    _stop_file_watcher()
    state.save_config()
    return jsonify({"success": True})


@bp.route("/watch/clear", methods=["POST"])
def api_watch_clear():
    """Clear pending changes."""
    state.clear_pending_changes()
    return jsonify({"success": True})


@bp.route("/watch/auto_inject_status", methods=["GET"])
def api_auto_inject_status():
    """Get auto inject status for real-time UI updates."""
    device = state.device
    return jsonify(
        {
            "success": True,
            "status": device.auto_inject_status,
            "message": device.auto_inject_message,
            "source_file": device.auto_inject_source_file,
            "modified_funcs": device.auto_inject_modified_funcs,
            "progress": device.auto_inject_progress,
            "last_update": device.auto_inject_last_update,
            "result": device.auto_inject_result,
        }
    )


@bp.route("/watch/auto_inject_reset", methods=["POST"])
def api_auto_inject_reset():
    """Reset auto inject status to idle."""
    device = state.device
    device.auto_inject_status = "idle"
    device.auto_inject_message = ""
    device.auto_inject_progress = 0
    device.auto_inject_last_update = 0
    return jsonify({"success": True})

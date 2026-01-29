#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
File Browser API routes for FPBInject Web Server.

Provides endpoints for browsing and writing files.
"""

import os

from flask import Blueprint, jsonify, request

from core.state import state

bp = Blueprint("files", __name__)


@bp.route("/browse", methods=["GET"])
def api_browse():
    """Browse filesystem for files."""
    path = request.args.get("path", os.path.expanduser("~"))
    filter_ext = request.args.get("filter", "").split(",")

    # Expand ~ to home directory
    if path.startswith("~"):
        path = os.path.expanduser(path)

    if not os.path.exists(path):
        return jsonify(
            {"success": False, "error": "Path not found", "current_path": path}
        )

    if os.path.isfile(path):
        return jsonify(
            {
                "success": True,
                "type": "file",
                "path": path,
                "current_path": os.path.dirname(path),
            }
        )

    items = []
    try:
        for name in sorted(os.listdir(path)):
            # Skip hidden files
            if name.startswith("."):
                continue
            full_path = os.path.join(path, name)
            is_dir = os.path.isdir(full_path)

            # Filter by extension for files
            if not is_dir and filter_ext and filter_ext[0]:
                if not any(name.endswith(ext) for ext in filter_ext):
                    continue

            items.append(
                {
                    "name": name,
                    "path": full_path,
                    "type": "dir" if is_dir else "file",
                }
            )
    except PermissionError:
        return jsonify(
            {"success": False, "error": "Permission denied", "current_path": path}
        )

    # Sort: directories first, then files
    items.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower()))

    return jsonify(
        {
            "success": True,
            "type": "directory",
            "current_path": path,
            "parent": os.path.dirname(path),
            "items": items,
        }
    )


@bp.route("/file/write", methods=["POST"])
def api_file_write():
    """Write content to a file."""
    data = request.json or {}
    path = data.get("path", "")
    content = data.get("content", "")

    if not path:
        return jsonify({"success": False, "error": "Path not specified"})

    # Expand ~ to home directory
    if path.startswith("~"):
        path = os.path.expanduser(path)

    # Security check: prevent writing outside of allowed directories
    # Allow writing to watch directories or common development paths
    allowed = False
    device = state.device
    watch_dirs = device.watch_dirs if device.watch_dirs else []

    # Also allow home directory and common project paths
    home_dir = os.path.expanduser("~")
    allowed_paths = watch_dirs + [home_dir]

    for allowed_path in allowed_paths:
        try:
            if os.path.commonpath([path, allowed_path]) == allowed_path:
                allowed = True
                break
        except ValueError:
            continue

    if not allowed:
        # Allow if path is under any parent directory of watch dirs
        for watch_dir in watch_dirs:
            parent = os.path.dirname(watch_dir)
            while parent and parent != "/":
                if path.startswith(parent):
                    allowed = True
                    break
                parent = os.path.dirname(parent)
            if allowed:
                break

    # For safety, always allow if under home directory
    if path.startswith(home_dir):
        allowed = True

    if not allowed:
        return jsonify({"success": False, "error": "Path not in allowed directories"})

    try:
        # Create directory if it doesn't exist
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return jsonify({"success": True, "path": path})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

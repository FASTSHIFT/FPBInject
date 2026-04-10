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


@bp.route("/file/write/binary", methods=["POST"])
def api_file_write_binary():
    """Write binary content (from hex string) to a file."""
    data = request.json or {}
    path = data.get("path", "")
    hex_data = data.get("hex_data", "")

    if not path:
        return jsonify({"success": False, "error": "Path not specified"})

    if not hex_data:
        return jsonify({"success": False, "error": "No data to write"})

    # Expand ~ to home directory
    if path.startswith("~"):
        path = os.path.expanduser(path)

    # Reuse the same security check as text file write
    allowed = False
    device = state.device
    watch_dirs = device.watch_dirs if device.watch_dirs else []

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
        for watch_dir in watch_dirs:
            parent = os.path.dirname(watch_dir)
            while parent and parent != "/":
                if path.startswith(parent):
                    allowed = True
                    break
                parent = os.path.dirname(parent)
            if allowed:
                break

    if path.startswith(home_dir):
        allowed = True

    if not allowed:
        return jsonify({"success": False, "error": "Path not in allowed directories"})

    try:
        # Convert hex string to bytes
        clean_hex = hex_data.replace(" ", "").replace("\n", "")
        binary_data = bytes.fromhex(clean_hex)

        # Create directory if it doesn't exist
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(path, "wb") as f:
            f.write(binary_data)

        return jsonify({"success": True, "path": path, "size": len(binary_data)})
    except ValueError as e:
        return jsonify({"success": False, "error": f"Invalid hex data: {e}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/convert/lvgl-to-png", methods=["POST"])
def api_convert_lvgl_to_png():
    """Convert LVGL binary image to PNG using icu CLI tool.

    JSON body:
        data: base64-encoded LVGL binary image data

    Returns:
        JSON with base64-encoded PNG data
    """
    import base64
    import shutil
    import subprocess

    data = request.json or {}
    b64_data = data.get("data", "")

    if not b64_data:
        return jsonify({"success": False, "error": "No data provided"})

    # Check if icu tool is available
    icu_path = shutil.which("icu")
    if not icu_path:
        return jsonify({"success": False, "error": "icu tool not installed"})

    try:
        bin_data = base64.b64decode(b64_data)
    except Exception as e:
        return jsonify({"success": False, "error": f"Invalid base64 data: {e}"})

    try:
        result = subprocess.run(
            [
                icu_path,
                "convert",
                "/dev/stdin",
                "-f",
                "lvgl-v9",
                "-F",
                "png",
                "--stdout",
            ],
            input=bin_data,
            capture_output=True,
            timeout=10,
        )

        if result.returncode != 0 or not result.stdout:
            error_msg = result.stderr.decode("utf-8", errors="replace").strip()
            return jsonify(
                {"success": False, "error": error_msg or "Conversion failed"}
            )

        png_b64 = base64.b64encode(result.stdout).decode("ascii")
        return jsonify({"success": True, "data": png_b64, "size": len(result.stdout)})

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Conversion timed out"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

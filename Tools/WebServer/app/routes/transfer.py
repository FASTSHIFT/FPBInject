#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
File Transfer API routes for FPBInject Web Server.

Provides endpoints for file upload/download between PC and embedded device.
"""

import json
import logging
import queue
import threading

from flask import Blueprint, Response, jsonify, request

from core.file_transfer import FileTransfer
from core.state import state
from services.device_worker import run_in_device_worker

bp = Blueprint("transfer", __name__)
logger = logging.getLogger(__name__)


def _get_helpers():
    """Lazy import to avoid circular dependency."""
    from routes import get_fpb_inject
    from core.state import state

    def add_tool_log(msg):
        state.device.add_tool_log(msg)

    return add_tool_log, get_fpb_inject


def _run_serial_op(func, timeout=10.0):
    """Run a serial operation in the device worker thread."""
    device = state.device
    result = {"error": None, "data": None}

    def wrapper():
        try:
            result["data"] = func()
        except Exception as e:
            result["error"] = str(e)
            logger.exception(f"Serial operation error: {e}")

    if not run_in_device_worker(device, wrapper, timeout=timeout):
        return {"error": "Operation timeout - device worker not running"}

    if result["error"]:
        return {"error": result["error"]}

    return result["data"]


def _get_file_transfer():
    """Get FileTransfer instance."""
    _, get_fpb_inject = _get_helpers()
    fpb = get_fpb_inject()
    chunk_size = state.device.chunk_size or 256
    return FileTransfer(fpb, chunk_size=chunk_size)


@bp.route("/transfer/list", methods=["GET"])
def api_transfer_list():
    """
    List directory contents on device.

    Query params:
        path: Directory path on device (default: "/")

    Returns:
        JSON with entries list
    """
    add_tool_log, _ = _get_helpers()
    path = request.args.get("path", "/")

    ft = _get_file_transfer()

    def do_list():
        ft.fpb.enter_fl_mode()
        try:
            success, entries = ft.flist(path)
            return {"success": success, "entries": entries, "path": path}
        finally:
            ft.fpb.exit_fl_mode()

    result = _run_serial_op(do_list, timeout=10.0)

    if "error" in result and result.get("error"):
        add_tool_log(f"[ERROR] List failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    return jsonify(result)


@bp.route("/transfer/stat", methods=["GET"])
def api_transfer_stat():
    """
    Get file/directory status on device.

    Query params:
        path: File path on device

    Returns:
        JSON with file stat info
    """
    add_tool_log, _ = _get_helpers()
    path = request.args.get("path")

    if not path:
        return jsonify({"success": False, "error": "Path not specified"})

    ft = _get_file_transfer()

    def do_stat():
        ft.fpb.enter_fl_mode()
        try:
            success, stat_info = ft.fstat(path)
            return {"success": success, "stat": stat_info, "path": path}
        finally:
            ft.fpb.exit_fl_mode()

    result = _run_serial_op(do_stat, timeout=5.0)

    if "error" in result and result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    return jsonify(result)


@bp.route("/transfer/mkdir", methods=["POST"])
def api_transfer_mkdir():
    """
    Create directory on device.

    JSON body:
        path: Directory path to create

    Returns:
        JSON with success status
    """
    add_tool_log, _ = _get_helpers()
    data = request.json or {}
    path = data.get("path")

    if not path:
        return jsonify({"success": False, "error": "Path not specified"})

    ft = _get_file_transfer()

    def do_mkdir():
        ft.fpb.enter_fl_mode()
        try:
            success, msg = ft.fmkdir(path)
            return {"success": success, "message": msg}
        finally:
            ft.fpb.exit_fl_mode()

    result = _run_serial_op(do_mkdir, timeout=5.0)

    if "error" in result and result.get("error"):
        add_tool_log(f"[ERROR] Mkdir failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    if result.get("success"):
        add_tool_log(f"[SUCCESS] Created directory: {path}")

    return jsonify(result)


@bp.route("/transfer/delete", methods=["POST"])
def api_transfer_delete():
    """
    Delete file on device.

    JSON body:
        path: File path to delete

    Returns:
        JSON with success status
    """
    add_tool_log, _ = _get_helpers()
    data = request.json or {}
    path = data.get("path")

    if not path:
        return jsonify({"success": False, "error": "Path not specified"})

    ft = _get_file_transfer()

    def do_delete():
        ft.fpb.enter_fl_mode()
        try:
            success, msg = ft.fremove(path)
            return {"success": success, "message": msg}
        finally:
            ft.fpb.exit_fl_mode()

    result = _run_serial_op(do_delete, timeout=5.0)

    if "error" in result and result.get("error"):
        add_tool_log(f"[ERROR] Delete failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    if result.get("success"):
        add_tool_log(f"[SUCCESS] Deleted: {path}")

    return jsonify(result)


@bp.route("/transfer/upload", methods=["POST"])
def api_transfer_upload():
    """
    Upload file to device with streaming progress.

    Form data:
        file: File to upload
        remote_path: Destination path on device

    Returns:
        SSE stream with progress updates including speed and ETA
    """
    import time

    add_tool_log, _ = _get_helpers()

    # Get file from request
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"})

    file = request.files["file"]
    remote_path = request.form.get("remote_path")

    if not remote_path:
        return jsonify({"success": False, "error": "Remote path not specified"})

    # Read file data
    file_data = file.read()
    total_size = len(file_data)

    add_tool_log(
        f"[UPLOAD] Starting upload: {file.filename} -> {remote_path} ({total_size} bytes)"
    )

    progress_queue = queue.Queue()

    def upload_task():
        ft = _get_file_transfer()
        start_time = time.time()
        last_time = start_time
        last_bytes = 0

        def progress_cb(uploaded, total):
            nonlocal last_time, last_bytes
            now = time.time()
            elapsed = now - start_time
            interval = now - last_time

            # Calculate speed (bytes per second)
            if interval > 0.1:  # Update speed every 100ms
                speed = (uploaded - last_bytes) / interval
                last_time = now
                last_bytes = uploaded
            else:
                speed = uploaded / elapsed if elapsed > 0 else 0

            # Calculate ETA
            remaining = total - uploaded
            eta = remaining / speed if speed > 0 else 0

            progress_queue.put(
                {
                    "type": "progress",
                    "uploaded": uploaded,
                    "total": total,
                    "percent": round((uploaded / total) * 100, 1) if total > 0 else 0,
                    "speed": round(speed, 1),
                    "eta": round(eta, 1),
                    "elapsed": round(elapsed, 1),
                }
            )

        def do_upload():
            ft.fpb.enter_fl_mode()
            try:
                success, msg = ft.upload(file_data, remote_path, progress_cb)
                elapsed = time.time() - start_time
                avg_speed = total_size / elapsed if elapsed > 0 else 0

                if success:
                    add_tool_log(
                        f"[SUCCESS] Upload complete: {remote_path} "
                        f"({total_size} bytes in {elapsed:.1f}s, {avg_speed:.0f} B/s)"
                    )
                    progress_queue.put(
                        {
                            "type": "result",
                            "success": True,
                            "message": msg,
                            "elapsed": round(elapsed, 2),
                            "avg_speed": round(avg_speed, 1),
                        }
                    )
                else:
                    add_tool_log(f"[ERROR] Upload failed: {msg}")
                    progress_queue.put(
                        {"type": "result", "success": False, "error": msg}
                    )
            finally:
                ft.fpb.exit_fl_mode()
                progress_queue.put(None)

        if not run_in_device_worker(state.device, do_upload, timeout=120.0):
            progress_queue.put(
                {"type": "result", "success": False, "error": "Device worker timeout"}
            )
            progress_queue.put(None)

    thread = threading.Thread(target=upload_task, daemon=True)
    thread.start()

    def generate():
        while True:
            try:
                item = progress_queue.get(timeout=60)
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "close",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/transfer/download", methods=["POST"])
def api_transfer_download():
    """
    Download file from device with streaming progress.

    JSON body:
        remote_path: Source path on device

    Returns:
        SSE stream with progress updates including speed and ETA
    """
    import time

    add_tool_log, _ = _get_helpers()

    data = request.json or {}
    remote_path = data.get("remote_path")

    if not remote_path:
        return jsonify({"success": False, "error": "Remote path not specified"})

    add_tool_log(f"[DOWNLOAD] Starting download: {remote_path}")

    progress_queue = queue.Queue()

    def download_task():
        ft = _get_file_transfer()
        start_time = time.time()
        last_time = start_time
        last_bytes = 0

        def progress_cb(downloaded, total):
            nonlocal last_time, last_bytes
            now = time.time()
            elapsed = now - start_time
            interval = now - last_time

            # Calculate speed (bytes per second)
            if interval > 0.1:  # Update speed every 100ms
                speed = (downloaded - last_bytes) / interval
                last_time = now
                last_bytes = downloaded
            else:
                speed = downloaded / elapsed if elapsed > 0 else 0

            # Calculate ETA
            remaining = total - downloaded
            eta = remaining / speed if speed > 0 else 0

            progress_queue.put(
                {
                    "type": "progress",
                    "downloaded": downloaded,
                    "total": total,
                    "percent": round((downloaded / total) * 100, 1) if total > 0 else 0,
                    "speed": round(speed, 1),
                    "eta": round(eta, 1),
                    "elapsed": round(elapsed, 1),
                }
            )

        def do_download():
            ft.fpb.enter_fl_mode()
            try:
                success, file_data, msg = ft.download(remote_path, progress_cb)
                elapsed = time.time() - start_time

                if success:
                    import base64

                    b64_data = base64.b64encode(file_data).decode("ascii")
                    avg_speed = len(file_data) / elapsed if elapsed > 0 else 0
                    add_tool_log(
                        f"[SUCCESS] Download complete: {remote_path} "
                        f"({len(file_data)} bytes in {elapsed:.1f}s, {avg_speed:.0f} B/s)"
                    )
                    progress_queue.put(
                        {
                            "type": "result",
                            "success": True,
                            "message": msg,
                            "data": b64_data,
                            "size": len(file_data),
                            "elapsed": round(elapsed, 2),
                            "avg_speed": round(avg_speed, 1),
                        }
                    )
                else:
                    add_tool_log(f"[ERROR] Download failed: {msg}")
                    progress_queue.put(
                        {"type": "result", "success": False, "error": msg}
                    )
            finally:
                ft.fpb.exit_fl_mode()
                progress_queue.put(None)

        if not run_in_device_worker(state.device, do_download, timeout=120.0):
            progress_queue.put(
                {"type": "result", "success": False, "error": "Device worker timeout"}
            )
            progress_queue.put(None)

    thread = threading.Thread(target=download_task, daemon=True)
    thread.start()

    def generate():
        while True:
            try:
                item = progress_queue.get(timeout=60)
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "close",
            "X-Accel-Buffering": "no",
        },
    )

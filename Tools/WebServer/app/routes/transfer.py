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
from utils.crc import crc16
from services.device_worker import run_in_device_worker

bp = Blueprint("transfer", __name__)
logger = logging.getLogger(__name__)

# Global transfer cancel flag
_transfer_cancelled = threading.Event()


def _get_helpers():
    """Lazy import to avoid circular dependency."""
    from routes import get_fpb_inject
    from core.state import state, tool_log

    def log_info(msg):
        tool_log(state.device, "INFO", msg)

    def log_success(msg):
        tool_log(state.device, "SUCCESS", msg)

    def log_error(msg):
        tool_log(state.device, "ERROR", msg)

    def log_warn(msg):
        tool_log(state.device, "WARN", msg)

    return log_info, log_success, log_error, log_warn, get_fpb_inject


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


def _get_file_transfer(log_callback=None):
    """Get FileTransfer instance."""
    *_, get_fpb_inject = _get_helpers()
    fpb = get_fpb_inject()
    chunk_size = state.device.chunk_size or 256
    max_retries = (
        state.device.transfer_max_retries
        if hasattr(state.device, "transfer_max_retries")
        else 10
    )
    return FileTransfer(
        fpb, chunk_size=chunk_size, max_retries=max_retries, log_callback=log_callback
    )


@bp.route("/transfer/cancel", methods=["POST"])
def api_transfer_cancel():
    """
    Cancel ongoing file transfer.

    Returns:
        JSON with success status
    """
    log_info, _, _, _, _ = _get_helpers()
    _transfer_cancelled.set()
    log_info("Cancel requested")
    return jsonify({"success": True, "message": "Cancel requested"})


@bp.route("/transfer/list", methods=["GET"])
def api_transfer_list():
    """
    List directory contents on device.

    Query params:
        path: Directory path on device (default: "/")

    Returns:
        JSON with entries list
    """
    _, _, log_error, _, _ = _get_helpers()
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
        log_error(f"List failed: {result['error']}")
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
    _, log_success, log_error, _, _ = _get_helpers()
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
        log_error(f"Mkdir failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    if result.get("success"):
        log_success(f"Created directory: {path}")

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
    _, log_success, log_error, _, _ = _get_helpers()
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
        log_error(f"Delete failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    if result.get("success"):
        log_success(f"Deleted: {path}")

    return jsonify(result)


@bp.route("/transfer/rename", methods=["POST"])
def api_transfer_rename():
    """
    Rename file or directory on device.

    JSON body:
        old_path: Current path
        new_path: New path

    Returns:
        JSON with success status
    """
    _, log_success, log_error, _, _ = _get_helpers()
    data = request.json or {}
    old_path = data.get("old_path")
    new_path = data.get("new_path")

    if not old_path:
        return jsonify({"success": False, "error": "Old path not specified"})
    if not new_path:
        return jsonify({"success": False, "error": "New path not specified"})

    ft = _get_file_transfer()

    def do_rename():
        ft.fpb.enter_fl_mode()
        try:
            success, msg = ft.frename(old_path, new_path)
            return {"success": success, "message": msg}
        finally:
            ft.fpb.exit_fl_mode()

    result = _run_serial_op(do_rename, timeout=5.0)

    if "error" in result and result.get("error"):
        log_error(f"Rename failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    if result.get("success"):
        log_success(f"Renamed: {old_path} -> {new_path}")

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

    log_info, log_success, log_error, log_warn, _ = _get_helpers()

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

    log_info(f"Starting upload: {file.filename} -> {remote_path} ({total_size} bytes)")

    # Clear cancel flag at start
    _transfer_cancelled.clear()

    progress_queue = queue.Queue()
    # Track last activity time for timeout
    last_activity = {"time": time.time()}

    def upload_task():
        def log_callback(msg):
            """Send log messages to frontend via progress queue."""
            progress_queue.put({"type": "log", "message": msg})
            # Note: Don't call log_xxx here to avoid duplicate logs
            # Frontend will display via SSE, backend tool_log is separate channel

        ft = _get_file_transfer(log_callback=log_callback)
        start_time = time.time()
        last_time = start_time
        last_bytes = 0
        cancelled = False

        def progress_cb(uploaded, total):
            nonlocal last_time, last_bytes, cancelled

            # Update activity time
            last_activity["time"] = time.time()

            # Check for cancel
            if _transfer_cancelled.is_set():
                cancelled = True
                return  # Don't raise, just set flag

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
                    "stats": ft.get_stats(),
                }
            )

        def do_upload():
            nonlocal cancelled
            ft.fpb.enter_fl_mode()
            try:
                # Manual upload with cancel check
                # Use "rw" mode to allow CRC verification after write
                success, msg = ft.fopen(remote_path, "rw")
                if not success:
                    log_error(f"Upload failed to open: {msg}")
                    progress_queue.put(
                        {
                            "type": "result",
                            "success": False,
                            "error": f"Failed to open: {msg}",
                        }
                    )
                    return

                uploaded = 0
                chunk_size = ft.chunk_size
                ft.reset_stats()  # Reset stats before transfer
                while uploaded < total_size:
                    # Check cancel before each chunk
                    if _transfer_cancelled.is_set():
                        cancelled = True
                        ft.fclose()
                        log_info("Upload cancelled by user")
                        progress_queue.put(
                            {
                                "type": "result",
                                "success": False,
                                "error": "Cancelled",
                                "cancelled": True,
                            }
                        )
                        return

                    chunk = file_data[uploaded : uploaded + chunk_size]
                    success, msg = ft.fwrite(chunk, current_offset=uploaded)
                    if not success:
                        ft.fclose()
                        log_error(f"Upload write failed: {msg}")
                        progress_queue.put(
                            {
                                "type": "result",
                                "success": False,
                                "error": f"Write failed: {msg}",
                            }
                        )
                        return

                    uploaded += len(chunk)
                    progress_cb(uploaded, total_size)

                    if cancelled:
                        ft.fclose()
                        return

                # Verify CRC if enabled
                if state.device.verify_crc and total_size > 0:
                    expected_crc = crc16(file_data)
                    success, dev_size, dev_crc = ft.fcrc(total_size)
                    if not success:
                        log_warn("CRC verification failed: could not get device CRC")
                        progress_queue.put(
                            {
                                "type": "crc_warning",
                                "message": "CRC verification failed: could not get device CRC",
                            }
                        )
                    elif dev_size != total_size:
                        ft.fclose()
                        error_msg = f"Size mismatch: expected {total_size}, device has {dev_size}"
                        log_error(error_msg)
                        progress_queue.put(
                            {
                                "type": "result",
                                "success": False,
                                "error": error_msg,
                                "crc_error": True,
                            }
                        )
                        return
                    elif dev_crc != expected_crc:
                        ft.fclose()
                        error_msg = f"CRC mismatch: expected 0x{expected_crc:04X}, device has 0x{dev_crc:04X}"
                        log_error(error_msg)
                        progress_queue.put(
                            {
                                "type": "result",
                                "success": False,
                                "error": error_msg,
                                "crc_error": True,
                            }
                        )
                        return
                    else:
                        log_info(f"CRC verified: 0x{dev_crc:04X}")

                success, msg = ft.fclose()
                elapsed = time.time() - start_time
                avg_speed = total_size / elapsed if elapsed > 0 else 0
                transfer_stats = ft.get_stats()

                log_success(
                    f"Upload complete: {remote_path} "
                    f"({total_size} bytes in {elapsed:.1f}s, {avg_speed:.0f} B/s, "
                    f"loss rate: {transfer_stats['packet_loss_rate']}%)"
                )
                progress_queue.put(
                    {
                        "type": "result",
                        "success": True,
                        "message": f"Uploaded {total_size} bytes",
                        "elapsed": round(elapsed, 2),
                        "avg_speed": round(avg_speed, 1),
                        "stats": transfer_stats,
                    }
                )
            finally:
                ft.fpb.exit_fl_mode()
                progress_queue.put(None)

        # Use very long timeout - actual timeout is managed by activity tracking
        if not run_in_device_worker(state.device, do_upload, timeout=86400.0):
            progress_queue.put(
                {
                    "type": "result",
                    "success": False,
                    "error": "Device worker not running",
                }
            )
            progress_queue.put(None)

    thread = threading.Thread(target=upload_task, daemon=True)
    thread.start()

    def generate():
        # Inactivity timeout: 120 seconds without any progress
        INACTIVITY_TIMEOUT = 120.0
        while True:
            try:
                item = progress_queue.get(timeout=5.0)
                if item is None:
                    break
                # Update activity time on any message
                last_activity["time"] = time.time()
                yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                # Check if transfer is still active
                inactive_time = time.time() - last_activity["time"]
                if inactive_time > INACTIVITY_TIMEOUT:
                    # No activity for too long, timeout
                    yield f"data: {json.dumps({'type': 'result', 'success': False, 'error': 'Transfer timeout - no activity'})}\n\n"
                    break
                # Send heartbeat to keep connection alive
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

    log_info, log_success, log_error, log_warn, _ = _get_helpers()

    data = request.json or {}
    remote_path = data.get("remote_path")

    if not remote_path:
        return jsonify({"success": False, "error": "Remote path not specified"})

    log_info(f"Starting download: {remote_path}")

    # Clear cancel flag at start
    _transfer_cancelled.clear()

    progress_queue = queue.Queue()
    # Track last activity time for timeout
    last_activity = {"time": time.time()}

    def download_task():
        def log_callback(msg):
            """Send log messages to frontend via progress queue."""
            progress_queue.put({"type": "log", "message": msg})
            # Note: Don't call log_xxx here to avoid duplicate logs
            # Frontend will display via SSE, backend tool_log is separate channel

        ft = _get_file_transfer(log_callback=log_callback)
        start_time = time.time()
        last_time = start_time
        last_bytes = 0
        cancelled = False

        def progress_cb(downloaded, total):
            nonlocal last_time, last_bytes, cancelled

            # Update activity time
            last_activity["time"] = time.time()

            # Check for cancel
            if _transfer_cancelled.is_set():
                cancelled = True
                return  # Don't raise, just set flag

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
                    "stats": ft.get_stats(),
                }
            )

        def do_download():
            nonlocal cancelled
            ft.fpb.enter_fl_mode()
            try:
                # Get file size first
                success, stat = ft.fstat(remote_path)
                if not success:
                    log_error(
                        f"Download failed to stat: {stat.get('error', 'unknown')}"
                    )
                    progress_queue.put(
                        {
                            "type": "result",
                            "success": False,
                            "error": f"Failed to stat: {stat.get('error', 'unknown')}",
                        }
                    )
                    return

                total_size = stat.get("size", 0)
                if stat.get("type") == "dir":
                    progress_queue.put(
                        {
                            "type": "result",
                            "success": False,
                            "error": "Cannot download directory",
                        }
                    )
                    return

                if total_size == 0:
                    progress_queue.put(
                        {
                            "type": "result",
                            "success": False,
                            "error": "File is empty",
                        }
                    )
                    return

                # Open file for reading
                success, msg = ft.fopen(remote_path, "r")
                if not success:
                    log_error(f"Download failed to open: {msg}")
                    progress_queue.put(
                        {
                            "type": "result",
                            "success": False,
                            "error": f"Failed to open: {msg}",
                        }
                    )
                    return

                file_data = b""
                chunk_size = ft.chunk_size
                current_offset = 0
                ft.reset_stats()  # Reset stats before transfer
                while True:
                    # Check cancel before each chunk
                    if _transfer_cancelled.is_set():
                        cancelled = True
                        ft.fclose()
                        log_info("Download cancelled by user")
                        progress_queue.put(
                            {
                                "type": "result",
                                "success": False,
                                "error": "Cancelled",
                                "cancelled": True,
                            }
                        )
                        return

                    success, chunk, msg = ft.fread(
                        chunk_size, current_offset=current_offset
                    )
                    if not success:
                        ft.fclose()
                        log_error(f"Download read failed: {msg}")
                        progress_queue.put(
                            {
                                "type": "result",
                                "success": False,
                                "error": f"Read failed: {msg}",
                            }
                        )
                        return

                    if msg == "EOF" or len(chunk) == 0:
                        break

                    file_data += chunk
                    current_offset += len(chunk)
                    progress_cb(len(file_data), total_size)

                    if cancelled:
                        ft.fclose()
                        return

                # Verify CRC if enabled
                if state.device.verify_crc and len(file_data) > 0:
                    local_crc = crc16(file_data)
                    success, dev_size, dev_crc = ft.fcrc(len(file_data))
                    if not success:
                        log_warn("CRC verification failed: could not get device CRC")
                        progress_queue.put(
                            {
                                "type": "crc_warning",
                                "message": "CRC verification failed: could not get device CRC",
                            }
                        )
                    elif dev_crc != local_crc:
                        ft.fclose()
                        error_msg = f"CRC mismatch: local 0x{local_crc:04X}, device 0x{dev_crc:04X}"
                        log_error(error_msg)
                        progress_queue.put(
                            {
                                "type": "result",
                                "success": False,
                                "error": error_msg,
                                "crc_error": True,
                            }
                        )
                        return
                    else:
                        log_info(f"CRC verified: 0x{dev_crc:04X}")

                ft.fclose()
                elapsed = time.time() - start_time

                import base64

                b64_data = base64.b64encode(file_data).decode("ascii")
                avg_speed = len(file_data) / elapsed if elapsed > 0 else 0
                transfer_stats = ft.get_stats()

                log_success(
                    f"Download complete: {remote_path} "
                    f"({len(file_data)} bytes in {elapsed:.1f}s, {avg_speed:.0f} B/s, "
                    f"loss rate: {transfer_stats['packet_loss_rate']}%)"
                )
                progress_queue.put(
                    {
                        "type": "result",
                        "success": True,
                        "message": f"Downloaded {len(file_data)} bytes",
                        "data": b64_data,
                        "size": len(file_data),
                        "elapsed": round(elapsed, 2),
                        "avg_speed": round(avg_speed, 1),
                        "stats": transfer_stats,
                    }
                )
            finally:
                ft.fpb.exit_fl_mode()
                progress_queue.put(None)

        # Use very long timeout - actual timeout is managed by activity tracking
        if not run_in_device_worker(state.device, do_download, timeout=86400.0):
            progress_queue.put(
                {
                    "type": "result",
                    "success": False,
                    "error": "Device worker not running",
                }
            )
            progress_queue.put(None)

    thread = threading.Thread(target=download_task, daemon=True)
    thread.start()

    def generate():
        # Inactivity timeout: 120 seconds without any progress
        INACTIVITY_TIMEOUT = 120.0
        while True:
            try:
                item = progress_queue.get(timeout=5.0)
                if item is None:
                    break
                # Update activity time on any message
                last_activity["time"] = time.time()
                yield f"data: {json.dumps(item)}\n\n"
            except queue.Empty:
                # Check if transfer is still active
                inactive_time = time.time() - last_activity["time"]
                if inactive_time > INACTIVITY_TIMEOUT:
                    # No activity for too long, timeout
                    yield f"data: {json.dumps({'type': 'result', 'success': False, 'error': 'Transfer timeout - no activity'})}\n\n"
                    break
                # Send heartbeat to keep connection alive
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

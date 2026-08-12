#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPB Inject Operations API routes for FPBInject Web Server.

Provides endpoints for FPB injection, unpatch, and device info.
All serial operations are executed in the device worker thread for thread safety.
"""

import logging
import os
import queue
import threading
import time as _time

from flask import Blueprint, jsonify, request

from fpbinject.app.utils.sse import sse_response
from fpbinject.core.state import state
from fpbinject.services.device_worker import run_in_device_worker

bp = Blueprint("fpb", __name__)
logger = logging.getLogger(__name__)

# Global inject cancel flag (mirrors _transfer_cancelled in transfer.py)
_inject_cancelled = threading.Event()


def _get_helpers():
    """Lazy import to avoid circular dependency."""
    from fpbinject.routes import get_fpb_inject
    from fpbinject.utils.helpers import build_slot_response
    from fpbinject.core.state import state, tool_log

    def log_info(msg):
        tool_log(state.device, "INFO", msg)

    def log_success(msg):
        tool_log(state.device, "SUCCESS", msg)

    def log_error(msg):
        tool_log(state.device, "ERROR", msg)

    def log_warn(msg):
        tool_log(state.device, "WARN", msg)

    def _build_slot_response(device, app_state):
        """Wrapper to call build_slot_response with get_fpb_inject."""
        return build_slot_response(device, app_state, get_fpb_inject)

    return (
        log_info,
        log_success,
        log_error,
        log_warn,
        get_fpb_inject,
        _build_slot_response,
    )


def _run_serial_op(func, timeout=10.0):
    """
    Run a serial operation in the device worker thread.

    Args:
        func: Function to execute (should return a result dict)
        timeout: Maximum time to wait for completion

    Returns:
        Result dict from func, or error dict on timeout/failure
    """
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


@bp.route("/fpb/ping", methods=["POST"])
def api_fpb_ping():
    """Ping device to test connection."""
    _, _, _, _, get_fpb_inject, _ = _get_helpers()
    fpb = get_fpb_inject()

    def do_ping():
        success, msg = fpb.ping()
        return {"success": success, "message": msg}

    result = _run_serial_op(do_ping, timeout=5.0)
    if "error" in result and result.get("error"):
        return jsonify({"success": False, "message": result["error"]})
    return jsonify(result)


@bp.route("/fpb/test-serial", methods=["POST"])
def api_fpb_test_serial():
    """
    Test serial throughput with 3-phase probing.

    Phase 1: TX Fragment probe - detect if fragmentation is needed.
    Phase 2: Upload chunk probe - find device shell buffer limit.
    Phase 3: Download chunk probe - find max reliable download size.
    """
    log_info, log_success, log_error, _, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    start_size = data.get("start_size", 16)
    max_size = data.get("max_size", 4096)
    timeout = data.get("timeout", 2.0)

    fpb = get_fpb_inject()

    log_info("Starting 3-phase serial throughput test...")

    def do_test():
        return fpb.test_serial_throughput(
            start_size=start_size, max_size=max_size, timeout=timeout
        )

    result = _run_serial_op(do_test, timeout=60.0)

    if "error" in result and result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    if result.get("success"):
        # Phase 1 summary
        if result.get("fragment_needed"):
            log_info("Phase 1: TX fragmentation may be needed")
        else:
            log_info("Phase 1: TX fragmentation not needed")

        # Phase 2 summary
        max_working = result.get("max_working_size", 0)
        failed_at = result.get("failed_size", 0)
        rec_upload = result.get("recommended_upload_chunk_size", 64)

        if failed_at > 0:
            log_info(f"Phase 2: Upload max={max_working}B, failed at {failed_at}B")
        else:
            log_success(f"Phase 2: All upload tests passed up to {max_working}B")
        log_info(f"Recommended upload chunk: {rec_upload}B")

        # Phase 3 summary
        rec_download = result.get("recommended_download_chunk_size", 1024)
        phases = result.get("phases", {})
        dl_phase = phases.get("download", {})
        if dl_phase.get("skipped"):
            log_info(f"Phase 3: Skipped ({dl_phase.get('skip_reason', 'unknown')})")
        else:
            dl_max = dl_phase.get("max_working_size", 0)
            dl_fail = dl_phase.get("failed_size", 0)
            if dl_fail > 0:
                log_info(f"Phase 3: Download max={dl_max}B, failed at {dl_fail}B")
            else:
                log_success(f"Phase 3: All download tests passed up to {dl_max}B")
        log_info(f"Recommended download chunk: {rec_download}B")

    return jsonify(result)


@bp.route("/fpb/info", methods=["GET"])
def api_fpb_info():
    """Get device info including slot states."""
    _, _, _, _, get_fpb_inject, _build_slot_response = _get_helpers()

    fpb = get_fpb_inject()

    def do_info():
        info, error = fpb.info()
        fpb.exit_fl_mode()
        return {"info": info, "error": error}

    result = _run_serial_op(do_info, timeout=5.0)

    if "error" in result and result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    info = result.get("info")
    error = result.get("error") if isinstance(result, dict) else None

    if error:
        return jsonify({"success": False, "error": error})

    # Store device info
    if info:
        state.device.device_info = info

    # Check build time mismatch between device and ELF
    build_time_mismatch = False
    device_build_time = info.get("build_time") if info else None
    elf_build_time = None

    if state.device.elf_path and os.path.exists(state.device.elf_path):
        elf_build_time = fpb.get_elf_build_time(state.device.elf_path)

    if device_build_time and elf_build_time:
        if device_build_time.strip() != elf_build_time.strip():
            build_time_mismatch = True
            logger.warning(
                f"Build time mismatch! Device: '{device_build_time}', ELF: '{elf_build_time}'"
            )

    # Use shared helper to build response
    slot_response = _build_slot_response(state.device, state)

    if slot_response is None:
        return jsonify({"success": False, "error": "No device info available"})

    # Get FPB version from info (default to v1)
    fpb_version = info.get("fpb_version", 1) if info else 1

    # Check version compatibility (compare major.minor only)
    version_mismatch = False
    device_version = None
    host_version = None
    if info and info.get("version_string"):
        import re as _re

        from fpbinject.version import VERSION_MAJOR, VERSION_MINOR

        match = _re.search(r"v(\d+)\.(\d+)", info["version_string"])
        if match:
            dev_major, dev_minor = int(match.group(1)), int(match.group(2))
            device_version = f"{dev_major}.{dev_minor}"
            host_version = f"{VERSION_MAJOR}.{VERSION_MINOR}"
            if (dev_major, dev_minor) != (VERSION_MAJOR, VERSION_MINOR):
                version_mismatch = True
                logger.warning(
                    f"Version mismatch! Device: {device_version}, "
                    f"Host: {host_version}"
                )

    return jsonify(
        {
            "success": True,
            "info": info,
            "slots": slot_response["slots"],
            "memory": slot_response["memory"],
            "fpb_version": fpb_version,
            "build_time_mismatch": build_time_mismatch,
            "device_build_time": device_build_time,
            "elf_build_time": elf_build_time,
            "version_mismatch": version_mismatch,
            "device_version": device_version,
            "host_version": host_version,
        }
    )


@bp.route("/fpb/unpatch", methods=["POST"])
def api_fpb_unpatch():
    """Clear FPB patch. Use all=True to clear all patches and free memory."""
    log_info, _, _, _, get_fpb_inject, _ = _get_helpers()

    try:
        data = request.json or {}
        comp = data.get("comp", 0)
        clear_all = data.get("all", False)

        fpb = get_fpb_inject()

        def do_unpatch():
            return fpb.unpatch(comp=comp, all=clear_all)

        result = _run_serial_op(do_unpatch, timeout=5.0)

        if "error" in result and result.get("error"):
            return jsonify({"success": False, "message": result["error"]})

        success, msg = result

        if success:
            if clear_all:
                state.device.inject_active = False
                state.device.last_inject_target = None
                state.device.last_inject_func = None
            log_info(f"{'All slots' if clear_all else f'Slot {comp}'} cleared")

        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@bp.route("/fpb/enable", methods=["POST"])
def api_fpb_enable():
    """Enable or disable FPB patch without clearing it."""
    log_info, _, _, _, get_fpb_inject, _ = _get_helpers()

    try:
        data = request.json or {}
        comp = data.get("comp", 0)
        enable = data.get("enable", True)
        enable_all = data.get("all", False)

        fpb = get_fpb_inject()

        def do_enable():
            return fpb.enable_patch(comp=comp, enable=enable, all=enable_all)

        result = _run_serial_op(do_enable, timeout=5.0)

        if "error" in result and result.get("error"):
            return jsonify({"success": False, "message": result["error"]})

        success, msg = result

        if success:
            action = "enabled" if enable else "disabled"
            if enable_all:
                log_info(f"All patches {action}")
            else:
                log_info(f"Slot {comp} {action}")

        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@bp.route("/fpb/inject", methods=["POST"])
def api_fpb_inject():
    """Perform code injection."""
    log_info, log_success, log_error, _, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    source_content = data.get("source_content")
    target_func = data.get("target_func")
    inject_func = data.get("inject_func")
    patch_mode = data.get("patch_mode", state.device.patch_mode)
    comp = data.get("comp", -1)
    source_ext = data.get("source_ext", ".c")

    if not source_content:
        return jsonify({"success": False, "error": "Source content not provided"})

    if not target_func:
        return jsonify({"success": False, "error": "Target function not specified"})

    fpb = get_fpb_inject()

    log_info(f"Starting injection for {target_func} (mode: {patch_mode})")

    def do_inject():
        fpb.enter_fl_mode()
        try:
            success, result = fpb.inject(
                source_content=source_content,
                target_func=target_func,
                inject_func=inject_func,
                patch_mode=patch_mode,
                comp=comp,
                source_ext=source_ext,
            )
            return {"success": success, "result": result}
        finally:
            fpb.exit_fl_mode()

    result = _run_serial_op(do_inject, timeout=30.0)

    if "error" in result and result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    success = result.get("success", False)
    inject_result = result.get("result", {})

    if success:
        log_success(
            f"Injection complete: {target_func} @ slot {inject_result.get('slot', '?')}"
        )

    return jsonify({"success": success, **inject_result})


@bp.route("/fpb/inject/multi", methods=["POST"])
def api_fpb_inject_multi():
    """Perform multi-function code injection. Each inject_* function gets its own Slot."""
    log_info, log_success, log_error, _, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    source_content = data.get("source_content")
    patch_mode = data.get("patch_mode", state.device.patch_mode)
    source_ext = data.get("source_ext", ".c")

    if not source_content:
        return jsonify({"success": False, "error": "Source content not provided"})

    fpb = get_fpb_inject()

    log_info(f"Starting multi-function injection (mode: {patch_mode})")

    def do_inject_multi():
        fpb.enter_fl_mode()
        try:
            success, result = fpb.inject_multi(
                source_content=source_content,
                patch_mode=patch_mode,
                source_ext=source_ext,
            )
            return {"success": success, "result": result}
        finally:
            fpb.exit_fl_mode()

    result = _run_serial_op(do_inject_multi, timeout=60.0)

    if "error" in result and result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    success = result.get("success", False)
    inject_result = result.get("result", {})

    if success:
        successful = inject_result.get("successful_count", 0)
        total = inject_result.get("total_count", 0)
        log_success(f"Multi-injection complete: {successful}/{total} functions")

    return jsonify({"success": success, **inject_result})


@bp.route("/fpb/mem-read", methods=["POST"])
def api_fpb_mem_read():
    """Read device memory.

    JSON body:
        addr: Memory address (int)
        length: Number of bytes to read (int)
        fmt: Output format - "hex", "raw", or "u32" (default: "hex")
    """
    _, _, log_error, _, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    addr = data.get("addr", 0)
    length = data.get("length", 64)
    fmt = data.get("fmt", "hex")

    if isinstance(addr, str):
        addr = int(addr, 0)

    fpb = get_fpb_inject()

    def do_mem_read():
        fpb.enter_fl_mode()
        try:
            raw_data, msg = fpb.read_memory(addr, length)
        finally:
            fpb.exit_fl_mode()

        if raw_data is None:
            return {"success": False, "error": f"Memory read failed: {msg}"}

        result = {
            "success": True,
            "addr": f"0x{addr:08X}",
            "length": length,
            "actual_length": len(raw_data),
        }

        if fmt == "hex":
            lines = []
            for i in range(0, len(raw_data), 16):
                chunk = raw_data[i : i + 16]
                hex_part = " ".join(f"{b:02X}" for b in chunk)
                ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
                lines.append(f"0x{addr + i:08X}: {hex_part:<48s} {ascii_part}")
            result["hex_dump"] = "\n".join(lines)
        elif fmt == "raw":
            result["data"] = raw_data.hex()
        elif fmt == "u32":
            words = []
            for i in range(0, len(raw_data) - 3, 4):
                val = int.from_bytes(raw_data[i : i + 4], "little")
                words.append(f"0x{val:08X}")
            result["words"] = words

        return result

    result = _run_serial_op(do_mem_read, timeout=10.0)

    if "error" in result and result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    return jsonify(result)


@bp.route("/fpb/mem-write", methods=["POST"])
def api_fpb_mem_write():
    """Write data to device memory.

    JSON body:
        addr: Memory address (int)
        data: Hex string of data to write (e.g. "DEADBEEF")
    """
    _, _, log_error, _, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    addr = data.get("addr", 0)
    data_hex = data.get("data", "")

    if isinstance(addr, str):
        addr = int(addr, 0)

    try:
        write_data = bytes.fromhex(data_hex)
    except ValueError:
        return jsonify({"success": False, "error": f"Invalid hex data: '{data_hex}'"})

    fpb = get_fpb_inject()

    def do_mem_write():
        fpb.enter_fl_mode()
        try:
            success, error = fpb.write_memory(addr, write_data)
        finally:
            fpb.exit_fl_mode()

        if not success:
            return {"success": False, "error": f"Memory write failed: {error}"}

        return {
            "success": True,
            "addr": f"0x{addr:08X}",
            "length": len(write_data),
            "message": f"Wrote {len(write_data)} bytes to 0x{addr:08X}",
        }

    result = _run_serial_op(do_mem_write, timeout=10.0)

    if "error" in result and result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    return jsonify(result)


class _InjectCancelled(Exception):
    """Raised when injection is cancelled by user."""

    pass


def _make_inject_progress_callback(progress_queue):
    """Create a progress callback with speed/ETA calculation.

    Returns a callback ``(uploaded, total) -> None`` that pushes enriched
    progress events (speed, eta, elapsed) to *progress_queue* and raises
    :class:`_InjectCancelled` when the global cancel flag is set.
    """
    state_dict = {"start_time": 0.0, "last_time": 0.0, "last_bytes": 0}

    def callback(uploaded, total):
        # Check cancel flag
        if _inject_cancelled.is_set():
            raise _InjectCancelled("Inject cancelled by user")

        now = _time.time()

        # First chunk — initialise
        if state_dict["start_time"] == 0:
            state_dict["start_time"] = now
            state_dict["last_time"] = now
            state_dict["last_bytes"] = 0

        elapsed = now - state_dict["start_time"]
        interval = now - state_dict["last_time"]

        # Update instantaneous speed every 100 ms to avoid jitter
        if interval > 0.1:
            speed = (uploaded - state_dict["last_bytes"]) / interval
            state_dict["last_time"] = now
            state_dict["last_bytes"] = uploaded
        else:
            speed = uploaded / elapsed if elapsed > 0 else 0

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

    return callback


@bp.route("/fpb/inject/cancel", methods=["POST"])
def api_fpb_inject_cancel():
    """Cancel an ongoing injection operation."""
    log_info, _, _, _, _, _ = _get_helpers()
    _inject_cancelled.set()
    log_info("Inject cancel requested")
    return jsonify({"success": True, "message": "Cancel requested"})


@bp.route("/fpb/inject/multi/stream", methods=["POST"])
def api_fpb_inject_multi_stream():
    """Multi-function injection with per-function + per-chunk SSE progress."""
    log_info, log_success, log_error, _, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    source_content = data.get("source_content")
    patch_mode = data.get("patch_mode", state.device.patch_mode)
    source_ext = data.get("source_ext", ".c")

    if not source_content:
        return jsonify({"success": False, "error": "Source content not provided"})

    progress_queue = queue.Queue()

    progress_callback = _make_inject_progress_callback(progress_queue)

    def status_callback(event):
        progress_queue.put({"type": "status", **event})

    def inject_task():
        fpb = get_fpb_inject()
        log_info(f"Starting multi-injection stream (mode: {patch_mode})")

        def do_inject_multi():
            _inject_cancelled.clear()
            fpb.enter_fl_mode()
            try:
                progress_queue.put({"type": "status", "stage": "compiling"})

                success, result = fpb.inject_multi(
                    source_content=source_content,
                    patch_mode=patch_mode,
                    source_ext=source_ext,
                    progress_callback=progress_callback,
                    status_callback=status_callback,
                )

                if success:
                    sc = result.get("successful_count", 0)
                    tc = result.get("total_count", 0)
                    log_success(f"Multi-injection complete: {sc}/{tc} functions")
                    progress_queue.put({"type": "result", "success": True, **result})
                else:
                    progress_queue.put({"type": "result", "success": False, **result})
            except _InjectCancelled:
                log_info("Multi-injection cancelled by user")
                progress_queue.put(
                    {
                        "type": "result",
                        "success": False,
                        "error": "Cancelled",
                        "cancelled": True,
                    }
                )
            finally:
                fpb.exit_fl_mode()
                progress_queue.put(None)

        if not run_in_device_worker(state.device, do_inject_multi, timeout=120.0):
            progress_queue.put(
                {"type": "result", "success": False, "error": "Device worker timeout"}
            )
            progress_queue.put(None)

    thread = threading.Thread(target=inject_task, daemon=True)
    thread.start()

    return sse_response(progress_queue)


@bp.route("/fpb/inject/stream", methods=["POST"])
def api_fpb_inject_stream():
    """Perform code injection with streaming progress via SSE."""
    log_info, log_success, log_error, _, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    source_content = data.get("source_content")
    target_func = data.get("target_func")
    inject_func = data.get("inject_func")
    patch_mode = data.get("patch_mode", state.device.patch_mode)
    comp = data.get("comp", 0)
    source_ext = data.get("source_ext", ".c")

    if not source_content:
        return jsonify({"success": False, "error": "Source content not provided"})

    if not target_func:
        return jsonify({"success": False, "error": "Target function not specified"})

    progress_queue = queue.Queue()

    progress_callback = _make_inject_progress_callback(progress_queue)

    def inject_task():
        """Execute injection in device worker thread."""
        fpb = get_fpb_inject()
        log_info(f"Starting injection for {target_func} (mode: {patch_mode})")

        def do_inject():
            _inject_cancelled.clear()
            fpb.enter_fl_mode()
            try:
                progress_queue.put({"type": "status", "stage": "compiling"})

                success, result = fpb.inject(
                    source_content=source_content,
                    target_func=target_func,
                    inject_func=inject_func,
                    patch_mode=patch_mode,
                    comp=comp,
                    source_ext=source_ext,
                    progress_callback=progress_callback,
                )

                if success:
                    log_success(f"Injection complete: {target_func}")
                    progress_queue.put({"type": "result", "success": True, **result})
                else:
                    progress_queue.put({"type": "result", "success": False, **result})
            except _InjectCancelled:
                log_info(f"Injection cancelled for {target_func}")
                progress_queue.put(
                    {
                        "type": "result",
                        "success": False,
                        "error": "Cancelled",
                        "cancelled": True,
                    }
                )
            finally:
                fpb.exit_fl_mode()
                progress_queue.put(None)

        # Run in device worker for thread safety
        if not run_in_device_worker(state.device, do_inject, timeout=60.0):
            progress_queue.put(
                {"type": "result", "success": False, "error": "Device worker timeout"}
            )
            progress_queue.put(None)

    # Start the injection task in a separate thread that will queue work to device worker
    thread = threading.Thread(target=inject_task, daemon=True)
    thread.start()

    return sse_response(progress_queue)

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPB Inject Operations API routes for FPBInject Web Server.

Provides endpoints for FPB injection, unpatch, and device info.
All serial operations are executed in the device worker thread for thread safety.
"""

import json
import logging
import os
import queue
import threading

from flask import Blueprint, Response, jsonify, request

from core.state import state
from services.device_worker import run_in_device_worker

bp = Blueprint("fpb", __name__)
logger = logging.getLogger(__name__)


def _get_helpers():
    """Lazy import to avoid circular dependency."""
    from routes import get_fpb_inject
    from utils.helpers import build_slot_response
    from core.state import state

    def add_tool_log(msg):
        state.device.add_tool_log(msg)

    def _build_slot_response(device, app_state):
        """Wrapper to call build_slot_response with get_fpb_inject."""
        return build_slot_response(device, app_state, get_fpb_inject)

    return add_tool_log, get_fpb_inject, _build_slot_response


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
    _, get_fpb_inject, _ = _get_helpers()
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
    Test serial throughput to find max single-transfer size.

    Uses x2 stepping to probe device's receive buffer limit.
    Returns max working size and recommended chunk size.
    """
    add_tool_log, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    start_size = data.get("start_size", 16)
    max_size = data.get("max_size", 4096)
    timeout = data.get("timeout", 2.0)

    fpb = get_fpb_inject()

    add_tool_log("[TEST] Starting serial throughput test...")

    def do_test():
        return fpb.test_serial_throughput(
            start_size=start_size, max_size=max_size, timeout=timeout
        )

    result = _run_serial_op(do_test, timeout=30.0)

    if "error" in result and result.get("error"):
        add_tool_log(f"[ERROR] Serial test failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    if result.get("success"):
        max_working = result.get("max_working_size", 0)
        failed_at = result.get("failed_size", 0)
        recommended = result.get("recommended_chunk_size", 64)

        if failed_at > 0:
            add_tool_log(
                f"[TEST] Max working size: {max_working} bytes, "
                f"failed at: {failed_at} bytes"
            )
        else:
            add_tool_log(f"[TEST] All tests passed up to {max_working} bytes")
        add_tool_log(f"[TEST] Recommended chunk size: {recommended} bytes")
    else:
        add_tool_log(f"[ERROR] Serial test failed: {result.get('error', 'Unknown')}")

    return jsonify(result)


@bp.route("/fpb/info", methods=["GET"])
def api_fpb_info():
    """Get device info including slot states."""
    _, get_fpb_inject, _build_slot_response = _get_helpers()

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

    return jsonify(
        {
            "success": True,
            "info": info,
            "slots": slot_response["slots"],
            "memory": slot_response["memory"],
            "build_time_mismatch": build_time_mismatch,
            "device_build_time": device_build_time,
            "elf_build_time": elf_build_time,
        }
    )


@bp.route("/fpb/unpatch", methods=["POST"])
def api_fpb_unpatch():
    """Clear FPB patch. Use all=True to clear all patches and free memory."""
    add_tool_log, get_fpb_inject, _ = _get_helpers()

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
            add_tool_log(
                f"[UNPATCH] {'All slots' if clear_all else f'Slot {comp}'} cleared"
            )

        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@bp.route("/fpb/inject", methods=["POST"])
def api_fpb_inject():
    """Perform code injection."""
    add_tool_log, get_fpb_inject, _ = _get_helpers()

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

    add_tool_log(f"[INJECT] Starting injection for {target_func} (mode: {patch_mode})")

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
        add_tool_log(f"[ERROR] Injection failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    success = result.get("success", False)
    inject_result = result.get("result", {})

    if success:
        add_tool_log(
            f"[SUCCESS] Injection complete: {target_func} @ slot {inject_result.get('slot', '?')}"
        )
    else:
        add_tool_log(
            f"[ERROR] Injection failed: {inject_result.get('error', 'unknown error')}"
        )

    return jsonify({"success": success, **inject_result})


@bp.route("/fpb/inject/multi", methods=["POST"])
def api_fpb_inject_multi():
    """Perform multi-function code injection. Each inject_* function gets its own Slot."""
    add_tool_log, get_fpb_inject, _ = _get_helpers()

    data = request.json or {}
    source_content = data.get("source_content")
    patch_mode = data.get("patch_mode", state.device.patch_mode)
    source_ext = data.get("source_ext", ".c")

    if not source_content:
        return jsonify({"success": False, "error": "Source content not provided"})

    fpb = get_fpb_inject()

    add_tool_log(
        f"[INJECT_MULTI] Starting multi-function injection (mode: {patch_mode})"
    )

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
        add_tool_log(f"[ERROR] Multi-injection failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]})

    success = result.get("success", False)
    inject_result = result.get("result", {})

    if success:
        successful = inject_result.get("successful_count", 0)
        total = inject_result.get("total_count", 0)
        add_tool_log(
            f"[SUCCESS] Multi-injection complete: {successful}/{total} functions"
        )
    else:
        add_tool_log(
            f"[ERROR] Multi-injection failed: {inject_result.get('error', 'unknown error')}"
        )

    return jsonify({"success": success, **inject_result})


@bp.route("/fpb/inject/stream", methods=["POST"])
def api_fpb_inject_stream():
    """Perform code injection with streaming progress via SSE."""
    add_tool_log, get_fpb_inject, _ = _get_helpers()

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

    def progress_callback(uploaded, total):
        progress_queue.put(
            {
                "type": "progress",
                "uploaded": uploaded,
                "total": total,
                "percent": round((uploaded / total) * 100, 1) if total > 0 else 0,
            }
        )

    def inject_task():
        """Execute injection in device worker thread."""
        fpb = get_fpb_inject()
        add_tool_log(
            f"[INJECT] Starting injection for {target_func} (mode: {patch_mode})"
        )

        def do_inject():
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
                    add_tool_log(f"[SUCCESS] Injection complete: {target_func}")
                    progress_queue.put({"type": "result", "success": True, **result})
                else:
                    add_tool_log(
                        f"[ERROR] Injection failed: {result.get('error', 'unknown')}"
                    )
                    progress_queue.put({"type": "result", "success": False, **result})
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

    def generate():
        while True:
            try:
                item = progress_queue.get(timeout=30)
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
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

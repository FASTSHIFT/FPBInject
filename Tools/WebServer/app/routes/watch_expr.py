#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Watch Expression API routes for FPBInject Web Server.

Provides endpoints for evaluating C/C++ watch expressions,
pointer dereference, and watch list management.
"""

import logging

from flask import Blueprint, jsonify, request

from core.state import state
from core.watch_evaluator import WatchEvaluator

logger = logging.getLogger(__name__)

bp = Blueprint("watch_expr", __name__)

# In-memory watch list (persisted via state save/restore)
_watch_list = []
_watch_next_id = 1


def _get_evaluator():
    """Create a WatchEvaluator if GDB is available."""
    from core.gdb_manager import is_gdb_available

    if not is_gdb_available(state) or state.gdb_session is None:
        return None
    return WatchEvaluator(state.gdb_session)


def _read_device_memory(addr, size):
    """Read memory from device via serial. Returns hex string or None."""
    from app.routes.symbols import _dynamic_timeout, _get_fpb_inject, _run_serial_op

    fpb = _get_fpb_inject()
    timeout = _dynamic_timeout(size)
    result = _run_serial_op(lambda: fpb.read_memory(addr, size), timeout=timeout)
    if isinstance(result, dict) and "error" in result:
        return None, result["error"]
    raw_data, msg = result
    if raw_data is None:
        return None, msg
    return raw_data.hex(), None


@bp.route("/watch_expr/evaluate", methods=["POST"])
def api_watch_evaluate():
    """Evaluate a watch expression.

    JSON body:
        expr: C/C++ expression string
        read_device: bool (default true) - whether to read device memory

    Returns type info, address, optional struct layout, and hex data.
    """
    data = request.get_json() or {}
    expr = data.get("expr", "").strip()
    read_device = data.get("read_device", True)

    if not expr:
        return jsonify({"success": False, "error": "Expression is empty"})

    evaluator = _get_evaluator()
    if evaluator is None:
        return jsonify({"success": False, "error": "GDB not available"})

    result = evaluator.evaluate(expr)
    if result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    response = {
        "success": True,
        "expr": expr,
        "addr": f"0x{result['addr']:08X}",
        "size": result["size"],
        "type_name": result["type_name"],
        "is_pointer": result["is_pointer"],
        "is_aggregate": result["is_aggregate"],
        "struct_layout": result.get("struct_layout"),
        "hex_data": None,
        "source": None,
    }

    if read_device and result["size"] > 0:
        hex_data, err = _read_device_memory(result["addr"], result["size"])
        if hex_data:
            response["hex_data"] = hex_data
            response["source"] = "device"
        elif err:
            response["read_error"] = err

    return jsonify(response)


@bp.route("/watch_expr/deref", methods=["POST"])
def api_watch_deref():
    """Dereference a pointer: read pointer value from device, resolve target type.

    JSON body:
        addr: hex address of the pointer variable
        type_name: pointer type, e.g. "uint8_t *"
        max_size: max bytes to read for target (default 256)
    """
    data = request.get_json() or {}
    addr_str = data.get("addr", "")
    type_name = data.get("type_name", "")
    max_size = min(data.get("max_size", 256), 65536)

    from app.routes.symbols import _parse_addr

    addr = _parse_addr(addr_str)
    if addr is None:
        return jsonify({"success": False, "error": "Invalid pointer address"})

    if not type_name:
        return jsonify({"success": False, "error": "type_name is required"})

    evaluator = _get_evaluator()
    if evaluator is None:
        return jsonify({"success": False, "error": "GDB not available"})

    # Read pointer value from device (4 bytes for ARM 32-bit)
    ptr_hex, err = _read_device_memory(addr, 4)
    if ptr_hex is None:
        return jsonify({"success": False, "error": f"Failed to read pointer: {err}"})

    # Parse pointer value (little-endian ARM)
    ptr_bytes = bytes.fromhex(ptr_hex)
    target_addr = int.from_bytes(ptr_bytes, byteorder="little")

    if target_addr == 0:
        return jsonify({"success": False, "error": "NULL pointer"})

    # Get target type info
    deref_info = evaluator.get_deref_info(type_name)
    if deref_info.get("error"):
        return jsonify({"success": False, "error": deref_info["error"]})

    target_size = min(deref_info["target_size"], max_size)
    if target_size <= 0:
        target_size = min(4, max_size)  # fallback: read 4 bytes

    # Read target data
    hex_data = None
    if target_size > 0:
        hex_data, _ = _read_device_memory(target_addr, target_size)

    return jsonify(
        {
            "success": True,
            "target_addr": f"0x{target_addr:08X}",
            "target_type": deref_info["target_type"],
            "target_size": target_size,
            "is_aggregate": deref_info["is_aggregate"],
            "struct_layout": deref_info.get("struct_layout"),
            "hex_data": hex_data,
        }
    )


@bp.route("/watch_expr/list", methods=["GET"])
def api_watch_list():
    """Get all watch expressions."""
    return jsonify({"success": True, "watches": _watch_list})


@bp.route("/watch_expr/add", methods=["POST"])
def api_watch_add():
    """Add a watch expression.

    JSON body:
        expr: expression string
    """
    global _watch_next_id
    data = request.get_json() or {}
    expr = data.get("expr", "").strip()

    if not expr:
        return jsonify({"success": False, "error": "Expression is empty"})

    if len(expr) > 256:
        return jsonify({"success": False, "error": "Expression too long"})

    # Check for duplicates
    for w in _watch_list:
        if w["expr"] == expr:
            return jsonify({"success": True, "id": w["id"], "duplicate": True})

    watch_id = _watch_next_id
    _watch_next_id += 1
    entry = {"id": watch_id, "expr": expr, "collapsed": False}
    _watch_list.append(entry)

    return jsonify({"success": True, "id": watch_id})


@bp.route("/watch_expr/remove", methods=["POST"])
def api_watch_remove():
    """Remove a watch expression.

    JSON body:
        id: watch expression id
    """
    data = request.get_json() or {}
    watch_id = data.get("id")

    if watch_id is None:
        return jsonify({"success": False, "error": "id is required"})

    global _watch_list
    before = len(_watch_list)
    _watch_list = [w for w in _watch_list if w["id"] != watch_id]

    if len(_watch_list) == before:
        return jsonify({"success": False, "error": "Watch not found"})

    return jsonify({"success": True})


@bp.route("/watch_expr/clear", methods=["POST"])
def api_watch_clear():
    """Clear all watch expressions."""
    global _watch_list, _watch_next_id
    _watch_list = []
    _watch_next_id = 1
    return jsonify({"success": True})

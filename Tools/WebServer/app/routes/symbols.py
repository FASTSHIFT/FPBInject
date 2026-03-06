#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Symbols API routes for FPBInject Web Server.

Provides endpoints for symbol query, search, disassembly and decompilation.
"""

import logging
import os
import time

from flask import Blueprint, jsonify, request, Response

from core.state import state
from services.device_worker import run_in_device_worker

logger = logging.getLogger(__name__)

bp = Blueprint("symbols", __name__)


def _get_fpb_inject():
    """Lazy import to avoid circular dependency."""
    from routes import get_fpb_inject

    return get_fpb_inject()


def _run_serial_op(func, timeout=10.0):
    """Run a serial operation in the device worker thread.

    Ensures serial port access is always from the owner thread (fpb-worker).

    Args:
        func: Function to execute (should return a result)
        timeout: Maximum time to wait for completion

    Returns:
        Result from func, or dict with 'error' key on failure
    """
    device = state.device
    result = {"error": None, "data": None}

    def wrapper():
        try:
            result["data"] = func()
        except Exception as e:
            result["error"] = str(e)
            logger.exception(f"Serial operation error: {e}")

    t_start = time.time()
    if not run_in_device_worker(device, wrapper, timeout=timeout):
        elapsed = time.time() - t_start
        logger.warning(f"Serial operation timeout after {elapsed:.1f}s")
        return {"error": "Operation timeout - device worker not running"}

    elapsed = time.time() - t_start
    if elapsed > 3.0:
        logger.warning(f"Serial operation took {elapsed:.1f}s")

    if result["error"]:
        return {"error": result["error"]}

    return result["data"]


@bp.route("/symbols", methods=["GET"])
def api_get_symbols():
    """Get symbols from ELF file."""
    _ensure_symbols_loaded()

    # Filter symbols if search query provided
    query = request.args.get("q", "").lower()
    limit = int(request.args.get("limit", 100))

    symbols = state.symbols
    if query:
        symbols = {k: v for k, v in symbols.items() if query in k.lower()}

    # Convert to list and limit
    symbol_list = [
        {
            "name": name,
            "addr": (
                f"0x{info['addr']:08X}" if isinstance(info, dict) else f"0x{info:08X}"
            ),
            "size": info.get("size", 0) if isinstance(info, dict) else 0,
            "type": info.get("type", "other") if isinstance(info, dict) else "function",
            "section": info.get("section", "") if isinstance(info, dict) else "",
        }
        for name, info in sorted(symbols.items(), key=lambda x: x[0])
    ][:limit]

    return jsonify(
        {
            "success": True,
            "symbols": symbol_list,
            "total": len(state.symbols),
            "filtered": len(symbols),
        }
    )


def _get_addr(info):
    """Get address from symbol info (supports both old int and new dict format)."""
    if isinstance(info, dict):
        return info["addr"]
    return info


def _lookup_symbol(sym_name):
    """Look up a symbol, using GDB > cache > pyelftools streaming.

    Results are cached in state.symbols for subsequent lookups.
    """
    from core import elf_utils
    from core.gdb_manager import is_gdb_available

    # Try cache first
    if sym_name in state.symbols:
        return state.symbols[sym_name]

    # If full symbols already loaded, it's definitely not there
    if state.symbols_loaded:
        return None

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return None

    # GDB fast path (~0.01s vs ~3s)
    if is_gdb_available(state):
        result = state.gdb_session.lookup_symbol(sym_name)
    else:
        # pyelftools fallback: streaming single-symbol lookup
        result = elf_utils.lookup_symbol(device.elf_path, sym_name)

    # Cache for future lookups
    if result is not None:
        state.symbols[sym_name] = result

    return result


def _ensure_symbols_loaded():
    """Ensure symbols are loaded exactly once (thread-safe).

    When GDB is available, skip full preloading — GDB handles per-query
    search in milliseconds. Full dump (info variables/functions) would
    timeout on large ELFs (200k+ symbols).
    """
    from core.gdb_manager import is_gdb_available

    # GDB available: no need to preload, per-query search is fast enough
    if is_gdb_available(state):
        return

    if state.symbols_loaded:
        return

    with state._symbols_load_lock:
        # Double-check after acquiring lock
        if state.symbols_loaded:
            return

        device = state.device
        if not device.elf_path or not os.path.exists(device.elf_path):
            return

        logger.info("Loading symbols via pyelftools (GDB not available)...")
        fpb = _get_fpb_inject()
        state.symbols = fpb.get_symbols(device.elf_path)

        state.symbols_loaded = True


@bp.route("/symbols/search", methods=["GET"])
def api_search_symbols():
    """Search symbols from ELF file. Uses cache when available."""
    from core import elf_utils

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        elf_path = device.elf_path if device.elf_path else "(not set)"
        return jsonify(
            {
                "success": False,
                "error": f"ELF file not found: {elf_path}",
                "symbols": [],
            }
        )

    query = request.args.get("q", "").strip()
    limit = int(request.args.get("limit", 100))

    if not query:
        return jsonify({"success": True, "symbols": [], "total": 0, "filtered": 0})

    try:
        from core.gdb_manager import is_gdb_available

        # Use cached symbols if already loaded (instant search)
        if state.symbols_loaded:
            query_lower = query.lower()
            is_addr = query_lower.startswith("0x") or (
                len(query_lower) >= 4
                and all(c in "0123456789abcdef" for c in query_lower)
            )
            addr_str = query_lower[2:] if query_lower.startswith("0x") else query_lower

            matched = []
            for name, info in state.symbols.items():
                if not isinstance(info, dict):
                    continue
                if is_addr:
                    if addr_str not in f"{info.get('addr', 0):08x}":
                        continue
                else:
                    if query_lower not in name.lower():
                        continue
                matched.append(
                    {
                        "name": name,
                        "addr": f"0x{info['addr']:08X}",
                        "size": info.get("size", 0),
                        "type": info.get("type", "other"),
                        "section": info.get("section", ""),
                    }
                )

            matched.sort(key=lambda x: x["name"])
            total = len(state.symbols)
            symbol_list = matched[:limit]
        elif is_gdb_available(state):
            # GDB fast search (~0.01s vs ~3s)
            symbol_list, total = state.gdb_session.search_symbols(query, limit=limit)
        else:
            # pyelftools streaming search (no full load)
            symbol_list, total = elf_utils.search_symbols(
                device.elf_path, query, limit=limit
            )
    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": f"Failed to search symbols: {e}",
                "symbols": [],
            }
        )

    return jsonify(
        {
            "success": True,
            "symbols": symbol_list,
            "total": total,
            "filtered": len(symbol_list),
        }
    )


@bp.route("/symbols/reload", methods=["POST"])
def api_reload_symbols():
    """Reload symbols from ELF file."""
    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    try:
        with state._symbols_load_lock:
            from core.gdb_manager import is_gdb_available

            if is_gdb_available(state):
                # GDB: no full dump needed, clear cache so searches use GDB
                state.symbols = {}
                state.symbols_loaded = False
                return jsonify(
                    {
                        "success": True,
                        "count": 0,
                        "message": "GDB active, symbols queried on demand",
                    }
                )
            else:
                fpb = _get_fpb_inject()
                state.symbols = fpb.get_symbols(device.elf_path)
            state.symbols_loaded = True
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to reload symbols: {e}"})

    return jsonify({"success": True, "count": len(state.symbols)})


@bp.route("/symbols/signature", methods=["GET"])
def api_get_function_signature():
    """Get function signature by searching source files."""
    func_name = request.args.get("func", "")
    if not func_name:
        return jsonify({"success": False, "error": "Function name not specified"})

    device = state.device

    # Try to find function signature from watch directories
    signature = None
    source_file = None

    # Search in watch directories (make a copy to avoid modifying original)
    watch_dirs = list(device.watch_dirs) if device.watch_dirs else []

    from core.patch_generator import find_function_signature

    for watch_dir in watch_dirs:
        if not os.path.isdir(watch_dir):
            continue

        # Search for C/C++ files
        for root, dirs, files in os.walk(watch_dir):
            # Skip common non-source directories
            dirs[:] = [
                d
                for d in dirs
                if d not in [".git", "build", "out", "__pycache__", "node_modules"]
            ]

            for filename in files:
                if not filename.endswith((".c", ".cpp", ".h", ".hpp")):
                    continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Quick check if function name exists in file
                    if func_name not in content:
                        continue

                    # Find function signature
                    sig = find_function_signature(content, func_name)
                    if sig:
                        signature = sig
                        source_file = filepath
                        break
                except Exception:
                    continue

            if signature:
                break
        if signature:
            break

    if signature:
        return jsonify(
            {
                "success": True,
                "func": func_name,
                "signature": signature,
                "source_file": source_file,
            }
        )
    else:
        return jsonify(
            {
                "success": False,
                "error": f"Function '{func_name}' not found in source files",
                "func": func_name,
            }
        )


@bp.route("/symbols/disasm", methods=["GET"])
def api_disasm_symbol():
    """Disassemble a specific function."""
    func_name = request.args.get("func", "")
    if not func_name:
        return jsonify({"success": False, "error": "Function name not specified"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify(
            {"success": False, "error": "ELF file not configured or not found"}
        )

    try:
        fpb = _get_fpb_inject()
        success, result = fpb.disassemble_function(device.elf_path, func_name)

        if success:
            return jsonify({"success": True, "disasm": result})
        else:
            return jsonify(
                {"success": False, "error": result, "disasm": f"; Error: {result}"}
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "disasm": f"; Error: {e}"})


@bp.route("/symbols/decompile", methods=["GET"])
def api_decompile_symbol():
    """Decompile a specific function using Ghidra."""
    func_name = request.args.get("func", "")
    if not func_name:
        return jsonify({"success": False, "error": "Function name not specified"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify(
            {"success": False, "error": "ELF file not configured or not found"}
        )

    try:
        fpb = _get_fpb_inject()
        success, result = fpb.decompile_function(device.elf_path, func_name)

        if success:
            return jsonify({"success": True, "decompiled": result})
        else:
            return jsonify(
                {
                    "success": False,
                    "error": result,
                    "decompiled": f"// Error: {result}",
                }
            )
    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": str(e),
                "decompiled": f"// Error: {e}",
            }
        )


@bp.route("/symbols/decompile/stream", methods=["GET"])
def api_decompile_symbol_stream():
    """Decompile a specific function using Ghidra with streaming progress."""
    import json
    from core import elf_utils

    func_name = request.args.get("func", "")
    if not func_name:
        return jsonify({"success": False, "error": "Function name not specified"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify(
            {"success": False, "error": "ELF file not configured or not found"}
        )

    ghidra_path = getattr(device, "ghidra_path", None)
    if not ghidra_path:
        return jsonify({"success": False, "error": "GHIDRA_NOT_CONFIGURED"})

    def generate():
        try:
            # Check if we have a cached project
            cached = elf_utils._ghidra_project_cache
            elf_mtime = os.path.getmtime(device.elf_path)
            use_cache = (
                cached["elf_path"] == device.elf_path
                and cached["elf_mtime"] == elf_mtime
                and cached["project_dir"]
                and os.path.exists(cached["project_dir"])
            )

            if use_cache:
                yield f"data: {json.dumps({'type': 'status', 'stage': 'decompiling', 'message': 'Using cached analysis...'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'status', 'stage': 'analyzing', 'message': 'Analyzing ELF file (first time, may take a while)...'})}\n\n"

            # Call decompile function
            fpb = _get_fpb_inject()
            success, result = fpb.decompile_function(device.elf_path, func_name)

            if success:
                yield f"data: {json.dumps({'type': 'result', 'success': True, 'decompiled': result})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'result', 'success': False, 'error': result})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'result', 'success': False, 'error': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/symbols/value", methods=["GET"])
def api_get_symbol_value():
    """Get symbol value from ELF file (for const/variable viewing).

    Returns hex data and optional struct layout from DWARF.
    """
    from core import elf_utils

    t_start = time.time()

    sym_name = request.args.get("name", "").strip()
    if not sym_name:
        return jsonify({"success": False, "error": "Symbol name not specified"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    # Look up symbol info (streaming, no full load)
    sym_info = _lookup_symbol(sym_name)
    t_lookup = time.time()
    logger.info(f"[value] Symbol lookup '{sym_name}': {t_lookup - t_start:.2f}s")
    if not sym_info:
        return jsonify({"success": False, "error": f"Symbol '{sym_name}' not found"})

    addr = _get_addr(sym_info)
    size = sym_info.get("size", 0) if isinstance(sym_info, dict) else 0
    sym_type = (
        sym_info.get("type", "other") if isinstance(sym_info, dict) else "function"
    )
    section = sym_info.get("section", "") if isinstance(sym_info, dict) else ""

    # Read raw bytes from ELF
    raw_data = elf_utils.read_symbol_value(device.elf_path, sym_name)
    t_read = time.time()
    logger.info(f"[value] read_symbol_value: {t_read - t_lookup:.2f}s")
    hex_data = raw_data.hex() if raw_data else None

    # Try to get struct layout — GDB fast path or DWARF fallback
    from core.gdb_manager import is_gdb_available

    if is_gdb_available(state):
        struct_layout = state.gdb_session.get_struct_layout(sym_name)
    else:
        struct_layout = elf_utils.get_struct_layout(device.elf_path, sym_name)
    t_dwarf = time.time()
    logger.info(f"[value] get_struct_layout: {t_dwarf - t_read:.2f}s")

    logger.info(f"[value] Total for '{sym_name}': {t_dwarf - t_start:.2f}s")

    return jsonify(
        {
            "success": True,
            "name": sym_name,
            "addr": f"0x{addr:08X}",
            "size": size,
            "type": sym_type,
            "section": section,
            "hex_data": hex_data,
            "struct_layout": struct_layout,
        }
    )


@bp.route("/symbols/read", methods=["POST"])
def api_read_symbol_from_device():
    """Read symbol value from device memory (live read via serial)."""
    from core import elf_utils

    t_start = time.time()

    data = request.get_json() or {}
    sym_name = data.get("name", "").strip()
    if not sym_name:
        return jsonify({"success": False, "error": "Symbol name not specified"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    # Look up symbol info (cached or streaming)
    sym_info = _lookup_symbol(sym_name)
    t_lookup = time.time()
    if t_lookup - t_start > 1.0:
        logger.warning(f"Symbol lookup for '{sym_name}' took {t_lookup - t_start:.1f}s")
    if not sym_info:
        return jsonify({"success": False, "error": f"Symbol '{sym_name}' not found"})

    addr = _get_addr(sym_info)
    size = sym_info.get("size", 0) if isinstance(sym_info, dict) else 0
    if size <= 0:
        return jsonify(
            {"success": False, "error": f"Symbol '{sym_name}' has unknown size"}
        )

    try:
        fpb = _get_fpb_inject()

        # Dispatch serial read to worker thread to avoid cross-thread access
        result = _run_serial_op(lambda: fpb.read_memory(addr, size))
        if isinstance(result, dict) and "error" in result:
            return jsonify({"success": False, "error": result["error"]})

        raw_data, msg = result
        if raw_data is None:
            return jsonify({"success": False, "error": msg})

        hex_data = raw_data.hex()

        from core.gdb_manager import is_gdb_available

        if is_gdb_available(state):
            struct_layout = state.gdb_session.get_struct_layout(sym_name)
        else:
            struct_layout = elf_utils.get_struct_layout(device.elf_path, sym_name)

        return jsonify(
            {
                "success": True,
                "name": sym_name,
                "addr": f"0x{addr:08X}",
                "size": size,
                "hex_data": hex_data,
                "struct_layout": struct_layout,
                "source": "device",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/symbols/write", methods=["POST"])
def api_write_symbol_to_device():
    """Write symbol value to device memory (live write via serial)."""
    data = request.get_json() or {}
    sym_name = data.get("name", "").strip()
    hex_data = data.get("hex_data", "").strip()

    if not sym_name:
        return jsonify({"success": False, "error": "Symbol name not specified"})
    if not hex_data:
        return jsonify({"success": False, "error": "hex_data not specified"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    # Look up symbol info (streaming, no full load)
    sym_info = _lookup_symbol(sym_name)
    if not sym_info:
        return jsonify({"success": False, "error": f"Symbol '{sym_name}' not found"})

    addr = _get_addr(sym_info)
    sym_type = (
        sym_info.get("type", "other") if isinstance(sym_info, dict) else "function"
    )

    if sym_type == "const":
        return jsonify(
            {"success": False, "error": "Cannot write to const symbol (read-only)"}
        )

    try:
        write_bytes = bytes.fromhex(hex_data)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid hex_data format"})

    try:
        fpb = _get_fpb_inject()

        # Dispatch serial write to worker thread to avoid cross-thread access
        result = _run_serial_op(lambda: fpb.write_memory(addr, write_bytes))
        if isinstance(result, dict) and "error" in result:
            return jsonify({"success": False, "error": result["error"]})

        ok, msg = result
        return jsonify(
            {
                "success": ok,
                "message": msg if ok else None,
                "error": msg if not ok else None,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

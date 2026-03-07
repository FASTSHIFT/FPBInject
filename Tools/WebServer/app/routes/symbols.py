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

# Cache for struct layout results (keyed by symbol name).
# Struct layout is derived from ELF debug info and does not change at runtime,
# so we cache it to avoid repeated GDB queries on every auto-read.
_struct_layout_cache = {}

# Cache for symbol detail results from GDB (addr, size, type, section).
# nm only provides {name: addr}; GDB provides full detail on first access.
_symbol_detail_cache = {}


def _get_struct_layout_cached(sym_name):
    """Get struct layout with caching. Returns cached result on subsequent calls."""
    if sym_name in _struct_layout_cache:
        return _struct_layout_cache[sym_name]

    from core.gdb_manager import is_gdb_available

    layout = None
    if is_gdb_available(state):
        try:
            layout = state.gdb_session.get_struct_layout(sym_name)
        except Exception:
            logger.debug(f"Failed to get struct layout for '{sym_name}'")

    _struct_layout_cache[sym_name] = layout
    return layout


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

    # Convert to list and limit — state.symbols is {name: {addr, sym_type}} from nm
    symbol_list = [
        {
            "name": name,
            "addr": f"0x{_get_addr(info):08X}",
            "type": (
                info.get("sym_type", "other") if isinstance(info, dict) else "other"
            ),
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
    """Get address from symbol info (supports int, nm dict, and GDB detail dict)."""
    if isinstance(info, dict):
        return info.get("addr", 0)
    return info


def _lookup_symbol(sym_name):
    """Look up symbol detail (addr, size, type, section) via GDB with caching.

    The nm-loaded state.symbols has {name: {"addr": int, "sym_type": str}}.
    This function uses GDB to get full detail (size, type, section) and caches
    the result in _symbol_detail_cache for subsequent calls.
    """
    from core.gdb_manager import is_gdb_available

    # Try detail cache first (dict with addr/size/type/section from GDB)
    if sym_name in _symbol_detail_cache:
        return _symbol_detail_cache[sym_name]

    # Check if nm has this symbol
    nm_info = state.symbols.get(sym_name)
    nm_addr = None
    nm_sym_type = "other"
    if nm_info is not None:
        if isinstance(nm_info, dict):
            nm_addr = nm_info.get("addr")
            nm_sym_type = nm_info.get("sym_type", "other")
            # If nm dict already has "size" key, it's a GDB-style detail dict (from tests)
            if "size" in nm_info:
                _symbol_detail_cache[sym_name] = nm_info
                return nm_info
        elif isinstance(nm_info, int):
            # Backward compat: old int format
            nm_addr = nm_info

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return None

    if not is_gdb_available(state) or state.gdb_session is None:
        if nm_addr is not None:
            result = {"addr": nm_addr, "size": 0, "type": nm_sym_type, "section": ""}
            _symbol_detail_cache[sym_name] = result
            return result
        logger.warning("GDB not available, cannot look up symbol detail")
        return None

    t0 = time.time()
    result = state.gdb_session.lookup_symbol(sym_name)
    elapsed = time.time() - t0

    if elapsed > 1.0:
        logger.warning(f"[symbols] GDB lookup_symbol '{sym_name}' took {elapsed:.2f}s")
    else:
        logger.info(f"[symbols] GDB lookup_symbol '{sym_name}': {elapsed:.3f}s")

    if result is not None:
        _symbol_detail_cache[sym_name] = result
        return result

    # GDB returned None but nm has the address — return minimal info
    if nm_addr is not None:
        result = {"addr": nm_addr, "size": 0, "type": nm_sym_type, "section": ""}
        _symbol_detail_cache[sym_name] = result
        return result

    return None


def _ensure_symbols_loaded():
    """Ensure symbols are loaded exactly once (thread-safe) via nm.

    nm is fast (~1s for 200k+ symbols) and loads the full symbol table
    into memory for instant search. GDB is only used for per-symbol
    detail queries (ptype, sizeof, struct layout).
    """
    if state.symbols_loaded:
        return

    with state._symbols_load_lock:
        if state.symbols_loaded:
            return

        device = state.device
        if not device.elf_path or not os.path.exists(device.elf_path):
            logger.warning("ELF file not found, symbol preloading skipped")
            return

        try:
            fpb = _get_fpb_inject()
            t0 = time.time()
            state.symbols = fpb.get_symbols(device.elf_path)
            state.symbols_loaded = True
            elapsed = time.time() - t0
            logger.info(
                f"[symbols] nm loaded {len(state.symbols)} symbols in {elapsed:.2f}s"
            )
        except Exception as e:
            logger.error(f"Failed to load symbols via nm: {e}")


@bp.route("/symbols/search", methods=["GET"])
def api_search_symbols():
    """Search symbols from ELF file. Uses nm-loaded cache for fast search."""
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

    if len(query) < 2:
        return jsonify({"success": True, "symbols": [], "total": 0, "filtered": 0})

    # Ensure symbols are loaded via nm
    _ensure_symbols_loaded()

    if not state.symbols_loaded:
        return jsonify(
            {
                "success": False,
                "error": "Symbols not loaded (nm unavailable or ELF missing)",
                "symbols": [],
            }
        )

    try:
        query_lower = query.lower()
        is_addr = query_lower.startswith("0x") or (
            len(query_lower) >= 4 and all(c in "0123456789abcdef" for c in query_lower)
        )
        addr_str = query_lower[2:] if query_lower.startswith("0x") else query_lower

        matched = []
        for name, info in state.symbols.items():
            addr_val = _get_addr(info)
            sym_type = (
                info.get("sym_type", "other") if isinstance(info, dict) else "other"
            )

            if is_addr:
                if addr_str not in f"{addr_val:08x}":
                    continue
            else:
                if query_lower not in name.lower():
                    continue
            matched.append(
                {
                    "name": name,
                    "addr": f"0x{addr_val:08X}",
                    "type": sym_type,
                }
            )

        matched.sort(key=lambda x: x["name"])
        symbol_list = matched[:limit]
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
            "total": len(state.symbols),
            "filtered": len(symbol_list),
        }
    )


@bp.route("/symbols/reload", methods=["POST"])
def api_reload_symbols():
    """Reload symbols from ELF file via nm."""
    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    try:
        with state._symbols_load_lock:
            state.symbols = {}
            state.symbols_loaded = False
            _struct_layout_cache.clear()
            _symbol_detail_cache.clear()

        # Re-load via nm
        _ensure_symbols_loaded()

        return jsonify(
            {
                "success": True,
                "count": len(state.symbols),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to reload symbols: {e}"})


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

    Returns hex data and optional struct layout via GDB.
    """
    from core.gdb_manager import is_gdb_available

    t_start = time.time()

    sym_name = request.args.get("name", "").strip()
    if not sym_name:
        return jsonify({"success": False, "error": "Symbol name not specified"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    if not is_gdb_available(state):
        return jsonify({"success": False, "error": "GDB not available"})

    # Look up symbol info
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

    # Read raw bytes via GDB
    raw_data = state.gdb_session.read_symbol_value(sym_name)
    t_read = time.time()
    logger.info(f"[value] read_symbol_value: {t_read - t_lookup:.2f}s")
    hex_data = raw_data.hex() if raw_data else None

    # Get struct layout via GDB (cached)
    struct_layout = _get_struct_layout_cached(sym_name)
    t_struct = time.time()
    logger.info(f"[value] get_struct_layout: {t_struct - t_read:.2f}s")

    logger.info(f"[value] Total for '{sym_name}': {t_struct - t_start:.2f}s")

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

        struct_layout = _get_struct_layout_cached(sym_name)

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

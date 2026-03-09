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

from app.utils.sse import sse_response
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

# For very large symbols (e.g. framebuffers), running "ptype /o" is expensive
# and provides little value. Skip layout parsing above this size to keep
# /symbols/value responsive.
MAX_LAYOUT_ANALYSIS_SIZE = 256 * 1024


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


def _dynamic_timeout(size):
    """Calculate dynamic timeout based on data size.

    Assumes ~128 bytes/chunk with ~2s per chunk worst case,
    plus generous headroom.
    """
    chunk_size = state.device.chunk_size if state.device.chunk_size > 0 else 128
    num_chunks = max(1, (size + chunk_size - 1) // chunk_size)
    return max(10.0, num_chunks * 3.0)


def _get_gdb_values(sym_name, addr, struct_layout):
    """Use GDB to decode struct field values at a device memory address.

    Returns dict mapping field_name -> display_string, or None.
    Uses GDB's native 'print' to decode all fields including typedefs.
    """
    from core.gdb_manager import is_gdb_available

    if not is_gdb_available(state) or not state.gdb_session:
        return None
    if not struct_layout:
        return None

    try:
        return state.gdb_session.parse_struct_values(sym_name, addr, sym_name)
    except Exception as e:
        logger.debug(f"Failed to get GDB values for '{sym_name}': {e}")
        return None


# Integer type keywords for hex decode (lowercase matching)
_INT_TYPE_KEYWORDS = {
    "int",
    "uint",
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
    "int64",
    "uint64",
    "short",
    "long",
    "size_t",
    "int8_t",
    "uint8_t",
    "int16_t",
    "uint16_t",
    "int32_t",
    "uint32_t",
}


def _decode_field_value(raw_bytes: bytes, type_name: str):
    """Decode a struct field's raw bytes into a display value.

    Handles pointers, integers (signed/unsigned), char arrays, floats.
    Returns the decoded value (int/float/str) or None for unknown types.
    Typedef fallback is handled separately by _decode_field_value_fallback.

    All multi-byte values are little-endian (ARM).
    """
    import struct as struct_mod

    size = len(raw_bytes)
    if size == 0:
        return None

    # Pointer types → hex address
    if "*" in type_name:
        val = int.from_bytes(raw_bytes, "little")
        return f"0x{val:08X}"

    type_lower = type_name.lower()

    # Integer types
    is_int = any(kw in type_lower for kw in _INT_TYPE_KEYWORDS)
    if is_int and size <= 8:
        val = int.from_bytes(raw_bytes, "little")
        # Signed check: type doesn't start with 'u'/'U' and doesn't contain 'uint'
        if (
            not type_name.startswith("u")
            and not type_name.startswith("U")
            and "uint" not in type_name
        ):
            max_signed = 1 << (size * 8 - 1)
            if val >= max_signed:
                val -= 1 << (size * 8)
        return val

    # char array → string
    if "char" in type_lower:
        null_idx = raw_bytes.find(b"\x00")
        str_bytes = raw_bytes[:null_idx] if null_idx >= 0 else raw_bytes
        s = "".join(chr(b) if 32 <= b < 127 else "." for b in str_bytes)
        return f'"{s}"'

    # float (4 bytes, little-endian)
    if "float" in type_lower and size == 4:
        (val,) = struct_mod.unpack("<f", raw_bytes)
        return float(f"{val:.7g}")

    # double (8 bytes, little-endian)
    if "double" in type_lower and size == 8:
        (val,) = struct_mod.unpack("<d", raw_bytes)
        return float(f"{val:.15g}")

    # Unknown type — return None so caller can try nested struct layout
    return None


def _decode_field_value_fallback(raw_bytes: bytes, type_name: str):
    """Typedef fallback: decode unknown types as unsigned integer.

    Only used when _decode_field_value returns None AND no nested struct
    layout is found. Handles typedef'd scalars like lv_coord_t.
    """
    size = len(raw_bytes)
    if size in (1, 2, 4, 8) and "[" not in type_name:
        return int.from_bytes(raw_bytes, "little")
    return None


def _decode_struct_values(struct_layout, hex_data):
    """Decode all struct fields from hex_data using struct_layout type info.

    For nested structs, recursively queries GDB for sub-struct layout and
    decodes the corresponding hex sub-range, producing nested dicts that
    the frontend can render as expandable tree nodes.

    Args:
        struct_layout: list of {name, offset, size, type_name}
        hex_data: hex string of the raw bytes

    Returns:
        dict mapping field_name -> decoded value, or None if no layout.
    """
    if not struct_layout or not hex_data:
        return None

    raw = bytes.fromhex(hex_data)
    result = {}
    for member in struct_layout:
        offset = member["offset"]
        size = member["size"]
        type_name = member["type_name"]
        name = member["name"]

        end = offset + size
        if end > len(raw):
            result[name] = None
            continue

        field_bytes = raw[offset:end]

        # 1) Try known scalar types (int, ptr, float, char, etc.)
        decoded = _decode_field_value(field_bytes, type_name)
        if decoded is not None:
            result[name] = decoded
            continue

        # 2) Unknown type → mark as collapsed struct placeholder.
        #    The frontend renders this as an expandable node; nested
        #    layout is fetched on-demand when the user clicks to expand,
        #    avoiding expensive recursive GDB queries upfront.
        # 3) Typedef fallback (e.g. lv_coord_t → unsigned int)
        fallback = _decode_field_value_fallback(field_bytes, type_name)
        result[name] = fallback

    return result


# Cache for nested struct layouts (keyed by type_name)
_nested_layout_cache = {}


def _get_nested_struct_layout(type_name):
    """Get struct layout for a nested type via GDB ptype.

    Tries 'ptype /o struct TYPE' and 'ptype /o TYPE' to resolve the layout.
    Results are cached since type layouts don't change at runtime.
    """
    if type_name in _nested_layout_cache:
        return _nested_layout_cache[type_name]

    from core.gdb_manager import is_gdb_available

    if not is_gdb_available(state) or not state.gdb_session:
        _nested_layout_cache[type_name] = None
        return None

    # Strip qualifiers for lookup
    clean_type = type_name.strip()
    for prefix in ("const ", "volatile ", "struct ", "union "):
        if clean_type.startswith(prefix):
            clean_type = clean_type[len(prefix) :]

    layout = None
    try:
        # Try with struct prefix first, then bare type name
        for expr in [f"struct {clean_type}", clean_type]:
            layout = state.gdb_session.get_struct_layout(expr)
            if layout:
                break
    except Exception:
        pass

    _nested_layout_cache[type_name] = layout
    return layout


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
            _nested_layout_cache.clear()

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

    gdb_ok = is_gdb_available(state)

    # Look up symbol info — works with nm cache even without GDB
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
    is_pointer = (
        sym_info.get("is_pointer", False) if isinstance(sym_info, dict) else False
    )
    pointer_target = (
        sym_info.get("pointer_target") if isinstance(sym_info, dict) else None
    )

    # Read raw bytes and struct layout via GDB (when available)
    hex_data = None
    struct_layout = None
    gdb_values = None
    read_mode = "read_symbol_value"
    if gdb_ok and state.gdb_session:
        if is_pointer:
            raw_data = state.gdb_session.read_symbol_value(sym_name)
            t_read = time.time()
            logger.info(f"[value] read_symbol_value: {t_read - t_lookup:.2f}s")
            hex_data = raw_data.hex() if raw_data else None
            t_struct = t_read
        else:
            # Combined read: hold GDB lock across x/Nwx + ptype /o to
            # prevent pipe cross-talk between the two commands.
            if size > MAX_LAYOUT_ANALYSIS_SIZE:
                logger.warning(
                    f"[value] skip struct layout for large symbol '{sym_name}' "
                    f"(size={size} > {MAX_LAYOUT_ANALYSIS_SIZE})"
                )
                raw_data = state.gdb_session.read_symbol_value(sym_name)
                struct_layout = None
                read_mode = "read_symbol_value"
            else:
                raw_data, struct_layout = (
                    state.gdb_session.read_symbol_value_and_layout(sym_name)
                )
                read_mode = "read_symbol_value_and_layout"
            t_read = time.time()
            logger.info(f"[value] {read_mode}: {t_read - t_lookup:.2f}s")
            hex_data = raw_data.hex() if raw_data else None
            if struct_layout:
                gdb_values = _get_gdb_values(sym_name, addr, struct_layout)
            t_struct = time.time()
            logger.info(f"[value] get_gdb_values: {t_struct - t_read:.2f}s")
    else:
        logger.info(
            f"[value] GDB not available, returning nm-only info for '{sym_name}'"
        )

    logger.info(f"[value] Total for '{sym_name}': {time.time() - t_start:.2f}s")

    resp = {
        "success": True,
        "name": sym_name,
        "addr": f"0x{addr:08X}",
        "size": size,
        "type": sym_type,
        "section": section,
        "hex_data": hex_data,
        "struct_layout": struct_layout,
        "gdb_values": gdb_values,
    }
    if is_pointer:
        resp["is_pointer"] = True
        resp["pointer_target"] = pointer_target
    return jsonify(resp)


@bp.route("/symbols/read", methods=["POST"])
def api_read_symbol_from_device():
    """Read symbol value from device memory (live read via serial).

    For pointer types, supports optional 'deref' flag to also read
    the data at the address the pointer points to.
    """
    t_start = time.time()

    data = request.get_json() or {}
    sym_name = data.get("name", "").strip()
    deref = data.get("deref", False)
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
    is_pointer = (
        sym_info.get("is_pointer", False) if isinstance(sym_info, dict) else False
    )
    pointer_target = (
        sym_info.get("pointer_target") if isinstance(sym_info, dict) else None
    )
    if size <= 0:
        return jsonify(
            {"success": False, "error": f"Symbol '{sym_name}' has unknown size"}
        )

    try:
        fpb = _get_fpb_inject()

        # Dispatch serial read to worker thread to avoid cross-thread access
        timeout = _dynamic_timeout(size)
        result = _run_serial_op(lambda: fpb.read_memory(addr, size), timeout=timeout)
        if isinstance(result, dict) and "error" in result:
            return jsonify({"success": False, "error": result["error"]})

        raw_data, msg = result
        if raw_data is None:
            return jsonify({"success": False, "error": msg})

        hex_data = raw_data.hex()

        # For pointer types, skip struct layout of the pointer variable itself.
        # NOTE: For device reads, values are decoded from hex_data on the backend
        # using struct_layout type info. GDB is NOT re-queried (would return stale
        # ELF initial values instead of live device values).
        struct_layout = None
        gdb_values = None
        if not is_pointer:
            struct_layout = _get_struct_layout_cached(sym_name)
            if struct_layout:
                gdb_values = _decode_struct_values(struct_layout, hex_data)

        resp = {
            "success": True,
            "name": sym_name,
            "addr": f"0x{addr:08X}",
            "size": size,
            "hex_data": hex_data,
            "struct_layout": struct_layout,
            "gdb_values": gdb_values,
            "source": "device",
        }
        if is_pointer:
            resp["is_pointer"] = True
            resp["pointer_target"] = pointer_target

        # Dereference: read the data at the pointer target address
        if deref and is_pointer and hex_data:
            ptr_value = int.from_bytes(bytes.fromhex(hex_data), "little")
            resp["pointer_value"] = f"0x{ptr_value:08X}"

            if ptr_value != 0 and pointer_target:
                from core.gdb_manager import is_gdb_available

                target_size = 0
                target_layout = None
                if is_gdb_available(state) and state.gdb_session:
                    target_size = state.gdb_session.get_sizeof(pointer_target)
                    if target_size > 0:
                        target_layout = state.gdb_session.get_struct_layout(sym_name)

                if target_size > 0:
                    deref_timeout = _dynamic_timeout(target_size)
                    deref_result = _run_serial_op(
                        lambda: fpb.read_memory(ptr_value, target_size),
                        timeout=deref_timeout,
                    )
                    if (
                        not isinstance(deref_result, dict)
                        and deref_result[0] is not None
                    ):
                        deref_raw, _ = deref_result
                        deref_hex = deref_raw.hex()
                        deref_gdb_values = None
                        if target_layout:
                            deref_gdb_values = _decode_struct_values(
                                target_layout, deref_hex
                            )
                        resp["deref_data"] = {
                            "addr": f"0x{ptr_value:08X}",
                            "size": target_size,
                            "hex_data": deref_hex,
                            "struct_layout": target_layout,
                            "gdb_values": deref_gdb_values,
                            "type_name": pointer_target,
                        }
                    else:
                        resp["deref_error"] = (
                            f"Failed to read {target_size} bytes at 0x{ptr_value:08X}"
                        )
                else:
                    resp["deref_error"] = f"Cannot determine size of '{pointer_target}'"
            elif ptr_value == 0:
                resp["deref_error"] = "NULL pointer"

        return jsonify(resp)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/symbols/read/stream", methods=["POST"])
def api_read_symbol_stream():
    """Read symbol value from device with per-chunk SSE progress.

    Same parameters as /symbols/read but returns text/event-stream.

    SSE events:
        {type: "status", stage: "reading", symbol, addr, size}
        {type: "progress", read, total, percent}
        {type: "result", success, name, addr, size, hex_data, struct_layout, ...}
    """
    import queue
    import threading

    data = request.get_json() or {}
    sym_name = data.get("name", "").strip()
    deref = data.get("deref", False)  # noqa: F841
    if not sym_name:
        return jsonify({"success": False, "error": "Symbol name not specified"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    sym_info = _lookup_symbol(sym_name)
    if not sym_info:
        return jsonify({"success": False, "error": f"Symbol '{sym_name}' not found"})

    addr = _get_addr(sym_info)
    size = sym_info.get("size", 0) if isinstance(sym_info, dict) else 0
    is_pointer = (
        sym_info.get("is_pointer", False) if isinstance(sym_info, dict) else False
    )
    pointer_target = (
        sym_info.get("pointer_target") if isinstance(sym_info, dict) else None
    )
    if size <= 0:
        return jsonify(
            {"success": False, "error": f"Symbol '{sym_name}' has unknown size"}
        )

    progress_queue = queue.Queue()

    def read_task():
        try:
            fpb = _get_fpb_inject()

            progress_queue.put(
                {
                    "type": "status",
                    "stage": "reading",
                    "symbol": sym_name,
                    "addr": f"0x{addr:08X}",
                    "size": size,
                }
            )

            last_pct = {"v": -1}

            def progress_cb(offset, total):
                pct = round(offset * 100 / total, 1) if total > 0 else 0
                if int(pct) != last_pct["v"]:
                    last_pct["v"] = int(pct)
                    progress_queue.put(
                        {
                            "type": "progress",
                            "read": offset,
                            "total": total,
                            "percent": pct,
                        }
                    )

            def do_read():
                return fpb.read_memory(addr, size, progress_callback=progress_cb)

            timeout = _dynamic_timeout(size)
            if not run_in_device_worker(device, lambda: None, timeout=0.1):
                # Quick check if worker is alive
                pass

            result = {"data": None, "error": None}

            def do_read_wrapper():
                try:
                    result["data"] = fpb.read_memory(
                        addr, size, progress_callback=progress_cb
                    )
                except Exception as e:
                    result["error"] = str(e)

            if not run_in_device_worker(device, do_read_wrapper, timeout=timeout):
                progress_queue.put(
                    {
                        "type": "result",
                        "success": False,
                        "error": "Device worker timeout",
                    }
                )
                progress_queue.put(None)
                return

            if result["error"]:
                progress_queue.put(
                    {
                        "type": "result",
                        "success": False,
                        "error": result["error"],
                    }
                )
                progress_queue.put(None)
                return

            raw_data, msg = result["data"]
            if raw_data is None:
                progress_queue.put(
                    {
                        "type": "result",
                        "success": False,
                        "error": msg or "Read failed",
                    }
                )
                progress_queue.put(None)
                return

            hex_data = raw_data.hex()

            struct_layout = None
            gdb_values = None
            if not is_pointer:
                struct_layout = _get_struct_layout_cached(sym_name)
                if struct_layout:
                    gdb_values = _decode_struct_values(struct_layout, hex_data)

            resp = {
                "type": "result",
                "success": True,
                "name": sym_name,
                "addr": f"0x{addr:08X}",
                "size": size,
                "hex_data": hex_data,
                "struct_layout": struct_layout,
                "gdb_values": gdb_values,
                "source": "device",
            }
            if is_pointer:
                resp["is_pointer"] = True
                resp["pointer_target"] = pointer_target

            progress_queue.put(resp)

        except Exception as e:
            progress_queue.put({"type": "result", "success": False, "error": str(e)})
        finally:
            progress_queue.put(None)

    thread = threading.Thread(target=read_task, daemon=True)
    thread.start()

    return sse_response(progress_queue)


@bp.route("/symbols/write", methods=["POST"])
def api_write_symbol_to_device():
    """Write symbol value to device memory (live write via serial).

    Supports partial writes via optional 'offset' parameter.
    When offset is provided, writes hex_data at symbol_addr + offset.
    """
    data = request.get_json() or {}
    sym_name = data.get("name", "").strip()
    hex_data = data.get("hex_data", "").strip()
    write_offset = data.get("offset", 0)

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
        write_offset = int(write_offset)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid offset value"})

    try:
        write_bytes = bytes.fromhex(hex_data)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid hex_data format"})

    # Validate offset + data doesn't exceed symbol size
    sym_size = sym_info.get("size", 0) if isinstance(sym_info, dict) else 0
    if sym_size > 0 and write_offset + len(write_bytes) > sym_size:
        return jsonify(
            {
                "success": False,
                "error": f"Write exceeds symbol size "
                f"(offset={write_offset} + len={len(write_bytes)} > size={sym_size})",
            }
        )

    write_addr = addr + write_offset

    try:
        fpb = _get_fpb_inject()

        # Dispatch serial write to worker thread to avoid cross-thread access
        timeout = _dynamic_timeout(len(write_bytes))
        result = _run_serial_op(
            lambda: fpb.write_memory(write_addr, write_bytes), timeout=timeout
        )
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


# ═══════════════════════════════════════════════════════════════════
# Generic memory read/write (address-based, no symbol name required)
# ═══════════════════════════════════════════════════════════════════


def _parse_addr(value):
    """Parse an address from string or int. Returns int or None."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        try:
            return int(value, 16) if value.startswith("0x") else int(value)
        except ValueError:
            return None
    return None


@bp.route("/memory/read", methods=["GET"])
def api_memory_read():
    """Read arbitrary memory from device.

    Query params:
        addr: hex address (e.g. 0x20000000)
        size: number of bytes to read
    """
    addr = _parse_addr(request.args.get("addr", ""))
    size = request.args.get("size", type=int)

    if addr is None:
        return jsonify({"success": False, "error": "Invalid or missing 'addr'"})
    if not size or size <= 0:
        return jsonify({"success": False, "error": "Invalid or missing 'size'"})
    if size > 65536:
        return jsonify({"success": False, "error": "Size exceeds 64KB limit"})

    try:
        fpb = _get_fpb_inject()
        timeout = _dynamic_timeout(size)
        result = _run_serial_op(lambda: fpb.read_memory(addr, size), timeout=timeout)
        if isinstance(result, dict) and "error" in result:
            return jsonify({"success": False, "error": result["error"]})

        raw_data, msg = result
        if raw_data is None:
            return jsonify({"success": False, "error": msg})

        return jsonify(
            {
                "success": True,
                "addr": f"0x{addr:08X}",
                "size": len(raw_data),
                "hex_data": raw_data.hex(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/memory/write", methods=["POST"])
def api_memory_write():
    """Write arbitrary memory to device.

    JSON body:
        addr: hex address string or int
        hex_data: hex string of bytes to write
    """
    data = request.get_json() or {}
    addr = _parse_addr(data.get("addr"))
    hex_data = data.get("hex_data", "").strip()

    if addr is None:
        return jsonify({"success": False, "error": "Invalid or missing 'addr'"})
    if not hex_data:
        return jsonify({"success": False, "error": "hex_data not specified"})

    try:
        write_bytes = bytes.fromhex(hex_data)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid hex_data format"})

    if len(write_bytes) > 65536:
        return jsonify({"success": False, "error": "Data exceeds 64KB limit"})

    try:
        fpb = _get_fpb_inject()
        timeout = _dynamic_timeout(len(write_bytes))
        result = _run_serial_op(
            lambda: fpb.write_memory(addr, write_bytes), timeout=timeout
        )
        if isinstance(result, dict) and "error" in result:
            return jsonify({"success": False, "error": result["error"]})

        ok, msg = result
        return jsonify(
            {
                "success": ok,
                "addr": f"0x{addr:08X}",
                "size": len(write_bytes),
                "message": msg if ok else None,
                "error": msg if not ok else None,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/memory/read/stream", methods=["POST"])
def api_memory_read_stream():
    """Read memory with real-time SSE progress streaming.

    JSON body:
        addr: hex address string or int
        size: number of bytes to read

    Returns: text/event-stream with per-chunk progress events and final result.
    """
    import queue
    import threading

    data = request.get_json() or {}
    addr = _parse_addr(data.get("addr"))
    size = data.get("size", 0)

    if addr is None:
        return jsonify({"success": False, "error": "Invalid or missing 'addr'"})

    try:
        size = int(size)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid 'size'"})

    if size <= 0:
        return jsonify({"success": False, "error": "Invalid 'size'"})
    if size > 65536:
        return jsonify({"success": False, "error": "Size exceeds 64KB limit"})

    progress_queue = queue.Queue()

    def read_task():
        try:
            fpb = _get_fpb_inject()
            last_pct = {"v": -1}

            def progress_cb(offset, total):
                pct = int(offset * 100 / total) if total > 0 else 0
                if pct != last_pct["v"]:
                    last_pct["v"] = pct
                    progress_queue.put(
                        {
                            "type": "progress",
                            "offset": offset,
                            "total": total,
                            "pct": pct,
                        }
                    )

            result_holder = {"data": None, "error": None}

            def do_read():
                try:
                    raw, msg = fpb.read_memory(
                        addr, size, progress_callback=progress_cb
                    )
                    result_holder["data"] = raw
                    result_holder["msg"] = msg
                except Exception as e:
                    result_holder["error"] = str(e)

            timeout = _dynamic_timeout(size)
            device = state.device
            ok = run_in_device_worker(device, do_read, timeout=timeout)

            if not ok:
                progress_queue.put(
                    {
                        "type": "result",
                        "success": False,
                        "error": "Operation timeout",
                    }
                )
            elif result_holder["error"]:
                progress_queue.put(
                    {
                        "type": "result",
                        "success": False,
                        "error": result_holder["error"],
                    }
                )
            elif result_holder["data"] is None:
                progress_queue.put(
                    {
                        "type": "result",
                        "success": False,
                        "error": result_holder.get("msg", "Read failed"),
                    }
                )
            else:
                raw = result_holder["data"]
                progress_queue.put(
                    {
                        "type": "result",
                        "success": True,
                        "addr": f"0x{addr:08X}",
                        "size": len(raw),
                        "hex_data": raw.hex(),
                    }
                )
        except Exception as e:
            progress_queue.put({"type": "result", "success": False, "error": str(e)})
        finally:
            progress_queue.put(None)

    thread = threading.Thread(target=read_task, daemon=True)
    thread.start()

    return sse_response(progress_queue)

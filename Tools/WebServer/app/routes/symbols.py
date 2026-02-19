#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Symbols API routes for FPBInject Web Server.

Provides endpoints for symbol query, search, disassembly and decompilation.
"""

import os

from flask import Blueprint, jsonify, request, Response

from core.state import state

bp = Blueprint("symbols", __name__)


def _get_fpb_inject():
    """Lazy import to avoid circular dependency."""
    from routes import get_fpb_inject

    return get_fpb_inject()


@bp.route("/symbols", methods=["GET"])
def api_get_symbols():
    """Get symbols from ELF file."""
    if not state.symbols_loaded:
        device = state.device
        if device.elf_path and os.path.exists(device.elf_path):
            fpb = _get_fpb_inject()
            state.symbols = fpb.get_symbols(device.elf_path)
            state.symbols_loaded = True

    # Filter symbols if search query provided
    query = request.args.get("q", "").lower()
    limit = int(request.args.get("limit", 100))

    symbols = state.symbols
    if query:
        symbols = {k: v for k, v in symbols.items() if query in k.lower()}

    # Convert to list and limit
    symbol_list = [
        {"name": name, "addr": f"0x{addr:08X}"}
        for name, addr in sorted(symbols.items(), key=lambda x: x[0])
    ][:limit]

    return jsonify(
        {
            "success": True,
            "symbols": symbol_list,
            "total": len(state.symbols),
            "filtered": len(symbols),
        }
    )


@bp.route("/symbols/search", methods=["GET"])
def api_search_symbols():
    """Search symbols from ELF file. Supports search by name or address (0x prefix)."""
    # Load symbols if not loaded
    if not state.symbols_loaded:
        device = state.device
        if device.elf_path and os.path.exists(device.elf_path):
            try:
                fpb = _get_fpb_inject()
                state.symbols = fpb.get_symbols(device.elf_path)
                state.symbols_loaded = True
            except Exception as e:
                return jsonify(
                    {
                        "success": False,
                        "error": f"Failed to load symbols: {e}",
                        "symbols": [],
                    }
                )
        else:
            elf_path = device.elf_path if device.elf_path else "(not set)"
            return jsonify(
                {
                    "success": False,
                    "error": f"ELF file not found: {elf_path}",
                    "symbols": [],
                }
            )

    # Filter symbols if search query provided
    query = request.args.get("q", "").strip()
    limit = int(request.args.get("limit", 100))

    symbols = state.symbols

    if query:
        # Check if query is an address (starts with 0x or is hex digits)
        is_addr_search = query.lower().startswith("0x") or (
            len(query) >= 4 and all(c in "0123456789abcdefABCDEF" for c in query)
        )

        if is_addr_search:
            # Search by address
            try:
                # Parse the address
                addr_str = query.lower()
                if addr_str.startswith("0x"):
                    addr_str = addr_str[2:]

                # Find symbols matching the address (partial match on hex string)
                symbols = {k: v for k, v in symbols.items() if addr_str in f"{v:08x}"}
            except ValueError:
                # Invalid hex, fall back to name search
                query_lower = query.lower()
                symbols = {k: v for k, v in symbols.items() if query_lower in k.lower()}
        else:
            # Search by name (case-insensitive)
            query_lower = query.lower()
            symbols = {k: v for k, v in symbols.items() if query_lower in k.lower()}

    # Convert to list and limit
    symbol_list = [
        {"name": name, "addr": f"0x{addr:08X}"}
        for name, addr in sorted(symbols.items(), key=lambda x: x[0])
    ][:limit]

    return jsonify(
        {
            "success": True,
            "symbols": symbol_list,
            "total": len(state.symbols),
            "filtered": len(symbols),
        }
    )


@bp.route("/symbols/reload", methods=["POST"])
def api_reload_symbols():
    """Reload symbols from ELF file."""
    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    try:
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

    # Also add parent directories of ELF path as potential source locations
    if device.elf_path and os.path.exists(device.elf_path):
        elf_dir = os.path.dirname(device.elf_path)
        # Look for common source directories relative to build dir
        for parent in [".", "..", "../..", "../../.."]:
            src_dir = os.path.normpath(os.path.join(elf_dir, parent))
            if os.path.isdir(src_dir) and src_dir not in watch_dirs:
                watch_dirs.append(src_dir)

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

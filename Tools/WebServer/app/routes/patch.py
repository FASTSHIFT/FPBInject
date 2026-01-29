#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Patch Management API routes for FPBInject Web Server.

Provides endpoints for patch source management, generation, and preview.
"""

import logging
import os

from flask import Blueprint, jsonify, request

from core.state import state

bp = Blueprint("patch", __name__)
logger = logging.getLogger(__name__)


def _get_fpb_inject():
    """Lazy import to avoid circular dependency."""
    from routes import get_fpb_inject

    return get_fpb_inject()


@bp.route("/patch/source", methods=["GET"])
def api_get_patch_source():
    """Get current patch source content."""
    device = state.device

    # Try to load from file if path is set
    if device.patch_source_path and os.path.exists(device.patch_source_path):
        try:
            with open(device.patch_source_path, "r") as f:
                device.patch_source_content = f.read()
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    content = device.patch_source_content or state.patch_template

    return jsonify(
        {
            "success": True,
            "content": content,
            "path": device.patch_source_path,
        }
    )


@bp.route("/patch/source", methods=["POST"])
def api_set_patch_source():
    """Set patch source content."""
    data = request.json or {}
    content = data.get("content")
    save_to_file = data.get("save_to_file", False)

    if content is None:
        return jsonify({"success": False, "error": "Content not provided"})

    device = state.device
    device.patch_source_content = content

    # Save to file if requested
    if save_to_file and device.patch_source_path:
        try:
            with open(device.patch_source_path, "w") as f:
                f.write(content)
        except Exception as e:
            return jsonify({"success": False, "error": f"Failed to save: {e}"})

    return jsonify({"success": True})


@bp.route("/patch/template", methods=["GET"])
def api_get_patch_template():
    """Get default patch template."""
    return jsonify({"success": True, "content": state.patch_template})


@bp.route("/patch/auto_generate", methods=["POST"])
def api_auto_generate_patch():
    """
    Auto-generate patch from source file with FPB_INJECT markers.

    Finds functions marked with /* FPB_INJECT */ comment,
    copies entire file with marked functions renamed to inject_xxx.
    """
    from core.patch_generator import PatchGenerator

    data = request.json or {}
    file_path = data.get("file_path")

    if not file_path:
        return jsonify({"success": False, "error": "File path not provided"})

    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": f"File not found: {file_path}"})

    try:
        gen = PatchGenerator()

        # Generate patch (finds FPB_INJECT markers automatically)
        patch_content, marked_functions = gen.generate_patch(file_path)

        if not marked_functions:
            return jsonify(
                {
                    "success": True,
                    "marked_functions": [],
                    "patch_content": "",
                    "message": "No FPB_INJECT markers found. Add /* FPB_INJECT */ before functions to inject.",
                }
            )

        return jsonify(
            {
                "success": True,
                "marked_functions": marked_functions,
                "injected_functions": [f"inject_{f}" for f in marked_functions],
                "patch_content": patch_content,
                "source_file": file_path,
            }
        )

    except Exception as e:
        logger.exception(f"Error generating patch: {e}")
        return jsonify({"success": False, "error": str(e)})


@bp.route("/patch/detect_markers", methods=["POST"])
def api_detect_markers():
    """
    Detect FPB_INJECT markers in a file.

    Returns list of marked function names without generating patch.
    """
    from core.patch_generator import PatchGenerator

    data = request.json or {}
    file_path = data.get("file_path")

    if not file_path:
        return jsonify({"success": False, "error": "File path not provided"})

    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": f"File not found: {file_path}"})

    try:
        gen = PatchGenerator()
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        marked = gen.find_marked_functions(content)

        return jsonify(
            {
                "success": True,
                "file_path": file_path,
                "marked_functions": marked,
                "count": len(marked),
            }
        )

    except Exception as e:
        logger.exception(f"Error detecting markers: {e}")
        return jsonify({"success": False, "error": str(e)})


@bp.route("/patch/preview", methods=["POST"])
def api_patch_preview():
    """Get patch file content preview (compile without upload)."""
    data = request.json or {}
    source_content = data.get("source_content")

    if not source_content:
        return jsonify({"success": False, "error": "Source content not provided"})

    device = state.device
    if not device.elf_path or not os.path.exists(device.elf_path):
        return jsonify({"success": False, "error": "ELF file not found"})

    fpb = _get_fpb_inject()

    # Get a base address for compilation (use a placeholder)
    base_addr = 0x20000000

    # Compile to get binary and symbols
    data_bytes, inject_symbols, error = fpb.compile_inject(
        source_content,
        base_addr,
        device.elf_path,
        device.compile_commands_path,
    )

    if error:
        return jsonify({"success": False, "error": error})

    # Format as hex dump
    hex_lines = []
    for i in range(0, len(data_bytes), 16):
        chunk = data_bytes[i : i + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        hex_lines.append(f"{base_addr + i:08X}  {hex_part:<48}  {ascii_part}")

    # Symbol info
    symbol_info = []
    for name, addr in sorted(inject_symbols.items(), key=lambda x: x[1]):
        symbol_info.append(f"  0x{addr:08X}  {name}")

    preview = f"""=== Patch Binary Preview ===
Size: {len(data_bytes)} bytes
Base Address: 0x{base_addr:08X}

=== Symbols ===
{chr(10).join(symbol_info) if symbol_info else '  (no symbols)'}

=== Hex Dump ===
{chr(10).join(hex_lines)}
"""
    return jsonify(
        {
            "success": True,
            "preview": preview,
            "size": len(data_bytes),
            "symbols": [
                {"name": n, "addr": f"0x{a:08X}"} for n, a in inject_symbols.items()
            ],
        }
    )

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Flask API routes for FPBInject Web Server.
"""

import json
import logging
import os
import time
import queue
import threading

from flask import jsonify, request, render_template, Response

from state import state
from device_worker import (
    start_worker,
    stop_worker,
    run_in_device_worker,
    get_device_timer_manager,
)
from fpb_inject import (
    FPBInject,
    scan_serial_ports,
    serial_open,
)

logger = logging.getLogger(__name__)

# Global FPBInject instance
_fpb_inject = None


def get_fpb_inject():
    """Get or create FPBInject instance."""
    global _fpb_inject
    if _fpb_inject is None:
        _fpb_inject = FPBInject(state.device)
        # Initialize toolchain path from device config
        if state.device.toolchain_path:
            _fpb_inject.set_toolchain_path(state.device.toolchain_path)
    return _fpb_inject


def add_tool_log(message):
    """Add a message to tool output log (shown in OUTPUT terminal)."""
    device = state.device
    log_id = device.tool_log_next_id
    device.tool_log_next_id += 1
    entry = {"id": log_id, "message": message}
    device.tool_log.append(entry)
    if len(device.tool_log) > device.tool_log_max_size:
        device.tool_log = device.tool_log[-device.tool_log_max_size :]


def register_routes(app):
    """Register all routes with the Flask app."""

    @app.route("/")
    def index():
        """Serve the main web interface."""
        return render_template("index.html")

    # ============== Port & Connection ==============

    @app.route("/api/ports", methods=["GET"])
    def api_get_ports():
        """Get available serial ports."""
        ports = scan_serial_ports()
        return jsonify({"success": True, "ports": ports})

    @app.route("/api/connect", methods=["POST"])
    def api_connect():
        """Connect to a serial port."""
        data = request.json or {}
        port = data.get("port")
        baudrate = data.get("baudrate", 115200)
        timeout = data.get("timeout", 2)

        if not port:
            return jsonify({"success": False, "error": "Port not specified"})

        device = state.device

        # Start worker first
        start_worker(device)

        result = {"error": None}

        def do_connect():
            if device.ser:
                try:
                    device.ser.close()
                except:
                    pass
                device.ser = None

            ser, error = serial_open(port, baudrate, timeout)
            if error:
                result["error"] = error
            else:
                device.ser = ser
                device.port = port
                device.baudrate = baudrate
                device.timeout = timeout

        if not run_in_device_worker(device, do_connect, timeout=5.0):
            return jsonify({"success": False, "error": "Connect timeout"})

        if result["error"]:
            add_tool_log(f"[ERROR] Connection failed: {result['error']}")
            return jsonify({"success": False, "error": result["error"]})

        device.auto_connect = True
        state.save_config()

        # Setup toolchain if configured
        fpb = get_fpb_inject()
        if device.toolchain_path:
            fpb.set_toolchain_path(device.toolchain_path)

        add_tool_log(f"[SUCCESS] Connected to {port} @ {baudrate}")
        return jsonify({"success": True, "port": port})

    @app.route("/api/disconnect", methods=["POST"])
    def api_disconnect():
        """Disconnect from serial port."""
        device = state.device

        def do_disconnect():
            if device.ser:
                try:
                    device.ser.close()
                except:
                    pass
                device.ser = None

        run_in_device_worker(device, do_disconnect, timeout=2.0)
        stop_worker(device)

        device.auto_connect = False
        device.inject_active = False
        state.save_config()

        add_tool_log("[INFO] Disconnected from serial port")
        return jsonify({"success": True})

    @app.route("/api/status", methods=["GET"])
    def api_status():
        """Get current device status."""
        device = state.device

        connected = False
        try:
            connected = device.ser is not None and device.ser.isOpen()
        except:
            pass

        return jsonify(
            {
                "success": True,
                "connected": connected,
                "port": device.port,
                "baudrate": device.baudrate,
                "elf_path": device.elf_path,
                "toolchain_path": device.toolchain_path,
                "compile_commands_path": device.compile_commands_path,
                "watch_dirs": device.watch_dirs,
                "patch_mode": device.patch_mode,
                "chunk_size": device.chunk_size,
                "auto_connect": device.auto_connect,
                "auto_compile": device.auto_compile,
                "patch_source_path": device.patch_source_path,
                "watcher_enabled": device.watcher_enabled,
                "inject_active": device.inject_active,
                "last_inject_target": device.last_inject_target,
                "last_inject_func": device.last_inject_func,
                "last_inject_time": device.last_inject_time,
                "device_info": device.device_info,
            }
        )

    @app.route("/api/config", methods=["GET"])
    def api_get_config():
        """Get current device configuration."""
        device = state.device
        return jsonify(
            {
                "port": device.port,
                "baudrate": device.baudrate,
                "elf_path": device.elf_path,
                "toolchain_path": device.toolchain_path,
                "compile_commands_path": device.compile_commands_path,
                "watch_dirs": device.watch_dirs,
                "patch_mode": device.patch_mode,
                "watcher_enabled": device.watcher_enabled,
                "auto_compile": device.auto_compile,
            }
        )

    @app.route("/api/config", methods=["POST"])
    def api_config():
        """Update device configuration."""
        data = request.json or {}
        device = state.device

        if "port" in data:
            device.port = data["port"]

        if "baudrate" in data:
            device.baudrate = data["baudrate"]

        if "elf_path" in data:
            device.elf_path = data["elf_path"]
            # Reload symbols
            if device.elf_path and os.path.exists(device.elf_path):
                fpb = get_fpb_inject()
                state.symbols = fpb.get_symbols(device.elf_path)
                state.symbols_loaded = True

        if "toolchain_path" in data:
            device.toolchain_path = data["toolchain_path"]
            fpb = get_fpb_inject()
            fpb.set_toolchain_path(device.toolchain_path)

        if "compile_commands_path" in data:
            device.compile_commands_path = data["compile_commands_path"]

        if "watch_dirs" in data:
            device.watch_dirs = data["watch_dirs"]
            # Restart file watcher if needed
            _restart_file_watcher()

        if "patch_mode" in data:
            device.patch_mode = data["patch_mode"]

        if "chunk_size" in data:
            device.chunk_size = data["chunk_size"]

        if "auto_compile" in data:
            device.auto_compile = data["auto_compile"]

        if "watcher_enabled" in data:
            device.watcher_enabled = data["watcher_enabled"]
            # Start or stop file watcher based on setting
            if device.watcher_enabled:
                _restart_file_watcher()
            else:
                _stop_file_watcher()

        if "patch_source_path" in data:
            device.patch_source_path = data["patch_source_path"]
            # Load patch source content if file exists
            if device.patch_source_path and os.path.exists(device.patch_source_path):
                try:
                    with open(device.patch_source_path, "r") as f:
                        device.patch_source_content = f.read()
                except:
                    pass

        state.save_config()
        return jsonify({"success": True})

    # ============== FPB Inject Operations ==============

    @app.route("/api/fpb/ping", methods=["POST"])
    def api_fpb_ping():
        """Ping device to test connection."""
        fpb = get_fpb_inject()
        success, msg = fpb.ping()
        return jsonify({"success": success, "message": msg})

    @app.route("/api/fpb/info", methods=["GET"])
    def api_fpb_info():
        """Get device info including slot states."""
        fpb = get_fpb_inject()
        info, error = fpb.info()
        if error:
            return jsonify({"success": False, "error": error})
        state.device.device_info = info

        # Ensure symbols are loaded for address lookup
        device = state.device
        if (
            not state.symbols_loaded
            and device.elf_path
            and os.path.exists(device.elf_path)
        ):
            state.symbols = fpb.get_symbols(device.elf_path)
            state.symbols_loaded = True

        # Get symbols for address lookup
        symbols_reverse = {}
        if state.symbols:
            symbols_reverse = {v: k for k, v in state.symbols.items()}

        # Build slot states from device info
        slots = []
        device_slots = info.get("slots", [])
        for i in range(6):
            slot_data = next((s for s in device_slots if s.get("id") == i), None)
            if slot_data and slot_data.get("occupied"):
                orig_addr = slot_data.get("orig_addr", 0)
                target_addr = slot_data.get("target_addr", 0)
                code_size = slot_data.get("code_size", 0)
                # Lookup function name from symbols (try both original and Thumb-cleared address)
                func_name = symbols_reverse.get(orig_addr, "")
                if not func_name:
                    func_name = symbols_reverse.get(orig_addr & ~1, "")
                slots.append(
                    {
                        "id": i,
                        "occupied": True,
                        "orig_addr": f"0x{orig_addr:08X}",
                        "target_addr": f"0x{target_addr:08X}",
                        "func": func_name,
                        "code_size": code_size,
                    }
                )
            else:
                slots.append(
                    {
                        "id": i,
                        "occupied": False,
                        "orig_addr": "",
                        "target_addr": "",
                        "func": "",
                        "code_size": 0,
                    }
                )

        # Memory info
        memory_info = {
            "is_dynamic": info.get("is_dynamic", False) if info else False,
            "base": info.get("base", 0) if info else 0,
            "size": info.get("size", 0) if info else 0,
            "used": info.get("used", 0) if info else 0,
        }

        return jsonify(
            {
                "success": True,
                "info": info,
                "slots": slots,
                "memory": memory_info,
            }
        )

    @app.route("/api/fpb/unpatch", methods=["POST"])
    def api_fpb_unpatch():
        """Clear FPB patch. Use all=True to clear all patches and free memory."""
        data = request.json or {}
        comp = data.get("comp", 0)
        clear_all = data.get("all", False)

        fpb = get_fpb_inject()
        success, msg = fpb.unpatch(comp=comp, all=clear_all)

        if success:
            if clear_all:
                state.device.inject_active = False
                state.device.last_inject_target = None
                state.device.last_inject_func = None
            add_tool_log(
                f"[UNPATCH] {'All slots' if clear_all else f'Slot {comp}'} cleared"
            )

        return jsonify({"success": success, "message": msg})

    @app.route("/api/fpb/inject", methods=["POST"])
    def api_fpb_inject():
        """Perform code injection."""
        data = request.json or {}
        source_content = data.get("source_content")
        target_func = data.get("target_func")
        inject_func = data.get("inject_func")
        patch_mode = data.get("patch_mode", state.device.patch_mode)
        comp = data.get("comp", -1)  # Default to auto-select slot
        source_ext = data.get("source_ext", ".c")  # Default to .c

        if not source_content:
            return jsonify({"success": False, "error": "Source content not provided"})

        if not target_func:
            return jsonify({"success": False, "error": "Target function not specified"})

        fpb = get_fpb_inject()

        add_tool_log(
            f"[INJECT] Starting injection for {target_func} (mode: {patch_mode})"
        )

        # Enter fl interactive mode before injection
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
        finally:
            # Exit fl interactive mode after injection
            fpb.exit_fl_mode()

        if success:
            add_tool_log(
                f"[SUCCESS] Injection complete: {target_func} @ slot {result.get('slot', '?')}"
            )
        else:
            add_tool_log(
                f"[ERROR] Injection failed: {result.get('error', 'unknown error')}"
            )

        return jsonify({"success": success, **result})

    @app.route("/api/fpb/inject/multi", methods=["POST"])
    def api_fpb_inject_multi():
        """Perform multi-function code injection. Each inject_* function gets its own Slot."""
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

        # Enter fl interactive mode before injection
        fpb.enter_fl_mode()

        try:
            success, result = fpb.inject_multi(
                source_content=source_content,
                patch_mode=patch_mode,
                source_ext=source_ext,
            )
        finally:
            # Exit fl interactive mode after injection
            fpb.exit_fl_mode()

        if success:
            successful = result.get("successful_count", 0)
            total = result.get("total_count", 0)
            add_tool_log(
                f"[SUCCESS] Multi-injection complete: {successful}/{total} functions"
            )
        else:
            add_tool_log(
                f"[ERROR] Multi-injection failed: {result.get('error', 'unknown error')}"
            )

        return jsonify({"success": success, **result})

        return jsonify({"success": success, **result})

    @app.route("/api/fpb/inject/stream", methods=["POST"])
    def api_fpb_inject_stream():
        """Perform code injection with streaming progress via SSE."""
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
            fpb = get_fpb_inject()
            add_tool_log(
                f"[INJECT] Starting injection for {target_func} (mode: {patch_mode})"
            )

            # Enter fl interactive mode before injection
            fpb.enter_fl_mode()

            try:
                # Send compiling status
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
                progress_queue.put(None)  # Signal end of stream

        # Start injection in background thread
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
                    # Send heartbeat
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

    # ============== Symbols ==============

    @app.route("/api/symbols", methods=["GET"])
    def api_get_symbols():
        """Get symbols from ELF file."""
        if not state.symbols_loaded:
            device = state.device
            if device.elf_path and os.path.exists(device.elf_path):
                fpb = get_fpb_inject()
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

    @app.route("/api/symbols/search", methods=["GET"])
    def api_search_symbols():
        """Search symbols from ELF file."""
        # Load symbols if not loaded
        if not state.symbols_loaded:
            device = state.device
            if device.elf_path and os.path.exists(device.elf_path):
                try:
                    fpb = get_fpb_inject()
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

    @app.route("/api/symbols/reload", methods=["POST"])
    def api_reload_symbols():
        """Reload symbols from ELF file."""
        device = state.device
        if not device.elf_path or not os.path.exists(device.elf_path):
            return jsonify({"success": False, "error": "ELF file not found"})

        try:
            fpb = get_fpb_inject()
            state.symbols = fpb.get_symbols(device.elf_path)
            state.symbols_loaded = True
        except Exception as e:
            return jsonify(
                {"success": False, "error": f"Failed to reload symbols: {e}"}
            )

        return jsonify({"success": True, "count": len(state.symbols)})

    @app.route("/api/symbols/signature", methods=["GET"])
    def api_get_function_signature():
        """Get function signature by searching source files."""
        func_name = request.args.get("func", "")
        if not func_name:
            return jsonify({"success": False, "error": "Function name not specified"})

        device = state.device

        # Try to find function signature from watch directories
        signature = None
        source_file = None

        # Search in watch directories
        watch_dirs = device.watch_dirs if device.watch_dirs else []

        # Also add parent directories of ELF path as potential source locations
        if device.elf_path and os.path.exists(device.elf_path):
            elf_dir = os.path.dirname(device.elf_path)
            # Look for common source directories relative to build dir
            for parent in [".", "..", "../..", "../../.."]:
                src_dir = os.path.normpath(os.path.join(elf_dir, parent))
                if os.path.isdir(src_dir) and src_dir not in watch_dirs:
                    watch_dirs.append(src_dir)

        from patch_generator import CParser

        parser = CParser()

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

                        # Parse functions from file
                        functions = parser.parse_functions(content)
                        if func_name in functions:
                            func_info = functions[func_name]
                            signature = func_info.signature
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

    @app.route("/api/symbols/disasm", methods=["GET"])
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
            fpb = get_fpb_inject()
            success, result = fpb.disassemble_function(device.elf_path, func_name)

            if success:
                return jsonify({"success": True, "disasm": result})
            else:
                return jsonify(
                    {"success": False, "error": result, "disasm": f"; Error: {result}"}
                )
        except Exception as e:
            return jsonify(
                {"success": False, "error": str(e), "disasm": f"; Error: {e}"}
            )

    # ============== Patch Source Management ==============

    @app.route("/api/patch/source", methods=["GET"])
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

    @app.route("/api/patch/source", methods=["POST"])
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

    @app.route("/api/patch/template", methods=["GET"])
    def api_get_patch_template():
        """Get default patch template."""
        return jsonify({"success": True, "content": state.patch_template})

    @app.route("/api/patch/generate", methods=["POST"])
    def api_generate_patch():
        """Generate patch code from template."""
        data = request.json or {}
        target_func = data.get("target_func")
        signature = data.get("signature", "void")

        if not target_func:
            return jsonify({"success": False, "error": "Target function not specified"})

        # Generate patch code
        patch_code = f"""/*
 * Auto-generated patch for: {target_func}
 */

#include <syslog.h>

__attribute__((used, section(".text.inject")))
{signature} inject_{target_func}(/* TODO: add arguments */) {{
    syslog(LOG_INFO, "Injected {target_func} called\\n");
    // TODO: Add your injection logic here
    // Call original function if needed:
    // {target_func}_original(...);
}}
"""
        return jsonify({"success": True, "content": patch_code})

    @app.route("/api/patch/auto_generate", methods=["POST"])
    def api_auto_generate_patch():
        """
        Auto-generate patch from modified source file.

        Detects modified functions by comparing with git HEAD,
        clones the entire file with modified functions renamed to inject_xxx.
        """
        from patch_generator import PatchGenerator

        data = request.json or {}
        file_path = data.get("file_path")

        if not file_path:
            return jsonify({"success": False, "error": "File path not provided"})

        if not os.path.exists(file_path):
            return jsonify({"success": False, "error": f"File not found: {file_path}"})

        try:
            gen = PatchGenerator()

            # Detect modified functions
            modified = gen.detect_modified_functions(file_path)

            if not modified:
                return jsonify(
                    {
                        "success": True,
                        "modified_functions": [],
                        "patch_content": "",
                        "message": "No modified functions detected",
                    }
                )

            # Generate patch content
            patch_content, injected = gen.generate_patch(file_path, modified)

            return jsonify(
                {
                    "success": True,
                    "modified_functions": modified,
                    "injected_functions": [f"inject_{f}" for f in injected],
                    "patch_content": patch_content,
                    "source_file": file_path,
                }
            )

        except Exception as e:
            logger.exception(f"Error generating patch: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/patch/detect_changes", methods=["POST"])
    def api_detect_changes():
        """
        Detect which functions have been modified in a file.

        Returns list of modified function names without generating patch.
        """
        from patch_generator import PatchGenerator

        data = request.json or {}
        file_path = data.get("file_path")

        if not file_path:
            return jsonify({"success": False, "error": "File path not provided"})

        if not os.path.exists(file_path):
            return jsonify({"success": False, "error": f"File not found: {file_path}"})

        try:
            gen = PatchGenerator()
            modified = gen.detect_modified_functions(file_path)

            return jsonify(
                {
                    "success": True,
                    "file_path": file_path,
                    "modified_functions": modified,
                    "count": len(modified),
                }
            )

        except Exception as e:
            logger.exception(f"Error detecting changes: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/patch/preview", methods=["POST"])
    def api_patch_preview():
        """Get patch file content preview (compile without upload)."""
        data = request.json or {}
        source_content = data.get("source_content")

        if not source_content:
            return jsonify({"success": False, "error": "Source content not provided"})

        device = state.device
        if not device.elf_path or not os.path.exists(device.elf_path):
            return jsonify({"success": False, "error": "ELF file not found"})

        fpb = get_fpb_inject()

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

    # ============== File Watching ==============

    @app.route("/api/watch/status", methods=["GET"])
    def api_watch_status():
        """Get file watcher status."""
        changes = state.get_pending_changes()
        return jsonify(
            {
                "success": True,
                "watching": state.file_watcher is not None,
                "watch_dirs": state.device.watch_dirs,
                "pending_changes": changes,
                "auto_compile": state.device.auto_compile,
            }
        )

    @app.route("/api/watch/start", methods=["POST"])
    def api_watch_start():
        """Start file watching."""
        data = request.json or {}
        dirs = data.get("dirs", state.device.watch_dirs)

        if not dirs:
            return jsonify({"success": False, "error": "No directories to watch"})

        state.device.watch_dirs = dirs
        state.device.watcher_enabled = True
        state.save_config()

        success = _start_file_watcher(dirs)
        return jsonify({"success": success})

    @app.route("/api/watch/stop", methods=["POST"])
    def api_watch_stop():
        """Stop file watching."""
        _stop_file_watcher()
        state.device.watcher_enabled = False
        state.save_config()
        return jsonify({"success": True})

    @app.route("/api/watch/clear", methods=["POST"])
    def api_watch_clear():
        """Clear pending changes."""
        state.clear_pending_changes()
        return jsonify({"success": True})

    @app.route("/api/watch/auto_inject_status", methods=["GET"])
    def api_auto_inject_status():
        """Get auto inject status for real-time UI updates."""
        device = state.device
        return jsonify(
            {
                "success": True,
                "status": device.auto_inject_status,
                "message": device.auto_inject_message,
                "source_file": device.auto_inject_source_file,
                "modified_funcs": device.auto_inject_modified_funcs,
                "progress": device.auto_inject_progress,
                "last_update": device.auto_inject_last_update,
                "result": device.auto_inject_result,  # Include injection statistics
            }
        )

    @app.route("/api/watch/auto_inject_reset", methods=["POST"])
    def api_auto_inject_reset():
        """Reset auto inject status to idle."""
        device = state.device
        device.auto_inject_status = "idle"
        device.auto_inject_message = ""
        device.auto_inject_progress = 0
        device.auto_inject_last_update = 0
        return jsonify({"success": True})

    # ============== Serial Log ==============

    @app.route("/api/log", methods=["GET"])
    def api_log():
        """Get serial communication log."""
        since_id = request.args.get("since", 0, type=int)
        device = state.device

        log_snapshot = list(device.serial_log)
        logs = [entry for entry in log_snapshot if entry["id"] >= since_id]
        next_id = device.log_next_id

        return jsonify({"success": True, "logs": logs, "next_index": next_id})

    @app.route("/api/log/clear", methods=["POST"])
    def api_log_clear():
        """Clear serial communication log."""
        device = state.device

        def do_clear():
            device.serial_log = []
            device.log_next_id = 0

        if device.worker and device.worker.is_running():
            run_in_device_worker(device, do_clear, timeout=1.0)
        else:
            do_clear()

        return jsonify({"success": True})

    # ============== Combined Logs API (for frontend compatibility) ==============

    @app.route("/api/logs", methods=["GET"])
    def api_logs():
        """Get combined tool logs and raw serial data for frontend."""
        tool_since = request.args.get("tool_since", 0, type=int)
        raw_since = request.args.get("raw_since", 0, type=int)
        device = state.device

        # Get tool logs (format: {id, message})
        tool_snapshot = list(device.tool_log)
        tool_logs = []
        for entry in tool_snapshot:
            if entry["id"] >= tool_since:
                tool_logs.append(entry.get("message", ""))
        tool_next = device.tool_log_next_id

        # Get raw serial data
        raw_snapshot = list(device.raw_serial_log)
        raw_entries = [entry for entry in raw_snapshot if entry["id"] >= raw_since]
        # Combine raw data into a single string
        raw_data = "".join(entry.get("data", "") for entry in raw_entries)
        raw_next = device.raw_log_next_id

        return jsonify(
            {
                "success": True,
                "tool_logs": tool_logs,
                "tool_next": tool_next,
                "raw_data": raw_data,
                "raw_next": raw_next,
            }
        )

    @app.route("/api/serial/send", methods=["POST"])
    def api_serial_send():
        """Send raw data to serial port (for interactive terminal)."""
        data = request.json or {}
        raw_data = data.get("data", "")

        if not raw_data:
            return jsonify({"success": False, "error": "No data provided"})

        device = state.device
        if device.ser is None:
            return jsonify({"success": False, "error": "Serial port not opened"})

        worker = device.worker
        if worker and worker.is_running():
            # Write raw data directly
            worker.enqueue("write", raw_data)
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Worker not running"})

    # ============== Raw Serial Log (TX/RX) ==============

    @app.route("/api/raw_log", methods=["GET"])
    def api_raw_log():
        """Get raw serial communication log (TX/RX)."""
        since_id = request.args.get("since", 0, type=int)
        device = state.device

        log_snapshot = list(device.raw_serial_log)
        logs = [entry for entry in log_snapshot if entry["id"] >= since_id]
        next_id = device.raw_log_next_id

        return jsonify({"success": True, "logs": logs, "next_index": next_id})

    @app.route("/api/raw_log/clear", methods=["POST"])
    def api_raw_log_clear():
        """Clear raw serial communication log."""
        device = state.device

        def do_clear():
            device.raw_serial_log = []
            device.raw_log_next_id = 0

        if device.worker and device.worker.is_running():
            run_in_device_worker(device, do_clear, timeout=1.0)
        else:
            do_clear()

        return jsonify({"success": True})

    @app.route("/api/command", methods=["POST"])
    def api_command():
        """Send raw command to device."""
        data = request.json or {}
        command = data.get("command", "")

        if not command:
            return jsonify({"success": False, "error": "Missing command"})

        device = state.device
        if device.ser is None:
            return jsonify({"success": False, "error": "Serial port not opened"})

        if not command.endswith("\n"):
            command += "\n"

        worker = device.worker
        if worker and worker.is_running():
            worker.enqueue("write", command)
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Worker not running"})

    # ============== File Browser ==============

    @app.route("/api/browse", methods=["GET"])
    def api_browse():
        """Browse filesystem for files."""
        path = request.args.get("path", os.path.expanduser("~"))
        filter_ext = request.args.get("filter", "").split(",")

        # Expand ~ to home directory
        if path.startswith("~"):
            path = os.path.expanduser(path)

        if not os.path.exists(path):
            return jsonify(
                {"success": False, "error": "Path not found", "current_path": path}
            )

        if os.path.isfile(path):
            return jsonify(
                {
                    "success": True,
                    "type": "file",
                    "path": path,
                    "current_path": os.path.dirname(path),
                }
            )

        items = []
        try:
            for name in sorted(os.listdir(path)):
                # Skip hidden files
                if name.startswith("."):
                    continue
                full_path = os.path.join(path, name)
                is_dir = os.path.isdir(full_path)

                # Filter by extension for files
                if not is_dir and filter_ext and filter_ext[0]:
                    if not any(name.endswith(ext) for ext in filter_ext):
                        continue

                items.append(
                    {
                        "name": name,
                        "path": full_path,
                        "type": "dir" if is_dir else "file",
                    }
                )
        except PermissionError:
            return jsonify(
                {"success": False, "error": "Permission denied", "current_path": path}
            )

        # Sort: directories first, then files
        items.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower()))

        return jsonify(
            {
                "success": True,
                "type": "directory",
                "current_path": path,
                "parent": os.path.dirname(path),
                "items": items,
            }
        )


# ============== File Watcher Helpers ==============


def _start_file_watcher(dirs):
    """Start file watcher for given directories."""
    try:
        from file_watcher import start_watching

        state.file_watcher = start_watching(dirs, _on_file_change)
        return True
    except Exception as e:
        logger.error(f"Failed to start file watcher: {e}")
        return False


def _stop_file_watcher():
    """Stop file watcher."""
    if state.file_watcher:
        try:
            from file_watcher import stop_watching

            stop_watching(state.file_watcher)
        except:
            pass
        state.file_watcher = None


def _restart_file_watcher():
    """Restart file watcher with current watch dirs."""
    _stop_file_watcher()
    if state.device.watch_dirs:
        _start_file_watcher(state.device.watch_dirs)


def restore_file_watcher():
    """Restore file watcher on startup if watcher_enabled is True."""
    if state.device.watcher_enabled and state.device.watch_dirs:
        _start_file_watcher(state.device.watch_dirs)


def _on_file_change(path, change_type):
    """Callback when a watched file changes."""
    logger.info(f"File changed: {path} ({change_type})")
    state.add_pending_change(path, change_type)

    # Auto compile/inject if enabled
    if state.device.auto_compile:
        _trigger_auto_inject(path)


def _trigger_auto_inject(file_path):
    """Trigger automatic patch generation and injection for a changed file."""
    import time
    import threading

    device = state.device

    # Update status
    device.auto_inject_status = "detecting"
    device.auto_inject_message = f"检测到文件变化: {os.path.basename(file_path)}"
    device.auto_inject_source_file = file_path
    device.auto_inject_progress = 10
    device.auto_inject_last_update = time.time()

    def do_auto_inject():
        try:
            from patch_generator import PatchGenerator

            gen = PatchGenerator()

            # Step 1: Detect modified functions
            device.auto_inject_status = "detecting"
            device.auto_inject_message = "正在检测修改的函数..."
            device.auto_inject_progress = 20
            device.auto_inject_last_update = time.time()

            modified = gen.detect_modified_functions(file_path)

            if not modified:
                device.auto_inject_status = "idle"
                device.auto_inject_modified_funcs = []
                device.auto_inject_progress = 0
                device.auto_inject_last_update = time.time()
                logger.info(f"No modified functions detected in {file_path}")

                # Auto unpatch: if the last injected target function is now unchanged,
                # it means the file has been restored to original state
                if device.inject_active and device.last_inject_target:
                    logger.info(
                        f"Target function '{device.last_inject_target}' restored to original, auto unpatch..."
                    )
                    device.auto_inject_message = "函数已恢复原状，正在清除注入..."
                    try:
                        fpb = get_fpb_inject()
                        fpb.enter_fl_mode()
                        try:
                            success, msg = fpb.unpatch(0)
                            if success:
                                device.inject_active = False
                                device.auto_inject_status = "success"
                                device.auto_inject_message = (
                                    "函数已恢复原状，已自动清除注入"
                                )
                                device.auto_inject_progress = 100
                                logger.info("Auto unpatch successful")
                            else:
                                device.auto_inject_message = f"清除注入失败: {msg}"
                                logger.warning(f"Auto unpatch failed: {msg}")
                        finally:
                            fpb.exit_fl_mode()
                    except Exception as e:
                        device.auto_inject_message = f"清除注入出错: {e}"
                        logger.warning(f"Auto unpatch error: {e}")
                    device.auto_inject_last_update = time.time()
                else:
                    device.auto_inject_message = "未检测到函数修改"

                return

            device.auto_inject_modified_funcs = modified
            logger.info(f"Detected modified functions: {modified}")

            # Step 2: Generate patch
            device.auto_inject_status = "generating"
            device.auto_inject_message = f"正在生成 Patch: {', '.join(modified)}"
            device.auto_inject_progress = 40
            device.auto_inject_last_update = time.time()

            patch_content, injected = gen.generate_patch(file_path, modified)

            if not patch_content:
                device.auto_inject_status = "failed"
                device.auto_inject_message = "生成 Patch 失败"
                device.auto_inject_progress = 0
                device.auto_inject_last_update = time.time()
                return

            # Log first 500 chars of patch for debugging
            logger.info(f"Generated patch (first 500 chars):\n{patch_content[:500]}")
            logger.info(f"Injected functions: {injected}")

            # Check if inject_ functions are in the patch content
            import re

            inject_func_pattern = re.findall(r"\binject_\w+\s*\(", patch_content)
            if inject_func_pattern:
                logger.info(
                    f"Found inject_ function definitions in patch: {inject_func_pattern[:5]}"
                )
            else:
                logger.warning(
                    "No inject_ function definitions found in generated patch!"
                )
                logger.warning(
                    f"Patch content (first 2000 chars):\n{patch_content[:2000]}"
                )

            # Update patch source
            device.patch_source_content = patch_content

            # Step 3: Check if device is connected
            if device.ser is None or not device.ser.isOpen():
                device.auto_inject_status = "failed"
                device.auto_inject_message = "设备未连接，Patch 已生成但未注入"
                device.auto_inject_progress = 50
                device.auto_inject_last_update = time.time()
                return

            # Step 4: Enter fl interactive mode
            fpb = get_fpb_inject()

            device.auto_inject_status = "compiling"
            device.auto_inject_message = "进入 fl 交互模式..."
            device.auto_inject_progress = 55
            device.auto_inject_last_update = time.time()

            fpb.enter_fl_mode()

            try:
                # Step 5: Perform multi-function injection
                device.auto_inject_message = "正在编译..."
                device.auto_inject_progress = 60
                device.auto_inject_last_update = time.time()

                # Get source file extension from the original file
                source_ext = os.path.splitext(file_path)[1] or ".c"

                device.auto_inject_status = "injecting"
                func_list = ", ".join(modified[:3])
                if len(modified) > 3:
                    func_list += f" 等 {len(modified)} 个函数"
                device.auto_inject_message = f"正在注入: {func_list}"
                device.auto_inject_progress = 80
                device.auto_inject_last_update = time.time()

                # Use inject_multi for multi-function injection
                # Each inject_* function gets its own Slot with smart reuse
                success, result = fpb.inject_multi(
                    source_content=patch_content,
                    patch_mode=device.patch_mode,
                    source_ext=source_ext,
                )

                if success:
                    successful_count = result.get("successful_count", 0)
                    total_count = result.get("total_count", 0)
                    injections = result.get("injections", [])

                    # Build summary message
                    if successful_count == total_count:
                        status_msg = f"注入成功: {successful_count} 个函数"
                    else:
                        status_msg = (
                            f"部分成功: {successful_count}/{total_count} 个函数"
                        )

                    # Add injected function names
                    injected_names = [
                        inj.get("target_func", "?")
                        for inj in injections
                        if inj.get("success", False)
                    ]
                    if injected_names:
                        status_msg += f" ({', '.join(injected_names[:3])})"
                        if len(injected_names) > 3:
                            status_msg += f" 等"

                    device.auto_inject_status = "success"
                    device.auto_inject_message = status_msg
                    device.auto_inject_progress = 100
                    device.auto_inject_result = result
                    device.inject_active = True
                    device.last_inject_time = time.time()

                    # Set last inject target/func from first successful injection
                    for inj in injections:
                        if inj.get("success", False):
                            device.last_inject_target = inj.get("target_func")
                            device.last_inject_func = inj.get("inject_func")
                            break

                    logger.info(
                        f"Auto inject successful: {successful_count}/{total_count} functions"
                    )

                    # Log errors if any
                    errors = result.get("errors", [])
                    if errors:
                        for err in errors:
                            logger.warning(f"Injection warning: {err}")

                    # Update slot info after successful injection
                    fpb.info()
                else:
                    device.auto_inject_status = "failed"
                    error_msg = result.get("error", "Unknown error")
                    errors = result.get("errors", [])
                    if errors:
                        error_msg = "; ".join(errors[:3])
                    device.auto_inject_message = f"注入失败: {error_msg}"
                    device.auto_inject_progress = 0
                    logger.error(f"Auto inject failed: {error_msg}")

            finally:
                # Step 6: Exit fl interactive mode
                device.auto_inject_message += " (退出 fl 模式)"
                device.auto_inject_last_update = time.time()
                fpb.exit_fl_mode()

            device.auto_inject_last_update = time.time()

        except Exception as e:
            device.auto_inject_status = "failed"
            device.auto_inject_message = f"错误: {str(e)}"
            device.auto_inject_progress = 0
            device.auto_inject_last_update = time.time()
            logger.exception(f"Auto inject error: {e}")

    # Run in background thread to not block the watcher
    thread = threading.Thread(target=do_auto_inject, daemon=True)
    thread.start()

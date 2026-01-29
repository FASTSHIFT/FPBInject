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

from core.state import state
from services.device_worker import (
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


def _build_slot_response(device, app_state):
    """
    Build slot response data from cached device info.

    This is used by both /api/fpb/info and /api/logs to provide
    consistent slot information to the frontend.

    Args:
        device: DeviceState instance
        app_state: AppState instance

    Returns:
        dict with 'slots' and 'memory' keys, or None if no info available
    """
    info = device.device_info
    if info is None:
        return None

    # Ensure symbols are loaded for address lookup
    fpb = get_fpb_inject()
    if (
        not app_state.symbols_loaded
        and device.elf_path
        and os.path.exists(device.elf_path)
    ):
        app_state.symbols = fpb.get_symbols(device.elf_path)
        app_state.symbols_loaded = True

    # Get symbols for address lookup
    symbols_reverse = {}
    if app_state.symbols:
        symbols_reverse = {v: k for k, v in app_state.symbols.items()}

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
    memory = {
        "is_dynamic": info.get("is_dynamic", False),
        "base": info.get("base", 0),
        "size": info.get("size", 0),
        "used": info.get("used", 0),
    }

    return {"slots": slots, "memory": memory}


def register_routes(app):
    """Register all routes with the Flask app."""
    # Register blueprints from app/routes/
    from app.routes import register_blueprints

    register_blueprints(app)

    @app.route("/")
    def index():
        """Serve the main web interface."""
        return render_template("index.html")

    # ============== Port & Connection ==============
    # NOTE: Connection routes have been migrated to app/routes/connection.py

    # ============== FPB Inject Operations ==============
    # NOTE: FPB routes have been migrated to app/routes/fpb.py

    # ============== Symbols ==============
    # NOTE: Symbols routes have been migrated to app/routes/symbols.py

    # ============== Patch Source Management ==============
    # NOTE: Patch routes have been migrated to app/routes/patch.py

    # ============== File Watching ==============
    # NOTE: Watch routes have been migrated to app/routes/watch.py

    # ============== Serial Log ==============
    # NOTE: Log routes have been migrated to app/routes/logs.py

    # ============== File Browser ==============
    # NOTE: File browser routes have been migrated to app/routes/files.py


# ============== File Watcher Helpers ==============


def _start_file_watcher(dirs):
    """Start file watcher for given directories."""
    try:
        from services.file_watcher import start_watching

        state.file_watcher = start_watching(dirs, _on_file_change)
        return True
    except Exception as e:
        logger.error(f"Failed to start file watcher: {e}")
        return False


def _stop_file_watcher():
    """Stop file watcher."""
    if state.file_watcher:
        try:
            from services.file_watcher import stop_watching

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
    """Restore file watcher on startup if auto_compile is enabled."""
    if state.device.auto_compile and state.device.watch_dirs:
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
    device.auto_inject_message = f"File change detected: {os.path.basename(file_path)}"
    device.auto_inject_source_file = file_path
    device.auto_inject_progress = 10
    device.auto_inject_last_update = time.time()

    def do_auto_inject():
        try:
            from core.patch_generator import PatchGenerator

            gen = PatchGenerator()

            # Step 1: Find FPB_INJECT markers
            device.auto_inject_status = "detecting"
            device.auto_inject_message = "Searching for FPB_INJECT markers..."
            device.auto_inject_progress = 20
            device.auto_inject_last_update = time.time()

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            marked = gen.find_marked_functions(content)

            if not marked:
                device.auto_inject_status = "idle"
                device.auto_inject_modified_funcs = []
                device.auto_inject_progress = 0
                device.auto_inject_last_update = time.time()
                logger.info(f"No FPB_INJECT markers found in {file_path}")

                # Auto unpatch: if the last injected target function is now unmarked,
                # it means the marker has been removed
                if device.inject_active and device.last_inject_target:
                    logger.info(
                        f"Target function '{device.last_inject_target}' marker removed, auto unpatch..."
                    )
                    device.auto_inject_message = (
                        "Markers removed, clearing injection..."
                    )
                    try:
                        fpb = get_fpb_inject()
                        fpb.enter_fl_mode()
                        try:
                            success, msg = fpb.unpatch(0)
                            if success:
                                device.inject_active = False
                                device.auto_inject_status = "success"
                                device.auto_inject_message = (
                                    "Markers removed, injection automatically cleared"
                                )
                                device.auto_inject_progress = 100
                                logger.info("Auto unpatch successful")
                            else:
                                device.auto_inject_message = (
                                    f"Failed to clear injection: {msg}"
                                )
                                logger.warning(f"Auto unpatch failed: {msg}")
                        finally:
                            fpb.exit_fl_mode()
                    except Exception as e:
                        device.auto_inject_message = f"Error clearing injection: {e}"
                        logger.warning(f"Auto unpatch error: {e}")
                    device.auto_inject_last_update = time.time()
                else:
                    device.auto_inject_message = "No FPB_INJECT markers found"

                return

            device.auto_inject_modified_funcs = marked
            logger.info(f"Found marked functions: {marked}")

            # Step 2: Generate patch
            device.auto_inject_status = "generating"
            device.auto_inject_message = f"Generating Patch: {', '.join(marked)}"
            device.auto_inject_progress = 40
            device.auto_inject_last_update = time.time()

            patch_content, injected = gen.generate_patch(file_path)

            if not patch_content:
                device.auto_inject_status = "failed"
                device.auto_inject_message = "Failed to generate Patch"
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
                device.auto_inject_message = (
                    "Device not connected, Patch generated but not injected"
                )
                device.auto_inject_progress = 50
                device.auto_inject_last_update = time.time()
                return

            # Step 4: Enter fl interactive mode
            fpb = get_fpb_inject()

            device.auto_inject_status = "compiling"
            device.auto_inject_message = "Entering fl interactive mode..."
            device.auto_inject_progress = 55
            device.auto_inject_last_update = time.time()

            fpb.enter_fl_mode()

            try:
                # Step 5: Perform multi-function injection
                device.auto_inject_message = "Compiling..."
                device.auto_inject_progress = 60
                device.auto_inject_last_update = time.time()

                # Get source file extension from the original file
                source_ext = os.path.splitext(file_path)[1] or ".c"

                device.auto_inject_status = "injecting"
                func_list = ", ".join(marked[:3])
                if len(marked) > 3:
                    func_list += f" etc. {len(marked)} functions"
                device.auto_inject_message = f"Injecting: {func_list}"
                device.auto_inject_progress = 80
                device.auto_inject_last_update = time.time()

                # Use inject_multi for multi-function injection
                # Each inject_* function gets its own Slot with smart reuse
                success, result = fpb.inject_multi(
                    source_content=patch_content,
                    patch_mode=device.patch_mode,
                    source_ext=source_ext,
                    original_source_file=file_path,
                )

                if success:
                    successful_count = result.get("successful_count", 0)
                    total_count = result.get("total_count", 0)
                    injections = result.get("injections", [])

                    # Build summary message
                    if successful_count == total_count:
                        status_msg = (
                            f"Injection successful: {successful_count} functions"
                        )
                    else:
                        status_msg = f"Partially successful: {successful_count}/{total_count} functions"

                    # Add injected function names
                    injected_names = [
                        inj.get("target_func", "?")
                        for inj in injections
                        if inj.get("success", False)
                    ]
                    if injected_names:
                        status_msg += f" ({', '.join(injected_names[:3])})"
                        if len(injected_names) > 3:
                            status_msg += f" etc."

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
                    device.auto_inject_message = f"Injection failed: {error_msg}"
                    device.auto_inject_progress = 0
                    logger.error(f"Auto inject failed: {error_msg}")

            finally:
                # Step 6: Exit fl interactive mode
                device.auto_inject_message += " (Exiting fl mode)"
                device.auto_inject_last_update = time.time()
                fpb.exit_fl_mode()

            device.auto_inject_last_update = time.time()

        except Exception as e:
            device.auto_inject_status = "failed"
            device.auto_inject_message = f"Error: {str(e)}"
            device.auto_inject_progress = 0
            device.auto_inject_last_update = time.time()
            logger.exception(f"Auto inject error: {e}")

    # Run in background thread to not block the watcher
    thread = threading.Thread(target=do_auto_inject, daemon=True)
    thread.start()

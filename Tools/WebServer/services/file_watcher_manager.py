#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
File watcher management for FPBInject Web Server.

Provides functions to start/stop file watching and handle file change events.
"""

import logging
import os
import threading
import time

from core.state import state

logger = logging.getLogger(__name__)

# ELF file watcher instance
_elf_watcher = None


def start_file_watcher(dirs):
    """Start file watcher for given directories."""
    try:
        from services.file_watcher import start_watching

        state.file_watcher = start_watching(dirs, _on_file_change)
        return True
    except Exception as e:
        logger.error(f"Failed to start file watcher: {e}")
        return False


def stop_file_watcher():
    """Stop file watcher."""
    if state.file_watcher:
        try:
            from services.file_watcher import stop_watching

            stop_watching(state.file_watcher)
        except Exception:
            pass
        state.file_watcher = None


def restart_file_watcher():
    """Restart file watcher with current watch dirs."""
    stop_file_watcher()
    if state.device.watch_dirs:
        start_file_watcher(state.device.watch_dirs)


def restore_file_watcher():
    """Restore file watcher on startup if auto_compile is enabled."""
    if state.device.auto_compile and state.device.watch_dirs:
        start_file_watcher(state.device.watch_dirs)


# =============================================================================
# ELF File Watcher
# =============================================================================


def start_elf_watcher(elf_path):
    """Start watching ELF file for changes."""
    global _elf_watcher

    stop_elf_watcher()

    if not elf_path or not os.path.exists(elf_path):
        return False

    try:
        from services.file_watcher import start_watching

        elf_dir = os.path.dirname(elf_path)

        # Watch the directory containing the ELF file
        # Filter to only watch .elf files
        _elf_watcher = start_watching(
            [elf_dir], _on_elf_file_change, extensions=[".elf"]
        )

        # Record initial mtime
        state.device.elf_file_mtime = os.path.getmtime(elf_path)
        state.device.elf_file_changed = False

        logger.info(f"Started ELF file watcher for: {elf_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to start ELF watcher: {e}")
        return False


def stop_elf_watcher():
    """Stop ELF file watcher."""
    global _elf_watcher

    if _elf_watcher:
        try:
            from services.file_watcher import stop_watching

            stop_watching(_elf_watcher)
        except Exception:
            pass
        _elf_watcher = None
        logger.info("Stopped ELF file watcher")


def check_elf_file_changed():
    """
    Check if ELF file has changed since last load.

    Returns:
        dict with 'changed' (bool) and 'elf_path' (str)
    """
    device = state.device
    elf_path = device.elf_path

    if not elf_path or not os.path.exists(elf_path):
        return {"changed": False, "elf_path": elf_path}

    try:
        current_mtime = os.path.getmtime(elf_path)
        if device.elf_file_mtime > 0 and current_mtime > device.elf_file_mtime:
            device.elf_file_changed = True
    except OSError:
        pass

    return {"changed": device.elf_file_changed, "elf_path": elf_path}


def acknowledge_elf_change():
    """Acknowledge ELF file change (user chose to reload or ignore)."""
    device = state.device
    device.elf_file_changed = False

    # Update mtime to current
    if device.elf_path and os.path.exists(device.elf_path):
        try:
            device.elf_file_mtime = os.path.getmtime(device.elf_path)
        except OSError:
            pass

    # Clear Ghidra decompilation cache since ELF file changed
    try:
        from core.elf_utils import clear_ghidra_cache

        clear_ghidra_cache()
    except ImportError:
        pass


def _on_elf_file_change(path, change_type):
    """Callback when ELF file changes."""
    device = state.device

    # Only care about the configured ELF file
    if not device.elf_path:
        return

    # Normalize paths for comparison
    changed_path = os.path.normpath(os.path.abspath(path))
    elf_path = os.path.normpath(os.path.abspath(device.elf_path))

    if changed_path == elf_path:
        logger.info(f"ELF file changed: {path} ({change_type})")
        device.elf_file_changed = True

        # Update mtime
        try:
            device.elf_file_mtime = os.path.getmtime(path)
        except OSError:
            pass


def _on_file_change(path, change_type):
    """Callback when a watched file changes."""
    logger.info(f"File changed: {path} ({change_type})")
    state.add_pending_change(path, change_type)

    # Auto compile/inject if enabled
    if state.device.auto_compile:
        _trigger_auto_inject(path)


def _trigger_auto_inject(file_path):
    """Trigger automatic patch generation and injection for a changed file."""
    from routes import get_fpb_inject

    device = state.device

    # Update status
    device.auto_inject_status = "detecting"
    device.auto_inject_message = f"File change detected: {os.path.basename(file_path)}"
    device.auto_inject_source_file = file_path
    device.auto_inject_progress = 10
    device.auto_inject_last_update = time.time()

    # Timeout for serial operations dispatched to the fpb-worker thread.
    # inject_multi involves compile + upload + patch for each function,
    # so we need a generous timeout.
    WORKER_TIMEOUT = 120.0

    def do_auto_inject():
        try:
            from core.patch_generator import PatchGenerator
            from services.device_worker import run_in_device_worker

            gen = PatchGenerator()

            # Step 1: Find FPB_INJECT markers (in-place mode)
            # This is pure file I/O — no serial access, safe in any thread.
            device.auto_inject_status = "detecting"
            device.auto_inject_message = "Searching for FPB_INJECT markers..."
            device.auto_inject_progress = 20
            device.auto_inject_last_update = time.time()

            inplace_file, marked = gen.generate_patch_inplace(file_path)

            if not marked:
                device.auto_inject_status = "idle"
                device.auto_inject_modified_funcs = []
                device.auto_inject_progress = 0
                device.auto_inject_last_update = time.time()
                logger.info(f"No FPB_INJECT markers found in {file_path}")

                # Auto unpatch: if the last injected target function is now unmarked,
                # it means the marker has been removed.
                # Serial I/O must go through DeviceWorker.
                if device.inject_active and device.last_inject_target:
                    logger.info(
                        f"Target function '{device.last_inject_target}' marker removed, auto unpatch..."
                    )
                    device.auto_inject_message = (
                        "Markers removed, clearing injection..."
                    )

                    unpatch_result = {"success": False, "msg": ""}

                    def do_unpatch():
                        try:
                            fpb = get_fpb_inject()
                            fpb.enter_fl_mode()
                            try:
                                ok, msg = fpb.unpatch(0)
                                unpatch_result["success"] = ok
                                unpatch_result["msg"] = msg
                            finally:
                                fpb.exit_fl_mode()
                        except Exception as e:
                            unpatch_result["msg"] = str(e)

                    if run_in_device_worker(device, do_unpatch, timeout=WORKER_TIMEOUT):
                        if unpatch_result["success"]:
                            device.inject_active = False
                            device.auto_inject_status = "success"
                            device.auto_inject_message = (
                                "Markers removed, injection automatically cleared"
                            )
                            device.auto_inject_progress = 100
                            logger.info("Auto unpatch successful")
                        else:
                            device.auto_inject_message = (
                                f"Failed to clear injection: {unpatch_result['msg']}"
                            )
                            logger.warning(
                                f"Auto unpatch failed: {unpatch_result['msg']}"
                            )
                    else:
                        device.auto_inject_message = (
                            "Failed to clear injection: DeviceWorker timeout"
                        )
                        logger.warning("Auto unpatch: DeviceWorker timeout")

                    device.auto_inject_last_update = time.time()
                else:
                    device.auto_inject_message = "No FPB_INJECT markers found"

                return

            device.auto_inject_modified_funcs = marked
            logger.info(f"Found marked functions (in-place): {marked}")

            # Step 2: Skip patch generation - use in-place compilation
            device.auto_inject_status = "generating"
            device.auto_inject_message = f"In-place compile: {', '.join(marked)}"
            device.auto_inject_progress = 40
            device.auto_inject_last_update = time.time()

            logger.info(f"In-place mode: compiling {file_path} directly")
            logger.info(f"Inject functions: {marked}")

            # Update patch source (read original file for display)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                device.patch_source_content = f.read()

            # Step 3: Check if device is connected
            if device.ser is None or not device.ser.isOpen():
                device.auto_inject_status = "failed"
                device.auto_inject_message = (
                    "Device not connected, Patch generated but not injected"
                )
                device.auto_inject_progress = 50
                device.auto_inject_last_update = time.time()
                return

            # Step 4 & 5: Enter fl mode, inject, exit fl mode
            # All serial I/O is dispatched to the fpb-worker thread via
            # DeviceWorker to avoid ThreadCheckedSerial violations.
            inject_result = {"success": False, "result": {}}

            def do_inject():
                fpb = get_fpb_inject()

                device.auto_inject_status = "compiling"
                device.auto_inject_message = "Entering fl interactive mode..."
                device.auto_inject_progress = 55
                device.auto_inject_last_update = time.time()

                fpb.enter_fl_mode()

                try:
                    device.auto_inject_message = "Compiling..."
                    device.auto_inject_progress = 60
                    device.auto_inject_last_update = time.time()

                    source_ext = os.path.splitext(file_path)[1] or ".c"

                    device.auto_inject_status = "injecting"
                    func_list = ", ".join(marked[:3])
                    if len(marked) > 3:
                        func_list += f" etc. {len(marked)} functions"
                    device.auto_inject_message = f"Injecting: {func_list}"
                    device.auto_inject_progress = 80
                    device.auto_inject_last_update = time.time()

                    success, result = fpb.inject_multi(
                        source_file=file_path,
                        inject_functions=marked,
                        patch_mode=device.patch_mode,
                        source_ext=source_ext,
                        original_source_file=file_path,
                    )

                    inject_result["success"] = success
                    inject_result["result"] = result

                    # Update slot info after injection attempt
                    if success:
                        fpb.info()
                finally:
                    fpb.exit_fl_mode()

            if not run_in_device_worker(device, do_inject, timeout=WORKER_TIMEOUT):
                device.auto_inject_status = "failed"
                device.auto_inject_message = "Injection failed: DeviceWorker timeout"
                device.auto_inject_progress = 0
                device.auto_inject_last_update = time.time()
                logger.error("Auto inject: DeviceWorker timeout")
                return

            # Step 6: Process injection result
            success = inject_result["success"]
            result = inject_result["result"]

            if success:
                successful_count = result.get("successful_count", 0)
                total_count = result.get("total_count", 0)
                injections = result.get("injections", [])

                if successful_count == total_count:
                    status_msg = f"Injection successful: {successful_count} functions"
                else:
                    status_msg = f"Partially successful: {successful_count}/{total_count} functions"

                injected_names = [
                    inj.get("target_func", "?")
                    for inj in injections
                    if inj.get("success", False)
                ]
                if injected_names:
                    status_msg += f" ({', '.join(injected_names[:3])})"
                    if len(injected_names) > 3:
                        status_msg += " etc."

                device.auto_inject_status = "success"
                device.auto_inject_message = status_msg
                device.auto_inject_progress = 100
                device.auto_inject_result = result
                device.inject_active = True
                device.last_inject_time = time.time()

                for inj in injections:
                    if inj.get("success", False):
                        device.last_inject_target = inj.get("target_func")
                        device.last_inject_func = inj.get("inject_func")
                        break

                logger.info(
                    f"Auto inject successful: {successful_count}/{total_count} functions"
                )

                errors = result.get("errors", [])
                if errors:
                    for err in errors:
                        logger.warning(f"Injection warning: {err}")
            else:
                device.auto_inject_status = "failed"
                error_msg = result.get("error", "Unknown error")
                errors = result.get("errors", [])
                if errors:
                    error_msg = "; ".join(errors[:3])
                device.auto_inject_message = f"Injection failed: {error_msg}"
                device.auto_inject_progress = 0
                logger.error(f"Auto inject failed: {error_msg}")

            device.auto_inject_last_update = time.time()

        except Exception as e:
            device.auto_inject_status = "failed"
            device.auto_inject_message = f"Error: {str(e)}"
            device.auto_inject_progress = 0
            device.auto_inject_last_update = time.time()
            logger.exception(f"Auto inject error: {e}")

    # Run in background thread to not block the watcher.
    # Note: serial I/O inside do_auto_inject is dispatched to the
    # fpb-worker thread via run_in_device_worker, so no thread violation.
    thread = threading.Thread(target=do_auto_inject, daemon=True)
    thread.start()

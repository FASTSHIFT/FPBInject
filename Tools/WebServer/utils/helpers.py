#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Shared helper functions for FPBInject Web Server.
"""

import os


def build_slot_response(device, app_state, get_fpb_inject):
    """
    Build slot response data from cached device info.

    This is used by both /api/fpb/info and /api/logs to provide
    consistent slot information to the frontend.

    Args:
        device: DeviceState instance
        app_state: AppState instance
        get_fpb_inject: Function to get FPBInject instance

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
    # FPB v2 supports 8 slots, v1 supports 6
    fpb_version = info.get("fpb_version", 1)
    max_slots = 8 if fpb_version >= 2 else 6
    for i in range(max_slots):
        slot_data = next((s for s in device_slots if s.get("id") == i), None)
        if slot_data and slot_data.get("occupied"):
            orig_addr = slot_data.get("orig_addr", 0)
            target_addr = slot_data.get("target_addr", 0)
            code_size = slot_data.get("code_size", 0)
            # Lookup function name from symbols
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

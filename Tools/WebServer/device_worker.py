#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Device worker thread for FPBInject Web Server.

DEPRECATED: This module has been moved to services/device_worker.py
This file is kept for backward compatibility.
"""

# Re-export from new location for backward compatibility
from services.device_worker import (
    DeviceWorker,
    get_worker,
    start_worker,
    stop_worker,
    run_in_device_worker,
    get_device_timer_manager,
)

__all__ = [
    "DeviceWorker",
    "get_worker",
    "start_worker",
    "stop_worker",
    "run_in_device_worker",
    "get_device_timer_manager",
]

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
File watcher module for FPBInject Web Server.

DEPRECATED: This module has been moved to services/file_watcher.py
This file is kept for backward compatibility.
"""

# Re-export from new location for backward compatibility
from services.file_watcher import (
    FileChangeHandler,
    PollingWatcher,
    FileWatcher,
    start_watching,
    stop_watching,
    WATCHDOG_AVAILABLE,
)

__all__ = [
    "FileChangeHandler",
    "PollingWatcher",
    "FileWatcher",
    "start_watching",
    "stop_watching",
    "WATCHDOG_AVAILABLE",
]

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
State management for FPBInject Web Server.

DEPRECATED: This module has been moved to core/state.py
This file is kept for backward compatibility.
"""

# Re-export from new location for backward compatibility
from core.state import (
    CONFIG_FILE,
    CONFIG_VERSION,
    PERSISTENT_KEYS,
    DeviceState,
    AppState,
    state,
)

__all__ = [
    "CONFIG_FILE",
    "CONFIG_VERSION",
    "PERSISTENT_KEYS",
    "DeviceState",
    "AppState",
    "state",
]

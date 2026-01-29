#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Timer module for FPBInject Web Server.

DEPRECATED: This module has been moved to services/timer.py
This file is kept for backward compatibility.
"""

# Re-export from new location for backward compatibility
from services.timer import Timer, TimerManager

__all__ = ["Timer", "TimerManager"]

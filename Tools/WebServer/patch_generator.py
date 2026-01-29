#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Patch Generator for FPBInject.

DEPRECATED: This module has been moved to core/patch_generator.py
This file is kept for backward compatibility.
"""

# Re-export from new location for backward compatibility
from core.patch_generator import (
    FPB_INJECT_MARKER,
    PatchGenerator,
    find_function_signature,
    check_dependencies,
)

__all__ = [
    "FPB_INJECT_MARKER",
    "PatchGenerator",
    "find_function_signature",
    "check_dependencies",
]

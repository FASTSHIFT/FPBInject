#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Toolchain utilities for FPBInject Web Server.

Provides common functions for working with ARM toolchain.
"""

import os
from typing import Optional


def get_tool_path(tool_name: str, toolchain_path: Optional[str] = None) -> str:
    """
    Get full path for a toolchain tool.

    Args:
        tool_name: Name of the tool (e.g., 'arm-none-eabi-gcc')
        toolchain_path: Optional path to toolchain directory

    Returns:
        Full path to tool if found in toolchain_path, otherwise just tool_name
    """
    if toolchain_path:
        full_path = os.path.join(toolchain_path, tool_name)
        if os.path.exists(full_path):
            return full_path
    return tool_name


def get_subprocess_env(toolchain_path: Optional[str] = None) -> dict:
    """
    Get environment dict with toolchain path prepended to PATH.

    Args:
        toolchain_path: Optional path to toolchain directory

    Returns:
        Environment dict suitable for subprocess calls
    """
    env = os.environ.copy()
    if toolchain_path and os.path.isdir(toolchain_path):
        current_path = env.get("PATH", "")
        env["PATH"] = f"{toolchain_path}:{current_path}"
    return env

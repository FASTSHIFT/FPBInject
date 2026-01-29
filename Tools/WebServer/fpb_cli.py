#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPBInject CLI - Lightweight command-line interface for AI integration.

DEPRECATED: This module has been moved to cli/fpb_cli.py
This file is kept for backward compatibility.
"""

# Re-export from new location for backward compatibility
from cli.fpb_cli import (
    FPBCLIError,
    DeviceState,
    FPBCLI,
    HAS_SERIAL,
    main,
)

__all__ = [
    "FPBCLIError",
    "DeviceState",
    "FPBCLI",
    "HAS_SERIAL",
    "main",
]

if __name__ == "__main__":
    main()

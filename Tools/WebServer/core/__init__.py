#!/usr/bin/env python3
"""FPBInject Core Package."""

from core.safe_parser import (
    safe_shlex_split,
    quote_path,
    normalize_path,
    FPBMarkerParser,
    CommandBuilder,
)
from core.linker_script import (
    LinkerScriptConfig,
    LinkerScriptGenerator,
    create_linker_script,
)

__all__ = [
    "safe_shlex_split",
    "quote_path",
    "normalize_path",
    "FPBMarkerParser",
    "CommandBuilder",
    "LinkerScriptConfig",
    "LinkerScriptGenerator",
    "create_linker_script",
]

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Configuration schema definition for FPBInject Web Server.

This module defines all configuration items in a centralized schema.
Adding a new config item only requires modifying this file.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional, Tuple
from enum import Enum


class ConfigType(Enum):
    """Configuration item types."""

    STRING = "string"
    PATH = "path"  # Generic path with browse button
    DIR_PATH = "dir_path"  # Directory path
    FILE_PATH = "file_path"  # File path with extension filter
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    PATH_LIST = "path_list"  # List of directory paths


class ConfigGroup(Enum):
    """Configuration groups for UI organization."""

    CONNECTION = "connection"  # Serial connection (not in sidebar config)
    PROJECT = "project"  # Project paths
    INJECT = "inject"  # Injection settings
    TRANSFER = "transfer"  # Transfer parameters
    LOGGING = "logging"  # Logging settings
    TOOLS = "tools"  # Analysis tools


# Group display labels
GROUP_LABELS = {
    ConfigGroup.CONNECTION: "Connection",
    ConfigGroup.PROJECT: "Project Paths",
    ConfigGroup.INJECT: "Injection",
    ConfigGroup.TRANSFER: "Transfer",
    ConfigGroup.LOGGING: "Logging",
    ConfigGroup.TOOLS: "Analysis Tools",
}


@dataclass
class ConfigItem:
    """Configuration item definition."""

    key: str  # Config key name (snake_case)
    label: str  # Display label
    group: ConfigGroup  # Group for UI organization
    config_type: ConfigType  # Value type
    default: Any  # Default value
    tooltip: str = ""  # Tooltip text
    # Type-specific options
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    unit: str = ""  # Unit label (Bytes, ms, times)
    options: List[Tuple[str, str]] = field(default_factory=list)  # Select options
    file_ext: str = ""  # File extension filter
    # UI control
    depends_on: Optional[str] = None  # Dependent config key
    show_in_sidebar: bool = True  # Whether to show in sidebar config
    order: int = 0  # Sort order within group
    # Value transformation
    ui_multiplier: float = 1.0  # Multiply by this when displaying in UI

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Convert enums to strings
        result["group"] = self.group.value
        result["config_type"] = self.config_type.value
        return result


# =============================================================================
# Configuration Schema Definition
# =============================================================================

CONFIG_SCHEMA: List[ConfigItem] = [
    # === Connection (not shown in sidebar config panel) ===
    ConfigItem(
        key="port",
        label="Serial Port",
        group=ConfigGroup.CONNECTION,
        config_type=ConfigType.STRING,
        default=None,
        show_in_sidebar=False,
        order=10,
    ),
    ConfigItem(
        key="baudrate",
        label="Baud Rate",
        group=ConfigGroup.CONNECTION,
        config_type=ConfigType.NUMBER,
        default=115200,
        show_in_sidebar=False,
        order=20,
    ),
    ConfigItem(
        key="auto_connect",
        label="Auto Connect",
        group=ConfigGroup.CONNECTION,
        config_type=ConfigType.BOOLEAN,
        default=False,
        show_in_sidebar=False,
        order=30,
    ),
    # === Project Paths ===
    ConfigItem(
        key="elf_path",
        label="ELF Path",
        group=ConfigGroup.PROJECT,
        config_type=ConfigType.FILE_PATH,
        default="",
        tooltip="Path to the compiled ELF file for symbol lookup and disassembly",
        file_ext=".elf",
        order=10,
    ),
    ConfigItem(
        key="compile_commands_path",
        label="Compile DB",
        group=ConfigGroup.PROJECT,
        config_type=ConfigType.FILE_PATH,
        default="",
        tooltip="Path to compile_commands.json for accurate compile flags",
        file_ext=".json",
        order=20,
    ),
    ConfigItem(
        key="toolchain_path",
        label="Toolchain",
        group=ConfigGroup.PROJECT,
        config_type=ConfigType.DIR_PATH,
        default="",
        tooltip="Path to cross-compiler toolchain bin directory",
        order=30,
    ),
    # === Injection Settings ===
    ConfigItem(
        key="patch_mode",
        label="Inject Mode",
        group=ConfigGroup.INJECT,
        config_type=ConfigType.SELECT,
        default="trampoline",
        tooltip="Trampoline: Use code trampoline (default)\n"
        "DebugMonitor: Use DebugMonitor exception\n"
        "Direct: Direct code replacement",
        options=[
            ("trampoline", "Trampoline"),
            ("debugmon", "DebugMonitor"),
            ("direct", "Direct"),
        ],
        order=10,
    ),
    ConfigItem(
        key="auto_compile",
        label="Auto Inject on Save",
        group=ConfigGroup.INJECT,
        config_type=ConfigType.BOOLEAN,
        default=False,
        tooltip="Automatically compile and inject when source files are saved",
        order=20,
    ),
    ConfigItem(
        key="watch_dirs",
        label="Watch Directories",
        group=ConfigGroup.INJECT,
        config_type=ConfigType.PATH_LIST,
        default=[],
        tooltip="Directories to watch for file changes",
        depends_on="auto_compile",
        order=30,
    ),
    # === Transfer Parameters ===
    ConfigItem(
        key="chunk_size",
        label="Chunk Size",
        group=ConfigGroup.TRANSFER,
        config_type=ConfigType.NUMBER,
        default=128,
        tooltip="Size of each uploaded data block. Smaller values are more stable but slower.",
        min_value=16,
        max_value=1024,
        step=16,
        unit="Bytes",
        order=10,
    ),
    ConfigItem(
        key="tx_chunk_size",
        label="TX Chunk",
        group=ConfigGroup.TRANSFER,
        config_type=ConfigType.NUMBER,
        default=0,
        tooltip="TX chunk size for serial commands (bytes). 0 = disabled. "
        "Workaround for slow serial drivers.",
        min_value=0,
        max_value=256,
        step=8,
        unit="Bytes",
        order=20,
    ),
    ConfigItem(
        key="tx_chunk_delay",
        label="TX Delay",
        group=ConfigGroup.TRANSFER,
        config_type=ConfigType.NUMBER,
        default=0.005,
        tooltip="Delay between TX chunks. Only used when TX Chunk > 0.",
        min_value=0.001,
        max_value=0.1,
        step=0.001,
        unit="ms",
        ui_multiplier=1000,  # Display as milliseconds
        order=30,
    ),
    ConfigItem(
        key="transfer_max_retries",
        label="Max Retries",
        group=ConfigGroup.TRANSFER,
        config_type=ConfigType.NUMBER,
        default=10,
        tooltip="Maximum retry attempts for file transfer when CRC mismatch occurs.",
        min_value=0,
        max_value=20,
        step=1,
        unit="times",
        order=40,
    ),
    ConfigItem(
        key="verify_crc",
        label="Verify CRC after Transfer",
        group=ConfigGroup.TRANSFER,
        config_type=ConfigType.BOOLEAN,
        default=True,
        tooltip="Verify file integrity with CRC after transfer",
        order=50,
    ),
    # === Logging Settings ===
    ConfigItem(
        key="log_file_path",
        label="Log Path",
        group=ConfigGroup.LOGGING,
        config_type=ConfigType.PATH,
        default="",
        tooltip="Path to save serial logs",
        order=10,
    ),
    ConfigItem(
        key="log_file_enabled",
        label="Record Serial Logs",
        group=ConfigGroup.LOGGING,
        config_type=ConfigType.BOOLEAN,
        default=False,
        tooltip="Record serial communication logs to file",
        order=20,
    ),
    # === Analysis Tools ===
    ConfigItem(
        key="ghidra_path",
        label="Ghidra Path",
        group=ConfigGroup.TOOLS,
        config_type=ConfigType.DIR_PATH,
        default="",
        tooltip="Path to Ghidra installation directory (containing support/analyzeHeadless)",
        order=10,
    ),
    ConfigItem(
        key="enable_decompile",
        label="Enable Decompilation",
        group=ConfigGroup.TOOLS,
        config_type=ConfigType.BOOLEAN,
        default=False,
        tooltip="Enable decompilation when creating patch templates (requires Ghidra)",
        order=20,
    ),
]

# =============================================================================
# Helper Functions
# =============================================================================


def get_persistent_keys() -> List[str]:
    """Get list of all persistent configuration keys."""
    return [item.key for item in CONFIG_SCHEMA]


def get_config_defaults() -> dict:
    """Get dictionary of all default values."""
    return {item.key: item.default for item in CONFIG_SCHEMA}


def get_schema_by_key(key: str) -> Optional[ConfigItem]:
    """Get config item by key."""
    for item in CONFIG_SCHEMA:
        if item.key == key:
            return item
    return None


def get_sidebar_schema() -> List[ConfigItem]:
    """Get config items that should be shown in sidebar."""
    return [item for item in CONFIG_SCHEMA if item.show_in_sidebar]


def get_schema_by_group(group: ConfigGroup) -> List[ConfigItem]:
    """Get config items for a specific group, sorted by order."""
    items = [item for item in CONFIG_SCHEMA if item.group == group]
    return sorted(items, key=lambda x: x.order)


def get_schema_as_dict() -> dict:
    """Get full schema as dictionary for JSON serialization."""
    return {
        "schema": [item.to_dict() for item in get_sidebar_schema()],
        "groups": {g.value: label for g, label in GROUP_LABELS.items()},
        "group_order": [g.value for g in ConfigGroup if g != ConfigGroup.CONNECTION],
    }


# Generate PERSISTENT_KEYS for backward compatibility
PERSISTENT_KEYS = get_persistent_keys()

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
State management for FPBInject Web Server.

Manages device state, configuration, and persistence.
"""

import json
import logging
import os
import threading

# Config file path (relative to WebServer directory, not core/)
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"
)

# Config version for migration support
CONFIG_VERSION = 1

# Keys to persist
PERSISTENT_KEYS = [
    "port",
    "baudrate",
    "elf_path",
    "toolchain_path",
    "compile_commands_path",
    "watch_dirs",
    "patch_mode",
    "chunk_size",
    "tx_chunk_size",
    "tx_chunk_delay",
    "auto_connect",
    "auto_compile",
    "enable_decompile",
    "transfer_max_retries",
    "verify_crc",
    "log_file_enabled",
    "log_file_path",
]


class DeviceState:
    """State container for FPBInject device."""

    def __init__(self):
        # Serial connection
        self.ser = None
        self.port = None
        self.baudrate = 115200
        self.timeout = 2

        # FPB Inject configuration
        self.elf_path = ""
        self.toolchain_path = ""
        self.compile_commands_path = ""
        self.watch_dirs = []
        self.patch_mode = "trampoline"  # trampoline, debugmon, direct
        self.chunk_size = 128
        self.tx_chunk_size = 0  # 0 = disabled, >0 = chunk size for TX
        self.tx_chunk_delay = 0.005  # Delay between TX chunks (seconds)
        self.transfer_max_retries = 10  # Max retries for file transfer

        # Patch source settings
        self.patch_source_path = ""  # Current patch source file path
        self.patch_source_content = ""  # Editable patch source content

        # Auto settings
        self.auto_connect = False
        self.auto_compile = False  # Auto compile and inject on file change
        self.enable_decompile = False  # Enable decompilation (requires angr)
        self.verify_crc = True  # Verify CRC after file transfer (default enabled)

        # Device info (from fl --info)
        self.device_info = None
        self.base_addr = 0

        # Injection status
        self.last_inject_target = None
        self.last_inject_func = None
        self.last_inject_time = None
        self.inject_active = False

        # Serial log (RX/TX direction log)
        self.serial_log = []
        self.log_max_size = 5000
        self.log_next_id = 0

        # Raw serial log (for terminal display)
        self.raw_serial_log = []
        self.raw_log_max_size = 5000
        self.raw_log_next_id = 0

        # Tool output log (for OUTPUT terminal)
        self.tool_log = []
        self.tool_log_max_size = 1000
        self.tool_log_next_id = 0

        # Worker thread reference
        self.worker = None

        # Auto inject state
        self.auto_inject_status = (
            "idle"  # idle, detecting, generating, compiling, injecting, success, failed
        )
        self.auto_inject_message = ""
        self.auto_inject_source_file = ""
        self.auto_inject_modified_funcs = []
        self.auto_inject_progress = 0
        self.auto_inject_last_update = 0
        self.auto_inject_result = {}  # Injection statistics result

        # Slot update tracking (for frontend push)
        self.slot_update_id = 0  # Incremented on slot info change
        self.cached_slots = []  # Cached slot info from last info response

        # Log file recording
        self.log_file_enabled = False
        self.log_file_path = ""
        self.log_file_line_buffer = ""  # Buffer for line-based logging

    def add_tool_log(self, message):
        """Add a message to tool output log (shown in OUTPUT terminal)."""
        log_id = self.tool_log_next_id
        self.tool_log_next_id += 1
        entry = {"id": log_id, "message": message}
        self.tool_log.append(entry)
        if len(self.tool_log) > self.tool_log_max_size:
            self.tool_log = self.tool_log[-self.tool_log_max_size :]

    def to_dict(self):
        """Export persistent config as dict."""
        return {key: getattr(self, key) for key in PERSISTENT_KEYS}

    def from_dict(self, data):
        """Import config from dict."""
        for key in PERSISTENT_KEYS:
            if key in data:
                setattr(self, key, data[key])


class AppState:
    """Global application state manager."""

    def __init__(self):
        self._lock = threading.Lock()
        self.device = DeviceState()

        # File watcher state
        self.file_watcher = None
        self.pending_changes = []  # List of changed files
        self.last_change_time = None

        # Symbols cache from ELF
        self.symbols = {}
        self.symbols_loaded = False

        # Patch generation state
        self.generated_patch = None
        self.patch_template = self._get_default_patch_template()

        # Load config from file
        self.load_config()

    def _get_default_patch_template(self):
        """Get default patch template code."""
        return """/*
 * FPBInject Patch Source
 * Generated by FPBInject WebServer
 *
 * Place this file in the inject directory and modify as needed.
 * Use /* FPB_INJECT */ marker before functions you want to inject.
 * Function names are preserved (no renaming).
 *
 * NOTE: Calling the original function from injected code is NOT supported
 *       due to FPB hardware limitations (would cause infinite recursion).
 */

#include <stdio.h>

/*
 * Example: Replace a function named "target_function"
 * The inject function should have the same signature as the original.
 *
 * /* FPB_INJECT */
 * __attribute__((section(".fpb.text"), used))
 * void target_function(int arg1, int arg2) {
 *     printf("Patched: arg1=%d, arg2=%d\\n", arg1, arg2);
 *     // Completely replaces the original function
 * }
 */

"""

    def load_config(self):
        """Load configuration from JSON file."""
        logger = logging.getLogger(__name__)
        if not os.path.exists(CONFIG_FILE):
            logger.info(f"Config file not found: {CONFIG_FILE}, using defaults")
            return

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)

            self.device.from_dict(config)
            logger.info(f"Config loaded from {CONFIG_FILE}")
        except Exception as e:
            logger.exception(f"Error loading config: {e}")

    def save_config(self):
        """Save configuration to JSON file."""
        logger = logging.getLogger(__name__)
        try:
            config = {"version": CONFIG_VERSION}
            config.update(self.device.to_dict())

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"Config saved to {CONFIG_FILE}")
        except Exception as e:
            logger.exception(f"Error saving config: {e}")

    def add_pending_change(self, file_path, change_type):
        """Add a file change to pending list."""
        with self._lock:
            import time

            self.pending_changes.append(
                {
                    "path": file_path,
                    "type": change_type,
                    "time": time.time(),
                }
            )
            self.last_change_time = time.time()
            # Keep only last 100 changes
            if len(self.pending_changes) > 100:
                self.pending_changes = self.pending_changes[-100:]

    def clear_pending_changes(self):
        """Clear pending changes list."""
        with self._lock:
            self.pending_changes = []

    def get_pending_changes(self):
        """Get and return pending changes."""
        with self._lock:
            return list(self.pending_changes)


# Global state instance
state = AppState()

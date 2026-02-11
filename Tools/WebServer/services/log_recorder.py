#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Log file recording service for FPBInject Web Server.

Provides functionality to save console logs to file.
"""

import logging
import os
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class LogFileRecorder:
    """Records console logs to file."""

    def __init__(self):
        self._lock = threading.Lock()
        self._file = None
        self._enabled = False
        self._path = ""

    def start(self, path: str) -> tuple[bool, str]:
        """Start recording logs to file."""
        with self._lock:
            if self._enabled:
                return False, "Already recording"

            try:
                # Expand ~ to home directory
                path = os.path.expanduser(path)

                # Create directory if not exists
                dir_path = os.path.dirname(path)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)

                self._file = open(path, "a", encoding="utf-8")
                self._enabled = True
                self._path = path

                logger.info(f"Log recording started: {path}")
                return True, ""
            except Exception as e:
                self._enabled = False
                self._path = ""
                error_msg = f"Failed to start recording: {e}"
                logger.error(error_msg)
                return False, error_msg

    def stop(self) -> tuple[bool, str]:
        """Stop recording logs."""
        with self._lock:
            if not self._enabled:
                return False, "Not recording"

            try:
                if self._file:
                    self._file.close()
                    self._file = None

                path = self._path
                self._enabled = False
                self._path = ""

                logger.info(f"Log recording stopped: {path}")
                return True, ""
            except Exception as e:
                error_msg = f"Failed to stop recording: {e}"
                logger.error(error_msg)
                return False, error_msg

    def write(self, message: str):
        """Write a message to log file."""
        with self._lock:
            if not self._enabled or not self._file:
                return

            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                # Handle multi-line messages
                lines = message.split("\n")
                for i, line in enumerate(lines):
                    if (
                        line or i == 0
                    ):  # Write first line even if empty, skip other empty lines
                        if i == 0:
                            self._file.write(f"[{timestamp}] {line}\n")
                        else:
                            self._file.write(f"{line}\n")
                self._file.flush()
            except Exception as e:
                logger.error(f"Failed to write log: {e}")

    @property
    def enabled(self) -> bool:
        """Check if recording is enabled."""
        with self._lock:
            return self._enabled

    @property
    def path(self) -> str:
        """Get current log file path."""
        with self._lock:
            return self._path


# Global instance
log_recorder = LogFileRecorder()

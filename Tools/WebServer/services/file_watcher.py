#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
File watcher module for FPBInject Web Server.

Monitors directories for file changes and triggers callbacks.
"""

import logging
import os
import threading
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# Try to import watchdog, fall back to polling if not available
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog not installed, using polling-based file watching")


class FileChangeHandler:
    """Base class for file change handling."""

    def __init__(
        self, callback: Callable[[str, str], None], extensions: List[str] = None
    ):
        """
        Initialize file change handler.

        Args:
            callback: Function to call on file change (path, change_type)
            extensions: List of file extensions to watch (e.g., ['.c', '.cpp', '.h'])
        """
        self.callback = callback
        self.extensions = extensions or [".c", ".cpp", ".h", ".hpp"]

    def should_process(self, path: str) -> bool:
        """Check if file should be processed based on extension."""
        if not self.extensions:
            return True
        return any(path.endswith(ext) for ext in self.extensions)


if WATCHDOG_AVAILABLE:

    class WatchdogHandler(FileSystemEventHandler, FileChangeHandler):
        """Watchdog-based file change handler."""

        def __init__(
            self, callback: Callable[[str, str], None], extensions: List[str] = None
        ):
            FileSystemEventHandler.__init__(self)
            FileChangeHandler.__init__(self, callback, extensions)
            self._last_events = {}  # Debounce duplicate events
            self._debounce_delay = 0.5  # seconds

        def _should_debounce(self, path: str) -> bool:
            """Check if event should be debounced."""
            now = time.time()
            last_time = self._last_events.get(path, 0)
            if now - last_time < self._debounce_delay:
                return True
            self._last_events[path] = now
            return False

        def on_modified(self, event: FileSystemEvent):
            if event.is_directory:
                return
            if not self.should_process(event.src_path):
                return
            if self._should_debounce(event.src_path):
                return
            logger.debug(f"File modified: {event.src_path}")
            self.callback(event.src_path, "modified")

        def on_created(self, event: FileSystemEvent):
            if event.is_directory:
                return
            if not self.should_process(event.src_path):
                return
            if self._should_debounce(event.src_path):
                return
            logger.debug(f"File created: {event.src_path}")
            self.callback(event.src_path, "created")

        def on_deleted(self, event: FileSystemEvent):
            if event.is_directory:
                return
            if not self.should_process(event.src_path):
                return
            logger.debug(f"File deleted: {event.src_path}")
            self.callback(event.src_path, "deleted")


class PollingWatcher:
    """Polling-based file watcher (fallback when watchdog not available)."""

    def __init__(
        self,
        directories: List[str],
        callback: Callable[[str, str], None],
        extensions: List[str] = None,
        interval: float = 1.0,
    ):
        """
        Initialize polling watcher.

        Args:
            directories: List of directories to watch
            callback: Function to call on file change
            extensions: List of file extensions to watch
            interval: Polling interval in seconds
        """
        self.directories = directories
        self.callback = callback
        self.extensions = extensions or [".c", ".cpp", ".h", ".hpp"]
        self.interval = interval
        self._running = False
        self._thread = None
        self._file_mtimes = {}

    def _should_process(self, path: str) -> bool:
        """Check if file should be processed."""
        return any(path.endswith(ext) for ext in self.extensions)

    def _scan_directory(self, directory: str):
        """Scan directory for files."""
        files = {}
        try:
            for root, _, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    if self._should_process(filepath):
                        try:
                            files[filepath] = os.path.getmtime(filepath)
                        except OSError:
                            pass
        except OSError:
            pass
        return files

    def _poll_loop(self):
        """Main polling loop."""
        # Initial scan
        for directory in self.directories:
            if os.path.isdir(directory):
                self._file_mtimes.update(self._scan_directory(directory))

        while self._running:
            time.sleep(self.interval)

            if not self._running:
                break

            # Check for changes
            current_files = {}
            for directory in self.directories:
                if os.path.isdir(directory):
                    current_files.update(self._scan_directory(directory))

            # Check for new or modified files
            for filepath, mtime in current_files.items():
                if filepath not in self._file_mtimes:
                    # New file
                    self.callback(filepath, "created")
                elif mtime > self._file_mtimes[filepath]:
                    # Modified file
                    self.callback(filepath, "modified")

            # Check for deleted files
            for filepath in self._file_mtimes:
                if filepath not in current_files:
                    self.callback(filepath, "deleted")

            self._file_mtimes = current_files

    def start(self):
        """Start polling."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"Polling watcher started for {len(self.directories)} directories")

    def stop(self):
        """Stop polling."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("Polling watcher stopped")


class FileWatcher:
    """File watcher manager."""

    def __init__(
        self,
        directories: List[str],
        callback: Callable[[str, str], None],
        extensions: List[str] = None,
    ):
        """
        Initialize file watcher.

        Args:
            directories: List of directories to watch
            callback: Function to call on file change (path, change_type)
            extensions: List of file extensions to watch
        """
        self.directories = [d for d in directories if os.path.isdir(d)]
        self.callback = callback
        self.extensions = extensions or [".c", ".cpp", ".h", ".hpp"]
        self._observer = None
        self._polling_watcher = None

    def start(self):
        """Start watching directories."""
        if not self.directories:
            logger.warning("No valid directories to watch")
            return False

        if WATCHDOG_AVAILABLE:
            try:
                self._observer = Observer()
                handler = WatchdogHandler(self.callback, self.extensions)

                for directory in self.directories:
                    self._observer.schedule(handler, directory, recursive=True)
                    logger.info(f"Watching directory: {directory}")

                self._observer.start()
                logger.info("Watchdog observer started")
                return True
            except Exception as e:
                logger.error(f"Failed to start watchdog observer: {e}")
                # Fall through to polling

        # Use polling as fallback
        self._polling_watcher = PollingWatcher(
            self.directories, self.callback, self.extensions
        )
        self._polling_watcher.start()
        return True

    def stop(self):
        """Stop watching."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
            logger.info("Watchdog observer stopped")

        if self._polling_watcher:
            self._polling_watcher.stop()
            self._polling_watcher = None

    def is_running(self) -> bool:
        """Check if watcher is running."""
        if self._observer:
            return self._observer.is_alive()
        if self._polling_watcher:
            return self._polling_watcher._running
        return False


# Module-level functions for easy usage


def start_watching(
    directories: List[str],
    callback: Callable[[str, str], None],
    extensions: List[str] = None,
) -> Optional[FileWatcher]:
    """
    Start watching directories for file changes.

    Args:
        directories: List of directories to watch
        callback: Function to call on file change (path, change_type)
        extensions: List of file extensions to watch

    Returns:
        FileWatcher instance or None on failure
    """
    watcher = FileWatcher(directories, callback, extensions)
    if watcher.start():
        return watcher
    return None


def stop_watching(watcher: FileWatcher):
    """Stop file watcher."""
    if watcher:
        watcher.stop()

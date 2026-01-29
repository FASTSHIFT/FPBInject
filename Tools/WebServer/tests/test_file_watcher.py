#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File watcher module tests
"""

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import file_watcher


class TestFileChangeHandler(unittest.TestCase):
    """FileChangeHandler tests"""

    def test_init_default_extensions(self):
        """Test initialization with default extensions"""
        callback = Mock()
        handler = file_watcher.FileChangeHandler(callback)

        self.assertEqual(handler.callback, callback)
        self.assertEqual(handler.extensions, [".c", ".cpp", ".h", ".hpp"])

    def test_init_custom_extensions(self):
        """Test initialization with custom extensions"""
        callback = Mock()
        handler = file_watcher.FileChangeHandler(callback, [".py", ".txt"])

        self.assertEqual(handler.extensions, [".py", ".txt"])

    def test_should_process_matching_extension(self):
        """Test should_process with matching extension"""
        handler = file_watcher.FileChangeHandler(Mock())

        self.assertTrue(handler.should_process("/path/to/file.c"))
        self.assertTrue(handler.should_process("/path/to/file.cpp"))
        self.assertTrue(handler.should_process("/path/to/file.h"))

    def test_should_process_non_matching_extension(self):
        """Test should_process with non-matching extension"""
        handler = file_watcher.FileChangeHandler(Mock())

        self.assertFalse(handler.should_process("/path/to/file.py"))
        self.assertFalse(handler.should_process("/path/to/file.txt"))

    def test_should_process_no_extensions(self):
        """Test should_process with empty extensions list returns False"""
        handler = file_watcher.FileChangeHandler(Mock(), extensions=[])

        # Empty extensions list means no files match (not all files match)
        self.assertFalse(handler.should_process("/path/to/any.file"))


class TestPollingWatcher(unittest.TestCase):
    """PollingWatcher tests"""

    def test_init(self):
        """Test initialization"""
        callback = Mock()
        watcher = file_watcher.PollingWatcher(["/tmp"], callback)

        self.assertEqual(watcher.directories, ["/tmp"])
        self.assertEqual(watcher.callback, callback)
        self.assertFalse(watcher._running)

    def test_should_process(self):
        """Test _should_process method"""
        watcher = file_watcher.PollingWatcher(["/tmp"], Mock())

        self.assertTrue(watcher._should_process("/path/to/file.c"))
        self.assertFalse(watcher._should_process("/path/to/file.py"))

    def test_scan_directory(self):
        """Test _scan_directory method"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            c_file = os.path.join(tmpdir, "test.c")
            py_file = os.path.join(tmpdir, "test.py")
            with open(c_file, "w") as f:
                f.write("int main() {}")
            with open(py_file, "w") as f:
                f.write("print('hello')")

            watcher = file_watcher.PollingWatcher([tmpdir], Mock())
            files = watcher._scan_directory(tmpdir)

            self.assertIn(c_file, files)
            self.assertNotIn(py_file, files)

    def test_scan_nonexistent_directory(self):
        """Test _scan_directory with nonexistent directory"""
        watcher = file_watcher.PollingWatcher(["/nonexistent"], Mock())
        files = watcher._scan_directory("/nonexistent")

        self.assertEqual(files, {})

    def test_start_stop(self):
        """Test start and stop"""
        with tempfile.TemporaryDirectory() as tmpdir:
            callback = Mock()
            watcher = file_watcher.PollingWatcher([tmpdir], callback, interval=0.1)

            watcher.start()
            self.assertTrue(watcher._running)

            time.sleep(0.2)

            watcher.stop()
            self.assertFalse(watcher._running)

    def test_start_already_running(self):
        """Test start when already running"""
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = file_watcher.PollingWatcher([tmpdir], Mock(), interval=0.1)

            watcher.start()
            watcher.start()  # Should not start another thread

            self.assertTrue(watcher._running)
            watcher.stop()

    def test_detect_new_file(self):
        """Test detecting new file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            callback = Mock()
            watcher = file_watcher.PollingWatcher([tmpdir], callback, interval=0.1)

            watcher.start()
            time.sleep(0.15)

            # Create new file
            new_file = os.path.join(tmpdir, "new.c")
            with open(new_file, "w") as f:
                f.write("void test() {}")

            time.sleep(0.2)
            watcher.stop()

            # Check callback was called for created file
            calls = [c for c in callback.call_args_list if c[0][1] == "created"]
            self.assertTrue(len(calls) > 0)

    def test_detect_modified_file(self):
        """Test detecting modified file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial file
            test_file = os.path.join(tmpdir, "test.c")
            with open(test_file, "w") as f:
                f.write("void test() {}")

            callback = Mock()
            watcher = file_watcher.PollingWatcher([tmpdir], callback, interval=0.1)

            watcher.start()
            time.sleep(0.15)

            # Modify file
            time.sleep(0.1)  # Ensure mtime changes
            with open(test_file, "w") as f:
                f.write("void test() { return; }")

            time.sleep(0.2)
            watcher.stop()

            # Check callback was called for modified file
            calls = [c for c in callback.call_args_list if c[0][1] == "modified"]
            self.assertTrue(len(calls) > 0)


class TestFileWatcher(unittest.TestCase):
    """FileWatcher tests"""

    def test_init_filters_invalid_dirs(self):
        """Test initialization filters invalid directories"""
        watcher = file_watcher.FileWatcher(["/tmp", "/nonexistent/path"], Mock())

        self.assertIn("/tmp", watcher.directories)
        self.assertNotIn("/nonexistent/path", watcher.directories)

    def test_start_no_directories(self):
        """Test start with no valid directories"""
        watcher = file_watcher.FileWatcher(["/nonexistent"], Mock())

        result = watcher.start()

        self.assertFalse(result)

    def test_start_with_polling(self):
        """Test start with polling fallback"""
        with tempfile.TemporaryDirectory() as tmpdir:
            callback = Mock()
            watcher = file_watcher.FileWatcher([tmpdir], callback)

            # Force polling by mocking WATCHDOG_AVAILABLE
            with patch.object(file_watcher, "WATCHDOG_AVAILABLE", False):
                result = watcher.start()

            self.assertTrue(result)
            self.assertIsNotNone(watcher._polling_watcher)

            watcher.stop()

    def test_stop_no_watcher(self):
        """Test stop when no watcher is running"""
        watcher = file_watcher.FileWatcher(["/tmp"], Mock())
        watcher.stop()  # Should not raise

    def test_is_running_not_started(self):
        """Test is_running when not started"""
        watcher = file_watcher.FileWatcher(["/tmp"], Mock())

        self.assertFalse(watcher.is_running())

    def test_is_running_with_polling(self):
        """Test is_running with polling watcher"""
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = file_watcher.FileWatcher([tmpdir], Mock())

            with patch.object(file_watcher, "WATCHDOG_AVAILABLE", False):
                watcher.start()

            self.assertTrue(watcher.is_running())

            watcher.stop()
            self.assertFalse(watcher.is_running())


class TestModuleFunctions(unittest.TestCase):
    """Module-level function tests"""

    def test_start_watching(self):
        """Test start_watching function"""
        with tempfile.TemporaryDirectory() as tmpdir:
            callback = Mock()

            with patch.object(file_watcher, "WATCHDOG_AVAILABLE", False):
                watcher = file_watcher.start_watching([tmpdir], callback)

            self.assertIsNotNone(watcher)
            self.assertTrue(watcher.is_running())

            file_watcher.stop_watching(watcher)

    def test_start_watching_failure(self):
        """Test start_watching with invalid directories"""
        watcher = file_watcher.start_watching(["/nonexistent"], Mock())

        self.assertIsNone(watcher)

    def test_stop_watching_none(self):
        """Test stop_watching with None"""
        file_watcher.stop_watching(None)  # Should not raise


@unittest.skipUnless(file_watcher.WATCHDOG_AVAILABLE, "watchdog not installed")
class TestWatchdogHandler(unittest.TestCase):
    """WatchdogHandler tests (only run if watchdog is available)"""

    def test_init(self):
        """Test initialization"""
        callback = Mock()
        handler = file_watcher.WatchdogHandler(callback)

        self.assertEqual(handler.callback, callback)

    def test_should_debounce(self):
        """Test debounce logic"""
        handler = file_watcher.WatchdogHandler(Mock())

        # First event should not be debounced
        self.assertFalse(handler._should_debounce("/path/to/file.c"))

        # Immediate second event should be debounced
        self.assertTrue(handler._should_debounce("/path/to/file.c"))

    def test_on_modified_directory(self):
        """Test on_modified ignores directories"""
        callback = Mock()
        handler = file_watcher.WatchdogHandler(callback)

        event = Mock()
        event.is_directory = True
        event.src_path = "/path/to/dir"

        handler.on_modified(event)

        callback.assert_not_called()

    def test_on_modified_wrong_extension(self):
        """Test on_modified ignores wrong extensions"""
        callback = Mock()
        handler = file_watcher.WatchdogHandler(callback)

        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.py"

        handler.on_modified(event)

        callback.assert_not_called()

    def test_on_modified_success(self):
        """Test on_modified calls callback"""
        callback = Mock()
        handler = file_watcher.WatchdogHandler(callback)

        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.c"

        handler.on_modified(event)

        callback.assert_called_once_with("/path/to/file.c", "modified")

    def test_on_created(self):
        """Test on_created calls callback"""
        callback = Mock()
        handler = file_watcher.WatchdogHandler(callback)

        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.c"

        handler.on_created(event)

        callback.assert_called_once_with("/path/to/file.c", "created")

    def test_on_deleted(self):
        """Test on_deleted calls callback"""
        callback = Mock()
        handler = file_watcher.WatchdogHandler(callback)

        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.c"

        handler.on_deleted(event)

        callback.assert_called_once_with("/path/to/file.c", "deleted")


class TestFileWatcherWithWatchdog(unittest.TestCase):
    """FileWatcher tests with watchdog mocked"""

    @patch.object(file_watcher, "WATCHDOG_AVAILABLE", True)
    def test_start_with_watchdog(
        self,
    ):
        """Test start with watchdog"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Skip if watchdog not actually installed
            try:
                from watchdog.observers import Observer
            except ImportError:
                self.skipTest("watchdog not installed")

            with patch("watchdog.observers.Observer") as mock_observer_class:
                mock_observer = Mock()
                mock_observer_class.return_value = mock_observer

                # Need to mock WatchdogHandler too
                with patch.object(file_watcher, "WatchdogHandler", Mock()):
                    watcher = file_watcher.FileWatcher([tmpdir], Mock())
                    watcher._observer = None  # Reset

                    # Manually set WATCHDOG_AVAILABLE for this test
                    original = file_watcher.WATCHDOG_AVAILABLE
                    file_watcher.WATCHDOG_AVAILABLE = True

                    try:
                        result = watcher.start()
                        # May fall back to polling if watchdog setup fails
                        self.assertTrue(result)
                    finally:
                        file_watcher.WATCHDOG_AVAILABLE = original
                        watcher.stop()

    def test_stop_with_observer(self):
        """Test stop with observer"""
        watcher = file_watcher.FileWatcher(["/tmp"], Mock())
        mock_observer = Mock()
        watcher._observer = mock_observer

        watcher.stop()

        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

    def test_is_running_with_observer(self):
        """Test is_running with observer"""
        watcher = file_watcher.FileWatcher(["/tmp"], Mock())
        mock_observer = Mock()
        mock_observer.is_alive.return_value = True
        watcher._observer = mock_observer

        self.assertTrue(watcher.is_running())

        mock_observer.is_alive.return_value = False
        self.assertFalse(watcher.is_running())


if __name__ == "__main__":
    unittest.main()


class TestPollingWatcherExtended(unittest.TestCase):
    """Extended PollingWatcher tests"""

    def test_detect_deleted_file(self):
        """Test detecting deleted file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial file
            test_file = os.path.join(tmpdir, "test.c")
            with open(test_file, "w") as f:
                f.write("void test() {}")

            callback = Mock()
            watcher = file_watcher.PollingWatcher([tmpdir], callback, interval=0.1)

            watcher.start()
            time.sleep(0.15)

            # Delete file
            os.unlink(test_file)

            time.sleep(0.2)
            watcher.stop()

            # Check callback was called for deleted file
            calls = [c for c in callback.call_args_list if c[0][1] == "deleted"]
            self.assertTrue(len(calls) > 0)


class TestFileWatcherExtended(unittest.TestCase):
    """Extended FileWatcher tests"""

    @patch.object(file_watcher, "WATCHDOG_AVAILABLE", True)
    def test_start_watchdog_exception(self):
        """Test start with watchdog exception falls back to polling"""
        # Skip if watchdog not actually installed
        try:
            from watchdog.observers import Observer
        except ImportError:
            self.skipTest("watchdog not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = Mock()
            watcher = file_watcher.FileWatcher([tmpdir], callback)

            # Mock Observer to raise exception
            with patch("watchdog.observers.Observer") as mock_observer:
                mock_observer.side_effect = Exception("Watchdog error")

                result = watcher.start()

                # Should fall back to polling
                self.assertTrue(result)
                self.assertIsNotNone(watcher._polling_watcher)

            watcher.stop()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Watcher module test
"""

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from file_watcher import (
    FileChangeHandler,
    FileWatcher,
    PollingWatcher,
    start_watching,
    stop_watching,
    WATCHDOG_AVAILABLE,
)


class TestFileChangeHandler(unittest.TestCase):
    """FileChangeHandler test"""

    def setUp(self):
        self.callback = Mock()
        self.handler = FileChangeHandler(
            callback=self.callback, extensions=[".c", ".h"]
        )

    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.handler.callback, self.callback)
        self.assertEqual(self.handler.extensions, [".c", ".h"])

    def test_init_default_extensions(self):
        """Test default extensions"""
        handler = FileChangeHandler(callback=self.callback)
        self.assertIn(".c", handler.extensions)
        self.assertIn(".h", handler.extensions)

    def test_should_process_matching_file(self):
        """Test matching file should be processed"""
        result = self.handler.should_process("/path/to/file.c")
        self.assertTrue(result)

    def test_should_process_header_file(self):
        """Test header file should be processed"""
        result = self.handler.should_process("/path/to/header.h")
        self.assertTrue(result)

    def test_should_not_process_non_matching(self):
        """Test non-matching file should not be processed"""
        result = self.handler.should_process("/path/to/file.txt")
        self.assertFalse(result)

    def test_should_process_all_when_no_extensions(self):
        """Test process all files when no extensions limit"""
        handler = FileChangeHandler(callback=self.callback, extensions=None)
        # When extensions is None, default will use ['.c', '.cpp', '.h', '.hpp']
        result = handler.should_process("/path/to/file.c")
        self.assertTrue(result)


class TestPollingWatcher(unittest.TestCase):
    """PollingWatcher test"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.callback = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Test initialization"""
        watcher = PollingWatcher(
            directories=[self.temp_dir],
            callback=self.callback,
            extensions=[".c"],
            interval=0.5,
        )

        self.assertEqual(watcher.directories, [self.temp_dir])
        self.assertEqual(watcher.callback, self.callback)
        self.assertEqual(watcher.extensions, [".c"])
        self.assertEqual(watcher.interval, 0.5)

    def test_start_stop(self):
        """Test start and stop"""
        watcher = PollingWatcher(
            directories=[self.temp_dir], callback=self.callback, interval=0.1
        )

        watcher.start()
        self.assertTrue(watcher._running)

        watcher.stop()
        self.assertFalse(watcher._running)

    def test_detect_new_file(self):
        """Test detect new file"""
        watcher = PollingWatcher(
            directories=[self.temp_dir], callback=self.callback, interval=0.1
        )

        watcher.start()
        time.sleep(0.2)

        # Create new file
        test_file = os.path.join(self.temp_dir, "test.c")
        with open(test_file, "w") as f:
            f.write("// test")

        time.sleep(0.3)
        watcher.stop()

        # Should detect creation
        self.callback.assert_called()

    def test_detect_modified_file(self):
        """Test detect file modification"""
        # Create file first
        test_file = os.path.join(self.temp_dir, "existing.c")
        with open(test_file, "w") as f:
            f.write("// original")

        watcher = PollingWatcher(
            directories=[self.temp_dir], callback=self.callback, interval=0.1
        )

        watcher.start()
        time.sleep(0.2)

        # Modify file
        with open(test_file, "w") as f:
            f.write("// modified")

        time.sleep(0.3)
        watcher.stop()

        # Should detect modification
        self.callback.assert_called()


class TestFileWatcher(unittest.TestCase):
    """FileWatcher test"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.callback = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Test initialization"""
        watcher = FileWatcher(
            directories=[self.temp_dir], callback=self.callback, extensions=[".c"]
        )

        self.assertEqual(watcher.directories, [self.temp_dir])
        self.assertEqual(watcher.callback, self.callback)

    def test_init_filters_invalid_dirs(self):
        """Test filter invalid directories during initialization"""
        watcher = FileWatcher(
            directories=[self.temp_dir, "/nonexistent/12345"], callback=self.callback
        )

        self.assertEqual(watcher.directories, [self.temp_dir])

    def test_start_stop(self):
        """Test start and stop"""
        watcher = FileWatcher(directories=[self.temp_dir], callback=self.callback)

        result = watcher.start()
        self.assertTrue(result)
        self.assertTrue(watcher.is_running())

        watcher.stop()
        time.sleep(0.1)
        self.assertFalse(watcher.is_running())

    def test_start_no_directories(self):
        """Test start when no directories"""
        watcher = FileWatcher(directories=[], callback=self.callback)

        result = watcher.start()
        self.assertFalse(result)

    def test_is_running(self):
        """Test running status check"""
        watcher = FileWatcher(directories=[self.temp_dir], callback=self.callback)

        self.assertFalse(watcher.is_running())

        watcher.start()
        self.assertTrue(watcher.is_running())

        watcher.stop()


class TestModuleFunctions(unittest.TestCase):
    """Module functions test"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.callback = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_start_watching(self):
        """Test start_watching function"""
        watcher = start_watching(directories=[self.temp_dir], callback=self.callback)

        self.assertIsNotNone(watcher)
        self.assertIsInstance(watcher, FileWatcher)

        stop_watching(watcher)

    def test_start_watching_no_dirs(self):
        """Test start_watching when no directories"""
        watcher = start_watching(directories=[], callback=self.callback)

        self.assertIsNone(watcher)

    def test_stop_watching_none(self):
        """Test stop None"""
        stop_watching(None)  # Should not error


class TestPollingWatcherExtended(unittest.TestCase):
    """PollingWatcher extended test"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.callback = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_should_process(self):
        """Test file extension check"""
        watcher = PollingWatcher(
            directories=[self.temp_dir],
            callback=self.callback,
            extensions=[".c", ".h"],
        )

        self.assertTrue(watcher._should_process("/path/to/file.c"))
        self.assertTrue(watcher._should_process("/path/to/file.h"))
        self.assertFalse(watcher._should_process("/path/to/file.txt"))

    def test_scan_directory_empty(self):
        """Test scan empty directory"""
        watcher = PollingWatcher(
            directories=[self.temp_dir],
            callback=self.callback,
        )

        files = watcher._scan_directory(self.temp_dir)
        self.assertEqual(files, {})

    def test_scan_directory_with_files(self):
        """Test scan directory with files"""
        # Create test file
        test_file = os.path.join(self.temp_dir, "test.c")
        with open(test_file, "w") as f:
            f.write("// test")

        watcher = PollingWatcher(
            directories=[self.temp_dir],
            callback=self.callback,
        )

        files = watcher._scan_directory(self.temp_dir)
        self.assertIn(test_file, files)

    def test_scan_directory_nonexistent(self):
        """Test scan nonexistent directory"""
        watcher = PollingWatcher(
            directories=["/nonexistent/12345"],
            callback=self.callback,
        )

        files = watcher._scan_directory("/nonexistent/12345")
        self.assertEqual(files, {})

    def test_detect_deleted_file(self):
        """Test detect file deletion"""
        # Create file
        test_file = os.path.join(self.temp_dir, "to_delete.c")
        with open(test_file, "w") as f:
            f.write("// to delete")

        watcher = PollingWatcher(
            directories=[self.temp_dir],
            callback=self.callback,
            interval=0.1,
        )

        watcher.start()
        time.sleep(0.2)

        # Delete file
        os.remove(test_file)

        time.sleep(0.3)
        watcher.stop()

        # Should detect deletion
        calls = [c for c in self.callback.call_args_list if c[0][1] == "deleted"]
        self.assertTrue(len(calls) > 0)


class TestFileWatcherExtended(unittest.TestCase):
    """FileWatcher extended test"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.callback = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_double_start(self):
        """Test double start"""
        watcher = FileWatcher(directories=[self.temp_dir], callback=self.callback)

        result1 = watcher.start()
        result2 = watcher.start()  # Second start

        self.assertTrue(result1)
        # Second start may return True (already running)

        watcher.stop()

    def test_double_stop(self):
        """Test double stop"""
        watcher = FileWatcher(directories=[self.temp_dir], callback=self.callback)

        watcher.start()
        watcher.stop()
        watcher.stop()  # Second stop should not error


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Watcher 模块测试
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
    """FileChangeHandler 测试"""

    def setUp(self):
        self.callback = Mock()
        self.handler = FileChangeHandler(
            callback=self.callback, extensions=[".c", ".h"]
        )

    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.handler.callback, self.callback)
        self.assertEqual(self.handler.extensions, [".c", ".h"])

    def test_init_default_extensions(self):
        """测试默认扩展名"""
        handler = FileChangeHandler(callback=self.callback)
        self.assertIn(".c", handler.extensions)
        self.assertIn(".h", handler.extensions)

    def test_should_process_matching_file(self):
        """测试匹配的文件应该处理"""
        result = self.handler.should_process("/path/to/file.c")
        self.assertTrue(result)

    def test_should_process_header_file(self):
        """测试头文件应该处理"""
        result = self.handler.should_process("/path/to/header.h")
        self.assertTrue(result)

    def test_should_not_process_non_matching(self):
        """测试不匹配的文件不应该处理"""
        result = self.handler.should_process("/path/to/file.txt")
        self.assertFalse(result)

    def test_should_process_all_when_no_extensions(self):
        """测试无扩展名限制时处理所有文件"""
        handler = FileChangeHandler(callback=self.callback, extensions=None)
        # 当 extensions 为 None 时，默认会使用 ['.c', '.cpp', '.h', '.hpp']
        result = handler.should_process("/path/to/file.c")
        self.assertTrue(result)


class TestPollingWatcher(unittest.TestCase):
    """PollingWatcher 测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.callback = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """测试初始化"""
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
        """测试启动和停止"""
        watcher = PollingWatcher(
            directories=[self.temp_dir], callback=self.callback, interval=0.1
        )

        watcher.start()
        self.assertTrue(watcher._running)

        watcher.stop()
        self.assertFalse(watcher._running)

    def test_detect_new_file(self):
        """测试检测新文件"""
        watcher = PollingWatcher(
            directories=[self.temp_dir], callback=self.callback, interval=0.1
        )

        watcher.start()
        time.sleep(0.2)

        # 创建新文件
        test_file = os.path.join(self.temp_dir, "test.c")
        with open(test_file, "w") as f:
            f.write("// test")

        time.sleep(0.3)
        watcher.stop()

        # 应该检测到创建
        self.callback.assert_called()

    def test_detect_modified_file(self):
        """测试检测文件修改"""
        # 先创建文件
        test_file = os.path.join(self.temp_dir, "existing.c")
        with open(test_file, "w") as f:
            f.write("// original")

        watcher = PollingWatcher(
            directories=[self.temp_dir], callback=self.callback, interval=0.1
        )

        watcher.start()
        time.sleep(0.2)

        # 修改文件
        with open(test_file, "w") as f:
            f.write("// modified")

        time.sleep(0.3)
        watcher.stop()

        # 应该检测到修改
        self.callback.assert_called()


class TestFileWatcher(unittest.TestCase):
    """FileWatcher 测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.callback = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """测试初始化"""
        watcher = FileWatcher(
            directories=[self.temp_dir], callback=self.callback, extensions=[".c"]
        )

        self.assertEqual(watcher.directories, [self.temp_dir])
        self.assertEqual(watcher.callback, self.callback)

    def test_init_filters_invalid_dirs(self):
        """测试初始化时过滤无效目录"""
        watcher = FileWatcher(
            directories=[self.temp_dir, "/nonexistent/12345"], callback=self.callback
        )

        self.assertEqual(watcher.directories, [self.temp_dir])

    def test_start_stop(self):
        """测试启动和停止"""
        watcher = FileWatcher(directories=[self.temp_dir], callback=self.callback)

        result = watcher.start()
        self.assertTrue(result)
        self.assertTrue(watcher.is_running())

        watcher.stop()
        time.sleep(0.1)
        self.assertFalse(watcher.is_running())

    def test_start_no_directories(self):
        """测试无目录时启动"""
        watcher = FileWatcher(directories=[], callback=self.callback)

        result = watcher.start()
        self.assertFalse(result)

    def test_is_running(self):
        """测试运行状态检查"""
        watcher = FileWatcher(directories=[self.temp_dir], callback=self.callback)

        self.assertFalse(watcher.is_running())

        watcher.start()
        self.assertTrue(watcher.is_running())

        watcher.stop()


class TestModuleFunctions(unittest.TestCase):
    """模块级函数测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.callback = Mock()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_start_watching(self):
        """测试 start_watching 函数"""
        watcher = start_watching(directories=[self.temp_dir], callback=self.callback)

        self.assertIsNotNone(watcher)
        self.assertIsInstance(watcher, FileWatcher)

        stop_watching(watcher)

    def test_start_watching_no_dirs(self):
        """测试无目录时 start_watching"""
        watcher = start_watching(directories=[], callback=self.callback)

        self.assertIsNone(watcher)

    def test_stop_watching_none(self):
        """测试停止 None"""
        stop_watching(None)  # 不应该报错


if __name__ == "__main__":
    unittest.main(verbosity=2)

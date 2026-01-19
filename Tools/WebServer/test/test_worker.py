#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Worker 模块测试
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import worker


class TestWorkerModule(unittest.TestCase):
    """Worker 模块测试"""

    def setUp(self):
        """每个测试前停止 worker"""
        worker.stop()
        worker.configure(None, None)

    def tearDown(self):
        """每个测试后停止 worker"""
        worker.stop()
        worker.configure(None, None)

    def test_start_stop(self):
        """测试启动和停止"""
        self.assertFalse(worker.is_running())

        worker.start()
        time.sleep(0.1)
        self.assertTrue(worker.is_running())

        worker.stop()
        time.sleep(0.1)
        self.assertFalse(worker.is_running())

    def test_start_twice(self):
        """测试重复启动"""
        worker.start()
        worker.start()  # 不应该报错

        self.assertTrue(worker.is_running())

    def test_stop_without_start(self):
        """测试未启动时停止"""
        worker.stop()  # 不应该报错
        self.assertFalse(worker.is_running())

    def test_enqueue_when_not_running(self):
        """测试未运行时入队"""
        result = worker.enqueue("test", {})
        self.assertFalse(result)

    def test_enqueue_when_running(self):
        """测试运行时入队"""
        worker.start()

        result = worker.enqueue("test", {"key": "value"})
        self.assertTrue(result)

    def test_enqueue_and_wait(self):
        """测试入队并等待"""
        worker.start()

        result = worker.enqueue_and_wait("test", {}, timeout=1.0)
        # 没有处理器，但应该完成
        self.assertTrue(result)

    def test_enqueue_and_wait_not_running(self):
        """测试未运行时入队并等待"""
        result = worker.enqueue_and_wait("test", {}, timeout=0.1)
        self.assertFalse(result)

    def test_run_in_worker(self):
        """测试在 worker 中运行函数"""
        worker.start()

        executed = []

        def task():
            executed.append(True)

        result = worker.run_in_worker(task, timeout=1.0)

        self.assertTrue(result)
        self.assertEqual(executed, [True])

    def test_run_in_worker_exception(self):
        """测试在 worker 中运行抛出异常的函数"""
        worker.start()

        def bad_task():
            raise ValueError("Test error")

        # 不应该抛出异常到调用者
        result = worker.run_in_worker(bad_task, timeout=1.0)
        self.assertTrue(result)

    def test_configure_process_queue_item(self):
        """测试配置队列处理回调"""
        handler = Mock()
        worker.configure(process_queue_item=handler, process_rx=None)

        worker.start()
        worker.enqueue("custom_cmd", {"data": 123})
        time.sleep(0.2)

        handler.assert_called_with("custom_cmd", {"data": 123})

    def test_configure_process_rx(self):
        """测试配置接收处理回调"""
        rx_handler = Mock()
        worker.configure(process_queue_item=None, process_rx=rx_handler)

        worker.start()
        time.sleep(0.2)

        # RX 处理器应该被调用
        self.assertTrue(rx_handler.called)

    def test_get_timer_manager(self):
        """测试获取定时器管理器"""
        self.assertIsNone(worker.get_timer_manager())

        worker.start()

        tm = worker.get_timer_manager()
        self.assertIsNotNone(tm)

    def test_timer_integration(self):
        """测试定时器集成"""
        worker.start()

        executed = []

        def timer_callback():
            executed.append(time.time())

        tm = worker.get_timer_manager()
        timer = tm.add(0.1, timer_callback, "test_timer")
        # 重置定时器以确保从现在开始计时
        timer.reset()

        # 唤醒 worker 来立即处理
        for _ in range(5):
            worker.wake()
            time.sleep(0.12)

        # 应该执行多次
        self.assertGreaterEqual(len(executed), 2)

    def test_wake(self):
        """测试唤醒 worker"""
        worker.start()

        # 不应该报错
        worker.wake()
        worker.wake()

    def test_wake_when_not_running(self):
        """测试未运行时唤醒"""
        worker.wake()  # 不应该报错

    def test_process_queue_item_exception(self):
        """测试队列处理器异常"""

        def bad_handler(cmd_type, cmd_data):
            raise RuntimeError("Handler error")

        worker.configure(process_queue_item=bad_handler, process_rx=None)
        worker.start()

        # 不应该崩溃
        worker.enqueue("test", {})
        time.sleep(0.2)

        self.assertTrue(worker.is_running())

    def test_process_rx_exception(self):
        """测试接收处理器异常"""

        def bad_rx():
            raise RuntimeError("RX error")

        worker.configure(process_queue_item=None, process_rx=bad_rx)
        worker.start()

        time.sleep(0.2)

        # Worker 应该继续运行
        self.assertTrue(worker.is_running())

    def test_enqueue_with_done_event(self):
        """测试带 done_event 的入队"""
        worker.start()

        done_event = threading.Event()
        worker.enqueue("test", {}, done_event)

        # 等待完成
        result = done_event.wait(timeout=1.0)
        self.assertTrue(result)

    def test_multiple_enqueue(self):
        """测试多次入队"""
        results = []

        def handler(cmd_type, cmd_data):
            results.append(cmd_data)

        worker.configure(process_queue_item=handler, process_rx=None)
        worker.start()

        for i in range(5):
            worker.enqueue("test", i)

        time.sleep(0.5)

        self.assertEqual(len(results), 5)
        self.assertEqual(sorted(results), [0, 1, 2, 3, 4])


class TestWorkerStates(unittest.TestCase):
    """Worker 状态测试"""

    def setUp(self):
        worker.stop()
        worker.configure(None, None)

    def tearDown(self):
        worker.stop()
        worker.configure(None, None)

    def test_restart(self):
        """测试重启"""
        worker.start()
        self.assertTrue(worker.is_running())

        worker.stop()
        time.sleep(0.1)
        self.assertFalse(worker.is_running())

        worker.start()
        time.sleep(0.1)
        self.assertTrue(worker.is_running())

    def test_timer_cleared_on_stop(self):
        """测试停止时清除定时器"""
        worker.start()
        tm = worker.get_timer_manager()
        tm.add(1.0, lambda: None, "test")

        worker.stop()

        # 停止后定时器管理器应该是 None
        self.assertIsNone(worker.get_timer_manager())


if __name__ == "__main__":
    unittest.main(verbosity=2)

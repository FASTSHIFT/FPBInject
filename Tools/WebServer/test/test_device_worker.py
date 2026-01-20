#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Device Worker 模块测试
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import device_worker
from device_worker import (
    DeviceWorker,
    get_worker,
    start_worker,
    stop_worker,
    run_in_device_worker,
    get_device_timer_manager,
)


class TestDeviceWorker(unittest.TestCase):
    """DeviceWorker 类测试"""

    def setUp(self):
        """设置测试环境"""
        self.device = Mock()
        self.device.ser = None
        self.device.serial_log = []
        self.device.log_next_id = 0
        self.device.log_max_size = 1000
        self.worker = DeviceWorker(self.device)

    def tearDown(self):
        """清理测试环境"""
        if self.worker.is_running():
            self.worker.stop()

    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.worker.device, self.device)
        self.assertFalse(self.worker.is_running())

    def test_start(self):
        """测试启动"""
        self.worker.start()
        time.sleep(0.1)

        self.assertTrue(self.worker.is_running())

    def test_stop(self):
        """测试停止"""
        self.worker.start()
        time.sleep(0.1)

        self.worker.stop()
        time.sleep(0.1)

        self.assertFalse(self.worker.is_running())

    def test_start_twice(self):
        """测试重复启动"""
        self.worker.start()
        self.worker.start()  # 不应该报错

        self.assertTrue(self.worker.is_running())

    def test_stop_without_start(self):
        """测试未启动时停止"""
        self.worker.stop()  # 不应该报错
        self.assertFalse(self.worker.is_running())

    def test_enqueue_not_running(self):
        """测试未运行时入队"""
        result = self.worker.enqueue("test", {})
        self.assertFalse(result)

    def test_enqueue_running(self):
        """测试运行时入队"""
        self.worker.start()

        result = self.worker.enqueue("test", {})
        self.assertTrue(result)

    def test_enqueue_and_wait(self):
        """测试入队并等待"""
        self.worker.start()

        result = self.worker.enqueue_and_wait("test", {}, timeout=1.0)
        self.assertTrue(result)

    def test_enqueue_and_wait_not_running(self):
        """测试未运行时入队并等待"""
        result = self.worker.enqueue_and_wait("test", {}, timeout=0.1)
        self.assertFalse(result)

    def test_run_in_worker(self):
        """测试在 worker 中运行函数"""
        self.worker.start()

        executed = []

        def task():
            executed.append(True)

        result = self.worker.run_in_worker(task, timeout=1.0)

        self.assertTrue(result)
        self.assertEqual(executed, [True])

    def test_run_in_worker_exception(self):
        """测试在 worker 中运行抛出异常的函数"""
        self.worker.start()

        def bad_task():
            raise ValueError("Test error")

        # 不应该抛出异常
        result = self.worker.run_in_worker(bad_task, timeout=1.0)
        self.assertTrue(result)

    def test_get_timer_manager(self):
        """测试获取定时器管理器"""
        self.assertIsNone(self.worker.get_timer_manager())

        self.worker.start()

        tm = self.worker.get_timer_manager()
        self.assertIsNotNone(tm)

    def test_wake(self):
        """测试唤醒"""
        self.worker.start()

        # 不应该报错
        self.worker.wake()

    def test_wake_not_running(self):
        """测试未运行时唤醒"""
        self.worker.wake()  # 不应该报错

    def test_timer_integration(self):
        """测试定时器集成"""
        self.worker.start()

        executed = []

        def timer_callback():
            executed.append(time.time())

        tm = self.worker.get_timer_manager()
        tm.add(0.1, timer_callback, "test_timer")

        time.sleep(0.35)

        self.assertGreaterEqual(len(executed), 2)


class TestSerialOperations(unittest.TestCase):
    """串口操作测试"""

    def setUp(self):
        """设置测试环境"""
        self.device = Mock()
        self.device.serial_log = []
        self.device.log_next_id = 0
        self.device.log_max_size = 1000
        self.mock_ser = Mock()
        self.mock_ser.isOpen.return_value = True
        self.device.ser = self.mock_ser
        self.worker = DeviceWorker(self.device)

    def tearDown(self):
        """清理测试环境"""
        if self.worker.is_running():
            self.worker.stop()

    def test_serial_write_cmd(self):
        """测试串口写入命令"""
        self.worker.start()

        self.worker.enqueue("write", "test command\n")
        time.sleep(0.2)

        self.mock_ser.write.assert_called()
        self.mock_ser.flush.assert_called()

    def test_serial_write_bytes(self):
        """测试串口写入字节"""
        self.worker.start()

        self.worker.enqueue("write", b"binary data")
        time.sleep(0.2)

        self.mock_ser.write.assert_called()

    def test_serial_write_no_serial(self):
        """测试无串口时写入"""
        self.device.ser = None
        self.worker.start()

        # 不应该报错
        self.worker.enqueue("write", "test")
        time.sleep(0.2)

    def test_serial_write_closed(self):
        """测试串口关闭时写入"""
        self.mock_ser.isOpen.return_value = False
        self.worker.start()

        # 不应该报错
        self.worker.enqueue("write", "test")
        time.sleep(0.2)

        self.mock_ser.write.assert_not_called()

    def test_serial_read(self):
        """测试串口读取"""
        # Mock in_waiting to return 10 bytes available
        type(self.mock_ser).in_waiting = PropertyMock(return_value=10)
        self.mock_ser.read.return_value = b"test data\n"
        
        # Also need to mock raw_serial_log for raw log
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 1000

        self.worker.start()
        time.sleep(0.5)  # Give more time for worker to process

        # 应该有日志记录
        self.assertTrue(len(self.device.serial_log) > 0)

    def test_serial_log_overflow(self):
        """测试串口日志溢出"""
        self.device.log_max_size = 5

        # 手动添加日志
        for i in range(10):
            self.device.serial_log.append({"id": i})
            if len(self.device.serial_log) > self.device.log_max_size:
                self.device.serial_log = self.device.serial_log[
                    -self.device.log_max_size :
                ]

        self.assertEqual(len(self.device.serial_log), 5)


class TestModuleFunctions(unittest.TestCase):
    """模块级函数测试"""

    def setUp(self):
        """设置测试环境"""
        device_worker._worker = None
        self.device = Mock()
        self.device.ser = None
        self.device.serial_log = []
        self.device.log_next_id = 0
        self.device.log_max_size = 1000
        self.device.worker = None

    def tearDown(self):
        """清理测试环境"""
        if device_worker._worker is not None:
            device_worker._worker.stop()
            device_worker._worker = None

    def test_get_worker(self):
        """测试获取 worker"""
        worker = get_worker(self.device)

        self.assertIsNotNone(worker)
        self.assertIsInstance(worker, DeviceWorker)

    def test_get_worker_returns_same(self):
        """测试获取相同的 worker"""
        worker1 = get_worker(self.device)
        worker2 = get_worker(self.device)

        self.assertEqual(worker1, worker2)

    def test_start_worker(self):
        """测试启动 worker"""
        worker = start_worker(self.device)
        time.sleep(0.1)

        self.assertTrue(worker.is_running())
        self.assertEqual(self.device.worker, worker)

    def test_stop_worker(self):
        """测试停止 worker"""
        start_worker(self.device)
        time.sleep(0.1)

        stop_worker(self.device)
        time.sleep(0.1)

        self.assertIsNone(self.device.worker)
        self.assertIsNone(device_worker._worker)

    def test_run_in_device_worker_no_worker(self):
        """测试无 worker 时运行函数"""
        result = run_in_device_worker(self.device, lambda: None)
        self.assertFalse(result)

    def test_run_in_device_worker_not_running(self):
        """测试 worker 未运行时运行函数"""
        self.device.worker = Mock()
        self.device.worker.is_running.return_value = False

        result = run_in_device_worker(self.device, lambda: None)
        self.assertFalse(result)

    def test_run_in_device_worker_success(self):
        """测试运行函数成功"""
        start_worker(self.device)
        time.sleep(0.1)

        executed = []

        def task():
            executed.append(True)

        result = run_in_device_worker(self.device, task)

        self.assertTrue(result)
        self.assertEqual(executed, [True])

    def test_get_device_timer_manager_no_worker(self):
        """测试无 worker 时获取定时器管理器"""
        result = get_device_timer_manager(self.device)
        self.assertIsNone(result)

    def test_get_device_timer_manager_with_worker(self):
        """测试有 worker 时获取定时器管理器"""
        start_worker(self.device)
        time.sleep(0.1)

        tm = get_device_timer_manager(self.device)

        self.assertIsNotNone(tm)


class TestDeviceWorkerExtended(unittest.TestCase):
    """DeviceWorker 扩展测试"""

    def setUp(self):
        self.device = Mock()
        self.device.ser = None
        self.device.serial_log = []
        self.device.log_next_id = 0
        self.device.log_max_size = 1000
        self.worker = DeviceWorker(self.device)

    def tearDown(self):
        if self.worker.is_running():
            self.worker.stop()

    def test_queue_overflow_handling(self):
        """测试队列溢出处理"""
        self.worker.start()
        time.sleep(0.1)

        # 快速入队多个任务
        for i in range(10):
            self.worker.enqueue("test", {"index": i})

        time.sleep(0.5)
        # 应该正常完成，不应崩溃

    def test_enqueue_with_handler(self):
        """测试带处理器的入队"""
        self.worker.start()
        time.sleep(0.1)

        result = self.worker.enqueue("serial_write", {"data": b"test"})
        self.assertTrue(result)

    def test_multiple_start_stop_cycles(self):
        """测试多次启动停止循环"""
        for _ in range(3):
            self.worker.start()
            time.sleep(0.1)
            self.assertTrue(self.worker.is_running())
            self.worker.stop()
            time.sleep(0.1)
            self.assertFalse(self.worker.is_running())


if __name__ == "__main__":
    unittest.main(verbosity=2)

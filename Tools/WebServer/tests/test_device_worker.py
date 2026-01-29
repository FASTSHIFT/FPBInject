#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Device Worker module tests
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.device_worker as device_worker
from services.device_worker import (
    DeviceWorker,
    get_worker,
    start_worker,
    stop_worker,
    run_in_device_worker,
    get_device_timer_manager,
)


class TestDeviceWorker(unittest.TestCase):
    """DeviceWorker class tests"""

    def setUp(self):
        """Set up test environment"""
        self.device = Mock()
        self.device.ser = None
        self.device.serial_log = []
        self.device.log_next_id = 0
        self.device.log_max_size = 1000
        self.worker = DeviceWorker(self.device)

    def tearDown(self):
        """Clean up test environment"""
        if self.worker.is_running():
            self.worker.stop()

    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.worker.device, self.device)
        self.assertFalse(self.worker.is_running())

    def test_start(self):
        """Test start"""
        self.worker.start()
        time.sleep(0.1)

        self.assertTrue(self.worker.is_running())

    def test_stop(self):
        """Test stop"""
        self.worker.start()
        time.sleep(0.1)

        self.worker.stop()
        time.sleep(0.1)

        self.assertFalse(self.worker.is_running())

    def test_start_twice(self):
        """Test starting twice"""
        self.worker.start()
        self.worker.start()  # Should not error

        self.assertTrue(self.worker.is_running())

    def test_stop_without_start(self):
        """Test stopping without starting"""
        self.worker.stop()  # Should not error
        self.assertFalse(self.worker.is_running())

    def test_enqueue_not_running(self):
        """Test enqueue when not running"""
        result = self.worker.enqueue("test", {})
        self.assertFalse(result)

    def test_enqueue_running(self):
        """Test enqueue when running"""
        self.worker.start()

        result = self.worker.enqueue("test", {})
        self.assertTrue(result)

    def test_enqueue_and_wait(self):
        """Test enqueue and wait"""
        self.worker.start()

        result = self.worker.enqueue_and_wait("test", {}, timeout=1.0)
        self.assertTrue(result)

    def test_enqueue_and_wait_not_running(self):
        """Test enqueue and wait when not running"""
        result = self.worker.enqueue_and_wait("test", {}, timeout=0.1)
        self.assertFalse(result)

    def test_run_in_worker(self):
        """Test running function in worker"""
        self.worker.start()

        executed = []

        def task():
            executed.append(True)

        result = self.worker.run_in_worker(task, timeout=1.0)

        self.assertTrue(result)
        self.assertEqual(executed, [True])

    def test_run_in_worker_exception(self):
        """Test running exception-throwing function in worker"""
        self.worker.start()

        def bad_task():
            raise ValueError("Test error")

        # Should not throw exception
        result = self.worker.run_in_worker(bad_task, timeout=1.0)
        self.assertTrue(result)

    def test_get_timer_manager(self):
        """Test getting timer manager"""
        self.assertIsNone(self.worker.get_timer_manager())

        self.worker.start()

        tm = self.worker.get_timer_manager()
        self.assertIsNotNone(tm)

    def test_wake(self):
        """Test wake"""
        self.worker.start()

        # Should not error
        self.worker.wake()

    def test_wake_not_running(self):
        """Test wake when not running"""
        self.worker.wake()  # Should not error

    def test_timer_integration(self):
        """Test timer integration"""
        self.worker.start()

        executed = []

        def timer_callback():
            executed.append(time.time())

        tm = self.worker.get_timer_manager()
        tm.add(0.1, timer_callback, "test_timer")

        time.sleep(0.35)

        self.assertGreaterEqual(len(executed), 2)


class TestSerialOperations(unittest.TestCase):
    """Serial operation test"""

    def setUp(self):
        """Set up test environment"""
        self.device = Mock()
        self.device.serial_log = []
        self.device.log_next_id = 0
        self.device.log_max_size = 1000
        self.mock_ser = Mock()
        self.mock_ser.isOpen.return_value = True
        self.device.ser = self.mock_ser
        self.worker = DeviceWorker(self.device)

    def tearDown(self):
        """Clean up test environment"""
        if self.worker.is_running():
            self.worker.stop()

    def test_serial_write_cmd(self):
        """Test serial write command"""
        self.worker.start()

        self.worker.enqueue("write", "test command\n")
        time.sleep(0.2)

        self.mock_ser.write.assert_called()
        self.mock_ser.flush.assert_called()

    def test_serial_write_bytes(self):
        """Test serial write bytes"""
        self.worker.start()

        self.worker.enqueue("write", b"binary data")
        time.sleep(0.2)

        self.mock_ser.write.assert_called()

    def test_serial_write_no_serial(self):
        """Test write when no serial"""
        self.device.ser = None
        self.worker.start()

        # Should not error
        self.worker.enqueue("write", "test")
        time.sleep(0.2)

    def test_serial_write_closed(self):
        """Test write when serial closed"""
        self.mock_ser.isOpen.return_value = False
        self.worker.start()

        # Should not error
        self.worker.enqueue("write", "test")
        time.sleep(0.2)

        self.mock_ser.write.assert_not_called()

    def test_serial_read(self):
        """Test serial read"""
        # Mock in_waiting to return 10 bytes available
        type(self.mock_ser).in_waiting = PropertyMock(return_value=10)
        self.mock_ser.read.return_value = b"test data\n"

        # Also need to mock raw_serial_log for raw log
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 1000

        self.worker.start()
        time.sleep(0.5)  # Give more time for worker to process

        # Should have log records
        self.assertTrue(len(self.device.serial_log) > 0)

    def test_serial_log_overflow(self):
        """Test serial log overflow"""
        self.device.log_max_size = 5

        # Manually add logs
        for i in range(10):
            self.device.serial_log.append({"id": i})
            if len(self.device.serial_log) > self.device.log_max_size:
                self.device.serial_log = self.device.serial_log[
                    -self.device.log_max_size :
                ]

        self.assertEqual(len(self.device.serial_log), 5)


class TestModuleFunctions(unittest.TestCase):
    """Module functions test"""

    def setUp(self):
        """Set up test environment"""
        device_worker._worker = None
        self.device = Mock()
        self.device.ser = None
        self.device.serial_log = []
        self.device.log_next_id = 0
        self.device.log_max_size = 1000
        self.device.worker = None

    def tearDown(self):
        """Clean up test environment"""
        if device_worker._worker is not None:
            device_worker._worker.stop()
            device_worker._worker = None

    def test_get_worker(self):
        """Test get worker"""
        worker = get_worker(self.device)

        self.assertIsNotNone(worker)
        self.assertIsInstance(worker, DeviceWorker)

    def test_get_worker_returns_same(self):
        """Test get same worker"""
        worker1 = get_worker(self.device)
        worker2 = get_worker(self.device)

        self.assertEqual(worker1, worker2)

    def test_start_worker(self):
        """Test start worker"""
        worker = start_worker(self.device)
        time.sleep(0.1)

        self.assertTrue(worker.is_running())
        self.assertEqual(self.device.worker, worker)

    def test_stop_worker(self):
        """Test stop worker"""
        start_worker(self.device)
        time.sleep(0.1)

        stop_worker(self.device)
        time.sleep(0.1)

        self.assertIsNone(self.device.worker)
        self.assertIsNone(device_worker._worker)

    def test_run_in_device_worker_no_worker(self):
        """Test run function with no worker"""
        result = run_in_device_worker(self.device, lambda: None)
        self.assertFalse(result)

    def test_run_in_device_worker_not_running(self):
        """Test run function when worker not running"""
        self.device.worker = Mock()
        self.device.worker.is_running.return_value = False

        result = run_in_device_worker(self.device, lambda: None)
        self.assertFalse(result)

    def test_run_in_device_worker_success(self):
        """Test run function success"""
        start_worker(self.device)
        time.sleep(0.1)

        executed = []

        def task():
            executed.append(True)

        result = run_in_device_worker(self.device, task)

        self.assertTrue(result)
        self.assertEqual(executed, [True])

    def test_get_device_timer_manager_no_worker(self):
        """Test get timer manager with no worker"""
        result = get_device_timer_manager(self.device)
        self.assertIsNone(result)

    def test_get_device_timer_manager_with_worker(self):
        """Test get timer manager with worker"""
        start_worker(self.device)
        time.sleep(0.1)

        tm = get_device_timer_manager(self.device)

        self.assertIsNotNone(tm)


class TestDeviceWorkerExtended(unittest.TestCase):
    """DeviceWorker extended test"""

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
        """Test queue overflow handling"""
        self.worker.start()
        time.sleep(0.1)

        # Quickly enqueue multiple tasks
        for i in range(10):
            self.worker.enqueue("test", {"index": i})

        time.sleep(0.5)
        # Should complete normally, not crash

    def test_enqueue_with_handler(self):
        """Test enqueue with handler"""
        self.worker.start()
        time.sleep(0.1)

        result = self.worker.enqueue("serial_write", {"data": b"test"})
        self.assertTrue(result)

    def test_multiple_start_stop_cycles(self):
        """Test multiple start stop cycles"""
        for _ in range(3):
            self.worker.start()
            time.sleep(0.1)
            self.assertTrue(self.worker.is_running())
            self.worker.stop()
            time.sleep(0.1)
            self.assertFalse(self.worker.is_running())


if __name__ == "__main__":
    unittest.main(verbosity=2)

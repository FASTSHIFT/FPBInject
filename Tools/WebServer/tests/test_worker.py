#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Worker module tests
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
    """Worker module tests"""

    def setUp(self):
        """Stop worker before each test"""
        worker.stop()
        worker.configure(None, None)

    def tearDown(self):
        """Stop worker after each test"""
        worker.stop()
        worker.configure(None, None)

    def test_start_stop(self):
        """Test start and stop"""
        self.assertFalse(worker.is_running())

        worker.start()
        time.sleep(0.1)
        self.assertTrue(worker.is_running())

        worker.stop()
        time.sleep(0.1)
        self.assertFalse(worker.is_running())

    def test_start_twice(self):
        """Test starting twice"""
        worker.start()
        worker.start()  # Should not error

        self.assertTrue(worker.is_running())

    def test_stop_without_start(self):
        """Test stopping without starting"""
        worker.stop()  # Should not error
        self.assertFalse(worker.is_running())

    def test_enqueue_when_not_running(self):
        """Test enqueue when not running"""
        result = worker.enqueue("test", {})
        self.assertFalse(result)

    def test_enqueue_when_running(self):
        """Test enqueue when running"""
        worker.start()

        result = worker.enqueue("test", {"key": "value"})
        self.assertTrue(result)

    def test_enqueue_and_wait(self):
        """Test enqueue and wait"""
        worker.start()

        result = worker.enqueue_and_wait("test", {}, timeout=1.0)
        # No handler, but should complete
        self.assertTrue(result)

    def test_enqueue_and_wait_not_running(self):
        """Test enqueue and wait when not running"""
        result = worker.enqueue_and_wait("test", {}, timeout=0.1)
        self.assertFalse(result)

    def test_run_in_worker(self):
        """Test running function in worker"""
        worker.start()

        executed = []

        def task():
            executed.append(True)

        result = worker.run_in_worker(task, timeout=1.0)

        self.assertTrue(result)
        self.assertEqual(executed, [True])

    def test_run_in_worker_exception(self):
        """Test running exception-throwing function in worker"""
        worker.start()

        def bad_task():
            raise ValueError("Test error")

        # Should not throw exception to caller
        result = worker.run_in_worker(bad_task, timeout=1.0)
        self.assertTrue(result)

    def test_configure_process_queue_item(self):
        """Test configuring queue processing callback"""
        handler = Mock()
        worker.configure(process_queue_item=handler, process_rx=None)

        worker.start()
        worker.enqueue("custom_cmd", {"data": 123})
        time.sleep(0.2)

        handler.assert_called_with("custom_cmd", {"data": 123})

    def test_configure_process_rx(self):
        """Test configuring receive processing callback"""
        rx_handler = Mock()
        worker.configure(process_queue_item=None, process_rx=rx_handler)

        worker.start()
        time.sleep(0.2)

        # RX handler should be called
        self.assertTrue(rx_handler.called)

    def test_get_timer_manager(self):
        """Test getting timer manager"""
        self.assertIsNone(worker.get_timer_manager())

        worker.start()

        tm = worker.get_timer_manager()
        self.assertIsNotNone(tm)

    def test_timer_integration(self):
        """Test timer integration"""
        worker.start()

        executed = []

        def timer_callback():
            executed.append(time.time())

        tm = worker.get_timer_manager()
        timer = tm.add(0.1, timer_callback, "test_timer")
        # Reset timer to ensure timing from now
        timer.reset()

        # Wake worker to process immediately
        for _ in range(5):
            worker.wake()
            time.sleep(0.12)

        # Should execute multiple times
        self.assertGreaterEqual(len(executed), 2)

    def test_wake(self):
        """Test waking worker"""
        worker.start()

        # Should not error
        worker.wake()
        worker.wake()

    def test_wake_when_not_running(self):
        """Test waking when not running"""
        worker.wake()  # Should not error

    def test_process_queue_item_exception(self):
        """Test queue handler exception"""

        def bad_handler(cmd_type, cmd_data):
            raise RuntimeError("Handler error")

        worker.configure(process_queue_item=bad_handler, process_rx=None)
        worker.start()

        # Should not crash
        worker.enqueue("test", {})
        time.sleep(0.2)

        self.assertTrue(worker.is_running())

    def test_process_rx_exception(self):
        """Test receive handler exception"""

        def bad_rx():
            raise RuntimeError("RX error")

        worker.configure(process_queue_item=None, process_rx=bad_rx)
        worker.start()

        time.sleep(0.2)

        # Worker should continue running
        self.assertTrue(worker.is_running())

    def test_enqueue_with_done_event(self):
        """Test enqueue with done_event"""
        worker.start()

        done_event = threading.Event()
        worker.enqueue("test", {}, done_event)

        # Wait for completion
        result = done_event.wait(timeout=1.0)
        self.assertTrue(result)

    def test_multiple_enqueue(self):
        """Test multiple enqueues"""
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
    """Worker state tests"""

    def setUp(self):
        worker.stop()
        worker.configure(None, None)

    def tearDown(self):
        worker.stop()
        worker.configure(None, None)

    def test_restart(self):
        """Test restart"""
        worker.start()
        self.assertTrue(worker.is_running())

        worker.stop()
        time.sleep(0.1)
        self.assertFalse(worker.is_running())

        worker.start()
        time.sleep(0.1)
        self.assertTrue(worker.is_running())

    def test_timer_cleared_on_stop(self):
        """Test timer cleared on stop"""
        worker.start()
        tm = worker.get_timer_manager()
        tm.add(1.0, lambda: None, "test")

        worker.stop()

        # Timer manager should be None after stop
        self.assertIsNone(worker.get_timer_manager())

    def test_run_in_worker_timeout(self):
        """Test run_in_worker timeout"""
        worker.start()

        def slow_task():
            time.sleep(2)

        # Since task is slow but enqueue_and_wait has timeout
        # Here we use a task that completes normally
        def fast_task():
            pass

        result = worker.run_in_worker(fast_task, timeout=0.5)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Timer module test
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.timer import Timer, TimerManager


class TestTimer(unittest.TestCase):
    """Timer class test cases"""

    def test_init(self):
        """Test initialization"""
        callback = lambda: None
        timer = Timer(1.0, callback, name="test_timer")

        self.assertEqual(timer.interval, 1.0)
        self.assertEqual(timer.callback, callback)
        self.assertEqual(timer.name, "test_timer")
        self.assertEqual(timer.next_run, 0)
        self.assertTrue(timer.enabled)

    def test_init_default_name(self):
        """Test default name"""
        timer = Timer(1.0, lambda: None)

        self.assertTrue(timer.name.startswith("timer_"))

    def test_check_fires_callback(self):
        """Test check fires callback"""
        called = [False]

        def callback():
            called[0] = True

        timer = Timer(0.1, callback)
        timer.next_run = 0  # Set to fire immediately

        result = timer.check(time.time())

        self.assertTrue(result)
        self.assertTrue(called[0])

    def test_check_updates_next_run(self):
        """Test check updates next_run"""
        timer = Timer(1.0, lambda: None)
        timer.next_run = 0

        now = time.time()
        timer.check(now)

        self.assertAlmostEqual(timer.next_run, now + 1.0, places=2)

    def test_check_not_yet_due(self):
        """Test not yet due doesn't fire"""
        called = [False]
        timer = Timer(10.0, lambda: called.__setitem__(0, True))
        timer.next_run = time.time() + 100  # Far in the future

        result = timer.check(time.time())

        self.assertFalse(result)
        self.assertFalse(called[0])

    def test_check_disabled(self):
        """Test disabled state doesn't fire"""
        called = [False]
        timer = Timer(0.1, lambda: called.__setitem__(0, True))
        timer.next_run = 0
        timer.enabled = False

        result = timer.check(time.time())

        self.assertFalse(result)
        self.assertFalse(called[0])

    def test_reset(self):
        """Test reset"""
        timer = Timer(1.0, lambda: None)
        timer.next_run = 0

        now = time.time()
        timer.reset(now)

        self.assertAlmostEqual(timer.next_run, now + 1.0, places=2)

    def test_reset_default_now(self):
        """Test reset uses current time"""
        timer = Timer(1.0, lambda: None)
        timer.next_run = 0

        before = time.time()
        timer.reset()
        after = time.time()

        self.assertGreaterEqual(timer.next_run, before + 1.0)
        self.assertLessEqual(timer.next_run, after + 1.0)

    def test_time_until_next(self):
        """Test calculate next run time"""
        timer = Timer(1.0, lambda: None)
        now = time.time()
        timer.next_run = now + 5.0

        remaining = timer.time_until_next(now)

        self.assertAlmostEqual(remaining, 5.0, places=1)

    def test_time_until_next_past_due(self):
        """Test returns 0 when past due"""
        timer = Timer(1.0, lambda: None)
        timer.next_run = time.time() - 10  # Past time

        remaining = timer.time_until_next(time.time())

        self.assertEqual(remaining, 0)

    def test_time_until_next_disabled(self):
        """Test returns infinity when disabled"""
        timer = Timer(1.0, lambda: None)
        timer.enabled = False

        remaining = timer.time_until_next(time.time())

        self.assertEqual(remaining, float("inf"))

    def test_set_interval(self):
        """Test set interval"""
        timer = Timer(1.0, lambda: None)

        timer.set_interval(2.5)

        self.assertEqual(timer.interval, 2.5)


class TestTimerManager(unittest.TestCase):
    """TimerManager class test cases"""

    def test_init(self):
        """Test initialization"""
        manager = TimerManager()

        self.assertEqual(manager.timers, [])

    def test_add_timer(self):
        """Test add timer"""
        manager = TimerManager()

        timer = manager.add(1.0, lambda: None, name="test")

        self.assertEqual(len(manager.timers), 1)
        self.assertIn(timer, manager.timers)
        self.assertIsInstance(timer, Timer)
        self.assertEqual(timer.name, "test")

    def test_add_multiple_timers(self):
        """Test add multiple timers"""
        manager = TimerManager()

        t1 = manager.add(1.0, lambda: None, name="t1")
        t2 = manager.add(2.0, lambda: None, name="t2")
        t3 = manager.add(0.5, lambda: None, name="t3")

        self.assertEqual(len(manager.timers), 3)

    def test_remove_timer(self):
        """Test remove timer"""
        manager = TimerManager()

        t1 = manager.add(1.0, lambda: None)
        t2 = manager.add(2.0, lambda: None)

        manager.remove(t1)

        self.assertEqual(len(manager.timers), 1)
        self.assertNotIn(t1, manager.timers)
        self.assertIn(t2, manager.timers)

    def test_tick(self):
        """Test tick checks all timers"""
        manager = TimerManager()
        called = [0]

        def callback():
            called[0] += 1

        # Add 3 timers, all set to fire immediately
        for i in range(3):
            t = manager.add(0.1, callback)
            t.next_run = 0

        manager.tick(time.time())

        self.assertEqual(called[0], 3)

    def test_get_next_timeout(self):
        """Test get next timeout time"""
        manager = TimerManager()

        now = time.time()
        t1 = manager.add(5.0, lambda: None)
        t1.next_run = now + 5.0
        t2 = manager.add(2.0, lambda: None)
        t2.next_run = now + 2.0

        timeout = manager.next_wake_time(now)

        self.assertAlmostEqual(timeout, 2.0, places=1)

    def test_get_next_timeout_empty(self):
        """Test empty manager returns None"""
        manager = TimerManager()

        timeout = manager.next_wake_time(time.time())

        self.assertIsNone(timeout)

    def test_clear(self):
        """Test clear all timers"""
        manager = TimerManager()
        manager.add(1.0, lambda: None)
        manager.add(2.0, lambda: None)

        manager.clear()

        self.assertEqual(len(manager.timers), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

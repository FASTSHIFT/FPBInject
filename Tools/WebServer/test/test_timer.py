#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Timer 模块测试
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timer import Timer, TimerManager


class TestTimer(unittest.TestCase):
    """Timer 类测试用例"""

    def test_init(self):
        """测试初始化"""
        callback = lambda: None
        timer = Timer(1.0, callback, name="test_timer")

        self.assertEqual(timer.interval, 1.0)
        self.assertEqual(timer.callback, callback)
        self.assertEqual(timer.name, "test_timer")
        self.assertEqual(timer.next_run, 0)
        self.assertTrue(timer.enabled)

    def test_init_default_name(self):
        """测试默认名称"""
        timer = Timer(1.0, lambda: None)

        self.assertTrue(timer.name.startswith("timer_"))

    def test_check_fires_callback(self):
        """测试 check 触发回调"""
        called = [False]

        def callback():
            called[0] = True

        timer = Timer(0.1, callback)
        timer.next_run = 0  # 设置为立即触发

        result = timer.check(time.time())

        self.assertTrue(result)
        self.assertTrue(called[0])

    def test_check_updates_next_run(self):
        """测试 check 更新 next_run"""
        timer = Timer(1.0, lambda: None)
        timer.next_run = 0

        now = time.time()
        timer.check(now)

        self.assertAlmostEqual(timer.next_run, now + 1.0, places=2)

    def test_check_not_yet_due(self):
        """测试未到期不触发"""
        called = [False]
        timer = Timer(10.0, lambda: called.__setitem__(0, True))
        timer.next_run = time.time() + 100  # 很久以后

        result = timer.check(time.time())

        self.assertFalse(result)
        self.assertFalse(called[0])

    def test_check_disabled(self):
        """测试禁用状态不触发"""
        called = [False]
        timer = Timer(0.1, lambda: called.__setitem__(0, True))
        timer.next_run = 0
        timer.enabled = False

        result = timer.check(time.time())

        self.assertFalse(result)
        self.assertFalse(called[0])

    def test_reset(self):
        """测试重置"""
        timer = Timer(1.0, lambda: None)
        timer.next_run = 0

        now = time.time()
        timer.reset(now)

        self.assertAlmostEqual(timer.next_run, now + 1.0, places=2)

    def test_reset_default_now(self):
        """测试重置使用当前时间"""
        timer = Timer(1.0, lambda: None)
        timer.next_run = 0

        before = time.time()
        timer.reset()
        after = time.time()

        self.assertGreaterEqual(timer.next_run, before + 1.0)
        self.assertLessEqual(timer.next_run, after + 1.0)

    def test_time_until_next(self):
        """测试计算下次运行时间"""
        timer = Timer(1.0, lambda: None)
        now = time.time()
        timer.next_run = now + 5.0

        remaining = timer.time_until_next(now)

        self.assertAlmostEqual(remaining, 5.0, places=1)

    def test_time_until_next_past_due(self):
        """测试已过期返回0"""
        timer = Timer(1.0, lambda: None)
        timer.next_run = time.time() - 10  # 过去的时间

        remaining = timer.time_until_next(time.time())

        self.assertEqual(remaining, 0)

    def test_time_until_next_disabled(self):
        """测试禁用时返回无穷大"""
        timer = Timer(1.0, lambda: None)
        timer.enabled = False

        remaining = timer.time_until_next(time.time())

        self.assertEqual(remaining, float("inf"))

    def test_set_interval(self):
        """测试设置间隔"""
        timer = Timer(1.0, lambda: None)

        timer.set_interval(2.5)

        self.assertEqual(timer.interval, 2.5)


class TestTimerManager(unittest.TestCase):
    """TimerManager 类测试用例"""

    def test_init(self):
        """测试初始化"""
        manager = TimerManager()

        self.assertEqual(manager.timers, [])

    def test_add_timer(self):
        """测试添加定时器"""
        manager = TimerManager()

        timer = manager.add(1.0, lambda: None, name="test")

        self.assertEqual(len(manager.timers), 1)
        self.assertIn(timer, manager.timers)
        self.assertIsInstance(timer, Timer)
        self.assertEqual(timer.name, "test")

    def test_add_multiple_timers(self):
        """测试添加多个定时器"""
        manager = TimerManager()

        t1 = manager.add(1.0, lambda: None, name="t1")
        t2 = manager.add(2.0, lambda: None, name="t2")
        t3 = manager.add(0.5, lambda: None, name="t3")

        self.assertEqual(len(manager.timers), 3)

    def test_remove_timer(self):
        """测试移除定时器"""
        manager = TimerManager()

        t1 = manager.add(1.0, lambda: None)
        t2 = manager.add(2.0, lambda: None)

        manager.remove(t1)

        self.assertEqual(len(manager.timers), 1)
        self.assertNotIn(t1, manager.timers)
        self.assertIn(t2, manager.timers)

    def test_tick(self):
        """测试 tick 检查所有定时器"""
        manager = TimerManager()
        called = [0]

        def callback():
            called[0] += 1

        # 添加3个定时器，都设置为立即触发
        for i in range(3):
            t = manager.add(0.1, callback)
            t.next_run = 0

        manager.tick(time.time())

        self.assertEqual(called[0], 3)

    def test_get_next_timeout(self):
        """测试获取下次超时时间"""
        manager = TimerManager()

        now = time.time()
        t1 = manager.add(5.0, lambda: None)
        t1.next_run = now + 5.0
        t2 = manager.add(2.0, lambda: None)
        t2.next_run = now + 2.0

        timeout = manager.next_wake_time(now)

        self.assertAlmostEqual(timeout, 2.0, places=1)

    def test_get_next_timeout_empty(self):
        """测试空管理器返回 None"""
        manager = TimerManager()

        timeout = manager.next_wake_time(time.time())

        self.assertIsNone(timeout)

    def test_clear(self):
        """测试清空所有定时器"""
        manager = TimerManager()
        manager.add(1.0, lambda: None)
        manager.add(2.0, lambda: None)

        manager.clear()

        self.assertEqual(len(manager.timers), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

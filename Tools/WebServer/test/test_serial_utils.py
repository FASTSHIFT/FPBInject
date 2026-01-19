#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serial Utils 模块测试
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial_utils


class TestScanSerialPorts(unittest.TestCase):
    """scan_serial_ports 测试"""

    @patch("serial_utils.serial.tools.list_ports.comports")
    @patch("serial_utils.glob.glob")
    def test_scan_ports_basic(self, mock_glob, mock_comports):
        """测试扫描基本端口"""
        mock_port = Mock()
        mock_port.device = "/dev/ttyUSB0"
        mock_port.description = "USB Serial"
        mock_comports.return_value = [mock_port]
        mock_glob.return_value = []

        result = serial_utils.scan_serial_ports()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["device"], "/dev/ttyUSB0")
        self.assertEqual(result[0]["description"], "USB Serial")

    @patch("serial_utils.serial.tools.list_ports.comports")
    @patch("serial_utils.glob.glob")
    def test_scan_ports_with_ch341(self, mock_glob, mock_comports):
        """测试扫描包含 CH341 的端口"""
        mock_comports.return_value = []
        mock_glob.return_value = ["/dev/ttyCH341USB0", "/dev/ttyCH341USB1"]

        result = serial_utils.scan_serial_ports()

        self.assertEqual(len(result), 2)
        self.assertTrue(all("CH341" in r["description"] for r in result))

    @patch("serial_utils.serial.tools.list_ports.comports")
    @patch("serial_utils.glob.glob")
    def test_scan_ports_no_duplicates(self, mock_glob, mock_comports):
        """测试不会重复添加端口"""
        mock_port = Mock()
        mock_port.device = "/dev/ttyCH341USB0"
        mock_port.description = "USB Serial"
        mock_comports.return_value = [mock_port]
        mock_glob.return_value = ["/dev/ttyCH341USB0"]  # 同一设备

        result = serial_utils.scan_serial_ports()

        # 应该只有一个
        self.assertEqual(len(result), 1)

    @patch("serial_utils.serial.tools.list_ports.comports")
    @patch("serial_utils.glob.glob")
    def test_scan_ports_empty(self, mock_glob, mock_comports):
        """测试无可用端口"""
        mock_comports.return_value = []
        mock_glob.return_value = []

        result = serial_utils.scan_serial_ports()

        self.assertEqual(result, [])


class TestSerialOpen(unittest.TestCase):
    """serial_open 测试"""

    @patch("serial_utils.serial.Serial")
    def test_open_success(self, mock_serial):
        """测试成功打开端口"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", 115200, 1)

        self.assertEqual(ser, mock_ser)
        self.assertIsNone(error)
        mock_serial.assert_called_with("/dev/ttyUSB0", 115200, timeout=1)

    @patch("serial_utils.serial.Serial")
    def test_open_not_opened(self, mock_serial):
        """测试端口未能打开"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = False
        mock_serial.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("Error opening", error)

    @patch("serial_utils.serial.Serial")
    def test_open_serial_exception(self, mock_serial):
        """测试串口异常"""
        import serial

        mock_serial.side_effect = serial.SerialException("Port busy")

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("Serial error", error)

    @patch("serial_utils.serial.Serial")
    def test_open_generic_exception(self, mock_serial):
        """测试通用异常"""
        mock_serial.side_effect = Exception("Unknown error")

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("Error", error)


class TestSerialWrite(unittest.TestCase):
    """serial_write 测试"""

    def test_write_no_serial(self):
        """测试无串口对象"""
        device = Mock()
        device.ser = None

        result, error = serial_utils.serial_write(device, "test")

        self.assertIsNone(result)
        self.assertIn("not opened", error)

    def test_write_no_worker(self):
        """测试无 worker"""
        device = Mock()
        device.ser = Mock()
        device.worker = None

        result, error = serial_utils.serial_write(device, "test")

        self.assertIsNone(result)
        self.assertIn("worker not started", error)

    def test_write_worker_not_running(self):
        """测试 worker 未运行"""
        device = Mock()
        device.ser = Mock()
        device.worker = Mock()
        device.worker.is_running.return_value = False

        result, error = serial_utils.serial_write(device, "test")

        self.assertIsNone(result)
        self.assertIn("worker not started", error)

    def test_write_timeout(self):
        """测试写入超时"""
        device = Mock()
        device.ser = Mock()
        device.worker = Mock()
        device.worker.is_running.return_value = True
        device.worker.enqueue_and_wait.return_value = False

        result, error = serial_utils.serial_write(device, "test", timeout=1.0)

        self.assertIsNone(result)
        self.assertIn("timeout", error.lower())

    def test_write_success(self):
        """测试写入成功"""
        device = Mock()
        device.ser = Mock()
        device.worker = Mock()
        device.worker.is_running.return_value = True
        device.worker.enqueue_and_wait.return_value = True

        result, error = serial_utils.serial_write(device, "test")

        self.assertEqual(result, [])
        self.assertIsNone(error)


class TestSerialWriteAsync(unittest.TestCase):
    """serial_write_async 测试"""

    def test_write_async_no_worker(self):
        """测试无 worker 时异步写入"""
        device = Mock()
        device.worker = None

        # 不应该抛出异常
        serial_utils.serial_write_async(device, "test")

    def test_write_async_with_worker(self):
        """测试有 worker 时异步写入"""
        device = Mock()
        device.worker = Mock()

        serial_utils.serial_write_async(device, "test command")

        device.worker.enqueue.assert_called_with("write", "test command")


class TestSerialWriteDirect(unittest.TestCase):
    """serial_write_direct 测试"""

    def test_write_direct_no_serial(self):
        """测试无串口时直接写入"""
        device = Mock()
        device.ser = None

        # 不应该抛出异常
        serial_utils.serial_write_direct(device, "test")

    def test_write_direct_not_open(self):
        """测试串口未打开时直接写入"""
        device = Mock()
        device.ser = Mock()
        device.ser.isOpen.return_value = False

        # 不应该抛出异常
        serial_utils.serial_write_direct(device, "test")

        device.ser.write.assert_not_called()

    def test_write_direct_success(self):
        """测试直接写入成功"""
        device = Mock()
        device.ser = Mock()
        device.ser.isOpen.return_value = True

        serial_utils.serial_write_direct(device, "test")

        device.ser.write.assert_called_once()
        device.ser.flush.assert_called_once()

    def test_write_direct_exception(self):
        """测试直接写入异常"""
        device = Mock()
        device.ser = Mock()
        device.ser.isOpen.return_value = True
        device.ser.write.side_effect = Exception("Write error")

        # 不应该抛出异常
        serial_utils.serial_write_direct(device, "test")


class TestDeviceWorkerFunctions(unittest.TestCase):
    """设备 Worker 相关函数测试"""

    @patch("serial_utils.start_worker")
    def test_start_device_worker(self, mock_start):
        """测试启动设备 worker"""
        device = Mock()
        mock_start.return_value = True

        result = serial_utils.start_device_worker(device)

        mock_start.assert_called_with(device)
        self.assertTrue(result)

    @patch("serial_utils.stop_worker")
    def test_stop_device_worker(self, mock_stop):
        """测试停止设备 worker"""
        device = Mock()

        serial_utils.stop_device_worker(device)

        mock_stop.assert_called_with(device)

    def test_run_in_device_worker_no_worker(self):
        """测试无 worker 时运行函数"""
        device = Mock()
        device.worker = None

        result = serial_utils.run_in_device_worker(device, lambda: None)

        self.assertFalse(result)

    def test_run_in_device_worker_with_worker(self):
        """测试有 worker 时运行函数"""
        device = Mock()
        device.worker = Mock()
        device.worker.run_in_worker.return_value = True

        func = Mock()
        result = serial_utils.run_in_device_worker(device, func, timeout=1.0)

        device.worker.run_in_worker.assert_called_with(func, 1.0)
        self.assertTrue(result)

    def test_get_device_timer_manager_no_worker(self):
        """测试无 worker 时获取定时器管理器"""
        device = Mock()
        device.worker = None

        result = serial_utils.get_device_timer_manager(device)

        self.assertIsNone(result)

    def test_get_device_timer_manager_with_worker(self):
        """测试有 worker 时获取定时器管理器"""
        device = Mock()
        device.worker = Mock()
        mock_timer_manager = Mock()
        device.worker.get_timer_manager.return_value = mock_timer_manager

        result = serial_utils.get_device_timer_manager(device)

        self.assertEqual(result, mock_timer_manager)


if __name__ == "__main__":
    unittest.main(verbosity=2)

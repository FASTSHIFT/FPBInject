#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serial Utils module tests
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import serial as serial_utils  # noqa: E402


class TestScanSerialPorts(unittest.TestCase):
    """scan_serial_ports test"""

    @patch("utils.serial.serial.tools.list_ports.comports")
    @patch("utils.serial.glob.glob")
    def test_scan_ports_basic(self, mock_glob, mock_comports):
        """Test scanning basic ports"""
        mock_port = Mock()
        mock_port.device = "/dev/ttyUSB0"
        mock_port.description = "USB Serial"
        mock_comports.return_value = [mock_port]
        mock_glob.return_value = []

        result = serial_utils.scan_serial_ports()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["device"], "/dev/ttyUSB0")
        self.assertEqual(result[0]["description"], "USB Serial")

    @patch("utils.serial.serial.tools.list_ports.comports")
    @patch("utils.serial.glob.glob")
    def test_scan_ports_with_ch341(self, mock_glob, mock_comports):
        """Test scanning ports containing CH341"""
        mock_comports.return_value = []
        mock_glob.return_value = ["/dev/ttyCH341USB0", "/dev/ttyCH341USB1"]

        result = serial_utils.scan_serial_ports()

        self.assertEqual(len(result), 2)
        self.assertTrue(all("CH341" in r["description"] for r in result))

    @patch("utils.serial.serial.tools.list_ports.comports")
    @patch("utils.serial.glob.glob")
    def test_scan_ports_no_duplicates(self, mock_glob, mock_comports):
        """Test no duplicate ports added"""
        mock_port = Mock()
        mock_port.device = "/dev/ttyCH341USB0"
        mock_port.description = "USB Serial"
        mock_comports.return_value = [mock_port]
        mock_glob.return_value = ["/dev/ttyCH341USB0"]  # Same device

        result = serial_utils.scan_serial_ports()

        # Should have only one
        self.assertEqual(len(result), 1)

    @patch("utils.serial.serial.tools.list_ports.comports")
    @patch("utils.serial.glob.glob")
    def test_scan_ports_empty(self, mock_glob, mock_comports):
        """Test no available ports"""
        mock_comports.return_value = []
        mock_glob.return_value = []

        result = serial_utils.scan_serial_ports()

        self.assertEqual(result, [])

    @patch("utils.serial.serial.tools.list_ports.comports")
    @patch("utils.serial.glob.glob")
    def test_scan_ports_filters_ttyS_devices(self, mock_glob, mock_comports):
        """Test that /dev/ttyS* devices are filtered out"""
        mock_port_usb = Mock()
        mock_port_usb.device = "/dev/ttyUSB0"
        mock_port_usb.description = "USB Serial"

        mock_port_ttyS0 = Mock()
        mock_port_ttyS0.device = "/dev/ttyS0"
        mock_port_ttyS0.description = "Serial Port 0"

        mock_port_ttyS1 = Mock()
        mock_port_ttyS1.device = "/dev/ttyS1"
        mock_port_ttyS1.description = "Serial Port 1"

        mock_port_acm = Mock()
        mock_port_acm.device = "/dev/ttyACM0"
        mock_port_acm.description = "ACM Device"

        mock_comports.return_value = [
            mock_port_usb,
            mock_port_ttyS0,
            mock_port_ttyS1,
            mock_port_acm,
        ]
        mock_glob.return_value = []

        result = serial_utils.scan_serial_ports()

        # Should only have USB and ACM devices, not ttyS*
        self.assertEqual(len(result), 2)
        devices = [r["device"] for r in result]
        self.assertIn("/dev/ttyUSB0", devices)
        self.assertIn("/dev/ttyACM0", devices)
        self.assertNotIn("/dev/ttyS0", devices)
        self.assertNotIn("/dev/ttyS1", devices)

    @patch("utils.serial.serial.tools.list_ports.comports")
    @patch("utils.serial.glob.glob")
    def test_scan_ports_only_ttyS_returns_empty(self, mock_glob, mock_comports):
        """Test that when only /dev/ttyS* devices exist, result is empty"""
        mock_port_ttyS0 = Mock()
        mock_port_ttyS0.device = "/dev/ttyS0"
        mock_port_ttyS0.description = "Serial Port 0"

        mock_port_ttyS1 = Mock()
        mock_port_ttyS1.device = "/dev/ttyS1"
        mock_port_ttyS1.description = "Serial Port 1"

        mock_comports.return_value = [mock_port_ttyS0, mock_port_ttyS1]
        mock_glob.return_value = []

        result = serial_utils.scan_serial_ports()

        self.assertEqual(result, [])


class TestSerialOpen(unittest.TestCase):
    """serial_open test"""

    @patch("utils.serial.serial.Serial")
    def test_open_success(self, mock_serial):
        """Test successfully opening port"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", 115200, 1)

        self.assertEqual(ser, mock_ser)
        self.assertIsNone(error)
        mock_serial.assert_called_with(
            "/dev/ttyUSB0", 115200, timeout=1, write_timeout=1
        )

    @patch("utils.serial.serial.Serial")
    def test_open_not_opened(self, mock_serial):
        """Test port failed to open"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = False
        mock_serial.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("Error opening", error)

    @patch("utils.serial.serial.Serial")
    def test_open_serial_exception(self, mock_serial):
        """Test serial exception"""
        import serial

        mock_serial.side_effect = serial.SerialException("Port busy")

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("Serial error", error)

    @patch("utils.serial.serial.Serial")
    def test_open_generic_exception(self, mock_serial):
        """Test generic exception"""
        mock_serial.side_effect = Exception("Unknown error")

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("Error", error)


class TestSerialWrite(unittest.TestCase):
    """serial_write test"""

    def test_write_no_serial(self):
        """Test no serial object"""
        device = Mock()
        device.ser = None

        result, error = serial_utils.serial_write(device, "test")

        self.assertIsNone(result)
        self.assertIn("not opened", error)

    def test_write_no_worker(self):
        """Test no worker"""
        device = Mock()
        device.ser = Mock()
        device.worker = None

        result, error = serial_utils.serial_write(device, "test")

        self.assertIsNone(result)
        self.assertIn("worker not started", error)

    def test_write_worker_not_running(self):
        """Test worker not running"""
        device = Mock()
        device.ser = Mock()
        device.worker = Mock()
        device.worker.is_running.return_value = False

        result, error = serial_utils.serial_write(device, "test")

        self.assertIsNone(result)
        self.assertIn("worker not started", error)

    def test_write_timeout(self):
        """Test write timeout"""
        device = Mock()
        device.ser = Mock()
        device.worker = Mock()
        device.worker.is_running.return_value = True
        device.worker.enqueue_and_wait.return_value = False

        result, error = serial_utils.serial_write(device, "test", timeout=1.0)

        self.assertIsNone(result)
        self.assertIn("timeout", error.lower())

    def test_write_success(self):
        """Test write success"""
        device = Mock()
        device.ser = Mock()
        device.worker = Mock()
        device.worker.is_running.return_value = True
        device.worker.enqueue_and_wait.return_value = True

        result, error = serial_utils.serial_write(device, "test")

        self.assertEqual(result, [])
        self.assertIsNone(error)


class TestSerialWriteAsync(unittest.TestCase):
    """serial_write_async test"""

    def test_write_async_no_worker(self):
        """Test async write without worker"""
        device = Mock()
        device.worker = None

        # Should not raise exception
        serial_utils.serial_write_async(device, "test")

    def test_write_async_with_worker(self):
        """Test async write with worker"""
        device = Mock()
        device.worker = Mock()

        serial_utils.serial_write_async(device, "test command")

        device.worker.enqueue.assert_called_with("write", "test command")


class TestSerialWriteDirect(unittest.TestCase):
    """serial_write_direct test"""

    def test_write_direct_no_serial(self):
        """Test direct write without serial"""
        device = Mock()
        device.ser = None

        # Should not raise exception
        serial_utils.serial_write_direct(device, "test")

    def test_write_direct_not_open(self):
        """Test direct write when serial not open"""
        device = Mock()
        device.ser = Mock()
        device.ser.isOpen.return_value = False

        # Should not raise exception
        serial_utils.serial_write_direct(device, "test")

        device.ser.write.assert_not_called()

    def test_write_direct_success(self):
        """Test direct write success"""
        device = Mock()
        device.ser = Mock()
        device.ser.isOpen.return_value = True

        serial_utils.serial_write_direct(device, "test")

        device.ser.write.assert_called_once()
        device.ser.flush.assert_called_once()

    def test_write_direct_exception(self):
        """Test direct write exception"""
        device = Mock()
        device.ser = Mock()
        device.ser.isOpen.return_value = True
        device.ser.write.side_effect = Exception("Write error")

        # Should not raise exception
        serial_utils.serial_write_direct(device, "test")


class TestDeviceWorkerFunctions(unittest.TestCase):
    """Device Worker related functions test"""

    @patch("utils.serial.start_worker")
    def test_start_device_worker(self, mock_start):
        """Test starting device worker"""
        device = Mock()
        mock_start.return_value = True

        result = serial_utils.start_device_worker(device)

        mock_start.assert_called_with(device)
        self.assertTrue(result)

    @patch("utils.serial.stop_worker")
    def test_stop_device_worker(self, mock_stop):
        """Test stopping device worker"""
        device = Mock()

        serial_utils.stop_device_worker(device)

        mock_stop.assert_called_with(device)

    def test_run_in_device_worker_no_worker(self):
        """Test running function without worker"""
        device = Mock()
        device.worker = None

        result = serial_utils.run_in_device_worker(device, lambda: None)

        self.assertFalse(result)

    def test_run_in_device_worker_with_worker(self):
        """Test running function with worker"""
        device = Mock()
        device.worker = Mock()
        device.worker.run_in_worker.return_value = True

        func = Mock()
        result = serial_utils.run_in_device_worker(device, func, timeout=1.0)

        device.worker.run_in_worker.assert_called_with(func, 1.0)
        self.assertTrue(result)

    def test_get_device_timer_manager_no_worker(self):
        """Test getting timer manager without worker"""
        device = Mock()
        device.worker = None

        result = serial_utils.get_device_timer_manager(device)

        self.assertIsNone(result)

    def test_get_device_timer_manager_with_worker(self):
        """Test getting timer manager with worker"""
        device = Mock()
        device.worker = Mock()
        mock_timer_manager = Mock()
        device.worker.get_timer_manager.return_value = mock_timer_manager

        result = serial_utils.get_device_timer_manager(device)

        self.assertEqual(result, mock_timer_manager)


if __name__ == "__main__":
    unittest.main(verbosity=2)

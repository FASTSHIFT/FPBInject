#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serial Utils module tests
"""

import os
import sys
import threading
import unittest
from unittest.mock import Mock, patch

import serial

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.utils import serial as serial_utils  # noqa: E402


class TestScanSerialPorts(unittest.TestCase):
    """scan_serial_ports test"""

    @patch("fpbinject.utils.serial.serial.tools.list_ports.comports")
    @patch("fpbinject.utils.serial.glob.glob")
    def test_scan_ports_basic(self, mock_glob, mock_comports):
        """Test scanning basic ports"""
        mock_port = Mock()
        mock_port.device = "/dev/ttyUSB0"
        mock_port.description = "USB Serial"
        mock_comports.return_value = [mock_port]
        mock_glob.return_value = []

        with patch("fpbinject.utils.serial.os.access", return_value=True):
            result = serial_utils.scan_serial_ports()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["device"], "/dev/ttyUSB0")
        self.assertEqual(result[0]["description"], "USB Serial")
        self.assertTrue(result[0]["accessible"])

    @patch("fpbinject.utils.serial.serial.tools.list_ports.comports")
    @patch("fpbinject.utils.serial.glob.glob")
    def test_scan_ports_with_ch341(self, mock_glob, mock_comports):
        """Test scanning ports containing CH341"""
        mock_comports.return_value = []
        mock_glob.return_value = ["/dev/ttyCH341USB0", "/dev/ttyCH341USB1"]

        with patch("fpbinject.utils.serial.os.access", return_value=True):
            result = serial_utils.scan_serial_ports()

        self.assertEqual(len(result), 2)
        self.assertTrue(all("CH341" in r["description"] for r in result))

    @patch("fpbinject.utils.serial.serial.tools.list_ports.comports")
    @patch("fpbinject.utils.serial.glob.glob")
    def test_scan_ports_no_duplicates(self, mock_glob, mock_comports):
        """Test no duplicate ports added"""
        mock_port = Mock()
        mock_port.device = "/dev/ttyCH341USB0"
        mock_port.description = "USB Serial"
        mock_comports.return_value = [mock_port]
        mock_glob.return_value = ["/dev/ttyCH341USB0"]  # Same device

        with patch("fpbinject.utils.serial.os.access", return_value=True):
            result = serial_utils.scan_serial_ports()

        # Should have only one
        self.assertEqual(len(result), 1)

    @patch("fpbinject.utils.serial.serial.tools.list_ports.comports")
    @patch("fpbinject.utils.serial.glob.glob")
    def test_scan_ports_empty(self, mock_glob, mock_comports):
        """Test no available ports"""
        mock_comports.return_value = []
        mock_glob.return_value = []

        result = serial_utils.scan_serial_ports()

        self.assertEqual(result, [])

    @patch("fpbinject.utils.serial.serial.tools.list_ports.comports")
    @patch("fpbinject.utils.serial.glob.glob")
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

        with patch("fpbinject.utils.serial.os.access", return_value=True):
            result = serial_utils.scan_serial_ports()

        # Should only have USB and ACM devices, not ttyS*
        self.assertEqual(len(result), 2)
        devices = [r["device"] for r in result]
        self.assertIn("/dev/ttyUSB0", devices)
        self.assertIn("/dev/ttyACM0", devices)
        self.assertNotIn("/dev/ttyS0", devices)
        self.assertNotIn("/dev/ttyS1", devices)

    @patch("fpbinject.utils.serial.serial.tools.list_ports.comports")
    @patch("fpbinject.utils.serial.glob.glob")
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

    @patch("fpbinject.utils.serial.serial.tools.list_ports.comports")
    @patch("fpbinject.utils.serial.glob.glob")
    def test_scan_ports_accessible_false(self, mock_glob, mock_comports):
        """Test that inaccessible ports have accessible=False"""
        mock_port = Mock()
        mock_port.device = "/dev/ttyACM0"
        mock_port.description = "ACM Device"
        mock_comports.return_value = [mock_port]
        mock_glob.return_value = []

        with patch("fpbinject.utils.serial.os.access", return_value=False):
            result = serial_utils.scan_serial_ports()

        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["accessible"])


class TestClassifySerialError(unittest.TestCase):
    """_classify_serial_error test"""

    def test_permission_denied(self):
        e = serial.SerialException("[Errno 13] Permission denied: '/dev/ttyACM0'")
        self.assertEqual(serial_utils._classify_serial_error(e), "permission_denied")

    def test_device_not_found(self):
        e = serial.SerialException("[Errno 2] No such file or directory")
        self.assertEqual(serial_utils._classify_serial_error(e), "device_not_found")

    def test_device_busy(self):
        e = serial.SerialException("[Errno 16] Device or resource busy")
        self.assertEqual(serial_utils._classify_serial_error(e), "device_busy")

    def test_generic_serial_error(self):
        e = serial.SerialException("some other error")
        self.assertEqual(serial_utils._classify_serial_error(e), "serial_error")

    def test_file_not_found_error_string(self):
        e = Exception("FileNotFoundError: /dev/ttyACM0")
        self.assertEqual(serial_utils._classify_serial_error(e), "device_not_found")


class TestSerialOpen(unittest.TestCase):
    """serial_open test"""

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_success(self, mock_serial_cls):
        """Test successfully opening port"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", 115200, 1)

        self.assertIsInstance(ser, serial_utils.ThreadCheckedSerial)
        self.assertIsNone(error)
        # Deferred open: Serial() called with no args, then attributes set
        mock_serial_cls.assert_called_once_with()
        self.assertEqual(mock_ser.port, "/dev/ttyUSB0")
        self.assertEqual(mock_ser.baudrate, 115200)
        self.assertEqual(mock_ser.bytesize, 8)
        mock_ser.open.assert_called_once()

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_not_opened(self, mock_serial_cls):
        """Test port failed to open"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = False
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("Error opening", error)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_serial_exception(self, mock_serial_cls):
        """Test serial exception includes error code prefix"""
        mock_ser = Mock()
        mock_ser.open.side_effect = serial.SerialException("Port busy")
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("[serial_error]", error)
        self.assertIn("Port busy", error)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_permission_denied(self, mock_serial_cls):
        """Test permission denied error code"""
        mock_ser = Mock()
        mock_ser.open.side_effect = serial.SerialException(
            "[Errno 13] could not open port /dev/ttyACM0: "
            "[Errno 13] Permission denied: '/dev/ttyACM0'"
        )
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyACM0")

        self.assertIsNone(ser)
        self.assertIn("[permission_denied]", error)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_device_not_found(self, mock_serial_cls):
        """Test device not found error code"""
        mock_ser = Mock()
        mock_ser.open.side_effect = serial.SerialException(
            "[Errno 2] could not open port /dev/ttyACM0: "
            "[Errno 2] No such file or directory: '/dev/ttyACM0'"
        )
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyACM0")

        self.assertIsNone(ser)
        self.assertIn("[device_not_found]", error)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_device_busy(self, mock_serial_cls):
        """Test device busy error code"""
        mock_ser = Mock()
        mock_ser.open.side_effect = serial.SerialException(
            "[Errno 16] Device or resource busy: '/dev/ttyACM0'"
        )
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyACM0")

        self.assertIsNone(ser)
        self.assertIn("[device_busy]", error)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_generic_exception(self, mock_serial_cls):
        """Test generic exception includes error code prefix"""
        mock_ser = Mock()
        mock_ser.open.side_effect = Exception("Unknown error")
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(ser)
        self.assertIn("[unknown_error]", error)
        self.assertIn("Unknown error", error)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_with_custom_serial_params(self, mock_serial_cls):
        """Test opening port with custom data_bits, parity, stop_bits, flow_control"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open(
            "/dev/ttyUSB0",
            9600,
            2.0,
            data_bits=7,
            parity="even",
            stop_bits=2,
            flow_control="rtscts",
        )

        self.assertIsInstance(ser, serial_utils.ThreadCheckedSerial)
        self.assertIsNone(error)
        self.assertEqual(mock_ser.port, "/dev/ttyUSB0")
        self.assertEqual(mock_ser.baudrate, 9600)
        self.assertEqual(mock_ser.bytesize, 7)
        self.assertEqual(mock_ser.parity, serial.PARITY_EVEN)
        self.assertEqual(mock_ser.stopbits, serial.STOPBITS_TWO)
        self.assertTrue(mock_ser.rtscts)
        self.assertFalse(mock_ser.xonxoff)
        mock_ser.open.assert_called_once()

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_with_xonxoff_flow(self, mock_serial_cls):
        """Test opening port with XON/XOFF flow control"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", flow_control="xonxoff")

        self.assertIsInstance(ser, serial_utils.ThreadCheckedSerial)
        self.assertIsNone(error)
        self.assertTrue(mock_ser.xonxoff)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_with_odd_parity(self, mock_serial_cls):
        """Test opening port with odd parity"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", parity="odd")

        self.assertIsNone(error)
        self.assertEqual(mock_ser.parity, serial.PARITY_ODD)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_with_unknown_parity_defaults_to_none(self, mock_serial_cls):
        """Test opening port with unknown parity falls back to PARITY_NONE"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", parity="invalid")

        self.assertIsNone(error)
        self.assertEqual(mock_ser.parity, serial.PARITY_NONE)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_default_dtr_rts_off(self, mock_serial_cls):
        """Test that DTR and RTS default to False (inactive) on connect"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0")

        self.assertIsNone(error)
        self.assertFalse(mock_ser.dtr)
        self.assertFalse(mock_ser.rts)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_with_dtr_on(self, mock_serial_cls):
        """Test opening port with DTR asserted"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", dtr=True)

        self.assertIsNone(error)
        self.assertTrue(mock_ser.dtr)
        self.assertFalse(mock_ser.rts)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_with_rts_on(self, mock_serial_cls):
        """Test opening port with RTS asserted"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", rts=True)

        self.assertIsNone(error)
        self.assertFalse(mock_ser.dtr)
        self.assertTrue(mock_ser.rts)

    @patch("fpbinject.utils.serial.serial.Serial")
    def test_open_with_both_dtr_rts_on(self, mock_serial_cls):
        """Test opening port with both DTR and RTS asserted"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        mock_serial_cls.return_value = mock_ser

        ser, error = serial_utils.serial_open("/dev/ttyUSB0", dtr=True, rts=True)

        self.assertIsNone(error)
        self.assertTrue(mock_ser.dtr)
        self.assertTrue(mock_ser.rts)


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

    @patch("fpbinject.utils.serial.start_worker")
    def test_start_device_worker(self, mock_start):
        """Test starting device worker"""
        device = Mock()
        mock_start.return_value = True

        result = serial_utils.start_device_worker(device)

        mock_start.assert_called_with(device)
        self.assertTrue(result)

    @patch("fpbinject.utils.serial.stop_worker")
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


class TestThreadCheckedSerial(unittest.TestCase):
    """ThreadCheckedSerial thread safety tests"""

    def test_auto_bind_on_first_io(self):
        """Test that owner thread is auto-bound on first I/O call"""
        mock_ser = Mock()
        mock_ser.in_waiting = 5
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)

        self.assertIsNone(wrapped._owner_thread)
        _ = wrapped.in_waiting
        self.assertEqual(wrapped._owner_thread, threading.current_thread().ident)

    def test_explicit_bind_thread(self):
        """Test explicit bind_thread sets owner"""
        mock_ser = Mock()
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)

        wrapped.bind_thread()
        self.assertEqual(wrapped._owner_thread, threading.current_thread().ident)
        self.assertEqual(wrapped._owner_thread_name, threading.current_thread().name)

    def test_same_thread_io_allowed(self):
        """Test I/O from owner thread succeeds"""
        mock_ser = Mock()
        mock_ser.in_waiting = 0
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)
        wrapped.bind_thread()

        # These should not raise
        _ = wrapped.in_waiting
        wrapped.write(b"hello")
        wrapped.read(5)
        wrapped.flush()
        wrapped.reset_input_buffer()

    def test_cross_thread_read_raises(self):
        """Test read from non-owner thread raises SerialThreadViolation"""
        mock_ser = Mock()
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)
        wrapped.bind_thread()  # Bind to current (main) thread

        error = [None]

        def other_thread():
            try:
                wrapped.read(1)
            except serial_utils.SerialThreadViolation as e:
                error[0] = e

        t = threading.Thread(target=other_thread)
        t.start()
        t.join(timeout=2)

        self.assertIsNotNone(error[0])
        self.assertIn("Serial.read()", str(error[0]))

    def test_cross_thread_write_raises(self):
        """Test write from non-owner thread raises SerialThreadViolation"""
        mock_ser = Mock()
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)
        wrapped.bind_thread()

        error = [None]

        def other_thread():
            try:
                wrapped.write(b"data")
            except serial_utils.SerialThreadViolation as e:
                error[0] = e

        t = threading.Thread(target=other_thread)
        t.start()
        t.join(timeout=2)

        self.assertIsNotNone(error[0])
        self.assertIn("Serial.write()", str(error[0]))

    def test_cross_thread_in_waiting_raises(self):
        """Test in_waiting from non-owner thread raises SerialThreadViolation"""
        mock_ser = Mock()
        mock_ser.in_waiting = 10
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)
        wrapped.bind_thread()

        error = [None]

        def other_thread():
            try:
                _ = wrapped.in_waiting
            except serial_utils.SerialThreadViolation as e:
                error[0] = e

        t = threading.Thread(target=other_thread)
        t.start()
        t.join(timeout=2)

        self.assertIsNotNone(error[0])
        self.assertIn("Serial.in_waiting()", str(error[0]))

    def test_cross_thread_flush_raises(self):
        """Test flush from non-owner thread raises SerialThreadViolation"""
        mock_ser = Mock()
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)
        wrapped.bind_thread()

        error = [None]

        def other_thread():
            try:
                wrapped.flush()
            except serial_utils.SerialThreadViolation as e:
                error[0] = e

        t = threading.Thread(target=other_thread)
        t.start()
        t.join(timeout=2)

        self.assertIsNotNone(error[0])
        self.assertIn("Serial.flush()", str(error[0]))

    def test_lifecycle_methods_allowed_cross_thread(self):
        """Test isOpen/close are allowed from any thread"""
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)
        wrapped.bind_thread()

        results = []

        def other_thread():
            try:
                results.append(wrapped.isOpen())
                wrapped.close()
                results.append(True)
            except serial_utils.SerialThreadViolation:
                results.append(False)

        t = threading.Thread(target=other_thread)
        t.start()
        t.join(timeout=2)

        self.assertEqual(results, [True, True])

    def test_error_message_contains_thread_info(self):
        """Test error message includes both thread names and ids"""
        mock_ser = Mock()
        wrapped = serial_utils.ThreadCheckedSerial(mock_ser)
        wrapped.bind_thread()

        error = [None]

        def other_thread():
            try:
                wrapped.write(b"x")
            except serial_utils.SerialThreadViolation as e:
                error[0] = str(e)

        t = threading.Thread(target=other_thread, name="test-offender")
        t.start()
        t.join(timeout=2)

        self.assertIn("test-offender", error[0])
        self.assertIn(threading.current_thread().name, error[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)

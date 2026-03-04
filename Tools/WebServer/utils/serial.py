#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Serial communication utilities for FPBInject Web Server.

Provides serial port operations with multi-device support.
"""

import glob
import logging
import threading

import serial
import serial.tools.list_ports

from services.device_worker import start_worker, stop_worker

logger = logging.getLogger(__name__)


class SerialThreadViolation(RuntimeError):
    """Raised when serial port is accessed from a non-owner thread."""

    pass


class ThreadCheckedSerial:
    """Wrapper around serial.Serial that enforces single-thread I/O access.

    All I/O operations (read, write, flush, etc.) must be called from the
    owner thread. The owner thread is auto-bound on the first I/O call.
    Lifecycle methods (isOpen, close) are allowed from any thread.
    """

    # Methods that perform I/O and must be thread-checked
    _IO_METHODS = frozenset(
        {
            "read",
            "write",
            "flush",
            "reset_input_buffer",
            "reset_output_buffer",
            "readline",
            "readlines",
            "readall",
        }
    )

    def __init__(self, ser):
        self._ser = ser
        self._owner_thread = None
        self._owner_thread_name = None

    def bind_thread(self):
        """Explicitly bind the current thread as the owner."""
        self._owner_thread = threading.current_thread().ident
        self._owner_thread_name = threading.current_thread().name
        logger.debug(f"Serial port bound to thread: {self._owner_thread_name}")

    def _check_thread(self, method_name):
        """Check that the current thread is the owner thread."""
        current = threading.current_thread()
        if self._owner_thread is None:
            # Auto-bind on first I/O call
            self._owner_thread = current.ident
            self._owner_thread_name = current.name
            logger.debug(f"Serial port auto-bound to thread: {self._owner_thread_name}")
            return

        if current.ident != self._owner_thread:
            raise SerialThreadViolation(
                f"Serial.{method_name}() called from thread "
                f"'{current.name}' (id={current.ident}), "
                f"but owner is '{self._owner_thread_name}' "
                f"(id={self._owner_thread})"
            )

    @property
    def in_waiting(self):
        self._check_thread("in_waiting")
        return self._ser.in_waiting

    def __getattr__(self, name):
        # Thread-checked I/O methods
        if name in self._IO_METHODS:
            self._check_thread(name)
            return getattr(self._ser, name)

        # All other attributes pass through directly
        return getattr(self._ser, name)


def scan_serial_ports():
    """Scan for available serial ports."""
    ports = serial.tools.list_ports.comports()
    # Filter out /dev/ttyS* devices (legacy serial ports, usually virtual or unused)
    result = [
        {"device": port.device, "description": port.description}
        for port in ports
        if not port.device.startswith("/dev/ttyS")
    ]

    # Also scan for CH341 USB serial devices which may not be detected by pyserial
    ch341_devices = glob.glob("/dev/ttyCH341USB*")
    existing_devices = {item["device"] for item in result}
    for dev in ch341_devices:
        if dev not in existing_devices:
            result.append({"device": dev, "description": "CH341 USB Serial"})

    return result


def serial_open(
    port,
    baudrate=115200,
    timeout=2.0,
    data_bits=8,
    parity="none",
    stop_bits=1,
    flow_control="none",
):
    """Open a serial port.

    Args:
        port: Serial port path
        baudrate: Baud rate (default: 115200)
        timeout: Read/write timeout in seconds (default: 2.0)
        data_bits: Data bits, 5/6/7/8 (default: 8)
        parity: Parity, none/even/odd/mark/space (default: none)
        stop_bits: Stop bits, 1/1.5/2 (default: 1)
        flow_control: Flow control, none/rtscts/dsrdtr/xonxoff (default: none)
    """
    PARITY_MAP = {
        "none": serial.PARITY_NONE,
        "even": serial.PARITY_EVEN,
        "odd": serial.PARITY_ODD,
        "mark": serial.PARITY_MARK,
        "space": serial.PARITY_SPACE,
    }
    STOPBITS_MAP = {
        1: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2: serial.STOPBITS_TWO,
    }
    try:
        ser = serial.Serial(
            port,
            baudrate,
            bytesize=int(data_bits),
            parity=PARITY_MAP.get(parity, serial.PARITY_NONE),
            stopbits=STOPBITS_MAP.get(float(stop_bits), serial.STOPBITS_ONE),
            xonxoff=(flow_control == "xonxoff"),
            rtscts=(flow_control == "rtscts"),
            dsrdtr=(flow_control == "dsrdtr"),
            timeout=timeout,
            write_timeout=timeout,
        )
        if not ser.isOpen():
            return None, f"Error opening serial port {port}"
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        import time

        time.sleep(0.1)
        return ThreadCheckedSerial(ser), None
    except serial.SerialException as e:
        return None, f"Serial error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def serial_write(device, command, timeout=2.0):
    """Queue command for serial write and wait for completion."""
    if device.ser is None:
        return None, "Serial port not opened"

    worker = device.worker
    if worker is None or not worker.is_running():
        return None, "Device worker not started"

    if not worker.enqueue_and_wait("write", command, timeout):
        return None, "Command timeout"

    return [], None


def serial_write_async(device, command):
    """Queue a command for async serial write (fire-and-forget)."""
    worker = device.worker
    if worker is not None:
        worker.enqueue("write", command)


def serial_write_direct(device, command):
    """
    Direct serial write (call from worker thread only).

    Args:
        device: DeviceState object
        command: Command string to send
    """
    logger = logging.getLogger(__name__)
    ser = device.ser
    if ser is None or not ser.isOpen():
        return

    try:
        ser.write(command.encode())
        ser.flush()
    except Exception as e:
        logger.warning(f"Serial write error: {e}")


def start_device_worker(device):
    """Start the worker thread for a device."""
    return start_worker(device)


def stop_device_worker(device):
    """Stop the worker thread for a device."""
    stop_worker(device)


def run_in_device_worker(device, func, timeout=2.0):
    """Run a function in the device's worker thread and wait for completion."""
    worker = device.worker
    if worker is None:
        return False
    return worker.run_in_worker(func, timeout)


def get_device_timer_manager(device):
    """Get the timer manager for a device."""
    worker = device.worker
    if worker is None:
        return None
    return worker.get_timer_manager()

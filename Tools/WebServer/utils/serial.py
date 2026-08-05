#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Serial communication utilities for FPBInject Web Server.

Provides serial port operations with multi-device support.
"""

import glob
import logging
import os
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
        # Optional tee sinks for full passthrough (e.g. virtual serial).
        # _tee_tx(bytes): host->device bytes actually written.
        # _tee_rx(bytes): device->host bytes actually read.
        self._tee_tx = None
        self._tee_rx = None

    def set_tee(self, tx=None, rx=None):
        """Install tee callbacks that observe all raw serial I/O.

        Both callbacks receive raw ``bytes`` and are invoked from the owner
        (worker) thread. They must not raise or block. Used to mirror the
        full byte stream — including FPB protocol traffic that bypasses the
        RX polling path — to the virtual serial passthrough.
        """
        self._tee_tx = tx
        self._tee_rx = rx

    def read(self, *args, **kwargs):
        self._check_thread("read")
        data = self._ser.read(*args, **kwargs)
        if data and self._tee_rx is not None:
            try:
                self._tee_rx(data)
            except Exception:
                pass
        return data

    def write(self, data, *args, **kwargs):
        self._check_thread("write")
        n = self._ser.write(data, *args, **kwargs)
        if data and self._tee_tx is not None:
            try:
                # Normalize to bytes for the sink.
                self._tee_tx(
                    data if isinstance(data, (bytes, bytearray)) else bytes(data)
                )
            except Exception:
                pass
        return n

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
    """Scan for available serial ports.

    Returns a list of dicts with keys: device, description, accessible.
    ``accessible`` is True when the current process has read+write permission.
    """
    ports = serial.tools.list_ports.comports()
    # Filter out /dev/ttyS* devices (legacy serial ports, usually virtual or unused)
    result = [
        {
            "device": port.device,
            "description": port.description,
            "accessible": os.access(port.device, os.R_OK | os.W_OK),
        }
        for port in ports
        if not port.device.startswith("/dev/ttyS")
    ]

    # Also scan for CH341 USB serial devices which may not be detected by pyserial
    ch341_devices = glob.glob("/dev/ttyCH341USB*")
    existing_devices = {item["device"] for item in result}
    for dev in ch341_devices:
        if dev not in existing_devices:
            result.append(
                {
                    "device": dev,
                    "description": "CH341 USB Serial",
                    "accessible": os.access(dev, os.R_OK | os.W_OK),
                }
            )

    return result


def _classify_serial_error(e):
    """Classify a serial exception into an error code.

    Returns:
        str: One of 'permission_denied', 'device_not_found', 'device_busy',
             or 'serial_error'.
    """
    msg = str(e)
    if "Permission denied" in msg or "Errno 13" in msg:
        return "permission_denied"
    if "No such file" in msg or "Errno 2" in msg or "FileNotFoundError" in msg:
        return "device_not_found"
    if "Device or resource busy" in msg or "Errno 16" in msg:
        return "device_busy"
    return "serial_error"


def serial_open(
    port,
    baudrate=115200,
    timeout=2.0,
    data_bits=8,
    parity="none",
    stop_bits=1,
    flow_control="none",
    dtr=False,
    rts=False,
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
        dtr: Initial DTR (Data Terminal Ready) state on connect (default: False)
        rts: Initial RTS (Request To Send) state on connect (default: False)

    Returns:
        tuple: (ThreadCheckedSerial, None) on success, or
               (None, error_string) on failure.
               The error_string is prefixed with a bracketed error code, e.g.
               ``[permission_denied] Serial error: ...``
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
        # Deferred open: set all parameters before opening the port.
        # Many USB-serial chips (CH343G, CH340, etc.) use RTS/DTR for
        # bootloader entry or reset. Setting RTS/DTR before open()
        # ensures the desired initial pin state.
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = baudrate
        ser.bytesize = int(data_bits)
        ser.parity = PARITY_MAP.get(parity, serial.PARITY_NONE)
        ser.stopbits = STOPBITS_MAP.get(float(stop_bits), serial.STOPBITS_ONE)
        ser.xonxoff = flow_control == "xonxoff"
        ser.rtscts = flow_control == "rtscts"
        ser.dsrdtr = flow_control == "dsrdtr"
        ser.timeout = timeout
        ser.write_timeout = timeout

        # Set initial RTS/DTR state before opening
        ser.dtr = bool(dtr)
        ser.rts = bool(rts)
        ser.open()

        if not ser.isOpen():
            return None, f"Error opening serial port {port}"
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        import time

        time.sleep(0.1)
        return ThreadCheckedSerial(ser), None
    except serial.SerialException as e:
        code = _classify_serial_error(e)
        return None, f"[{code}] Serial error: {e}"
    except Exception as e:
        return None, f"[unknown_error] Error: {e}"


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

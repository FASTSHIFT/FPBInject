#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtual serial passthrough tests.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.virtual_serial import VirtualSerialService  # noqa: E402


class _FakeSerial:
    """Minimal stand-in for ThreadCheckedSerial exposing set_tee."""

    def __init__(self):
        self._tee_rx = None
        self._tee_tx = None

    def set_tee(self, tx=None, rx=None):
        self._tee_tx = tx
        self._tee_rx = rx


class _FakeDevice:
    def __init__(self, ser=None):
        self.ser = ser


@unittest.skipUnless(hasattr(os, "openpty"), "PTY not supported on this platform")
class TestVirtualSerialService(unittest.TestCase):
    """VirtualSerialService PTY passthrough tests."""

    def setUp(self):
        self.device = _FakeDevice()
        self.svc = VirtualSerialService(self.device)
        self._symlink = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), f".vtty-{os.getpid()}"
        )

    def tearDown(self):
        self.svc.stop()
        try:
            if os.path.islink(self._symlink):
                os.unlink(self._symlink)
        except OSError:
            pass

    def _start(self):
        ok, err = self.svc.start(symlink=self._symlink)
        self.assertTrue(ok, err)
        return err

    def test_start_creates_pty_and_symlink(self):
        self._start()
        status = self.svc.status()
        self.assertTrue(status["enabled"])
        self.assertTrue(status["slave"])
        self.assertTrue(os.path.exists(status["slave"]))
        self.assertEqual(status["symlink"], self._symlink)
        self.assertTrue(os.path.islink(self._symlink))

    def test_start_idempotent(self):
        self._start()
        ok, _ = self.svc.start(symlink=self._symlink)
        self.assertTrue(ok)

    def test_forward_rx_reaches_slave(self):
        self._start()
        slave = open(self.svc.status()["slave"], "rb", buffering=0)
        try:
            self.svc.forward_rx(b"hello")
            data = slave.read(5)
            self.assertEqual(data, b"hello")
        finally:
            slave.close()

    def test_poll_tx_reads_external_input(self):
        self._start()
        slave = open(self.svc.status()["slave"], "wb", buffering=0)
        try:
            slave.write(b"ls\n")
            slave.flush()
            time.sleep(0.05)
            out = self.svc.poll_tx()
            self.assertEqual(out, b"ls\n")
        finally:
            slave.close()

    def test_tee_installed_on_start_and_removed_on_stop(self):
        """Full passthrough: start installs an rx tee; stop removes it."""
        ser = _FakeSerial()
        device = _FakeDevice(ser=ser)
        svc = VirtualSerialService(device)
        try:
            ok, err = svc.start(symlink=self._symlink)
            self.assertTrue(ok, err)
            # The tee must be wired to forward_rx so protocol I/O is mirrored.
            self.assertEqual(ser._tee_rx, svc.forward_rx)
        finally:
            svc.stop()
        self.assertIsNone(ser._tee_rx)

    def test_tee_rx_mirrors_protocol_bytes_to_slave(self):
        """Bytes fed through the tee (as protocol reads would) reach the slave."""
        ser = _FakeSerial()
        device = _FakeDevice(ser=ser)
        svc = VirtualSerialService(device)
        try:
            svc.start(symlink=self._symlink)
            slave = open(svc.status()["slave"], "rb", buffering=0)
            try:
                # Simulate a protocol-layer ser.read() delivering bytes via tee.
                ser._tee_rx(b"[FLOK]data")
                self.assertEqual(slave.read(10), b"[FLOK]data")
            finally:
                slave.close()
        finally:
            svc.stop()

    def test_stop_removes_symlink_and_disables(self):
        self._start()
        self.svc.stop()
        self.assertFalse(self.svc.is_enabled())
        self.assertFalse(os.path.islink(self._symlink))

    def test_poll_tx_when_disabled_returns_none(self):
        self.assertIsNone(self.svc.poll_tx())

    def test_forward_rx_when_disabled_noop(self):
        self.svc.forward_rx(b"data")


if __name__ == "__main__":
    unittest.main()

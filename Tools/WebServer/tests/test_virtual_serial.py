#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtual serial passthrough tests.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.virtual_serial import VirtualSerialService  # noqa: E402


class _FakeDevice:
    def __init__(self):
        self.ser = None


@unittest.skipUnless(hasattr(os, "openpty"), "PTY not supported on this platform")
class TestVirtualSerialService(unittest.TestCase):
    """VirtualSerialService PTY passthrough tests."""

    def setUp(self):
        self.device = _FakeDevice()
        self.svc = VirtualSerialService(self.device)
        # Use a unique temp symlink to avoid clobbering a real one.
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

    def _start(self, mute_policy="buffer"):
        ok, err = self.svc.start(symlink=self._symlink, mute_policy=mute_policy)
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
            # Small wait for data to become available on master.
            import time

            time.sleep(0.05)
            out = self.svc.poll_tx()
            self.assertEqual(out, b"ls\n")
        finally:
            slave.close()

    def test_mute_blocks_rx_forwarding(self):
        self._start()
        slave = open(self.svc.status()["slave"], "rb", buffering=0)
        try:
            os.set_blocking(slave.fileno(), False)
            self.svc.mute()
            self.svc.forward_rx(b"frame")
            # Muted: nothing forwarded, non-blocking read yields no data.
            try:
                data = slave.read(5)
            except (BlockingIOError, OSError):
                data = None
            self.assertFalse(data)
        finally:
            slave.close()

    def test_mute_buffers_then_flushes(self):
        self._start(mute_policy="buffer")
        slave = open(self.svc.status()["slave"], "wb", buffering=0)
        try:
            self.svc.mute()
            slave.write(b"abc")
            slave.flush()
            import time

            time.sleep(0.05)
            # While muted, poll returns nothing (buffered).
            self.assertIsNone(self.svc.poll_tx())
            # After unmute, buffered bytes are flushed.
            self.svc.unmute()
            self.assertEqual(self.svc.poll_tx(), b"abc")
        finally:
            slave.close()

    def test_mute_drop_policy_discards(self):
        self._start(mute_policy="drop")
        slave = open(self.svc.status()["slave"], "wb", buffering=0)
        try:
            self.svc.mute()
            slave.write(b"abc")
            slave.flush()
            import time

            time.sleep(0.05)
            self.assertIsNone(self.svc.poll_tx())
            self.svc.unmute()
            # Dropped: nothing to flush.
            self.assertIsNone(self.svc.poll_tx())
        finally:
            slave.close()

    def test_stop_removes_symlink_and_disables(self):
        self._start()
        self.svc.stop()
        self.assertFalse(self.svc.is_enabled())
        self.assertFalse(os.path.islink(self._symlink))

    def test_poll_tx_when_disabled_returns_none(self):
        self.assertIsNone(self.svc.poll_tx())

    def test_forward_rx_when_disabled_noop(self):
        # Should not raise.
        self.svc.forward_rx(b"data")


if __name__ == "__main__":
    unittest.main()

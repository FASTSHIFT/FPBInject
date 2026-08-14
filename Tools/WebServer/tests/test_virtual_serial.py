#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtual serial passthrough tests.
"""

import os
import sys
import time
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.services.virtual_serial import (  # noqa: E402
    VirtualSerialService,
    default_symlink_for_port,
)


class _FakeSerial:
    """Minimal stand-in for ThreadCheckedSerial exposing set_tee."""

    def __init__(self):
        self._tee_rx = None
        self._tee_tx = None

    def set_tee(self, tx=None, rx=None):
        self._tee_tx = tx
        self._tee_rx = rx


class _FakeDevice:
    def __init__(self, ser=None, port=None):
        self.ser = ser
        self.port = port


class TestDefaultSymlinkForPort(unittest.TestCase):
    """Derivation of the per-device default symlink from the port name."""

    def test_ttyacm(self):
        self.assertEqual(default_symlink_for_port("/dev/ttyACM0"), "/tmp/fpb-ttyACM0")

    def test_ttyusb(self):
        self.assertEqual(default_symlink_for_port("/dev/ttyUSB1"), "/tmp/fpb-ttyUSB1")

    def test_by_id_path(self):
        got = default_symlink_for_port("/dev/serial/by-id/usb-Foo_if00")
        self.assertEqual(got, "/tmp/fpb-usb-Foo_if00")

    def test_none_falls_back(self):
        self.assertEqual(default_symlink_for_port(None), "/tmp/fpb-tty0")

    def test_sanitizes_unsafe_chars(self):
        got = default_symlink_for_port("/dev/tty:weird*name")
        self.assertTrue(got.startswith("/tmp/fpb-"))
        self.assertNotIn(":", got)
        self.assertNotIn("*", got)


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

    def test_legacy_default_symlink_treated_as_auto(self):
        """The legacy '/tmp/fpb-tty0' value derives per-device (back-compat)."""
        port = f"/dev/ttyLEG{os.getpid()}"
        expected = default_symlink_for_port(port)
        device = _FakeDevice(port=port)
        svc = VirtualSerialService(device)
        try:
            ok, err = svc.start(symlink="/tmp/fpb-tty0")
            self.assertTrue(ok, err)
            self.assertEqual(svc.status()["symlink"], expected)
        finally:
            svc.stop()

    def test_auto_symlink_derived_from_port(self):
        """symlink=None/'auto' derives the alias from device.port."""
        # Use a unique fake port so the derived path won't clash with reality.
        port = f"/dev/ttyFAKE{os.getpid()}"
        expected = default_symlink_for_port(port)
        device = _FakeDevice(port=port)
        svc = VirtualSerialService(device)
        try:
            ok, err = svc.start(symlink="auto")
            self.assertTrue(ok, err)
            self.assertEqual(svc.status()["symlink"], expected)
            self.assertTrue(os.path.islink(expected))
        finally:
            svc.stop()
        self.assertFalse(os.path.islink(expected))

    def test_collision_falls_back_to_suffix(self):
        """A second instance on the same base path gets a -N suffix."""
        base = self._symlink
        svc2 = VirtualSerialService(_FakeDevice())
        try:
            self.svc.start(symlink=base)
            svc2.start(symlink=base)
            self.assertEqual(self.svc.status()["symlink"], base)
            # Second instance must not steal the first one's live link.
            self.assertNotEqual(svc2.status()["symlink"], base)
            self.assertEqual(svc2.status()["symlink"], f"{base}-1")
        finally:
            svc2.stop()

    def test_reclaims_dangling_symlink(self):
        """A stale (dangling) symlink at the base path is safely reclaimed."""
        base = self._symlink
        # Create a dangling link pointing at a non-existent pts.
        try:
            os.symlink("/dev/pts/999999", base)
        except OSError:
            self.skipTest("cannot create test symlink")
        self.svc.start(symlink=base)
        self.assertEqual(self.svc.status()["symlink"], base)
        self.assertEqual(os.path.realpath(base), self.svc.status()["slave"])

    def test_empty_symlink_disables_alias(self):
        """symlink='' creates the PTY but no stable alias."""
        ok, err = self.svc.start(symlink="")
        self.assertTrue(ok, err)
        status = self.svc.status()
        self.assertTrue(status["enabled"])
        self.assertTrue(status["slave"])
        self.assertIsNone(status["symlink"])

    def test_all_candidates_in_use_starts_without_symlink(self):
        """When base + all -N suffixes are live, start still succeeds but the
        symlink is None (external tools use /dev/pts/N directly)."""
        base = self._symlink
        # Force _reserve_symlink to exhaust every candidate by claiming that
        # each one links to a "live" pts.
        with unittest.mock.patch.object(
            self.svc, "_reserve_symlink", return_value=None
        ):
            ok, err = self.svc.start(symlink=base)
        self.assertTrue(ok, err)
        self.assertIsNone(self.svc.status()["symlink"])
        self.assertTrue(self.svc.status()["enabled"])

    def test_reserve_symlink_oserror_is_non_fatal(self):
        """os.symlink raising (e.g. read-only dir) must not crash start()."""
        with unittest.mock.patch(
            "fpbinject.services.virtual_serial.os.symlink",
            side_effect=OSError("read-only fs"),
        ):
            ok, err = self.svc.start(symlink=self._symlink)
        # PTY still up; alias just couldn't be created.
        self.assertTrue(ok, err)
        self.assertIsNone(self.svc.status()["symlink"])

    def test_openpty_failure_returns_error(self):
        """openpty failing yields (False, error), not an exception."""
        svc = VirtualSerialService(_FakeDevice())
        with unittest.mock.patch(
            "fpbinject.services.virtual_serial.os.openpty",
            side_effect=OSError("no ptys"),
        ):
            ok, err = svc.start(symlink=self._symlink)
        self.assertFalse(ok)
        self.assertIn("openpty failed", err)

    def test_stop_when_not_started_is_noop(self):
        """Calling stop() before start() does nothing and does not raise."""
        self.svc.stop()  # should be a no-op
        self.assertFalse(self.svc.status()["enabled"])

    def test_forward_rx_write_oserror_swallowed(self):
        """A write OSError on the master fd is logged, not raised."""
        self._start()
        with unittest.mock.patch(
            "fpbinject.services.virtual_serial.os.write",
            side_effect=OSError("broken pipe"),
        ):
            # Should not raise.
            self.svc.forward_rx(b"payload")

    def test_poll_tx_oserror_returns_none(self):
        """A read OSError on the master fd yields None rather than raising."""
        self._start()
        with unittest.mock.patch(
            "fpbinject.services.virtual_serial.os.read",
            side_effect=OSError("io error"),
        ):
            self.assertIsNone(self.svc.poll_tx())


@unittest.skipUnless(hasattr(os, "openpty"), "PTY not supported on this platform")
class TestVirtualSerialEnvSensitivity(unittest.TestCase):
    """Behaviors that depend on the runtime environment (temp dir, platform)."""

    def test_symlink_dir_uses_tempdir_not_hardcoded_tmp(self):
        """default_symlink_for_port derives from tempfile.gettempdir(), so a
        non-/tmp TMPDIR is honored (portability / sandboxed environments)."""
        import importlib
        import fpbinject.services.virtual_serial as vs

        with unittest.mock.patch("tempfile.gettempdir", return_value="/custom/tmp"):
            importlib.reload(vs)
            try:
                self.assertEqual(
                    vs.default_symlink_for_port("/dev/ttyACM0"),
                    "/custom/tmp/fpb-ttyACM0",
                )
            finally:
                importlib.reload(vs)  # restore real tempdir binding

    def test_platform_without_openpty_reports_error(self):
        """On a platform lacking os.openpty (e.g. Windows) start() fails
        gracefully with a clear message instead of raising."""
        svc = VirtualSerialService(_FakeDevice())
        real_openpty = getattr(os, "openpty", None)
        try:
            if hasattr(os, "openpty"):
                del os.openpty
            ok, err = svc.start(symlink="/tmp/whatever")
            self.assertFalse(ok)
            self.assertIn("not supported", err)
        finally:
            if real_openpty is not None:
                os.openpty = real_openpty


if __name__ == "__main__":
    unittest.main()

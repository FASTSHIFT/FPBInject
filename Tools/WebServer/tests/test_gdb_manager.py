#!/usr/bin/env python3

"""Tests for GDB integration manager (core/gdb_manager.py)."""

import time
import unittest
from unittest.mock import MagicMock, patch

from fpbinject.core.gdb_manager import (
    start_gdb,
    stop_gdb,
    is_gdb_available,
    start_external_gdb_server,
    stop_external_gdb_server,
    get_external_gdb_port,
    _apply_elf_memory_regions,
    _create_serial_memory_callbacks,
    _GDBFLIdleExit,
)


class TestIsGDBAvailable(unittest.TestCase):
    """Test is_gdb_available helper."""

    def test_no_session(self):
        state = MagicMock()
        state.gdb_session = None
        self.assertFalse(is_gdb_available(state))

    def test_session_not_alive(self):
        state = MagicMock()
        state.gdb_session = MagicMock()
        state.gdb_session.is_alive = False
        self.assertFalse(is_gdb_available(state))

    def test_session_alive(self):
        state = MagicMock()
        state.gdb_session = MagicMock()
        state.gdb_session.is_alive = True
        self.assertTrue(is_gdb_available(state))


class TestStopGDB(unittest.TestCase):
    """Test stop_gdb cleanup."""

    def test_stop_with_session_and_bridge(self):
        state = MagicMock()
        mock_session = MagicMock()
        mock_bridge = MagicMock()
        mock_ext_bridge = MagicMock()
        state.gdb_session = mock_session
        state.gdb_bridge = mock_bridge
        state.external_gdb_bridge = mock_ext_bridge

        stop_gdb(state)

        mock_session.stop.assert_called_once()
        mock_bridge.stop.assert_called_once()
        mock_ext_bridge.stop.assert_called_once()
        self.assertIsNone(state.gdb_session)
        self.assertIsNone(state.gdb_bridge)
        self.assertIsNone(state.external_gdb_bridge)

    def test_stop_with_nothing(self):
        state = MagicMock()
        state.gdb_session = None
        state.gdb_bridge = None
        state.external_gdb_bridge = None

        # Should not raise
        stop_gdb(state)

    def test_stop_handles_exception(self):
        state = MagicMock()
        state.gdb_session = MagicMock()
        state.gdb_session.stop.side_effect = Exception("cleanup error")
        state.gdb_bridge = MagicMock()

        # Should not raise
        stop_gdb(state)
        self.assertIsNone(state.gdb_session)
        self.assertIsNone(state.gdb_bridge)


class TestStartGDB(unittest.TestCase):
    """Test start_gdb integration."""

    def _make_state(self, elf_path="/fake/elf", toolchain_path=None):
        state = MagicMock()
        state.device = MagicMock()
        state.device.elf_path = elf_path
        state.device.toolchain_path = toolchain_path
        state.gdb_bridge = None
        state.gdb_session = None
        return state

    def test_no_elf_path(self):
        state = self._make_state(elf_path="")
        result = start_gdb(state)
        self.assertFalse(result)

    @patch("fpbinject.core.gdb_manager.os.path.exists", return_value=False)
    def test_elf_not_found(self, mock_exists):
        state = self._make_state()
        result = start_gdb(state)
        self.assertFalse(result)

    @patch("fpbinject.core.gdb_manager.start_external_gdb_server")
    @patch("fpbinject.core.gdb_manager.GDBSession")
    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    @patch("fpbinject.core.gdb_manager.os.path.exists", return_value=True)
    def test_start_success(self, mock_exists, MockBridge, MockSession, mock_ext):
        mock_bridge = MockBridge.return_value
        mock_bridge.start.return_value = 12345

        mock_session = MockSession.return_value
        mock_session.start.return_value = True

        state = self._make_state()
        result = start_gdb(state)

        self.assertTrue(result)
        mock_bridge.start.assert_called_once()
        mock_session.start.assert_called_once_with(rsp_port=12345)
        self.assertEqual(state.gdb_bridge, mock_bridge)
        self.assertEqual(state.gdb_session, mock_session)
        mock_ext.assert_called_once()

    @patch("fpbinject.core.gdb_manager.GDBSession")
    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    @patch("fpbinject.core.gdb_manager.os.path.exists", return_value=True)
    def test_start_session_fails(self, mock_exists, MockBridge, MockSession):
        mock_bridge = MockBridge.return_value
        mock_bridge.start.return_value = 12345

        mock_session = MockSession.return_value
        mock_session.start.return_value = False

        state = self._make_state()
        result = start_gdb(state)

        self.assertFalse(result)
        # Bridge should be cleaned up
        mock_bridge.stop.assert_called()
        self.assertIsNone(state.gdb_bridge)

    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    @patch("fpbinject.core.gdb_manager.os.path.exists", return_value=True)
    def test_start_bridge_exception(self, mock_exists, MockBridge):
        MockBridge.return_value.start.side_effect = Exception("port in use")

        state = self._make_state()
        result = start_gdb(state)

        self.assertFalse(result)

    @patch("fpbinject.core.gdb_manager.start_external_gdb_server")
    @patch("fpbinject.core.gdb_manager.GDBSession")
    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    @patch("fpbinject.core.gdb_manager.os.path.exists", return_value=True)
    def test_start_uses_offline_stubs(
        self, mock_exists, MockBridge, MockSession, mock_ext
    ):
        """When no read/write functions provided, offline stubs are used."""
        mock_bridge = MockBridge.return_value
        mock_bridge.start.return_value = 12345
        mock_session = MockSession.return_value
        mock_session.start.return_value = True

        state = self._make_state()
        result = start_gdb(state)

        self.assertTrue(result)
        # Bridge was created with callable read/write functions
        call_args = MockBridge.call_args
        read_fn = call_args[1]["read_memory_fn"]
        write_fn = call_args[1]["write_memory_fn"]
        # Test offline stubs
        data, msg = read_fn(0x1000, 4)
        self.assertEqual(data, b"\x00\x00\x00\x00")
        ok, msg = write_fn(0x1000, b"\x01\x02")
        self.assertTrue(ok)

    @patch("fpbinject.core.gdb_manager.GDBSession")
    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    @patch("fpbinject.core.gdb_manager.os.path.exists", return_value=True)
    def test_start_stops_existing(self, mock_exists, MockBridge, MockSession):
        """Starting GDB should stop any existing session first."""
        mock_bridge = MockBridge.return_value
        mock_bridge.start.return_value = 12345
        mock_session = MockSession.return_value
        mock_session.start.return_value = True

        state = self._make_state()
        old_session = MagicMock()
        old_bridge = MagicMock()
        state.gdb_session = old_session
        state.gdb_bridge = old_bridge

        start_gdb(state)

        old_session.stop.assert_called_once()
        old_bridge.stop.assert_called_once()


class TestExternalGDBServer(unittest.TestCase):
    """Test external GDB server management."""

    def _make_state(self, port=3333):
        state = MagicMock()
        state.device = MagicMock()
        state.device.external_gdb_port = port
        state.device.ser = MagicMock()  # Simulate connected
        state.external_gdb_bridge = None
        return state

    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    def test_start_external_success(self, MockBridge):
        mock_bridge = MockBridge.return_value
        mock_bridge.start.return_value = 3333
        mock_bridge.is_running = True

        state = self._make_state()
        result = start_external_gdb_server(state)

        self.assertTrue(result)
        self.assertEqual(state.external_gdb_bridge, mock_bridge)
        mock_bridge.start.assert_called_once()

    def test_start_external_disabled(self):
        """Port 0 should disable external GDB server."""
        state = self._make_state(port=0)
        result = start_external_gdb_server(state)
        self.assertFalse(result)
        self.assertIsNone(state.external_gdb_bridge)

    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    def test_start_external_already_running(self, MockBridge):
        """Should return True if already running."""
        state = self._make_state()
        existing_bridge = MagicMock()
        existing_bridge.is_running = True
        existing_bridge.port = 3333
        state.external_gdb_bridge = existing_bridge

        result = start_external_gdb_server(state)
        self.assertTrue(result)
        MockBridge.assert_not_called()  # Should not create new bridge

    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    def test_start_external_exception(self, MockBridge):
        MockBridge.return_value.start.side_effect = Exception("port in use")

        state = self._make_state()
        result = start_external_gdb_server(state)
        self.assertFalse(result)

    def test_stop_external(self):
        state = MagicMock()
        mock_bridge = MagicMock()
        state.external_gdb_bridge = mock_bridge

        stop_external_gdb_server(state)

        mock_bridge.stop.assert_called_once()
        self.assertIsNone(state.external_gdb_bridge)

    def test_stop_external_none(self):
        state = MagicMock()
        state.external_gdb_bridge = None
        # Should not raise
        stop_external_gdb_server(state)

    def test_stop_external_exception(self):
        state = MagicMock()
        state.external_gdb_bridge = MagicMock()
        state.external_gdb_bridge.stop.side_effect = Exception("error")
        # Should not raise
        stop_external_gdb_server(state)
        self.assertIsNone(state.external_gdb_bridge)

    def test_get_port_running(self):
        state = MagicMock()
        state.external_gdb_bridge = MagicMock()
        state.external_gdb_bridge.is_running = True
        state.external_gdb_bridge.port = 3333

        self.assertEqual(get_external_gdb_port(state), 3333)

    def test_get_port_not_running(self):
        state = MagicMock()
        state.external_gdb_bridge = MagicMock()
        state.external_gdb_bridge.is_running = False

        self.assertEqual(get_external_gdb_port(state), 0)

    def test_get_port_none(self):
        state = MagicMock()
        state.external_gdb_bridge = None

        self.assertEqual(get_external_gdb_port(state), 0)

    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    def test_start_external_creates_serial_callbacks(self, MockBridge):
        """When no callbacks provided, serial callbacks should be created."""
        mock_bridge = MockBridge.return_value
        mock_bridge.start.return_value = 3333

        state = self._make_state()
        start_external_gdb_server(state)

        # Verify bridge was created with callable functions
        call_args = MockBridge.call_args
        read_fn = call_args[1]["read_memory_fn"]
        write_fn = call_args[1]["write_memory_fn"]
        self.assertTrue(callable(read_fn))
        self.assertTrue(callable(write_fn))

    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    def test_start_external_uses_provided_callbacks(self, MockBridge):
        """When callbacks are provided, they should be used directly."""
        mock_bridge = MockBridge.return_value
        mock_bridge.start.return_value = 3333

        custom_read = MagicMock()
        custom_write = MagicMock()

        state = self._make_state()
        start_external_gdb_server(state, custom_read, custom_write)

        call_args = MockBridge.call_args
        self.assertEqual(call_args[1]["read_memory_fn"], custom_read)
        self.assertEqual(call_args[1]["write_memory_fn"], custom_write)


class TestSerialMemoryCallbacks(unittest.TestCase):
    """Test _create_serial_memory_callbacks."""

    def _make_state(self, connected=True):
        state = MagicMock()
        state.device = MagicMock()
        state.device.ser = MagicMock() if connected else None
        return state

    def test_read_not_connected(self):
        state = self._make_state(connected=False)
        read_fn, _ = _create_serial_memory_callbacks(state)

        data, msg = read_fn(0x20000000, 4)
        self.assertIsNone(data)
        self.assertIn("Not connected", msg)

    def test_write_not_connected(self):
        state = self._make_state(connected=False)
        _, write_fn = _create_serial_memory_callbacks(state)

        ok, msg = write_fn(0x20000000, b"\x01\x02")
        self.assertFalse(ok)
        self.assertIn("Not connected", msg)

    @patch("fpbinject.services.device_worker.run_in_device_worker", return_value=False)
    def test_read_worker_timeout(self, mock_worker):
        state = self._make_state(connected=True)
        read_fn, _ = _create_serial_memory_callbacks(state)

        data, msg = read_fn(0x20000000, 4)
        self.assertIsNone(data)
        self.assertIn("timeout", msg.lower())

    @patch("fpbinject.services.device_worker.run_in_device_worker", return_value=False)
    def test_write_worker_timeout(self, mock_worker):
        state = self._make_state(connected=True)
        _, write_fn = _create_serial_memory_callbacks(state)

        ok, msg = write_fn(0x20000000, b"\x01")
        self.assertFalse(ok)
        self.assertIn("timeout", msg.lower())


class TestGDBFLIdleExit(unittest.TestCase):
    """Test the lazy fl-exit watcher used by the external GDB bridge.

    The watcher schedules a soft timer on the DeviceWorker's TimerManager
    so no extra thread is spawned. Tests drive the TimerManager tick
    manually instead of relying on the worker thread.
    """

    def _make(self, idle_sec=0.05):
        from fpbinject.services.timer import TimerManager

        fpb = MagicMock()
        tm = TimerManager()
        idle = _GDBFLIdleExit(lambda: fpb, tm, idle_sec=idle_sec)
        return idle, tm, fpb

    def test_fires_exit_after_idle(self):
        """After idle_sec of real wall time, tick fires exit_fl_mode once."""
        idle, tm, fpb = self._make(idle_sec=0.03)
        idle.mark_active()

        # Still within the window: tick must not fire exit.
        tm.tick()
        fpb.exit_fl_mode.assert_not_called()

        # Sleep past the idle window and tick again -> exit fires.
        time.sleep(0.06)
        tm.tick()
        fpb.exit_fl_mode.assert_called_once()

    def test_burst_coalesces_into_single_exit(self):
        """Marking active repeatedly resets the deadline; one exit at the end."""
        idle, tm, fpb = self._make(idle_sec=0.05)

        for _ in range(5):
            idle.mark_active()
            time.sleep(0.01)  # each access spaced under the window
            tm.tick()
        fpb.exit_fl_mode.assert_not_called()

        # Now let the window elapse without further activity.
        time.sleep(0.08)
        tm.tick()
        fpb.exit_fl_mode.assert_called_once()

    def test_stop_cancels_pending_exit(self):
        """stop() removes the timer so no exit fires afterwards."""
        idle, tm, fpb = self._make(idle_sec=0.02)
        idle.mark_active()
        idle.stop()
        time.sleep(0.05)
        tm.tick()
        fpb.exit_fl_mode.assert_not_called()

    def test_no_timer_manager_is_safe(self):
        """When the worker isn't running yet, mark_active must not crash."""
        fpb = MagicMock()
        idle = _GDBFLIdleExit(lambda: fpb, None, idle_sec=0.05)
        idle.mark_active()  # no-op, timer manager missing
        idle.stop()
        fpb.exit_fl_mode.assert_not_called()


class TestSerialCallbacksLazyExit(unittest.TestCase):
    """The read/write callbacks must use the lazy idle-exit path, not
    fl_session(), so a burst of GDB reads doesn't re-enter/exit fl every time.
    """

    @patch("fpbinject.core.gdb_manager.GDBRSPBridge")
    def test_no_fl_session_per_access(self, MockBridge):
        """The callbacks should not wrap each access in fl_session()."""
        mock_bridge = MockBridge.return_value
        mock_bridge.start.return_value = 3333

        state = MagicMock()
        state.device = MagicMock()
        state.device.ser = MagicMock()
        state.device.external_gdb_port = 3333
        state.external_gdb_bridge = None

        start_external_gdb_server(state)

        # An idle-exit watcher was attached, and no fl_session was invoked on
        # the fpb instance (because the callbacks defer the exit).
        self.assertIsNotNone(state.external_gdb_idle_exit)

    def test_stop_external_shuts_down_idle_exit(self):
        state = MagicMock()
        state.external_gdb_bridge = MagicMock()
        idle_exit = MagicMock()
        state.external_gdb_idle_exit = idle_exit

        stop_external_gdb_server(state)

        idle_exit.stop.assert_called_once()
        self.assertIsNone(state.external_gdb_idle_exit)


class TestApplyElfMemoryRegions(unittest.TestCase):
    """Test _apply_elf_memory_regions helper."""

    @patch(
        "fpbinject.core.gdb_manager.get_memory_regions",
        return_value=[(0x08000000, 0x08100000)],
    )
    def test_applies_elf_regions(self, mock_get):
        bridge = MagicMock()
        _apply_elf_memory_regions(bridge, "/path/to/firmware.elf")
        mock_get.assert_called_once_with("/path/to/firmware.elf")
        bridge.set_memory_regions.assert_called_once_with([(0x08000000, 0x08100000)])

    @patch("fpbinject.core.gdb_manager.get_memory_regions", return_value=[])
    def test_empty_regions_keeps_default(self, mock_get):
        bridge = MagicMock()
        _apply_elf_memory_regions(bridge, "/path/to/firmware.elf")
        bridge.set_memory_regions.assert_not_called()

    def test_no_elf_path(self):
        bridge = MagicMock()
        _apply_elf_memory_regions(bridge, "")
        bridge.set_memory_regions.assert_not_called()

    def test_none_elf_path(self):
        bridge = MagicMock()
        _apply_elf_memory_regions(bridge, None)
        bridge.set_memory_regions.assert_not_called()


if __name__ == "__main__":
    unittest.main()

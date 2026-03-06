#!/usr/bin/env python3

"""Tests for GDB integration manager (core/gdb_manager.py)."""

import unittest
from unittest.mock import MagicMock, patch

from core.gdb_manager import start_gdb, stop_gdb, is_gdb_available


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
        state.gdb_session = mock_session
        state.gdb_bridge = mock_bridge

        stop_gdb(state)

        mock_session.stop.assert_called_once()
        mock_bridge.stop.assert_called_once()
        self.assertIsNone(state.gdb_session)
        self.assertIsNone(state.gdb_bridge)

    def test_stop_with_nothing(self):
        state = MagicMock()
        state.gdb_session = None
        state.gdb_bridge = None

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

    @patch("core.gdb_manager.os.path.exists", return_value=False)
    def test_elf_not_found(self, mock_exists):
        state = self._make_state()
        result = start_gdb(state)
        self.assertFalse(result)

    @patch("core.gdb_manager.GDBSession")
    @patch("core.gdb_manager.GDBRSPBridge")
    @patch("core.gdb_manager.os.path.exists", return_value=True)
    def test_start_success(self, mock_exists, MockBridge, MockSession):
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

    @patch("core.gdb_manager.GDBSession")
    @patch("core.gdb_manager.GDBRSPBridge")
    @patch("core.gdb_manager.os.path.exists", return_value=True)
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

    @patch("core.gdb_manager.GDBRSPBridge")
    @patch("core.gdb_manager.os.path.exists", return_value=True)
    def test_start_bridge_exception(self, mock_exists, MockBridge):
        MockBridge.return_value.start.side_effect = Exception("port in use")

        state = self._make_state()
        result = start_gdb(state)

        self.assertFalse(result)

    @patch("core.gdb_manager.GDBSession")
    @patch("core.gdb_manager.GDBRSPBridge")
    @patch("core.gdb_manager.os.path.exists", return_value=True)
    def test_start_uses_offline_stubs(self, mock_exists, MockBridge, MockSession):
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

    @patch("core.gdb_manager.GDBSession")
    @patch("core.gdb_manager.GDBRSPBridge")
    @patch("core.gdb_manager.os.path.exists", return_value=True)
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


if __name__ == "__main__":
    unittest.main()

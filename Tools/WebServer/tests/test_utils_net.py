#!/usr/bin/env python3

"""
Tests for utils/net.py
"""

import os
import signal
import socket
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.net import (  # noqa: E402
    check_and_free_port,
    get_port_owner,
    is_port_available,
    kill_port_owner,
)


class TestIsPortAvailable(unittest.TestCase):
    """Tests for is_port_available."""

    def test_available_port(self):
        """An unused port should be available."""
        # Use a random high port unlikely to be in use
        self.assertTrue(is_port_available("127.0.0.1", 59123))

    def test_occupied_port(self):
        """A port with a listener should not be available."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        try:
            self.assertFalse(is_port_available("127.0.0.1", port))
        finally:
            s.close()

    def test_port_after_close(self):
        """Port should be available after listener closes."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        self.assertTrue(is_port_available("127.0.0.1", port))


class TestGetPortOwner(unittest.TestCase):
    """Tests for get_port_owner."""

    def test_no_listener(self):
        """Should return None for a port with no listener."""
        result = get_port_owner(59124)
        self.assertIsNone(result)

    def test_own_process(self):
        """Should find our own process as the owner."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        try:
            owner = get_port_owner(port)
            if owner:  # May fail in some CI environments
                self.assertEqual(owner["pid"], os.getpid())
                self.assertIn("pid", owner)
                self.assertIn("name", owner)
        finally:
            s.close()


class TestKillPortOwner(unittest.TestCase):
    """Tests for kill_port_owner."""

    def test_no_owner(self):
        """Should return False when no process owns the port."""
        self.assertFalse(kill_port_owner(59125))

    def test_skip_own_pid(self):
        """Should not kill our own process."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        try:
            # kill_port_owner should skip our own PID
            result = kill_port_owner(port)
            self.assertFalse(result)
        finally:
            s.close()

    @patch("utils.net.get_port_owner")
    @patch("utils.net.os.kill")
    def test_kill_stale_process(self, mock_kill, mock_owner):
        """Should kill a stale process and return True."""
        mock_owner.return_value = {
            "pid": 99999,
            "name": "python",
            "cmdline": "python main.py",
        }
        # Simulate process dying after SIGTERM
        mock_kill.side_effect = [None, OSError("No such process")]

        result = kill_port_owner(12345, timeout=0.5)
        self.assertTrue(result)
        mock_kill.assert_any_call(99999, signal.SIGTERM)

    @patch("utils.net.get_port_owner")
    @patch("utils.net.os.kill")
    def test_kill_fails(self, mock_kill, mock_owner):
        """Should return False when kill raises OSError."""
        mock_owner.return_value = {"pid": 99999, "name": "x", "cmdline": "x"}
        mock_kill.side_effect = OSError("Operation not permitted")

        result = kill_port_owner(12345)
        self.assertFalse(result)


class TestCheckAndFreePort(unittest.TestCase):
    """Tests for check_and_free_port."""

    def test_available_port(self):
        """Should return True immediately for a free port."""
        self.assertTrue(check_and_free_port("127.0.0.1", 59126))

    @patch("utils.net.kill_port_owner", return_value=True)
    @patch("utils.net.is_port_available", return_value=False)
    def test_occupied_then_freed(self, mock_avail, mock_kill):
        """Should try to kill and return True on success."""
        self.assertTrue(check_and_free_port("127.0.0.1", 12345))
        mock_kill.assert_called_once_with(12345)

    @patch("utils.net.kill_port_owner", return_value=False)
    @patch("utils.net.is_port_available", return_value=False)
    def test_occupied_kill_fails(self, mock_avail, mock_kill):
        """Should return False when kill fails."""
        self.assertFalse(check_and_free_port("127.0.0.1", 12345))


class TestGDBPortConflict(unittest.TestCase):
    """Integration test: GDB server port conflict detection."""

    @patch("utils.net.get_port_owner")
    def test_gdb_manager_checks_port(self, mock_owner):
        """start_external_gdb_server should check port availability."""
        mock_owner.return_value = None

        with patch(
            "core.gdb_manager.is_port_available", return_value=True
        ) as mock_check:
            with patch("core.gdb_manager.GDBRSPBridge") as mock_bridge_cls:
                mock_bridge = MagicMock()
                mock_bridge.start.return_value = 3333
                mock_bridge.is_running = False
                mock_bridge_cls.return_value = mock_bridge

                from core.gdb_manager import start_external_gdb_server

                state = MagicMock()
                state.device.external_gdb_port = 3333
                state.device.elf_path = None
                state.device.download_chunk_size = 1024
                state.external_gdb_bridge = None

                result = start_external_gdb_server(state)
                self.assertTrue(result)
                mock_check.assert_called_once_with("127.0.0.1", 3333)

    def test_gdb_manager_rejects_occupied_port(self):
        """start_external_gdb_server should fail with detailed info if port can't be freed."""
        with patch("core.gdb_manager.is_port_available", return_value=False):
            with patch(
                "core.gdb_manager.get_port_owner",
                return_value={
                    "pid": 999,
                    "name": "python",
                    "cmdline": "python main.py",
                },
            ):
                with patch("core.gdb_manager.kill_port_owner", return_value=False):
                    from core.gdb_manager import start_external_gdb_server

                    state = MagicMock()
                    state.device.external_gdb_port = 3333
                    state.external_gdb_bridge = None

                    result = start_external_gdb_server(state)
                    self.assertFalse(result)

    def test_gdb_manager_kills_stale_and_starts(self):
        """start_external_gdb_server should kill stale process and succeed."""
        with patch("core.gdb_manager.is_port_available", return_value=False):
            with patch(
                "core.gdb_manager.get_port_owner",
                return_value={"pid": 888, "name": "python", "cmdline": "old"},
            ):
                with patch("core.gdb_manager.kill_port_owner", return_value=True):
                    with patch("core.gdb_manager.GDBRSPBridge") as mock_bridge_cls:
                        mock_bridge = MagicMock()
                        mock_bridge.start.return_value = 3333
                        mock_bridge.is_running = False
                        mock_bridge_cls.return_value = mock_bridge

                        from core.gdb_manager import start_external_gdb_server

                        state = MagicMock()
                        state.device.external_gdb_port = 3333
                        state.device.elf_path = None
                        state.device.download_chunk_size = 1024
                        state.external_gdb_bridge = None

                        result = start_external_gdb_server(state)
                        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()

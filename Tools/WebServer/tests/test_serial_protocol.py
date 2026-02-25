#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serial protocol tests
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.serial_protocol import FPBProtocol, Platform


class TestFPBProtocolWakeupShell(unittest.TestCase):
    """Test wakeup_shell functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.device = MagicMock()
        self.device.ser = MagicMock()
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 5000
        self.protocol = FPBProtocol(self.device)

    def test_wakeup_shell_default_count(self):
        """Test wakeup_shell with default count (3)"""
        self.protocol.wakeup_shell(cnt=3)

        # Should write newline 3 times
        self.assertEqual(self.device.ser.write.call_count, 3)
        self.device.ser.write.assert_called_with(b"\n")
        self.assertEqual(self.device.ser.flush.call_count, 3)

    def test_wakeup_shell_custom_count(self):
        """Test wakeup_shell with custom count via parameter"""
        self.protocol.wakeup_shell(cnt=5)

        self.assertEqual(self.device.ser.write.call_count, 5)
        self.device.ser.write.assert_called_with(b"\n")

    def test_wakeup_shell_zero_count(self):
        """Test wakeup_shell with zero count (disabled)"""
        self.protocol.wakeup_shell(cnt=0)

        self.device.ser.write.assert_not_called()

    def test_wakeup_shell_explicit_count_parameter(self):
        """Test wakeup_shell with explicit cnt parameter"""
        self.device.wakeup_shell_cnt = 10  # Should be ignored

        self.protocol.wakeup_shell(cnt=2)

        self.assertEqual(self.device.ser.write.call_count, 2)

    def test_enter_fl_mode_calls_wakeup_shell(self):
        """Test that enter_fl_mode calls wakeup_shell"""
        self.device.wakeup_shell_cnt = 3
        self.device.serial_echo_enabled = False
        self.device.ser.in_waiting = 0
        self.device.ser.read.return_value = b"fl>"

        # Mock in_waiting to return data after some iterations
        in_waiting_values = [0, 0, 3]
        self.device.ser.in_waiting = 0

        def in_waiting_side_effect():
            if in_waiting_values:
                return in_waiting_values.pop(0)
            return 3

        type(self.device.ser).in_waiting = property(
            lambda self: in_waiting_side_effect()
        )
        self.device.ser.read.return_value = b"fl>"

        with patch("time.sleep"):
            with patch("time.time") as mock_time:
                # Simulate time progression
                mock_time.side_effect = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
                self.protocol.enter_fl_mode(timeout=0.5)

        # Check that newlines were sent (wakeup_shell)
        write_calls = self.device.ser.write.call_args_list
        newline_calls = [c for c in write_calls if c == call(b"\n")]
        self.assertEqual(len(newline_calls), 3)


class TestFPBProtocolPlatform(unittest.TestCase):
    """Test platform detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.device = MagicMock()
        self.device.ser = MagicMock()
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 5000
        self.device.serial_echo_enabled = False
        self.device.wakeup_shell_cnt = 3
        self.protocol = FPBProtocol(self.device)

    def test_initial_platform_unknown(self):
        """Test initial platform is unknown"""
        self.assertEqual(self.protocol.get_platform(), Platform.UNKNOWN)

    def test_platform_nuttx_detected(self):
        """Test NuttX platform detection"""
        self.device.ser.in_waiting = 3
        self.device.ser.read.return_value = b"fl>"

        with patch("time.sleep"):
            with patch("time.time") as mock_time:
                mock_time.side_effect = [0, 0.1, 0.6]
                self.protocol.enter_fl_mode(timeout=0.5)

        self.assertEqual(self.protocol.get_platform(), Platform.NUTTX)

    def test_platform_bare_metal_detected(self):
        """Test bare metal platform detection"""
        self.device.ser.in_waiting = 3
        self.device.ser.read.return_value = b"[FLOK] pong"

        with patch("time.sleep"):
            with patch("time.time") as mock_time:
                mock_time.side_effect = [0, 0.1, 0.6]
                self.protocol.enter_fl_mode(timeout=0.5)

        self.assertEqual(self.protocol.get_platform(), Platform.BARE_METAL)


class TestFPBProtocolParseResponse(unittest.TestCase):
    """Test response parsing"""

    def setUp(self):
        """Set up test fixtures"""
        self.device = MagicMock()
        self.protocol = FPBProtocol(self.device)

    def test_parse_flok_response(self):
        """Test parsing [FLOK] response"""
        resp = "[FLOK] success message"
        result = self.protocol.parse_response(resp)

        self.assertTrue(result["ok"])
        self.assertEqual(result["msg"], "success message")

    def test_parse_flerr_response(self):
        """Test parsing [FLERR] response"""
        resp = "[FLERR] error message"
        result = self.protocol.parse_response(resp)

        self.assertFalse(result["ok"])
        self.assertEqual(result["msg"], "error message")

    def test_parse_multiline_response(self):
        """Test parsing multiline response"""
        resp = "some output\nmore output\n[FLOK] done"
        result = self.protocol.parse_response(resp)

        self.assertTrue(result["ok"])
        self.assertEqual(result["msg"], "done")

    def test_parse_response_with_ansi_codes(self):
        """Test parsing response with ANSI escape codes"""
        resp = "\x1b[32m[FLOK]\x1b[0m success"
        result = self.protocol.parse_response(resp)

        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()

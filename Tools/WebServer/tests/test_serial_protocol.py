#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serial Protocol module tests
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.serial_protocol import FPBProtocol  # noqa: E402


class TestFPBProtocolInit(unittest.TestCase):
    """FPBProtocol initialization tests"""

    def test_init_defaults(self):
        """Test default initialization"""
        device = Mock()
        protocol = FPBProtocol(device)

        self.assertEqual(protocol._in_fl_mode, False)
        self.assertEqual(protocol._platform, "unknown")
        self.assertEqual(protocol.device, device)

    def test_get_platform(self):
        """Test get_platform returns current platform"""
        device = Mock()
        protocol = FPBProtocol(device)

        self.assertEqual(protocol.get_platform(), "unknown")

        protocol._platform = "nuttx"
        self.assertEqual(protocol.get_platform(), "nuttx")


class TestEnterFlMode(unittest.TestCase):
    """enter_fl_mode tests"""

    def test_no_serial_connection(self):
        """Test returns False when no serial connection"""
        device = Mock()
        device.ser = None
        protocol = FPBProtocol(device)

        result = protocol.enter_fl_mode()

        self.assertFalse(result)
        self.assertFalse(protocol._in_fl_mode)

    def test_already_in_fl_mode(self):
        """Test returns True immediately if already in fl mode"""
        device = Mock()
        device.ser = Mock()
        protocol = FPBProtocol(device)
        protocol._in_fl_mode = True

        result = protocol.enter_fl_mode()

        self.assertTrue(result)
        # Serial should not be accessed
        device.ser.write.assert_not_called()

    def test_detect_nuttx_fl_prompt(self):
        """Test detecting NuttX platform via fl> prompt"""
        device = Mock()
        device.ser = Mock()
        device.ser.in_waiting = 10
        device.ser.read.return_value = b"fl>\n"

        protocol = FPBProtocol(device)

        result = protocol.enter_fl_mode(timeout=0.1)

        self.assertTrue(result)
        self.assertTrue(protocol._in_fl_mode)
        self.assertEqual(protocol._platform, "nuttx")

    def test_detect_bare_metal(self):
        """Test detecting bare-metal platform"""
        device = Mock()
        device.ser = Mock()
        device.ser.in_waiting = 0  # No response

        protocol = FPBProtocol(device)

        result = protocol.enter_fl_mode(timeout=0.05)

        self.assertFalse(result)
        self.assertFalse(protocol._in_fl_mode)
        self.assertEqual(protocol._platform, "bare-metal")


class TestPlatformCaching(unittest.TestCase):
    """Platform detection caching tests"""

    def test_platform_not_reset_on_reentry(self):
        """Test platform is not reset when re-entering fl mode"""
        device = Mock()
        device.ser = Mock()
        device.ser.in_waiting = 10
        device.ser.read.return_value = b"fl>\n"

        protocol = FPBProtocol(device)

        # First entry - should detect NuttX
        protocol.enter_fl_mode(timeout=0.1)
        self.assertEqual(protocol._platform, "nuttx")

        # Exit fl mode
        protocol._in_fl_mode = False

        # Second entry - platform should remain "nuttx"
        protocol.enter_fl_mode(timeout=0.1)
        self.assertEqual(protocol._platform, "nuttx")

    def test_platform_not_overwritten_to_bare_metal(self):
        """Test platform is not overwritten to bare-metal once set to nuttx"""
        device = Mock()
        device.ser = Mock()

        protocol = FPBProtocol(device)

        # Simulate first successful detection
        protocol._platform = "nuttx"

        # Simulate failed fl mode entry (no response)
        device.ser.in_waiting = 0
        result = protocol.enter_fl_mode(timeout=0.05)

        # Should fail but platform should NOT be changed from nuttx
        self.assertFalse(result)
        self.assertEqual(protocol._platform, "nuttx")

    def test_platform_set_to_bare_metal_only_when_unknown(self):
        """Test bare-metal is only set when platform is unknown"""
        device = Mock()
        device.ser = Mock()
        device.ser.in_waiting = 0

        protocol = FPBProtocol(device)
        self.assertEqual(protocol._platform, "unknown")

        # First failed entry - should set to bare-metal
        protocol.enter_fl_mode(timeout=0.05)
        self.assertEqual(protocol._platform, "bare-metal")

        # Reset to unknown
        protocol._platform = "unknown"

        # Second failed entry - should set to bare-metal again
        protocol.enter_fl_mode(timeout=0.05)
        self.assertEqual(protocol._platform, "bare-metal")

    @patch("core.serial_protocol.logger")
    def test_detection_log_only_on_first_detection(self, mock_logger):
        """Test 'Detected NuttX platform' is logged only on first detection"""
        device = Mock()
        device.ser = Mock()
        device.ser.in_waiting = 10
        device.ser.read.return_value = b"fl>\n"

        protocol = FPBProtocol(device)

        # First entry - should log
        protocol.enter_fl_mode(timeout=0.1)
        info_calls_after_first = mock_logger.info.call_count

        # Exit and re-enter
        protocol._in_fl_mode = False
        protocol.enter_fl_mode(timeout=0.1)
        info_calls_after_second = mock_logger.info.call_count

        # Should NOT have additional "Detected NuttX" log
        self.assertEqual(info_calls_after_first, info_calls_after_second)


class TestExitFlMode(unittest.TestCase):
    """exit_fl_mode tests"""

    def test_not_in_fl_mode(self):
        """Test returns True when not in fl mode"""
        device = Mock()
        protocol = FPBProtocol(device)
        protocol._in_fl_mode = False

        result = protocol.exit_fl_mode()

        self.assertTrue(result)

    def test_no_serial_connection(self):
        """Test returns False when no serial connection"""
        device = Mock()
        device.ser = None
        protocol = FPBProtocol(device)
        protocol._in_fl_mode = True

        result = protocol.exit_fl_mode()

        self.assertFalse(result)

    def test_exit_success(self):
        """Test successful exit"""
        device = Mock()
        device.ser = Mock()
        protocol = FPBProtocol(device)
        protocol._in_fl_mode = True

        result = protocol.exit_fl_mode()

        self.assertTrue(result)
        self.assertFalse(protocol._in_fl_mode)
        device.ser.write.assert_called_with(b"exit\n")

    def test_exit_does_not_reset_platform(self):
        """Test exit does not reset platform"""
        device = Mock()
        device.ser = Mock()
        protocol = FPBProtocol(device)
        protocol._in_fl_mode = True
        protocol._platform = "nuttx"

        protocol.exit_fl_mode()

        # Platform should remain nuttx
        self.assertEqual(protocol._platform, "nuttx")


if __name__ == "__main__":
    unittest.main()

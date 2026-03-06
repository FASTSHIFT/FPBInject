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


class TestParseReadResponse(unittest.TestCase):
    """Test _parse_read_response method."""

    def setUp(self):
        self.device = MagicMock()
        self.protocol = FPBProtocol(self.device)

    def test_valid_response(self):
        """Parse valid READ response with base64 + CRC."""
        import base64
        from utils.crc import crc16

        raw = b"\x01\x02\x03\x04"
        b64 = base64.b64encode(raw).decode()
        crc = crc16(raw)
        resp = f"[FLOK] READ 4 bytes crc=0x{crc:04X} data={b64}"

        result = self.protocol._parse_read_response(resp)
        self.assertEqual(result, raw)

    def test_crc_mismatch(self):
        """Return None on CRC mismatch."""
        import base64

        raw = b"\x01\x02\x03\x04"
        b64 = base64.b64encode(raw).decode()
        resp = f"[FLOK] READ 4 bytes crc=0xFFFF data={b64}"

        result = self.protocol._parse_read_response(resp)
        self.assertIsNone(result)

    def test_length_mismatch(self):
        """Return None on length mismatch."""
        import base64

        raw = b"\x01\x02"
        b64 = base64.b64encode(raw).decode()
        resp = f"[FLOK] READ 99 bytes crc=0x0000 data={b64}"

        result = self.protocol._parse_read_response(resp)
        self.assertIsNone(result)

    def test_no_match(self):
        """Return None for non-READ response."""
        result = self.protocol._parse_read_response("[FLERR] Read failed")
        self.assertIsNone(result)

    def test_invalid_base64(self):
        """Return None for invalid base64."""
        resp = "[FLOK] READ 4 bytes crc=0x1234 data=!!!invalid!!!"
        result = self.protocol._parse_read_response(resp)
        self.assertIsNone(result)


class TestReadMemory(unittest.TestCase):
    """Test read_memory method."""

    def setUp(self):
        self.device = MagicMock()
        self.device.chunk_size = 128
        self.protocol = FPBProtocol(self.device)

    def test_single_chunk(self):
        """Read data that fits in one chunk."""
        import base64
        from utils.crc import crc16

        raw = b"\xaa" * 16
        b64 = base64.b64encode(raw).decode()
        crc = crc16(raw)
        self.protocol.send_cmd = MagicMock(
            return_value=f"[FLOK] READ 16 bytes crc=0x{crc:04X} data={b64}"
        )

        data, msg = self.protocol.read_memory(0x20000000, 16)
        self.assertEqual(data, raw)
        self.assertIn("OK", msg)

    def test_multi_chunk(self):
        """Read data spanning multiple chunks."""
        import base64
        from utils.crc import crc16

        self.device.chunk_size = 4

        def mock_send(cmd, timeout=0.5):
            # Extract len from command
            import re

            m = re.search(r"--len (\d+)", cmd)
            n = int(m.group(1))
            chunk = b"\xbb" * n
            b64 = base64.b64encode(chunk).decode()
            crc = crc16(chunk)
            return f"[FLOK] READ {n} bytes crc=0x{crc:04X} data={b64}"

        self.protocol.send_cmd = MagicMock(side_effect=mock_send)

        data, msg = self.protocol.read_memory(0x20000000, 10)
        self.assertEqual(len(data), 10)
        self.assertEqual(data, b"\xbb" * 10)
        # 10 bytes / 4 chunk = 3 calls
        self.assertEqual(self.protocol.send_cmd.call_count, 3)

    def test_read_failure(self):
        """Return None on read failure."""
        self.protocol.send_cmd = MagicMock(return_value="[FLERR] Read failed")

        data, msg = self.protocol.read_memory(0x20000000, 16)
        self.assertIsNone(data)
        self.assertIn("failed", msg.lower())

    def test_read_exception(self):
        """Return None on exception."""
        self.protocol.send_cmd = MagicMock(side_effect=Exception("Timeout"))

        data, msg = self.protocol.read_memory(0x20000000, 16)
        self.assertIsNone(data)
        self.assertIn("Timeout", msg)


class TestWriteMemory(unittest.TestCase):
    """Test write_memory method."""

    def setUp(self):
        self.device = MagicMock()
        self.device.chunk_size = 128
        self.protocol = FPBProtocol(self.device)

    def test_single_chunk(self):
        """Write data that fits in one chunk."""
        self.protocol.send_cmd = MagicMock(
            return_value="[FLOK] WRITE 4 bytes to 0x20000000"
        )

        ok, msg = self.protocol.write_memory(0x20000000, b"\x01\x02\x03\x04")
        self.assertTrue(ok)
        self.assertIn("OK", msg)
        self.protocol.send_cmd.assert_called_once()

    def test_multi_chunk(self):
        """Write data spanning multiple chunks."""
        self.device.chunk_size = 4
        self.protocol.send_cmd = MagicMock(return_value="[FLOK] WRITE 4 bytes")

        ok, msg = self.protocol.write_memory(0x20000000, b"\xaa" * 10)
        self.assertTrue(ok)
        self.assertEqual(self.protocol.send_cmd.call_count, 3)

    def test_write_failure(self):
        """Return False on write failure."""
        self.protocol.send_cmd = MagicMock(return_value="[FLERR] Write error")

        ok, msg = self.protocol.write_memory(0x20000000, b"\x01\x02")
        self.assertFalse(ok)
        self.assertIn("failed", msg.lower())

    def test_write_exception(self):
        """Return False on exception."""
        self.protocol.send_cmd = MagicMock(side_effect=Exception("Serial error"))

        ok, msg = self.protocol.write_memory(0x20000000, b"\x01")
        self.assertFalse(ok)
        self.assertIn("Serial error", msg)


if __name__ == "__main__":
    unittest.main()

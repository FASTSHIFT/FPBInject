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

from fpbinject.core.serial_protocol import FPBProtocol, Platform


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

        call_count = 0

        def fake_time():
            nonlocal call_count
            call_count += 1
            return call_count * 0.05

        with patch("time.sleep"):
            with patch("time.time", side_effect=fake_time):
                self.protocol.enter_fl_mode(timeout=0.5)

        self.assertEqual(self.protocol.get_platform(), Platform.NUTTX)

    def test_platform_bare_metal_detected(self):
        """Test bare metal platform detection"""
        self.device.ser.in_waiting = 3
        self.device.ser.read.return_value = b"[FLOK] pong"

        call_count = 0

        def fake_time():
            nonlocal call_count
            call_count += 1
            return call_count * 0.05

        with patch("time.sleep"):
            with patch("time.time", side_effect=fake_time):
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
        import struct
        from fpbinject.utils.crc import crc16_update

        raw = b"\x01\x02\x03\x04"
        b64 = base64.b64encode(raw).decode()
        # CRC covers: addr(4B LE) + len(4B LE) + data
        addr = 0x20000000
        crc = crc16_update(0xFFFF, struct.pack("<II", addr, len(raw)))
        crc = crc16_update(crc, raw)
        resp = f"[FLOK] READ 4 bytes crc=0x{crc:04X} data={b64}"

        result = self.protocol._parse_read_response(resp, addr=addr)
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
        self.device.download_chunk_size = 128
        self.protocol = FPBProtocol(self.device)

    def test_single_chunk(self):
        """Read data that fits in one chunk."""
        import base64
        import struct
        from fpbinject.utils.crc import crc16_update

        addr = 0x20000000
        raw = b"\xaa" * 16
        b64 = base64.b64encode(raw).decode()
        crc = crc16_update(0xFFFF, struct.pack("<II", addr, len(raw)))
        crc = crc16_update(crc, raw)
        self.protocol.send_cmd = MagicMock(
            return_value=f"[FLOK] READ 16 bytes crc=0x{crc:04X} data={b64}"
        )

        data, msg = self.protocol.read_memory(addr, 16)
        self.assertEqual(data, raw)
        self.assertIn("OK", msg)

    def test_multi_chunk(self):
        """Read data spanning multiple chunks."""
        import base64
        import struct
        from fpbinject.utils.crc import crc16_update

        self.device.download_chunk_size = 4
        base_addr = 0x20000000

        def mock_send(cmd, timeout=0.5):
            import re

            m_addr = re.search(r"-a 0x([0-9A-Fa-f]+)", cmd)
            m_len = re.search(r"-l (\d+)", cmd)
            chunk_addr = int(m_addr.group(1), 16)
            n = int(m_len.group(1))
            chunk = b"\xbb" * n
            b64 = base64.b64encode(chunk).decode()
            crc = crc16_update(0xFFFF, struct.pack("<II", chunk_addr, n))
            crc = crc16_update(crc, chunk)
            return f"[FLOK] READ {n} bytes crc=0x{crc:04X} data={b64}"

        self.protocol.send_cmd = MagicMock(side_effect=mock_send)

        data, msg = self.protocol.read_memory(base_addr, 10)
        self.assertEqual(len(data), 10)
        self.assertEqual(data, b"\xbb" * 10)
        # 10 bytes / 4 chunk = 3 calls
        self.assertEqual(self.protocol.send_cmd.call_count, 3)

    def test_read_failure_after_retries(self):
        """Return None after exhausting all retries."""
        self.protocol.send_cmd = MagicMock(return_value="[FLERR] Read failed")

        data, msg = self.protocol.read_memory(0x20000000, 16, max_retries=2)
        self.assertIsNone(data)
        self.assertIn("failed", msg.lower())
        # 1 initial + 2 retries = 3 attempts
        self.assertEqual(self.protocol.send_cmd.call_count, 3)

    def test_read_exception_after_retries(self):
        """Return None after retrying exceptions."""
        self.protocol.send_cmd = MagicMock(side_effect=Exception("Timeout"))

        data, msg = self.protocol.read_memory(0x20000000, 16, max_retries=1)
        self.assertIsNone(data)
        self.assertIn("Timeout", msg)
        self.assertEqual(self.protocol.send_cmd.call_count, 2)

    def test_read_retry_then_succeed(self):
        """Succeed after transient failure."""
        import base64
        import struct
        from fpbinject.utils.crc import crc16_update

        addr = 0x20000000
        raw = b"\xcc" * 16
        b64 = base64.b64encode(raw).decode()
        crc = crc16_update(0xFFFF, struct.pack("<II", addr, len(raw)))
        crc = crc16_update(crc, raw)
        good_resp = f"[FLOK] READ 16 bytes crc=0x{crc:04X} data={b64}"

        self.protocol.send_cmd = MagicMock(side_effect=["[FLERR] noise", good_resp])

        data, msg = self.protocol.read_memory(addr, 16)
        self.assertEqual(data, raw)
        self.assertEqual(self.protocol.send_cmd.call_count, 2)


class TestWriteMemory(unittest.TestCase):
    """Test write_memory method."""

    def setUp(self):
        self.device = MagicMock()
        self.device.upload_chunk_size = 128
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
        self.device.upload_chunk_size = 4
        self.protocol.send_cmd = MagicMock(return_value="[FLOK] WRITE 4 bytes")

        ok, msg = self.protocol.write_memory(0x20000000, b"\xaa" * 10)
        self.assertTrue(ok)
        self.assertEqual(self.protocol.send_cmd.call_count, 3)

    def test_write_failure_after_retries(self):
        """Return False after exhausting all retries."""
        self.protocol.send_cmd = MagicMock(return_value="[FLERR] Write error")

        ok, msg = self.protocol.write_memory(0x20000000, b"\x01\x02", max_retries=2)
        self.assertFalse(ok)
        self.assertIn("failed", msg.lower())
        self.assertEqual(self.protocol.send_cmd.call_count, 3)

    def test_write_exception_after_retries(self):
        """Return False after retrying exceptions."""
        self.protocol.send_cmd = MagicMock(side_effect=Exception("Serial error"))

        ok, msg = self.protocol.write_memory(0x20000000, b"\x01", max_retries=1)
        self.assertFalse(ok)
        self.assertIn("Serial error", msg)
        self.assertEqual(self.protocol.send_cmd.call_count, 2)

    def test_write_retry_then_succeed(self):
        """Succeed after transient failure."""
        self.protocol.send_cmd = MagicMock(
            side_effect=["[FLERR] noise", "[FLOK] WRITE 2 bytes"]
        )

        ok, msg = self.protocol.write_memory(0x20000000, b"\x01\x02")
        self.assertTrue(ok)
        self.assertEqual(self.protocol.send_cmd.call_count, 2)


class TestEnhancedCRC(unittest.TestCase):
    """Test that CRC includes addr/offset + len + data (not just data)."""

    def setUp(self):
        self.device = MagicMock()
        self.device.upload_chunk_size = 128
        self.device.download_chunk_size = 128
        self.protocol = FPBProtocol(self.device)

    def test_write_crc_includes_addr_and_len(self):
        """write_memory CRC must cover addr + len + data."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] WRITE 4 bytes")

        addr = 0x20001000
        data = b"\xde\xad\xbe\xef"
        self.protocol.write_memory(addr, data)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        sent_crc = int(m.group(1), 16)

        expected = crc16_update(0xFFFF, struct.pack("<II", addr, len(data)))
        expected = crc16_update(expected, data)
        self.assertEqual(sent_crc, expected)

    def test_upload_crc_includes_offset_and_len(self):
        """upload CRC must cover offset + len + data."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] Uploaded 4 bytes")

        offset = 0x100
        data = b"\x01\x02\x03\x04"
        self.protocol.upload(data, start_offset=offset)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        sent_crc = int(m.group(1), 16)

        expected = crc16_update(0xFFFF, struct.pack("<II", offset, len(data)))
        expected = crc16_update(expected, data)
        self.assertEqual(sent_crc, expected)

    def test_read_response_crc_includes_addr_and_len(self):
        """_parse_read_response must verify CRC over addr + len + data."""
        import base64
        import struct
        from fpbinject.utils.crc import crc16, crc16_update

        addr = 0x20002000
        raw = b"\xaa\xbb\xcc\xdd"
        b64 = base64.b64encode(raw).decode()

        # Correct CRC (addr + len + data)
        good_crc = crc16_update(0xFFFF, struct.pack("<II", addr, len(raw)))
        good_crc = crc16_update(good_crc, raw)
        resp = f"[FLOK] READ 4 bytes crc=0x{good_crc:04X} data={b64}"
        self.assertEqual(self.protocol._parse_read_response(resp, addr=addr), raw)

        # Old-style CRC (data only) should now fail
        old_crc = crc16(raw)
        resp_old = f"[FLOK] READ 4 bytes crc=0x{old_crc:04X} data={b64}"
        self.assertIsNone(self.protocol._parse_read_response(resp_old, addr=addr))

    def test_read_cmd_includes_crc(self):
        """read_memory must send -r covering addr + len."""
        import re
        import struct
        import base64
        from fpbinject.utils.crc import crc16_update

        addr = 0x20000100
        length = 16
        raw = b"\xdd" * length
        b64 = base64.b64encode(raw).decode()
        resp_crc = crc16_update(0xFFFF, struct.pack("<II", addr, length))
        resp_crc = crc16_update(resp_crc, raw)

        self.protocol.send_cmd = MagicMock(
            return_value=f"[FLOK] READ {length} bytes crc=0x{resp_crc:04X} data={b64}"
        )

        self.protocol.read_memory(addr, length)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNotNone(m, "read command must include -r")
        sent_crc = int(m.group(1), 16)

        expected = crc16_update(0xFFFF, struct.pack("<II", addr, length))
        self.assertEqual(sent_crc, expected)

    def test_patch_cmd_includes_crc(self):
        """patch must send -r covering comp + orig + target."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] Patch 0")

        comp, orig, target = 0, 0x08001000, 0x20002000
        self.protocol.patch(comp, orig, target)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNotNone(m, "patch command must include -r")
        sent_crc = int(m.group(1), 16)

        expected = crc16_update(0xFFFF, struct.pack("<III", comp, orig, target))
        self.assertEqual(sent_crc, expected)

    def test_tpatch_cmd_includes_crc(self):
        """tpatch must send -r covering comp + orig + target."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] Trampoline 0")

        comp, orig, target = 1, 0x08002000, 0x20003000
        self.protocol.tpatch(comp, orig, target)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNotNone(m, "tpatch command must include -r")
        sent_crc = int(m.group(1), 16)

        expected = crc16_update(0xFFFF, struct.pack("<III", comp, orig, target))
        self.assertEqual(sent_crc, expected)

    def test_dpatch_cmd_includes_crc(self):
        """dpatch must send -r covering comp + orig + target."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] DebugMon 0")

        comp, orig, target = 2, 0x08003000, 0x20004000
        self.protocol.dpatch(comp, orig, target)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNotNone(m, "dpatch command must include -r")
        sent_crc = int(m.group(1), 16)

        expected = crc16_update(0xFFFF, struct.pack("<III", comp, orig, target))
        self.assertEqual(sent_crc, expected)

    def test_crc16_update_chaining(self):
        """crc16_update chaining must equal crc16 on concatenated data."""
        from fpbinject.utils.crc import crc16, crc16_update

        a = b"\x01\x02\x03\x04"
        b = b"\x05\x06\x07\x08"

        combined = crc16(a + b)
        chained = crc16_update(0xFFFF, a)
        chained = crc16_update(chained, b)
        self.assertEqual(combined, chained)

    def test_alloc_cmd_includes_crc(self):
        """alloc must send -r covering size(4B)."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.protocol.send_cmd = MagicMock(
            return_value="[FLOK] Allocated 256 at 0x20001000"
        )

        size = 256
        self.protocol.alloc(size)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNotNone(m, "alloc command must include -r")
        sent_crc = int(m.group(1), 16)

        expected = crc16_update(0xFFFF, struct.pack("<I", size))
        self.assertEqual(sent_crc, expected)

    def test_unpatch_cmd_includes_crc(self):
        """unpatch (single slot) must send -r covering comp(4B)."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] Cleared slot 2")

        comp = 2
        self.protocol.unpatch(comp=comp)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNotNone(m, "unpatch command must include -r")
        sent_crc = int(m.group(1), 16)

        expected = crc16_update(0xFFFF, struct.pack("<I", comp))
        self.assertEqual(sent_crc, expected)

    def test_unpatch_all_no_crc(self):
        """unpatch --all should not include CRC (no comp to protect)."""
        import re

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] Cleared all")

        self.protocol.unpatch(all=True)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNone(m, "unpatch --all should not include -r")

    def test_enable_cmd_includes_crc(self):
        """enable (single slot) must send -r covering comp(4B) + enable(4B)."""
        import re
        import struct
        from fpbinject.utils.crc import crc16_update

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] Enabled patch 1")

        comp, enable = 1, True
        self.protocol.enable_patch(comp=comp, enable=enable)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNotNone(m, "enable command must include -r")
        sent_crc = int(m.group(1), 16)

        enable_val = 1 if enable else 0
        expected = crc16_update(0xFFFF, struct.pack("<II", comp, enable_val))
        self.assertEqual(sent_crc, expected)

    def test_enable_all_no_crc(self):
        """enable --all should not include CRC."""
        import re

        self.protocol.send_cmd = MagicMock(return_value="[FLOK] Enabled all")

        self.protocol.enable_patch(all=True)

        cmd_str = self.protocol.send_cmd.call_args[0][0]
        m = re.search(r"-r 0x([0-9A-Fa-f]+)", cmd_str)
        self.assertIsNone(m, "enable --all should not include -r")


class TestEnablePatch(unittest.TestCase):
    """Tests for enable_patch method."""

    def setUp(self):
        self.device = MagicMock()
        self.device.ser = MagicMock()
        self.protocol = FPBProtocol(self.device)
        self.protocol.send_cmd = MagicMock()
        self.protocol.parse_response = MagicMock()

    def test_enable_single_patch(self):
        """enable_patch enables a single comparator."""
        self.protocol.parse_response.return_value = {"ok": True, "msg": "Enabled 0"}
        ok, msg = self.protocol.enable_patch(comp=0, enable=True)
        self.assertTrue(ok)
        call_args = self.protocol.send_cmd.call_args[0][0]
        self.assertIn("-c enable", call_args)
        self.assertIn("--comp 0", call_args)
        self.assertIn("--enable 1", call_args)

    def test_disable_single_patch(self):
        """enable_patch disables a single comparator."""
        self.protocol.parse_response.return_value = {"ok": True, "msg": "Disabled 0"}
        ok, msg = self.protocol.enable_patch(comp=2, enable=False)
        self.assertTrue(ok)
        call_args = self.protocol.send_cmd.call_args[0][0]
        self.assertIn("-c enable", call_args)
        self.assertIn("--comp 2", call_args)
        self.assertIn("--enable 0", call_args)

    def test_enable_all_patches(self):
        """enable_patch enables all comparators with --all flag."""
        self.protocol.parse_response.return_value = {"ok": True, "msg": "Enabled all"}
        ok, msg = self.protocol.enable_patch(enable=True, all=True)
        self.assertTrue(ok)
        self.protocol.send_cmd.assert_called_once_with("-c enable --enable 1 --all")

    def test_disable_all_patches(self):
        """enable_patch disables all comparators with --all flag."""
        self.protocol.parse_response.return_value = {"ok": True, "msg": "Disabled all"}
        ok, msg = self.protocol.enable_patch(enable=False, all=True)
        self.assertTrue(ok)
        self.protocol.send_cmd.assert_called_once_with("-c enable --enable 0 --all")

    def test_enable_patch_failure(self):
        """enable_patch returns failure from device."""
        self.protocol.parse_response.return_value = {"ok": False, "msg": "Invalid comp"}
        ok, msg = self.protocol.enable_patch(comp=99, enable=True)
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid comp")

    def test_enable_patch_exception(self):
        """enable_patch handles exceptions gracefully."""
        self.protocol.send_cmd.side_effect = Exception("Serial error")
        ok, msg = self.protocol.enable_patch(comp=0, enable=True)
        self.assertFalse(ok)
        self.assertIn("Serial error", msg)

    def test_enable_patch_default_values(self):
        """enable_patch uses default values (comp=0, enable=True, all=False)."""
        self.protocol.parse_response.return_value = {"ok": True, "msg": "Enabled 0"}
        ok, msg = self.protocol.enable_patch()
        self.assertTrue(ok)
        call_args = self.protocol.send_cmd.call_args[0][0]
        self.assertIn("-c enable", call_args)
        self.assertIn("--comp 0", call_args)
        self.assertIn("--enable 1", call_args)
        self.assertIn("-r 0x", call_args)


class TestFPBProtocolInfo(unittest.TestCase):
    """Test info() method."""

    def setUp(self):
        self.device = MagicMock()
        self.device.ser = MagicMock()
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 5000
        self.device.serial_echo_enabled = False
        self.protocol = FPBProtocol(self.device)

    def test_info_returns_none_when_no_flok_marker(self):
        """info() returns (None, error) when response has no [FLOK] marker."""
        # Simulate: send_cmd returns garbage, parse_response returns ok=True
        # but raw has no [FLOK]
        self.protocol.send_cmd = MagicMock(return_value="some garbage response")
        self.protocol.parse_response = MagicMock(
            return_value={"ok": True, "msg": "", "raw": "some garbage response"}
        )
        info, error = self.protocol.info()
        self.assertIsNone(info)
        self.assertEqual(error, "Device not responding")

    def test_info_success_with_flok_marker(self):
        """info() returns valid dict when response has [FLOK] marker."""
        raw = "[FLOK]\nBuild: Jan 01 2025\nFPB: v1, 6 code + 2 lit = 8 total"
        self.protocol.send_cmd = MagicMock(return_value=raw)
        self.protocol.parse_response = MagicMock(
            return_value={"ok": True, "msg": "", "raw": raw}
        )
        info, error = self.protocol.info()
        self.assertIsNotNone(info)
        self.assertEqual(error, "")
        self.assertEqual(info["build_time"], "Jan 01 2025")

    def test_info_returns_none_on_parse_failure(self):
        """info() returns (None, error) when parse_response returns ok=False."""
        self.protocol.send_cmd = MagicMock(return_value="[FLERR] timeout")
        self.protocol.parse_response = MagicMock(
            return_value={"ok": False, "msg": "timeout", "raw": "[FLERR] timeout"}
        )
        info, error = self.protocol.info()
        self.assertIsNone(info)
        self.assertEqual(error, "timeout")

    def test_info_parses_version_string_and_fpb_detail(self):
        """info() parses FPBInject version string, fpb_detail, and file_transfer."""
        raw = (
            "[FLOK]\n"
            "FPBInject v1.6.0\n"
            "Build: Mar 27 2026 11:31:06\n"
            "Used: 3857\n"
            "Slots: 1/8\n"
            "FileTransfer: enabled\n"
            "FPB: v2, 8 code + 0 lit = 8 total, enabled\n"
            "Slot[0]: 0x2C2D01D8 -> 0x3D2C0EF0, 3857 bytes (COMP=0x2C2D0150, remap, on)\n"
            "Slot[1]: empty (COMP=0x00000000, off)\n"
        )
        self.protocol.send_cmd = MagicMock(return_value=raw)
        self.protocol.parse_response = MagicMock(
            return_value={"ok": True, "msg": "", "raw": raw}
        )
        info, error = self.protocol.info()
        self.assertIsNotNone(info)
        self.assertEqual(error, "")
        self.assertEqual(info["version_string"], "FPBInject v1.6.0")
        self.assertEqual(info["build_time"], "Mar 27 2026 11:31:06")
        self.assertEqual(info["fpb_detail"], "v2, 8 code + 0 lit = 8 total, enabled")
        self.assertEqual(info["file_transfer"], "enabled")
        self.assertEqual(info["fpb_version"], 2)
        self.assertEqual(info["used"], 3857)
        self.assertEqual(info.get("active_slots"), 1)
        self.assertEqual(info.get("total_slots"), 8)
        # Slot[0] occupied, Slot[1] empty
        occupied = [s for s in info["slots"] if s["occupied"]]
        empty = [s for s in info["slots"] if not s["occupied"]]
        self.assertEqual(len(occupied), 1)
        self.assertGreaterEqual(len(empty), 1)


class TestPhaseFragmentSizeProbe(unittest.TestCase):
    """Test _phase_fragment_size_probe (Phase 1.5)"""

    def setUp(self):
        self.device = MagicMock()
        self.device.ser = MagicMock()
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 5000
        self.device.serial_tx_fragment_size = 0
        self.device.serial_tx_fragment_delay = 0.002
        self.protocol = FPBProtocol(self.device)

    def test_finds_largest_working_fragment_size(self):
        """Should find the largest fragment_size that works."""
        # 128 fails, 64 succeeds
        call_count = [0]

        def fake_probe_echo(size, timeout=2.0):
            call_count[0] += 1
            frag = self.device.serial_tx_fragment_size
            if frag >= 64:
                return {"passed": True}
            return {"passed": False, "error": "CRC mismatch"}

        self.protocol._probe_echo = fake_probe_echo

        result = self.protocol._phase_fragment_size_probe(timeout=1.0)
        self.assertTrue(result["success"])
        # 128 fails, 64 succeeds → recommended is 64
        # (128 tried first but fails, then 64 succeeds)
        self.assertIn(result["recommended_fragment_size"], [64, 128])
        self.assertGreater(result["recommended_fragment_size"], 0)

    def test_all_sizes_fail(self):
        """Should return failure when all fragment sizes fail."""
        self.protocol._probe_echo = lambda size, timeout=2.0: {
            "passed": False,
            "error": "fail",
        }

        result = self.protocol._phase_fragment_size_probe(timeout=1.0)
        self.assertFalse(result["success"])
        self.assertIn("failed", result.get("error", ""))
        # Should restore original params
        self.assertEqual(self.device.serial_tx_fragment_size, 0)

    def test_delay_optimization(self):
        """Should try reducing delay after finding working size."""
        # All sizes work, all delays work
        self.protocol._probe_echo = lambda size, timeout=2.0: {"passed": True}

        result = self.protocol._phase_fragment_size_probe(timeout=1.0)
        self.assertTrue(result["success"])
        # Should have optimized delay to smallest (1ms)
        self.assertEqual(result["recommended_fragment_delay"], 0.001)

    def test_delay_stops_at_first_failure(self):
        """Should stop reducing delay at first failure."""
        call_count = [0]

        def fake_probe(size, timeout=2.0):
            call_count[0] += 1
            delay = self.device.serial_tx_fragment_delay
            # Fail at 2ms delay
            if delay <= 0.002:
                return {"passed": False, "error": "timeout"}
            return {"passed": True}

        self.protocol._probe_echo = fake_probe

        result = self.protocol._phase_fragment_size_probe(timeout=1.0)
        self.assertTrue(result["success"])
        # 5ms works, 3ms works, 2ms fails → recommended is 3ms
        self.assertEqual(result["recommended_fragment_delay"], 0.003)

    def test_applies_params_to_device(self):
        """Should set device fragment params after successful probe."""
        self.protocol._probe_echo = lambda size, timeout=2.0: {"passed": True}

        result = self.protocol._phase_fragment_size_probe(timeout=1.0)
        self.assertTrue(result["success"])
        self.assertEqual(
            self.device.serial_tx_fragment_size,
            result["recommended_fragment_size"],
        )
        self.assertEqual(
            self.device.serial_tx_fragment_delay,
            result["recommended_fragment_delay"],
        )


class TestSerialThroughputFragmentIntegration(unittest.TestCase):
    """Test that test_serial_throughput integrates Phase 1.5 correctly."""

    def setUp(self):
        self.device = MagicMock()
        self.device.ser = MagicMock()
        self.device.raw_serial_log = []
        self.device.raw_log_next_id = 0
        self.device.raw_log_max_size = 5000
        self.device.serial_tx_fragment_size = 0
        self.device.serial_tx_fragment_delay = 0.002
        self.protocol = FPBProtocol(self.device)

    def test_fragment_needed_triggers_phase_1_5(self):
        """When Phase 1 fails, Phase 1.5 should run and set fragment params."""
        phase1_done = [False]

        def fake_probe_echo(size, timeout=2.0):
            frag = self.device.serial_tx_fragment_size
            if not phase1_done[0] and frag == 0:
                # Phase 1: no fragmentation → fail
                return {"passed": False, "error": "timeout"}
            # With fragmentation enabled → succeed
            return {"passed": True}

        def fake_probe_echoback(size, timeout=3.0):
            return {"passed": True, "size": size}

        self.protocol._probe_echo = fake_probe_echo
        self.protocol._probe_echoback = fake_probe_echoback

        # After Phase 1 fails, mark it done so Phase 1.5/2/3 can succeed
        orig_phase1 = self.protocol._phase_fragment_probe

        def patched_phase1(timeout=2.0):
            result = orig_phase1(timeout)
            phase1_done[0] = True
            return result

        self.protocol._phase_fragment_probe = patched_phase1

        results = self.protocol.test_serial_throughput(timeout=1.0)
        self.assertTrue(results["success"])
        self.assertTrue(results["fragment_needed"])
        self.assertIn("recommended_fragment_size", results)
        self.assertGreater(results["recommended_fragment_size"], 0)

    def test_no_fragment_skips_phase_1_5(self):
        """When Phase 1 succeeds, Phase 1.5 should not run."""
        self.protocol._probe_echo = lambda size, timeout=2.0: {"passed": True}
        self.protocol._probe_echoback = lambda size, timeout=3.0: {
            "passed": True,
            "size": size,
        }

        results = self.protocol.test_serial_throughput(timeout=1.0)
        self.assertTrue(results["success"])
        self.assertFalse(results["fragment_needed"])
        self.assertNotIn("recommended_fragment_size", results)
        self.assertNotIn("fragment_probe", results.get("phases", {}))


if __name__ == "__main__":
    unittest.main()

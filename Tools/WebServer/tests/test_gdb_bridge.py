#!/usr/bin/env python3

"""Tests for GDB RSP Bridge (core/gdb_bridge.py)."""

import socket
import time
import unittest
from unittest.mock import MagicMock

from fpbinject.core.gdb_bridge import (
    GDBRSPBridge,
    _checksum,
    _encode_packet,
    _parse_packet,
)


class TestPacketHelpers(unittest.TestCase):
    """Test RSP packet encoding/decoding helpers."""

    def test_checksum(self):
        self.assertEqual(_checksum("OK"), (ord("O") + ord("K")) & 0xFF)
        self.assertEqual(_checksum(""), 0)
        self.assertEqual(_checksum("S05"), (ord("S") + ord("0") + ord("5")) & 0xFF)

    def test_encode_packet(self):
        pkt = _encode_packet("OK")
        cs = _checksum("OK")
        self.assertEqual(pkt, f"$OK#{cs:02x}".encode("ascii"))

    def test_encode_empty(self):
        pkt = _encode_packet("")
        self.assertEqual(pkt, b"$#00")

    def test_parse_packet_valid(self):
        data = _parse_packet(b"$OK#9a")
        self.assertEqual(data, "OK")

    def test_parse_packet_with_prefix(self):
        data = _parse_packet(b"+$S05#b8")
        self.assertEqual(data, "S05")

    def test_parse_packet_no_dollar(self):
        self.assertIsNone(_parse_packet(b"OK#9a"))

    def test_parse_packet_no_hash(self):
        self.assertIsNone(_parse_packet(b"$OK"))

    def test_parse_packet_empty_data(self):
        data = _parse_packet(b"$#00")
        self.assertEqual(data, "")


class TestGDBRSPBridge(unittest.TestCase):
    """Test GDB RSP Bridge server."""

    def setUp(self):
        self.read_fn = MagicMock(return_value=(b"\x01\x02\x03\x04", "OK"))
        self.write_fn = MagicMock(return_value=(True, "OK"))
        self.bridge = GDBRSPBridge(
            read_memory_fn=self.read_fn,
            write_memory_fn=self.write_fn,
            listen_port=0,  # auto-assign
        )

    def tearDown(self):
        self.bridge.stop()

    def test_start_stop(self):
        port = self.bridge.start()
        self.assertGreater(port, 0)
        self.assertTrue(self.bridge.is_running)
        self.bridge.stop()
        self.assertFalse(self.bridge.is_running)

    def test_port_property(self):
        port = self.bridge.start()
        self.assertEqual(self.bridge.port, port)

    def test_double_start(self):
        port1 = self.bridge.start()
        port2 = self.bridge.start()
        self.assertEqual(port1, port2)

    def test_handle_packet_query_stop(self):
        resp = self.bridge._handle_packet("?")
        self.assertEqual(resp, "S05")

    def test_handle_packet_qsupported(self):
        resp = self.bridge._handle_packet("qSupported:multiprocess+")
        self.assertIn("PacketSize=", resp)

    def test_handle_packet_qattached(self):
        resp = self.bridge._handle_packet("qAttached")
        self.assertEqual(resp, "1")

    def test_handle_packet_hg(self):
        resp = self.bridge._handle_packet("Hg0")
        self.assertEqual(resp, "OK")

    def test_handle_packet_hc(self):
        resp = self.bridge._handle_packet("Hc0")
        self.assertEqual(resp, "OK")

    def test_handle_packet_register_read(self):
        resp = self.bridge._handle_packet("g")
        # 17 registers * 4 bytes * 2 hex chars = 136
        self.assertEqual(len(resp), 17 * 4 * 2)
        self.assertTrue(all(c == "0" for c in resp))

    def test_handle_packet_register_write(self):
        resp = self.bridge._handle_packet("G" + "0" * 136)
        self.assertEqual(resp, "OK")

    def test_handle_packet_single_reg_read(self):
        resp = self.bridge._handle_packet("p0")
        self.assertEqual(len(resp), 8)

    def test_handle_packet_continue(self):
        resp = self.bridge._handle_packet("c")
        self.assertEqual(resp, "S05")

    def test_handle_packet_step(self):
        resp = self.bridge._handle_packet("s")
        self.assertEqual(resp, "S05")

    def test_handle_packet_kill(self):
        resp = self.bridge._handle_packet("k")
        self.assertIsNone(resp)

    def test_handle_packet_detach(self):
        resp = self.bridge._handle_packet("D")
        self.assertEqual(resp, "OK")

    def test_handle_packet_unknown(self):
        resp = self.bridge._handle_packet("Z0,1234,4")
        self.assertEqual(resp, "")

    def test_handle_packet_empty(self):
        resp = self.bridge._handle_packet("")
        self.assertEqual(resp, "")

    def test_handle_packet_vcont_query(self):
        resp = self.bridge._handle_packet("vCont?")
        self.assertIn("vCont", resp)

    def test_handle_packet_vcont(self):
        resp = self.bridge._handle_packet("vCont;c")
        self.assertEqual(resp, "S05")

    def test_handle_packet_thread_info(self):
        resp = self.bridge._handle_packet("qfThreadInfo")
        self.assertEqual(resp, "m1")
        resp = self.bridge._handle_packet("qsThreadInfo")
        self.assertEqual(resp, "l")

    def test_handle_packet_qc(self):
        resp = self.bridge._handle_packet("qC")
        self.assertEqual(resp, "QC1")

    def test_handle_packet_no_ack_mode(self):
        resp = self.bridge._handle_packet("QStartNoAckMode")
        self.assertEqual(resp, "OK")

    def test_handle_read_success(self):
        self.read_fn.return_value = (b"\xab\xcd\xef\x01" + b"\x00" * 124, "OK")
        resp = self.bridge._handle_read("20001000,4")
        self.assertEqual(resp, "abcdef01")
        # Cache prefetches a full 128-byte line at aligned address
        self.read_fn.assert_called_once_with(0x20001000, 128)

    def test_handle_read_failure(self):
        self.read_fn.return_value = (None, "timeout")
        resp = self.bridge._handle_read("20001000,4")
        self.assertEqual(resp, "E01")

    def test_handle_read_zero_length(self):
        resp = self.bridge._handle_read("20001000,0")
        self.assertEqual(resp, "")

    def test_handle_read_bad_format(self):
        resp = self.bridge._handle_read("bad")
        self.assertEqual(resp, "E01")

    def test_handle_read_caps_length(self):
        """Read length > 4096 should be capped."""
        self.read_fn.return_value = (b"\x00" * 4096, "OK")
        self.bridge._handle_read("20001000,2000")  # 0x2000 = 8192
        self.read_fn.assert_called_once_with(0x20001000, 4096)

    def test_handle_read_exception(self):
        self.read_fn.side_effect = Exception("serial error")
        resp = self.bridge._handle_read("20001000,4")
        self.assertEqual(resp, "E01")

    def test_handle_write_success(self):
        self.write_fn.return_value = (True, "OK")
        resp = self.bridge._handle_write("20001000,2:abcd")
        self.assertEqual(resp, "OK")
        self.write_fn.assert_called_once_with(0x20001000, b"\xab\xcd")

    def test_handle_write_failure(self):
        self.write_fn.return_value = (False, "write error")
        resp = self.bridge._handle_write("20001000,2:abcd")
        self.assertEqual(resp, "E01")

    def test_handle_write_bad_format(self):
        resp = self.bridge._handle_write("bad")
        self.assertEqual(resp, "E01")

    def test_handle_write_length_mismatch(self):
        resp = self.bridge._handle_write("20001000,4:abcd")  # 4 bytes expected, 2 given
        self.assertEqual(resp, "E01")

    def test_handle_write_exception(self):
        self.write_fn.side_effect = Exception("serial error")
        resp = self.bridge._handle_write("20001000,2:abcd")
        self.assertEqual(resp, "E01")

    def test_tcp_connection(self):
        """Test actual TCP connection and packet exchange."""
        port = self.bridge.start()

        # Connect as a GDB client
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        try:
            sock.connect(("127.0.0.1", port))

            # Send '?' query
            pkt = _encode_packet("?")
            sock.sendall(pkt)

            # Read response
            time.sleep(0.2)
            resp = sock.recv(1024)
            self.assertIn(b"S05", resp)
        finally:
            sock.close()
            time.sleep(0.1)


class TestGDBRSPBridgeMemoryPackets(unittest.TestCase):
    """Test memory read/write via full packet handling."""

    def setUp(self):
        self.read_fn = MagicMock(return_value=(b"\x41\x42", "OK"))
        self.write_fn = MagicMock(return_value=(True, "OK"))
        self.bridge = GDBRSPBridge(
            read_memory_fn=self.read_fn,
            write_memory_fn=self.write_fn,
            listen_port=0,
        )

    def test_m_packet(self):
        resp = self.bridge._handle_packet("m20001000,2")
        self.assertEqual(resp, "4142")

    def test_M_packet(self):
        resp = self.bridge._handle_packet("M20001000,2:4142")
        self.assertEqual(resp, "OK")
        self.write_fn.assert_called_once_with(0x20001000, b"\x41\x42")

    def test_X_packet_unsupported(self):
        resp = self.bridge._handle_packet("X20001000,2:\x41\x42")
        self.assertEqual(resp, "")


class TestGDBRSPBridgeMemoryRegions(unittest.TestCase):
    """Test memory region address validation."""

    def setUp(self):
        self.read_fn = MagicMock(return_value=(b"\x01\x02\x03\x04", "OK"))
        self.write_fn = MagicMock(return_value=(True, "OK"))
        self.bridge = GDBRSPBridge(
            read_memory_fn=self.read_fn,
            write_memory_fn=self.write_fn,
            listen_port=0,
        )

    def test_default_regions_allow_flash(self):
        """Flash region (0x00000000-0x20000000) should be allowed by default."""
        self.assertTrue(self.bridge._is_address_valid(0x08000000, 4))

    def test_default_regions_allow_sram(self):
        """SRAM region (0x20000000-0x40000000) should be allowed by default."""
        self.assertTrue(self.bridge._is_address_valid(0x20000000, 256))

    def test_default_regions_allow_peripherals(self):
        """Peripheral region (0x40000000-0x60000000) should be allowed by default."""
        self.assertTrue(self.bridge._is_address_valid(0x40000000, 4))

    def test_default_regions_allow_system(self):
        """System region (0xE0000000-0xF0000000) should be allowed by default."""
        self.assertTrue(self.bridge._is_address_valid(0xE000ED00, 4))

    def test_default_regions_block_invalid(self):
        """Address 0xF0000000+ should be blocked by default."""
        self.assertFalse(self.bridge._is_address_valid(0xFFFFFFFC, 4))

    def test_default_regions_block_gap(self):
        """Address in gap (0xA0000000-0xE0000000) should be blocked."""
        self.assertFalse(self.bridge._is_address_valid(0xC0000000, 4))

    def test_cross_boundary_blocked(self):
        """Read that crosses region boundary should be blocked."""
        # Ends at 0x20000004, which is in SRAM, but starts in Flash boundary
        # Actually 0x1FFFFFFC + 8 = 0x20000004, crosses Flash->SRAM
        self.assertFalse(self.bridge._is_address_valid(0x1FFFFFFC, 8))

    def test_handle_read_blocked(self):
        """Read to invalid address should return E14 without calling read_fn."""
        resp = self.bridge._handle_read("FFFFFFFC,4")
        self.assertEqual(resp, "E14")
        self.read_fn.assert_not_called()

    def test_handle_read_allowed(self):
        """Read to valid address should proceed normally."""
        resp = self.bridge._handle_read("20001000,4")
        self.assertEqual(resp, "01020304")
        self.read_fn.assert_called_once()

    def test_handle_write_blocked(self):
        """Write to invalid address should return E14 without calling write_fn."""
        resp = self.bridge._handle_write("FFFFFFFC,2:abcd")
        self.assertEqual(resp, "E14")
        self.write_fn.assert_not_called()

    def test_handle_write_allowed(self):
        """Write to valid address should proceed normally."""
        resp = self.bridge._handle_write("20001000,2:abcd")
        self.assertEqual(resp, "OK")
        self.write_fn.assert_called_once()

    def test_set_memory_regions_custom(self):
        """Custom regions should replace defaults."""
        self.bridge.set_memory_regions(
            [
                (0x20000000, 0x20010000),  # 64KB SRAM only
            ]
        )
        self.assertTrue(self.bridge._is_address_valid(0x20000000, 4))
        self.assertFalse(
            self.bridge._is_address_valid(0x08000000, 4)
        )  # Flash now blocked
        self.assertFalse(self.bridge._is_address_valid(0x20010000, 4))  # Past end

    def test_empty_regions_allow_all(self):
        """Empty region list should allow all addresses (no filtering)."""
        self.bridge.set_memory_regions([])
        self.assertTrue(self.bridge._is_address_valid(0xFFFFFFFC, 4))

    def test_m_packet_blocked_address(self):
        """Full packet path: m packet to invalid address returns E14."""
        resp = self.bridge._handle_packet("mFFFFFFFC,4")
        self.assertEqual(resp, "E14")
        self.read_fn.assert_not_called()

    def test_M_packet_blocked_address(self):
        """Full packet path: M packet to invalid address returns E14."""
        resp = self.bridge._handle_packet("MFFFFFFFC,2:abcd")
        self.assertEqual(resp, "E14")
        self.write_fn.assert_not_called()


class TestGDBRSPBridgeReadCache(unittest.TestCase):
    """Test single-shot read cache line behavior."""

    def setUp(self):
        self.read_fn = MagicMock(return_value=(bytes(range(128)), "ok"))
        self.write_fn = MagicMock(return_value=(True, "ok"))
        self.bridge = GDBRSPBridge(
            read_memory_fn=self.read_fn,
            write_memory_fn=self.write_fn,
            listen_port=0,
        )

    def test_cache_hit_same_line(self):
        """Second read within same cache line should not call device."""
        self.bridge._handle_read("20000000,4")
        self.assertEqual(self.read_fn.call_count, 1)

        self.read_fn.reset_mock()
        self.bridge._handle_read("20000010,4")
        self.read_fn.assert_not_called()

    def test_cache_returns_correct_slice(self):
        """Cached read returns the correct byte offset."""
        resp = self.bridge._handle_read("20000010,4")
        self.assertEqual(resp, "10111213")

    def test_cache_miss_different_line(self):
        """Read in a different cache line should fetch from device."""
        self.bridge._handle_read("20000000,4")
        self.bridge._handle_read("20000080,4")  # next 128B line
        self.assertEqual(self.read_fn.call_count, 2)

    def test_large_read_bypasses_cache(self):
        """Read larger than cache line goes directly to device."""
        big = b"\xbb" * 512
        self.read_fn.return_value = (big, "ok")
        self.bridge._handle_read("20000000,200")  # 512 bytes
        self.read_fn.assert_called_with(0x20000000, 512)
        self.assertIsNone(self.bridge._cache_line)

    def test_write_invalidates_cache(self):
        """Write should discard the cache line."""
        self.bridge._handle_read("20000000,4")
        self.assertIsNotNone(self.bridge._cache_line)

        self.bridge._handle_write("20000000,4:DEADBEEF")
        self.assertIsNone(self.bridge._cache_line)

    def test_non_memory_packet_invalidates_cache(self):
        """Non-read/write packets (e.g. step) should discard cache."""
        self.bridge._handle_read("20000000,4")
        self.assertIsNotNone(self.bridge._cache_line)

        self.bridge._handle_packet("s")  # step
        self.assertIsNone(self.bridge._cache_line)

    def test_failed_read_not_cached(self):
        """Failed device read should not populate cache."""
        self.read_fn.return_value = (None, "error")
        self.bridge._handle_read("20000000,4")
        self.assertIsNone(self.bridge._cache_line)


if __name__ == "__main__":
    unittest.main()

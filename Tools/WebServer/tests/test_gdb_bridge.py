#!/usr/bin/env python3

"""Tests for GDB RSP Bridge (core/gdb_bridge.py)."""

import socket
import time
import unittest
from unittest.mock import MagicMock

from core.gdb_bridge import (
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
        self.read_fn.return_value = (b"\xab\xcd\xef\x01", "OK")
        resp = self.bridge._handle_read("20001000,4")
        self.assertEqual(resp, "abcdef01")
        self.read_fn.assert_called_once_with(0x20001000, 4)

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


if __name__ == "__main__":
    unittest.main()

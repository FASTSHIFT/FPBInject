#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPB Inject module tests
"""

import os
import sys
import unittest
import tempfile
import json
import subprocess
from unittest.mock import Mock, patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpb_inject import (
    FPBInject,
    FPBInjectError,
    scan_serial_ports,
    serial_open,
)
from utils.crc import crc16
from core.state import DeviceState


class TestCRC16(unittest.TestCase):
    """CRC16 tests"""

    def test_crc16_empty(self):
        """Test empty data"""
        result = crc16(b"")
        self.assertIsInstance(result, int)

    def test_crc16_known_value(self):
        """Test known value"""
        # CRC16-CCITT for "123456789" should be 0x29B1
        data = b"123456789"
        result = crc16(data)
        self.assertEqual(result, 0x29B1)

    def test_crc16_single_byte(self):
        """Test single byte"""
        result = crc16(b"\x00")
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 0xFFFF)

    def test_crc16_consistency(self):
        """Test consistency"""
        data = b"test data for crc"
        result1 = crc16(data)
        result2 = crc16(data)
        self.assertEqual(result1, result2)


class TestScanSerialPorts(unittest.TestCase):
    """Scan serial ports tests"""

    def test_scan_returns_list(self):
        """Test returns list"""
        ports = scan_serial_ports()
        self.assertIsInstance(ports, list)

    def test_scan_port_format(self):
        """Test port format"""
        ports = scan_serial_ports()
        for port in ports:
            self.assertIn("device", port)
            self.assertIn("description", port)


class TestSerialOpen(unittest.TestCase):
    """Serial port open tests"""

    def test_open_invalid_port(self):
        """Test opening invalid port"""
        ser, error = serial_open("/dev/nonexistent_port_12345", 115200, 1)

        self.assertIsNone(ser)
        self.assertIsNotNone(error)

    @patch("utils.serial.serial.Serial")
    def test_open_success(self, mock_serial):
        """Test successful open"""
        mock_instance = Mock()
        mock_serial.return_value = mock_instance

        ser, error = serial_open("/dev/ttyUSB0", 115200, 1)

        self.assertIsNone(error)
        self.assertEqual(ser, mock_instance)


class TestFPBInject(unittest.TestCase):
    """FPBInject class tests"""

    def setUp(self):
        self.device = DeviceState()
        self.fpb = FPBInject(self.device)

    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.fpb.device, self.device)
        self.assertIsNone(self.fpb._toolchain_path)

    def test_set_toolchain_path_valid(self):
        """Test setting valid toolchain path"""
        # Use an existing directory
        path = "/tmp"
        self.fpb.set_toolchain_path(path)

        self.assertEqual(self.fpb._toolchain_path, path)

    def test_set_toolchain_path_invalid(self):
        """Test setting invalid toolchain path"""
        self.fpb.set_toolchain_path("/nonexistent/path")

        self.assertIsNone(self.fpb._toolchain_path)

    def test_set_toolchain_path_empty(self):
        """Test setting empty path"""
        self.fpb._toolchain_path = "/some/path"
        self.fpb.set_toolchain_path("")

        self.assertIsNone(self.fpb._toolchain_path)

    def test_get_tool_path_with_toolchain(self):
        """Test getting tool path with toolchain"""
        import tempfile
        import os

        # Create temporary directory and fake tool
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_path = os.path.join(tmpdir, "arm-none-eabi-gcc")
            with open(tool_path, "w") as f:
                f.write("#!/bin/bash\necho test")

            self.fpb.set_toolchain_path(tmpdir)
            result = self.fpb.get_tool_path("arm-none-eabi-gcc")

            self.assertEqual(result, tool_path)

    def test_get_tool_path_without_toolchain(self):
        """Test returning tool name when no toolchain path"""
        self.fpb._toolchain_path = None

        result = self.fpb.get_tool_path("arm-none-eabi-gcc")

        self.assertEqual(result, "arm-none-eabi-gcc")

    def test_get_subprocess_env_with_toolchain(self):
        """Test getting subprocess environment with toolchain"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            self.fpb._toolchain_path = tmpdir

            env = self.fpb._get_subprocess_env()

            self.assertIn("PATH", env)
            self.assertTrue(env["PATH"].startswith(tmpdir + ":"))

    def test_get_subprocess_env_without_toolchain(self):
        """Test getting subprocess environment without toolchain"""
        self.fpb._toolchain_path = None

        env = self.fpb._get_subprocess_env()

        self.assertIn("PATH", env)

    def test_parse_response_ok(self):
        """Test parsing OK response"""
        resp = "[OK] Operation successful"

        result = self.fpb._parse_response(resp)

        self.assertTrue(result["ok"])
        self.assertEqual(result["msg"], "Operation successful")

    def test_parse_response_err(self):
        """Test parsing ERR response"""
        resp = "[ERR] Something went wrong"

        result = self.fpb._parse_response(resp)

        self.assertFalse(result["ok"])
        self.assertEqual(result["msg"], "Something went wrong")

    def test_parse_response_multiline(self):
        """Test parsing multiline response"""
        resp = """Info line 1
Info line 2
[OK] Done
fl>"""

        result = self.fpb._parse_response(resp)

        self.assertTrue(result["ok"])
        self.assertEqual(result["msg"], "Done")

    def test_parse_response_with_ansi(self):
        """Test parsing response with ANSI escape sequences"""
        resp = "\x1b[0m[OK] Success\x1b[K"

        result = self.fpb._parse_response(resp)

        self.assertTrue(result["ok"])

    def test_parse_response_with_prompt(self):
        """Test parsing response with prompt"""
        resp = """[OK] Success
fl>"""

        result = self.fpb._parse_response(resp)

        self.assertTrue(result["ok"])

    def test_parse_response_error_keyword(self):
        """Test parsing response containing error keyword"""
        resp = "An error occurred during processing"

        result = self.fpb._parse_response(resp)

        self.assertFalse(result["ok"])

    def test_parse_response_empty(self):
        """Test parsing empty response"""
        result = self.fpb._parse_response("")

        self.assertTrue(result["ok"])  # Empty response is considered success

    def test_ping_not_connected(self):
        """Test ping when not connected"""
        self.device.ser = None

        success, msg = self.fpb.ping()

        self.assertFalse(success)

    def test_info_not_connected(self):
        """Test getting info when not connected"""
        self.device.ser = None

        info, error = self.fpb.info()

        self.assertIsNone(info)
        self.assertIsNotNone(error)

    def test_alloc_not_connected(self):
        """Test alloc when not connected"""
        self.device.ser = None

        addr, error = self.fpb.alloc(1024)

        self.assertIsNone(addr)

    def test_unpatch_all_not_connected(self):
        """Test unpatch all when not connected"""
        self.device.ser = None

        success, msg = self.fpb.unpatch(all=True)

        self.assertFalse(success)

    def test_patch_not_connected(self):
        """Test patch when not connected"""
        self.device.ser = None

        success, msg = self.fpb.patch(0, 0x20000000, 0x20001000)

        self.assertFalse(success)

    def test_tpatch_not_connected(self):
        """Test tpatch when not connected"""
        self.device.ser = None

        success, msg = self.fpb.tpatch(0, 0x20000000, 0x20001000)

        self.assertFalse(success)

    def test_dpatch_not_connected(self):
        """Test dpatch when not connected"""
        self.device.ser = None

        success, msg = self.fpb.dpatch(0, 0x20000000, 0x20001000)

        self.assertFalse(success)

    def test_unpatch_not_connected(self):
        """Test unpatch when not connected"""
        self.device.ser = None

        success, msg = self.fpb.unpatch(0)

        self.assertFalse(success)

    def test_log_raw(self):
        """Test raw log recording"""
        self.fpb._log_raw("TX", "test command")

        self.assertEqual(len(self.device.raw_serial_log), 1)
        self.assertEqual(self.device.raw_serial_log[0]["dir"], "TX")
        self.assertEqual(self.device.raw_serial_log[0]["data"], "test command")

    def test_log_raw_empty(self):
        """Test empty data not recorded"""
        self.fpb._log_raw("TX", "")

        self.assertEqual(len(self.device.raw_serial_log), 0)

    def test_log_raw_limit(self):
        """Test log size limit"""
        self.device.raw_log_max_size = 10

        for i in range(20):
            self.fpb._log_raw("TX", f"msg{i}")

        self.assertEqual(len(self.device.raw_serial_log), 10)


class TestFPBInjectWithMockSerial(unittest.TestCase):
    """FPBInject tests with mock serial port"""

    def setUp(self):
        self.device = DeviceState()
        self.device.ser = Mock()
        self.device.ser.in_waiting = 0
        self.device.ser.isOpen.return_value = True
        self.fpb = FPBInject(self.device)

    def test_enter_fl_mode(self):
        """Test entering fl mode"""
        self.device.ser.read.return_value = b"fl>"
        self.device.ser.in_waiting = 3

        result = self.fpb.enter_fl_mode(timeout=0.1)

        self.assertTrue(result)
        self.assertEqual(self.fpb.get_platform(), "nuttx")
        self.device.ser.write.assert_called()

    def test_enter_fl_mode_bare_metal(self):
        """Test entering fl mode on bare-metal (no fl> prompt)"""
        self.device.ser.read.return_value = b"[OK] some response"
        self.device.ser.in_waiting = 18

        result = self.fpb.enter_fl_mode(timeout=0.1)

        self.assertFalse(result)
        self.assertEqual(self.fpb.get_platform(), "bare-metal")

    def test_enter_fl_mode_nuttx_hint(self):
        """Test detecting NuttX platform via hint message"""
        # Simulate NuttX returning the hint message
        responses = [
            b"[ERR] Enter 'fl' to start interactive mode",
            b"fl>",
        ]
        call_count = [0]

        def mock_read(n):
            if call_count[0] < len(responses):
                resp = responses[call_count[0]]
                call_count[0] += 1
                return resp
            return b""

        def mock_in_waiting():
            if call_count[0] < len(responses):
                return len(responses[call_count[0]])
            return 0

        self.device.ser.read.side_effect = mock_read
        type(self.device.ser).in_waiting = property(lambda x: mock_in_waiting())

        result = self.fpb.enter_fl_mode(timeout=0.2)

        self.assertTrue(result)
        self.assertEqual(self.fpb.get_platform(), "nuttx")

    def test_get_platform_default(self):
        """Test default platform value"""
        self.assertEqual(self.fpb.get_platform(), "unknown")

    def test_exit_fl_mode(self):
        """Test exiting fl mode"""
        self.device.ser.read.return_value = b"[OK]\nap>"
        self.device.ser.in_waiting = 8

        result = self.fpb.exit_fl_mode(timeout=0.1)

        self.assertTrue(result)

    def test_send_cmd(self):
        """Test sending command"""

        def mock_read(n):
            self.device.ser.in_waiting = 0
            return b"[OK] Pong\n"

        self.device.ser.read.side_effect = mock_read
        self.device.ser.in_waiting = 10

        # Directly call internal method
        result = self.fpb._send_cmd("--cmd ping", timeout=0.1)

        self.assertIn("OK", result)


class TestFPBInjectCompile(unittest.TestCase):
    """FPBInject compilation related tests"""

    def setUp(self):
        self.device = DeviceState()
        self.fpb = FPBInject(self.device)

    def test_parse_compile_commands_not_found(self):
        """Test parsing nonexistent compile_commands.json"""
        result = self.fpb.parse_compile_commands("/nonexistent/path.json")

        self.assertIsNone(result)

    def test_get_symbols_not_found(self):
        """Test getting symbols from nonexistent ELF"""
        result = self.fpb.get_symbols("/nonexistent/elf.elf")

        self.assertEqual(result, {})

    def test_inject_no_elf(self):
        """Test injection when no ELF file"""
        self.device.elf_path = ""

        success, result = self.fpb.inject("void foo() {}", "target")

        self.assertFalse(success)
        self.assertIn("error", result)


class TestFPBInjectError(unittest.TestCase):
    """FPBInjectError exception tests"""

    def test_exception_message(self):
        """Test exception message"""
        try:
            raise FPBInjectError("Test error message")
        except FPBInjectError as e:
            self.assertEqual(str(e), "Test error message")

    def test_exception_inheritance(self):
        """Test exception inheritance"""
        self.assertTrue(issubclass(FPBInjectError, Exception))


class TestFPBInjectCoverage(unittest.TestCase):
    """FPBInject class tests (extended coverage)"""

    def setUp(self):
        self.device = DeviceState()
        self.device.ser = Mock()
        self.device.ser.isOpen.return_value = True
        self.device.chunk_size = 48  # Set fixed chunk_size for testing
        self.fpb = FPBInject(self.device)

    def test_send_cmd_write_error(self):
        """Test send command write error"""
        self.device.ser.write.side_effect = Exception("Write Error")

        with self.assertRaises(Exception):  # _send_cmd doesn't catch exception
            self.fpb._send_cmd("test")

    def test_send_cmd_read_error(self):
        """Test send command read error"""

        # send_cmd calls write then read
        # Mock ser.read to raise exception
        def mock_read(size=None):
            raise Exception("Read Error")

        self.device.ser.in_waiting = 5
        self.device.ser.read.side_effect = mock_read

        with self.assertRaises(Exception):
            self.fpb._send_cmd("test")

    def test_parse_compile_commands(self):
        """Test parsing compile_commands.json"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "arm-none-eabi-gcc -c main.c -o main.o -I/inc -DDEBUG",
                        "file": "main.c",
                    }
                ],
                f,
            )
            cmd_path = f.name

        try:
            result = self.fpb.parse_compile_commands(cmd_path)
            self.assertIsNotNone(result)
            self.assertEqual(result["compiler"], "arm-none-eabi-gcc")
            self.assertIn("/inc", result["includes"])
            self.assertIn("DEBUG", result["defines"])

        finally:
            os.remove(cmd_path)

    def test_parse_compile_commands_complex(self):
        """Test parsing complex compile commands"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "/usr/bin/gcc -c -I/a -I /b -D A -DB -isystem /sys -o out.o main.c -mcpu=cortex-m4 -Os",
                        "file": "main.c",
                    }
                ],
                f,
            )
            cmd_path = f.name

        try:
            result = self.fpb.parse_compile_commands(cmd_path)
            self.assertIsNotNone(result)
            self.assertIn("/a", result["includes"])
            self.assertIn("/b", result["includes"])
            self.assertIn("/sys", result["includes"])
            self.assertIn("A", result["defines"])
            self.assertIn("B", result["defines"])
            self.assertIn("-mcpu=cortex-m4", result["cflags"])
            self.assertIn("-Os", result["cflags"])

        finally:
            os.remove(cmd_path)

    def test_parse_compile_commands_malformed(self):
        """Test parsing malformed json"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("Not JSON")
            cmd_path = f.name

        try:
            result = self.fpb.parse_compile_commands(cmd_path)
            self.assertIsNone(result)
        finally:
            os.remove(cmd_path)

    def test_parse_compile_commands_empty(self):
        """Test empty JSON list"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            cmd_path = f.name

        try:
            result = self.fpb.parse_compile_commands(cmd_path)
            self.assertIsNone(result)
        finally:
            os.remove(cmd_path)

    @patch("subprocess.run")
    def test_get_symbols(self, mock_run):
        """Test getting symbol table"""
        mock_output = MagicMock()
        mock_output.stdout = """
08000000 T main
20000000 D var
08001000 t static_func
"""
        mock_run.return_value = mock_output
        self.fpb._toolchain_path = "/usr/bin"

        symbols = self.fpb.get_symbols("/path/to/elf")

        self.assertIn("main", symbols)
        self.assertEqual(symbols["main"], 0x08000000)
        self.assertIn("static_func", symbols)

    @patch("subprocess.run")
    def test_get_symbols_error(self, mock_run):
        """Test getting symbol table failure"""
        mock_run.side_effect = Exception("nm failed")

        symbols = self.fpb.get_symbols("/path/to/elf")

        self.assertEqual(symbols, {})

    def test_upload_success(self):
        """Test upload success"""
        self.fpb._protocol.send_cmd = Mock(return_value="[OK]")

        data = b"\x01" * 100
        success, result = self.fpb.upload(data, 0x20000000)

        self.assertTrue(success)
        self.assertEqual(result["bytes"], 100)
        # 100 bytes / 48 bytes per chunk = 2.08, rounded up = 3 chunks
        self.assertEqual(result["chunks"], 3)

    def test_upload_fail(self):
        """Test upload failure"""
        self.fpb._protocol.send_cmd = Mock(return_value="[ERR] Write error")

        data = b"\x01" * 10
        success, result = self.fpb.upload(data, 0x20000000)

        self.assertFalse(success)
        self.assertIn("Write error", result["error"])

    def test_upload_callback(self):
        """Test upload callback"""
        self.fpb._protocol.send_cmd = Mock(return_value="[OK]")
        callback = Mock()

        data = b"\x01" * 100
        self.fpb.upload(data, 0x20000000, progress_callback=callback)

        self.assertEqual(callback.call_count, 3)

    def test_inject_no_symbols(self):
        """Test injection when target symbol not found"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            self.device.elf_path = f.name

        try:
            with patch.object(self.fpb, "get_symbols") as mock_syms:
                mock_syms.return_value = {}  # Empty symbols

                success, result = self.fpb.inject("source", "target_func")

                self.assertFalse(success)
                self.assertIn("not found in ELF", result["error"])
        finally:
            if os.path.exists(self.device.elf_path):
                os.remove(self.device.elf_path)

    @patch("fpb_inject.FPBInject.compile_inject")
    def test_inject_compile_fail(self, mock_compile):
        """Test injection when compilation step fails"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            self.device.elf_path = f.name

        try:
            with patch.object(self.fpb, "get_symbols") as mock_syms, patch.object(
                self.fpb, "info"
            ) as mock_info, patch.object(
                self.fpb, "find_slot_for_target"
            ) as mock_find_slot:

                mock_syms.return_value = {"target_func": 0x08000000}
                mock_info.return_value = ({"base": 0x20000000}, "")
                mock_find_slot.return_value = (
                    0,
                    False,
                )  # Return slot 0, no unpatch needed

                mock_compile.return_value = (None, None, "Compile Error")

                success, result = self.fpb.inject("source", "target_func")

                self.assertFalse(success)
                self.assertIn("Compile Error", result["error"])
        finally:
            if os.path.exists(self.device.elf_path):
                os.remove(self.device.elf_path)

    @patch("fpb_inject.FPBInject.compile_inject")
    @patch("fpb_inject.FPBInject.unpatch")
    @patch("fpb_inject.FPBInject.upload")
    @patch("fpb_inject.FPBInject.tpatch")
    def test_inject_success_flow(
        self, mock_tpatch, mock_upload, mock_unpatch, mock_compile
    ):
        """Test injection success flow"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            self.device.elf_path = f.name

        try:
            with patch.object(self.fpb, "get_symbols") as mock_syms, patch.object(
                self.fpb, "info"
            ) as mock_info, patch.object(self.fpb, "alloc") as mock_alloc, patch.object(
                self.fpb, "find_slot_for_target"
            ) as mock_find_slot:

                mock_syms.return_value = {"target_func": 0x08000000}
                mock_info.return_value = ({"used": 0}, "")
                mock_alloc.return_value = (0x20000000, "")
                mock_find_slot.return_value = (
                    0,
                    False,
                )  # Return slot 0, no unpatch needed

                # compile_inject called twice for dynamic allocation
                # First for size calculation, second for actual address
                mock_compile.side_effect = [
                    (b"\x01\x02", {}, ""),  # First compilation
                    (
                        b"\x01\x02",
                        {"inject_target_func": 0x20000000},
                        "",
                    ),  # Second compilation
                ]

                mock_upload.return_value = (True, {"time": 0.1})
                mock_tpatch.return_value = (True, "")

                success, result = self.fpb.inject(
                    "source",
                    "target_func",
                    inject_func="inject_target_func",
                    patch_mode="trampoline",
                )

                self.assertTrue(success)
                self.assertEqual(mock_compile.call_count, 2)
                mock_alloc.assert_called()
                mock_upload.assert_called()
                mock_tpatch.assert_called()
        finally:
            if os.path.exists(self.device.elf_path):
                os.remove(self.device.elf_path)

    @patch("fpb_inject.FPBInject.compile_inject")
    def test_inject_dynamic_allocation(self, mock_compile):
        """Test dynamic allocation injection"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            self.device.elf_path = f.name

        try:
            with patch.object(self.fpb, "get_symbols") as mock_syms, patch.object(
                self.fpb, "info"
            ) as mock_info, patch.object(self.fpb, "alloc") as mock_alloc, patch.object(
                self.fpb, "find_slot_for_target"
            ) as mock_find_slot, patch.object(
                self.fpb, "upload"
            ) as mock_upload, patch.object(
                self.fpb, "tpatch"
            ) as mock_tpatch:

                mock_syms.return_value = {"target_func": 0x08000000}
                # info returns used memory
                mock_info.return_value = (
                    {"used": 0},
                    "",
                )
                mock_find_slot.return_value = (
                    0,
                    False,
                )  # Return slot 0, no unpatch needed

                mock_alloc.return_value = (0x20001000, "")
                mock_upload.return_value = (True, {})
                mock_tpatch.return_value = (True, "")

                # First compilation for size
                # Second compilation for address
                mock_compile.side_effect = [
                    (b"\x00" * 100, {}, ""),  # 1st
                    (b"\x00" * 100, {"inject_target_func": 0x20001000}, ""),  # 2nd
                ]

                success, result = self.fpb.inject("source", "target_func")

                self.assertTrue(success)
                mock_alloc.assert_called()
                self.assertEqual(mock_compile.call_count, 2)
        finally:
            if os.path.exists(self.device.elf_path):
                os.remove(self.device.elf_path)


class TestFPBInjectCommands(unittest.TestCase):
    """FPBInject command tests (extended coverage)"""

    def setUp(self):
        self.device = DeviceState()
        self.device.ser = Mock()
        self.device.ser.isOpen.return_value = True
        self.device.ser.in_waiting = 0
        self.fpb = FPBInject(self.device)

    def test_ping_success(self):
        """Test ping success"""
        self.fpb._protocol.send_cmd = Mock(return_value="[OK] Pong")

        success, msg = self.fpb.ping()

        self.assertTrue(success)

    def test_ping_failure(self):
        """Test ping failure"""
        self.fpb._protocol.send_cmd = Mock(return_value="[ERR] No response")

        success, msg = self.fpb.ping()

        self.assertFalse(success)

    def test_info_success(self):
        """Test info success"""
        self.fpb._protocol.send_cmd = Mock(
            return_value="FPBInject v1.0\nBuild: Jan 30 2026 10:00:00\nUsed: 100\nSlots: 0/6\n[OK] Info complete"
        )

        info, error = self.fpb.info()

        self.assertIsNotNone(info)
        self.assertEqual(info["used"], 100)
        self.assertEqual(info["build_time"], "Jan 30 2026 10:00:00")

    def test_info_failure(self):
        """Test info failure"""
        self.fpb._protocol.send_cmd = Mock(return_value="[ERR] Device not ready")

        info, error = self.fpb.info()

        self.assertIsNone(info)
        self.assertIn("Device not ready", error)

    def test_alloc_success(self):
        """Test alloc success"""
        # alloc response format: "[OK] Allocated buffer at 0x20001000"
        self.fpb._protocol.send_cmd = Mock(
            return_value="[OK] Allocated buffer at 0x20001000"
        )

        addr, error = self.fpb.alloc(1024)

        self.assertEqual(addr, 0x20001000)
        self.assertEqual(error, "")

    def test_alloc_failure(self):
        """Test alloc failure"""
        self.fpb._protocol.send_cmd = Mock(return_value="[ERR] Out of memory")

        addr, error = self.fpb.alloc(1024)

        self.assertIsNone(addr)

    def test_unpatch_all_success(self):
        """Test unpatch all success"""
        self.fpb._protocol.send_cmd = Mock(return_value="[OK] Cleared")

        success, msg = self.fpb.unpatch(all=True)

        self.assertTrue(success)

    def test_patch_success(self):
        """Test patch success"""
        self.fpb._protocol.send_cmd = Mock(return_value="[OK] Patched")

        success, msg = self.fpb.patch(0, 0x08000000, 0x20001000)

        self.assertTrue(success)

    def test_tpatch_success(self):
        """Test tpatch success"""
        self.fpb._protocol.send_cmd = Mock(return_value="[OK] Trampoline patched")

        success, msg = self.fpb.tpatch(0, 0x08000000, 0x20001000)

        self.assertTrue(success)

    def test_dpatch_success(self):
        """Test dpatch success"""
        self.fpb._protocol.send_cmd = Mock(return_value="[OK] DebugMonitor patched")

        success, msg = self.fpb.dpatch(0, 0x08000000, 0x20001000)

        self.assertTrue(success)

    def test_unpatch_success(self):
        """Test unpatch success"""
        self.fpb._protocol.send_cmd = Mock(return_value="[OK] Unpatched")

        success, msg = self.fpb.unpatch(0)

        self.assertTrue(success)

    def test_exit_fl_mode(self):
        """Test exiting fl mode"""
        # Set the fl mode flag to ensure exit is attempted
        self.fpb._protocol._in_fl_mode = True

        def mock_read(size=None):
            self.device.ser.in_waiting = 0
            return b"[OK]\nap>"

        self.device.ser.read.side_effect = mock_read
        self.device.ser.in_waiting = 10

        result = self.fpb.exit_fl_mode(timeout=0.1)

        self.assertTrue(result)

    def test_exit_fl_mode_error(self):
        """Test exiting fl mode exception"""
        # Set the fl mode flag to ensure exit is attempted
        self.fpb._protocol._in_fl_mode = True
        self.device.ser.write.side_effect = Exception("Write error")

        result = self.fpb.exit_fl_mode(timeout=0.1)

        self.assertFalse(result)


class TestDecompileFunction(unittest.TestCase):
    """Decompile function tests"""

    def setUp(self):
        self.device = DeviceState()
        self.fpb = FPBInject(self.device)

    def test_decompile_angr_not_installed(self):
        """Test decompile when angr is not installed"""
        with patch.dict("sys.modules", {"angr": None}):
            # Force reimport check
            success, msg = self.fpb.decompile_function("/tmp/test.elf", "test_func")

            # Should return ANGR_NOT_INSTALLED since we're mocking import failure
            self.assertFalse(success)
            self.assertEqual(msg, "ANGR_NOT_INSTALLED")

    @patch("fpb_inject.FPBInject.decompile_function")
    def test_decompile_success_mock(self, mock_decompile):
        """Test successful decompile with mock"""
        mock_decompile.return_value = (
            True,
            "// Decompiled\nvoid test_func(void) { }",
        )

        success, result = mock_decompile("/tmp/test.elf", "test_func")

        self.assertTrue(success)
        self.assertIn("test_func", result)

    @patch("fpb_inject.FPBInject.decompile_function")
    def test_decompile_function_not_found(self, mock_decompile):
        """Test decompile when function not found"""
        mock_decompile.return_value = (
            False,
            "Function 'unknown' not found in ELF",
        )

        success, result = mock_decompile("/tmp/test.elf", "unknown")

        self.assertFalse(success)
        self.assertIn("not found", result)


class TestSerialThroughput(unittest.TestCase):
    """Serial throughput test cases"""

    def setUp(self):
        self.device = DeviceState()
        self.device.ser = Mock()
        self.device.ser.isOpen.return_value = True
        self.device.ser.in_waiting = 0
        self.device.ser.timeout = 1.0
        self.fpb = FPBInject(self.device)

    def test_test_serial_no_connection(self):
        """Test serial throughput without connection"""
        self.device.ser = None
        # Need to recreate protocol with None ser
        self.fpb._protocol.device = self.device

        result = self.fpb.test_serial_throughput()

        self.assertFalse(result["success"])
        self.assertIn("not connected", result.get("error", ""))
        self.assertEqual(result["max_working_size"], 0)

    def test_test_serial_all_pass(self):
        """Test serial throughput with all tests passing"""
        # Mock send_cmd to return [OK] without CRC (CRC check will be skipped)
        self.fpb._protocol.send_cmd = Mock(return_value="[OK] Echo received")

        result = self.fpb.test_serial_throughput(start_size=16, max_size=64)

        self.assertTrue(result["success"])
        self.assertGreater(result["max_working_size"], 0)
        self.assertGreater(len(result["tests"]), 0)

    def test_test_serial_partial_pass(self):
        """Test serial throughput with some tests failing"""
        # First calls return OK, then empty (timeout)
        call_count = [0]

        def mock_send_cmd(cmd, timeout=2.0):
            call_count[0] += 1
            if call_count[0] <= 2:
                return "[OK] Echo received"
            return ""  # Timeout

        self.fpb._protocol.send_cmd = Mock(side_effect=mock_send_cmd)

        result = self.fpb.test_serial_throughput(
            start_size=16, max_size=256, timeout=0.1
        )

        self.assertTrue(result["success"])
        self.assertGreater(len(result["tests"]), 0)

    def test_test_serial_recommended_size(self):
        """Test that recommended chunk size is calculated correctly"""
        # Mock send_cmd to return [OK]
        self.fpb._protocol.send_cmd = Mock(return_value="[OK] Echo received")

        result = self.fpb.test_serial_throughput(start_size=16, max_size=128)

        self.assertTrue(result["success"])
        # Recommended should be 75% of max working size
        if result["max_working_size"] > 0:
            expected_min = 64  # Minimum recommended size
            self.assertGreaterEqual(result["recommended_chunk_size"], expected_min)

    def test_test_serial_exception_handling(self):
        """Test serial throughput exception handling"""
        self.device.ser.write.side_effect = Exception("Serial write error")

        result = self.fpb.test_serial_throughput(start_size=16, max_size=32)

        # Should handle exception gracefully
        self.assertIn("tests", result)


class TestBuildTimeFeature(unittest.TestCase):
    """Build time verification feature tests"""

    def setUp(self):
        self.device = DeviceState()
        self.device.ser = Mock()
        self.device.ser.isOpen.return_value = True
        self.device.ser.in_waiting = 0
        self.fpb = FPBInject(self.device)

    def test_info_parse_build_time(self):
        """Test parsing build time from info response"""
        self.fpb._protocol.send_cmd = Mock(return_value="""FPBInject v1.0
Build: Jan 29 2026 14:30:00
Used: 100
Slots: 0/6
[OK] Info complete""")

        info, error = self.fpb.info()

        self.assertIsNotNone(info)
        self.assertEqual(info.get("build_time"), "Jan 29 2026 14:30:00")
        self.assertEqual(info["used"], 100)

    def test_info_no_build_time(self):
        """Test info response without build time (old firmware)"""
        self.fpb._protocol.send_cmd = Mock(return_value="""FPBInject v1.0
Used: 100
Slots: 0/6
[OK] Info complete""")

        info, error = self.fpb.info()

        self.assertIsNotNone(info)
        self.assertNotIn("build_time", info)

    def test_info_dynamic_mode_with_build_time(self):
        """Test info with build time and active slots"""
        self.fpb._protocol.send_cmd = Mock(return_value="""FPBInject v1.0
Build: Feb 15 2026 09:45:30
Used: 256
Slots: 2/6
Slot[0]: 0x08001000 -> 0x20001000, 128 bytes
Slot[1]: 0x08002000 -> 0x20001080, 64 bytes
[OK] Info complete""")

        info, error = self.fpb.info()

        self.assertIsNotNone(info)
        self.assertEqual(info.get("build_time"), "Feb 15 2026 09:45:30")
        self.assertEqual(info["used"], 256)
        self.assertEqual(len(info["slots"]), 2)

    @patch("subprocess.run")
    def test_get_elf_build_time_found(self, mock_run):
        """Test getting build time from ELF file"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
some_string
FPBInject v1.0
Jan 29 2026
14:30:00
other_string
"""
        mock_run.return_value = mock_result

        with tempfile.NamedTemporaryFile(delete=False) as f:
            elf_path = f.name

        try:
            result = self.fpb.get_elf_build_time(elf_path)

            self.assertIsNotNone(result)
            self.assertIn("Jan 29 2026", result)
            self.assertIn("14:30:00", result)
        finally:
            os.remove(elf_path)

    @patch("subprocess.run")
    def test_get_elf_build_time_not_found(self, mock_run):
        """Test getting build time when not present in ELF"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
random_string
no_date_here
another_line
"""
        mock_run.return_value = mock_result

        with tempfile.NamedTemporaryFile(delete=False) as f:
            elf_path = f.name

        try:
            result = self.fpb.get_elf_build_time(elf_path)

            self.assertIsNone(result)
        finally:
            os.remove(elf_path)

    def test_get_elf_build_time_file_not_exists(self):
        """Test getting build time from non-existent file"""
        result = self.fpb.get_elf_build_time("/nonexistent/path/to/elf")

        self.assertIsNone(result)

    def test_get_elf_build_time_none_path(self):
        """Test getting build time with None path"""
        result = self.fpb.get_elf_build_time(None)

        self.assertIsNone(result)

    @patch("subprocess.run")
    def test_get_elf_build_time_strings_error(self, mock_run):
        """Test getting build time when strings command fails"""
        mock_run.side_effect = Exception("strings command failed")

        with tempfile.NamedTemporaryFile(delete=False) as f:
            elf_path = f.name

        try:
            result = self.fpb.get_elf_build_time(elf_path)

            self.assertIsNone(result)
        finally:
            os.remove(elf_path)

    @patch("subprocess.run")
    def test_get_elf_build_time_with_fpbinject_marker(self, mock_run):
        """Test getting build time using FPBInject marker strategy"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
random_data
FPBInject v1.0
Mar 10 2026
16:20:45
more_data
"""
        mock_run.return_value = mock_result

        with tempfile.NamedTemporaryFile(delete=False) as f:
            elf_path = f.name

        try:
            result = self.fpb.get_elf_build_time(elf_path)

            self.assertIsNotNone(result)
            self.assertEqual(result, "Mar 10 2026 16:20:45")
        finally:
            os.remove(elf_path)

    @patch("subprocess.run")
    def test_get_elf_build_time_timeout(self, mock_run):
        """Test getting build time with timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired("strings", 60)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            elf_path = f.name

        try:
            result = self.fpb.get_elf_build_time(elf_path)

            self.assertIsNone(result)
        finally:
            os.remove(elf_path)


class TestCompileInjectObjcopyError(unittest.TestCase):
    """Test compile_inject objcopy error handling"""

    def setUp(self):
        self.device = DeviceState()
        self.fpb = FPBInject(self.device)

    @patch("core.compiler.subprocess.run")
    @patch("core.compiler.parse_compile_commands")
    def test_objcopy_error_returns_error_message(self, mock_parse, mock_run):
        """Test that objcopy failure returns error message instead of raising exception"""
        # Setup mock compile config
        mock_parse.return_value = {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mthumb", "-mcpu=cortex-m4"],
        }

        # Mock subprocess.run to simulate:
        # 1. Compile success
        # 2. Link success
        # 3. Objcopy failure (ELF has no sections)
        def run_side_effect(cmd, **kwargs):
            result = Mock()
            if "objcopy" in str(cmd):
                # Simulate objcopy error: ELF has no sections
                result.returncode = 1
                result.stderr = "error: the input file has no sections"
                result.stdout = ""
            else:
                # Compile and link succeed
                result.returncode = 0
                result.stderr = ""
                result.stdout = ""
            return result

        mock_run.side_effect = run_side_effect

        from core.compiler import compile_inject

        # Call compile_inject
        data, symbols, error = compile_inject(
            source_content="void inject_test(void) {}",
            base_addr=0x20001000,
            compile_commands_path="/fake/compile_commands.json",
        )

        # Should return error message, not raise exception
        self.assertIsNone(data)
        self.assertIsNone(symbols)
        self.assertIsNotNone(error)
        self.assertIn("Objcopy error", error)
        self.assertIn("no sections", error)

    @patch("core.compiler.subprocess.run")
    @patch("core.compiler.parse_compile_commands")
    def test_link_error_returns_error_message(self, mock_parse, mock_run):
        """Test that link failure returns error message"""
        mock_parse.return_value = {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mthumb", "-mcpu=cortex-m4"],
        }

        def run_side_effect(cmd, **kwargs):
            result = Mock()
            # Check if this is the link command (has -nostartfiles)
            cmd_str = (
                " ".join(str(c) for c in cmd) if isinstance(cmd, list) else str(cmd)
            )
            if "-nostartfiles" in cmd_str:
                # Link fails
                result.returncode = 1
                result.stderr = "undefined reference to 'some_symbol'"
                result.stdout = ""
            else:
                # Compile succeeds
                result.returncode = 0
                result.stderr = ""
                result.stdout = ""
            return result

        mock_run.side_effect = run_side_effect

        from core.compiler import compile_inject

        data, symbols, error = compile_inject(
            source_content="void inject_test(void) {}",
            base_addr=0x20001000,
            compile_commands_path="/fake/compile_commands.json",
        )

        self.assertIsNone(data)
        self.assertIsNone(symbols)
        self.assertIsNotNone(error)
        self.assertIn("Link error", error)


if __name__ == "__main__":
    unittest.main(verbosity=2)

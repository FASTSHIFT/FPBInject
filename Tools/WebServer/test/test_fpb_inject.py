#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPB Inject 模块测试
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
    crc16,
)
from state import DeviceState


class TestCRC16(unittest.TestCase):
    """CRC16 测试"""

    def test_crc16_empty(self):
        """测试空数据"""
        result = crc16(b"")
        self.assertIsInstance(result, int)

    def test_crc16_known_value(self):
        """测试已知值"""
        # CRC16-CCITT 的 "123456789" 应该是 0x29B1
        data = b"123456789"
        result = crc16(data)
        self.assertEqual(result, 0x29B1)

    def test_crc16_single_byte(self):
        """测试单字节"""
        result = crc16(b"\x00")
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 0xFFFF)

    def test_crc16_consistency(self):
        """测试一致性"""
        data = b"test data for crc"
        result1 = crc16(data)
        result2 = crc16(data)
        self.assertEqual(result1, result2)


class TestScanSerialPorts(unittest.TestCase):
    """扫描串口测试"""

    def test_scan_returns_list(self):
        """测试返回列表"""
        ports = scan_serial_ports()
        self.assertIsInstance(ports, list)

    def test_scan_port_format(self):
        """测试端口格式"""
        ports = scan_serial_ports()
        for port in ports:
            self.assertIn("device", port)
            self.assertIn("description", port)


class TestSerialOpen(unittest.TestCase):
    """串口打开测试"""

    def test_open_invalid_port(self):
        """测试打开无效端口"""
        ser, error = serial_open("/dev/nonexistent_port_12345", 115200, 1)

        self.assertIsNone(ser)
        self.assertIsNotNone(error)

    @patch("fpb_inject.serial.Serial")
    def test_open_success(self, mock_serial):
        """测试成功打开"""
        mock_instance = Mock()
        mock_serial.return_value = mock_instance

        ser, error = serial_open("/dev/ttyUSB0", 115200, 1)

        self.assertIsNone(error)
        self.assertEqual(ser, mock_instance)


class TestFPBInject(unittest.TestCase):
    """FPBInject 类测试"""

    def setUp(self):
        self.device = DeviceState()
        self.fpb = FPBInject(self.device)

    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.fpb.device, self.device)
        self.assertIsNone(self.fpb._toolchain_path)

    def test_set_toolchain_path_valid(self):
        """测试设置有效工具链路径"""
        # 使用一个存在的目录
        path = "/tmp"
        self.fpb.set_toolchain_path(path)

        self.assertEqual(self.fpb._toolchain_path, path)

    def test_set_toolchain_path_invalid(self):
        """测试设置无效工具链路径"""
        self.fpb.set_toolchain_path("/nonexistent/path")

        self.assertIsNone(self.fpb._toolchain_path)

    def test_set_toolchain_path_empty(self):
        """测试设置空路径"""
        self.fpb._toolchain_path = "/some/path"
        self.fpb.set_toolchain_path("")

        self.assertIsNone(self.fpb._toolchain_path)

    def test_get_tool_path_with_toolchain(self):
        """测试使用工具链路径获取工具"""
        import tempfile
        import os

        # 创建临时目录和假工具
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_path = os.path.join(tmpdir, "arm-none-eabi-gcc")
            with open(tool_path, "w") as f:
                f.write("#!/bin/bash\necho test")

            self.fpb.set_toolchain_path(tmpdir)
            result = self.fpb.get_tool_path("arm-none-eabi-gcc")

            self.assertEqual(result, tool_path)

    def test_get_tool_path_without_toolchain(self):
        """测试没有工具链路径时返回工具名"""
        self.fpb._toolchain_path = None

        result = self.fpb.get_tool_path("arm-none-eabi-gcc")

        self.assertEqual(result, "arm-none-eabi-gcc")

    def test_get_subprocess_env_with_toolchain(self):
        """测试获取带工具链的子进程环境"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            self.fpb._toolchain_path = tmpdir

            env = self.fpb._get_subprocess_env()

            self.assertIn("PATH", env)
            self.assertTrue(env["PATH"].startswith(tmpdir + ":"))

    def test_get_subprocess_env_without_toolchain(self):
        """测试获取不带工具链的子进程环境"""
        self.fpb._toolchain_path = None

        env = self.fpb._get_subprocess_env()

        self.assertIn("PATH", env)

    def test_parse_response_ok(self):
        """测试解析 OK 响应"""
        resp = "[OK] Operation successful"

        result = self.fpb._parse_response(resp)

        self.assertTrue(result["ok"])
        self.assertEqual(result["msg"], "Operation successful")

    def test_parse_response_err(self):
        """测试解析 ERR 响应"""
        resp = "[ERR] Something went wrong"

        result = self.fpb._parse_response(resp)

        self.assertFalse(result["ok"])
        self.assertEqual(result["msg"], "Something went wrong")

    def test_parse_response_multiline(self):
        """测试解析多行响应"""
        resp = """Info line 1
Info line 2
[OK] Done
fl>"""

        result = self.fpb._parse_response(resp)

        self.assertTrue(result["ok"])
        self.assertEqual(result["msg"], "Done")

    def test_parse_response_with_ansi(self):
        """测试解析带 ANSI 转义的响应"""
        resp = "\x1b[0m[OK] Success\x1b[K"

        result = self.fpb._parse_response(resp)

        self.assertTrue(result["ok"])

    def test_parse_response_with_prompt(self):
        """测试解析带提示符的响应"""
        resp = """[OK] Success
fl>"""

        result = self.fpb._parse_response(resp)

        self.assertTrue(result["ok"])

    def test_parse_response_error_keyword(self):
        """测试解析包含 error 关键字的响应"""
        resp = "An error occurred during processing"

        result = self.fpb._parse_response(resp)

        self.assertFalse(result["ok"])

    def test_parse_response_empty(self):
        """测试解析空响应"""
        result = self.fpb._parse_response("")

        self.assertTrue(result["ok"])  # 空响应视为成功

    def test_ping_not_connected(self):
        """测试未连接时 ping"""
        self.device.ser = None

        success, msg = self.fpb.ping()

        self.assertFalse(success)

    def test_info_not_connected(self):
        """测试未连接时获取 info"""
        self.device.ser = None

        info, error = self.fpb.info()

        self.assertIsNone(info)
        self.assertIsNotNone(error)

    def test_alloc_not_connected(self):
        """测试未连接时 alloc"""
        self.device.ser = None

        addr, error = self.fpb.alloc(1024)

        self.assertIsNone(addr)

    def test_unpatch_all_not_connected(self):
        """测试未连接时 unpatch all"""
        self.device.ser = None

        success, msg = self.fpb.unpatch(all=True)

        self.assertFalse(success)

    def test_patch_not_connected(self):
        """测试未连接时 patch"""
        self.device.ser = None

        success, msg = self.fpb.patch(0, 0x20000000, 0x20001000)

        self.assertFalse(success)

    def test_tpatch_not_connected(self):
        """测试未连接时 tpatch"""
        self.device.ser = None

        success, msg = self.fpb.tpatch(0, 0x20000000, 0x20001000)

        self.assertFalse(success)

    def test_dpatch_not_connected(self):
        """测试未连接时 dpatch"""
        self.device.ser = None

        success, msg = self.fpb.dpatch(0, 0x20000000, 0x20001000)

        self.assertFalse(success)

    def test_unpatch_not_connected(self):
        """测试未连接时 unpatch"""
        self.device.ser = None

        success, msg = self.fpb.unpatch(0)

        self.assertFalse(success)

    def test_log_raw(self):
        """测试原始日志记录"""
        self.fpb._log_raw("TX", "test command")

        self.assertEqual(len(self.device.raw_serial_log), 1)
        self.assertEqual(self.device.raw_serial_log[0]["dir"], "TX")
        self.assertEqual(self.device.raw_serial_log[0]["data"], "test command")

    def test_log_raw_empty(self):
        """测试空数据不记录"""
        self.fpb._log_raw("TX", "")

        self.assertEqual(len(self.device.raw_serial_log), 0)

    def test_log_raw_limit(self):
        """测试日志大小限制"""
        self.device.raw_log_max_size = 10

        for i in range(20):
            self.fpb._log_raw("TX", f"msg{i}")

        self.assertEqual(len(self.device.raw_serial_log), 10)


class TestFPBInjectWithMockSerial(unittest.TestCase):
    """带模拟串口的 FPBInject 测试"""

    def setUp(self):
        self.device = DeviceState()
        self.device.ser = Mock()
        self.device.ser.in_waiting = 0
        self.device.ser.isOpen.return_value = True
        self.fpb = FPBInject(self.device)

    def test_enter_fl_mode(self):
        """测试进入 fl 模式"""
        self.device.ser.read.return_value = b"fl>"
        self.device.ser.in_waiting = 3

        result = self.fpb.enter_fl_mode(timeout=0.1)

        self.assertTrue(result)
        self.device.ser.write.assert_called()

    def test_exit_fl_mode(self):
        """测试退出 fl 模式"""
        self.device.ser.read.return_value = b"[OK]\nap>"
        self.device.ser.in_waiting = 8

        result = self.fpb.exit_fl_mode(timeout=0.1)

        self.assertTrue(result)

    def test_send_cmd(self):
        """测试发送命令"""

        def mock_read(n):
            self.device.ser.in_waiting = 0
            return b"[OK] Pong\n"

        self.device.ser.read.side_effect = mock_read
        self.device.ser.in_waiting = 10

        # 直接调用内部方法
        result = self.fpb._send_cmd("--cmd ping", timeout=0.1)

        self.assertIn("OK", result)


class TestFPBInjectCompile(unittest.TestCase):
    """FPBInject 编译相关测试"""

    def setUp(self):
        self.device = DeviceState()
        self.fpb = FPBInject(self.device)

    def test_parse_compile_commands_not_found(self):
        """测试解析不存在的 compile_commands.json"""
        result = self.fpb.parse_compile_commands("/nonexistent/path.json")

        self.assertIsNone(result)

    def test_get_symbols_not_found(self):
        """测试获取不存在的 ELF 符号"""
        result = self.fpb.get_symbols("/nonexistent/elf.elf")

        self.assertEqual(result, {})

    def test_inject_no_elf(self):
        """测试没有 ELF 文件时注入"""
        self.device.elf_path = ""

        success, result = self.fpb.inject("void foo() {}", "target")

        self.assertFalse(success)
        self.assertIn("error", result)


class TestFPBInjectError(unittest.TestCase):
    """FPBInjectError 异常测试"""

    def test_exception_message(self):
        """测试异常消息"""
        try:
            raise FPBInjectError("Test error message")
        except FPBInjectError as e:
            self.assertEqual(str(e), "Test error message")

    def test_exception_inheritance(self):
        """测试异常继承"""
        self.assertTrue(issubclass(FPBInjectError, Exception))


class TestFPBInjectCoverage(unittest.TestCase):
    """FPBInject 类测试 (扩展覆盖率)"""

    def setUp(self):
        self.device = DeviceState()
        self.device.ser = Mock()
        self.device.ser.isOpen.return_value = True
        self.device.chunk_size = 48  # 设置固定的 chunk_size 用于测试
        self.fpb = FPBInject(self.device)

    def test_send_cmd_write_error(self):
        """测试发送命令写入错误"""
        self.device.ser.write.side_effect = Exception("Write Error")

        with self.assertRaises(Exception):  # _send_cmd doesn't catch exception
            self.fpb._send_cmd("test")

    def test_send_cmd_read_error(self):
        """测试发送命令读取错误"""
        # send_cmd calls write then read
        # Mock ser.read to raise exception
        self.device.ser.in_waiting = 5
        self.device.ser.read.side_effect = Exception("Read Error")

        with self.assertRaises(Exception):
            self.fpb._send_cmd("test")

    def test_parse_compile_commands(self):
        """测试解析 compile_commands.json"""
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
        """测试解析复杂的编译命令"""
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
        """测试解析格式错误的 json"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("Not JSON")
            cmd_path = f.name

        try:
            result = self.fpb.parse_compile_commands(cmd_path)
            self.assertIsNone(result)
        finally:
            os.remove(cmd_path)

    def test_parse_compile_commands_empty(self):
        """测试空JSON列表"""
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
        """测试获取符号表"""
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
        """测试获取符号表失败"""
        mock_run.side_effect = Exception("nm failed")

        symbols = self.fpb.get_symbols("/path/to/elf")

        self.assertEqual(symbols, {})

    def test_upload_success(self):
        """测试 upload 成功"""
        self.fpb._send_cmd = Mock(return_value="[OK]")

        data = b"\x01" * 100
        success, result = self.fpb.upload(data, 0x20000000)

        self.assertTrue(success)
        self.assertEqual(result["bytes"], 100)
        # 100 bytes / 48 bytes per chunk = 2.08, 向上取整 = 3 chunks
        self.assertEqual(result["chunks"], 3)

    def test_upload_fail(self):
        """测试 upload 失败"""
        self.fpb._send_cmd = Mock(return_value="[ERR] Write error")

        data = b"\x01" * 10
        success, result = self.fpb.upload(data, 0x20000000)

        self.assertFalse(success)
        self.assertIn("Write error", result["error"])

    def test_upload_callback(self):
        """测试 upload 回调"""
        self.fpb._send_cmd = Mock(return_value="[OK]")
        callback = Mock()

        data = b"\x01" * 100
        self.fpb.upload(data, 0x20000000, progress_callback=callback)

        self.assertEqual(callback.call_count, 3)

    def test_inject_no_symbols(self):
        """测试注入时找不到目标符号"""
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
        """测试注入时编译步骤失败"""
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
        """测试注入成功流程"""
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

                # compile_inject returns (data, symbols, error)
                mock_compile.return_value = (
                    b"\x01\x02",
                    {"inject_target_func": 0x20000000},
                    "",
                )

                mock_upload.return_value = (True, {"time": 0.1})
                mock_tpatch.return_value = (True, "")

                success, result = self.fpb.inject(
                    "source",
                    "target_func",
                    inject_func="inject_target_func",
                    patch_mode="trampoline",
                )

                self.assertTrue(success)
                mock_upload.assert_called()
                mock_tpatch.assert_called()
        finally:
            if os.path.exists(self.device.elf_path):
                os.remove(self.device.elf_path)

    @patch("fpb_inject.FPBInject.compile_inject")
    def test_inject_dynamic_allocation(self, mock_compile):
        """测试动态分配注入"""
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
                # info returns is_dynamic=True to trigger dynamic alloc
                mock_info.return_value = (
                    {"base": 0, "size": 0, "is_dynamic": True},
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
    """FPBInject 命令测试 (扩展覆盖率)"""

    def setUp(self):
        self.device = DeviceState()
        self.device.ser = Mock()
        self.device.ser.isOpen.return_value = True
        self.device.ser.in_waiting = 0
        self.fpb = FPBInject(self.device)

    def test_ping_success(self):
        """测试 ping 成功"""
        self.fpb._send_cmd = Mock(return_value="[OK] Pong")

        success, msg = self.fpb.ping()

        self.assertTrue(success)

    def test_ping_failure(self):
        """测试 ping 失败"""
        self.fpb._send_cmd = Mock(return_value="[ERR] No response")

        success, msg = self.fpb.ping()

        self.assertFalse(success)

    def test_info_success(self):
        """测试 info 成功"""
        self.fpb._send_cmd = Mock(
            return_value="Base: 0x20000000\nSize: 1024\nUsed: 100\n[OK]"
        )

        info, error = self.fpb.info()

        self.assertIsNotNone(info)
        self.assertEqual(info["base"], 0x20000000)
        self.assertEqual(info["size"], 1024)
        self.assertEqual(info["used"], 100)

    def test_info_failure(self):
        """测试 info 失败"""
        self.fpb._send_cmd = Mock(return_value="[ERR] Device not ready")

        info, error = self.fpb.info()

        self.assertIsNone(info)
        self.assertIn("Device not ready", error)

    def test_alloc_success(self):
        """测试 alloc 成功"""
        # alloc response format: "[OK] Allocated buffer at 0x20001000"
        self.fpb._send_cmd = Mock(return_value="[OK] Allocated buffer at 0x20001000")

        addr, error = self.fpb.alloc(1024)

        self.assertEqual(addr, 0x20001000)
        self.assertEqual(error, "")

    def test_alloc_failure(self):
        """测试 alloc 失败"""
        self.fpb._send_cmd = Mock(return_value="[ERR] Out of memory")

        addr, error = self.fpb.alloc(1024)

        self.assertIsNone(addr)

    def test_unpatch_all_success(self):
        """测试 unpatch all 成功"""
        self.fpb._send_cmd = Mock(return_value="[OK] Cleared")

        success, msg = self.fpb.unpatch(all=True)

        self.assertTrue(success)

    def test_patch_success(self):
        """测试 patch 成功"""
        self.fpb._send_cmd = Mock(return_value="[OK] Patched")

        success, msg = self.fpb.patch(0, 0x08000000, 0x20001000)

        self.assertTrue(success)

    def test_tpatch_success(self):
        """测试 tpatch 成功"""
        self.fpb._send_cmd = Mock(return_value="[OK] Trampoline patched")

        success, msg = self.fpb.tpatch(0, 0x08000000, 0x20001000)

        self.assertTrue(success)

    def test_dpatch_success(self):
        """测试 dpatch 成功"""
        self.fpb._send_cmd = Mock(return_value="[OK] DebugMonitor patched")

        success, msg = self.fpb.dpatch(0, 0x08000000, 0x20001000)

        self.assertTrue(success)

    def test_unpatch_success(self):
        """测试 unpatch 成功"""
        self.fpb._send_cmd = Mock(return_value="[OK] Unpatched")

        success, msg = self.fpb.unpatch(0)

        self.assertTrue(success)

    def test_exit_fl_mode(self):
        """测试退出 fl 模式"""
        self.device.ser.read.return_value = b"[OK]\nap>"
        self.device.ser.in_waiting = 10

        result = self.fpb.exit_fl_mode(timeout=0.1)

        self.assertTrue(result)

    def test_exit_fl_mode_error(self):
        """测试退出 fl 模式异常"""
        # Set the fl mode flag to ensure exit is attempted
        self.fpb._in_fl_mode = True
        self.device.ser.write.side_effect = Exception("Write error")

        result = self.fpb.exit_fl_mode(timeout=0.1)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)

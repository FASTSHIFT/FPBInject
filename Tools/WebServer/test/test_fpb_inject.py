#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPB Inject 模块测试
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

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

    def test_free_not_connected(self):
        """测试未连接时 free"""
        self.device.ser = None

        success, msg = self.fpb.free()

        self.assertFalse(success)

    def test_clear_not_connected(self):
        """测试未连接时 clear"""
        self.device.ser = None

        success, msg = self.fpb.clear()

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


if __name__ == "__main__":
    unittest.main(verbosity=2)

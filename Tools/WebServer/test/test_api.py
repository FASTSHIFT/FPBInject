#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPBInject WebServer API 测试
"""

import unittest
import json
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import create_app
from state import state

# Create test app
app = create_app()


class TestFPBInjectAPI(unittest.TestCase):
    """FPBInject API 测试用例"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.client = app.test_client()
        cls.client.testing = True

    def setUp(self):
        """每个测试前初始化"""
        # 重置设备状态
        device = state.device
        device.ser = None
        device.port = None
        device.elf_path = ""
        device.toolchain_path = ""
        device.compile_commands_path = ""
        device.patch_mode = "trampoline"

    def tearDown(self):
        """每个测试后清理"""
        pass

    # ==================== 端口相关测试 ====================

    def test_list_ports(self):
        """测试获取串口列表"""
        response = self.client.get("/api/ports")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("ports", data)
        self.assertIsInstance(data["ports"], list)
        self.assertTrue(data["success"])

    def test_connect_no_port(self):
        """测试连接时未指定端口"""
        response = self.client.post("/api/connect", json={})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_disconnect_without_connection(self):
        """测试未连接时断开"""
        response = self.client.post("/api/disconnect")
        # 即使未连接也应返回成功
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    def test_status_disconnected(self):
        """测试断开状态查询"""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertFalse(data["connected"])

    # ==================== 配置相关测试 ====================

    def test_update_config(self):
        """测试更新配置"""
        config = {
            "elf_path": "/path/to/test.elf",
            "toolchain_path": "/path/to/toolchain",
            "compile_commands_path": "/path/to/compile_commands.json",
            "patch_mode": "debugmon",
        }
        response = self.client.post("/api/config", json=config)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

        # 验证状态已更新
        self.assertEqual(state.device.elf_path, config["elf_path"])
        self.assertEqual(state.device.toolchain_path, config["toolchain_path"])
        self.assertEqual(state.device.patch_mode, config["patch_mode"])

    def test_update_config_partial(self):
        """测试部分更新配置"""
        response = self.client.post(
            "/api/config", json={"elf_path": "/new/path/to/test.elf"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

        # 验证只有指定字段被更新
        self.assertEqual(state.device.elf_path, "/new/path/to/test.elf")

    def test_update_config_port_baudrate(self):
        """测试更新串口和波特率配置"""
        config = {"port": "/dev/ttyUSB0", "baudrate": 921600}
        response = self.client.post("/api/config", json=config)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

        # 验证串口和波特率已更新
        self.assertEqual(state.device.port, "/dev/ttyUSB0")
        self.assertEqual(state.device.baudrate, 921600)

        # 验证状态 API 返回更新后的值
        response = self.client.get("/api/status")
        data = json.loads(response.data)
        self.assertEqual(data["port"], "/dev/ttyUSB0")
        self.assertEqual(data["baudrate"], 921600)

    # ==================== FPB 操作测试 ====================

    def test_fpb_ping(self):
        """测试 FPB ping"""
        response = self.client.post("/api/fpb/ping")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        # 未连接时 ping 会失败，但 API 应该返回
        self.assertIn("success", data)

    def test_fpb_info(self):
        """测试获取 FPB info"""
        response = self.client.get("/api/fpb/info")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        # 未连接时会返回错误
        self.assertIn("success", data)

    def test_fpb_unpatch(self):
        """测试 FPB unpatch"""
        response = self.client.post("/api/fpb/unpatch", json={"comp": 0})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("success", data)

    # ==================== 符号相关测试 ====================

    def test_symbols_list(self):
        """测试获取符号列表"""
        response = self.client.get("/api/symbols")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("success", data)
        self.assertIn("symbols", data)

    # ==================== Patch 相关测试 ====================

    def test_patch_template(self):
        """测试获取 patch 模板"""
        response = self.client.get(
            "/api/patch/template", json={"func_name": "test_func"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("success", data)

    def test_patch_detect_changes_no_file(self):
        """测试检测变化 - 文件不存在"""
        response = self.client.post(
            "/api/patch/detect_changes", json={"file_path": "/nonexistent/file.c"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_patch_auto_generate_no_file(self):
        """测试自动生成 patch - 文件不存在"""
        response = self.client.post(
            "/api/patch/auto_generate", json={"file_path": "/nonexistent/file.c"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    # ==================== 文件监控测试 ====================

    def test_watch_status(self):
        """测试获取监控状态"""
        response = self.client.get("/api/watch/status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("watching", data)
        self.assertIn("watch_dirs", data)

    def test_watch_stop(self):
        """测试停止监控"""
        response = self.client.post("/api/watch/stop")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    def test_watch_auto_inject_status(self):
        """测试获取自动注入状态"""
        response = self.client.get("/api/watch/auto_inject_status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("status", data)
        self.assertIn("message", data)
        self.assertIn("progress", data)
        self.assertIn("modified_funcs", data)

    def test_watch_auto_inject_reset(self):
        """测试重置自动注入状态"""
        response = self.client.post("/api/watch/auto_inject_reset")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    # ==================== 日志测试 ====================

    def test_log_get(self):
        """测试获取日志"""
        response = self.client.get("/api/log")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("logs", data)

    def test_log_clear(self):
        """测试清除日志"""
        response = self.client.post("/api/log/clear")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    def test_raw_log_get(self):
        """测试获取原始串口日志"""
        response = self.client.get("/api/raw_log")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("logs", data)
        self.assertIn("next_index", data)

    def test_raw_log_clear(self):
        """测试清除原始串口日志"""
        response = self.client.post("/api/raw_log/clear")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    # ==================== 文件浏览测试 ====================

    def test_browse_root(self):
        """测试浏览根目录"""
        response = self.client.get("/api/browse?path=/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("items", data)
        self.assertIn("path", data)

    def test_browse_home(self):
        """测试浏览 home 目录"""
        home = os.path.expanduser("~")
        response = self.client.get(f"/api/browse?path={home}")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("items", data)


class TestStateManagement(unittest.TestCase):
    """状态管理测试"""

    def test_state_initial_values(self):
        """测试状态初始值"""
        from state import DeviceState

        test_state = DeviceState()
        self.assertIsNone(test_state.ser)
        self.assertIsNone(test_state.port)
        self.assertEqual(test_state.baudrate, 115200)
        self.assertEqual(test_state.patch_mode, "trampoline")

    def test_state_to_dict(self):
        """测试状态转字典"""
        from state import DeviceState

        test_state = DeviceState()
        test_state.elf_path = "/test/path.elf"
        d = test_state.to_dict()
        self.assertEqual(d["elf_path"], "/test/path.elf")
        self.assertIn("patch_mode", d)


class TestFPBInjectModule(unittest.TestCase):
    """FPB 注入模块测试"""

    def test_scan_serial_ports(self):
        """测试扫描串口"""
        from fpb_inject import scan_serial_ports

        ports = scan_serial_ports()
        self.assertIsInstance(ports, list)

    def test_fpb_inject_init(self):
        """测试 FPBInject 初始化"""
        from fpb_inject import FPBInject
        from state import DeviceState

        device = DeviceState()
        fpb = FPBInject(device)
        self.assertIsNotNone(fpb)
        self.assertEqual(fpb.device, device)


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)

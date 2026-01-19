#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Routes API 测试
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
import routes
from state import DeviceState, AppState, state


class TestRoutesBase(unittest.TestCase):
    """Routes 测试基类"""

    def setUp(self):
        """设置测试环境"""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

        # 重置全局状态
        routes._fpb_inject = None

        # 创建测试用的 state
        self.original_device = state.device
        state.device = DeviceState()

        # 注册路由
        routes.register_routes(self.app)

        self.client = self.app.test_client()

    def tearDown(self):
        """清理测试环境"""
        state.device = self.original_device
        routes._fpb_inject = None


class TestIndexRoute(TestRoutesBase):
    """首页路由测试"""

    @patch("routes.render_template")
    def test_index(self, mock_render):
        """测试首页"""
        mock_render.return_value = "<html>Test</html>"

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once_with("index.html")


class TestPortsAPI(TestRoutesBase):
    """端口 API 测试"""

    @patch("routes.scan_serial_ports")
    def test_get_ports(self, mock_scan):
        """测试获取端口列表"""
        mock_scan.return_value = [
            {"port": "/dev/ttyUSB0", "description": "USB Serial"},
            {"port": "/dev/ttyUSB1", "description": "USB Serial 2"},
        ]

        response = self.client.get("/api/ports")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["ports"]), 2)

    @patch("routes.scan_serial_ports")
    def test_get_ports_empty(self, mock_scan):
        """测试无可用端口"""
        mock_scan.return_value = []

        response = self.client.get("/api/ports")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["ports"], [])


class TestConnectAPI(TestRoutesBase):
    """连接 API 测试"""

    @patch("routes.start_worker")
    @patch("routes.run_in_device_worker")
    def test_connect_no_port(self, mock_run, mock_start):
        """测试连接时未指定端口"""
        response = self.client.post(
            "/api/connect", data=json.dumps({}), content_type="application/json"
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Port not specified", data["error"])

    @patch("routes.start_worker")
    @patch("routes.run_in_device_worker")
    def test_connect_timeout(self, mock_run, mock_start):
        """测试连接超时"""
        mock_run.return_value = False

        response = self.client.post(
            "/api/connect",
            data=json.dumps({"port": "/dev/ttyUSB0"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("timeout", data["error"].lower())


class TestDisconnectAPI(TestRoutesBase):
    """断开连接 API 测试"""

    @patch("routes.run_in_device_worker")
    @patch("routes.stop_worker")
    def test_disconnect(self, mock_stop, mock_run):
        """测试断开连接"""
        mock_run.return_value = True

        response = self.client.post("/api/disconnect")
        data = json.loads(response.data)

        self.assertTrue(data["success"])


class TestStatusAPI(TestRoutesBase):
    """状态 API 测试"""

    def test_get_status(self):
        """测试获取状态"""
        state.device.port = "/dev/ttyUSB0"
        state.device.baudrate = 115200

        response = self.client.get("/api/status")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(data["connected"])
        self.assertEqual(data["port"], "/dev/ttyUSB0")


class TestRoutesFPB(TestRoutesBase):
    """FPB 相关路由测试"""

    @patch("routes.get_fpb_inject")
    def test_fpb_ping(self, mock_get_fpb):
        """测试 Ping"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (True, "pong")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "pong")

    @patch("routes.get_fpb_inject")
    def test_fpb_info(self, mock_get_fpb):
        """测试 Info"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = ({"chip": "ESP32"}, "")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["info"]["chip"], "ESP32")

    @patch("routes.get_fpb_inject")
    def test_fpb_inject(self, mock_get_fpb):
        """测试 Inject"""
        mock_fpb = Mock()
        mock_fpb.inject.return_value = (True, {"time": 100})
        mock_get_fpb.return_value = mock_fpb

        payload = {
            "source_content": "void f(){}",
            "target_func": "main",
        }
        response = self.client.post("/api/fpb/inject", json=payload)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_fpb.enter_fl_mode.assert_called()
        mock_fpb.exit_fl_mode.assert_called()

    @patch("routes.get_fpb_inject")
    def test_fpb_inject_missing_params(self, mock_get_fpb):
        """测试 Inject 缺少参数"""
        response = self.client.post("/api/fpb/inject", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not provided", data["error"])

    def test_api_config(self):
        """测试配置更新"""
        payload = {
            "port": "/dev/ttyTest",
            "baudrate": 9600,
            "patch_mode": "debugmon",
            "chunk_size": 128,
        }
        response = self.client.post("/api/config", json=payload)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.port, "/dev/ttyTest")
        self.assertEqual(state.device.baudrate, 9600)
        self.assertEqual(state.device.patch_mode, "debugmon")
        self.assertEqual(state.device.chunk_size, 128)

    def test_patch_template(self):
        """测试获取补丁模板"""
        response = self.client.get("/api/patch/template")
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("content", data)

    def test_generate_patch(self):
        """测试生成补丁"""
        payload = {"target_func": "my_func"}
        response = self.client.post("/api/patch/generate", json=payload)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("inject_my_func", data["content"])

    def test_get_status_all_fields(self):
        """测试获取所有状态字段"""
        response = self.client.get("/api/status")
        data = json.loads(response.data)

        # 验证所有必需字段存在
        required_fields = [
            "success",
            "connected",
            "port",
            "baudrate",
            "elf_path",
            "toolchain_path",
            "compile_commands_path",
            "watch_dirs",
            "patch_mode",
            "chunk_size",
            "auto_connect",
            "auto_compile",
            "patch_source_path",
            "nuttx_mode",
            "watcher_enabled",
            "inject_active",
        ]

        for field in required_fields:
            self.assertIn(field, data)


class TestConfigAPI(TestRoutesBase):
    """配置 API 测试"""

    def test_update_port(self):
        """测试更新端口"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"port": "/dev/ttyUSB1"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.port, "/dev/ttyUSB1")

    def test_update_baudrate(self):
        """测试更新波特率"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"baudrate": 921600}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.baudrate, 921600)

    def test_update_patch_mode(self):
        """测试更新补丁模式"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"patch_mode": "jump"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.patch_mode, "jump")

    def test_update_chunk_size(self):
        """测试更新块大小"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"chunk_size": 512}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.chunk_size, 512)

    def test_update_auto_compile(self):
        """测试更新自动编译设置"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"auto_compile": True}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertTrue(state.device.auto_compile)

    def test_update_nuttx_mode(self):
        """测试更新 NuttX 模式"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"nuttx_mode": True}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertTrue(state.device.nuttx_mode)

    @patch("routes._restart_file_watcher")
    def test_update_watch_dirs(self, mock_restart):
        """测试更新监控目录"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"watch_dirs": ["/tmp/test1", "/tmp/test2"]}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.watch_dirs, ["/tmp/test1", "/tmp/test2"])
        mock_restart.assert_called_once()

    def test_update_elf_path_nonexistent(self):
        """测试更新不存在的 ELF 路径"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"elf_path": "/nonexistent/file.elf"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.elf_path, "/nonexistent/file.elf")

    @patch("routes.get_fpb_inject")
    def test_update_toolchain_path(self, mock_get_fpb):
        """测试更新工具链路径"""
        mock_fpb = Mock()
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post(
            "/api/config",
            data=json.dumps({"toolchain_path": "/opt/gcc-arm"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_fpb.set_toolchain_path.assert_called_with("/opt/gcc-arm")


class TestFPBPingAPI(TestRoutesBase):
    """FPB Ping API 测试"""

    @patch("routes.get_fpb_inject")
    def test_ping_success(self, mock_get_fpb):
        """测试 ping 成功"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (True, "Pong!")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Pong!")

    @patch("routes.get_fpb_inject")
    def test_ping_failure(self, mock_get_fpb):
        """测试 ping 失败"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (False, "Timeout")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBInfoAPI(TestRoutesBase):
    """FPB Info API 测试"""

    @patch("routes.get_fpb_inject")
    def test_info_success(self, mock_get_fpb):
        """测试获取设备信息成功"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = ({"fpb": 4, "version": "1.0"}, None)
        mock_get_fpb.return_value = mock_fpb

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["info"]["fpb"], 4)

    @patch("routes.get_fpb_inject")
    def test_info_error(self, mock_get_fpb):
        """测试获取设备信息失败"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (None, "Device not responding")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not responding", data["error"])


class TestFPBUnpatchAPI(TestRoutesBase):
    """FPB Unpatch API 测试"""

    @patch("routes.get_fpb_inject")
    def test_unpatch_success(self, mock_get_fpb):
        """测试取消补丁成功"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (True, "OK")
        mock_get_fpb.return_value = mock_fpb

        state.device.inject_active = True

        response = self.client.post(
            "/api/fpb/unpatch",
            data=json.dumps({"comp": 0}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(state.device.inject_active)

    @patch("routes.get_fpb_inject")
    def test_unpatch_failure(self, mock_get_fpb):
        """测试取消补丁失败"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (False, "Error")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post("/api/fpb/unpatch")
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBInjectAPI(TestRoutesBase):
    """FPB Inject API 测试"""

    @patch("routes.get_fpb_inject")
    def test_inject_no_source(self, mock_get_fpb):
        """测试注入无源码"""
        response = self.client.post(
            "/api/fpb/inject",
            data=json.dumps({"target_func": "main"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Source content", data["error"])

    @patch("routes.get_fpb_inject")
    def test_inject_no_target(self, mock_get_fpb):
        """测试注入无目标函数"""
        response = self.client.post(
            "/api/fpb/inject",
            data=json.dumps({"source_content": "int test() { return 1; }"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Target function", data["error"])

    @patch("routes.get_fpb_inject")
    def test_inject_success(self, mock_get_fpb):
        """测试注入成功"""
        mock_fpb = Mock()
        mock_fpb.inject.return_value = (True, {"message": "Injection successful"})
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post(
            "/api/fpb/inject",
            data=json.dumps(
                {
                    "source_content": "int inject_test() { return 1; }",
                    "target_func": "original_func",
                    "inject_func": "inject_test",
                }
            ),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_fpb.enter_fl_mode.assert_called_once()
        mock_fpb.exit_fl_mode.assert_called_once()


class TestGetFPBInject(unittest.TestCase):
    """get_fpb_inject 函数测试"""

    def setUp(self):
        routes._fpb_inject = None
        self.original_device = state.device
        state.device = DeviceState()

    def tearDown(self):
        routes._fpb_inject = None
        state.device = self.original_device

    @patch("routes.FPBInject")
    def test_get_fpb_inject_creates_instance(self, mock_class):
        """测试创建 FPBInject 实例"""
        mock_instance = Mock()
        mock_class.return_value = mock_instance

        result = routes.get_fpb_inject()

        self.assertEqual(result, mock_instance)
        mock_class.assert_called_once()

    @patch("routes.FPBInject")
    def test_get_fpb_inject_returns_existing(self, mock_class):
        """测试返回已存在的实例"""
        mock_instance = Mock()
        mock_class.return_value = mock_instance

        result1 = routes.get_fpb_inject()
        result2 = routes.get_fpb_inject()

        self.assertEqual(result1, result2)
        mock_class.assert_called_once()

    @patch("routes.FPBInject")
    def test_get_fpb_inject_with_toolchain(self, mock_class):
        """测试带工具链路径的创建"""
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        state.device.toolchain_path = "/opt/toolchain"

        routes.get_fpb_inject()

        mock_instance.set_toolchain_path.assert_called_with("/opt/toolchain")


if __name__ == "__main__":
    unittest.main(verbosity=2)

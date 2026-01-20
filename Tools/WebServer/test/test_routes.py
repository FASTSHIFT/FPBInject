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


class TestRoutesExtended(TestRoutesBase):
    """Routes 扩展测试"""

    def test_symbols_reload(self):
        """测试符号重新加载"""
        state.device.elf_path = "/tmp/test.elf"

        with patch("routes.get_fpb_inject") as mock_get_fpb:
            mock_fpb = Mock()
            mock_fpb.get_symbols.return_value = {"main": 0x08000000}
            mock_get_fpb.return_value = mock_fpb

            with patch("os.path.exists", return_value=True):
                response = self.client.post("/api/symbols/reload")
                data = json.loads(response.data)

                self.assertTrue(data["success"])
                self.assertEqual(data["count"], 1)

    def test_symbols_reload_no_elf(self):
        """测试无 ELF 文件时重新加载"""
        state.device.elf_path = ""

        response = self.client.post("/api/symbols/reload")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    def test_get_symbols_with_query(self):
        """测试带搜索条件获取符号"""
        state.symbols = {
            "main": 0x08000000,
            "test_func": 0x08001000,
            "helper": 0x08002000,
        }
        state.symbols_loaded = True

        response = self.client.get("/api/symbols?q=test&limit=10")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 1)

    def test_patch_source_get(self):
        """测试获取补丁源码"""
        state.device.patch_source_content = "// test code"

        response = self.client.get("/api/patch/source")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertIn("test code", data["content"])

    def test_patch_source_set(self):
        """测试设置补丁源码"""
        response = self.client.post(
            "/api/patch/source",
            json={"content": "// new code"},
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.patch_source_content, "// new code")

    def test_patch_source_set_no_content(self):
        """测试设置空内容"""
        response = self.client.post(
            "/api/patch/source",
            json={},
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not provided", data["error"])

    def test_generate_patch_no_target(self):
        """测试生成补丁无目标函数"""
        response = self.client.post("/api/patch/generate", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"])

    @patch("routes.get_fpb_inject")
    def test_fpb_info_error(self, mock_get_fpb):
        """测试获取设备信息失败"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (None, "Device error")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Device error", data["error"])

    def test_watch_status(self):
        """测试获取文件监视状态"""
        response = self.client.get("/api/watch/status")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertIn("watching", data)
        self.assertIn("watch_dirs", data)

    def test_patch_generate_with_signature(self):
        """测试带签名生成补丁"""
        response = self.client.post(
            "/api/patch/generate", json={"target_func": "my_func", "signature": "int"}
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertIn("inject_my_func", data["content"])
        self.assertIn("int inject_my_func", data["content"])

    @patch("patch_generator.PatchGenerator")
    def test_auto_generate_patch_no_file(self, mock_gen_class):
        """测试自动生成补丁无文件路径"""
        response = self.client.post("/api/patch/auto_generate", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not provided", data["error"])

    @patch("patch_generator.PatchGenerator")
    def test_auto_generate_patch_file_not_found(self, mock_gen_class):
        """测试自动生成补丁文件不存在"""
        response = self.client.post(
            "/api/patch/auto_generate", json={"file_path": "/nonexistent/file.c"}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    @patch("patch_generator.PatchGenerator")
    def test_auto_generate_patch_no_modified(self, mock_gen_class):
        """测试自动生成补丁无修改"""
        mock_gen = Mock()
        mock_gen.detect_modified_functions.return_value = []
        mock_gen_class.return_value = mock_gen

        with patch("os.path.exists", return_value=True):
            response = self.client.post(
                "/api/patch/auto_generate", json={"file_path": "/tmp/test.c"}
            )
            data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["modified_functions"], [])

    @patch("patch_generator.PatchGenerator")
    def test_auto_generate_patch_success(self, mock_gen_class):
        """测试自动生成补丁成功"""
        mock_gen = Mock()
        mock_gen.detect_modified_functions.return_value = ["func1", "func2"]
        mock_gen.generate_patch.return_value = ("// patch code", ["func1", "func2"])
        mock_gen_class.return_value = mock_gen

        with patch("os.path.exists", return_value=True):
            response = self.client.post(
                "/api/patch/auto_generate", json={"file_path": "/tmp/test.c"}
            )
            data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["modified_functions"]), 2)
        self.assertIn("inject_func1", data["injected_functions"])

    @patch("patch_generator.PatchGenerator")
    def test_detect_changes_no_file(self, mock_gen_class):
        """测试检测变更无文件"""
        response = self.client.post("/api/patch/detect_changes", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not provided", data["error"])

    @patch("patch_generator.PatchGenerator")
    def test_detect_changes_success(self, mock_gen_class):
        """测试检测变更成功"""
        mock_gen = Mock()
        mock_gen.detect_modified_functions.return_value = ["func1"]
        mock_gen_class.return_value = mock_gen

        with patch("os.path.exists", return_value=True):
            response = self.client.post(
                "/api/patch/detect_changes", json={"file_path": "/tmp/test.c"}
            )
            data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["modified_functions"], ["func1"])

    def test_status_with_connected_serial(self):
        """测试有连接的串口状态"""
        mock_serial = Mock()
        mock_serial.isOpen.return_value = True
        state.device.ser = mock_serial

        response = self.client.get("/api/status")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertTrue(data["connected"])

    def test_status_serial_exception(self):
        """测试串口异常状态"""
        mock_serial = Mock()
        mock_serial.isOpen.side_effect = Exception("Port error")
        state.device.ser = mock_serial

        response = self.client.get("/api/status")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(data["connected"])

    @patch("routes.start_worker")
    @patch("routes.run_in_device_worker")
    @patch("routes.serial_open")
    def test_connect_success(self, mock_serial_open, mock_run, mock_start):
        """测试连接成功"""
        mock_serial = Mock()
        mock_serial_open.return_value = (mock_serial, None)

        def run_func(device, func, timeout=None):
            func()
            return True

        mock_run.side_effect = run_func

        response = self.client.post(
            "/api/connect", json={"port": "/dev/ttyUSB0", "baudrate": 115200}
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["port"], "/dev/ttyUSB0")

    @patch("routes.get_fpb_inject")
    def test_config_update_elf_path_exists(self, mock_get_fpb):
        """测试更新存在的 ELF 路径"""
        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {"main": 0x08000000}
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            response = self.client.post("/api/config", json={"elf_path": elf_path})
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertEqual(state.device.elf_path, elf_path)
            self.assertTrue(state.symbols_loaded)
        finally:
            os.unlink(elf_path)

    def test_config_update_compile_commands_path(self):
        """测试更新 compile_commands 路径"""
        response = self.client.post(
            "/api/config", json={"compile_commands_path": "/tmp/compile_commands.json"}
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(
            state.device.compile_commands_path, "/tmp/compile_commands.json"
        )

    def test_config_update_patch_source_path_exists(self):
        """测试更新存在的补丁源码路径"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("// test source")
            source_path = f.name

        try:
            response = self.client.post(
                "/api/config", json={"patch_source_path": source_path}
            )
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertIn("test source", state.device.patch_source_content)
        finally:
            os.unlink(source_path)

    def test_patch_source_get_from_file(self):
        """测试从文件获取补丁源码"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("// file content")
            source_path = f.name

        try:
            state.device.patch_source_path = source_path

            response = self.client.get("/api/patch/source")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertIn("file content", data["content"])
        finally:
            os.unlink(source_path)

    def test_patch_source_save_to_file(self):
        """测试保存补丁源码到文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            source_path = f.name

        try:
            state.device.patch_source_path = source_path

            response = self.client.post(
                "/api/patch/source",
                json={"content": "// saved content", "save_to_file": True},
            )
            data = json.loads(response.data)

            self.assertTrue(data["success"])

            with open(source_path, "r") as f:
                saved = f.read()
            self.assertIn("saved content", saved)
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)

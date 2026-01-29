#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Routes API tests
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
import routes
from core.state import DeviceState, AppState, state


class TestRoutesBase(unittest.TestCase):
    """Routes test base class"""

    def setUp(self):
        """Set up test environment"""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

        # Reset global state
        routes._fpb_inject = None

        # Create test state
        self.original_device = state.device
        state.device = DeviceState()

        # Register routes
        routes.register_routes(self.app)

        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up test environment"""
        state.device = self.original_device
        routes._fpb_inject = None


class TestIndexRoute(TestRoutesBase):
    """Index route tests"""

    @patch("routes.render_template")
    def test_index(self, mock_render):
        """Test index page"""
        mock_render.return_value = "<html>Test</html>"

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once_with("index.html")


class TestPortsAPI(TestRoutesBase):
    """Ports API tests"""

    @patch("fpb_inject.scan_serial_ports")
    def test_get_ports(self, mock_scan):
        """Test getting ports list"""
        mock_scan.return_value = [
            {"port": "/dev/ttyUSB0", "description": "USB Serial"},
            {"port": "/dev/ttyUSB1", "description": "USB Serial 2"},
        ]

        response = self.client.get("/api/ports")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["ports"]), 2)

    @patch("fpb_inject.scan_serial_ports")
    def test_get_ports_empty(self, mock_scan):
        """Test no available ports"""
        mock_scan.return_value = []

        response = self.client.get("/api/ports")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["ports"], [])


class TestConnectAPI(TestRoutesBase):
    """Connect API tests"""

    @patch("app.routes.connection.start_worker")
    @patch("app.routes.connection.run_in_device_worker")
    def test_connect_no_port(self, mock_run, mock_start):
        """Test connect without specifying port"""
        response = self.client.post(
            "/api/connect", data=json.dumps({}), content_type="application/json"
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Port not specified", data["error"])

    @patch("app.routes.connection.start_worker")
    @patch("app.routes.connection.run_in_device_worker")
    def test_connect_timeout(self, mock_run, mock_start):
        """Test connection timeout"""
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
    """Disconnect API tests"""

    @patch("app.routes.connection.run_in_device_worker")
    @patch("app.routes.connection.stop_worker")
    def test_disconnect(self, mock_stop, mock_run):
        """Test disconnect"""
        mock_run.return_value = True

        response = self.client.post("/api/disconnect")
        data = json.loads(response.data)

        self.assertTrue(data["success"])


class TestStatusAPI(TestRoutesBase):
    """Status API tests"""

    def test_get_status(self):
        """Test getting status"""
        state.device.port = "/dev/ttyUSB0"
        state.device.baudrate = 115200

        response = self.client.get("/api/status")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(data["connected"])
        self.assertEqual(data["port"], "/dev/ttyUSB0")


class TestRoutesFPB(TestRoutesBase):
    """FPB related route tests"""

    @patch("routes.get_fpb_inject")
    def test_fpb_ping(self, mock_get_fpb):
        """Test Ping"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (True, "pong")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "pong")

    @patch("routes.get_fpb_inject")
    def test_fpb_info(self, mock_get_fpb):
        """Test Info"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = ({"chip": "ESP32"}, "")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["info"]["chip"], "ESP32")

    @patch("routes.get_fpb_inject")
    def test_fpb_inject(self, mock_get_fpb):
        """Test Inject"""
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
        """Test Inject missing parameters"""
        response = self.client.post("/api/fpb/inject", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not provided", data["error"])

    def test_api_config(self):
        """Test configuration update"""
        payload = {
            "port": "/dev/ttyTest",
            "baudrate": 9600,
            "patch_mode": "debugmon",
            "chunk_size": 128,
            "tx_chunk_size": 16,
            "tx_chunk_delay": 0.01,
        }
        response = self.client.post("/api/config", json=payload)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.port, "/dev/ttyTest")
        self.assertEqual(state.device.baudrate, 9600)
        self.assertEqual(state.device.patch_mode, "debugmon")
        self.assertEqual(state.device.chunk_size, 128)
        self.assertEqual(state.device.tx_chunk_size, 16)
        self.assertEqual(state.device.tx_chunk_delay, 0.01)

    def test_patch_template(self):
        """Test getting patch template"""
        response = self.client.get("/api/patch/template")
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("content", data)

    def test_get_status_all_fields(self):
        """Test getting all status fields"""
        response = self.client.get("/api/status")
        data = json.loads(response.data)

        # Verify all required fields exist
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
            "inject_active",
        ]

        for field in required_fields:
            self.assertIn(field, data)


class TestConfigAPI(TestRoutesBase):
    """Configuration API tests"""

    def test_update_port(self):
        """Test updating port"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"port": "/dev/ttyUSB1"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.port, "/dev/ttyUSB1")

    def test_update_baudrate(self):
        """Test updating baudrate"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"baudrate": 921600}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.baudrate, 921600)

    def test_update_patch_mode(self):
        """Test updating patch mode"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"patch_mode": "jump"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.patch_mode, "jump")

    def test_update_chunk_size(self):
        """Test updating chunk size"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"chunk_size": 512}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.chunk_size, 512)

    def test_update_auto_compile(self):
        """Test updating auto compile setting"""
        response = self.client.post(
            "/api/config",
            data=json.dumps({"auto_compile": True}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertTrue(state.device.auto_compile)

    @patch("services.file_watcher_manager.restart_file_watcher")
    def test_update_watch_dirs(self, mock_restart):
        """Test updating watch directories"""
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
        """Test updating nonexistent ELF path"""
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
        """Test updating toolchain path"""
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
    """FPB Ping API tests"""

    @patch("routes.get_fpb_inject")
    def test_ping_success(self, mock_get_fpb):
        """Test ping success"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (True, "Pong!")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Pong!")

    @patch("routes.get_fpb_inject")
    def test_ping_failure(self, mock_get_fpb):
        """Test ping failure"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (False, "Timeout")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBTestSerialAPI(TestRoutesBase):
    """FPB Test Serial API tests"""

    @patch("routes.get_fpb_inject")
    def test_serial_success(self, mock_get_fpb):
        """Test serial throughput test success"""
        mock_fpb = Mock()
        mock_fpb.test_serial_throughput.return_value = {
            "success": True,
            "max_working_size": 256,
            "failed_size": 512,
            "tests": [
                {"size": 16, "passed": True, "response_time_ms": 5.2},
                {"size": 32, "passed": True, "response_time_ms": 6.1},
                {"size": 64, "passed": True, "response_time_ms": 8.3},
                {"size": 128, "passed": True, "response_time_ms": 12.5},
                {"size": 256, "passed": True, "response_time_ms": 20.1},
                {"size": 512, "passed": False, "error": "No response (timeout)"},
            ],
            "recommended_chunk_size": 192,
        }
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post(
            "/api/fpb/test-serial",
            data=json.dumps({"start_size": 16, "max_size": 512}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["max_working_size"], 256)
        self.assertEqual(data["failed_size"], 512)
        self.assertEqual(data["recommended_chunk_size"], 192)
        self.assertEqual(len(data["tests"]), 6)

    @patch("routes.get_fpb_inject")
    def test_serial_all_pass(self, mock_get_fpb):
        """Test serial throughput when all sizes pass"""
        mock_fpb = Mock()
        mock_fpb.test_serial_throughput.return_value = {
            "success": True,
            "max_working_size": 4096,
            "failed_size": 0,
            "tests": [
                {"size": 16, "passed": True},
                {"size": 32, "passed": True},
            ],
            "recommended_chunk_size": 3072,
        }
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post(
            "/api/fpb/test-serial",
            data=json.dumps({}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["failed_size"], 0)

    @patch("routes.get_fpb_inject")
    def test_serial_not_connected(self, mock_get_fpb):
        """Test serial throughput when not connected"""
        mock_fpb = Mock()
        mock_fpb.test_serial_throughput.return_value = {
            "success": False,
            "error": "Serial port not connected",
            "max_working_size": 0,
            "failed_size": 0,
            "tests": [],
            "recommended_chunk_size": 64,
        }
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post(
            "/api/fpb/test-serial",
            data=json.dumps({}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not connected", data.get("error", ""))


class TestFPBInfoAPI(TestRoutesBase):
    """FPB Info API tests"""

    @patch("routes.get_fpb_inject")
    def test_info_success(self, mock_get_fpb):
        """Test getting device info success"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = ({"fpb": 4, "version": "1.0"}, None)
        mock_get_fpb.return_value = mock_fpb

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["info"]["fpb"], 4)

    @patch("routes.get_fpb_inject")
    def test_info_error(self, mock_get_fpb):
        """Test getting device info failure"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (None, "Device not responding")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not responding", data["error"])


class TestFPBUnpatchAPI(TestRoutesBase):
    """FPB Unpatch API tests"""

    @patch("routes.get_fpb_inject")
    def test_unpatch_success(self, mock_get_fpb):
        """Test unpatch success"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (True, "OK")
        mock_get_fpb.return_value = mock_fpb

        state.device.inject_active = True

        response = self.client.post(
            "/api/fpb/unpatch",
            data=json.dumps({"all": True}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(state.device.inject_active)

    @patch("routes.get_fpb_inject")
    def test_unpatch_single_slot(self, mock_get_fpb):
        """Test unpatch single slot"""
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
        # Single slot unpatch should not clear inject_active
        self.assertTrue(state.device.inject_active)

    @patch("routes.get_fpb_inject")
    def test_unpatch_failure(self, mock_get_fpb):
        """Test unpatch failure"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (False, "Error")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.post("/api/fpb/unpatch")
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestDecompileAPI(TestRoutesBase):
    """Decompile API tests"""

    def test_decompile_no_func(self):
        """Test decompile without function name"""
        response = self.client.get("/api/symbols/decompile")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"])

    def test_decompile_no_elf(self):
        """Test decompile without ELF file"""
        response = self.client.get("/api/symbols/decompile?func=test_func")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("ELF", data["error"])

    @patch("routes.get_fpb_inject")
    def test_decompile_angr_not_installed(self, mock_get_fpb):
        """Test decompile when angr is not installed"""
        mock_fpb = Mock()
        mock_fpb.decompile_function.return_value = (False, "ANGR_NOT_INSTALLED")
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            state.device.elf_path = elf_path

            response = self.client.get("/api/symbols/decompile?func=test_func")
            data = json.loads(response.data)

            self.assertFalse(data["success"])
            self.assertEqual(data["error"], "ANGR_NOT_INSTALLED")
        finally:
            os.unlink(elf_path)

    @patch("routes.get_fpb_inject")
    def test_decompile_success(self, mock_get_fpb):
        """Test successful decompilation"""
        mock_fpb = Mock()
        mock_fpb.decompile_function.return_value = (
            True,
            "// Decompiled\nvoid test_func(void) {\n    return;\n}",
        )
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            state.device.elf_path = elf_path

            response = self.client.get("/api/symbols/decompile?func=test_func")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertIn("decompiled", data)
            self.assertIn("test_func", data["decompiled"])
        finally:
            os.unlink(elf_path)

    @patch("routes.get_fpb_inject")
    def test_decompile_function_not_found(self, mock_get_fpb):
        """Test decompile when function not found"""
        mock_fpb = Mock()
        mock_fpb.decompile_function.return_value = (
            False,
            "Function 'nonexistent' not found in ELF",
        )
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            state.device.elf_path = elf_path

            response = self.client.get("/api/symbols/decompile?func=nonexistent")
            data = json.loads(response.data)

            self.assertFalse(data["success"])
            self.assertIn("not found", data["error"])
        finally:
            os.unlink(elf_path)


class TestFPBInjectAPI(TestRoutesBase):
    """FPB Inject API tests"""

    @patch("routes.get_fpb_inject")
    def test_inject_no_source(self, mock_get_fpb):
        """Test inject without source"""
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
        """Test inject without target function"""
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
        """Test inject success"""
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
    """get_fpb_inject function tests"""

    def setUp(self):
        routes._fpb_inject = None
        self.original_device = state.device
        state.device = DeviceState()

    def tearDown(self):
        routes._fpb_inject = None
        state.device = self.original_device

    @patch("routes.FPBInject")
    def test_get_fpb_inject_creates_instance(self, mock_class):
        """Test creating FPBInject instance"""
        mock_instance = Mock()
        mock_class.return_value = mock_instance

        result = routes.get_fpb_inject()

        self.assertEqual(result, mock_instance)
        mock_class.assert_called_once()

    @patch("routes.FPBInject")
    def test_get_fpb_inject_returns_existing(self, mock_class):
        """Test returning existing instance"""
        mock_instance = Mock()
        mock_class.return_value = mock_instance

        result1 = routes.get_fpb_inject()
        result2 = routes.get_fpb_inject()

        self.assertEqual(result1, result2)
        mock_class.assert_called_once()

    @patch("routes.FPBInject")
    def test_get_fpb_inject_with_toolchain(self, mock_class):
        """Test creating with toolchain path"""
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        state.device.toolchain_path = "/opt/toolchain"

        routes.get_fpb_inject()

        mock_instance.set_toolchain_path.assert_called_with("/opt/toolchain")


class TestRoutesExtended(TestRoutesBase):
    """Routes extended tests"""

    def test_symbols_reload(self):
        """Test symbol reloading"""
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
        """Test reloading without ELF file"""
        state.device.elf_path = ""

        response = self.client.post("/api/symbols/reload")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    def test_get_symbols_with_query(self):
        """Test getting symbols with search criteria"""
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

    def test_get_symbols_search_by_address(self):
        """Test searching symbols by address (0x prefix)"""
        state.symbols = {
            "main": 0x08000000,
            "test_func": 0x08001000,
            "helper": 0x08002000,
        }
        state.symbols_loaded = True

        # Search by exact address with 0x prefix
        response = self.client.get("/api/symbols/search?q=0x08001000")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 1)
        self.assertEqual(data["symbols"][0]["name"], "test_func")

    def test_get_symbols_search_by_address_partial(self):
        """Test searching symbols by partial address"""
        state.symbols = {
            "main": 0x08000000,
            "test_func": 0x08001000,
            "helper": 0x08002000,
        }
        state.symbols_loaded = True

        # Search by partial hex (without 0x prefix)
        response = self.client.get("/api/symbols/search?q=08001")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 1)
        self.assertEqual(data["symbols"][0]["name"], "test_func")

    def test_patch_source_get(self):
        """Test getting patch source"""
        state.device.patch_source_content = "// test code"

        response = self.client.get("/api/patch/source")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertIn("test code", data["content"])

    def test_patch_source_set(self):
        """Test setting patch source"""
        response = self.client.post(
            "/api/patch/source",
            json={"content": "// new code"},
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.patch_source_content, "// new code")

    def test_patch_source_set_no_content(self):
        """Test setting empty content"""
        response = self.client.post(
            "/api/patch/source",
            json={},
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not provided", data["error"])

    @patch("routes.get_fpb_inject")
    def test_fpb_info_error(self, mock_get_fpb):
        """Test getting device info failure"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (None, "Device error")
        mock_get_fpb.return_value = mock_fpb

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Device error", data["error"])

    def test_watch_status(self):
        """Test getting file watcher status"""
        response = self.client.get("/api/watch/status")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertIn("watching", data)
        self.assertIn("watch_dirs", data)

    @patch("core.patch_generator.PatchGenerator")
    def test_auto_generate_patch_no_file(self, mock_gen_class):
        """Test auto generating patch without file path"""
        response = self.client.post("/api/patch/auto_generate", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not provided", data["error"])

    @patch("core.patch_generator.PatchGenerator")
    def test_auto_generate_patch_file_not_found(self, mock_gen_class):
        """Test auto generating patch when file not found"""
        response = self.client.post(
            "/api/patch/auto_generate", json={"file_path": "/nonexistent/file.c"}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    @patch("core.patch_generator.PatchGenerator")
    def test_auto_generate_patch_no_markers(self, mock_gen_class):
        """Test auto generating patch with no markers"""
        mock_gen = Mock()
        mock_gen.generate_patch.return_value = ("", [])
        mock_gen_class.return_value = mock_gen

        with patch("os.path.exists", return_value=True):
            response = self.client.post(
                "/api/patch/auto_generate", json={"file_path": "/tmp/test.c"}
            )
            data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["marked_functions"], [])

    @patch("core.patch_generator.PatchGenerator")
    def test_auto_generate_patch_success(self, mock_gen_class):
        """Test auto generating patch success"""
        mock_gen = Mock()
        mock_gen.generate_patch.return_value = ("// patch code", ["func1", "func2"])
        mock_gen_class.return_value = mock_gen

        with patch("os.path.exists", return_value=True):
            response = self.client.post(
                "/api/patch/auto_generate", json={"file_path": "/tmp/test.c"}
            )
            data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["marked_functions"]), 2)
        self.assertIn("inject_func1", data["injected_functions"])

    @patch("core.patch_generator.PatchGenerator")
    def test_detect_markers_no_file(self, mock_gen_class):
        """Test detecting markers without file"""
        response = self.client.post("/api/patch/detect_markers", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not provided", data["error"])

    @patch("core.patch_generator.PatchGenerator")
    @patch(
        "builtins.open", mock_open(read_data="/* FPB_INJECT */\nvoid func1(void) {}")
    )
    def test_detect_markers_success(self, mock_gen_class):
        """Test detecting markers success"""
        mock_gen = Mock()
        mock_gen.find_marked_functions.return_value = ["func1"]
        mock_gen_class.return_value = mock_gen

        with patch("os.path.exists", return_value=True):
            response = self.client.post(
                "/api/patch/detect_markers", json={"file_path": "/tmp/test.c"}
            )
            data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["marked_functions"], ["func1"])

    def test_status_with_connected_serial(self):
        """Test status with connected serial"""
        mock_serial = Mock()
        mock_serial.isOpen.return_value = True
        state.device.ser = mock_serial

        response = self.client.get("/api/status")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertTrue(data["connected"])

    def test_status_serial_exception(self):
        """Test status with serial exception"""
        mock_serial = Mock()
        mock_serial.isOpen.side_effect = Exception("Port error")
        state.device.ser = mock_serial

        response = self.client.get("/api/status")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(data["connected"])

    @patch("app.routes.connection.start_worker")
    @patch("app.routes.connection.run_in_device_worker")
    @patch("fpb_inject.serial_open")
    def test_connect_success(self, mock_serial_open, mock_run, mock_start):
        """Test connect success"""
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
        """Test updating existing ELF path"""
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
        """Test updating compile_commands path"""
        response = self.client.post(
            "/api/config", json={"compile_commands_path": "/tmp/compile_commands.json"}
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(
            state.device.compile_commands_path, "/tmp/compile_commands.json"
        )


class TestBuildTimeVerification(TestRoutesBase):
    """Build time verification API tests"""

    @patch("routes.get_fpb_inject")
    def test_fpb_info_build_time_match(self, mock_get_fpb):
        """Test info with matching build times"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {
                "ok": True,
                "build_time": "Jan 29 2026 14:30:00",
                "is_dynamic": False,
                "slots": [],
            },
            "",
        )
        mock_fpb.get_elf_build_time.return_value = "Jan 29 2026 14:30:00"
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb

        # Set ELF path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".elf") as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/fpb/info")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertFalse(data.get("build_time_mismatch", False))
            self.assertEqual(data.get("device_build_time"), "Jan 29 2026 14:30:00")
            self.assertEqual(data.get("elf_build_time"), "Jan 29 2026 14:30:00")
        finally:
            os.unlink(state.device.elf_path)

    @patch("routes.get_fpb_inject")
    def test_fpb_info_build_time_mismatch(self, mock_get_fpb):
        """Test info with mismatched build times"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {
                "ok": True,
                "build_time": "Jan 29 2026 14:30:00",
                "is_dynamic": False,
                "slots": [],
            },
            "",
        )
        # Different build time in ELF
        mock_fpb.get_elf_build_time.return_value = "Jan 28 2026 10:00:00"
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(delete=False, suffix=".elf") as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/fpb/info")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertTrue(data.get("build_time_mismatch", False))
            self.assertEqual(data.get("device_build_time"), "Jan 29 2026 14:30:00")
            self.assertEqual(data.get("elf_build_time"), "Jan 28 2026 10:00:00")
        finally:
            os.unlink(state.device.elf_path)

    @patch("routes.get_fpb_inject")
    def test_fpb_info_no_device_build_time(self, mock_get_fpb):
        """Test info when device doesn't report build time (old firmware)"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {
                "ok": True,
                "is_dynamic": False,
                "slots": [],
                # No build_time field
            },
            "",
        )
        mock_fpb.get_elf_build_time.return_value = "Jan 29 2026 14:30:00"
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(delete=False, suffix=".elf") as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/fpb/info")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            # No mismatch if device doesn't report build time
            self.assertFalse(data.get("build_time_mismatch", False))
            self.assertIsNone(data.get("device_build_time"))
        finally:
            os.unlink(state.device.elf_path)

    @patch("routes.get_fpb_inject")
    def test_fpb_info_no_elf_build_time(self, mock_get_fpb):
        """Test info when ELF doesn't contain build time"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {
                "ok": True,
                "build_time": "Jan 29 2026 14:30:00",
                "is_dynamic": False,
                "slots": [],
            },
            "",
        )
        mock_fpb.get_elf_build_time.return_value = None
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(delete=False, suffix=".elf") as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/fpb/info")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            # No mismatch if ELF doesn't have build time
            self.assertFalse(data.get("build_time_mismatch", False))
            self.assertEqual(data.get("device_build_time"), "Jan 29 2026 14:30:00")
            self.assertIsNone(data.get("elf_build_time"))
        finally:
            os.unlink(state.device.elf_path)

    @patch("routes.get_fpb_inject")
    def test_fpb_info_no_elf_path(self, mock_get_fpb):
        """Test info when no ELF path is configured"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {
                "ok": True,
                "build_time": "Jan 29 2026 14:30:00",
                "is_dynamic": False,
                "slots": [],
            },
            "",
        )
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb

        state.device.elf_path = ""

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(data.get("build_time_mismatch", False))
        self.assertIsNone(data.get("elf_build_time"))


class TestFilesAPI(TestRoutesBase):
    """Files API tests"""

    def test_browse_home_directory(self):
        """Test browsing home directory"""
        response = self.client.get("/api/browse?path=~")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["type"], "directory")
        self.assertIn("items", data)

    def test_browse_nonexistent_path(self):
        """Test browsing non-existent path"""
        response = self.client.get("/api/browse?path=/nonexistent/path/12345")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    def test_browse_file_path(self):
        """Test browsing a file path returns file info"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            response = self.client.get(f"/api/browse?path={temp_path}")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertEqual(data["type"], "file")
            self.assertEqual(data["path"], temp_path)
        finally:
            os.unlink(temp_path)

    def test_browse_with_filter(self):
        """Test browsing with file extension filter"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            open(os.path.join(tmpdir, "test.c"), "w").close()
            open(os.path.join(tmpdir, "test.h"), "w").close()
            open(os.path.join(tmpdir, "test.txt"), "w").close()

            response = self.client.get(f"/api/browse?path={tmpdir}&filter=.c,.h")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            # Should only include .c and .h files
            file_names = [item["name"] for item in data["items"]]
            self.assertIn("test.c", file_names)
            self.assertIn("test.h", file_names)
            self.assertNotIn("test.txt", file_names)

    def test_browse_hidden_files_excluded(self):
        """Test that hidden files are excluded"""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, ".hidden"), "w").close()
            open(os.path.join(tmpdir, "visible"), "w").close()

            response = self.client.get(f"/api/browse?path={tmpdir}")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            file_names = [item["name"] for item in data["items"]]
            self.assertNotIn(".hidden", file_names)
            self.assertIn("visible", file_names)

    def test_file_write_no_path(self):
        """Test file write without path"""
        response = self.client.post(
            "/api/file/write",
            data=json.dumps({"content": "test"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"].lower())

    def test_file_write_success(self):
        """Test successful file write"""
        # Use home directory which is always allowed
        home = os.path.expanduser("~")
        file_path = os.path.join(home, ".fpb_test_write.txt")

        try:
            response = self.client.post(
                "/api/file/write",
                data=json.dumps({"path": file_path, "content": "test content"}),
                content_type="application/json",
            )
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertTrue(os.path.exists(file_path))
            with open(file_path) as f:
                self.assertEqual(f.read(), "test content")
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)

    def test_file_write_creates_directory(self):
        """Test file write creates parent directory"""
        # Use home directory which is always allowed
        home = os.path.expanduser("~")
        subdir = os.path.join(home, ".fpb_test_subdir")
        file_path = os.path.join(subdir, "test.txt")

        try:
            response = self.client.post(
                "/api/file/write",
                data=json.dumps({"path": file_path, "content": "test"}),
                content_type="application/json",
            )
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertTrue(os.path.exists(file_path))
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
            if os.path.exists(subdir):
                os.rmdir(subdir)

    def test_file_write_with_tilde(self):
        """Test file write with ~ path expansion"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file in home directory (use temp for safety)
            home = os.path.expanduser("~")
            file_path = os.path.join(home, ".fpb_test_temp.txt")

            try:
                response = self.client.post(
                    "/api/file/write",
                    data=json.dumps({"path": file_path, "content": "test"}),
                    content_type="application/json",
                )
                data = json.loads(response.data)

                self.assertTrue(data["success"])
            finally:
                if os.path.exists(file_path):
                    os.unlink(file_path)


class TestLogsAPI(TestRoutesBase):
    """Logs API tests"""

    def test_get_log_empty(self):
        """Test getting empty log"""
        response = self.client.get("/api/log")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["logs"], [])

    def test_get_log_with_entries(self):
        """Test getting log with entries"""
        state.device.serial_log = [
            {"id": 0, "data": "test1"},
            {"id": 1, "data": "test2"},
        ]
        state.device.log_next_id = 2

        response = self.client.get("/api/log")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["logs"]), 2)
        self.assertEqual(data["next_index"], 2)

    def test_get_log_since(self):
        """Test getting log since specific id"""
        state.device.serial_log = [
            {"id": 0, "data": "test1"},
            {"id": 1, "data": "test2"},
            {"id": 2, "data": "test3"},
        ]
        state.device.log_next_id = 3

        response = self.client.get("/api/log?since=1")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["logs"]), 2)  # id 1 and 2

    def test_clear_log(self):
        """Test clearing log"""
        state.device.serial_log = [{"id": 0, "data": "test"}]
        state.device.log_next_id = 1

        response = self.client.post("/api/log/clear")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.serial_log, [])
        self.assertEqual(state.device.log_next_id, 0)

    def test_get_raw_log(self):
        """Test getting raw serial log"""
        state.device.raw_serial_log = [
            {"id": 0, "dir": "TX", "data": "test"},
        ]
        state.device.raw_log_next_id = 1

        response = self.client.get("/api/raw_log")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["logs"]), 1)

    def test_clear_raw_log(self):
        """Test clearing raw log"""
        state.device.raw_serial_log = [{"id": 0, "data": "test"}]
        state.device.raw_log_next_id = 1

        response = self.client.post("/api/raw_log/clear")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(state.device.raw_serial_log, [])

    def test_get_logs_combined(self):
        """Test getting combined logs"""
        state.device.tool_log = [{"id": 0, "message": "tool msg"}]
        state.device.tool_log_next_id = 1
        state.device.raw_serial_log = [{"id": 0, "data": "raw data"}]
        state.device.raw_log_next_id = 1

        response = self.client.get("/api/logs")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertIn("tool_logs", data)
        self.assertIn("raw_data", data)

    def test_serial_send_no_data(self):
        """Test serial send without data"""
        response = self.client.post(
            "/api/serial/send",
            data=json.dumps({}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("No data", data["error"])

    def test_serial_send_no_port(self):
        """Test serial send without port open"""
        state.device.ser = None

        response = self.client.post(
            "/api/serial/send",
            data=json.dumps({"data": "test"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not opened", data["error"])

    def test_serial_send_no_worker(self):
        """Test serial send without worker running"""
        state.device.ser = Mock()
        state.device.worker = None

        response = self.client.post(
            "/api/serial/send",
            data=json.dumps({"data": "test"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Worker not running", data["error"])

    def test_serial_send_success(self):
        """Test successful serial send"""
        state.device.ser = Mock()
        mock_worker = Mock()
        mock_worker.is_running.return_value = True
        state.device.worker = mock_worker

        response = self.client.post(
            "/api/serial/send",
            data=json.dumps({"data": "test"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_worker.enqueue.assert_called_once_with("write", "test")

    def test_command_no_command(self):
        """Test command without command"""
        response = self.client.post(
            "/api/command",
            data=json.dumps({}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Missing command", data["error"])

    def test_command_no_port(self):
        """Test command without port open"""
        state.device.ser = None

        response = self.client.post(
            "/api/command",
            data=json.dumps({"command": "test"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not opened", data["error"])

    def test_command_success(self):
        """Test successful command"""
        state.device.ser = Mock()
        mock_worker = Mock()
        mock_worker.is_running.return_value = True
        state.device.worker = mock_worker

        response = self.client.post(
            "/api/command",
            data=json.dumps({"command": "test"}),
            content_type="application/json",
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_worker.enqueue.assert_called_once_with("write", "test\n")

    def test_command_adds_newline(self):
        """Test command adds newline if missing"""
        state.device.ser = Mock()
        mock_worker = Mock()
        mock_worker.is_running.return_value = True
        state.device.worker = mock_worker

        response = self.client.post(
            "/api/command",
            data=json.dumps({"command": "test"}),
            content_type="application/json",
        )

        # Should add newline
        mock_worker.enqueue.assert_called_with("write", "test\n")

    def test_command_no_double_newline(self):
        """Test command doesn't add double newline"""
        state.device.ser = Mock()
        mock_worker = Mock()
        mock_worker.is_running.return_value = True
        state.device.worker = mock_worker

        response = self.client.post(
            "/api/command",
            data=json.dumps({"command": "test\n"}),
            content_type="application/json",
        )

        # Should not add another newline
        mock_worker.enqueue.assert_called_with("write", "test\n")


class TestSymbolsAPI(TestRoutesBase):
    """Symbols API tests"""

    def setUp(self):
        super().setUp()
        state.symbols = {}
        state.symbols_loaded = False

    @patch("routes.get_fpb_inject")
    def test_get_symbols_empty(self, mock_get_fpb):
        """Test getting symbols when none loaded"""
        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {}
        mock_get_fpb.return_value = mock_fpb

        state.device.elf_path = ""

        response = self.client.get("/api/symbols")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["symbols"], [])

    @patch("routes.get_fpb_inject")
    def test_get_symbols_with_data(self, mock_get_fpb):
        """Test getting symbols with data"""
        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {
            "func_a": 0x08001000,
            "func_b": 0x08002000,
        }
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/symbols")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertEqual(len(data["symbols"]), 2)
        finally:
            os.unlink(state.device.elf_path)

    @patch("routes.get_fpb_inject")
    def test_get_symbols_with_query(self, mock_get_fpb):
        """Test getting symbols with search query"""
        state.symbols = {
            "gpio_init": 0x08001000,
            "gpio_read": 0x08002000,
            "uart_init": 0x08003000,
        }
        state.symbols_loaded = True

        response = self.client.get("/api/symbols?q=gpio")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 2)

    @patch("routes.get_fpb_inject")
    def test_search_symbols_by_name(self, mock_get_fpb):
        """Test searching symbols by name"""
        state.symbols = {
            "gpio_init": 0x08001000,
            "gpio_read": 0x08002000,
            "uart_init": 0x08003000,
        }
        state.symbols_loaded = True

        response = self.client.get("/api/symbols/search?q=gpio")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 2)

    @patch("routes.get_fpb_inject")
    def test_search_symbols_by_address(self, mock_get_fpb):
        """Test searching symbols by address"""
        state.symbols = {
            "func_a": 0x08001000,
            "func_b": 0x08002000,
        }
        state.symbols_loaded = True

        response = self.client.get("/api/symbols/search?q=0x08001")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["filtered"], 1)

    @patch("routes.get_fpb_inject")
    def test_search_symbols_no_elf(self, mock_get_fpb):
        """Test searching symbols without ELF file"""
        state.symbols_loaded = False
        state.device.elf_path = ""

        response = self.client.get("/api/symbols/search?q=test")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    @patch("routes.get_fpb_inject")
    def test_reload_symbols_success(self, mock_get_fpb):
        """Test reloading symbols"""
        mock_fpb = Mock()
        mock_fpb.get_symbols.return_value = {"func": 0x08001000}
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name

        try:
            response = self.client.post("/api/symbols/reload")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 1)
        finally:
            os.unlink(state.device.elf_path)

    def test_reload_symbols_no_elf(self):
        """Test reloading symbols without ELF file"""
        state.device.elf_path = ""

        response = self.client.post("/api/symbols/reload")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    def test_get_signature_no_func(self):
        """Test getting signature without function name"""
        response = self.client.get("/api/symbols/signature")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"].lower())

    @patch("core.patch_generator.find_function_signature")
    def test_get_signature_found(self, mock_find):
        """Test getting signature when found"""
        mock_find.return_value = "void test_func(int a, int b)"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a source file
            src_file = os.path.join(tmpdir, "test.c")
            with open(src_file, "w") as f:
                f.write("void test_func(int a, int b) {}")

            state.device.watch_dirs = [tmpdir]

            response = self.client.get("/api/symbols/signature?func=test_func")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertIn("signature", data)

    def test_get_signature_not_found(self):
        """Test getting signature when not found"""
        state.device.watch_dirs = []

        response = self.client.get("/api/symbols/signature?func=nonexistent_func")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    def test_disasm_no_func(self):
        """Test disassembly without function name"""
        response = self.client.get("/api/symbols/disasm")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"].lower())

    def test_disasm_no_elf(self):
        """Test disassembly without ELF file"""
        state.device.elf_path = ""

        response = self.client.get("/api/symbols/disasm?func=test")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    @patch("routes.get_fpb_inject")
    def test_disasm_success(self, mock_get_fpb):
        """Test successful disassembly"""
        mock_fpb = Mock()
        mock_fpb.disassemble_function.return_value = (True, "push {r4, lr}")
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/symbols/disasm?func=test")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertIn("disasm", data)
        finally:
            os.unlink(state.device.elf_path)

    @patch("routes.get_fpb_inject")
    def test_disasm_failure(self, mock_get_fpb):
        """Test disassembly failure"""
        mock_fpb = Mock()
        mock_fpb.disassemble_function.return_value = (False, "Function not found")
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/symbols/disasm?func=test")
            data = json.loads(response.data)

            self.assertFalse(data["success"])
        finally:
            os.unlink(state.device.elf_path)

    def test_decompile_no_func(self):
        """Test decompilation without function name"""
        response = self.client.get("/api/symbols/decompile")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not specified", data["error"].lower())

    def test_decompile_no_elf(self):
        """Test decompilation without ELF file"""
        state.device.elf_path = ""

        response = self.client.get("/api/symbols/decompile?func=test")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    @patch("routes.get_fpb_inject")
    def test_decompile_success(self, mock_get_fpb):
        """Test successful decompilation"""
        mock_fpb = Mock()
        mock_fpb.decompile_function.return_value = (True, "int test() { return 0; }")
        mock_get_fpb.return_value = mock_fpb

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/symbols/decompile?func=test")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertIn("decompiled", data)
        finally:
            os.unlink(state.device.elf_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)

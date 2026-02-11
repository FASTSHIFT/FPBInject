#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPBInject WebServer API tests
"""

import unittest
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import create_app  # noqa: E402
from core.state import state  # noqa: E402

# Create test app
app = create_app()


class TestFPBInjectAPI(unittest.TestCase):
    """FPBInject API test cases"""

    @classmethod
    def setUpClass(cls):
        """Test class initialization"""
        cls.client = app.test_client()
        cls.client.testing = True

    def setUp(self):
        """Initialize before each test"""
        # Reset device state
        device = state.device
        device.ser = None
        device.port = None
        device.elf_path = ""
        device.toolchain_path = ""
        device.compile_commands_path = ""
        device.patch_mode = "trampoline"

    def tearDown(self):
        """Clean up after each test"""
        pass

    # ==================== Port related tests ====================

    def test_list_ports(self):
        """Test getting serial port list"""
        response = self.client.get("/api/ports")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("ports", data)
        self.assertIsInstance(data["ports"], list)
        self.assertTrue(data["success"])

    def test_connect_no_port(self):
        """Test connect without specifying port"""
        response = self.client.post("/api/connect", json={})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_disconnect_without_connection(self):
        """Test disconnect when not connected"""
        response = self.client.post("/api/disconnect")
        # Should return success even when not connected
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    def test_status_disconnected(self):
        """Test disconnect status query"""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertFalse(data["connected"])

    # ==================== Configuration related tests ====================

    def test_update_config(self):
        """Test updating configuration"""
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

        # Verify state has been updated
        self.assertEqual(state.device.elf_path, config["elf_path"])
        self.assertEqual(state.device.toolchain_path, config["toolchain_path"])
        self.assertEqual(state.device.patch_mode, config["patch_mode"])

    def test_update_config_partial(self):
        """Test partial configuration update"""
        response = self.client.post(
            "/api/config", json={"elf_path": "/new/path/to/test.elf"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

        # Verify only specified fields are updated
        self.assertEqual(state.device.elf_path, "/new/path/to/test.elf")

    def test_update_config_port_baudrate(self):
        """Test updating serial and baudrate configuration"""
        config = {"port": "/dev/ttyUSB0", "baudrate": 921600}
        response = self.client.post("/api/config", json=config)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

        # Verify serial and baudrate have been updated
        self.assertEqual(state.device.port, "/dev/ttyUSB0")
        self.assertEqual(state.device.baudrate, 921600)

        # Verify status API returns updated values
        response = self.client.get("/api/status")
        data = json.loads(response.data)
        self.assertEqual(data["port"], "/dev/ttyUSB0")
        self.assertEqual(data["baudrate"], 921600)

    # ==================== FPB Operation Tests ====================

    def test_fpb_ping(self):
        """Test FPB ping"""
        response = self.client.post("/api/fpb/ping")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        # When not connected ping will fail, but API should return
        self.assertIn("success", data)

    def test_fpb_info(self):
        """Test getting FPB info"""
        response = self.client.get("/api/fpb/info")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        # When not connected will return error
        self.assertIn("success", data)

    def test_fpb_unpatch(self):
        """Test FPB unpatch"""
        response = self.client.post("/api/fpb/unpatch", json={"comp": 0})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("success", data)

    # ==================== Symbol Related Tests ====================

    def test_symbols_list(self):
        """Test getting symbol list"""
        response = self.client.get("/api/symbols")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("success", data)
        self.assertIn("symbols", data)

    # ==================== Patch Related Tests ====================

    def test_patch_template(self):
        """Test getting patch template"""
        response = self.client.get(
            "/api/patch/template", json={"func_name": "test_func"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("success", data)

    def test_patch_detect_markers_no_file(self):
        """Test detecting markers - file does not exist"""
        response = self.client.post(
            "/api/patch/detect_markers", json={"file_path": "/nonexistent/file.c"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_patch_auto_generate_no_file(self):
        """Test auto generating patch - file does not exist"""
        response = self.client.post(
            "/api/patch/auto_generate", json={"file_path": "/nonexistent/file.c"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    # ==================== File monitoring tests ====================

    def test_watch_status(self):
        """Test getting monitoring status"""
        response = self.client.get("/api/watch/status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("watching", data)
        self.assertIn("watch_dirs", data)

    def test_watch_stop(self):
        """Test stopping monitoring"""
        response = self.client.post("/api/watch/stop")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    def test_watch_auto_inject_status(self):
        """Test getting auto injection status"""
        response = self.client.get("/api/watch/auto_inject_status")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("status", data)
        self.assertIn("message", data)
        self.assertIn("progress", data)
        self.assertIn("modified_funcs", data)

    def test_watch_auto_inject_reset(self):
        """Test resetting auto injection status"""
        response = self.client.post("/api/watch/auto_inject_reset")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    # ==================== Log tests ====================

    def test_log_get(self):
        """Test getting logs"""
        response = self.client.get("/api/log")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("logs", data)

    def test_log_clear(self):
        """Test clearing logs"""
        response = self.client.post("/api/log/clear")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    def test_raw_log_get(self):
        """Test getting raw serial logs"""
        response = self.client.get("/api/raw_log")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("logs", data)
        self.assertIn("next_index", data)

    def test_raw_log_clear(self):
        """Test clearing raw serial logs"""
        response = self.client.post("/api/raw_log/clear")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])

    # ==================== File browsing tests ====================

    def test_browse_root(self):
        """Test browsing root directory"""
        response = self.client.get("/api/browse?path=/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("items", data)
        self.assertIn("current_path", data)

    def test_browse_home(self):
        """Test browsing home directory"""
        home = os.path.expanduser("~")
        response = self.client.get(f"/api/browse?path={home}")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("items", data)


class TestStateManagement(unittest.TestCase):
    """State management tests"""

    def test_state_initial_values(self):
        """Test state initial values"""
        from core.state import DeviceState

        test_state = DeviceState()
        self.assertIsNone(test_state.ser)
        self.assertIsNone(test_state.port)
        self.assertEqual(test_state.baudrate, 115200)
        self.assertEqual(test_state.patch_mode, "trampoline")

    def test_state_to_dict(self):
        """Test state to dictionary"""
        from core.state import DeviceState

        test_state = DeviceState()
        test_state.elf_path = "/test/path.elf"
        d = test_state.to_dict()
        self.assertEqual(d["elf_path"], "/test/path.elf")
        self.assertIn("patch_mode", d)


class TestFPBInjectModule(unittest.TestCase):
    """FPB injection module tests"""

    def test_scan_serial_ports(self):
        """Test scanning serial ports"""
        from fpb_inject import scan_serial_ports

        ports = scan_serial_ports()
        self.assertIsInstance(ports, list)

    def test_fpb_inject_init(self):
        """Test FPBInject initialization"""
        from fpb_inject import FPBInject
        from core.state import DeviceState

        device = DeviceState()
        fpb = FPBInject(device)
        self.assertIsNotNone(fpb)
        self.assertEqual(fpb.device, device)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)

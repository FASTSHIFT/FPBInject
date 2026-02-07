#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPB routes API tests
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app.routes import fpb
from core.state import DeviceState, AppState, state


def mock_run_in_device_worker(device, func, timeout=5.0):
    """Mock run_in_device_worker that executes func synchronously."""
    func()
    return True


class TestFPBRoutesBase(unittest.TestCase):
    """FPB routes test base class"""

    def setUp(self):
        """Set up test environment"""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

        # Reset global state
        self.original_device = state.device
        state.device = DeviceState()

        # Register blueprint
        self.app.register_blueprint(fpb.bp, url_prefix="/api")

        self.client = self.app.test_client()

        # Patch run_in_device_worker to execute synchronously
        self.worker_patcher = patch(
            "app.routes.fpb.run_in_device_worker", side_effect=mock_run_in_device_worker
        )
        self.mock_worker = self.worker_patcher.start()

    def tearDown(self):
        """Clean up test environment"""
        self.worker_patcher.stop()
        state.device = self.original_device


class TestFPBPingRoute(TestFPBRoutesBase):
    """FPB ping route tests"""

    @patch("app.routes.fpb._get_helpers")
    def test_ping_success(self, mock_helpers):
        """Test ping success"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (True, "Pong!")
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Pong!")

    @patch("app.routes.fpb._get_helpers")
    def test_ping_failure(self, mock_helpers):
        """Test ping failure"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (False, "Timeout")
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBTestSerialRoute(TestFPBRoutesBase):
    """FPB test-serial route tests"""

    @patch("app.routes.fpb._get_helpers")
    def test_serial_test_success(self, mock_helpers):
        """Test serial throughput test success"""
        mock_fpb = Mock()
        mock_fpb.test_serial_throughput.return_value = {
            "success": True,
            "max_working_size": 256,
            "failed_size": 512,
            "recommended_chunk_size": 192,
        }
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post(
            "/api/fpb/test-serial",
            json={"start_size": 16, "max_size": 512},
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["max_working_size"], 256)

    @patch("app.routes.fpb._get_helpers")
    def test_serial_test_failure(self, mock_helpers):
        """Test serial throughput test failure"""
        mock_fpb = Mock()
        mock_fpb.test_serial_throughput.return_value = {
            "success": False,
            "error": "Not connected",
        }
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post("/api/fpb/test-serial", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBInfoRoute(TestFPBRoutesBase):
    """FPB info route tests"""

    @patch("app.routes.fpb._get_helpers")
    def test_info_success(self, mock_helpers):
        """Test info success"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {"base": 0x20000000, "size": 1024, "build_time": "Jan 15 2025 10:30:00"},
            None,
        )
        mock_fpb.exit_fl_mode = Mock()
        mock_fpb.get_elf_build_time.return_value = "Jan 15 2025 10:30:00"

        mock_build_slot = Mock(
            return_value={"slots": [], "memory": {"base": 0x20000000, "size": 1024}}
        )
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, mock_build_slot)

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertIn("info", data)

    @patch("app.routes.fpb._get_helpers")
    def test_info_error(self, mock_helpers):
        """Test info error"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (None, "Device not responding")
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not responding", data["error"])

    @patch("app.routes.fpb._get_helpers")
    def test_info_build_time_mismatch(self, mock_helpers):
        """Test info with build time mismatch"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {"base": 0x20000000, "build_time": "Jan 15 2025 10:30:00"},
            None,
        )
        mock_fpb.exit_fl_mode = Mock()
        mock_fpb.get_elf_build_time.return_value = "Jan 16 2025 11:00:00"

        mock_build_slot = Mock(return_value={"slots": [], "memory": {}})
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, mock_build_slot)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/fpb/info")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertTrue(data["build_time_mismatch"])
        finally:
            os.unlink(state.device.elf_path)


class TestFPBUnpatchRoute(TestFPBRoutesBase):
    """FPB unpatch route tests"""

    @patch("app.routes.fpb._get_helpers")
    def test_unpatch_single_slot(self, mock_helpers):
        """Test unpatch single slot"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (True, "OK")
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        state.device.inject_active = True

        response = self.client.post("/api/fpb/unpatch", json={"comp": 0})
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        # Single slot unpatch should not clear inject_active
        self.assertTrue(state.device.inject_active)

    @patch("app.routes.fpb._get_helpers")
    def test_unpatch_all(self, mock_helpers):
        """Test unpatch all slots"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (True, "OK")
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        state.device.inject_active = True
        state.device.last_inject_target = "test_func"

        response = self.client.post("/api/fpb/unpatch", json={"all": True})
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(state.device.inject_active)
        self.assertIsNone(state.device.last_inject_target)

    @patch("app.routes.fpb._get_helpers")
    def test_unpatch_failure(self, mock_helpers):
        """Test unpatch failure"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (False, "Error")
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post("/api/fpb/unpatch", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])

    @patch("app.routes.fpb._get_helpers")
    def test_unpatch_exception(self, mock_helpers):
        """Test unpatch with exception"""
        mock_fpb = Mock()
        mock_fpb.unpatch.side_effect = Exception("Unexpected error")
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post("/api/fpb/unpatch", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Unexpected error", data["message"])


class TestFPBInjectRoute(TestFPBRoutesBase):
    """FPB inject route tests"""

    @patch("app.routes.fpb._get_helpers")
    def test_inject_no_source(self, mock_helpers):
        """Test inject without source content"""
        mock_helpers.return_value = (Mock(), Mock(), Mock())

        response = self.client.post("/api/fpb/inject", json={"target_func": "main"})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Source content", data["error"])

    @patch("app.routes.fpb._get_helpers")
    def test_inject_no_target(self, mock_helpers):
        """Test inject without target function"""
        mock_helpers.return_value = (Mock(), Mock(), Mock())

        response = self.client.post(
            "/api/fpb/inject", json={"source_content": "void test() {}"}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Target function", data["error"])

    @patch("app.routes.fpb._get_helpers")
    def test_inject_success(self, mock_helpers):
        """Test inject success"""
        mock_fpb = Mock()
        mock_fpb.inject.return_value = (True, {"slot": 0, "time": 0.5})
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post(
            "/api/fpb/inject",
            json={
                "source_content": "/* FPB_INJECT */\nvoid test_func() {}",
                "target_func": "original_func",
            },
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_fpb.enter_fl_mode.assert_called_once()
        mock_fpb.exit_fl_mode.assert_called_once()

    @patch("app.routes.fpb._get_helpers")
    def test_inject_failure(self, mock_helpers):
        """Test inject failure"""
        mock_fpb = Mock()
        mock_fpb.inject.return_value = (False, {"error": "Compile error"})
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post(
            "/api/fpb/inject",
            json={
                "source_content": "invalid code",
                "target_func": "test",
            },
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBInjectMultiRoute(TestFPBRoutesBase):
    """FPB inject/multi route tests"""

    @patch("app.routes.fpb._get_helpers")
    def test_inject_multi_no_source(self, mock_helpers):
        """Test inject_multi without source content"""
        mock_helpers.return_value = (Mock(), Mock(), Mock())

        response = self.client.post("/api/fpb/inject/multi", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Source content", data["error"])

    @patch("app.routes.fpb._get_helpers")
    def test_inject_multi_success(self, mock_helpers):
        """Test inject_multi success"""
        mock_fpb = Mock()
        mock_fpb.inject_multi.return_value = (
            True,
            {"successful_count": 2, "total_count": 2},
        )
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post(
            "/api/fpb/inject/multi",
            json={
                "source_content": "/* FPB_INJECT */\nvoid func_a() {} /* FPB_INJECT */\nvoid func_b() {}"
            },
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["successful_count"], 2)

    @patch("app.routes.fpb._get_helpers")
    def test_inject_multi_failure(self, mock_helpers):
        """Test inject_multi failure"""
        mock_fpb = Mock()
        mock_fpb.inject_multi.return_value = (False, {"error": "No inject functions"})
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = (Mock(), lambda: mock_fpb, Mock())

        response = self.client.post(
            "/api/fpb/inject/multi",
            json={"source_content": "void test() {}"},
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBInjectStreamRoute(TestFPBRoutesBase):
    """FPB inject/stream route tests"""

    @patch("app.routes.fpb._get_helpers")
    def test_inject_stream_no_source(self, mock_helpers):
        """Test inject_stream without source content"""
        mock_helpers.return_value = (Mock(), Mock(), Mock())

        response = self.client.post(
            "/api/fpb/inject/stream", json={"target_func": "main"}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Source content", data["error"])

    @patch("app.routes.fpb._get_helpers")
    def test_inject_stream_no_target(self, mock_helpers):
        """Test inject_stream without target function"""
        mock_helpers.return_value = (Mock(), Mock(), Mock())

        response = self.client.post(
            "/api/fpb/inject/stream", json={"source_content": "void test() {}"}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Target function", data["error"])


if __name__ == "__main__":
    unittest.main()

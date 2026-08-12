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
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from fpbinject.app.routes import fpb  # noqa: E402
from fpbinject.core.state import DeviceState, state  # noqa: E402


def mock_run_in_device_worker(device, func, timeout=5.0):
    """Mock run_in_device_worker that executes func synchronously."""
    func()
    return True


def make_mock_helpers(mock_fpb, mock_build_slot=None):
    """Create mock helpers return value with proper structure.

    Returns: (log_info, log_success, log_error, log_warn, get_fpb_inject, _build_slot_response)
    """
    return (
        Mock(),  # log_info
        Mock(),  # log_success
        Mock(),  # log_error
        Mock(),  # log_warn
        lambda: mock_fpb,  # get_fpb_inject
        mock_build_slot or Mock(),  # _build_slot_response
    )


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
            "fpbinject.app.routes.fpb.run_in_device_worker",
            side_effect=mock_run_in_device_worker,
        )
        self.mock_worker = self.worker_patcher.start()

    def tearDown(self):
        """Clean up test environment"""
        self.worker_patcher.stop()
        state.device = self.original_device


class TestFPBPingRoute(TestFPBRoutesBase):
    """FPB ping route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_ping_success(self, mock_helpers):
        """Test ping success"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (True, "Pong!")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Pong!")

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_ping_failure(self, mock_helpers):
        """Test ping failure"""
        mock_fpb = Mock()
        mock_fpb.ping.return_value = (False, "Timeout")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post("/api/fpb/ping")
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBTestSerialRoute(TestFPBRoutesBase):
    """FPB test-serial route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_serial_test_success(self, mock_helpers):
        """Test serial throughput test success"""
        mock_fpb = Mock()
        mock_fpb.test_serial_throughput.return_value = {
            "success": True,
            "max_working_size": 256,
            "failed_size": 512,
            "recommended_upload_chunk_size": 192,
            "recommended_download_chunk_size": 2048,
            "fragment_needed": False,
            "phases": {},
        }
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/test-serial",
            json={"start_size": 16, "max_size": 512},
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["max_working_size"], 256)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_serial_test_failure(self, mock_helpers):
        """Test serial throughput test failure"""
        mock_fpb = Mock()
        mock_fpb.test_serial_throughput.return_value = {
            "success": False,
            "error": "Not connected",
        }
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post("/api/fpb/test-serial", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBInfoRoute(TestFPBRoutesBase):
    """FPB info route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
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
        mock_helpers.return_value = make_mock_helpers(mock_fpb, mock_build_slot)

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertIn("info", data)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_info_error(self, mock_helpers):
        """Test info error"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (None, "Device not responding")
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not responding", data["error"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_info_no_device_info_available(self, mock_helpers):
        """Test info when device returns empty response (no FLOK marker)"""
        mock_fpb = Mock()
        # Simulate: info() returns None when device doesn't respond with FLOK
        mock_fpb.info.return_value = (None, "Device not responding")
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        # Ensure no cached device_info
        state.device.device_info = None

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("not responding", data["error"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
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
        mock_helpers.return_value = make_mock_helpers(mock_fpb, mock_build_slot)

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            state.device.elf_path = f.name

        try:
            response = self.client.get("/api/fpb/info")
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertTrue(data["build_time_mismatch"])
        finally:
            os.unlink(state.device.elf_path)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_info_version_mismatch(self, mock_helpers):
        """Test info detects major.minor version mismatch"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {"base": 0x20000000, "version_string": "FPBInject v1.5.0"},
            None,
        )
        mock_fpb.exit_fl_mode = Mock()
        mock_fpb.get_elf_build_time.return_value = None

        mock_build_slot = Mock(return_value={"slots": [], "memory": {}})
        mock_helpers.return_value = make_mock_helpers(mock_fpb, mock_build_slot)

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertTrue(data["version_mismatch"])
        self.assertEqual(data["device_version"], "1.5")

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_info_version_match_same_minor(self, mock_helpers):
        """Test info: same major.minor with different patch is NOT a mismatch"""
        from fpbinject.version import VERSION_MAJOR, VERSION_MINOR

        mock_fpb = Mock()
        # Use current host major.minor but different patch
        mock_fpb.info.return_value = (
            {
                "base": 0x20000000,
                "version_string": f"FPBInject v{VERSION_MAJOR}.{VERSION_MINOR}.99",
            },
            None,
        )
        mock_fpb.exit_fl_mode = Mock()
        mock_fpb.get_elf_build_time.return_value = None

        mock_build_slot = Mock(return_value={"slots": [], "memory": {}})
        mock_helpers.return_value = make_mock_helpers(mock_fpb, mock_build_slot)

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(data["version_mismatch"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_info_version_no_version_string(self, mock_helpers):
        """Test info: no version_string in device response means no mismatch"""
        mock_fpb = Mock()
        mock_fpb.info.return_value = (
            {"base": 0x20000000},
            None,
        )
        mock_fpb.exit_fl_mode = Mock()
        mock_fpb.get_elf_build_time.return_value = None

        mock_build_slot = Mock(return_value={"slots": [], "memory": {}})
        mock_helpers.return_value = make_mock_helpers(mock_fpb, mock_build_slot)

        response = self.client.get("/api/fpb/info")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(data["version_mismatch"])


class TestFPBUnpatchRoute(TestFPBRoutesBase):
    """FPB unpatch route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_unpatch_single_slot(self, mock_helpers):
        """Test unpatch single slot"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (True, "OK")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        state.device.inject_active = True

        response = self.client.post("/api/fpb/unpatch", json={"comp": 0})
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        # Single slot unpatch should not clear inject_active
        self.assertTrue(state.device.inject_active)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_unpatch_all(self, mock_helpers):
        """Test unpatch all slots"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (True, "OK")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        state.device.inject_active = True
        state.device.last_inject_target = "test_func"

        response = self.client.post("/api/fpb/unpatch", json={"all": True})
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertFalse(state.device.inject_active)
        self.assertIsNone(state.device.last_inject_target)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_unpatch_failure(self, mock_helpers):
        """Test unpatch failure"""
        mock_fpb = Mock()
        mock_fpb.unpatch.return_value = (False, "Error")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post("/api/fpb/unpatch", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_unpatch_exception(self, mock_helpers):
        """Test unpatch with exception"""
        mock_fpb = Mock()
        mock_fpb.unpatch.side_effect = Exception("Unexpected error")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post("/api/fpb/unpatch", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Unexpected error", data["message"])


class TestFPBEnableRoute(TestFPBRoutesBase):
    """FPB enable route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_enable_single_slot(self, mock_helpers):
        """Test enable single slot"""
        mock_fpb = Mock()
        mock_fpb.enable_patch.return_value = (True, "Enabled patch 0")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post("/api/fpb/enable", json={"comp": 0, "enable": True})
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_fpb.enable_patch.assert_called_once_with(comp=0, enable=True, all=False)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_disable_single_slot(self, mock_helpers):
        """Test disable single slot"""
        mock_fpb = Mock()
        mock_fpb.enable_patch.return_value = (True, "Disabled patch 0")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/enable", json={"comp": 0, "enable": False}
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_fpb.enable_patch.assert_called_once_with(comp=0, enable=False, all=False)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_enable_all_slots(self, mock_helpers):
        """Test enable all slots"""
        mock_fpb = Mock()
        mock_fpb.enable_patch.return_value = (True, "Enabled 6 patches")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/enable", json={"enable": True, "all": True}
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_fpb.enable_patch.assert_called_once_with(comp=0, enable=True, all=True)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_disable_all_slots(self, mock_helpers):
        """Test disable all slots"""
        mock_fpb = Mock()
        mock_fpb.enable_patch.return_value = (True, "Disabled 6 patches")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/enable", json={"enable": False, "all": True}
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        mock_fpb.enable_patch.assert_called_once_with(comp=0, enable=False, all=True)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_enable_failure(self, mock_helpers):
        """Test enable failure"""
        mock_fpb = Mock()
        mock_fpb.enable_patch.return_value = (False, "Invalid comp")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/enable", json={"comp": 99, "enable": True}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_enable_exception(self, mock_helpers):
        """Test enable with exception"""
        mock_fpb = Mock()
        mock_fpb.enable_patch.side_effect = Exception("Unexpected error")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post("/api/fpb/enable", json={"comp": 0, "enable": True})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Unexpected error", data["message"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_enable_default_values(self, mock_helpers):
        """Test enable with default values"""
        mock_fpb = Mock()
        mock_fpb.enable_patch.return_value = (True, "OK")
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post("/api/fpb/enable", json={})
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        # Default: comp=0, enable=True, all=False
        mock_fpb.enable_patch.assert_called_once_with(comp=0, enable=True, all=False)


class TestFPBInjectRoute(TestFPBRoutesBase):
    """FPB inject route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_no_source(self, mock_helpers):
        """Test inject without source content"""
        mock_helpers.return_value = make_mock_helpers(Mock())

        response = self.client.post("/api/fpb/inject", json={"target_func": "main"})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Source content", data["error"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_no_target(self, mock_helpers):
        """Test inject without target function"""
        mock_helpers.return_value = make_mock_helpers(Mock())

        response = self.client.post(
            "/api/fpb/inject", json={"source_content": "void test() {}"}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Target function", data["error"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_success(self, mock_helpers):
        """Test inject success"""
        mock_fpb = Mock()
        mock_fpb.inject.return_value = (True, {"slot": 0, "time": 0.5})
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

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

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_failure(self, mock_helpers):
        """Test inject failure"""
        mock_fpb = Mock()
        mock_fpb.inject.return_value = (False, {"error": "Compile error"})
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

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

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_multi_no_source(self, mock_helpers):
        """Test inject_multi without source content"""
        mock_helpers.return_value = make_mock_helpers(Mock())

        response = self.client.post("/api/fpb/inject/multi", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Source content", data["error"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_multi_success(self, mock_helpers):
        """Test inject_multi success"""
        mock_fpb = Mock()
        mock_fpb.inject_multi.return_value = (
            True,
            {"successful_count": 2, "total_count": 2},
        )
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/inject/multi",
            json={
                "source_content": "/* FPB_INJECT */\nvoid func_a() {} /* FPB_INJECT */\nvoid func_b() {}"
            },
        )
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["successful_count"], 2)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_multi_failure(self, mock_helpers):
        """Test inject_multi failure"""
        mock_fpb = Mock()
        mock_fpb.inject_multi.return_value = (False, {"error": "No inject functions"})
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/inject/multi",
            json={"source_content": "void test() {}"},
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])


class TestFPBInjectStreamRoute(TestFPBRoutesBase):
    """FPB inject/stream route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_stream_no_source(self, mock_helpers):
        """Test inject_stream without source content"""
        mock_helpers.return_value = make_mock_helpers(Mock())

        response = self.client.post(
            "/api/fpb/inject/stream", json={"target_func": "main"}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Source content", data["error"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_stream_no_target(self, mock_helpers):
        """Test inject_stream without target function"""
        mock_helpers.return_value = make_mock_helpers(Mock())

        response = self.client.post(
            "/api/fpb/inject/stream", json={"source_content": "void test() {}"}
        )
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Target function", data["error"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_stream_success_emits_sse(self, mock_helpers):
        """Test inject_stream returns SSE events on success."""
        mock_fpb = Mock()
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()

        def fake_inject(**kwargs):
            cb = kwargs.get("progress_callback")
            if cb:
                cb(50, 100)
                cb(100, 100)
            return True, {"slot": 0, "code_size": 64}

        mock_fpb.inject.side_effect = fake_inject
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/inject/stream",
            json={
                "source_content": "/* FPB_INJECT */\nvoid f() {}",
                "target_func": "original_f",
            },
        )

        self.assertIn("text/event-stream", response.content_type)
        body = response.get_data(as_text=True)
        events = _parse_sse_events(body)

        types = [e["type"] for e in events]
        self.assertIn("status", types)
        self.assertIn("result", types)

        result_evt = next(e for e in events if e["type"] == "result")
        self.assertTrue(result_evt["success"])


class TestFPBInjectMultiStreamRoute(TestFPBRoutesBase):
    """FPB inject/multi/stream route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_multi_stream_no_source(self, mock_helpers):
        """Test inject/multi/stream without source content."""
        mock_helpers.return_value = make_mock_helpers(Mock())

        response = self.client.post("/api/fpb/inject/multi/stream", json={})
        data = json.loads(response.data)

        self.assertFalse(data["success"])
        self.assertIn("Source content", data["error"])

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_multi_stream_success_emits_sse(self, mock_helpers):
        """Test inject/multi/stream returns SSE events with progress."""
        mock_fpb = Mock()
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()

        def fake_inject_multi(**kwargs):
            status_cb = kwargs.get("status_callback")
            progress_cb = kwargs.get("progress_callback")
            if status_cb:
                status_cb(
                    {"stage": "injecting", "index": 0, "name": "func_a", "total": 2}
                )
            if progress_cb:
                progress_cb(32, 64)
                progress_cb(64, 64)
            if status_cb:
                status_cb(
                    {"stage": "injecting", "index": 1, "name": "func_b", "total": 2}
                )
            if progress_cb:
                progress_cb(32, 64)
                progress_cb(64, 64)
            return True, {"successful_count": 2, "total_count": 2}

        mock_fpb.inject_multi.side_effect = fake_inject_multi
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/inject/multi/stream",
            json={
                "source_content": "/* FPB_INJECT */\nvoid func_a() {}\nvoid func_b() {}"
            },
        )

        self.assertIn("text/event-stream", response.content_type)
        body = response.get_data(as_text=True)
        events = _parse_sse_events(body)

        types = [e["type"] for e in events]
        self.assertIn("status", types)
        self.assertIn("progress", types)
        self.assertIn("result", types)

        progress_events = [e for e in events if e["type"] == "progress"]
        self.assertGreater(len(progress_events), 0)
        self.assertIn("percent", progress_events[0])

        result_evt = next(e for e in events if e["type"] == "result")
        self.assertTrue(result_evt["success"])
        self.assertEqual(result_evt["successful_count"], 2)

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_multi_stream_worker_timeout(self, mock_helpers):
        """Test inject/multi/stream handles device worker timeout."""
        mock_helpers.return_value = make_mock_helpers(Mock())

        # Make run_in_device_worker return False (timeout)
        self.worker_patcher.stop()
        timeout_patcher = patch(
            "fpbinject.app.routes.fpb.run_in_device_worker", return_value=False
        )
        timeout_patcher.start()

        try:
            response = self.client.post(
                "/api/fpb/inject/multi/stream",
                json={"source_content": "void f() {}"},
            )

            body = response.get_data(as_text=True)
            events = _parse_sse_events(body)

            result_evt = next((e for e in events if e["type"] == "result"), None)
            self.assertIsNotNone(result_evt)
            self.assertFalse(result_evt["success"])
            self.assertIn("timeout", result_evt["error"].lower())
        finally:
            timeout_patcher.stop()
            self.mock_worker = self.worker_patcher.start()


def _parse_sse_events(body):
    """Parse SSE text body into list of dicts."""
    events = []
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


class TestFPBInjectCancelRoute(TestFPBRoutesBase):
    """FPB inject/cancel route tests"""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_cancel_sets_flag(self, mock_helpers):
        """Test cancel endpoint sets the _inject_cancelled event."""
        mock_helpers.return_value = make_mock_helpers(Mock())

        # Clear the flag first
        fpb._inject_cancelled.clear()
        self.assertFalse(fpb._inject_cancelled.is_set())

        response = self.client.post("/api/fpb/inject/cancel")
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertTrue(fpb._inject_cancelled.is_set())

        # Clean up
        fpb._inject_cancelled.clear()


class TestMakeInjectProgressCallback(unittest.TestCase):
    """Test _make_inject_progress_callback helper."""

    def test_progress_has_speed_eta_elapsed(self):
        """Progress events include speed, eta, elapsed fields."""
        import queue as _queue

        q = _queue.Queue()
        fpb._inject_cancelled.clear()
        cb = fpb._make_inject_progress_callback(q)

        cb(50, 100)
        cb(100, 100)

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        self.assertEqual(len(events), 2)
        for ev in events:
            self.assertEqual(ev["type"], "progress")
            self.assertIn("speed", ev)
            self.assertIn("eta", ev)
            self.assertIn("elapsed", ev)
            self.assertIn("percent", ev)

        # Last event should be 100%
        self.assertEqual(events[-1]["percent"], 100.0)
        self.assertEqual(events[-1]["uploaded"], 100)
        self.assertEqual(events[-1]["total"], 100)

    def test_cancel_raises_exception(self):
        """Callback raises _InjectCancelled when cancel flag is set."""
        import queue as _queue

        q = _queue.Queue()
        fpb._inject_cancelled.set()
        cb = fpb._make_inject_progress_callback(q)

        with self.assertRaises(fpb._InjectCancelled):
            cb(50, 100)

        # Clean up
        fpb._inject_cancelled.clear()


class TestInjectStreamCancel(TestFPBRoutesBase):
    """Test inject/stream cancellation."""

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_stream_cancelled(self, mock_helpers):
        """Test inject_stream returns cancelled result when cancelled."""
        mock_fpb = Mock()
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()

        def fake_inject(**kwargs):
            cb = kwargs.get("progress_callback")
            if cb:
                # Simulate cancel during upload
                fpb._inject_cancelled.set()
                cb(50, 100)  # This should raise _InjectCancelled

        mock_fpb.inject.side_effect = fake_inject
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/inject/stream",
            json={
                "source_content": "/* FPB_INJECT */\nvoid f() {}",
                "target_func": "original_f",
            },
        )

        body = response.get_data(as_text=True)
        events = _parse_sse_events(body)

        result_evt = next((e for e in events if e["type"] == "result"), None)
        self.assertIsNotNone(result_evt)
        self.assertFalse(result_evt["success"])
        self.assertTrue(result_evt.get("cancelled", False))

        # Clean up
        fpb._inject_cancelled.clear()

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_multi_stream_cancelled(self, mock_helpers):
        """Test inject/multi/stream returns cancelled result when cancelled."""
        mock_fpb = Mock()
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()

        def fake_inject_multi(**kwargs):
            cb = kwargs.get("progress_callback")
            if cb:
                fpb._inject_cancelled.set()
                cb(32, 64)  # Should raise _InjectCancelled

        mock_fpb.inject_multi.side_effect = fake_inject_multi
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/inject/multi/stream",
            json={"source_content": "/* FPB_INJECT */\nvoid f() {}"},
        )

        body = response.get_data(as_text=True)
        events = _parse_sse_events(body)

        result_evt = next((e for e in events if e["type"] == "result"), None)
        self.assertIsNotNone(result_evt)
        self.assertFalse(result_evt["success"])
        self.assertTrue(result_evt.get("cancelled", False))

        # Clean up
        fpb._inject_cancelled.clear()

    @patch("fpbinject.app.routes.fpb._get_helpers")
    def test_inject_stream_progress_has_speed_fields(self, mock_helpers):
        """Test inject_stream SSE progress events include speed/eta/elapsed."""
        mock_fpb = Mock()
        mock_fpb.enter_fl_mode = Mock()
        mock_fpb.exit_fl_mode = Mock()

        def fake_inject(**kwargs):
            cb = kwargs.get("progress_callback")
            if cb:
                cb(50, 100)
                cb(100, 100)
            return True, {"slot": 0, "code_size": 64}

        mock_fpb.inject.side_effect = fake_inject
        mock_helpers.return_value = make_mock_helpers(mock_fpb)

        response = self.client.post(
            "/api/fpb/inject/stream",
            json={
                "source_content": "/* FPB_INJECT */\nvoid f() {}",
                "target_func": "original_f",
            },
        )

        body = response.get_data(as_text=True)
        events = _parse_sse_events(body)

        progress_events = [e for e in events if e["type"] == "progress"]
        self.assertGreater(len(progress_events), 0)

        for ev in progress_events:
            self.assertIn("speed", ev)
            self.assertIn("eta", ev)
            self.assertIn("elapsed", ev)


if __name__ == "__main__":
    unittest.main()

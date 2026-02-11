#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Integration tests for log file recording API routes.
"""

import json
import os
import tempfile
import unittest

from app import create_app
from core.state import state
from services.log_recorder import log_recorder


class TestLogFileRoutes(unittest.TestCase):
    """Test cases for log file recording API routes."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = create_app()
        self.client = self.app.test_client()
        self.temp_dir = tempfile.mkdtemp()

        # Stop any existing recording
        if log_recorder.enabled:
            log_recorder.stop()

    def tearDown(self):
        """Clean up test fixtures."""
        if log_recorder.enabled:
            log_recorder.stop()

        # Clean up temp files
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_start_log_recording(self):
        """Test starting log recording via API."""
        log_path = os.path.join(self.temp_dir, "test.log")

        response = self.client.post(
            "/api/log_file/start",
            data=json.dumps({"path": log_path}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertTrue(log_recorder.enabled)
        self.assertEqual(log_recorder.path, log_path)
        self.assertTrue(state.device.log_file_enabled)
        self.assertEqual(state.device.log_file_path, log_path)

    def test_start_log_recording_no_path(self):
        """Test starting log recording without path."""
        response = self.client.post(
            "/api/log_file/start",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("No path provided", data["error"])

    def test_stop_log_recording(self):
        """Test stopping log recording via API."""
        log_path = os.path.join(self.temp_dir, "test.log")

        # Start recording first
        log_recorder.start(log_path)
        state.device.log_file_enabled = True

        response = self.client.post("/api/log_file/stop")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertFalse(log_recorder.enabled)
        self.assertFalse(state.device.log_file_enabled)

    def test_stop_log_recording_not_started(self):
        """Test stopping log recording when not started."""
        response = self.client.post("/api/log_file/stop")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
        self.assertIn("Not recording", data["error"])

    def test_get_log_file_status(self):
        """Test getting log file recording status."""
        log_path = os.path.join(self.temp_dir, "test.log")

        # Start recording
        log_recorder.start(log_path)
        state.device.log_file_enabled = True
        state.device.log_file_path = log_path

        response = self.client.get("/api/log_file/status")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertTrue(data["enabled"])
        self.assertEqual(data["path"], log_path)
        self.assertTrue(data["config_enabled"])
        self.assertEqual(data["config_path"], log_path)

    def test_get_log_file_status_not_recording(self):
        """Test getting status when not recording."""
        response = self.client.get("/api/log_file/status")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertFalse(data["enabled"])
        self.assertEqual(data["path"], "")

    def test_log_messages_written_to_file(self):
        """Test that serial log messages are written to file."""
        log_path = os.path.join(self.temp_dir, "test.log")

        # Start recording
        self.client.post(
            "/api/log_file/start",
            data=json.dumps({"path": log_path}),
            content_type="application/json",
        )

        # Simulate serial data (this is what gets recorded)
        from services.log_recorder import log_recorder

        log_recorder.write("Serial data line 1")
        log_recorder.write("Serial data line 2")

        # Stop recording
        self.client.post("/api/log_file/stop")

        # Check file content
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Serial data line 1", content)
        self.assertIn("Serial data line 2", content)

    def test_config_persistence(self):
        """Test that log file config is persisted."""
        log_path = os.path.join(self.temp_dir, "test.log")

        # Start recording
        self.client.post(
            "/api/log_file/start",
            data=json.dumps({"path": log_path}),
            content_type="application/json",
        )

        # Check that config is saved
        self.assertTrue(state.device.log_file_enabled)
        self.assertEqual(state.device.log_file_path, log_path)

        # Stop recording
        self.client.post("/api/log_file/stop")

        # Check that config is updated
        self.assertFalse(state.device.log_file_enabled)


if __name__ == "__main__":
    unittest.main()

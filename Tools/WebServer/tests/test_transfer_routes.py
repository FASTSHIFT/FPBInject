#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for app/routes/transfer.py
"""

import base64
import io
import json
import os
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app.routes.transfer import bp
from core.file_transfer import FileTransfer, calc_crc16


def mock_run_in_device_worker(device, func, timeout=10.0):
    """Mock run_in_device_worker that executes func synchronously."""
    func()
    return True


class TestTransferRoutes(unittest.TestCase):
    """Tests for file transfer API routes."""

    def setUp(self):
        """Set up test environment."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(bp, url_prefix="/api")
        self.client = self.app.test_client()

        # Create mock FPB
        self.mock_fpb = Mock()
        self.mock_fpb.send_fl_cmd = Mock(return_value=(True, "[OK] Test"))
        self.mock_fpb.enter_fl_mode = Mock()
        self.mock_fpb.exit_fl_mode = Mock()

        # Create mock device
        self.mock_device = Mock()
        self.mock_device.chunk_size = 256
        self.mock_device.add_tool_log = Mock()

        # Set up patches
        self.state_patcher = patch("app.routes.transfer.state")
        self.mock_state = self.state_patcher.start()
        self.mock_state.device = self.mock_device

        self.helpers_patcher = patch("app.routes.transfer._get_helpers")
        self.mock_helpers = self.helpers_patcher.start()
        self.mock_helpers.return_value = (
            self.mock_device.add_tool_log,
            lambda: self.mock_fpb,
        )

        self.worker_patcher = patch(
            "app.routes.transfer.run_in_device_worker",
            side_effect=mock_run_in_device_worker,
        )
        self.mock_worker = self.worker_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.state_patcher.stop()
        self.helpers_patcher.stop()
        self.worker_patcher.stop()

    def test_transfer_list_success(self):
        """Test successful directory listing."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[OK] FLIST dir=1 file=2\n  D subdir\n  F test.txt 100\n  F data.bin 256",
        )
        response = self.client.get("/api/transfer/list?path=/data")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["path"], "/data")
        self.assertEqual(len(data["entries"]), 3)

    def test_transfer_list_default_path(self):
        """Test listing with default path."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[OK] FLIST dir=0 file=0")
        response = self.client.get("/api/transfer/list")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["path"], "/")

    def test_transfer_list_failure(self):
        """Test listing failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[ERR] Not a directory")
        response = self.client.get("/api/transfer/list?path=/test.txt")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_transfer_list_worker_timeout(self):
        """Test listing with worker timeout."""
        self.worker_patcher.stop()
        with patch("app.routes.transfer.run_in_device_worker", return_value=False):
            response = self.client.get("/api/transfer/list?path=/data")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertFalse(data["success"])
            self.assertIn("timeout", data["error"].lower())
        self.mock_worker = self.worker_patcher.start()

    def test_transfer_stat_success(self):
        """Test successful file stat."""
        self.mock_fpb.send_fl_cmd.return_value = (
            True,
            "[OK] FSTAT /test.txt size=1024 mtime=1234567890 type=file",
        )
        response = self.client.get("/api/transfer/stat?path=/test.txt")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["stat"]["size"], 1024)
        self.assertEqual(data["stat"]["type"], "file")

    def test_transfer_stat_no_path(self):
        """Test stat without path."""
        response = self.client.get("/api/transfer/stat")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Path not specified", data["error"])

    def test_transfer_stat_failure(self):
        """Test stat failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[ERR] File not found")
        response = self.client.get("/api/transfer/stat?path=/nonexistent")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_transfer_mkdir_success(self):
        """Test successful directory creation."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[OK] FMKDIR /newdir")
        response = self.client.post(
            "/api/transfer/mkdir",
            json={"path": "/newdir"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])

    def test_transfer_mkdir_no_path(self):
        """Test mkdir without path."""
        response = self.client.post(
            "/api/transfer/mkdir", json={}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Path not specified", data["error"])

    def test_transfer_mkdir_failure(self):
        """Test mkdir failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[ERR] Already exists")
        response = self.client.post(
            "/api/transfer/mkdir",
            json={"path": "/existing"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_transfer_delete_success(self):
        """Test successful file deletion."""
        self.mock_fpb.send_fl_cmd.return_value = (True, "[OK] FREMOVE /test.txt")
        response = self.client.post(
            "/api/transfer/delete",
            json={"path": "/test.txt"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])

    def test_transfer_delete_no_path(self):
        """Test delete without path."""
        response = self.client.post(
            "/api/transfer/delete", json={}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Path not specified", data["error"])

    def test_transfer_delete_failure(self):
        """Test delete failure."""
        self.mock_fpb.send_fl_cmd.return_value = (False, "[ERR] Permission denied")
        response = self.client.post(
            "/api/transfer/delete",
            json={"path": "/protected.txt"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_transfer_upload_no_file(self):
        """Test upload without file."""
        response = self.client.post("/api/transfer/upload")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("No file provided", data["error"])

    def test_transfer_upload_no_remote_path(self):
        """Test upload without remote path."""
        data = {"file": (io.BytesIO(b"test content"), "test.txt")}
        response = self.client.post(
            "/api/transfer/upload", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertFalse(result["success"])
        self.assertIn("Remote path not specified", result["error"])

    def test_transfer_download_no_path(self):
        """Test download without path."""
        response = self.client.post(
            "/api/transfer/download", json={}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Remote path not specified", data["error"])

    def test_transfer_cancel_success(self):
        """Test cancel transfer endpoint."""
        response = self.client.post("/api/transfer/cancel")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("Cancel requested", data["message"])

    def test_transfer_cancel_sets_flag(self):
        """Test that cancel sets the _transfer_cancelled flag."""
        from app.routes.transfer import _transfer_cancelled

        _transfer_cancelled.clear()
        self.assertFalse(_transfer_cancelled.is_set())
        response = self.client.post("/api/transfer/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(_transfer_cancelled.is_set())


class TestTransferHelpers(unittest.TestCase):
    """Tests for transfer helper functions."""

    def test_get_file_transfer(self):
        """Test _get_file_transfer creates FileTransfer instance."""
        mock_fpb = Mock()
        with patch("app.routes.transfer._get_helpers") as mock_helpers:
            mock_helpers.return_value = (Mock(), lambda: mock_fpb)
            with patch("app.routes.transfer.state") as mock_state:
                mock_state.device.chunk_size = 512
                from app.routes.transfer import _get_file_transfer

                ft = _get_file_transfer()
                self.assertEqual(ft.fpb, mock_fpb)
                self.assertEqual(ft.chunk_size, 512)

    def test_get_file_transfer_default_chunk_size(self):
        """Test _get_file_transfer with default chunk size."""
        mock_fpb = Mock()
        with patch("app.routes.transfer._get_helpers") as mock_helpers:
            mock_helpers.return_value = (Mock(), lambda: mock_fpb)
            with patch("app.routes.transfer.state") as mock_state:
                mock_state.device.chunk_size = None
                from app.routes.transfer import _get_file_transfer

                ft = _get_file_transfer()
                self.assertEqual(ft.chunk_size, 256)

    def test_run_serial_op_success(self):
        """Test _run_serial_op with successful operation."""
        with patch("app.routes.transfer.state") as mock_state:
            mock_state.device = Mock()
            with patch("app.routes.transfer.run_in_device_worker") as mock_run:

                def side_effect(device, func, timeout):
                    func()
                    return True

                mock_run.side_effect = side_effect
                from app.routes.transfer import _run_serial_op

                result = _run_serial_op(lambda: {"test": "data"})
                self.assertEqual(result, {"test": "data"})

    def test_run_serial_op_timeout(self):
        """Test _run_serial_op with timeout."""
        with patch("app.routes.transfer.state") as mock_state:
            mock_state.device = Mock()
            with patch("app.routes.transfer.run_in_device_worker") as mock_run:
                mock_run.return_value = False
                from app.routes.transfer import _run_serial_op

                result = _run_serial_op(lambda: {"test": "data"})
                self.assertIn("error", result)
                self.assertIn("timeout", result["error"].lower())

    def test_run_serial_op_exception(self):
        """Test _run_serial_op with exception."""
        with patch("app.routes.transfer.state") as mock_state:
            mock_state.device = Mock()
            with patch("app.routes.transfer.run_in_device_worker") as mock_run:

                def side_effect(device, func, timeout):
                    func()
                    return True

                mock_run.side_effect = side_effect
                from app.routes.transfer import _run_serial_op

                def raise_error():
                    raise ValueError("Test error")

                result = _run_serial_op(raise_error)
                self.assertIn("error", result)
                self.assertIn("Test error", result["error"])


if __name__ == "__main__":
    unittest.main()

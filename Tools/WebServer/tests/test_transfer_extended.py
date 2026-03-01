#!/usr/bin/env python3
"""Extended transfer route tests for upload/download coverage."""

import io
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from app.routes.transfer import bp, _transfer_cancelled  # noqa: E402


def mock_run_in_device_worker(device, func, timeout=10.0):
    """Mock that executes func synchronously."""
    func()
    return True


class TransferTestBase(unittest.TestCase):
    """Base class for transfer tests."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(bp, url_prefix="/api")
        self.client = self.app.test_client()

        self.mock_fpb = Mock()
        self.mock_fpb.enter_fl_mode = Mock()
        self.mock_fpb.exit_fl_mode = Mock()

        self.mock_device = Mock()
        self.mock_device.chunk_size = 64
        self.mock_device.verify_crc = False
        self.mock_device.transfer_max_retries = 3

        self.state_patcher = patch("app.routes.transfer.state")
        self.mock_state = self.state_patcher.start()
        self.mock_state.device = self.mock_device

        self.helpers_patcher = patch("app.routes.transfer._get_helpers")
        self.mock_helpers = self.helpers_patcher.start()
        self.mock_helpers.return_value = (
            Mock(),  # log_info
            Mock(),  # log_success
            Mock(),  # log_error
            Mock(),  # log_warn
            lambda: self.mock_fpb,  # get_fpb_inject
        )

        self.worker_patcher = patch(
            "app.routes.transfer.run_in_device_worker",
            side_effect=mock_run_in_device_worker,
        )
        self.mock_worker = self.worker_patcher.start()

        _transfer_cancelled.clear()

    def tearDown(self):
        self.state_patcher.stop()
        self.helpers_patcher.stop()
        self.worker_patcher.stop()

    def _parse_sse_events(self, response):
        """Parse SSE response into list of dicts."""
        events = []
        for line in response.data.decode().strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        return events


class TestUploadRoute(TransferTestBase):
    """Test /api/transfer/upload SSE endpoint."""

    @patch("app.routes.transfer._get_file_transfer")
    def test_upload_success(self, mock_get_ft):
        """Test successful file upload."""
        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fwrite.return_value = (True, "OK")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.reset_stats = Mock()
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        data = {
            "file": (io.BytesIO(b"hello world"), "test.txt"),
            "remote_path": "/data/test.txt",
        }
        response = self.client.post(
            "/api/transfer/upload",
            data=data,
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertTrue(len(results) > 0)
        self.assertTrue(results[-1]["success"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_upload_fopen_failure(self, mock_get_ft):
        """Test upload when fopen fails."""
        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fopen.return_value = (False, "Permission denied")
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        data = {
            "file": (io.BytesIO(b"data"), "test.txt"),
            "remote_path": "/data/test.txt",
        }
        response = self.client.post(
            "/api/transfer/upload",
            data=data,
            content_type="multipart/form-data",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])
        self.assertIn("Failed to open", results[-1]["error"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_upload_fwrite_failure(self, mock_get_ft):
        """Test upload when fwrite fails."""
        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fwrite.return_value = (False, "Write error")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.fpb = self.mock_fpb
        mock_ft.reset_stats = Mock()
        mock_get_ft.return_value = mock_ft

        data = {
            "file": (io.BytesIO(b"data"), "test.txt"),
            "remote_path": "/data/test.txt",
        }
        response = self.client.post(
            "/api/transfer/upload",
            data=data,
            content_type="multipart/form-data",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])
        self.assertIn("Write failed", results[-1]["error"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_upload_with_crc_success(self, mock_get_ft):
        """Test upload with CRC verification success."""
        self.mock_device.verify_crc = True

        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fwrite.return_value = (True, "OK")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.fcrc.return_value = (True, 11, 0)  # Will be overridden
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.reset_stats = Mock()
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        file_content = b"hello world"
        from utils.crc import crc16

        expected_crc = crc16(file_content)
        mock_ft.fcrc.return_value = (True, len(file_content), expected_crc)

        data = {
            "file": (io.BytesIO(file_content), "test.txt"),
            "remote_path": "/data/test.txt",
        }
        response = self.client.post(
            "/api/transfer/upload",
            data=data,
            content_type="multipart/form-data",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertTrue(results[-1]["success"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_upload_crc_mismatch(self, mock_get_ft):
        """Test upload with CRC mismatch."""
        self.mock_device.verify_crc = True

        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fwrite.return_value = (True, "OK")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.fcrc.return_value = (True, 11, 0xDEAD)  # Wrong CRC
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.reset_stats = Mock()
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        data = {
            "file": (io.BytesIO(b"hello world"), "test.txt"),
            "remote_path": "/data/test.txt",
        }
        response = self.client.post(
            "/api/transfer/upload",
            data=data,
            content_type="multipart/form-data",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])
        self.assertIn("CRC mismatch", results[-1]["error"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_upload_size_mismatch(self, mock_get_ft):
        """Test upload with size mismatch."""
        self.mock_device.verify_crc = True

        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fwrite.return_value = (True, "OK")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.fcrc.return_value = (True, 999, 0x1234)  # Wrong size
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.reset_stats = Mock()
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        data = {
            "file": (io.BytesIO(b"hello world"), "test.txt"),
            "remote_path": "/data/test.txt",
        }
        response = self.client.post(
            "/api/transfer/upload",
            data=data,
            content_type="multipart/form-data",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])
        self.assertIn("Size mismatch", results[-1]["error"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_upload_crc_check_failure(self, mock_get_ft):
        """Test upload when CRC check itself fails."""
        self.mock_device.verify_crc = True

        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fwrite.return_value = (True, "OK")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.fcrc.return_value = (False, 0, 0)  # CRC check failed
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.reset_stats = Mock()
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        data = {
            "file": (io.BytesIO(b"hello world"), "test.txt"),
            "remote_path": "/data/test.txt",
        }
        response = self.client.post(
            "/api/transfer/upload",
            data=data,
            content_type="multipart/form-data",
        )

        events = self._parse_sse_events(response)
        # Should still succeed (CRC warning, not failure)
        results = [e for e in events if e.get("type") == "result"]
        self.assertTrue(results[-1]["success"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_upload_cancel(self, mock_get_ft):
        """Test upload cancellation."""
        mock_ft = Mock()
        mock_ft.chunk_size = 64

        def fopen_sets_cancel(*args, **kwargs):
            _transfer_cancelled.set()
            return (True, "OK")

        mock_ft.fopen.side_effect = fopen_sets_cancel
        mock_ft.fwrite.return_value = (True, "OK")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.fpb = self.mock_fpb
        mock_ft.reset_stats = Mock()
        mock_get_ft.return_value = mock_ft

        data = {
            "file": (io.BytesIO(b"data" * 100), "test.txt"),
            "remote_path": "/data/test.txt",
        }
        response = self.client.post(
            "/api/transfer/upload",
            data=data,
            content_type="multipart/form-data",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertTrue(len(results) > 0)
        self.assertFalse(results[-1]["success"])

    def test_upload_worker_not_running(self):
        """Test upload when device worker is not running."""
        self.worker_patcher.stop()
        with patch("app.routes.transfer.run_in_device_worker", return_value=False):
            data = {
                "file": (io.BytesIO(b"data"), "test.txt"),
                "remote_path": "/data/test.txt",
            }
            response = self.client.post(
                "/api/transfer/upload",
                data=data,
                content_type="multipart/form-data",
            )
            events = self._parse_sse_events(response)
            results = [e for e in events if e.get("type") == "result"]
            self.assertFalse(results[-1]["success"])
            self.assertIn("worker", results[-1]["error"].lower())
        self.mock_worker = self.worker_patcher.start()


class TestDownloadRoute(TransferTestBase):
    """Test /api/transfer/download SSE endpoint."""

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_success(self, mock_get_ft):
        """Test successful file download."""
        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fstat.return_value = (True, {"size": 11, "type": "file"})
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fread.side_effect = [
            (True, b"hello world", ""),
            (True, b"", "EOF"),
        ]
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.reset_stats = Mock()
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/data/test.txt"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertTrue(results[-1]["success"])
        self.assertEqual(results[-1]["size"], 11)
        # Verify base64 data
        import base64

        decoded = base64.b64decode(results[-1]["data"])
        self.assertEqual(decoded, b"hello world")

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_stat_failure(self, mock_get_ft):
        """Test download when fstat fails."""
        mock_ft = Mock()
        mock_ft.fstat.return_value = (False, {"error": "Not found"})
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/nonexistent"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_directory_error(self, mock_get_ft):
        """Test download on directory."""
        mock_ft = Mock()
        mock_ft.fstat.return_value = (True, {"size": 0, "type": "dir"})
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/data"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])
        self.assertIn("directory", results[-1]["error"].lower())

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_empty_file(self, mock_get_ft):
        """Test download of empty file."""
        mock_ft = Mock()
        mock_ft.fstat.return_value = (True, {"size": 0, "type": "file"})
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/empty.txt"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])
        self.assertIn("empty", results[-1]["error"].lower())

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_fopen_failure(self, mock_get_ft):
        """Test download when fopen fails."""
        mock_ft = Mock()
        mock_ft.fstat.return_value = (True, {"size": 100, "type": "file"})
        mock_ft.fopen.return_value = (False, "Access denied")
        mock_ft.fpb = self.mock_fpb
        mock_ft.reset_stats = Mock()
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/protected.txt"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_fread_failure(self, mock_get_ft):
        """Test download when fread fails."""
        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fstat.return_value = (True, {"size": 100, "type": "file"})
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fread.return_value = (False, b"", "Read error")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.fpb = self.mock_fpb
        mock_ft.reset_stats = Mock()
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/data/test.txt"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_with_crc_success(self, mock_get_ft):
        """Test download with CRC verification."""
        self.mock_device.verify_crc = True

        file_content = b"test data here"
        from utils.crc import crc16

        expected_crc = crc16(file_content)

        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fstat.return_value = (True, {"size": len(file_content), "type": "file"})
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fread.side_effect = [
            (True, file_content, ""),
            (True, b"", "EOF"),
        ]
        mock_ft.fcrc.return_value = (True, len(file_content), expected_crc)
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.reset_stats = Mock()
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/data/test.txt"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertTrue(results[-1]["success"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_crc_mismatch(self, mock_get_ft):
        """Test download with CRC mismatch."""
        self.mock_device.verify_crc = True

        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fstat.return_value = (True, {"size": 10, "type": "file"})
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fread.side_effect = [
            (True, b"0123456789", ""),
            (True, b"", "EOF"),
        ]
        mock_ft.fcrc.return_value = (True, 10, 0xBEEF)  # Wrong CRC
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.fpb = self.mock_fpb
        mock_ft.reset_stats = Mock()
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/data/test.txt"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertFalse(results[-1]["success"])
        self.assertIn("CRC mismatch", results[-1]["error"])

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_cancel(self, mock_get_ft):
        """Test download cancellation."""
        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fstat.return_value = (True, {"size": 1000, "type": "file"})

        def fopen_sets_cancel(*args, **kwargs):
            _transfer_cancelled.set()
            return (True, "OK")

        mock_ft.fopen.side_effect = fopen_sets_cancel
        mock_ft.fread.return_value = (True, b"x" * 64, "")
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.fpb = self.mock_fpb
        mock_ft.reset_stats = Mock()
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/data/big.bin"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        results = [e for e in events if e.get("type") == "result"]
        self.assertTrue(len(results) > 0)
        self.assertFalse(results[-1]["success"])

    def test_download_worker_not_running(self):
        """Test download when device worker is not running."""
        self.worker_patcher.stop()
        with patch("app.routes.transfer.run_in_device_worker", return_value=False):
            response = self.client.post(
                "/api/transfer/download",
                json={"remote_path": "/data/test.txt"},
                content_type="application/json",
            )
            events = self._parse_sse_events(response)
            results = [e for e in events if e.get("type") == "result"]
            self.assertFalse(results[-1]["success"])
        self.mock_worker = self.worker_patcher.start()

    @patch("app.routes.transfer._get_file_transfer")
    def test_download_crc_check_failure(self, mock_get_ft):
        """Test download when CRC check itself fails."""
        self.mock_device.verify_crc = True

        mock_ft = Mock()
        mock_ft.chunk_size = 64
        mock_ft.fstat.return_value = (True, {"size": 5, "type": "file"})
        mock_ft.fopen.return_value = (True, "OK")
        mock_ft.fread.side_effect = [
            (True, b"hello", ""),
            (True, b"", "EOF"),
        ]
        mock_ft.fcrc.return_value = (False, 0, 0)
        mock_ft.fclose.return_value = (True, "OK")
        mock_ft.get_stats.return_value = {"packet_loss_rate": "0.0"}
        mock_ft.reset_stats = Mock()
        mock_ft.fpb = self.mock_fpb
        mock_get_ft.return_value = mock_ft

        response = self.client.post(
            "/api/transfer/download",
            json={"remote_path": "/data/test.txt"},
            content_type="application/json",
        )

        events = self._parse_sse_events(response)
        # CRC check failure is a warning, not an error
        results = [e for e in events if e.get("type") == "result"]
        self.assertTrue(results[-1]["success"])


if __name__ == "__main__":
    unittest.main()

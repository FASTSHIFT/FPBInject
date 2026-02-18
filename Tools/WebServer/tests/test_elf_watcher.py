#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ELF file watcher tests
"""

import os
import sys
import unittest
import tempfile
import time
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import state, DeviceState  # noqa: E402


class TestElfWatcher(unittest.TestCase):
    """ELF file watcher tests"""

    def setUp(self):
        """Reset state before each test"""
        state.device = DeviceState()

    def tearDown(self):
        """Clean up after each test"""
        from services.file_watcher_manager import stop_elf_watcher

        stop_elf_watcher()

    @patch("services.file_watcher.start_watching")
    def test_start_elf_watcher_success(self, mock_start):
        """Test starting ELF watcher successfully"""
        from services.file_watcher_manager import start_elf_watcher

        mock_watcher = Mock()
        mock_start.return_value = mock_watcher

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            result = start_elf_watcher(temp_path)

            self.assertTrue(result)
            mock_start.assert_called_once()
            self.assertFalse(state.device.elf_file_changed)
            self.assertGreater(state.device.elf_file_mtime, 0)
        finally:
            os.unlink(temp_path)

    def test_start_elf_watcher_no_path(self):
        """Test starting ELF watcher with no path"""
        from services.file_watcher_manager import start_elf_watcher

        result = start_elf_watcher("")
        self.assertFalse(result)

        result = start_elf_watcher(None)
        self.assertFalse(result)

    def test_start_elf_watcher_nonexistent_file(self):
        """Test starting ELF watcher with nonexistent file"""
        from services.file_watcher_manager import start_elf_watcher

        result = start_elf_watcher("/nonexistent/path/file.elf")
        self.assertFalse(result)

    @patch("services.file_watcher.start_watching")
    def test_start_elf_watcher_failure(self, mock_start):
        """Test starting ELF watcher with failure"""
        from services.file_watcher_manager import start_elf_watcher

        mock_start.side_effect = Exception("Failed to start")

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            result = start_elf_watcher(temp_path)
            self.assertFalse(result)
        finally:
            os.unlink(temp_path)

    @patch("services.file_watcher.stop_watching")
    def test_stop_elf_watcher(self, mock_stop):
        """Test stopping ELF watcher"""
        from services.file_watcher_manager import stop_elf_watcher
        import services.file_watcher_manager as fwm

        fwm._elf_watcher = Mock()

        stop_elf_watcher()

        mock_stop.assert_called_once()
        self.assertIsNone(fwm._elf_watcher)

    def test_stop_elf_watcher_when_none(self):
        """Test stopping ELF watcher when none exists"""
        from services.file_watcher_manager import stop_elf_watcher
        import services.file_watcher_manager as fwm

        fwm._elf_watcher = None

        # Should not raise
        stop_elf_watcher()

        self.assertIsNone(fwm._elf_watcher)

    def test_check_elf_file_changed_no_path(self):
        """Test check_elf_file_changed with no ELF path"""
        from services.file_watcher_manager import check_elf_file_changed

        state.device.elf_path = ""

        result = check_elf_file_changed()

        self.assertFalse(result["changed"])
        self.assertEqual(result["elf_path"], "")

    def test_check_elf_file_changed_nonexistent(self):
        """Test check_elf_file_changed with nonexistent file"""
        from services.file_watcher_manager import check_elf_file_changed

        state.device.elf_path = "/nonexistent/file.elf"

        result = check_elf_file_changed()

        self.assertFalse(result["changed"])

    def test_check_elf_file_changed_not_modified(self):
        """Test check_elf_file_changed when file not modified"""
        from services.file_watcher_manager import check_elf_file_changed

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            state.device.elf_file_mtime = os.path.getmtime(temp_path)
            state.device.elf_file_changed = False

            result = check_elf_file_changed()

            self.assertFalse(result["changed"])
            self.assertEqual(result["elf_path"], temp_path)
        finally:
            os.unlink(temp_path)

    def test_check_elf_file_changed_modified(self):
        """Test check_elf_file_changed when file is modified"""
        from services.file_watcher_manager import check_elf_file_changed

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            # Set old mtime
            state.device.elf_file_mtime = os.path.getmtime(temp_path) - 10
            state.device.elf_file_changed = False

            # Touch file to update mtime
            time.sleep(0.1)
            os.utime(temp_path, None)

            result = check_elf_file_changed()

            self.assertTrue(result["changed"])
            self.assertEqual(result["elf_path"], temp_path)
        finally:
            os.unlink(temp_path)

    def test_check_elf_file_changed_already_flagged(self):
        """Test check_elf_file_changed when already flagged"""
        from services.file_watcher_manager import check_elf_file_changed

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            state.device.elf_file_mtime = os.path.getmtime(temp_path)
            state.device.elf_file_changed = True

            result = check_elf_file_changed()

            self.assertTrue(result["changed"])
        finally:
            os.unlink(temp_path)

    def test_acknowledge_elf_change(self):
        """Test acknowledge_elf_change clears flag"""
        from services.file_watcher_manager import acknowledge_elf_change

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            state.device.elf_file_changed = True

            acknowledge_elf_change()

            self.assertFalse(state.device.elf_file_changed)
            # mtime should be updated
            self.assertGreater(state.device.elf_file_mtime, 0)
        finally:
            os.unlink(temp_path)

    def test_acknowledge_elf_change_no_file(self):
        """Test acknowledge_elf_change with no file"""
        from services.file_watcher_manager import acknowledge_elf_change

        state.device.elf_path = "/nonexistent/file.elf"
        state.device.elf_file_changed = True

        # Should not raise
        acknowledge_elf_change()

        self.assertFalse(state.device.elf_file_changed)

    def test_on_elf_file_change_callback(self):
        """Test _on_elf_file_change callback"""
        from services.file_watcher_manager import _on_elf_file_change

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            state.device.elf_file_changed = False

            _on_elf_file_change(temp_path, "modified")

            self.assertTrue(state.device.elf_file_changed)
        finally:
            os.unlink(temp_path)

    def test_on_elf_file_change_different_file(self):
        """Test _on_elf_file_change ignores different files"""
        from services.file_watcher_manager import _on_elf_file_change

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            state.device.elf_file_changed = False

            _on_elf_file_change("/some/other/file.elf", "modified")

            self.assertFalse(state.device.elf_file_changed)
        finally:
            os.unlink(temp_path)

    def test_on_elf_file_change_no_elf_path(self):
        """Test _on_elf_file_change when no ELF path configured"""
        from services.file_watcher_manager import _on_elf_file_change

        state.device.elf_path = ""
        state.device.elf_file_changed = False

        # Should not raise
        _on_elf_file_change("/some/file.elf", "modified")

        self.assertFalse(state.device.elf_file_changed)


class TestElfWatcherAPI(unittest.TestCase):
    """Test ELF watcher API endpoints"""

    def setUp(self):
        """Set up test client"""
        state.device = DeviceState()

        # Import app and create test client
        from app import create_app

        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up after each test"""
        from services.file_watcher_manager import stop_elf_watcher

        stop_elf_watcher()

    def test_api_elf_status_no_file(self):
        """Test GET /api/watch/elf_status with no ELF file"""
        state.device.elf_path = ""

        response = self.client.get("/api/watch/elf_status")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["changed"])

    def test_api_elf_status_not_changed(self):
        """Test GET /api/watch/elf_status when file not changed"""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            state.device.elf_file_mtime = os.path.getmtime(temp_path)
            state.device.elf_file_changed = False

            response = self.client.get("/api/watch/elf_status")

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertFalse(data["changed"])
            self.assertEqual(data["elf_path"], temp_path)
        finally:
            os.unlink(temp_path)

    def test_api_elf_status_changed(self):
        """Test GET /api/watch/elf_status when file changed"""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            state.device.elf_file_changed = True

            response = self.client.get("/api/watch/elf_status")

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertTrue(data["changed"])
        finally:
            os.unlink(temp_path)

    def test_api_elf_acknowledge(self):
        """Test POST /api/watch/elf_acknowledge"""
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            temp_path = f.name

        try:
            state.device.elf_path = temp_path
            state.device.elf_file_changed = True

            response = self.client.post("/api/watch/elf_acknowledge")

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertFalse(state.device.elf_file_changed)
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)

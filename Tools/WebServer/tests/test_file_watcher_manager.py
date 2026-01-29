#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File watcher manager tests
"""

import os
import sys
import unittest
import tempfile
import time
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import state, DeviceState


class TestFileWatcherManager(unittest.TestCase):
    """File watcher manager tests"""

    def setUp(self):
        """Reset state before each test"""
        state.device = DeviceState()
        state.file_watcher = None

    def tearDown(self):
        """Clean up after each test"""
        state.file_watcher = None

    @patch("services.file_watcher.start_watching")
    def test_start_file_watcher_success(self, mock_start):
        """Test starting file watcher successfully"""
        from services.file_watcher_manager import start_file_watcher

        mock_watcher = Mock()
        mock_start.return_value = mock_watcher

        result = start_file_watcher(["/tmp/test"])

        self.assertTrue(result)
        self.assertEqual(state.file_watcher, mock_watcher)
        mock_start.assert_called_once()

    @patch("services.file_watcher.start_watching")
    def test_start_file_watcher_failure(self, mock_start):
        """Test starting file watcher with failure"""
        from services.file_watcher_manager import start_file_watcher

        mock_start.side_effect = Exception("Failed to start")

        result = start_file_watcher(["/tmp/test"])

        self.assertFalse(result)
        self.assertIsNone(state.file_watcher)

    @patch("services.file_watcher.stop_watching")
    def test_stop_file_watcher(self, mock_stop):
        """Test stopping file watcher"""
        from services.file_watcher_manager import stop_file_watcher

        state.file_watcher = Mock()

        stop_file_watcher()

        mock_stop.assert_called_once()
        self.assertIsNone(state.file_watcher)

    def test_stop_file_watcher_when_none(self):
        """Test stopping file watcher when none exists"""
        from services.file_watcher_manager import stop_file_watcher

        state.file_watcher = None

        # Should not raise
        stop_file_watcher()

        self.assertIsNone(state.file_watcher)

    @patch("services.file_watcher.stop_watching")
    def test_stop_file_watcher_exception(self, mock_stop):
        """Test stopping file watcher with exception"""
        from services.file_watcher_manager import stop_file_watcher

        state.file_watcher = Mock()
        mock_stop.side_effect = Exception("Stop failed")

        # Should not raise
        stop_file_watcher()

        self.assertIsNone(state.file_watcher)

    @patch("services.file_watcher_manager.start_file_watcher")
    @patch("services.file_watcher_manager.stop_file_watcher")
    def test_restart_file_watcher(self, mock_stop, mock_start):
        """Test restarting file watcher"""
        from services.file_watcher_manager import restart_file_watcher

        state.device.watch_dirs = ["/tmp/test"]

        restart_file_watcher()

        mock_stop.assert_called_once()
        mock_start.assert_called_once_with(["/tmp/test"])

    @patch("services.file_watcher_manager.start_file_watcher")
    @patch("services.file_watcher_manager.stop_file_watcher")
    def test_restart_file_watcher_no_dirs(self, mock_stop, mock_start):
        """Test restarting file watcher with no watch dirs"""
        from services.file_watcher_manager import restart_file_watcher

        state.device.watch_dirs = []

        restart_file_watcher()

        mock_stop.assert_called_once()
        mock_start.assert_not_called()

    @patch("services.file_watcher_manager.start_file_watcher")
    def test_restore_file_watcher_enabled(self, mock_start):
        """Test restoring file watcher when auto_compile is enabled"""
        from services.file_watcher_manager import restore_file_watcher

        state.device.auto_compile = True
        state.device.watch_dirs = ["/tmp/test"]

        restore_file_watcher()

        mock_start.assert_called_once_with(["/tmp/test"])

    @patch("services.file_watcher_manager.start_file_watcher")
    def test_restore_file_watcher_disabled(self, mock_start):
        """Test restoring file watcher when auto_compile is disabled"""
        from services.file_watcher_manager import restore_file_watcher

        state.device.auto_compile = False
        state.device.watch_dirs = ["/tmp/test"]

        restore_file_watcher()

        mock_start.assert_not_called()

    @patch("services.file_watcher_manager.start_file_watcher")
    def test_restore_file_watcher_no_dirs(self, mock_start):
        """Test restoring file watcher with no watch dirs"""
        from services.file_watcher_manager import restore_file_watcher

        state.device.auto_compile = True
        state.device.watch_dirs = []

        restore_file_watcher()

        mock_start.assert_not_called()

    @patch("services.file_watcher_manager._trigger_auto_inject")
    def test_on_file_change_with_auto_compile(self, mock_trigger):
        """Test file change callback with auto_compile enabled"""
        from services.file_watcher_manager import _on_file_change

        state.device.auto_compile = True

        _on_file_change("/tmp/test.c", "modified")

        mock_trigger.assert_called_once_with("/tmp/test.c")
        # Check pending change was added
        self.assertTrue(len(state.pending_changes) > 0)

    @patch("services.file_watcher_manager._trigger_auto_inject")
    def test_on_file_change_without_auto_compile(self, mock_trigger):
        """Test file change callback with auto_compile disabled"""
        from services.file_watcher_manager import _on_file_change

        state.device.auto_compile = False

        _on_file_change("/tmp/test.c", "modified")

        mock_trigger.assert_not_called()


class TestTriggerAutoInject(unittest.TestCase):
    """Test _trigger_auto_inject function"""

    def setUp(self):
        """Reset state before each test"""
        state.device = DeviceState()

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_no_markers(self, mock_gen_class, mock_get_fpb):
        """Test auto inject when no markers found"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.return_value = []
            mock_gen_class.return_value = mock_gen

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.2)

            self.assertEqual(state.device.auto_inject_status, "idle")
            self.assertEqual(state.device.auto_inject_modified_funcs, [])
        finally:
            os.unlink(temp_path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_no_markers_with_active_inject(
        self, mock_gen_class, mock_get_fpb
    ):
        """Test auto inject clears injection when markers removed"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Setup: device has active injection
        state.device.inject_active = True
        state.device.last_inject_target = "test_func"

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.return_value = []
            mock_gen_class.return_value = mock_gen

            mock_fpb = Mock()
            mock_fpb.unpatch.return_value = (True, "")
            mock_get_fpb.return_value = mock_fpb

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.2)

            mock_fpb.enter_fl_mode.assert_called_once()
            mock_fpb.unpatch.assert_called_once_with(0)
            mock_fpb.exit_fl_mode.assert_called_once()
            self.assertFalse(state.device.inject_active)
        finally:
            os.unlink(temp_path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_generate_patch_fails(
        self, mock_gen_class, mock_get_fpb
    ):
        """Test auto inject when patch generation fails"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.return_value = ["test_func"]
            mock_gen.generate_patch.return_value = (None, [])
            mock_gen_class.return_value = mock_gen

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.2)

            self.assertEqual(state.device.auto_inject_status, "failed")
            self.assertIn("Failed to generate", state.device.auto_inject_message)
        finally:
            os.unlink(temp_path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_device_not_connected(
        self, mock_gen_class, mock_get_fpb
    ):
        """Test auto inject when device not connected"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.return_value = ["test_func"]
            mock_gen.generate_patch.return_value = (
                "void inject_test_func(void) {}",
                ["test_func"],
            )
            mock_gen_class.return_value = mock_gen

            # Device not connected
            state.device.ser = None

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.2)

            self.assertEqual(state.device.auto_inject_status, "failed")
            self.assertIn("not connected", state.device.auto_inject_message)
        finally:
            os.unlink(temp_path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_success(self, mock_gen_class, mock_get_fpb):
        """Test successful auto inject"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.return_value = ["test_func"]
            mock_gen.generate_patch.return_value = (
                "void inject_test_func(void) {}",
                ["test_func"],
            )
            mock_gen_class.return_value = mock_gen

            # Mock connected device
            mock_ser = Mock()
            mock_ser.isOpen.return_value = True
            state.device.ser = mock_ser

            mock_fpb = Mock()
            mock_fpb.inject_multi.return_value = (
                True,
                {
                    "successful_count": 1,
                    "total_count": 1,
                    "injections": [
                        {
                            "success": True,
                            "target_func": "test_func",
                            "inject_func": "inject_test_func",
                        }
                    ],
                    "errors": [],
                },
            )
            mock_fpb.info.return_value = ({}, None)
            mock_get_fpb.return_value = mock_fpb

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.3)

            self.assertEqual(state.device.auto_inject_status, "success")
            self.assertTrue(state.device.inject_active)
            mock_fpb.enter_fl_mode.assert_called_once()
            mock_fpb.inject_multi.assert_called_once()
            mock_fpb.exit_fl_mode.assert_called_once()
        finally:
            os.unlink(temp_path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_partial_success(self, mock_gen_class, mock_get_fpb):
        """Test auto inject with partial success"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.return_value = ["func1", "func2"]
            mock_gen.generate_patch.return_value = (
                "void inject_func1(void) {} void inject_func2(void) {}",
                ["func1", "func2"],
            )
            mock_gen_class.return_value = mock_gen

            # Mock connected device
            mock_ser = Mock()
            mock_ser.isOpen.return_value = True
            state.device.ser = mock_ser

            mock_fpb = Mock()
            mock_fpb.inject_multi.return_value = (
                True,
                {
                    "successful_count": 1,
                    "total_count": 2,
                    "injections": [
                        {
                            "success": True,
                            "target_func": "func1",
                            "inject_func": "inject_func1",
                        },
                        {
                            "success": False,
                            "target_func": "func2",
                            "error": "No slot",
                        },
                    ],
                    "errors": ["func2 failed"],
                },
            )
            mock_fpb.info.return_value = ({}, None)
            mock_get_fpb.return_value = mock_fpb

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.3)

            self.assertEqual(state.device.auto_inject_status, "success")
            self.assertIn("1/2", state.device.auto_inject_message)
        finally:
            os.unlink(temp_path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_failure(self, mock_gen_class, mock_get_fpb):
        """Test auto inject failure"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.return_value = ["test_func"]
            mock_gen.generate_patch.return_value = (
                "void inject_test_func(void) {}",
                ["test_func"],
            )
            mock_gen_class.return_value = mock_gen

            # Mock connected device
            mock_ser = Mock()
            mock_ser.isOpen.return_value = True
            state.device.ser = mock_ser

            mock_fpb = Mock()
            mock_fpb.inject_multi.return_value = (
                False,
                {"error": "Compile failed", "errors": ["Syntax error"]},
            )
            mock_get_fpb.return_value = mock_fpb

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.3)

            self.assertEqual(state.device.auto_inject_status, "failed")
            self.assertIn("failed", state.device.auto_inject_message.lower())
        finally:
            os.unlink(temp_path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_exception(self, mock_gen_class, mock_get_fpb):
        """Test auto inject with exception"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.side_effect = Exception("Parse error")
            mock_gen_class.return_value = mock_gen

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.2)

            self.assertEqual(state.device.auto_inject_status, "failed")
            self.assertIn("Error", state.device.auto_inject_message)
        finally:
            os.unlink(temp_path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_trigger_auto_inject_many_functions(self, mock_gen_class, mock_get_fpb):
        """Test auto inject with more than 3 functions"""
        from services.file_watcher_manager import _trigger_auto_inject

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void test_func(void) {}")
            temp_path = f.name

        try:
            mock_gen = Mock()
            mock_gen.find_marked_functions.return_value = [
                "func1",
                "func2",
                "func3",
                "func4",
                "func5",
            ]
            mock_gen.generate_patch.return_value = (
                "void inject_func1(void) {}",
                ["func1", "func2", "func3", "func4", "func5"],
            )
            mock_gen_class.return_value = mock_gen

            # Mock connected device
            mock_ser = Mock()
            mock_ser.isOpen.return_value = True
            state.device.ser = mock_ser

            mock_fpb = Mock()
            mock_fpb.inject_multi.return_value = (
                True,
                {
                    "successful_count": 5,
                    "total_count": 5,
                    "injections": [
                        {
                            "success": True,
                            "target_func": f"func{i}",
                            "inject_func": f"inject_func{i}",
                        }
                        for i in range(1, 6)
                    ],
                    "errors": [],
                },
            )
            mock_fpb.info.return_value = ({}, None)
            mock_get_fpb.return_value = mock_fpb

            _trigger_auto_inject(temp_path)

            # Wait for background thread
            time.sleep(0.3)

            self.assertEqual(state.device.auto_inject_status, "success")
            # Should show "etc." for more than 3 functions
            self.assertIn("etc", state.device.auto_inject_message)
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)

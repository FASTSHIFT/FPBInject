#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State management tests
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.core.state import DeviceState, AppState  # noqa: E402
from fpbinject.core.config_schema import PERSISTENT_KEYS  # noqa: E402


class TestDeviceState(unittest.TestCase):
    """DeviceState tests"""

    def test_init_defaults(self):
        """Test default initialization"""
        device = DeviceState()

        self.assertIsNone(device.ser)
        self.assertEqual(device.baudrate, 115200)
        self.assertEqual(device.patch_mode, "trampoline")
        self.assertEqual(device.upload_chunk_size, 128)

    def test_add_tool_log(self):
        """Test adding tool log"""
        device = DeviceState()

        device.add_tool_log("Test message 1")
        device.add_tool_log("Test message 2")

        self.assertEqual(len(device.tool_log), 2)
        self.assertEqual(device.tool_log[0]["message"], "Test message 1")
        self.assertEqual(device.tool_log[1]["id"], 1)

    def test_add_tool_log_limit(self):
        """Test tool log size limit"""
        device = DeviceState()
        device.tool_log_max_size = 10

        for i in range(20):
            device.add_tool_log(f"Message {i}")

        self.assertEqual(len(device.tool_log), 10)

    def test_to_dict(self):
        """Test exporting to dict"""
        device = DeviceState()
        device.port = "/dev/ttyUSB0"
        device.baudrate = 921600
        device.elf_path = "/path/to/elf"

        result = device.to_dict()

        self.assertEqual(result["port"], "/dev/ttyUSB0")
        self.assertEqual(result["baudrate"], 921600)
        self.assertEqual(result["elf_path"], "/path/to/elf")

    def test_from_dict(self):
        """Test importing from dict"""
        device = DeviceState()
        data = {
            "port": "/dev/ttyACM0",
            "baudrate": 460800,
            "patch_mode": "debugmon",
            "unknown_key": "ignored",
        }

        device.from_dict(data)

        self.assertEqual(device.port, "/dev/ttyACM0")
        self.assertEqual(device.baudrate, 460800)
        self.assertEqual(device.patch_mode, "debugmon")


class TestAppState(unittest.TestCase):
    """AppState tests"""

    def test_init(self):
        """Test initialization"""
        with patch("fpbinject.core.state.AppState.load_config"):
            app_state = AppState()

        self.assertIsNotNone(app_state.device)
        self.assertEqual(app_state.pending_changes, [])
        self.assertFalse(app_state.symbols_loaded)

    def test_get_default_patch_template(self):
        """Test default patch template"""
        with patch("fpbinject.core.state.AppState.load_config"):
            app_state = AppState()

        template = app_state._get_default_patch_template()

        self.assertIn("FPBInject", template)
        self.assertIn("FPB_INJECT", template)
        self.assertIn("target_function", template)

    def test_add_pending_change(self):
        """Test adding pending change"""
        with patch("fpbinject.core.state.AppState.load_config"):
            app_state = AppState()

        app_state.add_pending_change("/tmp/test.c", "modified")

        changes = app_state.get_pending_changes()
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["path"], "/tmp/test.c")
        self.assertEqual(changes[0]["type"], "modified")

    def test_add_pending_change_limit(self):
        """Test pending changes limit"""
        with patch("fpbinject.core.state.AppState.load_config"):
            app_state = AppState()

        for i in range(150):
            app_state.add_pending_change(f"/tmp/test{i}.c", "modified")

        changes = app_state.get_pending_changes()
        self.assertEqual(len(changes), 100)

    def test_clear_pending_changes(self):
        """Test clearing pending changes"""
        with patch("fpbinject.core.state.AppState.load_config"):
            app_state = AppState()

        app_state.add_pending_change("/tmp/test.c", "modified")
        app_state.clear_pending_changes()

        self.assertEqual(len(app_state.get_pending_changes()), 0)

    def test_save_config(self):
        """Test saving config"""
        with patch("fpbinject.core.state.AppState.load_config"):
            app_state = AppState()

        app_state.device.port = "/dev/ttyUSB0"
        app_state.device.baudrate = 921600

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_path = f.name

        try:
            app_state.config_path = config_path
            app_state.save_config()

            with open(config_path, "r") as f:
                saved = json.load(f)

            self.assertEqual(saved["port"], "/dev/ttyUSB0")
            self.assertEqual(saved["baudrate"], 921600)
            self.assertIn("version", saved)
        finally:
            os.unlink(config_path)

    def test_load_config_not_found(self):
        """Test loading config when file not found"""
        with patch("fpbinject.core.state.AppState.load_config"):
            app_state = AppState()
        app_state.configure("/nonexistent/config.json")

        # Should use defaults
        self.assertEqual(app_state.device.baudrate, 115200)
        self.assertTrue(app_state.first_launch)

    def test_load_config_success(self):
        """Test loading config successfully"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"port": "/dev/ttyACM0", "baudrate": 460800}, f)
            config_path = f.name

        try:
            app_state = AppState()
            app_state.configure(config_path)

            self.assertEqual(app_state.device.port, "/dev/ttyACM0")
            self.assertEqual(app_state.device.baudrate, 460800)
        finally:
            os.unlink(config_path)

    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            config_path = f.name

        try:
            with patch("fpbinject.core.state.AppState.load_config"):
                app_state = AppState()
            app_state.configure(config_path)

            # Should use defaults on error
            self.assertEqual(app_state.device.baudrate, 115200)
        finally:
            os.unlink(config_path)


if __name__ == "__main__":
    unittest.main()


class TestPersistentKeys(unittest.TestCase):
    """Test persistent keys coverage"""

    def test_all_persistent_keys_exist(self):
        """Test all persistent keys exist in DeviceState"""
        device = DeviceState()

        for key in PERSISTENT_KEYS:
            self.assertTrue(hasattr(device, key), f"DeviceState missing key: {key}")

    def test_round_trip_all_keys(self):
        """Test round-trip for all persistent keys"""
        device1 = DeviceState()
        device1.port = "/dev/test"
        device1.baudrate = 9600
        device1.elf_path = "/path/to/elf"
        device1.toolchain_path = "/path/to/toolchain"
        device1.compile_commands_path = "/path/to/compile_commands.json"
        device1.watch_dirs = ["/dir1", "/dir2"]
        device1.patch_mode = "debugmon"
        device1.upload_chunk_size = 256
        device1.download_chunk_size = 2048
        device1.serial_tx_fragment_size = 32
        device1.serial_tx_fragment_delay = 0.01
        device1.auto_connect = True
        device1.auto_compile = True
        device1.enable_decompile = True
        device1.ghidra_path = "/opt/ghidra_11.0"
        device1.transfer_max_retries = 5
        device1.log_file_enabled = True
        device1.log_file_path = "/tmp/test.log"

        data = device1.to_dict()

        device2 = DeviceState()
        device2.from_dict(data)

        for key in PERSISTENT_KEYS:
            self.assertEqual(
                getattr(device1, key),
                getattr(device2, key),
                f"Key mismatch: {key}",
            )

    def test_ghidra_path_persistence(self):
        """Test ghidra_path is properly persisted"""
        device = DeviceState()
        device.ghidra_path = "/home/user/ghidra_11.2.1_PUBLIC"

        data = device.to_dict()
        self.assertIn("ghidra_path", data)
        self.assertEqual(data["ghidra_path"], "/home/user/ghidra_11.2.1_PUBLIC")

        device2 = DeviceState()
        device2.from_dict(data)
        self.assertEqual(device2.ghidra_path, "/home/user/ghidra_11.2.1_PUBLIC")


class TestToolLogHandler(unittest.TestCase):
    """ToolLogHandler tests"""

    def test_emit_info(self):
        """Test emit with INFO level"""
        from fpbinject.core.state import ToolLogHandler
        import logging

        device = DeviceState()
        handler = ToolLogHandler(device, prefix="test")
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        self.assertEqual(len(device.tool_log), 1)
        self.assertIn("[INFO]", device.tool_log[0]["message"])
        self.assertIn("test:", device.tool_log[0]["message"])

    def test_emit_warning(self):
        """Test emit with WARNING level"""
        from fpbinject.core.state import ToolLogHandler
        import logging

        device = DeviceState()
        handler = ToolLogHandler(device)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="warn msg",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        self.assertIn("[WARN]", device.tool_log[0]["message"])

    def test_emit_no_prefix(self):
        """Test emit without prefix"""
        from fpbinject.core.state import ToolLogHandler
        import logging

        device = DeviceState()
        handler = ToolLogHandler(device)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="err",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        self.assertIn("[ERROR]", device.tool_log[0]["message"])
        self.assertNotIn(
            ":", device.tool_log[0]["message"].split("]")[1].split("err")[0].strip()
        )


class TestToolLogFunction(unittest.TestCase):
    """tool_log and _get_caller_name tests"""

    def test_tool_log_formats_message(self):
        """Test tool_log formats with caller name"""
        from fpbinject.core.state import tool_log

        device = DeviceState()
        tool_log(device, "INFO", "test message")

        self.assertEqual(len(device.tool_log), 1)
        msg = device.tool_log[0]["message"]
        self.assertIn("[INFO]", msg)
        self.assertIn("test message", msg)
        # Should contain the caller function name
        self.assertIn("test_tool_log_formats_message", msg)

    def test_get_caller_name(self):
        """Test _get_caller_name returns correct function name"""
        from fpbinject.core.state import _get_caller_name

        name = _get_caller_name(depth=1)
        self.assertEqual(name, "test_get_caller_name")

    def test_get_caller_name_deep(self):
        """Test _get_caller_name with deeper depth"""
        from fpbinject.core.state import _get_caller_name

        def inner():
            return _get_caller_name(depth=2)

        name = inner()
        self.assertEqual(name, "test_get_caller_name_deep")

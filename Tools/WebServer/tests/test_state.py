#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State module tests
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import DeviceState, AppState, PERSISTENT_KEYS, CONFIG_VERSION


class TestDeviceState(unittest.TestCase):
    """DeviceState test cases"""

    def test_init_default_values(self):
        """Test initializing default values"""
        state = DeviceState()

        # Serial related
        self.assertIsNone(state.ser)
        self.assertIsNone(state.port)
        self.assertEqual(state.baudrate, 115200)
        self.assertEqual(state.timeout, 2)

        # Configuration related
        self.assertEqual(state.elf_path, "")
        self.assertEqual(state.toolchain_path, "")
        self.assertEqual(state.compile_commands_path, "")
        self.assertEqual(state.watch_dirs, [])
        self.assertEqual(state.patch_mode, "trampoline")
        self.assertEqual(state.chunk_size, 128)
        self.assertEqual(state.tx_chunk_size, 0)
        self.assertEqual(state.tx_chunk_delay, 0.005)

        # Auto settings
        self.assertFalse(state.auto_connect)
        self.assertFalse(state.auto_compile)

        # Injection status
        self.assertIsNone(state.last_inject_target)
        self.assertIsNone(state.last_inject_func)
        self.assertFalse(state.inject_active)

        # Logs
        self.assertEqual(state.serial_log, [])
        self.assertEqual(state.raw_serial_log, [])
        self.assertEqual(state.log_max_size, 5000)

    def test_to_dict(self):
        """Test converting to dictionary"""
        state = DeviceState()
        state.elf_path = "/test/path.elf"
        state.toolchain_path = "/usr/bin"
        state.patch_mode = "debugmon"
        state.baudrate = 921600
        state.watch_dirs = ["/dir1", "/dir2"]

        d = state.to_dict()

        # Verify all persistent keys exist
        for key in PERSISTENT_KEYS:
            self.assertIn(key, d)

        # Verify values
        self.assertEqual(d["elf_path"], "/test/path.elf")
        self.assertEqual(d["toolchain_path"], "/usr/bin")
        self.assertEqual(d["patch_mode"], "debugmon")
        self.assertEqual(d["baudrate"], 921600)
        self.assertEqual(d["watch_dirs"], ["/dir1", "/dir2"])

    def test_from_dict(self):
        """Test importing from dictionary"""
        state = DeviceState()

        data = {
            "port": "/dev/ttyUSB0",
            "baudrate": 460800,
            "elf_path": "/my/elf.elf",
            "toolchain_path": "/opt/toolchain/bin",
            "compile_commands_path": "/build/compile_commands.json",
            "watch_dirs": ["/src"],
            "patch_mode": "direct",
            "chunk_size": 256,
            "tx_chunk_size": 16,
            "tx_chunk_delay": 0.01,
            "auto_connect": True,
            "auto_compile": True,
        }

        state.from_dict(data)

        self.assertEqual(state.port, "/dev/ttyUSB0")
        self.assertEqual(state.baudrate, 460800)
        self.assertEqual(state.elf_path, "/my/elf.elf")
        self.assertEqual(state.toolchain_path, "/opt/toolchain/bin")
        self.assertEqual(state.patch_mode, "direct")
        self.assertEqual(state.chunk_size, 256)
        self.assertEqual(state.tx_chunk_size, 16)
        self.assertEqual(state.tx_chunk_delay, 0.01)
        self.assertTrue(state.auto_connect)
        self.assertTrue(state.auto_compile)

    def test_from_dict_partial(self):
        """Test partial import"""
        state = DeviceState()
        state.baudrate = 115200  # Default value
        state.patch_mode = "trampoline"  # Default value

        # Only update partial fields
        state.from_dict({"baudrate": 921600})

        self.assertEqual(state.baudrate, 921600)
        self.assertEqual(state.patch_mode, "trampoline")  # Unchanged

    def test_from_dict_ignore_unknown(self):
        """Test ignoring unknown keys"""
        state = DeviceState()

        # Contains unknown keys
        state.from_dict({"unknown_key": "value", "baudrate": 9600})

        self.assertEqual(state.baudrate, 9600)
        self.assertFalse(hasattr(state, "unknown_key") and state.unknown_key == "value")

    def test_auto_inject_state(self):
        """Test auto injection status fields"""
        state = DeviceState()

        self.assertEqual(state.auto_inject_status, "idle")
        self.assertEqual(state.auto_inject_message, "")
        self.assertEqual(state.auto_inject_source_file, "")
        self.assertEqual(state.auto_inject_modified_funcs, [])
        self.assertEqual(state.auto_inject_progress, 0)


class TestAppState(unittest.TestCase):
    """AppState test cases"""

    def test_init(self):
        """Test initialization"""
        # Use temporary config file
        app_state = AppState()

        self.assertIsNotNone(app_state.device)
        self.assertIsInstance(app_state.device, DeviceState)
        self.assertIsNone(app_state.file_watcher)
        self.assertEqual(app_state.pending_changes, [])
        self.assertIsNone(app_state.last_change_time)
        self.assertEqual(app_state.symbols, {})
        self.assertFalse(app_state.symbols_loaded)

    def test_add_pending_change(self):
        """Test adding pending changes"""
        app_state = AppState()

        app_state.add_pending_change("/path/to/file.c", "modified")

        self.assertEqual(len(app_state.pending_changes), 1)
        change = app_state.pending_changes[0]
        self.assertEqual(change["path"], "/path/to/file.c")
        self.assertEqual(change["type"], "modified")
        self.assertIn("time", change)
        self.assertIsNotNone(app_state.last_change_time)

    def test_add_pending_change_multiple(self):
        """Test adding multiple changes"""
        app_state = AppState()

        app_state.add_pending_change("/file1.c", "modified")
        app_state.add_pending_change("/file2.c", "created")
        app_state.add_pending_change("/file3.c", "deleted")

        self.assertEqual(len(app_state.pending_changes), 3)

    def test_add_pending_change_limit(self):
        """Test changes quantity limit"""
        app_state = AppState()

        # Add more than 100 changes
        for i in range(150):
            app_state.add_pending_change(f"/file{i}.c", "modified")

        # Should only keep last 100
        self.assertEqual(len(app_state.pending_changes), 100)
        # First one should be file50.c
        self.assertEqual(app_state.pending_changes[0]["path"], "/file50.c")

    def test_clear_pending_changes(self):
        """Test clearing pending changes"""
        app_state = AppState()

        app_state.add_pending_change("/file.c", "modified")
        app_state.clear_pending_changes()

        self.assertEqual(app_state.pending_changes, [])

    def test_get_pending_changes(self):
        """Test getting pending changes"""
        app_state = AppState()

        app_state.add_pending_change("/file.c", "modified")

        changes = app_state.get_pending_changes()

        # Should return copy
        self.assertEqual(len(changes), 1)
        self.assertIsNot(changes, app_state.pending_changes)

    def test_default_patch_template(self):
        """Test default patch template"""
        app_state = AppState()

        template = app_state.patch_template

        self.assertIn("FPBInject", template)
        self.assertIn("inject_", template)
        self.assertIn("#include", template)


class TestConfigPersistence(unittest.TestCase):
    """Configuration persistence test"""

    def setUp(self):
        """Create temporary config file"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")

    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)

    def test_save_and_load_config(self):
        """Test saving and loading configuration"""
        import core.state as core_state_module

        # Temporarily replace config file path
        original_config_file = core_state_module.CONFIG_FILE
        core_state_module.CONFIG_FILE = self.config_file

        try:
            app_state = AppState()
            app_state.device.elf_path = "/test/elf.elf"
            app_state.device.toolchain_path = "/test/toolchain"
            app_state.device.patch_mode = "debugmon"

            # Save
            app_state.save_config()

            # Verify file was created
            self.assertTrue(os.path.exists(self.config_file))

            # Read and verify
            with open(self.config_file, "r") as f:
                config = json.load(f)

            self.assertEqual(config["elf_path"], "/test/elf.elf")
            self.assertEqual(config["toolchain_path"], "/test/toolchain")
            self.assertEqual(config["patch_mode"], "debugmon")
            self.assertEqual(config["version"], CONFIG_VERSION)

            # Create new state and load
            new_state = AppState()

            self.assertEqual(new_state.device.elf_path, "/test/elf.elf")
            self.assertEqual(new_state.device.patch_mode, "debugmon")

        finally:
            core_state_module.CONFIG_FILE = original_config_file

    def test_load_nonexistent_config(self):
        """Test loading non-existent config file"""
        import core.state as core_state_module

        original_config_file = core_state_module.CONFIG_FILE
        core_state_module.CONFIG_FILE = "/nonexistent/path/config.json"

        try:
            # Should not raise exception
            app_state = AppState()

            # Should use default values
            self.assertEqual(app_state.device.baudrate, 115200)

        finally:
            core_state_module.CONFIG_FILE = original_config_file


class TestDeviceStateExtended(unittest.TestCase):
    """DeviceState extended tests"""

    def test_raw_serial_log_limit(self):
        """Test raw serial log limit"""
        state = DeviceState()
        state.raw_log_max_size = 5

        for i in range(10):
            state.raw_serial_log.append({"dir": "TX", "data": f"msg{i}"})
            if len(state.raw_serial_log) > state.raw_log_max_size:
                state.raw_serial_log = state.raw_serial_log[-state.raw_log_max_size :]

        self.assertEqual(len(state.raw_serial_log), 5)

    def test_device_info_default(self):
        """Test device info default values"""
        state = DeviceState()
        self.assertIsNone(state.device_info)

    def test_patch_source_content(self):
        """Test patch source content"""
        state = DeviceState()
        self.assertEqual(state.patch_source_content, "")

        state.patch_source_content = "// test code"
        self.assertEqual(state.patch_source_content, "// test code")


class TestAppStateExtended(unittest.TestCase):
    """AppState extended tests"""

    def test_symbols_loaded_default(self):
        """Test symbol loading status default values"""
        app_state = AppState()
        self.assertFalse(app_state.symbols_loaded)

    def test_symbols_default(self):
        """Test symbols default values"""
        app_state = AppState()
        self.assertEqual(app_state.symbols, {})

    def test_file_watcher_default(self):
        """Test file watcher default values"""
        app_state = AppState()
        self.assertIsNone(app_state.file_watcher)

    def test_get_pending_changes_empty(self):
        """Test getting empty pending changes"""
        app_state = AppState()
        changes = app_state.get_pending_changes()
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

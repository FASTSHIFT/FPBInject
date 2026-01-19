#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State 模块测试
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import DeviceState, AppState, PERSISTENT_KEYS, CONFIG_VERSION


class TestDeviceState(unittest.TestCase):
    """DeviceState 测试用例"""

    def test_init_default_values(self):
        """测试初始化默认值"""
        state = DeviceState()

        # 串口相关
        self.assertIsNone(state.ser)
        self.assertIsNone(state.port)
        self.assertEqual(state.baudrate, 115200)
        self.assertEqual(state.timeout, 2)

        # 配置相关
        self.assertEqual(state.elf_path, "")
        self.assertEqual(state.toolchain_path, "")
        self.assertEqual(state.compile_commands_path, "")
        self.assertEqual(state.watch_dirs, [])
        self.assertEqual(state.patch_mode, "trampoline")
        self.assertEqual(state.chunk_size, 128)

        # 自动设置
        self.assertFalse(state.auto_connect)
        self.assertFalse(state.auto_compile)
        self.assertFalse(state.watcher_enabled)

        # NuttX 模式
        self.assertFalse(state.nuttx_mode)

        # 注入状态
        self.assertIsNone(state.last_inject_target)
        self.assertIsNone(state.last_inject_func)
        self.assertFalse(state.inject_active)

        # 日志
        self.assertEqual(state.serial_log, [])
        self.assertEqual(state.raw_serial_log, [])
        self.assertEqual(state.log_max_size, 5000)

    def test_to_dict(self):
        """测试转换为字典"""
        state = DeviceState()
        state.elf_path = "/test/path.elf"
        state.toolchain_path = "/usr/bin"
        state.patch_mode = "debugmon"
        state.baudrate = 921600
        state.watch_dirs = ["/dir1", "/dir2"]
        state.nuttx_mode = True
        state.watcher_enabled = True

        d = state.to_dict()

        # 验证所有持久化键都存在
        for key in PERSISTENT_KEYS:
            self.assertIn(key, d)

        # 验证值
        self.assertEqual(d["elf_path"], "/test/path.elf")
        self.assertEqual(d["toolchain_path"], "/usr/bin")
        self.assertEqual(d["patch_mode"], "debugmon")
        self.assertEqual(d["baudrate"], 921600)
        self.assertEqual(d["watch_dirs"], ["/dir1", "/dir2"])
        self.assertTrue(d["nuttx_mode"])
        self.assertTrue(d["watcher_enabled"])

    def test_from_dict(self):
        """测试从字典导入"""
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
            "auto_connect": True,
            "auto_compile": True,
            "patch_source_path": "/src/patch.c",
            "nuttx_mode": True,
            "watcher_enabled": True,
        }

        state.from_dict(data)

        self.assertEqual(state.port, "/dev/ttyUSB0")
        self.assertEqual(state.baudrate, 460800)
        self.assertEqual(state.elf_path, "/my/elf.elf")
        self.assertEqual(state.toolchain_path, "/opt/toolchain/bin")
        self.assertEqual(state.patch_mode, "direct")
        self.assertEqual(state.chunk_size, 256)
        self.assertTrue(state.auto_connect)
        self.assertTrue(state.auto_compile)
        self.assertTrue(state.nuttx_mode)
        self.assertTrue(state.watcher_enabled)

    def test_from_dict_partial(self):
        """测试部分导入"""
        state = DeviceState()
        state.baudrate = 115200  # 默认值
        state.patch_mode = "trampoline"  # 默认值

        # 只更新部分字段
        state.from_dict({"baudrate": 921600})

        self.assertEqual(state.baudrate, 921600)
        self.assertEqual(state.patch_mode, "trampoline")  # 未改变

    def test_from_dict_ignore_unknown(self):
        """测试忽略未知键"""
        state = DeviceState()

        # 包含未知键
        state.from_dict({"unknown_key": "value", "baudrate": 9600})

        self.assertEqual(state.baudrate, 9600)
        self.assertFalse(hasattr(state, "unknown_key") and state.unknown_key == "value")

    def test_auto_inject_state(self):
        """测试自动注入状态字段"""
        state = DeviceState()

        self.assertEqual(state.auto_inject_status, "idle")
        self.assertEqual(state.auto_inject_message, "")
        self.assertEqual(state.auto_inject_source_file, "")
        self.assertEqual(state.auto_inject_modified_funcs, [])
        self.assertEqual(state.auto_inject_progress, 0)


class TestAppState(unittest.TestCase):
    """AppState 测试用例"""

    def test_init(self):
        """测试初始化"""
        # 使用临时配置文件
        app_state = AppState()

        self.assertIsNotNone(app_state.device)
        self.assertIsInstance(app_state.device, DeviceState)
        self.assertIsNone(app_state.file_watcher)
        self.assertEqual(app_state.pending_changes, [])
        self.assertIsNone(app_state.last_change_time)
        self.assertEqual(app_state.symbols, {})
        self.assertFalse(app_state.symbols_loaded)

    def test_add_pending_change(self):
        """测试添加待处理变化"""
        app_state = AppState()

        app_state.add_pending_change("/path/to/file.c", "modified")

        self.assertEqual(len(app_state.pending_changes), 1)
        change = app_state.pending_changes[0]
        self.assertEqual(change["path"], "/path/to/file.c")
        self.assertEqual(change["type"], "modified")
        self.assertIn("time", change)
        self.assertIsNotNone(app_state.last_change_time)

    def test_add_pending_change_multiple(self):
        """测试添加多个变化"""
        app_state = AppState()

        app_state.add_pending_change("/file1.c", "modified")
        app_state.add_pending_change("/file2.c", "created")
        app_state.add_pending_change("/file3.c", "deleted")

        self.assertEqual(len(app_state.pending_changes), 3)

    def test_add_pending_change_limit(self):
        """测试变化数量限制"""
        app_state = AppState()

        # 添加超过100个变化
        for i in range(150):
            app_state.add_pending_change(f"/file{i}.c", "modified")

        # 应该只保留最后100个
        self.assertEqual(len(app_state.pending_changes), 100)
        # 第一个应该是 file50.c
        self.assertEqual(app_state.pending_changes[0]["path"], "/file50.c")

    def test_clear_pending_changes(self):
        """测试清除待处理变化"""
        app_state = AppState()

        app_state.add_pending_change("/file.c", "modified")
        app_state.clear_pending_changes()

        self.assertEqual(app_state.pending_changes, [])

    def test_get_pending_changes(self):
        """测试获取待处理变化"""
        app_state = AppState()

        app_state.add_pending_change("/file.c", "modified")

        changes = app_state.get_pending_changes()

        # 应该返回副本
        self.assertEqual(len(changes), 1)
        self.assertIsNot(changes, app_state.pending_changes)

    def test_default_patch_template(self):
        """测试默认 patch 模板"""
        app_state = AppState()

        template = app_state.patch_template

        self.assertIn("FPBInject", template)
        self.assertIn("inject_", template)
        self.assertIn("#include", template)


class TestConfigPersistence(unittest.TestCase):
    """配置持久化测试"""

    def setUp(self):
        """创建临时配置文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")

    def tearDown(self):
        """清理临时文件"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)

    def test_save_and_load_config(self):
        """测试保存和加载配置"""
        import state as state_module

        # 临时替换配置文件路径
        original_config_file = state_module.CONFIG_FILE
        state_module.CONFIG_FILE = self.config_file

        try:
            app_state = AppState()
            app_state.device.elf_path = "/test/elf.elf"
            app_state.device.toolchain_path = "/test/toolchain"
            app_state.device.patch_mode = "debugmon"
            app_state.device.nuttx_mode = True

            # 保存
            app_state.save_config()

            # 验证文件已创建
            self.assertTrue(os.path.exists(self.config_file))

            # 读取并验证
            with open(self.config_file, "r") as f:
                config = json.load(f)

            self.assertEqual(config["elf_path"], "/test/elf.elf")
            self.assertEqual(config["toolchain_path"], "/test/toolchain")
            self.assertEqual(config["patch_mode"], "debugmon")
            self.assertTrue(config["nuttx_mode"])
            self.assertEqual(config["version"], CONFIG_VERSION)

            # 创建新状态并加载
            new_state = AppState()

            self.assertEqual(new_state.device.elf_path, "/test/elf.elf")
            self.assertEqual(new_state.device.patch_mode, "debugmon")
            self.assertTrue(new_state.device.nuttx_mode)

        finally:
            state_module.CONFIG_FILE = original_config_file

    def test_load_nonexistent_config(self):
        """测试加载不存在的配置文件"""
        import state as state_module

        original_config_file = state_module.CONFIG_FILE
        state_module.CONFIG_FILE = "/nonexistent/path/config.json"

        try:
            # 不应该抛出异常
            app_state = AppState()

            # 应该使用默认值
            self.assertEqual(app_state.device.baudrate, 115200)

        finally:
            state_module.CONFIG_FILE = original_config_file


if __name__ == "__main__":
    unittest.main(verbosity=2)

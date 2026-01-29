#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Toolchain utilities tests
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import toolchain


class TestGetToolPath(unittest.TestCase):
    """get_tool_path function tests"""

    def test_no_toolchain_path(self):
        """Test without toolchain path returns tool name"""
        result = toolchain.get_tool_path("arm-none-eabi-gcc")
        self.assertEqual(result, "arm-none-eabi-gcc")

    def test_with_toolchain_path(self):
        """Test with toolchain path returns full path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_path = os.path.join(tmpdir, "arm-none-eabi-gcc")
            with open(tool_path, "w") as f:
                f.write("#!/bin/bash\n")

            result = toolchain.get_tool_path("arm-none-eabi-gcc", tmpdir)
            self.assertEqual(result, tool_path)

    def test_tool_not_in_toolchain(self):
        """Test when tool not found in toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = toolchain.get_tool_path("arm-none-eabi-gcc", tmpdir)
            self.assertEqual(result, "arm-none-eabi-gcc")

    def test_none_toolchain_path(self):
        """Test with None toolchain path"""
        result = toolchain.get_tool_path("arm-none-eabi-gcc", None)
        self.assertEqual(result, "arm-none-eabi-gcc")


class TestGetSubprocessEnv(unittest.TestCase):
    """get_subprocess_env function tests"""

    def test_no_toolchain_path(self):
        """Test without toolchain path"""
        env = toolchain.get_subprocess_env()
        self.assertIn("PATH", env)

    def test_with_toolchain_path(self):
        """Test with toolchain path prepends to PATH"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = toolchain.get_subprocess_env(tmpdir)
            self.assertTrue(env["PATH"].startswith(tmpdir + ":"))

    def test_invalid_toolchain_path(self):
        """Test with invalid toolchain path"""
        env = toolchain.get_subprocess_env("/nonexistent/path")
        # Should not modify PATH for non-existent directory
        self.assertNotIn("/nonexistent/path", env["PATH"])

    def test_none_toolchain_path(self):
        """Test with None toolchain path"""
        env = toolchain.get_subprocess_env(None)
        self.assertIn("PATH", env)


if __name__ == "__main__":
    unittest.main()

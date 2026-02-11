#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ELF utilities tests
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import elf_utils  # noqa: E402


class TestGetToolPath(unittest.TestCase):
    """get_tool_path function tests"""

    def test_no_toolchain_path(self):
        """Test without toolchain path"""
        result = elf_utils.get_tool_path("arm-none-eabi-gcc")
        self.assertEqual(result, "arm-none-eabi-gcc")

    def test_with_toolchain_path(self):
        """Test with toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_path = os.path.join(tmpdir, "arm-none-eabi-gcc")
            with open(tool_path, "w") as f:
                f.write("#!/bin/bash\n")

            result = elf_utils.get_tool_path("arm-none-eabi-gcc", tmpdir)
            self.assertEqual(result, tool_path)

    def test_tool_not_in_toolchain(self):
        """Test when tool not found in toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = elf_utils.get_tool_path("arm-none-eabi-gcc", tmpdir)
            self.assertEqual(result, "arm-none-eabi-gcc")


class TestGetSubprocessEnv(unittest.TestCase):
    """get_subprocess_env function tests"""

    def test_no_toolchain_path(self):
        """Test without toolchain path"""
        env = elf_utils.get_subprocess_env()
        self.assertIn("PATH", env)

    def test_with_toolchain_path(self):
        """Test with toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = elf_utils.get_subprocess_env(tmpdir)
            self.assertTrue(env["PATH"].startswith(tmpdir + ":"))

    def test_invalid_toolchain_path(self):
        """Test with invalid toolchain path"""
        env = elf_utils.get_subprocess_env("/nonexistent/path")
        # Should not modify PATH for non-existent directory
        self.assertNotIn("/nonexistent/path", env["PATH"])


class TestGetElfBuildTime(unittest.TestCase):
    """get_elf_build_time function tests"""

    def test_no_elf_path(self):
        """Test with no ELF path"""
        result = elf_utils.get_elf_build_time("")
        self.assertIsNone(result)

    def test_nonexistent_elf(self):
        """Test with nonexistent ELF"""
        result = elf_utils.get_elf_build_time("/nonexistent/file.elf")
        self.assertIsNone(result)

    @patch("subprocess.run")
    def test_strings_failure(self, mock_run):
        """Test when strings command fails"""
        mock_run.return_value = Mock(returncode=1, stdout="")

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)

    @patch("subprocess.run")
    def test_build_time_found_with_marker(self, mock_run):
        """Test finding build time with FPBInject marker"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="FPBInject v1.0\nJan 15 2025\n10:30:45\nother data",
        )

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNotNone(result)
            self.assertIn("Jan", result)
            self.assertIn("2025", result)
        finally:
            os.unlink(elf_path)

    @patch("subprocess.run")
    def test_build_time_found_consecutive(self, mock_run):
        """Test finding build time with consecutive date/time strings"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="some data\nFeb 20 2025\n14:22:33\nmore data",
        )

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNotNone(result)
            self.assertIn("Feb", result)
        finally:
            os.unlink(elf_path)


class TestGetSymbols(unittest.TestCase):
    """get_symbols function tests"""

    @patch("subprocess.run")
    def test_get_symbols_success(self, mock_run):
        """Test getting symbols successfully"""
        # First call for mangled names
        mock_run.side_effect = [
            Mock(
                returncode=0,
                stdout="08000000 T main\n20000000 D var\n08001000 t static_func\n",
            ),
            Mock(
                returncode=0,
                stdout="08000000 T main\n20000000 D var\n08001000 t static_func\n",
            ),
        ]

        symbols = elf_utils.get_symbols("/path/to/elf")

        self.assertIn("main", symbols)
        self.assertEqual(symbols["main"], 0x08000000)
        self.assertIn("static_func", symbols)

    @patch("subprocess.run")
    def test_get_symbols_with_demangled(self, mock_run):
        """Test getting symbols with demangled names"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="08000000 T _Z4testv\n"),
            Mock(returncode=0, stdout="08000000 T test()\n"),
        ]

        symbols = elf_utils.get_symbols("/path/to/elf")

        self.assertIn("_Z4testv", symbols)
        self.assertIn("test", symbols)

    @patch("subprocess.run")
    def test_get_symbols_error(self, mock_run):
        """Test getting symbols with error"""
        mock_run.side_effect = Exception("nm failed")

        symbols = elf_utils.get_symbols("/path/to/elf")

        self.assertEqual(symbols, {})


class TestDisassembleFunction(unittest.TestCase):
    """disassemble_function tests"""

    @patch("subprocess.run")
    def test_disassemble_success(self, mock_run):
        """Test successful disassembly"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="08000000 <main>:\n 8000000: push {r7, lr}\n 8000002: mov r7, sp\n",
        )

        success, result = elf_utils.disassemble_function("/path/to/elf", "main")

        self.assertTrue(success)
        self.assertIn("main", result)

    @patch("subprocess.run")
    def test_disassemble_function_not_found(self, mock_run):
        """Test disassembly when function not found"""
        mock_run.return_value = Mock(returncode=0, stdout="")

        success, result = elf_utils.disassemble_function("/path/to/elf", "nonexistent")

        self.assertFalse(success)
        self.assertIn("not found", result)

    @patch("subprocess.run")
    def test_disassemble_timeout(self, mock_run):
        """Test disassembly timeout"""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("objdump", 30)

        success, result = elf_utils.disassemble_function("/path/to/elf", "main")

        self.assertFalse(success)
        self.assertIn("timed out", result)

    @patch("subprocess.run")
    def test_disassemble_tool_not_found(self, mock_run):
        """Test disassembly when tool not found"""
        mock_run.side_effect = FileNotFoundError("objdump not found")

        success, result = elf_utils.disassemble_function("/path/to/elf", "main")

        self.assertFalse(success)
        self.assertIn("not found", result)


class TestDecompileFunction(unittest.TestCase):
    """decompile_function tests"""

    def test_decompile_angr_not_installed(self):
        """Test decompile when angr is not installed"""
        with patch.dict("sys.modules", {"angr": None}):
            success, result = elf_utils.decompile_function("/path/to/elf", "main")

            self.assertFalse(success)
            self.assertEqual(result, "ANGR_NOT_INSTALLED")


class TestGetSignature(unittest.TestCase):
    """get_signature function tests"""

    @patch("subprocess.run")
    def test_get_signature_with_params(self, mock_run):
        """Test getting signature with parameters"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="08000000 T test_func(int, char*)\n",
        )

        result = elf_utils.get_signature("/path/to/elf", "test_func")

        self.assertIsNotNone(result)
        self.assertIn("test_func", result)

    @patch("subprocess.run")
    def test_get_signature_simple(self, mock_run):
        """Test getting simple signature"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="08000000 T main\n"),
            Mock(returncode=0, stdout=""),
        ]

        result = elf_utils.get_signature("/path/to/elf", "main")

        self.assertEqual(result, "main")

    @patch("subprocess.run")
    def test_get_signature_error(self, mock_run):
        """Test getting signature with error"""
        mock_run.side_effect = Exception("nm failed")

        result = elf_utils.get_signature("/path/to/elf", "test_func")

        self.assertEqual(result, "test_func")


if __name__ == "__main__":
    unittest.main()


class TestDisassembleFunctionExtended(unittest.TestCase):
    """Extended disassemble_function tests"""

    @patch("subprocess.run")
    def test_disassemble_fallback_without_demangling(self, mock_run):
        """Test disassembly fallback without demangling"""
        # First call with -C returns empty, second without -C returns result
        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),
            Mock(
                returncode=0,
                stdout="08000000 <_Z4mainv>:\n 8000000: push {r7, lr}\n",
            ),
        ]

        success, result = elf_utils.disassemble_function("/path/to/elf", "_Z4mainv")

        self.assertTrue(success)
        self.assertIn("_Z4mainv", result)

    @patch("subprocess.run")
    def test_disassemble_extracts_function_only(self, mock_run):
        """Test disassembly extracts only the target function"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
08000000 <main>:
 8000000: push {r7, lr}
 8000002: mov r7, sp

08000010 <other_func>:
 8000010: bx lr
""",
        )

        success, result = elf_utils.disassemble_function("/path/to/elf", "main")

        self.assertTrue(success)
        self.assertIn("main", result)
        # Should stop before other_func
        self.assertNotIn("other_func", result)


class TestGetElfBuildTimeExtended(unittest.TestCase):
    """Extended get_elf_build_time tests"""

    @patch("subprocess.run")
    def test_build_time_no_match(self, mock_run):
        """Test when no build time pattern found"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="random data\nno date here\njust text",
        )

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)

    @patch("subprocess.run")
    def test_build_time_exception(self, mock_run):
        """Test when exception occurs"""
        mock_run.side_effect = Exception("strings failed")

        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name

        try:
            result = elf_utils.get_elf_build_time(elf_path)
            self.assertIsNone(result)
        finally:
            os.unlink(elf_path)


class TestGetSymbolsExtended(unittest.TestCase):
    """Extended get_symbols tests"""

    @patch("subprocess.run")
    def test_get_symbols_with_invalid_address(self, mock_run):
        """Test getting symbols with invalid address format"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="invalid T main\n"),
            Mock(returncode=0, stdout=""),
        ]

        symbols = elf_utils.get_symbols("/path/to/elf")

        # Should skip invalid lines
        self.assertNotIn("main", symbols)

    @patch("subprocess.run")
    def test_get_symbols_with_function_signature(self, mock_run):
        """Test getting symbols with C++ function signatures"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="08000000 T _Z4testv\n"),
            Mock(returncode=0, stdout="08000000 T test(int, char*)\n"),
        ]

        symbols = elf_utils.get_symbols("/path/to/elf")

        self.assertIn("_Z4testv", symbols)
        self.assertIn("test", symbols)


if __name__ == "__main__":
    unittest.main()

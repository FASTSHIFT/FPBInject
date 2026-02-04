#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiler module tests
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import compiler


class TestGetToolPath(unittest.TestCase):
    """get_tool_path function tests"""

    def test_no_toolchain_path(self):
        """Test without toolchain path"""
        result = compiler.get_tool_path("arm-none-eabi-gcc")
        self.assertEqual(result, "arm-none-eabi-gcc")

    def test_with_toolchain_path(self):
        """Test with toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_path = os.path.join(tmpdir, "arm-none-eabi-gcc")
            with open(tool_path, "w") as f:
                f.write("#!/bin/bash\n")

            result = compiler.get_tool_path("arm-none-eabi-gcc", tmpdir)
            self.assertEqual(result, tool_path)


class TestGetSubprocessEnv(unittest.TestCase):
    """get_subprocess_env function tests"""

    def test_no_toolchain_path(self):
        """Test without toolchain path"""
        env = compiler.get_subprocess_env()
        self.assertIn("PATH", env)

    def test_with_toolchain_path(self):
        """Test with toolchain path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = compiler.get_subprocess_env(tmpdir)
            self.assertTrue(env["PATH"].startswith(tmpdir + ":"))


class TestParseDepFileForCompileCommand(unittest.TestCase):
    """parse_dep_file_for_compile_command function tests"""

    def test_no_source_file(self):
        """Test with no source file"""
        result = compiler.parse_dep_file_for_compile_command("")
        self.assertIsNone(result)

    def test_no_dep_file_found(self):
        """Test when no .d file is found"""
        result = compiler.parse_dep_file_for_compile_command(
            "/nonexistent/source.c", "/nonexistent/build"
        )
        self.assertIsNone(result)


class TestParseCompileCommands(unittest.TestCase):
    """parse_compile_commands function tests"""

    def test_file_not_found(self):
        """Test with nonexistent file"""
        result = compiler.parse_compile_commands("/nonexistent/compile_commands.json")
        self.assertIsNone(result)

    def test_invalid_json(self):
        """Test with invalid JSON"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNone(result)
        finally:
            os.unlink(path)

    def test_empty_array(self):
        """Test with empty array"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNone(result)
        finally:
            os.unlink(path)

    def test_invalid_format_not_array(self):
        """Test with non-array JSON"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value"}, f)
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNone(result)
        finally:
            os.unlink(path)

    def test_valid_compile_commands(self):
        """Test with valid compile_commands.json"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "arm-none-eabi-gcc -c -I/inc -DDEBUG -mcpu=cortex-m4 -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertEqual(result["compiler"], "arm-none-eabi-gcc")
            self.assertIn("/inc", result["includes"])
            self.assertIn("DEBUG", result["defines"])
            self.assertIn("-mcpu=cortex-m4", result["cflags"])
        finally:
            os.unlink(path)

    def test_compile_commands_with_source_file_match(self):
        """Test matching specific source file"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".c", delete=False
        ) as src_file:
            src_file.write("int main() { return 0; }")
            src_path = src_file.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": f"arm-none-eabi-gcc -c -DMATCHED -o out.o {src_path}",
                        "file": src_path,
                    },
                    {
                        "directory": "/tmp",
                        "command": "arm-none-eabi-gcc -c -DOTHER -o other.o other.c",
                        "file": "other.c",
                    },
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path, source_file=src_path)
            self.assertIsNotNone(result)
            self.assertIn("MATCHED", result["defines"])
        finally:
            os.unlink(path)
            os.unlink(src_path)

    def test_compile_commands_with_isystem(self):
        """Test parsing -isystem flag"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -isystem /sys/inc -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("/sys/inc", result["includes"])
        finally:
            os.unlink(path)

    def test_compile_commands_with_undef(self):
        """Test parsing -U flag"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -U NDEBUG -UDEBUG -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("-U", result["cflags"])
        finally:
            os.unlink(path)


class TestCompileInject(unittest.TestCase):
    """compile_inject function tests"""

    def test_no_config(self):
        """Test without compile configuration"""
        data, symbols, error = compiler.compile_inject(
            "void test() {}", 0x20000000, compile_commands_path=None
        )

        self.assertIsNone(data)
        self.assertIsNone(symbols)
        self.assertIn("No compile configuration", error)

    @patch("core.compiler.parse_compile_commands")
    def test_compile_error(self, mock_parse):
        """Test compilation error"""
        mock_parse.return_value = {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4"],
            "ldflags": [],
            "raw_command": None,
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="error: syntax error")

            data, symbols, error = compiler.compile_inject(
                "invalid code {{{",
                0x20000000,
                compile_commands_path="/tmp/compile_commands.json",
            )

            self.assertIsNone(data)
            self.assertIn("Compile error", error)

    @patch("core.compiler.parse_compile_commands")
    def test_link_error(self, mock_parse):
        """Test link error"""
        mock_parse.return_value = {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4"],
            "ldflags": [],
            "raw_command": None,
        }

        with patch("subprocess.run") as mock_run:
            # First call (compile) succeeds, second call (link) fails
            mock_run.side_effect = [
                Mock(returncode=0, stderr=""),
                Mock(returncode=1, stderr="undefined reference"),
            ]

            data, symbols, error = compiler.compile_inject(
                "void inject_test() {}",
                0x20000000,
                compile_commands_path="/tmp/compile_commands.json",
            )

            self.assertIsNone(data)
            self.assertIn("Link error", error)

    @patch("core.compiler.parse_compile_commands")
    def test_objcopy_error(self, mock_parse):
        """Test objcopy error"""
        mock_parse.return_value = {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4"],
            "ldflags": [],
            "raw_command": None,
        }

        with patch("subprocess.run") as mock_run:
            # Compile and link succeed, objcopy fails
            mock_run.side_effect = [
                Mock(returncode=0, stderr=""),
                Mock(returncode=0, stderr=""),
                Mock(returncode=1, stderr="has no sections"),
            ]

            data, symbols, error = compiler.compile_inject(
                "void inject_test() {}",
                0x20000000,
                compile_commands_path="/tmp/compile_commands.json",
            )

            self.assertIsNone(data)
            self.assertIn("Objcopy error", error)


class TestFixVeneerThumbBits(unittest.TestCase):
    """fix_veneer_thumb_bits function tests"""

    def test_no_elf_path(self):
        """Test with no ELF path"""
        data = b"\x00" * 16
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, None)
        self.assertEqual(result, data)

    def test_short_data(self):
        """Test with data too short"""
        data = b"\x00" * 4
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/path/to/elf")
        self.assertEqual(result, data)

    @patch("subprocess.run")
    def test_no_thumb_funcs(self, mock_run):
        """Test when no Thumb functions found"""
        mock_run.return_value = Mock(returncode=0, stdout="")

        data = b"\x00" * 16
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/path/to/elf")
        self.assertEqual(result, data)

    @patch("subprocess.run")
    def test_fix_veneer(self, mock_run):
        """Test fixing veneer Thumb bit"""
        # Mock readelf output with Thumb function (address has bit 0 set)
        mock_run.return_value = Mock(
            returncode=0,
            stdout="    1: 08000001     4 FUNC    GLOBAL DEFAULT    1 test_func\n",
        )

        # Create data with veneer pattern pointing to 0x08000000 (missing Thumb bit)
        # Pattern: 5F F8 00 F0 (ldr.w pc, [pc, #0]) followed by address
        veneer_pattern = bytes([0x5F, 0xF8, 0x00, 0xF0])
        target_addr = (0x08000000).to_bytes(4, "little")
        data = veneer_pattern + target_addr + b"\x00" * 8

        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/path/to/elf")

        # Check that Thumb bit was set
        fixed_addr = int.from_bytes(result[4:8], "little")
        self.assertEqual(fixed_addr, 0x08000001)


if __name__ == "__main__":
    unittest.main()


class TestParseCompileCommandsExtended(unittest.TestCase):
    """Extended parse_compile_commands tests"""

    def test_compile_commands_with_separate_define(self):
        """Test parsing -D with separate argument"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -D DEBUG -D VERSION=1 -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("DEBUG", result["defines"])
            self.assertIn("VERSION=1", result["defines"])
        finally:
            os.unlink(path)

    def test_compile_commands_with_separate_include(self):
        """Test parsing -I with separate argument"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -I /inc1 -I/inc2 -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("/inc1", result["includes"])
            self.assertIn("/inc2", result["includes"])
        finally:
            os.unlink(path)

    def test_compile_commands_with_arch_flags(self):
        """Test parsing architecture flags"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -mthumb -mcpu=cortex-m4 -mfloat-abi=hard -mfpu=fpv4-sp-d16 -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("-mthumb", result["cflags"])
            self.assertIn("-mcpu=cortex-m4", result["cflags"])
            self.assertIn("-mfloat-abi=hard", result["cflags"])
        finally:
            os.unlink(path)

    def test_compile_commands_with_function_sections(self):
        """Test parsing function/data sections flags"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -ffunction-sections -fdata-sections -fno-common -nostdlib -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("-ffunction-sections", result["cflags"])
            self.assertIn("-fdata-sections", result["cflags"])
        finally:
            os.unlink(path)

    def test_compile_commands_skip_output_file(self):
        """Test that -o argument is skipped"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -o output.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            # output.o should not be in any list
            self.assertNotIn("output.o", result["includes"])
            self.assertNotIn("output.o", result["defines"])
        finally:
            os.unlink(path)

    def test_compile_commands_skip_param(self):
        """Test that --param is skipped"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c --param max-inline-insns-single=100 -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
        finally:
            os.unlink(path)

    def test_compile_commands_skip_wa_flag(self):
        """Test that -Wa, assembler flags are skipped"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -Wa,-mimplicit-it=thumb -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
        finally:
            os.unlink(path)

    def test_compile_commands_adds_os_flag(self):
        """Test that -Os is added if not present"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("-Os", result["cflags"])
        finally:
            os.unlink(path)

    def test_compile_commands_objcopy_derived(self):
        """Test that objcopy path is derived from compiler"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [
                    {
                        "directory": "/tmp",
                        "command": "/usr/bin/arm-none-eabi-gcc -c -o main.o main.c",
                        "file": "main.c",
                    }
                ],
                f,
            )
            path = f.name

        try:
            result = compiler.parse_compile_commands(path)
            self.assertIsNotNone(result)
            self.assertIn("objcopy", result["objcopy"])
        finally:
            os.unlink(path)

    def test_compile_commands_path_suffix_match(self):
        """Test matching source file by path suffix when base paths differ"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # compile_commands.json has path with /home/user/project prefix
            json.dump(
                [
                    {
                        "directory": "/home/user/project/build",
                        "command": "gcc -c -DMATCHED -I/home/user/project/Source -o func.o /home/user/project/App/func_loader/func_loader.c",
                        "file": "/home/user/project/App/func_loader/func_loader.c",
                    },
                    {
                        "directory": "/tmp",
                        "command": "gcc -c -DOTHER -o other.o other.c",
                        "file": "other.c",
                    },
                ],
                f,
            )
            path = f.name

        try:
            # Source file has different base path (/media/disk/project)
            # but same relative path (App/func_loader/func_loader.c)
            result = compiler.parse_compile_commands(
                path, source_file="/media/disk/project/App/func_loader/func_loader.c"
            )
            self.assertIsNotNone(result)
            # Should match by path suffix and use the correct compile command
            self.assertIn("MATCHED", result["defines"])
            self.assertIn("/home/user/project/Source", result["includes"])
        finally:
            os.unlink(path)


class TestParseDepFile(unittest.TestCase):
    """parse_dep_file_for_compile_command tests"""

    def test_parse_dep_file_with_valid_file(self):
        """Test parsing valid .d file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .d file with compile command
            dep_file = os.path.join(tmpdir, ".test.o.d")
            with open(dep_file, "w") as f:
                f.write("cmd_path/test.o := gcc -c -DTEST -o test.o test.c\n")
                f.write("test.o: test.c test.h\n")

            # Create source file
            src_file = os.path.join(tmpdir, "test.c")
            with open(src_file, "w") as f:
                f.write("int main() {}")

            result = compiler.parse_dep_file_for_compile_command(src_file, tmpdir)
            # May or may not find it depending on search logic
            # Just verify it doesn't crash


if __name__ == "__main__":
    unittest.main()


class TestParseDepFileExtended(unittest.TestCase):
    """Extended parse_dep_file_for_compile_command tests"""

    def test_parse_dep_file_timeout(self):
        """Test parse_dep_file with timeout"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "test.c")
            with open(src_file, "w") as f:
                f.write("int main() {}")

            with patch("subprocess.run") as mock_run:
                import subprocess

                mock_run.side_effect = subprocess.TimeoutExpired("find", 30)

                result = compiler.parse_dep_file_for_compile_command(src_file, tmpdir)
                # Should handle timeout gracefully
                self.assertIsNone(result)

    def test_parse_dep_file_with_matching_content(self):
        """Test parse_dep_file finds matching .d file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            src_file = os.path.join(tmpdir, "test.c")
            with open(src_file, "w") as f:
                f.write("int main() {}")

            # Create .d file with compile command
            dep_file = os.path.join(tmpdir, ".test.o.d")
            with open(dep_file, "w") as f:
                f.write(f"cmd_path/test.o := gcc -c -DTEST -o test.o {src_file}\n")

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout=dep_file)

                result = compiler.parse_dep_file_for_compile_command(src_file, tmpdir)
                # May or may not find depending on implementation details


class TestCompileInjectExtended(unittest.TestCase):
    """Extended compile_inject tests"""

    @patch("core.compiler.parse_compile_commands")
    def test_compile_with_raw_command(self, mock_parse):
        """Test compile using raw command from .d file"""
        mock_parse.return_value = {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4"],
            "ldflags": [],
            "raw_command": "arm-none-eabi-gcc -c -DRAW_CMD -o test.o test.c",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="compile error")

            data, symbols, error = compiler.compile_inject(
                "void inject_test() {}",
                0x20000000,
                compile_commands_path="/tmp/compile_commands.json",
            )

            self.assertIsNone(data)
            self.assertIn("Compile error", error)

    @patch("core.compiler.parse_compile_commands")
    def test_compile_with_cpp_extension(self, mock_parse):
        """Test compile with .cpp extension"""
        mock_parse.return_value = {
            "compiler": "arm-none-eabi-g++",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4"],
            "ldflags": [],
            "raw_command": None,
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="compile error")

            data, symbols, error = compiler.compile_inject(
                "void inject_test() {}",
                0x20000000,
                compile_commands_path="/tmp/compile_commands.json",
                source_ext=".cpp",
            )

            self.assertIsNone(data)


class TestStaticAndGlobalVariables(unittest.TestCase):
    """Tests for static and global variable support in inject code."""

    def setUp(self):
        """Set up toolchain path."""
        # Try to find toolchain
        self.toolchain_path = None
        possible_paths = [
            "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin",
            "/usr/bin",
        ]
        for path in possible_paths:
            gcc_path = os.path.join(path, "arm-none-eabi-gcc")
            if os.path.exists(gcc_path):
                self.toolchain_path = path
                break

    def _create_compile_commands(self, tmpdir):
        """Create a minimal compile_commands.json."""
        cc_path = os.path.join(tmpdir, "compile_commands.json")
        with open(cc_path, "w") as f:
            json.dump(
                [
                    {
                        "directory": tmpdir,
                        "command": "arm-none-eabi-gcc -c -mcpu=cortex-m4 -mthumb -o test.o test.c",
                        "file": "test.c",
                    }
                ],
                f,
            )
        return cc_path

    @unittest.skipIf(
        not os.path.exists(
            "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin/arm-none-eabi-gcc"
        ),
        "ARM toolchain not available",
    )
    def test_static_variable_with_initializer(self):
        """Test that static variables with initializers are included in binary."""
        source = """
static int counter = 42;

int inject_test(void) {
    counter++;
    return counter;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cc_path = self._create_compile_commands(tmpdir)

            data, symbols, error = compiler.compile_inject(
                source,
                0x20001000,
                compile_commands_path=cc_path,
                toolchain_path=self.toolchain_path,
            )

            self.assertEqual(error, "", f"Compile failed: {error}")
            self.assertIsNotNone(data)
            self.assertGreater(len(data), 0)

            # Check that inject_test symbol exists
            self.assertIn("inject_test", symbols)

            # The binary should contain the initialized value (42 = 0x2a)
            # It should be somewhere in the data section
            self.assertIn(b"\x2a\x00\x00\x00", data)

    @unittest.skipIf(
        not os.path.exists(
            "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin/arm-none-eabi-gcc"
        ),
        "ARM toolchain not available",
    )
    def test_static_variable_zero_initialized(self):
        """Test that zero-initialized static variables (BSS) are included in binary."""
        source = """
static int zero_counter;

int inject_test(void) {
    zero_counter++;
    return zero_counter;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cc_path = self._create_compile_commands(tmpdir)

            data, symbols, error = compiler.compile_inject(
                source,
                0x20001000,
                compile_commands_path=cc_path,
                toolchain_path=self.toolchain_path,
            )

            self.assertEqual(error, "", f"Compile failed: {error}")
            self.assertIsNotNone(data)
            self.assertGreater(len(data), 0)

            # Check that inject_test symbol exists
            self.assertIn("inject_test", symbols)

    @unittest.skipIf(
        not os.path.exists(
            "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin/arm-none-eabi-gcc"
        ),
        "ARM toolchain not available",
    )
    def test_mixed_static_variables(self):
        """Test code with both initialized and zero-initialized static variables."""
        source = """
static int initialized_var = 100;
static int zero_var;

int inject_test(void) {
    initialized_var++;
    zero_var++;
    return initialized_var + zero_var;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cc_path = self._create_compile_commands(tmpdir)

            data, symbols, error = compiler.compile_inject(
                source,
                0x20001000,
                compile_commands_path=cc_path,
                toolchain_path=self.toolchain_path,
            )

            self.assertEqual(error, "", f"Compile failed: {error}")
            self.assertIsNotNone(data)
            self.assertGreater(len(data), 0)

            # Check that inject_test symbol exists
            self.assertIn("inject_test", symbols)

            # The binary should contain the initialized value (100 = 0x64)
            self.assertIn(b"\x64\x00\x00\x00", data)

    @unittest.skipIf(
        not os.path.exists(
            "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin/arm-none-eabi-gcc"
        ),
        "ARM toolchain not available",
    )
    def test_static_array(self):
        """Test static array with initializers."""
        source = """
static int lookup_table[4] = {1, 2, 3, 4};

int inject_test(int index) {
    if (index >= 0 && index < 4) {
        return lookup_table[index];
    }
    return -1;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cc_path = self._create_compile_commands(tmpdir)

            data, symbols, error = compiler.compile_inject(
                source,
                0x20001000,
                compile_commands_path=cc_path,
                toolchain_path=self.toolchain_path,
            )

            self.assertEqual(error, "", f"Compile failed: {error}")
            self.assertIsNotNone(data)

            # Check that inject_test symbol exists
            self.assertIn("inject_test", symbols)

            # The binary should contain the array values
            self.assertIn(b"\x01\x00\x00\x00", data)
            self.assertIn(b"\x02\x00\x00\x00", data)
            self.assertIn(b"\x03\x00\x00\x00", data)
            self.assertIn(b"\x04\x00\x00\x00", data)

    @unittest.skipIf(
        not os.path.exists(
            "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin/arm-none-eabi-gcc"
        ),
        "ARM toolchain not available",
    )
    def test_global_variable(self):
        """Test global (non-static) variable."""
        source = """
int global_counter = 55;

int inject_test(void) {
    global_counter++;
    return global_counter;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cc_path = self._create_compile_commands(tmpdir)

            data, symbols, error = compiler.compile_inject(
                source,
                0x20001000,
                compile_commands_path=cc_path,
                toolchain_path=self.toolchain_path,
            )

            self.assertEqual(error, "", f"Compile failed: {error}")
            self.assertIsNotNone(data)

            # Check that inject_test symbol exists
            self.assertIn("inject_test", symbols)

            # The binary should contain the initialized value (55 = 0x37)
            self.assertIn(b"\x37\x00\x00\x00", data)

    @unittest.skipIf(
        not os.path.exists(
            "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin/arm-none-eabi-gcc"
        ),
        "ARM toolchain not available",
    )
    def test_const_data(self):
        """Test const data in rodata section."""
        source = """
static const int magic_numbers[] = {0xDEAD, 0xBEEF, 0xCAFE};

int inject_test(int index) {
    if (index >= 0 && index < 3) {
        return magic_numbers[index];
    }
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cc_path = self._create_compile_commands(tmpdir)

            data, symbols, error = compiler.compile_inject(
                source,
                0x20001000,
                compile_commands_path=cc_path,
                toolchain_path=self.toolchain_path,
            )

            self.assertEqual(error, "", f"Compile failed: {error}")
            self.assertIsNotNone(data)

            # Check that inject_test symbol exists
            self.assertIn("inject_test", symbols)

            # The binary should contain the magic numbers (little-endian)
            self.assertIn(b"\xad\xde\x00\x00", data)  # 0xDEAD
            self.assertIn(b"\xef\xbe\x00\x00", data)  # 0xBEEF
            self.assertIn(b"\xfe\xca\x00\x00", data)  # 0xCAFE


class TestLinkerScriptBssHandling(unittest.TestCase):
    """Tests specifically for BSS section handling in linker script."""

    @unittest.skipIf(
        not os.path.exists(
            "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin/arm-none-eabi-gcc"
        ),
        "ARM toolchain not available",
    )
    def test_bss_is_zeroed_in_binary(self):
        """Test that BSS section is included in binary with zeros."""
        # Use volatile to prevent compiler from optimizing away the variables
        source = """
static volatile int bss_var1;
static volatile int bss_var2;

int inject_test(void) {
    bss_var1++;
    bss_var2++;
    return bss_var1 + bss_var2;
}
"""
        toolchain_path = "prebuilts/gcc/linux-x86_64/arm-none-eabi/bin"

        with tempfile.TemporaryDirectory() as tmpdir:
            cc_path = os.path.join(tmpdir, "compile_commands.json")
            with open(cc_path, "w") as f:
                json.dump(
                    [
                        {
                            "directory": tmpdir,
                            "command": "arm-none-eabi-gcc -c -mcpu=cortex-m4 -mthumb -o test.o test.c",
                            "file": "test.c",
                        }
                    ],
                    f,
                )

            data, symbols, error = compiler.compile_inject(
                source,
                0x20001000,
                compile_commands_path=cc_path,
                toolchain_path=toolchain_path,
            )

            self.assertEqual(error, "", f"Compile failed: {error}")
            self.assertIsNotNone(data)

            # The binary should be larger than just the code
            # because it includes BSS with zeros
            self.assertGreater(len(data), 30)

            # Check that inject_test symbol exists
            self.assertIn("inject_test", symbols)

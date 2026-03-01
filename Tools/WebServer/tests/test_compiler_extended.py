#!/usr/bin/env python3
"""Extended compiler tests for coverage improvement."""

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import compiler  # noqa: E402


class TestCompileInjectSuccessPath(unittest.TestCase):
    """Test the full successful compile_inject path."""

    def _make_config(self, raw_command=None):
        return {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": ["/tmp"],
            "defines": ["DEBUG"],
            "cflags": ["-mcpu=cortex-m4", "-mthumb"],
            "ldflags": [],
            "raw_command": raw_command,
        }

    def _run_compile(
        self, source, mock_parse, mock_run, nm_stdout="", config=None, **kwargs
    ):
        mock_parse.return_value = config or self._make_config(
            raw_command=kwargs.pop("raw_command", None)
        )
        bin_data = kwargs.pop("bin_data", b"\x00" * 16)
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stdout=nm_stdout),
        ]
        original_open = open

        def patched_open(path, *args, **kw):
            if str(path).endswith("inject.bin") and "rb" in str(args):
                return io.BytesIO(bin_data)
            return original_open(path, *args, **kw)

        with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
            with patch("builtins.open", side_effect=patched_open):
                return compiler.compile_inject(
                    source,
                    kwargs.get("base_addr", 0x20001000),
                    compile_commands_path="/tmp/cc.json",
                    **{k: v for k, v in kwargs.items() if k != "base_addr"},
                )

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_full_success(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            "/* FPB_INJECT */\nvoid test_func(void) {}",
            mock_parse,
            mock_run,
            nm_stdout="20001000 T test_func\n20001020 t local_helper\n",
        )
        self.assertEqual(error, "")
        self.assertIsNotNone(data)
        self.assertIn("test_func", symbols)
        self.assertEqual(symbols["test_func"], 0x20001000)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_raw_command(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            "/* FPB_INJECT */\nvoid test_func(void) {}",
            mock_parse,
            mock_run,
            nm_stdout="20001000 T test_func\n",
            raw_command="arm-none-eabi-gcc -c -MD -MF .dep -MT out.o -DRAW -I/inc -o out.o src.c",
        )
        self.assertEqual(error, "")
        first_cmd = mock_run.call_args_list[0][0][0]
        self.assertIn("-DRAW", first_cmd)
        self.assertNotIn("-MD", first_cmd)
        self.assertNotIn("-MF", first_cmd)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_cpp_extension(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            '/* FPB_INJECT */\nextern "C" void test_func(void) {}',
            mock_parse,
            mock_run,
            nm_stdout="20001000 T test_func\n",
            source_ext=".cpp",
        )
        self.assertEqual(error, "")
        first_cmd = mock_run.call_args_list[0][0][0]
        cpp_args = [a for a in first_cmd if a.endswith(".cpp")]
        self.assertEqual(len(cpp_args), 1)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_demangled_names(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            "/* FPB_INJECT */\nvoid foo(int a, char* b) {}",
            mock_parse,
            mock_run,
            nm_stdout="20001000 T foo(int, char*)\n20001020 T bar\n",
        )
        self.assertEqual(error, "")
        self.assertIn("foo", symbols)
        self.assertIn("bar", symbols)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_malformed_nm_lines(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            "/* FPB_INJECT */\nvoid valid_func(void) {}",
            mock_parse,
            mock_run,
            nm_stdout="20001000 T valid_func\nmalformed line\n\n",
        )
        self.assertEqual(error, "")
        self.assertIn("valid_func", symbols)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_no_fpb_markers(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            "void test_func(void) {}",
            mock_parse,
            mock_run,
            nm_stdout="20001000 T test_func\n",
        )
        self.assertEqual(error, "")

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_symbols_filtered_by_base_addr(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            "/* FPB_INJECT */\nvoid inject_func(void) {}",
            mock_parse,
            mock_run,
            nm_stdout="08000000 T firmware_func\n20001000 T inject_func\n",
        )
        self.assertEqual(error, "")
        self.assertIn("inject_func", symbols)
        self.assertNotIn("firmware_func", symbols)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_verbose_mode(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            "/* FPB_INJECT */\nvoid test_func(void) {}",
            mock_parse,
            mock_run,
            nm_stdout="20001000 T test_func\n",
            verbose=True,
        )
        self.assertEqual(error, "")

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_with_elf_path(self, mock_run, mock_parse):
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
            elf_path = f.name
        try:
            data, symbols, error = self._run_compile(
                "/* FPB_INJECT */\nvoid test_func(void) {}",
                mock_parse,
                mock_run,
                nm_stdout="20001000 T test_func\n",
                elf_path=elf_path,
            )
            self.assertEqual(error, "")
            link_cmd = mock_run.call_args_list[1][0][0]
            just_sym = [a for a in link_cmd if "--just-symbols" in a]
            self.assertEqual(len(just_sym), 1)
        finally:
            os.unlink(elf_path)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_non_text_symbols_excluded(self, mock_run, mock_parse):
        data, symbols, error = self._run_compile(
            "/* FPB_INJECT */\nvoid test_func(void) {}",
            mock_parse,
            mock_run,
            nm_stdout="20001000 T test_func\n20001100 D data_var\n20001200 B bss_var\n",
        )
        self.assertEqual(error, "")
        self.assertIn("test_func", symbols)
        self.assertNotIn("data_var", symbols)
        self.assertNotIn("bss_var", symbols)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_compile_error(self, mock_run, mock_parse):
        mock_parse.return_value = self._make_config()
        mock_run.return_value = Mock(returncode=1, stderr="error: undefined reference")
        data, symbols, error = compiler.compile_inject(
            "bad code",
            0x20001000,
            compile_commands_path="/tmp/cc.json",
        )
        self.assertIsNone(data)
        self.assertIn("Compile error", error)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_link_error(self, mock_run, mock_parse):
        mock_parse.return_value = self._make_config()
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),
            Mock(returncode=1, stderr="undefined symbol"),
        ]
        data, symbols, error = compiler.compile_inject(
            "void f(void) {}",
            0x20001000,
            compile_commands_path="/tmp/cc.json",
        )
        self.assertIsNone(data)
        self.assertIn("Link error", error)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_objcopy_error(self, mock_run, mock_parse):
        mock_parse.return_value = self._make_config()
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=1, stderr="objcopy failed"),
        ]
        data, symbols, error = compiler.compile_inject(
            "void f(void) {}",
            0x20001000,
            compile_commands_path="/tmp/cc.json",
        )
        self.assertIsNone(data)
        self.assertIn("Objcopy error", error)

    def test_no_config(self):
        data, symbols, error = compiler.compile_inject("void f(void) {}", 0x20001000)
        self.assertIsNone(data)
        self.assertIn("No compile configuration", error)


class TestFixVeneerExtended(unittest.TestCase):
    """Extended fix_veneer_thumb_bits tests."""

    @patch("subprocess.run")
    def test_readelf_exception(self, mock_run):
        mock_run.side_effect = Exception("readelf not found")
        data = b"\x00" * 16
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/path/to/elf")
        self.assertEqual(result, data)

    @patch("subprocess.run")
    def test_multiple_veneers(self, mock_run):
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                "    1: 08000001     4 FUNC    GLOBAL DEFAULT    1 func_a\n"
                "    2: 08001001     4 FUNC    GLOBAL DEFAULT    1 func_b\n"
            ),
        )
        veneer = bytes([0x5F, 0xF8, 0x00, 0xF0])
        addr_a = (0x08000000).to_bytes(4, "little")
        addr_b = (0x08001000).to_bytes(4, "little")
        data = veneer + addr_a + veneer + addr_b + b"\x00" * 8
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/path/to/elf")
        fixed_a = int.from_bytes(result[4:8], "little")
        fixed_b = int.from_bytes(result[12:16], "little")
        self.assertEqual(fixed_a, 0x08000001)
        self.assertEqual(fixed_b, 0x08001001)

    @patch("subprocess.run")
    def test_veneer_already_has_thumb_bit(self, mock_run):
        mock_run.return_value = Mock(
            returncode=0,
            stdout="    1: 08000001     4 FUNC    GLOBAL DEFAULT    1 func_a\n",
        )
        veneer = bytes([0x5F, 0xF8, 0x00, 0xF0])
        addr = (0x08000001).to_bytes(4, "little")
        data = veneer + addr + b"\x00" * 8
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/path/to/elf")
        fixed = int.from_bytes(result[4:8], "little")
        self.assertEqual(fixed, 0x08000001)

    @patch("subprocess.run")
    def test_veneer_verbose(self, mock_run):
        mock_run.return_value = Mock(
            returncode=0,
            stdout="    1: 08000001     4 FUNC    GLOBAL DEFAULT    1 func_a\n",
        )
        veneer = bytes([0x5F, 0xF8, 0x00, 0xF0])
        addr = (0x08000000).to_bytes(4, "little")
        data = veneer + addr + b"\x00" * 8
        result = compiler.fix_veneer_thumb_bits(
            data, 0x20000000, "/path/to/elf", verbose=True
        )
        fixed = int.from_bytes(result[4:8], "little")
        self.assertEqual(fixed, 0x08000001)

    @patch("subprocess.run")
    def test_no_elf_path(self, mock_run):
        data = b"\x00" * 16
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, None)
        self.assertEqual(result, data)
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests to improve compiler.py coverage - targeting uncovered lines."""

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import compiler  # noqa: E402


class TestResolveMangledNames(unittest.TestCase):
    """Direct tests for _resolve_mangled_names (lines 25-101)."""

    @patch("subprocess.run")
    def test_basic_c_function(self, mock_run):
        """C function: mangled == demangled."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="00000000 T my_func\n"),
            Mock(returncode=0, stdout="00000000 T my_func\n"),
        ]
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertEqual(result["my_func"], "my_func")

    @patch("subprocess.run")
    def test_cpp_mangled(self, mock_run):
        """C++ function with mangling."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="00000000 T _Z14gui_loop_closePPv\n"),
            Mock(returncode=0, stdout="00000000 T gui_loop_close(void**)\n"),
        ]
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertEqual(result["gui_loop_close"], "_Z14gui_loop_closePPv")

    @patch("subprocess.run")
    def test_cpp_namespaced(self, mock_run):
        """C++ namespaced function generates suffix variants."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="00000000 T _ZN5ferry9WidgetIMP4typeEv\n"),
            Mock(
                returncode=0,
                stdout="00000000 T ferry::WidgetIMP::type()\n",
            ),
        ]
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertIn("ferry::WidgetIMP::type", result)
        self.assertIn("WidgetIMP::type", result)
        self.assertIn("type", result)
        self.assertEqual(result["WidgetIMP::type"], "_ZN5ferry9WidgetIMP4typeEv")

    @patch("subprocess.run")
    def test_nm_failure(self, mock_run):
        """nm returns non-zero."""
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr="error"),
            Mock(returncode=0, stdout=""),
        ]
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertEqual(result, {})

    @patch("subprocess.run")
    def test_line_count_mismatch(self, mock_run):
        """Raw and demangled nm output have different line counts."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="00000000 T a\n00000010 T b\n"),
            Mock(returncode=0, stdout="00000000 T a\n"),
        ]
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertEqual(result, {})

    @patch("subprocess.run")
    def test_skip_non_text_symbols(self, mock_run):
        """Non-T symbols are skipped."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="00000000 D data_sym\n00000010 T text_sym\n"),
            Mock(returncode=0, stdout="00000000 D data_sym\n00000010 T text_sym\n"),
        ]
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertNotIn("data_sym", result)
        self.assertIn("text_sym", result)

    @patch("subprocess.run")
    def test_skip_short_lines(self, mock_run):
        """Lines with < 3 parts are skipped."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="00000000 T func\nshort\n"),
            Mock(returncode=0, stdout="00000000 T func\nshort\n"),
        ]
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertIn("func", result)

    @patch("subprocess.run")
    def test_exception_handling(self, mock_run):
        """Exception during nm is caught gracefully."""
        mock_run.side_effect = Exception("nm not found")
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertEqual(result, {})

    @patch("subprocess.run")
    def test_demangled_no_parens(self, mock_run):
        """Demangled name without parentheses (e.g. C symbol)."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="00000000 T plain_func\n"),
            Mock(returncode=0, stdout="00000000 T plain_func\n"),
        ]
        result = compiler._resolve_mangled_names("/tmp/test.o")
        self.assertEqual(result["plain_func"], "plain_func")


class TestResolveFunctionsFromMarkerLines(unittest.TestCase):
    """Direct tests for _resolve_functions_from_marker_lines (lines 104-223)."""

    @patch("subprocess.run")
    def test_empty_marker_lines(self, mock_run):
        """Empty marker list returns empty."""
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", []
        )
        self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_basic_resolution(self, mock_run):
        """Marker at line 5 resolves to function at line 6."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T my_func\t/tmp/test.cpp:6\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, ["my_func"])

    @patch("subprocess.run")
    def test_multiple_markers(self, mock_run):
        """Multiple markers resolve to different functions."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                "00000000 T func_a\t/tmp/test.cpp:3\n"
                "00000020 T func_b\t/tmp/test.cpp:10\n"
                "00000040 T func_c\t/tmp/test.cpp:20\n"
            ),
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [2, 9, 19]
        )
        self.assertEqual(result, ["func_a", "func_b", "func_c"])

    @patch("subprocess.run")
    def test_nm_failure(self, mock_run):
        """nm -l returns non-zero."""
        mock_run.return_value = Mock(returncode=1, stderr="error", stdout="")
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_no_line_info(self, mock_run):
        """nm output has no file:line info (no -g flag)."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T my_func\n",  # no tab, no file:line
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_wrong_source_file(self, mock_run):
        """nm output references a different source file."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T other_func\t/tmp/other.cpp:6\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_non_text_symbols_skipped(self, mock_run):
        """Non-T type symbols are ignored."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 D data_var\t/tmp/test.cpp:6\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_demangled_with_params(self, mock_run):
        """Demangled name with params is stripped to base name."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T WidgetIMP::type() const\t/tmp/test.cpp:6\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, ["WidgetIMP::type"])

    @patch("subprocess.run")
    def test_marker_after_all_functions(self, mock_run):
        """Marker line after all functions finds nothing."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T early_func\t/tmp/test.cpp:3\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [100]
        )
        self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_duplicate_resolution(self, mock_run):
        """Two markers resolving to same function produce one entry."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T my_func\t/tmp/test.cpp:10\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5, 8]
        )
        self.assertEqual(result, ["my_func"])

    @patch("subprocess.run")
    def test_exception_handling(self, mock_run):
        """Exception is caught gracefully."""
        mock_run.side_effect = Exception("nm not found")
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_discriminator_in_line(self, mock_run):
        """nm output with discriminator: 'file:line (discriminator N)'."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T my_func\t/tmp/test.cpp:6 (discriminator 1)\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, ["my_func"])

    @patch("subprocess.run")
    def test_no_colon_in_location(self, mock_run):
        """Location part without colon is skipped."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T my_func\tno_colon_here\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, [])

    @patch("subprocess.run")
    def test_invalid_line_number(self, mock_run):
        """Non-numeric line number in nm output is skipped."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="00000000 T my_func\t/tmp/test.cpp:abc\n",
        )
        result = compiler._resolve_functions_from_marker_lines(
            "/tmp/test.o", "/tmp/test.cpp", [5]
        )
        self.assertEqual(result, [])


class TestCompileInjectMarkerLines(unittest.TestCase):
    """Test compile_inject with inject_marker_lines path (lines 428-454)."""

    def _make_config(self):
        return {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": ["/tmp"],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4", "-mthumb"],
            "ldflags": [],
            "raw_command": None,
        }

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_marker_lines_resolved(self, mock_run, mock_parse):
        """inject_marker_lines triggers nm -l resolution."""
        mock_parse.return_value = self._make_config()
        bin_data = b"\x00" * 16

        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as src:
            src.write("/*FPB_INJECT*/\nint WidgetIMP::type() const { return 0; }\n")
            src_path = src.name

        # nm -l output must reference the actual source file basename
        src_basename = os.path.basename(src_path)
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),  # compile
            # _resolve_functions_from_marker_lines nm -C -l
            Mock(
                returncode=0,
                stdout=f"00000000 T WidgetIMP::type\t{src_path}:2\n",
            ),
            # _resolve_mangled_names: nm raw
            Mock(
                returncode=0,
                stdout="00000000 T _ZNK9WidgetIMP4typeEv\n",
            ),
            # _resolve_mangled_names: nm -C
            Mock(
                returncode=0,
                stdout="00000000 T WidgetIMP::type() const\n",
            ),
            Mock(returncode=0, stderr=""),  # link
            Mock(returncode=0, stderr=""),  # objcopy
            # final nm -C --defined-only
            Mock(
                returncode=0,
                stdout="20001000 T WidgetIMP::type() const\n",
            ),
        ]

        original_open = open

        def patched_open(path, *args, **kw):
            if str(path).endswith("inject.bin") and "rb" in str(args):
                return io.BytesIO(bin_data)
            return original_open(path, *args, **kw)

        try:
            with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
                with patch("builtins.open", side_effect=patched_open):
                    data, symbols, error = compiler.compile_inject(
                        source_content=None,
                        base_addr=0x20001000,
                        compile_commands_path="/tmp/cc.json",
                        source_file=src_path,
                        inject_marker_lines=[1],
                    )
            self.assertEqual(error, "")
            self.assertIsNotNone(data)
            self.assertIn("WidgetIMP::type", symbols)
        finally:
            os.unlink(src_path)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_marker_lines_resolution_fails(self, mock_run, mock_parse):
        """inject_marker_lines resolution failure returns error."""
        mock_parse.return_value = self._make_config()

        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),  # compile
            # _resolve_functions_from_marker_lines: nm returns nothing useful
            Mock(returncode=0, stdout=""),
        ]

        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as src:
            src.write("/*FPB_INJECT*/\nint foo() { return 0; }\n")
            src_path = src.name

        try:
            data, symbols, error = compiler.compile_inject(
                source_content=None,
                base_addr=0x20001000,
                compile_commands_path="/tmp/cc.json",
                source_file=src_path,
                inject_marker_lines=[1],
            )
            self.assertIsNone(data)
            self.assertIn("Failed to resolve FPB_INJECT markers", error)
        finally:
            os.unlink(src_path)


class TestCompileInjectCppSwitch(unittest.TestCase):
    """Test gcc -> g++ auto-switch (lines 327-341)."""

    def _make_config(self):
        return {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4", "-mthumb"],
            "ldflags": [],
            "raw_command": None,
        }

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_gcc_to_gpp_via_source_file(self, mock_run, mock_parse):
        """source_file .cpp triggers gcc -> g++ switch."""
        mock_parse.return_value = self._make_config()
        mock_run.return_value = Mock(returncode=1, stderr="compile error")

        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as src:
            src.write("void f() {}")
            src_path = src.name

        try:
            compiler.compile_inject(
                source_content=None,
                base_addr=0x20001000,
                compile_commands_path="/tmp/cc.json",
                source_file=src_path,
            )
            # Check that g++ was used in compile command
            compile_cmd = mock_run.call_args_list[0][0][0]
            self.assertIn("arm-none-eabi-g++", compile_cmd[0])
        finally:
            os.unlink(src_path)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_gcc_to_gpp_via_original_source_file(self, mock_run, mock_parse):
        """original_source_file .cc triggers gcc -> g++ switch."""
        mock_parse.return_value = self._make_config()
        mock_run.return_value = Mock(returncode=1, stderr="compile error")

        compiler.compile_inject(
            source_content="void f() {}",
            base_addr=0x20001000,
            compile_commands_path="/tmp/cc.json",
            original_source_file="/tmp/test.cc",
        )
        compile_cmd = mock_run.call_args_list[0][0][0]
        self.assertIn("arm-none-eabi-g++", compile_cmd[0])


class TestCompileInjectFpbSymsMatching(unittest.TestCase):
    """Test FPB inject symbol suffix matching (lines 615-644)."""

    def _make_config(self):
        return {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4", "-mthumb"],
            "ldflags": [],
            "raw_command": None,
        }

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_suffix_matching_merges_short_name(self, mock_run, mock_parse):
        """Suffix matching: symbols has 'ns::Class::method', inject has 'Class::method'."""
        mock_parse.return_value = self._make_config()
        bin_data = b"\x00" * 16

        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),  # compile
            Mock(returncode=0, stdout="", stderr=""),  # nm raw
            Mock(returncode=0, stdout="", stderr=""),  # nm -C
            Mock(returncode=0, stderr=""),  # link
            Mock(returncode=0, stderr=""),  # objcopy
            # final nm: symbol has full namespace
            Mock(
                returncode=0,
                stdout="20001000 T ferry::WidgetIMP::type() const\n",
            ),
        ]

        original_open = open

        def patched_open(path, *args, **kw):
            if str(path).endswith("inject.bin") and "rb" in str(args):
                return io.BytesIO(bin_data)
            return original_open(path, *args, **kw)

        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as src:
            src.write("int WidgetIMP::type() const { return 0; }\n")
            src_path = src.name

        try:
            with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
                with patch("builtins.open", side_effect=patched_open):
                    data, symbols, error = compiler.compile_inject(
                        source_content=None,
                        base_addr=0x20001000,
                        compile_commands_path="/tmp/cc.json",
                        source_file=src_path,
                        inject_functions=["WidgetIMP::type"],
                    )
            self.assertEqual(error, "")
            # Short name should be merged into symbols
            self.assertIn("WidgetIMP::type", symbols)
        finally:
            os.unlink(src_path)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_fpb_funcs_not_found_warning(self, mock_run, mock_parse):
        """inject_functions provided but not found in symbols triggers warning."""
        mock_parse.return_value = self._make_config()
        bin_data = b"\x00" * 16

        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),  # compile
            Mock(returncode=0, stdout="", stderr=""),  # nm raw
            Mock(returncode=0, stdout="", stderr=""),  # nm -C
            Mock(returncode=0, stderr=""),  # link
            Mock(returncode=0, stderr=""),  # objcopy
            # final nm: no matching symbols
            Mock(
                returncode=0,
                stdout="20001000 T unrelated_func\n",
            ),
        ]

        original_open = open

        def patched_open(path, *args, **kw):
            if str(path).endswith("inject.bin") and "rb" in str(args):
                return io.BytesIO(bin_data)
            return original_open(path, *args, **kw)

        with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as src:
            src.write("void missing_func(void) {}\n")
            src_path = src.name

        try:
            with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
                with patch("builtins.open", side_effect=patched_open):
                    data, symbols, error = compiler.compile_inject(
                        source_content=None,
                        base_addr=0x20001000,
                        compile_commands_path="/tmp/cc.json",
                        source_file=src_path,
                        inject_functions=["missing_func"],
                    )
            self.assertEqual(error, "")
            self.assertIsNotNone(data)
            # missing_func not in symbols (only unrelated_func matched)
            self.assertNotIn("missing_func", symbols)
        finally:
            os.unlink(src_path)


class TestFixVeneerThumbBits(unittest.TestCase):
    """Additional fix_veneer_thumb_bits coverage (lines 689-722)."""

    @patch("subprocess.run")
    def test_short_data(self, mock_run):
        """Data shorter than 8 bytes returns unchanged."""
        result = compiler.fix_veneer_thumb_bits(b"\x00" * 4, 0x20000000, "/elf")
        self.assertEqual(result, b"\x00" * 4)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_no_thumb_funcs(self, mock_run):
        """No FUNC symbols found returns data unchanged."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="    1: 08000000     4 NOTYPE  GLOBAL DEFAULT    1 not_func\n",
        )
        data = b"\x00" * 16
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/elf")
        self.assertEqual(result, data)

    @patch("subprocess.run")
    def test_veneer_addr_not_in_thumb_set(self, mock_run):
        """Veneer target not in thumb set is not fixed."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="    1: 08000001     4 FUNC    GLOBAL DEFAULT    1 func_a\n",
        )
        veneer = bytes([0x5F, 0xF8, 0x00, 0xF0])
        # Address 0x09000000 is not in thumb_funcs
        addr = (0x09000000).to_bytes(4, "little")
        data = veneer + addr + b"\x00" * 8
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/elf")
        fixed = int.from_bytes(result[4:8], "little")
        self.assertEqual(fixed, 0x09000000)  # unchanged

    @patch("subprocess.run")
    def test_readelf_value_error(self, mock_run):
        """Invalid hex in readelf output is skipped."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="    1: ZZZZZZZZ     4 FUNC    GLOBAL DEFAULT    1 bad_addr\n",
        )
        data = b"\x00" * 16
        result = compiler.fix_veneer_thumb_bits(data, 0x20000000, "/elf")
        self.assertEqual(result, data)


if __name__ == "__main__":
    unittest.main()

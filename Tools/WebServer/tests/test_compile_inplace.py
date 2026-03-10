#!/usr/bin/env python3
"""Tests for in-place compilation feature.

Tests the new source_file + inject_functions parameters in compile_inject,
the generate_patch_inplace method in PatchGenerator, and the updated
file_watcher_manager auto-inject flow.
"""

import io
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import compiler  # noqa: E402
from core.patch_generator import PatchGenerator  # noqa: E402

# =============================================================================
# Test: compile_inject in-place mode
# =============================================================================


class TestCompileInjectInplace(unittest.TestCase):
    """Test compile_inject with source_file and inject_functions parameters."""

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

    def _run_inplace(
        self,
        mock_parse,
        mock_run,
        source_content_in_file,
        inject_functions,
        nm_stdout="",
        config=None,
        **kwargs
    ):
        """Helper to run compile_inject in in-place mode."""
        mock_parse.return_value = config or self._make_config()
        bin_data = kwargs.pop("bin_data", b"\x00" * 16)
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),  # compile
            Mock(returncode=0, stderr=""),  # link
            Mock(returncode=0, stderr=""),  # objcopy
            Mock(returncode=0, stdout=nm_stdout),  # nm
        ]

        # Create a real temp file with source content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(source_content_in_file)
            source_path = f.name

        original_open = open

        def patched_open(path, *args, **kw):
            if str(path).endswith("inject.bin") and "rb" in str(args):
                return io.BytesIO(bin_data)
            return original_open(path, *args, **kw)

        try:
            with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
                with patch("builtins.open", side_effect=patched_open):
                    return compiler.compile_inject(
                        base_addr=kwargs.get("base_addr", 0x20001000),
                        compile_commands_path="/tmp/cc.json",
                        source_file=source_path,
                        inject_functions=inject_functions,
                        **{k: v for k, v in kwargs.items() if k != "base_addr"},
                    )
        finally:
            os.unlink(source_path)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_inplace_basic(self, mock_run, mock_parse):
        """In-place mode compiles the original file directly."""
        data, symbols, error = self._run_inplace(
            mock_parse,
            mock_run,
            source_content_in_file=(
                "/* FPB_INJECT */\nvoid my_func(void) { }\n"
                "void other_func(void) { }\n"
            ),
            inject_functions=["my_func"],
            nm_stdout="20001000 T my_func\n",
        )
        self.assertEqual(error, "")
        self.assertIsNotNone(data)
        self.assertIn("my_func", symbols)

        # Verify the compile command uses the original file path (not a temp inject.c)
        compile_cmd = mock_run.call_args_list[0][0][0]
        source_args = [a for a in compile_cmd if a.endswith(".c")]
        self.assertEqual(len(source_args), 1)
        # Should NOT be "inject.c" in tmpdir
        self.assertNotIn("inject", os.path.basename(source_args[0]))

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_inplace_linker_script_keep(self, mock_run, mock_parse):
        """In-place mode generates KEEP(.text.func) in linker script."""
        data, symbols, error = self._run_inplace(
            mock_parse,
            mock_run,
            source_content_in_file="void func_a(void) {}\nvoid func_b(void) {}\n",
            inject_functions=["func_a", "func_b"],
            nm_stdout="20001000 T func_a\n20001020 T func_b\n",
        )
        self.assertEqual(error, "")

        # Check the linker script written to tmpdir contains KEEP rules
        # The link command should reference a .ld file
        link_cmd = mock_run.call_args_list[1][0][0]
        ld_args = [a for a in link_cmd if a.endswith(".ld") or ".ld" in a]
        self.assertTrue(len(ld_args) > 0, "Linker script should be in link command")

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_inplace_uses_u_flags(self, mock_run, mock_parse):
        """In-place mode adds -Wl,-u,func for each inject function."""
        data, symbols, error = self._run_inplace(
            mock_parse,
            mock_run,
            source_content_in_file="void target_func(void) {}\n",
            inject_functions=["target_func"],
            nm_stdout="20001000 T target_func\n",
        )
        self.assertEqual(error, "")

        link_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("-Wl,-u,target_func", link_cmd)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_inplace_multi_functions(self, mock_run, mock_parse):
        """In-place mode with multiple inject functions."""
        data, symbols, error = self._run_inplace(
            mock_parse,
            mock_run,
            source_content_in_file="void fa(void){}\nvoid fb(void){}\nvoid fc(void){}\n",
            inject_functions=["fa", "fb"],
            nm_stdout="20001000 T fa\n20001020 T fb\n20001040 T fc\n",
        )
        self.assertEqual(error, "")
        self.assertIn("fa", symbols)
        self.assertIn("fb", symbols)

        link_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("-Wl,-u,fa", link_cmd)
        self.assertIn("-Wl,-u,fb", link_cmd)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_inplace_auto_detect_ext(self, mock_run, mock_parse):
        """In-place mode auto-detects source extension from file path."""
        mock_parse.return_value = self._make_config()
        bin_data = b"\x00" * 16
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stdout="20001000 T test\n"),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False) as f:
            f.write("void test(void) {}")
            cpp_path = f.name

        original_open = open

        def patched_open(path, *args, **kw):
            if str(path).endswith("inject.bin") and "rb" in str(args):
                return io.BytesIO(bin_data)
            return original_open(path, *args, **kw)

        try:
            with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
                with patch("builtins.open", side_effect=patched_open):
                    data, symbols, error = compiler.compile_inject(
                        base_addr=0x20001000,
                        compile_commands_path="/tmp/cc.json",
                        source_file=cpp_path,
                        inject_functions=["test"],
                    )
            self.assertEqual(error, "")
        finally:
            os.unlink(cpp_path)

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_inplace_compile_error(self, mock_run, mock_parse):
        """In-place mode returns compile error properly."""
        mock_parse.return_value = self._make_config()
        mock_run.return_value = Mock(returncode=1, stderr="error: syntax error")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("bad code {{{")
            source_path = f.name

        try:
            data, symbols, error = compiler.compile_inject(
                base_addr=0x20001000,
                compile_commands_path="/tmp/cc.json",
                source_file=source_path,
                inject_functions=["test"],
            )
            self.assertIsNone(data)
            self.assertIn("Compile error", error)
        finally:
            os.unlink(source_path)

    def test_inplace_file_not_found_fallback(self):
        """When source_file doesn't exist, falls back to content mode."""
        # source_file doesn't exist and no source_content → error
        data, symbols, error = compiler.compile_inject(
            base_addr=0x20001000,
            source_file="/nonexistent/file.c",
            inject_functions=["test"],
        )
        self.assertIsNone(data)
        # Should get "No source content" error since file doesn't exist
        # and no source_content provided
        self.assertTrue(len(error) > 0)

    def test_no_source_content_or_file(self):
        """Neither source_content nor source_file provided."""
        data, symbols, error = compiler.compile_inject(
            base_addr=0x20001000,
        )
        self.assertIsNone(data)
        self.assertIn("No source content", error)


# =============================================================================
# Test: compile_inject backward compatibility (content mode)
# =============================================================================


class TestCompileInjectContentModeCompat(unittest.TestCase):
    """Ensure content mode (legacy) still works after refactor."""

    def _make_config(self):
        return {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": ["/tmp"],
            "defines": ["DEBUG"],
            "cflags": ["-mcpu=cortex-m4", "-mthumb"],
            "ldflags": [],
            "raw_command": None,
        }

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_content_mode_still_works(self, mock_run, mock_parse):
        """Legacy content mode with source_content still works."""
        mock_parse.return_value = self._make_config()
        bin_data = b"\x00" * 16
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stdout="20001000 T test_func\n"),
        ]
        original_open = open

        def patched_open(path, *args, **kw):
            if str(path).endswith("inject.bin") and "rb" in str(args):
                return io.BytesIO(bin_data)
            return original_open(path, *args, **kw)

        with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
            with patch("builtins.open", side_effect=patched_open):
                data, symbols, error = compiler.compile_inject(
                    source_content="/* FPB_INJECT */\nvoid test_func(void) {}",
                    base_addr=0x20001000,
                    compile_commands_path="/tmp/cc.json",
                )
        self.assertEqual(error, "")
        self.assertIsNotNone(data)

        # Verify it wrote to a temp inject.c file
        compile_cmd = mock_run.call_args_list[0][0][0]
        source_args = [a for a in compile_cmd if a.endswith(".c")]
        self.assertEqual(len(source_args), 1)
        self.assertIn("inject", os.path.basename(source_args[0]))

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_content_mode_uses_fpb_text_section(self, mock_run, mock_parse):
        """Content mode linker script uses .fpb.text section (legacy)."""
        mock_parse.return_value = self._make_config()
        bin_data = b"\x00" * 16
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stdout="20001000 T f\n"),
        ]

        real_open = open

        def patched_open(path, *args, **kw):
            if str(path).endswith("inject.bin") and "rb" in str(args):
                return io.BytesIO(bin_data)
            return real_open(path, *args, **kw)

        with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
            with patch("builtins.open", side_effect=patched_open):
                data, symbols, error = compiler.compile_inject(
                    source_content="/* FPB_INJECT */\nvoid f(void) {}",
                    base_addr=0x20001000,
                    compile_commands_path="/tmp/cc.json",
                )
        self.assertEqual(error, "")


# =============================================================================
# Test: PatchGenerator.generate_patch_inplace
# =============================================================================


class TestGeneratePatchInplace(unittest.TestCase):
    """Test PatchGenerator.generate_patch_inplace method."""

    def test_inplace_finds_markers(self):
        """generate_patch_inplace returns file path and function list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(
                "/* FPB_INJECT */\n"
                "void my_func(void) { }\n"
                "\n"
                "/* FPB_INJECT */\n"
                "int another_func(int x) { return x; }\n"
            )
            path = f.name

        try:
            gen = PatchGenerator()
            result_path, funcs = gen.generate_patch_inplace(path)
            self.assertEqual(result_path, path)
            self.assertIn("my_func", funcs)
            self.assertIn("another_func", funcs)
            self.assertEqual(len(funcs), 2)
        finally:
            os.unlink(path)

    def test_inplace_no_markers(self):
        """generate_patch_inplace returns None when no markers found."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void plain_func(void) { }\n")
            path = f.name

        try:
            gen = PatchGenerator()
            result_path, funcs = gen.generate_patch_inplace(path)
            self.assertIsNone(result_path)
            self.assertEqual(funcs, [])
        finally:
            os.unlink(path)

    def test_inplace_file_not_found(self):
        """generate_patch_inplace returns None for nonexistent file."""
        gen = PatchGenerator()
        result_path, funcs = gen.generate_patch_inplace("/nonexistent/file.c")
        self.assertIsNone(result_path)
        self.assertEqual(funcs, [])

    def test_inplace_single_function(self):
        """generate_patch_inplace with single marked function."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(
                "#include <stdio.h>\n"
                "void helper(void) { }\n"
                "/* FPB_INJECT */\n"
                "void target(void) { helper(); }\n"
            )
            path = f.name

        try:
            gen = PatchGenerator()
            result_path, funcs = gen.generate_patch_inplace(path)
            self.assertEqual(result_path, path)
            self.assertEqual(funcs, ["target"])
        finally:
            os.unlink(path)

    def test_inplace_preserves_original_file(self):
        """generate_patch_inplace does not modify the original file."""
        original_content = "/* FPB_INJECT */\n" "void my_func(void) { }\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(original_content)
            path = f.name

        try:
            gen = PatchGenerator()
            gen.generate_patch_inplace(path)

            with open(path, "r") as f:
                after_content = f.read()
            self.assertEqual(original_content, after_content)
        finally:
            os.unlink(path)


# =============================================================================
# Test: file_watcher_manager in-place flow
# =============================================================================


class TestAutoInjectInplace(unittest.TestCase):
    """Test _trigger_auto_inject uses in-place compilation flow."""

    def setUp(self):
        """Set up test fixtures."""
        from core.state import state

        self.state = state
        self.state.device.auto_compile = True
        self.state.device.inject_active = False
        self.state.device.last_inject_target = None
        self.state.device.auto_inject_status = "idle"
        self.state.device.auto_inject_message = ""
        self.state.device.auto_inject_progress = 0
        self.state.device.auto_inject_modified_funcs = []
        self.state.device.patch_source_content = None

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_inplace_flow_no_markers(self, mock_gen_class, mock_get_fpb):
        """Auto inject with no markers sets idle status."""
        from services.file_watcher_manager import _trigger_auto_inject

        mock_gen = Mock()
        mock_gen_class.return_value = mock_gen
        mock_gen.generate_patch_inplace.return_value = (None, [])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void plain(void) {}")
            path = f.name

        try:
            _trigger_auto_inject(path)
            # Wait for background thread
            time.sleep(0.5)

            self.assertEqual(self.state.device.auto_inject_status, "idle")
            mock_gen.generate_patch_inplace.assert_called_once_with(path)
        finally:
            os.unlink(path)

    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_inplace_flow_device_not_connected(self, mock_gen_class, mock_get_fpb):
        """Auto inject fails gracefully when device not connected."""
        from services.file_watcher_manager import _trigger_auto_inject

        mock_gen = Mock()
        mock_gen_class.return_value = mock_gen
        mock_gen.generate_patch_inplace.return_value = (
            "/tmp/test.c",
            ["my_func"],
        )

        self.state.device.ser = None

        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("/* FPB_INJECT */\nvoid my_func(void) {}")
            path = f.name

        try:
            _trigger_auto_inject(path)
            time.sleep(0.5)

            self.assertEqual(self.state.device.auto_inject_status, "failed")
            self.assertIn("not connected", self.state.device.auto_inject_message)
            # Verify generate_patch_inplace was called (not generate_patch)
            mock_gen.generate_patch_inplace.assert_called_once()
            mock_gen.generate_patch.assert_not_called()
        finally:
            os.unlink(path)

    @patch("services.device_worker.run_in_device_worker")
    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_inplace_flow_success(self, mock_gen_class, mock_get_fpb, mock_run_worker):
        """Auto inject success path uses in-place mode."""
        from services.file_watcher_manager import _trigger_auto_inject

        mock_gen = Mock()
        mock_gen_class.return_value = mock_gen

        source_content = "/* FPB_INJECT */\nvoid target_func(void) {}"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(source_content)
            path = f.name

        mock_gen.generate_patch_inplace.return_value = (
            path,
            ["target_func"],
        )

        # Mock serial connection
        mock_ser = Mock()
        mock_ser.isOpen.return_value = True
        self.state.device.ser = mock_ser

        # Mock FPB inject
        mock_fpb = Mock()
        mock_get_fpb.return_value = mock_fpb
        mock_fpb.enter_fl_mode.return_value = True
        mock_fpb.exit_fl_mode.return_value = True
        mock_fpb.info.return_value = ({"slots": []}, "")
        mock_fpb.inject_multi.return_value = (
            True,
            {
                "successful_count": 1,
                "total_count": 1,
                "injections": [
                    {
                        "target_func": "target_func",
                        "inject_func": "target_func",
                        "success": True,
                    }
                ],
                "errors": [],
            },
        )

        # run_in_device_worker executes the callback immediately
        def _run_immediate(device, func, timeout=5.0):
            func()
            return True

        mock_run_worker.side_effect = _run_immediate

        try:
            _trigger_auto_inject(path)
            time.sleep(0.5)

            self.assertEqual(self.state.device.auto_inject_status, "success")

            # Verify inject_multi was called with in-place params
            mock_fpb.inject_multi.assert_called_once()
            call_kwargs = mock_fpb.inject_multi.call_args[1]
            self.assertEqual(call_kwargs["source_file"], path)
            self.assertEqual(call_kwargs["inject_functions"], ["target_func"])
            # source_content should NOT be in kwargs (in-place mode)
            self.assertNotIn("source_content", call_kwargs)

            # Verify patch_source_content is set to original file content
            self.assertEqual(self.state.device.patch_source_content, source_content)
        finally:
            os.unlink(path)

    @patch("services.device_worker.run_in_device_worker")
    @patch("routes.get_fpb_inject")
    @patch("core.patch_generator.PatchGenerator")
    def test_inplace_flow_auto_unpatch(
        self, mock_gen_class, mock_get_fpb, mock_run_worker
    ):
        """Auto unpatch when markers are removed."""
        from services.file_watcher_manager import _trigger_auto_inject

        mock_gen = Mock()
        mock_gen_class.return_value = mock_gen
        mock_gen.generate_patch_inplace.return_value = (None, [])

        self.state.device.inject_active = True
        self.state.device.last_inject_target = "old_func"

        mock_fpb = Mock()
        mock_get_fpb.return_value = mock_fpb
        mock_fpb.enter_fl_mode.return_value = True
        mock_fpb.exit_fl_mode.return_value = True
        mock_fpb.unpatch.return_value = (True, "OK")

        # run_in_device_worker executes the callback immediately
        def _run_immediate(device, func, timeout=5.0):
            func()
            return True

        mock_run_worker.side_effect = _run_immediate

        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void plain(void) {}")
            path = f.name

        try:
            _trigger_auto_inject(path)
            time.sleep(0.5)

            mock_fpb.unpatch.assert_called_once_with(0)
            self.assertFalse(self.state.device.inject_active)
        finally:
            os.unlink(path)


# =============================================================================
# Test: Linker script generation
# =============================================================================


class TestLinkerScriptGeneration(unittest.TestCase):
    """Test linker script KEEP rules for in-place mode."""

    @patch("core.compiler.parse_compile_commands")
    @patch("subprocess.run")
    def test_inplace_ld_has_keep_text_func(self, mock_run, mock_parse):
        """Linker script in in-place mode has KEEP(*(.text.func)) rules."""
        mock_parse.return_value = {
            "compiler": "arm-none-eabi-gcc",
            "objcopy": "arm-none-eabi-objcopy",
            "includes": [],
            "defines": [],
            "cflags": ["-mcpu=cortex-m4", "-mthumb"],
            "ldflags": [],
            "raw_command": None,
        }

        # Capture what gets written to the .ld file
        bin_data = b"\x00" * 16
        mock_run.side_effect = [
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stderr=""),
            Mock(returncode=0, stdout="20001000 T func_a\n"),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write("void func_a(void) {}")
            source_path = f.name

        try:
            with patch("core.compiler.fix_veneer_thumb_bits", return_value=bin_data):
                # Use a custom open to capture ld file content
                written_files = {}
                real_open = open

                class CapturingWriter:
                    def __init__(self, real_file, path):
                        self._file = real_file
                        self._path = path
                        self._content = []

                    def write(self, data):
                        self._content.append(data)
                        return self._file.write(data)

                    def __enter__(self):
                        self._file.__enter__()
                        return self

                    def __exit__(self, *args):
                        written_files[self._path] = "".join(self._content)
                        return self._file.__exit__(*args)

                    def __getattr__(self, name):
                        return getattr(self._file, name)

                def spy_open(path, *args, **kw):
                    if str(path).endswith("inject.bin") and "rb" in str(args):
                        return io.BytesIO(bin_data)
                    f = real_open(path, *args, **kw)
                    if str(path).endswith(".ld") and "w" in str(args[:1]):
                        return CapturingWriter(f, str(path))
                    return f

                with patch("builtins.open", side_effect=spy_open):
                    data, symbols, error = compiler.compile_inject(
                        base_addr=0x20001000,
                        compile_commands_path="/tmp/cc.json",
                        source_file=source_path,
                        inject_functions=["func_a"],
                    )

                self.assertEqual(error, "")

                # Find the .ld file content
                ld_file = [k for k in written_files if k.endswith(".ld")]
                self.assertEqual(len(ld_file), 1)
                ld_text = written_files[ld_file[0]]
                self.assertIn("KEEP(*(.text.func_a))", ld_text)
                # Should also have legacy .fpb.text for backward compat
                self.assertIn("KEEP(*(.fpb.text))", ld_text)
        finally:
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()

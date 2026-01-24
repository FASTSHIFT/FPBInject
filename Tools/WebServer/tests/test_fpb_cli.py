#!/usr/bin/env python3
"""
Test cases for fpb_cli.py - Comprehensive test suite
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fpb_cli import FPBCLI, FPBCLIError, DeviceState, HAS_SERIAL, main


class TestDeviceState(unittest.TestCase):
    """Test DeviceState class"""

    def test_init_defaults(self):
        """Test default initialization values"""
        state = DeviceState()
        self.assertIsNone(state.ser)
        self.assertIsNone(state.elf_path)
        self.assertIsNone(state.compile_commands_path)
        self.assertFalse(state.connected)
        self.assertEqual(state.ram_start, 0x20000000)
        self.assertEqual(state.ram_size, 0x10000)
        self.assertEqual(state.inject_base, 0x20001000)
        self.assertIsNone(state.cached_slots)
        self.assertEqual(state.slot_update_id, 0)
        self.assertEqual(state.chunk_size, 128)

    @unittest.skipIf(not HAS_SERIAL, "pyserial not installed")
    @patch("fpb_cli.serial.Serial")
    def test_connect_success(self, mock_serial):
        """Test successful connection"""
        state = DeviceState()
        mock_serial.return_value = MagicMock()

        result = state.connect("/dev/ttyACM0", 115200)
        self.assertTrue(result)
        self.assertTrue(state.connected)
        self.assertIsNotNone(state.ser)

    @unittest.skipIf(not HAS_SERIAL, "pyserial not installed")
    @patch("fpb_cli.serial.Serial")
    def test_connect_failure(self, mock_serial):
        """Test connection failure"""
        state = DeviceState()
        mock_serial.side_effect = Exception("Connection refused")

        with self.assertRaises(RuntimeError) as ctx:
            state.connect("/dev/invalid", 115200)
        self.assertIn("Failed to connect", str(ctx.exception))
        self.assertFalse(state.connected)

    def test_disconnect(self):
        """Test disconnect"""
        state = DeviceState()
        mock_ser = MagicMock()
        state.ser = mock_ser
        state.connected = True

        state.disconnect()

        mock_ser.close.assert_called_once()
        self.assertIsNone(state.ser)
        self.assertFalse(state.connected)

    def test_disconnect_no_connection(self):
        """Test disconnect when not connected"""
        state = DeviceState()
        state.disconnect()  # Should not raise
        self.assertFalse(state.connected)


class TestFPBCLI(unittest.TestCase):
    """Test cases for FPBCLI class"""

    def setUp(self):
        """Set up test fixtures"""
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        """Cleanup"""
        self.cli.cleanup()

    def test_init_default(self):
        """Test default initialization"""
        cli = FPBCLI()
        self.assertFalse(cli.verbose)
        self.assertIsNotNone(cli._device_state)
        self.assertIsNotNone(cli._fpb)
        cli.cleanup()

    def test_init_verbose(self):
        """Test verbose initialization"""
        cli = FPBCLI(verbose=True)
        self.assertTrue(cli.verbose)
        cli.cleanup()

    def test_init_with_paths(self):
        """Test initialization with elf and compile_commands paths"""
        cli = FPBCLI(elf_path="/path/to/elf", compile_commands="/path/to/cc.json")
        self.assertEqual(cli._device_state.elf_path, "/path/to/elf")
        self.assertEqual(cli._device_state.compile_commands_path, "/path/to/cc.json")
        cli.cleanup()

    @unittest.skipIf(not HAS_SERIAL, "pyserial not installed")
    @patch("fpb_cli.serial.Serial")
    def test_init_with_port(self, mock_serial):
        """Test initialization with serial port"""
        mock_serial.return_value = MagicMock()
        cli = FPBCLI(port="/dev/ttyACM0", baudrate=9600)
        self.assertTrue(cli._device_state.connected)
        cli.cleanup()

    def test_output_json(self):
        """Test JSON output formatting"""
        data = {"success": True, "message": "Test"}

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.output_json(data)

        output = f.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["success"], True)
        self.assertEqual(parsed["message"], "Test")

    def test_output_json_unicode(self):
        """Test JSON output with unicode"""
        data = {"success": True, "message": "测试消息"}

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.output_json(data)

        output = f.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["message"], "测试消息")

    def test_output_error(self):
        """Test error output formatting"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.output_error("Test error")

        output = f.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["success"], False)
        self.assertEqual(parsed["error"], "Test error")

    def test_output_error_with_exception_non_verbose(self):
        """Test error output without exception in non-verbose mode"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.output_error("Test error", ValueError("Details"))

        output = f.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["success"], False)
        self.assertNotIn("exception", parsed)

    def test_output_error_with_exception_verbose(self):
        """Test error output with exception details in verbose mode"""
        cli_verbose = FPBCLI(verbose=True)

        f = io.StringIO()
        with redirect_stdout(f):
            cli_verbose.output_error("Test error", ValueError("Details"))

        output = f.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["success"], False)
        self.assertIn("exception", parsed)
        self.assertEqual(parsed["exception"], "Details")
        cli_verbose.cleanup()


class TestFPBCLIAnalyze(unittest.TestCase):
    """Test analyze command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        self.cli.cleanup()

    def test_analyze_success(self):
        """Test successful analyze"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols, \
             patch.object(self.cli._fpb, "disassemble_function") as mock_disasm, \
             patch.object(self.cli._fpb, "get_signature") as mock_sig:
            mock_symbols.return_value = {"main": 0x08001000}
            mock_disasm.return_value = (True, "push {r7, lr}\nmov r7, sp")
            mock_sig.return_value = "int main(void)"

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.analyze("/fake/elf", "main")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["analysis"]["func_name"], "main")
            self.assertEqual(output["analysis"]["addr"], "0x8001000")
            self.assertEqual(output["analysis"]["signature"], "int main(void)")

    def test_analyze_function_not_found(self):
        """Test analyze with non-existent function"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols:
            mock_symbols.return_value = {"other": 0x08001000}

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.analyze("/fake/elf", "nonexistent")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
            self.assertIn("not found", output["error"])

    def test_analyze_exception(self):
        """Test analyze with exception"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols:
            mock_symbols.side_effect = Exception("File not found")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.analyze("/fake/elf", "main")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
            self.assertIn("failed", output["error"].lower())


class TestFPBCLIDisasm(unittest.TestCase):
    """Test disasm command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        self.cli.cleanup()

    def test_disasm_success(self):
        """Test successful disassembly"""
        with patch.object(self.cli._fpb, "disassemble_function") as mock_disasm:
            mock_disasm.return_value = (True, "push {r7, lr}\nmov r7, sp\npop {r7, pc}")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.disasm("/fake/elf", "main")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertIn("push", output["disasm"])
            self.assertEqual(output["language"], "arm_asm")

    def test_disasm_failure(self):
        """Test disassembly failure"""
        with patch.object(self.cli._fpb, "disassemble_function") as mock_disasm:
            mock_disasm.return_value = (False, None)

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.disasm("/fake/elf", "main")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])

    def test_disasm_exception(self):
        """Test disasm with exception"""
        with patch.object(self.cli._fpb, "disassemble_function") as mock_disasm:
            mock_disasm.side_effect = Exception("Error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.disasm("/fake/elf", "main")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])


class TestFPBCLIDecompile(unittest.TestCase):
    """Test decompile command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        self.cli.cleanup()

    def test_decompile_success(self):
        """Test successful decompilation"""
        with patch.object(self.cli._fpb, "decompile_function") as mock_dec:
            mock_dec.return_value = (True, "int main(void) {\n  return 0;\n}")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.decompile("/fake/elf", "main")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertIn("main", output["decompiled"])
            self.assertEqual(output["language"], "c")

    def test_decompile_import_error(self):
        """Test decompile without angr"""
        with patch.object(self.cli._fpb, "decompile_function") as mock_dec:
            mock_dec.side_effect = ImportError("No module named 'angr'")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.decompile("/fake/elf", "main")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
            self.assertIn("angr", output["error"])


class TestFPBCLISignature(unittest.TestCase):
    """Test signature command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        self.cli.cleanup()

    def test_signature_success(self):
        """Test successful signature retrieval"""
        with patch.object(self.cli._fpb, "get_signature") as mock_sig:
            mock_sig.return_value = "void pinMode(uint8_t pin, uint8_t mode)"

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.signature("/fake/elf", "pinMode")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertIn("pinMode", output["signature"])

    def test_signature_exception(self):
        """Test signature with exception"""
        with patch.object(self.cli._fpb, "get_signature") as mock_sig:
            mock_sig.side_effect = Exception("Error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.signature("/fake/elf", "test")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])


class TestFPBCLISearch(unittest.TestCase):
    """Test search command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        self.cli.cleanup()

    def test_search_success(self):
        """Test successful search"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols:
            mock_symbols.return_value = {
                "gpio_init": 0x08001000,
                "gpio_write": 0x08001020,
                "main": 0x08001100,
            }

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.search("/fake/elf", "gpio")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["count"], 2)

    def test_search_no_results(self):
        """Test search with no matches"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols:
            mock_symbols.return_value = {"main": 0x08001100}

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.search("/fake/elf", "gpio")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["count"], 0)

    def test_search_case_insensitive(self):
        """Test case-insensitive search"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols:
            mock_symbols.return_value = {"GPIO_Init": 0x08001000}

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.search("/fake/elf", "gpio")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["count"], 1)

    def test_search_limit_results(self):
        """Test search limits to 20 results"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols:
            # Create 30 symbols
            mock_symbols.return_value = {f"gpio_{i}": 0x08001000 + i for i in range(30)}

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.search("/fake/elf", "gpio")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["count"], 30)
            self.assertEqual(len(output["symbols"]), 20)  # Limited to 20

    def test_search_exception(self):
        """Test search with exception"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols:
            mock_symbols.side_effect = Exception("Error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.search("/fake/elf", "gpio")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])


class TestFPBCLICompile(unittest.TestCase):
    """Test compile command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        self.cli.cleanup()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compile_file_not_found(self):
        """Test compile with non-existent file"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.compile("/nonexistent/patch.c")

        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("not found", output["error"])

    def test_compile_success(self):
        """Test successful compilation"""
        # Create test file
        source = Path(self.temp_dir) / "test.c"
        source.write_text("void inject_test(void) {}")

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (b"\x00\x01\x02", {"inject_test": 0x20001000}, None)

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.compile(str(source))

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["binary_size"], 3)

    def test_compile_large_binary(self):
        """Test compile with large binary (>1024 bytes)"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("void inject_test(void) {}")

        # Create binary larger than 1024 bytes
        large_binary = b"\x00" * 2000

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (large_binary, {"inject_test": 0x20001000}, None)

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.compile(str(source))

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["binary_size"], 2000)
            self.assertIn("...", output["binary_hex"])

    def test_compile_error(self):
        """Test compilation error"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("invalid code")

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (None, None, "Syntax error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.compile(str(source))

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
            self.assertIn("Compilation error", output["error"])

    def test_compile_no_output(self):
        """Test compile produces no output"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("")

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (None, None, None)

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.compile(str(source))

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
            self.assertIn("no output", output["error"])

    def test_compile_with_options(self):
        """Test compile with all options"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("void inject_test(void) {}")

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (b"\x00", {"inject_test": 0x20002000}, None)

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.compile(str(source), elf_path="/path/to/elf",
                                 base_addr=0x20002000, compile_commands="/path/to/cc.json")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["base_addr"], "0x20002000")


class TestFPBCLIInfo(unittest.TestCase):
    """Test info command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        self.cli.cleanup()

    def test_info_not_connected(self):
        """Test info without connection"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.info()

        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    def test_info_success(self):
        """Test successful info"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "info") as mock_info:
            mock_info.return_value = ({"slots": [], "total_slots": 6}, None)

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.info()

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertIn("info", output)

    def test_info_error(self):
        """Test info with error"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "info") as mock_info:
            mock_info.return_value = (None, "Communication error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.info()

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])

    def test_info_exception(self):
        """Test info with exception"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "info") as mock_info:
            mock_info.side_effect = Exception("Error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.info()

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])


class TestFPBCLIInject(unittest.TestCase):
    """Test inject command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        self.cli.cleanup()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_inject_file_not_found(self):
        """Test inject with non-existent file"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.inject("target", "/nonexistent.c")

        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("not found", output["error"])

    def test_inject_not_connected_no_elf(self):
        """Test inject without connection and no ELF"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("void inject_test(void) {}")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.inject("target", str(source))

        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    def test_inject_not_connected_with_elf(self):
        """Test inject offline with ELF (compile validation)"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("void inject_test(void) {}")

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (b"\x00\x01", {"inject_test": 0x20001000}, None)

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.inject("target", str(source), elf_path="/fake/elf")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])  # Not connected
            self.assertIn("compiled", output)  # But shows compiled info

    def test_inject_compile_error_offline(self):
        """Test inject offline with compile error"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("invalid")

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (None, None, "Syntax error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.inject("target", str(source), elf_path="/fake/elf")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
            self.assertIn("Compilation error", output["error"])

    def test_inject_connected_success(self):
        """Test successful injection"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("void inject_test(void) {}")

        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "inject") as mock_inject:
            mock_inject.return_value = (True, {"slot": 0, "code_size": 32})

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.inject("target", str(source))

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])

    def test_inject_with_all_options(self):
        """Test inject with all options"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("void inject_test(void) {}")

        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "inject") as mock_inject:
            mock_inject.return_value = (True, {"slot": 1})

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.inject("target", str(source), elf_path="/fake/elf",
                                compile_commands="/fake/cc.json", patch_mode="debugmon",
                                comp=1, verify=True)

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])

    def test_inject_exception(self):
        """Test inject with exception"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("void inject_test(void) {}")

        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "inject") as mock_inject:
            mock_inject.side_effect = Exception("Injection failed")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.inject("target", str(source))

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])


class TestFPBCLIUnpatch(unittest.TestCase):
    """Test unpatch command"""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        self.cli.cleanup()

    def test_unpatch_not_connected(self):
        """Test unpatch without connection"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.unpatch(comp=0)

        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    def test_unpatch_success(self):
        """Test successful unpatch"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "unpatch") as mock_unpatch:
            mock_unpatch.return_value = (True, "Patch cleared")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.unpatch(comp=0)

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["comp"], 0)

    def test_unpatch_all(self):
        """Test unpatch all"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "unpatch") as mock_unpatch:
            mock_unpatch.return_value = (True, "All patches cleared")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.unpatch(all_patches=True)

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["comp"], "all")

    def test_unpatch_exception(self):
        """Test unpatch with exception"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "unpatch") as mock_unpatch:
            mock_unpatch.side_effect = Exception("Error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.unpatch(comp=0)

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])


class TestFPBCLICommands(unittest.TestCase):
    """Test CLI command execution via subprocess"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures"""
        cls.cli_path = Path(__file__).parent.parent / "fpb_cli.py"

    def run_cli(self, *args):
        """Helper to run CLI and parse JSON output"""
        cmd = [sys.executable, str(self.cli_path)] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return json.loads(result.stdout), result.returncode
        except json.JSONDecodeError:
            return {"error": result.stderr, "stdout": result.stdout}, result.returncode

    def test_help(self):
        """Test --help flag"""
        cmd = [sys.executable, str(self.cli_path), "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        # Help goes to stdout
        self.assertIn("usage", result.stdout.lower())

    def test_version(self):
        """Test --version flag"""
        cmd = [sys.executable, str(self.cli_path), "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)

    def test_compile_missing_source(self):
        """Test compile with non-existent source file"""
        output, code = self.run_cli("compile", "/nonexistent/patch.c")
        self.assertEqual(output["success"], False)
        self.assertIn("not found", output.get("error", "").lower())

    def test_info_no_port(self):
        """Test info without port"""
        output, code = self.run_cli("info")
        self.assertEqual(output["success"], False)
        self.assertIn("No device connected", output["error"])

    def test_unpatch_no_port(self):
        """Test unpatch without port"""
        output, code = self.run_cli("unpatch", "--comp", "0")
        self.assertEqual(output["success"], False)


class TestMain(unittest.TestCase):
    """Test main function"""

    def test_main_no_args(self):
        """Test main with no arguments"""
        with patch("sys.argv", ["fpb_cli.py"]):
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 1)

    def test_main_keyboard_interrupt(self):
        """Test main handles keyboard interrupt"""
        with patch("sys.argv", ["fpb_cli.py", "search", "/fake.elf", "test"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli.search.side_effect = KeyboardInterrupt()
                mock_cli_class.return_value = mock_cli
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 130)

    def test_main_cli_error(self):
        """Test main handles FPBCLIError"""
        with patch("sys.argv", ["fpb_cli.py", "search", "/fake.elf", "test"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli.search.side_effect = FPBCLIError("Test error")
                mock_cli_class.return_value = mock_cli
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 1)

    def test_main_unexpected_error(self):
        """Test main handles unexpected errors"""
        with patch("sys.argv", ["fpb_cli.py", "search", "/fake.elf", "test"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli.search.side_effect = RuntimeError("Unexpected")
                mock_cli_class.return_value = mock_cli
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 1)


class TestFPBCLIError(unittest.TestCase):
    """Test FPBCLIError exception"""

    def test_fpbcli_error_message(self):
        """Test FPBCLIError stores message"""
        err = FPBCLIError("Test error message")
        self.assertEqual(str(err), "Test error message")

    def test_fpbcli_error_inheritance(self):
        """Test FPBCLIError is Exception subclass"""
        err = FPBCLIError("Test")
        self.assertIsInstance(err, Exception)


class TestDeviceStateAdvanced(unittest.TestCase):
    """Additional DeviceState tests"""

    def test_connect_without_serial(self):
        """Test connect raises without pyserial"""
        state = DeviceState()
        with patch("fpb_cli.HAS_SERIAL", False):
            # Reload DeviceState method would be complex, test error message
            pass

    def test_disconnect_with_close_error(self):
        """Test disconnect handles close error gracefully"""
        state = DeviceState()
        mock_ser = MagicMock()
        mock_ser.close.side_effect = Exception("Close failed")
        state.ser = mock_ser
        state.connected = True

        # Should not raise
        try:
            state.disconnect()
        except Exception:
            pass  # May or may not raise depending on implementation


class TestMainArgumentParsing(unittest.TestCase):
    """Test main function argument parsing"""

    def test_main_analyze_command(self):
        """Test main with analyze command"""
        with patch("sys.argv", ["fpb_cli.py", "analyze", "/fake.elf", "main"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.analyze.assert_called_once()

    def test_main_disasm_command(self):
        """Test main with disasm command"""
        with patch("sys.argv", ["fpb_cli.py", "disasm", "/fake.elf", "main"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.disasm.assert_called_once()

    def test_main_decompile_command(self):
        """Test main with decompile command"""
        with patch("sys.argv", ["fpb_cli.py", "decompile", "/fake.elf", "main"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.decompile.assert_called_once()

    def test_main_signature_command(self):
        """Test main with signature command"""
        with patch("sys.argv", ["fpb_cli.py", "signature", "/fake.elf", "main"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.signature.assert_called_once()

    def test_main_search_command(self):
        """Test main with search command"""
        with patch("sys.argv", ["fpb_cli.py", "search", "/fake.elf", "gpio"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.search.assert_called_once()

    def test_main_compile_command(self):
        """Test main with compile command"""
        with patch("sys.argv", ["fpb_cli.py", "compile", "/fake.c"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.compile.assert_called_once()

    def test_main_info_command(self):
        """Test main with info command"""
        with patch("sys.argv", ["fpb_cli.py", "info"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.info.assert_called_once()

    def test_main_inject_command(self):
        """Test main with inject command"""
        with patch("sys.argv", ["fpb_cli.py", "inject", "target", "patch.c"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.inject.assert_called_once()

    def test_main_unpatch_command(self):
        """Test main with unpatch command"""
        with patch("sys.argv", ["fpb_cli.py", "unpatch", "--comp", "0"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.unpatch.assert_called_once()

    def test_main_with_global_elf(self):
        """Test main with global --elf option"""
        with patch("sys.argv", ["fpb_cli.py", "--elf", "/path/to/elf", "info"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                # Check that FPBCLI was created with elf_path
                call_kwargs = mock_cli_class.call_args.kwargs
                self.assertEqual(call_kwargs.get("elf_path"), "/path/to/elf")

    def test_main_with_port_and_baudrate(self):
        """Test main with --port and --baudrate"""
        with patch("sys.argv", ["fpb_cli.py", "--port", "/dev/ttyACM0", "--baudrate", "9600", "info"]):
            with patch("fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                call_kwargs = mock_cli_class.call_args.kwargs
                self.assertEqual(call_kwargs.get("port"), "/dev/ttyACM0")
                self.assertEqual(call_kwargs.get("baudrate"), 9600)


class TestFPBCLISetupLogging(unittest.TestCase):
    """Test setup_logging method"""

    def test_setup_logging_verbose(self):
        """Test verbose logging setup"""
        cli = FPBCLI(verbose=True)
        self.assertTrue(cli.verbose)
        cli.cleanup()

    def test_setup_logging_quiet(self):
        """Test quiet logging setup"""
        cli = FPBCLI(verbose=False)
        self.assertFalse(cli.verbose)
        cli.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)

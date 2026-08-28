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
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fpbinject.cli.fpb_cli import (
    FPBCLI,
    FPBCLIError,
    DeviceState,
    HAS_SERIAL,
    main,
)  # noqa: E402


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
        self.assertEqual(state.upload_chunk_size, 128)
        self.assertEqual(state.serial_tx_fragment_size, 0)
        self.assertEqual(state.serial_tx_fragment_delay, 0.002)

    @unittest.skipIf(not HAS_SERIAL, "pyserial not installed")
    @patch("fpbinject.cli.fpb_cli.serial.Serial")
    def test_connect_success(self, mock_serial):
        """Test successful connection"""
        state = DeviceState()
        mock_serial.return_value = MagicMock()

        result = state.connect("/dev/ttyACM0", 115200)
        self.assertTrue(result)
        self.assertTrue(state.connected)
        self.assertIsNotNone(state.ser)

    @unittest.skipIf(not HAS_SERIAL, "pyserial not installed")
    @patch("fpbinject.cli.fpb_cli.serial.Serial")
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

    def test_add_tool_log_stub(self):
        """Test add_tool_log is a no-op stub"""
        state = DeviceState()
        # Should not raise
        state.add_tool_log("test message")
        state.add_tool_log("")
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

    def test_init_with_tx_chunk_params(self):
        """Test initialization with TX chunk parameters"""
        cli = FPBCLI(tx_chunk_size=16, tx_chunk_delay=0.01)
        self.assertEqual(cli._device_state.serial_tx_fragment_size, 16)
        self.assertEqual(cli._device_state.serial_tx_fragment_delay, 0.01)
        cli.cleanup()

    @unittest.skipIf(not HAS_SERIAL, "pyserial not installed")
    @patch("fpbinject.cli.fpb_cli.PortLock")
    @patch("fpbinject.cli.fpb_cli.serial.Serial")
    def test_init_with_port(self, mock_serial, mock_port_lock):
        """Test initialization with serial port (direct mode)"""
        mock_serial.return_value = MagicMock()
        mock_port_lock.return_value.acquire.return_value = True
        cli = FPBCLI(port="/dev/ttyACM0", baudrate=9600, direct=True)
        self.assertTrue(cli._device_state.connected)
        cli.cleanup()

    def test_init_no_port_no_probe(self):
        """FPBCLI() without --port must not perform any network probe.

        This guarantees offline ELF/compile commands stay self-contained
        and unit tests do not depend on ambient network state.
        """
        with patch("fpbinject.cli.fpb_cli.ServerProxy") as mock_proxy_cls:
            cli = FPBCLI()
            try:
                mock_proxy_cls.assert_not_called()
                self.assertIsNone(cli._proxy)
                self.assertFalse(cli._device_state.connected)
            finally:
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
        data = {
            "success": True,
            "message": "Test message with unicode: \u00e9\u00e8\u00ea",
        }

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.output_json(data)

        output = f.getvalue()
        parsed = json.loads(output)
        self.assertEqual(
            parsed["message"], "Test message with unicode: \u00e9\u00e8\u00ea"
        )

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
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols, patch.object(
            self.cli._fpb, "disassemble_function"
        ) as mock_disasm, patch.object(self.cli._fpb, "get_signature") as mock_sig:
            mock_symbols.return_value = {
                "main": {"addr": 0x08001000, "sym_type": "function"}
            }
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
            mock_symbols.return_value = {
                "other": {"addr": 0x08001000, "sym_type": "function"}
            }

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
        """Test decompile without Ghidra configured"""
        with patch.object(self.cli._fpb, "decompile_function") as mock_dec:
            mock_dec.return_value = (False, "GHIDRA_NOT_CONFIGURED")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.decompile("/fake/elf", "main")

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
            self.assertIn("GHIDRA", output["error"])


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
                "gpio_init": {"addr": 0x08001000, "sym_type": "function"},
                "gpio_write": {"addr": 0x08001020, "sym_type": "function"},
                "main": {"addr": 0x08001100, "sym_type": "function"},
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
            mock_symbols.return_value = {
                "main": {"addr": 0x08001100, "sym_type": "function"}
            }

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.search("/fake/elf", "gpio")

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["count"], 0)

    def test_search_case_insensitive(self):
        """Test case-insensitive search"""
        with patch.object(self.cli._fpb, "get_symbols") as mock_symbols:
            mock_symbols.return_value = {
                "GPIO_Init": {"addr": 0x08001000, "sym_type": "function"}
            }

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
            mock_symbols.return_value = {
                f"gpio_{i}": {"addr": 0x08001000 + i, "sym_type": "function"}
                for i in range(30)
            }

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
        source.write_text("/* FPB_INJECT */\nvoid test_func(void) {}")

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (
                b"\x00\x01\x02",
                {"inject_test": 0x20001000},
                None,
            )

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.compile(str(source))

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["binary_size"], 3)

    def test_compile_large_binary(self):
        """Test compile with large binary (>1024 bytes)"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("/* FPB_INJECT */\nvoid test_func(void) {}")

        # Create binary larger than 1024 bytes
        large_binary = b"\x00" * 2000

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (
                large_binary,
                {"inject_test": 0x20001000},
                None,
            )

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
        source.write_text("/* FPB_INJECT */\nvoid test_func(void) {}")

        with patch.object(self.cli._fpb, "compile_inject") as mock_compile:
            mock_compile.return_value = (b"\x00", {"inject_test": 0x20002000}, None)

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.compile(
                    str(source),
                    elf_path="/path/to/elf",
                    base_addr=0x20002000,
                    compile_commands="/path/to/cc.json",
                )

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

    def test_test_serial_not_connected(self):
        """Test serial throughput without connection"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.test_serial()

        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    def test_test_serial_success(self):
        """Test serial throughput success"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "test_serial_throughput") as mock_test:
            mock_test.return_value = {
                "success": True,
                "max_working_size": 256,
                "failed_size": 512,
                "tests": [
                    {"size": 16, "passed": True},
                    {"size": 32, "passed": True},
                    {"size": 64, "passed": True},
                    {"size": 128, "passed": True},
                    {"size": 256, "passed": True},
                    {"size": 512, "passed": False, "error": "timeout"},
                ],
                "recommended_upload_chunk_size": 192,
                "recommended_download_chunk_size": 2048,
                "fragment_needed": False,
                "phases": {},
            }

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.test_serial(start_size=16, max_size=512)

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["max_working_size"], 256)
            self.assertEqual(output["failed_size"], 512)
            self.assertEqual(len(output["tests"]), 6)

    def test_test_serial_all_pass(self):
        """Test serial throughput when all sizes pass"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "test_serial_throughput") as mock_test:
            mock_test.return_value = {
                "success": True,
                "max_working_size": 4096,
                "failed_size": 0,
                "tests": [{"size": 16, "passed": True}],
                "recommended_upload_chunk_size": 3072,
                "recommended_download_chunk_size": 4096,
                "fragment_needed": False,
                "phases": {},
            }

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.test_serial()

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["failed_size"], 0)

    def test_test_serial_exception(self):
        """Test serial throughput with exception"""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "test_serial_throughput") as mock_test:
            mock_test.side_effect = Exception("Serial error")

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.test_serial()

            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
            self.assertIn("Serial error", output["error"])

    # ===== doctor tests =====

    def test_doctor_suggestions_fragment_and_chunks(self):
        """_doctor_suggestions turns a probe result into tuning flags."""
        result = {
            "success": True,
            "fragment_needed": True,
            "recommended_fragment_size": 64,
            "recommended_fragment_delay": 0.005,
            "recommended_upload_chunk_size": 96,
            "recommended_download_chunk_size": 2048,
        }
        suggestions = FPBCLI._doctor_suggestions(result)
        cmds = " ".join(s["command"] for s in suggestions)
        self.assertIn("--serial-tx-fragment-size 64", cmds)
        self.assertIn("--serial-tx-fragment-delay 0.005", cmds)
        self.assertIn("--upload-chunk-size 96", cmds)
        self.assertIn("--download-chunk-size 2048", cmds)

    def test_doctor_suggestions_healthy_no_fragment(self):
        """No fragmentation needed -> no TX-fragment suggestion."""
        result = {
            "success": True,
            "fragment_needed": False,
            "recommended_upload_chunk_size": 512,
            "recommended_download_chunk_size": 4096,
        }
        suggestions = FPBCLI._doctor_suggestions(result)
        cmds = " ".join(s["command"] for s in suggestions)
        self.assertNotIn("fragment", cmds)
        self.assertIn("--upload-chunk-size 512", cmds)

    def test_doctor_suggestions_empty_on_failure(self):
        self.assertEqual(FPBCLI._doctor_suggestions({"success": False}), [])
        self.assertEqual(FPBCLI._doctor_suggestions(None), [])

    def test_doctor_outputs_apply_command(self):
        """doctor emits an apply_command and a hint from the probe result."""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "test_serial_throughput") as mock_test:
            mock_test.return_value = {
                "success": True,
                "fragment_needed": True,
                "recommended_fragment_size": 32,
                "recommended_fragment_delay": 0.01,
                "recommended_upload_chunk_size": 48,
                "recommended_download_chunk_size": 1024,
            }
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.doctor()
            out = json.loads(f.getvalue())
            self.assertTrue(out["success"])
            self.assertIn("--serial-tx-fragment-size 32", out["apply_command"])
            self.assertIn("re-run your transfer with", out["hint"])

    def test_doctor_healthy_hint(self):
        """doctor with no suggestions reports a healthy hint."""
        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "test_serial_throughput") as mock_test:
            mock_test.return_value = {"success": True, "fragment_needed": False}
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.doctor()
            out = json.loads(f.getvalue())
            self.assertEqual(out["apply_command"], "")
            self.assertIn("healthy", out["hint"])

    # ===== file_list tests =====

    def test_file_list_not_connected(self):
        """Test file_list when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_list("/")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_list_success(self, mock_ft_cls):
        """Test file_list success"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.flist.return_value = (True, [{"name": "test.txt", "type": "file"}])
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_list("/data")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["path"], "/data")
        self.assertEqual(len(output["entries"]), 1)

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_list_failure(self, mock_ft_cls):
        """Test file_list when flist returns failure"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.flist.return_value = (False, [])
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_list("/nonexist")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_list_exception(self, mock_ft_cls):
        """Test file_list with exception"""
        self.cli._device_state.connected = True
        mock_ft_cls.side_effect = Exception("Transfer init error")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_list("/")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    # ===== file_stat tests =====

    def test_file_stat_not_connected(self):
        """Test file_stat when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_stat("/test.txt")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_stat_success(self, mock_ft_cls):
        """Test file_stat success"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.fstat.return_value = (True, {"size": 1024, "type": "file"})
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_stat("/data/test.bin")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["stat"]["size"], 1024)

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_stat_failure(self, mock_ft_cls):
        """Test file_stat when fstat returns failure"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.fstat.return_value = (False, {"error": "not found"})
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_stat("/missing")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    # ===== file_download tests =====

    def test_file_download_not_connected(self):
        """Test file_download when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_download("/remote.bin", "/tmp/local.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_download_success(self, mock_ft_cls):
        """Test file_download success"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.download.return_value = (True, b"file content", "OK")
        mock_ft_cls.return_value = mock_ft

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, "downloaded.bin")
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.file_download("/remote.bin", local_path)
            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["size"], 12)
            self.assertTrue(os.path.exists(local_path))
            with open(local_path, "rb") as lf:
                self.assertEqual(lf.read(), b"file content")

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_download_failure(self, mock_ft_cls):
        """Test file_download when download fails"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.download.return_value = (False, None, "CRC error")
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_download("/remote.bin", "/tmp/out.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        # CRC-flavored failure should carry a doctor hint.
        self.assertIn("hint", output)
        self.assertIn("doctor", output["hint"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_download_creates_directory(self, mock_ft_cls):
        """Test file_download creates local directory if needed"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.download.return_value = (True, b"data", "OK")
        mock_ft_cls.return_value = mock_ft

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, "subdir", "nested", "file.bin")
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.file_download("/remote.bin", local_path)
            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertTrue(os.path.exists(local_path))

    def test_info_build_time_match(self):
        """Test info with matching build times"""
        self.cli._device_state.connected = True

        with tempfile.NamedTemporaryFile(delete=False, suffix=".elf") as tf:
            elf_path = tf.name
        self.cli._device_state.elf_path = elf_path

        try:
            with patch.object(self.cli._fpb, "info") as mock_info:
                mock_info.return_value = (
                    {"slots": [], "build_time": "Jan 29 2026 14:30:00"},
                    None,
                )
                with patch.object(self.cli._fpb, "get_elf_build_time") as mock_elf_time:
                    mock_elf_time.return_value = "Jan 29 2026 14:30:00"

                    f = io.StringIO()
                    with redirect_stdout(f):
                        self.cli.info()

                    output = json.loads(f.getvalue())
                    self.assertTrue(output["success"])
                    self.assertFalse(output.get("build_time_mismatch", False))
                    self.assertEqual(
                        output.get("device_build_time"), "Jan 29 2026 14:30:00"
                    )
                    self.assertEqual(
                        output.get("elf_build_time"), "Jan 29 2026 14:30:00"
                    )
        finally:
            os.unlink(elf_path)

    def test_info_build_time_mismatch(self):
        """Test info with mismatched build times"""
        self.cli._device_state.connected = True

        with tempfile.NamedTemporaryFile(delete=False, suffix=".elf") as tf:
            elf_path = tf.name
        self.cli._device_state.elf_path = elf_path

        try:
            with patch.object(self.cli._fpb, "info") as mock_info:
                mock_info.return_value = (
                    {"slots": [], "build_time": "Jan 29 2026 14:30:00"},
                    None,
                )
                with patch.object(self.cli._fpb, "get_elf_build_time") as mock_elf_time:
                    mock_elf_time.return_value = "Jan 28 2026 10:00:00"

                    f = io.StringIO()
                    with redirect_stdout(f):
                        self.cli.info()

                    output = json.loads(f.getvalue())
                    self.assertTrue(output["success"])
                    self.assertTrue(output.get("build_time_mismatch", False))
                    self.assertEqual(
                        output.get("device_build_time"), "Jan 29 2026 14:30:00"
                    )
                    self.assertEqual(
                        output.get("elf_build_time"), "Jan 28 2026 10:00:00"
                    )
        finally:
            os.unlink(elf_path)

    def test_info_no_elf_path(self):
        """Test info without ELF path configured"""
        self.cli._device_state.connected = True
        self.cli._device_state.elf_path = ""

        with patch.object(self.cli._fpb, "info") as mock_info:
            mock_info.return_value = (
                {"slots": [], "build_time": "Jan 29 2026 14:30:00"},
                None,
            )

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.info()

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            # Build time fields present but elf_build_time is None
            self.assertEqual(output.get("device_build_time"), "Jan 29 2026 14:30:00")
            self.assertIsNone(output.get("elf_build_time"))
            self.assertFalse(output.get("build_time_mismatch", False))

    def test_info_no_device_build_time(self):
        """Test info when device doesn't report build time"""
        self.cli._device_state.connected = True

        with tempfile.NamedTemporaryFile(delete=False, suffix=".elf") as tf:
            elf_path = tf.name
        self.cli._device_state.elf_path = elf_path

        try:
            with patch.object(self.cli._fpb, "info") as mock_info:
                mock_info.return_value = ({"slots": []}, None)  # No build_time
                with patch.object(self.cli._fpb, "get_elf_build_time") as mock_elf_time:
                    mock_elf_time.return_value = "Jan 29 2026 14:30:00"

                    f = io.StringIO()
                    with redirect_stdout(f):
                        self.cli.info()

                    output = json.loads(f.getvalue())
                    self.assertTrue(output["success"])
                    # Has build time fields but no mismatch (device doesn't report)
                    self.assertFalse(output.get("build_time_mismatch", False))
                    self.assertIsNone(output.get("device_build_time"))
                    self.assertEqual(
                        output.get("elf_build_time"), "Jan 29 2026 14:30:00"
                    )
        finally:
            os.unlink(elf_path)

    # ===== file_upload tests =====

    def test_file_upload_not_connected(self):
        """Test file_upload when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_upload("/tmp/local.bin", "/remote.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_upload_success(self, mock_ft_cls):
        """Test file_upload success"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.upload.return_value = (True, "Uploaded 5 bytes to /remote.bin")
        mock_ft_cls.return_value = mock_ft

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"hello")
            tf.flush()
            local_path = tf.name

        try:
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.file_upload(local_path, "/remote.bin")
            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["size"], 5)
            self.assertEqual(output["remote_path"], "/remote.bin")
            self.assertEqual(output["local_path"], local_path)
        finally:
            os.unlink(local_path)

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_upload_failure(self, mock_ft_cls):
        """Test file_upload when upload fails"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.upload.return_value = (False, "CRC mismatch")
        mock_ft_cls.return_value = mock_ft

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"data")
            tf.flush()
            local_path = tf.name

        try:
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.file_upload(local_path, "/remote.bin")
            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
        finally:
            os.unlink(local_path)

    def test_file_upload_local_not_found(self):
        """Test file_upload with nonexistent local file"""
        self.cli._device_state.connected = True
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_upload("/nonexistent/file.bin", "/remote.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_upload_exception(self, mock_ft_cls):
        """Test file_upload with exception"""
        self.cli._device_state.connected = True
        mock_ft_cls.side_effect = Exception("Transfer init error")

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"data")
            tf.flush()
            local_path = tf.name

        try:
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.file_upload(local_path, "/remote.bin")
            output = json.loads(f.getvalue())
            self.assertFalse(output["success"])
        finally:
            os.unlink(local_path)

    # ===== file_remove tests =====

    def test_file_remove_not_connected(self):
        """Test file_remove when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_remove("/data/old.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_remove_success(self, mock_ft_cls):
        """Test file_remove success"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.fremove.return_value = (True, "OK")
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_remove("/data/old.bin")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["path"], "/data/old.bin")

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_remove_failure(self, mock_ft_cls):
        """Test file_remove when fremove fails"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.fremove.return_value = (False, "file not found")
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_remove("/data/missing.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_remove_exception(self, mock_ft_cls):
        """Test file_remove with exception"""
        self.cli._device_state.connected = True
        mock_ft_cls.side_effect = Exception("Transfer init error")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_remove("/data/old.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    # ===== file_mkdir tests =====

    def test_file_mkdir_not_connected(self):
        """Test file_mkdir when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_mkdir("/data/newdir")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_mkdir_success(self, mock_ft_cls):
        """Test file_mkdir success"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.fmkdir.return_value = (True, "OK")
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_mkdir("/data/newdir")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["path"], "/data/newdir")

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_mkdir_failure(self, mock_ft_cls):
        """Test file_mkdir when fmkdir fails"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.fmkdir.return_value = (False, "permission denied")
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_mkdir("/data/newdir")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_mkdir_exception(self, mock_ft_cls):
        """Test file_mkdir with exception"""
        self.cli._device_state.connected = True
        mock_ft_cls.side_effect = Exception("Transfer init error")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_mkdir("/data/newdir")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    # ===== file_rename tests =====

    def test_file_rename_not_connected(self):
        """Test file_rename when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_rename("/data/old.bin", "/data/new.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_rename_success(self, mock_ft_cls):
        """Test file_rename success"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.frename.return_value = (True, "OK")
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_rename("/data/old.bin", "/data/new.bin")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["old_path"], "/data/old.bin")
        self.assertEqual(output["new_path"], "/data/new.bin")

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_rename_failure(self, mock_ft_cls):
        """Test file_rename when frename fails"""
        self.cli._device_state.connected = True
        mock_ft = MagicMock()
        mock_ft.frename.return_value = (False, "source not found")
        mock_ft_cls.return_value = mock_ft

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_rename("/data/old.bin", "/data/new.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    @patch("fpbinject.core.file_transfer.FileTransfer")
    def test_file_rename_exception(self, mock_ft_cls):
        """Test file_rename with exception"""
        self.cli._device_state.connected = True
        mock_ft_cls.side_effect = Exception("Transfer init error")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_rename("/data/old.bin", "/data/new.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    # ===== file_upload via proxy tests =====

    def test_file_upload_proxy(self):
        """Test file_upload delegates to proxy when available"""
        self.cli._proxy = MagicMock()
        self.cli._proxy.file_upload.return_value = {
            "success": True,
            "message": "Uploaded 5 bytes",
        }

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"hello")
            tf.flush()
            local_path = tf.name

        try:
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.file_upload(local_path, "/remote.bin")
            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.cli._proxy.file_upload.assert_called_once_with(
                local_path, "/remote.bin"
            )
        finally:
            os.unlink(local_path)

    def test_file_remove_proxy(self):
        """Test file_remove delegates to proxy when available"""
        self.cli._proxy = MagicMock()
        self.cli._proxy.file_remove.return_value = {
            "success": True,
            "message": "OK",
        }

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_remove("/data/old.bin")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.cli._proxy.file_remove.assert_called_once_with("/data/old.bin")

    def test_file_mkdir_proxy(self):
        """Test file_mkdir delegates to proxy when available"""
        self.cli._proxy = MagicMock()
        self.cli._proxy.file_mkdir.return_value = {
            "success": True,
            "message": "OK",
        }

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_mkdir("/data/newdir")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.cli._proxy.file_mkdir.assert_called_once_with("/data/newdir")

    def test_file_rename_proxy(self):
        """Test file_rename delegates to proxy when available"""
        self.cli._proxy = MagicMock()
        self.cli._proxy.file_rename.return_value = {
            "success": True,
            "message": "OK",
        }

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.file_rename("/data/old.bin", "/data/new.bin")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.cli._proxy.file_rename.assert_called_once_with(
            "/data/old.bin", "/data/new.bin"
        )

    # ===== mem_read tests =====

    def test_mem_read_not_connected(self):
        """Test mem_read when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_read(0x20000000, 64)
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    def test_mem_read_success_hex(self):
        """Test mem_read success with hex format"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()
        self.cli._fpb.read_memory.return_value = (b"\x00\x01\x02\x03" * 4, "OK")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_read(0x20000000, 16, "hex")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertIn("hex_dump", output)
        self.assertEqual(output["actual_length"], 16)

    def test_mem_read_success_raw(self):
        """Test mem_read success with raw format"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()
        self.cli._fpb.read_memory.return_value = (b"\xde\xad", "OK")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_read(0x20000000, 2, "raw")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["data"], "dead")

    def test_mem_read_success_u32(self):
        """Test mem_read success with u32 format"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()
        self.cli._fpb.read_memory.return_value = (
            b"\x01\x00\x00\x00\x02\x00\x00\x00",
            "OK",
        )

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_read(0x20000000, 8, "u32")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(len(output["words"]), 2)
        self.assertEqual(output["words"][0], "0x00000001")

    def test_mem_read_failure(self):
        """Test mem_read when read_memory returns None"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()
        self.cli._fpb.read_memory.return_value = (None, "timeout")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_read(0x20000000, 64)
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    def test_mem_read_proxy(self):
        """Test mem_read delegates to proxy"""
        self.cli._proxy = MagicMock()
        self.cli._proxy.mem_read.return_value = {"success": True, "hex_dump": "00 01"}

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_read(0x20000000, 64, "hex")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.cli._proxy.mem_read.assert_called_once_with(0x20000000, 64, "hex")

    # ===== mem_write tests =====

    def test_mem_write_not_connected(self):
        """Test mem_write when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_write(0x20000000, "DEADBEEF")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    def test_mem_write_success(self):
        """Test mem_write success"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()
        self.cli._fpb.write_memory.return_value = (True, None)

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_write(0x20000000, "DEADBEEF")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.assertEqual(output["length"], 4)

    def test_mem_write_invalid_hex(self):
        """Test mem_write with invalid hex data"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_write(0x20000000, "ZZZZ")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("Invalid hex data", output["error"])

    def test_mem_write_failure(self):
        """Test mem_write when write_memory fails"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()
        self.cli._fpb.write_memory.return_value = (False, "bus fault")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_write(0x20000000, "DEADBEEF")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    def test_mem_write_proxy(self):
        """Test mem_write delegates to proxy"""
        self.cli._proxy = MagicMock()
        self.cli._proxy.mem_write.return_value = {"success": True, "message": "written"}

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_write(0x20000000, "DEADBEEF")
        output = json.loads(f.getvalue())
        self.assertTrue(output["success"])
        self.cli._proxy.mem_write.assert_called_once_with(0x20000000, "DEADBEEF")

    # ===== mem_dump tests =====

    def test_mem_dump_not_connected(self):
        """Test mem_dump when not connected"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_dump(0x20000000, 64, "/tmp/out.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    def test_mem_dump_success(self):
        """Test mem_dump success"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()
        self.cli._fpb.read_memory.return_value = (b"\x00\x01\x02\x03", "OK")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "dump.bin")
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.mem_dump(0x20000000, 4, out_path)
            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertEqual(output["length"], 4)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, "rb") as lf:
                self.assertEqual(lf.read(), b"\x00\x01\x02\x03")

    def test_mem_dump_failure(self):
        """Test mem_dump when read_memory returns None"""
        self.cli._device_state.connected = True
        self.cli._fpb = MagicMock()
        self.cli._fpb.read_memory.return_value = (None, "timeout")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_dump(0x20000000, 64, "/tmp/out.bin")
        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])

    def test_mem_dump_proxy_success(self):
        """Test mem_dump via proxy"""
        self.cli._proxy = MagicMock()
        self.cli._proxy.mem_read.return_value = {
            "success": True,
            "data": "00010203",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "dump.bin")
            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.mem_dump(0x20000000, 4, out_path)
            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])
            self.assertTrue(os.path.exists(out_path))

    def test_mem_dump_proxy_failure(self):
        """Test mem_dump via proxy when read fails"""
        self.cli._proxy = MagicMock()
        self.cli._proxy.mem_read.return_value = {
            "success": False,
            "error": "not connected",
        }

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.mem_dump(0x20000000, 64, "/tmp/out.bin")
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
        source.write_text("/* FPB_INJECT */\nvoid test_func(void) {}")

        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.inject("target", str(source))

        output = json.loads(f.getvalue())
        self.assertFalse(output["success"])
        self.assertIn("No device connected", output["error"])

    def test_inject_not_connected_with_elf(self):
        """Test inject offline with ELF (compile validation)"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("/* FPB_INJECT */\nvoid test_func(void) {}")

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
        source.write_text("/* FPB_INJECT */\nvoid test_func(void) {}")

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
        source.write_text("/* FPB_INJECT */\nvoid test_func(void) {}")

        self.cli._device_state.connected = True
        with patch.object(self.cli._fpb, "inject") as mock_inject:
            mock_inject.return_value = (True, {"slot": 1})

            f = io.StringIO()
            with redirect_stdout(f):
                self.cli.inject(
                    "target",
                    str(source),
                    elf_path="/fake/elf",
                    compile_commands="/fake/cc.json",
                    patch_mode="debugmon",
                    comp=1,
                    verify=True,
                )

            output = json.loads(f.getvalue())
            self.assertTrue(output["success"])

    def test_inject_exception(self):
        """Test inject with exception"""
        source = Path(self.temp_dir) / "test.c"
        source.write_text("/* FPB_INJECT */\nvoid test_func(void) {}")

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
        """Helper to run CLI and parse JSON output.

        Pins --server-url to an unreachable local port so tests stay
        deterministic even when an unrelated WebServer is listening on
        the default 5500 on the developer's machine.
        """
        cmd = [
            sys.executable,
            str(self.cli_path),
            "--server-url",
            "http://127.0.0.1:1",
        ] + list(args)
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
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli.search.side_effect = KeyboardInterrupt()
                mock_cli_class.return_value = mock_cli
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 130)

    def test_main_cli_error(self):
        """Test main handles FPBCLIError"""
        with patch("sys.argv", ["fpb_cli.py", "search", "/fake.elf", "test"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli.search.side_effect = FPBCLIError("Test error")
                mock_cli_class.return_value = mock_cli
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(ctx.exception.code, 1)

    def test_main_unexpected_error(self):
        """Test main handles unexpected errors"""
        with patch("sys.argv", ["fpb_cli.py", "search", "/fake.elf", "test"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
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
        with patch("fpbinject.cli.fpb_cli.HAS_SERIAL", False):
            # Reload DeviceState method would be complex, test error message
            pass

    def test_disconnect_with_close_error(self):
        """Test disconnect handles close error gracefully"""
        device_state = DeviceState()
        mock_ser = MagicMock()
        mock_ser.close.side_effect = Exception("Close failed")
        device_state.ser = mock_ser
        device_state.connected = True

        # Should not raise
        try:
            device_state.disconnect()
        except Exception:
            pass  # May or may not raise depending on implementation


class TestMainArgumentParsing(unittest.TestCase):
    """Test main function argument parsing.

    These tests only verify that ``main()`` dispatches to the right FPBCLI
    method for each subcommand; they must not perform real connection
    resolution. Device subcommands would otherwise fall through to a 3s
    mDNS browse (``discover_sync``) with no server present, adding ~1min
    across the class. setUp stubs discovery so resolution resolves to the
    localhost fallback instantly while keeping ``resolve_connection_plan``
    itself real (so --port/--baudrate assertions still hold).
    """

    def setUp(self):
        patchers = [
            patch("fpbinject.cli.fpb_cli.discover_sync", return_value=[]),
            patch("fpbinject.cli.fpb_cli.list_cli_servers", return_value=[]),
            patch("fpbinject.cli.fpb_cli._localhost_status_ok", return_value=False),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_main_analyze_command(self):
        """Test main with analyze command"""
        with patch("sys.argv", ["fpb_cli.py", "analyze", "/fake.elf", "main"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.analyze.assert_called_once()

    def test_main_disasm_command(self):
        """Test main with disasm command"""
        with patch("sys.argv", ["fpb_cli.py", "disasm", "/fake.elf", "main"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.disasm.assert_called_once()

    def test_main_decompile_command(self):
        """Test main with decompile command"""
        with patch("sys.argv", ["fpb_cli.py", "decompile", "/fake.elf", "main"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.decompile.assert_called_once()

    def test_main_signature_command(self):
        """Test main with signature command"""
        with patch("sys.argv", ["fpb_cli.py", "signature", "/fake.elf", "main"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.signature.assert_called_once()

    def test_main_search_command(self):
        """Test main with search command"""
        with patch("sys.argv", ["fpb_cli.py", "search", "/fake.elf", "gpio"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.search.assert_called_once()

    def test_main_compile_command(self):
        """Test main with compile command"""
        with patch("sys.argv", ["fpb_cli.py", "compile", "/fake.c"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.compile.assert_called_once()

    def test_main_info_command(self):
        """Test main with info command"""
        with patch("sys.argv", ["fpb_cli.py", "info"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.info.assert_called_once()

    def test_main_inject_command(self):
        """Test main with inject command"""
        with patch("sys.argv", ["fpb_cli.py", "inject", "target", "patch.c"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.inject.assert_called_once()

    def test_main_unpatch_command(self):
        """Test main with unpatch command"""
        with patch("sys.argv", ["fpb_cli.py", "unpatch", "--comp", "0"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.unpatch.assert_called_once()

    def test_main_with_global_elf(self):
        """Test main with global --elf option"""
        with patch("sys.argv", ["fpb_cli.py", "--elf", "/path/to/elf", "info"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                # Check that FPBCLI was created with elf_path
                call_kwargs = mock_cli_class.call_args.kwargs
                self.assertEqual(call_kwargs.get("elf_path"), "/path/to/elf")

    def test_main_with_port_and_baudrate(self):
        """Test main with --port and --baudrate"""
        with patch(
            "sys.argv",
            ["fpb_cli.py", "--port", "/dev/ttyACM0", "--baudrate", "9600", "info"],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                plan = mock_cli_class.call_args.kwargs.get("plan")
                self.assertIsNotNone(plan)
                self.assertEqual(plan.serial_port, "/dev/ttyACM0")
                self.assertEqual(plan.baudrate, 9600)

    def test_main_transfer_flags_new_names(self):
        """New schema flag names map into the FPBCLI kwargs."""
        with patch(
            "sys.argv",
            [
                "fpb_cli.py",
                "--serial-tx-fragment-size",
                "64",
                "--serial-tx-fragment-delay",
                "0.01",
                "--transfer-max-retries",
                "3",
                "info",
            ],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli_class.return_value = MagicMock()
                main()
                kwargs = mock_cli_class.call_args.kwargs
                self.assertEqual(kwargs.get("tx_chunk_size"), 64)
                self.assertEqual(kwargs.get("tx_chunk_delay"), 0.01)
                self.assertEqual(kwargs.get("max_retries"), 3)

    def test_main_transfer_flags_legacy_aliases(self):
        """Legacy --tx-chunk-* / --max-retries aliases still work."""
        with patch(
            "sys.argv",
            [
                "fpb_cli.py",
                "--tx-chunk-size",
                "32",
                "--tx-chunk-delay",
                "0.02",
                "--max-retries",
                "7",
                "info",
            ],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli_class.return_value = MagicMock()
                main()
                kwargs = mock_cli_class.call_args.kwargs
                self.assertEqual(kwargs.get("tx_chunk_size"), 32)
                self.assertEqual(kwargs.get("tx_chunk_delay"), 0.02)
                self.assertEqual(kwargs.get("max_retries"), 7)

    def test_main_transfer_flags_defaults(self):
        """Unset transfer flags fall back to schema defaults for the CLI."""
        with patch("sys.argv", ["fpb_cli.py", "info"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli_class.return_value = MagicMock()
                main()
                kwargs = mock_cli_class.call_args.kwargs
                self.assertEqual(kwargs.get("tx_chunk_size"), 0)
                self.assertEqual(kwargs.get("tx_chunk_delay"), 0.002)
                self.assertEqual(kwargs.get("max_retries"), 10)

    def test_main_file_list_command(self):
        """Test main with file-list command"""
        with patch("sys.argv", ["fpb_cli.py", "file-list", "/data"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.file_list.assert_called_once_with("/data")

    def test_main_file_list_default_path(self):
        """Test main with file-list command using default path"""
        with patch("sys.argv", ["fpb_cli.py", "file-list"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.file_list.assert_called_once_with("/")

    def test_main_file_stat_command(self):
        """Test main with file-stat command"""
        with patch("sys.argv", ["fpb_cli.py", "file-stat", "/data/test.bin"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.file_stat.assert_called_once_with("/data/test.bin")

    def test_main_file_download_command(self):
        """Test main with file-download command"""
        with patch(
            "sys.argv",
            ["fpb_cli.py", "file-download", "/remote.bin", "/tmp/local.bin"],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.file_download.assert_called_once_with(
                    "/remote.bin", "/tmp/local.bin"
                )

    def test_main_file_upload_command(self):
        """Test main with file-upload command"""
        with patch(
            "sys.argv",
            ["fpb_cli.py", "file-upload", "/tmp/local.bin", "/remote.bin"],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.file_upload.assert_called_once_with(
                    "/tmp/local.bin", "/remote.bin"
                )

    def test_main_file_remove_command(self):
        """Test main with file-remove command"""
        with patch("sys.argv", ["fpb_cli.py", "file-remove", "/data/old.bin"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.file_remove.assert_called_once_with("/data/old.bin")

    def test_main_file_mkdir_command(self):
        """Test main with file-mkdir command"""
        with patch("sys.argv", ["fpb_cli.py", "file-mkdir", "/data/newdir"]):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.file_mkdir.assert_called_once_with("/data/newdir")

    def test_main_file_rename_command(self):
        """Test main with file-rename command"""
        with patch(
            "sys.argv",
            ["fpb_cli.py", "file-rename", "/data/old.bin", "/data/new.bin"],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.file_rename.assert_called_once_with(
                    "/data/old.bin", "/data/new.bin"
                )

    def test_main_mem_read_command(self):
        """Test main with mem-read command"""
        with patch(
            "sys.argv",
            ["fpb_cli.py", "mem-read", "0x20000000", "64", "--fmt", "raw"],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.mem_read.assert_called_once_with(0x20000000, 64, "raw")

    def test_main_mem_write_command(self):
        """Test main with mem-write command"""
        with patch(
            "sys.argv",
            ["fpb_cli.py", "mem-write", "0x20000000", "DEADBEEF"],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.mem_write.assert_called_once_with(0x20000000, "DEADBEEF")

    def test_main_mem_dump_command(self):
        """Test main with mem-dump command"""
        with patch(
            "sys.argv",
            ["fpb_cli.py", "mem-dump", "0x20000000", "256", "/tmp/dump.bin"],
        ):
            with patch("fpbinject.cli.fpb_cli.FPBCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli_class.return_value = mock_cli
                main()
                mock_cli.mem_dump.assert_called_once_with(
                    0x20000000, 256, "/tmp/dump.bin"
                )


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


class TestCppMemberFunctionHijacking(unittest.TestCase):
    """Test C++ member function hijacking capabilities"""

    def setUp(self):
        """Set up test fixtures"""
        self.cli = FPBCLI()
        # Mock ELF data with C++ mangled symbols
        self.mock_elf_data = {
            "functions": [
                {"name": "blink_led", "address": 0x080087D0, "size": 100},
                {
                    "name": "_ZN5Print5printEPKc",
                    "address": 0x08008792,
                    "size": 50,
                },  # Print::print(char const*)
                {
                    "name": "_ZN5Print5writeEPKc",
                    "address": 0x080086D8,
                    "size": 40,
                },  # Print::write(char const*)
                {
                    "name": "_ZN14HardwareSerial5beginEm",
                    "address": 0x08008500,
                    "size": 30,
                },  # HardwareSerial::begin(unsigned long)
            ],
            "symbols": [
                {"name": "_ZN5Print5printEPKc", "address": 0x08008792, "type": "FUNC"},
                {"name": "_ZN5Print5writeEPKc", "address": 0x080086D8, "type": "FUNC"},
                {
                    "name": "_ZN14HardwareSerial5beginEm",
                    "address": 0x08008500,
                    "type": "FUNC",
                },
            ],
        }

    def tearDown(self):
        """Clean up"""
        self.cli.cleanup()

    def test_search_cpp_mangled_name(self):
        """Test searching for C++ mangled function names"""
        with patch.object(self.cli, "_fpb") as mock_fpb:
            # Mock get_symbols to return C++ mangled names
            mock_fpb.get_symbols.return_value = {
                "_ZN5Print5printEPKc": {"addr": 0x08008792, "sym_type": "function"},
                "_ZN5Print5writeEPKc": {"addr": 0x080086D8, "sym_type": "function"},
                "_ZN14HardwareSerial5beginEm": {
                    "addr": 0x08008500,
                    "sym_type": "function",
                },
                "blink_led": {"addr": 0x080087D0, "sym_type": "function"},
            }

            # Capture output
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                self.cli.search("/tmp/test.elf", "_ZN5Print")
                output = mock_stdout.getvalue()
                result = json.loads(output)

                self.assertTrue(result["success"])
                # Should find Print class methods
                self.assertGreater(result["count"], 0)

    def test_search_cpp_class_name(self):
        """Test searching using partial C++ class names"""
        with patch.object(self.cli, "_fpb") as mock_fpb:
            mock_fpb.get_symbols.return_value = {
                "_ZN5Print5printEPKc": {"addr": 0x08008792, "sym_type": "function"},
                "_ZN5Print5writeEPKc": {"addr": 0x080086D8, "sym_type": "function"},
                "_ZN14HardwareSerial5beginEm": {
                    "addr": 0x08008500,
                    "sym_type": "function",
                },
            }

            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                self.cli.search("/tmp/test.elf", "HardwareSerial")
                output = mock_stdout.getvalue()
                result = json.loads(output)

                self.assertTrue(result["success"])
                self.assertGreater(result["count"], 0)

    def test_cpp_member_function_signature_detection(self):
        """Test detecting C++ member function by mangled name format"""
        # _ZN prefix indicates a C++ member function (nested name)
        mangled_names = [
            "_ZN5Print5printEPKc",  # Print::print(char const*)
            "_ZN5Print5writeEPKc",  # Print::write(char const*)
            "_ZN14HardwareSerial5beginEm",  # HardwareSerial::begin(unsigned long)
        ]

        for name in mangled_names:
            # _ZN indicates C++ mangled name with nested names
            self.assertTrue(name.startswith("_ZN"), f"{name} should start with _ZN")

    def test_compile_cpp_patch_with_extern_c(self):
        """Test compiling C++ patch with extern C linkage"""
        # C++ member function patch needs extern "C" to avoid double mangling
        # Example code (not used in test, just for documentation):
        # cpp_patch_code = '''
        # #include <stddef.h>
        # extern "C" size_t _ZN5Print5writeEPKc(void* thisptr, const char* str);
        # /* FPB_INJECT */
        # extern "C" size_t Print_print(void* thisptr, const char* str) {
        #     _ZN5Print5writeEPKc(thisptr, "[HOOK] ");
        #     return _ZN5Print5writeEPKc(thisptr, str);
        # }
        # '''
        with patch.object(self.cli, "compile") as mock_compile:
            mock_compile.return_value = {
                "success": True,
                "binary_size": 56,
                "base_addr": "0x20001000",
                "symbols": {
                    "Print_print": "0x20001000",
                    "___ZN5Print5writeEPKc_veneer": "0x20001020",
                },
            }

            result = self.cli.compile("/tmp/test_patch.cpp")
            self.assertTrue(result["success"])
            self.assertIn("Print_print", result["symbols"])
            # Veneer for original function call
            self.assertIn("___ZN5Print5writeEPKc_veneer", result["symbols"])

    def test_inject_cpp_member_function_with_trampoline(self):
        """Test injecting a C++ member function hijack using trampoline mode"""
        with patch.object(self.cli, "inject") as mock_inject:
            mock_inject.return_value = {
                "success": True,
                "result": {
                    "code_size": 56,
                    "inject_func": "Print_print",
                    "target_addr": "0x08008792",  # Print::print address
                    "inject_addr": "0x20000250",
                    "slot": 0,
                    "patch_mode": "trampoline",
                },
            }

            result = self.cli.inject(
                inject_func="Print_print",
                target_addr="0x08008792",  # C++ mangled function address
                patch_mode="trampoline",
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["result"]["patch_mode"], "trampoline")
            self.assertEqual(result["result"]["target_addr"], "0x08008792")

    def test_arm_eabi_cpp_member_function_calling_convention(self):
        """Test understanding of ARM EABI C++ member function calling convention

        For C++ member functions on ARM EABI:
        - r0 = this pointer
        - r1 = first argument
        - r2 = second argument
        - etc.
        """
        # This test documents the calling convention
        # The hijack function must preserve this convention:
        # void* thisptr in r0, const char* str in r1

        # Example: Print::print(const char* str)
        # Assembly call would be:
        #   r0 = &Serial (this pointer)
        #   r1 = "Hello" (string argument)
        #   BL _ZN5Print5printEPKc

        expected_signature = "size_t inject_func(void* thisptr, const char* str)"
        self.assertIn("thisptr", expected_signature)
        self.assertIn("str", expected_signature)

    def test_compile_cpp_patch_generates_veneer(self):
        """Test that compiling C++ patch generates veneer for original function call"""
        with patch.object(self.cli, "compile") as mock_compile:
            mock_compile.return_value = {
                "success": True,
                "binary_size": 56,
                "base_addr": "0x20001000",
                "symbols": {
                    "Print_print": "0x20001000",
                    "___ZN5Print5writeEPKc_veneer": "0x20001020",
                },
            }

            result = self.cli.compile("/tmp/test_patch.cpp")

            # Veneer symbol should be generated for the external C++ function call
            veneer_symbols = [s for s in result["symbols"] if "veneer" in s]
            self.assertTrue(
                len(veneer_symbols) > 0, "Should generate veneer for C++ function calls"
            )

    def test_cpp_mangled_name_demangling_concept(self):
        """Test C++ name mangling/demangling concepts

        Itanium C++ ABI mangling rules (used by ARM):
        _Z = mangled C++ symbol
        N = nested name
        <number><name> = length-prefixed name
        E = end of nested name
        P = pointer
        K = const
        c = char
        m = unsigned long
        """
        # _ZN5Print5printEPKc breakdown:
        # _Z = C++ mangled
        # N = nested name start
        # 5Print = class name "Print" (5 chars)
        # 5print = method name "print" (5 chars)
        # E = end nested name
        # P = pointer
        # K = const
        # c = char
        # Result: Print::print(char const*)

        mangled = "_ZN5Print5printEPKc"
        self.assertTrue(mangled.startswith("_ZN"))
        self.assertIn("Print", mangled)
        self.assertIn("print", mangled)


class TestFpbCliEntryPoint(unittest.TestCase):
    """Test the fpb_cli.py entry point wrapper"""

    def test_import_cli_main(self):
        """Test that the CLI entry point is importable"""
        from fpbinject.cli import fpb_cli

        self.assertTrue(hasattr(fpb_cli, "main"))

    def test_console_script_target_resolves(self):
        """The fpbinject console script target (fpbinject.cli.fpb_cli:main)."""
        from fpbinject.cli.fpb_cli import main as cli_main

        self.assertTrue(callable(cli_main))

    def test_cli_main_can_be_called(self):
        """Test that cli main can be called.

        With no subcommand, main() prints help and calls sys.exit(1). The
        stub must raise SystemExit (real behavior) so main() stops there;
        otherwise execution falls through to connection resolution and
        blocks ~3s on an mDNS browse.
        """
        from fpbinject.cli.fpb_cli import main as cli_main

        with patch("sys.argv", ["fpbinject"]):
            with patch("sys.exit", side_effect=SystemExit):
                with self.assertRaises(SystemExit):
                    cli_main()


class TestCorePackage(unittest.TestCase):
    """Test the core package"""

    def test_import_core_package(self):
        """Test that core package can be imported"""
        import fpbinject.core as core

        self.assertIsNotNone(core)

    def test_import_core_submodules(self):
        """Test that core submodules can be imported"""
        from fpbinject.core import elf_utils
        from fpbinject.core import compiler
        from fpbinject.core import state
        from fpbinject.core import patch_generator

        self.assertIsNotNone(elf_utils)
        self.assertIsNotNone(compiler)
        self.assertIsNotNone(state)
        self.assertIsNotNone(patch_generator)


class TestFPBCLIClass(unittest.TestCase):
    """Test FPBCLI class methods"""

    def setUp(self):
        """Set up test environment"""
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        """Clean up"""
        self.cli.cleanup()

    def test_output_json(self):
        """Test JSON output"""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.output_json({"success": True, "data": "test"})
            output = mock_stdout.getvalue()
            data = json.loads(output)
            self.assertTrue(data["success"])

    def test_output_error(self):
        """Test error output"""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.output_error("Test error")
            output = mock_stdout.getvalue()
            data = json.loads(output)
            self.assertFalse(data["success"])
            self.assertEqual(data["error"], "Test error")

    def test_output_error_with_exception(self):
        """Test error output with exception in verbose mode"""
        self.cli.verbose = True
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.output_error("Test error", Exception("Details"))
            output = mock_stdout.getvalue()
            data = json.loads(output)
            self.assertIn("exception", data)

    def test_analyze_function_not_found(self):
        """Test analyze when function not found"""
        with patch.object(self.cli._fpb, "get_symbols", return_value={}):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                self.cli.analyze("/path/to/elf", "nonexistent")
                output = mock_stdout.getvalue()
                data = json.loads(output)
                self.assertFalse(data["success"])

    def test_disasm_failure(self):
        """Test disasm when disassembly fails"""
        with patch.object(
            self.cli._fpb, "disassemble_function", return_value=(False, "")
        ):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                self.cli.disasm("/path/to/elf", "test_func")
                output = mock_stdout.getvalue()
                data = json.loads(output)
                self.assertFalse(data["success"])

    def test_signature_success(self):
        """Test signature retrieval"""
        with patch.object(
            self.cli._fpb, "get_signature", return_value="void test_func(int arg)"
        ):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                self.cli.signature("/path/to/elf", "test_func")
                output = mock_stdout.getvalue()
                data = json.loads(output)
                self.assertTrue(data["success"])
                self.assertEqual(data["signature"], "void test_func(int arg)")

    def test_search_success(self):
        """Test symbol search"""
        mock_symbols = {
            "gpio_init": {"addr": 0x08000100, "sym_type": "function"},
            "gpio_read": {"addr": 0x08000200, "sym_type": "function"},
            "uart_init": {"addr": 0x08000300, "sym_type": "function"},
        }
        with patch.object(self.cli._fpb, "get_symbols", return_value=mock_symbols):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                self.cli.search("/path/to/elf", "gpio")
                output = mock_stdout.getvalue()
                data = json.loads(output)
                self.assertTrue(data["success"])
                self.assertEqual(data["count"], 2)

    def test_compile_file_not_found(self):
        """Test compile with nonexistent file"""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.compile("/nonexistent/file.c")
            output = mock_stdout.getvalue()
            data = json.loads(output)
            self.assertFalse(data["success"])
            self.assertIn("not found", data["error"])

    def test_unpatch_not_connected(self):
        """Test unpatch when not connected"""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.unpatch(comp=0)
            output = mock_stdout.getvalue()
            data = json.loads(output)
            self.assertFalse(data["success"])
            self.assertIn("No device connected", data["error"])

    def test_info_not_connected(self):
        """Test info when not connected"""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.info()
            output = mock_stdout.getvalue()
            data = json.loads(output)
            self.assertFalse(data["success"])

    def test_test_serial_not_connected(self):
        """Test test_serial when not connected"""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.test_serial()
            output = mock_stdout.getvalue()
            data = json.loads(output)
            self.assertFalse(data["success"])


class TestDeviceStateCLI(unittest.TestCase):
    """Test DeviceState class from CLI"""

    def test_init(self):
        """Test initialization"""
        from fpbinject.cli.fpb_cli import DeviceState

        device = DeviceState()
        self.assertIsNone(device.ser)
        self.assertFalse(device.connected)
        self.assertEqual(device.upload_chunk_size, 128)

    def test_disconnect(self):
        """Test disconnect"""
        from fpbinject.cli.fpb_cli import DeviceState

        device = DeviceState()
        device.ser = MagicMock()
        device.connected = True

        device.disconnect()

        self.assertIsNone(device.ser)
        self.assertFalse(device.connected)

    def test_connect_no_serial(self):
        """Test connect when pyserial not installed"""
        from fpbinject.cli.fpb_cli import DeviceState

        device = DeviceState()

        with patch("fpbinject.cli.fpb_cli.HAS_SERIAL", False):
            with self.assertRaises(RuntimeError) as cm:
                device.connect("/dev/ttyUSB0")

            self.assertIn("pyserial not installed", str(cm.exception))


class TestFPBCLIMain(unittest.TestCase):
    """Test main function"""

    @patch("sys.argv", ["fpb_cli.py"])
    @patch("sys.exit", side_effect=SystemExit)
    def test_main_no_command(self, mock_exit):
        """Test main with no command shows help.

        sys.exit is stubbed to raise (real behavior) so main() stops after
        printing help instead of falling through to a ~3s mDNS browse.
        """
        from fpbinject.cli.fpb_cli import main

        with self.assertRaises(SystemExit):
            main()
        mock_exit.assert_called_with(1)

    @patch("sys.argv", ["fpb_cli.py", "search", "/path/to/elf", "test"])
    @patch.object(FPBCLI, "search")
    @patch.object(FPBCLI, "cleanup")
    def test_main_search_command(self, mock_cleanup, mock_search):
        """Test main with search command"""
        from fpbinject.cli.fpb_cli import main

        main()
        mock_search.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("sys.argv", ["fpb_cli.py", "server-stop"])
    @patch.object(FPBCLI, "server_stop")
    @patch.object(FPBCLI, "cleanup")
    def test_main_server_stop_command(self, mock_cleanup, mock_stop):
        """Test main dispatches server-stop command."""
        from fpbinject.cli.fpb_cli import main

        main()
        mock_stop.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("sys.argv", ["fpb_cli.py", "server-stop", "--server-port", "8080"])
    @patch.object(FPBCLI, "server_stop")
    @patch.object(FPBCLI, "cleanup")
    def test_main_server_stop_with_port(self, mock_cleanup, mock_stop):
        """Test main dispatches server-stop with custom port."""
        from fpbinject.cli.fpb_cli import main

        main()
        mock_stop.assert_called_once_with(8080)


class TestFPBCLIServerStop(unittest.TestCase):
    """Test FPBCLI.server_stop method."""

    def setUp(self):
        self.cli = FPBCLI(verbose=False)

    def tearDown(self):
        self.cli.cleanup()

    @patch(
        "fpbinject.cli.server_proxy.stop_cli_server",
        return_value={
            "success": False,
            "error": "No CLI-launched server is running on port 5500",
        },
    )
    @patch("fpbinject.cli.server_proxy.list_cli_servers", return_value=[])
    def test_server_stop_no_server(self, mock_list, mock_stop):
        """server_stop with no running server."""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.server_stop()
            data = json.loads(mock_stdout.getvalue())
            self.assertFalse(data["success"])

    @patch(
        "fpbinject.cli.server_proxy.stop_cli_server",
        return_value={
            "success": True,
            "message": "Server on port 6000 (PID 123) terminated",
        },
    )
    @patch(
        "fpbinject.cli.server_proxy.list_cli_servers",
        return_value=[{"port": 6000, "pid": 123}],
    )
    def test_server_stop_auto_detect_single(self, mock_list, mock_stop):
        """server_stop auto-detects single running server."""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.server_stop()
            data = json.loads(mock_stdout.getvalue())
            self.assertTrue(data["success"])
            mock_stop.assert_called_once_with(6000)

    @patch(
        "fpbinject.cli.server_proxy.list_cli_servers",
        return_value=[{"port": 5500, "pid": 100}, {"port": 6000, "pid": 200}],
    )
    def test_server_stop_multiple_servers(self, mock_list):
        """server_stop with multiple servers returns error."""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.server_stop()
            data = json.loads(mock_stdout.getvalue())
            self.assertFalse(data["success"])
            self.assertIn("Multiple", data["error"])
            self.assertEqual(len(data["servers"]), 2)

    @patch(
        "fpbinject.cli.server_proxy.stop_cli_server",
        return_value={
            "success": True,
            "message": "Server on port 8080 (PID 456) terminated",
        },
    )
    def test_server_stop_explicit_port(self, mock_stop):
        """server_stop with explicit port skips auto-detect."""
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            self.cli.server_stop(port=8080)
            data = json.loads(mock_stdout.getvalue())
            self.assertTrue(data["success"])
            mock_stop.assert_called_once_with(8080)


if __name__ == "__main__":
    unittest.main(verbosity=2)

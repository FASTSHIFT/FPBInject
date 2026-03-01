"""Tests for FPBInject MCP Server (fpb_mcp_server.py)"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCaptureCliOutput(unittest.TestCase):
    """Test _capture_cli_output helper"""

    def test_captures_json_output(self):
        from fpb_mcp_server import _capture_cli_output

        def fake_func():
            print(json.dumps({"success": True, "data": "test"}))

        result = _capture_cli_output(fake_func)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], "test")

    def test_empty_output(self):
        from fpb_mcp_server import _capture_cli_output

        def fake_func():
            pass

        result = _capture_cli_output(fake_func)
        self.assertFalse(result["success"])
        self.assertIn("No output", result["error"])

    def test_passes_args(self):
        from fpb_mcp_server import _capture_cli_output

        def fake_func(a, b, key=None):
            print(json.dumps({"a": a, "b": b, "key": key}))

        result = _capture_cli_output(fake_func, 1, 2, key="val")
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 2)
        self.assertEqual(result["key"], "val")

    def test_invalid_json_output(self):
        from fpb_mcp_server import _capture_cli_output

        def fake_func():
            print("not json")

        with self.assertRaises(json.JSONDecodeError):
            _capture_cli_output(fake_func)


class TestGetCli(unittest.TestCase):
    """Test _get_cli singleton management"""

    def setUp(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None

    def tearDown(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None

    @patch("fpb_mcp_server.FPBCLI")
    def test_creates_new_instance(self, mock_cli_cls):
        from fpb_mcp_server import _get_cli

        mock_cli_cls.return_value = MagicMock()
        cli = _get_cli()
        mock_cli_cls.assert_called_once()
        self.assertIsNotNone(cli)

    @patch("fpb_mcp_server.FPBCLI")
    def test_reuses_instance(self, mock_cli_cls):
        from fpb_mcp_server import _get_cli

        mock_cli_cls.return_value = MagicMock()
        cli1 = _get_cli()
        cli2 = _get_cli()
        self.assertIs(cli1, cli2)
        mock_cli_cls.assert_called_once()

    @patch("fpb_mcp_server.FPBCLI")
    def test_updates_elf_path(self, mock_cli_cls):
        from fpb_mcp_server import _get_cli

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        _get_cli()
        _get_cli(elf_path="/new/path.elf")
        self.assertEqual(mock_instance._device_state.elf_path, "/new/path.elf")

    @patch("fpb_mcp_server.FPBCLI")
    def test_updates_compile_commands(self, mock_cli_cls):
        from fpb_mcp_server import _get_cli

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        _get_cli()
        _get_cli(compile_commands="/new/cc.json")
        self.assertEqual(
            mock_instance._device_state.compile_commands_path, "/new/cc.json"
        )

    @patch("fpb_mcp_server.FPBCLI")
    def test_connects_port_on_existing(self, mock_cli_cls):
        from fpb_mcp_server import _get_cli

        mock_instance = MagicMock()
        mock_instance._device_state.connected = False
        mock_cli_cls.return_value = mock_instance
        _get_cli()
        _get_cli(port="/dev/ttyACM0", baudrate=9600)
        mock_instance._device_state.connect.assert_called_with("/dev/ttyACM0", 9600)


class TestSerialLog(unittest.TestCase):
    """Test _append_serial_log and ring buffer"""

    def setUp(self):
        import fpb_mcp_server

        fpb_mcp_server._serial_log.clear()

    def test_append_entry(self):
        from fpb_mcp_server import _append_serial_log, _serial_log

        _append_serial_log("test line")
        self.assertEqual(len(_serial_log), 1)
        self.assertEqual(_serial_log[0]["data"], "test line")
        self.assertIn("time", _serial_log[0])

    def test_ignores_empty(self):
        from fpb_mcp_server import _append_serial_log, _serial_log

        _append_serial_log("")
        _append_serial_log(None)
        self.assertEqual(len(_serial_log), 0)

    def test_ring_buffer_limit(self):
        from fpb_mcp_server import _append_serial_log, _serial_log, _SERIAL_LOG_MAX

        for i in range(_SERIAL_LOG_MAX + 100):
            _append_serial_log(f"line {i}")
        self.assertLessEqual(len(_serial_log), _SERIAL_LOG_MAX)
        # Most recent entry should be the last one added
        self.assertEqual(_serial_log[-1]["data"], f"line {_SERIAL_LOG_MAX + 99}")


class TestOfflineTools(unittest.TestCase):
    """Test offline MCP tools (analyze, disasm, search, etc.)"""

    def setUp(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None

    def tearDown(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None

    @patch("fpb_mcp_server.FPBCLI")
    def test_analyze(self, mock_cli_cls):
        from fpb_mcp_server import analyze

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.analyze = MagicMock(
            side_effect=lambda *a: print(
                json.dumps(
                    {
                        "success": True,
                        "analysis": {"func_name": "foo", "addr": "0x1000"},
                    }
                )
            )
        )
        result = analyze("test.elf", "foo")
        self.assertTrue(result["success"])
        mock_instance.analyze.assert_called_once_with("test.elf", "foo")

    @patch("fpb_mcp_server.FPBCLI")
    def test_disasm(self, mock_cli_cls):
        from fpb_mcp_server import disasm

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.disasm = MagicMock(
            side_effect=lambda *a: print(
                json.dumps({"success": True, "disasm": "push {r7}"})
            )
        )
        result = disasm("test.elf", "foo")
        self.assertTrue(result["success"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_decompile(self, mock_cli_cls):
        from fpb_mcp_server import decompile

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.decompile = MagicMock(
            side_effect=lambda *a: print(
                json.dumps({"success": True, "decompiled": "void foo() {}"})
            )
        )
        result = decompile("test.elf", "foo")
        self.assertTrue(result["success"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_signature(self, mock_cli_cls):
        from fpb_mcp_server import signature

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.signature = MagicMock(
            side_effect=lambda *a: print(
                json.dumps({"success": True, "signature": "void foo(int)"})
            )
        )
        result = signature("test.elf", "foo")
        self.assertTrue(result["success"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_search(self, mock_cli_cls):
        from fpb_mcp_server import search

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.search = MagicMock(
            side_effect=lambda *a: print(
                json.dumps(
                    {
                        "success": True,
                        "count": 2,
                        "symbols": [
                            {"name": "foo", "addr": "0x1000"},
                            {"name": "foobar", "addr": "0x2000"},
                        ],
                    }
                )
            )
        )
        result = search("test.elf", "foo")
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)

    @patch("fpb_mcp_server.FPBCLI")
    def test_compile_patch(self, mock_cli_cls):
        from fpb_mcp_server import compile_patch

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.compile = MagicMock(
            side_effect=lambda *a, **kw: print(
                json.dumps({"success": True, "binary_size": 64})
            )
        )
        result = compile_patch("patch.c", "test.elf", "cc.json")
        self.assertTrue(result["success"])
        self.assertEqual(result["binary_size"], 64)


class TestOnlineTools(unittest.TestCase):
    """Test online MCP tools (connect, disconnect, info, inject, unpatch)"""

    def setUp(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None

    def tearDown(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None

    @patch("fpb_mcp_server.FPBCLI")
    def test_connect_success(self, mock_cli_cls):
        from fpb_mcp_server import connect

        mock_instance = MagicMock()
        mock_instance._device_state.connected = True
        mock_cli_cls.return_value = mock_instance
        result = connect("/dev/ttyACM0", 115200)
        self.assertTrue(result["success"])
        self.assertEqual(result["port"], "/dev/ttyACM0")

    @patch("fpb_mcp_server.FPBCLI")
    def test_connect_failure(self, mock_cli_cls):
        from fpb_mcp_server import connect

        mock_cli_cls.side_effect = Exception("Port not found")
        result = connect("/dev/ttyXXX")
        self.assertFalse(result["success"])
        self.assertIn("Port not found", result["error"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_disconnect(self, mock_cli_cls):
        import fpb_mcp_server
        from fpb_mcp_server import disconnect

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        fpb_mcp_server._cli_instance = mock_instance
        result = disconnect()
        self.assertTrue(result["success"])
        mock_instance.cleanup.assert_called_once()
        self.assertIsNone(fpb_mcp_server._cli_instance)

    def test_disconnect_no_instance(self):
        from fpb_mcp_server import disconnect

        result = disconnect()
        self.assertTrue(result["success"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_info(self, mock_cli_cls):
        from fpb_mcp_server import info

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.info = MagicMock(
            side_effect=lambda: print(
                json.dumps({"success": True, "info": {"total_slots": 6}})
            )
        )
        result = info()
        self.assertTrue(result["success"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_inject(self, mock_cli_cls):
        from fpb_mcp_server import inject

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.inject = MagicMock(
            side_effect=lambda *a, **kw: print(
                json.dumps({"success": True, "result": {"slot": 0}})
            )
        )
        result = inject("foo", "patch.c", "test.elf", "cc.json")
        self.assertTrue(result["success"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_unpatch(self, mock_cli_cls):
        from fpb_mcp_server import unpatch

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.unpatch = MagicMock(
            side_effect=lambda *a: print(
                json.dumps({"success": True, "message": "Cleared"})
            )
        )
        result = unpatch(comp=0)
        self.assertTrue(result["success"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_unpatch_all(self, mock_cli_cls):
        from fpb_mcp_server import unpatch

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.unpatch = MagicMock(
            side_effect=lambda *a: print(
                json.dumps({"success": True, "message": "All cleared"})
            )
        )
        result = unpatch(all_patches=True)
        self.assertTrue(result["success"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_test_serial(self, mock_cli_cls):
        from fpb_mcp_server import test_serial

        mock_instance = MagicMock()
        mock_cli_cls.return_value = mock_instance
        mock_instance.test_serial = MagicMock(
            side_effect=lambda *a: print(
                json.dumps({"success": True, "max_working_size": 512})
            )
        )
        result = test_serial()
        self.assertTrue(result["success"])


class TestSerialReadTool(unittest.TestCase):
    """Test serial_read MCP tool"""

    def setUp(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None
        fpb_mcp_server._serial_log.clear()

    def tearDown(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None
        fpb_mcp_server._serial_log.clear()

    @patch("fpb_mcp_server.FPBCLI")
    def test_not_connected(self, mock_cli_cls):
        from fpb_mcp_server import serial_read

        mock_instance = MagicMock()
        mock_instance._device_state.ser = None
        mock_instance._device_state.connected = False
        mock_cli_cls.return_value = mock_instance
        result = serial_read()
        self.assertFalse(result["success"])
        self.assertIn("Not connected", result["error"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_reads_data(self, mock_cli_cls):
        from fpb_mcp_server import serial_read

        mock_instance = MagicMock()
        mock_ser = MagicMock()
        mock_instance._device_state.ser = mock_ser
        mock_instance._device_state.connected = True
        # in_waiting: first call returns data size, then 0 forever
        call_count = [0]

        def in_waiting_side_effect():
            call_count[0] += 1
            return 6 if call_count[0] == 1 else 0

        type(mock_ser).in_waiting = PropertyMock(side_effect=in_waiting_side_effect)
        mock_ser.read.return_value = b"hello\n"
        mock_cli_cls.return_value = mock_instance
        result = serial_read(timeout=0.3)
        self.assertTrue(result["success"])
        self.assertIn("hello", result["new_data"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_returns_log_history(self, mock_cli_cls):
        from fpb_mcp_server import serial_read, _append_serial_log

        mock_instance = MagicMock()
        mock_ser = MagicMock()
        mock_instance._device_state.ser = mock_ser
        mock_instance._device_state.connected = True
        type(mock_ser).in_waiting = PropertyMock(return_value=0)
        mock_cli_cls.return_value = mock_instance
        # Pre-populate log
        _append_serial_log("old line 1")
        _append_serial_log("old line 2")
        result = serial_read(timeout=0.2)
        self.assertTrue(result["success"])
        self.assertEqual(result["log_count"], 2)
        self.assertIn("old line 1", result["log"])


class TestSerialSendTool(unittest.TestCase):
    """Test serial_send MCP tool"""

    def setUp(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None
        fpb_mcp_server._serial_log.clear()

    def tearDown(self):
        import fpb_mcp_server

        fpb_mcp_server._cli_instance = None
        fpb_mcp_server._serial_log.clear()

    @patch("fpb_mcp_server.FPBCLI")
    def test_not_connected(self, mock_cli_cls):
        from fpb_mcp_server import serial_send

        mock_instance = MagicMock()
        mock_instance._device_state.ser = None
        mock_instance._device_state.connected = False
        mock_cli_cls.return_value = mock_instance
        result = serial_send("test")
        self.assertFalse(result["success"])
        self.assertIn("Not connected", result["error"])

    @patch("fpb_mcp_server.FPBCLI")
    def test_sends_data(self, mock_cli_cls):
        from fpb_mcp_server import serial_send

        mock_instance = MagicMock()
        mock_ser = MagicMock()
        mock_instance._device_state.ser = mock_ser
        mock_instance._device_state.connected = True
        mock_instance._fpb = MagicMock()
        mock_instance._fpb._protocol._in_fl_mode = False
        call_count = [0]

        def in_waiting_side_effect():
            call_count[0] += 1
            return 5 if call_count[0] == 1 else 0

        type(mock_ser).in_waiting = PropertyMock(side_effect=in_waiting_side_effect)
        mock_ser.read.return_value = b"OK\r\n"
        mock_cli_cls.return_value = mock_instance
        result = serial_send("help", timeout=0.2)
        self.assertTrue(result["success"])
        self.assertEqual(result["sent"], "help")
        mock_ser.write.assert_called_once_with(b"help\n")

    @patch("fpb_mcp_server.FPBCLI")
    def test_send_no_read(self, mock_cli_cls):
        from fpb_mcp_server import serial_send

        mock_instance = MagicMock()
        mock_ser = MagicMock()
        mock_instance._device_state.ser = mock_ser
        mock_instance._device_state.connected = True
        mock_instance._fpb = MagicMock()
        mock_instance._fpb._protocol._in_fl_mode = False
        mock_cli_cls.return_value = mock_instance
        result = serial_send("test", read_response=False, timeout=0.2)
        self.assertTrue(result["success"])
        self.assertEqual(result["response"], "")

    @patch("fpb_mcp_server.FPBCLI")
    def test_send_exception(self, mock_cli_cls):
        from fpb_mcp_server import serial_send

        mock_instance = MagicMock()
        mock_ser = MagicMock()
        mock_ser.write.side_effect = OSError("Port closed")
        mock_instance._device_state.ser = mock_ser
        mock_instance._device_state.connected = True
        mock_instance._fpb = MagicMock()
        mock_instance._fpb._protocol._in_fl_mode = False
        mock_cli_cls.return_value = mock_instance
        result = serial_send("test")
        self.assertFalse(result["success"])
        self.assertIn("Port closed", result["error"])


class TestMcpServerModule(unittest.TestCase):
    """Test module-level setup"""

    def test_mcp_instance_exists(self):
        from fpb_mcp_server import mcp

        self.assertIsNotNone(mcp)

    def test_server_dir_in_path(self):
        from fpb_mcp_server import _SERVER_DIR

        self.assertIn(str(_SERVER_DIR), sys.path)


if __name__ == "__main__":
    unittest.main()

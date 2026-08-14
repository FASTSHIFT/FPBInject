#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main module tests
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fpbinject.main as main  # noqa: E402
from fpbinject.core.state import state, DeviceState  # noqa: E402


def _make_server_args(**overrides):
    """Build a realistic server args Namespace for main() tests.

    Constructs the namespace directly (rather than calling parse_args, which
    the caller often patches) with concrete server defaults plus every
    schema-driven connection flag set to None. This avoids brittle Mock()
    objects whose attributes read back as truthy Mocks and would pollute
    connection_overrides()."""
    import argparse

    from fpbinject.core.arg_schema import iter_cli_items

    defaults = dict(
        host="0.0.0.0",
        http_port=5500,
        debug=False,
        skip_port_check=False,
        no_browser=True,
        no_auth=False,
        no_mdns=True,
        config=None,
    )
    # Every CLI-exposed connection/transfer flag defaults to None (unset).
    for item in iter_cli_items():
        defaults.setdefault(item.key, None)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestCreateApp(unittest.TestCase):
    """create_app function tests"""

    def test_create_app_returns_flask_app(self):
        """Test that create_app returns a Flask app"""
        app = main.create_app()
        self.assertIsNotNone(app)
        self.assertEqual(app.name, "fpbinject")

    def test_create_app_has_cors(self):
        """Test that CORS is enabled"""
        app = main.create_app()
        # CORS adds after_request handler
        self.assertIsNotNone(app)

    def test_create_app_has_routes(self):
        """Test that routes are registered"""
        app = main.create_app()
        # Check that some routes exist
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        self.assertIn("/", rules)


class TestCheckPortAvailable(unittest.TestCase):
    """check_port_available function tests"""

    @patch("fpbinject.main.socket.socket")
    def test_port_available(self, mock_socket_class):
        """Test port is available"""
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 1  # Non-zero means port is free
        mock_socket_class.return_value = mock_sock

        result = main.check_port_available("127.0.0.1", 5500)

        self.assertTrue(result)
        mock_sock.close.assert_called_once()

    @patch("fpbinject.main.socket.socket")
    def test_port_in_use(self, mock_socket_class):
        """Test port is in use"""
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0  # Zero means port is in use
        mock_socket_class.return_value = mock_sock

        result = main.check_port_available("127.0.0.1", 5500)

        self.assertFalse(result)
        mock_sock.close.assert_called_once()

    @patch("fpbinject.main.socket.socket")
    def test_port_check_exception(self, mock_socket_class):
        """Test port check with exception"""
        mock_sock = Mock()
        mock_sock.connect_ex.side_effect = Exception("Network error")
        mock_socket_class.return_value = mock_sock

        result = main.check_port_available("127.0.0.1", 5500)

        self.assertTrue(result)  # Exception means port is likely available


class TestParseArgs(unittest.TestCase):
    """parse_args function tests"""

    def test_default_args(self):
        """Test default arguments"""
        with patch("sys.argv", ["main.py"]):
            args = main.parse_args()

        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.http_port, 5500)
        self.assertIsNone(args.port)
        self.assertFalse(args.debug)

    def test_custom_port(self):
        """Test custom HTTP port argument"""
        with patch("sys.argv", ["main.py", "--http-port", "8080"]):
            args = main.parse_args()

        self.assertEqual(args.http_port, 8080)

    def test_custom_host(self):
        """Test custom host argument"""
        with patch("sys.argv", ["main.py", "--host", "localhost"]):
            args = main.parse_args()

        self.assertEqual(args.host, "localhost")

    def test_debug_mode(self):
        """Test debug mode argument"""
        with patch("sys.argv", ["main.py", "--debug"]):
            args = main.parse_args()

        self.assertTrue(args.debug)

    def test_no_browser_default_false(self):
        """Test --no-browser defaults to False"""
        with patch("sys.argv", ["main.py"]):
            args = main.parse_args()

        self.assertFalse(args.no_browser)

    def test_no_browser_flag(self):
        """Test --no-browser flag sets no_browser=True"""
        with patch("sys.argv", ["main.py", "--no-browser"]):
            args = main.parse_args()

        self.assertTrue(args.no_browser)

    def test_no_browser_with_other_args(self):
        """Test --no-browser can combine with other args"""
        with patch("sys.argv", ["main.py", "--http-port", "9090", "--no-browser"]):
            args = main.parse_args()

        self.assertEqual(args.http_port, 9090)
        self.assertTrue(args.no_browser)

    def test_http_port_default(self):
        """--http-port defaults to 5500"""
        with patch("sys.argv", ["main.py"]):
            args = main.parse_args()

        self.assertEqual(args.http_port, 5500)

    def test_http_port_custom(self):
        """--http-port sets the HTTP listen port"""
        with patch("sys.argv", ["main.py", "--http-port", "8080"]):
            args = main.parse_args()

        self.assertEqual(args.http_port, 8080)

    def test_serial_port_flag(self):
        """--port now selects the serial device (schema-driven)"""
        with patch("sys.argv", ["main.py", "--port", "/dev/ttyACM0"]):
            args = main.parse_args()

        self.assertEqual(args.port, "/dev/ttyACM0")
        # HTTP port stays at its default, independent of the serial port.
        self.assertEqual(args.http_port, 5500)

    def test_serial_connection_flags_default_none(self):
        """Unset connection flags default to None (override sentinel)"""
        with patch("sys.argv", ["main.py"]):
            args = main.parse_args()

        self.assertIsNone(args.port)
        self.assertIsNone(args.baudrate)
        self.assertIsNone(args.auto_connect)

    def test_serial_flags_full_set(self):
        """Server exposes the full connection/transfer flag set"""
        argv = [
            "main.py",
            "--port",
            "/dev/ttyUSB0",
            "--baudrate",
            "9600",
            "--parity",
            "even",
            "--data-bits",
            "7",
            "--serial-tx-fragment-size",
            "64",
        ]
        with patch("sys.argv", argv):
            args = main.parse_args()

        self.assertEqual(args.port, "/dev/ttyUSB0")
        self.assertEqual(args.baudrate, 9600)
        self.assertEqual(args.parity, "even")
        self.assertEqual(args.data_bits, 7)
        self.assertEqual(args.serial_tx_fragment_size, 64)


class TestInvocationCommands(unittest.TestCase):
    """invocation_commands function tests"""

    def test_source_run_main_py(self):
        """Running from source (./main.py) yields source-style hints."""
        with patch("sys.argv", ["main.py"]):
            server_cmd, cli_cmd = main.invocation_commands()
        self.assertEqual(server_cmd, "./main.py")
        self.assertEqual(cli_cmd, "fpb_cli.py")

    def test_source_run_with_full_path(self):
        """Only the basename of argv[0] is used, not the full path."""
        with patch("sys.argv", ["/home/user/Tools/WebServer/main.py"]):
            server_cmd, cli_cmd = main.invocation_commands()
        self.assertEqual(server_cmd, "./main.py")
        self.assertEqual(cli_cmd, "fpb_cli.py")

    def test_installed_console_script(self):
        """Installed console script yields packaged command names."""
        with patch("sys.argv", ["fpbinject-server"]):
            server_cmd, cli_cmd = main.invocation_commands()
        self.assertEqual(server_cmd, "fpbinject-server")
        self.assertEqual(cli_cmd, "fpbinject")

    def test_installed_console_script_full_path(self):
        """Installed script resolved via full path keeps its basename."""
        with patch("sys.argv", ["/usr/local/bin/fpbinject-server"]):
            server_cmd, cli_cmd = main.invocation_commands()
        self.assertEqual(server_cmd, "fpbinject-server")
        self.assertEqual(cli_cmd, "fpbinject")

    def test_empty_argv_falls_back_to_default(self):
        """Empty argv[0] falls back to the packaged server command name."""
        with patch("sys.argv", [""]):
            server_cmd, cli_cmd = main.invocation_commands()
        self.assertEqual(server_cmd, "fpbinject-server")
        self.assertEqual(cli_cmd, "fpbinject")


class TestCheckToolchain(unittest.TestCase):
    """check_toolchain function tests"""

    @patch("fpbinject.main.shutil.which", return_value="/usr/bin/gdb-multiarch")
    def test_gdb_found(self, mock_which):
        """Returns True when gdb-multiarch is found."""
        result = main.check_toolchain()
        self.assertTrue(result)

    @patch("fpbinject.main.shutil.which", return_value=None)
    @patch("sys.stdin")
    def test_gdb_not_found_non_interactive(self, mock_stdin, mock_which):
        """Non-interactive mode continues without gdb."""
        mock_stdin.isatty.return_value = False
        result = main.check_toolchain()
        self.assertTrue(result)

    @patch("fpbinject.main.shutil.which", return_value=None)
    @patch("sys.stdin")
    @patch("builtins.input", return_value="")
    def test_gdb_not_found_user_continues(self, mock_input, mock_stdin, mock_which):
        """User presses Enter to continue without gdb."""
        mock_stdin.isatty.return_value = True
        result = main.check_toolchain()
        self.assertTrue(result)

    @patch("fpbinject.main.shutil.which", return_value=None)
    @patch("sys.stdin")
    @patch("builtins.input", return_value="n")
    def test_gdb_not_found_user_says_no(self, mock_input, mock_stdin, mock_which):
        """User says 'n' to continue without gdb."""
        mock_stdin.isatty.return_value = True
        result = main.check_toolchain()
        self.assertTrue(result)

    @patch("fpbinject.main.shutil.which", return_value=None)
    @patch("sys.stdin")
    @patch("builtins.input", return_value="q")
    def test_gdb_not_found_user_quits(self, mock_input, mock_stdin, mock_which):
        """User says 'q' to quit."""
        mock_stdin.isatty.return_value = True
        with self.assertRaises(SystemExit) as cm:
            main.check_toolchain()
        self.assertEqual(cm.exception.code, 0)

    @patch("fpbinject.main.shutil.which", return_value=None)
    @patch("sys.stdin")
    @patch("builtins.input", side_effect=EOFError)
    def test_gdb_not_found_eof(self, mock_input, mock_stdin, mock_which):
        """EOFError on input returns True."""
        mock_stdin.isatty.return_value = True
        result = main.check_toolchain()
        self.assertTrue(result)

    @patch("fpbinject.main.shutil.which", return_value=None)
    @patch("sys.stdin")
    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_gdb_not_found_keyboard_interrupt(self, mock_input, mock_stdin, mock_which):
        """KeyboardInterrupt on input returns True."""
        mock_stdin.isatty.return_value = True
        result = main.check_toolchain()
        self.assertTrue(result)


class TestRestoreState(unittest.TestCase):
    """restore_state function tests"""

    def setUp(self):
        """Set up test environment"""
        self.original_device = state.device
        state.device = DeviceState()

    def tearDown(self):
        """Clean up test environment"""
        state.device = self.original_device

    def test_restore_state_no_auto_connect(self):
        """Test restore_state when auto_connect is disabled"""
        state.device.auto_connect = False
        state.device.port = "/dev/ttyUSB0"

        # Should not attempt to connect
        main.restore_state()

        self.assertIsNone(state.device.ser)

    def test_restore_state_no_port(self):
        """Test restore_state when no port is set"""
        state.device.auto_connect = True
        state.device.port = ""

        main.restore_state()

        self.assertIsNone(state.device.ser)

    @patch("fpbinject.main.restore_file_watcher")
    def test_restore_state_with_file_watcher(self, mock_restore):
        """Test restore_state restores file watcher"""
        state.device.auto_compile = True
        state.device.watch_dirs = ["/tmp/test"]
        state.device.auto_connect = False

        main.restore_state()

        mock_restore.assert_called_once()

    @patch("fpbinject.main.start_worker")
    @patch("fpbinject.main.serial_open")
    def test_restore_state_auto_connect_success(self, mock_serial, mock_worker):
        """Test restore_state with successful auto-connect"""
        state.device.auto_connect = True
        state.device.port = "/dev/ttyUSB0"
        state.device.baudrate = 115200
        state.device.timeout = 1

        mock_ser = Mock()
        mock_serial.return_value = (mock_ser, None)

        main.restore_state()

        mock_worker.assert_called_once()
        mock_serial.assert_called_once()
        self.assertEqual(state.device.ser, mock_ser)

    @patch("fpbinject.main.start_worker")
    @patch("fpbinject.main.serial_open")
    def test_restore_state_auto_connect_failure(self, mock_serial, mock_worker):
        """Test restore_state with failed auto-connect"""
        state.device.auto_connect = True
        state.device.port = "/dev/ttyUSB0"

        mock_serial.return_value = (None, "Port not found")

        main.restore_state()

        mock_worker.assert_called_once()
        self.assertIsNone(state.device.ser)

    @patch(
        "fpbinject.services.file_watcher_manager.start_elf_watcher", return_value=True
    )
    def test_restore_state_elf_watcher_success(self, mock_elf_watcher):
        """Test restore_state restores ELF watcher successfully"""
        state.device.auto_connect = False
        state.device.elf_path = "/tmp/test.elf"

        main.restore_state()

        mock_elf_watcher.assert_called_once_with("/tmp/test.elf")

    @patch(
        "fpbinject.services.file_watcher_manager.start_elf_watcher", return_value=False
    )
    def test_restore_state_elf_watcher_failure(self, mock_elf_watcher):
        """Test restore_state handles ELF watcher failure"""
        state.device.auto_connect = False
        state.device.elf_path = "/tmp/test.elf"

        main.restore_state()

        mock_elf_watcher.assert_called_once_with("/tmp/test.elf")

    @patch("fpbinject.services.log_recorder.log_recorder")
    def test_restore_state_log_recorder_success(self, mock_recorder):
        """Test restore_state restores log recorder"""
        state.device.auto_connect = False
        state.device.log_file_enabled = True
        state.device.log_file_path = "/tmp/test.log"
        mock_recorder.start.return_value = (True, None)

        main.restore_state()

        mock_recorder.start.assert_called_once_with(
            "/tmp/test.log",
            append=state.device.log_file_append,
            timestamp=state.device.log_file_timestamp,
        )

    @patch("fpbinject.services.log_recorder.log_recorder")
    def test_restore_state_log_recorder_failure(self, mock_recorder):
        """Test restore_state handles log recorder failure"""
        state.device.auto_connect = False
        state.device.log_file_enabled = True
        state.device.log_file_path = "/tmp/test.log"
        mock_recorder.start.return_value = (False, "Permission denied")

        main.restore_state()

        mock_recorder.start.assert_called_once()
        self.assertFalse(state.device.log_file_enabled)

    @patch("fpbinject.main.os.path.exists", return_value=True)
    @patch("fpbinject.core.gdb_manager.start_gdb_async")
    def test_restore_state_gdb_auto_start(self, mock_gdb, mock_exists):
        """Test restore_state auto-starts GDB when ELF exists"""
        state.device.auto_connect = False
        state.device.elf_path = "/tmp/test.elf"

        main.restore_state()

        mock_gdb.assert_called_once()


class TestMain(unittest.TestCase):
    """main function tests"""

    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available")
    @patch("fpbinject.main.parse_args")
    def test_main_port_in_use(self, mock_args, mock_check, mock_restore, mock_create):
        """Test main exits when port is in use"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=False,
            no_browser=True,
        )
        mock_check.return_value = False

        with self.assertRaises(SystemExit) as cm:
            main.main()

        self.assertEqual(cm.exception.code, 1)
        mock_create.assert_not_called()

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available")
    @patch("fpbinject.main.parse_args")
    def test_main_starts_server(
        self, mock_args, mock_check, mock_restore, mock_create, mock_timer_cls
    ):
        """Test main starts server successfully"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=False,
            no_browser=True,
        )
        mock_check.return_value = True

        mock_app = Mock()
        mock_create.return_value = mock_app

        main.main()

        mock_create.assert_called_once()
        mock_restore.assert_called_once()
        mock_app.run.assert_called_once_with(
            host="0.0.0.0", port=5500, debug=False, threaded=True
        )

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available")
    @patch("fpbinject.main.parse_args")
    def test_main_skip_port_check(
        self, mock_args, mock_check, mock_restore, mock_create, mock_timer_cls
    ):
        """Test main skips port check when skip_port_check is True"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=True,
            no_browser=True,
        )
        mock_check.return_value = False  # Port in use, but should be ignored

        mock_app = Mock()
        mock_create.return_value = mock_app

        main.main()

        # Port check should not be called when skip_port_check is True
        mock_check.assert_not_called()
        mock_create.assert_called_once()
        mock_restore.assert_called_once()
        mock_app.run.assert_called_once()

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    def test_main_applies_serial_port_override(
        self, mock_args, mock_check, mock_restore, mock_create, mock_timer_cls
    ):
        """A --port serial flag overrides config and enables auto-connect."""
        self.original_device = state.device
        state.device = DeviceState()
        try:
            mock_args.return_value = _make_server_args(
                http_port=5500,
                skip_port_check=True,
                no_browser=True,
                port="/dev/ttyACM0",
                baudrate=57600,
            )
            mock_create.return_value = Mock()

            main.main()

            self.assertEqual(state.device.port, "/dev/ttyACM0")
            self.assertEqual(state.device.baudrate, 57600)
            # Passing --port implies connect-on-start.
            self.assertTrue(state.device.auto_connect)
        finally:
            state.device = self.original_device

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main._discover_existing_config", return_value=None)
    @patch("fpbinject.main.parse_args")
    def test_main_serial_flags_skip_config_prompt(
        self,
        mock_args,
        mock_discover,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """Serial flags present -> no interactive config prompt (in-memory)."""
        self.original_device = state.device
        state.device = DeviceState()
        try:
            mock_args.return_value = _make_server_args(
                http_port=5500,
                skip_port_check=True,
                no_browser=True,
                port="/dev/ttyACM1",
                baudrate=921600,
            )
            mock_create.return_value = Mock()

            # Interactive TTY, but input() must never be called because the
            # user opted out of JSON config by passing connection flags.
            with patch("sys.stdin.isatty", return_value=True), patch(
                "builtins.input",
                side_effect=AssertionError("config prompt must be skipped"),
            ):
                main.main()

            # Ran with in-memory defaults (no config persisted) + overrides.
            self.assertIsNone(state.config_path)
            self.assertEqual(state.device.port, "/dev/ttyACM1")
            self.assertEqual(state.device.baudrate, 921600)
        finally:
            state.device = self.original_device

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    def test_main_no_serial_flags_leaves_config(
        self, mock_args, mock_check, mock_restore, mock_create, mock_timer_cls
    ):
        """Without serial flags, device config is left untouched."""
        self.original_device = state.device
        state.device = DeviceState()
        state.device.port = "/dev/preset"
        try:
            mock_args.return_value = _make_server_args(
                http_port=5500,
                skip_port_check=True,
                no_browser=True,
            )
            mock_create.return_value = Mock()

            main.main()

            # No --port flag -> config value preserved, no forced auto-connect.
            self.assertEqual(state.device.port, "/dev/preset")
            self.assertFalse(state.device.auto_connect)
        finally:
            state.device = self.original_device


class TestAutoOpenBrowser(unittest.TestCase):
    """Tests for auto-open browser and startup banner"""

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.webbrowser.open")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    def test_browser_opens_by_default(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_wb_open,
        mock_timer_cls,
    ):
        """Browser should auto-open when --no-browser is not set"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=True,
            no_browser=False,
        )
        mock_create.return_value = Mock()
        mock_timer = Mock()
        mock_timer_cls.return_value = mock_timer

        main.main()

        mock_timer_cls.assert_called_once_with(
            1.0, mock_wb_open, args=["http://127.0.0.1:5500"]
        )
        mock_timer.start.assert_called_once()

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.webbrowser.open")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    def test_no_browser_skips_open(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_wb_open,
        mock_timer_cls,
    ):
        """Browser should NOT open when --no-browser is set"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        main.main()

        mock_timer_cls.assert_not_called()

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.webbrowser.open")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    def test_browser_url_uses_custom_port(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_wb_open,
        mock_timer_cls,
    ):
        """Browser URL should use the custom port"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=9090,
            skip_port_check=True,
            no_browser=False,
        )
        mock_create.return_value = Mock()
        mock_timer = Mock()
        mock_timer_cls.return_value = mock_timer

        main.main()

        mock_timer_cls.assert_called_once_with(
            1.0, mock_wb_open, args=["http://127.0.0.1:9090"]
        )

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    @patch("logging.basicConfig")
    def test_startup_banner_logged(
        self,
        mock_basic,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """Startup banner should contain server URL"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        with patch("builtins.print") as mock_print:
            main.main()

        printed = "\n".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("FPBInject Web Server Started", printed)
        self.assertIn("http://127.0.0.1:5500", printed)

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    @patch("logging.basicConfig")
    def test_startup_banner_with_custom_port(
        self,
        mock_basic,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """Startup banner should show custom port"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=8080,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        with patch("builtins.print") as mock_print:
            main.main()

        printed = "\n".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("http://127.0.0.1:8080", printed)

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    def test_startup_banner_shows_lan_ip(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """Startup banner should show LAN network URL"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        mock_sock = Mock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 0)

        with patch("builtins.print") as mock_print, patch(
            "fpbinject.main.socket.socket", return_value=mock_sock
        ):
            main.main()

        printed = "\n".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("http://192.168.1.100:5500", printed)
        self.assertIn("Network", printed)

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    def test_startup_banner_lan_ip_unavailable(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """Startup banner shows 'unavailable' when LAN IP detection fails"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        mock_sock = Mock()
        mock_sock.connect.side_effect = OSError("Network unreachable")

        with patch("builtins.print") as mock_print, patch(
            "fpbinject.main.socket.socket", return_value=mock_sock
        ):
            main.main()

        printed = "\n".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("unavailable", printed)

    @patch("fpbinject.main.threading.Timer")
    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=True)
    @patch("fpbinject.main.parse_args")
    def test_startup_lan_ip_socket_closed(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """LAN IP detection should close the socket after use"""
        mock_args.return_value = _make_server_args(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        mock_sock = Mock()
        mock_sock.getsockname.return_value = ("10.0.0.5", 0)

        with patch("fpbinject.main.socket.socket", return_value=mock_sock):
            main.main()

        mock_sock.connect.assert_called_once_with(("8.8.8.8", 80))
        mock_sock.close.assert_called_once()


class TestCheckRequirements(unittest.TestCase):
    """check_requirements dependency checker tests"""

    def _make_req_file(self, content):
        """Create a temp dir with requirements.txt, return the 'sub' dir path."""
        import tempfile

        tmpdir = tempfile.mkdtemp()
        req_path = os.path.join(tmpdir, "requirements.txt")
        with open(req_path, "w") as f:
            f.write(content)
        # check_requirements looks at SCRIPT_DIR/../requirements.txt
        subdir = os.path.join(tmpdir, "sub")
        os.makedirs(subdir, exist_ok=True)
        return subdir

    def test_no_requirements_file(self):
        """Returns True when requirements.txt doesn't exist."""
        with patch("fpbinject.main.SCRIPT_DIR", "/nonexistent/path"):
            result = main.check_requirements()
        self.assertTrue(result)

    def test_all_installed(self):
        """Returns True when all packages are installed."""
        subdir = self._make_req_file("Flask\ncoverage\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir):
            result = main.check_requirements()
        self.assertTrue(result)

    def test_comments_and_blanks_skipped(self):
        """Comments and blank lines are ignored."""
        subdir = self._make_req_file("# comment\n\n  \nFlask\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir):
            result = main.check_requirements()
        self.assertTrue(result)

    def test_version_specifiers_stripped(self):
        """Version specifiers like >=, ==, < are stripped."""
        subdir = self._make_req_file("Flask>=2.0\ncoverage==7.0\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir):
            result = main.check_requirements()
        self.assertTrue(result)

    def test_missing_package_non_interactive(self):
        """Missing packages in non-interactive mode: returns True."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "sys.stdin"
        ) as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = main.check_requirements()
        self.assertTrue(result)

    def test_missing_package_user_skips(self):
        """User chooses 'n' to skip install."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "sys.stdin"
        ) as mock_stdin, patch("builtins.input", return_value="n"):
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)

    def test_missing_package_user_quits(self):
        """User chooses 'q' to quit."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "sys.stdin"
        ) as mock_stdin, patch("builtins.input", return_value="q"):
            mock_stdin.isatty.return_value = True
            with self.assertRaises(SystemExit):
                main.check_requirements()

    def test_missing_package_user_installs(self):
        """User chooses 'y' to install."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "sys.stdin"
        ) as mock_stdin, patch("builtins.input", return_value="y"), patch(
            "subprocess.call", return_value=0
        ) as mock_call:
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)
        mock_call.assert_called_once()
        args = mock_call.call_args[0][0]
        self.assertIn("nonexistent_pkg_xyz_12345", args)

    def test_missing_package_user_default_enter(self):
        """User presses Enter (default = install)."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "sys.stdin"
        ) as mock_stdin, patch("builtins.input", return_value=""), patch(
            "subprocess.call", return_value=0
        ) as mock_call:
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)
        mock_call.assert_called_once()

    def test_install_failure_continues(self):
        """pip install failure still returns True."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "sys.stdin"
        ) as mock_stdin, patch("builtins.input", return_value="y"), patch(
            "subprocess.call", return_value=1
        ):
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)

    def test_eof_on_input(self):
        """EOFError on input returns True."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "sys.stdin"
        ) as mock_stdin, patch("builtins.input", side_effect=EOFError):
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)

    def test_keyboard_interrupt_on_input(self):
        """KeyboardInterrupt on input returns True."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "sys.stdin"
        ) as mock_stdin, patch("builtins.input", side_effect=KeyboardInterrupt):
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)

    def test_pyserial_detected_via_metadata(self):
        """pyserial (pip name != import name) detected via importlib.metadata."""
        subdir = self._make_req_file("pyserial\n")
        with patch("fpbinject.main.SCRIPT_DIR", subdir), patch(
            "importlib.metadata.distribution"
        ) as mock_dist:
            mock_dist.return_value = Mock()
            result = main.check_requirements()
        self.assertTrue(result)
        mock_dist.assert_called_with("pyserial")


class TestMainPortConflict(unittest.TestCase):
    """Test main() port conflict handling with get_port_owner and CLI server detection."""

    def _mock_args(self, **overrides):
        defaults = dict(
            host="0.0.0.0",
            http_port=5500,
            skip_port_check=False,
            no_browser=True,
            no_auth=True,
        )
        defaults.update(overrides)
        return _make_server_args(**defaults)

    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=False)
    @patch(
        "fpbinject.main.get_port_owner",
        return_value={"pid": 100, "name": "python", "cmdline": "python main.py"},
    )
    @patch("fpbinject.main.parse_args")
    def test_port_conflict_non_cli_process(
        self, mock_args, mock_owner, mock_check, mock_restore, mock_create
    ):
        """Port occupied by non-CLI process → exit with options."""
        mock_args.return_value = self._mock_args()
        with patch("fpbinject.cli.server_proxy.get_cli_server_pid", return_value=None):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)
        mock_create.assert_not_called()

    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=False)
    @patch(
        "fpbinject.main.get_port_owner",
        return_value={
            "pid": 200,
            "name": "python",
            "cmdline": "python main.py --no-browser",
        },
    )
    @patch("fpbinject.main.parse_args")
    def test_port_conflict_cli_server_user_accepts(
        self, mock_args, mock_owner, mock_check, mock_restore, mock_create
    ):
        """Port occupied by CLI server, user answers Y → kill and continue."""
        mock_args.return_value = self._mock_args()
        mock_app = Mock()
        mock_create.return_value = mock_app
        with patch(
            "fpbinject.cli.server_proxy.get_cli_server_pid", return_value=200
        ), patch(
            "fpbinject.cli.server_proxy.stop_cli_server",
            return_value={"success": True, "message": "done"},
        ), patch(
            "builtins.input", return_value="Y"
        ), patch(
            "time.sleep"
        ), patch(
            "fpbinject.main.threading.Timer"
        ):
            # Should NOT exit — continues to start server
            main.main()
        mock_create.assert_called_once()

    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=False)
    @patch(
        "fpbinject.main.get_port_owner",
        return_value={
            "pid": 200,
            "name": "python",
            "cmdline": "python main.py --no-browser",
        },
    )
    @patch("fpbinject.main.parse_args")
    def test_port_conflict_cli_server_user_declines(
        self, mock_args, mock_owner, mock_check, mock_restore, mock_create
    ):
        """Port occupied by CLI server, user answers n → abort."""
        mock_args.return_value = self._mock_args()
        with patch(
            "fpbinject.cli.server_proxy.get_cli_server_pid", return_value=200
        ), patch("builtins.input", return_value="n"):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 0)
        mock_create.assert_not_called()

    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=False)
    @patch(
        "fpbinject.main.get_port_owner",
        return_value={
            "pid": 200,
            "name": "python",
            "cmdline": "python main.py --no-browser",
        },
    )
    @patch("fpbinject.main.parse_args")
    def test_port_conflict_cli_server_stop_fails(
        self, mock_args, mock_owner, mock_check, mock_restore, mock_create
    ):
        """Port occupied by CLI server, user answers Y but stop fails → exit 1."""
        mock_args.return_value = self._mock_args()
        with patch(
            "fpbinject.cli.server_proxy.get_cli_server_pid", return_value=200
        ), patch(
            "fpbinject.cli.server_proxy.stop_cli_server",
            return_value={"success": False, "error": "fail"},
        ), patch(
            "builtins.input", return_value="Y"
        ):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)

    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=False)
    @patch(
        "fpbinject.main.get_port_owner",
        return_value={
            "pid": 200,
            "name": "python",
            "cmdline": "python main.py --no-browser",
        },
    )
    @patch("fpbinject.main.parse_args")
    def test_port_conflict_cli_server_eof_on_input(
        self, mock_args, mock_owner, mock_check, mock_restore, mock_create
    ):
        """Port occupied by CLI server, EOFError on input → abort."""
        mock_args.return_value = self._mock_args()
        with patch(
            "fpbinject.cli.server_proxy.get_cli_server_pid", return_value=200
        ), patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 0)

    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=False)
    @patch("fpbinject.main.get_port_owner", return_value=None)
    @patch("fpbinject.main.parse_args")
    def test_port_conflict_unknown_owner(
        self, mock_args, mock_owner, mock_check, mock_restore, mock_create
    ):
        """Port occupied but owner unknown → exit with generic message."""
        mock_args.return_value = self._mock_args()
        with patch("fpbinject.cli.server_proxy.get_cli_server_pid", return_value=None):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)

    @patch("fpbinject.main.create_app")
    @patch("fpbinject.main.restore_state")
    @patch("fpbinject.main.check_port_available", return_value=False)
    @patch(
        "fpbinject.main.get_port_owner",
        return_value={"pid": 100, "name": "node", "cmdline": "node server.js"},
    )
    @patch("fpbinject.main.parse_args")
    def test_port_conflict_non_cli_with_stale_cli_pid(
        self, mock_args, mock_owner, mock_check, mock_restore, mock_create
    ):
        """Port occupied by non-CLI process but stale CLI PID exists → show both options."""
        mock_args.return_value = self._mock_args()
        with patch("fpbinject.cli.server_proxy.get_cli_server_pid", return_value=999):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()

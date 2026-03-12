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

import main  # noqa: E402
from core.state import state, DeviceState  # noqa: E402


class TestCreateApp(unittest.TestCase):
    """create_app function tests"""

    def test_create_app_returns_flask_app(self):
        """Test that create_app returns a Flask app"""
        app = main.create_app()
        self.assertIsNotNone(app)
        self.assertEqual(app.name, "main")

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

    @patch("main.socket.socket")
    def test_port_available(self, mock_socket_class):
        """Test port is available"""
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 1  # Non-zero means port is free
        mock_socket_class.return_value = mock_sock

        result = main.check_port_available("127.0.0.1", 5500)

        self.assertTrue(result)
        mock_sock.close.assert_called_once()

    @patch("main.socket.socket")
    def test_port_in_use(self, mock_socket_class):
        """Test port is in use"""
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0  # Zero means port is in use
        mock_socket_class.return_value = mock_sock

        result = main.check_port_available("127.0.0.1", 5500)

        self.assertFalse(result)
        mock_sock.close.assert_called_once()

    @patch("main.socket.socket")
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
        self.assertEqual(args.port, 5500)
        self.assertFalse(args.debug)

    def test_custom_port(self):
        """Test custom port argument"""
        with patch("sys.argv", ["main.py", "--port", "8080"]):
            args = main.parse_args()

        self.assertEqual(args.port, 8080)

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
        with patch("sys.argv", ["main.py", "--port", "9090", "--no-browser"]):
            args = main.parse_args()

        self.assertEqual(args.port, 9090)
        self.assertTrue(args.no_browser)


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

    @patch("main.restore_file_watcher")
    def test_restore_state_with_file_watcher(self, mock_restore):
        """Test restore_state restores file watcher"""
        state.device.auto_compile = True
        state.device.watch_dirs = ["/tmp/test"]
        state.device.auto_connect = False

        main.restore_state()

        mock_restore.assert_called_once()

    @patch("main.start_worker")
    @patch("main.serial_open")
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

    @patch("main.start_worker")
    @patch("main.serial_open")
    def test_restore_state_auto_connect_failure(self, mock_serial, mock_worker):
        """Test restore_state with failed auto-connect"""
        state.device.auto_connect = True
        state.device.port = "/dev/ttyUSB0"

        mock_serial.return_value = (None, "Port not found")

        main.restore_state()

        mock_worker.assert_called_once()
        self.assertIsNone(state.device.ser)


class TestMain(unittest.TestCase):
    """main function tests"""

    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available")
    @patch("main.parse_args")
    def test_main_port_in_use(self, mock_args, mock_check, mock_restore, mock_create):
        """Test main exits when port is in use"""
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
            skip_port_check=False,
            no_browser=True,
        )
        mock_check.return_value = False

        with self.assertRaises(SystemExit) as cm:
            main.main()

        self.assertEqual(cm.exception.code, 1)
        mock_create.assert_not_called()

    @patch("main.threading.Timer")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available")
    @patch("main.parse_args")
    def test_main_starts_server(
        self, mock_args, mock_check, mock_restore, mock_create, mock_timer_cls
    ):
        """Test main starts server successfully"""
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
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

    @patch("main.threading.Timer")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available")
    @patch("main.parse_args")
    def test_main_skip_port_check(
        self, mock_args, mock_check, mock_restore, mock_create, mock_timer_cls
    ):
        """Test main skips port check when skip_port_check is True"""
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
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


class TestAutoOpenBrowser(unittest.TestCase):
    """Tests for auto-open browser and startup banner"""

    @patch("main.threading.Timer")
    @patch("main.webbrowser.open")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available", return_value=True)
    @patch("main.parse_args")
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
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
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

    @patch("main.threading.Timer")
    @patch("main.webbrowser.open")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available", return_value=True)
    @patch("main.parse_args")
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
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        main.main()

        mock_timer_cls.assert_not_called()

    @patch("main.threading.Timer")
    @patch("main.webbrowser.open")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available", return_value=True)
    @patch("main.parse_args")
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
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=9090,
            debug=False,
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

    @patch("main.threading.Timer")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available", return_value=True)
    @patch("main.parse_args")
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
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        with patch("main.logger") as mock_logger:
            main.main()

        calls = [str(c) for c in mock_logger.info.call_args_list]
        log_output = "\n".join(calls)
        self.assertIn("FPBInject Web Server Started", log_output)
        self.assertIn("http://127.0.0.1:5500", log_output)

    @patch("main.threading.Timer")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available", return_value=True)
    @patch("main.parse_args")
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
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=8080,
            debug=False,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        with patch("main.logger") as mock_logger:
            main.main()

        calls = [str(c) for c in mock_logger.info.call_args_list]
        log_output = "\n".join(calls)
        self.assertIn("http://127.0.0.1:8080", log_output)

    @patch("main.threading.Timer")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available", return_value=True)
    @patch("main.parse_args")
    def test_startup_banner_shows_lan_ip(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """Startup banner should show LAN network URL"""
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        mock_sock = Mock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 0)

        with patch("main.logger") as mock_logger, patch(
            "main.socket.socket", return_value=mock_sock
        ):
            main.main()

        calls = [str(c) for c in mock_logger.info.call_args_list]
        log_output = "\n".join(calls)
        self.assertIn("http://192.168.1.100:5500", log_output)
        self.assertIn("Network", log_output)

    @patch("main.threading.Timer")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available", return_value=True)
    @patch("main.parse_args")
    def test_startup_banner_lan_ip_unavailable(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """Startup banner shows 'unavailable' when LAN IP detection fails"""
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        mock_sock = Mock()
        mock_sock.connect.side_effect = OSError("Network unreachable")

        with patch("main.logger") as mock_logger, patch(
            "main.socket.socket", return_value=mock_sock
        ):
            main.main()

        calls = [str(c) for c in mock_logger.info.call_args_list]
        log_output = "\n".join(calls)
        self.assertIn("unavailable", log_output)

    @patch("main.threading.Timer")
    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available", return_value=True)
    @patch("main.parse_args")
    def test_startup_lan_ip_socket_closed(
        self,
        mock_args,
        mock_check,
        mock_restore,
        mock_create,
        mock_timer_cls,
    ):
        """LAN IP detection should close the socket after use"""
        mock_args.return_value = Mock(
            host="0.0.0.0",
            port=5500,
            debug=False,
            skip_port_check=True,
            no_browser=True,
        )
        mock_create.return_value = Mock()

        mock_sock = Mock()
        mock_sock.getsockname.return_value = ("10.0.0.5", 0)

        with patch("main.socket.socket", return_value=mock_sock):
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
        with patch("main.SCRIPT_DIR", "/nonexistent/path"):
            result = main.check_requirements()
        self.assertTrue(result)

    def test_all_installed(self):
        """Returns True when all packages are installed."""
        subdir = self._make_req_file("Flask\ncoverage\n")
        with patch("main.SCRIPT_DIR", subdir):
            result = main.check_requirements()
        self.assertTrue(result)

    def test_comments_and_blanks_skipped(self):
        """Comments and blank lines are ignored."""
        subdir = self._make_req_file("# comment\n\n  \nFlask\n")
        with patch("main.SCRIPT_DIR", subdir):
            result = main.check_requirements()
        self.assertTrue(result)

    def test_version_specifiers_stripped(self):
        """Version specifiers like >=, ==, < are stripped."""
        subdir = self._make_req_file("Flask>=2.0\ncoverage==7.0\n")
        with patch("main.SCRIPT_DIR", subdir):
            result = main.check_requirements()
        self.assertTrue(result)

    def test_missing_package_non_interactive(self):
        """Missing packages in non-interactive mode: returns True."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("main.SCRIPT_DIR", subdir), patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = main.check_requirements()
        self.assertTrue(result)

    def test_missing_package_user_skips(self):
        """User chooses 'n' to skip install."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("main.SCRIPT_DIR", subdir), patch("sys.stdin") as mock_stdin, patch(
            "builtins.input", return_value="n"
        ):
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)

    def test_missing_package_user_quits(self):
        """User chooses 'q' to quit."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("main.SCRIPT_DIR", subdir), patch("sys.stdin") as mock_stdin, patch(
            "builtins.input", return_value="q"
        ):
            mock_stdin.isatty.return_value = True
            with self.assertRaises(SystemExit):
                main.check_requirements()

    def test_missing_package_user_installs(self):
        """User chooses 'y' to install."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("main.SCRIPT_DIR", subdir), patch("sys.stdin") as mock_stdin, patch(
            "builtins.input", return_value="y"
        ), patch("subprocess.call", return_value=0) as mock_call:
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)
        mock_call.assert_called_once()
        args = mock_call.call_args[0][0]
        self.assertIn("nonexistent_pkg_xyz_12345", args)

    def test_missing_package_user_default_enter(self):
        """User presses Enter (default = install)."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("main.SCRIPT_DIR", subdir), patch("sys.stdin") as mock_stdin, patch(
            "builtins.input", return_value=""
        ), patch("subprocess.call", return_value=0) as mock_call:
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)
        mock_call.assert_called_once()

    def test_install_failure_continues(self):
        """pip install failure still returns True."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("main.SCRIPT_DIR", subdir), patch("sys.stdin") as mock_stdin, patch(
            "builtins.input", return_value="y"
        ), patch("subprocess.call", return_value=1):
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)

    def test_eof_on_input(self):
        """EOFError on input returns True."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("main.SCRIPT_DIR", subdir), patch("sys.stdin") as mock_stdin, patch(
            "builtins.input", side_effect=EOFError
        ):
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)

    def test_keyboard_interrupt_on_input(self):
        """KeyboardInterrupt on input returns True."""
        subdir = self._make_req_file("nonexistent_pkg_xyz_12345\n")
        with patch("main.SCRIPT_DIR", subdir), patch("sys.stdin") as mock_stdin, patch(
            "builtins.input", side_effect=KeyboardInterrupt
        ):
            mock_stdin.isatty.return_value = True
            result = main.check_requirements()
        self.assertTrue(result)

    def test_pyserial_detected_via_metadata(self):
        """pyserial (pip name != import name) detected via importlib.metadata."""
        subdir = self._make_req_file("pyserial\n")
        with patch("main.SCRIPT_DIR", subdir), patch(
            "importlib.metadata.distribution"
        ) as mock_dist:
            mock_dist.return_value = Mock()
            result = main.check_requirements()
        self.assertTrue(result)
        mock_dist.assert_called_with("pyserial")


if __name__ == "__main__":
    unittest.main()

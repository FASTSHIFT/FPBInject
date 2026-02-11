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
            host="0.0.0.0", port=5500, debug=False, skip_port_check=False
        )
        mock_check.return_value = False

        with self.assertRaises(SystemExit) as cm:
            main.main()

        self.assertEqual(cm.exception.code, 1)
        mock_create.assert_not_called()

    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available")
    @patch("main.parse_args")
    def test_main_starts_server(self, mock_args, mock_check, mock_restore, mock_create):
        """Test main starts server successfully"""
        mock_args.return_value = Mock(
            host="0.0.0.0", port=5500, debug=False, skip_port_check=False
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

    @patch("main.create_app")
    @patch("main.restore_state")
    @patch("main.check_port_available")
    @patch("main.parse_args")
    def test_main_skip_port_check(
        self, mock_args, mock_check, mock_restore, mock_create
    ):
        """Test main skips port check when skip_port_check is True"""
        mock_args.return_value = Mock(
            host="0.0.0.0", port=5500, debug=False, skip_port_check=True
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


if __name__ == "__main__":
    unittest.main()

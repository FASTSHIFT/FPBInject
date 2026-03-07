#!/usr/bin/env python3
"""Tests for app/routes/watch_expr.py"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from app.routes.watch_expr import bp  # noqa: E402
from core.state import state  # noqa: E402


class WatchExprRoutesBase(unittest.TestCase):
    """Base class for watch expression route tests."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(bp, url_prefix="/api")
        self.client = self.app.test_client()
        state.gdb_session = None
        # Reset watch list
        import app.routes.watch_expr as we

        we._watch_list = []
        we._watch_next_id = 1

    def tearDown(self):
        state.gdb_session = None
        import app.routes.watch_expr as we

        we._watch_list = []
        we._watch_next_id = 1


class TestWatchEvaluateEndpoint(WatchExprRoutesBase):
    """Test /api/watch_expr/evaluate endpoint."""

    def test_empty_expr(self):
        response = self.client.post("/api/watch_expr/evaluate", json={"expr": ""})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("empty", data["error"].lower())

    def test_no_gdb(self):
        response = self.client.post(
            "/api/watch_expr/evaluate", json={"expr": "g_counter"}
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("GDB", data["error"])

    @patch("app.routes.watch_expr._read_device_memory")
    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_evaluate_simple_symbol(self, _mock_gdb_avail, mock_read):
        mock_session = Mock()
        mock_session.execute.side_effect = lambda cmd, **kw: {
            "whatis g_counter": "type = uint32_t",
            "print sizeof(g_counter)": "$1 = 4",
            "info address g_counter": 'Symbol "g_counter" is at address 0x20001000.',
        }.get(cmd)
        mock_session._parse_address_from_info.return_value = 0x20001000
        mock_session._parse_ptype_output.return_value = None
        state.gdb_session = mock_session
        mock_read.return_value = ("01000000", None)

        response = self.client.post(
            "/api/watch_expr/evaluate",
            json={"expr": "g_counter", "read_device": True},
        )
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["addr"], "0x20001000")
        self.assertEqual(data["size"], 4)
        self.assertEqual(data["type_name"], "uint32_t")
        self.assertEqual(data["hex_data"], "01000000")
        self.assertEqual(data["source"], "device")

    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_evaluate_no_read(self, _mock_gdb_avail):
        mock_session = Mock()
        mock_session.execute.side_effect = lambda cmd, **kw: {
            "whatis g_counter": "type = uint32_t",
            "print sizeof(g_counter)": "$1 = 4",
            "info address g_counter": 'Symbol "g_counter" is at address 0x20001000.',
        }.get(cmd)
        mock_session._parse_address_from_info.return_value = 0x20001000
        mock_session._parse_ptype_output.return_value = None
        state.gdb_session = mock_session

        response = self.client.post(
            "/api/watch_expr/evaluate",
            json={"expr": "g_counter", "read_device": False},
        )
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIsNone(data["hex_data"])
        self.assertIsNone(data["source"])

    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_evaluate_error(self, _mock_gdb_avail):
        mock_session = Mock()
        mock_session.execute.return_value = None
        state.gdb_session = mock_session

        response = self.client.post(
            "/api/watch_expr/evaluate", json={"expr": "nonexistent"}
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Cannot resolve", data["error"])


class TestWatchDerefEndpoint(WatchExprRoutesBase):
    """Test /api/watch_expr/deref endpoint."""

    def test_no_addr(self):
        response = self.client.post(
            "/api/watch_expr/deref", json={"type_name": "int *"}
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("address", data["error"].lower())

    def test_no_type(self):
        response = self.client.post(
            "/api/watch_expr/deref", json={"addr": "0x20000000"}
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("type_name", data["error"])

    def test_no_gdb(self):
        response = self.client.post(
            "/api/watch_expr/deref",
            json={"addr": "0x20000000", "type_name": "int *"},
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("GDB", data["error"])

    @patch("app.routes.watch_expr._read_device_memory")
    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_deref_success(self, _mock_gdb_avail, mock_read):
        mock_session = Mock()
        mock_session.execute.side_effect = lambda cmd, **kw: {
            "print sizeof(uint32_t)": "$1 = 4",
        }.get(cmd)
        mock_session._parse_ptype_output.return_value = None
        state.gdb_session = mock_session

        # First call: read pointer value, second call: read target data
        mock_read.side_effect = [
            ("00300020", None),  # pointer value = 0x20003000 (LE)
            ("DEADBEEF", None),  # target data
        ]

        response = self.client.post(
            "/api/watch_expr/deref",
            json={"addr": "0x20002000", "type_name": "uint32_t *"},
        )
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["target_addr"], "0x20003000")
        self.assertEqual(data["target_type"], "uint32_t")
        self.assertEqual(data["hex_data"], "DEADBEEF")

    @patch("app.routes.watch_expr._read_device_memory")
    @patch("core.gdb_manager.is_gdb_available", return_value=True)
    def test_deref_null_pointer(self, _mock_gdb_avail, mock_read):
        mock_session = Mock()
        state.gdb_session = mock_session
        mock_read.return_value = ("00000000", None)  # NULL

        response = self.client.post(
            "/api/watch_expr/deref",
            json={"addr": "0x20002000", "type_name": "int *"},
        )
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("NULL", data["error"])


class TestWatchListEndpoints(WatchExprRoutesBase):
    """Test watch list CRUD endpoints."""

    def test_list_empty(self):
        response = self.client.get("/api/watch_expr/list")
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["watches"]), 0)

    def test_add_and_list(self):
        response = self.client.post("/api/watch_expr/add", json={"expr": "g_counter"})
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["id"], 1)

        response = self.client.get("/api/watch_expr/list")
        data = response.get_json()
        self.assertEqual(len(data["watches"]), 1)
        self.assertEqual(data["watches"][0]["expr"], "g_counter")

    def test_add_empty(self):
        response = self.client.post("/api/watch_expr/add", json={"expr": ""})
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_add_too_long(self):
        response = self.client.post("/api/watch_expr/add", json={"expr": "x" * 300})
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_add_duplicate(self):
        self.client.post("/api/watch_expr/add", json={"expr": "g_counter"})
        response = self.client.post("/api/watch_expr/add", json={"expr": "g_counter"})
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data.get("duplicate"))

    def test_remove(self):
        self.client.post("/api/watch_expr/add", json={"expr": "g_counter"})
        response = self.client.post("/api/watch_expr/remove", json={"id": 1})
        data = response.get_json()
        self.assertTrue(data["success"])

        response = self.client.get("/api/watch_expr/list")
        data = response.get_json()
        self.assertEqual(len(data["watches"]), 0)

    def test_remove_not_found(self):
        response = self.client.post("/api/watch_expr/remove", json={"id": 999})
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"].lower())

    def test_remove_no_id(self):
        response = self.client.post("/api/watch_expr/remove", json={})
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_clear(self):
        self.client.post("/api/watch_expr/add", json={"expr": "a"})
        self.client.post("/api/watch_expr/add", json={"expr": "b"})
        response = self.client.post("/api/watch_expr/clear")
        data = response.get_json()
        self.assertTrue(data["success"])

        response = self.client.get("/api/watch_expr/list")
        data = response.get_json()
        self.assertEqual(len(data["watches"]), 0)

    def test_add_increments_id(self):
        r1 = self.client.post("/api/watch_expr/add", json={"expr": "a"})
        r2 = self.client.post("/api/watch_expr/add", json={"expr": "b"})
        self.assertEqual(r1.get_json()["id"], 1)
        self.assertEqual(r2.get_json()["id"], 2)


if __name__ == "__main__":
    unittest.main()

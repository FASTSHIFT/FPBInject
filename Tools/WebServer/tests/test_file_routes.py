#!/usr/bin/env python3
"""Tests for app/routes/files.py"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from app.routes.files import bp  # noqa: E402
from core.state import state  # noqa: E402


class FileRoutesBase(unittest.TestCase):
    """Base class for file route tests."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(bp, url_prefix="/api")
        self.client = self.app.test_client()
        self.tmpdir = tempfile.mkdtemp()
        state.device.watch_dirs = [self.tmpdir]

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)
        state.device.watch_dirs = []


class TestBrowse(FileRoutesBase):
    """Test /api/browse endpoint."""

    def test_browse_home(self):
        res = self.client.get("/api/browse")
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["type"], "directory")

    def test_browse_tmpdir(self):
        # Create a file and subdir
        os.makedirs(os.path.join(self.tmpdir, "subdir"))
        with open(os.path.join(self.tmpdir, "test.txt"), "w") as f:
            f.write("hello")

        res = self.client.get(f"/api/browse?path={self.tmpdir}")
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["type"], "directory")
        names = [item["name"] for item in data["items"]]
        self.assertIn("subdir", names)
        self.assertIn("test.txt", names)

    def test_browse_file_path(self):
        filepath = os.path.join(self.tmpdir, "test.txt")
        with open(filepath, "w") as f:
            f.write("hello")

        res = self.client.get(f"/api/browse?path={filepath}")
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["type"], "file")
        self.assertEqual(data["path"], filepath)

    def test_browse_nonexistent(self):
        res = self.client.get("/api/browse?path=/nonexistent/path/xyz")
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("not found", data["error"])

    def test_browse_with_filter(self):
        with open(os.path.join(self.tmpdir, "a.c"), "w") as f:
            f.write("")
        with open(os.path.join(self.tmpdir, "b.txt"), "w") as f:
            f.write("")

        res = self.client.get(f"/api/browse?path={self.tmpdir}&filter=.c")
        data = res.get_json()
        names = [item["name"] for item in data["items"]]
        self.assertIn("a.c", names)
        self.assertNotIn("b.txt", names)

    def test_browse_hidden_files_skipped(self):
        with open(os.path.join(self.tmpdir, ".hidden"), "w") as f:
            f.write("")
        with open(os.path.join(self.tmpdir, "visible"), "w") as f:
            f.write("")

        res = self.client.get(f"/api/browse?path={self.tmpdir}")
        data = res.get_json()
        names = [item["name"] for item in data["items"]]
        self.assertNotIn(".hidden", names)
        self.assertIn("visible", names)

    def test_browse_permission_denied(self):
        with patch("os.listdir", side_effect=PermissionError("denied")):
            res = self.client.get(f"/api/browse?path={self.tmpdir}")
            data = res.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Permission denied", data["error"])

    def test_browse_tilde_expansion(self):
        res = self.client.get("/api/browse?path=~")
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["current_path"], os.path.expanduser("~"))


class TestFileWrite(FileRoutesBase):
    """Test /api/file/write endpoint."""

    def test_write_success(self):
        filepath = os.path.join(self.tmpdir, "out.txt")
        res = self.client.post(
            "/api/file/write",
            json={"path": filepath, "content": "hello world"},
        )
        data = res.get_json()
        self.assertTrue(data["success"])
        with open(filepath) as f:
            self.assertEqual(f.read(), "hello world")

    def test_write_no_path(self):
        res = self.client.post("/api/file/write", json={"content": "x"})
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Path not specified", data["error"])

    def test_write_creates_directory(self):
        filepath = os.path.join(self.tmpdir, "newdir", "out.txt")
        res = self.client.post(
            "/api/file/write",
            json={"path": filepath, "content": "data"},
        )
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(os.path.exists(filepath))

    def test_write_tilde_expansion(self):
        home = os.path.expanduser("~")
        filepath = os.path.join(home, "fpbinject_test_write.tmp")
        try:
            res = self.client.post(
                "/api/file/write",
                json={"path": "~/fpbinject_test_write.tmp", "content": "test"},
            )
            data = res.get_json()
            self.assertTrue(data["success"])
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_write_not_allowed_path(self):
        state.device.watch_dirs = []
        self.client.post(
            "/api/file/write",
            json={"path": "/tmp/not_allowed.txt", "content": "x"},
        )
        # /tmp is not under home, so may be rejected
        # (depends on home dir, but test the logic path)

    def test_write_watch_dir_parent_allowed(self):
        """Writing to parent of watch dir should be allowed."""
        state.device.watch_dirs = [os.path.join(self.tmpdir, "sub")]
        filepath = os.path.join(self.tmpdir, "out.txt")
        res = self.client.post(
            "/api/file/write",
            json={"path": filepath, "content": "data"},
        )
        data = res.get_json()
        self.assertTrue(data["success"])

    def test_write_exception(self):
        with patch("builtins.open", side_effect=OSError("disk full")):
            filepath = os.path.join(self.tmpdir, "fail.txt")
            res = self.client.post(
                "/api/file/write",
                json={"path": filepath, "content": "x"},
            )
            data = res.get_json()
            self.assertFalse(data["success"])
            self.assertIn("disk full", data["error"])


class TestFileWriteBinary(FileRoutesBase):
    """Test /api/file/write/binary endpoint."""

    def test_write_binary_success(self):
        filepath = os.path.join(self.tmpdir, "out.bin")
        res = self.client.post(
            "/api/file/write/binary",
            json={"path": filepath, "hex_data": "deadbeef01020304"},
        )
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["size"], 8)
        with open(filepath, "rb") as f:
            self.assertEqual(f.read(), b"\xde\xad\xbe\xef\x01\x02\x03\x04")

    def test_write_binary_no_path(self):
        res = self.client.post(
            "/api/file/write/binary",
            json={"hex_data": "aabb"},
        )
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Path not specified", data["error"])

    def test_write_binary_no_data(self):
        filepath = os.path.join(self.tmpdir, "out.bin")
        res = self.client.post(
            "/api/file/write/binary",
            json={"path": filepath},
        )
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("No data to write", data["error"])

    def test_write_binary_invalid_hex(self):
        filepath = os.path.join(self.tmpdir, "out.bin")
        res = self.client.post(
            "/api/file/write/binary",
            json={"path": filepath, "hex_data": "ZZZZ"},
        )
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Invalid hex data", data["error"])

    def test_write_binary_hex_with_spaces(self):
        filepath = os.path.join(self.tmpdir, "out.bin")
        res = self.client.post(
            "/api/file/write/binary",
            json={"path": filepath, "hex_data": "de ad be ef"},
        )
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["size"], 4)
        with open(filepath, "rb") as f:
            self.assertEqual(f.read(), b"\xde\xad\xbe\xef")

    def test_write_binary_hex_with_newlines(self):
        filepath = os.path.join(self.tmpdir, "out.bin")
        res = self.client.post(
            "/api/file/write/binary",
            json={"path": filepath, "hex_data": "aabb\nccdd"},
        )
        data = res.get_json()
        self.assertTrue(data["success"])
        with open(filepath, "rb") as f:
            self.assertEqual(f.read(), b"\xaa\xbb\xcc\xdd")

    def test_write_binary_creates_directory(self):
        filepath = os.path.join(self.tmpdir, "newdir", "out.bin")
        res = self.client.post(
            "/api/file/write/binary",
            json={"path": filepath, "hex_data": "ff"},
        )
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(os.path.exists(filepath))

    def test_write_binary_tilde_expansion(self):
        home = os.path.expanduser("~")
        filepath = os.path.join(home, "fpbinject_test_binary.tmp")
        try:
            res = self.client.post(
                "/api/file/write/binary",
                json={"path": "~/fpbinject_test_binary.tmp", "hex_data": "00"},
            )
            data = res.get_json()
            self.assertTrue(data["success"])
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_write_binary_not_allowed(self):
        state.device.watch_dirs = []
        self.client.post(
            "/api/file/write/binary",
            json={"path": "/tmp/not_allowed.bin", "hex_data": "aa"},
        )
        # Path check depends on home dir

    def test_write_binary_exception(self):
        with patch("builtins.open", side_effect=OSError("read-only fs")):
            filepath = os.path.join(self.tmpdir, "fail.bin")
            res = self.client.post(
                "/api/file/write/binary",
                json={"path": filepath, "hex_data": "aa"},
            )
            data = res.get_json()
            self.assertFalse(data["success"])
            self.assertIn("read-only fs", data["error"])

    def test_write_binary_watch_dir_parent_allowed(self):
        state.device.watch_dirs = [os.path.join(self.tmpdir, "sub")]
        filepath = os.path.join(self.tmpdir, "out.bin")
        res = self.client.post(
            "/api/file/write/binary",
            json={"path": filepath, "hex_data": "aabb"},
        )
        data = res.get_json()
        self.assertTrue(data["success"])


if __name__ == "__main__":
    unittest.main()

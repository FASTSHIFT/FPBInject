#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""Tests for the file transaction guard (core/file_txn.py) and the 409 busy
behavior it gives the transfer routes."""

import io
import os
import sys
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402

from fpbinject.app.routes.transfer import bp  # noqa: E402
from fpbinject.core import file_txn  # noqa: E402
from fpbinject.core.file_txn import (  # noqa: E402
    TransferBusy,
    begin_transaction,
    end_transaction,
    file_transaction,
    get_active_transaction,
    request_cancel,
)


class _Dev:
    """Minimal device with the real transaction primitives."""

    def __init__(self):
        self.file_txn_lock = threading.Lock()
        self.file_txn_active = None


class TestFileTxnGuard(unittest.TestCase):
    """Unit tests for the guard primitives."""

    def setUp(self):
        self.dev = _Dev()

    def test_context_manager_acquires_and_releases(self):
        with file_transaction(self.dev, "upload", "/a.bin") as cancel_event:
            self.assertIsInstance(cancel_event, threading.Event)
            self.assertTrue(self.dev.file_txn_lock.locked())
            self.assertEqual(self.dev.file_txn_active["op"], "upload")
        # Released after the block.
        self.assertFalse(self.dev.file_txn_lock.locked())
        self.assertIsNone(self.dev.file_txn_active)

    def test_second_context_manager_raises_busy(self):
        with file_transaction(self.dev, "upload", "/a.bin"):
            with self.assertRaises(TransferBusy):
                with file_transaction(self.dev, "delete", "/b.bin"):
                    pass

    def test_lock_released_on_exception(self):
        with self.assertRaises(ValueError):
            with file_transaction(self.dev, "upload", "/a.bin"):
                raise ValueError("boom")
        self.assertFalse(self.dev.file_txn_lock.locked())
        self.assertIsNone(self.dev.file_txn_active)

    def test_begin_end_transaction(self):
        ev = begin_transaction(self.dev, "download", "/c.bin")
        self.assertIsInstance(ev, threading.Event)
        self.assertTrue(self.dev.file_txn_lock.locked())
        with self.assertRaises(TransferBusy):
            begin_transaction(self.dev, "upload", "/d.bin")
        end_transaction(self.dev)
        self.assertFalse(self.dev.file_txn_lock.locked())
        self.assertIsNone(self.dev.file_txn_active)

    def test_end_transaction_idempotent(self):
        # Safe to call with nothing held.
        end_transaction(self.dev)
        self.assertFalse(self.dev.file_txn_lock.locked())

    def test_busy_message_includes_op_and_path(self):
        with file_transaction(self.dev, "upload", "/firmware.bin"):
            try:
                begin_transaction(self.dev, "delete", "/x")
                self.fail("expected TransferBusy")
            except TransferBusy as e:
                self.assertIn("upload", str(e))
                self.assertIn("/firmware.bin", str(e))

    def test_get_active_transaction_hides_event(self):
        with file_transaction(self.dev, "upload", "/a.bin"):
            active = get_active_transaction(self.dev)
            self.assertEqual(active["op"], "upload")
            self.assertNotIn("cancel_event", active)
        self.assertIsNone(get_active_transaction(self.dev))

    def test_request_cancel_sets_event(self):
        ev = begin_transaction(self.dev, "upload", "/a.bin")
        try:
            self.assertTrue(request_cancel(self.dev))
            self.assertTrue(ev.is_set())
        finally:
            end_transaction(self.dev)

    def test_request_cancel_no_active(self):
        self.assertFalse(request_cancel(self.dev))


def _mock_run_in_device_worker(device, func, timeout=10.0):
    func()
    return True


class TestTransferBusy409(unittest.TestCase):
    """The transfer routes must return 409 when a transaction is active."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(bp, url_prefix="/api")
        self.client = self.app.test_client()

        self.mock_fpb = Mock()
        self.mock_fpb.enter_fl_mode = Mock()
        self.mock_fpb.exit_fl_mode = Mock()

        self.dev = _Dev()
        self.dev.upload_chunk_size = 64
        self.dev.download_chunk_size = 64
        self.dev.transfer_max_retries = 3

        self.state_patcher = patch("fpbinject.app.routes.transfer.state")
        self.mock_state = self.state_patcher.start()
        self.mock_state.device = self.dev

        self.helpers_patcher = patch("fpbinject.app.routes.transfer._get_helpers")
        self.mock_helpers = self.helpers_patcher.start()
        self.mock_helpers.return_value = (
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            lambda: self.mock_fpb,
        )

        self.worker_patcher = patch(
            "fpbinject.app.routes.transfer.run_in_device_worker",
            side_effect=_mock_run_in_device_worker,
        )
        self.worker_patcher.start()

    def tearDown(self):
        self.state_patcher.stop()
        self.helpers_patcher.stop()
        self.worker_patcher.stop()

    def _hold_transaction(self):
        """Simulate an in-flight transfer holding the guard."""
        begin_transaction(self.dev, "upload", "/busy.bin")

    def test_delete_returns_409_when_busy(self):
        self._hold_transaction()
        try:
            resp = self.client.post("/api/transfer/delete", json={"path": "/x"})
            self.assertEqual(resp.status_code, 409)
            data = resp.get_json()
            self.assertFalse(data["success"])
            self.assertTrue(data.get("busy"))
        finally:
            end_transaction(self.dev)

    def test_rename_returns_409_when_busy(self):
        self._hold_transaction()
        try:
            resp = self.client.post(
                "/api/transfer/rename",
                json={"old_path": "/a", "new_path": "/b"},
            )
            self.assertEqual(resp.status_code, 409)
        finally:
            end_transaction(self.dev)

    def test_mkdir_returns_409_when_busy(self):
        self._hold_transaction()
        try:
            resp = self.client.post("/api/transfer/mkdir", json={"path": "/d"})
            self.assertEqual(resp.status_code, 409)
        finally:
            end_transaction(self.dev)

    def test_list_returns_409_when_busy(self):
        self._hold_transaction()
        try:
            resp = self.client.get("/api/transfer/list?path=/")
            self.assertEqual(resp.status_code, 409)
        finally:
            end_transaction(self.dev)

    def test_stat_returns_409_when_busy(self):
        self._hold_transaction()
        try:
            resp = self.client.get("/api/transfer/stat?path=/x")
            self.assertEqual(resp.status_code, 409)
        finally:
            end_transaction(self.dev)

    def test_download_sync_returns_409_when_busy(self):
        self._hold_transaction()
        try:
            resp = self.client.post(
                "/api/transfer/download-sync", json={"remote_path": "/x"}
            )
            self.assertEqual(resp.status_code, 409)
        finally:
            end_transaction(self.dev)

    def test_upload_returns_409_when_busy(self):
        self._hold_transaction()
        try:
            data = {
                "file": (io.BytesIO(b"data"), "test.txt"),
                "remote_path": "/x",
            }
            resp = self.client.post(
                "/api/transfer/upload",
                data=data,
                content_type="multipart/form-data",
            )
            self.assertEqual(resp.status_code, 409)
        finally:
            end_transaction(self.dev)

    def test_streaming_download_returns_409_when_busy(self):
        self._hold_transaction()
        try:
            resp = self.client.post(
                "/api/transfer/download", json={"remote_path": "/x"}
            )
            self.assertEqual(resp.status_code, 409)
        finally:
            end_transaction(self.dev)

    def test_delete_succeeds_when_idle(self):
        # No active transaction -> guard acquired and released normally.
        self.mock_fpb.enter_fl_mode = Mock()
        with patch("fpbinject.app.routes.transfer._get_file_transfer") as mock_get_ft:
            mock_ft = Mock()
            mock_ft.fpb = self.mock_fpb
            mock_ft.fremove.return_value = (True, "OK")
            mock_get_ft.return_value = mock_ft
            resp = self.client.post("/api/transfer/delete", json={"path": "/x"})
            self.assertEqual(resp.status_code, 200)
        # Guard must be free again after the request.
        self.assertFalse(self.dev.file_txn_lock.locked())


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for POST /api/fpb/exec.
"""

import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from fpbinject.app.routes import fpb  # noqa: E402
from fpbinject.core.exec_client import worst_case_seconds  # noqa: E402
from fpbinject.core.serial_protocol import FPBProtocolError  # noqa: E402
from fpbinject.core.state import DeviceState, state  # noqa: E402

OK_RESULT = {
    "success": True,
    "ret": 0,
    "output": "hi\n",
    "replayed": False,
    "started": True,
    "output_truncated": False,
    "elapsed_ms": 1.0,
    "error_code": "",
    "error": "",
}


def sync_worker(device, func, timeout=5.0):
    func()
    return True


class ExecRouteBase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.original_device = state.device
        state.device = DeviceState()
        state.device.exec_enabled = True
        self.app.register_blueprint(fpb.bp, url_prefix="/api")
        self.client = self.app.test_client()

        self.fpb = Mock()
        self.fpb.exec_cmd.return_value = dict(OK_RESULT)
        helpers = (Mock(), Mock(), Mock(), Mock(), lambda: self.fpb, Mock())

        patchers = [
            patch(
                "fpbinject.app.routes.fpb.run_in_device_worker",
                side_effect=sync_worker,
            ),
            patch("fpbinject.app.routes.fpb._get_helpers", return_value=helpers),
        ]
        self.mock_worker = patchers[0].start()
        patchers[1].start()
        for p in patchers:
            self.addCleanup(p.stop)

    def tearDown(self):
        state.device = self.original_device

    def post(self, body, **kw):
        return self.client.post("/api/fpb/exec", json=body, **kw)


class TestExecRoute(ExecRouteBase):
    def test_success_passes_result_through(self):
        resp = self.post({"cmd": "ls -l"})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data, OK_RESULT)

    def test_arguments_forwarded(self):
        self.post({"cmd": "ls", "timeout": 4, "ack_timeout": 0.5, "max_retries": 2})
        self.fpb.exec_cmd.assert_called_once_with(
            "ls", timeout=4, ack_timeout=0.5, max_retries=2
        )

    def test_defaults(self):
        state.device.transfer_max_retries = 6
        self.post({"cmd": "ls"})
        self.fpb.exec_cmd.assert_called_once_with(
            "ls", timeout=10.0, ack_timeout=1.0, max_retries=6
        )

    def test_default_retries_follow_transfer_setting(self):
        state.device.transfer_max_retries = 1
        self.post({"cmd": "ls"})
        self.assertEqual(self.fpb.exec_cmd.call_args.kwargs["max_retries"], 1)

    def test_no_artificial_timeout_cap(self):
        resp = self.post({"cmd": "ls", "timeout": 3600})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.fpb.exec_cmd.call_args.kwargs["timeout"], 3600)

    def test_worker_window_covers_worst_case(self):
        self.post({"cmd": "ls", "timeout": 100, "ack_timeout": 2, "max_retries": 5})
        window = self.mock_worker.call_args.kwargs.get("timeout")
        if window is None:
            window = self.mock_worker.call_args.args[2]
        self.assertGreaterEqual(window, worst_case_seconds(100, 2, 5))

    def test_protocol_failures_are_http_200(self):
        failing = dict(
            OK_RESULT, success=False, error_code="unknown_state", error="stuck"
        )
        self.fpb.exec_cmd.return_value = failing
        resp = self.post({"cmd": "sleep 99"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)["error_code"], "unknown_state")

    def test_fl_mode_exited_after_exec(self):
        self.post({"cmd": "ls"})
        self.fpb.exit_fl_mode.assert_called()

    def test_transaction_released_after_request(self):
        self.post({"cmd": "ls"})
        self.assertFalse(state.device.file_txn_lock.locked())
        self.assertIsNone(state.device.file_txn_active)

    def test_transaction_released_on_error(self):
        self.fpb.exec_cmd.side_effect = RuntimeError("boom")
        self.post({"cmd": "ls"})
        self.assertFalse(state.device.file_txn_lock.locked())


class TestExecRouteGuards(ExecRouteBase):
    def test_disabled_by_default_setting(self):
        state.device.exec_enabled = False
        resp = self.post({"cmd": "ls"})
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "exec_disabled")
        self.fpb.exec_cmd.assert_not_called()

    def test_disabled_status_is_not_auth_status(self):
        # The SDK maps 401/403 to AuthError ("check your token"): not for this
        state.device.exec_enabled = False
        resp = self.post({"cmd": "ls"})
        self.assertNotIn(resp.status_code, (401, 403))

    def test_disabled_when_attribute_missing(self):
        del state.device.exec_enabled
        resp = self.post({"cmd": "ls"})
        self.assertEqual(json.loads(resp.data)["error_code"], "exec_disabled")

    def test_non_json_content_type_rejected(self):
        for ctype in ("text/plain", "application/x-www-form-urlencoded"):
            resp = self.client.post(
                "/api/fpb/exec", data='{"cmd": "ls"}', content_type=ctype
            )
            self.assertEqual(resp.status_code, 415, ctype)
            self.assertEqual(json.loads(resp.data)["error_code"], "bad_request")
        self.fpb.exec_cmd.assert_not_called()

    def test_missing_content_type_rejected(self):
        resp = self.client.post("/api/fpb/exec", data='{"cmd": "ls"}')
        self.assertEqual(resp.status_code, 415)
        self.fpb.exec_cmd.assert_not_called()

    def test_body_must_be_object(self):
        for body in ([1, 2], "ls", 5):
            resp = self.post(body)
            self.assertEqual(resp.status_code, 400)
        self.fpb.exec_cmd.assert_not_called()

    def test_malformed_json(self):
        resp = self.client.post(
            "/api/fpb/exec", data="{nope", content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_or_bad_cmd(self):
        for body in ({}, {"cmd": ""}, {"cmd": "  "}, {"cmd": 5}, {"cmd": None}):
            resp = self.post(body)
            self.assertEqual(resp.status_code, 400, body)
            self.assertEqual(json.loads(resp.data)["error_code"], "bad_request")
        self.fpb.exec_cmd.assert_not_called()

    def test_bad_numeric_arguments(self):
        bodies = (
            {"cmd": "ls", "timeout": 0},
            {"cmd": "ls", "timeout": -1},
            {"cmd": "ls", "timeout": "5"},
            {"cmd": "ls", "ack_timeout": 0},
            {"cmd": "ls", "max_retries": -1},
            {"cmd": "ls", "max_retries": 999},
            {"cmd": "ls", "max_retries": 1.5},
        )
        for body in bodies:
            resp = self.post(body)
            self.assertEqual(resp.status_code, 400, body)
        self.fpb.exec_cmd.assert_not_called()

    def test_validation_happens_before_enabled_check(self):
        state.device.exec_enabled = False
        resp = self.post({"cmd": ""})
        self.assertEqual(resp.status_code, 400)

    def test_busy_with_file_transfer(self):
        state.device.file_txn_lock.acquire()
        try:
            resp = self.post({"cmd": "ls"})
        finally:
            state.device.file_txn_lock.release()
        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["error_code"], "busy")
        self.assertTrue(data["busy"])
        self.fpb.exec_cmd.assert_not_called()


class TestExecRouteFailures(ExecRouteBase):
    def test_worker_not_running(self):
        self.mock_worker.side_effect = lambda device, func, timeout=5.0: False
        resp = self.post({"cmd": "ls"})
        data = json.loads(resp.data)
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "request_failed")
        self.assertIn("worker", data["error"])

    def test_exception_in_exec(self):
        self.fpb.exec_cmd.side_effect = FPBProtocolError("Serial port not connected")
        resp = self.post({"cmd": "ls"})
        data = json.loads(resp.data)
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "request_failed")
        self.assertIn("not connected", data["error"])


if __name__ == "__main__":
    unittest.main()

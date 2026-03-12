#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Authentication middleware tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from app.middleware import init_auth  # noqa: E402


class TestAuthMiddleware(unittest.TestCase):
    """Token authentication middleware tests"""

    def setUp(self):
        self.token = "a3f8b2c1"
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        init_auth(self.app, self.token)

        @self.app.route("/test")
        def test_route():
            return "ok"

        self.client = self.app.test_client()

    def test_localhost_no_token_allowed(self):
        """Localhost requests should pass without token"""
        # Flask test client uses 127.0.0.1 by default
        resp = self.client.get("/test")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"ok")

    def test_non_localhost_no_token_rejected(self):
        """Non-localhost without token should get 403"""
        resp = self.client.get("/test", environ_base={"REMOTE_ADDR": "192.168.1.100"})
        self.assertEqual(resp.status_code, 403)

    def test_non_localhost_wrong_token_rejected(self):
        """Non-localhost with wrong token should get 403"""
        resp = self.client.get(
            "/test?token=wrongtoken",
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_non_localhost_correct_query_token(self):
        """Non-localhost with correct query token should pass"""
        resp = self.client.get(
            f"/test?token={self.token}",
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"ok")

    def test_non_localhost_correct_header_token(self):
        """Non-localhost with correct X-Auth-Token header should pass"""
        resp = self.client.get(
            "/test",
            headers={"X-Auth-Token": self.token},
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_non_localhost_correct_cookie_token(self):
        """Non-localhost with correct cookie token should pass"""
        # First request: authenticate via query token to get cookie
        resp1 = self.client.get(
            f"/test?token={self.token}",
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )
        self.assertEqual(resp1.status_code, 200)
        # Second request: cookie should be sent automatically by test client
        resp2 = self.client.get(
            "/test",
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )
        self.assertEqual(resp2.status_code, 200)

    def test_set_cookie_on_first_query_auth(self):
        """First successful query token auth should set cookie"""
        resp = self.client.get(
            f"/test?token={self.token}",
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )
        self.assertEqual(resp.status_code, 200)
        set_cookie = resp.headers.get("Set-Cookie", "")
        self.assertIn("fpbinject_token", set_cookie)
        self.assertIn(self.token, set_cookie)

    def test_no_set_cookie_when_cookie_exists(self):
        """Should not re-set cookie if already present"""
        # First request: authenticate and get cookie
        self.client.get(
            f"/test?token={self.token}",
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )
        # Second request: cookie already exists, should not re-set
        resp = self.client.get(
            "/test",
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )
        self.assertEqual(resp.status_code, 200)
        set_cookie = resp.headers.get("Set-Cookie", "")
        self.assertNotIn("fpbinject_token", set_cookie)

    def test_security_headers_present(self):
        """Security headers should be added to all responses"""
        resp = self.client.get("/test")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_security_headers_on_403(self):
        """Security headers should be present even on 403"""
        resp = self.client.get("/test", environ_base={"REMOTE_ADDR": "192.168.1.100"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")


class TestNoAuthMode(unittest.TestCase):
    """Test that app works without auth middleware (--no-auth)"""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        # No init_auth called — simulates --no-auth

        @self.app.route("/test")
        def test_route():
            return "ok"

        self.client = self.app.test_client()

    def test_non_localhost_allowed_without_auth(self):
        """Without auth middleware, non-localhost should pass"""
        resp = self.client.get("/test", environ_base={"REMOTE_ADDR": "192.168.1.100"})
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()

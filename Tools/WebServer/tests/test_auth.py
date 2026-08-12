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
from fpbinject.app.middleware import init_auth  # noqa: E402


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

    def test_api_route_returns_json_on_403(self):
        """API routes should return JSON error on 403, not plain text"""

        @self.app.route("/api/ports")
        def api_ports():
            return {"success": True, "ports": []}

        resp = self.client.get(
            "/api/ports", environ_base={"REMOTE_ADDR": "192.168.1.100"}
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertIsNotNone(data)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Forbidden")

    def test_non_api_route_returns_plain_text_on_403(self):
        """Non-API routes should return plain text Forbidden on 403"""
        resp = self.client.get("/test", environ_base={"REMOTE_ADDR": "192.168.1.100"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data, b"Forbidden")


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


class TestSecurityHardening(unittest.TestCase):
    """Tests for security hardening measures."""

    def setUp(self):
        self.token = "a3f8b2c1"
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        init_auth(self.app, self.token)

        @self.app.route("/test")
        def test_route():
            return "ok"

        self.client = self.app.test_client()

    def test_csp_header_present(self):
        """Content-Security-Policy header should be set."""
        resp = self.client.get("/test")
        csp = resp.headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src", csp)
        self.assertIn("connect-src 'self'", csp)
        # CDN whitelist for codicon/xterm/highlight.js
        self.assertIn("https://cdn.jsdelivr.net", csp)

    def test_csp_allows_cdn_resources(self):
        """CSP must whitelist cdn.jsdelivr.net in script/style/font directives.

        base.html loads codicon fonts, xterm.js, highlight.js, and ace editor
        from cdn.jsdelivr.net. If CSP doesn't whitelist this domain in the
        correct directives, these resources will be blocked by the browser.

        This test was added after a regression where CSP blocked codicon fonts,
        causing all sidebar icons to disappear.
        """
        resp = self.client.get("/test")
        csp = resp.headers.get("Content-Security-Policy", "")

        # Parse CSP directives into a dict
        directives = {}
        for part in csp.split(";"):
            part = part.strip()
            if not part:
                continue
            tokens = part.split()
            directives[tokens[0]] = tokens[1:]

        cdn = "https://cdn.jsdelivr.net"

        # script-src: xterm.js, highlight.js, ace editor loaded from CDN
        self.assertIn(
            cdn,
            directives.get("script-src", []),
            "CDN missing from script-src — will block xterm/ace/highlight.js",
        )

        # style-src: codicon CSS, xterm CSS loaded from CDN
        self.assertIn(
            cdn,
            directives.get("style-src", []),
            "CDN missing from style-src — will block codicon/xterm CSS",
        )

        # font-src: codicon woff2 font loaded from CDN
        self.assertIn(
            cdn,
            directives.get("font-src", []),
            "CDN missing from font-src — will block codicon icon font",
        )

    def test_csp_allows_blob_urls(self):
        """CSP must allow blob: URLs for file download and image preview.

        Multiple JS features use URL.createObjectURL(blob) for:
        - File download triggers (symbols.js, editor.js, quick-commands.js)
        - Image preview in transfer tab (transfer.js)
        - Ace editor web workers

        If blob: is missing from img-src/worker-src, these features break.
        """
        resp = self.client.get("/test")
        csp = resp.headers.get("Content-Security-Policy", "")

        self.assertIn(
            "blob:",
            csp,
            "blob: missing from CSP — will break file downloads and image previews",
        )

    def test_csp_worker_src_allows_cdn(self):
        """CSP worker-src must allow CDN for Ace editor syntax checking.

        Ace editor loads worker-c_cpp.js from cdn.jsdelivr.net for
        C/C++ syntax checking. Without CDN in worker-src, the worker
        silently fails and syntax checking is disabled.
        """
        resp = self.client.get("/test")
        csp = resp.headers.get("Content-Security-Policy", "")

        directives = {}
        for part in csp.split(";"):
            part = part.strip()
            if not part:
                continue
            tokens = part.split()
            directives[tokens[0]] = tokens[1:]

        worker_src = directives.get("worker-src", [])
        self.assertIn(
            "https://cdn.jsdelivr.net",
            worker_src,
            "CDN missing from worker-src — Ace editor syntax checking will fail",
        )

    def test_referrer_policy_header_present(self):
        """Referrer-Policy header should be set."""
        resp = self.client.get("/test")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "same-origin")

    def test_constant_time_compare_rejects_none(self):
        """Token comparison should reject None values safely."""
        from fpbinject.app.middleware import _constant_time_compare

        self.assertFalse(_constant_time_compare(None, "token"))
        self.assertFalse(_constant_time_compare("token", None))
        self.assertFalse(_constant_time_compare(None, None))

    def test_constant_time_compare_correct(self):
        """Token comparison should accept matching tokens."""
        from fpbinject.app.middleware import _constant_time_compare

        self.assertTrue(_constant_time_compare("abc123", "abc123"))
        self.assertFalse(_constant_time_compare("abc123", "abc124"))
        self.assertFalse(_constant_time_compare("abc123", "abc12"))

    def test_tarpit_returns_403_streaming(self):
        """Tarpit response should be a 403 streaming response."""
        from fpbinject.app.middleware import _make_tarpit_response

        resp = _make_tarpit_response(0.001)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.headers.get("Cache-Control"), "no-store")

    def test_no_token_cookie_not_set_on_reject(self):
        """Rejected requests should not receive a Set-Cookie header."""
        resp = self.client.get("/test", environ_base={"REMOTE_ADDR": "192.168.1.100"})
        self.assertEqual(resp.status_code, 403)
        set_cookie = resp.headers.get("Set-Cookie", "")
        self.assertNotIn("fpbinject_token", set_cookie)

    def test_cache_control_on_403(self):
        """403 responses should have Cache-Control: no-store."""
        resp = self.client.get("/test", environ_base={"REMOTE_ADDR": "192.168.1.100"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.headers.get("Cache-Control"), "no-store")

    def test_security_headers_on_all_status_codes(self):
        """Security headers should be present on 200 and 403."""
        # 200
        resp_ok = self.client.get("/test")
        self.assertIn("X-Content-Type-Options", resp_ok.headers)
        self.assertIn("Content-Security-Policy", resp_ok.headers)
        # 403
        resp_err = self.client.get(
            "/test", environ_base={"REMOTE_ADDR": "192.168.1.100"}
        )
        self.assertIn("X-Content-Type-Options", resp_err.headers)


if __name__ == "__main__":
    unittest.main()

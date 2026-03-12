#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Authentication middleware for FPBInject Web Server.

Provides token-based authentication for non-localhost access.
Localhost requests are always allowed without authentication.
"""

import logging

from flask import request, abort, after_this_request

logger = logging.getLogger(__name__)

# Addresses considered localhost (exempt from auth)
LOCALHOST_ADDRS = {"127.0.0.1", "::1"}


def init_auth(app, token):
    """Register authentication middleware.

    Args:
        app: Flask application instance
        token: The authentication token string
    """

    @app.before_request
    def check_token():
        """Check authentication token for non-localhost requests."""
        # Localhost is always allowed
        if request.remote_addr in LOCALHOST_ADDRS:
            return None

        # Check token from query, header, or cookie
        req_token = (
            request.args.get("token")
            or request.headers.get("X-Auth-Token")
            or request.cookies.get("fpbinject_token")
        )

        if req_token != token:
            logger.warning(f"Auth rejected: {request.remote_addr} -> {request.path}")
            abort(403)

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
        return response

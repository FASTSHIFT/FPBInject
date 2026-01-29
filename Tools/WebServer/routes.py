#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Flask API routes for FPBInject Web Server.

This module provides:
- Route registration (register_routes)
- Global FPBInject instance management (get_fpb_inject)

API routes have been migrated to app/routes/ blueprints:
- connection.py: Port & Connection APIs
- fpb.py: FPB Inject Operations APIs
- symbols.py: Symbol query APIs
- patch.py: Patch management APIs
- watch.py: File watching APIs
- logs.py: Log APIs
- files.py: File browser APIs

File watcher management:
- services/file_watcher_manager.py
"""

import logging

from flask import render_template

from core.state import state
from fpb_inject import FPBInject

logger = logging.getLogger(__name__)

# Global FPBInject instance
_fpb_inject = None


def get_fpb_inject():
    """Get or create FPBInject instance."""
    global _fpb_inject
    if _fpb_inject is None:
        _fpb_inject = FPBInject(state.device)
        # Initialize toolchain path from device config
        if state.device.toolchain_path:
            _fpb_inject.set_toolchain_path(state.device.toolchain_path)
    return _fpb_inject


def register_routes(app):
    """Register all routes with the Flask app."""
    from app.routes import register_blueprints

    register_blueprints(app)

    @app.route("/")
    def index():
        """Serve the main web interface."""
        return render_template("index.html")

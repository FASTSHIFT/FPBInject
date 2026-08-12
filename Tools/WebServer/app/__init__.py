#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
FPBInject WebServer Flask Application Package.

This package contains the Flask application factory and route blueprints.
"""

import os

from flask import Flask
from flask_cors import CORS

# Locate the package root (holds templates/ and static/) via importlib.resources
# so it resolves correctly whether run from source or an installed wheel.
try:
    from importlib.resources import files as _res_files

    WEBSERVER_DIR = str(_res_files("fpbinject"))
except Exception:  # pragma: no cover - fallback for odd layouts
    WEBSERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        "fpbinject",
        template_folder=os.path.join(WEBSERVER_DIR, "templates"),
        static_folder=os.path.join(WEBSERVER_DIR, "static"),
    )
    CORS(app)

    # Import and register routes
    from fpbinject.routes import register_routes

    register_routes(app)

    return app

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

# Get the directory where WebServer is located
WEBSERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(WEBSERVER_DIR, "templates"),
        static_folder=os.path.join(WEBSERVER_DIR, "static"),
    )
    CORS(app)

    # Import and register routes
    # For now, use the legacy routes module during migration
    from routes import register_routes

    register_routes(app)

    return app

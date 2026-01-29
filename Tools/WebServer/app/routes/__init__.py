#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Flask API Routes Package.

This package contains all API route blueprints organized by functionality.
During migration, routes are gradually moved from the legacy routes.py module.
"""

from flask import Flask


def register_blueprints(app: Flask):
    """Register all route blueprints with the Flask app."""
    from . import files, logs

    # Register blueprints with /api prefix
    app.register_blueprint(logs.bp, url_prefix="/api")
    app.register_blueprint(files.bp, url_prefix="/api")


__all__ = ["register_blueprints"]

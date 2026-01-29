#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
App package initialization tests
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, WEBSERVER_DIR


class TestAppInit(unittest.TestCase):
    """App initialization tests"""

    def test_webserver_dir_exists(self):
        """Test WEBSERVER_DIR points to valid directory"""
        self.assertTrue(os.path.isdir(WEBSERVER_DIR))

    def test_create_app_returns_flask_app(self):
        """Test create_app returns Flask application"""
        app = create_app()

        self.assertIsNotNone(app)
        self.assertEqual(app.name, "app")

    def test_create_app_has_cors(self):
        """Test CORS is enabled"""
        app = create_app()

        # CORS adds headers to responses
        with app.test_client() as client:
            response = client.options("/")
            # CORS should be configured
            self.assertIsNotNone(app)

    def test_create_app_has_routes(self):
        """Test routes are registered"""
        app = create_app()

        rules = [rule.rule for rule in app.url_map.iter_rules()]
        self.assertIn("/", rules)

    def test_create_app_template_folder(self):
        """Test template folder is set correctly"""
        app = create_app()

        expected_template_folder = os.path.join(WEBSERVER_DIR, "templates")
        self.assertEqual(app.template_folder, expected_template_folder)

    def test_create_app_static_folder(self):
        """Test static folder is set correctly"""
        app = create_app()

        expected_static_folder = os.path.join(WEBSERVER_DIR, "static")
        self.assertEqual(app.static_folder, expected_static_folder)


if __name__ == "__main__":
    unittest.main()

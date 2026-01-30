#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Template rendering tests - ensures HTML templates render correctly after modularization.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask


class TestTemplateRendering(unittest.TestCase):
    """Test that Jinja2 templates render correctly."""

    def setUp(self):
        """Set up Flask app for template testing."""
        self.app = Flask(
            __name__,
            template_folder=os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "templates",
            ),
        )
        self.app.config["TESTING"] = True

    def test_index_renders(self):
        """Test that index.html renders without errors."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")
            self.assertIsInstance(html, str)
            self.assertGreater(len(html), 1000)

    def test_base_template_structure(self):
        """Test that base.html includes all required blocks."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            # Check DOCTYPE and basic HTML structure
            self.assertIn("<!doctype html>", html.lower())
            self.assertIn("<html", html)
            self.assertIn("</html>", html)
            self.assertIn("<head>", html)
            self.assertIn("</head>", html)
            self.assertIn("<body>", html)
            self.assertIn("</body>", html)

    def test_titlebar_partial(self):
        """Test that titlebar partial is included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            self.assertIn('class="title-bar"', html)
            self.assertIn("FPBInject Workbench", html)
            self.assertIn('id="clockDisplay"', html)
            self.assertIn('id="themeIcon"', html)

    def test_activitybar_partial(self):
        """Test that activitybar partial is included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            self.assertIn('class="activity-bar"', html)
            self.assertIn('class="activity-item', html)
            self.assertIn("codicon-files", html)
            self.assertIn("codicon-search", html)
            self.assertIn("codicon-settings-gear", html)

    def test_sidebar_partial(self):
        """Test that sidebar partial is included with all sections."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            # Sidebar container
            self.assertIn('class="sidebar"', html)
            self.assertIn('id="sidebar"', html)

            # Connection section
            self.assertIn('id="details-connection"', html)
            self.assertIn('id="portSelect"', html)
            self.assertIn('id="baudrate"', html)
            self.assertIn('id="connectBtn"', html)

            # Device info section
            self.assertIn('id="details-device"', html)
            self.assertIn('id="activeSlotCount"', html)
            self.assertIn('id="memoryInfo"', html)

            # Configuration section
            self.assertIn('id="details-configuration"', html)
            self.assertIn('id="elfPath"', html)
            self.assertIn('id="toolchainPath"', html)
            self.assertIn('id="patchMode"', html)

            # Symbols section
            self.assertIn('id="details-symbols"', html)
            self.assertIn('id="symbolSearch"', html)
            self.assertIn('id="symbolList"', html)

    def test_sidebar_device_slots(self):
        """Test that all 6 FPB slots are rendered via Jinja2 loop."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            # Check all 6 slots exist
            for i in range(6):
                self.assertIn(f'data-slot="{i}"', html)
                self.assertIn(f"Slot {i}", html)
                self.assertIn(f'id="slot{i}Func"', html)

            # Check slot actions
            self.assertIn("fpbReinject", html)
            self.assertIn("fpbUnpatch", html)

    def test_editor_partial(self):
        """Test that editor partial is included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            self.assertIn('class="editor-container"', html)
            self.assertIn('id="editorContainer"', html)
            self.assertIn('id="editorTabsHeader"', html)
            self.assertIn('id="slotSelect"', html)
            self.assertIn('id="injectBtn"', html)
            self.assertIn('id="injectProgress"', html)

    def test_terminal_partial(self):
        """Test that terminal partial is included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            self.assertIn('class="panel-container"', html)
            self.assertIn('id="panelContainer"', html)
            self.assertIn('id="tabBtnTool"', html)
            self.assertIn('id="tabBtnRaw"', html)
            self.assertIn('id="terminalPanelTool"', html)
            self.assertIn('id="terminalPanelRaw"', html)
            self.assertIn('id="terminal-container"', html)
            self.assertIn('id="raw-terminal-container"', html)

    def test_statusbar_partial(self):
        """Test that statusbar partial is included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            self.assertIn('class="status-bar"', html)
            self.assertIn('id="connectionStatus"', html)
            self.assertIn('id="watcherStatus"', html)
            self.assertIn('id="currentSlotDisplay"', html)

    def test_modals_partial(self):
        """Test that modals partial is included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            self.assertIn('id="fileBrowserModal"', html)
            self.assertIn('id="browserPath"', html)
            self.assertIn('id="fileList"', html)
            self.assertIn("closeFileBrowser", html)
            self.assertIn("selectBrowserItem", html)

    def test_scripts_partial(self):
        """Test that all JS modules are included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            # Core modules
            core_modules = [
                "state.js",
                "theme.js",
                "terminal.js",
                "connection.js",
                "logs.js",
                "slots.js",
            ]
            for module in core_modules:
                self.assertIn(f"/static/js/core/{module}", html)

            # UI modules
            ui_modules = ["sash.js", "sidebar.js"]
            for module in ui_modules:
                self.assertIn(f"/static/js/ui/{module}", html)

            # Feature modules
            feature_modules = [
                "fpb.js",
                "patch.js",
                "symbols.js",
                "editor.js",
                "config.js",
                "autoinject.js",
                "filebrowser.js",
            ]
            for module in feature_modules:
                self.assertIn(f"/static/js/features/{module}", html)

            # Main entry point
            self.assertIn("/static/js/app.js", html)

    def test_external_dependencies(self):
        """Test that external CDN dependencies are included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            # CSS
            self.assertIn("workbench.css", html)
            self.assertIn("codicon", html)
            self.assertIn("xterm.css", html)
            self.assertIn("vs2015.min.css", html)

            # JS
            self.assertIn("xterm.min.js", html)
            self.assertIn("xterm-addon-fit", html)
            self.assertIn("highlight.min.js", html)
            self.assertIn("ace.min.js", html)

    def test_sash_elements(self):
        """Test that resize sash elements are included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            self.assertIn('id="sashSidebar"', html)
            self.assertIn('id="sashCorner"', html)
            self.assertIn('id="sashPanel"', html)
            self.assertIn("sash-vertical", html)
            self.assertIn("sash-horizontal", html)
            self.assertIn("sash-corner", html)

    def test_inline_scripts(self):
        """Test that inline initialization scripts are included."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("index.html")

            self.assertIn("updateClock", html)
            self.assertIn("initSashResize", html)
            self.assertIn("loadLayoutPreferences", html)
            self.assertIn("loadThemePreference", html)
            self.assertIn("DOMContentLoaded", html)


class TestPartialTemplates(unittest.TestCase):
    """Test individual partial templates."""

    def setUp(self):
        """Set up Flask app for template testing."""
        self.app = Flask(
            __name__,
            template_folder=os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "templates",
            ),
        )
        self.app.config["TESTING"] = True

    def test_titlebar_standalone(self):
        """Test titlebar partial renders standalone."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("partials/titlebar.html")
            self.assertIn("title-bar", html)
            self.assertIn("FPBInject", html)

    def test_activitybar_standalone(self):
        """Test activitybar partial renders standalone."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("partials/activitybar.html")
            self.assertIn("activity-bar", html)

    def test_statusbar_standalone(self):
        """Test statusbar partial renders standalone."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("partials/statusbar.html")
            self.assertIn("status-bar", html)

    def test_modals_standalone(self):
        """Test modals partial renders standalone."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("partials/modals.html")
            self.assertIn("fileBrowserModal", html)

    def test_editor_standalone(self):
        """Test editor partial renders standalone."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("partials/editor.html")
            self.assertIn("editor-container", html)

    def test_terminal_standalone(self):
        """Test terminal partial renders standalone."""
        with self.app.app_context():
            from flask import render_template

            html = render_template("partials/terminal.html")
            self.assertIn("panel-container", html)


if __name__ == "__main__":
    unittest.main()

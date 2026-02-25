#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for i18n (internationalization) support.

Tests cover:
- Translation file structure and completeness
- Config schema ui_language item
- HTML templates with data-i18n attributes
- i18n.js module structure
"""

import os
import sys
import re
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES_DIR = os.path.join(BASE_DIR, "static", "js", "locales")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
JS_CORE_DIR = os.path.join(BASE_DIR, "static", "js", "core")


class TestTranslationFiles(unittest.TestCase):
    """Test translation file structure and completeness."""

    SUPPORTED_LANGUAGES = ["en", "zh-CN", "zh-TW"]

    def test_all_locale_files_exist(self):
        """Test that all supported language files exist."""
        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            self.assertTrue(
                os.path.exists(filepath), f"Missing translation file: {lang}.js"
            )

    def test_locale_files_not_empty(self):
        """Test that locale files are not empty."""
        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertGreater(
                len(content), 100, f"Translation file {lang}.js is too small"
            )

    def test_locale_files_define_i18n_resources(self):
        """Test that locale files define window.i18nResources."""
        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn(
                "window.i18nResources",
                content,
                f"{lang}.js should define window.i18nResources",
            )
            self.assertIn(
                f"['{lang}']",
                content,
                f"{lang}.js should define resources for '{lang}'",
            )

    def test_locale_files_have_translation_key(self):
        """Test that locale files have translation object."""
        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn(
                "translation:",
                content,
                f"{lang}.js should have translation object",
            )

    def test_required_translation_keys_exist(self):
        """Test that required translation keys exist in all files."""
        required_keys = [
            "sidebar:",
            "config:",
            "connection:",
            "buttons:",
            "tabs:",
            "panels:",
            "statusbar:",
            "messages:",
            "tooltips:",
        ]

        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            for key in required_keys:
                self.assertIn(
                    key,
                    content,
                    f"{lang}.js missing required key: {key}",
                )

    def test_config_labels_keys_match_schema(self):
        """Test that config.labels keys match config_schema.py keys."""
        from core.config_schema import CONFIG_SCHEMA

        schema_keys = {item.key for item in CONFIG_SCHEMA if item.show_in_sidebar}

        # Read English file as reference
        filepath = os.path.join(LOCALES_DIR, "en.js")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract keys from labels section
        labels_match = re.search(r"labels:\s*\{([^}]+)\}", content, re.DOTALL)
        if labels_match:
            labels_content = labels_match.group(1)
            # Extract key names
            label_keys = set(re.findall(r"(\w+):", labels_content))

            # Check that important schema keys have translations
            important_keys = {
                "elf_path",
                "toolchain_path",
                "patch_mode",
                "auto_compile",
                "ui_language",
            }
            for key in important_keys:
                if key in schema_keys:
                    self.assertIn(
                        key,
                        label_keys,
                        f"Missing translation for config key: {key}",
                    )


class TestConfigSchemaI18n(unittest.TestCase):
    """Test config_schema.py i18n related items."""

    def test_ui_language_config_exists(self):
        """Test that ui_language config item exists."""
        from core.config_schema import CONFIG_SCHEMA

        ui_lang_items = [item for item in CONFIG_SCHEMA if item.key == "ui_language"]
        self.assertEqual(len(ui_lang_items), 1, "ui_language config item should exist")

    def test_ui_language_is_select_type(self):
        """Test that ui_language is SELECT type."""
        from core.config_schema import CONFIG_SCHEMA, ConfigType

        ui_lang = next(item for item in CONFIG_SCHEMA if item.key == "ui_language")
        self.assertEqual(ui_lang.config_type, ConfigType.SELECT)

    def test_ui_language_has_all_options(self):
        """Test that ui_language has all supported language options."""
        from core.config_schema import CONFIG_SCHEMA

        ui_lang = next(item for item in CONFIG_SCHEMA if item.key == "ui_language")
        option_values = [opt[0] for opt in ui_lang.options]

        self.assertIn("en", option_values)
        self.assertIn("zh-CN", option_values)
        self.assertIn("zh-TW", option_values)

    def test_ui_language_default_is_english(self):
        """Test that ui_language default is English."""
        from core.config_schema import CONFIG_SCHEMA

        ui_lang = next(item for item in CONFIG_SCHEMA if item.key == "ui_language")
        self.assertEqual(ui_lang.default, "en")

    def test_ui_group_exists(self):
        """Test that UI config group exists."""
        from core.config_schema import ConfigGroup, GROUP_LABELS

        self.assertTrue(hasattr(ConfigGroup, "UI"))
        self.assertIn(ConfigGroup.UI, GROUP_LABELS)

    def test_ui_language_in_ui_group(self):
        """Test that ui_language is in UI group."""
        from core.config_schema import CONFIG_SCHEMA, ConfigGroup

        ui_lang = next(item for item in CONFIG_SCHEMA if item.key == "ui_language")
        self.assertEqual(ui_lang.group, ConfigGroup.UI)


class TestI18nModule(unittest.TestCase):
    """Test i18n.js module structure."""

    def setUp(self):
        """Load i18n.js content."""
        filepath = os.path.join(JS_CORE_DIR, "i18n.js")
        with open(filepath, "r", encoding="utf-8") as f:
            self.content = f.read()

    def test_i18n_module_exists(self):
        """Test that i18n.js exists."""
        filepath = os.path.join(JS_CORE_DIR, "i18n.js")
        self.assertTrue(os.path.exists(filepath))

    def test_init_i18n_function_exists(self):
        """Test that initI18n function is defined."""
        self.assertIn("function initI18n", self.content)
        self.assertIn("async function initI18n", self.content)

    def test_translate_page_function_exists(self):
        """Test that translatePage function is defined."""
        self.assertIn("function translatePage", self.content)

    def test_change_language_function_exists(self):
        """Test that changeLanguage function is defined."""
        self.assertIn("function changeLanguage", self.content)
        self.assertIn("async function changeLanguage", self.content)

    def test_t_function_exists(self):
        """Test that t (translate) function is defined."""
        self.assertIn("function t(", self.content)

    def test_is_i18n_ready_function_exists(self):
        """Test that isI18nReady function is defined."""
        self.assertIn("function isI18nReady", self.content)

    def test_uses_i18next(self):
        """Test that module uses i18next library."""
        self.assertIn("i18next", self.content)
        self.assertIn("i18next.init", self.content)
        self.assertIn("i18next.t", self.content)

    def test_handles_data_i18n_attributes(self):
        """Test that module handles data-i18n attributes."""
        self.assertIn("data-i18n", self.content)
        self.assertIn("querySelectorAll", self.content)

    def test_saves_language_to_localstorage(self):
        """Test that language preference is saved to localStorage."""
        self.assertIn("localStorage", self.content)
        self.assertIn("fpbinject_ui_language", self.content)


class TestI18nextLibrary(unittest.TestCase):
    """Test i18next library file."""

    def test_i18next_library_exists(self):
        """Test that i18next.min.js exists."""
        filepath = os.path.join(BASE_DIR, "static", "js", "lib", "i18next.min.js")
        self.assertTrue(os.path.exists(filepath))

    def test_i18next_library_not_empty(self):
        """Test that i18next library is not empty."""
        filepath = os.path.join(BASE_DIR, "static", "js", "lib", "i18next.min.js")
        size = os.path.getsize(filepath)
        self.assertGreater(size, 10000, "i18next.min.js seems too small")


class TestTemplatesI18nAttributes(unittest.TestCase):
    """Test HTML templates have proper i18n attributes."""

    def test_sidebar_has_i18n_attributes(self):
        """Test that sidebar.html has data-i18n attributes."""
        filepath = os.path.join(TEMPLATES_DIR, "partials", "sidebar.html")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("data-i18n", content)
        self.assertIn('data-i18n="sidebar.connection"', content)

    def test_sidebar_config_has_i18n_attributes(self):
        """Test that sidebar_config.html has data-i18n attributes."""
        filepath = os.path.join(TEMPLATES_DIR, "partials", "sidebar_config.html")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("data-i18n", content)
        self.assertIn('data-i18n="sidebar.config"', content)

    def test_terminal_has_i18n_attributes(self):
        """Test that terminal.html has data-i18n attributes."""
        filepath = os.path.join(TEMPLATES_DIR, "partials", "terminal.html")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("data-i18n", content)
        self.assertIn('data-i18n="tabs.output"', content)
        self.assertIn('data-i18n="tabs.serial"', content)

    def test_statusbar_has_i18n_attributes(self):
        """Test that statusbar.html has data-i18n attributes."""
        filepath = os.path.join(TEMPLATES_DIR, "partials", "statusbar.html")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("data-i18n", content)

    def test_scripts_loads_i18n_modules(self):
        """Test that scripts.html loads i18n modules."""
        filepath = os.path.join(TEMPLATES_DIR, "partials", "scripts.html")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("i18next.min.js", content)
        self.assertIn("i18n.js", content)
        self.assertIn("locales/en.js", content)
        self.assertIn("locales/zh-CN.js", content)
        self.assertIn("locales/zh-TW.js", content)

    def test_scripts_initializes_i18n(self):
        """Test that scripts.html initializes i18n."""
        filepath = os.path.join(TEMPLATES_DIR, "partials", "scripts.html")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("initI18n", content)
        self.assertIn("fpbinject_ui_language", content)


class TestTranslationConsistency(unittest.TestCase):
    """Test translation consistency across languages."""

    SUPPORTED_LANGUAGES = ["en", "zh-CN", "zh-TW"]

    def _extract_keys_from_js(self, content):
        """Extract translation keys from JS file content."""
        # Simple regex to find key patterns like "key:" or "key :"
        keys = set()
        # Match patterns like: word: or word :
        matches = re.findall(r"^\s*(\w+)\s*:", content, re.MULTILINE)
        keys.update(matches)
        return keys

    def _parse_translation_structure(self, content):
        """Parse translation file and extract all keys with their paths."""
        keys = set()

        def extract_nested_keys(text, prefix=""):
            """Recursively extract nested keys."""
            # Match key: value or key: { patterns
            pattern = r"(\w+)\s*:\s*(?:(\{)|['\"]([^'\"]*)['\"]|([^,\n\}]+))"
            for match in re.finditer(pattern, text):
                key = match.group(1)
                full_key = f"{prefix}.{key}" if prefix else key
                if match.group(2):  # Opening brace - nested object
                    # Find matching closing brace
                    start = match.end()
                    depth = 1
                    end = start
                    while depth > 0 and end < len(text):
                        if text[end] == "{":
                            depth += 1
                        elif text[end] == "}":
                            depth -= 1
                        end += 1
                    nested_content = text[start : end - 1]
                    extract_nested_keys(nested_content, full_key)
                else:
                    keys.add(full_key)

        # Find translation object content
        translation_match = re.search(
            r"translation:\s*\{(.+)\}\s*\};", content, re.DOTALL
        )
        if translation_match:
            extract_nested_keys(translation_match.group(1))

        return keys

    def test_all_languages_have_same_top_level_keys(self):
        """Test that all languages have the same top-level structure."""
        all_keys = {}

        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract top-level keys under translation:
            # Handle both with and without trailing commas (formatter may add them)
            translation_match = re.search(
                r"translation:\s*\{(.+)\},?\s*\};", content, re.DOTALL
            )
            if translation_match:
                translation_content = translation_match.group(1)
                # Get first-level keys (handle both 2 and 4 space indentation)
                keys = re.findall(r"^\s{2,4}(\w+):", translation_content, re.MULTILINE)
                all_keys[lang] = set(keys)

        # Compare keys across languages
        if all_keys:
            en_keys = all_keys.get("en", set())
            for lang in ["zh-CN", "zh-TW"]:
                lang_keys = all_keys.get(lang, set())
                missing = en_keys - lang_keys
                self.assertEqual(
                    len(missing),
                    0,
                    f"{lang} missing top-level keys: {missing}",
                )

    def test_all_languages_have_same_nested_keys(self):
        """Test that all languages have the same nested key structure."""
        all_keys = {}

        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract all nested keys
            keys = set()
            # Match patterns like: key: 'value' or key: "value"
            # This captures leaf nodes (actual translations)
            sections = [
                "sidebar",
                "config",
                "connection",
                "buttons",
                "tabs",
                "panels",
                "statusbar",
                "messages",
                "tooltips",
            ]

            for section in sections:
                # Find section content
                section_pattern = rf"{section}:\s*\{{([^}}]+)\}}"
                section_match = re.search(section_pattern, content, re.DOTALL)
                if section_match:
                    section_content = section_match.group(1)
                    # Extract keys from section - match keys at start of line followed by : and quote
                    # This avoids matching text inside string values like 'Watcher: Off'
                    key_matches = re.findall(
                        r"^\s*(\w+)\s*:\s*['\"]", section_content, re.MULTILINE
                    )
                    for key in key_matches:
                        keys.add(f"{section}.{key}")

            all_keys[lang] = keys

        # Compare keys across languages
        en_keys = all_keys.get("en", set())
        for lang in ["zh-CN", "zh-TW"]:
            lang_keys = all_keys.get(lang, set())
            missing = en_keys - lang_keys
            extra = lang_keys - en_keys
            self.assertEqual(
                len(missing),
                0,
                f"{lang} missing keys compared to en: {missing}",
            )
            # Extra keys are warnings, not errors
            if extra:
                print(f"Warning: {lang} has extra keys not in en: {extra}")

    def test_config_labels_consistency(self):
        """Test that config.labels keys are consistent across languages."""
        all_label_keys = {}

        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find labels section
            labels_match = re.search(r"labels:\s*\{([^}]+)\}", content, re.DOTALL)
            if labels_match:
                labels_content = labels_match.group(1)
                keys = set(re.findall(r"(\w+)\s*:", labels_content))
                all_label_keys[lang] = keys

        # Compare
        en_keys = all_label_keys.get("en", set())
        for lang in ["zh-CN", "zh-TW"]:
            lang_keys = all_label_keys.get(lang, set())
            missing = en_keys - lang_keys
            self.assertEqual(
                len(missing),
                0,
                f"{lang} missing config.labels keys: {missing}",
            )

    def test_tooltips_consistency(self):
        """Test that tooltips keys are consistent across languages."""
        all_tooltip_keys = {}

        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find tooltips section - match keys at start of line followed by : and quote
            tooltips_match = re.search(
                r"tooltips:\s*\{(.+?)\n    \}", content, re.DOTALL
            )
            if tooltips_match:
                tooltips_content = tooltips_match.group(1)
                # Only match actual keys (word at start of line followed by : and quote)
                keys = set(
                    re.findall(r"^\s*(\w+)\s*:\s*['\"]", tooltips_content, re.MULTILINE)
                )
                all_tooltip_keys[lang] = keys

        # Compare
        en_keys = all_tooltip_keys.get("en", set())
        for lang in ["zh-CN", "zh-TW"]:
            lang_keys = all_tooltip_keys.get(lang, set())
            missing = en_keys - lang_keys
            self.assertEqual(
                len(missing),
                0,
                f"{lang} missing tooltips keys: {missing}",
            )


class TestDataI18nAttributesCoverage(unittest.TestCase):
    """Test that all data-i18n attributes have corresponding translations."""

    SUPPORTED_LANGUAGES = ["en", "zh-CN", "zh-TW"]

    def _get_all_data_i18n_keys(self):
        """Extract all data-i18n attribute values from HTML templates."""
        keys = set()
        partials_dir = os.path.join(TEMPLATES_DIR, "partials")

        for filename in os.listdir(partials_dir):
            if filename.endswith(".html"):
                filepath = os.path.join(partials_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Match data-i18n="key" or data-i18n='key'
                matches = re.findall(r'data-i18n=["\']([^"\']+)["\']', content)
                for match in matches:
                    # Handle multiple keys separated by ;
                    for key in match.split(";"):
                        # Handle attribute translations like [title]key
                        if key.startswith("["):
                            attr_match = re.match(r"\[(\w+)\](.+)", key)
                            if attr_match:
                                keys.add(attr_match.group(2))
                        else:
                            keys.add(key)

        return keys

    def _get_translation_keys_from_file(self, lang):
        """Extract all translation keys from a locale file."""
        filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        keys = set()

        # Simpler approach: find all nested key paths by analyzing the structure
        # Match patterns like: section: { key: 'value' } or section: { nested: { key: 'value' } }
        lines = content.split("\n")
        current_path = []

        for line in lines:
            stripped = line.strip()

            # Skip comments
            if stripped.startswith("//"):
                continue

            # Track opening braces with key names
            key_with_brace = re.match(r"(\w+)\s*:\s*\{", stripped)
            if key_with_brace:
                current_path.append(key_with_brace.group(1))
                continue

            # Track closing braces
            if stripped.startswith("}"):
                if current_path:
                    current_path.pop()
                continue

            # Match leaf values: key: 'value' or key: "value"
            # Also match keys that may have value on next line: key:
            leaf_match = re.match(r"(\w+)\s*:\s*['\"]", stripped)
            if not leaf_match:
                # Try matching key with value on next line (key:)
                leaf_match = re.match(r"(\w+)\s*:$", stripped)
            if leaf_match and current_path:
                key = leaf_match.group(1)
                # Skip 'translation' as it's the root
                path = [p for p in current_path if p != "translation"]
                if path:
                    full_key = ".".join(path) + "." + key
                    keys.add(full_key)

        return keys

    def test_all_data_i18n_keys_have_translations(self):
        """Test that all data-i18n keys used in templates have translations."""
        used_keys = self._get_all_data_i18n_keys()

        for lang in self.SUPPORTED_LANGUAGES:
            available_keys = self._get_translation_keys_from_file(lang)

            missing = []
            for key in used_keys:
                # Check if key or any parent key exists
                key_found = False
                for avail_key in available_keys:
                    if avail_key == key or avail_key.startswith(f"{key}."):
                        key_found = True
                        break
                if not key_found:
                    missing.append(key)

            self.assertEqual(
                len(missing),
                0,
                f"{lang} missing translations for data-i18n keys: {missing}",
            )


class TestHardcodedTextDetection(unittest.TestCase):
    """Test for hardcoded English text that should be translated."""

    # Common English words/phrases that should be translated
    HARDCODED_PATTERNS = [
        # Section headers (uppercase)
        r">([A-Z][A-Z\s]{3,})<",
        # Button text
        r">\s*(Connect|Disconnect|Save|Cancel|Clear|Refresh|Add|Remove|Start|Stop|Inject|Compile|Browse)\s*<",
        # Common UI text
        r">\s*(No file open|Click .+ to|Empty|Loading|Error|Success|Warning)\s*<",
        # Slot text
        r">\s*(Slot \d+)\s*<",
        # File transfer text
        r">\s*(File|Folder|Download|Upload)\s*<",
    ]

    # Whitelist - text that's OK to be hardcoded
    WHITELIST = [
        "UTF-8",
        "C",
        "FPBInject",
        "Workbench",
        "FASTSHIFT",
        "VIFEX",
        # Technical terms
        "ELF",
        "CRC",
        "FPB",
        "RAM",
        "ROM",
        # Version strings
        r"v\d+\.\d+",
    ]

    def _is_whitelisted(self, text):
        """Check if text is in whitelist."""
        text = text.strip()
        for pattern in self.WHITELIST:
            if pattern == text:
                return True
            if pattern.startswith("r") or "\\" in pattern:
                # It's a regex pattern
                try:
                    if re.match(pattern.lstrip("r"), text):
                        return True
                except re.error:
                    pass
        return False

    def test_scan_hardcoded_text_in_templates(self):
        """Scan templates for hardcoded English text that needs translation."""
        partials_dir = os.path.join(TEMPLATES_DIR, "partials")
        issues = []

        for filename in os.listdir(partials_dir):
            if not filename.endswith(".html"):
                continue

            filepath = os.path.join(partials_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Skip elements that already have data-i18n
            # Remove data-i18n elements from consideration
            content_without_i18n = re.sub(
                r"<[^>]+data-i18n=[^>]+>[^<]*</[^>]+>", "", content
            )

            for pattern in self.HARDCODED_PATTERNS:
                matches = re.findall(pattern, content_without_i18n, re.IGNORECASE)
                for match in matches:
                    if not self._is_whitelisted(match):
                        issues.append(f"{filename}: '{match}'")

        # Report issues but don't fail - this is informational
        if issues:
            print(f"\n⚠️  Potential hardcoded text found ({len(issues)} items):")
            for issue in issues[:20]:  # Limit output
                print(f"   - {issue}")
            if len(issues) > 20:
                print(f"   ... and {len(issues) - 20} more")

    def test_buttons_without_i18n(self):
        """Find buttons without data-i18n attributes."""
        partials_dir = os.path.join(TEMPLATES_DIR, "partials")
        issues = []

        for filename in os.listdir(partials_dir):
            if not filename.endswith(".html"):
                continue

            filepath = os.path.join(partials_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find buttons with text content but no data-i18n
            button_pattern = r"<button[^>]*>([^<]+)</button>"
            for match in re.finditer(button_pattern, content):
                button_tag = match.group(0)
                button_text = match.group(1).strip()

                # Skip if has data-i18n or is icon-only
                if "data-i18n" in button_tag:
                    continue
                if not button_text or button_text.startswith("<"):
                    continue
                if self._is_whitelisted(button_text):
                    continue

                issues.append(f"{filename}: button '{button_text}'")

        if issues:
            print(f"\n⚠️  Buttons without i18n ({len(issues)} items):")
            for issue in issues[:10]:
                print(f"   - {issue}")

    def test_js_hardcoded_ui_strings(self):
        """Scan JS files for hardcoded UI strings that should use t()."""
        issues = []

        # Patterns for hardcoded strings in JS that should be translated
        js_hardcoded_patterns = [
            # textContent/innerText assignments with English text
            (r"\.textContent\s*=\s*['\"]([A-Z][a-zA-Z\s\.]+)['\"]", "textContent"),
            (r"\.innerText\s*=\s*['\"]([A-Z][a-zA-Z\s\.]+)['\"]", "innerText"),
            # innerHTML with simple text (not HTML)
            (r"\.innerHTML\s*=\s*['\"]([A-Z][a-zA-Z\s]+)['\"]", "innerHTML"),
        ]

        # Whitelist for JS - technical terms and acceptable hardcoded text
        js_whitelist = [
            "Connected",
            "Disconnected",
            "Connect",
            "Disconnect",
            "Connecting",
            "Empty",
            "Used",
            "Bytes",
            "Error",
            "Success",
            "Failed",
            "Loading",
            "FPB v2 only",
            "Retry",
            "Connection failed",
        ]

        for filename in os.listdir(JS_CORE_DIR):
            if not filename.endswith(".js"):
                continue
            # Skip i18n.js and locale files
            if filename in ["i18n.js"]:
                continue

            filepath = os.path.join(JS_CORE_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                # Skip lines that already use t() function
                if "t(" in line:
                    continue

                for pattern, pattern_type in js_hardcoded_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        match_text = match.strip()
                        # Skip if whitelisted or too short
                        if match_text in js_whitelist or len(match_text) < 3:
                            continue
                        # Skip if it's a variable or contains special chars
                        if "${" in match_text or "{{" in match_text:
                            continue
                        issues.append(
                            f"{filename}:{line_num} ({pattern_type}): '{match_text}'"
                        )

        # This test should FAIL if there are hardcoded strings
        self.assertEqual(
            len(issues),
            0,
            f"\n❌ Found {len(issues)} hardcoded UI strings in JS files that should use t():\n"
            + "\n".join(f"   - {issue}" for issue in issues[:30])
            + (f"\n   ... and {len(issues) - 30} more" if len(issues) > 30 else ""),
        )

    def test_html_elements_with_text_need_i18n(self):
        """Scan HTML for elements with visible text that lack data-i18n."""
        partials_dir = os.path.join(TEMPLATES_DIR, "partials")
        issues = []

        # Elements that typically contain translatable text
        text_elements = [
            (r"<button[^>]*>([^<]+)</button>", "button"),
            (r"<span[^>]*>([^<]+)</span>", "span"),
            (r"<label[^>]*>([^<]+)</label>", "label"),
            (r"<h[1-6][^>]*>([^<]+)</h[1-6]>", "heading"),
            (r"<p[^>]*>([^<]+)</p>", "paragraph"),
            (r"<div[^>]*>([^<]+)</div>", "div"),
            (r"<a[^>]*>([^<]+)</a>", "link"),
            (r"<option[^>]*>([^<]+)</option>", "option"),
            (r"<th[^>]*>([^<]+)</th>", "th"),
            (r"<td[^>]*>([^<]+)</td>", "td"),
        ]

        # Whitelist for HTML text
        html_text_whitelist = [
            # Technical/brand terms
            "FPBInject",
            "Workbench",
            "FASTSHIFT",
            "VIFEX",
            "UTF-8",
            "FPBInject Workbench",
            "FASTSHIFT (VIFEX)",
            # Technical abbreviations
            "ELF",
            "CRC",
            "FPB",
            "RAM",
            "ROM",
            "TX",
            "RX",
            # Numbers and symbols only
        ]

        for filename in os.listdir(partials_dir):
            if not filename.endswith(".html"):
                continue

            filepath = os.path.join(partials_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            for pattern, elem_type in text_elements:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    full_tag = match.group(0)
                    text = match.group(1).strip()

                    # Skip if already has data-i18n
                    if "data-i18n" in full_tag:
                        continue

                    # Skip empty, whitespace-only, or template variables
                    if not text or text.startswith("{{") or text.startswith("{%"):
                        continue

                    # Skip if whitelisted
                    if text in html_text_whitelist:
                        continue

                    # Skip if it's just numbers, symbols, or very short
                    if len(text) < 2 or re.match(
                        r"^[\d\s\-\+\*\/\.\,\:\;\!\?\@\#\$\%\^\&\(\)]+$", text
                    ):
                        continue

                    # Skip if no alphabetic characters (pure symbols/numbers)
                    if not re.search(r"[a-zA-Z]", text):
                        continue

                    # Check if it looks like English text that needs translation
                    # (contains at least one word with 3+ letters)
                    if re.search(r"[a-zA-Z]{3,}", text):
                        issues.append(f"{filename} ({elem_type}): '{text}'")

        # This test should FAIL if there are untranslated elements
        self.assertEqual(
            len(issues),
            0,
            f"\n❌ Found {len(issues)} HTML elements with text but no data-i18n:\n"
            + "\n".join(f"   - {issue}" for issue in issues[:30])
            + (f"\n   ... and {len(issues) - 30} more" if len(issues) > 30 else ""),
        )

    def test_html_title_attributes_need_i18n(self):
        """Scan HTML for title attributes that lack data-i18n translation."""
        partials_dir = os.path.join(TEMPLATES_DIR, "partials")
        issues = []

        # Whitelist for title attributes that don't need translation
        title_whitelist = [
            # Technical terms
            "UTF-8",
            "CRC",
            "FPB",
            "RAM",
            "ROM",
        ]

        for filename in os.listdir(partials_dir):
            if not filename.endswith(".html"):
                continue

            filepath = os.path.join(partials_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all HTML elements with title attribute
            # Match opening tags with title="..."
            element_pattern = r'<[^>]*title="([^"]+)"[^>]*>'
            for match in re.finditer(element_pattern, content):
                title_text = match.group(1).strip()
                full_tag = match.group(0)

                # Check if there's a data-i18n with [title] in the same element
                has_i18n_title = re.search(r'data-i18n="[^"]*\[title\][^"]*"', full_tag)

                if has_i18n_title:
                    continue

                # Skip if whitelisted
                if title_text in title_whitelist:
                    continue

                # Skip if no alphabetic characters
                if not re.search(r"[a-zA-Z]{3,}", title_text):
                    continue

                issues.append(f'{filename}: title="{title_text}"')

        # This test should FAIL if there are untranslated title attributes
        self.assertEqual(
            len(issues),
            0,
            f"\n❌ Found {len(issues)} title attributes without i18n translation:\n"
            + "\n".join(f"   - {issue}" for issue in issues[:30])
            + (f"\n   ... and {len(issues) - 30} more" if len(issues) > 30 else ""),
        )

    def test_html_placeholder_attributes_need_i18n(self):
        """Scan HTML for placeholder attributes that lack data-i18n translation."""
        partials_dir = os.path.join(TEMPLATES_DIR, "partials")
        issues = []

        # Whitelist for placeholder attributes that don't need translation
        placeholder_whitelist = [
            # Technical terms or paths
            "/data",
            "/",
            "128",
        ]

        for filename in os.listdir(partials_dir):
            if not filename.endswith(".html"):
                continue

            filepath = os.path.join(partials_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all HTML elements with placeholder attribute
            element_pattern = r'<[^>]*placeholder="([^"]+)"[^>]*>'
            for match in re.finditer(element_pattern, content):
                placeholder_text = match.group(1).strip()
                full_tag = match.group(0)

                # Check if there's a data-i18n with [placeholder] in the same element
                has_i18n_placeholder = re.search(
                    r'data-i18n="[^"]*\[placeholder\][^"]*"', full_tag
                )

                if has_i18n_placeholder:
                    continue

                # Skip if whitelisted
                if placeholder_text in placeholder_whitelist:
                    continue

                # Skip if no alphabetic characters
                if not re.search(r"[a-zA-Z]{3,}", placeholder_text):
                    continue

                issues.append(f'{filename}: placeholder="{placeholder_text}"')

        # This test should FAIL if there are untranslated placeholder attributes
        self.assertEqual(
            len(issues),
            0,
            f"\n❌ Found {len(issues)} placeholder attributes without i18n translation:\n"
            + "\n".join(f"   - {issue}" for issue in issues[:30])
            + (f"\n   ... and {len(issues) - 30} more" if len(issues) > 30 else ""),
        )


class TestTranslationCompleteness(unittest.TestCase):
    """Test that translations are complete and not empty."""

    SUPPORTED_LANGUAGES = ["en", "zh-CN", "zh-TW"]

    def test_no_empty_translations(self):
        """Test that no translation values are empty strings."""
        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find empty string values
            empty_matches = re.findall(r"(\w+):\s*['\"]['\"]", content)
            self.assertEqual(
                len(empty_matches),
                0,
                f"{lang} has empty translations: {empty_matches}",
            )

    def test_no_placeholder_translations(self):
        """Test that no translations contain placeholder text."""
        placeholders = ["TODO", "FIXME", "XXX", "TRANSLATE"]

        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract only translation values (quoted strings after colons)
            # This avoids false positives from key names like 'search_placeholder'
            translation_values = re.findall(r":\s*['\"]([^'\"]+)['\"]", content)

            for value in translation_values:
                for placeholder in placeholders:
                    self.assertNotIn(
                        placeholder,
                        value.upper(),
                        f"{lang} contains placeholder '{placeholder}' in value: {value}",
                    )

    def test_chinese_translations_have_chinese_chars(self):
        """Test that Chinese translations actually contain Chinese characters."""
        chinese_pattern = re.compile(r"[\u4e00-\u9fff]")

        for lang in ["zh-CN", "zh-TW"]:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all translation values
            values = re.findall(r":\s*['\"]([^'\"]+)['\"]", content)

            # At least 50% should contain Chinese characters
            chinese_count = sum(1 for v in values if chinese_pattern.search(v))
            total_count = len(values)

            self.assertGreater(
                chinese_count / total_count if total_count > 0 else 0,
                0.5,
                f"{lang} should have mostly Chinese translations, "
                f"but only {chinese_count}/{total_count} contain Chinese",
            )


class TestConfigSchemaJsI18nIntegration(unittest.TestCase):
    """Test config-schema.js i18n integration."""

    def setUp(self):
        """Load config-schema.js content."""
        filepath = os.path.join(JS_CORE_DIR, "config-schema.js")
        with open(filepath, "r", encoding="utf-8") as f:
            self.content = f.read()

    def test_get_config_label_function_exists(self):
        """Test that getConfigLabel function exists."""
        self.assertIn("function getConfigLabel", self.content)

    def test_get_config_tooltip_function_exists(self):
        """Test that getConfigTooltip function exists."""
        self.assertIn("function getConfigTooltip", self.content)

    def test_get_group_label_function_exists(self):
        """Test that getGroupLabel function exists."""
        self.assertIn("function getGroupLabel", self.content)

    def test_uses_i18n_functions(self):
        """Test that config-schema.js uses i18n functions."""
        self.assertIn("isI18nReady", self.content)
        self.assertIn("t(", self.content)


class TestFeaturesConfigI18nIntegration(unittest.TestCase):
    """Test features/config.js i18n integration."""

    def setUp(self):
        """Load config.js content."""
        filepath = os.path.join(BASE_DIR, "static", "js", "features", "config.js")
        with open(filepath, "r", encoding="utf-8") as f:
            self.content = f.read()

    def test_handles_language_change(self):
        """Test that config.js handles language change."""
        self.assertIn("changeLanguage", self.content)
        self.assertIn("ui_language", self.content)

    def test_syncs_language_from_server(self):
        """Test that config.js syncs language from server config."""
        self.assertIn("fpbinject_ui_language", self.content)


class TestDevicePopupMessages(unittest.TestCase):
    """Test device popup message translations for fpbPing and fpbInfo."""

    SUPPORTED_LANGUAGES = ["en", "zh-CN", "zh-TW"]

    # Required message keys for device popup feedback
    REQUIRED_MESSAGE_KEYS = [
        "not_connected",
        "ping_success",
        "device_responding",
        "ping_failed",
        "device_not_responding",
        "error",
        "device_info_success",
        "device_info_failed",
        "fpb_version",
        "build_time",
        "memory_used",
        "slots_used",
        "unknown_error",
        "build_time_mismatch",
        "build_time_mismatch_desc",
        "build_time_mismatch_warn",
        "device_firmware",
        "elf_file",
        "build_time_mismatch_hint",
        # Backend disconnection
        "backend_disconnected",
        "backend_restart_hint",
        # CRC errors
        "crc_verification_failed",
        "file_may_be_corrupted",
        # Transfer errors
        "upload_failed",
        "download_failed",
        "transfer_stats",
        "retries",
        "crc_errors",
        "timeout_errors",
        "packet_loss",
        # Delete confirmation
        "confirm_delete",
        "directory",
        # Injection failures
        "injection_failed_count",
        "failed_functions",
        "slots_full_hint",
        "clear_slots_hint",
        # Serial test
        "serial_test_complete",
        "current_chunk_size",
        "recommended_chunk_size",
        "apply_recommended_size",
        # ELF watcher
        "elf_file_changed",
        "reload_symbols_now",
        # Slot warnings
        "all_slots_occupied",
        "current_slots",
        "clear_slots_before_inject",
        "use_clear_all_hint",
        "click_ok_to_open_device",
        "slot_occupied_by",
        "overwrite_slot",
        # Clear all slots
        "confirm_clear_all_slots",
        "unpatch_all_warning",
    ]

    def test_all_device_message_keys_exist(self):
        """Test that all device popup message keys exist in all locale files."""
        for lang in self.SUPPORTED_LANGUAGES:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            for key in self.REQUIRED_MESSAGE_KEYS:
                self.assertIn(
                    f"{key}:",
                    content,
                    f"{lang}.js missing message key: {key}",
                )

    def test_fpb_js_uses_t_function_for_popups(self):
        """Test that fpb.js uses t() function for popup messages."""
        filepath = os.path.join(BASE_DIR, "static", "js", "features", "fpb.js")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that fpbPing uses t() for messages
        self.assertIn("t('messages.not_connected'", content)
        self.assertIn("t('messages.ping_success'", content)
        self.assertIn("t('messages.ping_failed'", content)

        # Check that fpbInfo uses t() for messages
        self.assertIn("t('messages.device_info_success'", content)
        self.assertIn("t('messages.device_info_failed'", content)
        self.assertIn("t('messages.fpb_version'", content)
        self.assertIn("t('messages.build_time'", content)
        self.assertIn("t('messages.memory_used'", content)
        self.assertIn("t('messages.slots_used'", content)

    def test_fpb_ping_has_alert_popup(self):
        """Test that fpbPing function has alert popup for feedback."""
        filepath = os.path.join(BASE_DIR, "static", "js", "features", "fpb.js")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Find fpbPing function and check it has alert calls
        fpb_ping_match = re.search(
            r"async function fpbPing\(\).*?^}",
            content,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(fpb_ping_match, "fpbPing function not found")

        fpb_ping_content = fpb_ping_match.group(0)
        # Should have alert for success, failure, and error cases
        alert_count = fpb_ping_content.count("alert(")
        self.assertGreaterEqual(
            alert_count, 3, "fpbPing should have at least 3 alert popups"
        )

    def test_fpb_info_has_alert_popup(self):
        """Test that fpbInfo function has alert popup for feedback."""
        filepath = os.path.join(BASE_DIR, "static", "js", "features", "fpb.js")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Find fpbInfo function and check it has alert calls
        fpb_info_match = re.search(
            r"async function fpbInfo\(\).*?^}",
            content,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(fpb_info_match, "fpbInfo function not found")

        fpb_info_content = fpb_info_match.group(0)
        # Should have alert for success, failure, and error cases
        alert_count = fpb_info_content.count("alert(")
        self.assertGreaterEqual(
            alert_count, 3, "fpbInfo should have at least 3 alert popups"
        )

    def test_chinese_translations_for_device_messages(self):
        """Test that Chinese locale files have proper translations for device messages."""
        chinese_pattern = re.compile(r"[\u4e00-\u9fff]")

        for lang in ["zh-CN", "zh-TW"]:
            filepath = os.path.join(LOCALES_DIR, f"{lang}.js")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Check that key device messages have Chinese translations
            for key in [
                "not_connected",
                "ping_success",
                "ping_failed",
                "device_info_success",
            ]:
                # Find the translation value for this key
                pattern = rf"{key}:\s*['\"]([^'\"]+)['\"]"
                match = re.search(pattern, content)
                self.assertIsNotNone(match, f"{lang}.js missing translation for {key}")
                if match:
                    value = match.group(1)
                    self.assertTrue(
                        chinese_pattern.search(value),
                        f"{lang}.js: {key} should have Chinese translation, got: {value}",
                    )


class TestHardcodedTextInPopups(unittest.TestCase):
    """Test that JS files don't have hardcoded English text in alert/confirm popups."""

    JS_FILES_TO_CHECK = [
        "static/js/core/connection.js",
        "static/js/core/slots.js",
        "static/js/features/fpb.js",
        "static/js/features/transfer.js",
        "static/js/features/patch.js",
        "static/js/features/elfwatcher.js",
        "static/js/features/autoinject.js",
    ]

    # Patterns that indicate hardcoded English text (should use t() instead)
    HARDCODED_PATTERNS = [
        # alert/confirm with plain English strings (not using t())
        r"alert\(\s*['\"][A-Z][a-z]",  # alert('Something...
        r"confirm\(\s*['\"][A-Z][a-z]",  # confirm('Something...
        r"alert\(\s*`[A-Z][a-z]",  # alert(`Something...
        r"confirm\(\s*`[A-Z][a-z]",  # confirm(`Something...
    ]

    # Exceptions - patterns that are allowed (e.g., already using t())
    ALLOWED_PATTERNS = [
        r"alert\(\s*`?\$\{t\(",  # alert(`${t(...
        r"confirm\(\s*`?\$\{t\(",  # confirm(`${t(...
        r"alert\(\s*t\(",  # alert(t(...
        r"confirm\(\s*t\(",  # confirm(t(...
        r"alert\(\s*message",  # alert(message) - variable
        r"alert\(\s*infoLines",  # alert(infoLines...) - variable
    ]

    def test_no_hardcoded_english_in_alerts(self):
        """Test that alert() calls use t() for translations."""
        for js_file in self.JS_FILES_TO_CHECK:
            filepath = os.path.join(BASE_DIR, js_file)
            if not os.path.exists(filepath):
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all alert( calls
            alert_matches = list(re.finditer(r"alert\([^)]+\)", content, re.DOTALL))

            for match in alert_matches:
                alert_text = match.group(0)
                line_num = content[: match.start()].count("\n") + 1

                # Check if it's using t() function
                uses_t_function = (
                    "t('" in alert_text
                    or 't("' in alert_text
                    or "${t(" in alert_text
                    or "alert(message" in alert_text
                    or "alert(infoLines" in alert_text
                )

                # Check for hardcoded English (starts with capital letter after quote)
                has_hardcoded = bool(
                    re.search(r"alert\(\s*['\"`][A-Z][a-z]", alert_text)
                )

                if has_hardcoded and not uses_t_function:
                    self.fail(
                        f"{js_file}:{line_num} has hardcoded English in alert(): "
                        f"{alert_text[:80]}..."
                    )

    def test_no_hardcoded_english_in_confirms(self):
        """Test that confirm() calls use t() for translations."""
        for js_file in self.JS_FILES_TO_CHECK:
            filepath = os.path.join(BASE_DIR, js_file)
            if not os.path.exists(filepath):
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all confirm( calls
            confirm_matches = list(re.finditer(r"confirm\([^;]+\)", content, re.DOTALL))

            for match in confirm_matches:
                confirm_text = match.group(0)
                line_num = content[: match.start()].count("\n") + 1

                # Check if it's using t() function
                uses_t_function = (
                    "t('" in confirm_text
                    or 't("' in confirm_text
                    or "${t(" in confirm_text
                )

                # Check for hardcoded English (starts with capital letter after quote)
                has_hardcoded = bool(
                    re.search(r"confirm\(\s*['\"`][A-Z][a-z]", confirm_text)
                )

                if has_hardcoded and not uses_t_function:
                    self.fail(
                        f"{js_file}:{line_num} has hardcoded English in confirm(): "
                        f"{confirm_text[:80]}..."
                    )

    def test_popup_messages_use_t_function(self):
        """Test that all popup-related JS files use t() for user-facing messages."""
        for js_file in self.JS_FILES_TO_CHECK:
            filepath = os.path.join(BASE_DIR, js_file)
            if not os.path.exists(filepath):
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # File should import/use t() function if it has alert/confirm
            has_popups = "alert(" in content or "confirm(" in content
            uses_t = "t('" in content or 't("' in content

            if has_popups:
                self.assertTrue(
                    uses_t,
                    f"{js_file} has alert/confirm but doesn't use t() for i18n",
                )


if __name__ == "__main__":
    unittest.main()

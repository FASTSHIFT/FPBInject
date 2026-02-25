#!/usr/bin/env python3

"""Tests for config_schema module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_schema import (  # noqa: E402
    CONFIG_SCHEMA,
    ConfigItem,
    ConfigType,
    ConfigGroup,
    GROUP_LABELS,
    PERSISTENT_KEYS,
    get_persistent_keys,
    get_config_defaults,
    get_schema_by_key,
    get_sidebar_schema,
    get_schema_by_group,
    get_schema_as_dict,
)


class TestConfigSchema(unittest.TestCase):
    """Test CONFIG_SCHEMA definition."""

    def test_schema_not_empty(self):
        """Test that schema has items."""
        self.assertGreater(len(CONFIG_SCHEMA), 0)

    def test_all_items_are_config_items(self):
        """Test that all schema items are ConfigItem instances."""
        for item in CONFIG_SCHEMA:
            self.assertIsInstance(item, ConfigItem)

    def test_all_items_have_required_fields(self):
        """Test that all items have required fields."""
        for item in CONFIG_SCHEMA:
            self.assertIsInstance(item.key, str)
            self.assertGreater(len(item.key), 0)
            self.assertIsInstance(item.label, str)
            self.assertIsInstance(item.group, ConfigGroup)
            self.assertIsInstance(item.config_type, ConfigType)

    def test_unique_keys(self):
        """Test that all keys are unique."""
        keys = [item.key for item in CONFIG_SCHEMA]
        self.assertEqual(len(keys), len(set(keys)))

    def test_all_groups_have_labels(self):
        """Test that all groups have display labels."""
        for group in ConfigGroup:
            self.assertIn(group, GROUP_LABELS)

    def test_select_items_have_options(self):
        """Test that SELECT type items have options."""
        for item in CONFIG_SCHEMA:
            if item.config_type == ConfigType.SELECT:
                self.assertGreater(
                    len(item.options), 0, f"SELECT item {item.key} has no options"
                )

    def test_number_items_have_constraints(self):
        """Test that NUMBER type items have min/max/step."""
        for item in CONFIG_SCHEMA:
            if item.config_type == ConfigType.NUMBER and item.show_in_sidebar:
                # At least one constraint should be set for sidebar items
                has_constraint = (
                    item.min_value is not None
                    or item.max_value is not None
                    or item.step is not None
                )
                # baudrate is an exception (not shown in sidebar)
                if item.key != "baudrate":
                    self.assertTrue(
                        has_constraint or not item.show_in_sidebar,
                        f"NUMBER item {item.key} should have constraints",
                    )

    def test_depends_on_references_valid_key(self):
        """Test that depends_on references existing keys."""
        all_keys = {item.key for item in CONFIG_SCHEMA}
        for item in CONFIG_SCHEMA:
            if item.depends_on:
                self.assertIn(
                    item.depends_on,
                    all_keys,
                    f"Item {item.key} depends on non-existent key {item.depends_on}",
                )


class TestConfigItem(unittest.TestCase):
    """Test ConfigItem class."""

    def test_to_dict(self):
        """Test ConfigItem.to_dict() method."""
        item = ConfigItem(
            key="test_key",
            label="Test Label",
            group=ConfigGroup.PROJECT,
            config_type=ConfigType.STRING,
            default="default_value",
            tooltip="Test tooltip",
        )
        result = item.to_dict()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["key"], "test_key")
        self.assertEqual(result["label"], "Test Label")
        self.assertEqual(result["group"], "project")  # Enum converted to string
        self.assertEqual(result["config_type"], "string")  # Enum converted to string
        self.assertEqual(result["default"], "default_value")
        self.assertEqual(result["tooltip"], "Test tooltip")

    def test_to_dict_with_options(self):
        """Test ConfigItem.to_dict() with select options."""
        item = ConfigItem(
            key="select_key",
            label="Select",
            group=ConfigGroup.INJECT,
            config_type=ConfigType.SELECT,
            default="opt1",
            options=[("opt1", "Option 1"), ("opt2", "Option 2")],
        )
        result = item.to_dict()

        self.assertEqual(
            result["options"], [("opt1", "Option 1"), ("opt2", "Option 2")]
        )

    def test_to_dict_with_link(self):
        """Test ConfigItem.to_dict() with external link."""
        item = ConfigItem(
            key="tool_path",
            label="Tool Path",
            group=ConfigGroup.TOOLS,
            config_type=ConfigType.DIR_PATH,
            default="",
            link="https://github.com/example/tool",
        )
        result = item.to_dict()

        self.assertEqual(result["link"], "https://github.com/example/tool")

    def test_link_field_default_empty(self):
        """Test ConfigItem link field defaults to empty string."""
        item = ConfigItem(
            key="test_key",
            label="Test",
            group=ConfigGroup.PROJECT,
            config_type=ConfigType.STRING,
            default="",
        )
        self.assertEqual(item.link, "")


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""

    def test_get_persistent_keys(self):
        """Test get_persistent_keys returns all keys."""
        keys = get_persistent_keys()
        self.assertIsInstance(keys, list)
        self.assertEqual(len(keys), len(CONFIG_SCHEMA))
        for key in keys:
            self.assertIsInstance(key, str)

    def test_persistent_keys_matches_function(self):
        """Test PERSISTENT_KEYS matches get_persistent_keys()."""
        self.assertEqual(PERSISTENT_KEYS, get_persistent_keys())

    def test_get_config_defaults(self):
        """Test get_config_defaults returns all defaults."""
        defaults = get_config_defaults()
        self.assertIsInstance(defaults, dict)
        self.assertEqual(len(defaults), len(CONFIG_SCHEMA))

        # Check some known defaults
        self.assertEqual(defaults["chunk_size"], 128)
        self.assertEqual(defaults["patch_mode"], "trampoline")
        self.assertEqual(defaults["verify_crc"], True)

    def test_get_schema_by_key_found(self):
        """Test get_schema_by_key with existing key."""
        item = get_schema_by_key("elf_path")
        self.assertIsNotNone(item)
        self.assertEqual(item.key, "elf_path")
        self.assertEqual(item.config_type, ConfigType.FILE_PATH)

    def test_get_schema_by_key_not_found(self):
        """Test get_schema_by_key with non-existing key."""
        item = get_schema_by_key("non_existent_key")
        self.assertIsNone(item)

    def test_get_sidebar_schema(self):
        """Test get_sidebar_schema filters correctly."""
        sidebar_items = get_sidebar_schema()

        # All returned items should have show_in_sidebar=True
        for item in sidebar_items:
            self.assertTrue(item.show_in_sidebar)

        # Connection items should not be included
        sidebar_keys = {item.key for item in sidebar_items}
        self.assertNotIn("port", sidebar_keys)
        self.assertNotIn("baudrate", sidebar_keys)

    def test_get_schema_by_group(self):
        """Test get_schema_by_group returns correct items."""
        project_items = get_schema_by_group(ConfigGroup.PROJECT)

        self.assertGreater(len(project_items), 0)
        for item in project_items:
            self.assertEqual(item.group, ConfigGroup.PROJECT)

        # Check sorted by order
        orders = [item.order for item in project_items]
        self.assertEqual(orders, sorted(orders))

    def test_get_schema_as_dict(self):
        """Test get_schema_as_dict returns valid structure."""
        result = get_schema_as_dict()

        self.assertIn("schema", result)
        self.assertIn("groups", result)
        self.assertIn("group_order", result)

        # Schema should be list of dicts
        self.assertIsInstance(result["schema"], list)
        for item in result["schema"]:
            self.assertIsInstance(item, dict)
            self.assertIn("key", item)
            self.assertIn("label", item)
            self.assertIn("group", item)
            self.assertIn("config_type", item)

        # Groups should be dict
        self.assertIsInstance(result["groups"], dict)
        self.assertIn("project", result["groups"])

        # Group order should not include connection
        self.assertNotIn("connection", result["group_order"])


class TestConfigTypes(unittest.TestCase):
    """Test ConfigType enum."""

    def test_all_types_used(self):
        """Test that common types are used in schema."""
        used_types = {item.config_type for item in CONFIG_SCHEMA}

        self.assertIn(ConfigType.STRING, used_types)
        self.assertIn(ConfigType.NUMBER, used_types)
        self.assertIn(ConfigType.BOOLEAN, used_types)
        self.assertIn(ConfigType.SELECT, used_types)
        self.assertIn(ConfigType.PATH, used_types)


class TestConfigGroups(unittest.TestCase):
    """Test ConfigGroup enum."""

    def test_all_groups_have_items(self):
        """Test that all sidebar groups have at least one item."""
        for group in ConfigGroup:
            if group == ConfigGroup.CONNECTION:
                continue  # Connection is not shown in sidebar
            items = get_schema_by_group(group)
            self.assertGreater(len(items), 0, f"Group {group.value} has no items")


class TestKnownConfigItems(unittest.TestCase):
    """Test specific known config items."""

    def test_elf_path_config(self):
        """Test elf_path configuration."""
        item = get_schema_by_key("elf_path")
        self.assertIsNotNone(item)
        self.assertEqual(item.group, ConfigGroup.PROJECT)
        self.assertEqual(item.config_type, ConfigType.FILE_PATH)
        self.assertEqual(item.file_ext, ".elf")
        self.assertEqual(item.default, "")

    def test_patch_mode_config(self):
        """Test patch_mode configuration."""
        item = get_schema_by_key("patch_mode")
        self.assertIsNotNone(item)
        self.assertEqual(item.group, ConfigGroup.INJECT)
        self.assertEqual(item.config_type, ConfigType.SELECT)
        self.assertEqual(item.default, "trampoline")
        self.assertEqual(len(item.options), 3)

    def test_chunk_size_config(self):
        """Test chunk_size configuration."""
        item = get_schema_by_key("chunk_size")
        self.assertIsNotNone(item)
        self.assertEqual(item.group, ConfigGroup.TRANSFER)
        self.assertEqual(item.config_type, ConfigType.NUMBER)
        self.assertEqual(item.default, 128)
        self.assertEqual(item.min_value, 16)
        self.assertEqual(item.max_value, 1024)
        self.assertEqual(item.unit, "Bytes")

    def test_ghidra_path_config(self):
        """Test ghidra_path configuration."""
        item = get_schema_by_key("ghidra_path")
        self.assertIsNotNone(item)
        self.assertEqual(item.group, ConfigGroup.TOOLS)
        self.assertEqual(item.config_type, ConfigType.DIR_PATH)
        self.assertEqual(item.default, "")

    def test_ghidra_path_has_link(self):
        """Test ghidra_path has external link configured."""
        item = get_schema_by_key("ghidra_path")
        self.assertIsNotNone(item)
        self.assertIsNotNone(item.link)
        self.assertIn("github.com", item.link)
        self.assertIn("ghidra", item.link.lower())

    def test_watch_dirs_config(self):
        """Test watch_dirs configuration."""
        item = get_schema_by_key("watch_dirs")
        self.assertIsNotNone(item)
        self.assertEqual(item.group, ConfigGroup.INJECT)
        self.assertEqual(item.config_type, ConfigType.PATH_LIST)
        self.assertEqual(item.default, [])
        self.assertEqual(item.depends_on, "auto_compile")

    def test_tx_chunk_delay_ui_multiplier(self):
        """Test tx_chunk_delay has UI multiplier for ms display."""
        item = get_schema_by_key("tx_chunk_delay")
        self.assertIsNotNone(item)
        self.assertEqual(item.ui_multiplier, 1000)
        self.assertEqual(item.unit, "ms")


if __name__ == "__main__":
    unittest.main()

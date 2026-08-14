#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Schema-driven argparse generation for connection/transfer parameters.

Both ``fpbinject-server`` (main.py) and ``fpbinject`` (cli/fpb_cli.py) expose
the same serial/connection parameters on the command line. Rather than hand
writing ``add_argument`` calls in two places, this module derives the flags
directly from ``config_schema.CONFIG_SCHEMA`` — the single source of truth that
also drives ``DeviceState`` defaults and the Web config UI.

Usage::

    add_connection_args(parser)                 # inject --port, --baudrate, ...
    overrides = connection_overrides(args)      # {schema_key: value} for set flags
    apply_overrides(device, overrides)          # write onto a DeviceState

All generated flags default to ``None`` (a sentinel) so callers can tell
"user did not pass this" apart from "user passed the default value". This is
what lets command-line flags override config.json without clobbering unset
keys (see docs/unified-connection-args-refactor.md).
"""

import argparse
from typing import Dict, Iterable

from fpbinject.core.config_schema import (
    CONFIG_SCHEMA,
    ConfigGroup,
    ConfigItem,
    ConfigType,
)

# Groups whose items are eligible for command-line exposure by default.
_DEFAULT_GROUPS = (ConfigGroup.CONNECTION, ConfigGroup.TRANSFER)


def _flag_name(key: str) -> str:
    """Map a schema key ('foo_bar') to its long flag ('--foo-bar')."""
    return "--" + key.replace("_", "-")


def _is_float_item(item: ConfigItem) -> bool:
    """Decide whether a NUMBER item should parse as float rather than int."""
    if isinstance(item.default, float):
        return True
    if item.step is not None and float(item.step) != int(item.step):
        return True
    if item.min_value is not None and float(item.min_value) != int(item.min_value):
        return True
    return False


def _help_text(item: ConfigItem) -> str:
    """Build a help string from tooltip + range/unit hints."""
    parts = []
    if item.tooltip:
        # Keep it single-line for argparse; collapse newlines.
        parts.append(item.tooltip.replace("\n", " "))
    bounds = []
    if item.min_value is not None or item.max_value is not None:
        lo = "" if item.min_value is None else _fmt_num(item.min_value)
        hi = "" if item.max_value is None else _fmt_num(item.max_value)
        bounds.append(f"range: {lo}-{hi}")
    if item.default is not None and item.default != "":
        bounds.append(f"default: {item.default}")
    if item.unit:
        bounds.append(f"unit: {item.unit}")
    if bounds:
        parts.append("(" + ", ".join(bounds) + ")")
    return " ".join(parts)


def _fmt_num(value) -> str:
    """Format a numeric bound without trailing '.0' for integers."""
    fval = float(value)
    if fval == int(fval):
        return str(int(fval))
    return str(fval)


def iter_cli_items(groups: Iterable[ConfigGroup] = _DEFAULT_GROUPS):
    """Yield schema items eligible for CLI exposure in the given groups."""
    group_set = set(groups)
    for item in CONFIG_SCHEMA:
        if item.cli_expose and item.group in group_set:
            yield item


def add_connection_args(
    parser: argparse.ArgumentParser,
    *,
    groups: Iterable[ConfigGroup] = _DEFAULT_GROUPS,
) -> None:
    """Add argparse flags for all CLI-exposed items in ``groups``.

    Every flag defaults to ``None`` so :func:`connection_overrides` can report
    only the ones the user actually set.
    """
    group = parser.add_argument_group("connection / transfer")
    for item in iter_cli_items(groups):
        names = [_flag_name(item.key)]
        if item.cli_short:
            names.append(item.cli_short)
        names.extend(item.cli_aliases)
        help_text = _help_text(item)

        if item.config_type == ConfigType.BOOLEAN:
            # Tri-state: --flag / --no-flag, default None (unset).
            group.add_argument(
                *names,
                dest=item.key,
                action="store_const",
                const=True,
                default=None,
                help=help_text,
            )
            group.add_argument(
                _flag_name("no_" + item.key),
                dest=item.key,
                action="store_const",
                const=False,
                help=argparse.SUPPRESS,
            )
        elif item.config_type == ConfigType.SELECT:
            choices = [value for value, _label in item.options]
            group.add_argument(
                *names,
                dest=item.key,
                choices=choices,
                default=None,
                help=help_text,
            )
        elif item.config_type == ConfigType.NUMBER:
            group.add_argument(
                *names,
                dest=item.key,
                type=float if _is_float_item(item) else int,
                default=None,
                help=help_text,
            )
        else:
            # STRING / PATH / DIR_PATH / FILE_PATH -> plain string.
            group.add_argument(
                *names,
                dest=item.key,
                type=str,
                default=None,
                help=help_text,
            )


def connection_overrides(
    args: argparse.Namespace,
    *,
    groups: Iterable[ConfigGroup] = _DEFAULT_GROUPS,
) -> Dict[str, object]:
    """Extract {schema_key: value} for flags the user actually set.

    Only keys present on ``args`` with a non-None value are returned, so an
    unspecified flag never overrides config.json / schema defaults.
    """
    overrides: Dict[str, object] = {}
    for item in iter_cli_items(groups):
        value = getattr(args, item.key, None)
        if value is not None:
            overrides[item.key] = value
    return overrides


def apply_overrides(device, overrides: Dict[str, object]) -> None:
    """Write override values onto a DeviceState-like object via setattr."""
    for key, value in overrides.items():
        setattr(device, key, value)


def fill_missing_defaults(
    args: argparse.Namespace,
    *,
    groups: Iterable[ConfigGroup] = _DEFAULT_GROUPS,
) -> argparse.Namespace:
    """Replace unset (None) connection flags with their schema defaults.

    The server layers flags on top of config.json and therefore wants the
    None sentinel preserved. The CLI has no config layer, so it calls this to
    turn unset flags into concrete schema defaults (matching the historical
    hand-written argparse defaults). Returns the same namespace for chaining.
    """
    for item in iter_cli_items(groups):
        if getattr(args, item.key, None) is None:
            setattr(args, item.key, item.default)
    return args

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Safe parsing utilities for FPBInject Web Server.

Provides robust string parsing, path handling, and command construction
with proper escaping and cross-platform compatibility.
"""

import functools
import logging
import re
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


# ============================================================================
# LRU Cache Decorators
# ============================================================================


def cached_parse(maxsize: int = 128):
    """
    Decorator for caching parse results based on file path and mtime.

    Args:
        maxsize: Maximum cache size
    """

    def decorator(func):
        cache: Dict[Tuple[str, float], Any] = {}

        @functools.wraps(func)
        def wrapper(path: str, *args, **kwargs):
            try:
                p = Path(path)
                if p.exists():
                    mtime = p.stat().st_mtime
                    cache_key = (str(p.resolve()), mtime)

                    if cache_key in cache:
                        logger.debug(f"Cache hit for {path}")
                        return cache[cache_key]

                    result = func(path, *args, **kwargs)

                    # Evict oldest entries if cache is full
                    if len(cache) >= maxsize:
                        oldest_key = next(iter(cache))
                        del cache[oldest_key]

                    cache[cache_key] = result
                    return result
            except Exception as e:
                logger.debug(f"Cache lookup failed for {path}: {e}")

            return func(path, *args, **kwargs)

        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_info = lambda: {"size": len(cache), "maxsize": maxsize}
        return wrapper

    return decorator


# ============================================================================
# Safe Shell Parsing
# ============================================================================


def safe_shlex_split(command: str, fallback: bool = True) -> Optional[List[str]]:
    """
    Safely split a shell command string into tokens.

    Provides fallback to simple space splitting when shlex fails,
    with proper logging of the failure.

    Args:
        command: Command string to split
        fallback: If True, use simple split on failure; if False, return None

    Returns:
        List of tokens, or None if parsing fails and fallback is False
    """
    if not command:
        return []

    try:
        return shlex.split(command)
    except ValueError as e:
        logger.warning(
            f"shlex.split failed for command (using fallback): {e}\n"
            f"Command preview: {command[:200]}..."
        )

        if fallback:
            # Fallback: simple space split with basic quote handling
            return _fallback_split(command)
        return None


def _fallback_split(command: str) -> List[str]:
    """
    Fallback command splitting when shlex fails.

    Handles basic cases like unmatched quotes by treating them literally.
    """
    tokens = []
    current = []
    in_quote = None
    escape_next = False

    for char in command:
        if escape_next:
            current.append(char)
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char in ('"', "'"):
            if in_quote is None:
                in_quote = char
            elif in_quote == char:
                in_quote = None
            else:
                current.append(char)
            continue

        if char.isspace() and in_quote is None:
            if current:
                tokens.append("".join(current))
                current = []
            continue

        current.append(char)

    if current:
        tokens.append("".join(current))

    return tokens


def quote_path(path: str) -> str:
    """
    Safely quote a path for shell command insertion.

    Uses shlex.quote to handle spaces, special characters, and
    potential injection attempts.

    Args:
        path: Path string to quote

    Returns:
        Quoted path safe for shell insertion
    """
    return shlex.quote(str(path))


def quote_paths(paths: List[str]) -> List[str]:
    """Quote multiple paths."""
    return [quote_path(p) for p in paths]


# ============================================================================
# Cross-Platform Path Handling
# ============================================================================


def normalize_path(path: str) -> Path:
    """
    Normalize a path for cross-platform compatibility.

    Args:
        path: Path string (may use / or \\ separators)

    Returns:
        Normalized Path object
    """
    return Path(path).resolve()


def safe_path_join(*parts: str) -> Path:
    """
    Safely join path components.

    Args:
        *parts: Path components to join

    Returns:
        Joined Path object
    """
    if not parts:
        return Path(".")

    result = Path(parts[0])
    for part in parts[1:]:
        # Prevent path traversal attacks
        part_path = Path(part)
        if part_path.is_absolute():
            # For absolute paths, use them directly (common in compile commands)
            result = part_path
        else:
            result = result / part

    return result


def path_matches_suffix(path1: str, path2: str, min_depth: int = 3) -> bool:
    """
    Check if two paths share a common suffix.

    Useful for matching source files when base paths differ.

    Args:
        path1: First path
        path2: Second path
        min_depth: Minimum number of path components to match

    Returns:
        True if paths share a suffix of at least min_depth components
    """
    parts1 = Path(path1).parts
    parts2 = Path(path2).parts

    max_depth = min(len(parts1), len(parts2))

    for depth in range(max_depth, min_depth - 1, -1):
        if parts1[-depth:] == parts2[-depth:]:
            return True

    return False


# ============================================================================
# Dependency File Parsing
# ============================================================================


# Supported .d file formats
DEP_FILE_PATTERNS = [
    # GNU Make style: cmd_path/file.o := command
    (r"^cmd_[^\s:]+\s*:=\s*(.+)$", "gnu_make"),
    # Ninja style: command = ...
    (r"^command\s*=\s*(.+)$", "ninja"),
    # Simple assignment: CC = gcc ...
    (r"^(?:CC|CXX|COMPILE)\s*=\s*(.+)$", "simple"),
]


def parse_dep_file_command(content: str, source_file: str = None) -> Optional[str]:
    """
    Parse compile command from dependency file content.

    Supports multiple .d file formats with fallback.

    Args:
        content: Dependency file content
        source_file: Optional source file path for validation

    Returns:
        Compile command string or None
    """
    # Check if source file is referenced in content
    if source_file:
        source_basename = Path(source_file).name
        if source_file not in content and source_basename not in content:
            return None

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        for pattern, format_name in DEP_FILE_PATTERNS:
            match = re.match(pattern, line)
            if match:
                command = match.group(1).strip()
                if command:
                    logger.debug(f"Found command in {format_name} format")
                    return command

    return None


# ============================================================================
# FPB_INJECT Marker Detection
# ============================================================================


class FPBMarkerParser:
    """
    Parser for FPB_INJECT markers in C/C++ source code.

    Uses a two-stage approach:
    1. Locate marker comments
    2. Parse subsequent function definition

    This is more robust than single-regex approaches for complex declarations.
    """

    # Stage 1: Marker patterns
    MARKER_PATTERNS = [
        # Block comment: /* FPB_INJECT */ or /* FPB-INJECT */ etc.
        re.compile(
            r"/\*\s*[Ff][Pp][Bb][\s_\-]*[Ii][Nn][Jj][Ee][Cc][Tt]"
            r"(?:\s*:\s*[^*]*)?\s*\*/",
            re.MULTILINE,
        ),
        # Line comment: // FPB_INJECT
        re.compile(
            r"//\s*[Ff][Pp][Bb][_\-]?[Ii][Nn][Jj][Ee][Cc][Tt](?:\s*:.*)?$", re.MULTILINE
        ),
    ]

    # Stage 2: Function definition pattern (applied after marker)
    # Handles: attributes, modifiers, return type, function name
    FUNC_DEF_PATTERN = re.compile(
        r"^"
        r"(?:\s*__attribute__\s*\(\([^)]*\)\)\s*)*"  # Optional __attribute__
        r"(?:\s*(?:static|inline|extern|const|volatile)\s+)*"  # Modifiers
        r'(?:\s*extern\s+"C"\s+)?'  # extern "C"
        r"\s*"
        r"(?:"
        r"void|int|char|unsigned|signed|long|short|float|double|bool|_Bool|"
        r"(?:u?int(?:8|16|32|64)_t)|size_t|ssize_t|"
        r"\w+(?:\s*\*+)?"  # Custom types with optional pointer
        r")\s+"
        r"(\w+)"  # Function name (captured)
        r"\s*\(",
        re.MULTILINE | re.DOTALL,
    )

    # Keywords to exclude from function names
    KEYWORDS = frozenset(
        {
            "if",
            "while",
            "for",
            "switch",
            "return",
            "case",
            "default",
            "break",
            "continue",
            "goto",
            "sizeof",
            "typeof",
            "alignof",
        }
    )

    @classmethod
    def find_marked_functions(cls, content: str) -> List[Tuple[str, int, int]]:
        """
        Find all functions marked with FPB_INJECT.

        Args:
            content: Source file content

        Returns:
            List of (function_name, start_pos, end_pos) tuples
        """
        results = []

        # Find all markers
        marker_positions = []
        for pattern in cls.MARKER_PATTERNS:
            for match in pattern.finditer(content):
                marker_positions.append((match.start(), match.end()))

        # Sort by position
        marker_positions.sort(key=lambda x: x[0])

        # For each marker, find the following function definition
        for marker_start, marker_end in marker_positions:
            # Look for function definition in the next ~500 characters
            search_region = content[marker_end : marker_end + 500]

            func_match = cls.FUNC_DEF_PATTERN.search(search_region)
            if func_match:
                func_name = func_match.group(1)

                # Skip keywords
                if func_name in cls.KEYWORDS:
                    continue

                # Calculate absolute positions
                func_end = marker_end + func_match.end()

                results.append((func_name, marker_start, func_end))
                logger.debug(f"Found FPB_INJECT function: {func_name}")

        return results

    @classmethod
    def extract_function_names(cls, content: str) -> List[str]:
        """
        Extract just the function names from marked functions.

        Args:
            content: Source file content

        Returns:
            List of function names
        """
        return [name for name, _, _ in cls.find_marked_functions(content)]


# ============================================================================
# Command Builder
# ============================================================================


class CommandBuilder:
    """
    Safe command line builder with proper escaping.
    """

    def __init__(self, executable: str):
        """
        Initialize command builder.

        Args:
            executable: Path to executable
        """
        self._parts = [str(executable)]

    def add_flag(self, flag: str) -> "CommandBuilder":
        """Add a simple flag (e.g., -c, -v)."""
        self._parts.append(flag)
        return self

    def add_option(
        self, option: str, value: str, quote_value: bool = True
    ) -> "CommandBuilder":
        """
        Add an option with value (e.g., -o output.o).

        Args:
            option: Option flag (e.g., '-o', '-I')
            value: Option value
            quote_value: Whether to quote the value
        """
        self._parts.append(option)
        if quote_value and " " in value:
            self._parts.append(quote_path(value))
        else:
            self._parts.append(value)
        return self

    def add_include(self, path: str) -> "CommandBuilder":
        """Add include path (-I)."""
        return self.add_option("-I", path)

    def add_define(self, name: str, value: str = None) -> "CommandBuilder":
        """Add preprocessor definition (-D)."""
        if value is not None:
            self._parts.append(f"-D{name}={value}")
        else:
            self._parts.append(f"-D{name}")
        return self

    def add_source(self, path: str) -> "CommandBuilder":
        """Add source file."""
        self._parts.append(str(path))
        return self

    def add_output(self, path: str) -> "CommandBuilder":
        """Add output file (-o)."""
        return self.add_option("-o", path)

    def build(self) -> List[str]:
        """Build the command as a list of arguments."""
        return self._parts.copy()

    def build_string(self) -> str:
        """Build the command as a shell string."""
        return " ".join(quote_path(p) if " " in p else p for p in self._parts)


# ============================================================================
# Validation Utilities
# ============================================================================


def validate_source_content(content: str) -> Tuple[bool, str]:
    """
    Basic validation of source content.

    Args:
        content: Source code content

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not content or not content.strip():
        return False, "Empty source content"

    # Check for balanced braces (basic check)
    brace_count = content.count("{") - content.count("}")
    if brace_count != 0:
        return False, f"Unbalanced braces: {brace_count:+d}"

    # Check for balanced parentheses
    paren_count = content.count("(") - content.count(")")
    if paren_count != 0:
        return False, f"Unbalanced parentheses: {paren_count:+d}"

    return True, ""


def sanitize_function_name(name: str) -> str:
    """
    Sanitize a function name for safe use.

    Args:
        name: Raw function name

    Returns:
        Sanitized function name
    """
    # Remove any non-identifier characters
    sanitized = re.sub(r"[^\w]", "", name)

    # Ensure it doesn't start with a digit
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized

    return sanitized

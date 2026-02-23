#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Patch Generator for FPBInject (v2 - Marker Based)

Simple strategy:
1. Copy the entire source file (preserving all includes, macros, structs, etc.)
2. Find functions marked with /* FPB_INJECT */ comment
3. Add section attribute to marked functions for placement in .fpb.text
4. Linker with --gc-sections will remove unused code

Usage:
    Add /* FPB_INJECT */ comment before functions you want to inject:

    /* FPB_INJECT */
    void my_function(void)
    {
        // modified code - this completely replaces the original function
    }

Note: Calling the original function from injected code is NOT supported
      due to FPB hardware limitations (would cause infinite recursion).
"""

import logging
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set, Tuple

from core.safe_parser import FPBMarkerParser

logger = logging.getLogger(__name__)

# Marker comment pattern
FPB_INJECT_MARKER = "FPB_INJECT"

# Section attribute for FPB inject functions
FPB_SECTION_ATTR = '__attribute__((section(".fpb.text"), used))'

# Standard library headers (not to be converted to absolute paths)
STD_HEADERS: Set[str] = {
    "stdio.h",
    "stdlib.h",
    "string.h",
    "stdint.h",
    "stdbool.h",
    "stddef.h",
    "stdarg.h",
    "limits.h",
    "math.h",
    "time.h",
    "assert.h",
    "errno.h",
    "signal.h",
    "setjmp.h",
    "ctype.h",
    "locale.h",
    "float.h",
    "iso646.h",
    "wchar.h",
    "wctype.h",
    "complex.h",
    "fenv.h",
    "inttypes.h",
    "tgmath.h",
}

# Directories to skip during header search
SKIP_DIRS: Set[str] = {
    ".git",
    "build",
    "out",
    "__pycache__",
    "node_modules",
    ".svn",
    ".hg",
    "CMakeFiles",
}


class PatchGenerator:
    """Generate inject patches from marked C/C++ files."""

    def __init__(self, repo_root: str = None):
        """
        Initialize patch generator.

        Args:
            repo_root: Git repository root path (optional, for include path resolution)
        """
        self.repo_root = Path(repo_root) if repo_root else None
        self._header_cache: dict = {}

    def find_marked_functions(self, content: str) -> List[str]:
        """
        Find all functions marked with FPB_INJECT comment.

        Uses the robust FPBMarkerParser for accurate detection.

        Supported formats (case-insensitive):
        - /* FPB_INJECT */
        - /* FPB-INJECT */
        - /* fpb inject */
        - // FPB_INJECT
        - /* FPB_INJECT: description */

        Args:
            content: Source file content

        Returns:
            List of function names marked for injection
        """
        return FPBMarkerParser.extract_function_names(content)

    def generate_patch(
        self,
        file_path: str,
        output_path: str = None,
    ) -> Tuple[str, List[str]]:
        """
        Generate a patch file from a source file with FPB_INJECT markers.

        Strategy:
        1. Copy the entire file
        2. Add section attribute to marked functions
        3. Convert relative includes to absolute paths

        Args:
            file_path: Path to the source file with FPB_INJECT markers
            output_path: Output path for patch file (optional)

        Returns:
            Tuple of (patch_content, list_of_injected_functions)
        """
        file_path = Path(file_path)

        # Read source content
        content = file_path.read_text(encoding="utf-8", errors="replace")

        # Find marked functions
        marked_functions = self.find_marked_functions(content)

        if not marked_functions:
            logger.warning(f"No FPB_INJECT markers found in {file_path}")
            logger.info("Add /* FPB_INJECT */ before functions you want to inject")
            return "", []

        logger.info(
            f"Generating patch for {len(marked_functions)} functions: {marked_functions}"
        )

        # Get source directory for resolving includes
        source_dir = file_path.parent.resolve()

        # Process content
        patch_content = self._process_content(
            content, marked_functions, source_dir, str(file_path)
        )

        # Save to file if output_path specified
        if output_path:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(patch_content, encoding="utf-8")
            logger.info(f"Patch saved to: {output_path}")

        return patch_content, marked_functions

    def _process_content(
        self,
        content: str,
        marked_functions: List[str],
        source_dir: Path,
        file_path: str,
    ) -> str:
        """
        Process source content: add section attribute to marked functions, convert includes.

        Args:
            content: Original source content
            marked_functions: Functions to add section attribute
            source_dir: Directory of source file
            file_path: Path to source file

        Returns:
            Processed patch content
        """
        lines = content.split("\n")
        result_lines = []

        # Add header
        result_lines.extend(
            [
                "/**",
                " * Auto-generated patch file by FPBInject",
                f" * Source: {file_path}",
                f" * Inject functions: {', '.join(marked_functions)}",
                " */",
                "",
            ]
        )

        # Track if we just saw an FPB_INJECT marker
        saw_marker = False
        needs_attribute = False

        # Process each line
        for i, line in enumerate(lines):
            processed_line = line

            # Convert relative includes to absolute
            processed_line = self._convert_include_path(processed_line, source_dir)

            # Check if this line contains FPB_INJECT marker
            if self._is_marker_line(processed_line):
                saw_marker = True
                # Check if next lines already have the attribute
                needs_attribute = True
                for j in range(i + 1, min(i + 5, len(lines))):
                    if FPB_SECTION_ATTR in lines[j] or ".fpb.text" in lines[j]:
                        needs_attribute = False
                        break
                    if self._is_function_definition(lines[j], marked_functions):
                        break
                result_lines.append(processed_line)
                continue

            # If previous line was marker and this is function definition
            if saw_marker and self._is_function_definition(
                processed_line, marked_functions
            ):
                if needs_attribute:
                    result_lines.append(FPB_SECTION_ATTR)
                saw_marker = False
                needs_attribute = False

            result_lines.append(processed_line)

        return "\n".join(result_lines)

    def _is_marker_line(self, line: str) -> bool:
        """Check if line contains FPB_INJECT marker."""
        marker_patterns = [
            r"/\*\s*[Ff][Pp][Bb][\s_\-]*[Ii][Nn][Jj][Ee][Cc][Tt]",
            r"//\s*[Ff][Pp][Bb][_\-]?[Ii][Nn][Jj][Ee][Cc][Tt]",
        ]
        return any(re.search(pattern, line) for pattern in marker_patterns)

    def _is_function_definition(self, line: str, marked_functions: List[str]) -> bool:
        """Check if line is a function definition for one of the marked functions."""
        for func_name in marked_functions:
            pattern = rf"\b{re.escape(func_name)}\s*\("
            if re.search(pattern, line):
                return True
        return False

    def _convert_include_path(self, line: str, source_dir) -> str:
        """
        Convert relative #include paths to absolute paths.

        Uses pathlib for cross-platform compatibility.

        Examples:
            #include "lv_mem.h"          -> #include "/abs/path/to/lv_mem.h"
            #include "../misc/lv_log.h"  -> #include "/abs/path/to/misc/lv_log.h"
            #include <stdio.h>           -> unchanged (standard library)
            #include <local_header.h>    -> #include "/abs/path/to/local_header.h" (if found)
        """
        # Ensure source_dir is a Path
        if isinstance(source_dir, str):
            source_dir = Path(source_dir)

        # Handle double-quoted includes
        match = re.match(r'^(\s*#\s*include\s*)"([^"]+)"(.*)', line)
        if match:
            prefix, include_path, suffix = match.groups()

            # Skip if already absolute
            if Path(include_path).is_absolute():
                return line

            # Resolve relative path
            abs_path = (source_dir / include_path).resolve()

            # Only convert if file exists
            if abs_path.exists():
                return f'{prefix}"{abs_path}"{suffix}'

            return line

        # Handle angle-bracket includes
        match = re.match(r"^(\s*#\s*include\s*)<([^>]+)>(.*)", line)
        if match:
            prefix, include_path, suffix = match.groups()

            # Skip standard library headers
            if include_path in STD_HEADERS:
                return line

            # Search for the header
            found_path = self._find_header(include_path, source_dir)
            if found_path:
                return f'{prefix}"{found_path}"{suffix}'

        return line

    def _find_header(self, header_path: str, source_dir) -> Optional[str]:
        """
        Search for a header file in source directory tree.

        Uses caching to avoid repeated filesystem searches.

        Args:
            header_path: Header path from include directive
            source_dir: Starting directory for search

        Returns:
            Absolute path to header or None
        """
        # Ensure source_dir is a Path
        if isinstance(source_dir, str):
            source_dir = Path(source_dir)

        cache_key = (header_path, str(source_dir))
        if cache_key in self._header_cache:
            return self._header_cache[cache_key]

        result = self._search_header(header_path, source_dir)
        self._header_cache[cache_key] = result
        return result

    def _search_header(self, header_path: str, source_dir) -> Optional[str]:
        """
        Actually search for header file.

        Args:
            header_path: Header path from include directive
            source_dir: Starting directory for search

        Returns:
            Absolute path to header or None
        """
        # Ensure source_dir is a Path
        if isinstance(source_dir, str):
            source_dir = Path(source_dir)
        header_name = Path(header_path).name
        search_dir = source_dir

        # Search up to 5 levels up
        for _ in range(5):
            if not search_dir or not search_dir.is_dir():
                break

            # Try direct path first
            direct_path = search_dir / header_path
            if direct_path.exists():
                return str(direct_path.resolve())

            # Search recursively (limited depth)
            try:
                for root, dirs, files in os.walk(search_dir):
                    root_path = Path(root)

                    # Limit search depth
                    try:
                        depth = len(root_path.relative_to(search_dir).parts)
                    except ValueError:
                        depth = 0

                    if depth > 3:
                        dirs[:] = []
                        continue

                    # Skip non-source directories
                    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

                    # Check if header exists here
                    if header_name in files:
                        found_path = root_path / header_name
                        # Verify path suffix matches
                        if header_path == header_name or str(found_path).endswith(
                            header_path
                        ):
                            return str(found_path.resolve())
            except Exception as e:
                logger.debug(f"Error searching for header: {e}")

            search_dir = search_dir.parent

        return None

    def generate_patch_from_file(
        self,
        file_path: str,
        output_dir: str = None,
    ) -> Tuple[Optional[str], List[str]]:
        """
        High-level API: Generate patch from a marked file.

        Args:
            file_path: Path to the C/C++ file with FPB_INJECT markers
            output_dir: Directory to save patch file

        Returns:
            Tuple of (patch_file_path, list_of_injected_functions)
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None, []

        # Generate output path
        if output_dir:
            output_path = Path(output_dir) / f"patch_{file_path.stem}{file_path.suffix}"
        else:
            output_path = None

        # Generate patch
        patch_content, injected = self.generate_patch(
            str(file_path), str(output_path) if output_path else None
        )

        if not injected:
            return None, []

        return str(output_path) if output_path else None, injected


@lru_cache(maxsize=128)
def find_function_signature(content: str, func_name: str) -> Optional[str]:
    """
    Find function signature in source code.

    Args:
        content: Source file content
        func_name: Function name to find

    Returns:
        Function signature string or None if not found
    """
    # Pattern to match function definition
    func_pattern = rf"\b{re.escape(func_name)}\s*\("

    for match in re.finditer(func_pattern, content):
        func_start = match.start()

        # Look backward to find the return type
        start_search = max(0, func_start - 200)
        prefix = content[start_search:func_start]

        # Find the start of the declaration
        lines = prefix.split("\n")
        decl_parts = []

        for line in reversed(lines):
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("//")
                and not stripped.startswith("*")
            ):
                decl_parts.insert(0, stripped)
                # Stop if we hit the start of declaration
                if re.match(
                    r"^(?:static|inline|extern|const|volatile|unsigned|signed|"
                    r"void|int|char|short|long|float|double|struct|union|enum|\w+_t)\b",
                    stripped,
                ):
                    break
            elif not stripped and decl_parts:
                break

        if not decl_parts:
            continue

        return_type = " ".join(decl_parts)
        return_type = re.sub(r"\s+", " ", return_type).strip()

        # Skip invalid patterns
        if "=" in return_type or ";" in return_type or "(" in return_type:
            continue
        if re.match(
            r"^(if|else|while|for|switch|case|return|break|continue)\b", return_type
        ):
            continue

        # Find parameters
        paren_start = match.end() - 1
        depth = 1
        i = match.end()

        while i < len(content) and depth > 0:
            if content[i] == "(":
                depth += 1
            elif content[i] == ")":
                depth -= 1
            i += 1

        if depth == 0:
            params = content[paren_start:i]
            rest = content[i:].lstrip()

            if rest and (rest[0] == "{" or rest[0] == ";"):
                return f"{return_type} {func_name}{params}"

    return None


def check_dependencies() -> dict:
    """Check if required dependencies are available."""
    status = {"git": False}

    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        status["git"] = result.returncode == 0
    except Exception:
        pass

    return status


# CLI interface for testing
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    print("Patch Generator v2 (Marker Based)")
    print("=" * 40)

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"\nAnalyzing: {file_path}")

        gen = PatchGenerator()
        patch_content, injected = gen.generate_patch(file_path)

        if injected:
            print(f"\nFound {len(injected)} inject functions: {injected}")
            print("\n--- Generated Patch (first 2000 chars) ---")
            print(patch_content[:2000])
            if len(patch_content) > 2000:
                print(f"... ({len(patch_content)} total chars)")
        else:
            print("\nNo FPB_INJECT markers found!")
            print("Add /* FPB_INJECT */ before functions you want to inject.")
    else:
        print("\nUsage: python patch_generator.py <file.c>")
        print("\nExample source file:")
        print("  /* FPB_INJECT */")
        print("  void my_function(void)")
        print("  {")
        print("      // your modified code")
        print("  }")

#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Patch Generator for FPBInject (v2 - Marker Based)

Simple strategy:
1. Copy the entire source file (preserving all includes, macros, structs, etc.)
2. Find functions marked with /* FPB_INJECT */ comment
3. Rename marked functions to inject_xxx
4. Linker with --gc-sections will remove unused code

Usage:
    Add /* FPB_INJECT */ comment before functions you want to inject:

    /* FPB_INJECT */
    void my_function(void)
    {
        // modified code
    }
"""

import logging
import os
import re
import subprocess
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Marker comment pattern
FPB_INJECT_MARKER = "FPB_INJECT"


class PatchGenerator:
    """Generate inject patches from marked C/C++ files."""

    def __init__(self, repo_root: str = None):
        """
        Initialize patch generator.

        Args:
            repo_root: Git repository root path (optional, for include path resolution)
        """
        self.repo_root = repo_root

    def find_marked_functions(self, content: str) -> List[str]:
        """
        Find all functions marked with FPB_INJECT comment.

        Supported formats (case-insensitive):
        - /* FPB_INJECT */
        - /* FPB-INJECT */
        - // FPB_INJECT
        - /* fpbinject */
        - /* FPB_INJECT: description */

        Args:
            content: Source file content

        Returns:
            List of function names marked for injection
        """
        marked_functions = []

        # Pattern supports:
        # - Block comment: /* FPB_INJECT */ or /* FPB-INJECT */ or /* fpbinject */
        # - Line comment: // FPB_INJECT or // FPB-INJECT
        # - Optional description after colon
        # - Case-insensitive matching
        # followed by optional whitespace/newlines, then function signature
        patterns = [
            # Block comment: /* FPB_INJECT */ or /* FPB-INJECT */ etc.
            r"/\*\s*[Ff][Pp][Bb][_\-]?[Ii][Nn][Jj][Ee][Cc][Tt](?:\s*:\s*[^*]*)?\s*\*/",
            # Line comment: // FPB_INJECT or // FPB-INJECT etc.
            r"//\s*[Ff][Pp][Bb][_\-]?[Ii][Nn][Jj][Ee][Cc][Tt](?:\s*:.*)?$",
        ]

        combined_pattern = f"(?:{patterns[0]}|{patterns[1]})"
        # Full pattern: marker + optional whitespace + function signature
        full_pattern = (
            rf"(?:{combined_pattern})\s*\n?"
            r"(?:\s*(?:static|inline|extern|const|volatile|__attribute__\s*\([^)]*\))\s+)*"
            r"[\w\s\*]+?\s+(\w+)\s*\("
        )

        for match in re.finditer(full_pattern, content, re.MULTILINE):
            func_name = match.group(1)
            # Skip common keywords that might be matched
            if func_name not in ("if", "while", "for", "switch", "return"):
                marked_functions.append(func_name)
                logger.info(f"Found marked function: {func_name}")

        return marked_functions

    def generate_patch(
        self,
        file_path: str,
        output_path: str = None,
    ) -> Tuple[str, List[str]]:
        """
        Generate a patch file from a source file with FPB_INJECT markers.

        Strategy:
        1. Copy the entire file
        2. Rename marked functions to inject_xxx
        3. Convert relative includes to absolute paths

        Args:
            file_path: Path to the source file with FPB_INJECT markers
            output_path: Output path for patch file (optional)

        Returns:
            Tuple of (patch_content, list_of_injected_functions)
        """
        # Read source content
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

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
        source_dir = os.path.dirname(os.path.abspath(file_path))

        # Process content
        patch_content = self._process_content(
            content, marked_functions, source_dir, file_path
        )

        # Save to file if output_path specified
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(patch_content)
            logger.info(f"Patch saved to: {output_path}")

        return patch_content, marked_functions

    def _process_content(
        self,
        content: str,
        marked_functions: List[str],
        source_dir: str,
        file_path: str,
    ) -> str:
        """
        Process source content: rename functions, convert includes.

        Args:
            content: Original source content
            marked_functions: Functions to rename to inject_xxx
            source_dir: Directory of source file
            file_path: Path to source file

        Returns:
            Processed patch content
        """
        lines = content.split("\n")
        result_lines = []

        # Add header
        result_lines.append("/**")
        result_lines.append(" * Auto-generated patch file by FPBInject")
        result_lines.append(f" * Source: {file_path}")
        result_lines.append(f" * Inject functions: {', '.join(marked_functions)}")
        result_lines.append(" */")
        result_lines.append("")

        # Process each line
        for line in lines:
            processed_line = line

            # Convert relative includes to absolute
            processed_line = self._convert_include_path(processed_line, source_dir)

            # Rename marked functions
            for func_name in marked_functions:
                processed_line = self._rename_function(processed_line, func_name)

            result_lines.append(processed_line)

        return "\n".join(result_lines)

    def _rename_function(self, line: str, func_name: str) -> str:
        """
        Rename a function in a line (func_name -> inject_func_name).

        Only renames function definitions/declarations, not calls.
        """
        # Skip if already renamed
        if f"inject_{func_name}" in line:
            return line

        # Pattern for function definition: something before func_name(
        # This catches: void func_name(, static int func_name(, etc.
        pattern = r"(\s+|\*)" + re.escape(func_name) + r"\s*\("

        def replacer(m):
            return m.group(1) + f"inject_{func_name}("

        return re.sub(pattern, replacer, line)

    def _convert_include_path(self, line: str, source_dir: str) -> str:
        """
        Convert relative #include paths to absolute paths.

        Examples:
            #include "lv_mem.h"          -> #include "/abs/path/to/lv_mem.h"
            #include "../misc/lv_log.h"  -> #include "/abs/path/to/misc/lv_log.h"
            #include <stdio.h>           -> unchanged (unless found in source tree)
            #include <local_header.h>    -> #include "/abs/path/to/local_header.h" (if found)
        """
        # Handle double-quoted includes
        match = re.match(r'^(\s*#\s*include\s*)"([^"]+)"(.*)', line)
        if match:
            prefix = match.group(1)
            include_path = match.group(2)
            suffix = match.group(3)

            # Skip if already absolute
            if os.path.isabs(include_path):
                return line

            # Resolve relative path
            abs_path = os.path.normpath(os.path.join(source_dir, include_path))

            # Only convert if file exists
            if os.path.exists(abs_path):
                return f'{prefix}"{abs_path}"{suffix}'

            return line

        # Handle angle-bracket includes - try to find in source directory tree
        match = re.match(r"^(\s*#\s*include\s*)<([^>]+)>(.*)", line)
        if match:
            prefix = match.group(1)
            include_path = match.group(2)
            suffix = match.group(3)

            # Skip standard library headers (heuristic: no path separator and common names)
            std_headers = {
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
            if include_path in std_headers:
                return line

            # Search for the header in source directory and parent directories
            search_dir = source_dir
            for _ in range(5):  # Search up to 5 levels up
                if not search_dir or not os.path.isdir(search_dir):
                    break

                # Try direct path
                abs_path = os.path.normpath(os.path.join(search_dir, include_path))
                if os.path.exists(abs_path):
                    # Convert to double-quoted include with absolute path
                    return f'{prefix}"{abs_path}"{suffix}'

                # Search recursively in this directory (limited depth)
                for root, dirs, files in os.walk(search_dir):
                    # Limit search depth
                    depth = root[len(search_dir) :].count(os.sep)
                    if depth > 3:
                        dirs[:] = []
                        continue

                    # Skip common non-source directories
                    dirs[:] = [
                        d
                        for d in dirs
                        if d
                        not in [
                            ".git",
                            "build",
                            "out",
                            "__pycache__",
                            "node_modules",
                            ".svn",
                            ".hg",
                            "CMakeFiles",
                        ]
                    ]

                    # Check if the header exists here
                    header_name = os.path.basename(include_path)
                    if header_name in files:
                        abs_path = os.path.join(root, header_name)
                        # Verify it's the right file (path suffix matches)
                        if include_path == header_name or abs_path.endswith(
                            include_path
                        ):
                            return f'{prefix}"{abs_path}"{suffix}'

                search_dir = os.path.dirname(search_dir)

        return line

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
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None, []

        # Generate output path
        if output_dir:
            basename = os.path.basename(file_path)
            name, ext = os.path.splitext(basename)
            output_path = os.path.join(output_dir, f"patch_{name}{ext}")
        else:
            output_path = None

        # Generate patch
        patch_content, injected = self.generate_patch(file_path, output_path)

        if not injected:
            return None, []

        return output_path, injected


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
    # Handles: return_type func_name(params)
    # Including: static, inline, const, volatile, pointers, etc.

    # More robust pattern that captures:
    # 1. Optional modifiers (static, inline, etc.)
    # 2. Return type (including pointers like void *, int **, etc.)
    # 3. Function name
    # 4. Parameters

    # First try to find the function name followed by (
    func_pattern = rf"\b{re.escape(func_name)}\s*\("

    for match in re.finditer(func_pattern, content):
        func_start = match.start()

        # Look backward to find the return type (up to 200 chars or newline with non-space start)
        start_search = max(0, func_start - 200)
        prefix = content[start_search:func_start]

        # Find the start of the declaration (usually after a newline or semicolon/brace)
        lines = prefix.split("\n")
        # Take the last line(s) that form the declaration
        decl_parts = []
        for line in reversed(lines):
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("//")
                and not stripped.startswith("*")
            ):
                decl_parts.insert(0, stripped)
                # Stop if we hit a line that looks like the start of declaration
                if re.match(
                    r"^(?:static|inline|extern|const|volatile|unsigned|signed|void|int|char|short|long|float|double|struct|union|enum|\w+_t)\b",
                    stripped,
                ):
                    break
            elif not stripped:
                if decl_parts:
                    break

        if not decl_parts:
            continue

        return_type = " ".join(decl_parts)

        # Clean up return type - remove any trailing content after the type
        return_type = re.sub(r"\s+", " ", return_type).strip()

        # Skip if return_type looks like an assignment or function call
        # e.g., "void * new = " or "result = "
        if "=" in return_type or ";" in return_type or "(" in return_type:
            continue

        # Skip if return_type starts with keywords that indicate a statement
        if re.match(
            r"^(if|else|while|for|switch|case|return|break|continue)\b", return_type
        ):
            continue

        # Find parameters
        paren_start = match.end() - 1  # Position of (
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

            # Check if this is followed by { or ; (definition or declaration)
            rest = content[i:].lstrip()
            if rest and (rest[0] == "{" or rest[0] == ";"):
                return f"{return_type} {func_name}{params}"

    return None


def check_dependencies() -> dict:
    """Check if required dependencies are available."""
    status = {
        "git": False,
    }

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

        # Generate patch
        patch_content, injected = gen.generate_patch(file_path)

        if injected:
            print(f"\nFound {len(injected)} inject functions: {injected}")
            print(f"\n--- Generated Patch (first 2000 chars) ---")
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

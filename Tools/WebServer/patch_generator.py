#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Patch Generator for FPBInject

Automatically detects modified functions in C/C++ files and generates
inject patch files by:
1. Comparing current file with git HEAD version
2. Parsing functions using tree-sitter
3. Cloning the entire file with modified functions renamed to inject_xxx
"""

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import tree-sitter
TREE_SITTER_AVAILABLE = False
try:
    import tree_sitter_c as tsc
    from tree_sitter import Language, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    logger.warning("tree-sitter not available, using regex fallback")


@dataclass
class FunctionInfo:
    """Information about a C/C++ function."""

    name: str
    start_line: int  # 1-based
    end_line: int  # 1-based
    start_byte: int
    end_byte: int
    code: str
    signature: str  # Return type + name + params


class CParser:
    """C/C++ parser using tree-sitter or regex fallback."""

    def __init__(self):
        self._parser = None
        self._language = None

        if TREE_SITTER_AVAILABLE:
            try:
                self._language = Language(tsc.language())
                self._parser = Parser(self._language)
                logger.info("Using tree-sitter C parser")
            except Exception as e:
                logger.warning(f"Failed to init tree-sitter: {e}")

    def parse_functions(self, source_code: str) -> Dict[str, FunctionInfo]:
        """
        Parse source code and extract all function definitions.

        Returns:
            Dict mapping function name to FunctionInfo
        """
        if self._parser:
            return self._parse_with_tree_sitter(source_code)
        else:
            return self._parse_with_regex(source_code)

    def _parse_with_tree_sitter(self, source_code: str) -> Dict[str, FunctionInfo]:
        """Parse using tree-sitter for accurate AST."""
        functions = {}

        tree = self._parser.parse(bytes(source_code, "utf-8"))
        root = tree.root_node

        def find_functions(node):
            # Look for function_definition nodes
            if node.type == "function_definition":
                func_info = self._extract_function_info(node, source_code)
                if func_info:
                    functions[func_info.name] = func_info

            for child in node.children:
                find_functions(child)

        find_functions(root)
        return functions

    def _extract_function_info(self, node, source_code: str) -> Optional[FunctionInfo]:
        """Extract function information from a tree-sitter node."""
        # Find the declarator which contains the function name
        declarator = None
        for child in node.children:
            if child.type in ("function_declarator", "pointer_declarator"):
                declarator = child
                break
            elif child.type == "declarator":
                declarator = child
                break

        if not declarator:
            # Try to find nested declarator
            for child in node.children:
                for subchild in child.children:
                    if subchild.type in ("function_declarator", "pointer_declarator"):
                        declarator = subchild
                        break

        if not declarator:
            return None

        # Extract function name
        func_name = self._find_identifier(declarator, source_code)
        if not func_name:
            return None

        # Get the full code
        start_byte = node.start_byte
        end_byte = node.end_byte
        code = source_code[start_byte:end_byte]

        # Get line numbers (1-based)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        # Extract signature (everything before the body)
        body_node = None
        for child in node.children:
            if child.type == "compound_statement":
                body_node = child
                break

        if body_node:
            sig_end = body_node.start_byte
            signature = source_code[start_byte:sig_end].strip()
        else:
            signature = code.split("{")[0].strip() if "{" in code else code

        return FunctionInfo(
            name=func_name,
            start_line=start_line,
            end_line=end_line,
            start_byte=start_byte,
            end_byte=end_byte,
            code=code,
            signature=signature,
        )

    def _find_identifier(self, node, source_code: str) -> Optional[str]:
        """Recursively find the identifier (function name) in a declarator."""
        if node.type == "identifier":
            return source_code[node.start_byte : node.end_byte]

        for child in node.children:
            result = self._find_identifier(child, source_code)
            if result:
                return result

        return None

    def _parse_with_regex(self, source_code: str) -> Dict[str, FunctionInfo]:
        """Fallback parser using regex (less accurate)."""
        functions = {}

        # Pattern to match function definitions
        # This is simplified and may not handle all cases
        pattern = r"""
            ^                           # Start of line
            (?:[\w\s\*]+?)              # Return type (non-greedy)
            \s+                         # Whitespace
            (\w+)                       # Function name (capture)
            \s*                         # Optional whitespace
            \([^)]*\)                   # Parameters
            \s*                         # Optional whitespace
            \{                          # Opening brace
        """

        lines = source_code.split("\n")
        i = 0
        while i < len(lines):
            # Try to match function start
            remaining = "\n".join(lines[i:])
            match = re.match(pattern, remaining, re.MULTILINE | re.VERBOSE)

            if match:
                func_name = match.group(1)
                start_line = i + 1

                # Find the matching closing brace
                brace_count = 0
                func_lines = []
                j = i
                started = False

                while j < len(lines):
                    line = lines[j]
                    func_lines.append(line)

                    for char in line:
                        if char == "{":
                            brace_count += 1
                            started = True
                        elif char == "}":
                            brace_count -= 1

                    if started and brace_count == 0:
                        break
                    j += 1

                end_line = j + 1
                code = "\n".join(func_lines)

                # Calculate byte offsets
                start_byte = sum(len(lines[k]) + 1 for k in range(i))
                end_byte = start_byte + len(code)

                functions[func_name] = FunctionInfo(
                    name=func_name,
                    start_line=start_line,
                    end_line=end_line,
                    start_byte=start_byte,
                    end_byte=end_byte,
                    code=code,
                    signature=code.split("{")[0].strip(),
                )

                i = j + 1
            else:
                i += 1

        return functions


class PatchGenerator:
    """Generate inject patches from modified C/C++ files."""

    def __init__(self, repo_root: str = None):
        """
        Initialize patch generator.

        Args:
            repo_root: Git repository root path. If None, auto-detect.
        """
        self.repo_root = repo_root
        self.parser = CParser()

    def get_git_head_content(self, file_path: str) -> Optional[str]:
        """Get file content from git HEAD."""
        try:
            # Get repo root if not set
            if not self.repo_root:
                result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    cwd=os.path.dirname(file_path),
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self.repo_root = result.stdout.strip()

            # Get relative path
            rel_path = os.path.relpath(file_path, self.repo_root)

            # Get HEAD content
            result = subprocess.run(
                ["git", "show", f"HEAD:{rel_path}"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"git show failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Failed to get git HEAD content: {e}")
            return None

    def detect_modified_functions(
        self, file_path: str, original_content: str = None
    ) -> List[str]:
        """
        Detect which functions have been modified.

        Args:
            file_path: Path to the modified file
            original_content: Original content (if None, get from git HEAD)

        Returns:
            List of modified function names
        """
        # Read current content
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            current_content = f.read()

        # Get original content
        if original_content is None:
            original_content = self.get_git_head_content(file_path)
            if original_content is None:
                logger.warning(
                    "Cannot get original content, assuming all functions modified"
                )
                # Return all function names
                funcs = self.parser.parse_functions(current_content)
                return list(funcs.keys())

        # Parse both versions
        original_funcs = self.parser.parse_functions(original_content)
        current_funcs = self.parser.parse_functions(current_content)

        # Find modified functions
        modified = []

        for name, current_info in current_funcs.items():
            if name not in original_funcs:
                # New function
                modified.append(name)
                logger.info(f"New function detected: {name}")
            elif original_funcs[name].code != current_info.code:
                # Modified function
                modified.append(name)
                logger.info(f"Modified function detected: {name}")

        return modified

    def generate_patch(
        self,
        file_path: str,
        modified_functions: List[str] = None,
        output_path: str = None,
    ) -> Tuple[str, List[str]]:
        """
        Generate a patch file from a modified source file.

        Strategy:
        1. Clone the entire file (preserving all includes, macros, etc.)
        2. Rename modified functions to inject_xxx
        3. Remove unmodified function bodies (keep declarations optional)

        Args:
            file_path: Path to the modified source file
            modified_functions: List of function names to inject. If None, auto-detect.
            output_path: Output path for patch file. If None, auto-generate.

        Returns:
            Tuple of (patch_content, list_of_injected_functions)
        """
        # Read current content
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            current_content = f.read()

        # Auto-detect modified functions if not specified
        if modified_functions is None:
            modified_functions = self.detect_modified_functions(file_path)

        if not modified_functions:
            logger.info("No modified functions detected")
            return "", []

        logger.info(f"Generating patch for functions: {modified_functions}")

        # Parse current content
        functions = self.parser.parse_functions(current_content)

        # Build patch content
        # Strategy: Keep everything, but rename modified functions and remove others

        patch_lines = []
        lines = current_content.split("\n")

        # Get the directory of the source file for resolving relative includes
        source_dir = os.path.dirname(os.path.abspath(file_path))

        # Track which lines belong to functions
        line_to_func = {}  # line_num -> (func_name, is_modified)
        for name, info in functions.items():
            is_modified = name in modified_functions
            for line_num in range(info.start_line, info.end_line + 1):
                line_to_func[line_num] = (name, is_modified)

        # Add header comment
        patch_lines.append("/**")
        patch_lines.append(" * Auto-generated patch file by FPBInject")
        patch_lines.append(f" * Source: {file_path}")
        patch_lines.append(f" * Modified functions: {', '.join(modified_functions)}")
        patch_lines.append(" */")
        patch_lines.append("")

        # Process each line
        current_func = None
        skip_until_end = False

        for line_num, line in enumerate(lines, 1):
            if line_num in line_to_func:
                func_name, is_modified = line_to_func[line_num]

                if func_name != current_func:
                    # Entering a new function
                    current_func = func_name
                    skip_until_end = not is_modified

                if skip_until_end:
                    # Skip unmodified function body
                    continue

                if is_modified:
                    # Check if this line contains the function name (for renaming)
                    func_info = functions[func_name]
                    if line_num == func_info.start_line:
                        # This is the function signature line, rename it
                        # Find and replace the function name
                        renamed_line = self._rename_function_in_line(
                            line, func_name, f"inject_{func_name}"
                        )
                        patch_lines.append(renamed_line)
                    else:
                        patch_lines.append(line)
            else:
                # Not inside a function, keep the line
                current_func = None
                skip_until_end = False

                # Convert relative #include to absolute path
                converted_line = self._convert_include_path(line, source_dir)
                patch_lines.append(converted_line)

        patch_content = "\n".join(patch_lines)

        # Save to file if output_path specified
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(patch_content)
            logger.info(f"Patch saved to: {output_path}")

        return patch_content, modified_functions

    def _rename_function_in_line(self, line: str, old_name: str, new_name: str) -> str:
        """
        Rename a function in a line of code.

        Handles cases like:
        - void * lv_malloc(size_t size)
        - static inline void foo(void)
        - __attribute__((xxx)) int bar(int x)
        """
        # Use word boundary to replace function name
        pattern = r"\b" + re.escape(old_name) + r"\b"
        return re.sub(pattern, new_name, line, count=1)

    def _convert_include_path(self, line: str, source_dir: str) -> str:
        """
        Convert relative #include paths to absolute paths.

        Examples:
            #include "lv_mem.h"          -> #include "/abs/path/to/lv_mem.h"
            #include "../misc/lv_log.h"  -> #include "/abs/path/to/misc/lv_log.h"
            #include <stdio.h>           -> #include <stdio.h> (unchanged)
        """
        # Match #include "..." (not <...>)
        match = re.match(r'^(\s*#\s*include\s*)"([^"]+)"(.*)$', line)
        if not match:
            return line

        prefix = match.group(1)
        include_path = match.group(2)
        suffix = match.group(3)

        # Skip if already absolute
        if os.path.isabs(include_path):
            return line

        # Resolve relative path
        abs_path = os.path.normpath(os.path.join(source_dir, include_path))

        # Check if file exists
        if os.path.exists(abs_path):
            return f'{prefix}"{abs_path}"{suffix}'
        else:
            # Keep original if file not found (might be in system include path)
            logger.debug(f"Include file not found: {abs_path}, keeping original")
            return line

    def generate_patch_from_diff(
        self,
        file_path: str,
        output_dir: str = None,
    ) -> Tuple[Optional[str], List[str]]:
        """
        High-level API: Generate patch from a modified file.

        Args:
            file_path: Path to the modified C/C++ file
            output_dir: Directory to save patch file

        Returns:
            Tuple of (patch_file_path, list_of_injected_functions)
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None, []

        # Detect modifications
        modified = self.detect_modified_functions(file_path)
        if not modified:
            logger.info(f"No modifications detected in {file_path}")
            return None, []

        # Generate output path
        if output_dir:
            basename = os.path.basename(file_path)
            name, ext = os.path.splitext(basename)
            output_path = os.path.join(output_dir, f"patch_{name}{ext}")
        else:
            output_path = None

        # Generate patch
        patch_content, injected = self.generate_patch(file_path, modified, output_path)

        return output_path, injected


def check_dependencies() -> dict:
    """Check if required dependencies are available."""
    status = {
        "tree_sitter": TREE_SITTER_AVAILABLE,
        "git": False,
    }

    # Check git
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

    print("Dependency check:")
    deps = check_dependencies()
    for name, available in deps.items():
        status = "✓" if available else "✗"
        print(f"  {status} {name}")

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"\nAnalyzing: {file_path}")

        gen = PatchGenerator()

        # Detect modifications
        modified = gen.detect_modified_functions(file_path)
        print(f"\nModified functions: {modified}")

        if modified:
            # Generate patch
            patch_content, injected = gen.generate_patch(file_path, modified)
            print(f"\n--- Generated Patch ---")
            print(patch_content[:2000])
            if len(patch_content) > 2000:
                print(f"... ({len(patch_content)} total chars)")
    else:
        print("\nUsage: python patch_generator.py <file.c>")

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
    is_static: bool = False  # Whether the function is static


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
            is_static=self._is_static_function(node, source_code),
        )

    def _is_static_function(self, node, source_code: str) -> bool:
        """Check if a function is declared as static."""
        # Look for storage_class_specifier with 'static'
        for child in node.children:
            if child.type == "storage_class_specifier":
                specifier = source_code[child.start_byte : child.end_byte]
                if specifier == "static":
                    return True
        return False

    def _find_identifier(self, node, source_code: str) -> Optional[str]:
        """Recursively find the identifier (function name) in a declarator."""
        if node.type == "identifier":
            return source_code[node.start_byte : node.end_byte]

        for child in node.children:
            result = self._find_identifier(child, source_code)
            if result:
                return result

        return None

    def find_called_functions(
        self, func_code: str, all_functions: Dict[str, FunctionInfo]
    ) -> List[str]:
        """
        Find all function calls within a function's code.

        Args:
            func_code: The source code of the function
            all_functions: Dictionary of all functions in the file

        Returns:
            List of function names that are called
        """
        called = []

        if self._parser:
            # Use tree-sitter for accurate parsing
            tree = self._parser.parse(bytes(func_code, "utf-8"))
            called = self._find_calls_tree_sitter(
                tree.root_node, func_code, all_functions
            )
        else:
            # Regex fallback
            called = self._find_calls_regex(func_code, all_functions)

        return list(set(called))  # Remove duplicates

    def _find_calls_tree_sitter(
        self, node, source_code: str, all_functions: Dict[str, FunctionInfo]
    ) -> List[str]:
        """Find function calls using tree-sitter."""
        calls = []

        if node.type == "call_expression":
            # Get the function being called
            func_node = node.child_by_field_name("function")
            if func_node and func_node.type == "identifier":
                func_name = source_code[func_node.start_byte : func_node.end_byte]
                if func_name in all_functions:
                    calls.append(func_name)

        for child in node.children:
            calls.extend(
                self._find_calls_tree_sitter(child, source_code, all_functions)
            )

        return calls

    def _find_calls_regex(
        self, func_code: str, all_functions: Dict[str, FunctionInfo]
    ) -> List[str]:
        """Find function calls using regex (fallback)."""
        calls = []
        # Pattern: identifier followed by (
        pattern = r"\b(\w+)\s*\("
        for match in re.finditer(pattern, func_code):
            func_name = match.group(1)
            if func_name in all_functions:
                calls.append(func_name)
        return calls

    def _parse_with_regex(self, source_code: str) -> Dict[str, FunctionInfo]:
        """Fallback parser using regex (less accurate)."""
        functions = {}

        # Pattern to match function definitions
        # Handle multi-line signatures where { is on the next line
        # Pattern matches: return_type function_name(params) with optional newline before {
        pattern = r"""
            ^                           # Start of line
            ([\w\s\*]+?)                # Return type (capture for finding signature start)
            \s+                         # Whitespace
            (\w+)                       # Function name (capture)
            \s*                         # Optional whitespace
            \([^)]*\)                   # Parameters
            \s*                         # Optional whitespace (can include newline)
            \{                          # Opening brace
        """

        lines = source_code.split("\n")
        i = 0
        while i < len(lines):
            # Try to match function start
            remaining = "\n".join(lines[i:])
            match = re.match(pattern, remaining, re.MULTILINE | re.VERBOSE)

            if match:
                func_name = match.group(2)

                # Find which line contains the function name (signature line)
                # The match starts at line i, but we need to find the line with func_name
                signature_line = i
                matched_text = match.group(0)
                lines_in_match = matched_text.count("\n")

                # Search for the line containing the function name
                for offset in range(lines_in_match + 1):
                    if func_name in lines[i + offset]:
                        signature_line = i + offset
                        break

                start_line = signature_line + 1  # Convert to 1-based

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

        logger.info(f"Detecting modified functions in: {file_path}")

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

        logger.info(f"Original file has {len(original_funcs)} functions")
        logger.info(f"Current file has {len(current_funcs)} functions")

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
                # Log first 200 chars of diff for debugging
                orig_preview = original_funcs[name].code[:100].replace("\n", "\\n")
                curr_preview = current_info.code[:100].replace("\n", "\\n")
                logger.debug(f"Original (first 100 chars): {orig_preview}")
                logger.debug(f"Current (first 100 chars): {curr_preview}")

        logger.info(f"Total modified functions: {len(modified)} - {modified}")
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

        # Analyze dependencies: find static functions called by modified functions
        # These need to be included because they might be inlined in the ELF
        dependent_static_funcs = self._find_dependent_static_functions(
            functions, modified_functions
        )

        # Combine modified functions and their static dependencies
        functions_to_keep = set(modified_functions) | dependent_static_funcs
        logger.info(f"Functions to keep: {functions_to_keep}")
        if dependent_static_funcs:
            logger.info(f"Including static dependencies: {dependent_static_funcs}")

        # Track which lines belong to functions
        line_to_func = {}  # line_num -> (func_name, should_keep, should_rename)
        for name, info in functions.items():
            should_keep = name in functions_to_keep
            should_rename = (
                name in modified_functions
            )  # Only rename the actually modified ones
            for line_num in range(info.start_line, info.end_line + 1):
                line_to_func[line_num] = (name, should_keep, should_rename)
            # Log info for modified functions
            if should_rename:
                logger.info(
                    f"Function '{name}': start_line={info.start_line}, end_line={info.end_line}"
                )
                # Log the actual content of start_line
                if info.start_line <= len(lines):
                    logger.info(
                        f"Start line content: {lines[info.start_line - 1].strip()}"
                    )

        # Add header comment
        patch_lines.append("/**")
        patch_lines.append(" * Auto-generated patch file by FPBInject")
        patch_lines.append(f" * Source: {file_path}")
        patch_lines.append(f" * Modified functions: {', '.join(modified_functions)}")
        if dependent_static_funcs:
            patch_lines.append(
                f" * Static dependencies: {', '.join(dependent_static_funcs)}"
            )
        patch_lines.append(" */")
        patch_lines.append("")

        # Process each line
        current_func = None
        skip_until_end = False

        # Track conditional compilation nesting to remove feature guards
        # We'll remove #if/#ifdef/#ifndef ... #endif blocks that guard entire features
        # These often prevent inject functions from being compiled
        ifdef_stack = []  # Stack of (#if line_num, condition)

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Track conditional compilation directives
            if stripped.startswith("#if"):
                # Check if this is a feature guard (like #if LV_USE_NUTTX)
                # We'll comment these out to ensure our inject functions are compiled
                ifdef_stack.append((line_num, stripped))
                # Comment out the #if directive instead of including it
                patch_lines.append(f"// [FPBInject removed] {line}")
                continue
            elif stripped.startswith("#else") or stripped.startswith("#elif"):
                if ifdef_stack:
                    # Comment out
                    patch_lines.append(f"// [FPBInject removed] {line}")
                    continue
            elif stripped.startswith("#endif"):
                if ifdef_stack:
                    ifdef_stack.pop()
                    # Comment out the #endif
                    patch_lines.append(f"// [FPBInject removed] {line}")
                    continue

            if line_num in line_to_func:
                func_name, should_keep, should_rename = line_to_func[line_num]

                if func_name != current_func:
                    # Entering a new function
                    current_func = func_name
                    skip_until_end = not should_keep
                    logger.debug(
                        f"Line {line_num}: Entering function '{func_name}', should_keep={should_keep}, should_rename={should_rename}"
                    )

                if skip_until_end:
                    # Skip function body that we don't need
                    continue

                if should_keep:
                    # Check if this line contains the function name (for renaming)
                    func_info = functions[func_name]
                    if line_num == func_info.start_line and should_rename:
                        # This is the function signature line, rename it
                        # Find and replace the function name
                        renamed_line = self._rename_function_in_line(
                            line, func_name, f"inject_{func_name}"
                        )
                        logger.info(
                            f"Renaming function '{func_name}' to 'inject_{func_name}'"
                        )
                        logger.info(f"Original line ({line_num}): {line.strip()}")
                        logger.info(f"Renamed line:  {renamed_line.strip()}")
                        # Verify rename was successful
                        if f"inject_{func_name}" in renamed_line:
                            logger.info(f"Rename successful!")
                        else:
                            logger.warning(
                                f"Rename may have FAILED! inject_{func_name} not found in renamed_line"
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

        # Verify inject_ functions exist in generated patch
        import re

        inject_funcs_in_patch = re.findall(r"\binject_\w+", patch_content)
        if inject_funcs_in_patch:
            logger.info(
                f"Verified inject_ functions in patch: {list(set(inject_funcs_in_patch))[:10]}"
            )
        else:
            logger.warning("WARNING: No inject_ functions found in generated patch!")
            logger.warning(f"Modified functions were: {modified_functions}")
            logger.warning(f"Patch content length: {len(patch_content)} chars")

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

    def _find_dependent_static_functions(
        self,
        all_functions: Dict[str, FunctionInfo],
        modified_functions: List[str],
    ) -> set:
        """
        Find all static functions that are called by the modified functions.

        This is important because static functions might be inlined by the compiler
        and thus not present in the ELF symbol table.

        Args:
            all_functions: Dictionary of all functions in the file
            modified_functions: List of modified function names

        Returns:
            Set of static function names that should be included
        """
        dependent_statics = set()
        visited = set()

        def find_dependencies(func_name: str):
            """Recursively find static function dependencies."""
            if func_name in visited:
                return
            visited.add(func_name)

            if func_name not in all_functions:
                return

            func_info = all_functions[func_name]
            called_funcs = self.parser.find_called_functions(
                func_info.code, all_functions
            )

            for called_name in called_funcs:
                if called_name in all_functions:
                    called_info = all_functions[called_name]
                    # Include static functions (they might be inlined in ELF)
                    if called_info.is_static and called_name not in modified_functions:
                        dependent_statics.add(called_name)
                        logger.debug(
                            f"Found static dependency: {func_name} -> {called_name}"
                        )
                        # Recursively find dependencies of this static function
                        find_dependencies(called_name)

        # Find dependencies for all modified functions
        for func_name in modified_functions:
            find_dependencies(func_name)

        return dependent_statics

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

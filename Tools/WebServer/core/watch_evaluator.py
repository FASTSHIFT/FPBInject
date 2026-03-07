#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Watch Expression Evaluator for FPBInject Web Server.

Evaluates C/C++ watch expressions using GDB for type resolution
and serial protocol for device memory reads.
Supports: symbol names, type casts, pointer dereference, array slices,
member access, and enum display.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Security limits
MAX_EXPR_LEN = 256
MAX_READ_SIZE = 65536  # 64KB
MAX_DEREF_DEPTH = 5
MAX_ARRAY_COUNT = 1024

# Blacklisted GDB commands (prevent state modification)
_BLACKLISTED_COMMANDS = {"set", "call", "run", "continue", "step", "next", "finish"}


class WatchEvaluator:
    """Evaluate watch expressions using GDB type info + serial memory reads."""

    def __init__(self, gdb_session):
        self._gdb = gdb_session

    def evaluate(self, expr):
        """Evaluate a watch expression. Returns dict with type info and address.

        Does NOT read device memory — caller decides whether to read.

        Returns:
            dict with keys: addr, size, type_name, is_pointer, is_aggregate,
                  struct_layout, array_layout, error
        """
        expr = expr.strip()
        if not expr:
            return {"error": "Empty expression"}
        if len(expr) > MAX_EXPR_LEN:
            return {"error": f"Expression too long (max {MAX_EXPR_LEN} chars)"}

        # Security: check for blacklisted commands
        first_word = expr.split()[0].lower() if expr.split() else ""
        if first_word in _BLACKLISTED_COMMANDS:
            return {"error": f"Forbidden command: {first_word}"}

        # Check for array slice syntax: ((T *)ADDR)[start:count] or [count]
        slice_match = re.search(r"\[(\d+)?:(\d+)\]\s*$", expr)
        if slice_match:
            return self._evaluate_array_slice(expr, slice_match)

        # Standard expression evaluation
        try:
            type_name = self._get_whatis(expr)
            if type_name is None:
                return {"error": f"Cannot resolve type for: {expr}"}

            size = self._get_sizeof_expr(expr)
            addr = self._resolve_expr_addr(expr, type_name)
            if addr is None:
                return {"error": f"Cannot resolve address for: {expr}"}

            is_pointer = type_name.rstrip().endswith("*")
            is_aggregate = self._is_aggregate_type(type_name)

            struct_layout = None
            if is_aggregate:
                struct_layout = self._get_struct_layout(type_name)

            return {
                "addr": addr,
                "size": size,
                "type_name": type_name,
                "is_pointer": is_pointer,
                "is_aggregate": is_aggregate,
                "struct_layout": struct_layout,
                "error": None,
            }
        except Exception as e:
            logger.exception(f"Watch evaluate error for '{expr}': {e}")
            return {"error": str(e)}

    def get_deref_info(self, type_name):
        """Get type info for dereferencing a pointer type.

        Args:
            type_name: pointer type string, e.g. "uint8_t *"

        Returns:
            dict with target_type, target_size, is_aggregate, struct_layout
        """
        if not type_name or not type_name.rstrip().endswith("*"):
            return {"error": "Not a pointer type"}

        target_type = type_name.rstrip()
        # Remove trailing '*' and whitespace
        if target_type.endswith("*"):
            target_type = target_type[:-1].rstrip()

        target_size = self._get_sizeof_type(target_type)
        is_aggregate = self._is_aggregate_type(target_type)

        struct_layout = None
        if is_aggregate:
            struct_layout = self._get_struct_layout(target_type)

        return {
            "target_type": target_type,
            "target_size": target_size,
            "is_aggregate": is_aggregate,
            "struct_layout": struct_layout,
            "error": None,
        }

    def _evaluate_array_slice(self, expr, slice_match):
        """Evaluate array slice expression like ((int *)0x20000000)[0:10]."""
        start = int(slice_match.group(1) or 0)
        count = int(slice_match.group(2))

        if count <= 0:
            return {"error": "Array count must be positive"}
        if count > MAX_ARRAY_COUNT:
            return {"error": f"Array count exceeds limit ({MAX_ARRAY_COUNT})"}

        base_expr = expr[: slice_match.start()].strip()
        if not base_expr:
            return {"error": "Missing base expression for array slice"}

        # Get element type from base expression
        base_type = self._get_whatis(base_expr)
        if base_type is None:
            return {"error": f"Cannot resolve type for: {base_expr}"}

        # Determine element type (strip pointer)
        elem_type = base_type.rstrip()
        if elem_type.endswith("*"):
            elem_type = elem_type[:-1].rstrip()
        else:
            return {"error": f"Base expression is not a pointer: {base_type}"}

        elem_size = self._get_sizeof_type(elem_type)
        if elem_size <= 0:
            return {"error": f"Cannot determine element size for: {elem_type}"}

        # Resolve base address
        addr = self._resolve_expr_addr(base_expr, base_type)
        if addr is None:
            return {"error": f"Cannot resolve address for: {base_expr}"}

        # Calculate slice address and total size
        slice_addr = addr + start * elem_size
        total_size = count * elem_size

        if total_size > MAX_READ_SIZE:
            return {"error": f"Array slice size exceeds {MAX_READ_SIZE} bytes"}

        # Build array layout
        array_layout = [
            {
                "name": f"[{start + i}]",
                "type_name": elem_type,
                "offset": i * elem_size,
                "size": elem_size,
            }
            for i in range(count)
        ]

        return {
            "addr": slice_addr,
            "size": total_size,
            "type_name": f"{elem_type}[{count}]",
            "is_pointer": False,
            "is_aggregate": True,
            "struct_layout": array_layout,
            "error": None,
        }

    def _get_whatis(self, expr):
        """Get type of expression via GDB 'whatis'."""
        output = self._gdb.execute(f"whatis {expr}")
        if output:
            m = re.search(r"type\s*=\s*(.+)", output)
            if m:
                return m.group(1).strip()
        return None

    def _get_sizeof_expr(self, expr):
        """Get sizeof an expression."""
        output = self._gdb.execute(f"print sizeof({expr})")
        if output:
            m = re.search(r"\$\d+\s*=\s*(\d+)", output)
            if m:
                return int(m.group(1))
        return 0

    def _get_sizeof_type(self, type_name):
        """Get sizeof a type name."""
        output = self._gdb.execute(f"print sizeof({type_name})")
        if output:
            m = re.search(r"\$\d+\s*=\s*(\d+)", output)
            if m:
                return int(m.group(1))
        return 0

    def _resolve_expr_addr(self, expr, type_name):
        """Resolve the memory address of an expression.

        Strategy:
        1. If expression contains hex literal with cast → extract literal
        2. Pure symbol name → GDB 'info address'
        3. Complex expression → GDB 'print &(expr)'
        """
        # Case 1: Cast expression with address literal
        # e.g. *(struct foo *)0x20001000 or (uint32_t *)0x40021000
        m = re.search(r"0x([0-9a-fA-F]+)", expr)
        if m and ("*)" in expr or expr.lstrip().startswith("*")):
            return int(m.group(1), 16)

        # Case 2: Simple symbol name (no operators)
        if re.match(r"^[a-zA-Z_]\w*(\.\d+)?$", expr):
            output = self._gdb.execute(f"info address {expr}")
            if output:
                addr = self._gdb._parse_address_from_info(output)
                if addr is not None:
                    return addr

        # Case 3: Complex expression → print &(expr)
        output = self._gdb.execute(f"print &({expr})")
        if output:
            m = re.search(r"0x([0-9a-fA-F]+)", output)
            if m:
                return int(m.group(1), 16)

        return None

    def _is_aggregate_type(self, type_name):
        """Check if type is struct/class/union (aggregate)."""
        t = type_name.strip().rstrip("*").strip()
        return bool(
            re.match(r"^(struct|class|union)\s+", t)
            or re.match(r"^(const\s+)?(struct|class|union)\s+", t)
        )

    def _get_struct_layout(self, type_name):
        """Get struct layout via GDB ptype /o."""
        # Strip pointer suffix for ptype
        t = type_name.rstrip()
        while t.endswith("*"):
            t = t[:-1].rstrip()

        output = self._gdb.execute(f"ptype /o {t}")
        if output:
            return self._gdb._parse_ptype_output(output)
        return None

    def resolve_enum_display(self, type_name, raw_value):
        """Resolve enum value to name via GDB ptype.

        Args:
            type_name: enum type, e.g. "enum state_t"
            raw_value: integer value

        Returns:
            str: enum name or None
        """
        output = self._gdb.execute(f"ptype {type_name}")
        if not output:
            return None

        # Parse "type = enum state_t {IDLE = 0, RUNNING = 1, ERROR = 2}"
        for m in re.finditer(r"(\w+)\s*=\s*(-?\d+)", output):
            name = m.group(1)
            val = int(m.group(2))
            if val == raw_value:
                return name
        return None

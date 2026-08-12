"""Tests for core/gdb_json_print.py with mocked gdb module."""

import json
import sys
import types
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Build a fake 'gdb' module so gdb_json_print can be imported outside GDB.
# ---------------------------------------------------------------------------

_fake_gdb = types.ModuleType("gdb")

# Type codes
_fake_gdb.TYPE_CODE_PTR = 1
_fake_gdb.TYPE_CODE_STRUCT = 2
_fake_gdb.TYPE_CODE_UNION = 3
_fake_gdb.TYPE_CODE_ARRAY = 4
_fake_gdb.TYPE_CODE_ENUM = 5
_fake_gdb.TYPE_CODE_FLT = 6
_fake_gdb.TYPE_CODE_INT = 7
_fake_gdb.TYPE_CODE_FUNC = 8

# gdb.error
_fake_gdb.error = type("error", (Exception,), {})

# gdb.COMMAND_DATA
_fake_gdb.COMMAND_DATA = 0

# gdb.Command base class
_fake_gdb.Command = type("Command", (), {"__init__": lambda self, *a, **kw: None})

# Helpers (overridden per-test as needed)
_fake_gdb.string_to_argv = MagicMock(return_value=[])
_fake_gdb.parse_and_eval = MagicMock()
_fake_gdb.write = MagicMock()

# Inject before importing the module under test
sys.modules["gdb"] = _fake_gdb

# Now safe to import
from fpbinject.core.gdb_json_print import _val_to_json, JsonPrintCommand  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers to build mock gdb.Value / gdb.Type objects
# ---------------------------------------------------------------------------


def _make_type(code, target_code=None, fields=None, array_range=None):
    """Return a mock gdb.Type."""
    t = MagicMock()
    t.code = code
    t.strip_typedefs.return_value = t
    t.__str__ = lambda self: "mock_type"

    if target_code is not None:
        tgt = MagicMock()
        tgt.code = target_code
        tgt.strip_typedefs.return_value = tgt
        tgt.__str__ = lambda self: "target_type"
        t.target.return_value = tgt

    if fields is not None:
        t.fields.return_value = fields

    if array_range is not None:
        t.range.return_value = array_range

    return t


def _make_val(type_mock, int_val=0, float_val=0.0, str_val="?", children=None):
    """Return a mock gdb.Value."""
    v = MagicMock()
    v.type = type_mock
    v.type.strip_typedefs.return_value = type_mock
    v.__int__ = lambda self: int_val
    v.__float__ = lambda self: float_val
    v.__str__ = lambda self: str_val

    if children is not None:
        v.__getitem__ = lambda self, key: children[key]

    return v


def _make_field(name):
    f = MagicMock()
    f.name = name
    return f


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValToJsonScalar(unittest.TestCase):
    def test_int_value(self):
        t = _make_type(_fake_gdb.TYPE_CODE_INT)
        v = _make_val(t, int_val=42)
        self.assertEqual(_val_to_json(v), 42)

    def test_float_value(self):
        t = _make_type(_fake_gdb.TYPE_CODE_FLT)
        v = _make_val(t, float_val=3.14)
        self.assertAlmostEqual(_val_to_json(v), 3.14)

    def test_scalar_str_fallback(self):
        """When int() raises, fall back to str()."""
        t = _make_type(_fake_gdb.TYPE_CODE_INT)
        v = MagicMock()
        v.type = t
        v.type.strip_typedefs.return_value = t
        v.__int__ = MagicMock(side_effect=ValueError("bad"))
        v.__str__ = lambda self: "fallback"
        self.assertEqual(_val_to_json(v), "fallback")


class TestValToJsonPointer(unittest.TestCase):
    def test_data_pointer(self):
        t = _make_type(_fake_gdb.TYPE_CODE_PTR, target_code=_fake_gdb.TYPE_CODE_INT)
        v = _make_val(t, int_val=0x20001000)
        result = _val_to_json(v)
        self.assertEqual(result["_kind"], "ptr")
        self.assertEqual(result["_addr"], "0x20001000")

    def test_func_pointer(self):
        t = _make_type(_fake_gdb.TYPE_CODE_PTR, target_code=_fake_gdb.TYPE_CODE_FUNC)
        v = _make_val(t, int_val=0x08000100)
        result = _val_to_json(v)
        self.assertEqual(result["_kind"], "func_ptr")

    def test_pointer_gdb_error(self):
        """When int(val) raises gdb.error, addr should be 0."""
        t = _make_type(_fake_gdb.TYPE_CODE_PTR, target_code=_fake_gdb.TYPE_CODE_INT)
        v = MagicMock()
        v.type = t
        v.type.strip_typedefs.return_value = t
        v.__int__ = MagicMock(side_effect=_fake_gdb.error("optimized out"))
        result = _val_to_json(v)
        self.assertEqual(result["_addr"], "0x00000000")


class TestValToJsonStruct(unittest.TestCase):
    def test_struct_fields(self):
        f1 = _make_field("x")
        f2 = _make_field("y")
        t = _make_type(_fake_gdb.TYPE_CODE_STRUCT, fields=[f1, f2])

        int_type = _make_type(_fake_gdb.TYPE_CODE_INT)
        child_x = _make_val(int_type, int_val=10)
        child_y = _make_val(int_type, int_val=20)

        v = _make_val(t, children={"x": child_x, "y": child_y})
        result = _val_to_json(v)
        self.assertEqual(result, {"x": 10, "y": 20})

    def test_struct_max_depth(self):
        t = _make_type(_fake_gdb.TYPE_CODE_STRUCT, fields=[])
        v = _make_val(t)
        result = _val_to_json(v, depth=2, max_depth=2)
        self.assertEqual(result["_kind"], "struct")

    def test_struct_field_none_name_skipped(self):
        f = _make_field(None)
        t = _make_type(_fake_gdb.TYPE_CODE_STRUCT, fields=[f])
        v = _make_val(t)
        result = _val_to_json(v)
        self.assertEqual(result, {})

    def test_struct_field_error(self):
        f = _make_field("bad")
        t = _make_type(_fake_gdb.TYPE_CODE_STRUCT, fields=[f])
        v = MagicMock()
        v.type = t
        v.type.strip_typedefs.return_value = t
        v.__getitem__ = MagicMock(side_effect=RuntimeError("cannot access"))
        result = _val_to_json(v)
        self.assertEqual(result["bad"]["_kind"], "error")

    def test_union(self):
        f = _make_field("val")
        t = _make_type(_fake_gdb.TYPE_CODE_UNION, fields=[f])
        int_type = _make_type(_fake_gdb.TYPE_CODE_INT)
        child = _make_val(int_type, int_val=99)
        v = _make_val(t, children={"val": child})
        result = _val_to_json(v)
        self.assertEqual(result, {"val": 99})


class TestValToJsonArray(unittest.TestCase):
    def test_array(self):
        int_type = _make_type(_fake_gdb.TYPE_CODE_INT)
        elems = [_make_val(int_type, int_val=i) for i in range(3)]
        t = _make_type(_fake_gdb.TYPE_CODE_ARRAY, array_range=(0, 2))
        v = _make_val(t, children=elems)
        result = _val_to_json(v)
        self.assertEqual(result, [0, 1, 2])

    def test_array_element_error(self):
        """Array element access raises → stop early."""
        t = _make_type(_fake_gdb.TYPE_CODE_ARRAY, array_range=(0, 4))
        v = MagicMock()
        v.type = t
        v.type.strip_typedefs.return_value = t
        v.__getitem__ = MagicMock(side_effect=RuntimeError("bad"))
        result = _val_to_json(v)
        self.assertEqual(result, [])


class TestValToJsonEnum(unittest.TestCase):
    def test_enum(self):
        t = _make_type(_fake_gdb.TYPE_CODE_ENUM)
        v = _make_val(t, int_val=2, str_val="MY_ENUM_VAL")
        result = _val_to_json(v)
        self.assertEqual(result["_kind"], "enum")
        self.assertEqual(result["_val"], 2)
        self.assertEqual(result["_name"], "MY_ENUM_VAL")

    def test_enum_error_fallback(self):
        t = _make_type(_fake_gdb.TYPE_CODE_ENUM)
        v = MagicMock()
        v.type = t
        v.type.strip_typedefs.return_value = t
        v.__int__ = MagicMock(side_effect=Exception("bad"))
        v.__str__ = lambda self: "UNKNOWN"
        result = _val_to_json(v)
        self.assertEqual(result, "UNKNOWN")


class TestJsonPrintCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = JsonPrintCommand()
        _fake_gdb.write.reset_mock()
        _fake_gdb.string_to_argv.reset_mock()
        _fake_gdb.parse_and_eval.reset_mock()
        _fake_gdb.parse_and_eval.side_effect = None

    def test_no_args(self):
        _fake_gdb.string_to_argv.return_value = []
        self.cmd.invoke("", False)
        _fake_gdb.write.assert_called_once_with("Usage: json-print EXPR [MAX_DEPTH]\n")

    def test_expr_only(self):
        int_type = _make_type(_fake_gdb.TYPE_CODE_INT)
        mock_val = _make_val(int_type, int_val=42)
        _fake_gdb.string_to_argv.return_value = ["my_var"]
        _fake_gdb.parse_and_eval.return_value = mock_val
        self.cmd.invoke("my_var", False)
        output = _fake_gdb.write.call_args[0][0]
        self.assertEqual(json.loads(output), 42)

    def test_expr_with_max_depth(self):
        int_type = _make_type(_fake_gdb.TYPE_CODE_INT)
        mock_val = _make_val(int_type, int_val=7)
        _fake_gdb.string_to_argv.return_value = ["x", "3"]
        _fake_gdb.parse_and_eval.return_value = mock_val
        self.cmd.invoke("x 3", False)
        output = _fake_gdb.write.call_args[0][0]
        self.assertEqual(json.loads(output), 7)

    def test_eval_exception(self):
        _fake_gdb.string_to_argv.return_value = ["bad_expr"]
        _fake_gdb.parse_and_eval.side_effect = RuntimeError("No symbol")
        self.cmd.invoke("bad_expr", False)
        output = _fake_gdb.write.call_args[0][0]
        result = json.loads(output)
        self.assertEqual(result["_kind"], "error")
        self.assertIn("No symbol", result["_msg"])


if __name__ == "__main__":
    unittest.main()

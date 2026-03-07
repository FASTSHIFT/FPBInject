"""GDB Python script: register 'json-print' command for structured output.

Sourced by GDBSession on startup. Provides a custom GDB command that
evaluates an expression and outputs the result as JSON, recursively
traversing struct/union/array/pointer types via the gdb.Value API.

This replaces fragile text parsing of 'print' output for struct values.

Usage inside GDB:
    json-print EXPR [MAX_DEPTH]
    json-print "*((struct my_type *)0x20001000)" 2
"""

import gdb
import json


def _val_to_json(val, depth=0, max_depth=2):
    """Convert a gdb.Value to a JSON-serializable Python object.

    Returns:
        - int/float for scalars
        - dict with "_kind" key for pointers, enums, errors
        - dict of {field: value} for structs/unions
        - list for arrays
    """
    t = val.type.strip_typedefs()
    code = t.code

    # Pointer
    if code == gdb.TYPE_CODE_PTR:
        try:
            addr = int(val)
        except gdb.error:
            addr = 0
        target = t.target().strip_typedefs()
        if target.code == gdb.TYPE_CODE_FUNC:
            return {
                "_kind": "func_ptr",
                "_addr": "0x{:08x}".format(addr),
                "_sig": str(t),
            }
        return {
            "_kind": "ptr",
            "_addr": "0x{:08x}".format(addr),
            "_target": str(t.target()),
        }

    # Struct / Union
    if code in (gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION):
        if depth >= max_depth:
            return {"_kind": "struct", "_type": str(val.type)}
        d = {}
        for f in t.fields():
            if f.name is None:
                continue
            try:
                d[f.name] = _val_to_json(val[f.name], depth + 1, max_depth)
            except Exception as e:
                d[f.name] = {"_kind": "error", "_msg": str(e)}
        return d

    # Array
    if code == gdb.TYPE_CODE_ARRAY:
        r = t.range()
        n = min(r[1] - r[0] + 1, 64)
        result = []
        for i in range(n):
            try:
                result.append(_val_to_json(val[i], depth + 1, max_depth))
            except Exception:
                break
        return result

    # Enum
    if code == gdb.TYPE_CODE_ENUM:
        try:
            return {"_kind": "enum", "_val": int(val), "_name": str(val)}
        except Exception:
            return str(val)

    # Scalar (int, float, bool, char)
    try:
        if code == gdb.TYPE_CODE_FLT:
            return float(val)
        return int(val)
    except Exception:
        return str(val)


class JsonPrintCommand(gdb.Command):
    """json-print EXPR [MAX_DEPTH] - evaluate and output as JSON."""

    def __init__(self):
        super(JsonPrintCommand, self).__init__("json-print", gdb.COMMAND_DATA)

    def invoke(self, arg, from_tty):
        args = gdb.string_to_argv(arg)
        if not args:
            gdb.write("Usage: json-print EXPR [MAX_DEPTH]\n")
            return
        expr = args[0]
        max_depth = int(args[1]) if len(args) > 1 else 2
        try:
            val = gdb.parse_and_eval(expr)
            result = _val_to_json(val, max_depth=max_depth)
            gdb.write(json.dumps(result, ensure_ascii=False) + "\n")
        except Exception as e:
            gdb.write(
                json.dumps({"_kind": "error", "_msg": str(e)}, ensure_ascii=False)
                + "\n"
            )


JsonPrintCommand()

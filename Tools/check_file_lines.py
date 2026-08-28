#!/usr/bin/env python3
#
# check_file_lines.py - Enforce a max line count on first-party source files.
#
# Rationale: oversized files are hard to review and navigate. This guards
# against NEW files growing without bound. Vendored/generated code and tests
# are exempt (they legitimately run long). A small grandfather allowlist holds
# files that already exceed the limit; they must be split over time, and no
# file may be ADDED to the allowlist without a deliberate decision.
#
# Usage:
#   Tools/check_file_lines.py [--limit N] [path ...]
#     no paths  -> scan the whole first-party tree
#     paths     -> check only those files (used by the pre-commit hook for
#                  staged files); non-source/exempt paths are skipped
#
# Exit codes: 0 = OK, 1 = one or more non-exempt files exceed the limit.

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LIMIT = 1500

# Extensions considered "source" for this check.
SOURCE_EXTS = {".py", ".c", ".h", ".cpp", ".hpp", ".js"}

# Path fragments (posix-style) that are exempt: vendored, generated, tests.
EXEMPT_FRAGMENTS = (
    "project/platform/",  # STM32 CMSIS / StdPeriph (vendored)
    "project/arduinoapi/",  # Arduino API port (vendored)
    "/tests/",  # unit tests (py + js)
    "tools/webserver/tests/",
    "app/tests/",
    "/argparse/",  # vendored C argparse
    "/build/",
    "/node_modules/",
    "/__pycache__/",
    "static/js/lib/",  # vendored JS libs
)

# Files that already exceed the limit. They are allowed for now but MUST be
# split; do not add new entries here without agreement. Paths are repo-relative
# and posix-style.
GRANDFATHERED = {
    "Tools/WebServer/static/js/features/transfer.js",
    "Tools/WebServer/static/js/features/quick-commands.js",
    "Tools/WebServer/app/routes/symbols.py",
}


def _posix_rel(path: str) -> str:
    rel = os.path.relpath(os.path.abspath(path), REPO_ROOT)
    return rel.replace(os.sep, "/")


def _is_exempt(rel_posix: str) -> bool:
    low = "/" + rel_posix.lower()
    return any(frag in low for frag in EXEMPT_FRAGMENTS)


def _is_source(path: str) -> bool:
    return os.path.splitext(path)[1] in SOURCE_EXTS


def _count_lines(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _iter_tree():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        # Prune obvious heavy dirs early for speed.
        dirnames[:] = [
            d
            for d in dirnames
            if d not in {".git", "node_modules", "__pycache__", "build"}
        ]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if _is_source(full):
                yield full


def check(paths, limit):
    """Return list of (rel, lines) violations."""
    violations = []
    grandfathered_hits = []

    if paths:
        candidates = [p for p in paths if _is_source(p) and os.path.isfile(p)]
    else:
        candidates = list(_iter_tree())

    for full in candidates:
        rel = _posix_rel(full)
        if _is_exempt(rel):
            continue
        n = _count_lines(full)
        if n <= limit:
            continue
        if rel in GRANDFATHERED:
            grandfathered_hits.append((rel, n))
        else:
            violations.append((rel, n))

    return violations, grandfathered_hits


def main():
    ap = argparse.ArgumentParser(description="Enforce max source file line count.")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("paths", nargs="*", help="Specific files (default: whole tree)")
    args = ap.parse_args()

    violations, grandfathered = check(args.paths, args.limit)

    if grandfathered:
        print(
            f"ℹ️  {len(grandfathered)} grandfathered file(s) over {args.limit} "
            "lines (must be split over time):"
        )
        for rel, n in sorted(grandfathered, key=lambda x: -x[1]):
            print(f"    {n:>6}  {rel}")

    if violations:
        print(f"\n❌ {len(violations)} file(s) exceed the {args.limit}-line limit:")
        for rel, n in sorted(violations, key=lambda x: -x[1]):
            print(f"    {n:>6}  {rel}")
        print(
            "\nSplit the file into smaller modules. If a file legitimately must "
            "exceed the limit, add it to GRANDFATHERED in Tools/check_file_lines.py "
            "with reviewer agreement."
        )
        return 1

    print(f"✅ No non-exempt source file exceeds {args.limit} lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

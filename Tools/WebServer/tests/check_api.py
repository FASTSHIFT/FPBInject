#!/usr/bin/env python3
"""
API consistency checker - scans frontend and backend for API endpoint mismatches.
"""

import re
import os
from pathlib import Path
from collections import defaultdict


def find_backend_routes(routes_file):
    """Extract all API routes from routes.py"""
    routes = {}

    with open(routes_file, "r") as f:
        content = f.read()

    # Match @app.route("/api/...", methods=[...])
    pattern = r'@app\.route\(["\']([^"\']+)["\'](?:,\s*methods=\[([^\]]+)\])?\)'

    for match in re.finditer(pattern, content):
        path = match.group(1)
        methods_str = match.group(2) or '"GET"'
        # Parse methods
        methods = re.findall(r'"(\w+)"', methods_str)
        if not methods:
            methods = ["GET"]
        # Merge methods if path already exists
        if path in routes:
            routes[path] = list(set(routes[path] + methods))
        else:
            routes[path] = methods

    return routes


def find_frontend_api_calls(js_dir):
    """Extract all fetch() API calls from JavaScript files"""
    api_calls = []

    for js_file in Path(js_dir).rglob("*.js"):
        with open(js_file, "r") as f:
            content = f.read()

        # Match fetch('/api/...') or fetch(`/api/...`)
        # Pattern 1: fetch('/api/path')
        pattern1 = r"fetch\(['\"](/api/[^'\"?]+)"
        for match in re.finditer(pattern1, content):
            path = match.group(1)
            # Check if POST method is specified
            # Look for { method: 'POST' } nearby
            start = match.start()
            end = min(start + 200, len(content))
            context = content[start:end]
            if "method:" in context and "'POST'" in context or '"POST"' in context:
                method = "POST"
            elif (
                "method:" in context and "'DELETE'" in context or '"DELETE"' in context
            ):
                method = "DELETE"
            elif "method:" in context and "'PUT'" in context or '"PUT"' in context:
                method = "PUT"
            else:
                method = "GET"
            api_calls.append(
                {
                    "path": path,
                    "method": method,
                    "file": str(js_file),
                    "line": content[:start].count("\n") + 1,
                }
            )

        # Pattern 2: fetch(`/api/path...`)
        pattern2 = r"fetch\(`(/api/[^`?$]+)"
        for match in re.finditer(pattern2, content):
            path = match.group(1)
            # Remove template literal parts
            path = re.sub(r"\$\{[^}]+\}", "", path)
            start = match.start()
            end = min(start + 200, len(content))
            context = content[start:end]
            if "method:" in context and ("'POST'" in context or '"POST"' in context):
                method = "POST"
            else:
                method = "GET"
            api_calls.append(
                {
                    "path": path,
                    "method": method,
                    "file": str(js_file),
                    "line": content[:start].count("\n") + 1,
                }
            )

    return api_calls


def check_consistency(backend_routes, frontend_calls):
    """Check for mismatches between frontend and backend"""
    issues = []

    # Group frontend calls by path
    frontend_by_path = defaultdict(list)
    for call in frontend_calls:
        frontend_by_path[call["path"]].append(call)

    # Check each frontend call
    for path, calls in frontend_by_path.items():
        if path not in backend_routes:
            for call in calls:
                issues.append(
                    {
                        "type": "MISSING_ENDPOINT",
                        "severity": "ERROR",
                        "path": path,
                        "method": call["method"],
                        "file": call["file"],
                        "line": call["line"],
                        "message": f"Frontend calls {call['method']} {path} but endpoint doesn't exist in backend",
                    }
                )
        else:
            backend_methods = backend_routes[path]
            for call in calls:
                if call["method"] not in backend_methods:
                    issues.append(
                        {
                            "type": "METHOD_MISMATCH",
                            "severity": "ERROR",
                            "path": path,
                            "method": call["method"],
                            "file": call["file"],
                            "line": call["line"],
                            "message": f"Frontend calls {call['method']} {path} but backend only supports {backend_methods}",
                        }
                    )

    # Check for unused backend endpoints
    used_paths = set(frontend_by_path.keys())
    for path in backend_routes:
        if path.startswith("/api/") and path not in used_paths:
            issues.append(
                {
                    "type": "UNUSED_ENDPOINT",
                    "severity": "WARNING",
                    "path": path,
                    "method": ",".join(backend_routes[path]),
                    "message": f"Backend endpoint {path} is not called by frontend",
                }
            )

    return issues


def main():
    script_dir = Path(__file__).parent
    webserver_dir = script_dir.parent  # Go up to WebServer directory
    routes_file = webserver_dir / "routes.py"
    js_dir = webserver_dir / "static" / "js"

    print("=" * 60)
    print("API Consistency Checker")
    print("=" * 60)

    # Find backend routes
    print("\n[1] Scanning backend routes...")
    backend_routes = find_backend_routes(routes_file)
    print(f"    Found {len(backend_routes)} API endpoints")

    # Find frontend calls
    print("\n[2] Scanning frontend API calls...")
    frontend_calls = find_frontend_api_calls(js_dir)
    print(f"    Found {len(frontend_calls)} API calls")

    # Check consistency
    print("\n[3] Checking consistency...")
    issues = check_consistency(backend_routes, frontend_calls)

    # Report
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    errors = [i for i in issues if i["severity"] == "ERROR"]
    warnings = [i for i in issues if i["severity"] == "WARNING"]

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for issue in errors:
            print(f"\n  [{issue['type']}] {issue['path']}")
            print(f"    {issue['message']}")
            if "file" in issue:
                print(f"    Location: {issue['file']}:{issue['line']}")

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for issue in warnings:
            print(f"\n  [{issue['type']}] {issue['path']}")
            print(f"    {issue['message']}")

    if not errors and not warnings:
        print("\n✅ All API endpoints are consistent!")

    print("\n" + "=" * 60)
    print(f"Summary: {len(errors)} errors, {len(warnings)} warnings")
    print("=" * 60)

    # Print backend routes for reference
    print("\n[Reference] Backend API endpoints:")
    for path, methods in sorted(backend_routes.items()):
        if path.startswith("/api/"):
            print(f"  {','.join(methods):8} {path}")

    return len(errors)


if __name__ == "__main__":
    exit(main())

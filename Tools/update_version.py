#!/usr/bin/env python3
"""
FPBInject Version Update Script

Updates version number across all project files:
- Source/fpbinject_version.h (C/C++ header)
- Tools/WebServer/version.py (Python module)
- Tools/WebServer/static/js/core/version.js (Frontend JS)

Usage:
    python update_version.py 1.2.1
    python update_version.py 1.3.0
    python update_version.py --show  # Show current version
"""

import argparse
import os
import re
import sys

# Get project root (parent of Tools directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# File paths relative to project root
VERSION_H_PATH = os.path.join(PROJECT_ROOT, "Source", "fpbinject_version.h")
VERSION_PY_PATH = os.path.join(PROJECT_ROOT, "Tools", "WebServer", "version.py")
VERSION_JS_PATH = os.path.join(
    PROJECT_ROOT, "Tools", "WebServer", "static", "js", "core", "version.js"
)


def parse_version(version_str: str) -> tuple:
    """Parse version string like '1.2.1' into (major, minor, patch)"""
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", version_str)
    if not match:
        raise ValueError(f"Invalid version format: {version_str}. Expected: X.Y.Z")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def get_current_version() -> tuple:
    """Read current version from version.py"""
    if not os.path.exists(VERSION_PY_PATH):
        return None
    with open(VERSION_PY_PATH, "r") as f:
        content = f.read()
    major = re.search(r"VERSION_MAJOR\s*=\s*(\d+)", content)
    minor = re.search(r"VERSION_MINOR\s*=\s*(\d+)", content)
    patch = re.search(r"VERSION_PATCH\s*=\s*(\d+)", content)
    if major and minor and patch:
        return int(major.group(1)), int(minor.group(1)), int(patch.group(1))
    return None


def update_version_h(major: int, minor: int, patch: int) -> bool:
    """Update C header file"""
    content = f'''/**
 * @file fpbinject_version.h
 * @brief FPBInject version definition - single source of truth
 *
 * This file defines the version number for the entire FPBInject project.
 * All components should include this file and use FPBINJECT_VERSION_STRING.
 *
 * DO NOT EDIT MANUALLY - Use Tools/update_version.py to update version.
 */

#ifndef FPBINJECT_VERSION_H
#define FPBINJECT_VERSION_H

#define FPBINJECT_VERSION_MAJOR {major}
#define FPBINJECT_VERSION_MINOR {minor}
#define FPBINJECT_VERSION_PATCH {patch}

#define FPBINJECT_VERSION_STRING "v{major}.{minor}.{patch}"

#endif /* FPBINJECT_VERSION_H */
'''
    os.makedirs(os.path.dirname(VERSION_H_PATH), exist_ok=True)
    with open(VERSION_H_PATH, "w") as f:
        f.write(content)
    return True


def update_version_py(major: int, minor: int, patch: int) -> bool:
    """Update Python version file"""
    content = f'''"""
FPBInject WebServer version definition - single source of truth

DO NOT EDIT MANUALLY - Use Tools/update_version.py to update version.
"""

VERSION_MAJOR = {major}
VERSION_MINOR = {minor}
VERSION_PATCH = {patch}

VERSION_STRING = f"v{{VERSION_MAJOR}}.{{VERSION_MINOR}}.{{VERSION_PATCH}}"

__version__ = f"{{VERSION_MAJOR}}.{{VERSION_MINOR}}.{{VERSION_PATCH}}"
'''
    os.makedirs(os.path.dirname(VERSION_PY_PATH), exist_ok=True)
    with open(VERSION_PY_PATH, "w") as f:
        f.write(content)
    return True


def update_version_js(major: int, minor: int, patch: int) -> bool:
    """Update JavaScript version file"""
    content = f'''/**
 * FPBInject WebServer version definition
 * DO NOT EDIT MANUALLY - Use Tools/update_version.py to update version.
 */

const FPBINJECT_VERSION = {{
  major: {major},
  minor: {minor},
  patch: {patch},
  string: 'v{major}.{minor}.{patch}',
}};

window.FPBINJECT_VERSION = FPBINJECT_VERSION;
'''
    os.makedirs(os.path.dirname(VERSION_JS_PATH), exist_ok=True)
    with open(VERSION_JS_PATH, "w") as f:
        f.write(content)
    return True


def main():
    parser = argparse.ArgumentParser(description="Update FPBInject version")
    parser.add_argument("version", nargs="?", help="Version number (e.g., 1.2.1)")
    parser.add_argument("--show", action="store_true", help="Show current version")
    args = parser.parse_args()

    if args.show:
        current = get_current_version()
        if current:
            print(f"Current version: v{current[0]}.{current[1]}.{current[2]}")
        else:
            print("Version not found")
        return 0

    if not args.version:
        parser.print_help()
        return 1

    try:
        major, minor, patch = parse_version(args.version)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Updating version to v{major}.{minor}.{patch}...")

    # Update all files
    files_updated = []

    if update_version_h(major, minor, patch):
        files_updated.append(VERSION_H_PATH)
        print(f"  ✓ {os.path.relpath(VERSION_H_PATH, PROJECT_ROOT)}")

    if update_version_py(major, minor, patch):
        files_updated.append(VERSION_PY_PATH)
        print(f"  ✓ {os.path.relpath(VERSION_PY_PATH, PROJECT_ROOT)}")

    if update_version_js(major, minor, patch):
        files_updated.append(VERSION_JS_PATH)
        print(f"  ✓ {os.path.relpath(VERSION_JS_PATH, PROJECT_ROOT)}")

    print(f"\nUpdated {len(files_updated)} files to v{major}.{minor}.{patch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

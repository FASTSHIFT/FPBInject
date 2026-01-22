#!/usr/bin/env python3
"""
Kconfig syntax checker using kconfiglib (Python API)
Usage:
    python3 kconfig_lint.py <Kconfig file> [<Kconfig file> ...]
"""
import sys
import kconfiglib

if len(sys.argv) < 2:
    print("Usage: python3 kconfig_lint.py <Kconfig file> [<Kconfig file> ...]")
    sys.exit(1)

failed = False
for kconfig_file in sys.argv[1:]:
    print(f"Checking {kconfig_file} ...")
    try:
        # Parse Kconfig file (no actual config tree needed)
        kconf = kconfiglib.Kconfig(filename=kconfig_file)
        print("[OK] Syntax valid.")
    except Exception as e:
        print(f"[ERROR] {kconfig_file}: {e}")
        failed = True

if failed:
    sys.exit(1)
else:
    sys.exit(0)

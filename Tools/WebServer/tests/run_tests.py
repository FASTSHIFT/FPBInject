#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPBInject WebServer Test Runner

Supports coverage statistics and HTML report generation.

Usage:
    ./tests/run_tests.py              # Run all tests
    ./tests/run_tests.py -v           # Verbose output
    ./tests/run_tests.py --coverage   # Run tests and generate coverage report
    ./tests/run_tests.py --html       # Generate HTML coverage report
    ./tests/run_tests.py --target 80  # Set coverage target to 80%
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import unittest

# Add parent directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# Default coverage target
DEFAULT_COVERAGE_TARGET = 80

# Config file path
CONFIG_FILE = os.path.join(PARENT_DIR, "config.json")
CONFIG_BACKUP = os.path.join(PARENT_DIR, "config.json.bak")


def backup_config():
    """Backup original config file"""
    if os.path.exists(CONFIG_FILE):
        shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)
        return True
    return False


def restore_config():
    """Restore original config file"""
    if os.path.exists(CONFIG_BACKUP):
        shutil.copy2(CONFIG_BACKUP, CONFIG_FILE)
        os.remove(CONFIG_BACKUP)
        return True
    return False


def run_scan_chinese():
    """Run Chinese text scanner"""
    print("\n" + "=" * 70)
    print("Running Chinese Text Scanner")
    print("=" * 70)

    from scan_chinese import main as scan_main

    scan_main()
    return True  # Scanner always succeeds, just reports findings


def run_api_check():
    """Run API consistency check"""
    print("\n" + "=" * 70)
    print("Running API Consistency Check")
    print("=" * 70)

    from check_api import main as check_main

    error_count = check_main()
    return error_count == 0


def run_tests(
    verbosity=2,
    with_coverage=False,
    html_report=False,
    coverage_target=DEFAULT_COVERAGE_TARGET,
):
    """
    Run all tests.

    Args:
        verbosity: Output verbosity level (0-2)
        with_coverage: Whether to enable coverage statistics
        html_report: Whether to generate HTML report
        coverage_target: Coverage target percentage

    Returns:
        bool: Whether all tests passed
    """
    # Backup config file
    config_backed_up = backup_config()
    if config_backed_up:
        print("📦 Config file backed up")

    # Suppress noisy log output during tests
    logging.disable(logging.CRITICAL)

    try:
        if with_coverage:
            try:
                import coverage
            except ImportError:
                print("Error: Need to install coverage package")
                print("Please run: pip install coverage")
                sys.exit(1)

            # Create coverage object
            cov = coverage.Coverage(
                source=[PARENT_DIR],
                omit=[
                    "*/tests/*",
                    "*/__pycache__/*",
                    "*/static/*",
                    "*/templates/*",
                ],
            )
            cov.start()

        # Discover and load tests
        loader = unittest.TestLoader()
        suite = loader.discover(SCRIPT_DIR, pattern="test_*.py")

        # Run tests
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)

        if with_coverage:
            cov.stop()
            cov.save()

            print("\n" + "=" * 70)
            print("Coverage Report")
            print("=" * 70)

            # Call report() only once to get total coverage
            total = cov.report()

            if html_report:
                html_dir = os.path.join(SCRIPT_DIR, "htmlcov")
                cov.html_report(directory=html_dir)
                print(f"\nHTML report generated: {html_dir}/index.html")

            # Check if coverage meets target
            if total < coverage_target:
                print(
                    f"\n⚠️  Warning: Coverage {total:.1f}% below {coverage_target}% target"
                )
            else:
                print(f"\n✅ Coverage {total:.1f}% meets target (≥{coverage_target}%)")

        return result.wasSuccessful()
    finally:
        # Re-enable logging
        logging.disable(logging.NOTSET)

        # Restore config file
        if config_backed_up:
            restore_config()
            print("📦 Config file restored")


def main():
    parser = argparse.ArgumentParser(description="FPBInject WebServer Test Runner")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--coverage", action="store_true", help="Enable coverage statistics"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML coverage report (auto-enables --coverage)",
    )
    parser.add_argument(
        "--target",
        type=float,
        default=DEFAULT_COVERAGE_TARGET,
        help=f"Coverage target percentage (default: {DEFAULT_COVERAGE_TARGET}%%)",
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip API and Chinese text checks",
    )

    args = parser.parse_args()

    all_passed = True

    # Run additional checks first (unless skipped)
    if not args.skip_checks:
        # Run Chinese text scanner
        run_scan_chinese()

        # Run API consistency check
        if not run_api_check():
            print("\n❌ API consistency check failed!")
            all_passed = False

    verbosity = 2 if args.verbose else 1
    with_coverage = args.coverage or args.html

    # Run unit tests
    test_success = run_tests(
        verbosity=verbosity,
        with_coverage=with_coverage,
        html_report=args.html,
        coverage_target=args.target,
    )

    if not test_success:
        all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

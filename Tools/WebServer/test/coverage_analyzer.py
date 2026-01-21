#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coverage Analyzer Tool
Analyze code coverage details and list specific uncovered line numbers.
"""

import sys
import os
import unittest
import coverage

# Add parent directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)


def main():
    print("Running tests and analyzing coverage, please wait...")

    # Initialize coverage statistics
    cov = coverage.Coverage(
        source=[PARENT_DIR],
        omit=[
            "*/test/*",
            "*/__pycache__/*",
            "*/static/*",
            "*/templates/*",
            "*/venv/*",
            "*/env/*",
        ],
    )
    cov.start()

    # Run all tests
    loader = unittest.TestLoader()
    # Suppress standard output to get a clear report
    # stream = open(os.devnull, 'w')
    suite = loader.discover(SCRIPT_DIR, pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    cov.stop()
    cov.save()

    print("\n" + "=" * 80)
    print("Detailed coverage report (including uncovered line numbers)")
    print("=" * 80)

    # show_missing=True will display the line numbers corresponding to the Miss column in the report
    cov.report(show_missing=True)

    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()

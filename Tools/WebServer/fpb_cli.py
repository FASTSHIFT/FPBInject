#!/usr/bin/env python3
"""
FPB CLI entry point - forwards to fpbinject.cli.fpb_cli.

Supports both installed usage (``fpbinject`` console script) and running the
script directly from a source checkout without installing the package.
"""

import os
import sys


def _bootstrap_fpbinject_package():
    """Register this directory as the ``fpbinject`` package if not installed.

    Enables offline/no-install usage of ``./fpb_cli.py`` after the S0
    package-ization, where imports use the ``fpbinject.`` prefix but the
    physical directory is ``Tools/WebServer``.
    """
    try:
        import fpbinject  # noqa: F401

        return
    except ModuleNotFoundError:
        pass

    import types

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    pkg = types.ModuleType("fpbinject")
    pkg.__path__ = [pkg_dir]
    sys.modules["fpbinject"] = pkg
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)


_bootstrap_fpbinject_package()

from fpbinject.cli.fpb_cli import main  # noqa: E402

if __name__ == "__main__":
    main()

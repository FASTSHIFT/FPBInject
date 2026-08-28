#!/usr/bin/env python3
"""CLI error types.

Kept in a tiny standalone module so both ``fpb_cli`` and the extracted
connection-resolution helpers can import them without a circular dependency.
"""


class FPBCLIError(Exception):
    """CLI-specific error. ``exit_code`` defaults to 1.

    Raise the ``AmbiguousServerError`` subclass when more than one server
    matches a discovery handle so main() can exit ``2`` (the documented
    ladder code for "needs disambiguation").
    """

    exit_code = 1


class AmbiguousServerError(FPBCLIError):
    """Multi-match on discovery handle / mDNS browse; exits ``2``."""

    exit_code = 2

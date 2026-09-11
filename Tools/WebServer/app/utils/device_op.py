#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Shared fl-mode exit policy for route serial operations.

Every route that touches the serial port runs its work in the single owner
thread (the DeviceWorker). This module centralizes the one cross-cutting
concern that was previously hand-written (and forgotten) at each call site:
returning the device to the shell after an operation.

On NuttX a command implicitly enters ``fl`` interactive mode; leaving the
device stuck in ``fl>`` breaks the next tool (or a human on the console).
Because entering fl mode is idempotent, a whole multi-command operation
(e.g. a file download: fopen -> fread*N -> fcrc -> fclose) enters fl once and,
thanks to a single exit here, leaves once -- no per-chunk enter/exit churn.

Each route keeps its own ``run_in_device_worker`` dispatch (so worker mocking
stays per-module); it just wraps the work function with :func:`with_fl_exit`
so the exit is guaranteed and uniform.
"""

import logging

logger = logging.getLogger(__name__)


def with_fl_exit(func, keep_fl=False, fpb=None):
    """Wrap ``func`` so the device returns to the shell after it runs.

    The returned callable executes ``func`` and then, unless ``keep_fl`` is
    True, calls ``exit_fl_mode`` -- from the same (owner) thread that did the
    I/O. The exit is guarded so it never masks ``func``'s result or exception.

    ``fpb`` is the FPBInject instance to exit; when omitted it is resolved via
    ``get_fpb_inject()``. Passing it explicitly lets the caller (and tests)
    control which instance is used.
    """

    def wrapped():
        try:
            return func()
        finally:
            if not keep_fl:
                try:
                    target = fpb
                    if target is None:
                        from fpbinject.routes import get_fpb_inject

                        target = get_fpb_inject()
                    target.exit_fl_mode()
                except Exception as e:
                    logger.debug(f"exit_fl_mode after serial op failed: {e}")

    return wrapped

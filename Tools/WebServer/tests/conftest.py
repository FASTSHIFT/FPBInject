"""Pytest session setup for the FPBInject backend tests.

Safety guard: tests must never read or overwrite a developer's real
``config.json``. The production default ``CONFIG_FILE`` points at the
package directory's ``config.json``; a bare ``AppState()`` in a test would
otherwise load (and potentially save) that real file.

Here we repoint the default config location to a throwaway temp path for the
whole test session, so any ``AppState()`` that doesn't explicitly configure a
path stays isolated. Tests that need a specific path still call
``configure(...)`` / set ``config_path`` explicitly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _isolate_config(tmp_path_factory):
    """Repoint the default config path away from the real config.json."""
    import fpbinject.core.state as state_mod

    tmp_cfg = tmp_path_factory.mktemp("fpbcfg") / "config.json"
    original = state_mod.CONFIG_FILE
    state_mod.CONFIG_FILE = str(tmp_cfg)

    # Any global AppState created at import time still holds the old default;
    # repoint it too so its save_config() can't hit the real file.
    try:
        state_mod.state.config_path = str(tmp_cfg)
    except Exception:
        pass

    yield

    state_mod.CONFIG_FILE = original

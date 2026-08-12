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
    """Repoint config away from the real config.json for the whole session.

    Guards two leak paths:
      1. A bare AppState() reads/writes CONFIG_FILE -> repoint the constant.
      2. main.main() -> resolve_config_path() discovers the real
         <pkgdir>/config.json and reconfigures the global state onto it.
         Stub _discover_existing_config to None so the resolver never finds
         the developer's real file during tests.
    """
    import fpbinject.core.state as state_mod
    import fpbinject.main as main_mod

    tmp_dir = tmp_path_factory.mktemp("fpbcfg")
    tmp_cfg = tmp_dir / "config.json"
    original_cfg = state_mod.CONFIG_FILE
    state_mod.CONFIG_FILE = str(tmp_cfg)

    try:
        state_mod.state.config_path = str(tmp_cfg)
    except Exception:
        pass

    # Prevent resolve_config_path() (called by main.main() tests) from
    # discovering the developer's real config.json in CWD or the package
    # dir and reconfiguring the global state onto it. Stub discovery to
    # None; the original is preserved on the module so the discovery unit
    # tests can restore it.
    main_mod._discover_existing_config_orig = main_mod._discover_existing_config
    main_mod._discover_existing_config = lambda: None

    yield

    state_mod.CONFIG_FILE = original_cfg
    main_mod._discover_existing_config = main_mod._discover_existing_config_orig

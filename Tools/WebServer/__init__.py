"""FPBInject — runtime code injection for ARM Cortex-M via the FPB unit.

This package bundles the WebServer, CLI, and supporting modules. The physical
layout lives under ``Tools/WebServer/`` and is mapped to the import name
``fpbinject`` via setuptools ``package-dir`` (see pyproject.toml).
"""

from fpbinject.version import __version__

__all__ = ["__version__"]

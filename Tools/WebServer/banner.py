"""
Shared startup banner for FPBInject entry points.

Both the web server (fpbinject-server) and the CLI (fpbinject) print the
same figlet "slant" logo followed by a one-line description, the running
version tagged with the surface name, and a docs link.

The banner is purely cosmetic and must never contaminate machine-readable
output: the CLI only prints it on the no-command/help path, and ANSI color
is dropped automatically when the stream is not a TTY (pipes, CI, logs).
"""

import sys

from fpbinject.version import __version__

# figlet "ansi_shadow" font rendering of "FPBInject". Uses box-drawing and
# block glyphs, so the host terminal must support UTF-8 (all modern ones do).
_LOGO = r"""
███████╗██████╗ ██████╗ ██╗███╗   ██╗     ██╗███████╗ ██████╗████████╗
██╔════╝██╔══██╗██╔══██╗██║████╗  ██║     ██║██╔════╝██╔════╝╚══██╔══╝
█████╗  ██████╔╝██████╔╝██║██╔██╗ ██║     ██║█████╗  ██║        ██║
██╔══╝  ██╔═══╝ ██╔══██╗██║██║╚██╗██║██   ██║██╔══╝  ██║        ██║
██║     ██║     ██████╔╝██║██║ ╚████║╚█████╔╝███████╗╚██████╗   ██║
╚═╝     ╚═╝     ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚════╝ ╚══════╝ ╚═════╝   ╚═╝"""

_TAGLINE = "Runtime C code injection for ARM Cortex-M"
_DOCS_URL = "https://github.com/FASTSHIFT/FPBInject"


def render_banner(surface: str, *, color: bool = True) -> str:
    """Return the banner text for a given surface (e.g. "Web Server", "CLI").

    ``color`` toggles ANSI escapes; callers usually pass the result of
    ``stream.isatty()`` so redirected output stays clean.
    """
    cyan = "\033[36m" if color else ""
    dim = "\033[2m" if color else ""
    reset = "\033[0m" if color else ""

    return "\n".join(
        [
            f"{cyan}{_LOGO}{reset}",
            "",
            f"  {_TAGLINE}  {dim}·{reset}  {surface} {dim}v{__version__}{reset}",
            f"  {dim}{_DOCS_URL}{reset}",
            "",
        ]
    )


def print_banner(surface: str, *, stream=None) -> None:
    """Print the banner for ``surface`` to ``stream`` (default stdout)."""
    if stream is None:
        stream = sys.stdout
    color = hasattr(stream, "isatty") and stream.isatty()
    print(render_banner(surface, color=color), file=stream, flush=True)

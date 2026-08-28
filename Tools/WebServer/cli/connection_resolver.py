#!/usr/bin/env python3
"""Connection-plan resolution and mDNS discovery helpers for the CLI.

Extracted from ``fpb_cli`` to keep that module under the file-size limit.
These are pure module-level functions (no CLI object state): they turn
argparse ``args`` / handles / env vars into a :class:`ConnectionPlan`, and
implement the ``discover`` subcommand.

``fpb_cli`` re-exports every public name here, so
``from fpbinject.cli.fpb_cli import resolve_connection_plan`` (and friends)
keep working.
"""

import json
import os
import sys
from typing import Optional

from fpbinject.cli.errors import FPBCLIError, AmbiguousServerError
from fpbinject.cli.server_proxy import (
    DEFAULT_SERVER_URL,
    DEFAULT_PORT,
    list_cli_servers,
)
from fpbinject.cli.connection_plan import (
    CommandPolicy,
    ConnectionMode,
    ConnectionPlan,
)

try:  # Optional: discovery requires the zeroconf package.
    from fpbinject.cli.discover import (
        discover_sync,
        discover_sync_by_handle,
    )
except Exception:  # pragma: no cover
    discover_sync = None
    discover_sync_by_handle = None


def _is_local_url(url: str) -> bool:
    """True if ``url`` points at this host (loopback or local interface IP)."""
    from urllib.parse import urlparse

    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    if not host:
        return False
    if host in ("localhost",):
        return True
    try:
        from fpbinject.cli.discover import _is_loopback, _local_interface_ips

        if _is_loopback(host):
            return True
        return host in _local_interface_ips()
    except Exception:
        return host == "127.0.0.1"


def _localhost_status_ok(port: int = DEFAULT_PORT, timeout: float = 0.3) -> bool:
    """Quick TCP probe — does http://127.0.0.1:port answer /api/status?"""
    import urllib.request

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/status", timeout=timeout
        ) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _classify_url(url: str, *, token: Optional[str], source: str) -> ConnectionPlan:
    if _is_local_url(url):
        return ConnectionPlan(
            mode=ConnectionMode.LOCAL_PROXY,
            server_url=url,
            token=token,
            source=source,
        )
    return ConnectionPlan(
        mode=ConnectionMode.REMOTE_PROXY,
        server_url=url,
        token=token,
        source=source,
    )


def _attach_serial_port(
    plan: ConnectionPlan, port: Optional[str], baudrate: int
) -> ConnectionPlan:
    """Return a new plan with serial_port/baudrate filled and launch flags set
    according to whether the plan is local + has a serial port."""
    if not port:
        return plan
    is_local = plan.mode is ConnectionMode.LOCAL_PROXY
    return ConnectionPlan(
        mode=plan.mode,
        server_url=plan.server_url,
        token=plan.token,
        serial_port=port,
        baudrate=baudrate,
        allow_launch=is_local,
        allow_direct_fallback=is_local,
        source=plan.source,
        cache_handle=plan.cache_handle,
    )


def _with_cache_handle(
    plan: ConnectionPlan, cache_handle: Optional[str]
) -> ConnectionPlan:
    """Return a new plan tagged with the cache handle (so a connect failure
    can invalidate the right entry)."""
    if cache_handle is None:
        return plan
    return ConnectionPlan(
        mode=plan.mode,
        server_url=plan.server_url,
        token=plan.token,
        serial_port=plan.serial_port,
        baudrate=plan.baudrate,
        allow_launch=plan.allow_launch,
        allow_direct_fallback=plan.allow_direct_fallback,
        source=plan.source,
        cache_handle=cache_handle,
    )


def _resolve_handle_to_url(value: str, *, source: str) -> str:
    """Turn a user-supplied -s/FPB_SERVER value into a server URL.

    Three forms accepted:
      * URL (anything containing ``://``) -> used verbatim.
      * ``host:port`` handle -> cache lookup, falls back to mDNS browse.
      * ``host`` only        -> mDNS browse, must match exactly one server
                                 (multiple matches -> exit 2 with hints).

    Cache contract for ``host:port``:

      * Hit: return the cached URL immediately (no mDNS), AND spawn a
        daemon thread that re-runs the mDNS lookup to refresh the entry.
        The user does not block on the refresh.
      * Miss / expired / FPB_NO_CACHE=1: synchronous mDNS, then store.

    A cached URL that turns out to be unreachable triggers a connection
    error inside the connector; ``invalidate_cached_handle`` lets the
    caller wipe the bad entry and try again.

    The ``source`` string ("-s flag" / "FPB_SERVER env") is only used in
    error messages.
    """
    from fpbinject.cli.discover import classify_handle, find_by_handle
    from fpbinject.cli import handle_cache

    kind = classify_handle(value)
    if kind == "url":
        return value

    if discover_sync_by_handle is None:
        raise FPBCLIError(
            f"Cannot resolve {source} '{value}': zeroconf not installed. "
            "Pass a full URL instead."
        )

    if kind == "host_port":
        cached = handle_cache.lookup(value)
        if cached and cached.get("url"):
            handle_cache.spawn_refresh(lambda: _refresh_handle_cache(value))
            return cached["url"]

    servers = discover_sync_by_handle(value)
    matches = find_by_handle(servers, value)
    if not matches:
        prog = os.path.basename(sys.argv[0]) or "fpbinject"
        raise FPBCLIError(
            f"No FPBInject server matches {source} '{value}'. "
            f"Run '{prog} discover' to list visible servers."
        )
    if len(matches) > 1:
        msg = [f"{source} '{value}' is ambiguous; matches multiple servers:"]
        for s in matches:
            msg.append(f"  {s.handle}  {s.url}")
        msg.append("Be more specific (use 'host:port' form).")
        raise AmbiguousServerError("\n".join(msg))

    chosen = matches[0]
    if kind == "host_port":
        handle_cache.store(value, url=chosen.url, server_id=chosen.id)
    return chosen.url


def _refresh_handle_cache(value: str) -> None:
    """Background-thread entrypoint: re-run mDNS for ``value`` and update cache.

    Errors are swallowed because this is a best-effort refresh; the next
    foreground call will fall back to a synchronous lookup.
    """
    from fpbinject.cli.discover import find_by_handle
    from fpbinject.cli import handle_cache

    try:
        servers = discover_sync_by_handle(value, timeout=1.5)
        matches = find_by_handle(servers, value)
        if len(matches) == 1:
            chosen = matches[0]
            handle_cache.store(value, url=chosen.url, server_id=chosen.id)
        elif not matches:
            handle_cache.invalidate(value)
    except Exception:
        pass


def invalidate_cached_handle(value: str) -> None:
    """Public hook so the connector can drop a bad cache entry."""
    from fpbinject.cli import handle_cache

    handle_cache.invalidate(value)


def resolve_connection_plan(args) -> ConnectionPlan:
    """Single resolver: return the ConnectionPlan for ``args``.

    Precedence (first hit wins):
        1. command_policy in {OFFLINE, SERVER_ADMIN} -> OFFLINE plan
        2. --direct flag                              -> DIRECT plan
        3. -s / --server                              -> resolve handle, classify URL
        4. FPB_SERVER env                             -> resolve handle, classify URL
        5. --server-url (legacy)                      -> classify URL (deprecation warning)
        6. FPB_SERVER_URL env (legacy)                -> classify URL
        7. Single CLI-launched local PID              -> LOCAL_PROXY 127.0.0.1:<pid_port>
        8. http://127.0.0.1:5500 reachable            -> LOCAL_PROXY default
        9. --no-discovery                             -> LOCAL_PROXY default fallback
       10. mDNS browse:
             0 results  -> LOCAL_PROXY default
             1 result   -> classify (already normalized to 127.0.0.1 if same-host)
             2+ results -> stderr list + sys.exit(2)

    Local plans gain ``allow_launch`` and ``allow_direct_fallback`` only
    when ``--port`` is present (preserves the legacy "auto-launch failed
    -> direct serial" path while keeping it scoped).
    """
    policy = getattr(args, "command_policy", CommandPolicy.DEVICE)
    if policy in (CommandPolicy.OFFLINE, CommandPolicy.SERVER_ADMIN):
        return ConnectionPlan(mode=ConnectionMode.OFFLINE, source="offline-command")

    port = getattr(args, "port", None)
    baudrate = getattr(args, "baudrate", 115200)
    token = getattr(args, "token", None)
    verbose = getattr(args, "verbose", False)

    if getattr(args, "direct", False):
        if getattr(args, "server", None) or getattr(args, "server_url_legacy", None):
            raise FPBCLIError(
                "--direct cannot be combined with --server / --server-url; "
                "direct mode bypasses the WebServer."
            )
        if not port:
            raise FPBCLIError("--direct requires --port for device commands.")
        return ConnectionPlan(
            mode=ConnectionMode.DIRECT,
            serial_port=port,
            baudrate=baudrate,
            source="direct",
        )

    server_handle = getattr(args, "server", None)
    if server_handle:
        url = _resolve_handle_to_url(server_handle, source="-s flag")
        from fpbinject.cli.discover import classify_handle

        cache_key = (
            server_handle if classify_handle(server_handle) == "host_port" else None
        )
        plan = _classify_url(url, token=token, source="flag")
        plan = _attach_serial_port(plan, port, baudrate)
        return _with_cache_handle(plan, cache_key)

    env_handle = os.environ.get("FPB_SERVER")
    if env_handle:
        url = _resolve_handle_to_url(env_handle, source="FPB_SERVER env")
        from fpbinject.cli.discover import classify_handle

        cache_key = env_handle if classify_handle(env_handle) == "host_port" else None
        plan = _classify_url(url, token=token, source="env")
        plan = _attach_serial_port(plan, port, baudrate)
        return _with_cache_handle(plan, cache_key)

    legacy_url = getattr(args, "server_url_legacy", None)
    if legacy_url:
        if verbose:
            print(
                "warning: --server-url is deprecated; use -s / --server instead.",
                file=sys.stderr,
            )
        return _attach_serial_port(
            _classify_url(legacy_url, token=token, source="legacy-flag"), port, baudrate
        )

    legacy_env_url = os.environ.get("FPB_SERVER_URL")
    if legacy_env_url:
        if verbose:
            print(
                "warning: FPB_SERVER_URL is deprecated; use FPB_SERVER instead.",
                file=sys.stderr,
            )
        return _attach_serial_port(
            _classify_url(legacy_env_url, token=token, source="legacy-env"),
            port,
            baudrate,
        )

    pid_servers = list_cli_servers()
    if len(pid_servers) == 1:
        pid_port = pid_servers[0]["port"]
        url = f"http://127.0.0.1:{pid_port}"
        return _attach_serial_port(
            _classify_url(url, token=token, source="pid"), port, baudrate
        )

    if _localhost_status_ok(DEFAULT_PORT):
        return _attach_serial_port(
            _classify_url(DEFAULT_SERVER_URL, token=token, source="localhost-default"),
            port,
            baudrate,
        )

    if getattr(args, "no_discovery", False) or discover_sync is None:
        return _attach_serial_port(
            _classify_url(DEFAULT_SERVER_URL, token=token, source="localhost-fallback"),
            port,
            baudrate,
        )

    servers = discover_sync()
    if not servers:
        return _attach_serial_port(
            _classify_url(DEFAULT_SERVER_URL, token=token, source="localhost-fallback"),
            port,
            baudrate,
        )
    if len(servers) == 1:
        s = servers[0]
        if verbose:
            print(
                f"Using discovered server {s.url} (version={s.version})",
                file=sys.stderr,
            )
        return _attach_serial_port(
            _classify_url(s.url, token=token, source="mdns"), port, baudrate
        )

    lines = [
        "Multiple FPBInject servers discovered; pass -s <handle> to choose:",
    ]
    for s in servers:
        lines.append(
            f"  -s {s.handle}    version={s.version}  auth={s.auth}  device={s.device}"
        )
    raise AmbiguousServerError("\n".join(lines))


def resolve_server_url(args):
    """Resolve the WebServer URL the CLI should talk to.

    Precedence ladder (first hit wins):
        1. ``args.server_url`` (--server-url flag)
        2. ``FPB_SERVER_URL`` env var
        3. Non-server-needing subcommand
           (``command_policy in {OFFLINE, SERVER_ADMIN}``) -> None
        4. ``--no-discovery`` flag -> DEFAULT_SERVER_URL fallback
        5. mDNS browse: 0 -> fallback, 1 -> use, 2+ -> exit 2

    Exit codes:
        0 ok, 2 ambiguous (multi-result without --server-url).
    """
    if getattr(args, "server_url", None):
        return args.server_url
    env_url = os.environ.get("FPB_SERVER_URL")
    if env_url:
        return env_url
    policy = getattr(args, "command_policy", CommandPolicy.DEVICE)
    if policy in (CommandPolicy.OFFLINE, CommandPolicy.SERVER_ADMIN):
        return None
    if getattr(args, "no_discovery", False):
        return DEFAULT_SERVER_URL
    if discover_sync is None:
        return DEFAULT_SERVER_URL
    servers = discover_sync()
    if not servers:
        return DEFAULT_SERVER_URL
    if len(servers) == 1:
        s = servers[0]
        if getattr(args, "verbose", False):
            print(
                f"Using discovered server {s.url} (version={s.version})",
                file=sys.stderr,
            )
        return s.url
    print(
        "Multiple FPBInject servers discovered; pass -s <handle> to choose:",
        file=sys.stderr,
    )
    for s in servers:
        print(
            f"  -s {s.handle}    version={s.version}  auth={s.auth}  device={s.device}",
            file=sys.stderr,
        )
    sys.exit(2)


def cmd_discover(args):
    """``discover`` subcommand: human table by default, JSON with ``--json``."""
    if discover_sync is None:
        if getattr(args, "json", False):
            print("[]")
        else:
            print("(zeroconf not installed; cannot discover)", file=sys.stderr)
        return 1

    timeout = getattr(args, "timeout", 3.0)
    servers = discover_sync(timeout=timeout)

    if getattr(args, "json", False):
        payload = [
            {
                "name": s.name,
                "host": s.host,
                "port": s.port,
                "url": s.url,
                "version": s.version,
                "auth": s.auth,
                "device": s.device,
                "path": s.path,
                "id": s.id,
                "handle": s.handle,
            }
            for s in servers
        ]
        print(json.dumps(payload, indent=2))
        return 0

    if not servers:
        print("No FPBInject servers found.", file=sys.stderr)
        return 0

    rows = [("HANDLE", "URL", "AUTH", "DEVICE", "VERSION")]
    for s in servers:
        rows.append((s.handle, s.url, s.auth or "?", s.device or "?", s.version or "?"))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)))
    return 0

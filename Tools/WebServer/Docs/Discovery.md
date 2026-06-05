# FPBInject mDNS Discovery Protocol

This document specifies the mDNS / DNS-SD service that FPBInject WebServer instances publish on the local network and that `fpb_cli.py` consumes for auto-discovery.

## Goals

- Let CLI clients find a running WebServer on the LAN without prior knowledge of host or port.
- Advertise enough metadata for the client to pick the right server when more than one is reachable.
- Stay out of the authentication path: discovery is **endpoint discovery, not authentication**. Tokens are exchanged out-of-band.

## Service registration

| Field | Value |
|---|---|
| Service type | `_fpbinject._tcp.local.` |
| Instance name | `FPBInject on <hostname>` (RFC 6763 §4.1.1 user-visible name) |
| Port | The TCP port the WebServer is listening on (default `5500`, follows `--port`). |
| Address | All interfaces zeroconf binds to (IPv4 only by default). |
| Server hostname | `<hostname>.local.` |

`_fpbinject` is 9 characters, fits the RFC 6335 §5.1 ≤15-char limit, and is not registered on IANA — no collision with shipped service types.

## TXT records (v1)

Keys are case-insensitive. Values are printable UTF-8.

| Key | Value | Meaning |
|---|---|---|
| `txtvers` | `1` | Schema version of this TXT record (RFC 6763 §6.7). Bump only on incompatible changes. |
| `version` | e.g. `1.6.6` | WebServer application version. Clients MAY warn on major mismatch. |
| `auth` | `token` \| `none` | Advertised auth intent. `token` means a token is required for non-localhost access; `none` means the server was started with `--no-auth`. |
| `device` | `none` (v1) | Whether the server has a serial device attached. **v1 limitation: this value is set once at startup as `none` and is not updated at runtime.** Real-time updates may be added in a later schema version (will bump `txtvers`). |
| `path` | `/api` | API base path. Reserved for future protocol revs. |
| `id` | `fpb:<uuid>` | Stable per-installation UUID; persisted on the server in `Tools/WebServer/.fpbinject_server_id`. Survives port and hostname changes; deleting the file mints a new identity. Reserved for future client-side identity matching. |

### Security: token must not appear in TXT

The auth token MUST NOT be published in TXT records. mDNS announcements are broadcast in cleartext on UDP/5353 and cached for tens of minutes by other hosts on the network. Publishing the token (or a recoverable hash of it) defeats its purpose.

The CLI obtains the token from the server's startup banner (`🔑 Token: …`), the `FPB_TOKEN` env var, or the `--token` flag — never from mDNS.

## Lifecycle

| Event | Server behavior |
|---|---|
| Server start (no `--no-mdns`) | Construct `Zeroconf()`, register `ServiceInfo` for `_fpbinject._tcp.local.` with the TXT keys above. |
| Server graceful exit (atexit, SIGINT, SIGTERM) | `unregister_service()` sends a "goodbye" packet, then `close()`. |
| Server `kill -9` or hard crash | No goodbye packet. The stale entry is evicted by the mDNS TTL (default ~75 minutes per RFC 6762 §10). |
| `--no-mdns` flag | Server skips registration entirely. |

## Client discovery

`Tools/WebServer/cli/discover.py::discover_sync(timeout: float = 3.0)` returns `list[FPBServer]`.

Each `FPBServer` is a dataclass:

```
FPBServer(
    name:    str,    # full mDNS instance name
    host:    str,    # IPv4 or hostname (loopback when same-host)
    port:    int,
    version: str,    # from TXT
    auth:    str,    # "token" | "none"
    device:  str,    # "none" (v1)
    path:    str,    # "/api"
    url:     str,    # convenience: f"http://{host}:{port}"
    id:      str,    # from TXT (empty for legacy servers)
    handle:  str,    # "<host>:<port>" — the human-friendly id `-s` accepts
)
```

### CLI precedence ladder

`fpb_cli.py::resolve_connection_plan(args)` runs through this list and stops at the first match. Each step produces a final `ConnectionPlan` (mode + URL + token + serial port + flags); the connector consumes the plan once.

1. **Subcommand is offline or admin-only** (`analyze`, `disasm`, `decompile`, `signature`, `search`, `get-symbols`, `compile`, `discover`, `server-stop`, `disconnect`) — return Offline plan, skip everything below. Zero discovery delay.
2. **`--direct`** — return Direct plan. Requires `--port`. Rejected with `-s` / `--server-url`.
3. **`-s / --server <handle>`** — handle resolution:
   - URL (contains `://`) → used verbatim.
   - `host:port` → mDNS browse, exact `handle` match.
   - `host` → mDNS browse, must match exactly one server (else exit `2` with hints).
4. **`FPB_SERVER`** env var — same handle resolution as `-s`.
5. *(deprecated)* **`--server-url <URL>`** — URL only. Warns under `-v` and is removed in a future release.
6. *(deprecated)* **`FPB_SERVER_URL`** env — URL only.
7. **Single CLI-launched server** (PID file in `Tools/WebServer/.cli_server_*.pid`) — Local Proxy on `127.0.0.1:<pid_port>`. No mDNS.
8. **`http://127.0.0.1:5500/api/status` reachable** — Local Proxy on the default port. No mDNS.
9. **`--no-discovery`** — Local Proxy on `http://127.0.0.1:5500` (fallback only, no LAN browse).
10. **mDNS browse** for 3.0 s on `_fpbinject._tcp.local.`:
    - 0 results → Local Proxy on `http://127.0.0.1:5500` (fallback).
    - 1 result → classify the address. Same-host hits (loopback or local interface IP) are normalized to `127.0.0.1:<port>` so the user is never asked for a token to talk to a server they themselves started.
    - ≥ 2 results → list candidates on stderr, `sys.exit(2)`.

### Localhost preference

Within step 10, when a single mDNS service announces multiple addresses (very common on multi-homed hosts), the resolver sorts them with this key:

| Class | Key |
|-------|-----|
| Loopback (`127.0.0.0/8`) | `(0, addr)` |
| Local interface IP (matches `socket.getaddrinfo(gethostname())`) | `(1, addr)` |
| Anything else | `(2, addr)` |

Lowest tuple wins. If the winner is loopback or a local-interface IP, the host field of the resulting `FPBServer` is rewritten to `127.0.0.1` and the URL becomes `http://127.0.0.1:<port>`. This eliminates the LAN-IP-from-localhost trap that previously caused spurious 403s.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `1` | Runtime failure (connect/auth/IO/invalid flag combination). |
| `2` | Multiple servers discovered without `--server-url`; user must disambiguate. |

## v1 limitations

- `device` TXT is published once at startup as `none`. Real-time `connected`/`none` transitions are deferred to a later TXT schema version.
- `auth` TXT carries advertised intent (server's `--no-auth` flag), not effective state. A misconfigured server with `auth=token` but no token configured is the server operator's problem, not the client's.
- Ungraceful exits (`kill -9`, crash) leave a stale advertisement until mDNS TTL eviction. SIGINT and SIGTERM are handled and trigger an immediate goodbye packet.

## References

- RFC 6762 — Multicast DNS
- RFC 6763 — DNS-Based Service Discovery (§4.1.1 instance names, §6.7 `txtvers`)
- RFC 6335 §5.1 — service-name format
- python-zeroconf (https://github.com/python-zeroconf/python-zeroconf)

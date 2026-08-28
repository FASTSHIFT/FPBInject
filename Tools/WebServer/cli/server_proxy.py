#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
WebServer proxy for CLI coexistence.

When the WebServer is running, CLI device operations are forwarded
via HTTP API instead of opening a second serial connection.

If the WebServer is not running, the proxy can auto-launch it as a
background subprocess so the CLI always operates in proxy mode.
"""

import glob
import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class ProxyAuthError(Exception):
    """Raised when the WebServer rejects a request due to authentication.

    Distinguishes "reachable but unauthenticated/forbidden" (HTTP 401/403)
    from "server unreachable" (connection errors), so the CLI can give the
    user actionable guidance about supplying a token.
    """

    pass


# Default WebServer URL
DEFAULT_SERVER_URL = "http://127.0.0.1:5500"
DEFAULT_PORT = 5500

# Timeout for probe / API calls (seconds)
_PROBE_TIMEOUT = 2
_API_TIMEOUT = 30

# Auto-launch settings
_LAUNCH_TIMEOUT = 10  # Max seconds to wait for server startup
_LAUNCH_POLL_INTERVAL = 0.3  # Poll interval during startup wait

# PID file directory: WebServer root (next to main.py)
_WEBSERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pid_file_path(port: int = DEFAULT_PORT) -> str:
    """Return PID file path for a given port."""
    return os.path.join(_WEBSERVER_DIR, f".cli_server_{port}.pid")


def _remove_pid_file(port: int = DEFAULT_PORT):
    """Remove the CLI server PID file for a given port."""
    try:
        os.remove(_pid_file_path(port))
    except OSError:
        pass


def get_cli_server_pid(port: int = DEFAULT_PORT) -> Optional[int]:
    """Read the PID of a CLI-launched server on *port*, if alive.

    Returns the PID (int) if the PID file exists and the process is
    still running, otherwise None.  Stale PID files are cleaned up.
    """
    try:
        with open(_pid_file_path(port), "r") as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return None

    # Check if process is still alive
    try:
        os.kill(pid, 0)  # signal 0 = existence check
        return pid
    except OSError:
        # Process gone — stale PID file
        _remove_pid_file(port)
        return None


def list_cli_servers() -> List[Dict[str, Any]]:
    """List all CLI-launched servers (by scanning PID files).

    Returns a list of dicts with ``port`` and ``pid`` keys.
    """
    results = []
    for path in glob.glob(os.path.join(_WEBSERVER_DIR, ".cli_server_*.pid")):
        basename = os.path.basename(path)
        try:
            port = int(basename.replace(".cli_server_", "").replace(".pid", ""))
        except ValueError:
            continue
        pid = get_cli_server_pid(port)
        if pid is not None:
            results.append({"port": port, "pid": pid})
    return results


def stop_cli_server(port: int = DEFAULT_PORT) -> dict:
    """Stop a CLI-launched WebServer on *port* if one is running.

    Returns a JSON-style dict with success/message.
    """
    pid = get_cli_server_pid(port)
    if pid is None:
        return {
            "success": False,
            "error": f"No CLI-launched server is running on port {port}",
        }

    try:
        os.kill(pid, signal.SIGTERM)
        # Poll for exit, checking before each sleep so a fast-exiting
        # process is detected immediately. Same ~5s total budget as before
        # but with a finer interval, so the common case returns in ms.
        deadline = time.monotonic() + 5.0
        while True:
            try:
                os.kill(pid, 0)
            except OSError:
                break  # Process exited
            if time.monotonic() >= deadline:
                break
            time.sleep(0.02)
        _remove_pid_file(port)
        return {
            "success": True,
            "message": f"Server on port {port} (PID {pid}) terminated",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to stop server (PID {pid}): {e}",
        }


def _consume_sse_stream(resp, progress_cb=None, done_field="uploaded"):
    """Consume a server-sent-events stream and return the ``result`` event.

    Streams are always tiny newline-delimited ``data: {json}`` frames. We
    forward every ``progress`` event to ``progress_cb(done, total)`` so the
    CLI can render a live progress line, then return the final ``result``
    event (or ``None`` if the stream ended without one).

    ``done_field`` picks between ``uploaded`` (upload) and ``downloaded``
    (download) since the server uses different keys per direction.
    """
    last_result = None
    last_done = 0
    last_total = 0
    for raw in resp:
        try:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
        except Exception:
            continue
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except Exception:
            continue
        et = event.get("type")
        if et == "progress" and progress_cb is not None:
            done = event.get(done_field, 0)
            total = event.get("total", 0)
            last_done, last_total = done, total
            try:
                progress_cb(done, total)
            except Exception:
                # Never let a UI error abort the transfer.
                pass
        elif et == "result":
            last_result = event
            # Emit a final 100% tick ONLY if the last progress event did
            # not already reach it. The server usually emits a 100% tick
            # before result, so this is only a safety net for streams
            # that skip straight to result.
            if progress_cb is not None and event.get("success"):
                size = event.get("size") or event.get("total") or 0
                already_final = (
                    last_total and last_done >= last_total and last_total == size
                )
                if size and not already_final:
                    try:
                        progress_cb(size, size)
                    except Exception:
                        pass
    return last_result


class ServerProxy:
    """Proxy device operations through the running WebServer HTTP API."""

    def __init__(
        self,
        base_url: str = DEFAULT_SERVER_URL,
        token: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._server_process = None  # Tracks auto-launched subprocess

    # ------------------------------------------------------------------
    # Low-level HTTP helpers (stdlib only, no requests dependency)
    # ------------------------------------------------------------------

    def _build_url(self, path: str) -> str:
        url = f"{self.base_url}{path}"
        if self.token:
            sep = "&" if "?" in url else "?"
            url += f"{sep}token={self.token}"
        return url

    def _get(self, path: str, timeout: float = _API_TIMEOUT) -> dict:
        url = self._build_url(path)
        req = Request(url, method="GET")
        req.add_header("Accept", "application/json")
        if self.token:
            req.add_header("X-Auth-Token", self.token)
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            self._raise_for_auth(e)
            raise

    def _post(
        self, path: str, data: Optional[dict] = None, timeout: float = _API_TIMEOUT
    ) -> dict:
        url = self._build_url(path)
        body = json.dumps(data or {}).encode()
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if self.token:
            req.add_header("X-Auth-Token", self.token)
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            self._raise_for_auth(e)
            raise

    @staticmethod
    def _raise_for_auth(err: HTTPError) -> None:
        """Translate HTTP 401/403 into a clear ProxyAuthError.

        Other HTTP errors are left for the caller to handle.
        """
        if err.code in (401, 403):
            raise ProxyAuthError(
                "WebServer rejected the request (HTTP "
                f"{err.code}). A valid auth token is required for remote "
                "(non-localhost) access. Pass --token or set FPB_TOKEN."
            )

    # ------------------------------------------------------------------
    # Server detection & auto-launch
    # ------------------------------------------------------------------

    def is_server_running(self) -> bool:
        """Check if the WebServer is reachable."""
        try:
            resp = self._get("/api/status", timeout=_PROBE_TIMEOUT)
            return resp.get("success", False)
        except Exception:
            return False

    def is_device_connected(self) -> bool:
        """Check if the WebServer has an active device connection."""
        try:
            resp = self._get("/api/status", timeout=_PROBE_TIMEOUT)
            return resp.get("connected", False)
        except Exception:
            return False

    def get_status(self) -> dict:
        """Get full WebServer status."""
        return self._get("/api/status")

    def probe_status(self) -> dict:
        """One-shot status probe with the short PROBE timeout.

        Returns the raw /api/status response (with at least 'success' and
        'connected' keys), or an empty dict on any error. Use this when a
        caller needs both reachability and connection state in one call;
        avoids issuing two probes that may also disagree under races.
        """
        try:
            return self._get("/api/status", timeout=_PROBE_TIMEOUT)
        except Exception:
            return {}

    def ensure_server(self) -> bool:
        """Ensure the WebServer is running, auto-launching if needed.

        Returns True if server is reachable after this call.
        """
        if self.is_server_running():
            return True

        return self.launch_server()

    def launch_server(self) -> bool:
        """Launch WebServer as a background subprocess.

        Starts main.py with --no-browser flag and waits until the server
        responds to /api/status.  Writes a PID file so main.py and
        ``server-stop`` can identify CLI-launched instances.

        Auth is kept enabled — localhost requests are exempt by default.

        Returns True if server started successfully.
        """
        # Determine main.py path relative to this file
        webserver_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_py = os.path.join(webserver_dir, "main.py")

        if not os.path.exists(main_py):
            logger.error(f"WebServer main.py not found: {main_py}")
            return False

        # Parse port from base_url
        try:
            from urllib.parse import urlparse

            parsed = urlparse(self.base_url)
            port = parsed.port or 5500
        except Exception:
            port = 5500

        cmd = [
            sys.executable,
            main_py,
            "--no-browser",
            "--http-port",
            str(port),
        ]

        logger.info(f"Auto-launching WebServer: {' '.join(cmd)}")

        try:
            self._server_process = subprocess.Popen(
                cmd,
                cwd=webserver_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.error(f"Failed to launch WebServer: {e}")
            return False

        # Write PID file so others can identify this CLI-launched server
        try:
            with open(_pid_file_path(port), "w") as f:
                f.write(str(self._server_process.pid))
        except Exception as e:
            logger.warning(f"Failed to write PID file: {e}")

        # Wait for server to become reachable
        deadline = time.time() + _LAUNCH_TIMEOUT
        while time.time() < deadline:
            # Check if process died
            if self._server_process.poll() is not None:
                logger.error(
                    f"WebServer process exited with code {self._server_process.returncode}"
                )
                self._server_process = None
                _remove_pid_file(port)
                return False

            if self.is_server_running():
                logger.info("WebServer is ready")
                return True

            time.sleep(_LAUNCH_POLL_INTERVAL)

        logger.error(f"WebServer did not start within {_LAUNCH_TIMEOUT}s")
        # Kill the hung process
        try:
            self._server_process.terminate()
        except Exception:
            pass
        self._server_process = None
        _remove_pid_file(port)
        return False

    # ------------------------------------------------------------------
    # Connection management (proxied to WebServer)
    # ------------------------------------------------------------------

    def connect(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: int = 2,
    ) -> dict:
        """Connect to device via WebServer."""
        return self._post(
            "/api/connect",
            {"port": port, "baudrate": baudrate, "timeout": timeout},
        )

    def disconnect(self) -> dict:
        """Disconnect device via WebServer."""
        return self._post("/api/disconnect")

    # ------------------------------------------------------------------
    # Serial terminal (proxied to WebServer logs routes)
    # ------------------------------------------------------------------

    def serial_send(self, data: str) -> dict:
        """Send raw data to device serial port via WebServer.

        Uses the /api/serial/send endpoint (same as the web terminal).
        """
        return self._post("/api/serial/send", {"data": data})

    def serial_read(self, raw_since: int = 0) -> dict:
        """Read raw serial output via WebServer (legacy full-window read).

        Uses the /api/logs endpoint to fetch raw_serial_log entries.
        Returns dict with 'raw_data' and 'raw_next' for incremental reads.

        Prefer :meth:`serial_read_window` for context-safe bounded reads.
        """
        return self._get(f"/api/logs?raw_since={raw_since}&tool_since=999999999")

    def serial_read_window(
        self,
        since: int = 0,
        max_bytes: int = 4096,
        tail: int = 0,
        drop: bool = False,
        grep: Optional[str] = None,
    ) -> dict:
        """Context-safe windowed serial read via /api/serial/read.

        ``grep`` is an optional server-side regex (``re.search``) applied
        BEFORE the tail/paging window, so only matching entries consume
        the byte budget. Returns dict with data / next / pending_bytes /
        pending_entries / buffer_overflowed. Never returns more than
        ``max_bytes`` of data.
        """
        from urllib.parse import quote

        q = f"/api/serial/read?since={since}&max_bytes={max_bytes}"
        if tail and tail > 0:
            q += f"&tail={tail}"
        if drop:
            q += "&drop=1"
        if grep:
            q += f"&grep={quote(grep, safe='')}"
        return self._get(q)

    # ------------------------------------------------------------------
    # Virtual serial passthrough (proxied to WebServer connection routes)
    # ------------------------------------------------------------------

    def vserial_status(self) -> dict:
        """Get virtual serial passthrough status via WebServer."""
        return self._get("/api/vserial/status")

    def vserial_start(self, symlink: Optional[str] = None) -> dict:
        """Start virtual serial passthrough on the server.

        The PTY is created in the WebServer process (a long-lived host),
        so the device node persists for external tools to open.
        """
        payload: Dict[str, Any] = {}
        if symlink is not None:
            payload["symlink"] = symlink
        return self._post("/api/vserial/start", payload)

    def vserial_stop(self) -> dict:
        """Stop virtual serial passthrough on the server."""
        return self._post("/api/vserial/stop")

    # ------------------------------------------------------------------
    # Device operations (proxied to WebServer)
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """Get device FPB info via WebServer."""
        return self._get("/api/fpb/info")

    def inject(
        self,
        target_func: str,
        source_file: str,
        elf_path: Optional[str] = None,
        compile_commands: Optional[str] = None,
        patch_mode: str = "trampoline",
        comp: int = -1,
    ) -> dict:
        """Inject a patch via WebServer."""
        source_content = ""
        source_ext = ".c"
        if os.path.exists(source_file):
            with open(source_file, "r", encoding="utf-8") as f:
                source_content = f.read()
            source_ext = os.path.splitext(source_file)[1]

        payload: Dict[str, Any] = {
            "target_func": target_func,
            "source_content": source_content,
            "patch_mode": patch_mode,
            "comp": comp,
            "source_ext": source_ext,
            "original_source_file": os.path.abspath(source_file),
        }
        if elf_path:
            payload["elf_path"] = elf_path
        if compile_commands:
            payload["compile_commands_path"] = compile_commands

        return self._post("/api/fpb/inject", payload)

    def unpatch(self, comp: int = 0, all_patches: bool = False) -> dict:
        """Remove a patch via WebServer."""
        return self._post("/api/fpb/unpatch", {"comp": comp, "all": all_patches})

    def mem_read(self, addr: int, length: int, fmt: str = "hex") -> dict:
        """Read device memory via WebServer."""
        return self._post(
            "/api/fpb/mem-read",
            {"addr": addr, "length": length, "fmt": fmt},
        )

    def mem_write(self, addr: int, data_hex: str) -> dict:
        """Write device memory via WebServer."""
        return self._post(
            "/api/fpb/mem-write",
            {"addr": addr, "data": data_hex},
        )

    def test_serial(
        self,
        start_size: int = 16,
        max_size: int = 4096,
        timeout: float = 2.0,
        trials: int = 8,
        min_success_rate: float = 1.0,
    ) -> dict:
        """Test serial throughput via WebServer."""
        return self._post(
            "/api/fpb/test-serial",
            {
                "start_size": start_size,
                "max_size": max_size,
                "timeout": timeout,
                "trials": trials,
                "min_success_rate": min_success_rate,
            },
        )

    def file_list(self, path: str = "/") -> dict:
        """List directory contents via WebServer."""
        return self._get(f"/api/transfer/list?path={path}")

    def file_stat(self, path: str) -> dict:
        """Get file stat via WebServer."""
        return self._get(f"/api/transfer/stat?path={path}")

    def transfer_cancel(self) -> dict:
        """Ask the server to cancel the in-flight file transfer.

        Used when the CLI is interrupted (Ctrl-C) so the server-side transfer
        stops and releases the file transaction lock, instead of running to
        completion while the client is gone.
        """
        return self._post("/api/transfer/cancel", {}, timeout=_PROBE_TIMEOUT)

    def file_download(
        self,
        remote_path: str,
        timeout: float = 600.0,
        progress_cb=None,
    ) -> dict:
        """Download file via WebServer streaming SSE endpoint.

        The server pushes ``progress`` events (downloaded/total/speed/eta) and
        a final ``result`` event carrying base64 ``data``. Passing
        ``progress_cb(done, total)`` renders a live CLI progress line, just
        like the direct-mode transfer. ``timeout`` defaults high because
        serial transfers can be slow — actual throughput depends on the
        baudrate and link quality; callers may raise it further for very
        large files.
        """
        url = self._build_url("/api/transfer/download")
        payload = json.dumps({"remote_path": remote_path}).encode()
        req = Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("X-Auth-Token", self.token)

        try:
            resp = urlopen(req, timeout=timeout)
        except HTTPError as e:
            self._raise_for_auth(e)
            raise

        last_result = _consume_sse_stream(
            resp,
            progress_cb=progress_cb,
            done_field="downloaded",
        )
        if last_result:
            return last_result
        return {"success": False, "error": "Download stream ended with no result"}

    def file_upload(
        self,
        local_path: str,
        remote_path: str,
        progress_cb=None,
    ) -> dict:
        """Upload file to device via WebServer (multipart form, SSE stream).

        If ``progress_cb`` is given, it is called as ``progress_cb(done, total)``
        for every ``progress`` event the server pushes. This lets the CLI
        render a live progress line just like the direct-mode transfer.
        """
        import uuid

        url = self._build_url("/api/transfer/upload")
        boundary = uuid.uuid4().hex
        filename = os.path.basename(local_path)

        with open(local_path, "rb") as f:
            file_data = f.read()

        # Build multipart/form-data body
        lines = []
        # remote_path field
        lines.append(f"--{boundary}".encode())
        lines.append(b'Content-Disposition: form-data; name="remote_path"')
        lines.append(b"")
        lines.append(remote_path.encode())
        # file field
        lines.append(f"--{boundary}".encode())
        lines.append(
            f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode()
        )
        lines.append(b"Content-Type: application/octet-stream")
        lines.append(b"")
        lines.append(file_data)
        lines.append(f"--{boundary}--".encode())
        body = b"\r\n".join(lines)

        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        if self.token:
            req.add_header("X-Auth-Token", self.token)

        # Serial uploads are slow (throughput depends on baudrate + link);
        # use a generous timeout so large files don't spuriously fail while
        # the server is still transferring. The 20000 B/s divisor is a
        # conservative lower bound only used to grow the timeout budget with
        # payload size — it is NOT a claimed throughput.
        upload_timeout = max(600.0, len(file_data) / 20000.0 + 60.0)
        try:
            resp = urlopen(req, timeout=upload_timeout)
        except HTTPError as e:
            self._raise_for_auth(e)
            raise

        # Stream the SSE response line-by-line so `progress` events surface
        # in real time instead of after the whole upload completes.
        last_result = _consume_sse_stream(
            resp,
            progress_cb=progress_cb,
            done_field="uploaded",
        )
        if last_result:
            return last_result
        return {"success": True, "message": "Upload request sent"}

    def file_remove(self, path: str) -> dict:
        """Delete file on device via WebServer."""
        return self._post("/api/transfer/delete", {"path": path})

    def file_mkdir(self, path: str) -> dict:
        """Create directory on device via WebServer."""
        return self._post("/api/transfer/mkdir", {"path": path})

    def file_rename(self, old_path: str, new_path: str) -> dict:
        """Rename file/directory on device via WebServer."""
        return self._post(
            "/api/transfer/rename",
            {"old_path": old_path, "new_path": new_path},
        )

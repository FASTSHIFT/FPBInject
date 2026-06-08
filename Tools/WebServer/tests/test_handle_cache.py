#!/usr/bin/env python3
"""Tests for cli/handle_cache.py.

Pins: TTL boundary, atomic write, FPB_NO_CACHE bypass, daemon thread,
and the wire-up that makes -s host:port hit the cache before mDNS.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli import handle_cache  # noqa: E402


class TempCache:
    """Context-manager wrapping XDG_CACHE_HOME so each test has its own."""

    def __enter__(self):
        self._tmp = tempfile.mkdtemp(prefix="fpb-test-cache-")
        self._old_xdg = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = self._tmp
        os.environ.pop("FPB_NO_CACHE", None)
        return Path(self._tmp)

    def __exit__(self, *exc):
        if self._old_xdg is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self._old_xdg
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestStoreAndLookup(unittest.TestCase):
    def test_store_then_lookup_returns_url(self):
        with TempCache():
            handle_cache.store("bench:5500", url="http://1.2.3.4:5500", server_id="fpb:abc")
            entry = handle_cache.lookup("bench:5500")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["url"], "http://1.2.3.4:5500")
        self.assertEqual(entry["id"], "fpb:abc")

    def test_lookup_unknown_handle(self):
        with TempCache():
            self.assertIsNone(handle_cache.lookup("nope:9999"))

    def test_lookup_stale_entry_returns_none(self):
        with TempCache():
            handle_cache.store("old:5500", url="http://x:5500")
            entries = handle_cache._read_all()
            entries["old:5500"]["cached_at"] = time.time() - 25 * 3600
            handle_cache._write_all(entries)
            self.assertIsNone(handle_cache.lookup("old:5500", ttl_s=24 * 3600))

    def test_invalidate_drops_entry(self):
        with TempCache():
            handle_cache.store("bench:5500", url="http://x:5500")
            handle_cache.invalidate("bench:5500")
            self.assertIsNone(handle_cache.lookup("bench:5500"))


class TestNoCacheEnv(unittest.TestCase):
    def test_disabled_lookup_returns_none(self):
        with TempCache(), patch.dict(os.environ, {"FPB_NO_CACHE": "1"}):
            handle_cache.store("bench:5500", url="http://1.2.3.4:5500")
            self.assertIsNone(handle_cache.lookup("bench:5500"))

    def test_disabled_store_writes_nothing(self):
        with TempCache() as cache_dir, patch.dict(os.environ, {"FPB_NO_CACHE": "1"}):
            handle_cache.store("bench:5500", url="http://1.2.3.4:5500")
            self.assertFalse((cache_dir / "fpbinject" / "handles.json").exists())


class TestAtomicWrite(unittest.TestCase):
    def test_no_partial_file_on_replace(self):
        with TempCache() as cache_dir:
            handle_cache.store("a:1", url="http://a:1")
            handle_cache.store("b:2", url="http://b:2")
            cache_file = cache_dir / "fpbinject" / "handles.json"
            with cache_file.open() as f:
                blob = json.load(f)
            self.assertEqual(blob["version"], 1)
            self.assertEqual(blob["entries"]["a:1"]["url"], "http://a:1")
            self.assertEqual(blob["entries"]["b:2"]["url"], "http://b:2")

    def test_corrupt_file_treated_as_empty(self):
        with TempCache() as cache_dir:
            (cache_dir / "fpbinject").mkdir()
            (cache_dir / "fpbinject" / "handles.json").write_text("{not json")
            self.assertIsNone(handle_cache.lookup("any:1"))
            handle_cache.store("a:1", url="http://a:1")
            self.assertEqual(handle_cache.lookup("a:1")["url"], "http://a:1")


class TestSpawnRefreshIsDaemon(unittest.TestCase):
    def test_thread_is_daemon(self):
        called = []
        t = handle_cache.spawn_refresh(lambda: called.append(1))
        t.join(timeout=1.0)
        self.assertTrue(t.daemon)
        self.assertEqual(called, [1])


class TestResolverCacheIntegration(unittest.TestCase):
    """End-to-end: -s host:port hits cache, refreshes async."""

    def test_cache_hit_skips_mdns_and_spawns_refresh(self):
        with TempCache():
            handle_cache.store(
                "bench:5500", url="http://127.0.0.1:5500", server_id="fpb:abc"
            )

            from cli.fpb_cli import _resolve_handle_to_url

            with patch("cli.fpb_cli.discover_sync_by_handle") as mock_disc, patch(
                "cli.handle_cache.spawn_refresh"
            ) as mock_spawn:
                url = _resolve_handle_to_url("bench:5500", source="-s flag")

            self.assertEqual(url, "http://127.0.0.1:5500")
            mock_disc.assert_not_called()
            mock_spawn.assert_called_once()

    def test_cache_miss_falls_back_to_mdns_and_stores(self):
        with TempCache():
            from cli.discover import FPBServer
            from cli.fpb_cli import _resolve_handle_to_url

            fake_server = FPBServer(
                name="FPBInject on bench:5501._fpbinject._tcp.local.",
                host="127.0.0.1",
                port=5501,
                version="1.6.6",
                auth="none",
                device="none",
                path="/api",
                url="http://127.0.0.1:5501",
                id="fpb:zzz",
                handle="bench:5501",
            )
            with patch(
                "cli.fpb_cli.discover_sync_by_handle", return_value=[fake_server]
            ):
                url = _resolve_handle_to_url("bench:5501", source="-s flag")

            self.assertEqual(url, "http://127.0.0.1:5501")
            entry = handle_cache.lookup("bench:5501")
            self.assertIsNotNone(entry)
            self.assertEqual(entry["url"], "http://127.0.0.1:5501")
            self.assertEqual(entry["id"], "fpb:zzz")


if __name__ == "__main__":
    unittest.main()

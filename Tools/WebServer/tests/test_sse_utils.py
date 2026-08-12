#!/usr/bin/env python3
"""Tests for app/utils/sse.py"""

import json
import os
import queue
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpbinject.app.utils.sse import sse_generator, sse_response  # noqa: E402


class TestSSEGenerator(unittest.TestCase):
    """Tests for sse_generator()."""

    def test_single_dict_event(self):
        """Dict items are serialised as 'data: {...}\\n\\n'."""
        q = queue.Queue()
        q.put({"type": "progress", "pct": 50})
        q.put(None)

        chunks = list(sse_generator(q, poll_interval=0.1))
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].startswith("data: "))
        payload = json.loads(chunks[0].removeprefix("data: ").strip())
        self.assertEqual(payload["type"], "progress")
        self.assertEqual(payload["pct"], 50)

    def test_multiple_events(self):
        """Multiple dict items yield multiple SSE lines."""
        q = queue.Queue()
        q.put({"type": "status", "stage": "compiling"})
        q.put({"type": "progress", "pct": 100})
        q.put({"type": "result", "success": True})
        q.put(None)

        chunks = list(sse_generator(q, poll_interval=0.1))
        self.assertEqual(len(chunks), 3)
        types = [json.loads(c.removeprefix("data: ").strip())["type"] for c in chunks]
        self.assertEqual(types, ["status", "progress", "result"])

    def test_none_sentinel_terminates(self):
        """None sentinel stops the generator."""
        q = queue.Queue()
        q.put(None)

        chunks = list(sse_generator(q, poll_interval=0.1))
        self.assertEqual(len(chunks), 0)

    def test_heartbeat_on_poll_timeout(self):
        """Heartbeat is sent when queue.get times out."""
        q = queue.Queue()

        def feed():
            time.sleep(0.3)
            q.put({"type": "result", "success": True})
            q.put(None)

        t = threading.Thread(target=feed, daemon=True)
        t.start()

        chunks = list(sse_generator(q, poll_interval=0.1, inactivity_timeout=5.0))
        t.join(timeout=2)

        heartbeats = [
            c
            for c in chunks
            if json.loads(c.removeprefix("data: ").strip())["type"] == "heartbeat"
        ]
        self.assertGreater(len(heartbeats), 0)

    def test_inactivity_timeout(self):
        """Stream ends with error after inactivity_timeout."""
        q = queue.Queue()
        # Never feed anything — should timeout

        chunks = list(sse_generator(q, poll_interval=0.1, inactivity_timeout=0.3))
        self.assertGreater(len(chunks), 0)
        last = json.loads(chunks[-1].removeprefix("data: ").strip())
        self.assertEqual(last["type"], "result")
        self.assertFalse(last["success"])
        self.assertIn("Timeout", last["error"])


class TestSSEResponse(unittest.TestCase):
    """Tests for sse_response()."""

    def test_returns_flask_response(self):
        """sse_response returns a Flask Response with correct mimetype."""
        from flask import Flask

        app = Flask(__name__)
        q = queue.Queue()
        q.put(None)

        with app.app_context():
            resp = sse_response(q)
            self.assertEqual(resp.mimetype, "text/event-stream")
            self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")
            self.assertEqual(resp.headers.get("X-Accel-Buffering"), "no")

    def test_response_streams_data(self):
        """sse_response streams queue data correctly."""
        from flask import Flask

        app = Flask(__name__)
        q = queue.Queue()
        q.put({"type": "result", "success": True})
        q.put(None)

        with app.app_context():
            resp = sse_response(q)
            body = "".join(resp.response)
            self.assertIn('"success": true', body)


if __name__ == "__main__":
    unittest.main()

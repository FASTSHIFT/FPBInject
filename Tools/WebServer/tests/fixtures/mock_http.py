"""Reusable mock HTTP handler for tests.

Extracted from tests/test_server_proxy.py so other tests (e.g. mDNS discovery)
can spin up a fake WebServer without duplicating the handler.
"""

import http.server
import json


class MockHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Simple mock HTTP handler for testing.

    Class-level ``responses`` dict maps path -> JSON body for GET/POST.
    Class-level ``sse_responses`` dict maps path -> list of event dicts for
    Server-Sent Events POST endpoints.
    """

    responses: dict = {}
    sse_responses: dict = {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in self.responses:
            body = json.dumps(self.responses[path]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            self.rfile.read(content_length)
        path = self.path.split("?")[0]
        if path in self.sse_responses:
            sse_data = self.sse_responses[path]
            body = ""
            for event in sse_data:
                body += f"data: {json.dumps(event)}\n\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(body.encode())
        elif path in self.responses:
            resp_body = json.dumps(self.responses[path]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp_body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

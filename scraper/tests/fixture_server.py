"""Local test website (tests/fixtures/site) with redirects, 404s and a dynamic sitemap.

    python tests/fixture_server.py [port]
"""

from __future__ import annotations

import contextlib
import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).parent / "fixtures" / "site"
REDIRECTS = {"/alt-seite": "/kontakt/"}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass

    def do_HEAD(self):
        if self._special():
            return
        super().do_HEAD()

    def do_GET(self):
        if self._special(body=True):
            return
        super().do_GET()

    def _special(self, body: bool = False) -> bool:
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path in REDIRECTS:
            self.send_response(301)
            self.send_header("Location", REDIRECTS[path])
            self.end_headers()
            return True
        if path == "/sitemap.xml":
            port = self.server.server_address[1]
            data = (SITE / "sitemap.xml").read_text(encoding="utf-8").replace("PORT", str(port)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if body:
                self.wfile.write(data)
            return True
        target = SITE / path.lstrip("/")
        if path.endswith("/") and not (target / "index.html").exists() and path != "/":
            self.send_error(404)
            return True
        return False

    def list_directory(self, path):
        self.send_error(404)
        return None


@contextlib.contextmanager
def serve(port: int = 0):
    handler = functools.partial(Handler, directory=str(SITE))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://localhost:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    with serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765) as url:
        print(f"Fixture site: {url}", flush=True)
        threading.Event().wait()

"""The service on Python's HTTP server: for local development (`npm run dev:api`
or `python -m editpdf.server`), the tests, and a container when it runs as a
Cloud Builder container service instead of a Function.

    EDITPDF_HOST         interface to listen on (127.0.0.1; 0.0.0.0 in a container)
    EDITPDF_PORT         port (8787)
    EDITPDF_STATIC_DIR   the built web interface (frontend/dist)

plus the settings of editpdf.config.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from editpdf.app import App
from editpdf.config import config_from_env
from editpdf.http import Headers, Request, Response

_METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "editpdf"
        sys_version = ""

        def _serve(self) -> None:
            url = urlsplit(self.path)
            request = Request(self.command, url.path or "/", url.query, Headers(self.headers.items()))
            length = self.headers.get("content-length")
            if length is not None:
                if not length.isdigit():
                    self.send_error(400, "Bad Content-Length")
                    return
                if int(length) > app.config.limits.max_upload_bytes:
                    # Refused unread: a body too large never reaches memory.
                    request.declared_length = int(length)
                    self.close_connection = True
                else:
                    request.body = self.rfile.read(int(length))
            elif self.headers.get("transfer-encoding"):
                self.send_error(411, "Length Required")
                return
            self._write(app.handle(request))

        def _write(self, response: Response) -> None:
            self.send_response(response.status)
            for name, value in response.headers.items():
                if name != "content-length":
                    self.send_header(name, value)
            if response.status not in (204, 304):
                length = response.headers.get("content-length") if self.command == "HEAD" else str(len(response.body))
                self.send_header("content-length", length or "0")
            self.end_headers()
            if self.command != "HEAD" and response.body:
                self.wfile.write(response.body)

        def log_message(self, format: str, *args: object) -> None:
            pass  # the App logs every request itself

    for method in _METHODS:
        setattr(Handler, f"do_{method}", Handler._serve)
    return Handler


def create_server(app: App, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.daemon_threads = True
    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    host = os.environ.get("EDITPDF_HOST", "127.0.0.1")
    port = int(os.environ.get("EDITPDF_PORT", "8787"))
    static_dir = os.environ.get("EDITPDF_STATIC_DIR")
    config = config_from_env(os.environ)
    app = App(config, static_dir=Path(static_dir) if static_dir else None)
    server = create_server(app, host, port)
    # shutdown() waits for serve_forever() to return, and serve_forever() runs
    # on this thread, where the signal arrives: it has to be asked from another.
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    print(
        json.dumps(
            {
                "level": "info",
                "message": "listening",
                "url": f"http://{host}:{server.server_address[1]}",
                "limits": config.limits.as_json(),
                "ui": str(app.static.root) if app.static.available() else None,
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

"""The web interface (the built frontend), served from a directory next to the code."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import posixpath
import threading
from pathlib import Path
from urllib.parse import unquote

from editpdf.http import Headers, Request, Response

# The page's policy: everything from this origin, nothing inline but styles
# (React writes style attributes), workers and images from blob: and data: URLs
# because the page renders previews of the documents with pdf.js, and
# WebAssembly because pdf.js decodes some image formats (scans) with it.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'wasm-unsafe-eval'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "worker-src 'self' blob:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)

PAGE_HEADERS = {
    "content-security-policy": CONTENT_SECURITY_POLICY,
    "cross-origin-opener-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
}

_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".wasm": "application/wasm",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}


class StaticFiles:
    """Files of one directory, read once and kept: the interface is small."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._cache: dict[Path, tuple[bytes, str]] = {}
        self._lock = threading.Lock()

    def available(self) -> bool:
        return (self.root / "index.html").is_file()

    def _read(self, path: Path) -> tuple[bytes, str]:
        with self._lock:
            cached = self._cache.get(path)
            if cached is None:
                body = path.read_bytes()
                digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode()[:22]
                cached = (body, f'"{digest}"')
                self._cache[path] = cached
            return cached

    def _locate(self, url_path: str) -> Path | None:
        try:
            decoded = unquote(url_path, errors="strict")
        except UnicodeDecodeError:
            return None
        if "\x00" in decoded or ".." in decoded.split("/"):
            return None
        relative = posixpath.normpath(decoded).lstrip("/")
        if relative in ("", "."):
            relative = "index.html"
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            return None
        if candidate.is_file():
            return candidate
        # An address with no file extension is a page of the single-page
        # interface: it gets index.html, and the interface's router decides.
        if "." not in relative.rsplit("/", 1)[-1]:
            index = self.root / "index.html"
            return index if index.is_file() else None
        return None

    def response(self, request: Request) -> Response | None:
        """The interface's file for a GET or HEAD, or None when there is none."""
        path = self._locate(request.path)
        if path is None:
            return None
        body, etag = self._read(path)
        content_type = (
            _TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )
        immutable = path.parent.name == "assets" and path.parent.parent == self.root
        headers = Headers(
            {
                "content-type": content_type,
                "etag": etag,
                "cache-control": "public, max-age=31536000, immutable" if immutable else "no-cache",
                "x-content-type-options": "nosniff",
            }
        )
        if content_type.startswith("text/html"):
            for name, value in PAGE_HEADERS.items():
                headers.set(name, value)
        tags = [tag.strip().removeprefix("W/") for tag in (request.headers.get("if-none-match") or "").split(",")]
        if etag in tags:
            return Response(304, headers)
        headers.set("content-length", str(len(body)))
        return Response(200, headers, b"" if request.method == "HEAD" else body)

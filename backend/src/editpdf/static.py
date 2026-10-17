"""The web interface (the built frontend), served from a directory next to the code."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import posixpath
import threading
from importlib.resources.abc import Traversable
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
    """Files of one directory, read once and kept: the interface is small.

    The root is a Traversable: a directory on disk, or a package's resources
    (importlib.resources), which also works when a function's runtime imports
    the package straight from its zip.
    """

    def __init__(self, root: Traversable) -> None:
        self.root = root
        self._cache: dict[str, tuple[bytes, str]] = {}
        self._lock = threading.Lock()

    def available(self) -> bool:
        return self.root.joinpath("index.html").is_file()

    def _read(self, relative: str, node: Traversable) -> tuple[bytes, str]:
        with self._lock:
            cached = self._cache.get(relative)
            if cached is None:
                body = node.read_bytes()
                digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode()[:22]
                cached = (body, f'"{digest}"')
                self._cache[relative] = cached
            return cached

    def _node(self, relative: str) -> Traversable | None:
        node = self.root
        for part in relative.split("/"):
            node = node.joinpath(part)
        return node if node.is_file() else None

    def _locate(self, url_path: str) -> tuple[str, Traversable] | None:
        try:
            decoded = unquote(url_path, errors="strict")
        except UnicodeDecodeError:
            return None
        # Never out of the root: no climbing, no hidden files, no empty or odd segments.
        if "\x00" in decoded or "\\" in decoded or any(part.startswith(".") for part in decoded.split("/")):
            return None
        relative = posixpath.normpath(decoded).lstrip("/")
        if relative in ("", "."):
            relative = "index.html"
        node = self._node(relative)
        if node is not None:
            return relative, node
        # An address with no file extension is a page of the single-page
        # interface: it gets index.html, and the interface's router decides.
        if "." not in relative.rsplit("/", 1)[-1]:
            index = self._node("index.html")
            return ("index.html", index) if index is not None else None
        return None

    def response(self, request: Request) -> Response | None:
        """The interface's file for a GET or HEAD, or None when there is none."""
        located = self._locate(request.path)
        if located is None:
            return None
        relative, node = located
        body, etag = self._read(relative, node)
        name = relative.rsplit("/", 1)[-1]
        suffix = name[name.rfind(".") :].lower() if "." in name else ""
        content_type = _TYPES.get(suffix) or mimetypes.guess_type(name)[0] or "application/octet-stream"
        immutable = relative.startswith("assets/")
        headers = Headers(
            {
                "content-type": content_type,
                "etag": etag,
                "cache-control": "public, max-age=31536000, immutable" if immutable else "no-cache",
                "x-content-type-options": "nosniff",
            }
        )
        if content_type.startswith("text/html"):
            for header, value in PAGE_HEADERS.items():
                headers.set(header, value)
        tags = [tag.strip().removeprefix("W/") for tag in (request.headers.get("if-none-match") or "").split(",")]
        if etag in tags:
            return Response(304, headers)
        headers.set("content-length", str(len(body)))
        return Response(200, headers, b"" if request.method == "HEAD" else body)

"""Documents and requests for the tests."""

from __future__ import annotations

import io
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

from editpdf.app import App
from editpdf.config import config_from_env
from editpdf.http import Headers, Request, Response


def make_pdf(pages: int, *, title: str | None = None, width_base: int = 100) -> bytes:
    """A document of `pages` pages; page n is (width_base + n) points wide, so
    its width tells where it came from after a merge or a split."""
    writer = PdfWriter()
    for number in range(1, pages + 1):
        writer.add_blank_page(width=width_base + number, height=200)
    if title is not None:
        writer.add_metadata({"/Title": title})
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt(user_password="secret", algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def page_widths(data: bytes) -> list[int]:
    return [round(float(page.mediabox.width)) for page in PdfReader(io.BytesIO(data)).pages]


def page_rotations(data: bytes) -> list[int]:
    return [page.rotation for page in PdfReader(io.BytesIO(data)).pages]


Field = str | tuple[str, bytes] | tuple[str, bytes, str]


def multipart(fields: Sequence[tuple[str, Field]]) -> tuple[bytes, str]:
    """A multipart/form-data body: text fields as str, files as (name, bytes[, type])."""
    boundary = f"----editpdf{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode())
        if isinstance(value, str):
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            chunks.append(value.encode())
        else:
            filename, data, *rest = value
            content_type = rest[0] if rest else "application/pdf"
            chunks.append(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n".encode()
            )
            chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class TestApp:
    """An App with its log captured."""

    __test__ = False

    def __init__(self, env: Mapping[str, str] | None = None, **kwargs: Any) -> None:
        self.logs: list[dict[str, Any]] = []
        # No interface unless a test gives one: the tests do not depend on a frontend build.
        kwargs.setdefault("static_dir", Path(__file__).parent / "no-interface")
        self.app = App(config_from_env(env or {}), log=self.logs.append, **kwargs)

    def post(
        self, path: str, fields: Sequence[tuple[str, Field]], headers: Mapping[str, str] | None = None
    ) -> Response:
        body, content_type = multipart(fields)
        return self.request("POST", path, body, {"content-type": content_type, **(headers or {})})

    def get(self, path: str, headers: Mapping[str, str] | None = None) -> Response:
        return self.request("GET", path, b"", headers)

    def request(self, method: str, path: str, body: bytes = b"", headers: Mapping[str, str] | None = None) -> Response:
        path, _, query = path.partition("?")
        return self.app.handle(Request(method, path, query, Headers(headers or {}), body))

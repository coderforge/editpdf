"""multipart/form-data (RFC 7578), parsed from a body already in memory - a
function receives its request whole. Standard library only, so the function's
package carries nothing but pypdf."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from urllib.parse import unquote

from editpdf.pdf import InputDocument
from editpdf.problems import ApiError

#: More parts than any request of this API needs (a merge of max_files files).
MAX_PARTS = 1000
_PARAM = re.compile(r';\s*([A-Za-z0-9_.*-]+)\s*=\s*("(?:[^"\\]|\\.)*"|[^;]*)')


@dataclass(frozen=True)
class Part:
    name: str
    #: The file name; None for a text field.
    filename: str | None
    content_type: str | None
    data: bytes


def _invalid(detail: str = "The multipart/form-data body does not parse.") -> ApiError:
    return ApiError("invalid_request", detail)


def _parameters(header_value: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for key, raw in _PARAM.findall(header_value):
        value = raw.strip()
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = re.sub(r"\\(.)", r"\1", value[1:-1])
        params[key.lower()] = value
    # RFC 5987 extended values win over plain ones.
    for key in [k for k in params if k.endswith("*")]:
        charset, _, rest = params.pop(key).partition("'")
        _, _, encoded = rest.partition("'")
        # An undecodable extended value is dropped; the plain one, if any, stays.
        with contextlib.suppress(LookupError, UnicodeDecodeError):
            params[key[:-1]] = unquote(encoded, encoding=charset or "utf-8", errors="strict")
    return params


def boundary_of(content_type: str) -> str | None:
    """The boundary of a multipart/form-data content type, or None if it is not one."""
    media_type, _, _ = content_type.partition(";")
    if media_type.strip().lower() != "multipart/form-data":
        return None
    boundary = _parameters(content_type).get("boundary", "")
    return boundary if 0 < len(boundary) <= 200 else None


def parse_multipart(body: bytes, boundary: str) -> list[Part]:
    delimiter = b"--" + boundary.encode("latin-1")
    if body.startswith(delimiter):
        position = len(delimiter)
    else:
        start = body.find(b"\r\n" + delimiter)
        if start < 0:
            raise _invalid()
        position = start + 2 + len(delimiter)

    parts: list[Part] = []
    while True:
        if body[position : position + 2] == b"--":
            return parts
        line_end = body.find(b"\r\n", position)
        # Only transport padding may follow a delimiter on its line.
        if line_end < 0 or body[position:line_end].strip(b" \t"):
            raise _invalid()
        position = line_end + 2
        end = body.find(b"\r\n" + delimiter, position)
        if end < 0:
            raise _invalid()
        parts.append(_part(body[position:end]))
        if len(parts) > MAX_PARTS:
            raise _invalid(f"The request has more than {MAX_PARTS} parts.")
        position = end + 2 + len(delimiter)


def _part(raw: bytes) -> Part:
    if raw.startswith(b"\r\n"):
        head, data = b"", raw[2:]
    else:
        head, separator, data = raw.partition(b"\r\n\r\n")
        if not separator:
            raise _invalid()
    headers: dict[str, str] = {}
    for line in head.decode("utf-8", "replace").split("\r\n"):
        name, colon, value = line.partition(":")
        if not colon:
            raise _invalid()
        headers[name.strip().lower()] = value.strip()
    disposition = headers.get("content-disposition", "")
    if not disposition.lower().startswith("form-data"):
        raise _invalid()
    params = _parameters(disposition)
    if "name" not in params:
        raise _invalid()
    return Part(
        name=params["name"],
        filename=params.get("filename"),
        content_type=headers.get("content-type"),
        data=data,
    )


def display_name(name: str | None) -> str:
    """A name fit to quote back in a message: no control characters, not too long."""
    clean = re.sub(r"[\x00-\x1f\x7f]", "", name or "").strip()
    if clean == "":
        return "document.pdf"
    return clean if len(clean) <= 80 else clean[:77] + "..."


class Form:
    """The fields of a multipart/form-data request, with typed access."""

    def __init__(self, parts: list[Part]) -> None:
        self._parts = parts

    @classmethod
    def parse(cls, content_type: str, body: bytes) -> Form:
        boundary = boundary_of(content_type)
        if boundary is None:
            raise ApiError("unsupported_media_type", "Send the documents as multipart/form-data.")
        return cls(parse_multipart(body, boundary))

    def _all(self, name: str) -> list[Part]:
        return [part for part in self._parts if part.name == name]

    def count(self, name: str) -> int:
        """How many parts carry the field."""
        return len(self._all(name))

    def files(self, name: str) -> list[InputDocument]:
        """Every file sent under `name`, in the order sent."""
        documents = []
        for part in self._all(name):
            if part.filename is None:
                raise ApiError("invalid_request", f"{name} must be a file, not text.", field=name)
            documents.append(InputDocument(display_name(part.filename), part.data))
        return documents

    def file(self, name: str) -> InputDocument:
        """The one file sent under `name`."""
        documents = self.files(name)
        if not documents:
            raise ApiError("invalid_request", f"{name} is required: send the PDF document in it.", field=name)
        if len(documents) > 1:
            raise ApiError("invalid_request", f"{name} takes one document; send one part only.", field=name)
        return documents[0]

    def text(self, name: str) -> str | None:
        """The text sent under `name`, trimmed; None when absent or empty."""
        values = self._all(name)
        if len(values) > 1:
            raise ApiError("invalid_request", f"{name} was sent more than once.", field=name)
        if not values:
            return None
        part = values[0]
        if part.filename is not None:
            raise ApiError("invalid_request", f"{name} must be text, not a file.", field=name)
        try:
            text = part.data.decode("utf-8").strip()
        except UnicodeDecodeError as error:
            raise ApiError("invalid_request", f"{name} is not valid UTF-8 text.", field=name) from error
        return text or None

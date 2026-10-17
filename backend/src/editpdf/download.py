"""Names of the files we hand back, and the header that carries them."""

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import quote

MAX_NAME_LENGTH = 200


def _sanitize(name: str) -> str:
    """A file name without directories, control characters or characters shells and browsers trip on."""
    last = re.split(r"[/\\]", name)[-1]
    last = re.sub(r'[\x00-\x1f\x7f"*:<>?|]', "", last)
    last = re.sub(r"\s+", " ", last)
    return re.sub(r"^[\s.]+|[\s.]+$", "", last)


def base_name(name: str, fallback: str = "document") -> str:
    """The name of an input without its extension, to build output names on."""
    clean = re.sub(r"\.pdf$", "", _sanitize(name), flags=re.IGNORECASE)
    return clean[: MAX_NAME_LENGTH - 30] if clean else fallback


def output_name(requested: str | None, fallback: str, extension: Literal[".pdf", ".zip"]) -> str:
    """The name to save an output under: the one the client asked for when it
    is usable, else `fallback`; with `extension`, added when missing."""
    name = _sanitize(requested) if requested else ""
    if not name:
        name = fallback
    if not name.lower().endswith(extension):
        name = name[: MAX_NAME_LENGTH - len(extension)] + extension
    if len(name) > MAX_NAME_LENGTH:
        name = name[: MAX_NAME_LENGTH - len(extension)] + extension
    return name


def content_disposition(name: str) -> str:
    """`attachment` with the name twice: plain ASCII for old clients, UTF-8 (RFC 6266, 5987) for the rest."""
    ascii_name = re.sub(r'[^\x20-\x7e]|["\\]', "_", name)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"

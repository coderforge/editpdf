"""A request and a response, independent of what carries them (a Function
event, the local HTTP server)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl


class Headers:
    """Case-insensitive headers. Repeated headers are joined with commas, as HTTP allows."""

    def __init__(self, items: Mapping[str, str] | Iterable[tuple[str, str]] = ()) -> None:
        self._items: dict[str, str] = {}
        pairs = items.items() if isinstance(items, Mapping) else items
        for name, value in pairs:
            self.add(name, value)

    def add(self, name: str, value: str) -> None:
        key = name.lower()
        self._items[key] = f"{self._items[key]}, {value}" if key in self._items else value

    def set(self, name: str, value: str) -> None:
        self._items[name.lower()] = value

    def setdefault(self, name: str, value: str) -> None:
        self._items.setdefault(name.lower(), value)

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._items.get(name.lower(), default)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name.lower() in self._items

    def items(self) -> list[tuple[str, str]]:
        return list(self._items.items())

    def as_dict(self) -> dict[str, str]:
        return dict(self._items)


@dataclass
class Request:
    method: str
    #: The path, percent-encoded as it arrived.
    path: str
    query: str = ""
    headers: Headers = field(default_factory=Headers)
    body: bytes = b""
    #: The Content-Length of a body that was refused unread for its size.
    declared_length: int | None = None

    def query_params(self) -> list[tuple[str, str]]:
        return parse_qsl(self.query, keep_blank_values=True)


@dataclass
class Response:
    status: int = 200
    headers: Headers = field(default_factory=Headers)
    body: bytes = b""

    @classmethod
    def json(cls, data: Any, status: int = 200, content_type: str = "application/json") -> Response:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return cls(status, Headers({"content-type": content_type}), body)

    @classmethod
    def text(cls, text: str, content_type: str, status: int = 200) -> Response:
        return cls(status, Headers({"content-type": content_type}), text.encode("utf-8"))

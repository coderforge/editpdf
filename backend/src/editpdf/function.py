"""The entry point of the Cloud Builder Function: `handler(event, context)`.

The service itself is `App.handle` (Request in, Response out); this module is
the one place that knows how the platform hands a request to a function and
takes the answer back. It accepts the HTTP event shapes in common use:

- payload format 2.0 (`rawPath`, `rawQueryString`, `requestContext.http.method`);
- payload format 1.0 (`httpMethod`, `path`, `queryStringParameters`,
  `multiValueHeaders`);
- a plain one: `{"method", "path" | "url", "query", "headers", "body"}`;

as a dict or as its JSON text. Bodies come as text, as base64
(`isBase64Encoded`) or as bytes. The answer goes back as
`{"statusCode", "headers", "body", "isBase64Encoded"}`: binary bodies (PDF,
ZIP) in base64, text as it is.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode, urlsplit

from editpdf.app import App
from editpdf.config import config_from_env
from editpdf.http import Headers, Request, Response

_app: App | None = None


def _get_app(context: Any = None) -> App:
    """One App per instance: a function's environment changes only with a new
    deployment, which starts new instances."""
    global _app
    if _app is None:
        env: dict[str, str] = dict(os.environ)
        extra = getattr(context, "env", None) if not isinstance(context, Mapping) else context.get("env")
        if isinstance(extra, Mapping):
            env.update({str(key): str(value) for key, value in extra.items()})
        _app = App(config_from_env(env))
    return _app


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def to_request(event: Mapping[str, Any]) -> Request:
    """The request an event describes."""
    headers = Headers()
    for name, values in (event.get("multiValueHeaders") or {}).items():
        for value in _values(values):
            headers.add(name, value)
    for name, value in (event.get("headers") or {}).items():
        if name not in headers and value is not None:
            # Payload 2.0 joins repeated headers with commas already.
            headers.set(name, ", ".join(_values(value)))
    cookies = event.get("cookies")
    if cookies and "cookie" not in headers:
        headers.set("cookie", "; ".join(_values(cookies)))

    http = (event.get("requestContext") or {}).get("http") or {}
    method = str(http.get("method") or event.get("httpMethod") or event.get("method") or "GET").upper()

    if event.get("url"):
        url = urlsplit(str(event["url"]))
        path, query = url.path or "/", url.query
    else:
        path = str(event.get("rawPath") or http.get("path") or event.get("path") or "/")
        if event.get("rawQueryString") is not None:
            query = str(event["rawQueryString"])
        else:
            pairs: list[tuple[str, str]] = []
            multi = event.get("multiValueQueryStringParameters") or {}
            for name, values in multi.items():
                pairs.extend((name, value) for value in _values(values))
            for name, value in (event.get("queryStringParameters") or {}).items():
                if name not in multi:
                    pairs.extend((name, item) for item in _values(value))
            for name, value in (event.get("query") or {}).items():
                pairs.extend((name, item) for item in _values(value))
            query = urlencode(pairs)

    body = b""
    raw = event.get("body")
    if raw is not None and method not in ("GET", "HEAD"):
        if isinstance(raw, (bytes, bytearray, memoryview)):
            body = bytes(raw)
        elif event.get("isBase64Encoded"):
            try:
                body = base64.b64decode(str(raw), validate=True)
            except (binascii.Error, ValueError):
                body = b"\x00invalid base64"  # refused downstream as a body that does not parse
        else:
            body = str(raw).encode("utf-8")

    request_id = (event.get("requestContext") or {}).get("requestId")
    if request_id and "x-request-id" not in headers:
        headers.set("x-request-id", str(request_id))
    return Request(method=method, path=path, query=query, headers=headers, body=body)


_TEXT = re.compile(r"^(text/|application/(json|problem\+json|yaml|javascript|xml|manifest\+json)|image/svg\+xml)", re.I)


def to_result(response: Response) -> dict[str, Any]:
    """The answer, in the shape the platform takes back."""
    headers = response.headers.as_dict()
    if not response.body or _TEXT.match(headers.get("content-type", "")):
        return {
            "statusCode": response.status,
            "headers": headers,
            "body": response.body.decode("utf-8"),
            "isBase64Encoded": False,
        }
    return {
        "statusCode": response.status,
        "headers": headers,
        "body": base64.b64encode(response.body).decode("ascii"),
        "isBase64Encoded": True,
    }


def handler(event: Mapping[str, Any] | str | bytes, context: Any = None) -> dict[str, Any]:
    """An HTTP event in, an HTTP result out."""
    if isinstance(event, (str, bytes, bytearray)):
        event = json.loads(event)
    if not isinstance(event, Mapping):
        raise TypeError("the event must be a JSON object")
    return to_result(_get_app(context).handle(to_request(event)))

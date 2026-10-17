"""The service: one handler from Request to Response, the same whatever carries
the request (a Cloud Builder Function event, the local HTTP server)."""

from __future__ import annotations

import html
import io
import json
import logging
import re
import time
import uuid
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from editpdf import __version__
from editpdf.config import Config
from editpdf.download import base_name, content_disposition, output_name
from editpdf.forms import Form
from editpdf.http import Headers, Request, Response
from editpdf.pages import ResolvedRange, parse_page_selection
from editpdf.pdf import (
    RotationRule,
    SplitSpec,
    inspect_document,
    merge_documents,
    rotate_document,
    split_document,
)
from editpdf.problems import PROBLEMS, ApiError, problem_body
from editpdf.static import StaticFiles

API_PREFIX = "/api/"

# In the repository, backend/src/editpdf -> the repository root: where the
# OpenAPI document and the built interface are found during development. A
# bundled package carries its own (resources/, static/) and may sit anywhere.
_HERE = Path(__file__).resolve().parent
_REPOSITORY = _HERE.parents[2] if len(_HERE.parents) > 2 else _HERE

# Headers a browser page on another origin may read (CORS).
_EXPOSED_HEADERS = "Content-Disposition, X-Page-Count, X-Part-Count, X-Request-Id"

# On every API answer: documents are private, and none of it is a page.
_API_HEADERS = {
    "cache-control": "no-store",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
}

_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_ANGLES = {-270, -180, -90, 90, 180, 270}

logger = logging.getLogger("editpdf")


def _bundled() -> Traversable:
    """The package's own files, wherever the runtime imports it from (a
    directory, or the function's zip)."""
    return files("editpdf")


def _resource(bundled: str, in_repository: str) -> Traversable:
    """A file the package carries when bundled (resources/), else the repository's own."""
    resource = _bundled().joinpath("resources").joinpath(bundled)
    return resource if resource.is_file() else _REPOSITORY / in_repository


@cache
def openapi_text() -> str:
    return _resource("openapi.yaml", "openapi/editpdf-v1.yaml").read_text(encoding="utf-8")


@cache
def api_version() -> str:
    match = re.search(r"^info:\n(?:[ ]{2}.*\n)*?[ ]{2}version:\s*(\S+)", openapi_text(), re.MULTILINE)
    return match.group(1) if match else "unknown"


@cache
def terms_version() -> str:
    return _resource("TERMS_VERSION", "legal/VERSION").read_text(encoding="utf-8").strip()


def default_static_dir() -> Traversable:
    """The built interface: the package's static/ when bundled, else frontend/dist."""
    bundled = _bundled().joinpath("static")
    return bundled if bundled.joinpath("index.html").is_file() else _REPOSITORY / "frontend" / "dist"


def _log_json(entry: dict[str, Any]) -> None:
    level = {"info": logging.INFO, "warn": logging.WARNING, "error": logging.ERROR}[entry["level"]]
    logger.log(level, json.dumps({"service": "editpdf", **entry}, default=str))


# --- Parsing fields ------------------------------------------------------------------------


def _parse_angle(value: Any, field: str, from_text: bool) -> int:
    """An angle from a form field (text) or from the rotations JSON (a number, not a string)."""
    if from_text and isinstance(value, str) and re.fullmatch(r"-?\d{1,3}", value):
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or value not in _ANGLES:
        raise ApiError("invalid_request", f"{field} must be one of 90, 180, 270, -90, -180, -270.", field=field)
    return value


def _parse_rotations(text: str) -> list[RotationRule]:
    try:
        parsed = json.loads(text)
    except ValueError as error:
        raise ApiError("invalid_request", "rotations must be a JSON array.", field="rotations") from error
    if not isinstance(parsed, list) or not 1 <= len(parsed) <= 1000:
        raise ApiError("invalid_request", "rotations must be a JSON array of 1 to 1000 items.", field="rotations")
    rules = []
    for index, item in enumerate(parsed):
        field = f"rotations[{index}]"
        if not isinstance(item, dict):
            raise ApiError(
                "invalid_request", f"{field} must be an object with angle and, optionally, pages.", field=field
            )
        pages = item.get("pages")
        if pages is not None and not isinstance(pages, str):
            raise ApiError(
                "invalid_request", f'{field}.pages must be a page selection such as "1-3,5".', field=f"{field}.pages"
            )
        rules.append(
            RotationRule(
                angle=_parse_angle(item.get("angle"), f"{field}.angle", from_text=False),
                pages=None if pages is None else tuple(parse_page_selection(pages, f"{field}.pages")),
            )
        )
    return rules


def _parse_split_spec(form: Form) -> SplitSpec:
    size_text = form.text("size")
    ranges_text = form.text("ranges")
    # Without a mode, the field sent says which one is meant.
    mode = form.text("mode") or ("ranges" if ranges_text is not None else "every" if size_text is not None else "each")
    if mode == "each":
        if size_text is not None or ranges_text is not None:
            raise ApiError("invalid_request", "mode each takes neither size nor ranges.", field="mode")
        return SplitSpec("each")
    if mode == "every":
        if ranges_text is not None:
            raise ApiError("invalid_request", "mode every takes size, not ranges.", field="ranges")
        if size_text is None or not re.fullmatch(r"\d{1,7}", size_text) or int(size_text) < 1:
            raise ApiError("invalid_request", "size must be a whole number of pages, 1 or more.", field="size")
        return SplitSpec("every", size=int(size_text))
    if mode == "ranges":
        if size_text is not None:
            raise ApiError("invalid_request", "mode ranges takes ranges, not size.", field="size")
        if ranges_text is None:
            raise ApiError("invalid_request", "ranges is required with mode ranges, e.g. 1-3,4-6,7-.", field="ranges")
        return SplitSpec("ranges", ranges=tuple(parse_page_selection(ranges_text, "ranges")))
    raise ApiError("invalid_request", "mode must be each, every or ranges.", field="mode")


def _part_name(base: str, pages: ResolvedRange, page_count: int) -> str:
    width = len(str(page_count))
    start, end = str(pages.start).zfill(width), str(pages.end).zfill(width)
    return f"{base}-p{start}.pdf" if pages.start == pages.end else f"{base}-p{start}-{end}.pdf"


def _zip(entries: list[tuple[str, bytes]]) -> bytes:
    """A ZIP of the entries, in order. PDFs are compressed already, so they are
    stored; names are made unique, since extracting two of one name loses one."""
    buffer = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in entries:
            unique, copy = name, 2
            while unique in used:
                stem, dot, extension = name.rpartition(".")
                unique = f"{stem} ({copy}).{extension}" if dot else f"{name} ({copy})"
                copy += 1
            used.add(unique)
            archive.writestr(unique, data)
    return buffer.getvalue()


def _file_response(data: bytes, content_type: str, name: str, extra: Mapping[str, str]) -> Response:
    headers = Headers(
        {
            "content-type": content_type,
            "content-length": str(len(data)),
            "content-disposition": content_disposition(name),
        }
    )
    for key, value in extra.items():
        headers.set(key, value)
    return Response(200, headers, data)


def _problem_page(code: str) -> Response:
    """What a problem type URI resolves to: a page describing that problem."""
    kind = PROBLEMS[code]
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(kind.title)} - editpdf</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem}}
code{{background:#8882;padding:0 .3em;border-radius:3px}}</style>
</head><body>
<h1>{html.escape(kind.title)}</h1>
<p>HTTP {kind.status} &middot; <code>{code}</code></p>
<p>{html.escape(kind.description)}</p>
<p><a href="/api/v1/openapi.yaml">API reference</a> &middot; <a href="/">editpdf</a></p>
</body></html>
"""
    response = Response.text(page, "text/html; charset=utf-8")
    response.headers.set("cache-control", "public, max-age=3600")
    response.headers.set(
        "content-security-policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"
    )
    response.headers.set("x-content-type-options", "nosniff")
    return response


# --- The service ------------------------------------------------------------------------------

Route = Callable[[Request], Response]


@dataclass(frozen=True)
class Operation:
    path: str
    method: str


class App:
    def __init__(
        self,
        config: Config,
        *,
        static_dir: Traversable | None = None,
        log: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config
        self.static = StaticFiles(static_dir if static_dir is not None else default_static_dir())
        self.log = log or _log_json
        self.routes: dict[str, dict[str, Route]] = {
            "/api/v1/pdf/merge": {"POST": self.merge},
            "/api/v1/pdf/split": {"POST": self.split},
            "/api/v1/pdf/rotate": {"POST": self.rotate},
            "/api/v1/pdf/inspect": {"POST": self.inspect},
            "/api/v1/info": {"GET": self.info},
            "/api/v1/health": {"GET": self.health},
            "/api/v1/openapi.yaml": {"GET": self.openapi},
        }

    def operations(self) -> list[Operation]:
        """Every API path and method, for the contract test against the OpenAPI document."""
        return [Operation(path, method.lower()) for path, methods in self.routes.items() for method in methods]

    # --- Routes

    def _form(self, request: Request) -> Form:
        if max(len(request.body), request.declared_length or 0) > self.config.limits.max_upload_bytes:
            megabytes = int(self.config.limits.max_upload_bytes / (1024 * 1024) * 10) / 10
            raise ApiError(
                "payload_too_large", f"The request is larger than the {megabytes:g} MB this service accepts."
            )
        return Form.parse(request.headers.get("content-type") or "", request.body)

    def merge(self, request: Request) -> Response:
        form = self._form(request)
        limits = self.config.limits
        count = form.count("files")
        if count > limits.max_files:
            raise ApiError("too_many_files", f"One merge takes at most {limits.max_files} documents.", field="files")
        if count < 2:
            raise ApiError("invalid_request", "files must hold at least two documents to merge.", field="files")
        name = output_name(form.text("filename"), "merged.pdf", ".pdf")
        result = merge_documents(form.files("files"), limits)
        return _file_response(result.data, "application/pdf", name, {"x-page-count": str(result.page_count)})

    def split(self, request: Request) -> Response:
        form = self._form(request)
        spec = _parse_split_spec(form)
        requested = form.text("filename")
        document = form.file("file")
        base = base_name(document.name)
        parts = split_document(document, spec, self.config.limits)
        last_page = max(part.pages.end for part in parts)
        archive = _zip([(_part_name(base, part.pages, last_page), part.data) for part in parts])
        name = output_name(requested, f"{base}-split.zip", ".zip")
        return _file_response(archive, "application/zip", name, {"x-part-count": str(len(parts))})

    def rotate(self, request: Request) -> Response:
        form = self._form(request)
        rotations_text = form.text("rotations")
        if rotations_text is not None:
            rules = _parse_rotations(rotations_text)
        else:
            angle_text = form.text("angle")
            if angle_text is None:
                raise ApiError("invalid_request", "Send angle (90, 180, 270), or rotations.", field="angle")
            pages_text = form.text("pages")
            rules = [
                RotationRule(
                    angle=_parse_angle(angle_text, "angle", from_text=True),
                    pages=None if pages_text is None else tuple(parse_page_selection(pages_text, "pages")),
                )
            ]
        requested = form.text("filename")
        document = form.file("file")
        result = rotate_document(document, rules, self.config.limits)
        name = output_name(requested, f"{base_name(document.name)}-rotated.pdf", ".pdf")
        return _file_response(result.data, "application/pdf", name, {"x-page-count": str(result.page_count)})

    def inspect(self, request: Request) -> Response:
        form = self._form(request)
        return Response.json(inspect_document(form.file("file"), self.config.limits))

    def info(self, request: Request) -> Response:
        return Response.json(
            {
                "service": "editpdf",
                "version": __version__,
                "apiVersion": api_version(),
                "limits": self.config.limits.as_json(),
                "terms": {"version": terms_version(), "url": f"{self.config.public_url}/terms"},
            }
        )

    def health(self, request: Request) -> Response:
        return Response.json({"status": "ok"})

    def openapi(self, request: Request) -> Response:
        return Response.text(openapi_text(), "application/yaml; charset=utf-8")

    # --- Dispatch

    def _cors(self, request: Request) -> dict[str, str]:
        origin = request.headers.get("origin")
        if origin is None or origin not in self.config.cors_origins:
            return {}
        return {
            "access-control-allow-origin": origin,
            "access-control-expose-headers": _EXPOSED_HEADERS,
            "vary": "Origin",
        }

    def _route(self, request: Request) -> Response:
        path = request.path
        method = request.method.upper()

        if path.startswith(API_PREFIX):
            methods = self.routes.get(path)
            if methods is None:
                raise ApiError("not_found", f"There is no API operation at {path}.")
            if method == "OPTIONS":
                # A CORS preflight: answered for the origins configured, empty for the rest.
                allowed = self._cors(request)
                response = Response(204)
                if allowed:
                    for name, value in allowed.items():
                        response.headers.set(name, value)
                    response.headers.set("access-control-allow-methods", ", ".join([*methods, "OPTIONS"]))
                    response.headers.set("access-control-allow-headers", "Content-Type, X-Request-Id")
                    response.headers.set("access-control-max-age", "600")
                return response
            route = methods.get("GET" if method == "HEAD" else method)
            if route is None:
                allow = [m for name in methods for m in (["GET", "HEAD"] if name == "GET" else [name])]
                raise ApiError(
                    "method_not_allowed", f"{path} answers {', '.join(allow)}.", headers={"allow": ", ".join(allow)}
                )
            response = route(request)
            if method == "HEAD":
                response.body = b""
            return response

        if method not in ("GET", "HEAD"):
            raise ApiError("method_not_allowed", f"{path} answers GET and HEAD.", headers={"allow": "GET, HEAD"})
        if path.startswith("/problems/"):
            code = path.removeprefix("/problems/")
            if code in PROBLEMS:
                return _problem_page(code)
            raise ApiError("not_found", f"There is no problem type {code[:40]}.")
        if self.config.serve_ui:
            response = self.static.response(request)
            if response is not None:
                return response
        raise ApiError("not_found", f"There is nothing at {path}.")

    def handle(self, request: Request) -> Response:
        started = time.monotonic()
        given = request.headers.get("x-request-id")
        request_id = given if given is not None and _REQUEST_ID.fullmatch(given) else str(uuid.uuid4())
        failure: BaseException | None = None
        try:
            response = self._route(request)
        except ApiError as error:
            failure = error
            response = self._problem(error, request_id)
        except Exception as error:  # the client gets a problem document, the log the stack
            failure = error
            response = self._problem(
                ApiError("internal_error", "Something failed on our side.", cause=error), request_id
            )

        if request.path.startswith(API_PREFIX) or failure is not None:
            for name, value in _API_HEADERS.items():
                response.headers.setdefault(name, value)
        for name, value in self._cors(request).items():
            response.headers.setdefault(name, value)
        response.headers.set("x-request-id", request_id)

        # Never the documents, nor their names: they are the users' business.
        entry: dict[str, Any] = {
            "method": request.method,
            "path": request.path,
            "status": response.status,
            "durationMs": round((time.monotonic() - started) * 1000),
            "requestId": request_id,
        }
        if isinstance(failure, ApiError):
            if failure.cause is None:
                self.log({"level": "info", "message": "request refused", **entry, "code": failure.code})
            else:
                # A cause means a document that parsed and still failed: worth a look.
                self.log(
                    {
                        "level": "warn",
                        "message": "request refused",
                        **entry,
                        "code": failure.code,
                        "cause": repr(failure.cause),
                    }
                )
        elif failure is not None:
            logger.exception("request failed", exc_info=failure)
            self.log({"level": "error", "message": "request failed", **entry, "error": repr(failure)})
        else:
            self.log({"level": "info", "message": "request served", **entry})
        return response

    def _problem(self, error: ApiError, request_id: str) -> Response:
        response = Response.json(
            problem_body(error, self.config.public_url, request_id), error.status, "application/problem+json"
        )
        for name, value in error.headers.items():
            response.headers.set(name, value)
        return response

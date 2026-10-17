"""Errors as RFC 9457 problem documents. `code` is the stable, documented
identifier (openapi/editpdf-v1.yaml, ProblemCode); the type URI is built on it
and resolves to a page describing the problem."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProblemKind:
    status: int
    title: str
    description: str


PROBLEMS: Mapping[str, ProblemKind] = {
    "invalid_request": ProblemKind(
        400,
        "Invalid request",
        "A required field is missing, or a field holds a value the operation does not accept.",
    ),
    "invalid_page_selection": ProblemKind(
        400,
        "Invalid page selection",
        "A page selection does not parse. It is a comma-separated list of 1-based page numbers "
        "and ranges: 1, 2-5, 7- (to the last page).",
    ),
    "too_many_files": ProblemKind(
        400,
        "Too many files",
        "The request carries more documents than one merge accepts. GET /api/v1/info gives the limit.",
    ),
    "too_many_pages": ProblemKind(
        413,
        "Too many pages",
        "The request would process more pages, all documents together, than one request may. "
        "GET /api/v1/info gives the limit.",
    ),
    "payload_too_large": ProblemKind(
        413,
        "Payload too large",
        "The request body is larger than this deployment accepts. GET /api/v1/info gives the limit.",
    ),
    "unsupported_media_type": ProblemKind(
        415,
        "Unsupported media type",
        "Operations on documents take multipart/form-data.",
    ),
    "invalid_pdf": ProblemKind(
        422,
        "Not a valid PDF",
        "A file is not a PDF document, or it is damaged beyond what can be read.",
    ),
    "encrypted_pdf": ProblemKind(
        422,
        "Password protected PDF",
        "A document is encrypted. Remove its password with the program that set it, then try again.",
    ),
    "page_out_of_range": ProblemKind(
        422,
        "Page out of range",
        "A page selection names a page the document does not have.",
    ),
    "not_found": ProblemKind(404, "Not found", "There is nothing at this address."),
    "method_not_allowed": ProblemKind(
        405,
        "Method not allowed",
        "The address exists, but does not answer this HTTP method. The Allow header lists the ones it does.",
    ),
    "internal_error": ProblemKind(
        500,
        "Internal error",
        "Something failed on our side. Quote the request id when reporting it.",
    ),
}


class ApiError(Exception):
    """An error the client caused, or one we report to it as a problem document."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        field: str | None = None,
        headers: Mapping[str, str] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if code not in PROBLEMS:
            raise ValueError(f"unknown problem code {code}")
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.field = field
        self.headers = dict(headers or {})
        #: What went wrong underneath, for the log; never shown to the client.
        self.cause = cause

    @property
    def status(self) -> int:
        return PROBLEMS[self.code].status


def problem_type(public_url: str, code: str) -> str:
    return f"{public_url}/problems/{code}"


def problem_body(error: ApiError, public_url: str, request_id: str) -> dict[str, Any]:
    kind = PROBLEMS[error.code]
    body: dict[str, Any] = {
        "type": problem_type(public_url, error.code),
        "title": kind.title,
        "status": kind.status,
        "code": error.code,
        "detail": error.detail,
    }
    if error.field is not None:
        body["field"] = error.field
    body["requestId"] = request_id
    return body

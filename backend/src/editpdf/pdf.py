"""The operations on documents, with pypdf (pure Python: it runs wherever the
function does)."""

from __future__ import annotations

import io
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, TypeVar

from pypdf import PdfReader, PdfWriter

from editpdf.config import Limits
from editpdf.pages import PageRange, ResolvedRange, resolve_range, selected_indices
from editpdf.problems import ApiError

PRODUCER = "CoderForge editpdf (https://editpdf.coderforge.org)"

# The header may follow some junk (PDF 1.7, 7.5.2 lets readers tolerate it,
# and real files carry it), but not much.
_HEADER_WINDOW = 1024

T = TypeVar("T")


@dataclass(frozen=True)
class InputDocument:
    """A document as it arrived: the name the client gave it and its bytes."""

    name: str
    data: bytes


@dataclass(frozen=True)
class OutputDocument:
    data: bytes
    page_count: int


@dataclass(frozen=True)
class SplitPart:
    data: bytes
    page_count: int
    #: The pages of the source the part holds.
    pages: ResolvedRange


def has_pdf_header(data: bytes) -> bool:
    return b"%PDF-" in data[:_HEADER_WINDOW]


def normalize_angle(angle: int) -> int:
    """A clockwise rotation in [0, 360), from whatever a page declares (-90, 450...)."""
    return (round(angle / 90) * 90) % 360


def load_document(document: InputDocument, field: str, *, allow_encrypted: bool = False) -> PdfReader:
    """Parses a document, turning every way it can fail into a problem the
    client can act on. `field` is the request field the document came in."""
    if not has_pdf_header(document.data):
        raise ApiError("invalid_pdf", f'"{document.name}" is not a PDF document.', field=field)
    try:
        reader = PdfReader(io.BytesIO(document.data), strict=False)
        encrypted = reader.is_encrypted
    except Exception as error:  # pypdf raises many kinds; all mean the same to the client
        raise ApiError(
            "invalid_pdf", f'"{document.name}" is damaged and cannot be read.', field=field, cause=error
        ) from error
    if encrypted:
        if allow_encrypted:
            return reader
        raise ApiError(
            "encrypted_pdf",
            f'"{document.name}" is password protected. '
            "Remove the password with the program that set it, then try again.",
            field=field,
        )
    try:
        # A file can parse and still have no usable page tree.
        page_count = len(reader.pages)
    except Exception as error:
        raise ApiError(
            "invalid_pdf", f'"{document.name}" is damaged and cannot be read.', field=field, cause=error
        ) from error
    if page_count == 0:
        raise ApiError("invalid_pdf", f'"{document.name}" has no pages.', field=field)
    return reader


def _guarded(document: InputDocument, field: str, work: Callable[[], T]) -> T:
    """Runs the work on a document that parsed. A document can parse and still
    be too damaged to copy pages out of; that is the client's file, not our fault."""
    try:
        return work()
    except ApiError:
        raise
    except Exception as error:
        raise ApiError(
            "invalid_pdf",
            f'"{document.name}" could not be processed: '
            "it is damaged, or uses a feature this service does not support.",
            field=field,
            cause=error,
        ) from error


def _too_many_pages(limits: Limits) -> ApiError:
    return ApiError(
        "too_many_pages", f"One request processes at most {limits.max_pages} pages, all documents together."
    )


def _new_writer(title: str | None = None) -> PdfWriter:
    writer = PdfWriter()
    now = _pdf_date(datetime.now(timezone.utc))
    metadata = {"/Producer": PRODUCER, "/Creator": PRODUCER, "/CreationDate": now, "/ModDate": now}
    if title:
        metadata["/Title"] = title
    writer.add_metadata(metadata)
    return writer


def _pdf_date(moment: datetime) -> str:
    return moment.strftime("D:%Y%m%d%H%M%SZ")


def _save(writer: PdfWriter) -> bytes:
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _title_of(reader: PdfReader) -> str | None:
    try:
        metadata = reader.metadata
        return None if metadata is None else (metadata.title or None)
    except Exception:
        return None


def merge_documents(documents: Sequence[InputDocument], limits: Limits) -> OutputDocument:
    """Every page of every document, in order."""
    writer = _new_writer()
    page_count = 0
    for document in documents:
        reader = load_document(document, "files")
        page_count += len(reader.pages)
        if page_count > limits.max_pages:
            raise _too_many_pages(limits)

        def copy(reader: PdfReader = reader) -> None:
            for page in reader.pages:
                writer.add_page(page)

        _guarded(document, "files", copy)
    return OutputDocument(_save(writer), page_count)


SplitMode = Literal["each", "every", "ranges"]


@dataclass(frozen=True)
class SplitSpec:
    mode: SplitMode
    size: int = 1
    ranges: tuple[PageRange, ...] = ()


def _split_ranges(spec: SplitSpec, page_count: int) -> list[ResolvedRange]:
    if spec.mode == "each":
        return [ResolvedRange(page, page) for page in range(1, page_count + 1)]
    if spec.mode == "every":
        return [
            ResolvedRange(start, min(start + spec.size - 1, page_count))
            for start in range(1, page_count + 1, spec.size)
        ]
    return [resolve_range(page_range, page_count, "ranges") for page_range in spec.ranges]


def split_document(document: InputDocument, spec: SplitSpec, limits: Limits) -> list[SplitPart]:
    """One document per part, in the order the parts were asked for."""
    reader = load_document(document, "file")
    page_count = len(reader.pages)
    if page_count > limits.max_pages:
        raise _too_many_pages(limits)
    ranges = _split_ranges(spec, page_count)
    # Ranges may overlap: what is bounded is the work, the pages written out.
    if sum(len(part) for part in ranges) > limits.max_pages:
        raise _too_many_pages(limits)
    title = _title_of(reader)

    def cut() -> list[SplitPart]:
        parts = []
        for part in ranges:
            writer = _new_writer(title)
            for index in range(part.start - 1, part.end):
                writer.add_page(reader.pages[index])
            parts.append(SplitPart(_save(writer), len(part), part))
        return parts

    return _guarded(document, "file", cut)


@dataclass(frozen=True)
class RotationRule:
    #: Clockwise, a multiple of 90.
    angle: int
    #: The pages to turn; all of them when None.
    pages: tuple[PageRange, ...] | None = None


def rotate_document(document: InputDocument, rules: Iterable[RotationRule], limits: Limits) -> OutputDocument:
    """Turns pages on top of the rotation they already have."""
    reader = load_document(document, "file")
    page_count = len(reader.pages)
    if page_count > limits.max_pages:
        raise _too_many_pages(limits)
    turns: dict[int, int] = {}
    for rule in rules:
        if rule.pages is None:
            indices: Iterable[int] = range(page_count)
        else:
            indices = selected_indices(rule.pages, page_count, "pages")
        for index in indices:
            turns[index] = turns.get(index, 0) + rule.angle

    def turn() -> bytes:
        writer = PdfWriter(clone_from=reader)
        for index, angle in turns.items():
            page = writer.pages[index]
            page.rotation = normalize_angle(page.rotation + angle)
        writer.add_metadata({"/ModDate": _pdf_date(datetime.now(timezone.utc))})
        return _save(writer)

    return OutputDocument(_guarded(document, "file", turn), page_count)


def _iso(value: Any) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _metadata(reader: PdfReader) -> dict[str, str]:
    try:
        info = reader.metadata
    except Exception:
        return {}
    if info is None:
        return {}
    # Each entry on its own: one undecodable string should not hide the others.
    readers: dict[str, Callable[[], Any]] = {
        "title": lambda: info.title,
        "author": lambda: info.author,
        "subject": lambda: info.subject,
        "keywords": lambda: info.get("/Keywords"),
        "creator": lambda: info.creator,
        "producer": lambda: info.producer,
        "creationDate": lambda: _iso(info.creation_date),
        "modificationDate": lambda: _iso(info.modification_date),
    }
    metadata: dict[str, str] = {}
    for key, read in readers.items():
        try:
            value = read()
        except Exception:
            continue
        if value is not None and str(value) != "":
            metadata[key] = str(value)
    return metadata


def inspect_document(document: InputDocument, limits: Limits) -> dict[str, Any]:
    """What a document holds. An encrypted one is described as far as can be
    done without its password."""
    reader = load_document(document, "file", allow_encrypted=True)
    encrypted = reader.is_encrypted
    if encrypted:
        try:
            # Many "protected" files only restrict printing or editing: their
            # user password is empty, and their structure opens without one.
            reader.decrypt("")
            pages = list(reader.pages)
        except Exception:
            pages = []
    else:
        pages = _guarded(document, "file", lambda: list(reader.pages))
    if len(pages) > limits.max_pages:
        raise _too_many_pages(limits)

    def describe() -> list[dict[str, Any]]:
        return [
            {
                "number": number,
                "width": round(float(page.mediabox.width), 2),
                "height": round(float(page.mediabox.height), 2),
                "rotation": normalize_angle(int(page.rotation)),
            }
            for number, page in enumerate(pages, start=1)
        ]

    return {
        "pageCount": len(pages),
        "encrypted": encrypted,
        "sizeBytes": len(document.data),
        "pages": _guarded(document, "file", describe),
        # An encrypted document's strings are ciphertext.
        "metadata": {} if encrypted else _metadata(reader),
    }

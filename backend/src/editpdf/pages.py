"""Page selections: comma-separated page numbers and ranges, `1`, `2-5`, `7-`."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from editpdf.problems import ApiError

# Generous, but it keeps a selection from being a way to make us loop: no
# document has a page number of eight digits, and nobody types 1000 ranges.
MAX_ITEMS = 1000
_ITEM = re.compile(r"(\d{1,7})(?:\s*-\s*(\d{1,7})?)?")


@dataclass(frozen=True)
class PageRange:
    """A run of pages, 1-based and inclusive; `end` None means "to the last page"."""

    start: int
    end: int | None


@dataclass(frozen=True)
class ResolvedRange:
    """A run of pages resolved against a document: 1-based, inclusive."""

    start: int
    end: int

    def __len__(self) -> int:
        return self.end - self.start + 1


def parse_page_selection(text: str, field: str) -> list[PageRange]:
    """Parses a selection, keeping its order and merging nothing: for a split
    every item is a part of its own."""
    items = [item.strip() for item in text.split(",")]
    if len(items) > MAX_ITEMS:
        raise ApiError("invalid_page_selection", f"{field} has more than {MAX_ITEMS} items.", field=field)
    ranges: list[PageRange] = []
    for item in items:
        match = _ITEM.fullmatch(item)
        if match is None:
            shown = "an empty item" if item == "" else f'"{item[:40]}"'
            raise ApiError(
                "invalid_page_selection",
                f"{field} has {shown}; expected a page number (3), a range (2-5) or an open range (7-).",
                field=field,
            )
        start = int(match.group(1))
        if match.group(2) is not None:
            end: int | None = int(match.group(2))
        else:
            end = None if "-" in item else start
        if start < 1:
            raise ApiError("invalid_page_selection", f"{field}: pages are numbered from 1.", field=field)
        if end is not None and end < start:
            raise ApiError(
                "invalid_page_selection",
                f"{field}: the range {start}-{end} ends before it starts.",
                field=field,
            )
        ranges.append(PageRange(start, end))
    return ranges


def resolve_range(page_range: PageRange, page_count: int, field: str) -> ResolvedRange:
    """Resolves a range against a document of `page_count` pages."""
    end = page_count if page_range.end is None else page_range.end
    if page_range.start > page_count or end > page_count:
        if page_range.end == page_range.start:
            shown = f"page {page_range.start}"
        else:
            shown = f"pages {page_range.start}-{'' if page_range.end is None else page_range.end}"
        plural = "" if page_count == 1 else "s"
        raise ApiError(
            "page_out_of_range",
            f"{field} names {shown}, but the document has {page_count} page{plural}.",
            field=field,
        )
    return ResolvedRange(page_range.start, end)


def selected_indices(ranges: Iterable[PageRange], page_count: int, field: str) -> list[int]:
    """The 0-based indices of the pages a selection names, each once, in document order."""
    selected: set[int] = set()
    for page_range in ranges:
        resolved = resolve_range(page_range, page_count, field)
        selected.update(range(resolved.start - 1, resolved.end))
    return sorted(selected)

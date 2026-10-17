import io

import pytest
from pypdf import PdfReader

from editpdf.config import Limits
from editpdf.pages import parse_page_selection
from editpdf.pdf import (
    PRODUCER,
    InputDocument,
    RotationRule,
    SplitSpec,
    has_pdf_header,
    inspect_document,
    merge_documents,
    normalize_angle,
    rotate_document,
    split_document,
)
from editpdf.problems import ApiError

from .helpers import make_encrypted_pdf, make_pdf, page_rotations, page_widths

LIMITS = Limits()


def doc(data: bytes, name: str = "a.pdf") -> InputDocument:
    return InputDocument(name, data)


def problem(work) -> str:
    with pytest.raises(ApiError) as caught:
        work()
    return caught.value.code


def test_finds_the_header_at_the_start_or_after_a_little_junk():
    assert has_pdf_header(b"%PDF-1.7\n")
    assert has_pdf_header(b"junk\n%PDF-1.4\n")
    assert not has_pdf_header(b"PK\x03\x04")
    assert not has_pdf_header(b"")


@pytest.mark.parametrize(("angle", "expected"), [(0, 0), (90, 90), (-90, 270), (450, 90), (-450, 270), (360, 0)])
def test_normalize_angle(angle, expected):
    assert normalize_angle(angle) == expected


class TestMerge:
    def test_concatenates_every_page_in_the_order_given(self):
        first = make_pdf(2, width_base=100)
        second = make_pdf(3, width_base=200)
        result = merge_documents([doc(second), doc(first)], LIMITS)
        assert result.page_count == 5
        assert page_widths(result.data) == [201, 202, 203, 101, 102]

    def test_signs_the_result(self):
        result = merge_documents([doc(make_pdf(1)), doc(make_pdf(1))], LIMITS)
        assert PdfReader(io.BytesIO(result.data)).metadata.producer == PRODUCER

    def test_stops_at_the_page_limit(self):
        limits = Limits(max_pages=4)
        assert problem(lambda: merge_documents([doc(make_pdf(3)), doc(make_pdf(2))], limits)) == "too_many_pages"

    def test_refuses_a_file_that_is_not_a_pdf(self):
        work = lambda: merge_documents([doc(make_pdf(1)), doc(b"hello", "notes.txt")], LIMITS)  # noqa: E731
        assert problem(work) == "invalid_pdf"

    def test_refuses_a_damaged_pdf(self):
        work = lambda: merge_documents([doc(make_pdf(1)), doc(b"%PDF-1.7\ngarbage")], LIMITS)  # noqa: E731
        assert problem(work) == "invalid_pdf"

    def test_refuses_an_encrypted_pdf(self):
        work = lambda: merge_documents([doc(make_pdf(1)), doc(make_encrypted_pdf())], LIMITS)  # noqa: E731
        assert problem(work) == "encrypted_pdf"


class TestSplit:
    def test_one_part_per_page_in_mode_each(self):
        parts = split_document(doc(make_pdf(3)), SplitSpec("each"), LIMITS)
        assert [(part.pages.start, part.pages.end) for part in parts] == [(1, 1), (2, 2), (3, 3)]
        assert page_widths(parts[2].data) == [103]

    def test_parts_of_size_pages_in_mode_every_the_last_shorter(self):
        parts = split_document(doc(make_pdf(5)), SplitSpec("every", size=2), LIMITS)
        assert [part.page_count for part in parts] == [2, 2, 1]
        assert page_widths(parts[1].data) == [103, 104]

    def test_one_part_per_range_overlaps_and_order_kept(self):
        spec = SplitSpec("ranges", ranges=tuple(parse_page_selection("4-,1-2,2", "ranges")))
        parts = split_document(doc(make_pdf(5)), spec, LIMITS)
        assert [page_widths(part.data) for part in parts] == [[104, 105], [101, 102], [102]]

    def test_keeps_the_title_of_the_source(self):
        parts = split_document(doc(make_pdf(2, title="Report")), SplitSpec("each"), LIMITS)
        assert PdfReader(io.BytesIO(parts[0].data)).metadata.title == "Report"

    def test_refuses_a_range_past_the_last_page(self):
        spec = SplitSpec("ranges", ranges=tuple(parse_page_selection("1-9", "ranges")))
        assert problem(lambda: split_document(doc(make_pdf(3)), spec, LIMITS)) == "page_out_of_range"

    def test_bounds_the_pages_written_overlapping_ranges_included(self):
        spec = SplitSpec("ranges", ranges=tuple(parse_page_selection("1-,1-,1-", "ranges")))
        assert problem(lambda: split_document(doc(make_pdf(4)), spec, Limits(max_pages=10))) == "too_many_pages"


class TestRotate:
    def test_turns_every_page_when_no_pages_are_named(self):
        result = rotate_document(doc(make_pdf(3)), [RotationRule(90)], LIMITS)
        assert page_rotations(result.data) == [90, 90, 90]

    def test_turns_only_the_pages_named_on_top_of_their_rotation_adding_up_rules(self):
        first = rotate_document(doc(make_pdf(4)), [RotationRule(180)], LIMITS)
        result = rotate_document(
            doc(first.data),
            [
                RotationRule(90, tuple(parse_page_selection("1-2", "pages"))),
                RotationRule(-90, tuple(parse_page_selection("2", "pages"))),
                RotationRule(270, tuple(parse_page_selection("4", "pages"))),
            ],
            LIMITS,
        )
        assert page_rotations(result.data) == [270, 180, 180, 90]

    def test_refuses_a_page_the_document_does_not_have(self):
        rules = [RotationRule(90, tuple(parse_page_selection("3", "pages")))]
        assert problem(lambda: rotate_document(doc(make_pdf(2)), rules, LIMITS)) == "page_out_of_range"


class TestInspect:
    def test_describes_pages_and_metadata(self):
        data = make_pdf(2, title="Quarterly")
        info = inspect_document(doc(data), LIMITS)
        assert info["pageCount"] == 2
        assert info["encrypted"] is False
        assert info["sizeBytes"] == len(data)
        assert info["pages"] == [
            {"number": 1, "width": 101, "height": 200, "rotation": 0},
            {"number": 2, "width": 102, "height": 200, "rotation": 0},
        ]
        assert info["metadata"]["title"] == "Quarterly"

    def test_describes_an_encrypted_document_without_its_metadata(self):
        info = inspect_document(doc(make_encrypted_pdf()), LIMITS)
        assert info["encrypted"] is True
        assert info["metadata"] == {}

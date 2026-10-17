import pytest

from editpdf.pages import PageRange, ResolvedRange, parse_page_selection, resolve_range, selected_indices
from editpdf.problems import ApiError


def test_reads_numbers_ranges_and_open_ranges_keeping_order():
    assert parse_page_selection("3, 1-2 ,7-", "pages") == [PageRange(3, 3), PageRange(1, 2), PageRange(7, None)]


def test_ignores_whitespace_around_the_dash():
    assert parse_page_selection("2 - 4", "pages") == [PageRange(2, 4)]


@pytest.mark.parametrize("text", ["", "0", "a", "1,,2", "1-2-3", "-3", "5-3", "1.5", "12345678", "1;2"])
def test_refuses(text):
    with pytest.raises(ApiError) as caught:
        parse_page_selection(text, "pages")
    assert caught.value.code == "invalid_page_selection"


def test_refuses_more_than_1000_items():
    with pytest.raises(ApiError) as caught:
        parse_page_selection(",".join(["1"] * 1001), "pages")
    assert caught.value.code == "invalid_page_selection"


def test_names_the_field_and_the_item():
    with pytest.raises(ApiError) as caught:
        parse_page_selection("x", "ranges")
    assert caught.value.field == "ranges"
    assert '"x"' in caught.value.detail


def test_closes_an_open_range_at_the_last_page():
    assert resolve_range(PageRange(3, None), 5, "pages") == ResolvedRange(3, 5)


@pytest.mark.parametrize("page_range", [PageRange(6, 6), PageRange(2, 9), PageRange(6, None)])
def test_refuses_a_page_the_document_does_not_have(page_range):
    with pytest.raises(ApiError) as caught:
        resolve_range(page_range, 5, "pages")
    assert caught.value.code == "page_out_of_range"


def test_selected_indices_are_unique_sorted_and_zero_based():
    assert selected_indices(parse_page_selection("4-5,1,2-4", "pages"), 6, "pages") == [0, 1, 2, 3, 4]

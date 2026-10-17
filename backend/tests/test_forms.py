import pytest

from editpdf.forms import Form, boundary_of, display_name, parse_multipart
from editpdf.problems import ApiError

from .helpers import multipart


def parse(body: bytes, boundary: str = "XyZ"):
    return parse_multipart(body, boundary)


def test_reads_text_and_files_in_order():
    body, content_type = multipart(
        [("mode", "each"), ("files", ("a.pdf", b"%PDF-1\r\n\r\nbinary\x00")), ("files", ("b.pdf", b""))]
    )
    form = Form.parse(content_type, body)
    assert form.text("mode") == "each"
    assert [(d.name, d.data) for d in form.files("files")] == [("a.pdf", b"%PDF-1\r\n\r\nbinary\x00"), ("b.pdf", b"")]
    assert form.count("files") == 2


def test_boundary_of_reads_quoted_and_plain_boundaries():
    assert boundary_of('multipart/form-data; boundary="a b"') == "a b"
    assert boundary_of("Multipart/Form-Data;boundary=xyz") == "xyz"
    assert boundary_of("application/json") is None
    assert boundary_of("multipart/form-data") is None


def test_skips_a_preamble_and_transport_padding():
    body = b'preamble\r\n--XyZ  \r\nContent-Disposition: form-data; name="a"\r\n\r\n1\r\n--XyZ--\r\nepilogue'
    assert [(p.name, p.data) for p in parse(body)] == [("a", b"1")]


def test_reads_utf8_and_extended_file_names():
    body = (
        b'--XyZ\r\nContent-Disposition: form-data; name="f"; filename="Relazione \xc3\xa8.pdf"\r\n\r\nx\r\n'
        b'--XyZ\r\nContent-Disposition: form-data; name="g"; filename="plain.pdf"; filename*=UTF-8\'\'%C3%A0.pdf\r\n\r\ny\r\n'
        b'--XyZ\r\nContent-Disposition: form-data; name="h"; filename="say \\"hi\\".pdf"\r\n\r\nz\r\n'
        b"--XyZ--\r\n"
    )
    assert [p.filename for p in parse(body)] == ["Relazione è.pdf", "à.pdf", 'say "hi".pdf']


@pytest.mark.parametrize(
    "body",
    [
        b"no delimiter at all",
        b'--XyZ\r\nContent-Disposition: form-data; name="a"\r\n\r\nunterminated',
        b'--XyZ\r\nContent-Disposition: attachment; name="a"\r\n\r\n1\r\n--XyZ--',
        b"--XyZ\r\nContent-Disposition: form-data\r\n\r\n1\r\n--XyZ--",
        b"--XyZ\r\nnot a header\r\n\r\n1\r\n--XyZ--",
        b"--XyZjunk\r\n",
    ],
)
def test_refuses_bodies_that_do_not_parse(body):
    with pytest.raises(ApiError) as caught:
        parse(body)
    assert caught.value.code == "invalid_request"


def test_refuses_a_body_of_another_type():
    with pytest.raises(ApiError) as caught:
        Form.parse("application/json", b"{}")
    assert caught.value.code == "unsupported_media_type"


def test_typed_access_refuses_the_wrong_kind_and_repeats():
    body, content_type = multipart([("file", "text instead"), ("mode", ("x.pdf", b"")), ("size", "1"), ("size", "2")])
    form = Form.parse(content_type, body)
    for work, field in [
        (lambda: form.file("file"), "file"),
        (lambda: form.text("mode"), "mode"),
        (lambda: form.text("size"), "size"),
        (lambda: form.file("missing"), "missing"),
    ]:
        with pytest.raises(ApiError) as caught:
            work()
        assert caught.value.field == field


def test_empty_text_is_absent():
    body, content_type = multipart([("ranges", "   ")])
    assert Form.parse(content_type, body).text("ranges") is None


def test_display_name_strips_control_characters_and_shortens():
    assert display_name("a\x00b\nc.pdf") == "abc.pdf"
    assert display_name("") == "document.pdf"
    assert len(display_name("x" * 200)) == 80

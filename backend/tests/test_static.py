import pytest

from .helpers import TestApp


@pytest.fixture
def app(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>editpdf</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-1a2b3c.js").write_text("console.log(1)")
    (tmp_path / "pdfjs" / "wasm").mkdir(parents=True)
    (tmp_path / "pdfjs" / "wasm" / "jbig2.wasm").write_bytes(b"\0asm")
    (tmp_path.parent / "secret.txt").write_text("outside")
    return TestApp(static_dir=tmp_path)


def test_serves_index_at_root_with_the_page_security_headers(app):
    response = app.get("/")
    assert response.status == 200
    assert b"<title>editpdf</title>" in response.body
    assert "default-src 'self'" in response.headers.get("content-security-policy")
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("cache-control") == "no-cache"


@pytest.mark.parametrize("path", ["/terms", "/split", "/it/terms"])
def test_serves_index_for_the_interface_pages(app, path):
    response = app.get(path)
    assert response.status == 200
    assert b"<title>editpdf</title>" in response.body


def test_caches_hashed_assets_for_good(app):
    response = app.get("/assets/app-1a2b3c.js")
    assert response.headers.get("cache-control") == "public, max-age=31536000, immutable"
    assert response.headers.get("content-type") == "text/javascript; charset=utf-8"
    assert response.headers.get("content-security-policy") is None
    assert response.body == b"console.log(1)"


def test_serves_wasm_with_its_type(app):
    assert app.get("/pdfjs/wasm/jbig2.wasm").headers.get("content-type") == "application/wasm"


def test_answers_304_to_a_matching_etag(app):
    etag = app.get("/assets/app-1a2b3c.js").headers.get("etag")
    assert app.get("/assets/app-1a2b3c.js", {"if-none-match": f"W/{etag}"}).status == 304


def test_is_a_404_for_a_missing_file(app):
    assert app.get("/assets/missing.js").status == 404
    assert app.get("/favicon.ico").status == 404


@pytest.mark.parametrize("path", ["/assets/..%2f..%2fsecret.txt", "/..%2fsecret.txt", "/assets/%00.js", "/%ff"])
def test_never_leaves_its_directory(app, path):
    assert app.get(path).status == 404

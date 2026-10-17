import io
import json
import zipfile

import pytest

from .helpers import TestApp, make_pdf, page_rotations, page_widths


def problem_of(response) -> dict:
    assert response.headers.get("content-type") == "application/problem+json"
    return json.loads(response.body)


def merge_fields(*counts: int) -> list:
    return [
        ("files", (f"part {i + 1}.pdf", make_pdf(count, width_base=100 * (i + 1)))) for i, count in enumerate(counts)
    ]


class TestMerge:
    def test_answers_the_merged_document_as_a_download(self):
        response = TestApp().post("/api/v1/pdf/merge", merge_fields(1, 2))
        assert response.status == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert (
            response.headers.get("content-disposition")
            == "attachment; filename=\"merged.pdf\"; filename*=UTF-8''merged.pdf"
        )
        assert response.headers.get("x-page-count") == "3"
        assert response.headers.get("cache-control") == "no-store"
        assert len(response.headers.get("x-request-id")) == 36
        assert page_widths(response.body) == [101, 201, 202]

    def test_names_the_download_as_asked_without_directories_with_a_utf8_fallback(self):
        response = TestApp().post("/api/v1/pdf/merge", [*merge_fields(1, 1), ("filename", "../Relazione finale è.pdf")])
        assert response.headers.get("content-disposition") == (
            "attachment; filename=\"Relazione finale _.pdf\"; filename*=UTF-8''Relazione%20finale%20%C3%A8.pdf"
        )

    def test_needs_two_documents(self):
        response = TestApp().post("/api/v1/pdf/merge", merge_fields(1))
        assert response.status == 400
        assert problem_of(response) | {"requestId": None} == {
            "type": "https://editpdf.coderforge.org/problems/invalid_request",
            "title": "Invalid request",
            "status": 400,
            "code": "invalid_request",
            "detail": "files must hold at least two documents to merge.",
            "field": "files",
            "requestId": None,
        }

    def test_refuses_more_documents_than_the_limit(self):
        response = TestApp({"EDITPDF_MAX_FILES": "2"}).post("/api/v1/pdf/merge", merge_fields(1, 1, 1))
        assert response.status == 400
        assert problem_of(response)["code"] == "too_many_files"

    def test_refuses_a_body_larger_than_the_limit(self):
        response = TestApp({"EDITPDF_MAX_UPLOAD_BYTES": "1000"}).post("/api/v1/pdf/merge", merge_fields(1, 1))
        assert response.status == 413
        assert problem_of(response)["code"] == "payload_too_large"

    def test_refuses_a_body_that_is_not_multipart(self):
        response = TestApp().request("POST", "/api/v1/pdf/merge", b"{}", {"content-type": "application/json"})
        assert response.status == 415
        assert problem_of(response)["code"] == "unsupported_media_type"

    def test_names_the_file_that_is_not_a_pdf(self):
        response = TestApp().post(
            "/api/v1/pdf/merge", [*merge_fields(1), ("files", ("notes.txt", b"hello", "text/plain"))]
        )
        assert response.status == 422
        body = problem_of(response)
        assert body["code"] == "invalid_pdf"
        assert '"notes.txt"' in body["detail"]


class TestSplit:
    @staticmethod
    def split(fields: dict, pages: int = 5):
        return TestApp().post("/api/v1/pdf/split", [("file", ("Report.pdf", make_pdf(pages))), *fields.items()])

    @staticmethod
    def entries(response) -> dict:
        assert response.status == 200
        assert response.headers.get("content-type") == "application/zip"
        with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    def test_splits_every_page_by_default(self):
        response = self.split({})
        assert response.headers.get("x-part-count") == "5"
        assert 'filename="Report-split.zip"' in response.headers.get("content-disposition")
        assert list(self.entries(response)) == [f"Report-p{n}.pdf" for n in range(1, 6)]

    def test_pads_page_numbers_so_the_parts_sort(self):
        assert list(self.entries(self.split({"size": "4"}, 10))) == [
            "Report-p01-04.pdf",
            "Report-p05-08.pdf",
            "Report-p09-10.pdf",
        ]

    def test_infers_ranges_mode_from_the_ranges_field(self):
        files = self.entries(self.split({"ranges": "1-2, 5"}))
        assert list(files) == ["Report-p1-2.pdf", "Report-p5.pdf"]
        assert page_widths(files["Report-p1-2.pdf"]) == [101, 102]

    def test_keeps_both_parts_of_repeated_ranges(self):
        assert list(self.entries(self.split({"ranges": "1,1"}))) == ["Report-p1.pdf", "Report-p1 (2).pdf"]

    @pytest.mark.parametrize(
        ("fields", "field"),
        [
            ({"mode": "every"}, "size"),
            ({"mode": "every", "size": "0"}, "size"),
            ({"mode": "ranges"}, "ranges"),
            ({"mode": "each", "size": "2"}, "mode"),
            ({"mode": "every", "size": "2", "ranges": "1"}, "ranges"),
            ({"mode": "halves"}, "mode"),
        ],
    )
    def test_refuses(self, fields, field):
        response = self.split(fields)
        assert response.status == 400
        body = problem_of(response)
        assert (body["code"], body["field"]) == ("invalid_request", field)

    def test_refuses_a_selection_that_does_not_parse(self):
        body = problem_of(self.split({"ranges": "1-x"}))
        assert (body["code"], body["field"]) == ("invalid_page_selection", "ranges")

    def test_refuses_a_page_the_document_does_not_have(self):
        response = self.split({"ranges": "6"})
        assert response.status == 422
        assert problem_of(response)["code"] == "page_out_of_range"

    def test_needs_the_file(self):
        body = problem_of(TestApp().post("/api/v1/pdf/split", [("mode", "each")]))
        assert (body["code"], body["field"]) == ("invalid_request", "file")


class TestRotate:
    @staticmethod
    def rotate(fields: dict):
        return TestApp().post("/api/v1/pdf/rotate", [("file", ("scan.pdf", make_pdf(3))), *fields.items()])

    def test_turns_all_pages_by_angle(self):
        response = self.rotate({"angle": "-90"})
        assert response.status == 200
        assert 'filename="scan-rotated.pdf"' in response.headers.get("content-disposition")
        assert page_rotations(response.body) == [270, 270, 270]

    def test_turns_the_pages_selected(self):
        assert page_rotations(self.rotate({"angle": "180", "pages": "2-"}).body) == [0, 180, 180]

    def test_applies_rotations_which_win_over_angle(self):
        rotations = json.dumps([{"pages": "1", "angle": 90}, {"angle": 180}])
        assert page_rotations(self.rotate({"rotations": rotations, "angle": "90"}).body) == [270, 180, 180]

    @pytest.mark.parametrize(
        ("fields", "field"),
        [
            ({}, "angle"),
            ({"angle": "45"}, "angle"),
            ({"angle": "ninety"}, "angle"),
            ({"rotations": "nope"}, "rotations"),
            ({"rotations": "[]"}, "rotations"),
            ({"rotations": '[{"pages":1,"angle":90}]'}, "rotations[0].pages"),
            ({"rotations": '[{"angle":"90"}]'}, "rotations[0].angle"),
            ({"rotations": '[{"angle":true}]'}, "rotations[0].angle"),
            ({"rotations": "[null]"}, "rotations[0]"),
        ],
    )
    def test_refuses(self, fields, field):
        response = self.rotate(fields)
        assert response.status == 400
        body = problem_of(response)
        assert (body["code"], body["field"]) == ("invalid_request", field)


def test_inspect_describes_the_document():
    response = TestApp().post("/api/v1/pdf/inspect", [("file", ("a.pdf", make_pdf(2, title="Hello")))])
    body = json.loads(response.body)
    assert (body["pageCount"], body["encrypted"], body["metadata"]["title"]) == (2, False, "Hello")


class TestServiceRoutes:
    def test_info_gives_versions_limits_and_the_terms(self):
        body = json.loads(TestApp({"EDITPDF_MAX_FILES": "7"}).get("/api/v1/info").body)
        assert body == {
            "service": "editpdf",
            "version": "1.0.0",
            "apiVersion": "1.0.0",
            "limits": {"maxUploadBytes": 26214400, "maxFiles": 7, "maxPages": 2000},
            "terms": {"version": body["terms"]["version"], "url": "https://editpdf.coderforge.org/terms"},
        }

    def test_health(self):
        assert json.loads(TestApp().get("/api/v1/health").body) == {"status": "ok"}

    def test_head_answers_like_get_without_a_body(self):
        response = TestApp().request("HEAD", "/api/v1/health")
        assert (response.status, response.body) == (200, b"")

    def test_openapi_document_is_served(self):
        response = TestApp().get("/api/v1/openapi.yaml")
        assert response.headers.get("content-type") == "application/yaml; charset=utf-8"
        assert response.body.startswith(b"openapi: 3.1.0")

    def test_unknown_api_path_is_a_404_problem(self):
        response = TestApp().get("/api/v2/pdf/merge")
        assert response.status == 404
        assert problem_of(response)["code"] == "not_found"

    def test_wrong_method_is_a_405_naming_the_right_ones(self):
        response = TestApp().get("/api/v1/pdf/merge")
        assert response.status == 405
        assert response.headers.get("allow") == "POST"
        assert problem_of(response)["code"] == "method_not_allowed"

    def test_problem_type_resolves_to_a_page(self):
        app = TestApp()
        response = app.get("/problems/encrypted_pdf")
        assert response.status == 200
        assert b"Password protected PDF" in response.body
        assert app.get("/problems/nonsense").status == 404

    def test_keeps_a_valid_request_id_and_replaces_an_invalid_one(self):
        app = TestApp()
        assert app.get("/api/v1/health", {"x-request-id": "abc-123"}).headers.get("x-request-id") == "abc-123"
        assert "<" not in app.get("/api/v1/health", {"x-request-id": "bad id <script>"}).headers.get("x-request-id")

    def test_logs_requests_without_file_names(self):
        app = TestApp()
        app.post("/api/v1/pdf/inspect", [("file", ("secret-salary.pdf", b"not a pdf"))])
        assert len(app.logs) == 1
        assert app.logs[0] | {"durationMs": 0, "requestId": ""} == {
            "level": "info",
            "message": "request refused",
            "method": "POST",
            "path": "/api/v1/pdf/inspect",
            "status": 422,
            "code": "invalid_pdf",
            "durationMs": 0,
            "requestId": "",
        }
        assert "secret-salary" not in json.dumps(app.logs)

    def test_an_unexpected_failure_is_a_500_problem_and_logged(self, monkeypatch):
        app = TestApp()
        monkeypatch.setitem(app.app.routes["/api/v1/health"], "GET", lambda request: 1 / 0)
        response = app.get("/api/v1/health")
        assert response.status == 500
        assert problem_of(response)["code"] == "internal_error"
        assert app.logs[-1]["level"] == "error"


class TestCors:
    def test_answers_configured_origins_only(self):
        app = TestApp({"EDITPDF_CORS_ORIGINS": "https://app.example.org"})
        allowed = app.get("/api/v1/info", {"origin": "https://app.example.org"})
        assert allowed.headers.get("access-control-allow-origin") == "https://app.example.org"
        assert "Content-Disposition" in allowed.headers.get("access-control-expose-headers")
        assert (
            app.get("/api/v1/info", {"origin": "https://evil.example"}).headers.get("access-control-allow-origin")
            is None
        )

    def test_answers_the_preflight(self):
        app = TestApp({"EDITPDF_CORS_ORIGINS": "https://app.example.org"})
        response = app.request("OPTIONS", "/api/v1/pdf/merge", headers={"origin": "https://app.example.org"})
        assert response.status == 204
        assert response.headers.get("access-control-allow-methods") == "POST, OPTIONS"


def test_other_methods_than_get_and_head_are_refused_outside_the_api():
    assert TestApp().request("POST", "/").status == 405


def test_the_interface_is_not_served_when_switched_off(tmp_path):
    (tmp_path / "index.html").write_text("<title>editpdf</title>")
    assert TestApp({"EDITPDF_SERVE_UI": "false"}, static_dir=tmp_path).get("/").status == 404

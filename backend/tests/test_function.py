import base64
import io
import json
import zipfile

import pytest

from editpdf import function
from editpdf.function import handler, to_request

from .helpers import make_pdf, multipart, page_widths


@pytest.fixture(autouse=True)
def fresh_app(monkeypatch):
    # Each test reads the environment again.
    monkeypatch.setattr(function, "_app", None)


def decode(result) -> bytes:
    return base64.b64decode(result["body"]) if result["isBase64Encoded"] else result["body"].encode()


def test_payload_2_event_with_a_base64_multipart_body_answers_base64():
    body, content_type = multipart(
        [("files", ("a.pdf", make_pdf(1, width_base=300))), ("files", ("b.pdf", make_pdf(1, width_base=400)))]
    )
    result = handler(
        {
            "version": "2.0",
            "rawPath": "/api/v1/pdf/merge",
            "rawQueryString": "",
            "headers": {"content-type": content_type, "host": "editpdf.coderforge.org"},
            "requestContext": {"http": {"method": "POST"}, "requestId": "req-42"},
            "body": base64.b64encode(body).decode(),
            "isBase64Encoded": True,
        },
        None,
    )
    assert result["statusCode"] == 200
    assert result["isBase64Encoded"] is True
    assert result["headers"]["content-type"] == "application/pdf"
    assert result["headers"]["x-request-id"] == "req-42"
    assert page_widths(decode(result)) == [301, 401]


def test_payload_1_event_answers_json_as_text():
    result = handler(
        {
            "httpMethod": "GET",
            "path": "/api/v1/health",
            "headers": {"Host": "editpdf.coderforge.org"},
            "multiValueHeaders": {"Accept": ["application/json"]},
            "queryStringParameters": None,
            "body": None,
            "isBase64Encoded": False,
        },
        None,
    )
    assert result == {
        "statusCode": 200,
        "headers": result["headers"],
        "body": '{"status":"ok"}',
        "isBase64Encoded": False,
    }


def test_plain_event_with_a_bytes_body():
    body, content_type = multipart([("file", ("a.pdf", make_pdf(4))), ("size", "2")])
    result = handler(
        {"method": "POST", "url": "/api/v1/pdf/split", "headers": {"content-type": content_type}, "body": body}
    )
    assert result["statusCode"] == 200
    with zipfile.ZipFile(io.BytesIO(decode(result))) as archive:
        assert archive.namelist() == ["a-p1-2.pdf", "a-p3-4.pdf"]


def test_event_as_json_text():
    result = handler(json.dumps({"method": "GET", "path": "/api/v1/info"}))
    assert json.loads(result["body"])["service"] == "editpdf"


def test_problems_are_answered_as_text():
    result = handler({"method": "GET", "path": "/api/v1/nope"})
    assert (result["statusCode"], result["isBase64Encoded"]) == (404, False)
    assert json.loads(result["body"])["code"] == "not_found"


def test_bad_base64_is_a_problem_not_a_crash():
    result = handler(
        {
            "method": "POST",
            "path": "/api/v1/pdf/inspect",
            "headers": {"content-type": "multipart/form-data; boundary=x"},
            "body": "%%%",
            "isBase64Encoded": True,
        }
    )
    assert result["statusCode"] == 400


def test_reads_the_environment_given_in_the_context():
    result = handler({"method": "GET", "path": "/api/v1/info"}, {"env": {"EDITPDF_MAX_FILES": "3"}})
    assert json.loads(result["body"])["limits"]["maxFiles"] == 3


def test_rebuilds_the_query_from_single_and_multi_value_parameters():
    request = to_request(
        {
            "httpMethod": "GET",
            "path": "/api/v1/info",
            "multiValueQueryStringParameters": {"a": ["1", "2"]},
            "queryStringParameters": {"a": "2", "b": "3"},
        }
    )
    assert request.query == "a=1&a=2&b=3"


def test_keeps_the_raw_query_string_of_payload_2():
    assert (
        to_request({"rawPath": "/x", "rawQueryString": "q=a%20b", "requestContext": {"http": {"method": "GET"}}}).query
        == "q=a%20b"
    )


def test_joins_repeated_headers_and_passes_cookies():
    request = to_request({"path": "/", "headers": {"accept": ["a", "b"]}, "cookies": ["x=1", "y=2"]})
    assert request.headers.get("accept") == "a, b"
    assert request.headers.get("cookie") == "x=1; y=2"


def test_drops_a_body_on_get():
    assert to_request({"method": "GET", "path": "/", "body": "ignored"}).body == b""


class JsProxyLike:
    """What Pyodide hands a Python function for a JavaScript object."""

    def __init__(self, value):
        self._value = value

    def to_py(self):
        return self._value


def test_takes_events_handed_over_as_javascript_objects():
    result = handler(JsProxyLike({"method": "GET", "path": "/api/v1/health"}), JsProxyLike({"env": {}}))
    assert (result["statusCode"], result["body"]) == (200, '{"status":"ok"}')

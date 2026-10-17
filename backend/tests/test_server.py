import http.client
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from editpdf.app import App
from editpdf.config import config_from_env
from editpdf.server import create_server

from .helpers import make_pdf, multipart, page_rotations


@pytest.fixture
def server():
    app = App(config_from_env({"EDITPDF_MAX_UPLOAD_BYTES": "100000"}), log=lambda entry: None)
    server = create_server(app, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def request(port: int, method: str, path: str, body: bytes = b"", headers: dict | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response, data


def test_a_document_in_and_the_result_out(server):
    body, content_type = multipart([("file", ("a.pdf", make_pdf(2))), ("angle", "90")])
    response, data = request(server, "POST", "/api/v1/pdf/rotate", body, {"content-type": content_type})
    assert response.status == 200
    assert response.getheader("x-page-count") == "2"
    assert page_rotations(data) == [90, 90]


def test_a_declared_body_over_the_limit_is_refused_unread(server):
    connection = http.client.HTTPConnection("127.0.0.1", server, timeout=10)
    connection.putrequest("POST", "/api/v1/pdf/merge")
    connection.putheader("content-type", "multipart/form-data; boundary=x")
    connection.putheader("content-length", "5000000")
    connection.endheaders()
    response = connection.getresponse()
    assert response.status == 413
    assert json.loads(response.read())["code"] == "payload_too_large"
    connection.close()


def test_head_sends_headers_only(server):
    response, data = request(server, "HEAD", "/api/v1/health")
    assert response.status == 200
    assert data == b""


def test_stops_on_sigterm():
    src = Path(__file__).resolve().parents[1] / "src"
    process = subprocess.Popen(
        [sys.executable, "-m", "editpdf.server"],
        env={**os.environ, "PYTHONPATH": str(src), "EDITPDF_PORT": "0"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        assert b"listening" in process.stdout.readline()
        time.sleep(0.2)
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=10) == 0
    finally:
        process.kill()

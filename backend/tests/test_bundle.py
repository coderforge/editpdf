"""The package as the Function deploys it: imported straight from a zip, as a
runtime that does not unpack it would, with its resources and interface read
through importlib."""

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent

PROBE = """
import json, sys
import editpdf, main
assert ".zip" in editpdf.__file__, editpdf.__file__
results = {
    "info": main.function_handler({"method": "GET", "path": "/api/v1/info"}),
    "page": main.function_handler({"method": "GET", "path": "/split"}),
    "openapi": main.function_handler({"method": "GET", "path": "/api/v1/openapi.yaml"}),
}
print(json.dumps({name: {"status": r["statusCode"], "body": r["body"]} for name, r in results.items()}))
"""


def test_runs_from_its_zip(tmp_path):
    package = tmp_path / "function.zip"
    with zipfile.ZipFile(package, "w") as archive:
        for path in (BACKEND / "src" / "editpdf").rglob("*.py"):
            archive.write(path, f"editpdf/{path.relative_to(BACKEND / 'src' / 'editpdf').as_posix()}")
        archive.write(REPOSITORY / "openapi" / "editpdf-v1.yaml", "editpdf/resources/openapi.yaml")
        archive.write(REPOSITORY / "legal" / "VERSION", "editpdf/resources/TERMS_VERSION")
        archive.writestr("editpdf/static/index.html", "<!doctype html><div id=root></div>")
        archive.writestr("main.py", "from editpdf.function import handler as function_handler\n")
    # Away from the repository, so nothing can be found there instead.
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(package)},
        capture_output=True,
        text=True,
        check=True,
    )
    answers = json.loads(result.stdout.strip().splitlines()[-1])
    assert answers["info"]["status"] == 200
    assert (
        json.loads(answers["info"]["body"])["terms"]["version"]
        == (REPOSITORY / "legal" / "VERSION").read_text().strip()
    )
    assert answers["page"] == {"status": 200, "body": "<!doctype html><div id=root></div>"}
    assert answers["openapi"]["body"].startswith("openapi: 3.1.0")

"""The OpenAPI document is the contract: the code must serve exactly what it
promises, and promise nothing it does not serve."""

from pathlib import Path

import yaml

from editpdf.app import App, api_version
from editpdf.config import Config
from editpdf.problems import PROBLEMS

SPEC = yaml.safe_load((Path(__file__).resolve().parents[2] / "openapi" / "editpdf-v1.yaml").read_text(encoding="utf-8"))
METHODS = {"get", "put", "post", "delete", "patch", "head", "options"}


def test_lists_exactly_the_operations_the_code_serves():
    documented = sorted(
        f"{method} {path}" for path, item in SPEC["paths"].items() for method in item if method in METHODS
    )
    served = sorted(f"{operation.method} {operation.path}" for operation in App(Config()).operations())
    assert served == documented


def test_lists_exactly_the_problem_codes_the_code_can_answer():
    assert sorted(PROBLEMS) == sorted(SPEC["components"]["schemas"]["ProblemCode"]["enum"])


def test_versions_every_path_under_api_v1():
    assert all(path.startswith("/api/v1/") for path in SPEC["paths"])
    assert api_version() == SPEC["info"]["version"]
    assert SPEC["info"]["version"].startswith("1.")

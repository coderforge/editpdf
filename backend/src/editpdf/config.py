"""Settings of a deployment, read from the environment the platform hands the
function (Cloud Builder: the function's parameter and secret; locally:
os.environ). Every setting has a default, so an empty environment works."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

DEFAULT_PUBLIC_URL = "https://editpdf.coderforge.org"


@dataclass(frozen=True)
class Limits:
    #: Largest request body accepted, in bytes.
    max_upload_bytes: int = 25 * 1024 * 1024
    #: Most documents one merge accepts.
    max_files: int = 20
    #: Most pages one request processes, all documents together.
    max_pages: int = 2000

    def as_json(self) -> dict[str, int]:
        return {
            "maxUploadBytes": self.max_upload_bytes,
            "maxFiles": self.max_files,
            "maxPages": self.max_pages,
        }


@dataclass(frozen=True)
class Config:
    limits: Limits = field(default_factory=Limits)
    #: Where the service is published; problem types and the terms link are built on it.
    public_url: str = DEFAULT_PUBLIC_URL
    #: Origins allowed to call the API from a browser page of their own (CORS).
    cors_origins: tuple[str, ...] = ()
    #: Whether the web interface is served next to the API.
    serve_ui: bool = True


class ConfigError(ValueError):
    """A setting holds a value the service cannot run with."""


def _positive_integer(env: Mapping[str, str], name: str, fallback: int) -> int:
    raw = (env.get(name) or "").strip()
    if raw == "":
        return fallback
    if not re.fullmatch(r"\d{1,15}", raw) or int(raw) < 1:
        raise ConfigError(f'{name} must be a positive integer, got "{raw}"')
    return int(raw)


def _flag(env: Mapping[str, str], name: str, fallback: bool) -> bool:
    raw = (env.get(name) or "").strip().lower()
    if raw == "":
        return fallback
    if raw in ("true", "1", "yes"):
        return True
    if raw in ("false", "0", "no"):
        return False
    raise ConfigError(f'{name} must be true or false, got "{raw}"')


def _origin(value: str, name: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ConfigError(f'{name} holds "{value}", which is not an absolute http(s) URL')
    return f"{parts.scheme}://{parts.netloc}".lower()


def config_from_env(env: Mapping[str, str]) -> Config:
    public_url = (env.get("EDITPDF_PUBLIC_URL") or "").strip() or DEFAULT_PUBLIC_URL
    cors = tuple(
        _origin(item.strip(), "EDITPDF_CORS_ORIGINS")
        for item in (env.get("EDITPDF_CORS_ORIGINS") or "").split(",")
        if item.strip()
    )
    defaults = Limits()
    return Config(
        limits=Limits(
            max_upload_bytes=_positive_integer(env, "EDITPDF_MAX_UPLOAD_BYTES", defaults.max_upload_bytes),
            max_files=_positive_integer(env, "EDITPDF_MAX_FILES", defaults.max_files),
            max_pages=_positive_integer(env, "EDITPDF_MAX_PAGES", defaults.max_pages),
        ),
        public_url=_origin(public_url, "EDITPDF_PUBLIC_URL"),
        cors_origins=cors,
        serve_ui=_flag(env, "EDITPDF_SERVE_UI", True),
    )

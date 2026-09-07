"""/ds serves the syntax diagram per version and (optional) language."""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main


@pytest.fixture
def static_dir(tmp_path, monkeypatch):
    (tmp_path / "H02DS.png").write_bytes(b"neutral-v1.0")
    (tmp_path / "ds" / "go").mkdir(parents=True)
    (tmp_path / "ds" / "go" / "H06DS.png").write_bytes(b"go-v2.1")
    monkeypatch.setattr(main, "DS_STATIC_DIR", str(tmp_path))
    monkeypatch.setattr(main, "DS_DEFAULT_LANGUAGE", "go")
    return tmp_path


def test_default_language_serves_language_dir(static_dir):
    assert main.ds_image_path("v2.1", None) == str(static_dir / "ds" / "go" / "H06DS.png")


def test_explicit_language_case_insensitive(static_dir):
    assert main.ds_image_path("v2.1", "GO") == str(static_dir / "ds" / "go" / "H06DS.png")


def test_language_agnostic_fallback(static_dir):
    assert main.ds_image_path("v1.0", "c") == str(static_dir / "H02DS.png")


def test_unknown_language_for_version_is_invalid(static_dir):
    assert main.ds_image_path("v2.1", "c") is None


def test_unknown_version_is_invalid(static_dir):
    assert main.ds_image_path("v9.9", None) is None


@pytest.mark.parametrize("language", ["../..", "go/..", "GO!", "a" * 17, ""])
def test_bad_language_never_escapes_static(static_dir, language):
    result = main.ds_image_path("v2.1", language)
    if language == "":
        assert result == str(static_dir / "ds" / "go" / "H06DS.png")
    else:
        assert result is None


def test_endpoint(static_dir):
    client = TestClient(main.app)
    assert client.get("/ds", params={"version": "v2.1"}).content == b"go-v2.1"
    assert client.get("/ds", params={"version": "v2.1", "language": "GO"}).content == b"go-v2.1"
    assert client.get("/ds", params={"version": "v1.0", "language": "c"}).content == b"neutral-v1.0"
    assert client.get("/ds", params={"version": "v2.1", "language": "c"}).status_code == 400
    assert client.get("/ds", params={"version": "v2.1", "language": "../.."}).status_code == 400
    assert client.get("/ds", params={"version": "v9.9"}).status_code == 400
    assert client.get("/ds").status_code == 422

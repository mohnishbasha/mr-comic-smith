"""Server tests for S0-T08: health, static Studio, SPA fallback, security headers, problem+json."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import comic_smith
from comic_smith.config import Settings
from comic_smith.errors import ComicSmithError, ProjectNotFoundError
from comic_smith.server.app import CSP, create_app

INDEX_HTML = '<!doctype html><html><body><div id="root">studio-built</div></body></html>'


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (root / "assets" / "app.js").write_text("const answer = 42;", encoding="utf-8")
    return root


@pytest.fixture
def client(settings: Settings, static_dir: Path) -> TestClient:
    return TestClient(create_app(settings, static_dir=static_dir))


def test_server_healthz_returns_ok(client: TestClient) -> None:
    for path in ("/healthz", "/v1/healthz"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": comic_smith.__version__}


def test_server_readyz_returns_ok(client: TestClient) -> None:
    for path in ("/readyz", "/v1/readyz"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def it_server_serves_built_studio_at_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "studio-built" in response.text


def test_server_serves_static_assets(client: TestClient) -> None:
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "answer" in response.text


def test_server_spa_fallback_serves_index_for_client_routes(client: TestClient) -> None:
    for path in ("/p/demo/strips", "/settings/backends", "/p/x"):
        response = client.get(path)
        assert response.status_code == 200
        assert "studio-built" in response.text


def test_server_missing_asset_is_404_not_index(client: TestClient) -> None:
    response = client.get("/assets/missing.js")
    assert response.status_code == 404
    assert "studio-built" not in response.text


def test_server_spa_fallback_does_not_apply_to_api(client: TestClient) -> None:
    for path in ("/v1/nope", "/v1/projects/abc/other", "/v1"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert "studio-built" not in response.text


def test_server_static_path_traversal_is_not_served(client: TestClient, static_dir: Path) -> None:
    (static_dir.parent / "secret.txt").write_text("top-secret", encoding="utf-8")
    for path in ("/..%2Fsecret.txt", "/%2e%2e/secret.txt", "/../secret.txt"):
        assert "top-secret" not in client.get(path).text


def test_server_placeholder_page_when_studio_not_built(settings: Settings, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    response = TestClient(create_app(settings, static_dir=empty)).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "make studio-build" in response.text


def test_server_default_static_dir_still_answers(settings: Settings) -> None:
    assert TestClient(create_app(settings)).get("/").status_code == 200


def test_server_security_headers_on_every_response(client: TestClient) -> None:
    for path in ("/", "/v1/healthz", "/v1/nope", "/assets/app.js"):
        headers = client.get(path).headers
        assert headers["content-security-policy"] == CSP
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"


def test_server_csp_matches_architecture_11_3() -> None:
    assert CSP == (
        "default-src 'self'; img-src 'self' blob: data:; font-src 'self' data:; "
        "connect-src 'self' ws: wss:; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'none'"
    )


def test_server_comic_smith_error_renders_problem_json(settings: Settings, static_dir: Path) -> None:
    app = create_app(settings, static_dir=static_dir)

    @app.get("/v1/boom-missing")
    def boom_missing() -> None:
        raise ProjectNotFoundError("No such project.", hint="Check the id.")

    @app.get("/v1/boom-internal")
    def boom_internal() -> None:
        raise ComicSmithError("Kaboom")

    local = TestClient(app, raise_server_exceptions=False)
    response = local.get("/v1/boom-missing")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "project_not_found"
    assert body["instance"] == "/v1/boom-missing"
    assert body["hint"] == "Check the id."
    assert response.headers["x-content-type-options"] == "nosniff"
    assert local.get("/v1/boom-internal").status_code == 500

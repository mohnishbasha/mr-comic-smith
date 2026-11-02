"""FastAPI application factory: health probes, security headers, problem+json, and the Studio SPA.

The built Studio lives in `comic_smith/server/static` (filled by `make studio-build`). Client routes
such as `/p/:projectId/strips` fall back to `index.html`; the API prefix `/v1` never does.
"""

from collections.abc import Awaitable, Callable
from html import escape
from pathlib import Path
from typing import Final

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import comic_smith
from comic_smith.config import Settings
from comic_smith.errors import ComicSmithError

DEFAULT_STATIC_DIR: Final = Path(__file__).parent / "static"
API_PREFIX: Final = "v1"
PROBLEM_MEDIA_TYPE: Final = "application/problem+json"

CSP: Final = (
    "default-src 'self'; img-src 'self' blob: data:; font-src 'self' data:; "
    "connect-src 'self' ws: wss:; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS: Final = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

PLACEHOLDER_HTML: Final = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mr-comic-smith Studio</title>
<style>
body { font-family: system-ui, sans-serif; background: #fbf8f3; color: #1f1b16; margin: 0; }
main { max-width: 36rem; margin: 4rem auto; padding: 0 1rem; line-height: 1.5; }
code { background: #f3eee6; padding: 0.1rem 0.4rem; border-radius: 4px; }
</style>
</head>
<body>
<main>
<h1>The Studio has not been built yet</h1>
<p>The server is running, but there are no Studio files to show.</p>
<p>Run <code>make studio-build</code>, then reload this page.</p>
<p>Version {version}</p>
</main>
</body>
</html>
"""


class RouteNotFoundError(ComicSmithError):
    code = "not_found"
    default_stage = "server"
    title = "Not found"
    http_status = 404


def _problem_response(err: ComicSmithError, path: str) -> JSONResponse:
    return JSONResponse(
        err.to_problem(instance=path), status_code=err.http_status, media_type=PROBLEM_MEDIA_TYPE
    )


def _health_body() -> dict[str, str]:
    return {"status": "ok", "version": comic_smith.__version__}


def _resolve_file(root: Path, relative: str) -> Path | None:
    """Return a file under root for a request path, or None. Never escapes root."""
    if not relative:
        return None
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        return None
    return candidate


def create_app(settings: Settings, *, static_dir: Path | None = None) -> FastAPI:
    """Build the app. `static_dir` defaults to the bundled Studio directory."""
    root = static_dir if static_dir is not None else DEFAULT_STATIC_DIR
    app = FastAPI(title="mr-comic-smith", version=comic_smith.__version__, docs_url=None, redoc_url=None)
    app.state.settings = settings

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    @app.exception_handler(ComicSmithError)
    async def comic_smith_error_handler(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ComicSmithError)  # noqa: S101 - narrows the handler's Exception type
        return _problem_response(exc, request.url.path)

    @app.get("/healthz")
    @app.get("/v1/healthz")
    def healthz() -> dict[str, str]:
        return _health_body()

    @app.get("/readyz")
    @app.get("/v1/readyz")
    def readyz() -> dict[str, str]:
        return _health_body()

    def studio_response(path: str) -> Response:
        found = _resolve_file(root, path)
        if found is not None:
            return FileResponse(found)
        if "." in path.rsplit("/", 1)[-1]:
            return Response(status_code=404)  # a missing asset must not turn into index.html
        index = root / "index.html"
        if index.is_file():
            return FileResponse(index, media_type="text/html")
        return HTMLResponse(PLACEHOLDER_HTML.replace("{version}", escape(comic_smith.__version__)))

    # The Studio is the fallback for any unmatched GET, so API routes added later always win.
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - narrows the handler's type
        if exc.status_code != 404:
            return await http_exception_handler(request, exc)
        path = request.url.path.lstrip("/")
        is_api = path == API_PREFIX or path.startswith(API_PREFIX + "/")
        if is_api or request.method not in ("GET", "HEAD"):
            return _problem_response(
                RouteNotFoundError(f"There is nothing at /{path}.", hint="Check the URL."), request.url.path
            )
        return studio_response(path)

    return app

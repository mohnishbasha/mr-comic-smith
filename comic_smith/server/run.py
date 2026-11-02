"""Start the Studio server: guard the bind address, launch uvicorn, optionally open the browser."""

import socket
import threading
import time
import webbrowser
from typing import Final

import uvicorn

from comic_smith.config import Settings
from comic_smith.errors import UsageError
from comic_smith.server.app import create_app

LOCAL_HOSTS: Final = frozenset({"127.0.0.1", "localhost", "::1"})
WILDCARD_HOSTS: Final = {"0.0.0.0": "127.0.0.1", "::": "::1"}  # noqa: S104


def _has_secret(value: object) -> bool:
    getter = getattr(value, "get_secret_value", None)
    return bool(getter()) if callable(getter) else False


def _check_bind(settings: Settings, host: str) -> None:
    if host in LOCAL_HOSTS:
        return
    if _has_secret(settings.server_token) or _has_secret(settings.access_code):
        return
    raise UsageError(
        f"Refusing to listen on {host} without a credential.",
        hint=(
            "Set COMIC_SMITH_SERVER_TOKEN (or pass an access code for LAN mode), or bind to "
            "127.0.0.1 to keep the Studio on this computer."
        ),
    )


def _browser_url(host: str, port: int) -> str:
    target = WILDCARD_HOSTS.get(host, host)
    if ":" in target:
        target = f"[{target}]"
    return f"http://{target}:{port}/"


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    """Poll until something accepts connections on host:port."""
    probe = WILDCARD_HOSTS.get(host, host)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((probe, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _open_when_ready(host: str, port: int) -> None:
    if _wait_for_port(host, port):
        webbrowser.open(_browser_url(host, port))


def run(settings: Settings, *, host: str, port: int, open_browser: bool) -> None:
    """Serve the Studio until interrupted. Non-local binds need a token or access code."""
    _check_bind(settings, host)
    if open_browser:
        threading.Thread(target=_open_when_ready, args=(host, port), daemon=True).start()
    uvicorn.run(create_app(settings), host=host, port=port, log_level=settings.log_level)

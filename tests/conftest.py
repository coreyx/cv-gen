"""Shared fixtures: a local HTTP server, so fetching is tested without the internet."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class _QuietHandler(SimpleHTTPRequestHandler):
    """Serve files without logging every request to the test output."""

    def log_message(self, format: str, *args: object) -> None:
        """Discard request logs."""


@pytest.fixture
def http_root(tmp_path: Path) -> Path:
    """A folder the local server serves; tests drop files into it."""
    root = tmp_path / "www"
    root.mkdir()
    return root


@pytest.fixture
def http_server(http_root: Path) -> Iterator[str]:
    """Serve ``http_root`` on a free loopback port and yield its base URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(http_root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()

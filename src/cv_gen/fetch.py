"""Reading a source from an ``http(s)`` URL or a local file, with clear failures."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from pathlib import Path

from cv_gen import __version__
from cv_gen.errors import CvGenError

DEFAULT_TIMEOUT = 20.0
MAX_BYTES = 5 * 1024 * 1024
DEFAULT_USER_AGENT = f"cv-gen/{__version__} (+https://github.com/coreyx/cv-gen)"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "[::1]")


def is_loopback(url: str) -> bool:
    """Tell whether a URL points at this machine (allowed over plain http)."""
    host = urllib.request.urlparse(url).netloc.rsplit("@", 1)[-1]
    host = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
    return host in LOOPBACK_HOSTS


def fetch_bytes(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str | None = None,
    max_bytes: int = MAX_BYTES,
    https_only: bool = False,
) -> tuple[bytes, str | None]:
    """Download ``url`` and return its body and declared charset.

    Every failure (refused, not found, timed out, too large) becomes a CvGenError that
    names the URL. ``https_only`` refuses plain ``http`` except to loopback addresses.
    """
    scheme = urllib.request.urlparse(url).scheme
    if scheme not in ("http", "https"):
        raise CvGenError(f"unsupported URL scheme in {url}; use http(s) or a file path")
    if https_only and scheme != "https" and not is_loopback(url):
        raise CvGenError(f"refusing to fetch {url} over plain http; use https")
    request = urllib.request.Request(url, headers={"User-Agent": user_agent or DEFAULT_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
            charset = response.headers.get_content_charset()
    except urllib.error.HTTPError as error:
        raise CvGenError(f"fetching {url} failed: HTTP {error.code} {error.reason}") from error
    except urllib.error.URLError as error:
        reason = error.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise CvGenError(f"fetching {url} timed out after {timeout:g}s") from error
        raise CvGenError(
            f"cannot reach {url}: {reason}", "check the URL and your connection"
        ) from error
    except TimeoutError as error:
        raise CvGenError(f"fetching {url} timed out after {timeout:g}s") from error
    if len(body) > max_bytes:
        raise CvGenError(f"{url} is larger than {max_bytes // (1024 * 1024)} MB; refusing it")
    return body, charset


def decode(body: bytes, charset: str | None) -> str:
    """Decode a body with its declared charset, falling back to UTF-8."""
    try:
        return body.decode(charset or "utf-8", errors="replace")
    except LookupError:  # a charset name Python does not know
        return body.decode("utf-8", errors="replace")


def read_text(
    url: str | None = None,
    path: Path | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str | None = None,
) -> str:
    """Read a page from exactly one of ``url`` or ``path``."""
    if path is not None:
        if not path.is_file():
            raise CvGenError(f"no such file: {path}")
        return path.read_text(encoding="utf-8-sig", errors="replace")
    if url is None:
        raise CvGenError("no URL or path to read")
    body, charset = fetch_bytes(url, timeout=timeout, user_agent=user_agent)
    return decode(body, charset)

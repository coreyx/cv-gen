"""Turning the HTML page into a PDF through whichever engine is available.

Three engines, all printing the same HTML the browser shows:

``chrome``
    An installed Chrome, Edge or Chromium, driven headlessly from the command line.
    Needs no Python packages, and Edge ships with Windows.
``playwright``
    Playwright's bundled Chromium (``pip install "cv-gen[playwright]"``, then
    ``playwright install chromium``); the choice for servers without a browser.
``weasyprint``
    WeasyPrint (``pip install "cv-gen[weasyprint]"``); no browser at all, but it
    needs Pango, which on Windows means installing GTK.
"""

from __future__ import annotations

import abc
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import ClassVar

from cv_gen.errors import CvGenError

BROWSER_TIMEOUT = 90


class EngineUnavailable(Exception):
    """The engine cannot run here (not installed, browser missing); try another."""


class PdfEngine(abc.ABC):
    """A way to print HTML to PDF."""

    name: ClassVar[str]
    install_hint: ClassVar[str]

    @abc.abstractmethod
    def available(self) -> bool:
        """Tell, cheaply, whether the engine could run on this machine."""

    @abc.abstractmethod
    def render(self, html_path: Path, pdf_path: Path) -> None:
        """Print the HTML file at ``html_path`` to ``pdf_path``."""


def _browser_candidates() -> list[str]:
    """Return likely Chromium-family executables for this platform, most likely first."""
    names = [
        "chrome",
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "msedge",
        "microsoft-edge",
    ]
    found = [path for name in names if (path := shutil.which(name))]
    if sys.platform == "win32":
        roots = [
            os.environ.get(var) for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
        ]
        for root in filter(None, roots):
            found += [
                str(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"),
                str(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
                str(Path(root) / "Chromium" / "Application" / "chrome.exe"),
            ]
    elif sys.platform == "darwin":
        found += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    return found


class ChromeEngine(PdfEngine):
    """Headless Chrome, Edge or Chromium via ``--print-to-pdf``."""

    name = "chrome"
    install_hint = "install Chrome or Edge, or set CV_GEN_CHROME to a Chromium-family browser"

    def executable(self) -> str | None:
        """Return the browser to run: ``CV_GEN_CHROME``, else the first one found."""
        override = os.environ.get("CV_GEN_CHROME")
        if override:
            return override if Path(override).is_file() else None
        return next((path for path in _browser_candidates() if Path(path).is_file()), None)

    def available(self) -> bool:
        """Tell whether a browser executable was found."""
        return self.executable() is not None

    def render(self, html_path: Path, pdf_path: Path) -> None:
        """Run the browser headlessly with a throwaway profile and wait for the PDF."""
        browser = self.executable()
        if browser is None:
            raise EngineUnavailable("no Chromium-family browser found")
        profile = pdf_path.parent / "browser-profile"
        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            # Both spellings: the flag was renamed in Chrome 120; unknown flags are ignored.
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            # Lets web fonts named by the design system load before printing.
            "--virtual-time-budget=5000",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=BROWSER_TIMEOUT, check=False
            )
        except subprocess.TimeoutExpired as error:
            raise CvGenError(
                f"{browser} did not finish printing within {BROWSER_TIMEOUT}s"
            ) from error
        except OSError as error:
            raise EngineUnavailable(f"cannot run {browser}: {error}") from error
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
            raise CvGenError(
                f"{browser} produced no PDF (exit code {result.returncode})",
                " / ".join(detail) or "run with another engine: --pdf-engine playwright",
            )


class PlaywrightEngine(PdfEngine):
    """Playwright's Chromium."""

    name = "playwright"
    install_hint = 'pip install "cv-gen[playwright]" then run: playwright install chromium'

    def available(self) -> bool:
        """Tell whether the Playwright package is installed (the browser is checked later)."""
        return importlib.util.find_spec("playwright") is not None

    def render(self, html_path: Path, pdf_path: Path) -> None:
        """Print with Playwright, honoring the page's CSS page size and backgrounds."""
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page()
                    page.goto(html_path.as_uri(), wait_until="networkidle")
                    page.pdf(path=str(pdf_path), prefer_css_page_size=True, print_background=True)
                finally:
                    browser.close()
        except PlaywrightError as error:
            # Most often the browser was never downloaded; let auto mode try another engine.
            raise EngineUnavailable(f"playwright could not print: {error}") from error


class WeasyPrintEngine(PdfEngine):
    """WeasyPrint, a pure-Python HTML/CSS renderer."""

    name = "weasyprint"
    install_hint = 'pip install "cv-gen[weasyprint]" (on Windows, also install the GTK runtime)'

    def available(self) -> bool:
        """Tell whether WeasyPrint imports; it raises OSError when Pango is missing."""
        if importlib.util.find_spec("weasyprint") is None:
            return False
        try:
            import weasyprint  # noqa: F401
        except OSError:
            return False
        return True

    def render(self, html_path: Path, pdf_path: Path) -> None:
        """Print with WeasyPrint."""
        import weasyprint

        weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))


ENGINES: dict[str, type[PdfEngine]] = {
    "playwright": PlaywrightEngine,
    "chrome": ChromeEngine,
    "weasyprint": WeasyPrintEngine,
}
AUTO_ORDER = ("playwright", "chrome", "weasyprint")


def _install_hints() -> str:
    """Describe how to make each engine available."""
    return "; ".join(f"{name}: {ENGINES[name].install_hint}" for name in AUTO_ORDER)


def render_pdf(html: str, engine: str = "auto") -> bytes:
    """Print an HTML document to PDF bytes with the named engine, or the first that works."""
    names = AUTO_ORDER if engine == "auto" else (engine,)
    if engine != "auto" and engine not in ENGINES:
        raise CvGenError(f"unknown PDF engine '{engine}'; engines: auto, {', '.join(ENGINES)}")
    reasons = []
    with tempfile.TemporaryDirectory(prefix="cv-gen-pdf-") as folder:
        html_path = Path(folder) / "cv.html"
        html_path.write_text(html, encoding="utf-8")
        for name in names:
            candidate = ENGINES[name]()
            if not candidate.available():
                reasons.append(f"{name} is not installed")
                continue
            pdf_path = Path(folder) / f"cv-{name}.pdf"
            try:
                candidate.render(html_path, pdf_path)
            except EngineUnavailable as error:
                reasons.append(str(error))
                continue
            return pdf_path.read_bytes()
    what = (
        "no PDF engine is available"
        if engine == "auto"
        else f"PDF engine '{engine}' is not available"
    )
    raise CvGenError(f"{what} ({'; '.join(reasons)})", _install_hints())

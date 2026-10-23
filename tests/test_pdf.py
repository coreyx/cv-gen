"""Tests for the PDF engines and generator (REQ-8)."""

import io
import subprocess
from pathlib import Path

import pytest
from pypdf import PdfReader

from cv_gen.errors import CvGenError
from cv_gen.generators import RenderRequest, get_generator
from cv_gen.model import Resume
from cv_gen.pdf import engines
from cv_gen.pdf.engines import ChromeEngine, PlaywrightEngine, WeasyPrintEngine, render_pdf

ROOT = Path(__file__).parent.parent
SAMPLE = Resume.load(ROOT / "examples" / "sample-resume.yaml")
HAS_BROWSER = ChromeEngine().available()


@pytest.mark.browser
@pytest.mark.skipif(not HAS_BROWSER, reason="no Chromium-family browser installed")
def test_chrome_renders_a_readable_pdf() -> None:
    """AC 8.1: the PDF's text contains the name and every work organization."""
    content = get_generator("pdf").render(SAMPLE, RenderRequest(pdf_engine="chrome"))
    assert content.startswith(b"%PDF")
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)
    assert "Alex Rivera" in text
    for job in SAMPLE.work:
        assert job.name in text


def test_no_engine_explains_how_to_get_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 8.2 (engine half): with nothing available, the error names every engine's fix."""
    for cls in engines.ENGINES.values():
        monkeypatch.setattr(cls, "available", lambda self: False)
    with pytest.raises(CvGenError) as caught:
        render_pdf("<p>x</p>")
    assert "no PDF engine is available" in caught.value.message
    hint = caught.value.hint or ""
    assert "playwright install chromium" in hint
    assert "CV_GEN_CHROME" in hint
    assert "cv-gen[weasyprint]" in hint
    with pytest.raises(CvGenError, match="PDF engine 'chrome' is not available"):
        render_pdf("<p>x</p>", "chrome")


def test_auto_falls_through_unusable_engines(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto mode skips an engine that turns out to be unusable and uses the next."""

    def broken(self, html_path, pdf_path):
        raise engines.EngineUnavailable("browser not downloaded")

    def working(self, html_path, pdf_path):
        pdf_path.write_bytes(b"%PDF-fake")

    monkeypatch.setattr(PlaywrightEngine, "available", lambda self: True)
    monkeypatch.setattr(PlaywrightEngine, "render", broken)
    monkeypatch.setattr(ChromeEngine, "available", lambda self: True)
    monkeypatch.setattr(ChromeEngine, "render", working)
    assert render_pdf("<p>x</p>") == b"%PDF-fake"


def test_unknown_engine() -> None:
    """An unknown engine name lists the real ones."""
    with pytest.raises(CvGenError, match="unknown PDF engine 'prince'"):
        render_pdf("<p>x</p>", "prince")


def test_chrome_override_and_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CV_GEN_CHROME picks the browser; a browser that prints nothing is an error."""
    fake = tmp_path / "browser.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setenv("CV_GEN_CHROME", str(fake))
    assert ChromeEngine().executable() == str(fake)
    seen = {}

    def no_output(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 1, "", "line1\nGPU process exited\n")

    monkeypatch.setattr(subprocess, "run", no_output)
    html = tmp_path / "cv.html"
    html.write_text("<p>x</p>", encoding="utf-8")
    with pytest.raises(CvGenError, match="produced no PDF") as caught:
        ChromeEngine().render(html, tmp_path / "out.pdf")
    assert "GPU process exited" in (caught.value.hint or "")
    assert any(arg.startswith("--print-to-pdf=") for arg in seen["command"])

    def slow(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 90)

    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(CvGenError, match="did not finish printing"):
        ChromeEngine().render(html, tmp_path / "out.pdf")

    def missing(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(engines.EngineUnavailable):
        ChromeEngine().render(html, tmp_path / "out.pdf")

    monkeypatch.setenv("CV_GEN_CHROME", str(tmp_path / "nope.exe"))
    assert ChromeEngine().executable() is None
    with pytest.raises(engines.EngineUnavailable):
        ChromeEngine().render(html, tmp_path / "out.pdf")


def test_browser_discovery_lists_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discovery checks PATH names and the platform's usual install folders."""
    monkeypatch.delenv("CV_GEN_CHROME", raising=False)
    monkeypatch.setattr(engines.shutil, "which", lambda name: None)
    for platform in ("win32", "darwin", "linux"):
        monkeypatch.setattr(engines.sys, "platform", platform)
        candidates = engines._browser_candidates()
        if platform == "darwin":
            assert any("Google Chrome.app" in c for c in candidates)
        if platform == "linux":
            assert candidates == []


def test_optional_engines_report_absence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Playwright and WeasyPrint report unavailable when not installed."""
    monkeypatch.setattr(engines.importlib.util, "find_spec", lambda name: None)
    assert PlaywrightEngine().available() is False
    assert WeasyPrintEngine().available() is False

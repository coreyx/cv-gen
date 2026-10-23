"""Tests for rendering, guarding and writing outputs (REQ-8, REQ-14)."""

from pathlib import Path

import pytest

from cv_gen.config import RenderOptions
from cv_gen.errors import CvGenError
from cv_gen.generators import RenderRequest
from cv_gen.guard import find_terms, violations
from cv_gen.model import Resume
from cv_gen.pdf import engines
from cv_gen.pipeline import build, render

ROOT = Path(__file__).parent.parent
SAMPLE = Resume.load(ROOT / "examples" / "sample-resume.yaml")
TEXT_FORMATS = ["md", "txt", "docx", "json", "html"]


def with_acme() -> Resume:
    """The sample with an employer named Acme."""
    resume = SAMPLE.model_copy(deep=True)
    resume.work[1].name = "Acme Payments"
    return resume


def test_forbidden_term_writes_nothing(tmp_path: Path) -> None:
    """AC 14.1: a forbidden term fails the build, naming it, and writes no files."""
    out = tmp_path / "out"
    with pytest.raises(CvGenError) as caught:
        build(with_acme(), TEXT_FORMATS, RenderRequest(), out, forbidden_terms=["acme"])
    assert "acme" in caught.value.message
    for fmt in TEXT_FORMATS:
        assert f"{fmt}:" in caught.value.message
    assert not out.exists()


def test_guard_checks_docx_alone_and_pdf_through_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Word is read back, and a PDF is checked through the page it is printed from."""
    with pytest.raises(CvGenError, match=r"(?i)docx: acme"):
        build(with_acme(), ["docx"], RenderRequest(), tmp_path, forbidden_terms=["ACME"])
    monkeypatch.setattr("cv_gen.generators.pdf.render_pdf", lambda html, engine: b"%PDF-x")
    with pytest.raises(CvGenError, match=r"pdf: acme"):
        build(with_acme(), ["pdf"], RenderRequest(), tmp_path, forbidden_terms=["acme"])


def test_pdf_failure_still_writes_the_rest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 8.2 (build half): no PDF engine fails PDF only; the other formats are written."""
    for cls in engines.ENGINES.values():
        monkeypatch.setattr(cls, "available", lambda self: False)
    result = build(SAMPLE, ["md", "pdf", "txt"], RenderRequest(), tmp_path, basename="cv")
    assert [p.name for p in result.written] == ["cv.md", "cv.txt"]
    assert [f.format for f in result.failures] == ["pdf"]
    assert "no PDF engine" in result.failures[0].error.message


def test_formats_are_deduplicated_and_named(tmp_path: Path) -> None:
    """Aliases collapse to one output; file names come from the person's name."""
    result = build(SAMPLE, ["markdown", "md", "json"], RenderRequest(), tmp_path)
    assert [p.name for p in result.written] == ["alex-rivera-cv.md", "alex-rivera-cv.json"]


def test_bad_sections_fail_once_before_rendering() -> None:
    """Unknown render sections are reported before any format renders."""
    request = RenderRequest(options=RenderOptions(sections=["nope"]))
    with pytest.raises(CvGenError, match="unknown section id"):
        render(SAMPLE, TEXT_FORMATS, request, "cv")


def test_guard_matching_rules() -> None:
    """Terms match whole words, case-insensitively; blanks are ignored."""
    assert find_terms("Acme's tools", ["acme", " "]) == ["acme"]
    assert find_terms("Acmeville", ["acme"]) == []
    assert find_terms("ship by launch day", ["launch day"]) == ["launch day"]
    assert violations({"md": "clean", "txt": "ACME"}, ["acme"]) == {"txt": ["acme"]}

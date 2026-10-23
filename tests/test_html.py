"""Tests for the HTML generator (REQ-7)."""

import json
import re
from pathlib import Path

from cv_gen.config import RenderOptions
from cv_gen.design import load_design
from cv_gen.generators import RenderRequest
from cv_gen.generators.html import jsonld_script, person_jsonld, render_html, safe_url
from cv_gen.model import Resume

ROOT = Path(__file__).parent.parent
SAMPLE = Resume.load(ROOT / "examples" / "sample-resume.yaml")


def jsonld_blocks(html: str) -> list[str]:
    """Return the bodies of the page's JSON-LD script elements."""
    return re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)


def test_source_text_is_escaped() -> None:
    """AC 7.1: markup in source text is escaped; the only script is the JSON-LD block."""
    hostile = SAMPLE.model_copy(deep=True)
    hostile.basics.summary = "<script>alert(1)</script> & more"
    hostile.basics.name = "Alex </script><script>alert(2)</script>"
    hostile.work[0].url = "javascript:alert(3)"
    html = render_html(hostile, RenderRequest())
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in html
    assert html.count("<script") == 1
    assert "javascript:" not in html
    block = jsonld_blocks(html)[0]
    assert "</script" not in block
    assert json.loads(block)["name"] == hostile.basics.name


def test_jsonld_describes_the_person() -> None:
    """AC 7.2: the JSON-LD parses and names the person."""
    html = render_html(SAMPLE, RenderRequest())
    data = json.loads(jsonld_blocks(html)[0])
    assert data["@type"] == "Person"
    assert data["name"] == SAMPLE.basics.name
    assert data["jobTitle"] == "Senior Backend Engineer"
    assert data["address"]["addressLocality"] == "Montréal"
    assert "https://github.com/alexrivera-example" in data["sameAs"]
    assert data["worksFor"] == [{"@type": "Organization", "name": "Northwind Freight"}]
    assert "Kafka" in data["knowsAbout"]


def test_template_override_falls_back(tmp_path: Path) -> None:
    """AC 7.3: overriding only base.html.j2 still renders the built-in partials."""
    (tmp_path / "base.html.j2").write_text(
        '<!doctype html><html lang="fr"><body><p id=custom>{{ head.name }}</p>'
        "{% for section in sections %}{% include 'section.html.j2' %}{% endfor %}</body></html>",
        encoding="utf-8",
    )
    html = render_html(SAMPLE, RenderRequest(options=RenderOptions(templates=tmp_path)))
    assert "<p id=custom>Alex Rivera</p>" in html
    assert '<section class="cv-section cv-section--entries" id="work">' in html


def test_page_structure_and_theme(tmp_path: Path) -> None:
    """The page has a language, one h1, h2 per section, and the theme's CSS unescaped."""
    tokens = tmp_path / "t.json"
    tokens.write_text(
        json.dumps(
            {
                "color": {"accent": {"$type": "color", "$value": "#ff2bd6"}},
                "page": {"size": {"$value": "A4"}},
            }
        ),
        encoding="utf-8",
    )
    html = render_html(SAMPLE, RenderRequest(theme=load_design(str(tokens))))
    assert '<html lang="en">' in html
    assert html.count("<h1") == 1
    assert html.count('<h2 class="cv-section__title">') == 7
    assert "--cv-color-accent: #ff2bd6;" in html
    assert '--cv-font-body: "Calibri"' in html, "CSS inside <style> must not be HTML-escaped"
    assert "@page { size: A4; margin: 0.6in; background: #ffffff; }" in html
    assert '<a href="mailto:alex.rivera@example.com">' in html
    assert "<dt>Languages</dt>" in html


def test_custom_css_and_font_imports(tmp_path: Path) -> None:
    """A local design system's custom CSS and font imports reach the page."""
    (tmp_path / "x.css").write_text(".cv-name { letter-spacing: 2px; }", encoding="utf-8")
    url = "https://fonts.googleapis.com/css2?family=Chivo&display=swap"
    tokens = tmp_path / "t.json"
    tokens.write_text(
        json.dumps({"$extensions": {"com.cv-gen": {"customCss": "x.css", "fontImports": [url]}}}),
        encoding="utf-8",
    )
    html = render_html(SAMPLE, RenderRequest(theme=load_design(str(tokens))))
    assert ".cv-name { letter-spacing: 2px; }" in html
    assert (
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo&amp;display=swap">'
        in html
    )


def test_every_layout_renders() -> None:
    """The JSON Resume sample renders every built-in section."""
    sample = Resume.load(ROOT / "tests" / "fixtures" / "jsonresume-sample.json")
    html = render_html(sample, RenderRequest())
    assert html.count('<h2 class="cv-section__title">') == 12
    assert "Erlich Bachman" in html and "<dt>Wildlife</dt>" in html


def test_safe_url_and_jsonld_helpers() -> None:
    """Only safe schemes are linked; JSON-LD escaping covers <, > and &."""
    assert safe_url(" https://a.example ") == "https://a.example"
    assert safe_url("JAVASCRIPT:alert(1)") is None
    assert safe_url(None) is None
    escaped = str(jsonld_script({"a": "<&>"}))
    assert not set("<&>") & set(escaped)
    assert json.loads(escaped) == {"a": "<&>"}
    assert person_jsonld(Resume()) == {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": None,
    }

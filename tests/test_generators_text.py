"""Tests for the section view and the Markdown, text and JSON generators (REQ-6)."""

import json
import re
from pathlib import Path

import jsonschema
import pytest

from cv_gen.config import RenderOptions
from cv_gen.errors import CvGenError
from cv_gen.generators import RenderRequest, canonical_format, get_generator, view
from cv_gen.generators.markdown import escape, render_markdown
from cv_gen.generators.text import render_text
from cv_gen.model import Resume, json_schema

ROOT = Path(__file__).parent.parent
SAMPLE = Resume.load(ROOT / "examples" / "sample-resume.yaml")


def request(**options) -> RenderRequest:
    """A render request with the given render options."""
    return RenderRequest(options=RenderOptions(**options))


def test_markdown_structure() -> None:
    """AC 6.1: one # heading, ## sections, ### entries, and every job's essentials."""
    text = render_markdown(SAMPLE, request())
    lines = text.splitlines()
    assert [line for line in lines if line.startswith("# ")] == ["# Alex Rivera"]
    sections = [line for line in lines if line.startswith("## ")]
    assert sections == [
        "## Summary",
        "## Experience",
        "## Projects",
        "## Skills",
        "## Education",
        "## Languages",
        "## Talks",
    ]
    for job in SAMPLE.work:
        assert f"### {job.name}" in lines
        assert job.summary in text
    assert "**Senior Backend Engineer** · Mar 2021 – Present · Montréal" in text
    assert "Jun 2016 – Feb 2021" in text
    assert "2013 – 2014, 2015 – 2016" in text
    assert "- **Languages:** Go, Python, SQL, TypeScript" in text
    assert "GitHub: [alexrivera\\-example](https://github.com/alexrivera-example)" not in text
    assert "GitHub: [alexrivera-example](https://github.com/alexrivera-example)" in text
    assert "- **Boring queues**, GopherCon Canada (May 2024) — Why the simplest" in text
    assert "- **English** — Native" in text


def test_text_width_is_respected() -> None:
    """AC 6.3: no line exceeds the width unless it is a single unbreakable token."""
    for width in (40, 80):
        output = render_text(SAMPLE, request(text_width=width))
        for line in output.splitlines():
            if len(line) > width:
                token = line.strip().removeprefix("- ")
                assert " " not in token, f"over-long line at width {width}: {line!r}"


def test_text_layout() -> None:
    """Headings are upper case and underlined; entries carry their meta and bullets."""
    output = render_text(SAMPLE, request())
    assert output.startswith("ALEX RIVERA\n===========\nSenior Backend Engineer\n")
    assert "EXPERIENCE\n==========\n" in output
    assert "Senior Backend Engineer | Mar 2021 – Present | Montréal" in output
    assert "  - Cut p99 latency" in output
    assert "Email: alex.rivera@example.com" in output
    assert "GitHub: https://github.com/alexrivera-example" in output
    assert "Languages: Go, Python, SQL, TypeScript" in output
    assert "Website: https://alexrivera.example.com" in output
    assert "- French — Professional" in output
    assert "\n\n\n" not in output


def test_json_validates_against_schema() -> None:
    """AC 6.4: the JSON output validates against the model's JSON Schema."""
    data = json.loads(get_generator("json").render(SAMPLE, request()))
    jsonschema.validate(data, json_schema())
    assert Resume.from_data(data) == SAMPLE


def test_section_selection_and_order() -> None:
    """AC 6.5: render sections [skills, work] give Skills then Experience and nothing else."""
    for render in (render_markdown, render_text):
        output = render(SAMPLE, request(sections=["skills", "work"]))
        names = "skills|experience|summary|projects|education|languages|talks"
        headings = re.findall(rf"^(?:## )?({names})$", output, re.MULTILINE | re.IGNORECASE)
        assert [h.lower() for h in headings] == ["skills", "experience"]


def test_empty_sections_are_omitted() -> None:
    """AC 6.6: a model with no education has no Education heading."""
    resume = SAMPLE.model_copy(update={"education": []})
    assert "## Education" not in render_markdown(resume, request())
    assert "EDUCATION" not in render_text(resume, request())


def test_section_titles_and_unknown_ids() -> None:
    """Titles can be renamed; unknown section ids list what is available."""
    output = render_markdown(SAMPLE, request(section_titles={"work": "Work history"}))
    assert "## Work history" in output
    with pytest.raises(CvGenError, match="unknown section id") as caught:
        view.sections(SAMPLE, RenderOptions(sections=["work", "hobbies"]))
    assert "talks" in (caught.value.hint or "")


def test_markdown_escaping() -> None:
    """Source text never turns into Markdown formatting."""
    assert escape("*bold* _x_ [a](b) <i> `c`") == r"\*bold\* \_x\_ \[a\](b) \<i\> \`c\`"
    assert escape("# not a heading") == r"\# not a heading"
    assert escape("1. not a list") == r"1\. not a list"


def test_dates_and_helpers() -> None:
    """Dates read naturally, and file names come from the person's name."""
    assert view.format_date("2021-04-15") == "Apr 2021"
    assert view.format_date(None) is None
    assert view.format_period("2022", "2022") == "2022"
    assert view.format_period(None, "2020") == "2020"
    assert view.format_period("2020", None) == "2020 – Present"
    assert view.basename_for(SAMPLE) == "alex-rivera-cv"
    assert view.basename_for(SAMPLE, "cv") == "cv"
    assert view.basename_for(Resume()) == "resume"


def test_every_builtin_section_renders() -> None:
    """The JSON Resume sample exercises every built-in section in every text format."""
    sample = Resume.load(ROOT / "tests" / "fixtures" / "jsonresume-sample.json")
    titles = [s.title for s in view.sections(sample)]
    assert titles == [
        "Summary",
        "Experience",
        "Projects",
        "Skills",
        "Education",
        "Certifications",
        "Awards",
        "Publications",
        "Volunteering",
        "Languages",
        "Interests",
        "References",
    ]
    markdown = render_markdown(sample, request())
    text = render_text(sample, request())
    for expected in ("Bachelor, Information Technology", "Techcrunch", "Erlich Bachman", "CNCF"):
        assert expected in markdown and expected in text
    assert "**Wildlife:** Ferrets, Unicorns" in markdown


def test_format_aliases() -> None:
    """Formats accept friendly aliases; unknown formats list the real ones."""
    assert canonical_format("Markdown") == "md"
    assert canonical_format("word") == "docx"
    with pytest.raises(CvGenError, match="unknown format 'rtf'"):
        canonical_format("rtf")


def test_minimal_resume_renders() -> None:
    """A resume with only a name still renders in every text format."""
    tiny = Resume.from_data({"basics": {"name": "Solo"}})
    assert render_markdown(tiny, request()) == "# Solo\n"
    assert render_text(tiny, request()) == "SOLO\n====\n"


def test_untitled_list_item_links_its_text() -> None:
    """A list item with a link but no title turns its text into the link."""
    resume = Resume.from_data(
        {
            "basics": {"name": "A"},
            "sections": [
                {
                    "id": "now",
                    "title": "Now",
                    "items": [
                        {"text": "Available for work.", "url": "https://a.example/contact"},
                        {"url": "https://a.example/only-a-link"},
                    ],
                }
            ],
        }
    )
    output = render_markdown(resume, request())
    assert "- [Available for work.](https://a.example/contact)" in output
    assert "- [https://a.example/only-a-link](https://a.example/only-a-link)" in output
    from cv_gen.generators.html import render_html

    html = render_html(resume, request())
    assert '<a href="https://a.example/contact">Available for work.</a>' in html
    assert '<a href="https://a.example/only-a-link">https://a.example/only-a-link</a>' in html

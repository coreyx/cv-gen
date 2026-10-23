"""Tests for the standard resume model (REQ-1)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cv_gen.errors import CvGenError, from_validation, validation_lines
from cv_gen.model import Resume, json_schema, prune, read_document

FIXTURES = Path(__file__).parent / "fixtures"


def _strip_empty(value):
    """Mirror the model's pruning so a fixture compares with its round trip."""
    return prune(value)


def test_json_resume_sample_loads_without_loss() -> None:
    """AC 1.1: every standard field of the JSON Resume sample survives load and dump."""
    original = json.loads((FIXTURES / "jsonresume-sample.json").read_text(encoding="utf-8"))
    resume = Resume.from_data(original)
    assert resume.to_data() == _strip_empty(original)
    assert resume.basics.name == "Richard Hendriks"
    assert resume.work[0].highlights[1] == "Successfully won Techcrunch Disrupt"


def test_extensions_round_trip() -> None:
    """AC 1.4: headline, periods, tags and custom sections round-trip unchanged."""
    data = {
        "basics": {"name": "A", "headline": "I build things."},
        "work": [
            {
                "name": "Intel",
                "startDate": "2006",
                "endDate": "2013",
                "periods": [
                    {"startDate": "2006", "endDate": "2007"},
                    {"startDate": "2010", "endDate": "2013"},
                ],
                "tags": ["studio"],
            }
        ],
        "sections": [
            {
                "id": "current",
                "title": "Current",
                "updated": "2026-09-29",
                "paragraphs": ["One."],
                "items": [{"title": "X", "text": "Y", "url": "https://example.com"}],
            }
        ],
    }
    again = Resume.from_data(json.loads(Resume.from_data(data).to_json()))
    assert again.to_data() == data


def test_unknown_keys_are_kept() -> None:
    """Data written by other JSON Resume tools is preserved."""
    resume = Resume.from_data({"basics": {"name": "A", "x-pronouns": "they/them"}, "custom": 1})
    assert resume.to_data() == {"basics": {"name": "A", "x-pronouns": "they/them"}, "custom": 1}


def test_bad_month_names_the_field() -> None:
    """AC 1.3: an impossible month fails validation naming work[0].startDate."""
    with pytest.raises(ValidationError) as caught:
        Resume.from_data({"work": [{"name": "X", "startDate": "2021-13"}]})
    lines = validation_lines(caught.value)
    assert lines == ["work[0].startDate: '2021-13' is not in the expected format"]


def test_from_validation_wraps_lines() -> None:
    """The wrapped error names what was being validated and every problem."""
    with pytest.raises(ValidationError) as caught:
        Resume.from_data({"work": [{"startDate": "x"}], "education": [{"endDate": "y"}]})
    error = from_validation(caught.value, "resume.json", "fix the dates")
    assert isinstance(error, CvGenError)
    assert "resume.json is not valid" in error.message
    assert "work[0].startDate" in error.message and "education[0].endDate" in error.message
    assert str(error).endswith("hint: fix the dates")


@pytest.mark.parametrize("good", ["2021", "2021-04", "2021-04-30"])
def test_partial_dates_accepted(good: str) -> None:
    """Year, year-month and full dates are all valid."""
    assert Resume.from_data({"awards": [{"date": good}]}).awards[0].date == good


def test_section_ids_are_unique_and_not_builtin() -> None:
    """Custom section ids must be unique and must not shadow a built-in section."""
    with pytest.raises(ValidationError, match="duplicate section id"):
        Resume.from_data({"sections": [{"id": "a", "title": "A"}, {"id": "a", "title": "B"}]})
    with pytest.raises(ValidationError, match="built-in section id"):
        Resume.from_data({"sections": [{"id": "work", "title": "Work"}]})


def test_schema_describes_the_model() -> None:
    """The JSON Schema names the top-level sections and the $schema alias."""
    schema = json_schema()
    assert {"basics", "work", "sections", "$schema"} <= set(schema["properties"])


def test_read_document_yaml_and_errors(tmp_path: Path) -> None:
    """YAML documents load; empty documents are empty; lists at the top are refused."""
    good = tmp_path / "cv.yaml"
    good.write_text("basics:\n  name: Ada\n", encoding="utf-8")
    assert Resume.load(good).basics.name == "Ada"
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    assert read_document(empty) == {}
    bad = tmp_path / "bad.yaml"
    bad.write_text("- 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        read_document(bad)


def test_error_without_hint_prints_message_only() -> None:
    """A CvGenError without a hint is just its message."""
    assert str(CvGenError("nope")) == "nope"

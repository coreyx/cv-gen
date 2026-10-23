"""Tests for the web engine's transforms and date parsing (REQ-4)."""

import sys
from pathlib import Path

import pytest

from cv_gen.adapters.web import transforms
from cv_gen.adapters.web.dates import parse_date_range, to_iso
from cv_gen.adapters.web.transforms import TransformContext, apply
from cv_gen.errors import CvGenError

CTX = TransformContext(base_url="https://example.com/about/", field="work[0].name")
PLUGINS = Path(__file__).parent / "plugins"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "2006–2007, 2010–2013",
            {
                "startDate": "2006",
                "endDate": "2013",
                "periods": [
                    {"startDate": "2006", "endDate": "2007"},
                    {"startDate": "2010", "endDate": "2013"},
                ],
            },
        ),
        ("2024–", {"startDate": "2024"}),
        ("2022", {"startDate": "2022", "endDate": "2022"}),
        ("2013 - 2019", {"startDate": "2013", "endDate": "2019"}),
        ("2013—2019", {"startDate": "2013", "endDate": "2019"}),
        ("Jan 2020 to Present", {"startDate": "2020-01"}),
        ("Sept. 2019 – March 2021", {"startDate": "2019-09", "endDate": "2021-03"}),
        ("4/2018 - 12/2019", {"startDate": "2018-04", "endDate": "2019-12"}),
        ("2010-12 – 2011-02-03", {"startDate": "2010-12", "endDate": "2011-02-03"}),
        (
            "2001-2003; 2005-now",
            {
                "startDate": "2001",
                "periods": [{"startDate": "2001", "endDate": "2003"}, {"startDate": "2005"}],
            },
        ),
    ],
)
def test_date_ranges(text: str, expected: dict) -> None:
    """AC 4.2: periods, open ranges and dash variants parse to ISO partial dates."""
    assert parse_date_range(text) == expected


@pytest.mark.parametrize("bad", ["", "soon", "2020 – later", "Smarch 2020"])
def test_unreadable_dates(bad: str) -> None:
    """Text that is not a date range is an error, not a guess."""
    with pytest.raises(ValueError):
        parse_date_range(bad)


def test_to_iso_rejects_garbage() -> None:
    """A lone non-date is reported."""
    with pytest.raises(ValueError, match="cannot read"):
        to_iso("yesterday")


@pytest.mark.parametrize(
    ("spec", "value", "expected"),
    [
        ("normalize", "  a \n  b ", "a b"),
        ("normalize", [" a ", "b  c"], ["a", "b c"]),
        ("lower", "AbC", "abc"),
        ("upper", "abc", "ABC"),
        ({"replace": {"old": "&", "new": "and"}}, "R&D", "RandD"),
        ({"strip_prefix": "@"}, "@corey", "corey"),
        ({"strip_prefix": "@"}, "corey", "corey"),
        ({"strip_suffix": " →"}, "Read →", "Read"),
        ({"regex": {"pattern": r"(\d{4})"}}, "since 2009!", "2009"),
        ({"regex": r"(\d{4})"}, "never", None),
        ({"split": {"sep": "·"}}, "A · B ·  ", ["A", "B"]),
        ("split", ["already"], ["already"]),
        ({"join": ", "}, ["a", "b"], "a, b"),
        ("join", "x", "x"),
        ("as_list", "founder", ["founder"]),
        ("as_list", ["a"], ["a"]),
        ("as_list", None, None),
        ("first", ["a", "b"], "a"),
        ({"map": {"mapping": {"a": "Agency"}}}, "a", "Agency"),
        ({"map": {"mapping": {"a": "Agency"}}}, "z", "z"),
        ({"map": {"mapping": {"a": "Agency"}, "default": None}}, "z", None),
        ("absolute_url", "/blog/x", "https://example.com/blog/x"),
        ("date_range", "2021–", {"startDate": "2021"}),
        ("date_range", None, None),
        (
            "lead_sentence",
            "Founder. Game studio, Paydirt.",
            {"position": "Founder", "summary": "Game studio, Paydirt."},
        ),
        (
            "lead_sentence",
            "Core tech, systems, graphics and optimization on two games.",
            {"summary": "Core tech, systems, graphics and optimization on two games."},
        ),
        (
            {"lead_sentence": {"max_words": 1}},
            "Head of Core Tech. Sensorium Galaxy.",
            {"summary": "Head of Core Tech. Sensorium Galaxy."},
        ),
        (
            {"lead_sentence": {"lead": "title", "rest": "text"}},
            "QA Analyst. Hunted for bugs.",
            {"title": "QA Analyst", "text": "Hunted for bugs."},
        ),
    ],
)
def test_builtin_transforms(spec, value, expected) -> None:
    """Every built-in transform does what its documentation says."""
    assert apply(spec, value, CTX) == expected


def test_absolute_url_without_base_keeps_value() -> None:
    """A local file has no base URL, so links stay as written."""
    assert apply("absolute_url", "/x", TransformContext()) == "/x"


def test_unknown_and_malformed_transforms() -> None:
    """Unknown names list the known ones; malformed specs and failures name the field."""
    with pytest.raises(CvGenError, match="unknown transform 'nope'") as caught:
        apply("nope", "x", CTX)
    assert "normalize" in (caught.value.hint or "")
    with pytest.raises(CvGenError, match="one-key mapping"):
        apply({"a": 1, "b": 2}, "x", CTX)
    with pytest.raises(CvGenError, match=r"work\[0\]\.name: transform 'date_range' failed"):
        apply("date_range", "whenever", CTX)


def test_module_registered_transform(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 4.5: a transforms module registers transforms profiles can name."""
    monkeypatch.setattr(sys, "path", [str(PLUGINS), *sys.path])
    transforms.register_module("sample_transforms")
    assert "shout" in transforms.names()
    assert apply({"shout": {"mark": "?"}}, "hi", CTX) == "HI?"
    assert apply({"shout": ["!!"]}, "hi", CTX) == "HI!!"


def test_missing_transforms_module() -> None:
    """A transforms module that cannot be imported says how to fix it."""
    with pytest.raises(CvGenError, match="cannot import transforms module"):
        transforms.register_module("no_such_transforms_xyz")

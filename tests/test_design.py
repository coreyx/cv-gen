"""Tests for DTCG token loading and theme validation (REQ-9)."""

import hashlib
import json
from pathlib import Path

import pytest

from cv_gen.design import SEMANTIC_TOKENS, default_theme, load_design
from cv_gen.design.theme import (
    font_family_css,
    parse_color,
    parse_dimension,
    parse_font_family,
    parse_font_weight,
    parse_number,
    parse_page_size,
)
from cv_gen.design.tokens import flatten, load_document, resolve_aliases
from cv_gen.errors import CvGenError


def write_tokens(folder: Path, data: dict, name: str = "tokens.json") -> Path:
    """Write a tokens document and return its path."""
    path = folder / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_accent_becomes_css_variable(tmp_path: Path) -> None:
    """AC 9.1: color.accent #ff2bd6 is emitted as --cv-color-accent."""
    path = write_tokens(tmp_path, {"color": {"accent": {"$type": "color", "$value": "#FF2BD6"}}})
    theme = load_design(str(path))
    assert "--cv-color-accent: #ff2bd6;" in theme.css_variables()
    # The default link color aliases the accent, so it follows the override.
    assert theme.value("color.link") == "#ff2bd6"
    assert theme.supplied == ["color.accent"]


def test_aliases_resolve_and_cycles_fail(tmp_path: Path) -> None:
    """AC 9.2: aliases resolve; a circular alias fails naming the token."""
    data = {
        "color": {
            "$type": "color",
            "brand": {"$value": "#123456"},
            "accent": {"$value": "{color.brand}"},
            "heading": {"$value": "{color.accent}"},
        }
    }
    theme = load_design(str(write_tokens(tmp_path, data)))
    assert theme.value("color.accent") == "#123456"
    assert theme.value("color.heading") == "#123456"
    assert "color.brand" in theme.ignored
    looped = {"color": {"accent": {"$value": "{color.text}"}, "text": {"$value": "{color.accent}"}}}
    with pytest.raises(CvGenError, match="circular alias"):
        load_design(str(write_tokens(tmp_path, looped, "loop.json")))
    missing = {"color": {"accent": {"$value": "{color.nope}"}}}
    with pytest.raises(CvGenError, match="unknown token 'color.nope'"):
        load_design(str(write_tokens(tmp_path, missing, "missing.json")))


def test_injection_is_rejected(tmp_path: Path) -> None:
    """AC 9.3: a value that tries to break out of its declaration is refused, naming it."""
    data = {"color": {"accent": {"$type": "color", "$value": "red; } body { display:none"}}}
    with pytest.raises(CvGenError, match="design token 'color.accent' is not a valid color"):
        load_design(str(write_tokens(tmp_path, data)))
    fonts = {"font": {"body": {"$type": "fontFamily", "$value": 'Arial"; } * { color: red'}}}
    with pytest.raises(CvGenError, match="'font.body' is not a valid fontFamily"):
        load_design(str(write_tokens(tmp_path, fonts, "f.json")))


def test_url_design_with_wrong_pin_is_refused(http_root: Path, http_server: str) -> None:
    """AC 9.4: a URL design system whose content does not match its pin is refused."""
    body = json.dumps({"color": {"accent": {"$type": "color", "$value": "#00ff00"}}}).encode()
    (http_root / "tokens.json").write_bytes(body)
    url = f"{http_server}/tokens.json"
    with pytest.raises(CvGenError, match="does not match its sha256 pin"):
        load_design(url, sha256="0" * 64)
    theme = load_design(url, sha256=hashlib.sha256(body).hexdigest().upper())
    assert theme.value("color.accent") == "#00ff00"
    assert theme.source == url


def test_remote_design_cannot_add_css(http_root: Path, http_server: str) -> None:
    """A design system from a URL may not add custom CSS or font imports."""
    data = {"$extensions": {"com.cv-gen": {"customCss": "x.css", "fontImports": ["https://a/b"]}}}
    (http_root / "t.json").write_text(json.dumps(data), encoding="utf-8")
    theme = load_design(f"{http_server}/t.json")
    assert theme.custom_css == "" and theme.font_imports == []
    assert any("not allowed from a URL" in item for item in theme.ignored)


def test_local_extensions(tmp_path: Path) -> None:
    """A local design system can add custom CSS and https font imports."""
    (tmp_path / "extra.css").write_text("h1 { letter-spacing: 1px; }", encoding="utf-8")
    url = "https://fonts.googleapis.com/css2?family=Chivo&display=swap"
    data = {"$extensions": {"com.cv-gen": {"customCss": "extra.css", "fontImports": [url]}}}
    theme = load_design(str(write_tokens(tmp_path, data)))
    assert theme.custom_css == "h1 { letter-spacing: 1px; }"
    assert theme.font_imports == [url]
    (tmp_path / "evil.css").write_text("</style><script>alert(1)</script>", encoding="utf-8")
    evil = {"$extensions": {"com.cv-gen": {"customCss": "evil.css"}}}
    with pytest.raises(CvGenError, match="must not contain"):
        load_design(str(write_tokens(tmp_path, evil, "evil.json")))
    bad_font = {"$extensions": {"com.cv-gen": {"fontImports": ["javascript:alert(1)"]}}}
    with pytest.raises(CvGenError, match="plain https"):
        load_design(str(write_tokens(tmp_path, bad_font, "badfont.json")))
    missing = {"$extensions": {"com.cv-gen": {"customCss": "nope.css"}}}
    with pytest.raises(CvGenError, match="custom CSS not found"):
        load_design(str(write_tokens(tmp_path, missing, "missing.json")))


def test_yaml_tokens_and_relative_paths(tmp_path: Path) -> None:
    """Tokens may be YAML, and relative refs resolve against the base folder."""
    (tmp_path / "t.yaml").write_text(
        "page:\n  size: {$value: A4 landscape}\n"
        "  margin: {$type: dimension, $value: {value: 12, unit: mm}}\n",
        encoding="utf-8",
    )
    theme = load_design("t.yaml", base_dir=tmp_path)
    assert theme.value("page.size") == "A4 landscape"
    assert theme.value("page.margin") == "12mm"


def test_document_errors(tmp_path: Path) -> None:
    """Missing, unparseable and non-mapping files are reported."""
    with pytest.raises(CvGenError, match="no such design system"):
        load_document(str(tmp_path / "none.json"))
    (tmp_path / "bad.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(CvGenError, match="not valid JSON or YAML"):
        load_document(str(tmp_path / "bad.json"))
    (tmp_path / "list.yaml").write_text("- a\n", encoding="utf-8")
    with pytest.raises(CvGenError, match="must be a mapping"):
        load_document(str(tmp_path / "list.yaml"))


def test_default_theme_covers_every_token() -> None:
    """The built-in default defines every semantic token."""
    theme = default_theme()
    assert set(theme.css_values) == set(SEMANTIC_TOKENS)
    assert theme.fonts["font.body"][0] == "Calibri"
    assert theme.colors["color.accent"].hex == "#0b5cad"
    assert theme.source is None


def test_flatten_inherits_types() -> None:
    """Group $type applies to children; $-keys and non-mappings are not tokens."""
    tokens = flatten(
        {"a": {"$type": "color", "b": {"$value": "#fff"}, "c": {"d": {"$value": 1}}, "x": 1}}
    )
    assert tokens["a.b"].type == "color"
    assert tokens["a.c.d"].type == "color"
    assert resolve_aliases(tokens)["a.b"].value == "#fff"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#abc", "#aabbcc"),
        ("#AABBCC80", "#aabbcc80"),
        ("rgb(255, 0, 128)", "#ff0080"),
        ("rgba(255 0 128 / 50%)", "#ff008080"),
        ("rgb(100%, 0%, 0%)", "#ff0000"),
        ("hsl(0, 100%, 50%)", "#ff0000"),
        ("hsla(120deg 100% 25% / 0.5)", "#00800080"),
        ({"colorSpace": "srgb", "components": [1, 0, 0], "alpha": 1}, "#ff0000"),
        ({"hex": "#00ff00"}, "#00ff00"),
    ],
)
def test_colors(value, expected) -> None:
    """Every supported color syntax normalizes to hex."""
    assert parse_color(value).hex == expected


@pytest.mark.parametrize(
    "bad",
    [
        "red",
        "#ggg",
        "rgb(300, 0, 0)",
        12,
        {"colorSpace": "display-p3", "components": [1, 0, 0]},
        {"components": [2, 0, 0]},
        {"components": [1, 0, 0], "alpha": 3},
    ],
)
def test_bad_colors(bad) -> None:
    """Unsupported or malformed colors are rejected."""
    with pytest.raises(ValueError):
        parse_color(bad)


def test_other_parsers() -> None:
    """Dimensions, fonts, weights, numbers and page sizes validate and normalize."""
    assert parse_dimension("12.50pt") == "12.5pt"
    assert parse_dimension(0) == "0"
    assert parse_dimension({"value": 1.5, "unit": "rem"}) == "1.5rem"
    for bad in ("12", "12vh", {"value": "1", "unit": "px"}, "1px; color: red"):
        with pytest.raises(ValueError):
            parse_dimension(bad)
    assert parse_font_family("'Big Shoulders', Impact, sans-serif") == [
        "Big Shoulders",
        "Impact",
        "sans-serif",
    ]
    assert font_family_css(["Chivo", "system-ui"]) == '"Chivo", system-ui'
    for bad in ("", [1], "A{b}"):
        with pytest.raises(ValueError):
            parse_font_family(bad)
    assert parse_font_weight("Semi-Bold") == 600
    assert parse_font_weight(650) == 650
    with pytest.raises(ValueError):
        parse_font_weight("heavyish")
    assert parse_number(1.25) == "1.25"
    with pytest.raises(ValueError):
        parse_number("1.25")
    assert parse_page_size("letter") == "Letter"
    assert parse_page_size("8.5in 11in") == "8.5in 11in"
    for bad in ("A4 sideways", "huge", 4, "a b c"):
        with pytest.raises(ValueError):
            parse_page_size(bad)

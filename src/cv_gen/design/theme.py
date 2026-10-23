"""Turning design tokens into a validated theme for the HTML, PDF and Word generators.

cv-gen reads a fixed set of semantic token names (``SEMANTIC_TOKENS``). Each has a
type, and each value is parsed by that type's validator and written back out by it,
so the page's CSS only ever contains text a validator produced. A tokens file cannot
inject CSS, markup or script, which matters when the design system comes from a URL.
"""

from __future__ import annotations

import colorsys
import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from cv_gen.design.tokens import Token, TokenDocument, flatten, load_document, resolve_aliases
from cv_gen.errors import CvGenError

# Every token cv-gen reads, with its DTCG type. Defaults live in default.tokens.json.
SEMANTIC_TOKENS = {
    "color.text": "color",
    "color.muted": "color",
    "color.heading": "color",
    "color.accent": "color",
    "color.link": "color",
    "color.background": "color",
    "color.rule": "color",
    "font.body": "fontFamily",
    "font.heading": "fontFamily",
    "font.mono": "fontFamily",
    "font-size.base": "dimension",
    "font-size.small": "dimension",
    "font-size.name": "dimension",
    "font-size.section": "dimension",
    "font-size.entry": "dimension",
    "font-weight.heading": "fontWeight",
    "line-height.base": "number",
    "space.section": "dimension",
    "space.entry": "dimension",
    "rule.width": "dimension",
    "page.size": "pageSize",
    "page.margin": "dimension",
}

GENERIC_FAMILIES = {
    "serif",
    "sans-serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
    "ui-serif",
    "ui-sans-serif",
    "ui-monospace",
    "ui-rounded",
}
FONT_WEIGHTS = {
    "thin": 100,
    "hairline": 100,
    "extra-light": 200,
    "ultra-light": 200,
    "light": 300,
    "normal": 400,
    "regular": 400,
    "book": 400,
    "medium": 500,
    "semi-bold": 600,
    "demi-bold": 600,
    "bold": 700,
    "extra-bold": 800,
    "ultra-bold": 800,
    "black": 900,
    "heavy": 900,
}
UNITS = ("px", "rem", "em", "pt", "pc", "mm", "cm", "in", "%")
PAGE_SIZES = ("A3", "A4", "A5", "B4", "B5", "Letter", "Legal", "Ledger")
_NUMBER = r"-?(?:\d+\.?\d*|\.\d+)"
_FONT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]*$")
_HTTPS_URL = re.compile(r"^https://[A-Za-z0-9.\-]+(?::\d+)?/[^\s\"'<>()\\]*$")


@dataclass(frozen=True)
class Color:
    """An sRGB color with alpha, each channel 0-255 (alpha 0-1)."""

    red: int
    green: int
    blue: int
    alpha: float = 1.0

    @property
    def hex(self) -> str:
        """``#rrggbb``, or ``#rrggbbaa`` when not opaque."""
        base = f"#{self.red:02x}{self.green:02x}{self.blue:02x}"
        return base if self.alpha >= 1 else f"{base}{round(self.alpha * 255):02x}"


def _channel(text: str, scale: float = 255) -> float:
    """Read a CSS channel value: a number, or a percentage of ``scale``."""
    if text.endswith("%"):
        return float(text[:-1]) / 100 * scale
    return float(text)


def parse_color(value: Any) -> Color:
    """Parse a DTCG color: hex, ``rgb()``/``rgba()``, ``hsl()``/``hsla()``, or the object form."""
    if isinstance(value, dict):
        if isinstance(value.get("hex"), str) and "components" not in value:
            return parse_color(value["hex"])
        space = value.get("colorSpace", "srgb")
        components = value.get("components")
        if space != "srgb" or not isinstance(components, list) or len(components) != 3:
            raise ValueError("only srgb colors with three components are supported")
        if not all(isinstance(c, (int, float)) and 0 <= c <= 1 for c in components):
            raise ValueError("srgb components must be numbers from 0 to 1")
        alpha = value.get("alpha", 1)
        red, green, blue = (round(c * 255) for c in components)
        return Color(red, green, blue, _alpha(alpha))
    if not isinstance(value, str):
        raise ValueError("a color must be a string or a DTCG color object")
    text = value.strip()
    if match := re.fullmatch(r"#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", text):
        digits = match.group(1)
        if len(digits) in (3, 4):
            digits = "".join(ch * 2 for ch in digits)
        alpha = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
        return Color(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), alpha)
    number = rf"{_NUMBER}%?"
    if match := re.fullmatch(
        rf"rgba?\(\s*({number})\s*[,\s]\s*({number})\s*[,\s]\s*({number})\s*(?:[,/]\s*({number})\s*)?\)",
        text,
    ):
        red, green, blue = (round(_channel(match.group(i))) for i in (1, 2, 3))
        alpha = _channel(match.group(4), 1) if match.group(4) else 1.0
        if not all(0 <= c <= 255 for c in (red, green, blue)):
            raise ValueError("rgb channels must be 0-255")
        return Color(red, green, blue, _alpha(alpha))
    if match := re.fullmatch(
        rf"hsla?\(\s*({_NUMBER})(?:deg)?\s*[,\s]\s*({_NUMBER})%\s*[,\s]\s*({_NUMBER})%\s*(?:[,/]\s*({number})\s*)?\)",
        text,
    ):
        hue, sat, light = float(match.group(1)) % 360, float(match.group(2)), float(match.group(3))
        r, g, b = colorsys.hls_to_rgb(hue / 360, light / 100, sat / 100)
        alpha = _channel(match.group(4), 1) if match.group(4) else 1.0
        return Color(round(r * 255), round(g * 255), round(b * 255), _alpha(alpha))
    raise ValueError(f"{text!r} is not a hex, rgb() or hsl() color")


def _alpha(value: Any) -> float:
    """Check an alpha value is a number from 0 to 1."""
    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("alpha must be a number from 0 to 1")
    return float(value)


def parse_dimension(value: Any) -> str:
    """Parse ``"12pt"`` or ``{value: 12, unit: "pt"}`` into canonical CSS text."""
    if isinstance(value, dict):
        number, unit = value.get("value"), value.get("unit")
        if not isinstance(number, (int, float)) or unit not in UNITS:
            raise ValueError(f"a dimension needs a numeric value and a unit in {', '.join(UNITS)}")
        return f"{number:g}{unit}"
    if isinstance(value, (int, float)) and value == 0:
        return "0"
    if isinstance(value, str) and (
        match := re.fullmatch(rf"({_NUMBER})({'|'.join(UNITS)})", value.strip())
    ):
        return f"{float(match.group(1)):g}{match.group(2)}"
    raise ValueError(f"{value!r} is not a dimension such as 12pt or 0.6in")


def parse_font_family(value: Any) -> list[str]:
    """Parse a font family (a name, a comma list, or a list) into validated names."""
    names = (
        value
        if isinstance(value, list)
        else str(value).split(",")
        if isinstance(value, str)
        else None
    )
    if not names:
        raise ValueError("a font family must be a name or a list of names")
    cleaned = []
    for name in names:
        if not isinstance(name, str):
            raise ValueError("font family names must be strings")
        name = name.strip().strip("'\"").strip()
        if not _FONT_NAME.match(name):
            raise ValueError(f"{name!r} is not a plain font family name")
        cleaned.append(name)
    return cleaned


def font_family_css(names: list[str]) -> str:
    """Write a validated family list as CSS, quoting everything but generic families."""
    return ", ".join(name if name in GENERIC_FAMILIES else f'"{name}"' for name in names)


def parse_font_weight(value: Any) -> int:
    """Parse a weight (1-1000, or a DTCG keyword such as ``bold``)."""
    if isinstance(value, str) and value.strip().lower() in FONT_WEIGHTS:
        return FONT_WEIGHTS[value.strip().lower()]
    if isinstance(value, (int, float)) and 1 <= value <= 1000:
        return int(value)
    raise ValueError(f"{value!r} is not a font weight")


def parse_number(value: Any) -> str:
    """Parse a plain positive number (a line height)."""
    if isinstance(value, (int, float)) and 0 < value <= 10:
        return f"{value:g}"
    raise ValueError(f"{value!r} is not a number from 0 to 10")


def parse_page_size(value: Any) -> str:
    """Parse a CSS ``@page`` size: a named size (optionally landscape) or two dimensions."""
    if not isinstance(value, str):
        raise ValueError("a page size must be a string")
    words = value.split()
    names = {size.lower(): size for size in PAGE_SIZES}
    if words and words[0].lower() in names and len(words) <= 2:
        orientation = words[1].lower() if len(words) == 2 else None
        if orientation not in (None, "portrait", "landscape"):
            raise ValueError(f"{value!r}: orientation must be portrait or landscape")
        return " ".join([names[words[0].lower()], *([orientation] if orientation else [])])
    if len(words) == 2:
        return " ".join(parse_dimension(word) for word in words)
    raise ValueError(f"{value!r} is not a page size such as A4, Letter or '8.5in 11in'")


@dataclass
class Theme:
    """A validated design: CSS-ready values plus what Word needs, and a usage report."""

    css_values: dict[str, str]
    fonts: dict[str, list[str]]
    colors: dict[str, Color]
    source: str | None = None
    custom_css: str = ""
    font_imports: list[str] = field(default_factory=list)
    supplied: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)

    def css_variables(self) -> str:
        """Return a ``:root`` block defining ``--cv-<token>`` for every semantic token."""
        lines = [
            f"  --cv-{name.replace('.', '-')}: {value};" for name, value in self.css_values.items()
        ]
        return ":root {\n" + "\n".join(lines) + "\n}"

    def value(self, name: str) -> str:
        """Return the CSS text of one semantic token."""
        return self.css_values[name]


def _validated(name: str, raw: Any) -> tuple[str, list[str] | None, Color | None]:
    """Validate one semantic token; return its CSS text and any font list or color."""
    kind = SEMANTIC_TOKENS[name]
    try:
        if kind == "color":
            color = parse_color(raw)
            return color.hex, None, color
        if kind == "fontFamily":
            names = parse_font_family(raw)
            return font_family_css(names), names, None
        if kind == "dimension":
            return parse_dimension(raw), None, None
        if kind == "fontWeight":
            return str(parse_font_weight(raw)), None, None
        if kind == "number":
            return parse_number(raw), None, None
        return parse_page_size(raw), None, None
    except ValueError as error:
        raise CvGenError(f"design token '{name}' is not a valid {kind}: {error}") from error


def build_theme(documents: list[TokenDocument]) -> Theme:
    """Build a theme from tokens documents layered in order (defaults first)."""
    # Merge the token trees before resolving aliases, so a design system can alias the
    # defaults and an override (color.accent) carries through the defaults' own aliases
    # (color.link -> {color.accent}).
    tokens: dict[str, Token] = {}
    supplied: list[str] = []
    ignored: list[str] = []
    for index, document in enumerate(documents):
        own = flatten(document.data)
        tokens.update(own)
        if index > 0:
            supplied += [path for path in own if path in SEMANTIC_TOKENS]
            ignored += [path for path in own if path not in SEMANTIC_TOKENS]
    raw = {path: token.value for path, token in resolve_aliases(tokens).items()}
    css_values: dict[str, str] = {}
    fonts: dict[str, list[str]] = {}
    colors: dict[str, Color] = {}
    for name in SEMANTIC_TOKENS:
        css, font_names, color = _validated(name, raw[name])
        css_values[name] = css
        if font_names is not None:
            fonts[name] = font_names
        if color is not None:
            colors[name] = color
    theme = Theme(css_values, fonts, colors, supplied=supplied, ignored=ignored)
    if len(documents) > 1:
        _apply_extensions(theme, documents[-1])
        theme.source = documents[-1].ref
    return theme


def _apply_extensions(theme: Theme, document: TokenDocument) -> None:
    """Add custom CSS and font imports from a local design system's extensions block."""
    extensions = document.extensions
    if not extensions:
        return
    if document.is_remote:
        if {"customCss", "fontImports"} & set(extensions):
            theme.ignored.append("$extensions.com.cv-gen (not allowed from a URL)")
        return
    if css_path := extensions.get("customCss"):
        path = Path(css_path)
        if not path.is_absolute() and document.folder is not None:
            path = document.folder / path
        if not path.is_file():
            raise CvGenError(f"design system custom CSS not found: {path}")
        css = path.read_text(encoding="utf-8-sig")
        # The CSS is placed inside a <style> element; "</" is the only way out of it.
        if "</" in css:
            raise CvGenError(f"custom CSS {path} must not contain '</'")
        theme.custom_css = css
    for url in extensions.get("fontImports", []) or []:
        if not isinstance(url, str) or not _HTTPS_URL.match(url):
            raise CvGenError(f"font import {url!r} must be a plain https:// URL")
        theme.font_imports.append(url)


def _default_document() -> TokenDocument:
    """Load the built-in default tokens shipped with the package."""
    text = resources.files("cv_gen.design").joinpath("default.tokens.json").read_text("utf-8")
    return TokenDocument(
        data=json.loads(text), ref="(built-in default)", is_remote=False, folder=None
    )


def default_theme() -> Theme:
    """Return the built-in theme: neutral, print-first, WCAG AA contrast."""
    return build_theme([_default_document()])


def load_design(ref: str | None, sha256: str | None = None, base_dir: Path | None = None) -> Theme:
    """Load a design system (path or https URL) over the defaults; ``None`` gives the default."""
    if ref is None:
        return default_theme()
    return build_theme([_default_document(), load_document(ref, sha256, base_dir)])

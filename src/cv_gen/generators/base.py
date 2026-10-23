"""The generator contract and the registry of output formats."""

from __future__ import annotations

import abc
import importlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from cv_gen.config import PdfEngineName, RenderOptions
from cv_gen.errors import CvGenError

if TYPE_CHECKING:
    from cv_gen.design.theme import Theme
    from cv_gen.model import Resume


@dataclass
class RenderRequest:
    """Everything a generator needs besides the resume itself."""

    options: RenderOptions = field(default_factory=RenderOptions)
    theme: Theme | None = None
    pdf_engine: PdfEngineName = "auto"

    def resolved_theme(self) -> Theme:
        """Return the request's theme, or the built-in default theme."""
        if self.theme is None:
            from cv_gen.design.theme import default_theme

            self.theme = default_theme()
        return self.theme


class Generator(abc.ABC):
    """Turns a Resume into the bytes of one output format."""

    name: ClassVar[str]
    """The format name used on the command line (``--format md``)."""

    extension: ClassVar[str]
    """The file extension, without the dot."""

    binary: ClassVar[bool] = False
    """Whether the output is binary (DOCX, PDF) rather than UTF-8 text."""

    description: ClassVar[str] = ""

    @abc.abstractmethod
    def render(self, resume: Resume, request: RenderRequest) -> bytes:
        """Return the finished document."""


# Named by import path so that, say, building Markdown never imports python-docx.
GENERATORS = {
    "md": "cv_gen.generators.markdown:MarkdownGenerator",
    "txt": "cv_gen.generators.text:TextGenerator",
    "docx": "cv_gen.generators.docx:DocxGenerator",
    "json": "cv_gen.generators.jsonout:JsonGenerator",
    "html": "cv_gen.generators.html:HtmlGenerator",
    "pdf": "cv_gen.generators.pdf:PdfGenerator",
}

ALIASES = {"markdown": "md", "text": "txt", "word": "docx"}


def canonical_format(name: str) -> str:
    """Map a format name or alias to its canonical name, or fail listing the formats."""
    key = ALIASES.get(name.lower(), name.lower())
    if key not in GENERATORS:
        raise CvGenError(
            f"unknown format '{name}'; formats: {', '.join(GENERATORS)}",
            "run: cv-gen formats",
        )
    return key


def get_generator(name: str) -> Generator:
    """Instantiate the generator for a format name or alias."""
    module_name, _, attr = GENERATORS[canonical_format(name)].partition(":")
    cls: Any = getattr(importlib.import_module(module_name), attr)
    return cls()


def list_formats() -> list[tuple[str, str, str]]:
    """Return ``(name, extension, description)`` for every format."""
    rows = []
    for name in GENERATORS:
        generator = get_generator(name)
        rows.append((name, generator.extension, generator.description))
    return rows

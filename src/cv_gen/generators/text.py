"""Plain text output: wrapped, with underlined section headings.

Plain text is what many application forms and ATS paste boxes want: no markup, a
conventional heading for every section, one entry per block, and lines short enough
to survive email.
"""

from __future__ import annotations

import textwrap

from cv_gen.generators import view
from cv_gen.generators.base import Generator, RenderRequest
from cv_gen.generators.view import Entry, ViewSection
from cv_gen.model import Resume

CONTACT_LABELS = {"location": "Location", "email": "Email", "phone": "Phone", "url": "Website"}


def wrap(text: str, width: int, indent: str = "", hanging: str | None = None) -> list[str]:
    """Wrap ``text`` to ``width``; URLs and other long words are never broken."""
    return textwrap.wrap(
        text,
        width=width,
        initial_indent=indent,
        subsequent_indent=hanging if hanging is not None else indent,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [indent.rstrip()]


def _entry(entry: Entry, width: int) -> list[str]:
    """Lay out one ``entries`` block."""
    lines: list[str] = []
    if entry.title:
        lines += wrap(entry.title, width)
    if entry.meta:
        lines += wrap(" | ".join(entry.meta), width)
    if entry.url:
        lines += wrap(entry.url, width)
    if entry.summary:
        lines += wrap(entry.summary, width, "  ")
    for bullet in entry.bullets:
        lines += wrap(bullet, width, "  - ", "    ")
    if entry.keywords:
        lines += wrap(", ".join(entry.keywords), width, "  ")
    return [*lines, ""]


def _section(section: ViewSection, width: int) -> list[str]:
    """Lay out one section with an underlined, upper-case heading."""
    title = section.title.upper()
    lines = [title, "=" * min(len(title), width), ""]
    if section.updated:
        lines += [f"Updated {section.updated}", ""]
    for paragraph in section.paragraphs:
        lines += [*wrap(paragraph, width), ""]
    if section.layout == "entries":
        for entry in section.entries:
            lines += _entry(entry, width)
    elif section.layout == "keywords":
        for entry in section.entries:
            label = entry.title or ""
            if entry.subtitle:
                label += f" ({entry.subtitle})"
            lines += wrap(f"{label}: {', '.join(entry.keywords)}", width, "", "  ")
        lines.append("")
    elif section.entries:
        for entry in section.entries:
            head = entry.title or ""
            if entry.subtitle:
                head += f", {entry.subtitle}"
            if entry.dates:
                head += f" ({entry.dates})"
            body = entry.summary or entry.url or ""
            text = f"{head} — {body}" if head and body else head or body
            lines += wrap(text, width, "- ", "  ")
            if entry.url and entry.summary:
                lines += wrap(entry.url, width, "  ")
        lines.append("")
    return lines


def render_text(resume: Resume, request: RenderRequest) -> str:
    """Return the CV as wrapped plain text."""
    width = request.options.text_width
    head = view.header(resume)
    lines = [head.name.upper(), "=" * min(len(head.name), width)]
    if head.label:
        lines += wrap(head.label, width)
    if head.headline:
        lines += wrap(head.headline, width)
    if head.contacts:
        lines.append("")
        for contact in head.contacts:
            value = (
                contact.url
                if contact.url and contact.kind not in ("email", "phone")
                else contact.text
            )
            label = CONTACT_LABELS.get(contact.kind, contact.kind)
            lines += wrap(f"{label}: {value}", width)
    lines.append("")
    for section in view.sections(resume, request.options):
        lines += _section(section, width)
    return "\n".join(line.rstrip() for line in lines).rstrip() + "\n"


class TextGenerator(Generator):
    """Plain text (``.txt``)."""

    name = "txt"
    extension = "txt"
    description = "Plain UTF-8 text, wrapped (default 80 columns); for paste boxes and email."

    def render(self, resume: Resume, request: RenderRequest) -> bytes:
        """Render plain text as UTF-8."""
        return render_text(resume, request).encode("utf-8")

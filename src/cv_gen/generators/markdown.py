"""Markdown output: one ``#`` heading, ``##`` sections, ``###`` entries.

The heading levels are the structure, so the file reads well on GitHub, converts
cleanly with pandoc, and gives a language model or parser unambiguous sections.
"""

from __future__ import annotations

import re

from cv_gen.generators import view
from cv_gen.generators.base import Generator, RenderRequest
from cv_gen.generators.view import Entry, ViewSection
from cv_gen.model import Resume

_SPECIAL = re.compile(r"([\\`*_\[\]<>|])")
_BLOCK_MARKER = re.compile(r"^(\s*)([#+\-])(\s)", re.MULTILINE)
_ORDERED_MARKER = re.compile(r"^(\s*)(\d+)\.(\s)", re.MULTILINE)


def escape(text: str) -> str:
    """Escape characters Markdown would read as formatting, so source text stays literal."""
    escaped = _SPECIAL.sub(r"\\\1", text)
    escaped = _BLOCK_MARKER.sub(r"\1\\\2\3", escaped)
    return _ORDERED_MARKER.sub(r"\1\2\\.\3", escaped)


def link(text: str, url: str | None) -> str:
    """Return ``[text](url)``, or the escaped text when there is no URL."""
    if not url:
        return escape(text)
    return f"[{escape(text)}]({url.replace(' ', '%20').replace(')', '%29')})"


def _entry(entry: Entry) -> list[str]:
    """Lay out one entry as a ``###`` block."""
    lines = [f"### {link(entry.title, entry.url) if entry.title else 'Untitled'}", ""]
    if entry.meta:
        first, *rest = entry.meta
        parts = [f"**{escape(first)}**" if entry.subtitle else escape(first)]
        parts += [escape(part) for part in rest]
        lines += [" · ".join(parts), ""]
    if entry.summary:
        lines += [escape(entry.summary), ""]
    if entry.bullets:
        lines += [f"- {escape(bullet)}" for bullet in entry.bullets] + [""]
    if entry.keywords:
        lines += [f"*{escape(', '.join(entry.keywords))}*", ""]
    return lines


def _list_line(entry: Entry) -> str:
    """Lay out one entry of a ``list`` section on a single bullet line."""
    head = f"**{link(entry.title, entry.url)}**" if entry.title else ""
    if entry.subtitle:
        head += f", {escape(entry.subtitle)}"
    if entry.dates:
        head += f" ({escape(entry.dates)})"
    body = escape(entry.summary) if entry.summary else ""
    if not entry.title and entry.url:
        # With no title to carry the link, the text itself becomes the link.
        body = link(entry.summary or entry.url, entry.url)
    return "- " + (f"{head} — {body}" if head and body else head or body)


def _section(section: ViewSection) -> list[str]:
    """Lay out one section."""
    lines = [f"## {escape(section.title)}", ""]
    if section.updated:
        lines += [f"*Updated {escape(section.updated)}*", ""]
    for paragraph in section.paragraphs:
        lines += [escape(paragraph), ""]
    if section.layout == "entries":
        for entry in section.entries:
            lines += _entry(entry)
    elif section.layout == "keywords":
        for entry in section.entries:
            label = entry.title or ""
            if entry.subtitle:
                label += f" ({entry.subtitle})"
            lines.append(f"- **{escape(label)}:** {escape(', '.join(entry.keywords))}")
        lines.append("")
    elif section.entries:
        lines += [_list_line(entry) for entry in section.entries] + [""]
    return lines


def render_markdown(resume: Resume, request: RenderRequest) -> str:
    """Return the CV as Markdown text."""
    head = view.header(resume)
    lines = [f"# {escape(head.name)}", ""]
    if head.label:
        lines += [f"**{escape(head.label)}**", ""]
    if head.headline:
        lines += [f"*{escape(head.headline)}*", ""]
    if head.contacts:
        contact_parts = [
            link(c.text, c.url)
            if c.kind in ("location", "email", "phone", "url")
            else f"{escape(c.kind)}: {link(c.text, c.url)}"
            for c in head.contacts
        ]
        lines += [" · ".join(contact_parts), ""]
    for section in view.sections(resume, request.options):
        lines += _section(section)
    return "\n".join(lines).rstrip() + "\n"


class MarkdownGenerator(Generator):
    """Markdown (``.md``)."""

    name = "md"
    extension = "md"
    description = "Markdown with real heading levels; good for GitHub, pandoc and LLMs."

    def render(self, resume: Resume, request: RenderRequest) -> bytes:
        """Render Markdown as UTF-8."""
        return render_markdown(resume, request).encode("utf-8")

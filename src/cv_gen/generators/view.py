"""One reading of a Resume shared by every generator.

Section order, section titles, omission of empty sections and date wording are decided
here once, so Markdown, text, Word, HTML and PDF always agree. Generators only lay out
the :class:`Header` and the :class:`ViewSection` list this module returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from cv_gen.config import RenderOptions
from cv_gen.errors import CvGenError
from cv_gen.model import BUILTIN_SECTION_IDS, Basics, Location, Period, Resume

MONTH_ABBREVIATIONS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

DEFAULT_TITLES = {
    "summary": "Summary",
    "work": "Experience",
    "projects": "Projects",
    "skills": "Skills",
    "education": "Education",
    "certificates": "Certifications",
    "awards": "Awards",
    "publications": "Publications",
    "volunteer": "Volunteering",
    "languages": "Languages",
    "interests": "Interests",
    "references": "References",
}

Layout = Literal["text", "entries", "list", "keywords"]
"""How a section is laid out.

``text``: paragraphs. ``entries``: titled blocks with dates and bullets (jobs).
``list``: one line per entry, its title in bold (a "current focus" list).
``keywords``: one line per group, a label then comma-separated keywords (skills).
"""


@dataclass
class Contact:
    """One item of the header's contact line."""

    kind: str  # location, email, phone, url, or a profile's network name
    text: str
    url: str | None = None


@dataclass
class Header:
    """The top of the CV."""

    name: str
    label: str | None
    headline: str | None
    contacts: list[Contact]


@dataclass
class Entry:
    """One block in a section, in format-neutral terms."""

    title: str | None = None
    subtitle: str | None = None
    dates: str | None = None
    location: str | None = None
    url: str | None = None
    summary: str | None = None
    bullets: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    @property
    def meta(self) -> list[str]:
        """The subtitle, dates and location that are present, in that order."""
        return [part for part in (self.subtitle, self.dates, self.location) if part]


@dataclass
class ViewSection:
    """A section ready to lay out."""

    id: str
    title: str
    layout: Layout
    paragraphs: list[str] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)
    updated: str | None = None


def format_date(value: str | None) -> str | None:
    """Word an ISO partial date for a CV: ``2021`` or ``Apr 2021`` (days are dropped)."""
    if not value:
        return None
    year, _, rest = value.partition("-")
    if not rest:
        return year
    return f"{MONTH_ABBREVIATIONS[int(rest[:2]) - 1]} {year}"


def format_period(start: str | None, end: str | None) -> str | None:
    """Word one period: ``2013 – 2019``, ``2021 – Present``, or ``2022`` for one year."""
    first, last = format_date(start), format_date(end)
    if first is None:
        return last
    if last is None:
        return f"{first} – Present"
    return first if first == last else f"{first} – {last}"


def format_dates(
    start: str | None, end: str | None, periods: list[Period] | None = None
) -> str | None:
    """Word an entry's dates, listing separate periods when there are several."""
    if periods and len(periods) > 1:
        words = [format_period(p.startDate, p.endDate) for p in periods]
        return ", ".join(word for word in words if word)
    return format_period(start, end)


def location_text(location: Location | None) -> str | None:
    """Word a location as ``City, Region, Country`` with the parts that are present."""
    if location is None:
        return None
    parts = [location.city, location.region, location.countryCode]
    return ", ".join(part for part in parts if part) or None


def header(resume: Resume) -> Header:
    """Build the CV header from ``basics``."""
    basics: Basics = resume.basics
    contacts: list[Contact] = []
    if where := location_text(basics.location):
        contacts.append(Contact("location", where))
    if basics.email:
        contacts.append(Contact("email", basics.email, f"mailto:{basics.email}"))
    if basics.phone:
        contacts.append(Contact("phone", basics.phone, f"tel:{basics.phone.replace(' ', '')}"))
    if basics.url:
        contacts.append(Contact("url", _display_url(basics.url), basics.url))
    for profile in basics.profiles:
        text = profile.username or (_display_url(profile.url) if profile.url else None)
        if text:
            contacts.append(Contact(profile.network or "profile", text, profile.url))
    return Header(basics.name or "Curriculum Vitae", basics.label, basics.headline, contacts)


def _display_url(url: str) -> str:
    """Shorten a URL for display: no scheme, no ``www.``, no trailing slash."""
    for prefix in ("https://", "http://"):
        url = url.removeprefix(prefix)
    return url.removeprefix("www.").rstrip("/")


def _builtin(resume: Resume, section_id: str) -> tuple[Layout, list[str], list[Entry]]:
    """Return the layout, paragraphs and entries of a built-in section."""
    if section_id == "summary":
        return "text", [resume.basics.summary] if resume.basics.summary else [], []
    if section_id == "work":
        return (
            "entries",
            [],
            [
                Entry(
                    title=job.name,
                    subtitle=job.position,
                    dates=format_dates(job.startDate, job.endDate, job.periods),
                    location=job.location,
                    url=job.url,
                    summary=job.summary or job.description,
                    bullets=list(job.highlights),
                )
                for job in resume.work
            ],
        )
    if section_id == "projects":
        return (
            "entries",
            [],
            [
                Entry(
                    title=p.name,
                    subtitle=", ".join(p.roles) or p.entity,
                    dates=format_dates(p.startDate, p.endDate, p.periods),
                    url=p.url,
                    summary=p.description,
                    bullets=list(p.highlights),
                    keywords=list(p.keywords),
                )
                for p in resume.projects
            ],
        )
    if section_id == "education":
        return (
            "entries",
            [],
            [
                Entry(
                    title=e.institution,
                    subtitle=", ".join(part for part in (e.studyType, e.area) if part) or None,
                    dates=format_dates(e.startDate, e.endDate),
                    url=e.url,
                    summary=f"Score: {e.score}" if e.score else None,
                    bullets=list(e.courses),
                )
                for e in resume.education
            ],
        )
    if section_id == "volunteer":
        return (
            "entries",
            [],
            [
                Entry(
                    title=v.organization,
                    subtitle=v.position,
                    dates=format_dates(v.startDate, v.endDate),
                    url=v.url,
                    summary=v.summary,
                    bullets=list(v.highlights),
                )
                for v in resume.volunteer
            ],
        )
    if section_id == "awards":
        return (
            "entries",
            [],
            [
                Entry(
                    title=a.title, subtitle=a.awarder, dates=format_date(a.date), summary=a.summary
                )
                for a in resume.awards
            ],
        )
    if section_id == "certificates":
        return (
            "entries",
            [],
            [
                Entry(title=c.name, subtitle=c.issuer, dates=format_date(c.date), url=c.url)
                for c in resume.certificates
            ],
        )
    if section_id == "publications":
        return (
            "entries",
            [],
            [
                Entry(
                    title=p.name,
                    subtitle=p.publisher,
                    dates=format_date(p.releaseDate),
                    url=p.url,
                    summary=p.summary,
                )
                for p in resume.publications
            ],
        )
    if section_id == "skills":
        return (
            "keywords",
            [],
            [
                Entry(title=s.name, subtitle=s.level, keywords=list(s.keywords))
                for s in resume.skills
            ],
        )
    if section_id == "interests":
        return (
            "keywords",
            [],
            [Entry(title=i.name, keywords=list(i.keywords)) for i in resume.interests],
        )
    if section_id == "languages":
        return "list", [], [Entry(title=x.language, summary=x.fluency) for x in resume.languages]
    # references
    return "list", [], [Entry(title=r.name, summary=r.reference) for r in resume.references]


def _has_content(entry: Entry) -> bool:
    """Tell whether an entry carries anything worth printing."""
    return bool(entry.title or entry.summary or entry.url or entry.bullets or entry.keywords)


def sections(resume: Resume, options: RenderOptions | None = None) -> list[ViewSection]:
    """Return the sections to render, in order, without empty ones.

    By default: the built-in sections in conventional CV order, then custom sections
    in the order the source gave them. ``options.sections`` picks and orders them.
    """
    options = options or RenderOptions()
    custom = {section.id: section for section in resume.sections}
    available = [*BUILTIN_SECTION_IDS, *custom]
    wanted = options.sections if options.sections is not None else available
    unknown = [section_id for section_id in wanted if section_id not in available]
    if unknown:
        raise CvGenError(
            f"unknown section id(s) in render.sections: {', '.join(unknown)}",
            f"available here: {', '.join(available)}",
        )
    result: list[ViewSection] = []
    for section_id in wanted:
        if section_id in custom:
            source = custom[section_id]
            title = options.section_titles.get(section_id, source.title)
            paragraphs = list(source.paragraphs)
            entries = [
                Entry(
                    title=item.title,
                    subtitle=item.subtitle,
                    dates=format_date(item.date),
                    url=item.url,
                    summary=item.text,
                )
                for item in source.items
            ]
            layout: Layout = "list"
            updated = format_date(source.updated)
        else:
            title = options.section_titles.get(section_id, DEFAULT_TITLES[section_id])
            layout, paragraphs, entries = _builtin(resume, section_id)
            updated = None
        entries = [entry for entry in entries if _has_content(entry)]
        if paragraphs or entries:
            result.append(ViewSection(section_id, title, layout, paragraphs, entries, updated))
    return result


def basename_for(resume: Resume, configured: str | None = None) -> str:
    """Choose output file names: the configured basename, else a slug of the name."""
    if configured:
        return configured
    name = resume.basics.name or ""
    slug = "-".join("".join(ch if ch.isalnum() else " " for ch in name.lower()).split())
    return f"{slug}-cv" if slug else "resume"

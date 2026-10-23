"""HTML output: one self-contained, printable page styled by the design system.

Templates are Jinja2 with autoescape on, so every piece of source text is escaped;
links are limited to http(s), mailto and tel. The stylesheet is rendered separately,
without HTML escaping, from values the theme has already validated. The model is also
embedded as schema.org ``Person`` JSON-LD for search engines and parsers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader, StrictUndefined
from markupsafe import Markup

from cv_gen import __version__
from cv_gen.generators import view
from cv_gen.generators.base import Generator, RenderRequest
from cv_gen.model import Resume

SAFE_SCHEMES = ("http://", "https://", "mailto:", "tel:")


def safe_url(url: str | None) -> str | None:
    """Return the URL if its scheme is safe to link to, otherwise nothing.

    Scraped data could carry ``javascript:`` links; those render as plain text.
    """
    if not url:
        return None
    candidate = url.strip()
    return candidate if candidate.lower().startswith(SAFE_SCHEMES) else None


def environment(templates: Path | None, autoescape: bool) -> Environment:
    """Build a Jinja environment that prefers ``templates`` and falls back to the built-ins."""
    loaders: list[Any] = []
    if templates is not None:
        loaders.append(FileSystemLoader(str(templates)))
    loaders.append(PackageLoader("cv_gen.generators", "templates"))
    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=autoescape,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["safe_url"] = safe_url
    return env


def person_jsonld(resume: Resume) -> dict[str, Any]:
    """Describe the person as schema.org JSON-LD."""
    basics = resume.basics
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": basics.name,
    }
    optional = {
        "jobTitle": basics.label,
        "description": basics.summary,
        "url": safe_url(basics.url),
        "email": basics.email,
        "telephone": basics.phone,
        "image": safe_url(basics.image),
    }
    data.update({key: value for key, value in optional.items() if value})
    if basics.location:
        address = {
            "@type": "PostalAddress",
            "addressLocality": basics.location.city,
            "addressRegion": basics.location.region,
            "addressCountry": basics.location.countryCode,
            "postalCode": basics.location.postalCode,
            "streetAddress": basics.location.address,
        }
        data["address"] = {key: value for key, value in address.items() if value}
    same_as = [url for profile in basics.profiles if (url := safe_url(profile.url))]
    if same_as:
        data["sameAs"] = same_as
    knows = [kw for skill in resume.skills for kw in skill.keywords]
    if knows:
        data["knowsAbout"] = knows
    # Current positions only: schema.org has no property for past employers.
    current = [
        {
            "@type": "Organization",
            "name": job.name,
            **({"url": url} if (url := safe_url(job.url)) else {}),
        }
        for job in resume.work
        if job.name and not job.endDate
    ]
    if current:
        data["worksFor"] = current
    return data


def jsonld_script(data: dict[str, Any]) -> Markup:
    """Serialize JSON-LD so it cannot close its ``<script>`` element early."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    for char, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        text = text.replace(char, escape)
    return Markup(text)


def render_html(resume: Resume, request: RenderRequest, lang: str = "en") -> str:
    """Return the CV as a complete HTML document."""
    theme = request.resolved_theme()
    templates = request.options.templates
    styles = (
        environment(templates, autoescape=False).get_template("styles.css.j2").render(theme=theme)
    )
    page = environment(templates, autoescape=True).get_template("base.html.j2")
    return page.render(
        resume=resume,
        head=view.header(resume),
        sections=view.sections(resume, request.options),
        theme=theme,
        styles=Markup(styles),
        jsonld=jsonld_script(person_jsonld(resume)),
        lang=lang,
        version=__version__,
    )


class HtmlGenerator(Generator):
    """A self-contained web page (``.html``)."""

    name = "html"
    extension = "html"
    description = "A self-contained, printable web page styled by the design system."

    def render(self, resume: Resume, request: RenderRequest) -> bytes:
        """Render the page as UTF-8."""
        return render_html(resume, request).encode("utf-8")

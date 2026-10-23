"""The ``web`` adapter: any page, read through a declarative profile."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import Field, ValidationError

from cv_gen.adapters.base import Adapter, AdapterContext, AdapterOptions
from cv_gen.adapters.web.engine import parse_html, run_profile
from cv_gen.adapters.web.fetch import DEFAULT_TIMEOUT, read_text
from cv_gen.adapters.web.jsonld import find_person, person_to_basics
from cv_gen.adapters.web.profile import Profile, load_profile
from cv_gen.errors import CvGenError, from_validation
from cv_gen.merge import deep_merge
from cv_gen.model import Resume, prune


class WebOptions(AdapterOptions):
    """Options for the web adapter."""

    profile: Path | None = Field(
        default=None,
        description="The extraction profile (YAML); optional when the adapter ships one.",
    )
    url: str | None = Field(default=None, description="The page to fetch; overrides the profile's.")
    path: Path | None = Field(
        default=None, description="Read a saved copy of the page from disk instead of fetching."
    )
    base_url: str | None = Field(
        default=None,
        description="URL relative links resolve against; defaults to the page URL.",
    )
    timeout: float = Field(default=DEFAULT_TIMEOUT, gt=0, description="Seconds to wait.")
    user_agent: str | None = None


class WebAdapter(Adapter):
    """Extracts a CV from a web page using an extraction profile.

    Subclass it to ship a ready-made profile with a plugin: set ``default_profile`` and
    the ``profile`` option becomes optional for that adapter.
    """

    name = "web"
    description = "Any web page (URL or saved file), read through a YAML extraction profile."
    Options = WebOptions
    default_profile: ClassVar[Path | None] = None
    """A profile shipped with a subclass, used when the ``profile`` option is not set."""

    def __init__(self) -> None:
        """Start with no source read yet."""
        self.source: str | None = None

    def load(self, options: WebOptions, ctx: AdapterContext) -> Profile:
        """Load the profile the options name, or the adapter's own default profile."""
        if options.profile is not None:
            return load_profile(ctx.resolve(options.profile))
        if self.default_profile is not None:
            return load_profile(self.default_profile)
        raise CvGenError(f"the {self.name} adapter needs a profile option")

    def extract(self, options: WebOptions, ctx: AdapterContext) -> Resume:
        """Fetch or read the page, apply JSON-LD and the profile, and validate the result."""
        profile = self.load(options, ctx)
        url = options.url or profile.url
        path = ctx.resolve(options.path) if options.path else None
        if path is None and url is None:
            raise CvGenError(
                "the web adapter needs a page: set the url or path option, or url in the profile"
            )
        html = read_text(
            url=None if path else url,
            path=path,
            timeout=options.timeout,
            user_agent=options.user_agent,
        )
        self.source = str(path) if path else url
        base_url = options.base_url or url
        data: dict = {}
        if profile.jsonld:
            person = find_person(parse_html(html, []))
            if person:
                data = {"basics": person_to_basics(person)}
        # Explicit profile fields override the JSON-LD baseline field by field.
        data = deep_merge(data, run_profile(profile, html, base_url))
        try:
            return Resume.from_data(prune(data))
        except ValidationError as error:
            raise from_validation(error, f"data extracted from {path or url}") from error

    def describe_source(self, options: WebOptions) -> str | None:
        """Report the saved file when one was read, else the URL that was fetched."""
        return self.source

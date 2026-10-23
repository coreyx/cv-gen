"""An example cv-gen adapter: a small TOML profile format, mapped to the standard model.

Copy this package to write an adapter for your own source. Everything an adapter
needs is here:

1. An options model (``TomlProfileOptions``): the settings a config may pass it.
2. An ``Adapter`` subclass with a ``name``, a ``description`` and ``extract()``.
3. An entry point in ``pyproject.toml`` so ``cv-gen`` finds it once installed.

``extract()`` reads the source and returns a ``Resume``. Build plain data in the
model's shape (see ``docs/model.md``) and let ``Resume.from_data`` validate it: a
mistake surfaces as a clear error naming the field, not as a broken CV later.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from cv_gen.adapters import Adapter, AdapterContext, AdapterOptions, Resume
from cv_gen.errors import CvGenError

__all__ = ["TomlProfileAdapter", "TomlProfileOptions"]

# Words the source format uses for "still there"; the model leaves endDate out instead.
OPEN_ENDED = {"present", "now", "current", ""}


class TomlProfileOptions(AdapterOptions):
    """Options for the example adapter. Unknown options are rejected automatically."""

    path: Path
    """The TOML profile to read; relative paths resolve against the config's folder."""

    include_links: bool = True
    """Whether ``person.links`` become profiles (turn off for a CV without social links)."""


def _profile_from_link(url: str) -> dict[str, str]:
    """Name a link's network after its host: ``github.com`` becomes ``Github``."""
    host = url.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")
    return {"network": host.split(".")[0].capitalize(), "url": url}


class TomlProfileAdapter(Adapter):
    """Reads the example TOML profile format (see ``sample-profile.toml``)."""

    name = "example-toml"
    description = "Example adapter: a small TOML profile format (copy it to write your own)."
    Options = TomlProfileOptions

    def extract(self, options: TomlProfileOptions, ctx: AdapterContext) -> Resume:
        """Read the TOML file and map it onto the standard model."""
        path = ctx.resolve(options.path)
        try:
            source = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            # CvGenError is the "expected failure" type: the CLI prints it on one line.
            raise CvGenError(f"no such profile: {path}") from error
        except tomllib.TOMLDecodeError as error:
            raise CvGenError(f"{path} is not valid TOML: {error}") from error
        return Resume.from_data(self.to_model(source, options))

    def to_model(self, source: dict[str, Any], options: TomlProfileOptions) -> dict[str, Any]:
        """Map the source's shape onto the model's (kept separate so it is easy to test)."""
        person = source.get("person", {})
        basics: dict[str, Any] = {
            "name": person.get("name"),
            "label": person.get("title"),
            "email": person.get("email"),
            "summary": person.get("about"),
            "location": {"city": person.get("city"), "countryCode": person.get("country")},
        }
        if options.include_links:
            basics["profiles"] = [_profile_from_link(url) for url in person.get("links", [])]
        work = [
            {
                "name": job.get("company"),
                "position": job.get("role"),
                "startDate": job.get("from"),
                # Leave endDate out for an open-ended job; None is pruned by the model.
                "endDate": None if str(job.get("to", "")).lower() in OPEN_ENDED else job["to"],
                "highlights": job.get("did", []),
            }
            for job in source.get("job", [])
        ]
        skills = [
            {"name": group, "keywords": keywords}
            for group, keywords in source.get("skills", {}).items()
        ]
        return {"basics": basics, "work": work, "skills": skills}

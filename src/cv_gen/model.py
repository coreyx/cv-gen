"""The standard resume model every adapter produces and every generator consumes.

The model is a superset of the JSON Resume 1.0 schema (https://jsonresume.org/schema):
every standard field keeps its JSON Resume name, so a cv-gen JSON file is a valid
JSON Resume document. The extensions are ``basics.headline``, ``periods`` and ``tags``
on work and project entries, ``meta.sources``, and free-form custom ``sections``.

Every model allows unknown keys (``extra="allow"``) so data written by other JSON
Resume tools survives a round trip; generators simply ignore what they do not know.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

# ISO 8601 partial dates, as JSON Resume uses them: "2021", "2021-04" or "2021-04-15".
PARTIAL_DATE_PATTERN = r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$"

PartialDate = Annotated[str, StringConstraints(pattern=PARTIAL_DATE_PATTERN)]
"""A year, year-month or full date in ISO 8601 form."""

# Section ids generators already know; a custom section may not reuse one.
BUILTIN_SECTION_IDS = (
    "summary",
    "work",
    "projects",
    "skills",
    "education",
    "certificates",
    "awards",
    "publications",
    "volunteer",
    "languages",
    "interests",
    "references",
)


class Node(BaseModel):
    """Base for every model part: keeps unknown keys and accepts field names or aliases."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Location(Node):
    """Where a person or position is based."""

    address: str | None = None
    postalCode: str | None = None
    city: str | None = None
    countryCode: str | None = None
    region: str | None = None


class Profile(Node):
    """An account on another network, such as GitHub or LinkedIn."""

    network: str | None = None
    username: str | None = None
    url: str | None = None


class Basics(Node):
    """Identity, contact details and the short pitch at the top of a CV."""

    name: str | None = None
    label: str | None = None
    headline: str | None = Field(
        default=None, description="Extension: a one-line tagline, separate from the job label."
    )
    image: str | None = None
    email: str | None = None
    phone: str | None = None
    url: str | None = None
    summary: str | None = None
    location: Location | None = None
    profiles: list[Profile] = Field(default_factory=list)


class Period(Node):
    """One continuous stretch of time; an absent end date means "present"."""

    startDate: PartialDate | None = None
    endDate: PartialDate | None = None


class Work(Node):
    """A job, company or engagement."""

    name: str | None = None
    position: str | None = None
    url: str | None = None
    location: str | None = None
    description: str | None = None
    startDate: PartialDate | None = None
    endDate: PartialDate | None = None
    periods: list[Period] = Field(
        default_factory=list,
        description="Extension: separate stretches at the same organization, oldest first.",
    )
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)
    tags: list[str] = Field(
        default_factory=list, description="Extension: free-form labels, e.g. founder or agency."
    )


class Volunteer(Node):
    """Unpaid or community work."""

    organization: str | None = None
    position: str | None = None
    url: str | None = None
    startDate: PartialDate | None = None
    endDate: PartialDate | None = None
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)


class Education(Node):
    """A school, degree or course of study."""

    institution: str | None = None
    url: str | None = None
    area: str | None = None
    studyType: str | None = None
    startDate: PartialDate | None = None
    endDate: PartialDate | None = None
    score: str | None = None
    courses: list[str] = Field(default_factory=list)


class Award(Node):
    """A prize or recognition."""

    title: str | None = None
    date: PartialDate | None = None
    awarder: str | None = None
    summary: str | None = None


class Certificate(Node):
    """A certification."""

    name: str | None = None
    date: PartialDate | None = None
    url: str | None = None
    issuer: str | None = None


class Publication(Node):
    """An article, paper, book or talk."""

    name: str | None = None
    publisher: str | None = None
    releaseDate: PartialDate | None = None
    url: str | None = None
    summary: str | None = None


class Skill(Node):
    """A skill or a group of related skills (``keywords``)."""

    name: str | None = None
    level: str | None = None
    keywords: list[str] = Field(default_factory=list)


class Language(Node):
    """A spoken language."""

    language: str | None = None
    fluency: str | None = None


class Interest(Node):
    """A personal interest."""

    name: str | None = None
    keywords: list[str] = Field(default_factory=list)


class Reference(Node):
    """A quote from a reference."""

    name: str | None = None
    reference: str | None = None


class Project(Node):
    """A project, product or piece of work."""

    name: str | None = None
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    startDate: PartialDate | None = None
    endDate: PartialDate | None = None
    periods: list[Period] = Field(default_factory=list, description="Extension.")
    url: str | None = None
    roles: list[str] = Field(default_factory=list)
    entity: str | None = None
    type: str | None = None
    tags: list[str] = Field(default_factory=list, description="Extension.")


class SectionItem(Node):
    """One entry in a custom section: a titled line, a short story, a link."""

    title: str | None = None
    subtitle: str | None = None
    text: str | None = None
    url: str | None = None
    date: PartialDate | None = None


class Section(Node):
    """Extension: a free-form section for content JSON Resume has no place for.

    Examples: a "Current focus" list or an "Origin story". Generators render it with
    its own title, wherever the render options place its ``id``.
    """

    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]*$")]
    title: str
    updated: PartialDate | None = None
    paragraphs: list[str] = Field(default_factory=list)
    items: list[SectionItem] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _not_builtin(cls, value: str) -> str:
        """Reject ids that would collide with a built-in section in render options."""
        if value in BUILTIN_SECTION_IDS:
            raise ValueError(f"'{value}' is a built-in section id; choose another")
        return value


class SourceRecord(Node):
    """Extension: which adapter produced part of this document, and from where."""

    adapter: str
    location: str | None = None


class Meta(Node):
    """Document metadata."""

    canonical: str | None = None
    version: str | None = None
    lastModified: str | None = None
    sources: list[SourceRecord] = Field(default_factory=list, description="Extension.")


class Resume(Node):
    """A complete CV in the standard model."""

    schema_: str | None = Field(default=None, alias="$schema")
    basics: Basics = Field(default_factory=Basics)
    work: list[Work] = Field(default_factory=list)
    volunteer: list[Volunteer] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    interests: list[Interest] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    sections: list[Section] = Field(
        default_factory=list, description="Extension: custom sections, in source order."
    )
    meta: Meta | None = None

    @field_validator("sections")
    @classmethod
    def _unique_section_ids(cls, sections: list[Section]) -> list[Section]:
        """Render options address sections by id, so ids must not repeat."""
        seen: set[str] = set()
        for section in sections:
            if section.id in seen:
                raise ValueError(f"duplicate section id '{section.id}'")
            seen.add(section.id)
        return sections

    def to_data(self) -> dict[str, Any]:
        """Return the document as plain JSON-ready data, leaving out empty values."""
        return prune(self.model_dump(mode="json", by_alias=True, exclude_none=True))

    def to_json(self, indent: int = 2) -> str:
        """Return the document as JSON text."""
        return json.dumps(self.to_data(), indent=indent, ensure_ascii=False) + "\n"

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> Resume:
        """Validate plain data (a parsed JSON or YAML document) into a Resume."""
        return cls.model_validate(data)

    @classmethod
    def load(cls, path: Path) -> Resume:
        """Read a JSON or YAML document from ``path`` and validate it."""
        return cls.from_data(read_document(path))


def read_document(path: Path) -> dict[str, Any]:
    """Parse a JSON or YAML file into a mapping, choosing the parser by extension.

    YAML is read with ``safe_load``, so a document cannot construct Python objects.
    """
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping at the top level")
    return data


def prune(value: Any) -> Any:
    """Recursively drop empty strings, lists and mappings, so absence is uniform."""
    if isinstance(value, dict):
        pruned = {key: prune(item) for key, item in value.items()}
        return {key: item for key, item in pruned.items() if not _is_empty(item)}
    if isinstance(value, list):
        pruned_list = [prune(item) for item in value]
        return [item for item in pruned_list if not _is_empty(item)]
    if isinstance(value, str):
        return value.strip()
    return value


def _is_empty(value: Any) -> bool:
    """Tell whether a pruned value carries no information."""
    return value is None or value == "" or value == [] or value == {}


def json_schema() -> dict[str, Any]:
    """Return the JSON Schema of the standard model, by alias (``$schema``)."""
    return Resume.model_json_schema(by_alias=True)

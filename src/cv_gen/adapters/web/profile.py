"""The extraction profile: a declarative map from a page's structure to the model.

See ``docs/web-profiles.md`` for the full guide. In short, ``fields`` maps a target
path (``basics.headline``, ``work``) to a field spec, or to a list of specs whose
results are concatenated. A spec with ``each`` and ``fields`` builds a list of records.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from cv_gen.errors import CvGenError, from_validation


class FieldSpec(BaseModel):
    """How to read one value (or one list of records) from the current scope."""

    model_config = ConfigDict(extra="forbid")

    selector: str | None = Field(
        default=None, description="CSS selector relative to the scope; omit for the scope itself."
    )
    attr: str | None = Field(default=None, description="Read this attribute instead of the text.")
    extract: Literal["text", "attr", "json", "html"] | None = Field(
        default=None,
        description="text (default), attr, json (parse attr or text), html (inner HTML).",
    )
    all: bool = Field(default=False, description="Return a list of every match.")
    drop: list[str] = Field(
        default_factory=list, description="Selectors removed from a copy of the match first."
    )
    transforms: list[str | dict[str, Any]] = Field(default_factory=list)
    required: bool = Field(default=False, description="Fail when the selector matches nothing.")
    value: Any = Field(default=None, description="A constant instead of anything on the page.")
    default: Any = Field(default=None, description="Used when the selector matches nothing.")
    each: str | None = Field(
        default=None, description="Selector for repeated elements; builds one record per match."
    )
    fields: dict[str, FieldSpec | list[FieldSpec]] | None = Field(
        default=None, description="Fields of each record (with each) or of one nested object."
    )

    @model_validator(mode="after")
    def _consistent(self) -> FieldSpec:
        """Catch combinations that cannot mean anything."""
        if self.each and not self.fields:
            raise ValueError("'each' needs 'fields' describing each record")
        if self.extract == "attr" and not self.attr:
            raise ValueError("extract: attr needs an 'attr' name")
        return self

    @property
    def mode(self) -> str:
        """The extraction mode, defaulting to ``attr`` when an attribute is named."""
        return self.extract or ("attr" if self.attr else "text")

    @property
    def is_constant(self) -> bool:
        """Whether the spec gives a constant ``value`` (an explicit null counts)."""
        return "value" in self.model_fields_set


FieldValue = FieldSpec | list[FieldSpec]


class Profile(BaseModel):
    """A whole extraction profile for one kind of page."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    url: str | None = Field(default=None, description="The page's address, when none is given.")
    jsonld: bool = Field(default=True, description="Read a schema.org Person into basics first.")
    exclude: list[str] = Field(
        default_factory=list, description="Selectors removed from the page before extraction."
    )
    transforms_module: str | list[str] | None = None
    fields: dict[str, FieldValue] = Field(default_factory=dict)

    @property
    def transforms_modules(self) -> list[str]:
        """The transforms modules to import, as a list."""
        if self.transforms_module is None:
            return []
        if isinstance(self.transforms_module, str):
            return [self.transforms_module]
        return list(self.transforms_module)


def load_profile(path: Path) -> Profile:
    """Read and validate a profile file (YAML or JSON)."""
    if not path.is_file():
        raise CvGenError(f"no such profile: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except yaml.YAMLError as error:
        raise CvGenError(f"profile {path} is not valid YAML: {error}") from error
    try:
        return Profile.model_validate(data)
    except ValidationError as error:
        raise from_validation(error, f"profile {path}", "see docs/web-profiles.md") from error

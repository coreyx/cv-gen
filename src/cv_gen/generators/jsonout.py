"""JSON output: the standard model itself, a valid JSON Resume document."""

from __future__ import annotations

from cv_gen.generators.base import Generator, RenderRequest
from cv_gen.model import Resume


class JsonGenerator(Generator):
    """JSON (``.json``) in the standard model.

    Render options do not apply: the JSON is the complete data, for other tools
    (JSON Resume themes, scripts, ``cv-gen render``) to work from.
    """

    name = "json"
    extension = "json"
    description = "The standard model as JSON; a valid JSON Resume document."

    def render(self, resume: Resume, request: RenderRequest) -> bytes:
        """Render the model as indented UTF-8 JSON."""
        return resume.to_json().encode("utf-8")

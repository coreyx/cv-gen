"""Output generators: one per format, all reading the same section view."""

from cv_gen.generators.base import (
    Generator,
    RenderRequest,
    canonical_format,
    get_generator,
    list_formats,
)

__all__ = ["Generator", "RenderRequest", "canonical_format", "get_generator", "list_formats"]

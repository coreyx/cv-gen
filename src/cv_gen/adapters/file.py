"""The ``file`` adapter: a JSON or YAML document already in the standard model."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from cv_gen.adapters.base import Adapter, AdapterContext, AdapterOptions
from cv_gen.errors import CvGenError, from_validation
from cv_gen.model import Resume, read_document


class FileOptions(AdapterOptions):
    """Options for the file adapter."""

    path: Path
    """The JSON (``.json``) or YAML (any other extension) document to read."""


class FileAdapter(Adapter):
    """Reads a JSON Resume, or any document in the cv-gen model, from disk.

    It is also the overlay adapter: a small private YAML file with only the fields a
    public source lacks (an email, education) merged after the main source.
    """

    name = "file"
    description = "A JSON or YAML file in the standard model (JSON Resume included)."
    Options = FileOptions

    def extract(self, options: FileOptions, ctx: AdapterContext) -> Resume:
        """Read and validate the file named by ``options.path``."""
        path = ctx.resolve(options.path)
        if not path.is_file():
            raise CvGenError(f"no such file: {path}")
        try:
            return Resume.from_data(read_document(path))
        except ValidationError as error:
            raise from_validation(error, str(path)) from error
        except ValueError as error:  # bad JSON/YAML, or a non-mapping document
            raise CvGenError(f"cannot read {path}: {error}") from error

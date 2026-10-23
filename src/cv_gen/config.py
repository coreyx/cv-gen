"""The configuration file: sources, plugins, outputs, design, render options and guards.

The real file (``cv-gen.config.yaml``) is personal and git-ignored; the repository
commits ``cv-gen.config.example.yaml`` to copy from. Relative paths in the file are
resolved against the file's own folder, so a build works from any working directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from cv_gen.errors import CvGenError, from_validation
from cv_gen.merge import MergeMode

DEFAULT_CONFIG_NAME = "cv-gen.config.yaml"
EXAMPLE_CONFIG_NAME = "cv-gen.config.example.yaml"
DEFAULT_FORMATS = ["md", "txt", "docx", "json", "html"]
PdfEngineName = Literal["auto", "chrome", "playwright", "weasyprint"]


class Strict(BaseModel):
    """Base for configuration sections: unknown keys are mistakes, so they are errors."""

    model_config = ConfigDict(extra="forbid")


class SourceConfig(Strict):
    """One source: which adapter reads it, with what options, and how it merges."""

    adapter: str
    options: dict[str, Any] = Field(default_factory=dict)
    merge: MergeMode = "replace"


class PluginsConfig(Strict):
    """Where to find plugin modules that are not installed as packages."""

    paths: list[Path] = Field(default_factory=list)


class OutputConfig(Strict):
    """Where outputs go and which formats are built."""

    dir: Path = Path("out")
    basename: str | None = None
    formats: list[str] = Field(default_factory=lambda: list(DEFAULT_FORMATS))


class DesignRef(Strict):
    """A design system by path or URL, optionally pinned to a SHA-256 of its content."""

    ref: str
    sha256: str | None = None


class RenderOptions(Strict):
    """Options every generator honors."""

    sections: list[str] | None = Field(
        default=None, description="Section ids to include, in order. Default: every section."
    )
    section_titles: dict[str, str] = Field(default_factory=dict)
    text_width: int = Field(default=80, ge=40, le=200)
    templates: Path | None = None


class PdfConfig(Strict):
    """Which PDF engine to use."""

    engine: PdfEngineName = "auto"


class GuardConfig(Strict):
    """Words that must never appear in any output."""

    forbidden_terms: list[str] = Field(default_factory=list)


class Config(Strict):
    """A whole configuration file, with every relative path already resolved."""

    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    sources: list[SourceConfig] = Field(default_factory=list)
    output: OutputConfig = Field(default_factory=OutputConfig)
    design: DesignRef | None = None
    render: RenderOptions = Field(default_factory=RenderOptions)
    pdf: PdfConfig = Field(default_factory=PdfConfig)
    guard: GuardConfig = Field(default_factory=GuardConfig)
    base_dir: Path = Field(default_factory=Path.cwd, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _sugar(cls, data: Any) -> Any:
        """Accept ``source:`` for a single source and a plain string for ``design``."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "source" in data:
            if "sources" in data:
                raise ValueError("use either 'source' or 'sources', not both")
            data["sources"] = [data.pop("source")]
        if isinstance(data.get("design"), str):
            data["design"] = {"ref": data["design"]}
        return data

    def resolve(self, path: Path | str) -> Path:
        """Resolve ``path`` against the configuration file's folder."""
        path = Path(path).expanduser()
        return path if path.is_absolute() else (self.base_dir / path).resolve()


def is_url(ref: str) -> bool:
    """Tell whether a reference is an ``http(s)`` URL rather than a file path."""
    return ref.startswith(("http://", "https://"))


def load_config(path: Path | None = None, *, required: bool = True) -> Config:
    """Read and validate a configuration file, resolving its relative paths.

    With no ``path``, reads ``cv-gen.config.yaml`` in the working directory. When the
    file does not exist, raises with a pointer to the example file, or, if ``required``
    is false, returns the defaults rooted at the working directory.
    """
    explicit = path is not None
    path = Path(path) if path is not None else Path.cwd() / DEFAULT_CONFIG_NAME
    if not path.is_file():
        if not required and not explicit:
            return Config()
        raise CvGenError(
            f"no configuration file at {path}",
            f"copy {EXAMPLE_CONFIG_NAME} to {DEFAULT_CONFIG_NAME} and edit it, "
            "pass --config, or name a source with --adapter",
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except yaml.YAMLError as error:
        raise CvGenError(f"{path} is not valid YAML: {error}") from error
    if not isinstance(data, dict):
        raise CvGenError(f"{path} must contain a mapping at the top level")
    try:
        config = Config.model_validate({**data, "base_dir": path.parent.resolve()})
    except ValidationError as error:
        raise from_validation(error, str(path), f"see {EXAMPLE_CONFIG_NAME}") from error
    return _resolve_paths(config)


def _resolve_paths(config: Config) -> Config:
    """Make every path-valued setting absolute, relative to the config file."""
    config.plugins.paths = [config.resolve(p) for p in config.plugins.paths]
    config.output.dir = config.resolve(config.output.dir)
    if config.render.templates is not None:
        config.render.templates = config.resolve(config.render.templates)
    if config.design is not None and not is_url(config.design.ref):
        config.design.ref = str(config.resolve(config.design.ref))
    return config

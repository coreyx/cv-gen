"""The adapter contract: what every source adapter provides.

An adapter reads one kind of source and returns the standard :class:`~cv_gen.model.Resume`.
It declares its options as a Pydantic model so they are validated, documented and
exported as JSON Schema (``cv-gen adapters show <name>``) without extra code.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from cv_gen.model import Resume


class AdapterOptions(BaseModel):
    """Base class for an adapter's options. Unknown options are errors, not ignored."""

    model_config = ConfigDict(extra="forbid")


@dataclass
class AdapterContext:
    """What an adapter knows about the run it is part of.

    ``base_dir`` is the folder relative paths are resolved against: the configuration
    file's folder, or the working directory when the adapter is named on the command line.
    """

    base_dir: Path = field(default_factory=Path.cwd)

    def resolve(self, path: str | Path) -> Path:
        """Resolve ``path`` against ``base_dir`` unless it is already absolute."""
        path = Path(path).expanduser()
        return path if path.is_absolute() else (self.base_dir / path).resolve()


class Adapter(abc.ABC):
    """A source adapter. Subclass it, set the class attributes and implement ``extract``.

    Example::

        class MyOptions(AdapterOptions):
            path: Path

        class MyAdapter(Adapter):
            name = "my-format"
            description = "Reads my format."
            Options = MyOptions

            def extract(self, options: MyOptions, ctx: AdapterContext) -> Resume:
                data = parse(ctx.resolve(options.path))
                return Resume.from_data(data)
    """

    name: ClassVar[str]
    """The name used to select the adapter in configs and on the command line."""

    description: ClassVar[str] = ""
    """One line shown by ``cv-gen adapters list``."""

    Options: ClassVar[type[AdapterOptions]] = AdapterOptions
    """The options model; its fields are what a config's ``options:`` may contain."""

    @abc.abstractmethod
    def extract(self, options: Any, ctx: AdapterContext) -> Resume:
        """Read the source described by ``options`` and return it in the standard model."""

    def describe_source(self, options: Any) -> str | None:
        """Return where the data came from (a URL or path) for ``meta.sources``.

        The default looks for the common option names ``url`` and ``path``.
        """
        for attr in ("url", "path"):
            value = getattr(options, attr, None)
            if value:
                return str(value)
        return None


def options_schema(adapter: type[Adapter]) -> dict[str, Any]:
    """Return the JSON Schema of an adapter's options."""
    return adapter.Options.model_json_schema()


__all__ = ["Adapter", "AdapterContext", "AdapterOptions", "options_schema"]

"""The stages the CLI runs: extract sources into one Resume, render it, write the files."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import ValidationError

from cv_gen.adapters.base import AdapterContext
from cv_gen.adapters.registry import add_plugin_paths, resolve_adapter
from cv_gen.config import SourceConfig
from cv_gen.errors import CvGenError, from_validation
from cv_gen.merge import deep_merge
from cv_gen.model import Resume


def run_source(source: SourceConfig, base_dir: Path) -> tuple[Resume, str | None]:
    """Run one source's adapter; return its Resume and where the data came from."""
    adapter_cls = resolve_adapter(source.adapter)
    try:
        options = adapter_cls.Options.model_validate(source.options)
    except ValidationError as error:
        raise from_validation(
            error,
            f"options for adapter '{source.adapter}'",
            f"run: cv-gen adapters show {source.adapter}",
        ) from error
    adapter = adapter_cls()
    resume = adapter.extract(options, AdapterContext(base_dir=base_dir))
    if not isinstance(resume, Resume):
        raise CvGenError(f"adapter '{source.adapter}' returned {type(resume).__name__}, not Resume")
    return resume, adapter.describe_source(options)


def extract(
    sources: Sequence[SourceConfig], base_dir: Path, plugin_paths: Iterable[Path] = ()
) -> Resume:
    """Run every source in order and merge the results into one validated Resume.

    ``meta.sources`` of the result lists each adapter and location, in order.
    """
    add_plugin_paths(plugin_paths)
    if not sources:
        raise CvGenError(
            "no sources to extract from",
            "add a source to the configuration, or pass --adapter",
        )
    merged: dict = {}
    records = []
    for source in sources:
        resume, location = run_source(source, base_dir)
        merged = deep_merge(merged, resume.to_data(), source.merge)
        records.append({"adapter": source.adapter, "location": location})
    merged.setdefault("meta", {})["sources"] = [
        {key: value for key, value in record.items() if value is not None} for record in records
    ]
    try:
        return Resume.from_data(merged)
    except ValidationError as error:  # merging can break a rule, e.g. duplicate section ids
        raise from_validation(error, "the merged sources") from error

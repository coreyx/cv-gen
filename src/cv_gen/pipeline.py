"""The stages the CLI runs: extract sources into one Resume, render it, write the files."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from cv_gen.adapters.base import AdapterContext
from cv_gen.adapters.registry import add_plugin_paths, resolve_adapter
from cv_gen.config import SourceConfig
from cv_gen.errors import CvGenError, from_validation
from cv_gen.generators import view
from cv_gen.generators.base import RenderRequest, canonical_format, get_generator
from cv_gen.guard import violations
from cv_gen.merge import deep_merge
from cv_gen.model import Resume


@dataclass
class Output:
    """One rendered format: its file name and bytes, or the error that stopped it."""

    format: str
    filename: str
    content: bytes | None = None
    error: CvGenError | None = None


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


def render(
    resume: Resume, formats: Iterable[str], request: RenderRequest, basename: str
) -> list[Output]:
    """Render every requested format in memory.

    A format that fails (most often PDF, when no engine is installed) records its
    error and the others still render; nothing is written here.
    """
    # Bad render options would fail every format the same way; fail once, up front.
    view.sections(resume, request.options)
    outputs: list[Output] = []
    for name in dict.fromkeys(canonical_format(f) for f in formats):
        generator = get_generator(name)
        output = Output(name, f"{basename}.{generator.extension}")
        try:
            output.content = generator.render(resume, request)
        except CvGenError as error:
            output.error = error
        outputs.append(output)
    return outputs


def output_text(output: Output, resume: Resume, request: RenderRequest) -> str:
    """Return the text a reader of this output would see, for the guard."""
    if output.content is None:
        return ""
    if output.format == "docx":
        from cv_gen.generators.docx import docx_text

        return docx_text(output.content)
    if output.format == "pdf":
        # A PDF is printed from the HTML page, so the page's text is what it shows.
        from cv_gen.generators.html import render_html

        return render_html(resume, request)
    return output.content.decode("utf-8")


def guard(
    outputs: Sequence[Output], terms: Sequence[str], resume: Resume, request: RenderRequest
) -> None:
    """Refuse the whole build when any output contains a forbidden term."""
    if not terms:
        return
    texts = {output.format: output_text(output, resume, request) for output in outputs}
    found = violations(texts, terms)
    if found:
        detail = "; ".join(f"{fmt}: {', '.join(hits)}" for fmt, hits in found.items())
        raise CvGenError(
            f"forbidden terms found, so nothing was written ({detail})",
            "remove them from the source, or drop a section with render.sections",
        )


def write(outputs: Sequence[Output], out_dir: Path) -> list[Path]:
    """Write every successfully rendered output into ``out_dir``; return the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for output in outputs:
        if output.content is not None:
            path = out_dir / output.filename
            path.write_bytes(output.content)
            written.append(path)
    return written


@dataclass
class BuildResult:
    """What a build wrote and which formats failed."""

    written: list[Path]
    failures: list[Output]


def build(
    resume: Resume,
    formats: Iterable[str],
    request: RenderRequest,
    out_dir: Path,
    basename: str | None = None,
    forbidden_terms: Sequence[str] = (),
) -> BuildResult:
    """Render, guard, then write: a guard failure writes nothing at all."""
    outputs = render(resume, formats, request, view.basename_for(resume, basename))
    guard(outputs, forbidden_terms, resume, request)
    written = write(outputs, out_dir)
    return BuildResult(written, [output for output in outputs if output.error is not None])

"""The ``cv-gen`` command line: a thin layer over the pipeline stages."""

import functools
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, TypeVar

import typer
import yaml
from pydantic import ValidationError

from cv_gen import __version__, console
from cv_gen.adapters.base import options_schema
from cv_gen.adapters.registry import add_plugin_paths, available_adapters, resolve_adapter
from cv_gen.config import DEFAULT_CONFIG_NAME, Config, PdfEngineName, SourceConfig, load_config
from cv_gen.design.theme import load_design
from cv_gen.errors import CvGenError, from_validation
from cv_gen.generators.base import RenderRequest, list_formats
from cv_gen.model import Resume, json_schema, read_document
from cv_gen.pipeline import build as build_outputs
from cv_gen.pipeline import extract as extract_sources

app = typer.Typer(
    name="cv-gen",
    help="Generate CVs from any source: adapters in, Word/Markdown/text/JSON/HTML/PDF out.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)
adapters_app = typer.Typer(help="List and describe source adapters.", no_args_is_help=True)
design_app = typer.Typer(help="Check design systems (DTCG design tokens).", no_args_is_help=True)
app.add_typer(adapters_app, name="adapters")
app.add_typer(design_app, name="design")

_state = {"debug": False}
PDF_ENGINES: tuple[str, ...] = PdfEngineName.__args__

ConfigOpt = Annotated[
    Path | None,
    typer.Option("--config", "-c", help=f"Configuration file. Default: ./{DEFAULT_CONFIG_NAME}."),
]
AdapterOpt = Annotated[
    str | None,
    typer.Option("--adapter", "-a", help="Use this adapter instead of the config's sources."),
]
OptionOpt = Annotated[
    list[str] | None,
    typer.Option("--option", "-o", help="Adapter option as key=value (repeatable)."),
]
PluginPathOpt = Annotated[
    list[Path] | None,
    typer.Option("--plugin-path", help="Folder to import plugin modules from (repeatable)."),
]
FormatOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--format", "-f", help="Output format (repeatable): md, txt, docx, json, html, pdf."
    ),
]
OutOpt = Annotated[Path | None, typer.Option("--out", help="Output folder.")]
DesignOpt = Annotated[
    str | None, typer.Option("--design", help="Design system: a DTCG tokens file or https URL.")
]
DesignShaOpt = Annotated[
    str | None,
    typer.Option("--design-sha256", help="Refuse the design unless its SHA-256 matches."),
]
PdfEngineOpt = Annotated[
    str | None, typer.Option("--pdf-engine", help="auto, chrome, playwright or weasyprint.")
]
BasenameOpt = Annotated[
    str | None, typer.Option("--basename", help="Output file name without extension.")
]


F = TypeVar("F", bound=Callable[..., Any])


def reports_errors(command: F) -> F:
    """Turn an expected failure into ``error:``/``hint:`` lines and exit code 1.

    With ``--debug`` the exception propagates, so its traceback is shown.
    """

    @functools.wraps(command)
    def run(*args: Any, **kwargs: Any) -> Any:
        try:
            return command(*args, **kwargs)
        except CvGenError as error:
            if _state["debug"]:
                raise
            warn(f"error: {error.message}")
            if error.hint:
                warn(f"hint: {error.hint}")
            raise typer.Exit(1) from None

    return run  # type: ignore[return-value]


def say(message: str) -> None:
    """Print a progress line to standard output."""
    typer.echo(message)


def warn(message: str) -> None:
    """Print a line to standard error."""
    typer.echo(message, err=True)


def parse_option(text: str) -> tuple[str, Any]:
    """Split ``key=value`` and read the value as a YAML scalar (``5`` is an int)."""
    key, sep, raw = text.partition("=")
    if not sep or not key.strip():
        raise CvGenError(f"--option {text!r} is not key=value")
    try:
        value = yaml.safe_load(raw) if raw else ""
    except yaml.YAMLError:
        value = raw
    if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
        value = raw  # dates and the like stay as written
    return key.strip(), value


def load_run_config(config_path: Path | None, adapter: str | None) -> Config:
    """Load the config, which may be absent only when a source is named on the command line."""
    return load_config(config_path, required=adapter is None)


def sources_for(
    config: Config, adapter: str | None, options: list[str] | None
) -> list[SourceConfig]:
    """Return the sources to extract: the command line's adapter, or the config's."""
    if adapter is None:
        if options:
            raise CvGenError("--option needs --adapter")
        return config.sources
    return [SourceConfig(adapter=adapter, options=dict(parse_option(o) for o in options or []))]


def run_extract(
    config: Config, adapter: str | None, options: list[str] | None, plugin_paths: list[Path] | None
) -> Resume:
    """Run the sources for a command, with command-line plugin paths first."""
    paths = [path.resolve() for path in plugin_paths or []] + config.plugins.paths
    # Command-line options are written relative to where the command runs.
    base = Path.cwd() if adapter is not None else config.base_dir
    return extract_sources(sources_for(config, adapter, options), base, paths)


def render_request(
    config: Config, design: str | None, design_sha: str | None, engine: str | None
) -> RenderRequest:
    """Build the render request from the config and command-line overrides."""
    if design:  # command line: relative to where the command runs
        theme = load_design(design, design_sha, Path.cwd())
    elif config.design:  # config: already resolved against the config's folder
        theme = load_design(config.design.ref, design_sha or config.design.sha256, config.base_dir)
    else:
        theme = None
    pdf_engine: Any = engine or config.pdf.engine
    if pdf_engine not in PDF_ENGINES:
        raise CvGenError(f"unknown PDF engine '{pdf_engine}'; engines: {', '.join(PDF_ENGINES)}")
    return RenderRequest(options=config.render, theme=theme, pdf_engine=pdf_engine)


def write_and_report(
    resume: Resume,
    config: Config,
    formats: list[str] | None,
    out: Path | None,
    request: RenderRequest,
    basename: str | None,
) -> None:
    """Build the outputs, print what was written, and fail if any format failed."""
    result = build_outputs(
        resume,
        formats or config.output.formats,
        request,
        out.resolve() if out else config.output.dir,
        basename or config.output.basename,
        config.guard.forbidden_terms,
    )
    for path in result.written:
        say(f"wrote {path}")
    for failure in result.failures:
        assert failure.error is not None
        warn(f"error: {failure.format}: {failure.error.message}")
        if failure.error.hint:
            warn(f"hint: {failure.error.hint}")
    if result.failures:
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def root(
    debug: Annotated[bool, typer.Option("--debug", help="Show tracebacks for errors.")] = False,
    version: Annotated[bool, typer.Option("--version", help="Print the version and exit.")] = False,
) -> None:
    """Generate CVs from any source."""
    _state["debug"] = debug
    if version:
        say(f"cv-gen {__version__}")
        raise typer.Exit()


@app.command()
@reports_errors
def build(
    config_path: ConfigOpt = None,
    adapter: AdapterOpt = None,
    option: OptionOpt = None,
    plugin_path: PluginPathOpt = None,
    fmt: FormatOpt = None,
    out: OutOpt = None,
    design: DesignOpt = None,
    design_sha256: DesignShaOpt = None,
    pdf_engine: PdfEngineOpt = None,
    basename: BasenameOpt = None,
) -> None:
    """Extract from the sources and write every output format."""
    config = load_run_config(config_path, adapter)
    resume = run_extract(config, adapter, option, plugin_path)
    request = render_request(config, design, design_sha256, pdf_engine)
    write_and_report(resume, config, fmt, out, request, basename)


@app.command()
@reports_errors
def extract(
    config_path: ConfigOpt = None,
    adapter: AdapterOpt = None,
    option: OptionOpt = None,
    plugin_path: PluginPathOpt = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-O", help="Write the JSON here instead of stdout.")
    ] = None,
) -> None:
    """Run the source adapters and print the standard model as JSON."""
    config = load_run_config(config_path, adapter)
    resume = run_extract(config, adapter, option, plugin_path)
    if output is None:
        sys.stdout.write(resume.to_json())
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(resume.to_json(), encoding="utf-8")
        say(f"wrote {output.resolve()}")


@app.command()
@reports_errors
def render(
    resume_path: Annotated[Path, typer.Argument(help="A JSON or YAML file in the standard model.")],
    config_path: ConfigOpt = None,
    fmt: FormatOpt = None,
    out: OutOpt = None,
    design: DesignOpt = None,
    design_sha256: DesignShaOpt = None,
    pdf_engine: PdfEngineOpt = None,
    basename: BasenameOpt = None,
) -> None:
    """Render a standard-model file to output formats, without running any adapter."""
    config = load_config(config_path, required=config_path is not None)
    resume = load_resume(resume_path)
    request = render_request(config, design, design_sha256, pdf_engine)
    write_and_report(resume, config, fmt, out, request, basename)


def load_resume(path: Path) -> Resume:
    """Read and validate a standard-model file for a command."""
    if not path.is_file():
        raise CvGenError(f"no such file: {path}")
    try:
        return Resume.from_data(read_document(path))
    except ValidationError as error:
        raise from_validation(error, str(path)) from error
    except ValueError as error:
        raise CvGenError(f"cannot read {path}: {error}") from error


@app.command()
@reports_errors
def validate(
    resume_path: Annotated[Path, typer.Argument(help="A JSON or YAML file to check.")],
) -> None:
    """Check a file against the standard model."""
    resume = load_resume(resume_path)
    counts = f"{len(resume.work)} work entries, {len(resume.sections)} custom sections"
    say(f"{resume_path} is valid ({counts})")


@app.command()
@reports_errors
def schema(
    output: Annotated[
        Path | None, typer.Option("--output", "-O", help="Write here instead of stdout.")
    ] = None,
) -> None:
    """Print the JSON Schema of the standard model."""
    text = json.dumps(json_schema(), indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
    else:
        output.write_text(text, encoding="utf-8")
        say(f"wrote {output.resolve()}")


@app.command()
@reports_errors
def formats() -> None:
    """List the output formats."""
    for name, extension, description in list_formats():
        say(f"{name:<5} .{extension:<5} {description}")


@adapters_app.command("list")
@reports_errors
def adapters_list(config_path: ConfigOpt = None, plugin_path: PluginPathOpt = None) -> None:
    """List every adapter: built-ins and installed plugins."""
    config = load_config(config_path, required=False)
    add_plugin_paths([p.resolve() for p in plugin_path or []] + config.plugins.paths)
    for name, adapter in available_adapters().items():
        say(f"{name:<14} {adapter.description}")


@adapters_app.command("show")
@reports_errors
def adapters_show(
    name: Annotated[str, typer.Argument(help="An adapter name or module:Class reference.")],
    config_path: ConfigOpt = None,
    plugin_path: PluginPathOpt = None,
) -> None:
    """Describe an adapter and print its options as JSON Schema."""
    config = load_config(config_path, required=False)
    add_plugin_paths([p.resolve() for p in plugin_path or []] + config.plugins.paths)
    adapter = resolve_adapter(name)
    say(f"{name}: {adapter.description}")
    say("options (JSON Schema):")
    say(json.dumps(options_schema(adapter), indent=2))


@design_app.command("validate")
@reports_errors
def design_validate(
    ref: Annotated[str, typer.Argument(help="A DTCG tokens file or https URL.")],
    sha256: Annotated[str | None, typer.Option("--sha256", help="Expected SHA-256.")] = None,
) -> None:
    """Check a design system and show the values cv-gen will use."""
    theme = load_design(ref, sha256, Path.cwd())
    say(f"design system {theme.source} is valid")
    say(f"tokens used ({len(theme.supplied)}): {', '.join(theme.supplied) or 'none'}")
    if theme.ignored:
        say(f"tokens ignored ({len(theme.ignored)}): {', '.join(theme.ignored)}")
    if theme.custom_css:
        say("custom CSS: yes")
    for url in theme.font_imports:
        say(f"font import: {url}")
    say("resolved values:")
    for name, value in theme.css_values.items():
        marker = "*" if name in theme.supplied else " "
        say(f" {marker} {name:<20} {value}")


def main(argv: list[str] | None = None) -> None:
    """Run the command line (the ``cv-gen`` entry point)."""
    console.setup()
    app(args=argv, prog_name="cv-gen")

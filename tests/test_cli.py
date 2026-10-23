"""Tests for the command line (REQ-1, REQ-2, REQ-9, REQ-10, REQ-11)."""

import io
import json
import shutil
import sys
from pathlib import Path

import jsonschema
import pytest

from cv_gen import console
from cv_gen.cli import main, parse_option
from cv_gen.errors import CvGenError
from cv_gen.pdf import engines

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "examples" / "sample-resume.yaml"


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    """Run the CLI and return its exit code, stdout and stderr."""
    try:
        main(list(args))
        code = 0
    except SystemExit as exit_:
        code = exit_.code if isinstance(exit_.code, int) else 1
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def write_config(folder: Path, text: str) -> Path:
    """Write a config file into ``folder`` and return its path."""
    path = folder / "cv-gen.config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_help_lists_every_command(capsys) -> None:
    """AC 11.1: the help lists every command."""
    code, out, _ = run(capsys, "--help")
    assert code == 0
    for command in (
        "build",
        "extract",
        "render",
        "validate",
        "schema",
        "formats",
        "adapters",
        "design",
    ):
        assert command in out
    code, out, _ = run(capsys, "adapters", "--help")
    assert "list" in out and "show" in out
    code, out, _ = run(capsys, "--version")
    assert out.startswith("cv-gen ")
    code, out, _ = run(capsys, "formats")
    assert code == 0
    assert [line.split()[0] for line in out.splitlines()] == [
        "md",
        "txt",
        "docx",
        "json",
        "html",
        "pdf",
    ]


def test_render_writes_exactly_the_requested_files(capsys, tmp_path: Path) -> None:
    """AC 11.2: render with md and txt writes exactly those two files and prints both."""
    resume = tmp_path / "resume.json"
    resume.write_text(json.dumps({"basics": {"name": "Ada Lovelace"}}), encoding="utf-8")
    out = tmp_path / "out"
    code, stdout, _ = run(capsys, "render", str(resume), "-f", "md", "-f", "txt", "--out", str(out))
    assert code == 0
    assert sorted(p.name for p in out.iterdir()) == ["ada-lovelace-cv.md", "ada-lovelace-cv.txt"]
    assert stdout.count("wrote ") == 2
    assert str(out / "ada-lovelace-cv.md") in stdout


def test_failures_are_one_line_unless_debug(capsys, tmp_path: Path) -> None:
    """AC 11.3: a failing command exits 1 with a one-line error; --debug shows the exception."""
    missing = str(tmp_path / "missing.json")
    code, _, err = run(capsys, "validate", missing)
    assert code == 1
    assert err.startswith("error: no such file") and "Traceback" not in err
    assert err.count("\n") == 1
    with pytest.raises(CvGenError, match="no such file"):
        main(["--debug", "validate", missing])


def test_utf8_on_a_legacy_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 11.4: an en dash and a bullet print on a cp1252 stream after setup."""
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    console.setup()
    print("2021 – Present ●")
    sys.stdout.flush()
    assert "2021 – Present ●" in raw.getvalue().decode("utf-8")


def test_schema_validates_model_output(capsys, tmp_path: Path) -> None:
    """AC 1.2: the printed schema validates the model's own JSON output."""
    _, schema_text, _ = run(capsys, "schema")
    code, model_text, _ = run(capsys, "extract", "-a", "file", "-o", f"path={SAMPLE}")
    assert code == 0
    jsonschema.validate(json.loads(model_text), json.loads(schema_text))
    target = tmp_path / "schema.json"
    run(capsys, "schema", "-O", str(target))
    assert json.loads(target.read_text(encoding="utf-8")) == json.loads(schema_text)


def test_adapters_show_prints_options_schema(capsys) -> None:
    """AC 2.2: adapters show web prints the description and the options schema."""
    code, out, _ = run(capsys, "adapters", "show", "web")
    assert code == 0
    assert out.startswith("web: Any web page")
    schema = json.loads(out.split("options (JSON Schema):\n", 1)[1])
    assert {"profile", "url", "path", "timeout"} <= set(schema["properties"])
    code, _, err = run(capsys, "adapters", "show", "nope")
    assert code == 1 and "available adapters" in err


def test_design_validate_reports_tokens(capsys, tmp_path: Path) -> None:
    """AC 9.5: design validate lists the tokens used and those ignored."""
    tokens = tmp_path / "tokens.json"
    tokens.write_text(
        json.dumps(
            {
                "color": {
                    "$type": "color",
                    "accent": {"$value": "#ff2bd6"},
                    "brand": {"$value": "#000"},
                }
            }
        ),
        encoding="utf-8",
    )
    code, out, _ = run(capsys, "design", "validate", str(tokens))
    assert code == 0
    assert "tokens used (1): color.accent" in out
    assert "tokens ignored (1): color.brand" in out
    assert "* color.accent" in out and "#ff2bd6" in out


def test_command_line_format_overrides_config(capsys, tmp_path: Path) -> None:
    """AC 10.3: --format md builds only Markdown although the config lists every format."""
    shutil.copy(SAMPLE, tmp_path / "cv.yaml")
    config = write_config(
        tmp_path,
        "source: {adapter: file, options: {path: cv.yaml}}\n"
        "output: {dir: out, basename: cv, formats: [md, txt, docx, json, html, pdf]}\n",
    )
    code, _, _ = run(capsys, "build", "--config", str(config), "--format", "md")
    assert code == 0
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["cv.md"]


def test_build_without_config_or_adapter(capsys, tmp_path: Path, monkeypatch) -> None:
    """AC 10.4: no config and no --adapter names the missing file and the example."""
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "build")
    assert code == 1
    assert "cv-gen.config.yaml" in err and "cv-gen.config.example.yaml" in err


def test_build_from_config_with_design_and_guard(capsys, tmp_path: Path) -> None:
    """A config build applies its design and refuses forbidden terms."""
    shutil.copy(SAMPLE, tmp_path / "cv.yaml")
    (tmp_path / "t.json").write_text(
        json.dumps({"color": {"accent": {"$type": "color", "$value": "#ff2bd6"}}}), encoding="utf-8"
    )
    config = write_config(
        tmp_path,
        "source: {adapter: file, options: {path: cv.yaml}}\n"
        "design: t.json\n"
        "output: {dir: out, formats: [html]}\n",
    )
    code, _, _ = run(capsys, "build", "-c", str(config))
    assert code == 0
    assert "#ff2bd6" in (tmp_path / "out" / "alex-rivera-cv.html").read_text(encoding="utf-8")
    guarded = write_config(
        tmp_path, config.read_text(encoding="utf-8") + "guard: {forbidden_terms: [Ledgerline]}\n"
    )
    code, _, err = run(capsys, "build", "-c", str(guarded), "--out", str(tmp_path / "guarded"))
    assert code == 1 and "Ledgerline" in err
    assert not (tmp_path / "guarded").exists()


def test_partial_failure_exits_nonzero(capsys, tmp_path: Path, monkeypatch) -> None:
    """A PDF failure still writes the rest, reports the failure, and exits 1."""
    for cls in engines.ENGINES.values():
        monkeypatch.setattr(cls, "available", lambda self: False)
    code, out, err = run(
        capsys, "render", str(SAMPLE), "-f", "md", "-f", "pdf", "--out", str(tmp_path)
    )
    assert code == 1
    assert "wrote " in out
    assert "error: pdf: no PDF engine is available" in err
    assert "hint:" in err


def test_extract_options_and_output(capsys, tmp_path: Path) -> None:
    """extract writes to a file, and option errors are explained."""
    target = tmp_path / "x" / "resume.json"
    code, out, _ = run(capsys, "extract", "-a", "file", "-o", f"path={SAMPLE}", "-O", str(target))
    assert code == 0 and target.is_file() and "wrote" in out
    code, _, err = run(capsys, "extract", "-a", "file", "-o", "nonsense")
    assert code == 1 and "not key=value" in err
    config = write_config(tmp_path, "source: {adapter: file, options: {path: missing.yaml}}\n")
    code, _, err = run(capsys, "extract", "-c", str(config), "-o", "a=1")
    assert code == 1 and "--option needs --adapter" in err


def test_validate_and_render_errors(capsys, tmp_path: Path) -> None:
    """validate reports success and failure; render rejects bad engines and files."""
    code, out, _ = run(capsys, "validate", str(SAMPLE))
    assert code == 0 and "is valid (3 work entries, 1 custom sections)" in out
    bad = tmp_path / "bad.yaml"
    bad.write_text("work: [{startDate: soon}]\n", encoding="utf-8")
    code, _, err = run(capsys, "validate", str(bad))
    assert code == 1 and "work[0].startDate" in err
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    code, _, err = run(capsys, "validate", str(broken))
    assert code == 1 and "cannot read" in err
    code, _, err = run(
        capsys, "render", str(SAMPLE), "--pdf-engine", "prince", "--out", str(tmp_path)
    )
    assert code == 1 and "unknown PDF engine 'prince'" in err


def test_command_line_design(capsys, tmp_path: Path, monkeypatch) -> None:
    """--design on the command line resolves from the working directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "t.json").write_text(
        json.dumps({"color": {"accent": {"$type": "color", "$value": "#123456"}}}), encoding="utf-8"
    )
    code, _, _ = run(
        capsys, "render", str(SAMPLE), "-f", "html", "--design", "t.json", "--out", "o"
    )
    assert code == 0
    assert "#123456" in (tmp_path / "o" / "alex-rivera-cv.html").read_text(encoding="utf-8")


def test_parse_option_values() -> None:
    """Option values are YAML scalars; dates and odd values stay as written."""
    assert parse_option("timeout=5") == ("timeout", 5)
    assert parse_option("url=https://x.example/a") == ("url", "https://x.example/a")
    assert parse_option("when=2024-01-01") == ("when", "2024-01-01")
    assert parse_option("empty=") == ("empty", "")
    assert parse_option("odd=[1") == ("odd", "[1")

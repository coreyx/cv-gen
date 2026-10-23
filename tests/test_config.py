"""Tests for configuration loading and source merging (REQ-5, REQ-10)."""

from pathlib import Path

import pytest

from cv_gen.config import Config, load_config
from cv_gen.errors import CvGenError
from cv_gen.merge import deep_merge


def test_overlay_adds_email_to_extracted_data() -> None:
    """AC 5.1: an overlay carrying only basics.email keeps the base and adds the email."""
    base = {"basics": {"name": "Ada", "profiles": [{"network": "GitHub"}]}, "work": [{"name": "X"}]}
    merged = deep_merge(base, {"basics": {"email": "ada@example.com"}})
    assert merged == {
        "basics": {"name": "Ada", "profiles": [{"network": "GitHub"}], "email": "ada@example.com"},
        "work": [{"name": "X"}],
    }
    assert "email" not in base["basics"], "inputs are never modified"


def test_lists_replace_or_append() -> None:
    """AC 5.2: a later list replaces the earlier one, or follows it under append."""
    base = {"skills": [{"name": "A"}]}
    overlay = {"skills": [{"name": "B"}]}
    assert deep_merge(base, overlay)["skills"] == [{"name": "B"}]
    assert deep_merge(base, overlay, "append")["skills"] == [{"name": "A"}, {"name": "B"}]


def test_none_never_erases() -> None:
    """None in an overlay leaves the base value in place."""
    assert deep_merge({"a": 1}, {"a": None}) == {"a": 1}
    assert deep_merge({"a": 1}, None) == {"a": 1}


def test_relative_paths_resolve_against_config_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 10.2: paths in a config resolve from its folder, not the working directory."""
    folder = tmp_path / "cfg"
    folder.mkdir()
    (folder / "cv-gen.config.yaml").write_text(
        "source: {adapter: file, options: {path: ./data.yaml}}\n"
        "plugins: {paths: [./plugins]}\n"
        "output: {dir: ./build}\n"
        "render: {templates: ./tpl}\n"
        "design: ./tokens.json\n",
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    config = load_config(folder / "cv-gen.config.yaml")
    assert config.base_dir == folder.resolve()
    assert config.resolve(config.sources[0].options["path"]) == (folder / "data.yaml").resolve()
    assert config.plugins.paths == [(folder / "plugins").resolve()]
    assert config.output.dir == (folder / "build").resolve()
    assert config.render.templates == (folder / "tpl").resolve()
    assert config.design is not None
    assert Path(config.design.ref) == (folder / "tokens.json").resolve()


def test_design_url_is_left_alone(tmp_path: Path) -> None:
    """A design given as a URL is not treated as a path."""
    path = tmp_path / "c.yaml"
    path.write_text("design: {ref: 'https://example.com/t.json', sha256: abc}\n", encoding="utf-8")
    config = load_config(path)
    assert config.design is not None
    assert config.design.ref == "https://example.com/t.json"
    assert config.design.sha256 == "abc"


def test_missing_config_points_to_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 10.4 (config half): a missing file names itself and the example file."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CvGenError) as caught:
        load_config()
    assert "cv-gen.config.yaml" in caught.value.message
    assert "cv-gen.config.example.yaml" in (caught.value.hint or "")
    assert load_config(required=False).sources == []


def test_invalid_config_names_the_problem(tmp_path: Path) -> None:
    """Unknown keys, bad YAML and non-mappings are reported against the file."""
    unknown = tmp_path / "unknown.yaml"
    unknown.write_text("outputs: {}\n", encoding="utf-8")
    with pytest.raises(CvGenError, match="outputs: unknown option"):
        load_config(unknown)
    broken = tmp_path / "broken.yaml"
    broken.write_text("a: [\n", encoding="utf-8")
    with pytest.raises(CvGenError, match="not valid YAML"):
        load_config(broken)
    listy = tmp_path / "list.yaml"
    listy.write_text("- a\n", encoding="utf-8")
    with pytest.raises(CvGenError, match="mapping"):
        load_config(listy)


def test_source_and_sources_conflict() -> None:
    """Giving both spellings is an error rather than a silent choice."""
    with pytest.raises(ValueError, match="either 'source' or 'sources'"):
        Config.model_validate({"source": {"adapter": "a"}, "sources": []})


def test_defaults() -> None:
    """A minimal config builds every format except PDF by default."""
    config = Config()
    assert config.output.formats == ["md", "txt", "docx", "json", "html"]
    assert config.pdf.engine == "auto"
    assert config.render.text_width == 80

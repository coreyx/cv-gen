"""Tests for the adapter contract, registry, file adapter and extract stage (REQ-2, REQ-3)."""

import json
import sys
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from cv_gen.adapters import (
    AdapterContext,
    available_adapters,
    options_schema,
    registry,
    resolve_adapter,
)
from cv_gen.adapters.file import FileAdapter
from cv_gen.config import SourceConfig
from cv_gen.errors import CvGenError
from cv_gen.pipeline import extract

PLUGIN_SOURCE = """
from cv_gen.adapters import Adapter, AdapterOptions, Resume

RUNS = []

class Options(AdapterOptions):
    name: str

class MyAdapter(Adapter):
    name = "mine"
    description = "Test adapter."
    Options = Options

    def extract(self, options, ctx):
        RUNS.append(options.name)
        return Resume.from_data({"basics": {"name": options.name}})

class NotAnAdapter:
    pass
"""


@pytest.fixture
def plugin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A plugin package on disk, not installed; sys.path and modules are restored after."""
    package = tmp_path / "plugins" / "my_plugin"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "mod.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
    monkeypatch.setattr(sys, "path", list(sys.path))
    yield tmp_path / "plugins"
    for name in [m for m in sys.modules if m.startswith("my_plugin")]:
        del sys.modules[name]


def test_builtins_and_entry_points_are_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 2.1: built-ins and entry-point adapters are both available by name."""
    fake = [EntryPoint("fake", "cv_gen.adapters.file:FileAdapter", registry.ENTRY_POINT_GROUP)]
    monkeypatch.setattr(registry, "entry_points", lambda group: fake)
    adapters = available_adapters()
    assert adapters["file"] is FileAdapter
    assert adapters["fake"] is FileAdapter


def test_builtin_name_cannot_be_hijacked(monkeypatch: pytest.MonkeyPatch) -> None:
    """A plugin registering a built-in's name does not replace the built-in."""
    fake = [EntryPoint("file", "my_plugin.mod:MyAdapter", registry.ENTRY_POINT_GROUP)]
    monkeypatch.setattr(registry, "entry_points", lambda group: fake)
    assert resolve_adapter("file") is FileAdapter


def test_options_schema_describes_options() -> None:
    """AC 2.2 (data half): an adapter's options export as JSON Schema."""
    schema = options_schema(FileAdapter)
    assert schema["required"] == ["path"]


def test_module_reference_from_plugin_path(plugin_dir: Path, tmp_path: Path) -> None:
    """AC 2.3: a module:Class adapter under a plugin path runs without installation."""
    source = SourceConfig(adapter="my_plugin.mod:MyAdapter", options={"name": "Ada"})
    resume = extract([source], tmp_path, plugin_paths=[plugin_dir])
    assert resume.basics.name == "Ada"
    assert resume.meta is not None
    assert resume.meta.sources[0].adapter == "my_plugin.mod:MyAdapter"


def test_unknown_option_fails_before_running(plugin_dir: Path, tmp_path: Path) -> None:
    """AC 2.4: an unknown option is rejected, naming it, and the adapter never runs."""
    source = SourceConfig(adapter="my_plugin.mod:MyAdapter", options={"name": "A", "colour": 1})
    with pytest.raises(CvGenError) as caught:
        extract([source], tmp_path, plugin_paths=[plugin_dir])
    assert "colour: unknown option" in caught.value.message
    assert "adapters show" in (caught.value.hint or "")
    assert sys.modules["my_plugin.mod"].RUNS == []


def test_unknown_adapter_lists_names() -> None:
    """AC 2.5: an unknown name fails listing what is available."""
    with pytest.raises(CvGenError, match=r"unknown adapter 'nope'; available adapters: .*file"):
        resolve_adapter("nope")


@pytest.mark.parametrize(
    ("ref", "message"),
    [
        ("nocolon:", "not a module:Class"),
        ("no_such_module_xyz:Thing", "cannot import adapter module"),
        ("my_plugin.mod:Missing", "has no attribute"),
        ("my_plugin.mod:NotAnAdapter", "not a cv_gen.adapters.Adapter subclass"),
    ],
)
def test_bad_references(plugin_dir: Path, ref: str, message: str) -> None:
    """Broken references explain what is wrong with them."""
    registry.add_plugin_paths([plugin_dir])
    with pytest.raises(CvGenError, match=message):
        resolve_adapter(ref)


def test_plugin_paths_are_not_duplicated(plugin_dir: Path) -> None:
    """Adding the same plugin path twice leaves one entry."""
    registry.add_plugin_paths([plugin_dir, plugin_dir])
    registry.add_plugin_paths([plugin_dir])
    assert sys.path.count(str(plugin_dir)) == 1


def test_file_adapter_reads_yaml_and_json_alike(tmp_path: Path) -> None:
    """AC 3.1: a YAML file and its JSON copy produce the same model."""
    data = {"basics": {"name": "Ada", "label": "Engineer"}, "skills": [{"name": "Python"}]}
    (tmp_path / "cv.yaml").write_text(
        "basics: {name: Ada, label: Engineer}\nskills: [{name: Python}]\n"
    )
    (tmp_path / "cv.json").write_text(json.dumps(data))
    ctx = AdapterContext(base_dir=tmp_path)
    adapter = FileAdapter()
    from_yaml = adapter.extract(FileAdapter.Options(path=Path("cv.yaml")), ctx)
    from_json = adapter.extract(FileAdapter.Options(path=Path("cv.json")), ctx)
    assert from_yaml == from_json
    assert from_yaml.to_data() == data


def test_file_adapter_errors(tmp_path: Path) -> None:
    """Missing, unparseable and invalid files fail with the path in the message."""
    ctx = AdapterContext(base_dir=tmp_path)
    adapter = FileAdapter()
    with pytest.raises(CvGenError, match="no such file"):
        adapter.extract(FileAdapter.Options(path=Path("missing.yaml")), ctx)
    (tmp_path / "bad.json").write_text("{nope")
    with pytest.raises(CvGenError, match="cannot read"):
        adapter.extract(FileAdapter.Options(path=Path("bad.json")), ctx)
    (tmp_path / "invalid.yaml").write_text("work: [{startDate: soon}]\n")
    with pytest.raises(CvGenError, match=r"work\[0\]\.startDate"):
        adapter.extract(FileAdapter.Options(path=Path("invalid.yaml")), ctx)


def test_extract_merges_sources_in_order(tmp_path: Path) -> None:
    """Sources merge in order, and meta.sources records each one."""
    (tmp_path / "a.yaml").write_text("basics: {name: Ada}\nskills: [{name: A}]\n")
    (tmp_path / "b.yaml").write_text("basics: {email: ada@example.com}\nskills: [{name: B}]\n")
    sources = [
        SourceConfig(adapter="file", options={"path": "a.yaml"}),
        SourceConfig(adapter="file", options={"path": "b.yaml"}, merge="append"),
    ]
    resume = extract(sources, tmp_path)
    assert resume.basics.name == "Ada" and resume.basics.email == "ada@example.com"
    assert [s.name for s in resume.skills] == ["A", "B"]
    assert resume.meta is not None
    assert [s.location for s in resume.meta.sources] == ["a.yaml", "b.yaml"]


def test_extract_errors(tmp_path: Path) -> None:
    """No sources, and merges that break the model, are reported."""
    with pytest.raises(CvGenError, match="no sources"):
        extract([], tmp_path)
    (tmp_path / "a.yaml").write_text("sections: [{id: x, title: X}]\n")
    twice = [SourceConfig(adapter="file", options={"path": "a.yaml"}, merge="append")] * 2
    with pytest.raises(CvGenError, match="duplicate section id"):
        extract(twice, tmp_path)


def test_adapter_returning_wrong_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An adapter that returns something other than a Resume is caught."""
    monkeypatch.setattr(FileAdapter, "extract", lambda self, options, ctx: {"basics": {}})
    (tmp_path / "a.yaml").write_text("{}")
    with pytest.raises(CvGenError, match="not Resume"):
        extract([SourceConfig(adapter="file", options={"path": "a.yaml"})], tmp_path)

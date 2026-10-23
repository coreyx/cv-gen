"""Tests for the example adapter: the pattern to copy for your own adapter's tests."""

from pathlib import Path

import pytest
from cv_gen_example_adapter import TomlProfileAdapter, TomlProfileOptions

from cv_gen.adapters import AdapterContext, available_adapters
from cv_gen.errors import CvGenError

HERE = Path(__file__).parent.parent


def extract(path: str = "sample-profile.toml", **options):
    """Run the adapter the way cv-gen does: options validated, paths relative to a folder."""
    opts = TomlProfileOptions.model_validate({"path": path, **options})
    return TomlProfileAdapter().extract(opts, AdapterContext(base_dir=HERE))


def test_sample_maps_onto_the_model() -> None:
    """The sample profile becomes a valid Resume with the expected fields."""
    resume = extract()
    assert resume.basics.name == "Sam Okafor"
    assert resume.basics.label == "Data Engineer"
    assert resume.basics.location is not None and resume.basics.location.city == "Lagos"
    assert [p.network for p in resume.basics.profiles] == ["Github", "Linkedin"]
    assert [job.name for job in resume.work] == ["Kudi Analytics", "Paystack"]
    assert resume.work[0].endDate is None, "'present' means no end date"
    assert resume.work[1].endDate == "2022-01"
    assert resume.skills[1].keywords == ["Spark", "dbt", "Airflow", "BigQuery"]


def test_options_change_the_output() -> None:
    """include_links=false leaves the profiles out."""
    assert extract(include_links=False).basics.profiles == []


def test_errors_are_cv_gen_errors(tmp_path: Path) -> None:
    """Missing and malformed files raise CvGenError, which the CLI prints on one line."""
    with pytest.raises(CvGenError, match="no such profile"):
        extract(str(tmp_path / "missing.toml"))
    bad = tmp_path / "bad.toml"
    bad.write_text("[person\n", encoding="utf-8")
    with pytest.raises(CvGenError, match="not valid TOML"):
        extract(str(bad))


def test_unknown_options_are_rejected() -> None:
    """The options model rejects typos instead of ignoring them."""
    with pytest.raises(ValueError, match="incldue_links"):
        TomlProfileOptions.model_validate({"path": "x.toml", "incldue_links": False})


def test_registered_through_the_entry_point() -> None:
    """Installed, the package's entry point makes the adapter discoverable by name."""
    assert available_adapters()["example-toml"] is TomlProfileAdapter

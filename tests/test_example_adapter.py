"""The example adapter package works through the installed entry point (REQ-12)."""

import json
from pathlib import Path

import pytest

from cv_gen.cli import main
from cv_gen.model import Resume

SAMPLE = Path(__file__).parent.parent / "examples" / "adapter-example" / "sample-profile.toml"


def test_installed_example_extracts_a_valid_model(capsys: pytest.CaptureFixture[str]) -> None:
    """AC 12.1: the installed example is listed and extracts its sample to a valid model."""
    with pytest.raises(SystemExit) as listed:
        main(["adapters", "list"])
    assert listed.value.code == 0
    assert "example-toml" in capsys.readouterr().out
    with pytest.raises(SystemExit) as extracted:
        main(["extract", "--adapter", "example-toml", "-o", f"path={SAMPLE}"])
    assert extracted.value.code == 0
    resume = Resume.from_data(json.loads(capsys.readouterr().out))
    assert resume.basics.name == "Sam Okafor"
    assert resume.meta is not None and resume.meta.sources[0].adapter == "example-toml"

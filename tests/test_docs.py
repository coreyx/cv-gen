"""The documentation and the config-example pattern are in place (REQ-10, REQ-12)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from cv_gen.cli import main

ROOT = Path(__file__).parent.parent
GUIDES = ["adapters", "web-profiles", "design-tokens", "configuration", "cli", "model"]


def test_guides_exist_and_are_linked() -> None:
    """AC 12.3: docs/ holds every guide and the README links each one."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for guide in GUIDES:
        assert (ROOT / "docs" / f"{guide}.md").is_file(), guide
        assert f"(docs/{guide}.md)" in readme, guide


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_private_files_are_ignored() -> None:
    """AC 10.1: the real config and the private adapter folder are ignored; the example is not."""
    ignored = subprocess.run(
        ["git", "check-ignore", "cv-gen.config.yaml", "cv-gen-corey/README.md", "a.local.yaml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.stdout.split() == [
        "cv-gen.config.yaml",
        "cv-gen-corey/README.md",
        "a.local.yaml",
    ]
    example = subprocess.run(
        ["git", "check-ignore", "-q", "cv-gen.config.example.yaml"], cwd=ROOT, check=False
    )
    assert example.returncode == 1, "the example config must not be ignored"


def test_example_config_builds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The committed example config builds the sample out of the box."""
    with pytest.raises(SystemExit) as done:
        main(
            [
                "build",
                "-c",
                str(ROOT / "cv-gen.config.example.yaml"),
                "-f",
                "md",
                "-f",
                "docx",
                "--out",
                str(tmp_path),
            ]
        )
    assert done.value.code == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "alex-rivera-cv.docx",
        "alex-rivera-cv.md",
    ]


@pytest.mark.parametrize("design", ["serif.tokens.json", "compact.tokens.yaml"])
def test_example_designs_validate(design: str, capsys: pytest.CaptureFixture[str]) -> None:
    """The sample design systems are valid."""
    with pytest.raises(SystemExit) as done:
        main(["design", "validate", str(ROOT / "examples" / "designs" / design)])
    assert done.value.code == 0

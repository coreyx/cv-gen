"""Smoke test: the package imports and reports its version."""

import cv_gen


def test_version_is_set() -> None:
    """The package exposes a version string."""
    assert cv_gen.__version__

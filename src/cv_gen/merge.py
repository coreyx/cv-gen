"""Layering several sources into one document (REQ-5)."""

from __future__ import annotations

from typing import Any, Literal

MergeMode = Literal["replace", "append"]


def deep_merge(base: Any, overlay: Any, mode: MergeMode = "replace") -> Any:
    """Return ``overlay`` layered over ``base``, without modifying either.

    Mappings merge key by key, recursively. A scalar in the overlay replaces the base
    value. A list in the overlay replaces the base list, or, in ``append`` mode, is
    added after it. ``None`` in the overlay never erases a base value, so an overlay
    only has to mention what it changes.
    """
    if overlay is None:
        return base
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for key, value in overlay.items():
            merged[key] = deep_merge(base.get(key), value, mode) if key in base else value
        return merged
    if mode == "append" and isinstance(base, list) and isinstance(overlay, list):
        return [*base, *overlay]
    return overlay

"""Evaluating a profile against a parsed page.

The evaluation is recursive: the document is the first scope; a spec with ``each``
makes every matched element the scope of one record; a spec with ``fields`` and no
``each`` builds one nested object in the current scope.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from cv_gen.adapters.web import transforms
from cv_gen.adapters.web.profile import FieldSpec, FieldValue, Profile
from cv_gen.adapters.web.transforms import TransformContext
from cv_gen.errors import CvGenError

MERGE_TARGET = "."


def parse_html(html: str, exclude: list[str]) -> BeautifulSoup:
    """Parse a page and remove everything matching the ``exclude`` selectors."""
    soup = BeautifulSoup(html, "html.parser")
    for selector in exclude:
        for element in soup.select(selector):
            element.decompose()
    return soup


def element_text(element: Tag) -> str:
    """Return an element's visible text with whitespace collapsed.

    Text nodes are joined without a separator, so ``Alpha<span>, and</span>`` reads
    "Alpha, and"; line breaks count as spaces.
    """
    for br in element.find_all("br"):
        br.replace_with(" ")
    return re.sub(r"\s+", " ", element.get_text("")).strip()


def _read(element: Tag, spec: FieldSpec, path: str) -> Any:
    """Read one value from one element according to the spec's mode and ``drop`` list."""
    # Reading text rewrites <br> nodes and drop removes nodes: work on a copy so neither
    # changes the page that other fields still read.
    element = copy.copy(element)
    for selector in spec.drop:
        for dropped in element.select(selector):
            dropped.decompose()
    if spec.mode == "text":
        return element_text(element)
    if spec.mode == "html":
        return element.decode_contents()
    raw = element.get(spec.attr) if spec.attr else element_text(element)
    if isinstance(raw, list):  # bs4 returns multi-valued attributes (class) as lists
        raw = " ".join(raw)
    if spec.mode == "json":
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError as error:
            raise CvGenError(f"{path}: content is not valid JSON: {error}") from error
    return raw


def _select(scope: Tag, spec: FieldSpec) -> list[Tag]:
    """Return the elements a spec reads: the scope itself, the first match, or all."""
    if spec.selector is None:
        return [scope]
    if spec.all:
        return list(scope.select(spec.selector))
    found = scope.select_one(spec.selector)
    return [found] if found is not None else []


def evaluate(value_spec: FieldValue, scope: Tag, path: str, base_url: str | None) -> Any:
    """Evaluate a field spec (or a list of them, concatenated) in ``scope``."""
    if isinstance(value_spec, list):
        combined: list[Any] = []
        for index, spec in enumerate(value_spec):
            result = evaluate(spec, scope, f"{path}<{index}>", base_url)
            if isinstance(result, list):
                combined.extend(result)
            elif result is not None:
                combined.append(result)
        return combined

    spec = value_spec
    if spec.is_constant:
        result = spec.value
    else:
        elements = _select(scope, spec)
        if spec.each:
            # ``selector`` narrows the scope first; ``each`` then repeats inside it.
            roots = elements
            matches = [match for root in roots for match in root.select(spec.each)]
            if not matches and spec.required:
                raise CvGenError(f"{path}: required selector '{spec.each}' matched nothing")
            result = [
                build_record(spec.fields or {}, match, f"{path}[{i}]", base_url)
                for i, match in enumerate(matches)
            ]
        elif not elements:
            if spec.required:
                raise CvGenError(f"{path}: required selector '{spec.selector}' matched nothing")
            result = spec.default
        elif spec.fields:
            result = build_record(spec.fields, elements[0], path, base_url)
        else:
            values = [_read(element, spec, path) for element in elements]
            result = values if spec.all else values[0]

    if result is None:
        return None
    ctx = TransformContext(base_url=base_url, field=path)
    for transform_spec in spec.transforms:
        result = transforms.apply(transform_spec, result, ctx)
        if result is None:
            break
    return result


def set_path(record: dict[str, Any], dotted: str, value: Any) -> None:
    """Set ``record["a"]["b"] = value`` for ``dotted == "a.b"``, creating mappings."""
    *parents, leaf = dotted.split(".")
    node = record
    for key in parents:
        node = node.setdefault(key, {})
        if not isinstance(node, dict):
            raise CvGenError(f"cannot set '{dotted}': '{key}' already holds a value")
    node[leaf] = value


def build_record(
    fields: dict[str, FieldValue], scope: Tag, path: str, base_url: str | None
) -> dict[str, Any]:
    """Build one mapping from ``fields`` evaluated in ``scope``."""
    record: dict[str, Any] = {}
    for target, value_spec in fields.items():
        field_path = f"{path}.{target}" if path and target != MERGE_TARGET else (path or target)
        value = evaluate(value_spec, scope, field_path, base_url)
        if value is None:
            continue
        if target == MERGE_TARGET:
            # A list of specs under "." yields a list of mappings, merged in order.
            parts = value if isinstance(value, list) else [value]
            for part in parts:
                if not isinstance(part, dict):
                    raise CvGenError(f"{field_path}: the '.' target needs a mapping, got {part!r}")
                for key, item in part.items():
                    set_path(record, key, item)
        else:
            set_path(record, target, value)
    return record


def run_profile(profile: Profile, html: str, base_url: str | None) -> dict[str, Any]:
    """Evaluate a whole profile against a page and return plain model data."""
    for module in profile.transforms_modules:
        transforms.register_module(module)
    soup = parse_html(html, profile.exclude)
    return build_record(profile.fields, soup, "", base_url)

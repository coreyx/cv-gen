"""Named value transforms a web profile applies to extracted values, in order.

A transform takes the current value and a :class:`TransformContext`, plus keyword
arguments from the profile, and returns the new value::

    transforms: [normalize, {strip_prefix: "@"}, {split: {sep: ","}}]

Profiles reach site-specific logic by naming a ``transforms_module``; that module
registers its own transforms with the :func:`transform` decorator::

    from cv_gen.adapters.web import transform

    @transform("kind_label")
    def kind_label(value, ctx):
        return {"studio": "Studio"}.get(value, value)

A transform that returns a mapping can be applied to the ``"."`` target, which merges
the mapping into the record being built (one element, several fields).
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from cv_gen.adapters.web.dates import parse_date_range
from cv_gen.errors import CvGenError

TransformFn = Callable[..., Any]
_REGISTRY: dict[str, TransformFn] = {}


@dataclass
class TransformContext:
    """What a transform may need besides the value: the page URL and the field name."""

    base_url: str | None = None
    field: str = ""


def transform(name: str) -> Callable[[TransformFn], TransformFn]:
    """Register the decorated function as the transform ``name``.

    Registering a name twice replaces the earlier transform, so a plugin can override
    a built-in deliberately.
    """

    def register(fn: TransformFn) -> TransformFn:
        _REGISTRY[name] = fn
        return fn

    return register


def register_module(module_name: str) -> None:
    """Import a module whose ``@transform`` functions register themselves."""
    try:
        importlib.import_module(module_name)
    except ImportError as error:
        raise CvGenError(
            f"cannot import transforms module '{module_name}': {error}",
            "install the plugin, or add its folder to plugins.paths",
        ) from error


def names() -> list[str]:
    """Return every registered transform name, sorted."""
    return sorted(_REGISTRY)


def apply(spec: str | dict[str, Any], value: Any, ctx: TransformContext) -> Any:
    """Apply one transform spec to ``value``.

    ``spec`` is a name, or a one-key mapping from a name to its arguments: a mapping
    of keyword arguments, a list of positional ones, or a single positional value.
    """
    if isinstance(spec, str):
        name, args, kwargs = spec, [], {}
    elif isinstance(spec, dict) and len(spec) == 1:
        name, raw = next(iter(spec.items()))
        args, kwargs = (
            ([], raw) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [raw], {})
        )
    else:
        raise CvGenError(f"{ctx.field}: a transform is a name or a one-key mapping, got {spec!r}")
    fn = _REGISTRY.get(name)
    if fn is None:
        raise CvGenError(
            f"{ctx.field}: unknown transform '{name}'",
            f"known transforms: {', '.join(names())}",
        )
    try:
        return fn(value, ctx, *args, **kwargs)
    except CvGenError:
        raise
    except (TypeError, ValueError, re.error) as error:
        raise CvGenError(f"{ctx.field}: transform '{name}' failed: {error}") from error


def _each(fn: Callable[[str], Any]) -> Callable[[Any], Any]:
    """Apply a string function to a value, or to every string in a list."""

    def apply_to(value: Any) -> Any:
        if isinstance(value, list):
            return [apply_to(item) for item in value]
        return fn(value) if isinstance(value, str) else value

    return apply_to


@transform("normalize")
def normalize(value: Any, ctx: TransformContext) -> Any:
    """Collapse runs of whitespace to one space and trim the ends."""
    return _each(lambda text: re.sub(r"\s+", " ", text).strip())(value)


@transform("lower")
def lower(value: Any, ctx: TransformContext) -> Any:
    """Lower-case the text."""
    return _each(str.lower)(value)


@transform("upper")
def upper(value: Any, ctx: TransformContext) -> Any:
    """Upper-case the text."""
    return _each(str.upper)(value)


@transform("replace")
def replace(value: Any, ctx: TransformContext, old: str, new: str = "") -> Any:
    """Replace every ``old`` with ``new``."""
    return _each(lambda text: text.replace(old, new))(value)


@transform("strip_prefix")
def strip_prefix(value: Any, ctx: TransformContext, prefix: str) -> Any:
    """Remove ``prefix`` from the start of the text, when it is there."""
    return _each(lambda text: text.removeprefix(prefix))(value)


@transform("strip_suffix")
def strip_suffix(value: Any, ctx: TransformContext, suffix: str) -> Any:
    """Remove ``suffix`` from the end of the text, when it is there."""
    return _each(lambda text: text.removesuffix(suffix))(value)


@transform("regex")
def regex(value: Any, ctx: TransformContext, pattern: str, group: int | str = 1) -> Any:
    """Return a capture group of the first match of ``pattern``, or nothing on no match."""

    def capture(text: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(group) if match else None

    return _each(capture)(value)


@transform("split")
def split(value: Any, ctx: TransformContext, sep: str = ",", strip: bool = True) -> Any:
    """Split text into a list on ``sep``, trimming the parts and dropping empty ones."""
    if not isinstance(value, str):
        return value
    parts = value.split(sep)
    return [part.strip() for part in parts if part.strip()] if strip else parts


@transform("join")
def join(value: Any, ctx: TransformContext, sep: str = " ") -> Any:
    """Join a list into one string with ``sep``."""
    return sep.join(str(item) for item in value) if isinstance(value, list) else value


@transform("as_list")
def as_list(value: Any, ctx: TransformContext) -> Any:
    """Wrap a single value in a list (for fields such as ``tags``)."""
    if value is None or isinstance(value, list):
        return value
    return [value]


@transform("first")
def first(value: Any, ctx: TransformContext) -> Any:
    """Return the first item of a list."""
    return value[0] if isinstance(value, list) and value else value


@transform("map")
def map_values(
    value: Any, ctx: TransformContext, mapping: dict[str, Any], default: Any = ...
) -> Any:
    """Look the value up in ``mapping``; keep it, or use ``default``, when it is absent."""

    def look_up(text: str) -> Any:
        return mapping.get(text, text if default is ... else default)

    return _each(look_up)(value)


@transform("absolute_url")
def absolute_url(value: Any, ctx: TransformContext) -> Any:
    """Resolve a relative link against the page's URL."""
    if ctx.base_url is None:
        return value
    return _each(lambda href: urljoin(ctx.base_url or "", href))(value)


@transform("date_range")
def date_range(value: Any, ctx: TransformContext) -> Any:
    """Parse a written range into ``startDate``, ``endDate`` and ``periods`` (for ``"."``)."""
    return parse_date_range(value) if isinstance(value, str) else value


@transform("lead_sentence")
def lead_sentence(
    value: Any,
    ctx: TransformContext,
    max_words: int = 4,
    lead: str = "position",
    rest: str = "summary",
) -> Any:
    """Split a short opening sentence (a role, say) from the rest of the text.

    ``"Founder. Game studio, Paydirt."`` becomes ``{position: "Founder",
    summary: "Game studio, Paydirt."}`` with the defaults. Text whose first sentence
    is longer than ``max_words``, or that is a single sentence, goes entirely to
    ``rest``. Meant for the ``"."`` target.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    match = re.match(r"^(?P<lead>[^.]+?)\.\s+(?P<rest>\S.*)$", text, re.DOTALL)
    if match and len(match.group("lead").split()) <= max_words:
        return {lead: match.group("lead").strip(), rest: match.group("rest").strip()}
    return {rest: text}

"""Finding adapters: built-ins, installed plugins and ``module:Class`` references.

Three ways to make an adapter available, in the order they are consulted:

1. Built-ins shipped with cv-gen (``file``, ``web``).
2. Installed packages that declare an entry point in the ``cv_gen.adapters`` group.
3. A ``package.module:ClassName`` reference, importable from ``sys.path`` or from a
   configured plugin path, which needs no installation at all.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterable
from importlib.metadata import entry_points
from pathlib import Path

from cv_gen.adapters.base import Adapter
from cv_gen.errors import CvGenError

ENTRY_POINT_GROUP = "cv_gen.adapters"

# Built-ins are named by import path so that listing adapters never imports one that
# is not used (the web engine pulls in BeautifulSoup).
BUILTIN_ADAPTERS = {
    "file": "cv_gen.adapters.file:FileAdapter",
}


def add_plugin_paths(paths: Iterable[Path]) -> None:
    """Put plugin folders at the front of ``sys.path`` so their modules import.

    Paths already on ``sys.path`` are not added twice.
    """
    for path in reversed([str(Path(p)) for p in paths]):
        if path not in sys.path:
            sys.path.insert(0, path)


def load_reference(ref: str) -> type[Adapter]:
    """Import ``package.module:ClassName`` and check that it is an Adapter subclass."""
    module_name, _, attr = ref.partition(":")
    if not module_name or not attr:
        raise CvGenError(f"'{ref}' is not a module:Class reference")
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise CvGenError(
            f"cannot import adapter module '{module_name}': {error}",
            "install the plugin package, or add its folder to plugins.paths",
        ) from error
    try:
        adapter = getattr(module, attr)
    except AttributeError as error:
        raise CvGenError(f"module '{module_name}' has no attribute '{attr}'") from error
    if not (isinstance(adapter, type) and issubclass(adapter, Adapter)):
        raise CvGenError(f"'{ref}' is not a cv_gen.adapters.Adapter subclass")
    return adapter


def _entry_point_refs() -> dict[str, str]:
    """Return the ``name -> module:Class`` map declared by installed plugin packages."""
    return {ep.name: ep.value for ep in entry_points(group=ENTRY_POINT_GROUP)}


def adapter_refs() -> dict[str, str]:
    """Return every adapter name known without importing anything, with its reference.

    A plugin cannot replace a built-in by registering the same name; built-ins win.
    """
    return {**_entry_point_refs(), **BUILTIN_ADAPTERS}


def available_adapters() -> dict[str, type[Adapter]]:
    """Import and return every known adapter, by name, sorted by name."""
    return {name: load_reference(ref) for name, ref in sorted(adapter_refs().items())}


def resolve_adapter(name_or_ref: str) -> type[Adapter]:
    """Return the adapter class for a registered name or a ``module:Class`` reference."""
    if ":" in name_or_ref:
        return load_reference(name_or_ref)
    refs = adapter_refs()
    if name_or_ref not in refs:
        names = ", ".join(sorted(refs)) or "(none)"
        raise CvGenError(
            f"unknown adapter '{name_or_ref}'; available adapters: {names}",
            "use a module:Class reference for an adapter that is not installed",
        )
    return load_reference(refs[name_or_ref])

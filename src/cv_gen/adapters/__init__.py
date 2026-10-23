"""Source adapters and the public API for writing one.

Plugin authors import from here::

    from cv_gen.adapters import Adapter, AdapterContext, AdapterOptions
"""

from cv_gen.adapters.base import Adapter, AdapterContext, AdapterOptions, options_schema
from cv_gen.adapters.registry import (
    ENTRY_POINT_GROUP,
    add_plugin_paths,
    available_adapters,
    resolve_adapter,
)
from cv_gen.model import Resume

__all__ = [
    "ENTRY_POINT_GROUP",
    "Adapter",
    "AdapterContext",
    "AdapterOptions",
    "Resume",
    "add_plugin_paths",
    "available_adapters",
    "options_schema",
    "resolve_adapter",
]

"""The generic web-extraction engine: a page, a declarative profile, named transforms.

Plugin authors import from here::

    from cv_gen.adapters.web import TransformContext, WebAdapter, transform
"""

from cv_gen.adapters.web.adapter import WebAdapter, WebOptions
from cv_gen.adapters.web.transforms import TransformContext, register_module, transform

__all__ = ["TransformContext", "WebAdapter", "WebOptions", "register_module", "transform"]

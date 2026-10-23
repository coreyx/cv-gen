"""The generic web-extraction engine: a page, a declarative profile, named transforms.

Plugin authors import from here::

    from cv_gen.adapters.web import TransformContext, transform
"""

from cv_gen.adapters.web.transforms import TransformContext, register_module, transform

__all__ = ["TransformContext", "register_module", "transform"]

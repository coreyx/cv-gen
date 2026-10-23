"""A transforms module a test profile names, to prove plugin transforms register."""

from cv_gen.adapters.web import transform


@transform("shout")
def shout(value, ctx, mark="!"):
    """Upper-case the text and add ``mark``."""
    return f"{value.upper()}{mark}" if isinstance(value, str) else value

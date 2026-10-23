"""The error type every expected failure raises, and readable validation messages."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import ValidationError


class CvGenError(Exception):
    """An expected failure: bad input, a missing file, an unreachable source.

    The CLI prints ``message`` and ``hint`` without a traceback. Anything else that
    escapes is a bug and is shown in full.
    """

    def __init__(self, message: str, hint: str | None = None) -> None:
        """Create the error with a one-line ``message`` and an optional next step."""
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        """Return the message, followed by the hint when there is one."""
        return self.message if not self.hint else f"{self.message}\nhint: {self.hint}"


def format_location(location: Iterable[str | int]) -> str:
    """Render a Pydantic error location as a path: ``work[0].startDate``."""
    path = ""
    for part in location:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path or "(document)"


def validation_lines(error: ValidationError) -> list[str]:
    """Turn a Pydantic ``ValidationError`` into one ``path: message`` line per problem."""
    lines = []
    for item in error.errors():
        # Union and function validators append their kind to the location
        # ("function-after[...]"); it means nothing to a person reading a CV file.
        location = [part for part in item["loc"] if not str(part).startswith(("function-", "["))]
        message = item["msg"]
        if item["type"] == "string_pattern_mismatch":
            message = f"{item['input']!r} is not in the expected format"
        elif item["type"] == "extra_forbidden":
            message = "unknown option"
        lines.append(f"{format_location(location)}: {message}")
    return lines


def from_validation(error: ValidationError, what: str, hint: str | None = None) -> CvGenError:
    """Wrap a ``ValidationError`` about ``what`` (a file or an option set) as a CvGenError."""
    detail = "\n  ".join(validation_lines(error))
    return CvGenError(f"{what} is not valid:\n  {detail}", hint)

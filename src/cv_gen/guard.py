"""The output guard: words that must never appear in a generated CV (REQ-14).

People with confidential history (NDA clients, unannounced products, a past name)
list those words once in the config; every build then refuses to write any output
that contains one, whatever the source happens to say that day.
"""

from __future__ import annotations

import re
from collections.abc import Iterable


def _pattern(term: str) -> re.Pattern[str]:
    """Match ``term`` as a whole word or phrase, ignoring case."""
    return re.compile(rf"(?<!\w){re.escape(term.strip())}(?!\w)", re.IGNORECASE)


def find_terms(text: str, terms: Iterable[str]) -> list[str]:
    """Return the forbidden terms that occur in ``text``, in the order given."""
    return [term for term in terms if term.strip() and _pattern(term).search(text)]


def violations(texts: dict[str, str], terms: Iterable[str]) -> dict[str, list[str]]:
    """Map each output name to the forbidden terms found in its text; clean outputs are left out."""
    terms = list(terms)
    found = {name: find_terms(text, terms) for name, text in texts.items()}
    return {name: hits for name, hits in found.items() if hits}

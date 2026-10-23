"""Reading a schema.org ``Person`` from a page's JSON-LD, as a baseline for ``basics``.

Many personal sites publish one for search engines, so it is the most portable source
of a name, title, location and profile links, with no selectors at all.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# Hosts with a conventional display name; anything else shows its domain.
NETWORKS = {
    "x.com": "X",
    "twitter.com": "Twitter",
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "linkedin.com": "LinkedIn",
    "youtube.com": "YouTube",
    "medium.com": "Medium",
    "artstation.com": "ArtStation",
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "mastodon.social": "Mastodon",
    "bsky.app": "Bluesky",
    "dribbble.com": "Dribbble",
    "behance.net": "Behance",
    "stackoverflow.com": "Stack Overflow",
}


def _objects(node: Any) -> list[dict[str, Any]]:
    """Flatten a JSON-LD value (an object, a list, an ``@graph``) into its objects."""
    if isinstance(node, list):
        return [obj for item in node for obj in _objects(item)]
    if isinstance(node, dict):
        return [node, *_objects(node.get("@graph", []))]
    return []


def _is_person(obj: dict[str, Any]) -> bool:
    """Tell whether a JSON-LD object's ``@type`` is, or includes, Person."""
    kind = obj.get("@type")
    return kind == "Person" or (isinstance(kind, list) and "Person" in kind)


def find_person(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Return the first Person object in the page's JSON-LD blocks; ignore broken ones."""
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except ValueError:
            continue
        for obj in _objects(data):
            if _is_person(obj):
                return obj
    return None


def _text(value: Any) -> str | None:
    """Read a JSON-LD value that may be a string or an object with a name or URL."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("name") or value.get("url") or value.get("@id")
    return None


def profile_from_url(url: str) -> dict[str, str]:
    """Guess a profile's network and username from its URL."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    segments = [s for s in parsed.path.split("/") if s and s not in ("in", "u", "user")]
    profile = {"network": NETWORKS.get(host, host), "url": url}
    if segments:
        profile["username"] = segments[-1].removeprefix("@")
    return profile


def person_to_basics(person: dict[str, Any]) -> dict[str, Any]:
    """Map a schema.org Person onto the model's ``basics``."""
    basics: dict[str, Any] = {
        "name": _text(person.get("name")),
        "label": _text(person.get("jobTitle")),
        "summary": _text(person.get("description")),
        "url": _text(person.get("url")),
        "image": _text(person.get("image")),
        "phone": _text(person.get("telephone")),
    }
    if email := _text(person.get("email")):
        basics["email"] = email.removeprefix("mailto:")
    address = person.get("address")
    if isinstance(address, dict):
        basics["location"] = {
            "address": _text(address.get("streetAddress")),
            "postalCode": _text(address.get("postalCode")),
            "city": _text(address.get("addressLocality")),
            "region": _text(address.get("addressRegion")),
            "countryCode": _text(address.get("addressCountry")),
        }
    same_as = person.get("sameAs") or []
    links = [same_as] if isinstance(same_as, str) else same_as
    basics["profiles"] = [profile_from_url(link) for link in links if isinstance(link, str)]
    return basics

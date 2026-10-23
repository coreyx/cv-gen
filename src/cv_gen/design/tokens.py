"""Reading a design system in the W3C Design Tokens (DTCG) format.

A DTCG document is a tree of groups; a node with ``$value`` is a token, ``$type`` on a
group applies to the tokens under it, and a value written ``{group.token}`` is an alias
for another token's value. See https://www.designtokens.org/tr/drafts/format/.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cv_gen.config import is_url
from cv_gen.errors import CvGenError
from cv_gen.fetch import fetch_bytes

EXTENSION_KEY = "com.cv-gen"


@dataclass
class Token:
    """One design token: its dotted path, raw value and type (possibly inherited)."""

    path: str
    value: Any
    type: str | None


@dataclass
class TokenDocument:
    """A loaded tokens file and where it came from."""

    data: dict[str, Any]
    ref: str
    is_remote: bool
    folder: Path | None  # for resolving a local file's own relative paths

    @property
    def extensions(self) -> dict[str, Any]:
        """The root ``$extensions["com.cv-gen"]`` block, or an empty mapping."""
        block = self.data.get("$extensions", {})
        own = block.get(EXTENSION_KEY, {}) if isinstance(block, dict) else {}
        return own if isinstance(own, dict) else {}


def load_document(
    ref: str, sha256: str | None = None, base_dir: Path | None = None
) -> TokenDocument:
    """Read a tokens file from a path or an ``https`` URL, checking its pin if given.

    The SHA-256 pin is computed over the exact bytes received, so a design system
    published at a URL cannot change under a build that pinned it.
    """
    remote = is_url(ref)
    if remote:
        body, _ = fetch_bytes(ref, https_only=True)
        folder = None
    else:
        path = Path(ref).expanduser()
        if not path.is_absolute() and base_dir is not None:
            path = (base_dir / path).resolve()
        if not path.is_file():
            raise CvGenError(f"no such design system file: {path}")
        body = path.read_bytes()
        folder = path.parent
        ref = str(path)
    if sha256 is not None:
        actual = hashlib.sha256(body).hexdigest()
        if actual.lower() != sha256.strip().lower():
            raise CvGenError(
                f"design system {ref} does not match its sha256 pin",
                f"expected {sha256}, got {actual}; update the pin only if you trust the change",
            )
    text = body.decode("utf-8-sig", errors="replace")
    try:
        data = json.loads(text) if text.lstrip().startswith("{") else yaml.safe_load(text)
    except (ValueError, yaml.YAMLError) as error:
        raise CvGenError(f"design system {ref} is not valid JSON or YAML: {error}") from error
    if not isinstance(data, dict):
        raise CvGenError(f"design system {ref} must be a mapping of token groups")
    return TokenDocument(data=data, ref=ref, is_remote=remote, folder=folder)


def flatten(data: dict[str, Any]) -> dict[str, Token]:
    """Return every token in a DTCG tree by dotted path, with inherited ``$type``."""
    tokens: dict[str, Token] = {}

    def walk(node: dict[str, Any], prefix: str, inherited: str | None) -> None:
        group_type = node.get("$type", inherited)
        for key, child in node.items():
            if key.startswith("$") or not isinstance(child, dict):
                continue
            path = f"{prefix}.{key}" if prefix else key
            if "$value" in child:
                tokens[path] = Token(path, child["$value"], child.get("$type", group_type))
            else:
                walk(child, path, group_type)

    walk(data, "", None)
    return tokens


def _alias_target(value: Any) -> str | None:
    """Return the path a whole-value alias (``"{color.brand}"``) points to, if it is one."""
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        return value[1:-1].strip()
    return None


def resolve_aliases(tokens: dict[str, Token]) -> dict[str, Token]:
    """Replace every alias with the value it refers to, following chains.

    A token with no type of its own takes its target's type. An alias to a missing
    token, or a cycle of aliases, is an error naming the token.
    """
    resolved: dict[str, Token] = {}

    def resolve(path: str, chain: tuple[str, ...]) -> Token:
        if path in resolved:
            return resolved[path]
        token = tokens[path]
        target = _alias_target(token.value)
        if target is None:
            resolved[path] = token
            return token
        if target in chain or target == path:
            raise CvGenError(
                f"design token '{chain[0]}' has a circular alias: {' -> '.join((*chain, target))}"
            )
        if target not in tokens:
            raise CvGenError(f"design token '{path}' refers to unknown token '{target}'")
        final = resolve(target, (*chain, target))
        result = Token(path, final.value, token.type or final.type)
        resolved[path] = result
        return result

    for path in tokens:
        resolve(path, (path,))
    return resolved

# SPDX-License-Identifier: Apache-2.0
"""Identifiers and versions (`record_format.md` sections 7 and 8), and material references.

Every pattern here is matched in full, with `re.fullmatch`, never searched: `$` also matches before a final
newline. Character classes are written out, since `\\d` would match any Unicode digit.
"""

import functools
import re
from dataclasses import dataclass

from materica import shapes

NAMESPACE = re.compile(r"[a-z0-9_]+")
RECORD_ID = re.compile(r"[a-z0-9_]+/[A-Za-z0-9_.-]+")
FAMILY_ID = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)+\.v[1-9][0-9]*")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_COMPONENT = re.compile(r"0|[1-9][0-9]*")
CONTENT_HASH = re.compile(r"sha256:[0-9a-f]{64}")
# A request's field, `<section>.<field>` (`read_side_contract.md` section 1).
FIELD = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")


@functools.total_ordering
@dataclass(frozen=True)
class Version:
    """`MAJOR.MINOR.PATCH`, its components kept as their digits.

    Section 8 compares components as numbers. With no leading zeros, which construction refuses, comparing
    their lengths and then their digits gives that order for any length, where `int` refuses more than 4300
    digits.
    """

    major: str
    minor: str
    patch: str

    def __post_init__(self) -> None:
        for component in (self.major, self.minor, self.patch):
            if not _COMPONENT.fullmatch(component):
                raise ValueError(f"not a version component: {component!r}")

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() < other._key()

    def _key(self) -> tuple[tuple[int, str], ...]:
        return tuple((len(component), component) for component in (self.major, self.minor, self.patch))


def parse_version(text: str) -> Version | None:
    """The version `text` writes, or None where it does not match section 8's pattern in full."""
    matched = VERSION.fullmatch(text)
    return None if matched is None else Version(matched[1], matched[2], matched[3])


@dataclass(frozen=True)
class MaterialRef:
    """A material reference: a record's `id` and `version`, and its `content_hash` as the pin."""

    id: str
    version: str
    content_hash: str

    def to_json(self) -> shapes.MaterialRef:
        return {"id": self.id, "version": self.version, "content_hash": self.content_hash}

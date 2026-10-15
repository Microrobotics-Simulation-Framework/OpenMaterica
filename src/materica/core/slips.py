# SPDX-License-Identifier: Apache-2.0
"""Names one slip apart (`record_format.md` section 10).

A reader refuses a member it does not know that is one slip from a member the shape names at its place
(section 10 item 5, and `read_side_contract.md` section 1 for a request), and the specification keeps the
names valid at one place more than one slip apart, which `tests/spec_sync/name_overlaps.py` checks with the
same relation.
"""

from collections.abc import Collection, Iterable

_IRREGULAR_PLURALS = {"datum": "data", "index": "indices", "matrix": "matrices"}


def one_slip(a: str, b: str) -> str | None:
    """The slip that makes `a` into `b`, or None where there is none: one character inserted, deleted or
    substituted, an underscore included; two adjacent characters swapped; or one `_`-separated word made
    plural or singular. Characters are code points. A name is never one slip from itself."""
    first, second = a.split("_"), b.split("_")
    if len(first) == len(second):
        differing = [(x, y) for x, y in zip(first, second, strict=True) if x != y]
        if len(differing) == 1 and plural_of(*differing[0]):
            return "singular or plural"
    if len(a) == len(b):
        positions = [index for index, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
        if len(positions) == 1:
            return "a character substituted"
        if len(positions) == 2 and positions[1] == positions[0] + 1:
            i, j = positions
            if a[i] == b[j] and a[j] == b[i]:
                return "two characters swapped"
        return None
    shorter, longer = sorted((a, b), key=len)
    if len(longer) - len(shorter) == 1:
        for index, character in enumerate(longer):
            if longer[:index] + longer[index + 1 :] == shorter:
                return "an underscore added" if character == "_" else "a character added"
    return None


def plural_of(a: str, b: str) -> bool:
    """Whether one word is the other made plural or singular: `s` or `es` added at its end, a final `y`
    exchanged with `ies`, or `datum` with `data`, `index` with `indices` and `matrix` with `matrices`. The
    empty string between two underscores is no word, so `s` is not its plural."""
    singular, plural = sorted((a, b), key=len)
    return bool(singular) and (
        plural in (singular + "s", singular + "es")
        or (singular.endswith("y") and plural == singular[:-1] + "ies")
        or _IRREGULAR_PLURALS.get(singular) == plural
        or _IRREGULAR_PLURALS.get(plural) == singular
    )


def slipped(members: Iterable[str], named: Collection[str]) -> list[tuple[str, str]]:
    """Each of `members` that `named` does not hold and that is one slip from a name it holds, with the first
    such name in sorted order: the members section 10 item 5 refuses where the others are ignored."""
    found: list[tuple[str, str]] = []
    for member in members:
        if member not in named:
            name = next((name for name in sorted(named) if one_slip(member, name) is not None), None)
            if name is not None:
                found.append((member, name))
    return found

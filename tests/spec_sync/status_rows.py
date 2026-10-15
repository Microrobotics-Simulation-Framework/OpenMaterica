# SPDX-License-Identifier: Apache-2.0
"""The members that may hold a status object, and what one holds there, as `provenance.md` section 1 item 5
gives them: the writer schema's places, which `test_value_fields.py` holds to that section's table, and the
members of the shape S a status object stands for there, from the writer schema and, for a condition, from the
section's own list.

Step 8's oracles (HP3's strategies, the positions test) read status objects from here, never from
`value_shapes.status_row`, which step 8 itself reads, so that a fault there cannot move the code and its
oracles together (S2a-2's review, L5).
"""

import re

from tests.spec_sync.test_value_fields import DEFINITIONS, alternatives, document, members, status_places

PLACES = status_places(DEFINITIONS)


def condition_members(text: str) -> tuple[str, ...]:
    """The members of either shape of a condition, which a status object standing for one may not hold beside
    it, as section 1 lists them: "(for a condition, `value`, `range`, ... and `set_or_measured`;"."""
    found = re.search(r"\(for a condition, ((?:`[a-z_]+`(?:, | and )?)+);", re.sub(r"\s+", " ", text))
    if found is None:
        raise ValueError("provenance.md section 1 lists no members for a condition")
    return tuple(re.findall(r"`([a-z_]+)`", found[1]))


CONDITION_MEMBERS = condition_members(document("provenance.md"))


def tokens(definition: str, member: str) -> tuple[str, ...]:
    """The status tokens a status object may hold in `member` of `definition`: its place's, or those of the
    definition it refers to where that is a choice with a status object (a unit, a count)."""
    held = PLACES.get((definition, member))
    if held is None:
        referred = alternatives(members(DEFINITIONS, definition)[member])
        held = frozenset[str]().union(*(PLACES.get((name, None), frozenset[str]()) for name in referred))
    if not held:
        raise ValueError(f"{definition}.{member} takes no status object")
    return tuple(sorted(held))


def defines(definition: str, member: str) -> tuple[str, ...]:
    """The members of the shape S that a status object in `member` of `definition` stands for, none where S
    is a number, a string or a token; for a condition, both shapes' members, as section 1 lists them."""
    if definition == "conditions":
        return CONDITION_MEMBERS
    return tuple(dict.fromkeys(shape_members(members(DEFINITIONS, definition)[member])))


def shape_members(subschema: object) -> list[str]:
    """The members of every object definition `subschema` refers to, through choices, status objects aside."""
    found: list[str] = []
    for name in alternatives(subschema):  # type: ignore[arg-type]  # a schema read from JSON
        definition = DEFINITIONS[name]
        if name.startswith("status_"):
            continue
        if "properties" in definition or "allOf" in definition:
            found += members(DEFINITIONS, name)
        else:
            found += shape_members(definition)
    return found

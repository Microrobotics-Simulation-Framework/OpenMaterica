# SPDX-License-Identifier: Apache-2.0
"""Mutants of step 8 (`core/value_shapes.py`, `core/fields.py`), each with one fault, and the property of
`test_value_field_properties.py` that must kill each one. As in `test_mutants.py`, each must die within the
examples the `ci` profile gives a property, at both sizes, and records the examples its kill took as
`examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function or table of
`value_shapes` or `fields`, or the `members` helper wrapped so that it checks one member otherwise.
"""

from collections.abc import Callable, Collection, Iterable

import pytest
from hypothesis import strategies as st

from materica import shapes
from materica.core import fields, read, value_shapes
from materica.core.fields import RecordField
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.slips import one_slip
from materica.core.value_shapes import Check, Found, JsonObject, Members
from tests.property import test_value_field_properties as properties
from tests.property import value_field_strategies as strategies
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_mutants import Mutant, killed_by, setting


def faulty(size: Size) -> st.SearchStrategy[strategies.Example]:
    return strategies.faulty_records(size)


def unknowns(size: Size) -> st.SearchStrategy[properties.Unknowns]:
    return properties.with_unknowns(size)


ONE_FAULT = killed_by(faulty, properties.check_one_fault)
IGNORANCE = killed_by(unknowns, properties.check_ignored)


# Faults in what a token, a status object or a slip is.


TOKEN_PROBLEMS = value_shapes.token_problems


def _unknown_tokens_ignored(
    value: JsonValue, member: str, allowed: Collection[str], where: str, found: Found
) -> None:
    if not isinstance(value, str) or value in value_shapes.KNOWN[member]:
        TOKEN_PROBLEMS(value, member, allowed, where, found)


def _unknown_token_read_as_a_shape_fault(detail: str) -> Reason:
    return Reason("form_invalid", detail=detail)


STATUS_OBJECT = value_shapes.status_object


def _status_tokens_unchecked(
    value: JsonObject, where: str, tokens: Collection[str] | None, defines: Collection[str], found: Found
) -> None:
    STATUS_OBJECT(value, where, None, defines, found)


def _members_beside_a_status_ignored(
    value: JsonObject, where: str, tokens: Collection[str] | None, defines: Collection[str], found: Found
) -> None:
    kept = value if not defines else {name: member for name, member in value.items() if name not in defines}
    STATUS_OBJECT(kept, where, tokens, defines, found)


def slipped_by(
    relation: Callable[[str, str], str | None],
) -> Callable[[Iterable[str], Collection[str]], list[tuple[str, str]]]:
    """`slips.slipped`, with `relation` in place of `one_slip`."""

    def slipped(members: Iterable[str], named: Collection[str]) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for member in members:
            if member not in named:
                name = next((name for name in sorted(named) if relation(member, name) is not None), None)
                if name is not None:
                    found.append((member, name))
        return found

    return slipped


def without(*kinds: str) -> Callable[[str, str], str | None]:
    """`one_slip`, blind to the slips of `kinds`."""

    def relation(a: str, b: str) -> str | None:
        slip = one_slip(a, b)
        return None if slip in kinds else slip

    return relation


def within_two_slips(a: str, b: str) -> str | None:
    """Two names one or two characters apart, a relation wider than section 10's."""
    if one_slip(a, b) is not None:
        return "one slip"
    longer, shorter = sorted((a, b), key=len, reverse=True)
    return "two added" if len(longer) - len(shorter) == 2 and longer.startswith(shorter) else None


# Faults in which members a check reads, and how: `members` wrapped.

MEMBERS = value_shapes.members


def members_with(change: Callable[[Members], Members]) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection under which `members` checks the required and optional members `change` gives."""

    def checked(
        value: JsonValue,
        where: str,
        found: Found,
        required: Members,
        optional: Members | None = None,
        *,
        named: Collection[str] = (),
    ) -> JsonObject | None:
        changed = change({**required, **{f"?{name}": check for name, check in (optional or {}).items()}})
        required = {name: check for name, check in changed.items() if not name.startswith("?")}
        optional = {name[1:]: check for name, check in changed.items() if name.startswith("?")}
        return MEMBERS(value, where, found, required, optional, named=named)

    return setting(value_shapes, "members", checked)


def replacing(name: str, check: Check) -> Callable[[Members], Members]:
    return lambda checks: {key: check if key.lstrip("?") == name else value for key, value in checks.items()}


def optional(name: str) -> Callable[[Members], Members]:
    return lambda checks: {(f"?{key}" if key == name else key): value for key, value in checks.items()}


def _any(value: JsonValue, where: str, found: Found) -> None:
    pass


def _lists(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, list):
        found.append(value_shapes.invalid(f"{where} is not a list"))


def _without_nulls(
    value: JsonValue,
    where: str,
    found: Found,
    required: Members,
    optional: Members | None = None,
    *,
    named: Collection[str] = (),
) -> JsonObject | None:
    if isinstance(value, dict):
        value = {name: member for name, member in value.items() if member is not None}
    return MEMBERS(value, where, found, required, optional, named=named)


def _unknown_condition_names_checked(value: JsonValue, where: str, found: Found) -> None:
    if isinstance(value, dict):
        for name, entry in value.items():
            check = value_shapes.CONDITIONS.get(name, value_shapes.NUMERIC_CONDITION)
            check(entry, f"{where}.{name}", found)


def _every_unnamed_member_refused(
    value: JsonObject, named: Collection[str], where: str, found: Found
) -> None:
    for member in value:
        if member not in named:
            found.append(value_shapes.invalid(f"{where} holds {member!r}, which it does not name"))


def _nothing(*arguments: object) -> None:
    pass


def _no_record_problems(record: JsonObject) -> Found:
    return []


FORM_PROBLEMS = fields.form_problems


def _first_refusal_only(field: RecordField, record: JsonObject, claims: Collection[str]) -> Found:
    return FORM_PROBLEMS(field, record, claims)[:1]


def _section_specimen_unchecked(name: str, section: JsonObject) -> Found:
    return value_shapes.section_problems(
        name, {key: member for key, member in section.items() if key != "specimen"}
    )


COUNT_AS_NUMBER = value_shapes.or_status(value_shapes.number, shapes.StatisticsBlock, "n_specimens")


def facts_with(**shapes_of: value_shapes.Check) -> dict[str, value_shapes.Check]:
    """Step 8's specimen facts, the named ones checked as `shapes_of` gives."""
    changed = {
        name: value_shapes.or_status(check, shapes.Specimen, name) for name, check in shapes_of.items()
    }
    return {**value_shapes.FACTS, **changed}


STATE = value_shapes.fact_token("disease_and_treatment_state")
TEXT_ANYWHERE = facts_with(
    disease_and_treatment_state=value_shapes.based({"token": STATE}, {"text": value_shapes.string})
)
ANY_UNIT_OR_BASIS = facts_with(
    post_mortem_interval=value_shapes.based({"value": value_shapes.number, "unit": value_shapes.unit}),
    mimics=value_shapes.based({"text": value_shapes.string}),
)

MUTANTS = [
    Mutant(
        "unknown_tokens_ignored", ONE_FAULT, setting(value_shapes, "token_problems", _unknown_tokens_ignored)
    ),
    Mutant(
        "unknown_token_read_as_a_shape_fault",
        ONE_FAULT,
        setting(value_shapes, "unknown_token", _unknown_token_read_as_a_shape_fault),
    ),
    Mutant(
        "status_tokens_unchecked", ONE_FAULT, setting(value_shapes, "status_object", _status_tokens_unchecked)
    ),
    Mutant(
        "members_beside_a_status_ignored",
        ONE_FAULT,
        setting(value_shapes, "status_object", _members_beside_a_status_ignored),
    ),
    Mutant("missing_represents_accepted", ONE_FAULT, members_with(optional("represents"))),
    Mutant("null_read_as_absent", ONE_FAULT, setting(value_shapes, "members", _without_nulls)),
    Mutant(
        "unknown_condition_names_checked",
        ONE_FAULT,
        setting(value_shapes, "conditions", _unknown_condition_names_checked),
    ),
    Mutant("plus_minus_kinds_unchecked", ONE_FAULT, members_with(replacing("plus_minus", _lists))),
    Mutant("range_order_unchecked", ONE_FAULT, members_with(replacing("range", _any))),
    Mutant("counts_not_whole", ONE_FAULT, members_with(replacing("n_specimens", COUNT_AS_NUMBER))),
    Mutant(
        "conditional_members_unchecked", ONE_FAULT, setting(value_shapes, "present_exactly_where", _nothing)
    ),
    Mutant("uncertainty_rules_unchecked", ONE_FAULT, setting(value_shapes, "uncertainty_rules", _nothing)),
    Mutant("named_state_text_unchecked", ONE_FAULT, setting(value_shapes, "FACTS", TEXT_ANYWHERE)),
    Mutant("fixed_fact_members_unchecked", ONE_FAULT, setting(value_shapes, "FACTS", ANY_UNIT_OR_BASIS)),
    Mutant("record_structure_unchecked", ONE_FAULT, setting(fields, "record_problems", _no_record_problems)),
    Mutant(
        "section_specimen_unchecked",
        ONE_FAULT,
        setting(fields, "section_problems", _section_specimen_unchecked),
    ),
    Mutant("first_refusal_only", ONE_FAULT, setting(read, "form_problems", _first_refusal_only)),
    *[
        Mutant(
            f"slip_by_{name}_missed", ONE_FAULT, setting(value_shapes, "slipped", slipped_by(without(*kinds)))
        )
        for name, kinds in {
            "substitution": ("a character substituted",),
            "insertion": ("a character added",),
            "swap": ("two characters swapped",),
            "plural": ("singular or plural",),
            "underscore": ("an underscore added",),
        }.items()
    ],
    Mutant(
        "unknown_members_refused", IGNORANCE, setting(value_shapes, "slips", _every_unnamed_member_refused)
    ),
    Mutant("two_slips_refused", IGNORANCE, setting(value_shapes, "slipped", slipped_by(within_two_slips))),
]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    mutant.inject(monkeypatch)
    record_property("examples_to_kill", mutant.search(size))

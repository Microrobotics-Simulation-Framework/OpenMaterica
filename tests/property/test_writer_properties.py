# SPDX-License-Identifier: Apache-2.0
"""(7) The writer schema takes every value field the specification allows, and refuses each field it
forbids by one fault (`record_format.md` section 1 item 2: the writer schema is closed, every enumerated
member limited to its listed tokens). It takes every registered field in its place, a section's `fields` or
an overlay's `replaces`, bound to its row of section 4.1, and refuses one under a name its section does not
register or holding what its row does not give (maintainer, 2026-10-15). The fields come from
`value_fields.py`, built from the text and the vocabulary's rows, never from the schema or the bindings it
applies. Each refusal is checked on a field the schema takes, the same field but for the fault, so that it is
the fault's. And what it takes in a body, step 9 of a read passes. The mutants they kill are in
`test_writer_mutants.py`."""

import math
from collections.abc import Iterable
from dataclasses import replace
from typing import NamedTuple
from urllib.parse import urljoin

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core.fields import RecordField, unit_problems
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.vocabulary import VOCABULARY
from tests.conftest import EXAMPLES
from tests.property import audits, value_fields
from tests.property.strategies import SIZE, Size
from tests.property.support import feature
from tests.property.value_fields import (
    ANY,
    FAMILIES,
    FAULTS,
    FIXED_UNITS,
    NUMERIC_CONDITIONS,
    REGISTERED_UNITS,
    TOKEN_CONDITIONS,
    Faulty,
    Json,
    Plan,
    listing,
    mapping,
    registered_unit,
    row_of,
)
from tests.spec_sync.schemas import BASE, why_refused
from tests.verdicts import verdict

VALUE_FIELD: Json = {"$ref": urljoin(BASE, "record.writer.json#/$defs/value_field")}
# A record body: a material's, holding registered fields in their sections, or an overlay's, replacing them.
BODY: Json = {
    "anyOf": [
        {"$ref": urljoin(BASE, "record.writer.json#/$defs/material_body")},
        {"$ref": urljoin(BASE, "record.writer.json#/$defs/overlay_body")},
    ]
}


class Writer:
    """The writer schema at `place`, a value field or a record body, with each of `files` (a schema file, the
    writer's or the vocabulary's, a mutant of it) in place of the tree's: its verdict jsonschema-rs's, and the
    messages for a field it refuses python-jsonschema's."""

    def __init__(self, place: Json = VALUE_FIELD, files: Iterable[Json] = ()) -> None:
        files = tuple(files)
        self.verdict = verdict(place, files)
        self.messages = why_refused(place, files)

    def takes(self, field: JsonValue) -> bool:
        return self.verdict(field)

    def errors(self, field: JsonValue) -> list[str]:
        return [message[:200] for message in self.messages(field)][:3]


WRITER = Writer()
PLACED = Writer(BODY)
# The writer each family's faults are checked against: a binding's in a body, the others' in a value field.
WRITERS = {"binding": PLACED}


def check_takes(writer: Writer, field: JsonValue) -> None:
    assert writer.takes(field), f"refused a field the text allows: {writer.errors(field)}"


def check_refuses(writer: Writer, faulty: Faulty) -> None:
    assert writer.takes(faulty.base), (
        f"refused the field {faulty.fault} was drawn on: {writer.errors(faulty.base)}"
    )
    assert not writer.takes(faulty.field), f"took the fault {faulty.fault} at {faulty.place}"


def record_features(field: JsonValue) -> None:
    alternatives = "alternatives" in mapping(field)
    feature("alternatives", alternatives)
    for one in map(mapping, listing(mapping(field)["alternatives"]) if alternatives else [field]):
        feature(f"form_{one['form']}")
        feature("withheld", one.get(value_fields.form_member(str(one["form"]))) == {"status": "withheld"})
        block = one.get("statistics")
        if isinstance(block, dict) and "represents" in block:
            uncertainties = [block[name] for name in ("relative_uncertainty", "expanded_uncertainty")]
            feature(
                "uncertainty", any(isinstance(found, dict) and "value" in found for found in uncertainties)
            )
        conditions = mapping(one["conditions"]).values()
        feature("status_condition", any("status" in mapping(entry) for entry in conditions))
        feature("specimen", "specimen" in one)


# The acceptance properties declare each feature by the chance that a draw shows it: its share measured at
# the `ci` profile over 48 runs of 2,000 examples (2026-10-15), rounded down to two places, and each field's
# at the least of the fields' (0.137 to 0.148). Hypothesis shows a draw in clusters of examples, so at `ci`
# each feature is held to its draw floor (`audits.draw_floor`), and at `dev` and `deep` to a third of its
# chance.
@pytest.mark.chances(
    alternatives=0.15,
    withheld=0.2,
    uncertainty=0.62,
    status_condition=0.53,
    specimen=0.47,
    form_constant=0.15,
    form_table=0.13,
    form_power_law=0.13,
    form_interval=0.14,
    form_composition=0.14,
    form_parameter_set=0.13,
    form_reference_data=0.13,
    form_evidence=0.12,
)
@given(value_fields.fields())
def test_the_writer_schema_takes_every_field_the_text_allows(field: JsonValue) -> None:
    record_features(field)
    check_takes(WRITER, field)


def record_body_features(body: Json) -> None:
    container, name, registered = value_fields.placed(body)
    feature(f"field_{registered}")
    feature("place_fields", "sections" in body)
    feature("alternatives", "alternatives" in mapping(container[name]))


@pytest.mark.chances(
    **{f"field_{name}": 0.13 for name in value_fields.FIELDS},
    place_fields=0.66,
    alternatives=0.16,
)
@given(value_fields.bodies())
def test_the_writer_schema_takes_every_registered_field_in_its_place(body: Json) -> None:
    record_body_features(body)
    check_takes(PLACED, body)


def strata(family: str) -> list[tuple[str, ...]]:
    """The family's faults in the fewest parts, each drawn by a property of its own, at which the `ci`
    profile's examples give each fault a draw floor its audit can judge (`audits.draw_floor`); the parts take
    the faults in turn, so that each mixes the plans the faults are built on."""
    names = [fault.name for fault in FAULTS if fault.family == family]
    parts = next(
        parts
        for parts in range(1, len(names) + 1)
        if audits.draw_floor(EXAMPLES["ci"], 1 / math.ceil(len(names) / parts)) >= audits.LEAST_DRAWS
    )
    return [tuple(names[part::parts]) for part in range(parts)]


def stratum_id(family: str, part: int, parts: int) -> str:
    return family if parts == 1 else f"{family}-{part + 1}of{parts}"


@pytest.mark.parametrize(
    ("family", "faults"),
    [
        pytest.param(
            family, faults, id=stratum_id(family, part, len(parts)), marks=pytest.mark.drawn(*faults)
        )
        for family, parts in ((family, strata(family)) for family in FAMILIES)
        for part, faults in enumerate(parts)
    ],
)
@given(data=st.data())
def test_the_writer_schema_refuses_each_fault_the_text_names(
    family: str, faults: tuple[str, ...], data: st.DataObject
) -> None:
    faulty = data.draw(value_fields.faulty_fields(family, only=faults))
    feature(faulty.fault)
    check_refuses(WRITERS.get(family, WRITER), faulty)


# What the writer takes in a body, step 9 passes (`read_side_contract.md` section 3, step 9): the writer binds
# each unit step 9 compares to the one registered for it (maintainer, 2026-10-15), so that no record a reader
# must refuse there can be written. A body the text allows, or one planned with every condition and fact, its
# unit changed at a place step 9 compares, in the field or its first alternative: a writer that takes it
# fails the relation.

UNIT_PLACES = ("none", "field", "condition", "plus_minus", "token_condition", "fact")
ON_A_CONDITION = ("condition", "plus_minus", "token_condition")
WITH_EVERY_UNIT = Plan(rich=frozenset({"conditions", "specimen"}))
WITH_CONDITIONS = [name for name in value_fields.FIELDS if set(listing(row_of(name)["forms"])) - {"evidence"}]


class Changed(NamedTuple):
    place: str  # where a unit was changed, `none` where none was
    body: Json


@st.composite
def another_unit(draw: st.DrawFn, own: JsonValue) -> JsonValue:
    """A unit step 9 refuses where `own` is registered: another registered unit, `own` with a space or in
    capitals, or a status object of another token."""
    strings: list[JsonValue] = [unit for unit in REGISTERED_UNITS if unit != own]
    if isinstance(own, str):
        strings += [own + " ", own.upper()] if own.upper() != own else [own + " "]
    token = mapping(own)["status"] if isinstance(own, dict) else None
    statuses: list[JsonValue] = [{"status": other} for other in value_fields.ANY_STATUS if other != token]
    return draw(st.sampled_from([*strings, *statuses]))


@st.composite
def bodies_with_a_unit_changed(
    draw: st.DrawFn, among: tuple[str, ...] = UNIT_PLACES, plan: Plan = WITH_EVERY_UNIT, size: Size = SIZE
) -> Changed:
    place = draw(st.sampled_from(among))
    if place == "none":
        return Changed(place, draw(value_fields.bodies(ANY, size)))
    if place in ON_A_CONDITION:
        # An evidence field holds no conditions.
        registered = plan.registered or draw(st.sampled_from(WITH_CONDITIONS))
        forms = [str(form) for form in listing(row_of(registered)["forms"]) if form != "evidence"]
        plan = replace(plan, registered=registered, form=draw(st.sampled_from(forms)))
    body = draw(value_fields.bodies(plan, size))
    container, name, registered = value_fields.placed(body)
    value = mapping(container[name])
    field = mapping(listing(value["alternatives"])[0]) if "alternatives" in value else value
    conditions = mapping(field["conditions"])
    if place == "field":
        field["unit"] = draw(another_unit(row_of(registered)["unit"]))
    elif place in ("condition", "plus_minus"):
        # A table's axis condition is `not_applicable`, a status object, which holds no unit.
        held = [name for name in NUMERIC_CONDITIONS if "status" not in mapping(conditions[name])]
        condition_name = draw(st.sampled_from(held))
        condition = mapping(conditions[condition_name])
        entries = listing(condition["plus_minus"])
        holder = condition if place == "condition" else mapping(draw(st.sampled_from(entries)))
        holder["unit"] = draw(another_unit(registered_unit(condition_name)))
    elif place == "token_condition":
        token_condition = mapping(conditions[draw(st.sampled_from(TOKEN_CONDITIONS))])
        any_unit: list[JsonValue] = [*REGISTERED_UNITS, {"status": "unstated"}]
        token_condition["unit"] = draw(st.sampled_from(any_unit))
    else:
        fact_name = draw(st.sampled_from(sorted(FIXED_UNITS)))
        fact = mapping(mapping(field["specimen"])[fact_name])
        fact["unit"] = draw(another_unit(FIXED_UNITS[fact_name]))
    return Changed(place, body)


def step_9(body: Json) -> list[Reason]:
    """Step 9's reasons for a body's field, read in its section, each of its alternatives where it holds
    some."""
    container, name, registered = value_fields.placed(body)
    sections = body.get("sections")
    section = mapping(mapping(sections)[registered.partition(".")[0]]) if sections is not None else {}
    value = mapping(container[name])
    found: list[Reason] = []
    for one in listing(value["alternatives"]) if "alternatives" in value else [value]:
        found += unit_problems(RecordField(VOCABULARY.fields[registered], one, section))
    return found


def check_passes_step_9(writer: Writer, changed: Changed) -> bool:
    """Whether `writer` takes the body; where it does, step 9 must pass it."""
    if not writer.takes(changed.body):
        return False
    refused = step_9(changed.body)
    assert not refused, (
        f"the writer takes a body step 9 refuses, changed at the {changed.place}: {refused[:2]}"
    )
    return True


# `taken`, the writer taking the body, declared by its chance, the least share measured in seven runs at `ci`
# (12 to 20%, 2026-10-16): the writer takes the bodies drawn with no unit changed, and no other.
@pytest.mark.chances(taken=0.12)
@pytest.mark.drawn(*UNIT_PLACES)
@given(bodies_with_a_unit_changed())
def test_step_9_passes_every_body_the_writer_takes(changed: Changed) -> None:
    feature(changed.place)
    feature("taken", check_passes_step_9(PLACED, changed))

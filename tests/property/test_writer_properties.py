# SPDX-License-Identifier: Apache-2.0
"""(7) The writer schema takes every value field the specification allows, and refuses each field it
forbids by one fault (`record_format.md` section 1 item 2: the writer schema is closed, every enumerated
member limited to its listed tokens). It takes every registered field in its place, a section's `fields` or
an overlay's `replaces`, bound to its row of section 4.1, and refuses one under a name its section does not
register or holding what its row does not give (maintainer, 2026-10-15). The fields come from
`value_fields.py`, built from the text and the vocabulary's rows, never from the schema or the bindings it
applies. Each refusal is checked on a field the schema takes, the same field but for the fault, so that it is
the fault's. The mutants they kill are in `test_writer_mutants.py`."""

import math
from collections.abc import Iterable
from urllib.parse import urljoin

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing.jsonschema import DRAFT202012

from materica.core.jsonio import JsonValue
from tests.conftest import EXAMPLES
from tests.property import audits, value_fields
from tests.property.support import feature
from tests.property.value_fields import FAMILIES, FAULTS, Faulty, Json, listing, mapping
from tests.spec_sync.schemas import BASE, REGISTRY

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
    writer's or the vocabulary's, a mutant of it) in place of the tree's."""

    def __init__(self, place: Json = VALUE_FIELD, files: Iterable[Json] = ()) -> None:
        registry = REGISTRY
        for schema in files:
            registry = registry.with_resource(str(schema["$id"]), DRAFT202012.create_resource(schema))
        self.checker = Draft202012Validator(place, registry=registry)

    def takes(self, field: JsonValue) -> bool:
        # types-jsonschema types its second overload's instance as unknown.
        return self.checker.is_valid(field)  # pyright: ignore[reportUnknownMemberType]

    def errors(self, field: JsonValue) -> list[str]:
        # types-jsonschema types its second overload's instance as unknown.
        found = self.checker.iter_errors(field)  # pyright: ignore[reportUnknownMemberType]
        return [error.message[:200] for error in found][:3]


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

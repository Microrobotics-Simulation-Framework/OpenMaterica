# SPDX-License-Identifier: Apache-2.0
"""(7) The writer schema takes every value field the specification allows, and refuses each field it
forbids by one fault (`record_format.md` section 1 item 2: the writer schema is closed, every enumerated
member limited to its listed tokens). The fields come from `value_fields.py`, built from the text and the
vocabulary, never from the schema. Each refusal is checked on a field the schema takes, the same field but
for the fault, so that it is the fault's. The mutants they kill are in `test_writer_mutants.py`."""

from urllib.parse import urljoin

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from referencing.jsonschema import DRAFT202012

from materica.core.jsonio import JsonValue
from tests.property import value_fields
from tests.property.support import feature
from tests.property.value_fields import FAMILIES, FAULTS, Faulty, Json, listing, mapping
from tests.spec_sync.schemas import BASE, REGISTRY


class Writer:
    """The writer schema's value field, or that of `schema` in its place (a mutant of it)."""

    def __init__(self, schema: Json | None = None) -> None:
        registry = REGISTRY
        if schema is not None:
            registry = REGISTRY.with_resource(str(schema["$id"]), DRAFT202012.create_resource(schema))
        reference = {"$ref": urljoin(BASE, "record.writer.json#/$defs/value_field")}
        self.checker = Draft202012Validator(reference, registry=registry)

    def takes(self, field: JsonValue) -> bool:
        # types-jsonschema types its second overload's instance as unknown.
        return self.checker.is_valid(field)  # pyright: ignore[reportUnknownMemberType]

    def errors(self, field: JsonValue) -> list[str]:
        # types-jsonschema types its second overload's instance as unknown.
        found = self.checker.iter_errors(field)  # pyright: ignore[reportUnknownMemberType]
        return [error.message[:200] for error in found][:3]


WRITER = Writer()


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


@pytest.mark.features(
    alternatives=0.04,
    withheld=0.07,
    uncertainty=0.2,
    status_condition=0.17,
    specimen=0.14,
    form_constant=0.05,
    form_table=0.05,
    form_power_law=0.04,
    form_interval=0.03,
    form_composition=0.04,
    form_parameter_set=0.04,
    form_reference_data=0.04,
    form_evidence=0.02,
)
@given(value_fields.fields())
def test_the_writer_schema_takes_every_field_the_text_allows(field: JsonValue) -> None:
    record_features(field)
    check_takes(WRITER, field)


def shares(family: str) -> dict[str, float]:
    """A third of each fault's share of its family's draws: each is drawn as often as another."""
    names = [fault.name for fault in FAULTS if fault.family == family]
    return {name: 1 / len(names) / 3 for name in names}


@pytest.mark.parametrize(
    "family", [pytest.param(family, marks=pytest.mark.features(**shares(family))) for family in FAMILIES]
)
@given(data=st.data())
def test_the_writer_schema_refuses_each_fault_the_text_names(family: str, data: st.DataObject) -> None:
    faulty = data.draw(value_fields.faulty_fields(family))
    feature(faulty.fault)
    check_refuses(WRITER, faulty)

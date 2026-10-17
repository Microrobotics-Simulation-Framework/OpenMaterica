# SPDX-License-Identifier: Apache-2.0
"""Fuzz target 4's oracles (`tests/fuzz/field_oracle.py`), which the target itself, needing Atheris, cannot
show here: for a refusal step 8 is missing, quiet on step 8 as it is and failing on a step 8 that lets through
a member of the wrong type; for steps 9 and 10, quiet on them as they are and failing on a step 9 that lets
another unit through and a step 10 that lets a condition outside its tolerance through."""

import json

import pytest

from materica.core import conditions, fields, value_shapes
from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.reasons import Reason
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from tests.fuzz.field_oracle import (
    OPERATING,
    REQUIRED,
    check_no_refusal_missing,
    check_steps_9_and_10,
    passed_step_8,
)
from tests.property.full_fields import full_fields, record_of, request_for

FIELD = "fluid.dynamic_viscosity"


def result_of(field: dict[str, JsonValue]) -> JsonValue:
    """The read's result as the target takes it: "not yet" where a step not built yet would decide it."""
    record = record_of(field)
    record["content_hash"] = content_hash(record)
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    try:
        result = read(request_for(record), store)
    except NotImplementedError:
        return "not yet"
    written: JsonValue = json.loads(json.dumps(result.to_json()))
    return written


def a_count_of_the_wrong_type() -> dict[str, JsonValue]:
    field = full_fields()["population"]
    statistics = field["statistics"]
    assert isinstance(statistics, dict)
    statistics["n_donors"] = "four"
    return field


def test_the_oracle_is_quiet_on_step_8_as_it_is() -> None:
    for field in [*full_fields().values(), a_count_of_the_wrong_type()]:
        check_no_refusal_missing(FIELD, field, result_of(field))


def _any(value: JsonValue, where: str, found: value_shapes.Found) -> None:
    pass


def test_the_oracle_sees_a_refusal_step_8_misses(monkeypatch: pytest.MonkeyPatch) -> None:
    required, optional = value_shapes.STATISTICS
    blind: value_shapes.Members = {**required, "n_donors": _any}
    monkeypatch.setattr(value_shapes, "STATISTICS", (blind, optional))
    field = a_count_of_the_wrong_type()
    with pytest.raises(AssertionError, match="the reader \\$defs refuse"):
        check_no_refusal_missing(FIELD, field, result_of(field))


def a_derivation_beside(origin: str) -> dict[str, JsonValue]:
    """A field of that origin whose derivation's inputs, and so their specimen facts, are empty lists: the
    text refuses the first."""
    field = full_fields()["across_sources"]
    provenance = field["provenance"]
    assert isinstance(provenance, dict)
    derivation = provenance["derivation"]
    assert isinstance(derivation, dict)
    derivation["inputs"] = []
    derivation["input_specimens"] = []
    provenance["origin"] = origin
    return field


def test_the_oracle_is_quiet_on_a_derivation_beside_another_origin() -> None:
    """Step 8 and the reader `$defs` both leave it unread (`provenance.md` section 2 item 6)."""
    field = a_derivation_beside("measured_by_contributor")
    result = result_of(field)
    assert passed_step_8(result), result
    check_no_refusal_missing(FIELD, field, result)


def test_the_oracle_sees_a_derived_value_s_derivation_step_8_misses(monkeypatch: pytest.MonkeyPatch) -> None:
    field = a_derivation_beside("derived")
    assert not passed_step_8(result_of(field))
    monkeypatch.setattr(value_shapes, "derivation_inputs", _any)
    with pytest.raises(AssertionError, match="the reader \\$defs refuse"):
        check_no_refusal_missing(FIELD, field, result_of(field))


# Steps 9 and 10: units by code point, and conditions by HP7's oracle, as the target reads a field.

REQUIRES = VOCABULARY.fields[FIELD].requires
OPERATING_HERE = {name: value for name, value in OPERATING.items() if name in REQUIRES}
REQUIRED_HERE = {name: value for name, value in REQUIRED.items() if name in REQUIRES}


def read_at_operating_conditions(field: dict[str, JsonValue]) -> JsonValue:
    """The read of `field` as the target makes it: at the operating conditions of its row's requirements."""
    record = record_of(field)
    record["content_hash"] = content_hash(record)
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    request = request_for(record)
    request["operating_conditions"] = dict(OPERATING_HERE)
    request["requirement"] = {"want": "value", "conditions": dict(REQUIRED_HERE)}
    try:
        result = read(request, store)
    except NotImplementedError:
        return "not yet"
    written: JsonValue = json.loads(json.dumps(result.to_json()))
    return written


def with_temperature(kelvin: float, unit: JsonValue = "K") -> dict[str, JsonValue]:
    field = full_fields()["population"]
    conditions = field["conditions"]
    assert isinstance(conditions, dict)
    conditions["temperature"] = {"value": kelvin, "unit": unit, "basis": "stated"}
    return field


def check_at_operating_conditions(field: dict[str, JsonValue]) -> None:
    check_steps_9_and_10(FIELD, field, OPERATING_HERE, REQUIRED_HERE, read_at_operating_conditions(field))


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(with_temperature(310.15), id="met"),
        pytest.param(with_temperature(330.0), id="outside"),
        pytest.param(with_temperature(310.15, "Cel"), id="another_unit"),
        pytest.param(with_temperature(310.15, {"status": "unstated"}), id="a_status_unit"),
        *(pytest.param(field, id=name) for name, field in full_fields().items()),
    ],
)
def test_the_oracle_of_steps_9_and_10_is_quiet_on_the_core_as_it_is(field: dict[str, JsonValue]) -> None:
    check_at_operating_conditions(field)


def _every_unit_the_same(stored: JsonValue, registered: JsonValue) -> bool:
    return True


def _every_condition_met(name: str, *_: object) -> Reason | None:
    return None


@pytest.mark.parametrize(
    ("module", "name", "fault", "field", "complaint"),
    [
        pytest.param(
            fields, "same_unit", _every_unit_the_same, with_temperature(310.15, "Cel"), "step 9", id="step_9"
        ),
        pytest.param(
            conditions, "_compared", _every_condition_met, with_temperature(330.0), "step 10", id="step_10"
        ),
    ],
)
def test_the_oracle_of_steps_9_and_10_sees_a_step_that_lets_a_fault_through(
    module: object,
    name: str,
    fault: object,
    field: dict[str, JsonValue],
    complaint: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, name, fault)
    with pytest.raises(AssertionError, match=complaint):
        check_at_operating_conditions(field)

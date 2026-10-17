# SPDX-License-Identifier: Apache-2.0
"""Fuzz target 4's oracles (`tests/fuzz/field_oracle.py`), which the target itself, needing Atheris, cannot
show here: for a refusal step 8 is missing, quiet on step 8 as it is and failing on a step 8 that lets through
a member of the wrong type; for steps 9 and 10, quiet on them as they are and failing on a step 9 that lets
another unit through and a step 10 that lets a condition outside its tolerance through; for HP1 and HP2,
quiet on every result the core gives the full fields under each `want`, and failing on each law broken; and
against the reference model (HP12), quiet on the core as it is, and failing on a step 8 that refuses what the
text reads or lets through what it refuses; and HP12's open point `members_of_the_other_kind` known by its
shape, in a field or an alternative, where the oracle failed before it knew it, a step not built beside it
kept, and a fault beside it still seen."""

import copy
import json
from collections.abc import Callable

import pytest

from materica.core import conditions, fields, value_shapes
from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.reasons import Reason
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.fuzz.field_oracle import (
    OPERATING,
    REQUIRED,
    JsonObject,
    check_against_the_model,
    check_no_refusal_missing,
    check_result_laws,
    check_steps_9_and_10,
    passed_step_8,
    read_outcome,
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


# HP1 and HP2 on every result the target gets.

WANTS = ("value", "bounds", "components", "evidence")


def results_of_every_want(field: dict[str, JsonValue]) -> list[JsonValue]:
    results: list[JsonValue] = []
    for want in WANTS:
        record = record_of(field)
        record["content_hash"] = content_hash(record)
        store = RecordStore()
        store.add("record", json.dumps(record).encode())
        request = request_for(record)
        request["operating_conditions"] = dict(OPERATING_HERE)
        request["requirement"] = {"want": want, "conditions": dict(REQUIRED_HERE)}
        try:
            results.append(json.loads(json.dumps(read(request, store).to_json())))
        except NotImplementedError:
            results.append("not yet")
    return results


@pytest.mark.parametrize("name", sorted(full_fields()))
def test_the_oracle_of_hp1_and_hp2_is_quiet_on_the_core_as_it_is(name: str) -> None:
    fields = [full_fields()[name], with_temperature(330.0), with_temperature(310.15, "Cel")]
    for field in fields:
        for result in results_of_every_want(field):
            check_result_laws(result)


MET: dict[str, JsonValue] = {
    "status": "met",
    "reasons": [],
    "value": 1.0,
    "unit": "kg/m3",
    "conditions": [],
    "specimen": {},
    "statistics": {},
    "provenance": {"origin": "measured_by_contributor", "review": {"status": "not_checked"}},
    "labels": [],
}
OUTSIDE: dict[str, JsonValue] = {"code": "condition_outside", "condition": "temperature"}
NOMINAL: dict[str, JsonValue] = {"acceptance": "nominal", "value": 1.0}


@pytest.mark.parametrize(
    ("result", "complaint"),
    [
        ({**MET, "status": "not_met", "reasons": [OUTSIDE]}, "value where the status is not_met"),
        ({**MET, "reasons": [OUTSIDE]}, "the status met, the worst reason's not_met"),
        ({**MET, "status": "unknown", "reasons": [{"code": "condition_unchecked"}]}, "without its condition"),
        (
            {
                **MET,
                "status": "unknown",
                "reasons": [{"code": "stated_without_origin", "condition": "temperature"}],
            },
            "with the condition",
        ),
        ({**MET, "status": "unknown", "reasons": [OUTSIDE, OUTSIDE]}, "a reason twice"),
        ({key: value for key, value in MET.items() if key != "unit"}, "unit"),
        ({**MET, "assumption": NOMINAL}, "assumption"),
        (
            {"status": "not_met", "reasons": [{"code": "unit_mismatch"}], "conditions": [], "labels": []},
            "conditions",
        ),
    ],
)
def test_the_oracle_of_hp1_and_hp2_sees_each_law_broken(result: dict[str, JsonValue], complaint: str) -> None:
    check_result_laws(MET)
    with pytest.raises(AssertionError, match=complaint):
        check_result_laws(result)


# HP12 on the target's reads: the core against the reference model.


def model_case(field: dict[str, JsonValue], want: str = "value") -> tuple[tuple[bytes, ...], JsonObject]:
    record = record_of(field)
    record["content_hash"] = content_hash(record)
    request = request_for(record)
    requirement = request["requirement"]
    assert isinstance(requirement, dict)
    requirement["want"] = want
    return (json.dumps(record).encode(),), request


WITH_HASH: frozenset[Suite] = frozenset({"plain_read", "hash"})


def against_the_model(sources: tuple[bytes, ...], request: JsonObject) -> None:
    """The target's check, on the read it made, its outcome taken by `read_outcome` as the target takes it."""
    store = RecordStore()
    for number, source in enumerate(sources):
        store.add(f"source_{number}", source)
    _, outcome = read_outcome(lambda: read(request, store, claims=WITH_HASH))
    check_against_the_model(sources, request, WITH_HASH, outcome)


@pytest.mark.parametrize("name", sorted(full_fields()))
def test_the_model_oracle_is_quiet_on_the_core_as_it_is(name: str) -> None:
    for want in ("value", "bounds", "components", "evidence"):
        against_the_model(*model_case(full_fields()[name], want))


def _refuses_every_block(value: JsonValue, where: str, found: value_shapes.Found) -> None:
    found.append(value_shapes.invalid(f"{where} refused by a fault"))


def test_the_model_oracle_sees_a_refusal_step_8_gives_wrongly(monkeypatch: pytest.MonkeyPatch) -> None:
    """S2a-2's review, L3: without the model, no oracle here saw a field step 8 refused that the text
    reads."""
    sources, request = model_case(full_fields()["population"])
    against_the_model(sources, request)
    monkeypatch.setattr(value_shapes, "FIELD_STATISTICS", _refuses_every_block)
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)


def test_the_model_oracle_sees_a_refusal_step_8_misses(monkeypatch: pytest.MonkeyPatch) -> None:
    required, optional = value_shapes.STATISTICS
    monkeypatch.setattr(value_shapes, "STATISTICS", ({**required, "n_donors": _any}, optional))
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(*model_case(a_count_of_the_wrong_type()))


# HP12's open point `members_of_the_other_kind` on the target's reads (S2a-4's review B, M1): the core ignores
# a member of the other kind's shape on a condition, the model refuses it. HP12 knows the point by its draw's
# plant, which a fuzzed field carries none of, so the oracle knows it by its shape (`holds_the_other_kind`).
# The field is met, each condition it holds checked, so that two alternatives of it reach `no_pick`.

MET_CONDITIONS: dict[str, JsonValue] = {
    "temperature": {"value": 310.15, "unit": "K", "basis": "stated"},
    "shear_rate": {"value": 100.0, "unit": "1/s", "basis": "stated"},
    "measurement_dimension": {"value": 5.0e-5, "unit": "m", "basis": "stated"},
    "measurement_geometry": {"token": "tube", "basis": "stated"},
}
OPERATING_MET: JsonObject = {
    "temperature": {"value": 310.15, "unit": "K"},
    "shear_rate": {"value": 100.0, "unit": "1/s"},
    "measurement_dimension": {"value": 5.0e-5, "unit": "m"},
}
REQUIRED_MET: JsonObject = {
    "temperature": {"tolerance": {"value": 1.0, "unit": "K"}},
    "shear_rate": {"tolerance": {"value": 0.0, "unit": "1/s"}},
    "measurement_dimension": {"tolerance": {"value": 0.0, "unit": "m"}},
    "measurement_geometry": {"accept": ["tube"]},
}


def met_field() -> dict[str, JsonValue]:
    field = full_fields()["population"]
    field["conditions"] = copy.deepcopy(MET_CONDITIONS)
    return field


def met_case(field: dict[str, JsonValue]) -> tuple[tuple[bytes, ...], JsonObject]:
    sources, request = model_case(field)
    request["operating_conditions"] = copy.deepcopy(OPERATING_MET)
    request["requirement"] = {"want": "value", "conditions": copy.deepcopy(REQUIRED_MET)}
    return sources, request


def with_the_other_kind(condition: str, member: str, value: JsonValue) -> dict[str, JsonValue]:
    field = met_field()
    conditions = field["conditions"]
    assert isinstance(conditions, dict)
    held = conditions[condition]
    assert isinstance(held, dict)
    held[member] = value
    return field


OTHER_KIND: dict[str, tuple[str, str, JsonValue]] = {
    "numeric-holding-token": ("temperature", "token", "tube"),
    "token-holding-value": ("measurement_geometry", "value", 0.0005),
    "token-holding-range": ("measurement_geometry", "range", [1.0, 2.0]),
    "token-holding-plus-minus": ("measurement_geometry", "plus_minus", []),
    "token-holding-set-or-measured": ("measurement_geometry", "set_or_measured", "measured"),
}


def as_alternatives(field: dict[str, JsonValue]) -> dict[str, JsonValue]:
    other = met_field()
    other["value"] = 0.000701
    return {"alternatives": [field, other]}


def as_the_field(field: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return field


def never(example: object) -> bool:
    return False


def as_an_interval(field: dict[str, JsonValue]) -> dict[str, JsonValue]:
    del field["value"]
    return {**field, "form": "interval", "interval": {"lower": 0.0006, "upper": 0.0008}}


@pytest.mark.parametrize("held", sorted(OTHER_KIND))
@pytest.mark.parametrize(
    "place", [pytest.param(as_the_field, id="field"), pytest.param(as_alternatives, id="alternative")]
)
def test_the_model_oracle_knows_the_other_kind_by_its_shape(
    monkeypatch: pytest.MonkeyPatch, held: str, place: Callable[[dict[str, JsonValue]], dict[str, JsonValue]]
) -> None:
    """Quiet on the core as it is; failing, as it did before the oracle knew the shape, where it does not:
    the target then fails on a divergence HP12 lists, with no fault behind it."""
    sources, request = met_case(place(with_the_other_kind(*OTHER_KIND[held])))
    against_the_model(sources, request)
    monkeypatch.setattr("tests.fuzz.field_oracle.holds_the_other_kind", never)
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)


def test_the_model_oracle_keeps_a_step_not_built_beside_the_other_kind() -> None:
    """A form S2b reads holding the shape is a step not built (`NOT_BUILT`), as HP12 lists it: a plant would
    hold the core's "not yet" to a model that reads the interval."""
    against_the_model(*met_case(as_an_interval(with_the_other_kind(*OTHER_KIND["numeric-holding-token"]))))


@pytest.mark.parametrize("held", sorted(OTHER_KIND))
def test_the_model_oracle_sees_a_fault_beside_the_other_kind(
    monkeypatch: pytest.MonkeyPatch, held: str
) -> None:
    """The shape changes only the model's reading of the open point: a refusal step 8 gives wrongly beside it
    is still seen."""
    sources, request = met_case(with_the_other_kind(*OTHER_KIND[held]))
    monkeypatch.setattr(value_shapes, "FIELD_STATISTICS", _refuses_every_block)
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)

# SPDX-License-Identifier: Apache-2.0
"""Fuzz target 4's oracles (`tests/fuzz/field_oracle.py`), which the target itself, needing Atheris, cannot
show here: for a refusal step 8 is missing, quiet on step 8 as it is and failing on a step 8 that lets through
a member of the wrong type; for steps 9 and 10, quiet on them as they are and failing on a step 9 that lets
another unit through and a step 10 that lets a condition outside its tolerance through; for HP1 and HP2,
quiet on every result the core gives the full fields under each `want`, and failing on each law broken; and
against the reference model (HP12), quiet on the core as it is, and failing on a step 8 that refuses what the
text reads or lets through what it refuses. Each on the full constants, and on the full interval and
composition (S2b-1), with a fault of their own members. And a condition holding a member of the other
kind's shape, HP12's open point `members_of_the_other_kind` until the maintainer's ruling of 2026-10-19, held
to the model in a field or an alternative, the oracle failing on the core as it read the point before, and a
step not built beside it kept; S4a's control fault in step 7, which the model alone sees; and S4d's rows of
step 7 for a table alternative, held to the model, read at the places of a field's table alternatives too,
with S4d's control fault, which no seed shows and one change does, each shown through the target's own
`test_one_input` with Atheris stubbed."""

import contextlib
import copy
import json
import math
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

import pytest

from materica import shapes
from materica.core import conditions, evaluate, fields, jsonio, value_shapes
from materica.core import read as read_module
from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.reasons import Reason
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.fuzz.field_oracle import (
    EDGE_PLACES,
    OPERATING,
    OTHER_PLACES,
    REQUIRED,
    JsonObject,
    Place,
    alternative_places,
    check_against_the_model,
    check_no_refusal_missing,
    check_result_laws,
    check_steps_9_and_10,
    check_table_member,
    passed_step_8,
    places,
    read_outcome,
)
from tests.fuzz.seeded_fault import faulty_form_range, faulty_points, faulty_standing, faulty_value
from tests.property.full_fields import full_fields, full_forms, record_of, request_for
from tests.reference import read_model

FIELD = "fluid.dynamic_viscosity"
FORMS = full_forms()


def result_of(field: dict[str, JsonValue], name: str = FIELD) -> JsonValue:
    """The read's result as the target takes it: "not yet" where a step not built yet would decide it."""
    record = record_of(field, name)
    record["content_hash"] = content_hash(record)
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    try:
        result = read(request_for(record, name), store)
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
    for name, field in FORMS.values():
        check_no_refusal_missing(name, field, result_of(field, name))


def a_fraction_of_the_wrong_type() -> tuple[str, dict[str, JsonValue]]:
    name, field = full_forms()["composition"]
    composition = field["composition"]
    assert isinstance(composition, dict)
    components = composition["components"]
    assert isinstance(components, list)
    first = components[0]
    assert isinstance(first, dict)
    first["fraction"] = "0.102"
    return name, field


def test_the_oracle_sees_a_refusal_step_8_misses_in_a_component(monkeypatch: pytest.MonkeyPatch) -> None:
    name, field = a_fraction_of_the_wrong_type()
    check_no_refusal_missing(name, field, result_of(field, name))
    monkeypatch.setattr(fields, "COMPONENT", {**fields.COMPONENT, "fraction": _any})
    with pytest.raises(AssertionError, match="the reader \\$defs refuse"):
        check_no_refusal_missing(name, field, result_of(field, name))


def _any(value: JsonValue, where: str, found: value_shapes.Found) -> None:
    pass


def a_year_of_the_wrong_type() -> tuple[str, dict[str, JsonValue]]:
    name, field = full_forms()["evidence"]
    reports = field["evidence"]
    assert isinstance(reports, list)
    first = reports[0]
    assert isinstance(first, dict)
    first["standard"] = {"designation": "ISO 10993-5", "year": "2009"}
    return name, field


def test_the_oracle_sees_a_refusal_step_8_misses_in_an_evidence_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name, field = a_year_of_the_wrong_type()
    check_no_refusal_missing(name, field, result_of(field, name))
    monkeypatch.setattr(fields, "whole", _any)
    with pytest.raises(AssertionError, match="the reader \\$defs refuse"):
        check_no_refusal_missing(name, field, result_of(field, name))


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


# A table, read to the end since S3b-2: T1's third relation, step 9 with its `axis_unit`, and steps 10 and 11
# with its axis.


def a_table(**table: JsonValue) -> tuple[str, dict[str, JsonValue]]:
    """The full table form, its table's members changed."""
    name, field = full_forms()["table"]
    member = field["table"]
    assert isinstance(member, dict)
    member.update(table)
    return name, field


def _no_table_checked(value: JsonValue, where: str, found: value_shapes.Found) -> None:
    pass


def test_the_oracle_sees_a_refusal_step_8_misses_in_a_table(monkeypatch: pytest.MonkeyPatch) -> None:
    name, field = a_table(x="not a list")
    check_no_refusal_missing(name, field, result_of(field, name))
    monkeypatch.setitem(fields.OWN_MEMBERS, "table", _no_table_checked)
    with pytest.raises(AssertionError, match="the reader \\$defs refuse"):
        check_no_refusal_missing(name, field, result_of(field, name))


def table_read(name: str, field: dict[str, JsonValue]) -> JsonValue:
    record = record_of(field, name)
    record["content_hash"] = content_hash(record)
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    try:
        result = read(request_for(record, name), store)
    except NotImplementedError:
        return "not yet"
    written: JsonValue = json.loads(json.dumps(result.to_json()))
    return written


def _units_blind_to_the_axis(field: fields.RecordField) -> list[Reason]:
    return []


def _a_unit_refused(field: fields.RecordField) -> list[Reason]:
    return [Reason("unit_mismatch")]


def test_the_oracle_holds_a_tables_step_9_to_its_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quiet on a table steps 8 and 9 pass and on one whose `axis_unit` step 9 refuses; failing on a step 9
    that misses the `axis_unit`, and on one that refuses a unit it should pass, which the text's step 10 does
    not give."""
    name, passing = a_table()
    _, other_unit = a_table(axis_unit="Cel")
    for field in (passing, other_unit):
        check_steps_9_and_10(name, field, {}, {}, table_read(name, field))
    with monkeypatch.context() as patched:
        patched.setattr(read_module, "unit_problems", _units_blind_to_the_axis)
        with pytest.raises(AssertionError, match="step 9 gave"):
            check_steps_9_and_10(name, other_unit, {}, {}, table_read(name, other_unit))
    monkeypatch.setattr(read_module, "unit_problems", _a_unit_refused)
    with pytest.raises(AssertionError, match="step 10 gave"):
        check_steps_9_and_10(name, passing, {}, {}, table_read(name, passing))


def table_read_at(name: str, field: dict[str, JsonValue], at: dict[str, JsonObject]) -> JsonValue:
    """`field` read with `at` as its operating conditions."""
    record = record_of(field, name)
    record["content_hash"] = content_hash(record)
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    request = request_for(record, name)
    request["operating_conditions"] = dict(at)
    try:
        written: JsonValue = json.loads(json.dumps(read(request, store).to_json()))
    except NotImplementedError:
        return "not yet"
    return written


def _no_edge_refused(table: JsonObject, request: read_module.ReadRequest) -> read_module.FormRange:
    found = FORM_RANGE(table, request)
    kept = tuple(reason for reason in found.reasons if reason.code != "at_edge")
    return read_module.FormRange(kept) if kept else read_module.FormRange(value=0.0)


FORM_RANGE = read_module.form_range


def test_the_oracle_holds_a_tables_step_11_to_its_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quiet on a table read at an edge, at one outside a narrowed range, outside the range, over a range of
    its axis and with no operating value; failing on a step 11 that refuses no edge."""
    edged: JsonObject = {"x": [300.0, 310.0, 310.0, 320.0], "y": [1.0, 2.0, 3.0, 4.0], "edges": [310.0]}
    name, field = a_table(**edged)
    _, narrowed = a_table(**edged, source_range=[311.0, 320.0])
    places: list[tuple[dict[str, JsonValue], dict[str, JsonObject]]] = [
        (field, {"temperature": {"value": 310.0, "unit": "K"}}),
        (narrowed, {"temperature": {"value": 310.0, "unit": "K"}}),
        (field, {"temperature": {"value": 330.0, "unit": "K"}}),
        (field, {"temperature": {"range": [305.0, 315.0], "unit": "K"}}),
        (field, {}),
    ]
    for table_field, at in places:
        check_steps_9_and_10(name, table_field, at, {}, table_read_at(name, table_field, at))
    monkeypatch.setattr(read_module, "form_range", _no_edge_refused)
    at_the_edge = places[0][1]
    with pytest.raises(AssertionError, match="step"):
        check_steps_9_and_10(name, field, at_the_edge, {}, table_read_at(name, field, at_the_edge))


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


# A table's places: inside its range, at its edge, and outside it.
PLACES = (305.0, 310.0, 315.0, 330.0)


def test_the_oracle_of_hp2_s_table_member_is_quiet_on_the_core_and_sees_it_misplaced() -> None:
    """HP2's `table` clause (`check_table_member`): quiet on the core's reads of every full field at every
    `want`; it fails a value from a table without its table, a table beside a constant's value, and a table
    without a value among alternatives that hold one."""
    for field in full_fields().values():
        for result in results_of_every_want(field):
            check_table_member(field, result)
    name, table_field = a_table(x=[300.0, 310.0, 310.0, 320.0], y=[1.0, 2.0, 3.0, 4.0], edges=[310.0])
    read_at = [table_read_at(name, table_field, {"temperature": {"value": at, "unit": "K"}}) for at in PLACES]
    assert {"table" in result for result in read_at if isinstance(result, dict)} == {True, False}, read_at
    for result in read_at:
        check_table_member(table_field, result)
    table: dict[str, JsonValue] = {"axis": "temperature", "x": [300.0, 320.0]}
    constant = full_fields()["population"]
    alternatives: dict[str, JsonValue] = {"alternatives": [table_field, constant]}
    refused: dict[str, JsonValue] = {"status": "not_met", "reasons": [OUTSIDE], "labels": []}
    # A form the fuzzer writes as an object, which no set can hold (a find of the table value's control runs).
    check_table_member({"form": {"table": 1.0}}, refused)
    check_table_member({"alternatives": [{"form": ["table"]}, constant]}, MET)
    misplaced: list[tuple[JsonValue, JsonValue, str]] = [
        (table_field, MET, "table beside a value from a table"),
        (table_field, {**refused, "table": table}, "table beside a value from a table"),
        (constant, {**MET, "table": table}, "a table where no form is a table"),
        (alternatives, {**refused, "table": table}, "a table without a value"),
    ]
    for held, given, complaint in misplaced:
        with pytest.raises(AssertionError, match=complaint):
            check_table_member(held, given)


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


def test_the_model_oracle_sees_step_7_s_seeded_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    """S4a's control fault (`tests/fuzz/seeded_fault.py`, `faulty_standing`): a third alternative refused for
    its unit alone set aside, so that the two before it give `no_pick` where the text refuses the field. The
    read gives an answer, which the model's alone tells wrong."""
    base = full_fields()["population"]
    sources, request = model_case({"alternatives": [base, base, {**base, "unit": "mPa.s"}]})
    against_the_model(sources, request)
    monkeypatch.setattr(read_module, "_standing", faulty_standing)
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)


def test_the_model_oracle_sees_the_table_s_seeded_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    """S3a's control fault (`tests/fuzz/seeded_fault.py`, `faulty_points`): a table over temperature whose
    first knot lies below 250 refused at step 8, which the text and the model read to the end."""
    name, field = a_table(x=[200.0, 303.15, 313.15, 313.15, 323.15])
    sources, request = form_read(name, field, "value")
    against_the_model(sources, request)
    monkeypatch.setattr(fields, "_points", faulty_points)
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)


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


# A condition holding a member of the other kind's shape on the target's reads: HP12's open point
# `members_of_the_other_kind` (S2a-4's review B, M1), which the oracle knew by its shape until the maintainer
# ruled it fail closed (2026-10-19, `provenance.md` section 6.1 item 1); the core and the model both refuse it
# since. The field is met, each condition it holds checked, so that two alternatives of it reach `no_pick`.

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


def as_a_table(field: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """`field` as a table over shear rate that steps 8 and 9 pass, its axis condition `not_applicable`,
    without the Newtonian label, which a table over shear rate does not take."""
    del field["value"], field["label"]
    conditions = field["conditions"]
    assert isinstance(conditions, dict)
    table: JsonObject = {
        "axis": "shear_rate",
        "axis_unit": "1/s",
        "x": [1.0, 10.0],
        "y": [0.0007, 0.0006],
        "scheme": "linear",
        "edges": [],
    }
    return {
        **field,
        "form": "table",
        "table": table,
        "conditions": {**conditions, "shear_rate": {"status": "not_applicable"}},
    }


def _read_as_before_its_ruling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Step 8 as it read a condition until the maintainer's ruling of 2026-10-19: a member of the other kind's
    shape ignored, as a member the reader does not know."""
    conditions = value_shapes.conditions

    def ignoring(value: JsonValue, where: str, found: value_shapes.Found) -> None:
        if isinstance(value, dict):
            value = {
                name: {
                    held: member
                    for held, member in entry.items()
                    if held not in value_shapes.OF_THE_OTHER_KIND[VOCABULARY.conditions[name].shape]
                }
                if isinstance(entry, dict) and name in VOCABULARY.conditions
                else entry
                for name, entry in value.items()
            }
        conditions(value, where, found)

    monkeypatch.setattr(value_shapes, "conditions", ignoring)


@pytest.mark.parametrize("held", sorted(OTHER_KIND))
@pytest.mark.parametrize(
    "place", [pytest.param(as_the_field, id="field"), pytest.param(as_alternatives, id="alternative")]
)
def test_the_model_oracle_holds_the_other_kind_to_the_model(
    monkeypatch: pytest.MonkeyPatch, held: str, place: Callable[[dict[str, JsonValue]], dict[str, JsonValue]]
) -> None:
    """Quiet on the core as it is, which refuses the member; failing on the core as it read it before the
    ruling, which the oracle once let through as a known divergence."""
    sources, request = met_case(place(with_the_other_kind(*OTHER_KIND[held])))
    against_the_model(sources, request)
    _read_as_before_its_ruling(monkeypatch)
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)


def table_alternative_case() -> tuple[tuple[bytes, ...], JsonObject]:
    """The table over shear rate, `x` 1 to 10 1/s, read at 100 1/s, outside its readable range, beside the met
    constant: the table is set aside at step 7 and the constant is the one left (`read_side_contract.md`
    section 3, step 7)."""
    alternatives: list[JsonValue] = [as_a_table(met_field()), met_field()]
    field: dict[str, JsonValue] = {"alternatives": alternatives}
    return met_case(field)


def test_the_model_oracle_holds_a_table_alternatives_step_11_rows_to_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 7 over a table alternative whose read gives a reason at step 11, which both sides decide since
    S4d: quiet on the core as it is, which sets the table aside and reads the constant; failing on a core that
    refuses the field there, as every other `not_met` in an alternative's read does."""
    sources, request = table_alternative_case()
    written = written_read(sources, request)
    assert isinstance(written, dict)
    assert (written["status"], written["value"]) == ("met", 0.000692)
    against_the_model(sources, request)
    monkeypatch.setattr(read_module, "_set_aside_by_its_range", _never_set_aside)
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)


# S4d's control fault (`tests/fuzz/seeded_fault.py`, `faulty_form_range`): a table alternative read outside
# its readable range, at no edge and with no extrapolation covering it, a value of its `y` below 900, refusing
# the field where step 7 sets it aside. Fuzz target 4 reads a field's table alternatives at their places too
# (`field_oracle.alternative_places`), where the fault would show at once on four seeds without its gate.
# Its premise: no seed shows the gated fault; and one change to a seed does, found by the model's assertion.
# Each is shown through the target's own `test_one_input`, Atheris stubbed (its import a null context, its
# instrumentation the identity), so that the premise follows the target's record, requests and places as they
# change, rather than a copy of them.


def _instrumenting_nothing(**_: object) -> contextlib.AbstractContextManager[None]:
    return contextlib.nullcontext()


def _as_it_is(function: Callable[..., object]) -> Callable[..., object]:
    return function


@pytest.fixture
def target_4(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Fuzz target 4's module, imported with Atheris stubbed: the core it reads is not instrumented here."""
    atheris = ModuleType("atheris")
    atheris.__dict__.update(instrument_imports=_instrumenting_nothing, instrument_func=_as_it_is)
    monkeypatch.setitem(sys.modules, "atheris", atheris)
    import tests.fuzz.read_field_bytes as target

    return target


def holding_alternatives(target: ModuleType) -> list[tuple[str, bytes]]:
    """The target's seeds whose field holds alternatives, by the seed's name: its input's and its field's."""
    seeds: list[tuple[str, bytes]] = target.seeds()
    found: list[tuple[str, bytes]] = []
    for name, data in seeds:
        field = jsonio.parse(data[1:])
        if isinstance(field, dict) and "alternatives" in field:
            found.append((name, data))
    return found


def seed_of(target: ModuleType, input_name: str) -> bytes:
    """The seed of the field holding alternatives of the conformance input `input_name`."""
    stem = Path(input_name).stem
    (data,) = [data for name, data in holding_alternatives(target) if name.partition("-")[0] == stem]
    return data


def test_target_4_reads_a_fields_table_alternatives_at_their_places(
    target_4: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every seed holding table alternatives read by the target at some of their places, at most its sample
    of one table's, each read agreeing with the model on the core as it is; and none where the field holds no
    table alternative."""
    counted: list[int] = []

    def counting(field: JsonValue, data: bytes) -> list[Place]:
        found = alternative_places(field, data)
        counted.append(len(found))
        return found

    monkeypatch.setattr(target_4, "alternative_places", counting)
    tables = [data for _, data in holding_alternatives(target_4) if b'"form": "table"' in data]
    assert len(tables) >= 20
    for data in tables:
        counted.clear()
        target_4.test_one_input(data)
        (count,) = counted
        assert 1 <= count <= EDGE_PLACES + OTHER_PLACES
    assert alternative_places(met_field(), b"") == []
    assert alternative_places({"alternatives": [met_field(), met_field()]}, b"") == []


def test_no_seed_of_target_4_shows_the_table_alternatives_seeded_fault(
    target_4: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every seed holding alternatives passes the target with the fault seeded, though the target reads table
    alternatives outside their range in many of them, where the fault could refuse."""
    reads: list[read_module.ReadResult] = []

    def reading(*arguments: Any, **members: Any) -> read_module.ReadResult:
        result = read(*arguments, **members)
        reads.append(result)
        return result

    seeds = holding_alternatives(target_4)
    with monkeypatch.context() as patch:
        patch.setattr(target_4, "read", reading)
        for _, data in seeds:
            target_4.test_one_input(data)
    assert len(seeds) >= 50
    assert sum(any(reason.code == "outside_range" for reason in result.reasons) for result in reads) >= 100
    monkeypatch.setattr(read_module, "form_range", faulty_form_range)
    for _, data in seeds:
        target_4.test_one_input(data)


def test_four_seeds_show_the_table_alternatives_fault_without_its_gate(
    target_4: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Why the fault is gated: ungated, the four seeds whose density table, read just below its readable
    range at a place of its own, sits beside a constant that stays there fail the target at once."""
    monkeypatch.setattr(read_module, "form_range", faulty_form_range)
    monkeypatch.setattr("tests.fuzz.seeded_fault.LEAST_VALUE", math.inf)
    shown: list[str] = []
    for name, data in holding_alternatives(target_4):
        try:
            target_4.test_one_input(data)
        except AssertionError:
            shown.append(name.partition("-")[0])
    assert shown == [
        "density_alternatives_constant_263_and_edge",
        "density_alternatives_edge_narrowed_and_constant_272",
        "density_alternatives_edge_narrowed_and_constant_273",
        "density_alternatives_edge_narrowed_and_constant_274",
    ]


# One change to a seed that shows the fault: a value of such a table's `y` lowered below 900 (a minus sign
# inserted, a digit erased, a digit changed); or, beside a viscosity table, whose `y` lies below 900 already,
# read outside its range at a place of its own, a byte of the constant's condition name changed, which leaves
# its temperature unstated, so that the constant stays where it was set aside (the control's local runs found
# it so, 2026-10-22).
ONE_CHANGE: list[tuple[str, str, str]] = [
    ("density_alternatives_constant_263_and_edge.json", "916.0", "-916.0"),
    ("density_alternatives_edge_narrowed_and_constant_272.json", "1000.0", "100.0"),
    ("density_alternatives_edge_narrowed_and_constant_274.json", "918.0", "818.0"),
    (
        "viscosity_alternatives_table_and_constant.json",
        '"temperature": {"value": 310.15',
        '"te}perature": {"value": 310.15',
    ),
]


@pytest.mark.parametrize(("input_name", "old", "new"), ONE_CHANGE, ids=[name for name, _, _ in ONE_CHANGE])
def test_one_change_to_a_seed_shows_the_table_alternatives_seeded_fault_to_the_model_oracle(
    input_name: str, old: str, new: str, target_4: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = seed_of(target_4, input_name)
    assert seed.count(old.encode()) == 1
    changed = seed.replace(old.encode(), new.encode())
    target_4.test_one_input(changed)
    monkeypatch.setattr(read_module, "form_range", faulty_form_range)
    with pytest.raises(AssertionError, match=r"the implementation gives .*'outside_range'"):
        target_4.test_one_input(changed)


def read_case(sources: tuple[bytes, ...], request: JsonObject) -> read_module.ReadResult:
    store = RecordStore()
    for number, source in enumerate(sources):
        store.add(f"source_{number}", source)
    return read(request, store)


def _never_set_aside(read: read_module.FieldRead) -> bool:
    return False


def _not_built(*arguments: object) -> NoReturn:
    raise NotImplementedError("a step not built")


def _no_verdict(*arguments: object) -> NoReturn:
    raise read_model._Undecided("a step not built")  # pyright: ignore[reportPrivateUsage]


def test_the_model_oracle_keeps_a_step_not_built(monkeypatch: pytest.MonkeyPatch) -> None:
    """A step neither side has built: the core says "not yet" and the model gives no verdict, so the oracle
    passes it, and a core that answers there fails. No field the target writes reaches one since S4d built
    step 7's rows for a table alternative's step 11 (picks and overlays are the request's, which the target
    does not write), as none reached evidence once S2b-2 read it; so one is made here, step 7 over the table
    alternative above left unbuilt on both sides."""
    sources, request = table_alternative_case()
    monkeypatch.setattr(read_model, "fate_of", _no_verdict)
    monkeypatch.setattr(read_module, "_standing_at_step_11", _not_built)
    assert written_read(sources, request) == "not yet"
    against_the_model(sources, request)
    monkeypatch.undo()
    monkeypatch.setattr(read_model, "fate_of", _no_verdict)
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)


# The same oracles on the full interval and composition, each read as the target reads its field.


def form_read(name: str, field: dict[str, JsonValue], want: str) -> tuple[tuple[bytes, ...], JsonObject]:
    record = record_of(field, name)
    record["content_hash"] = content_hash(record)
    request = request_for(record, name)
    requires = VOCABULARY.fields[name].requires
    request["operating_conditions"] = {key: value for key, value in OPERATING.items() if key in requires}
    request["requirement"] = {
        "want": want,
        "conditions": {key: value for key, value in REQUIRED.items() if key in requires},
    }
    return (json.dumps(record).encode(),), request


def written_read(sources: tuple[bytes, ...], request: JsonObject) -> JsonValue:
    store = RecordStore()
    for number, source in enumerate(sources):
        store.add(f"source_{number}", source)
    try:
        return json.loads(json.dumps(read(request, store).to_json()))  # type: ignore[no-any-return]
    except NotImplementedError:
        return "not yet"


@pytest.mark.parametrize("form", sorted(FORMS))
def test_every_oracle_is_quiet_on_the_forms_as_the_core_reads_them(form: str) -> None:
    name, field = FORMS[form]
    for want in WANTS:
        sources, request = form_read(name, field, want)
        result = written_read(sources, request)
        check_result_laws(result)
        operating, required = request["operating_conditions"], request["requirement"]
        assert isinstance(operating, dict)
        assert isinstance(required, dict)
        conditions_required = required["conditions"]
        assert isinstance(conditions_required, dict)
        check_steps_9_and_10(name, field, operating, conditions_required, result)  # type: ignore[arg-type]
        against_the_model(sources, request)


def an_interval_upside_down() -> tuple[str, dict[str, JsonValue]]:
    name, field = full_forms()["interval"]
    field["interval"] = {"lower": 2.0, "upper": 1.0, "basis": "reported_range"}
    return name, field


def _in_any_order(value: JsonValue, where: str, found: value_shapes.Found) -> None:
    if isinstance(value, dict):
        value = {**value, "lower": 0.0, "upper": 0.0}
    fields.interval(value, where, found)


def test_the_model_oracle_sees_an_interval_step_8_lets_through(monkeypatch: pytest.MonkeyPatch) -> None:
    name, field = an_interval_upside_down()
    sources, request = form_read(name, field, "bounds")
    against_the_model(sources, request)
    monkeypatch.setitem(
        fields.OWN_MEMBERS,
        "interval",
        value_shapes.or_status(_in_any_order, shapes.IntervalField, "interval"),
    )
    with pytest.raises(AssertionError, match="the implementation gives"):
        against_the_model(sources, request)


# S3b-2's control fault (`tests/fuzz/seeded_fault.py`, `faulty_value`), which the fourth target meets at the
# places of a table it reads at (`read_field_bytes.places`).


def test_the_table_value_s_seeded_fault_raises_just_above_an_edge_the_table_drops_across(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quiet on the core; with the fault, a read in the interval just above an edge raises where the value
    just above lies outside 0.6 to 1.6 times the value just below, either way, and nowhere else: not at 0.6
    or 1.6 exactly, nor at a change of a tenth, nor just below the edge. Of a table of two edges, the edge the
    read lies just above is the one gated: the second's change raises there, the first's does not."""
    just_above: dict[str, JsonObject] = {
        "temperature": {"value": math.nextafter(310.0, math.inf), "unit": "K"}
    }
    just_below: dict[str, JsonObject] = {
        "temperature": {"value": math.nextafter(310.0, -math.inf), "unit": "K"}
    }

    def across(below: float, above: float) -> JsonObject:
        return a_table(x=[300.0, 310.0, 310.0, 320.0], y=[1.0, below, above, 4.0], edges=[310.0])[1]

    def two_edges(first: float, second: float) -> JsonObject:
        """Edges at 300 and 310, the value just above each `first` and `second` times the value below."""
        return a_table(
            x=[290.0, 300.0, 300.0, 310.0, 310.0, 320.0],
            y=[1.0, 2.0, 2.0 * first, 3.0, 3.0 * second, 4.0],
            edges=[300.0, 310.0],
        )[1]

    name, drops = a_table(x=[300.0, 310.0, 310.0, 320.0], y=[1.0, 2.0, 1.0, 4.0], edges=[310.0])
    raising = [drops, across(2.0, -3.0), across(1.0, 2.0), across(0.0, 1.0), across(2.0, 3.25)]
    raising += [two_edges(1.0, 2.0)]
    quiet = [across(2.5, 1.5), across(2.5, 4.0), across(2.0, 2.2), across(2.0, 1.8), across(2.0, 2.0)]
    quiet += [two_edges(2.0, 1.0)]
    assert table_read_at(name, drops, just_above) != "not yet"
    monkeypatch.setattr(evaluate, "value", faulty_value)
    for table in raising:
        with pytest.raises(ArithmeticError, match="the seeded fault in a table's value"):
            table_read_at(name, table, just_above)
    for table in quiet:
        table_read_at(name, table, just_above)
    table_read_at(name, drops, just_below)


def test_the_target_reads_a_table_one_double_above_each_edge() -> None:
    """The places the fourth target reads a table at (`field_oracle.places`) hold one double above each
    edge, where the seeded fault shows, and a value beyond each end of `x`."""
    _, field = a_table(x=[300.0, 310.0, 310.0, 320.0], y=[1.0, 2.0, 1.0, 4.0], edges=[310.0])
    found = [place.at for place in places(field, b"")]
    assert math.nextafter(310.0, math.inf) in found
    assert any(at < 300.0 for at in found)
    assert any(at > 320.0 for at in found)
    assert len(found) <= EDGE_PLACES + OTHER_PLACES

# SPDX-License-Identifier: Apache-2.0
"""Step 10 by example (`read_side_contract.md` section 5): each row of the table, the boundaries the case
files name, a stated `plus_minus` of each kind, the conditions checked and the entries returned. Read through
`conditions.check_conditions`, since a read that step 10 does not end raises until steps 11 to 13 are built;
the read itself is checked where step 10 ends it."""

import json
import math
from fractions import Fraction

import pytest

from materica import shapes
from materica.core.conditions import ConditionEntry, ConditionsRead, ImpliedCondition, check_conditions
from materica.core.fields import RecordField
from materica.core.identifiers import MaterialRef
from materica.core.jsonio import JsonValue
from materica.core.read import ReadResult, read
from materica.core.reasons import Reason
from materica.core.vocabulary import VOCABULARY
from tests.unit.test_read import stored, with_condition, with_field

VISCOSITY = VOCABULARY.fields["fluid.dynamic_viscosity"]
STATED: dict[str, JsonValue] = {"basis": "stated"}
UNSTATED: dict[str, JsonValue] = {"status": "unstated"}

Operating = dict[str, shapes.OperatingCondition]
Required = dict[str, shapes.RequirementCondition]


def field_holding(**conditions: JsonValue) -> RecordField:
    """The viscosity field holding `conditions`, as stored, its section holding nothing else."""
    value: dict[str, JsonValue] = {
        "form": "constant",
        "unit": "Pa.s",
        "value": 0.000692,
        "conditions": conditions,
    }
    return RecordField(VISCOSITY, value, {"fields": {"dynamic_viscosity": value}})


def temperature(value: float, tolerance: float) -> tuple[Operating, Required]:
    return (
        {"temperature": {"value": value, "unit": "K"}},
        {"temperature": {"tolerance": {"value": tolerance, "unit": "K"}}},
    )


def entries_of(read: ConditionsRead) -> tuple[ConditionEntry, ...]:
    assert read.entries is not None, read.reasons
    return read.entries


def entry_of(read: ConditionsRead, name: str) -> ConditionEntry:
    (found,) = [entry for entry in entries_of(read) if entry.name == name]
    return found


def reasons_of(read: ConditionsRead, condition: str | None = None) -> set[tuple[str, str | None]]:
    """The reasons found, those of `condition` alone where it is given."""
    return {
        (reason.code, reason.condition)
        for reason in read.reasons
        if condition is None or reason.condition == condition
    }


# Section 5's rows, each against a value and a range: `(record, operating, tolerance, status)`.
ROWS: list[tuple[str, JsonValue, shapes.OperatingCondition, float, str]] = [
    ("value at the tolerance", {"value": 310.0}, {"value": 311.0, "unit": "K"}, 1.0, "met"),
    ("value past the tolerance", {"value": 310.0}, {"value": 311.5, "unit": "K"}, 1.0, "not_met"),
    ("value against a range within", {"value": 310.0}, {"range": (309.0, 311.0), "unit": "K"}, 1.0, "met"),
    ("value against a range past", {"value": 310.0}, {"range": (309.0, 311.5), "unit": "K"}, 1.0, "not_met"),
    ("range against a value inside", {"range": [300.0, 320.0]}, {"value": 320.5, "unit": "K"}, 1.0, "met"),
    ("range against a value past", {"range": [300.0, 320.0]}, {"value": 321.5, "unit": "K"}, 1.0, "not_met"),
    (
        "range against a range inside",
        {"range": [300.0, 320.0]},
        {"range": (299.5, 321.0), "unit": "K"},
        1.0,
        "met",
    ),
    (
        "range against a range past",
        {"range": [300.0, 320.0]},
        {"range": (298.5, 321.0), "unit": "K"},
        1.0,
        "not_met",
    ),
    ("value at a tolerance of -0", {"value": 310.0}, {"value": 310.0, "unit": "K"}, -0.0, "met"),
]


@pytest.mark.parametrize(
    ("row", "record", "operating", "tolerance", "status"), ROWS, ids=[row for row, *_ in ROWS]
)
def test_each_row_of_section_5(
    row: str,
    record: dict[str, JsonValue],
    operating: shapes.OperatingCondition,
    tolerance: float,
    status: str,
) -> None:
    condition: JsonValue = {**record, "unit": "K", **STATED}
    found = check_conditions(
        field_holding(temperature=condition),
        {"temperature": operating},
        {"temperature": {"tolerance": {"value": tolerance, "unit": "K"}}},
    )
    entry = entry_of(found, "temperature")
    assert entry.status == status
    assert entry.record == condition
    assert entry.operating == operating
    assert (status == "not_met") == (("condition_outside", "temperature") in reasons_of(found))


# The exact arms of PR-306 and PR-335: floating point as written says `met` for each `not_met` here.
EXACT: list[tuple[str, JsonValue, shapes.OperatingCondition, float, str]] = [
    ("1674.0 against 0.2 within 1673.8", {"value": 1674.0}, {"value": 0.2, "unit": "K"}, 1673.8, "not_met"),
    ("310.15 against 310.25 within 0.1", {"value": 310.15}, {"value": 310.25, "unit": "K"}, 0.1, "not_met"),
    ("310.0 against 311.0 within 1.0", {"value": 310.0}, {"value": 311.0, "unit": "K"}, 1.0, "met"),
    (
        "[100, 1000] against 1000.1 within 0.1",
        {"range": [100.0, 1000.0]},
        {"value": 1000.1, "unit": "K"},
        0.1,
        "not_met",
    ),
    ("one ulp past 1.0", {"value": 0.0}, {"value": math.nextafter(1.0, 2.0), "unit": "K"}, 1.0, "not_met"),
    ("one ulp short of 1.0", {"value": 0.0}, {"value": math.nextafter(1.0, 0.0), "unit": "K"}, 1.0, "met"),
    ("subnormals", {"value": 5e-324}, {"value": 1e-323, "unit": "K"}, 5e-324, "met"),
    ("subnormals one apart past", {"value": 5e-324}, {"value": 1.5e-323, "unit": "K"}, 5e-324, "not_met"),
]


@pytest.mark.parametrize(
    ("arm", "record", "operating", "tolerance", "status"), EXACT, ids=[arm for arm, *_ in EXACT]
)
def test_every_comparison_is_exact_on_the_doubles(
    arm: str,
    record: dict[str, JsonValue],
    operating: shapes.OperatingCondition,
    tolerance: float,
    status: str,
) -> None:
    """The rationals the doubles are decide, never `abs(r - v) <= t` rounded (section 5, "Exactness")."""
    found = check_conditions(
        field_holding(temperature={**record, "unit": "K", **STATED}),
        {"temperature": operating},
        {"temperature": {"tolerance": {"value": tolerance, "unit": "K"}}},
    )
    assert entry_of(found, "temperature").status == status


def test_the_exact_arms_are_ones_floating_point_gets_wrong() -> None:
    """A control on the arms above: rounded as written, the `not_met` ones of PR-335 read `met`."""
    assert abs(1674.0 - 0.2) <= 1673.8
    assert Fraction(1674.0) - Fraction(0.2) > Fraction(1673.8)
    assert 1000.1 <= 1000.0 + 0.1
    assert Fraction(1000.1) > Fraction(1000.0) + Fraction(0.1)


# A stated plus or minus: `(plus_minus, operating value, status)` for a value of 310.0 K within 1.0 K.
PLUS_MINUS: list[tuple[str, list[JsonValue], float, str]] = [
    ("a bound inside", [{"stated_as": "bound", "value": 0.5, "unit": "K"}], 310.25, "met"),
    ("a bound to the edge", [{"stated_as": "bound", "value": 0.5, "unit": "K"}], 310.5, "met"),
    ("a bound past", [{"stated_as": "bound", "value": 0.5, "unit": "K"}], 310.75, "unknown"),
    ("an sd", [{"stated_as": "sd", "value": 0.1, "unit": "K"}], 310.0, "unknown"),
    ("an sd of zero", [{"stated_as": "sd", "value": 0.0, "unit": "K"}], 310.0, "met"),
    ("an unstated kind", [{"stated_as": UNSTATED, "value": 0.1, "unit": "K"}], 310.0, "unknown"),
    (
        "a bound decides beside an sd",
        [{"stated_as": "sd", "value": 2.0, "unit": "K"}, {"stated_as": "bound", "value": 0.0, "unit": "K"}],
        310.0,
        "met",
    ),
    ("never not_met of its own", [{"stated_as": "bound", "value": 5.0, "unit": "K"}], 310.0, "unknown"),
    ("a not_met stands", [{"stated_as": "bound", "value": 0.0, "unit": "K"}], 312.0, "not_met"),
]


@pytest.mark.parametrize(
    ("kind", "plus_minus", "operating", "status"), PLUS_MINUS, ids=[kind for kind, *_ in PLUS_MINUS]
)
def test_a_stated_plus_minus_turns_met_into_unknown_only(
    kind: str, plus_minus: list[JsonValue], operating: float, status: str
) -> None:
    condition: JsonValue = {"value": 310.0, "unit": "K", "plus_minus": plus_minus, **STATED}
    found = check_conditions(field_holding(temperature=condition), *temperature(operating, 1.0))
    assert entry_of(found, "temperature").status == status
    expected: dict[str, set[tuple[str, str | None]]] = {
        "met": set(),
        "unknown": {("condition_uncertain", "temperature")},
    }
    assert reasons_of(found, "temperature") == expected.get(status, {("condition_outside", "temperature")})


def test_a_bound_on_a_range_moves_both_ends_inward() -> None:
    """`[a, b]` stated within plus or minus u: `a + u - t <= v <= b - u + t`."""
    condition: JsonValue = {
        "range": [300.0, 320.0],
        "unit": "K",
        "plus_minus": [{"stated_as": "bound", "value": 2.0, "unit": "K"}],
        **STATED,
    }
    for operating, status in ((319.0, "met"), (319.5, "unknown"), (301.0, "met"), (300.5, "unknown")):
        found = check_conditions(field_holding(temperature=condition), *temperature(operating, 1.0))
        assert entry_of(found, "temperature").status == status, operating


def test_a_token_against_an_accept_list() -> None:
    field = field_holding(measurement_geometry={"token": "tube", **STATED}, measurement_dimension=UNSTATED)
    met = check_conditions(field, {}, {"measurement_geometry": {"accept": ["tube", "gap"]}})
    assert entry_of(met, "measurement_geometry").status == "met"
    refused = check_conditions(field, {}, {"measurement_geometry": {"accept": ["bulk"]}})
    assert entry_of(refused, "measurement_geometry").status == "not_met"
    assert ("condition_not_accepted", "measurement_geometry") in reasons_of(refused)


def test_the_conditions_checked_and_their_entries() -> None:
    """The record's, the row's, those another requires with its token, and the request's, each once: a
    condition absent or held as a status object is `unstated`, a name the reader does not know is
    `unknown_name` with no record, and one with no tolerance or accept list is `unchecked`."""
    field = field_holding(
        temperature={"value": 310.15, "unit": "K", **STATED, "x_note": 1.0},
        measurement_geometry={"token": "tube", **STATED},
        pressure={"value": 1.0, "unit": "bar"},
        density_kind={"status": "withheld", "reason": "reference-only", "x_note": 1.0},
    )
    found = check_conditions(
        field,
        {"temperature": {"value": 310.15, "unit": "K"}, "magnetic_flux_density": {"value": 1.0, "unit": "T"}},
        {"magnetic_flux_density": {"tolerance": {"value": 0.0, "unit": "T"}}},
    )
    assert [entry.to_json() for entry in entries_of(found)] == [
        {
            "name": "temperature",
            "status": "unknown",
            "record": {"value": 310.15, "unit": "K", "basis": "stated"},
            "operating": {"value": 310.15, "unit": "K"},
        },
        {"name": "measurement_geometry", "status": "unknown", "record": {"token": "tube", "basis": "stated"}},
        {"name": "pressure", "status": "unknown"},
        {
            "name": "density_kind",
            "status": "unknown",
            "record": {"status": "withheld", "reason": "reference-only"},
        },
        {"name": "shear_rate", "status": "unknown"},
        {"name": "measurement_dimension", "status": "unknown"},
        {"name": "magnetic_flux_density", "status": "unknown", "operating": {"value": 1.0, "unit": "T"}},
    ]
    assert reasons_of(found) == {
        ("condition_unchecked", "temperature"),
        ("condition_unchecked", "measurement_geometry"),
        ("condition_unknown_name", "pressure"),
        ("condition_unstated", "density_kind"),
        ("condition_unstated", "shear_rate"),
        ("condition_unstated", "measurement_dimension"),
        ("condition_unstated", "magnetic_flux_density"),
    }


def test_a_condition_required_with_another_token_only_with_it() -> None:
    bulk = check_conditions(field_holding(measurement_geometry={"token": "bulk", **STATED}), {}, {})
    assert "measurement_dimension" not in {entry.name for entry in entries_of(bulk)}
    unstated = check_conditions(field_holding(measurement_geometry=UNSTATED), {}, {})
    assert "measurement_dimension" not in {entry.name for entry in entries_of(unstated)}
    gap = check_conditions(field_holding(measurement_geometry={"token": "gap", **STATED}), {}, {})
    assert entry_of(gap, "measurement_dimension").status == "unknown"


def test_a_plus_minus_entry_is_returned_with_the_members_the_reader_knows() -> None:
    condition: JsonValue = {
        "value": 310.0,
        "unit": "K",
        "plus_minus": [{"stated_as": {"status": "unstated", "x": 1.0}, "value": 0.0, "unit": "K", "x": 1.0}],
        "set_or_measured": "measured",
        **STATED,
    }
    found = check_conditions(field_holding(temperature=condition), *temperature(310.0, 1.0))
    assert entry_of(found, "temperature").record == {
        "value": 310.0,
        "unit": "K",
        "plus_minus": [{"stated_as": {"status": "unstated"}, "value": 0.0, "unit": "K"}],
        "set_or_measured": "measured",
        "basis": "stated",
    }


def test_a_read_that_step_10_ends_holds_its_conditions_and_one_step_9_ends_none() -> None:
    record = with_field(
        "fluid.dynamic_viscosity", with_condition("shear_rate", {"value": 50.0, "unit": "1/s", **STATED})
    )
    request, store = stored(record)
    assert isinstance(request, dict)
    request["operating_conditions"] = {"temperature": {"value": 330.0, "unit": "K"}}
    result = read(request, store)
    assert result.status == "not_met"
    assert {(reason.code, reason.condition) for reason in result.reasons} == {
        ("condition_outside", "temperature"),
        ("condition_unchecked", "shear_rate"),
    }
    assert result.conditions is not None
    assert {entry.name: entry.status for entry in result.conditions} == {
        "temperature": "not_met",
        "shear_rate": "unknown",
    }
    written = json.loads(json.dumps(result.to_json()))
    assert ReadResult.from_json(written) == result
    assert "conditions" in written
    step_9 = read(
        *stored(
            with_field("fluid.dynamic_viscosity", {**with_condition("shear_rate", UNSTATED), "unit": "Pa s"})
        )
    )
    assert step_9.conditions is None
    assert "conditions" not in step_9.to_json()


# Implied conditions (`declarations.md` section 4.1, `read_side_contract.md` sections 1 and 5).

PIN = MaterialRef("conformance/field_fixture", "1.0.0", "sha256:" + "0" * 64)
LOCATED: dict[str, JsonValue] = {
    "record": {"id": PIN.id, "version": PIN.version, "content_hash": PIN.content_hash}
}


def implying(index: int, fact: str, token: str, **implies: dict[str, JsonValue]) -> ImpliedCondition:
    return ImpliedCondition(index, "fluid.dynamic_viscosity", LOCATED, fact, token, implies)


IN_VIVO = implying(0, "tissue_state", "in_vivo", temperature={"value": 310.15, "unit": "K"})


def specimen_field(
    field_facts: dict[str, JsonValue], section_facts: dict[str, JsonValue], **conditions: JsonValue
) -> RecordField:
    held = field_holding(**conditions)
    value = held.value
    assert isinstance(value, dict)
    value["specimen"] = field_facts
    return RecordField(VISCOSITY, value, {"specimen": section_facts, "fields": {"dynamic_viscosity": value}})


def in_vivo(**conditions: JsonValue) -> RecordField:
    return specimen_field({"tissue_state": {"token": "in_vivo", **STATED}}, {}, **conditions)


def test_an_implied_condition_fills_an_absent_or_unstated_condition_with_the_basis_implied() -> None:
    for field in (
        in_vivo(),
        in_vivo(temperature=UNSTATED),
        in_vivo(temperature={"status": "unstated", "reason": "x"}),
    ):
        found = check_conditions(field, *temperature(310.15, 1.0), [IN_VIVO])
        assert entry_of(found, "temperature").to_json() == {
            "name": "temperature",
            "status": "met",
            "record": {"value": 310.15, "unit": "K", "basis": "implied"},
            "operating": {"value": 310.15, "unit": "K"},
        }
        assert found.applied == (0,)


@pytest.mark.parametrize(
    "held",
    [{"value": 296.15, "unit": "K", **STATED}, {"status": "not_checked"}, {"status": "withheld"}],
    ids=["a_stated_value", "not_checked", "withheld"],
)
def test_an_implied_condition_never_overrides_a_stated_value_or_another_status(held: JsonValue) -> None:
    found = check_conditions(in_vivo(temperature=held), *temperature(310.15, 1.0), [IN_VIVO])
    assert entry_of(found, "temperature").record == held
    assert found.applied == ()


@pytest.mark.parametrize(
    ("field_facts", "section_facts", "applies"),
    [
        ({"tissue_state": {"token": "in_vivo", **STATED}}, {}, True),
        ({}, {"tissue_state": {"token": "in_vivo", **STATED}}, True),
        (
            {"tissue_state": {"token": "ex_vivo_fresh", **STATED}},
            {"tissue_state": {"token": "in_vivo", **STATED}},
            False,
        ),
        (
            {"tissue_state": {"token": "in_vivo", **STATED}},
            {"tissue_state": {"token": "ex_vivo_fresh", **STATED}},
            True,
        ),
        ({"tissue_state": UNSTATED}, {"tissue_state": {"token": "in_vivo", **STATED}}, False),
        ({}, {}, False),
        ({"tissue_state": {"token": "fixed", **STATED}}, {}, False),
    ],
    ids=[
        "field",
        "section",
        "field_overrides_section",
        "field_over_another",
        "status_overrides",
        "none",
        "other_token",
    ],
)
def test_an_implied_condition_applies_where_the_merged_specimen_states_its_fact_and_token(
    field_facts: dict[str, JsonValue], section_facts: dict[str, JsonValue], applies: bool
) -> None:
    found = check_conditions(specimen_field(field_facts, section_facts), *temperature(310.15, 1.0), [IN_VIVO])
    assert (entry_of(found, "temperature").status == "met") is applies
    assert found.applied == ((0,) if applies else ())


@pytest.mark.parametrize(
    ("other", "disagree"),
    [
        ({"value": 309.15, "unit": "K"}, True),
        ({"value": 310.15, "unit": "K"}, False),
        ({"range": [310.15, 310.15], "unit": "K"}, True),
    ],
    ids=["another_value", "the_same_value", "a_range_holding_it"],
)
def test_two_implied_conditions_that_disagree_end_the_read_at_step_10(
    other: dict[str, JsonValue], disagree: bool
) -> None:
    """Ruling A: `request_incomplete` with that condition, whether or not the record states it, no condition
    checked and no entry; agreeing, both are applied."""
    normal = implying(3, "disease_and_treatment_state", "normal", temperature=other)
    facts: dict[str, JsonValue] = {
        "tissue_state": {"token": "in_vivo", **STATED},
        "disease_and_treatment_state": {"token": "normal", **STATED},
    }
    for held in ({}, {"temperature": {"value": 296.15, "unit": "K", **STATED}}):
        found = check_conditions(
            specimen_field(facts, {}, **held), *temperature(310.15, 1.0), [IN_VIVO, normal]
        )
        if disagree:
            assert found == ConditionsRead((Reason("request_incomplete", "temperature"),), None)
        else:
            assert found.entries is not None
            assert found.applied == (() if held else (0, 3))


def test_disagreeing_implied_conditions_count_only_where_both_apply() -> None:
    normal = implying(1, "disease_and_treatment_state", "normal", temperature={"value": 293.15, "unit": "K"})
    found = check_conditions(in_vivo(), *temperature(310.15, 1.0), [IN_VIVO, normal])
    assert entry_of(found, "temperature").status == "met"
    assert found.applied == (0,)


def test_an_implied_value_is_compared_as_numbers_so_minus_zero_agrees_with_zero() -> None:
    zero = implying(0, "tissue_state", "in_vivo", specimen_size={"value": 0.0, "unit": "m"})
    minus_zero = implying(1, "tissue_state", "in_vivo", specimen_size={"value": -0.0, "unit": "m"})
    found = check_conditions(in_vivo(), {}, {}, [zero, minus_zero])
    assert entry_of(found, "specimen_size").status == "unknown"
    assert found.applied == (0, 1)


def test_an_implied_token_fills_a_token_condition_and_what_it_requires() -> None:
    """`read_side_contract.md` section 5: those another condition requires with the token it holds by an
    implied condition (PR-311)."""
    tube = implying(0, "tissue_state", "in_vivo", measurement_geometry={"token": "tube"})
    found = check_conditions(in_vivo(), {}, {"measurement_geometry": {"accept": ["tube"]}}, [tube])
    assert entry_of(found, "measurement_geometry").to_json() == {
        "name": "measurement_geometry",
        "status": "met",
        "record": {"token": "tube", "basis": "implied"},
    }
    assert entry_of(found, "measurement_dimension").status == "unknown"


@pytest.mark.parametrize(
    ("location", "field", "located"),
    [
        (LOCATED, "fluid.dynamic_viscosity", True),
        (LOCATED, "bulk.density", False),
        ({}, "fluid.dynamic_viscosity", False),
        ({**LOCATED, "interval": 0.0}, "fluid.dynamic_viscosity", False),
        ({**LOCATED, "region": "lumen"}, "fluid.dynamic_viscosity", False),
        ({"region": "lumen"}, "fluid.dynamic_viscosity", False),
        (
            {"record": {"id": PIN.id, "version": "2.0.0", "content_hash": PIN.content_hash}},
            "fluid.dynamic_viscosity",
            False,
        ),
        (
            {"record": {"id": PIN.id, "version": PIN.version, "content_hash": "sha256:" + "f" * 64}},
            "fluid.dynamic_viscosity",
            False,
        ),
        ({"record": "conformance/field_fixture"}, "fluid.dynamic_viscosity", False),
    ],
    ids=[
        "record",
        "another_field",
        "nowhere",
        "and_an_interval",
        "and_a_region",
        "a_region",
        "another_version",
        "another_content_hash",
        "not_a_reference",
    ],
)
def test_an_implied_condition_applies_only_at_the_reads_own_location(
    location: dict[str, JsonValue], field: str, located: bool
) -> None:
    condition = ImpliedCondition(0, field, location, "tissue_state", "in_vivo", {})
    assert condition.located_at("fluid.dynamic_viscosity", PIN) is located

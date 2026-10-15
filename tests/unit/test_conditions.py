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
from materica.core.conditions import ConditionEntry, ConditionsRead, check_conditions
from materica.core.fields import RecordField
from materica.core.jsonio import JsonValue
from materica.core.read import ReadResult, read
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


def entry_of(read: ConditionsRead, name: str) -> ConditionEntry:
    (found,) = [entry for entry in read.entries if entry.name == name]
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
    """`[a, b]` stated within ± u: `a + u - t <= v <= b - u + t`."""
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
    assert [entry.to_json() for entry in found.entries] == [
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
    assert "measurement_dimension" not in {entry.name for entry in bulk.entries}
    unstated = check_conditions(field_holding(measurement_geometry=UNSTATED), {}, {})
    assert "measurement_dimension" not in {entry.name for entry in unstated.entries}
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

# SPDX-License-Identifier: Apache-2.0
"""The monotonicity relations' mutants (`test_monotonicity_properties.py`): the fail-closed spike's seeded
faults that S2's forms reach, written against the core, the relation aimed at each named, and the unrestricted
twins N1 and N3, which must fail on the core as it is. Each must die within the examples the `ci` profile
gives a property, at both sizes, and records the examples its kill took as `examples_to_kill`. A fault is
injected where the core looks a name up when it runs."""

import dataclasses
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any, NamedTuple, cast

import pytest
from hypothesis import strategies as st

from materica import shapes
from materica.core import conditions, read, value_shapes
from materica.core.conditions import ConditionEntry, ConditionsRead, ImpliedCondition
from materica.core.fields import RecordField
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.value_shapes import Found, JsonObject, an_object, is_status_object
from tests.property import monotonicity_strategies as strategies
from tests.property import test_condition_mutants as condition_mutants
from tests.property import test_monotonicity_properties as properties
from tests.property.monotonicity_strategies import Changed, Drawn
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_condition_mutants import kill
from tests.property.test_mutants import setting


class Mutant(NamedTuple):
    name: str
    relation: str  # a key of `test_monotonicity_properties.RELATIONS`
    inject: Callable[[pytest.MonkeyPatch], None]


def injecting(*settings: Callable[[pytest.MonkeyPatch], None]) -> Callable[[pytest.MonkeyPatch], None]:
    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        for each in settings:
            each(monkeypatch)

    return inject


def taken(name: str) -> Callable[[pytest.MonkeyPatch], None]:
    (found,) = [mutant for mutant in condition_mutants.MUTANTS if mutant.name == name]
    inject: Callable[[pytest.MonkeyPatch], None] = found.inject
    return inject


CHECKED = conditions._checked  # pyright: ignore[reportPrivateUsage]
ENTRY = conditions._entry  # pyright: ignore[reportPrivateUsage]
COMPARED = conditions._compared  # pyright: ignore[reportPrivateUsage]
WITHIN = conditions._within  # pyright: ignore[reportPrivateUsage]
CHECK_CONDITIONS = conditions.check_conditions
READ_VALUE_FIELD = read.read_value_field
REQUIREMENT_CONDITION = read._requirement_condition  # pyright: ignore[reportPrivateUsage]
PROVENANCE = value_shapes.provenance


# N1r: a condition the request names that the record does not hold, skipped.


def _requested_absent_skipped(
    held: JsonObject, requires: Collection[str], required: Mapping[str, object]
) -> list[str]:
    checked: list[str] = CHECKED(
        held, requires, {name: entry for name, entry in required.items() if name in held}
    )
    return checked


# N2: an absent origin read as `measured_by_contributor`.


def _origin_default(field: RecordField, *arguments: Any) -> Any:
    value = an_object(field.value)
    provenance = value.get("provenance")
    if isinstance(provenance, dict) and "origin" not in provenance:
        defaulted = {**value, "provenance": {**provenance, "origin": "measured_by_contributor"}}
        field = dataclasses.replace(field, value=defaulted)
    return READ_VALUE_FIELD(field, *arguments)


# N3r and S2: a condition held as a status object read as met.


Operating = shapes.OperatingCondition | None
Required = shapes.RequirementCondition | None


def _status_object_passes(
    name: str, held: JsonValue | None, operating: Operating, required: Required, reasons: list[Reason]
) -> ConditionEntry:
    if held is not None and is_status_object(held):
        return ConditionEntry(name, "met", an_object(held), operating)
    entry: ConditionEntry = ENTRY(name, held, operating, required, reasons)
    return entry


def _not_applicable_anywhere(
    name: str, held: JsonValue | None, operating: Operating, required: Required, reasons: list[Reason]
) -> ConditionEntry:
    if held is not None and is_status_object(held) and an_object(held)["status"] == "not_applicable":
        return ConditionEntry(name, "met", an_object(held), operating)
    entry: ConditionEntry = ENTRY(name, held, operating, required, reasons)
    return entry


def _status_in_any_member(value: JsonValue, where: str, found: Found) -> None:
    """A status object in `origin` passes step 8, as one standing in any member would."""
    if isinstance(value, dict) and is_status_object(value.get("origin")):
        value = {**value, "origin": "measured_by_contributor"}
    PROVENANCE(value, where, found)


# N4, P2: a bound plus or minus widens the tolerance instead of narrowing it.


def _plus_minus_widens(
    name: str, condition: JsonObject, operating: Operating, required: Required
) -> Reason | None:
    entries = condition.get("plus_minus")
    stated = [an_object(entry) for entry in entries] if isinstance(entries, list) else []
    bounds = [entry["value"] for entry in stated if entry["stated_as"] == "bound"]
    if operating is not None and required is not None and "tolerance" in required and bounds:
        tolerance = cast(shapes.ToleranceRequirement, required)["tolerance"]["value"]  # pyright: ignore[reportUnnecessaryCast]
        bound = bounds[0]
        if isinstance(bound, float) and WITHIN(condition, operating, tolerance, -bound):
            return None
    found: Reason | None = COMPARED(name, condition, operating, required)
    return found


# N5r, P1: a value is met where it lies outside the tolerance.


def _tolerance_inverted(
    condition: JsonObject, operating: shapes.OperatingCondition, tolerance: float, bound: float
) -> bool:
    return not WITHIN(condition, operating, tolerance, bound)


# N6: a tolerance with no operating condition passes step 0, and gives a met entry.


def _tolerance_without_operating_passes(
    name: str, entry: JsonValue, operated: bool, found: list[Reason]
) -> Required:
    passed: Required = REQUIREMENT_CONDITION(name, entry, True, found)
    return passed


def _missing_operating_met(
    name: str, condition: JsonObject, operating: Operating, required: Required
) -> Reason | None:
    if operating is None and required is not None and "tolerance" in required:
        return None
    found: Reason | None = COMPARED(name, condition, operating, required)
    return found


# P3: an accept list read as its last token alone.


def _accept_list_as_its_last_token(
    name: str, condition: JsonObject, operating: Operating, required: Required
) -> Reason | None:
    if required is not None and "accept" in required:
        accept = cast(shapes.AcceptRequirement, required)["accept"]  # pyright: ignore[reportUnnecessaryCast]
        return None if condition["token"] == accept[-1] else Reason("condition_not_accepted", name)
    found: Reason | None = COMPARED(name, condition, operating, required)
    return found


# P4: every condition the request's operating conditions name is checked, as one it gives no tolerance.


def _operating_conditions_checked(
    field: RecordField,
    operating: Mapping[str, shapes.OperatingCondition],
    required: Mapping[str, shapes.RequirementCondition],
    implied: Sequence[ImpliedCondition] = (),
) -> ConditionsRead:
    found: ConditionsRead = CHECK_CONDITIONS(field, operating, required, implied)
    if found.entries is None:
        return found
    held = an_object(an_object(field.value)["conditions"])
    checked = {entry.name for entry in found.entries}
    reasons: list[Reason] = []
    added = [
        ENTRY(name, held.get(name), operating[name], None, reasons)
        for name in operating
        if name not in checked
    ]
    return dataclasses.replace(found, reasons=(*found.reasons, *reasons), entries=(*found.entries, *added))


MUTANTS = [
    # N1r
    Mutant("row_requirements_ignored", "N1r", taken("row_requirements_ignored")),
    Mutant("required_with_ignored", "N1r", taken("required_with_ignored")),
    Mutant("requested_absent_skipped", "N1r", setting(conditions, "_checked", _requested_absent_skipped)),
    # N2
    Mutant("origin_default", "N2", setting(read, "read_value_field", _origin_default)),
    # N3r
    Mutant("status_object_passes", "N3r", setting(conditions, "_entry", _status_object_passes)),
    Mutant("status_in_any_member", "N3r", setting(value_shapes, "provenance", _status_in_any_member)),
    # N4
    Mutant("plus_minus_widens", "N4", setting(conditions, "_compared", _plus_minus_widens)),
    # N5r
    Mutant("tolerance_inverted", "N5r", setting(conditions, "_within", _tolerance_inverted)),
    # N6
    Mutant(
        "missing_operating_met",
        "N6",
        injecting(
            setting(read, "_requirement_condition", _tolerance_without_operating_passes),
            setting(conditions, "_compared", _missing_operating_met),
        ),
    ),
    # N8
    Mutant("implied_overrides_a_stated_value", "N8", taken("implied_overrides_a_stated_value")),
    # P1
    Mutant("tolerance_inverted_widened", "P1", setting(conditions, "_within", _tolerance_inverted)),
    # P2
    Mutant("plus_minus_widens_removed", "P2", setting(conditions, "_compared", _plus_minus_widens)),
    # P3
    Mutant(
        "accept_list_as_its_last_token",
        "P3",
        setting(conditions, "_compared", _accept_list_as_its_last_token),
    ),
    # P4
    Mutant(
        "operating_conditions_checked",
        "P4",
        setting(read, "check_conditions", _operating_conditions_checked),
    ),
    # S1
    Mutant("sd_ignored", "S1", taken("sd_ignored")),
    # S2
    Mutant("status_object_read_as_met", "S2", setting(conditions, "_entry", _status_object_passes)),
    Mutant("not_applicable_anywhere", "S2", setting(conditions, "_entry", _not_applicable_anywhere)),
    # S5
    Mutant("floating_point_as_written", "S5", taken("floating_point_as_written")),
]


# The unrestricted twins, which do not hold: each, with its restriction dropped, must fail on the core.


def _always(facts: JsonObject) -> bool:
    return True


TWINS = {"N1": "N1r", "N3": "N3r"}


@st.composite
def unstated_under_an_implied_condition(draw: st.DrawFn, size: Size) -> Drawn:
    """N3's counterexample, drawn first: an in-vivo field whose temperature an implied condition at the
    operating value would fill, made `unstated`."""
    world = draw(strategies.worlds(size))
    new = strategies.changed(world)
    field = strategies.field_of(new)
    an_object(field["specimen"])["tissue_state"] = {"token": "in_vivo", "basis": "stated"}
    operating = strategies.operating_of(new).get("temperature")
    value = an_object(operating).get("value") if isinstance(operating, dict) else None
    new.request["acceptances"] = [
        strategies.implied_temperature(new, value if isinstance(value, float) else 310.15)
    ]
    base = strategies.repinned(new)
    after = strategies.changed(base)
    strategies.conditions_of(after)["temperature"] = {"status": "unstated"}
    facts: JsonObject = {
        "place": "conditions.temperature",
        "token": "unstated",
        "condition": "temperature",
        "implied": True,
    }
    return Drawn(base, Changed(strategies.repinned(after), facts))


@st.composite
def unchecked_beside_a_met_read(draw: st.DrawFn, size: Size) -> Drawn:
    """N1's counterexample, drawn first: a condition no row requires and the request leaves out, stated in a
    world the read otherwise meets (`condition_unchecked`), removed."""
    world = strategies.met_world(draw, size)
    strategies.conditions_of(world)["specimen_size"] = {"value": 0.005, "unit": "m", "basis": "stated"}
    world = strategies.repinned(world)
    facts: JsonObject = {"condition": "specimen_size", "checked": False, "implied": False}
    return Drawn(world, strategies.removed(world, "specimen_size", facts))


TWIN_SEARCHES: dict[str, Callable[[Size], st.SearchStrategy[Drawn]]] = {
    "N1": unchecked_beside_a_met_read,
    "N3": unstated_under_an_implied_condition,
}


SIZES = [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")]


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_relations_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    mutant.inject(monkeypatch)
    relation = properties.RELATIONS[mutant.relation]
    tried, _ = kill(strategies.drawn(size, relation.change), lambda drawn: checked(mutant.relation, drawn))
    record_property("examples_to_kill", tried)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("twin", sorted(TWINS))
def test_the_unrestricted_twins_mutant_is_killed_by_the_core(
    twin: str,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """N1 and N3 do not hold: a relation that held them would have lost the shapes their restrictions are
    for."""
    restricted = TWINS[twin]
    monkeypatch.setitem(
        properties.RELATIONS, restricted, properties.RELATIONS[restricted]._replace(applies=_always)
    )
    tried, _ = kill(TWIN_SEARCHES[twin](size), lambda drawn: checked(restricted, drawn))
    record_property("examples_to_kill", tried)


def checked(relation: str, drawn: Drawn) -> None:
    properties.check_relation(relation, drawn)

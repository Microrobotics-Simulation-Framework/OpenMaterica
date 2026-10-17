# SPDX-License-Identifier: Apache-2.0
"""Strategies for the information-monotonicity relations of a read (`test_monotonicity_properties.py`): a
world, one record holding a constant and a request for it, and one change to it that a relation speaks of.

Numbers come from small grids, so that a stated value, an operating value and a tolerance often sit exactly at
a boundary (`|r - v| = t`, a plus or minus that just fits), PR-335's 1674.0, 0.2 and 1673.8 among them. Half
the worlds are cooperative: the request is built to fit the field (operating values at or beside the stated
ones, tolerances at the distance or above it, accept lists holding the stated tokens), without which few reads
are `met` and the converse relations are nearly vacuous. Each change says what it did (`Changed.facts`), so
that a relation's precondition reads the generator's knowledge, never the reader under test.
"""

import copy
from collections.abc import Callable
from fractions import Fraction
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.property import model_strategies
from tests.property.condition_strategies import Read, at, base_reads, reference
from tests.property.strategies import Size
from tests.property.value_field_strategies import pinned

JsonObject = dict[str, JsonValue]
Draw = st.DrawFn

GRID: dict[str, tuple[float, ...]] = {
    "temperature": (293.15, 300.0, 309.0, 310.0, 310.15, 311.0),
    "shear_rate": (0.2, 10.0, 100.0, 1000.0, 1674.0),
    "magnetic_flux_density": (0.0, 0.5, 1.0),
    "specimen_size": (0.001, 0.005, 0.01),
    "measurement_dimension": (0.001, 0.005, 0.01),
}
TOLERANCES: dict[str, tuple[float, ...]] = {
    "temperature": (0.0, 0.15, 1.0, 10.0, 20.0),
    "shear_rate": (0.0, 10.0, 1000.0, 1673.8),
    "magnetic_flux_density": (0.0, 0.5),
    "specimen_size": (0.0, 0.004),
    "measurement_dimension": (0.0, 0.004),
}
PLUS_MINUS = (0.0, 0.15, 0.5, 1.0)
STATUS_TOKENS = ("unstated", "not_checked", "none", "not_applicable", "withheld")
CONDITIONS = VOCABULARY.conditions
# An implied condition the worlds' requests may carry: an in-vivo specimen is at body temperature.
IMPLIED_TEMPERATURES = (310.15, 309.0, 293.15)


class World(NamedTuple):
    record: JsonObject
    field: str
    request: JsonObject
    claims: frozenset[Suite]


class Changed(NamedTuple):
    world: World
    facts: JsonObject  # what the change did, for a relation's precondition


def unit_of(name: str) -> str:
    unit = CONDITIONS[name].unit
    assert unit is not None
    return unit


def field_of(world: World) -> JsonObject:
    section, _, name = world.field.partition(".")
    return at(world.record, "body", "sections", section, "fields", name)


def conditions_of(world: World) -> JsonObject:
    return at(field_of(world), "conditions")


def requirement_of(world: World) -> JsonObject:
    return at(world.request, "requirement", "conditions")


def operating_of(world: World) -> JsonObject:
    return at(world.request, "operating_conditions")


def repinned(world: World) -> World:
    record = pinned(world.record)
    request = copy.deepcopy(world.request)
    at(request, "target")["record"] = reference(record)
    for acceptance in request.get("acceptances", []):  # type: ignore[union-attr]
        if isinstance(acceptance, dict):
            acceptance["record"] = reference(record)
    return world._replace(record=record, request=request)


def changed(world: World) -> World:
    return world._replace(record=copy.deepcopy(world.record), request=copy.deepcopy(world.request))


# The world.


@st.composite
def stated(draw: Draw, name: str) -> JsonObject:
    spec = CONDITIONS[name]
    if spec.shape == "token":
        return {"token": draw(st.sampled_from(spec.tokens[:3])), "basis": "stated"}
    grid = GRID[name]
    entry: JsonObject
    if draw(st.integers(0, 4)) == 0:
        lo = draw(st.sampled_from(grid))
        entry = {"range": [lo, draw(st.sampled_from([g for g in grid if g >= lo]))]}
    else:
        entry = {"value": draw(st.sampled_from(grid))}
    entry |= {"unit": unit_of(name), "basis": "stated"}
    if draw(st.integers(0, 3)) == 0:
        entry["plus_minus"] = draw(plus_minus(name))
    return entry


@st.composite
def plus_minus(draw: Draw, name: str) -> list[JsonValue]:
    kind = draw(st.sampled_from(["bound", "bound", "sd", "unstated", "bound_and_sd"]))
    unit = unit_of(name)
    if kind == "bound_and_sd":
        return [
            {"stated_as": "bound", "value": draw(st.sampled_from(PLUS_MINUS)), "unit": unit},
            {"stated_as": "sd", "value": draw(st.sampled_from(PLUS_MINUS)), "unit": unit},
        ]
    stated_as: JsonValue = {"status": "unstated"} if kind == "unstated" else kind
    return [{"stated_as": stated_as, "value": draw(st.sampled_from(PLUS_MINUS)), "unit": unit}]


@st.composite
def condition_state(draw: Draw, name: str, cooperative: bool) -> JsonValue:
    """A condition as the record holds it: stated, `unstated`, absent (None) or another status object."""
    choice = draw(st.sampled_from([0] * 17 + [6, 8, 9])) if cooperative else draw(st.integers(0, 9))
    if choice < 6:
        found: JsonValue = draw(stated(name))
        return found
    if choice < 8:
        return {"status": "unstated"}
    if choice == 8:
        return None
    return {"status": draw(st.sampled_from(STATUS_TOKENS[1:]))}


def checked_names(world: World) -> list[str]:
    """The conditions step 10 checks of the world's field: those it holds, those its row requires, and those
    another condition requires with the token it holds (`provenance.md` section 6.1 item 9)."""
    held = conditions_of(world)
    names = dict.fromkeys([*held, *VOCABULARY.fields[world.field].requires])
    for name, spec in CONDITIONS.items():
        for other, tokens in spec.required_with.items():
            entry = held.get(other)
            if isinstance(entry, dict) and entry.get("token") in tokens:
                names[name] = None
    return [name for name in names if name in CONDITIONS]


@st.composite
def requested(draw: Draw, world: World, cooperative: bool) -> None:
    """The world's request's operating conditions and requirement: a cooperative one fits the field."""
    held = conditions_of(world)
    operating: JsonObject = {}
    required: JsonObject = {}
    for name in sorted(checked_names(world)):
        spec = CONDITIONS[name]
        entry = held.get(name)
        stated_entry = entry if isinstance(entry, dict) and "status" not in entry else None
        if spec.shape == "token":
            choice = draw(st.sampled_from([0] * 9 + [4])) if cooperative else draw(st.integers(0, 4))
            if choice < 3:
                token = stated_entry.get("token") if stated_entry else None
                accept: list[JsonValue] = [token] if isinstance(token, str) else [spec.tokens[0]]
                required[name] = {"accept": accept if choice < 2 else [spec.tokens[-1]]}
            continue
        grid, unit = GRID[name], unit_of(name)
        if cooperative and name not in VOCABULARY.fields[world.field].requires and draw(st.booleans()):
            continue  # a condition the record holds and the request leaves alone: `condition_unchecked`
        if cooperative:
            if stated_entry is not None and "value" in stated_entry:
                stated_value = stated_entry["value"]
                assert isinstance(stated_value, float)
                value = stated_value if draw(st.booleans()) else draw(st.sampled_from(grid))
                operating[name] = {"value": value, "unit": unit}
                distance = float(abs(Fraction(stated_value) - Fraction(value)))
                tolerance = distance if draw(st.booleans()) else draw(st.sampled_from(TOLERANCES[name]))
            elif stated_entry is not None:
                ends = stated_entry["range"]
                assert isinstance(ends, list)
                operating[name] = {"value": draw(st.sampled_from(ends)), "unit": unit}
                tolerance = draw(st.sampled_from(TOLERANCES[name]))
            else:
                operating[name] = {"value": draw(st.sampled_from(grid)), "unit": unit}
                tolerance = draw(st.sampled_from(TOLERANCES[name]))
            required[name] = {"tolerance": {"value": tolerance, "unit": unit}}
            continue
        choice = draw(st.integers(0, 9))
        if choice == 9:
            continue
        if choice < 7:
            operating[name] = {"value": draw(st.sampled_from(grid)), "unit": unit}
        else:
            lo = draw(st.sampled_from(grid))
            operating[name] = {
                "range": [lo, draw(st.sampled_from([g for g in grid if g >= lo]))],
                "unit": unit,
            }
        if draw(st.integers(0, 4)):
            required[name] = {"tolerance": {"value": draw(st.sampled_from(TOLERANCES[name])), "unit": unit}}
    world.request["operating_conditions"] = operating
    world.request["requirement"] = {"want": "value", "conditions": required}


ORIGINS = ("measured_by_contributor",) * 3 + ("stated_without_origin",) * 2 + ("measured_by_source",)
# Conditions beside the row's: a geometry, which may require a dimension with its token; a size no row
# requires, drawn twice as often as the others, so that a numeric condition the read leaves unchecked is in
# about one world in ten (`unchecked_numeric`); and a name the reader does not know.
EXTRAS = ("none", "none", "geometry", "size", "size", "unknown_name")


@st.composite
def worlds(draw: Draw, size: Size) -> World:
    """A record holding one constant of a row, its conditions drawn about the grids, and a request for it."""
    cooperative = draw(st.booleans())
    read = draw(base_reads(size))
    world = World(
        copy.deepcopy(read.record), read.field, copy.deepcopy(read.request), frozenset({"plain_read"})
    )
    field = field_of(world)
    held: JsonObject = {}
    for name in VOCABULARY.fields[world.field].requires:
        state = draw(condition_state(name, cooperative))
        if state is not None:
            held[name] = state
    extra = draw(st.sampled_from(EXTRAS))
    if extra == "geometry":
        held["measurement_geometry"] = {
            "token": draw(st.sampled_from(["tube", "tube", "bulk"])),
            "basis": "stated",
        }
        if draw(st.integers(0, 2)):
            held["measurement_dimension"] = draw(stated("measurement_dimension"))
    elif extra == "size":
        held["specimen_size"] = draw(stated("specimen_size"))
    elif extra == "unknown_name":
        held["temprature"] = {"value": 310.0, "unit": "K", "basis": "stated"}
    field["conditions"] = held
    if draw(st.integers(0, 3)) == 0:
        specimen = at(field, "specimen")
        specimen["tissue_state"] = {
            "token": draw(st.sampled_from(["in_vivo", "in_vivo", "ex_vivo_fresh"])),
            "basis": "stated",
        }
    origin = draw(st.sampled_from(ORIGINS))
    field["provenance"] = {"origin": origin, "review": {"status": "not_checked"}}
    if origin == "measured_by_source":
        at(field, "provenance")["source"] = {"key": "conformance2026"}
    draw(requested(world, cooperative))
    if draw(st.integers(0, 4)) == 0:
        world.request["acceptances"] = [
            implied_temperature(world, draw(st.sampled_from(IMPLIED_TEMPERATURES)))
        ]
    claims: frozenset[Suite] = (
        frozenset({"plain_read", "hash"}) if draw(st.booleans()) else frozenset({"plain_read"})
    )
    return repinned(world._replace(claims=claims))


def implied_temperature(world: World, value: float) -> JsonObject:
    return {
        "acceptance": "implied_condition",
        "record": {},
        "field": world.field,
        "fact": "tissue_state",
        "token": "in_vivo",
        "implies": {"temperature": {"value": value, "unit": "K"}},
        "reason": "an in-vivo specimen is at body temperature",
    }


def implied_applies(world: World, name: str) -> bool:
    """Whether an implied condition the request carries supplies `name` to the world's field: one that names
    it, on a field whose specimen, the section's facts overridden by the field's, states its fact's token."""
    section = at(world.record, "body", "sections", world.field.partition(".")[0])
    facts = {**at(section, "specimen"), **at(field_of(world), "specimen")}
    tissue = facts.get("tissue_state")
    in_vivo = isinstance(tissue, dict) and tissue.get("token") == "in_vivo"
    acceptances = world.request.get("acceptances", [])
    assert isinstance(acceptances, list)
    return in_vivo and any(
        isinstance(acceptance, dict) and name in at(acceptance, "implies") for acceptance in acceptances
    )


def unchecked_numeric(world: World) -> bool:
    """Whether the field holds a numeric condition the reader knows that the read leaves unchecked
    (`condition_unchecked`): N1's shape, which N1r leaves out."""
    return any(
        name in CONDITIONS and CONDITIONS[name].shape == "numeric" and not checked_by_the_read(world, name)
        for name in conditions_of(world)
    )


def checked_by_the_read(world: World, name: str) -> bool:
    """Section 5's first paragraph: the row requires it, another condition requires it with the token it
    holds, or the request names it; a condition the record merely holds is checked only while it holds it."""
    held = conditions_of(world)
    required_with = (
        any(
            isinstance(held.get(other), dict) and at(held, other).get("token") in tokens
            for other, tokens in CONDITIONS[name].required_with.items()
        )
        if name in CONDITIONS
        else False
    )
    return name in VOCABULARY.fields[world.field].requires or name in requirement_of(world) or required_with


# The changes. Each draws a change of the world and what it did, or None where the world holds nothing the
# change speaks of.

Change = Callable[[Draw, World], Changed | None]


def remove_condition(draw: Draw, world: World) -> Changed | None:
    held = conditions_of(world)
    if not held:
        return None
    name = draw(st.sampled_from(sorted(held)))
    facts: JsonObject = {
        "condition": name,
        "checked": checked_by_the_read(world, name),
        "implied": implied_applies(world, name),
    }
    new = changed(world)
    del conditions_of(new)[name]
    return Changed(repinned(new), facts)


PROVENANCE_MEMBERS = (("origin",), ("source",), ("source", "key"), ("review",))


def remove_provenance_member(draw: Draw, world: World) -> Changed | None:
    provenance = at(field_of(world), "provenance")
    present = [path for path in PROVENANCE_MEMBERS if has(provenance, path)]
    if not present:
        return None
    path = draw(st.sampled_from(present))
    new = changed(world)
    holder = at(field_of(new), "provenance", *path[:-1])
    del holder[path[-1]]
    return Changed(repinned(new), {"member": ".".join(path)})


def has(value: JsonValue, path: tuple[str, ...]) -> bool:
    for step in path:
        if not isinstance(value, dict) or step not in value:
            return False
        value = value[step]
    return True


# The places a status object may stand in a constant (`provenance.md` section 1 item 5), and the condition
# places.
STATUS_PLACES = (
    ("value",),
    ("unit",),
    ("statistics",),
    ("statistics", "sd"),
    ("statistics", "mean"),
    ("statistics", "represents"),
    ("provenance", "origin"),
    ("provenance", "source"),
)


def status_object(draw: Draw, world: World) -> Changed | None:
    field = field_of(world)
    members: list[tuple[str, ...]] = [path for path in STATUS_PLACES if has(field, path)]
    held: list[tuple[str, ...]] = [("conditions", name) for name in conditions_of(world)]
    on_a_condition = bool(held) and draw(st.booleans())
    place = draw(st.sampled_from(held if on_a_condition else members))
    token = draw(st.sampled_from(STATUS_TOKENS))
    new = changed(world)
    at(field_of(new), *place[:-1])[place[-1]] = {"status": token}
    condition = place[1] if place[0] == "conditions" else None
    facts: JsonObject = {
        "place": ".".join(place),
        "token": token,
        "condition": condition,
        "implied": condition is not None and implied_applies(world, condition),
    }
    return Changed(repinned(new), facts)


def add_plus_minus(draw: Draw, world: World) -> Changed | None:
    numeric = [
        name
        for name, entry in conditions_of(world).items()
        if name in CONDITIONS
        and CONDITIONS[name].shape == "numeric"
        and isinstance(entry, dict)
        and "status" not in entry
        and "plus_minus" not in entry
    ]
    if not numeric:
        return None
    name = draw(st.sampled_from(sorted(numeric)))
    new = changed(world)
    at(conditions_of(new), name)["plus_minus"] = draw(plus_minus(name))
    return Changed(repinned(new), {"condition": name})


def tolerances(world: World) -> list[str]:
    return sorted(
        name
        for name, entry in requirement_of(world).items()
        if isinstance(entry, dict) and "tolerance" in entry
    )


def tolerance_value(world: World, name: str) -> float:
    value = at(requirement_of(world), name, "tolerance")["value"]
    assert isinstance(value, float)
    return value


def narrow_tolerance(draw: Draw, world: World) -> Changed | None:
    names = tolerances(world)
    if not names:
        return None
    name = draw(st.sampled_from(names))
    t = tolerance_value(world, name)
    narrower = draw(st.sampled_from([v for v in TOLERANCES.get(name, (0.0,)) if v < t] + [t / 2]))
    new = changed(world)
    at(requirement_of(new), name, "tolerance")["value"] = float(narrower)
    return Changed(new, {"condition": name})


def widen_tolerance(draw: Draw, world: World) -> Changed | None:
    names = tolerances(world)
    if not names:
        return None
    name = draw(st.sampled_from(names))
    t = tolerance_value(world, name)
    wider = draw(st.sampled_from([v for v in TOLERANCES.get(name, ()) if v > t] + [t * 2 + 1.0]))
    new = changed(world)
    at(requirement_of(new), name, "tolerance")["value"] = float(wider)
    return Changed(new, {"condition": name})


def remove_operating(draw: Draw, world: World) -> Changed | None:
    names = sorted(operating_of(world))
    if not names:
        return None
    name = draw(st.sampled_from(names))
    new = changed(world)
    del operating_of(new)[name]
    return Changed(new, {"condition": name})


def add_implied(draw: Draw, world: World) -> Changed | None:
    new = changed(world)
    acceptances = new.request.setdefault("acceptances", [])
    assert isinstance(acceptances, list)
    acceptances.append(implied_temperature(world, draw(st.sampled_from(IMPLIED_TEMPERATURES))))
    return Changed(repinned(new), {})


def remove_plus_minus(draw: Draw, world: World) -> Changed | None:
    names = sorted(
        name
        for name, entry in conditions_of(world).items()
        if isinstance(entry, dict) and "plus_minus" in entry
    )
    if not names:
        return None
    name = draw(st.sampled_from(names))
    new = changed(world)
    del at(conditions_of(new), name)["plus_minus"]
    return Changed(repinned(new), {"condition": name})


def add_accept_token(draw: Draw, world: World) -> Changed | None:
    names = sorted(
        name for name, entry in requirement_of(world).items() if isinstance(entry, dict) and "accept" in entry
    )
    if not names:
        return None
    name = draw(st.sampled_from(names))
    accept = at(requirement_of(world), name)["accept"]
    assert isinstance(accept, list)
    missing = [token for token in CONDITIONS[name].tokens if token not in accept]
    if not missing:
        return None
    new = changed(world)
    added = at(requirement_of(new), name)["accept"]
    assert isinstance(added, list)
    added.append(draw(st.sampled_from(missing)))
    return Changed(new, {"condition": name})


def add_operating(draw: Draw, world: World) -> Changed | None:
    """A well-formed operating value, with no tolerance, for a numeric condition the request names nowhere."""
    free = sorted(
        name
        for name, spec in CONDITIONS.items()
        if spec.shape == "numeric" and name not in operating_of(world) and name not in requirement_of(world)
    )
    if not free:
        return None
    name = draw(st.sampled_from(free))
    new = changed(world)
    operating_of(new)[name] = {"value": draw(st.sampled_from(GRID[name])), "unit": unit_of(name)}
    return Changed(new, {"condition": name})


def stated_ends(entry: JsonObject) -> tuple[Fraction, Fraction]:
    if "value" in entry:
        value = entry["value"]
        assert isinstance(value, float)
        return Fraction(value), Fraction(value)
    ends = entry["range"]
    assert isinstance(ends, list)
    lo, hi = ends
    assert isinstance(lo, float)
    assert isinstance(hi, float)
    return Fraction(lo), Fraction(hi)


def exactly_met(world: World, name: str) -> bool | None:
    """Section 5's rows on the exact values, for a stated numeric condition without a plus or minus, against
    its operating condition and tolerance; None where the world gives it no tolerance or the record no
    value."""
    entry = conditions_of(world).get(name)
    operating = operating_of(world).get(name)
    required = requirement_of(world).get(name)
    if not (isinstance(entry, dict) and isinstance(operating, dict) and isinstance(required, dict)):
        return None
    if "status" in entry or "plus_minus" in entry or "tolerance" not in required:
        return None
    a, b = stated_ends(entry)
    lo, hi = stated_ends(operating)
    t = Fraction(tolerance_value(world, name))
    return a - t <= lo and hi <= b + t


def add_uncertain_plus_minus(draw: Draw, world: World) -> Changed | None:
    """S1: a positive `sd` or an unstated plus or minus on a stated condition section 5 finds met."""
    met = sorted(name for name in conditions_of(world) if exactly_met(world, name))
    if not met:
        return None
    name = draw(st.sampled_from(met))
    kind = draw(st.sampled_from(["sd", "unstated"]))
    stated_as: JsonValue = {"status": "unstated"} if kind == "unstated" else "sd"
    new = changed(world)
    at(conditions_of(new), name)["plus_minus"] = [
        {"stated_as": stated_as, "value": draw(st.sampled_from([0.15, 1.0])), "unit": unit_of(name)}
    ]
    return Changed(repinned(new), {"condition": name})


def stated_to_status(draw: Draw, world: World) -> Changed | None:
    """S2: a stated condition made a status object, never `unstated` where an implied condition fills it."""
    names = sorted(
        name
        for name, entry in conditions_of(world).items()
        if name in CONDITIONS and isinstance(entry, dict) and "status" not in entry
    )
    if not names:
        return None
    name = draw(st.sampled_from(names))
    tokens = [token for token in STATUS_TOKENS if not (token == "unstated" and implied_applies(world, name))]
    new = changed(world)
    conditions_of(new)[name] = {"status": draw(st.sampled_from(tokens))}
    return Changed(repinned(new), {"condition": name})


CHANGES: dict[str, Change] = {
    "remove_condition": remove_condition,
    "remove_provenance_member": remove_provenance_member,
    "status_object": status_object,
    "add_plus_minus": add_plus_minus,
    "narrow_tolerance": narrow_tolerance,
    "remove_operating": remove_operating,
    "add_implied": add_implied,
    "widen_tolerance": widen_tolerance,
    "remove_plus_minus": remove_plus_minus,
    "add_accept_token": add_accept_token,
    "add_operating": add_operating,
    "add_uncertain_plus_minus": add_uncertain_plus_minus,
    "stated_to_status": stated_to_status,
}


class Drawn(NamedTuple):
    base: World
    changed: Changed | None
    way: str = "drawn"  # the world as `worlds` draws it, or the trigger built in a met world


# Worlds built to hold a trigger a fault of the read needs, each in a declared share of a relation's draws:
# a world the read meets (`condition_strategies.base_reads`, every condition stated and met exactly, its
# origin other than `stated_without_origin`), changed so that one condition, member or request entry is where
# the relation speaks. The spike's mutants that their triggers alone show died after 4,000 to 8,300 examples
# on random worlds; at S2a each wants a feature floor (the spike's README, "At S2a").


def met_world(draw: Draw, size: Size) -> World:
    read = draw(base_reads(size))
    world = World(
        copy.deepcopy(read.record), read.field, copy.deepcopy(read.request), frozenset({"plain_read"})
    )
    provenance = at(field_of(world), "provenance")
    if provenance["origin"] == "stated_without_origin":
        provenance["origin"] = "measured_by_contributor"
    return world


def unnamed(world: World, name: str) -> None:
    """`name` left out of the request: neither operated nor toleranced."""
    requirement_of(world).pop(name, None)
    operating_of(world).pop(name, None)


# A condition stated, and an operating value one tenth of a millimetre past it, with no tolerance: outside.
JUST_OUTSIDE: tuple[JsonObject, JsonObject] = (
    {"value": 0.005, "unit": "m", "basis": "stated"},
    {"value": 0.0051, "unit": "m"},
)
BOUND: JsonObject = {"stated_as": "bound", "value": 0.001, "unit": "m"}


def just_outside(world: World) -> None:
    stated_entry, operating = JUST_OUTSIDE
    conditions_of(world)["measurement_dimension"] = copy.deepcopy(stated_entry)
    operating_of(world)["measurement_dimension"] = copy.deepcopy(operating)
    requirement_of(world)["measurement_dimension"] = {"tolerance": {"value": 0.0, "unit": "m"}}


def removed(world: World, name: str, facts: JsonObject) -> Changed:
    new = changed(world)
    del conditions_of(new)[name]
    return Changed(repinned(new), facts)


def stated_outside_in_vivo(world: World) -> None:
    """An in-vivo field whose temperature is stated outside its tolerance, 300.0 K against 310.15 within 1.0:
    a read `not_met` that an implied condition at the operating temperature would make `met` in its place."""
    at(field_of(world), "specimen")["tissue_state"] = {"token": "in_vivo", "basis": "stated"}
    conditions_of(world)["temperature"] = {"value": 300.0, "unit": "K", "basis": "stated"}
    operating_of(world)["temperature"] = {"value": 310.15, "unit": "K"}
    requirement_of(world)["temperature"] = {"tolerance": {"value": 1.0, "unit": "K"}}


def implied_beside_it(world: World) -> World:
    """`stated_outside_in_vivo`, the request carrying an implied condition at the operating temperature,
    which applies to the field (`implied_applies`); repinned."""
    stated_outside_in_vivo(world)
    world.request["acceptances"] = [implied_temperature(world, 310.15)]
    assert implied_applies(world, "temperature")
    assert checked_by_the_read(world, "temperature")
    return repinned(world)


# The ways of N1r's and N3r's draws that hold their unrestricted twins' counterexamples, which the twins'
# searches must find (`test_monotonicity_mutants.py`): a condition the read leaves unchecked removed, and one
# an implied condition fills removed, each from a world the read otherwise meets; and a status object, of any
# token, `unstated` included, in the place of a condition an implied condition fills.
UNRESTRICTED_WAYS = {"N1": ("unchecked", "implied_fills"), "N3": ("implied",)}
REMOVAL_WAYS = (
    "drawn",
    "row_required_unnamed",
    "required_with_unnamed",
    "named_only",
    *UNRESTRICTED_WAYS["N1"],
)
STATUS_WAYS = ("drawn", "origin", "condition_outside", *UNRESTRICTED_WAYS["N3"])
OUTSIDE_WAYS = ("drawn", "just_outside")
IMPLIED_WAYS = ("drawn", "stated_outside")
BOUNDARY_WAYS = ("drawn", "at_a_boundary")
NARROW_WAYS = ("drawn", "temperature_alone")
WIDEN_WAYS = ("drawn", "temperature_alone", "met")
PLUS_MINUS_REMOVAL_WAYS = ("drawn", "just_outside", "met")
ACCEPT_WAYS = ("drawn", "met")


@st.composite
def removed_conditions(draw: Draw, size: Size) -> Drawn:
    """N1r's change, the way drawn first: a condition the row requires that the request leaves out; the
    dimension a tube requires, which the request leaves out; a condition the request names that no row
    requires, stated outside its tolerance; or a condition of a world as drawn. Or N1's, which N1r leaves
    out: a condition no row requires and the request leaves out (`condition_unchecked`); or the temperature,
    stated outside its tolerance, which an implied condition fills once it is removed."""
    way = draw(st.sampled_from(REMOVAL_WAYS))
    if way == "drawn":
        world = draw(worlds(size))
        return Drawn(world, remove_condition(draw, world), way)
    world = met_world(draw, size)
    if way == "unchecked":
        conditions_of(world)["specimen_size"] = {"value": 0.005, "unit": "m", "basis": "stated"}
        unnamed(world, "specimen_size")
        world = repinned(world)
        facts: JsonObject = {"condition": "specimen_size", "checked": False, "implied": False}
        assert not checked_by_the_read(world, "specimen_size")
        return Drawn(world, removed(world, "specimen_size", facts), way)
    if way == "implied_fills":
        world = implied_beside_it(world)
        facts = {"condition": "temperature", "checked": True, "implied": True}
        return Drawn(world, removed(world, "temperature", facts), way)
    if way == "row_required_unnamed":
        name = draw(st.sampled_from(sorted(VOCABULARY.fields[world.field].requires)))
        unnamed(world, name)
    elif way == "required_with_unnamed":
        name = "measurement_dimension"
        unnamed(world, name)
    else:
        name = "specimen_size"
        conditions_of(world)[name] = {"value": 0.005, "unit": "m", "basis": "stated"}
        operating_of(world)[name] = {"value": 0.01, "unit": "m"}
        requirement_of(world)[name] = {"tolerance": {"value": 0.0, "unit": "m"}}
    world = repinned(world)
    facts = {"condition": name, "checked": True, "implied": False}
    return Drawn(world, removed(world, name, facts), way)


@st.composite
def status_objects(draw: Draw, size: Size) -> Drawn:
    """N3r's change, the way drawn first: a status object in `origin` beside a value stated without origin; in
    a condition stated outside its tolerance; in the temperature, stated outside its tolerance, which an
    implied condition fills where the status is `unstated` (N3's shape, which N3r leaves out) and must not
    where it is another; or anywhere in a world as drawn."""
    way = draw(st.sampled_from(STATUS_WAYS))
    if way == "drawn":
        world = draw(worlds(size))
        return Drawn(world, status_object(draw, world), way)
    world = met_world(draw, size)
    token = draw(st.sampled_from(STATUS_TOKENS))
    if way == "implied":
        world = implied_beside_it(world)
        facts: JsonObject = {
            "place": "conditions.temperature",
            "token": token,
            "condition": "temperature",
            "implied": True,
        }
        new = changed(world)
        conditions_of(new)["temperature"] = {"status": token}
        return Drawn(world, Changed(repinned(new), facts), way)
    if way == "origin":
        at(field_of(world), "provenance")["origin"] = "stated_without_origin"
        place = ("provenance", "origin")
        facts = {
            "place": "provenance.origin",
            "token": token,
            "condition": None,
            "implied": False,
        }
    else:
        just_outside(world)
        place = ("conditions", "measurement_dimension")
        facts = {
            "place": ".".join(place),
            "token": token,
            "condition": "measurement_dimension",
            "implied": False,
        }
    world = repinned(world)
    new = changed(world)
    at(field_of(new), place[0])[place[1]] = {"status": token}
    return Drawn(world, Changed(repinned(new), facts), way)


@st.composite
def plus_minus_added(draw: Draw, size: Size) -> Drawn:
    """N4's change, the way drawn first: a bound added to a condition stated just outside its tolerance, by
    less than the bound; or a plus or minus added in a world as drawn."""
    way = draw(st.sampled_from(OUTSIDE_WAYS))
    if way == "drawn":
        world = draw(worlds(size))
        return Drawn(world, add_plus_minus(draw, world), way)
    world = met_world(draw, size)
    just_outside(world)
    world = repinned(world)
    new = changed(world)
    at(conditions_of(new), "measurement_dimension")["plus_minus"] = [dict(BOUND)]
    return Drawn(world, Changed(repinned(new), {"condition": "measurement_dimension"}), way)


@st.composite
def plus_minus_removed(draw: Draw, size: Size) -> Drawn:
    """P2's change, the way drawn first: a bound removed from a condition stated just outside its tolerance,
    by less than the bound, or well within it (a read met); or a plus or minus removed in a world as drawn."""
    way = draw(st.sampled_from(PLUS_MINUS_REMOVAL_WAYS))
    if way == "drawn":
        world = draw(worlds(size))
        return Drawn(world, remove_plus_minus(draw, world), way)
    world = met_world(draw, size)
    just_outside(world)
    if way == "met":
        operating_of(world)["measurement_dimension"] = {"value": 0.005, "unit": "m"}
        requirement_of(world)["measurement_dimension"] = {"tolerance": {"value": 0.002, "unit": "m"}}
    at(conditions_of(world), "measurement_dimension")["plus_minus"] = [dict(BOUND)]
    world = repinned(world)
    new = changed(world)
    del at(conditions_of(new), "measurement_dimension")["plus_minus"]
    return Drawn(world, Changed(repinned(new), {"condition": "measurement_dimension"}), way)


@st.composite
def implied_added(draw: Draw, size: Size) -> Drawn:
    """N8's change, the way drawn first: an implied condition at the operating temperature, for an in-vivo
    field whose temperature is stated outside its tolerance; or one added in a world as drawn."""
    way = draw(st.sampled_from(IMPLIED_WAYS))
    if way == "drawn":
        world = draw(worlds(size))
        return Drawn(world, add_implied(draw, world), way)
    world = met_world(draw, size)
    stated_outside_in_vivo(world)
    world = repinned(world)
    new = changed(world)
    new.request["acceptances"] = [implied_temperature(new, 310.15)]
    return Drawn(world, Changed(repinned(new), {}), way)


@st.composite
def at_boundaries(draw: Draw, size: Size) -> Drawn:
    """S5's world, the way drawn first: the temperature at one of section 5's boundaries, as HP7 draws them,
    without a plus or minus, which S5 does not judge; or a world as drawn, on the grids."""
    way = draw(st.sampled_from(BOUNDARY_WAYS))
    world = draw(worlds(size))
    if way == "drawn":
        return Drawn(world, Changed(world, {}), way)
    new = changed(world)
    model_strategies.at_a_boundary(draw, Read(new.record, new.field, new.request))
    at(conditions_of(new), "temperature").pop("plus_minus", None)
    return Drawn(world, Changed(repinned(new), {}), way)


# Rows whose one numeric condition is the temperature, beside the bulk geometry, which requires no dimension:
# a world where a tolerance on the temperature alone decides every comparison of the read.
TEMPERATURE_ALONE = ("bulk.density", "magnetic.remanence", "magnetic.saturation_magnetisation")


def temperature_alone(draw: Draw, size: Size, operated: float, tolerance: float) -> World:
    """A met world of those rows, its temperature stated at 310.0 K and operated at `operated` within
    `tolerance`, and no other numeric condition."""
    read = draw(base_reads(size, TEMPERATURE_ALONE))
    world = World(
        copy.deepcopy(read.record), read.field, copy.deepcopy(read.request), frozenset({"plain_read"})
    )
    provenance = at(field_of(world), "provenance")
    if provenance["origin"] == "stated_without_origin":
        provenance["origin"] = "measured_by_contributor"
    conditions_of(world)["measurement_geometry"] = {"token": "bulk", "basis": "stated"}
    requirement_of(world)["measurement_geometry"] = {"accept": ["bulk"]}
    del conditions_of(world)["measurement_dimension"]
    unnamed(world, "measurement_dimension")
    conditions_of(world)["temperature"] = {"value": 310.0, "unit": "K", "basis": "stated"}
    operating_of(world)["temperature"] = {"value": operated, "unit": "K"}
    requirement_of(world)["temperature"] = {"tolerance": {"value": tolerance, "unit": "K"}}
    return repinned(world)


def tolerance_to(world: World, value: float) -> Changed:
    new = changed(world)
    at(requirement_of(new), "temperature", "tolerance")["value"] = value
    return Changed(new, {"condition": "temperature"})


@st.composite
def narrowed(draw: Draw, size: Size) -> Drawn:
    """N5r's change, the way drawn first: the temperature's tolerance narrowed below the distance it covers,
    in a world where it alone is toleranced; or a tolerance narrowed in a world as drawn."""
    way = draw(st.sampled_from(NARROW_WAYS))
    if way == "drawn":
        world = draw(worlds(size))
        return Drawn(world, narrow_tolerance(draw, world), way)
    world = temperature_alone(draw, size, 310.15, 1.0)
    return Drawn(world, tolerance_to(world, draw(st.sampled_from([0.0, 0.1]))), way)


@st.composite
def widened(draw: Draw, size: Size) -> Drawn:
    """P1's change, the way drawn first: the temperature's tolerance widened past the distance, in a world
    where it alone is toleranced, operated at its stated value (a read met) or past it; or a tolerance widened
    in a world as drawn."""
    way = draw(st.sampled_from(WIDEN_WAYS))
    if way == "drawn":
        world = draw(worlds(size))
        return Drawn(world, widen_tolerance(draw, world), way)
    operated = 310.15 if way == "temperature_alone" else 310.0
    world = temperature_alone(draw, size, operated, draw(st.sampled_from([0.0, 0.1])))
    return Drawn(world, tolerance_to(world, 1.0), way)


@st.composite
def accepted(draw: Draw, size: Size) -> Drawn:
    """P3's change, the way drawn first: a token added to the geometry's accept list in a world the read
    meets; or to an accept list of a world as drawn."""
    way = draw(st.sampled_from(ACCEPT_WAYS))
    world = draw(worlds(size)) if way == "drawn" else repinned(met_world(draw, size))
    return Drawn(world, add_accept_token(draw, world), way)


@st.composite
def changes(draw: Draw, size: Size, change: str) -> Drawn:
    world = draw(worlds(size))
    return Drawn(world, CHANGES[change](draw, world))


# Each relation's draws: its change on a world as drawn, or, for the relations a fault's trigger is rare for,
# the way drawn first, among its ways.
DRAWS: dict[str, Callable[[Size], st.SearchStrategy[Drawn]]] = {
    "remove_condition": removed_conditions,
    "status_object": status_objects,
    "add_plus_minus": plus_minus_added,
    "remove_plus_minus": plus_minus_removed,
    "add_implied": implied_added,
    "at_a_boundary": at_boundaries,
    "narrow_tolerance": narrowed,
    "widen_tolerance": widened,
    "add_accept_token": accepted,
}


WAYS: dict[str, tuple[str, ...]] = {
    "remove_condition": REMOVAL_WAYS,
    "status_object": STATUS_WAYS,
    "add_plus_minus": OUTSIDE_WAYS,
    "remove_plus_minus": PLUS_MINUS_REMOVAL_WAYS,
    "add_implied": IMPLIED_WAYS,
    "at_a_boundary": BOUNDARY_WAYS,
    "narrow_tolerance": NARROW_WAYS,
    "widen_tolerance": WIDEN_WAYS,
    "add_accept_token": ACCEPT_WAYS,
}


def drawn(size: Size, change: str) -> st.SearchStrategy[Drawn]:
    if change in DRAWS:
        return DRAWS[change](size)
    return changes(size, change)

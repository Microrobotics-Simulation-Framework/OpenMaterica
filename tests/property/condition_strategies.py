# SPDX-License-Identifier: Apache-2.0
"""Strategies for steps 9 and 10's properties: a numeric condition stated against an operating value or
range at each boundary section 5's exactness turns on, a stated plus or minus of each kind, the other rows of
section 5's table, and implied conditions, each drawn by its kind first, so that the feature audit holds each
kind to its draw floor; and reads end to end, of records that pass steps 8 to 10, and units other than the
registered one.

A boundary is drawn on the doubles a reader reads: an operating end at `fl(r + t)`, the double next to the
exact bound `r + t` inside or outside it, at ordinary magnitudes and among subnormals, a tolerance that is the
rounded difference `fl(r - v)`, PR-335's mixed magnitudes (a large stated value, a small operating one, and a
tolerance the double next to their exact difference, at or above it, or below it), and negative zero. Every
number is finite; a sum that would overflow is drawn again as the value itself, a boundary all the same.
"""

import copy
import math
import sys
from collections.abc import Callable
from fractions import Fraction
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from tests.property import records
from tests.property.strategies import DOUBLES, TEXT, Size
from tests.property.value_field_strategies import CONSTANT_FIELDS, PIN, fields, pinned, specimen

JsonObject = dict[str, JsonValue]
Draw = st.DrawFn

NUMERIC = tuple(sorted(name for name, spec in VOCABULARY.conditions.items() if spec.shape == "numeric"))
TOKEN = tuple(sorted(name for name, spec in VOCABULARY.conditions.items() if spec.shape == "token"))
ROWS = ("value_value", "value_range", "range_value", "range_range")
BOUNDARIES = (
    "anywhere",
    "at_the_tolerance",
    "one_ulp_inside",
    "one_ulp_outside",
    "rounded_difference",
    "subnormal_inside",
    "subnormal_outside",
    "mixed_magnitudes_inside",
    "mixed_magnitudes_outside",
    "minus_zero",
)
# The kinds drawn on one side of their bound, and the entry that side gives; the others reach both sides, by
# where they draw or by rounding.
SIDES = {
    "one_ulp_inside": "met",
    "one_ulp_outside": "not_met",
    "subnormal_inside": "met",
    "subnormal_outside": "not_met",
    "mixed_magnitudes_inside": "met",
    "mixed_magnitudes_outside": "not_met",
}
NEXT_TO_THE_BOUND = ("one_ulp_inside", "one_ulp_outside", "subnormal_inside", "subnormal_outside")
PLUS_MINUS_KINDS = ("bound", "bound_past_the_tolerance", "sd", "unstated", "bound_beside_sd", "zero")
SUBNORMAL = st.integers(-(2**20), 2**20).map(lambda units: units * 5e-324)
LARGE = st.floats(min_value=1e2, max_value=1e300)
SMALL = st.floats(min_value=-1.0, max_value=1.0)
LARGEST = sys.float_info.max


def finite(number: float, fallback: float) -> float:
    return number if math.isfinite(number) else fallback


def above(number: Fraction, *, strictly: bool) -> float | None:
    """The least double at or above `number`, or above it `strictly`; None where none is."""
    if number > LARGEST or (strictly and number == LARGEST):
        return None
    if number < -LARGEST:
        return -LARGEST
    nearest = float(number)
    if Fraction(nearest) < number or (strictly and Fraction(nearest) == number):
        nearest = math.nextafter(nearest, math.inf)
    return nearest


def below(number: Fraction, *, strictly: bool) -> float | None:
    """The greatest double at or below `number`, or below it `strictly`; None where none is."""
    found = above(-number, strictly=strictly)
    return None if found is None else -found


class Numeric(NamedTuple):
    """A numeric condition as a record states it, without its plus or minus, the operating condition and the
    tolerance; and the end of the stated span the boundary is drawn at, `lower` or `upper`."""

    record: JsonObject
    operating: JsonObject
    tolerance: float
    end: str


def pair(a: float, b: float) -> list[JsonValue]:
    return [min(a, b), max(a, b)]


@st.composite
def numeric(draw: Draw, row: str, boundary: str, slack: float = 0.0) -> Numeric:
    """A stated value or range `[a, b]` and an operating value or range of `row`, one operating end drawn at
    the `boundary` of the window `[a - (t - slack), b + (t - slack)]`, at its lower bound or its upper one,
    the other inside: `slack` is a bound's, whose window section 5 narrows by it."""
    if boundary.startswith("mixed_magnitudes"):
        return draw(mixed_magnitudes(row, inside=SIDES[boundary] == "met"))
    if boundary.startswith("subnormal"):
        r, t, free, width = draw(SUBNORMAL), abs(draw(SUBNORMAL)), draw(SUBNORMAL), abs(draw(SUBNORMAL))
    else:
        r, t, free, width = draw(DOUBLES), abs(draw(DOUBLES)), draw(DOUBLES), abs(draw(DOUBLES))
    if boundary == "minus_zero":
        r, t = draw(st.sampled_from([(-0.0, -0.0), (0.0, -0.0), (-0.0, 0.0), (-0.0, abs(r))]))
    a, b = (r, r) if row.startswith("value") else (r, finite(r + width, r))
    span = finite(t - slack, t)
    lower = draw(st.booleans())
    end = a if lower else b
    edge = finite(end - span if lower else end + span, end)
    if boundary in NEXT_TO_THE_BOUND:
        edge, lower, t = next_to_the_bound(a, b, t, slack, lower, inside=SIDES[boundary] == "met")
    if boundary in ("anywhere", "rounded_difference"):
        edge = free
    if boundary == "rounded_difference":
        t = finite(abs(end - free) + slack, t)
    if boundary == "minus_zero":
        edge = draw(st.sampled_from([-0.0, 0.0, edge]))
    return stated_against(row, r, (a, b), edge, t, lower)


def stated_against(
    row: str, r: float, span: tuple[float, float], edge: float, t: float, lower: bool
) -> Numeric:
    """`row`'s stated value `r` or range `span` and operating value `edge`, or range from `edge` to the stated
    end `lower` names."""
    a, b = span
    record: JsonObject = {"value": r} if row.startswith("value") else {"range": [a, b]}
    end = "lower" if lower else "upper"
    if row.endswith("_value"):
        return Numeric(record, {"value": edge}, t, end)
    return Numeric(record, {"range": pair(edge, a if lower else b)}, t, end)


def next_to_the_bound(
    a: float, b: float, t: float, slack: float, lower: bool, *, inside: bool
) -> tuple[float, bool, float]:
    """The double next to the exact lower bound `a - (t - slack)` of the window where `lower`, else to its
    upper bound `b + (t - slack)`: on it or inside it where `inside`, strictly outside it where not; with the
    side and the tolerance it is drawn at. Where no double lies there, the other bound's; where neither has
    one (a window past the largest doubles), the tolerance is `slack` instead, so that the window is the
    stated span, which always leaves a double outside one of its ends."""
    for tolerance in (t, slack):
        span = Fraction(tolerance) - Fraction(slack)
        for side in (lower, not lower):
            bound = Fraction(a) - span if side else Fraction(b) + span
            edge = (above if side == inside else below)(bound, strictly=not inside)
            if edge is not None:
                return edge, side, tolerance
    raise AssertionError(f"no double next to the window of [{a}, {b}] within {slack}")


@st.composite
def mixed_magnitudes(draw: Draw, row: str, *, inside: bool) -> Numeric:
    """PR-335's pattern: a stated value or range large in magnitude, an operating value or range end small,
    beside it, and a tolerance that is the double next to their exact difference, at or above it where
    `inside`, below it where not, so that no rounding of the difference decides the entry."""
    lower = draw(st.booleans())
    r = draw(LARGE) if lower else -draw(LARGE)
    a, b = (r, r) if row.startswith("value") else (r, finite(r + abs(draw(SMALL)), r))
    edge = draw(SMALL)
    difference = abs(Fraction(a if lower else b) - Fraction(edge))
    t = above(difference, strictly=False) if inside else below(difference, strictly=True)
    assert t is not None
    return stated_against(row, r, (a, b), edge, t, lower)


def plus_minus(kind: str, u: float) -> list[JsonValue]:
    entries: dict[str, list[JsonValue]] = {
        "bound": [{"stated_as": "bound", "value": u}],
        "bound_past_the_tolerance": [{"stated_as": "bound", "value": u}],
        "sd": [{"stated_as": "sd", "value": u}],
        "unstated": [{"stated_as": {"status": "unstated"}, "value": u}],
        "bound_beside_sd": [{"stated_as": "sd", "value": u}, {"stated_as": "bound", "value": u}],
        "zero": [{"stated_as": "sd", "value": 0.0}],
    }
    return entries[kind]


def unit_of(name: str) -> str:
    unit = VOCABULARY.conditions[name].unit
    assert unit is not None
    return unit


def stated(
    name: str, numeric_value: Numeric, plus_minus_entries: list[JsonValue] | None = None
) -> JsonObject:
    """The condition `name` as a record states it, in its registered unit."""
    unit = unit_of(name)
    found: JsonObject = {**numeric_value.record, "unit": unit, "basis": "stated"}
    if plus_minus_entries:
        found["plus_minus"] = [
            {**entry, "unit": unit} for entry in plus_minus_entries if isinstance(entry, dict)
        ]
    return found


def operating_of(name: str, numeric_value: Numeric) -> JsonObject:
    return {**numeric_value.operating, "unit": unit_of(name)}


def tolerance_of(name: str, numeric_value: Numeric) -> JsonObject:
    return {"tolerance": {"value": numeric_value.tolerance, "unit": unit_of(name)}}


# Reads end to end: a record holding a constant that passes steps 8 to 10, and a request it meets.


class Read(NamedTuple):
    record: JsonObject
    field: str  # `<section>.<field>`
    request: JsonObject


REGISTERED_UNITS = tuple(
    sorted(
        {spec.unit for spec in VOCABULARY.fields.values() if isinstance(spec.unit, str)}
        | {spec.unit for spec in VOCABULARY.conditions.values() if spec.unit is not None}
        | {unit for spec in VOCABULARY.facts.values() if (unit := spec.fixed.get("unit")) is not None}
    )
)
FACT_UNITS = {
    name: unit for name, spec in VOCABULARY.facts.items() if (unit := spec.fixed.get("unit")) is not None
}
# Conditions every base states beside its row's: a token condition, and the numeric one its token requires.
BESIDE_THE_ROW = ("measurement_geometry", "measurement_dimension")


def with_registered_facts(specimen: JsonValue) -> None:
    """Each fact of `specimen` whose row fixes a unit, held as its shape, given that unit."""
    if isinstance(specimen, dict):
        for name, fact in specimen.items():
            if name in FACT_UNITS and isinstance(fact, dict) and "status" not in fact:
                fact["unit"] = FACT_UNITS[name]


def specimens_of(field: JsonObject, section: JsonObject) -> list[JsonValue]:
    """Each specimen step 8 checks: the section's, the field's and a derived value's inputs'."""
    found: list[JsonValue] = [section.get("specimen"), field.get("specimen")]
    provenance = field.get("provenance")
    derivation = provenance.get("derivation") if isinstance(provenance, dict) else None
    inputs = derivation.get("input_specimens") if isinstance(derivation, dict) else None
    if isinstance(provenance, dict) and provenance.get("origin") == "derived" and isinstance(inputs, list):
        found += [item.get("specimen") for item in inputs if isinstance(item, dict)]
    return found


@st.composite
def met_condition(draw: Draw, name: str) -> tuple[JsonObject, JsonObject | None, JsonObject]:
    """A stated condition, the operating condition and the requirement that meet it exactly."""
    spec = VOCABULARY.conditions[name]
    if spec.unit is None:
        held = draw(st.sampled_from(spec.tokens))
        return {"token": held, "basis": "stated"}, None, {"accept": [held]}
    unit = spec.unit
    lo, hi = sorted([draw(DOUBLES), draw(DOUBLES)])
    if draw(st.booleans()):
        record: JsonObject = {"value": lo, "unit": unit, "basis": "stated"}
    else:
        record = {"range": [lo, hi], "unit": unit, "basis": "stated"}
    if name == "temperature":
        record["plus_minus"] = [{"stated_as": "bound", "value": 0.0, "unit": unit}]
    return record, {"value": lo, "unit": unit}, {"tolerance": {"value": 0.0, "unit": unit}}


@st.composite
def base_reads(draw: Draw, size: Size, names: tuple[str, ...] = CONSTANT_FIELDS) -> Read:
    """A record holding a constant of `names` that passes steps 8 and 9, every unit registered, its
    conditions its row's and `BESIDE_THE_ROW`, each stated and met by the request, so that steps 11 to 13
    decide the read; a section's and a field's `post_mortem_interval`, and a derived value's input's, are the
    places of a fact's unit."""
    name, field = draw(fields(size, names))
    spec = VOCABULARY.fields[name]
    field["unit"] = spec.unit
    section: JsonObject = {"fields": {name.partition(".")[2]: field}}
    if draw(st.booleans()):
        section["specimen"] = draw(specimen())
    seconds: JsonObject = {"value": 60.0, "unit": "s", "basis": "stated"}
    field_specimen = field.setdefault("specimen", {})
    assert isinstance(field_specimen, dict)
    field_specimen["post_mortem_interval"] = dict(seconds)
    section_specimen = section.setdefault("specimen", {})
    assert isinstance(section_specimen, dict)
    section_specimen["post_mortem_interval"] = dict(seconds)
    for held in specimens_of(field, section):
        with_registered_facts(held)
    conditions: JsonObject = {}
    operating: JsonObject = {}
    required: JsonObject = {}
    for condition in dict.fromkeys([*spec.requires, *BESIDE_THE_ROW]):
        conditions[condition], operated, required[condition] = draw(met_condition(condition))
        if operated is not None:
            operating[condition] = operated
    conditions["measurement_geometry"] = {"token": "tube", "basis": "stated"}
    required["measurement_geometry"] = {"accept": ["tube"]}
    field["conditions"] = conditions
    record = pinned(
        {
            "schema_version": "0.1.0",
            "record_type": "material",
            "id": "conformance/field_fixture",
            "version": "1.0.0",
            "name": "A value field (property)",
            "licence": {"values": "CC0-1.0", "evidence": "excluded"},
            "content_hash": PIN,
            "body": {"sections": {name.partition(".")[0]: section}},
        }
    )
    request: JsonObject = {
        "target": {"record": reference(record), "field": name},
        "operating_conditions": operating,
        "requirement": {"want": "value", "conditions": required},
    }
    return Read(record, name, request)


def reference(record: JsonObject) -> JsonObject:
    return {member: record[member] for member in ("id", "version", "content_hash")}


# Units (HP8): where a unit sits in a base read, and units other than the registered one.

UNIT_PLACES = (
    "field",
    "condition",
    "plus_minus",
    "token_condition",
    "field_fact",
    "section_fact",
    "input_fact",
)
OTHER_UNITS = (
    "compatibility_equal",
    "case_folded",
    "spaced",
    "another_registered",
    "any_text",
    "status_object",
)
# Input facts for a derived value, each with a fact whose row fixes its unit.
DERIVED: JsonObject = {
    "origin": "derived",
    "derivation": {
        "method": "arrhenius_mixing",
        "inputs": [
            {
                "record": {"id": "conformance/a", "version": "1.0.0", "content_hash": PIN},
                "field": "fluid.dynamic_viscosity",
            }
        ],
        "assumptions": [],
        "input_specimens": [
            {
                "input": 0.0,
                "specimen": {"post_mortem_interval": {"value": 60.0, "unit": "s", "basis": "stated"}},
            }
        ],
    },
}


class UnitPlace(NamedTuple):
    holder: JsonObject  # the object holding the `unit`
    registered: str | None  # None on a token condition, which registers none
    condition: str | None  # the condition a mismatch's reason carries


def at(value: JsonValue, *path: str | int) -> JsonObject:
    """The object at `path` in `value`, which a base read holds there."""
    for step in path:
        if isinstance(step, int):
            assert isinstance(value, list)
            value = value[step]
        else:
            assert isinstance(value, dict)
            value = value[step]
    assert isinstance(value, dict)
    return value


# A temperature's two `plus_minus` entries, one of each stated kind, which leave it met within a tolerance
# of 0: the `plus_minus` place, so that a unit is drawn in either entry.
TWO_ENTRIES: list[JsonValue] = [
    {"stated_as": "sd", "value": 0.0, "unit": "K"},
    {"stated_as": "bound", "value": 0.0, "unit": "K"},
]


def entries(place: str) -> st.SearchStrategy[int]:
    """The entry of two that `place_in` takes at `plus_minus`, drawn there alone."""
    return st.sampled_from(range(len(TWO_ENTRIES))) if place == "plus_minus" else st.just(0)


def place_in(read: Read, place: str, entry: int = 0) -> UnitPlace:
    """The object holding the unit at `place` in `read`'s record, changed in place where the base has none
    there (a derived value's provenance, a second `plus_minus` entry); at `plus_minus`, the entry `entry` of
    two."""
    section_name, _, name = read.field.partition(".")
    section = at(read.record, "body", "sections", section_name)
    field = at(section, "fields", name)
    registered = VOCABULARY.fields[read.field].unit
    if place == "field":
        return UnitPlace(field, registered if isinstance(registered, str) else None, None)
    if place == "condition":
        return UnitPlace(at(field, "conditions", "temperature"), "K", "temperature")
    if place == "plus_minus":
        temperature = at(field, "conditions", "temperature")
        temperature["plus_minus"] = copy.deepcopy(TWO_ENTRIES)
        return UnitPlace(at(temperature, "plus_minus", entry), "K", "temperature")
    if place == "token_condition":
        return UnitPlace(at(field, "conditions", "measurement_geometry"), None, "measurement_geometry")
    if place == "field_fact":
        return UnitPlace(at(field, "specimen", "post_mortem_interval"), "s", None)
    if place == "section_fact":
        return UnitPlace(at(section, "specimen", "post_mortem_interval"), "s", None)
    field["provenance"] = copy.deepcopy(DERIVED)
    path = ("provenance", "derivation", "input_specimens", 0, "specimen", "post_mortem_interval")
    return UnitPlace(at(field, *path), "s", None)


FULLWIDTH = {chr(code): chr(code + 0xFEE0) for code in range(0x21, 0x7F)}
COMPATIBLE = {
    **{key: [value] for key, value in FULLWIDTH.items()},
    "K": [chr(0x212A), FULLWIDTH["K"]],
    "1": [chr(0xB9), FULLWIDTH["1"]],
    "3": [chr(0xB3), FULLWIDTH["3"]],
}
SPACES = (" ", chr(0xA0), chr(0x200B), "\t", chr(0x2009))


@st.composite
def other_unit(draw: Draw, kind: str, registered: str) -> JsonValue:
    """A unit other than `registered`, of `kind`: one equal to it under NFKC, under case folding, or but for
    a space, another registered unit, any text, or a status object."""
    if kind == "status_object":
        token = draw(
            st.sampled_from(["unstated", "not_checked", "none", "not_applicable", "withheld", "bogus"])
        )
        return {"status": token, "reason": draw(TEXT)} if draw(st.booleans()) else {"status": token}
    if kind == "another_registered":
        return draw(st.sampled_from([unit for unit in REGISTERED_UNITS if unit != registered]))
    if kind == "any_text":
        text = draw(TEXT)
        return text if text != registered else text + "x"
    positions = list(range(len(registered)))
    if kind == "spaced":
        at = draw(st.integers(0, len(registered)))
        return registered[:at] + draw(st.sampled_from(SPACES)) + registered[at:]
    if kind == "case_folded":
        cased = [index for index in positions if registered[index].swapcase() != registered[index]]
        chosen = draw(st.lists(st.sampled_from(cased), min_size=1, unique=True))
        return "".join(char.swapcase() if index in chosen else char for index, char in enumerate(registered))
    chosen = draw(st.lists(st.sampled_from(positions), min_size=1, unique=True))
    return "".join(
        draw(st.sampled_from(COMPATIBLE[char])) if index in chosen else char
        for index, char in enumerate(registered)
    )


# HP3 at steps 9 and 10: a catalogue of faults, each one change to a base read, written from the text, with
# the reasons, `(code, condition)`, its rule gives. A fault of step 9 ends the read there; two implied
# conditions that disagree end it at step 10 before any condition is checked; any other fault of step 10
# adds its reason to the others step 10 finds, a `not_met` one ending the read with its `conditions`.

Pairs = frozenset[tuple[str, str | None]]


class Fault(NamedTuple):
    step: int
    ends: bool  # whether its reason is `not_met`
    group: str  # the part of the read it changes: two faults of a draw never share one
    change: Callable[[Draw, Read], Pairs]


def section_and_field(read: Read) -> tuple[JsonObject, JsonObject]:
    section_name, _, name = read.field.partition(".")
    section = at(read.record, "body", "sections", section_name)
    return section, at(section, "fields", name)


def requested(read: Read, *path: str) -> JsonObject:
    return at(read.request, *path)


def unit_fault(place: str) -> Fault:
    def change(draw: Draw, read: Read) -> Pairs:
        unit = place_in(read, place, draw(entries(place)))
        kind = draw(st.sampled_from(OTHER_UNITS))
        registered = unit.registered or "K"
        unit.holder["unit"] = draw(
            other_unit(
                kind if kind != "case_folded" or registered.lower() != registered.upper() else "spaced",
                registered,
            )
        )
        return frozenset({("unit_mismatch", unit.condition)})

    group = {"condition": "temperature", "plus_minus": "temperature", "token_condition": "geometry"}.get(
        place, place
    )
    return Fault(9, True, group, change)


def past_its_end(held: JsonObject) -> tuple[float, float]:
    """A double one ulp past the stated value or range `held`, and the start of what it states. Where the end
    is the largest double, the stated end moves one ulp in, so that one lies past it."""
    span = listed(held.get("range")) or [held.get("value"), held.get("value")]
    lo, hi = span
    assert isinstance(lo, float)
    assert isinstance(hi, float)
    past = math.nextafter(hi, math.inf)
    if not math.isfinite(past):
        past, hi = hi, math.nextafter(hi, -math.inf)
        lo = min(lo, hi)
        held.pop("value", None)
        held["range"] = [lo, hi]
    return past, lo


def outside(draw: Draw, read: Read) -> Pairs:
    """The operating temperature one ulp past the stated value or range, within a tolerance of 0."""
    _, field = section_and_field(read)
    past, _ = past_its_end(at(field, "conditions", "temperature"))
    requested(read, "operating_conditions")["temperature"] = {"value": past, "unit": "K"}
    return frozenset({("condition_outside", "temperature")})


def range_outside(draw: Draw, read: Read) -> Pairs:
    """An operating range of the dimension reaching one ulp past its stated value or range."""
    _, field = section_and_field(read)
    past, lo = past_its_end(at(field, "conditions", "measurement_dimension"))
    requested(read, "operating_conditions")["measurement_dimension"] = {"range": [lo, past], "unit": "m"}
    return frozenset({("condition_outside", "measurement_dimension")})


def not_accepted(draw: Draw, read: Read) -> Pairs:
    requested(read, "requirement", "conditions")["measurement_geometry"] = {"accept": ["bulk", "gap"]}
    return frozenset({("condition_not_accepted", "measurement_geometry")})


def in_vivo(read: Read) -> None:
    _, field = section_and_field(read)
    facts = field.setdefault("specimen", {})
    assert isinstance(facts, dict)
    facts["tissue_state"] = {"token": "in_vivo", "basis": "stated"}
    facts["disease_and_treatment_state"] = {"token": "normal", "basis": "stated"}


def implying(read: Read, fact: str, token: str, value: float) -> JsonObject:
    target = requested(read, "target")
    return {
        "acceptance": "implied_condition",
        "record": target["record"],
        "field": read.field,
        "fact": fact,
        "token": token,
        "implies": {"temperature": {"value": value, "unit": "K"}},
        "reason": "a property's",
    }


def disagreeing(draw: Draw, read: Read) -> Pairs:
    """Two implied conditions the specimen states, giving the temperature two values: whether or not the
    record states it, the read ends at step 10 (ruling A)."""
    in_vivo(read)
    first, second = draw(DOUBLES), draw(DOUBLES)
    if second == first:
        second = finite(math.nextafter(first, math.inf), math.nextafter(first, -math.inf))
    read.request["acceptances"] = [
        implying(read, "tissue_state", "in_vivo", first),
        implying(read, "disease_and_treatment_state", "normal", second),
    ]
    return frozenset({("request_incomplete", "temperature")})


def implied_outside(draw: Draw, read: Read) -> Pairs:
    """The temperature unstated, and an implied value one ulp past the operating value and its tolerance."""
    in_vivo(read)
    _, field = section_and_field(read)
    at(field, "conditions")["temperature"] = {"status": "unstated"}
    operated = requested(read, "operating_conditions", "temperature")["value"]
    assert isinstance(operated, float)
    past = math.nextafter(operated, math.inf)
    read.request["acceptances"] = [
        implying(
            read,
            "tissue_state",
            "in_vivo",
            past if math.isfinite(past) else math.nextafter(operated, -math.inf),
        )
    ]
    return frozenset({("condition_outside", "temperature")})


def unchecked(draw: Draw, read: Read) -> Pairs:
    del requested(read, "requirement", "conditions")["temperature"]
    return frozenset({("condition_unchecked", "temperature")})


def unstated(draw: Draw, read: Read) -> Pairs:
    _, field = section_and_field(read)
    at(field, "conditions")["measurement_dimension"] = {"status": draw(st.sampled_from(STATUSES))}
    requested(read, "operating_conditions").pop("measurement_dimension", None)
    requested(read, "requirement", "conditions").pop("measurement_dimension", None)
    return frozenset({("condition_unstated", "measurement_dimension")})


def unknown_name(draw: Draw, read: Read) -> Pairs:
    _, field = section_and_field(read)
    name = "x_" + draw(st.text("abcdefgh", min_size=1, max_size=6))
    at(field, "conditions")[name] = {"value": 1.0, "unit": "bar", "basis": "stated"}
    return frozenset({("condition_unknown_name", name)})


def uncertain(draw: Draw, read: Read) -> Pairs:
    """A standard deviation above zero, and no bound, beside a met temperature."""
    _, field = section_and_field(read)
    sd = draw(st.floats(min_value=5e-324, max_value=1e300))
    at(field, "conditions", "temperature")["plus_minus"] = [{"stated_as": "sd", "value": sd, "unit": "K"}]
    return frozenset({("condition_uncertain", "temperature")})


STATUSES = ("unstated", "not_checked", "none", "not_applicable", "withheld")
STEP_9_FAULTS = {f"unit_{place}": unit_fault(place) for place in UNIT_PLACES}
STEP_10_FAULTS = {
    "outside": Fault(10, True, "temperature", outside),
    "range_outside": Fault(10, True, "dimension", range_outside),
    "not_accepted": Fault(10, True, "geometry", not_accepted),
    "disagreeing": Fault(10, True, "temperature", disagreeing),
    "implied_outside": Fault(10, True, "temperature", implied_outside),
    "unchecked": Fault(10, False, "temperature", unchecked),
    "unstated": Fault(10, False, "dimension", unstated),
    "unknown_name": Fault(10, False, "unknown_name", unknown_name),
    "uncertain": Fault(10, False, "temperature", uncertain),
}
FAULTS = {**STEP_9_FAULTS, **STEP_10_FAULTS}


class Faulty(NamedTuple):
    read: Read
    faults: tuple[str, ...]
    expected: tuple[str, Pairs, bool]  # the status, or "past", the reasons, and whether `conditions` is held


def combined(names: tuple[str, ...], pairs: list[Pairs]) -> tuple[str, Pairs, bool]:
    """What a read with these faults gives: the reasons of step 9's where there are any; else those of two
    implied conditions that disagree; else every reason of step 10, `conditions` held, and "past" step 10
    where none ends it."""
    faults = [FAULTS[name] for name in names]
    step_9 = [found for fault, found in zip(faults, pairs, strict=True) if fault.step == 9]
    nothing: Pairs = frozenset()
    if step_9:
        return "not_met", nothing.union(*step_9), False
    if "disagreeing" in names:
        return "not_met", pairs[names.index("disagreeing")], False
    if any(fault.ends for fault in faults):
        return "not_met", nothing.union(*pairs), True
    return "past", nothing.union(*pairs), True


@st.composite
def faulty_reads(draw: Draw, among: tuple[str, ...], size: Size) -> Faulty:
    """A base read with one fault, its first drawn among `among` before the read, or in one draw in four a
    second of another group from the whole catalogue."""
    two = draw(st.integers(0, 3)) == 0
    first = draw(st.sampled_from(among))
    read = draw(base_reads(size))
    others = [name for name in FAULTS if FAULTS[name].group != FAULTS[first].group]
    names: tuple[str, ...] = (first, draw(st.sampled_from(others))) if two else (first,)
    pairs = [FAULTS[name].change(draw, read) for name in names]
    return Faulty(repinned(read), names, combined(names, pairs))


def repinned(read: Read) -> Read:
    """`read` with its record's hash recomputed, and its request's target and the implied conditions located
    at its record pinning it, any other member of theirs kept."""
    record = pinned(read.record)
    request = copy.deepcopy(read.request)
    at(request, "target", "record").update(reference(record))
    for acceptance in held(listed(request.get("acceptances"))):
        at(acceptance, "record").update(reference(record))
    return read._replace(record=record, request=request)


# HP5 at steps 9 and 10: members the reader does not know, where steps 9 and 10 read.

UNKNOWN_PLACES = (
    "condition",
    "plus_minus_entry",
    "fact",
    "operating",
    "requirement_condition",
    "tolerance",
    "implied",
    "implied_record",
    "implied_value",
)
ENDING = ("outside", "range_outside", "not_accepted", "implied_outside")


def listed(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def held(values: list[JsonValue]) -> list[JsonObject]:
    """The objects among `values` that are no status object."""
    return [value for value in values if isinstance(value, dict) and "status" not in value]


def objects_at(read: Read, place: str) -> list[JsonObject]:
    """The objects of `read` at `place` that a member may be added to (never a status object)."""
    section, field = section_and_field(read)
    stated = held(list(at(field, "conditions").values()))
    acceptances = held(listed(read.request.get("acceptances")))
    conditions = held(list(requested(read, "requirement", "conditions").values()))
    found: dict[str, list[JsonObject]] = {
        "condition": stated,
        "plus_minus_entry": held(
            [entry for condition in stated for entry in listed(condition.get("plus_minus"))]
        ),
        "fact": held([fact for holder in (field, section) for fact in at(holder, "specimen").values()]),
        "operating": held(list(requested(read, "operating_conditions").values())),
        "requirement_condition": conditions,
        "tolerance": [at(condition, "tolerance") for condition in conditions if "tolerance" in condition],
        "implied": acceptances,
        "implied_record": [at(acceptance, "record") for acceptance in acceptances],
        "implied_value": held(
            [value for acceptance in acceptances for value in at(acceptance, "implies").values()]
        ),
    }
    return found[place]


class Unknowns(NamedTuple):
    place: str  # the first addition's
    read: Read
    added: Read  # `read` with the members added
    places: tuple[str, ...]  # where each was added


@st.composite
def with_unknowns(draw: Draw, size: Size) -> Unknowns:
    """A base read, in one draw in two with a fault of step 10 that ends it, so that its `conditions` are
    returned, and with an implied condition the read applies; and one to four members the reader does not
    know added, the first at a place drawn first: each named `x_` and letters or, in one draw in three, a
    member at its place with two characters added."""
    place = draw(st.sampled_from(UNKNOWN_PLACES))
    read = draw(base_reads(size))
    ending = draw(st.sampled_from([None, *ENDING]))
    if ending is not None:
        FAULTS[ending].change(draw, read)
    if "acceptances" not in read.request:
        in_vivo(read)
        acceptance = implying(read, "tissue_state", "in_vivo", draw(DOUBLES))
        acceptance["implies"] = {"specimen_size": {"value": draw(DOUBLES), "unit": "m"}}
        read.request["acceptances"] = [acceptance]
    read = repinned(read)
    added = copy.deepcopy(read)
    places = [place, *draw(st.lists(st.sampled_from(UNKNOWN_PLACES), max_size=3))]
    for current in places:
        holders = objects_at(added, current)
        if not holders:
            continue
        holder = draw(st.sampled_from(holders))
        present = sorted(holder)
        if present and draw(st.integers(0, 2)) == 0:
            name = draw(st.sampled_from(present)) + "xx"
        else:
            name = "x_" + draw(st.text("abcdefghij", min_size=1, max_size=6))
        holder[name] = draw(records.trees(size).values)
    return Unknowns(place, read, repinned(added), tuple(places))

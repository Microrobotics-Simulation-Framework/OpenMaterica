# SPDX-License-Identifier: Apache-2.0
"""(10) Steps 9 and 10's laws (`read_side_contract.md` section 3, steps 9 and 10, and section 5): the S2
design's HP7, HP8 and HP9, and HP3 and HP5 for what steps 9 and 10 decide. The mutants they kill are in
`test_condition_mutants.py`.

- **HP7, conditions against an exact rational oracle.** Step 10 (`conditions.check_conditions`, called as the
  read calls it) gives each condition the entry and reason `condition_oracle.py` gives, written from section 5
  alone: each numeric row at each boundary its exactness turns on, a stated plus or minus of each kind, the
  table's other rows, the conditions checked, and implied conditions that fill, never override, and disagree.
  The entries are read from step 10 itself, as S2a-3 wrote it; HP3 below reads them end to end, where a read
  step 10 does not end goes on to steps 11 to 13 and returns them beside step 10's `unknown` reasons.
- **HP9, the specimen merge.** The facts an implied condition rests on are the section's, each overridden by
  the field's of its name (`record_format.md` section 4 item 2): `RecordField.specimen` is the merge a dict
  merge written here gives, and an implied condition applies exactly where it states the fact and token.
"""

import json
import math
import sys
import unicodedata
from fractions import Fraction
from typing import NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica import shapes
from materica.core.conditions import ConditionsRead, ImpliedCondition, check_conditions
from materica.core.fields import RecordField
from materica.core.identifiers import MaterialRef
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from tests.property import condition_oracle as oracle
from tests.property.condition_strategies import (
    BOUNDARIES,
    COMPATIBLE,
    NUMERIC,
    OTHER_UNITS,
    REGISTERED_UNITS,
    ROWS,
    SIDES,
    STEP_9_FAULTS,
    STEP_10_FAULTS,
    TOKEN,
    UNIT_PLACES,
    UNKNOWN_PLACES,
    Faulty,
    JsonObject,
    Numeric,
    Read,
    Unknowns,
    above,
    base_reads,
    below,
    entries,
    faulty_reads,
    finite,
    next_to_the_bound,
    numeric,
    operating_of,
    other_unit,
    place_in,
    plus_minus,
    repinned,
    stated,
    tolerance_of,
    unit_of,
    with_unknowns,
)
from tests.property.strategies import DOUBLES, SIZE, TEXT, Size
from tests.property.support import feature
from tests.property.value_field_strategies import CONSTANT_FIELDS

FIELD = "fluid.dynamic_viscosity"
PIN = MaterialRef("conformance/field_fixture", "1.0.0", "sha256:" + "0" * 64)
LOCATION: JsonObject = {"record": {"id": PIN.id, "version": PIN.version, "content_hash": PIN.content_hash}}


class Case(NamedTuple):
    """A field's conditions and specimen facts, and the request's operating conditions, requirement and
    implied conditions located at the read."""

    conditions: JsonObject
    operating: dict[str, JsonObject]
    required: dict[str, JsonObject]
    implied: tuple[oracle.Implied, ...]
    section_specimen: JsonObject
    field_specimen: JsonObject


def record_field(case: Case) -> RecordField:
    value: JsonObject = {"form": "constant", "unit": "Pa.s", "value": 0.000692, "conditions": case.conditions}
    if case.field_specimen:
        value["specimen"] = case.field_specimen
    section: JsonObject = {"fields": {"dynamic_viscosity": value}}
    if case.section_specimen:
        section["specimen"] = case.section_specimen
    return RecordField(VOCABULARY.fields[FIELD], value, section)


def as_operating(value: JsonObject) -> shapes.OperatingCondition:
    unit = value["unit"]
    assert isinstance(unit, str)
    if "value" in value:
        number = value["value"]
        assert isinstance(number, float)
        return {"value": number, "unit": unit}
    span = value["range"]
    assert isinstance(span, list)
    assert isinstance(span[0], float)
    assert isinstance(span[1], float)
    return {"range": (span[0], span[1]), "unit": unit}


def as_required(value: JsonObject) -> shapes.RequirementCondition:
    if "accept" in value:
        accept = value["accept"]
        assert isinstance(accept, list)
        return {"accept": [str(token) for token in accept]}
    tolerance = value["tolerance"]
    assert isinstance(tolerance, dict)
    assert isinstance(tolerance["value"], float)
    return {"tolerance": {"value": tolerance["value"], "unit": str(tolerance["unit"])}}


def step_10(case: Case) -> ConditionsRead:
    implied = [
        ImpliedCondition(
            condition.position, FIELD, LOCATION, condition.fact, condition.token, condition.implies
        )
        for condition in case.implied
    ]
    return check_conditions(
        record_field(case),
        {name: as_operating(value) for name, value in case.operating.items()},
        {name: as_required(value) for name, value in case.required.items()},
        implied,
    )


def check_against_the_oracle(case: Case) -> None:
    found = step_10(case)
    merged = {**case.section_specimen, **case.field_specimen}
    expected = oracle.expected(FIELD, case.conditions, merged, case.operating, case.required, case.implied)
    assert {(reason.code, reason.condition) for reason in found.reasons} == expected.reasons, case
    assert set(found.applied) == expected.applied, case
    if expected.statuses is None:
        assert found.entries is None, case
        return
    assert found.entries is not None, case
    assert {entry.name: entry.status for entry in found.entries} == expected.statuses, case
    assert {
        entry.name: entry.record for entry in found.entries if entry.record is not None
    } == expected.records
    operating = {entry.name: entry.operating for entry in found.entries if entry.operating is not None}
    assert operating == {
        name: as_operating(value) for name, value in case.operating.items() if name in expected.statuses
    }


# HP7: a numeric condition at each boundary of each row.


class Bounded(NamedTuple):
    boundary: str  # the kind drawn first
    end: str  # the end of the stated span the boundary is drawn at
    case: Case


@st.composite
def numeric_cases(draw: st.DrawFn, row: str) -> Bounded:
    """A stated value or range of a numeric condition against its operating value or range and tolerance,
    its boundary drawn first."""
    boundary = draw(st.sampled_from(BOUNDARIES))
    name = draw(st.sampled_from(NUMERIC))
    drawn = draw(numeric(row, boundary))
    case = Case(
        {name: stated(name, drawn)},
        {name: operating_of(name, drawn)},
        {name: tolerance_of(name, drawn)},
        (),
        {},
        {},
    )
    return Bounded(boundary, drawn.end, case)


def check_side(drawn: Bounded) -> None:
    """A case of a kind drawn on one side of its bound lies on that side, by the oracle's entry for it."""
    if drawn.boundary in SIDES:
        (name,) = drawn.case.conditions
        case = drawn.case
        expected = oracle.expected(FIELD, case.conditions, {}, case.operating, case.required)
        assert expected.statuses is not None
        assert expected.statuses[name] == SIDES[drawn.boundary], drawn


# Which end of the stated span the boundary sits at, and the window of a bound, declared by the least share
# measured at `ci` in twelve runs of each property, each row's (2026-10-16), rounded down to two places:
# Hypothesis draws `False`, the lower end, less often than `True`.
END_CHANCES = {"lower_end": 0.35, "upper_end": 0.5}


@pytest.mark.chances(**END_CHANCES)
@pytest.mark.parametrize("row", [pytest.param(row, marks=pytest.mark.drawn(*BOUNDARIES)) for row in ROWS])
@given(data=st.data())
def test_a_numeric_condition_is_checked_exactly_at_each_boundary(row: str, data: st.DataObject) -> None:
    """Each kind drawn on one side of its bound lies on that side, so that both sides of each are reached."""
    drawn = data.draw(numeric_cases(row))
    feature(drawn.boundary)
    feature(f"{drawn.end}_end")
    check_against_the_oracle(drawn.case)
    check_side(drawn)


def test_a_case_on_the_other_side_of_its_kind_is_found() -> None:
    """A control on `check_side`: a temperature met exactly, drawn as one ulp outside, fails it."""
    met = Case(
        {"temperature": stated("temperature", Numeric({"value": 310.15}, {}, 0.0, "lower"))},
        {"temperature": {"value": 310.15, "unit": "K"}},
        {"temperature": {"tolerance": {"value": 0.0, "unit": "K"}}},
        (),
        {},
        {},
    )
    check_side(Bounded("one_ulp_inside", "lower", met))
    with pytest.raises(AssertionError):
        check_side(Bounded("one_ulp_outside", "lower", met))


# HP7: a stated plus or minus of each kind.

PLUS_MINUS_KINDS = ("bound", "sd", "unstated", "bound_beside_sd", "zero")
WINDOW = ("at_the_tolerance", "one_ulp_inside", "one_ulp_outside", "anywhere")


class Stated(NamedTuple):
    kind: str  # the plus or minus's, drawn first
    window: str  # the boundary of its bound's window the operating end is drawn at
    end: str
    case: Case


@st.composite
def plus_minus_cases(draw: st.DrawFn) -> Stated:
    """A stated plus or minus of a kind drawn first, its bound's window drawn at its boundary."""
    kind = draw(st.sampled_from(PLUS_MINUS_KINDS))
    row = draw(st.sampled_from(ROWS))
    u = abs(draw(st.one_of(DOUBLES, st.floats(min_value=0.0, max_value=10.0))))
    window = draw(st.sampled_from(WINDOW))
    drawn = draw(numeric(row, window, slack=u if "bound" in kind else 0.0))
    name = draw(st.sampled_from(NUMERIC))
    case = Case(
        {name: stated(name, drawn, plus_minus(kind, u))},
        {name: operating_of(name, drawn)},
        {name: tolerance_of(name, drawn)},
        (),
        {},
        {},
    )
    return Stated(kind, window, drawn.end, case)


@pytest.mark.chances(**END_CHANCES, **{f"window_{window}": 0.18 for window in WINDOW})
@pytest.mark.drawn(*PLUS_MINUS_KINDS)
@given(plus_minus_cases())
def test_a_stated_plus_minus_turns_met_into_unknown_and_nothing_else(drawn: Stated) -> None:
    feature(drawn.kind)
    feature(f"window_{drawn.window}")
    feature(f"{drawn.end}_end")
    check_against_the_oracle(drawn.case)


# HP7: the table's other rows, and the conditions checked.

STATUS_TOKENS = ("unstated", "not_checked", "none", "not_applicable", "withheld")
TABLE_KINDS = (
    "status_object",
    "absent_but_required",
    "absent_but_named",
    "unknown_name",
    "unchecked",
    "token_accepted",
    "token_not_accepted",
    "required_with_its_token",
    "required_with_another_token",
)


@st.composite
def stated_numeric(draw: st.DrawFn, name: str) -> tuple[JsonObject, JsonObject, JsonObject]:
    """A stated numeric condition anywhere, its operating condition and its tolerance."""
    drawn = draw(numeric(draw(st.sampled_from(ROWS)), "anywhere"))
    return stated(name, drawn), operating_of(name, drawn), tolerance_of(name, drawn)


@st.composite
def table_cases(draw: st.DrawFn) -> tuple[str, Case]:
    """Some conditions of each kind of row, one of the kind drawn first among them."""
    kind = draw(st.sampled_from(TABLE_KINDS))
    conditions: JsonObject = {}
    operating: dict[str, JsonObject] = {}
    required: dict[str, JsonObject] = {}
    for name in VOCABULARY.fields[FIELD].requires:
        conditions[name], operating[name], required[name] = draw(stated_numeric(name))
    for current in [kind, *draw(st.lists(st.sampled_from(TABLE_KINDS), max_size=3))]:
        name = draw(st.sampled_from(NUMERIC if current in ("absent_but_named", "unchecked") else TOKEN))
        if current == "status_object":
            name = draw(st.sampled_from([*NUMERIC, *TOKEN]))
            token = draw(st.sampled_from(STATUS_TOKENS))
            conditions[name] = (
                {"status": token, "reason": draw(TEXT)} if draw(st.booleans()) else {"status": token}
            )
        elif current == "absent_but_required":
            conditions.pop(draw(st.sampled_from(VOCABULARY.fields[FIELD].requires)), None)
        elif current == "absent_but_named":
            _, operating[name], required[name] = draw(stated_numeric(name))
            conditions.pop(name, None)
        elif current == "unknown_name":
            conditions["x_" + draw(st.text("abcdef", min_size=1, max_size=5))] = (
                {"status": draw(st.sampled_from(STATUS_TOKENS))} if draw(st.booleans()) else draw(DOUBLES)
            )
        elif current == "unchecked":
            conditions[name], operating[name], _ = draw(stated_numeric(name))
            required.pop(name, None)
        elif current in ("token_accepted", "token_not_accepted"):
            tokens = VOCABULARY.conditions[name].tokens
            held = draw(st.sampled_from(tokens))
            conditions[name] = {"token": held, "basis": "stated"}
            others = [token for token in tokens if token != held]
            accept: list[JsonValue] = (
                [*draw(st.lists(st.sampled_from(others), unique=True))] if others else []
            )
            accept += draw(outside_the_row(name, held))
            required[name] = {"accept": [*accept, held] if current == "token_accepted" else accept}
        else:
            other, tokens = draw(st.sampled_from(sorted(REQUIRED_WITH)))
            held = draw(
                st.sampled_from(tokens if current == "required_with_its_token" else UNREQUIRING[other])
            )
            conditions[other] = {"token": held, "basis": "stated"}
    return kind, Case(conditions, operating, required, (), {}, {})


@st.composite
def outside_the_row(draw: st.DrawFn, name: str, held: str) -> list[JsonValue]:
    """Some strings that are none of the token condition `name`'s tokens, for an accept list beside its own:
    `held` capitalised, a prefix of it, and a token of another token condition's row."""
    prefix = held[: draw(st.integers(1, len(held) - 1))]
    strings = [held.capitalize(), prefix, draw(st.sampled_from(FOREIGN_TOKENS[name]))]
    return [*draw(st.lists(st.sampled_from(strings), unique=True))]


FOREIGN_TOKENS = {
    name: sorted(
        {token for other in TOKEN for token in VOCABULARY.conditions[other].tokens}
        - set(VOCABULARY.conditions[name].tokens)
    )
    for name in TOKEN
}


# Each condition another requires with some of its tokens, and those tokens (`provenance.md` section 6.1).
REQUIRED_WITH = {
    (other, tokens) for spec in VOCABULARY.conditions.values() for other, tokens in spec.required_with.items()
}
UNREQUIRING = {
    other: tuple(token for token in VOCABULARY.conditions[other].tokens if token not in tokens)
    for other, tokens in REQUIRED_WITH
}


@pytest.mark.drawn(*TABLE_KINDS)
@given(table_cases())
def test_each_row_of_the_table_and_the_conditions_it_checks(drawn: tuple[str, Case]) -> None:
    kind, case = drawn
    feature(kind)
    check_against_the_oracle(case)


# HP7: implied conditions.

IMPLIED_KINDS = (
    "fills_an_absent_condition",
    "fills_an_unstated_condition",
    "never_over_a_stated_value",
    "never_over_another_status",
    "two_that_agree",
    "two_that_disagree",
    "a_value_beside_a_range",
    "minus_zero_beside_zero",
    "its_fact_not_stated",
)
TOKEN_FACTS = tuple(sorted(name for name, spec in VOCABULARY.facts.items() if spec.tokens))


@st.composite
def implied_value(draw: st.DrawFn, name: str) -> JsonObject:
    if name in TOKEN:
        return {"token": draw(st.sampled_from(VOCABULARY.conditions[name].tokens))}
    unit = unit_of(name)
    if draw(st.booleans()):
        return {"value": draw(DOUBLES), "unit": unit}
    lo, hi = sorted([draw(DOUBLES), draw(DOUBLES)])
    return {"range": [lo, hi], "unit": unit}


@st.composite
def implied_cases(draw: st.DrawFn) -> tuple[str, Case]:
    """A field whose specimen states a fact and token, and implied conditions resting on it, in a case of
    the kind drawn first."""
    kind = draw(st.sampled_from(IMPLIED_KINDS))
    fact = draw(st.sampled_from(TOKEN_FACTS))
    token = draw(st.sampled_from(VOCABULARY.facts[fact].tokens))
    name = draw(st.sampled_from([*NUMERIC, *TOKEN]))
    value: JsonObject = draw(implied_value(name))
    conditions: JsonObject = {}
    implied = [oracle.Implied(0, fact, token, {name: value})]
    if kind == "fills_an_unstated_condition":
        conditions[name] = {"status": "unstated"}
    elif kind == "never_over_a_stated_value":
        conditions[name] = {**value, "basis": "stated"}
        if name in NUMERIC:
            conditions[name] = {"value": draw(DOUBLES), "unit": unit_of(name), "basis": "stated"}
    elif kind == "never_over_another_status":
        conditions[name] = {"status": draw(st.sampled_from(STATUS_TOKENS[1:]))}
    elif kind in ("two_that_agree", "two_that_disagree", "a_value_beside_a_range", "minus_zero_beside_zero"):
        other: JsonObject = draw(implied_value(name)) if kind == "two_that_disagree" else dict(value)
        if kind == "a_value_beside_a_range" and name in NUMERIC:
            number: JsonValue = draw(DOUBLES)
            value = {"value": number, "unit": unit_of(name)}
            other = {"range": [number, number], "unit": unit_of(name)}
        if kind == "minus_zero_beside_zero" and name in NUMERIC:
            value = {"value": 0.0, "unit": unit_of(name)}
            other = {"value": -0.0, "unit": unit_of(name)}
        second = draw(st.sampled_from([fact_token for fact_token in TOKEN_FACTS if fact_token != fact]))
        second_token = draw(st.sampled_from(VOCABULARY.facts[second].tokens))
        implied = [
            oracle.Implied(0, fact, token, {name: value}),
            oracle.Implied(4, second, second_token, {name: other}),
        ]
    facts: JsonObject = {} if kind == "its_fact_not_stated" else {fact: {"token": token, "basis": "stated"}}
    for condition in implied[1:]:
        facts[condition.fact] = {"token": condition.token, "basis": "stated"}
    operating: dict[str, JsonObject] = {}
    required: dict[str, JsonObject] = {}
    if name in NUMERIC and draw(st.booleans()):
        drawn = draw(numeric("value_value", "anywhere"))
        operating[name], required[name] = operating_of(name, drawn), tolerance_of(name, drawn)
    elif name in TOKEN and draw(st.booleans()):
        tokens: list[JsonValue] = [
            *draw(st.lists(st.sampled_from(VOCABULARY.conditions[name].tokens), unique=True))
        ]
        required[name] = {"accept": tokens}
    return kind, Case(conditions, operating, required, tuple(implied), {}, facts)


@pytest.mark.drawn(*IMPLIED_KINDS)
@given(implied_cases())
def test_implied_conditions_fill_never_override_and_end_the_read_where_they_disagree(
    drawn: tuple[str, Case],
) -> None:
    kind, case = drawn
    feature(kind)
    check_against_the_oracle(case)


# HP9: the specimen merge.

MERGE_KINDS = (
    "section_only",
    "field_only",
    "both_the_same_token",
    "the_field_another_token",
    "the_field_a_status_object",
    "the_section_a_status_object",
    "neither",
)


@st.composite
def merge_cases(draw: st.DrawFn) -> tuple[str, Case]:
    """Section and field facts, one fact of a kind drawn first, with others of both, and an implied condition
    resting on that fact and a token of it."""
    kind = draw(st.sampled_from(MERGE_KINDS))
    fact = draw(st.sampled_from(TOKEN_FACTS))
    tokens = VOCABULARY.facts[fact].tokens
    token = draw(st.sampled_from(tokens))
    other = draw(st.sampled_from([candidate for candidate in tokens if candidate != token] or [token]))
    section: JsonObject = {}
    field: JsonObject = {}
    for name in draw(st.lists(st.sampled_from(TOKEN_FACTS), unique=True, max_size=3)):
        holder = draw(st.sampled_from([section, field]))
        holder[name] = {"token": draw(st.sampled_from(VOCABULARY.facts[name].tokens)), "basis": "stated"}
    section.pop(fact, None)
    field.pop(fact, None)
    held: JsonObject = {"token": token, "basis": "stated"}
    if kind in (
        "section_only",
        "both_the_same_token",
        "the_field_another_token",
        "the_field_a_status_object",
    ):
        section[fact] = held
    if kind in ("field_only", "both_the_same_token", "the_section_a_status_object"):
        field[fact] = held
    if kind == "the_field_another_token":
        field[fact] = {"token": other, "basis": "stated"}
    if kind == "the_field_a_status_object":
        field[fact] = {"status": draw(st.sampled_from(STATUS_TOKENS))}
    if kind == "the_section_a_status_object":
        section[fact] = {"status": draw(st.sampled_from(STATUS_TOKENS))}
    implied = (oracle.Implied(0, fact, token, {"temperature": {"value": 310.15, "unit": "K"}}),)
    return kind, Case({}, {}, {}, implied, section, field)


def check_merge(case: Case) -> None:
    merged = dict(case.section_specimen)
    for name, fact in case.field_specimen.items():
        merged[name] = fact
    assert record_field(case).specimen() == merged, case
    check_against_the_oracle(case)


@pytest.mark.drawn(*MERGE_KINDS)
@given(merge_cases())
def test_an_implied_condition_rests_on_the_section_facts_overridden_by_the_fields(
    drawn: tuple[str, Case],
) -> None:
    kind, case = drawn
    feature(kind)
    check_merge(case)


def test_the_strings_drawn_outside_a_row_are_none_of_its_tokens() -> None:
    """A control on `outside_the_row`: no token of a row is a prefix of another, nor capitalised, so each
    string it draws is outside the row it is drawn for."""
    for name in TOKEN:
        tokens = VOCABULARY.conditions[name].tokens
        for held in tokens:
            drawn = {held.capitalize(), *(held[:end] for end in range(1, len(held))), *FOREIGN_TOKENS[name]}
            assert not drawn & set(tokens), (name, held, drawn & set(tokens))


def test_the_boundaries_are_drawn_on_finite_doubles() -> None:
    """A control on the strategies: a sum past the largest double is drawn as the value itself; the double
    next to an exact bound is the nearest on its side, and none lies past the largest double; a window that
    holds every double below it is left for its upper bound, and one that holds them all for the stated
    span."""
    largest = sys.float_info.max
    tenth = Fraction(1, 10)
    assert finite(largest * 2, 1.0) == 1.0
    assert Fraction(0.1) > tenth
    assert above(tenth, strictly=False) == 0.1
    assert below(tenth, strictly=True) == math.nextafter(0.1, 0.0)
    assert above(Fraction(1), strictly=True) == math.nextafter(1.0, 2.0)
    assert below(Fraction(1), strictly=False) == 1.0
    assert above(Fraction(largest), strictly=True) is None
    assert below(-Fraction(largest) * 2, strictly=False) is None
    past_the_lower = next_to_the_bound(-largest, 1.0, 1.0, 0.0, True, inside=False)
    assert past_the_lower == (math.nextafter(2.0, math.inf), False, 1.0)
    every_double = next_to_the_bound(0.0, 0.0, largest, 0.0, True, inside=False)
    assert every_double == (math.nextafter(0.0, -math.inf), True, 0.0)


# Reads end to end.

PAST = "past step 10"
# The codes only steps 11 to 13 give, which a read step 10 does not end may add beside step 10's reasons.
AFTER_STEP_10 = frozenset(
    code for code, row in oracle.REASONS["reasons"].items() if row.get("steps") and min(row["steps"]) > 10
)


class Outcome(NamedTuple):
    status: str  # the result's, or PAST where step 10 did not end the read and steps 11 to 13 decide it
    reasons: frozenset[tuple[str, str | None]]  # past step 10, those of the steps before 11 alone
    conditions: tuple[tuple[str, JsonValue], ...] | None  # each entry's name and JSON, where it has any


def outcome_of(record: JsonObject, request: JsonObject, text: bytes | None = None) -> Outcome:
    """The read of `request` among `record`, given as `text` where given."""
    store = RecordStore()
    store.add("record", json.dumps(record).encode() if text is None else text)
    try:
        result = read(request, store)
    except NotImplementedError:
        return Outcome(PAST, frozenset(), None)
    written = json.loads(json.dumps(result.to_json()))
    entries = written.get("conditions")
    conditions = None if entries is None else tuple(sorted((entry["name"], entry) for entry in entries))
    pairs = frozenset((reason.code, reason.condition) for reason in result.reasons)
    if result.status != "not_met":
        return Outcome(PAST, frozenset(pair for pair in pairs if pair[0] not in AFTER_STEP_10), conditions)
    return Outcome(result.status, pairs, conditions)


def passed_steps_8_to_10(found: Outcome) -> bool:
    """A read step 10 did not end, which gave no reason before step 11 and returned its conditions."""
    return found.status == PAST and found.reasons == frozenset() and found.conditions is not None


def check_base(read_case: Read) -> None:
    assert passed_steps_8_to_10(outcome_of(read_case.record, read_case.request)), read_case


@given(base_reads(SIZE))
def test_a_base_read_passes_steps_8_to_10(read_case: Read) -> None:
    """The base of every draw below: without it, a refusal could come from the base."""
    check_base(read_case)


# HP8: units by code point.

SENTINEL = "\x00unit\x00"


@st.composite
def escaped(draw: st.DrawFn, text: str) -> str:
    """`text` as a JSON string, each character written as itself, as `\\uXXXX` in either case, or a solidus
    as `\\/`."""
    written: list[str] = []
    for char in text:
        ways = [f"\\u{ord(char):04x}", f"\\u{ord(char):04X}"]
        if char not in '"\\' and ord(char) >= 0x20:
            ways.append(char)
        if char == "/":
            ways.append("\\/")
        written.append(draw(st.sampled_from(ways)))
    return '"' + "".join(written) + '"'


REGISTERED_PLACES = tuple(place for place in UNIT_PLACES if place != "token_condition")


@st.composite
def registered_units(draw: st.DrawFn, size: Size = SIZE) -> tuple[str, Read, bytes]:
    """A base read, its unit at a place drawn first the registered one, written in the record's text with
    escapes."""
    place = draw(st.sampled_from(REGISTERED_PLACES))
    read_case = draw(base_reads(size))
    unit = place_in(read_case, place, draw(entries(place)))
    read_case = repinned(read_case)
    unit.holder["unit"] = SENTINEL
    text = json.dumps(read_case.record).replace(json.dumps(SENTINEL), draw(escaped(str(unit.registered))), 1)
    unit.holder["unit"] = unit.registered
    return place, read_case, text.encode()


def check_registered(drawn: tuple[str, Read, bytes]) -> None:
    _, read_case, text = drawn
    assert passed_steps_8_to_10(outcome_of(read_case.record, read_case.request, text)), text


@pytest.mark.drawn(*REGISTERED_PLACES)
@given(registered_units())
def test_the_registered_unit_passes_step_9_however_escapes_write_it(drawn: tuple[str, Read, bytes]) -> None:
    feature(drawn[0])
    check_registered(drawn)


CASED_UNITS = tuple(unit for unit in REGISTERED_UNITS if unit.swapcase() != unit)
CASED_FIELDS = tuple(name for name in CONSTANT_FIELDS if str(VOCABULARY.fields[name].unit) in CASED_UNITS)


class OtherUnit(NamedTuple):
    place: str
    kind: str
    read: Read
    condition: str | None  # the condition the refusal carries


@st.composite
def other_units(draw: st.DrawFn, place: str, size: Size = SIZE) -> OtherUnit:
    """A base read, its unit at `place` another than the registered one, of a kind drawn first, at
    `plus_minus` in either of two entries; a token condition's any unit, since it registers none."""
    kind = draw(st.sampled_from(OTHER_UNITS))
    names = CASED_FIELDS if kind == "case_folded" else CONSTANT_FIELDS
    read_case = draw(base_reads(size, names))
    unit = place_in(read_case, place, draw(entries(place)))
    registered = unit.registered or draw(st.sampled_from(CASED_UNITS))
    unit.holder["unit"] = draw(other_unit(kind, registered))
    return OtherUnit(place, kind, repinned(read_case), unit.condition)


def check_refused(drawn: OtherUnit) -> None:
    expected = Outcome("not_met", frozenset({("unit_mismatch", drawn.condition)}), None)
    assert outcome_of(drawn.read.record, drawn.read.request) == expected, drawn


@pytest.mark.parametrize(
    "place", [pytest.param(place, marks=pytest.mark.drawn(*OTHER_UNITS)) for place in UNIT_PLACES]
)
@given(data=st.data())
def test_any_other_unit_gives_unit_mismatch_with_its_condition(place: str, data: st.DataObject) -> None:
    """Code point for code point: a unit equal under NFKC (U+212A, full-width forms) or case folding, or but
    for a space, is another unit, and so is a status object where a string is registered."""
    drawn = data.draw(other_units(place))
    feature(drawn.kind)
    check_refused(drawn)


def test_each_compatible_character_normalises_to_the_one_it_stands_for() -> None:
    """A control on `other_unit`: each unit it draws equal under NFKC is so, and differs."""
    for char, variants in COMPATIBLE.items():
        for variant in variants:
            assert variant != char
            assert unicodedata.normalize("NFKC", variant) == char, (char, variant)


# HP3 at steps 9 and 10: one fault, one refusal.


def check_one_fault(faulty: Faulty) -> None:
    status, pairs, held = faulty.expected
    found = outcome_of(faulty.read.record, faulty.read.request)
    assert (found.status, found.reasons, found.conditions is not None) == (
        PAST if status == "past" else status,
        pairs,
        held,
    ), faulty.faults


def fault_features(faulty: Faulty) -> None:
    feature(faulty.faults[0])
    feature("two_faults", len(faulty.faults) == 2)


@pytest.mark.chances(two_faults=0.25)
@pytest.mark.drawn(*STEP_9_FAULTS)
@given(faulty_reads(tuple(STEP_9_FAULTS), SIZE))
def test_one_fault_of_step_9_gives_its_refusal_and_no_other(faulty: Faulty) -> None:
    fault_features(faulty)
    check_one_fault(faulty)


@pytest.mark.chances(two_faults=0.25)
@pytest.mark.drawn(*STEP_10_FAULTS)
@given(faulty_reads(tuple(STEP_10_FAULTS), SIZE))
def test_one_fault_of_step_10_gives_its_reason_beside_the_others(faulty: Faulty) -> None:
    fault_features(faulty)
    check_one_fault(faulty)


# HP5 at steps 9 and 10: members the reader does not know change nothing.


def check_ignored(unknowns: Unknowns) -> None:
    before = outcome_of(unknowns.read.record, unknowns.read.request)
    after = outcome_of(unknowns.added.record, unknowns.added.request)
    assert after == before, (unknowns.added.request, unknowns.added.record)


@pytest.mark.drawn(*UNKNOWN_PLACES)
@given(with_unknowns(SIZE))
def test_members_the_reader_does_not_know_change_nothing_steps_9_and_10_read(unknowns: Unknowns) -> None:
    """In a condition, a stated plus or minus, a fact, the request's operating conditions and requirement, and
    an implied condition, its record and its values: a read that step 10 ends returns its entries without
    them."""
    feature(unknowns.place)
    check_ignored(unknowns)

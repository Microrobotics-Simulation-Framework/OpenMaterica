# SPDX-License-Identifier: Apache-2.0
"""(11) The result's laws (`read_side_contract.md` section 2): the S2 design's HP1, HP2, HP6 and HP11, over
reads that end at each step S2 builds (`result_strategies.py`). The mutants they kill are in
`test_result_mutants.py`.

- **HP1, totality and the reason table.** A read gives a result, or `NotImplementedError` where a step not
  built yet decides it, which only step 8's faults reach here (a table, evidence); every code is in
  the reason table; each `(code, condition)` appears once; and `condition` is present on every `condition_*`
  reason and on no reason of a code that never concerns one (section 2 item 2), the oracle the generated
  reason table.
- **HP2, the status law and the members present.** The status is the worst of the reasons' statuses, which
  the oracle folds from the vocabulary itself; and the members are present as item 6 says: `reasons` and
  `labels` always; `value` exactly where the status is not `not_met` and the result rests on one value (no
  assumption is declared here); `alternative_values` exactly under `no_pick`; `unit` beside either;
  `specimen`, `statistics` and `provenance` beside `value`; no `assumption`; and `conditions` beside a value,
  never under `no_pick` or after a refusal before step 10.
- **HP6, returned as stored.** Every member a read returns from the record equals the stored one, numbers bit
  for bit and status objects as status objects, holding the members the generated shapes define and no
  other (the oracle filters the stored value by the `TypedDict` keys itself, never by the reader's filter),
  each count and index an integer (the code design's rule 5); the review as `provenance.md` section 2 item 6
  reads it; and changing what a result returns changes neither the store nor a later read (rule 6). The
  value is the form's own member, under the `want` that gives it: a constant's number, an interval's bounds
  with their basis, a `none` bound a status, never infinity (`record_format.md` section 6, interval item 3),
  a composition with its basis, sum rule, stated sum and components, never normalised (composition item 4),
  a component's statistics block's counts integers.
- **HP11, claims.** Without the hash suite, `hash_not_checked` is present exactly where the read reached step
  4, which the draw knows; with a correct hash the two reads differ by that label alone.
"""

import json
import struct
from collections.abc import Mapping
from types import UnionType
from typing import Any, Union, cast, get_args, get_origin, get_type_hints, is_typeddict

import pytest
from hypothesis import given

from materica import shapes
from materica.core.jsonio import JsonValue
from materica.core.read import ReadResult, read
from materica.core.record import RecordStore
from materica.core.slips import one_slip
from tests.property import condition_oracle
from tests.property.condition_strategies import at
from tests.property.result_strategies import (
    KINDS,
    VALUED,
    WITH_HASH,
    WITHOUT_HASH,
    Drawn,
    drawn_reads,
    field_at,
    valued_reads,
)
from tests.property.strategies import SIZE
from tests.property.support import feature

JsonObject = dict[str, JsonValue]
REASONS: Mapping[str, Mapping[str, Any]] = condition_oracle.REASONS["reasons"]
BEST_FIRST = ("met", "unknown", "not_met")
# Section 2 item 2: the codes a reason of which carries `condition` always, and those that may carry one,
# where it concerns one condition or a form's axis; every other code carries none.
WITH_A_CONDITION = frozenset(code for code in REASONS if code.startswith("condition_"))
PERHAPS_A_CONDITION = frozenset(
    {
        "request_incomplete",
        "request_unit_mismatch",
        "unit_mismatch",
        "outside_range",
        "at_edge",
        "range_unstated",
        "want_mismatch",
    }
)
# The codes only steps before step 10 give: one of them in a result means step 10 never ran.
BEFORE_STEP_10 = frozenset(
    code for code, row in REASONS.items() if row.get("steps") and max(row["steps"]) < 10
)
COUNTS = ("n_specimens", "n_donors", "n_sources")


def stored(drawn: Drawn) -> RecordStore:
    store = RecordStore()
    for number, source in enumerate(drawn.sources):
        store.add(f"source_{number}", source)
    return store


def read_drawn(
    drawn: Drawn, claims: frozenset[Any] | None = None, store: RecordStore | None = None
) -> ReadResult | None:
    """The read, from `store` where given, or None where a step not built yet decides it. Anything else it
    raises fails the property: a read never raises for what a record or a request holds (section 2 item 1)."""
    try:
        return read(
            drawn.request,
            stored(drawn) if store is None else store,
            claims=drawn.claims if claims is None else claims,
        )
    except NotImplementedError:
        assert drawn.kind == "step_8_fault", f"{drawn.kind} raised"
        return None
    except Exception as error:
        raise AssertionError(f"the read raised {error!r}") from error


def written(result: ReadResult) -> JsonObject:
    """The result as a consumer receives it, through JSON text."""
    value: JsonObject = json.loads(json.dumps(result.to_json()))
    return value


# HP1: totality and the reason table.


def check_totality(drawn: Drawn) -> None:
    result = read_drawn(drawn)
    if result is None:
        return
    pairs = [(reason.code, reason.condition) for reason in result.reasons]
    assert len(set(pairs)) == len(pairs), f"a reason twice: {pairs}"
    for code, condition in pairs:
        assert code in REASONS, f"{code} is no code of the table"
        if code in WITH_A_CONDITION:
            assert isinstance(condition, str), f"{code} without its condition"
        elif code not in PERHAPS_A_CONDITION:
            assert condition is None, f"{code} with the condition {condition}"


def kind_feature(drawn: Drawn) -> None:
    feature(drawn.kind)


@pytest.mark.drawn(*KINDS)
@given(drawn_reads(SIZE))
def test_a_read_gives_a_result_whose_reasons_are_the_tables(drawn: Drawn) -> None:
    kind_feature(drawn)
    check_totality(drawn)


# HP2: the status law, and the members present.


def folded(codes: list[str]) -> str:
    return max((REASONS[code]["status"] for code in codes), key=BEST_FIRST.index, default="met")


def check_status_law(drawn: Drawn) -> None:
    result = read_drawn(drawn)
    if result is None:
        return
    codes = [str(reason.code) for reason in result.reasons]
    assert result.status == folded(codes), (result.status, codes)
    members = written(result)
    no_pick = "no_pick" in codes
    valued = result.status != "not_met" and not no_pick
    assert {"status", "reasons", "labels"} <= set(members), members
    assert ("value" in members) == valued, members
    assert ("alternative_values" in members) == no_pick, members
    assert ("unit" in members) == (valued or no_pick), members
    for name in ("specimen", "statistics", "provenance"):
        assert (name in members) == valued, (name, members)
    assert "assumption" not in members, members
    if valued:
        assert "conditions" in members, members
    if no_pick or set(codes) & BEFORE_STEP_10:
        assert "conditions" not in members, members


@pytest.mark.drawn(*KINDS)
@given(drawn_reads(SIZE))
def test_the_status_is_the_worst_reason_and_the_members_are_those_item_6_gives(drawn: Drawn) -> None:
    kind_feature(drawn)
    check_status_law(drawn)


# HP6: returned as stored.


def same(expected: object, actual: object) -> bool:
    """Equal as JSON values, of one type each (a bool is no number, an integer no double) and doubles bit for
    bit, so that `-0` is not `0`."""
    if isinstance(expected, float):
        return isinstance(actual, float) and struct.pack(">d", expected) == struct.pack(">d", actual)
    if isinstance(expected, list):
        items = cast(list[object], actual) if isinstance(actual, list) else None
        held = cast(list[object], expected)
        return (
            items is not None
            and len(items) == len(held)
            and all(same(item, given) for item, given in zip(held, items, strict=True))
        )
    if isinstance(expected, dict):
        members = cast(dict[str, object], actual) if isinstance(actual, dict) else None
        stored = cast(dict[str, object], expected)
        return (
            members is not None
            and members.keys() == stored.keys()
            and all(same(stored[name], members[name]) for name in stored)
        )
    return type(actual) is type(expected) and actual == expected


def whole(number: JsonValue) -> JsonValue:
    """An index or a count as a result writes it: an integer (the code design's rule 5)."""
    return int(number) if isinstance(number, float) else number


def flattened(shapes_: tuple[object, ...]) -> tuple[object, ...]:
    return tuple(
        alternative
        for shape in shapes_
        for alternative in (get_args(shape) if get_origin(shape) in (Union, UnionType) else (shape,))
    )


def as_stored(value: JsonValue, *shapes_: object) -> JsonValue:
    """`value`, which a generated shape among `shapes_` describes, holding at every depth the members that
    shape defines: an object holding `status` is a status object, holding `status` and `reason`."""
    alternatives = flattened(shapes_)
    if isinstance(value, list):
        items = [get_args(shape)[0] for shape in alternatives if get_origin(shape) in (list, tuple)]
        return [as_stored(item, *items) for item in value]
    objects = [shape for shape in alternatives if is_typeddict(shape)]
    if not isinstance(value, dict) or not objects:
        return value
    if "status" in value:
        return {name: value[name] for name in ("status", "reason") if name in value}
    members: dict[str, list[object]] = {}
    for shape in objects:
        if not set(get_type_hints(shape)) <= {"status", "reason"}:
            for name, member in get_type_hints(shape).items():
                members.setdefault(name, []).append(member)
    return {name: as_stored(member, *members[name]) for name, member in value.items() if name in members}


REVIEW_MEMBERS = ("result", "reviewer", "orcid", "date", "independent_of_extraction", "checklist")


def review_as_read(review: JsonValue) -> JsonValue:
    """`provenance.md` section 2 item 6, written here: as found, a status object holding `not_checked` that
    keeps its shape (section 1 item 5: a `reason` that is a string, no member a review defines beside it),
    or an object holding no `status` whose `result` is `reviewed`, neither holding a member one slip from a
    member a review names; any other review reads as `not_checked`."""
    named = ("status", "reason", *REVIEW_MEMBERS)
    not_checked: JsonObject = {"status": "not_checked"}
    if not isinstance(review, dict) or any(
        member not in named and one_slip(member, name) for member in review for name in named
    ):
        return not_checked
    if "status" in review:
        found = (
            review["status"] == "not_checked"
            and isinstance(review.get("reason", ""), str)
            and not any(name in review for name in REVIEW_MEMBERS)
        )
        return (
            {name: review[name] for name in ("status", "reason") if name in review} if found else not_checked
        )
    if review.get("result") != "reviewed":
        return not_checked
    return {name: review[name] for name in REVIEW_MEMBERS if name in review}


def expected_members(field: JsonObject, section: JsonObject) -> JsonObject:
    """What a read of `field`, in `section`, returns beside its value."""
    provenance = at(field, "provenance")
    summary: JsonObject = {"origin": provenance["origin"], "review": review_as_read(provenance.get("review"))}
    if "source" in provenance:
        summary["source"] = at(provenance, "source")["key"]
    if provenance["origin"] == "derived":
        derivation = cast(JsonObject, as_stored(provenance["derivation"], shapes.Derivation))
        for entry in cast(list[JsonObject], derivation["input_specimens"]):
            entry["input"] = whole(entry["input"])
        summary["derivation"] = derivation
    facts = {**at(section, "specimen"), **at(field, "specimen")}
    return {
        "unit": as_stored(field["unit"], shapes.Unit),
        "specimen": as_stored(facts, shapes.Specimen),
        "statistics": {
            name: whole(member) if name in COUNTS else member
            for name, member in cast(
                JsonObject, as_stored(field["statistics"], shapes.StatisticsBlock)
            ).items()
        },
        "provenance": summary,
        "conditions": {
            name: as_stored(condition, CONDITION_SHAPES[name])
            for name, condition in at(field, "conditions").items()
        },
    }


CONDITION_SHAPES = get_type_hints(shapes.Conditions)
# The members a read returns from a record beside the value, an `alternative_values` entry's but the unit,
# which the result holds once.
RETURNED = ("unit", "specimen", "statistics", "provenance")


def check_members(expected: JsonObject, given: JsonObject, names: tuple[str, ...] = RETURNED) -> None:
    for name in names:
        assert same(expected[name], given[name]), (name, expected[name], given[name])
    stated = at(expected, "conditions")
    for entry in cast(list[JsonObject], given["conditions"]):
        if "record" in entry:
            assert same(stated[str(entry["name"])], entry["record"]), entry


# Each form's own member (`record_format.md` section 5) and its generated shape.
OWN_MEMBERS = {"constant": "value", "interval": "interval", "composition": "composition"}
FIELD_SHAPES = {
    "constant": shapes.ConstantField,
    "interval": shapes.IntervalField,
    "composition": shapes.CompositionField,
}


def expected_value(field: JsonObject) -> JsonValue:
    """The field's own member as a read returns it, a component's statistics block's counts integers."""
    form = str(field["form"])
    own = OWN_MEMBERS[form]
    value = as_stored(field[own], get_type_hints(FIELD_SHAPES[form])[own])
    components = value.get("components") if isinstance(value, dict) else None
    for component in components if isinstance(components, list) else []:
        statistics = component.get("statistics") if isinstance(component, dict) else None
        if isinstance(statistics, dict):
            for name in COUNTS:
                if name in statistics:
                    statistics[name] = whole(statistics[name])
    return value


def check_returned_as_stored(drawn: Drawn) -> None:
    store = stored(drawn)
    result = read_drawn(drawn, store=store)
    assert result is not None
    members = cast(JsonObject, result.to_json())
    held = field_at(drawn.record, drawn.field)
    section = at(drawn.record, "body", "sections", drawn.field.partition(".")[0])
    if "value" in members:
        assert same(expected_value(held), members["value"]), (expected_value(held), members["value"])
        check_members(expected_members(held, section), members)
    for index, entry in enumerate(cast(list[JsonObject], members.get("alternative_values", []))):
        alternative = at(held, "alternatives", index)
        assert type(entry["alternative"]) is int, entry
        assert entry["alternative"] == index, entry
        assert same(expected_value(alternative), entry["value"]), (
            expected_value(alternative),
            entry["value"],
        )
        check_members(expected_members(alternative, section), entry, RETURNED[1:])
        assert same(expected_members(alternative, section)["unit"], members["unit"]), members["unit"]
    before = written(result)
    scrambled(result.to_json())
    assert written(result) == before, "a result shares its JSON with itself"
    scrambled(
        [result.specimen, result.statistics, result.unit, result.provenance and result.provenance.review]
    )
    for read_alone in result.alternative_values or ():
        scrambled([read_alone.specimen, read_alone.statistics])
    again = read_drawn(drawn, store=store)
    assert again is not None, drawn
    assert written(again) == before, "a result shares its members with the record"


def scrambled(value: object) -> None:
    """Every object in `value` emptied but for a member of its own, every list emptied."""
    if isinstance(value, dict):
        members = cast(dict[str, object], value)
        for member in list(members.values()):
            scrambled(member)
        members.clear()
        members["scrambled"] = True
    elif isinstance(value, list):
        items = cast(list[object], value)
        for item in items:
            scrambled(item)
        items.clear()


# A review's ways are declared by their chances: each one's share at `ci` over 22 runs (2026-10-18), rounded
# down to two places. Drawn by `st.sampled_from(REVIEWS)`, they are not a third each: the first shows in about
# half the examples. From the measured clusters, each falls below its draw floor with a probability of at most
# about 1e-12 at `ci`, and the first, the one `dev` judges, at most about 3e-8 there. The unknown member is
# declared the same way: drawn by `st.booleans()`, it shows in about a third of the examples, not half: 0.33
# to 0.36 at `ci` and at `dev` over 20 to 40 runs (2026-10-18), by the draws before it. At 0.33 it falls below
# its floor at `ci` with a probability of at most about 1e-14; `dev` judges no chance below a half.
@pytest.mark.chances(
    form_constant=0.5,
    form_interval=0.25,
    form_composition=0.25,
    negative_zero=0.25,
    statistics_withheld=0.25,
    unknown_member=0.33,
    review_anything=0.53,
    review_reviewed=0.24,
    review_not_checked=0.21,
)
@pytest.mark.drawn(*VALUED)
@given(valued_reads(SIZE))
def test_what_a_read_returns_is_as_stored_and_shares_nothing(drawn: Drawn) -> None:
    kind_feature(drawn)
    for shown in drawn.features:
        feature(shown)
    check_returned_as_stored(drawn)


# HP11: claims.


def without_the_label(result: JsonObject) -> JsonObject:
    labels = result["labels"]
    assert isinstance(labels, list)
    return {**result, "labels": [label for label in labels if label != "hash_not_checked"]}


def check_claims(drawn: Drawn) -> None:
    plain = read_drawn(drawn, WITHOUT_HASH)
    hashed = read_drawn(drawn, WITH_HASH)
    if plain is None or hashed is None:
        assert plain is hashed is None
        return
    assert ("hash_not_checked" in plain.labels) == drawn.reaches_step_4, (plain.labels, drawn.kind)
    assert "hash_not_checked" not in hashed.labels, hashed.labels
    assert without_the_label(written(plain)) == written(hashed)


@pytest.mark.drawn(*KINDS)
@given(drawn_reads(SIZE))
def test_without_the_hash_suite_the_label_marks_exactly_a_read_that_reached_step_4(drawn: Drawn) -> None:
    kind_feature(drawn)
    check_claims(drawn)

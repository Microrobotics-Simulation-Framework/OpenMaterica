# SPDX-License-Identifier: Apache-2.0
"""S4a's properties: step 7 over a field holding alternatives, read with no pick and no overlay
(`read_side_contract.md` section 3, step 7; `record_format.md` section 5), over the draws of
`alternatives_strategies.py`, each outcome drawn first.

- HP27: the read agrees with an oracle written from step 7's text that composes the reads of each alternative
  alone, the record holding it as the field, under the same request: each alternative's standing from the
  codes of its own read, by the step the reason table gives each (`vocabulary/reasons.json`), then the first
  outcome that applies, its reasons, each found reading one alternative carrying its index and a fault of the
  request none, and its members, an entry's from the alternative read alone under the `want` its form gives.
- HP28: order and wrapping, the fail-closed spike's P6 and P5. Reordering the stored alternatives changes the
  status never, and the reasons, the value and the entries only by the indexes' permutation (step 7: "The
  outcome is decided once every alternative is read, so it does not depend on the order of reading"); a value
  field wrapped as its only alternative gives the field's own status, value and reasons, each reason found
  reading it carrying `alternative: 0`, and every member where it stays.
- HP29: monotonicity among alternatives, the spike's N7r and S3. An alternative set aside, added at any
  stored index, changes the status never, and the reasons only by its own and by the indexes it moves,
  its own reported only where the result rests on no single alternative and is `not_met`; two or more
  alternatives that stay never give `met`.

The oracle reads each alternative alone with the implementation's own read of a value field, so HP27 holds
step 7's composition of those reads to the text, not steps 8 to 13, which the other groups and HP12, the
agreement with the reference model, hold.
"""

import copy
import json
from collections.abc import Callable, Mapping
from typing import NamedTuple, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core.read import read
from materica.core.record import RecordStore
from materica.shapes import Suite
from tests.property import alternatives_strategies as strategies
from tests.property.alternatives_strategies import OUTCOMES, Alternatives
from tests.property.strategies import SIZE, Size
from tests.property.support import feature, same
from tests.property.test_model_properties import compared
from tests.property.value_field_strategies import WANTS as FORM_WANTS
from tests.reference.strict_json import JsonObject, JsonValue, parse
from tests.spec_sync.schemas import SCHEMA


class Row(NamedTuple):
    status: str
    steps: frozenset[int]


# The reason table (`read_side_contract.md` section 4), as the vocabulary generated from it holds it.
TABLE: Mapping[str, Row] = {
    code: Row(row["status"], frozenset(int(step) for step in row.get("steps", [])))
    for code, row in json.loads((SCHEMA / "vocabulary" / "reasons.json").read_text(encoding="utf-8"))[
        "reasons"
    ].items()
}


def read_written(record: JsonObject, request: JsonObject, claims: frozenset[Suite]) -> JsonObject:
    """The implementation's read of `request` among `record` alone, its result's JSON read back."""
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    try:
        result = read(request, store, claims=claims)
    except Exception as error:
        raise AssertionError(f"the read raised {error!r}") from error
    written = parse(json.dumps(result.to_json()).encode())
    assert isinstance(written, dict)
    return written


def read_drawn(drawn: Alternatives) -> JsonObject:
    return read_written(drawn.record, drawn.request, drawn.claims)


def alone(drawn: Alternatives, index: int, want: str | None = None) -> JsonObject:
    """The read of the alternative at `index` alone, the record holding it as the field, under the drawn
    request, or under `want`."""
    record, request = strategies.holding(drawn, drawn.stored[index])
    if want is not None:
        request["requirement"] = {**request_requirement(request), "want": want}
    return read_written(record, request, drawn.claims)


def request_requirement(request: JsonObject) -> JsonObject:
    requirement = request["requirement"]
    assert isinstance(requirement, dict)
    return requirement


def reasons_of(result: JsonObject) -> list[JsonObject]:
    found = result["reasons"]
    assert isinstance(found, list)
    return [reason for reason in found if isinstance(reason, dict)]


def codes_of(result: JsonObject, status: str) -> set[str]:
    return {
        str(reason["code"]) for reason in reasons_of(result) if TABLE[str(reason["code"])].status == status
    }


# The oracle (HP27), from step 7's text.


def standing(alone_read: JsonObject) -> str:
    """How an alternative stands, from the `not_met` codes of its read alone and the steps the reason table
    gives each."""
    not_met = codes_of(alone_read, "not_met")
    # "So does a fault of the request (section 1)": `request_incomplete`, which steps 0, 10 and 11 give
    if "request_incomplete" in not_met:
        return "refuses"
    # "An alternative is set aside where its conditions ... give `not_met` at step 10"
    if not_met and all(TABLE[code].steps == frozenset({10}) for code in not_met):
        return "set_aside"
    # "one whose read gives no `not_met`", or "one whose form `want` cannot give": step 13's, which waits
    if all(13 in TABLE[code].steps for code in not_met):
        return "stays"
    # "Every other `not_met` in an alternative's read refuses the field"
    return "refuses"


def found_reading(alone_read: JsonObject, index: int) -> list[JsonObject]:
    """Its reasons, each carrying its index, but a fault of the request (section 2 item 2)."""
    return [
        reason if reason["code"] == "request_incomplete" else {**reason, "alternative": float(index)}
        for reason in reasons_of(alone_read)
    ]


def gives(drawn: Alternatives, index: int, alone_read: JsonObject) -> bool:
    """Whether `want` can give the form of an alternative that stays: its read found no reason at step 13, or
    it is an interval under `want: value` beside a nominal that applies to the read ("since a pick would let
    it apply")."""
    alternative = drawn.stored[index]
    assert isinstance(alternative, dict)
    interval_under_a_nominal = (
        drawn.nominal
        and alternative["form"] == "interval"
        and request_requirement(drawn.request)["want"] == "value"
    )
    return interval_under_a_nominal or not any(
        13 in TABLE[code].steps for code in codes_of(alone_read, "not_met")
    )


def entry(drawn: Alternatives, index: int) -> JsonObject:
    """Its `alternative_values` entry: its form's member as stored, which a read under the `want` its form
    gives returns, and its members as that read gives them, its labels without `hash_not_checked`."""
    alternative = drawn.stored[index]
    assert isinstance(alternative, dict)
    own = alone(drawn, index, FORM_WANTS[str(alternative["form"])])
    found: JsonObject = {"alternative": float(index)}
    for name in ("value", "conditions", "specimen", "statistics", "provenance"):
        if name in own:
            found[name] = own[name]
    labels = own["labels"]
    assert isinstance(labels, list)
    found["labels"] = [label for label in labels if label != "hash_not_checked"]
    return found


def unique(reasons: list[JsonObject]) -> list[JsonValue]:
    """Each reason once, by its code, condition and alternative (section 2 item 2)."""
    kept: dict[str, JsonObject] = {}
    for reason in reasons:
        kept.setdefault(
            json.dumps([reason["code"], reason.get("condition"), reason.get("alternative")]), reason
        )
    return list(kept.values())


def expected(drawn: Alternatives) -> tuple[str, JsonObject]:
    """The outcome and the result step 7's text gives the drawn read, composed of the reads of each
    alternative alone."""
    reads = [alone(drawn, index) for index in range(len(drawn.stored))]
    standings = [standing(alone_read) for alone_read in reads]
    staying = [index for index, found in enumerate(standings) if found == "stays"]
    # "and its `labels` holds at most `hash_not_checked`" for a result that rests on no single alternative
    labels: list[JsonValue] = [] if "hash" in drawn.claims else ["hash_not_checked"]
    if "refuses" in standings or not staying:
        # "`not_met`, with every alternative's reasons, those that wait included"
        every = [
            reason for index, alone_read in enumerate(reads) for reason in found_reading(alone_read, index)
        ]
        outcome = "refused" if "refuses" in standings else "all_set_aside"
        return outcome, {"status": "not_met", "reasons": unique(every), "labels": labels}
    if len(staying) == 1:
        # "that alternative's read, `want` included; the set-aside ones' reasons are not reported"
        (left,) = staying
        return "one_left", {**reads[left], "reasons": unique(found_reading(reads[left], left))}
    # "each one's `unknown` reasons stand beside `want_mismatch` or `no_pick`, and its `not_met` reasons wait"
    beside = [
        reason
        for index in staying
        for reason in found_reading(reads[index], index)
        if TABLE[str(reason["code"])].status == "unknown"
    ]
    if not any(gives(drawn, index, reads[index]) for index in staying):
        return "want_mismatch", {
            "status": "not_met",
            "reasons": unique([{"code": "want_mismatch"}, *beside]),
            "labels": labels,
        }
    entries: list[JsonValue] = [entry(drawn, index) for index in staying]
    first = drawn.stored[staying[0]]
    assert isinstance(first, dict)
    # the `unit` row: "it is the first remaining alternative's unit, in stored order"
    unit = alone(drawn, staying[0], FORM_WANTS[str(first["form"])])["unit"]
    return "no_pick", {
        "status": "unknown",
        "reasons": unique([{"code": "no_pick"}, *beside]),
        "alternative_values": entries,
        "unit": unit,
        "labels": labels,
    }


def check_outcome(drawn: Alternatives) -> None:
    """HP27: the read is the oracle's, every member compared as section 2 compares it: the status, then the
    reasons, then which members it holds, then each."""
    actual, oracle = compared(read_drawn(drawn)), compared(expected(drawn)[1])
    assert same(actual["status"], oracle["status"]), (
        f"status {actual['status']}, the text's {oracle['status']}"
    )
    assert same(actual["reasons"], oracle["reasons"]), (
        f"reasons {actual['reasons']}, the text's {oracle['reasons']}"
    )
    assert actual.keys() == oracle.keys(), f"members {sorted(actual)}, the text's {sorted(oracle)}"
    for name in oracle:
        assert same(actual[name], oracle[name]), f"{name}: {actual[name]}, the text's {oracle[name]}"


# HP28: order and wrapping.


def moved(result: JsonObject, new_index: Callable[[int], int]) -> JsonObject:
    """`result` with each alternative index moved to `new_index` of it, its entries in the new stored
    order."""
    changed = copy.deepcopy(result)

    def index_moved(holder: JsonObject) -> JsonObject:
        index = holder.get("alternative")
        if isinstance(index, float):
            return {**holder, "alternative": float(new_index(int(index)))}
        return holder

    def stored_index(entry: JsonObject) -> float:
        index = entry["alternative"]
        assert isinstance(index, float)
        return index

    changed["reasons"] = [index_moved(reason) for reason in reasons_of(result)]
    entries = result.get("alternative_values")
    if isinstance(entries, list):
        ordered = sorted(
            (index_moved(entry) for entry in entries if isinstance(entry, dict)), key=stored_index
        )
        changed["alternative_values"] = cast(list[JsonValue], ordered)
    return changed


def first_entrys_unit(stored: list[JsonValue], result: JsonObject) -> JsonValue:
    """The unit the alternative of `result`'s first entry stores, among `stored`, as `no_pick` returns it."""
    entries = result["alternative_values"]
    assert isinstance(entries, list)
    first = entries[0]
    assert isinstance(first, dict)
    index = first["alternative"]
    assert isinstance(index, float)
    alternative = stored[int(index)]
    assert isinstance(alternative, dict)
    return alternative["unit"]


def check_order(drawn: Alternatives, order: list[int]) -> None:
    """HP28's P6: the alternatives stored in `order` give the read of the drawn ones, each index moved, and
    under `no_pick` the unit of the first that stays in the new order."""
    stored = [drawn.stored[index] for index in order]
    record, request = strategies.holding(drawn, {"alternatives": stored})
    reordered = read_written(record, request, drawn.claims)
    expected_result = moved(read_drawn(drawn), order.index)
    if "alternative_values" in expected_result:
        expected_result["unit"] = first_entrys_unit(stored, expected_result)
    actual, oracle = compared(reordered), compared(expected_result)
    assert actual.keys() == oracle.keys(), f"members {sorted(actual)}, reordered from {sorted(oracle)}"
    for name in oracle:
        assert same(actual[name], oracle[name]), f"{name}, reordered: {actual[name]}, from {oracle[name]}"


def check_wrapping(drawn: Alternatives, index: int) -> None:
    """HP28's P5: the alternative at `index` read as a field, and as the only alternative of the field."""
    field = drawn.stored[index]
    record, request = strategies.holding(drawn, field)
    as_a_field = read_written(record, request, drawn.claims)
    record, request = strategies.holding(drawn, {"alternatives": [field]})
    wrapped = read_written(record, request, drawn.claims)
    assert wrapped["status"] == as_a_field["status"], (
        f"{wrapped['status']}, as a field {as_a_field['status']}"
    )
    tagged: JsonObject = {**as_a_field, "reasons": unique(found_reading(as_a_field, 0))}
    assert same(compared(wrapped)["reasons"], compared(tagged)["reasons"]), (
        f"reasons {wrapped['reasons']}, as a field {as_a_field['reasons']}"
    )
    if standing(as_a_field) == "stays":
        assert same(compared(wrapped), compared(tagged)), "the one left, as a field"
    else:
        assert set(wrapped) == {"status", "reasons", "labels"}, sorted(wrapped)
        labels = wrapped["labels"]
        assert isinstance(labels, list)
        assert set(labels) <= {"hash_not_checked"}, labels


# HP29: monotonicity among alternatives.


def check_set_aside_added(drawn: Alternatives) -> None:
    """N7r, from the other side: the alternative set aside at `drawn.added`, removed, changes the status
    never; the reasons change by its own alone, and only where the result is `not_met` and rests on no single
    alternative, and by the indexes past it, which move down by one."""
    position = drawn.added
    assert position is not None
    without = [alternative for index, alternative in enumerate(drawn.stored) if index != position]
    record, request = strategies.holding(drawn, {"alternatives": without})
    removed = read_written(record, request, drawn.claims)
    full = read_drawn(drawn)
    assert full["status"] == removed["status"], f"status {full['status']}, without it {removed['status']}"
    added = float(position)
    its_own = [reason for reason in reasons_of(full) if reason.get("alternative") == added]
    rests_on_none = "value" not in full and "alternative_values" not in full and "conditions" not in full
    assert not its_own or (full["status"] == "not_met" and rests_on_none), f"its reasons reported: {its_own}"
    shifted = moved(removed, lambda index: index + 1 if index >= position else index)
    others: JsonObject = {
        **full,
        "reasons": [reason for reason in reasons_of(full) if reason.get("alternative") != added],
    }
    assert same(compared(others), compared(shifted)), f"reasons and members {full}, without it {removed}"


def check_two_staying(drawn: Alternatives) -> None:
    """S3: two or more alternatives that stay never give `met`."""
    status = read_drawn(drawn)["status"]
    assert status != "met", "two or more alternatives that stay give met"


# Each property's examples at a size, and its check of one, which the mutant searches take too.


@st.composite
def reordered(draw: st.DrawFn, size: Size) -> tuple[Alternatives, list[int]]:
    """Alternatives, and an order of their stored indexes drawn among every permutation."""
    drawn = draw(strategies.alternatives(size))
    return drawn, draw(st.permutations(range(len(drawn.stored))))


@st.composite
def wrapped(draw: st.DrawFn, size: Size) -> tuple[Alternatives, int]:
    """Alternatives, and the stored index of the one wrapped alone."""
    drawn = draw(strategies.alternatives(size))
    return drawn, draw(st.integers(0, len(drawn.stored) - 1))


def check_reordered(example: tuple[Alternatives, list[int]]) -> None:
    check_order(*example)


def check_wrapped(example: tuple[Alternatives, int]) -> None:
    check_wrapping(*example)


def check_drawn_outcome(drawn: Alternatives) -> None:
    """The strategy's own check: the outcome it draws is the one the oracle gives, so that the audit's count
    of each is a count of what the text decides."""
    assert expected(drawn)[0] == drawn.outcome, f"drawn {drawn.outcome}, the text's {expected(drawn)[0]}"


@pytest.mark.drawn(*OUTCOMES)
@given(strategies.alternatives(SIZE))
def test_the_outcome_over_alternatives_is_the_texts(drawn: Alternatives) -> None:
    feature(drawn.outcome)
    check_drawn_outcome(drawn)
    check_outcome(drawn)


@pytest.mark.drawn(*OUTCOMES)
@given(reordered(SIZE))
def test_the_order_of_the_alternatives_moves_only_their_indexes(
    example: tuple[Alternatives, list[int]],
) -> None:
    feature(example[0].outcome)
    check_reordered(example)


@pytest.mark.drawn(*OUTCOMES)
@given(wrapped(SIZE))
def test_a_field_wrapped_as_its_only_alternative_reads_as_the_field(
    example: tuple[Alternatives, int],
) -> None:
    feature(example[0].outcome)
    check_wrapped(example)


@pytest.mark.drawn(*OUTCOMES)
@given(strategies.alternatives(SIZE, added=True))
def test_an_alternative_set_aside_changes_no_status(drawn: Alternatives) -> None:
    feature(drawn.outcome)
    check_set_aside_added(drawn)


@pytest.mark.drawn("want_mismatch", "no_pick")
@given(strategies.alternatives(SIZE, ("want_mismatch", "no_pick")))
def test_two_alternatives_that_stay_never_give_met(drawn: Alternatives) -> None:
    feature(drawn.outcome)
    check_two_staying(drawn)

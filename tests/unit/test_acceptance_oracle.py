# SPDX-License-Identifier: Apache-2.0
"""Fuzz target 5's oracles (`tests/fuzz/acceptance_oracle.py`, beside `field_oracle.py`'s it shares), which
the target itself, needing Atheris, cannot show here: quiet on the core as it is, at every place the target
reads, under every acceptance of the conformance cases (its seeds); failing on each law of a result under an
acceptance broken, on a status an acceptance makes better, and on the fault seeded for its control; and the
reference model's oracle failing where the read applies an extrapolation the text does not. And the control's
own premise: no seed holds the input the fault changes, so the fuzzer has to build one."""

import copy
import dataclasses
import json
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest

from materica.core import read as read_module
from materica.core.jsonio import JsonValue
from materica.core.read import FormRange, ReadRequest, read
from materica.core.reasons import Reason
from materica.core.record import RecordStore
from materica.shapes import Suite
from tests.fuzz import seeded_fault
from tests.fuzz.acceptance_oracle import (
    INPUTS,
    METHODS,
    PLACES,
    RECORDS,
    JsonObject,
    Place,
    check_acceptance_laws,
    check_no_better,
    check_shape_refused,
    request_at,
)
from tests.fuzz.field_oracle import check_against_the_model, check_table_member, read_outcome

CASES = (
    Path(__file__).resolve().parents[2] / "src" / "materica" / "data" / "conformance" / "plain_read" / "cases"
)
WITH_HASH: frozenset[Suite] = frozenset({"plain_read", "hash"})
SOURCES = tuple((INPUTS / name).read_bytes() for name in RECORDS)


def store() -> RecordStore:
    found = RecordStore()
    for name, data in zip(RECORDS, SOURCES, strict=True):
        found.add(name, data)
    return found


def field_of(name: str) -> JsonValue:
    found: JsonValue = json.loads((INPUTS / name).read_text(encoding="utf-8"))
    for step in ("body", "sections", "bulk", "fields", "density"):
        assert isinstance(found, dict)
        found = found[step]
    return found


def written(request: JsonObject) -> JsonValue:
    try:
        result = read(request, store(), claims=WITH_HASH)
    except NotImplementedError:
        return "not yet"
    found: JsonValue = json.loads(json.dumps(result.to_json()))
    return found


def check_place(place: Place, entry: JsonValue) -> None:
    """What the target checks at one place, the read made as it makes it."""
    request = request_at(place, [entry])
    first, outcome = read_outcome(partial(read, request, store(), claims=WITH_HASH))
    check_shape_refused(first, entry)
    check_acceptance_laws(first, entry)
    check_table_member(field_of(place.record), first)
    check_no_better(first, written(request_at(place, [])))
    check_against_the_model(SOURCES, request, WITH_HASH, outcome)


def seeds() -> list[JsonValue]:
    """The target's seeds: every acceptance of every conformance case's request, each once."""
    found: list[JsonValue] = []
    for path in sorted(CASES.glob("*.json")):
        case: JsonValue = json.loads(path.read_text(encoding="utf-8"))
        request = case.get("request") if isinstance(case, dict) else None
        acceptances = request.get("acceptances") if isinstance(request, dict) else None
        entries: list[JsonValue] = acceptances if isinstance(acceptances, list) else []
        for entry in entries:
            if entry not in found:
                found.append(entry)
    return found


SEEDS = seeds()


def test_the_seeds_are_many_and_hold_extrapolations_at_both_records() -> None:
    records = [
        entry.get("record")
        for entry in SEEDS
        if isinstance(entry, dict) and entry.get("acceptance") == "extrapolation"
    ]
    hashes = {str(record.get("content_hash")) for record in records if isinstance(record, dict)}
    stated = {json.loads((INPUTS / name).read_text(encoding="utf-8"))["content_hash"] for name in RECORDS}
    assert len(SEEDS) > 100, len(SEEDS)
    assert stated <= hashes, (stated, hashes)


@pytest.mark.parametrize("place", PLACES, ids=lambda place: f"{place.record}-{place.at}-{place.want}")
def test_the_oracles_are_quiet_on_the_core_at_each_place_under_every_seed(place: Place) -> None:
    for entry in SEEDS:
        check_place(place, entry)


def test_the_places_apply_an_extrapolation_at_some_and_refuse_it_at_others() -> None:
    """The target's places tell the extrapolation's rules apart: at the read under `want: value` it applies
    below and above the density table and between the edge table's range and its edge, and nowhere else."""
    applied: list[Place] = []
    for place in PLACES:
        pin = request_at(place, [])["target"]
        assert isinstance(pin, dict)
        entry = {
            "acceptance": "extrapolation",
            "record": pin["record"],
            "field": "bulk.density",
            "method": "constant",
            "law": "the end value",
        }
        result = written(request_at(place, [entry]))
        if isinstance(result, dict) and "assumption" in result:
            applied.append(place)
    assert [(place.record, place.at) for place in applied] == [
        ("density_table.json", 270.0),
        ("density_table.json", 350.0),
        ("density_edge_range_275_283.json", 274.0),
    ]


# Each law broken, on a result an extrapolation covers at 270 K below the density table.
ENTRY: JsonObject = {
    "acceptance": "extrapolation",
    "record": json.loads(json.dumps(request_at(PLACES[0], [])["target"]))["record"],
    "field": "bulk.density",
    "method": "constant",
    "law": "the end value held",
    "basis": "a fixture's",
}


def covered() -> JsonObject:
    found = written(request_at(PLACES[0], [ENTRY]))
    assert isinstance(found, dict)
    assert "assumption" in found
    return found


def changed(change: Callable[[JsonObject], None]) -> JsonObject:
    result = copy.deepcopy(covered())
    change(result)
    return result


def in_the_assumption(name: str, value: JsonValue) -> Callable[[JsonObject], None]:
    def change(result: JsonObject) -> None:
        assumption = result["assumption"]
        assert isinstance(assumption, dict)
        assumption[name] = value

    return change


def in_the_result(name: str, value: JsonValue = None) -> Callable[[JsonObject], None]:
    """`name` set to `value` in the result, or removed from it where `value` is None."""

    def change(result: JsonObject) -> None:
        if value is None:
            del result[name]
        else:
            result[name] = value

    return change


BROKEN: list[tuple[Callable[[JsonObject], None], str]] = [
    (in_the_assumption("law", 1.0), "an assumption whose law is no text"),
    (in_the_assumption("law", ""), "an assumption whose law is no text"),
    (in_the_assumption("basis", "a fixture's"), "an assumption other than the entry's"),
    (in_the_assumption("method", "linear"), "an assumption whose method is none"),
    (in_the_assumption("law", "another law"), "an assumption other than the entry's"),
    (in_the_result("status", "unknown"), "an extrapolation's result unknown"),
    (in_the_result("reasons", []), "an extrapolation's result"),
    (in_the_result("table"), r"an extrapolation's result without \['table'\]"),
    (in_the_result("value"), r"an extrapolation's result without \['value'\]"),
    (in_the_result("assumption", "an extrapolation"), "an assumption that is no object"),
]


@pytest.mark.parametrize(("change", "complaint"), BROKEN)
def test_the_acceptance_laws_see_each_law_broken(
    change: Callable[[JsonObject], None], complaint: str
) -> None:
    check_acceptance_laws(covered(), ENTRY)
    with pytest.raises(AssertionError, match=complaint):
        check_acceptance_laws(changed(change), ENTRY)


def test_the_acceptance_laws_see_an_assumption_where_no_extrapolation_covers_the_read() -> None:
    """An `assumption` stands only beside a read an extrapolation covers, `not_met` with `outside_range` among
    its reasons: one beside a read inside the range, which is not refused, is seen."""
    inside = written(request_at(PLACES[1], [ENTRY]))
    assert isinstance(inside, dict)
    check_acceptance_laws(inside, ENTRY)
    assumption: JsonObject = {
        "acceptance": "extrapolation",
        "method": "constant",
        "law": "the end value held",
    }
    with pytest.raises(AssertionError, match="an extrapolation's result"):
        check_acceptance_laws({**inside, "assumption": assumption}, ENTRY)


def test_no_better_sees_a_status_an_acceptance_makes_better() -> None:
    worse: JsonObject = {"status": "not_met"}
    better: JsonObject = {"status": "met"}
    check_no_better(worse, better)
    check_no_better(worse, worse)
    with pytest.raises(AssertionError, match="an acceptance turned a read not_met into met"):
        check_no_better(better, worse)


@pytest.mark.parametrize("at_the_read", [True, False], ids=["at-the-read", "elsewhere"])
def test_the_oracles_see_the_control_s_seeded_fault(
    at_the_read: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An extrapolation's `method` compared ignoring case, so that `Constant` is taken where step 0 must
    refuse it: the shape's oracle sees the read go on, wherever the extrapolation is located, and so does the
    model."""
    entry: JsonObject = {**ENTRY, "method": "Constant"}
    if not at_the_read:
        entry["region"] = "lumen"
    check_place(PLACES[0], entry)
    monkeypatch.setattr(read_module, "_extrapolation", seeded_fault.faulty_extrapolation)
    with pytest.raises(AssertionError, match="an extrapolation that breaks its shape not refused"):
        check_place(PLACES[0], entry)
    request = request_at(PLACES[0], [entry])
    _, outcome = read_outcome(partial(read, request, store(), claims=WITH_HASH))
    with pytest.raises(AssertionError, match="the implementation gives"):
        check_against_the_model(SOURCES, request, WITH_HASH, outcome)


def test_the_shape_s_oracle_sees_a_law_that_is_no_text_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shape's oracle holds the law too: a number as a `consumer_law`'s law taken is seen."""
    entry = {**ENTRY, "method": "consumer_law", "law": 1.0}
    check_place(PLACES[0], entry)
    extrapolation = read_module._extrapolation  # pyright: ignore[reportPrivateUsage]

    def law_of_any_type(index: int, given: dict[str, JsonValue], found: list[Reason]) -> object:
        return extrapolation(index, {**given, "law": "a number"}, found)

    monkeypatch.setattr(read_module, "_extrapolation", law_of_any_type)
    with pytest.raises(AssertionError, match="an extrapolation that breaks its shape not refused"):
        check_place(PLACES[0], entry)


def test_the_control_s_fault_changes_no_seed() -> None:
    """The fault takes a method one case change from a token: no seed holds one, so the fuzzer has to change a
    letter of one, and each seed holding an extrapolation is that one change away."""
    methods = [
        entry.get("method")
        for entry in SEEDS
        if isinstance(entry, dict) and entry.get("acceptance") == "extrapolation"
    ]
    near = [method for method in methods if isinstance(method, str) and method.lower() in METHODS]
    assert all(method in METHODS for method in near), near
    assert len(near) > 30, len(near)


def test_the_model_oracle_sees_an_extrapolation_applied_under_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A read that applies an extrapolation under `want: bounds`, which the text does not: the model sees
    it."""
    form_range = read_module.form_range

    def under_any_want(table: JsonObject, request: ReadRequest) -> FormRange:
        return form_range(table, dataclasses.replace(request, want="value"))

    place = PLACES[3]
    assert place.want == "bounds"
    request = request_at(place, [ENTRY])
    check_place(place, ENTRY)
    monkeypatch.setattr(read_module, "form_range", under_any_want)
    _, outcome = read_outcome(partial(read, request, store(), claims=WITH_HASH))
    with pytest.raises(AssertionError, match="the implementation gives"):
        check_against_the_model(SOURCES, request, WITH_HASH, outcome)

# SPDX-License-Identifier: Apache-2.0
"""What step 10 must find, written from `read_side_contract.md` section 5 and `declarations.md` section 4.1
alone, never from `core/conditions.py`: the oracle of HP7 and HP9, and of fuzz target 4 at step 10.

Each row of section 5's table is written out as the text gives it, its comparisons on the exact rationals the
doubles are (the "Exactness" paragraph), and the rule for a stated plus or minus after it, row by row. The
conditions checked, the implied conditions that apply and fill, and two that disagree follow the text's
sentences.
"""

import json
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import NamedTuple

from materica.core import jsonio
from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY

JsonObject = dict[str, JsonValue]
Pair = tuple[str, str | None]  # a reason's code and condition

REASONS = json.loads(
    (Path(jsonio.__file__).parents[1] / "schema" / "0.1" / "vocabulary" / "reasons.json").read_text("utf-8")
)
AFTER_STEP_8 = frozenset(
    code for code, row in REASONS["reasons"].items() if row.get("steps") and min(row["steps"]) > 8
)
"""The codes only steps after 8 give, by the reason table: a read that gives no other passed step 8. Here,
since this module imports no strategy, so that fuzz target 4 may read it without a Hypothesis profile."""


def exact(number: JsonValue) -> Fraction:
    assert isinstance(number, float), number
    return Fraction(number)


def ends(value: Mapping[str, JsonValue]) -> tuple[Fraction, Fraction]:
    span = value["range"]
    assert isinstance(span, list | tuple), span
    return exact(span[0]), exact(span[1])


def row_met(record: Mapping[str, JsonValue], operating: Mapping[str, JsonValue], tolerance: Fraction) -> bool:
    """Section 5's four numeric rows, as written."""
    t = tolerance
    if "value" in record and "value" in operating:
        r, v = exact(record["value"]), exact(operating["value"])
        return abs(r - v) <= t
    if "value" in record:
        r = exact(record["value"])
        lo, hi = ends(operating)
        return r - t <= lo and hi <= r + t
    a, b = ends(record)
    if "value" in operating:
        v = exact(operating["value"])
        return a - t <= v <= b + t
    lo, hi = ends(operating)
    return a - t <= lo and hi <= b + t


def bound_met(
    record: Mapping[str, JsonValue], operating: Mapping[str, JsonValue], tolerance: Fraction, u: Fraction
) -> bool:
    """Section 5's "A stated plus or minus", its `bound` item, as written: the row's test for every value
    within u."""
    t = tolerance
    if "value" in record and "value" in operating:
        r, v = exact(record["value"]), exact(operating["value"])
        return abs(r - v) + u <= t
    if "value" in record:
        r = exact(record["value"])
        lo, hi = ends(operating)
        return r + u - t <= lo and hi <= r - u + t
    a, b = ends(record)
    if "value" in operating:
        v = exact(operating["value"])
        return a + u - t <= v <= b - u + t
    lo, hi = ends(operating)
    return a + u - t <= lo and hi <= b - u + t


def numeric_entry(
    record: Mapping[str, JsonValue], operating: Mapping[str, JsonValue], tolerance: JsonValue
) -> tuple[str, str | None]:
    """The status and code of a stated numeric condition with a tolerance."""
    t = exact(tolerance)
    if not row_met(record, operating, t):
        return "not_met", "condition_outside"
    entries = record.get("plus_minus", [])
    assert isinstance(entries, list)
    kinds = [entry for entry in entries if isinstance(entry, dict)]
    bound = [entry for entry in kinds if entry.get("stated_as") == "bound"]
    if bound:
        u = exact(bound[0]["value"])
        return ("met", None) if bound_met(record, operating, t, u) else ("unknown", "condition_uncertain")
    if any(exact(entry["value"]) > 0 for entry in kinds):
        return "unknown", "condition_uncertain"
    return "met", None


class Expected(NamedTuple):
    reasons: frozenset[Pair]
    statuses: dict[str, str] | None  # each condition checked and its entry's status; None where none is
    records: dict[str, JsonValue]  # each entry's `record` where it has one
    applied: frozenset[int]


def states(specimen: Mapping[str, JsonValue], fact: str, token: str) -> bool:
    held = specimen.get(fact)
    return isinstance(held, dict) and "status" not in held and held.get("token") == token


def said(value: Mapping[str, JsonValue]) -> object:
    if "token" in value:
        return ("token", value["token"])
    if "value" in value:
        return ("value", exact(value["value"]))
    return ("range", *ends(value))


class Implied(NamedTuple):
    """An implied condition located at the read: its index, the fact and token it rests on, and its values."""

    position: int
    fact: str
    token: str
    implies: dict[str, JsonObject]


def expected(
    field: str,
    conditions: Mapping[str, JsonValue],
    specimen: Mapping[str, JsonValue],
    operating: Mapping[str, Mapping[str, JsonValue]],
    required: Mapping[str, Mapping[str, JsonValue]],
    implied: Sequence[Implied] = (),
) -> Expected:
    """Step 10 for `field` holding `conditions`, with its merged `specimen`, against the request."""
    applying = [condition for condition in implied if states(specimen, condition.fact, condition.token)]
    supplied: dict[str, set[object]] = {}
    for condition in applying:
        for name, value in condition.implies.items():
            supplied.setdefault(name, set()).add(said(value))
    disagreeing = frozenset(
        (("request_incomplete", name) for name, values in supplied.items() if len(values) > 1)
    )
    if disagreeing:
        return Expected(disagreeing, None, {}, frozenset())
    filled: dict[str, JsonValue] = {}
    applied: set[int] = set()
    for condition in applying:
        for name, value in condition.implies.items():
            stored = conditions.get(name)
            if stored is None or (isinstance(stored, dict) and stored.get("status") == "unstated"):
                filled.setdefault(name, {**value, "basis": "implied"})
                applied.add(condition.position)
    held: dict[str, JsonValue] = {**conditions, **filled}
    checked = list(held)
    checked += VOCABULARY.fields[field].requires
    for name, spec in VOCABULARY.conditions.items():
        for other, tokens in spec.required_with.items():
            other_held = held.get(other)
            if (
                isinstance(other_held, dict)
                and "status" not in other_held
                and other_held.get("token") in tokens
            ):
                checked.append(name)
    checked += list(required)
    reasons: set[Pair] = set()
    statuses: dict[str, str] = {}
    records: dict[str, JsonValue] = {}
    for name in dict.fromkeys(checked):
        code: str | None
        entry = held.get(name)
        if entry is not None and name in VOCABULARY.conditions:
            records[name] = entry
        if name not in VOCABULARY.conditions:
            statuses[name], code = "unknown", "condition_unknown_name"
        elif entry is None or (isinstance(entry, dict) and "status" in entry):
            statuses[name], code = "unknown", "condition_unstated"
        elif name not in required:
            statuses[name], code = "unknown", "condition_unchecked"
        elif "accept" in required[name]:
            accept = required[name]["accept"]
            assert isinstance(entry, dict)
            assert isinstance(accept, list)
            met = entry["token"] in accept
            statuses[name], code = ("met", None) if met else ("not_met", "condition_not_accepted")
        else:
            tolerance = required[name]["tolerance"]
            assert isinstance(entry, dict)
            assert isinstance(tolerance, dict)
            statuses[name], code = numeric_entry(entry, operating[name], tolerance["value"])
        if code is not None:
            reasons.add((code, name))
    return Expected(frozenset(reasons), statuses, records, frozenset(applied))

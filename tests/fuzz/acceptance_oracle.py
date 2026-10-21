# SPDX-License-Identifier: Apache-2.0
"""The oracles by which fuzz target 5 (`read_acceptance_bytes.py`) sees a read under one acceptance go wrong,
apart from the target, which needs Atheris, so that a unit test can show each fails
(`tests/unit/test_acceptance_oracle.py`).

The target reads two tables of the conformance inputs at fixed places, each once with the fuzzed entry as the
request's one acceptance: the density table (`x` from 280 to 340 K, no edge) below, inside and above its
range, and below it under `want: bounds`; and the edge table whose readable range is narrowed to [275, 283] K,
its edge at 273 K outside it, at that edge, beyond it and between it and the range. An extrapolation located
at either record (the seeds pin both) is applied at some places, refused at others, and never applies to the
read of the other record.

Beside the reference model's agreement (`field_oracle.check_against_the_model`), the results are held to the
laws of `read_side_contract.md` section 2 under an acceptance, after section 1's refusal of an extrapolation
that breaks its shape (`check_shape_refused`): HP1 and HP2 where no `assumption` stands
(`field_oracle.check_result_laws`, which no nominal or extrapolation reaches there); and where one stands, the
extrapolation's (section 5): `not_met` the worst of the codes, `outside_range` with the axis among them, the
value with the members beside it and the table it is read from, and the `assumption` the entry's own `method`
and `law`, `basis` aside, its `law` text of at least one character (`declarations.md` section 4.1), since only
an extrapolation that passed step 0 applies. And an acceptance never makes a read's status better than the
same read without it (the S3 design's target 4: no implied condition fills a condition these records leave
unstated, no nominal applies to a table, and an extrapolation keeps `not_met`)."""

import json
from pathlib import Path
from typing import NamedTuple

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from tests.fuzz.field_oracle import check_result_laws, objects
from tests.property.condition_oracle import REASONS

JsonObject = dict[str, JsonValue]
INPUTS = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "materica"
    / "data"
    / "conformance"
    / "plain_read"
    / "inputs"
)
RECORDS = ("density_table.json", "density_edge_range_275_283.json")
FIELD = "bulk.density"
METHODS = VOCABULARY.token_lists["extrapolation_method"]
BEST_FIRST = ("met", "unknown", "not_met")
# The members a result holds beside a value an extrapolation covers (section 2 item 6).
BESIDE_THE_VALUE = ("value", "unit", "conditions", "specimen", "statistics", "provenance", "table")


class Place(NamedTuple):
    record: str  # one of `RECORDS`
    at: float  # the temperature, in K
    want: str


PLACES = (
    Place("density_table.json", 270.0, "value"),
    Place("density_table.json", 310.0, "value"),
    Place("density_table.json", 350.0, "value"),
    Place("density_table.json", 270.0, "bounds"),
    Place("density_edge_range_275_283.json", 273.0, "value"),
    Place("density_edge_range_275_283.json", 268.0, "value"),
    Place("density_edge_range_275_283.json", 274.0, "value"),
)


def record_of(name: str) -> JsonObject:
    found: JsonObject = json.loads((INPUTS / name).read_text(encoding="utf-8"))
    return found


def pin_of(name: str) -> JsonObject:
    record = record_of(name)
    return {member: record[member] for member in ("id", "version", "content_hash")}


def request_at(place: Place, acceptances: list[JsonValue]) -> JsonObject:
    """The request of `place`, its density kind accepted, with `acceptances` where there are any."""
    request: JsonObject = {
        "target": {"record": pin_of(place.record), "field": FIELD},
        "operating_conditions": {"temperature": {"value": place.at, "unit": "K"}},
        "requirement": {"want": place.want, "conditions": {"density_kind": {"accept": ["apparent"]}}},
    }
    if acceptances:
        request["acceptances"] = acceptances
    return request


def breaks_its_shape(entry: JsonValue) -> bool:
    """Whether `entry` is an extrapolation whose own members break its shape (`declarations.md` section 4.1:
    "`method` (`constant` or `consumer_law`), `law` (text of at least one character"), whatever field or
    location it names."""
    if not (isinstance(entry, dict) and entry.get("acceptance") == "extrapolation"):
        return False
    law = entry.get("law")
    return entry.get("method") not in METHODS or not (isinstance(law, str) and law)


def check_shape_refused(result: JsonValue, entry: JsonValue) -> None:
    """`read_side_contract.md` section 1: "An acceptance of any other kind, or one that breaks its shape,
    gives `request_incomplete`", which carries no condition: an extrapolation whose method or law breaks its
    shape refuses the request, wherever it is located."""
    if not breaks_its_shape(entry):
        return
    codes = {(str(reason.get("code")), reason.get("condition")) for reason in objects(result, "reasons")}
    assert isinstance(result, dict), result
    assert result.get("status") == "not_met", f"an extrapolation that breaks its shape not refused: {result}"
    assert ("request_incomplete", None) in codes, (
        f"an extrapolation that breaks its shape not refused: {codes}"
    )


def check_acceptance_laws(result: JsonValue, entry: JsonValue) -> None:
    """HP1 and HP2 under the acceptance `entry`: where no `assumption` stands, as without one; where one
    stands, an extrapolation's covering `outside_range`, as the entry gives it."""
    if result == "not yet":
        return
    assert isinstance(result, dict), result
    if "assumption" not in result:
        check_result_laws(result)
        return
    assumption = result["assumption"]
    assert isinstance(assumption, dict), f"an assumption that is no object: {assumption!r}"
    law = assumption.get("law")
    assert isinstance(law, str), f"an assumption whose law is no text: {law!r}"
    assert law, f"an assumption whose law is no text: {law!r}"
    assert assumption.get("method") in METHODS, f"an assumption whose method is none: {assumption!r}"
    expected = (
        {"acceptance": "extrapolation", "method": entry.get("method"), "law": entry.get("law")}
        if isinstance(entry, dict)
        else None
    )
    assert assumption == expected, f"an assumption other than the entry's: {assumption!r}"
    codes = [(str(reason.get("code")), reason.get("condition")) for reason in objects(result, "reasons")]
    statuses = [str(REASONS["reasons"][code]["status"]) for code, _ in codes if code in REASONS["reasons"]]
    worst = max(statuses, key=BEST_FIRST.index, default="met")
    assert result.get("status") == worst == "not_met", f"an extrapolation's result {result.get('status')}"
    assert ("outside_range", "temperature") in codes, f"an extrapolation with no outside_range: {codes}"
    missing = [member for member in BESIDE_THE_VALUE if member not in result]
    assert not missing, f"an extrapolation's result without {missing}"


def check_no_better(result: JsonValue, without: JsonValue) -> None:
    """The read under the acceptance is no better than the same read without it."""
    if not (isinstance(result, dict) and isinstance(without, dict)):
        return
    given, alone = str(result.get("status")), str(without.get("status"))
    assert BEST_FIRST.index(given) >= BEST_FIRST.index(alone), (
        f"an acceptance turned a read {alone} into {given}"
    )

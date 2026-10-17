# SPDX-License-Identifier: Apache-2.0
"""The oracles by which fuzz target 4 (`read_field_bytes.py`) sees a read go wrong, apart from the target,
which needs Atheris, so that a unit test can show each fails (`tests/unit/test_fuzz_oracle.py`).

The reference model (`tests/reference/read_model.py`) says what each read must give: the target holds every
read to it as HP12 does (`check_against_the_model`), so that a refusal step 8 gives wrongly is seen, which no
other oracle here can see (S2a-2's review, L3). Beside it, the target holds step 8 to T1's third relation
(`tests/spec_sync/test_t1.py`): what the reader `$defs` refuse, step 8 refuses. A constant step 8 passes it
holds to steps 9 and 10 as the text gives them: its units each compared with the one registered for it, code
point for code point, written here from `record_format.md` section 4.2 and step 9; and its conditions against
the request by `condition_oracle.py`, HP7's oracle, written from section 5 alone.
"""

import json
from collections.abc import Callable, Mapping
from urllib.parse import urljoin

from materica.core.jsonio import JsonValue
from materica.core.read import ReadResult
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.property import condition_oracle
from tests.property.condition_oracle import AFTER_STEP_8, REASONS
from tests.property.model_strategies import Example
from tests.property.test_model_properties import (
    OPEN_POINTS,
    Outcome,
    check_outcome,
    request_of,
    targets,
    written_outcome,
)
from tests.reference import read_model
from tests.reference.mutants import MUTANTS
from tests.spec_sync.schemas import BASE, takes, why_refused

JsonObject = dict[str, JsonValue]

CONSTANT = "record.reader.json#/$defs/constant_field"
# jsonschema-rs alone, on every input the target reaches: T1 holds its verdicts on that definition to
# python-jsonschema's (`tests/property/test_validators_agree.py`).
READER_TAKES = takes(CONSTANT)
WHY = why_refused({"$ref": urljoin(BASE, CONSTANT)})

# The operating conditions and the requirement a read gives each condition a field's row may require: a
# tolerance about a seed's usual value, or an accept list of some of the row's tokens.
OPERATING: dict[str, JsonObject] = {
    "temperature": {"value": 310.15, "unit": "K"},
    "shear_rate": {"value": 100.0, "unit": "1/s"},
    "magnetic_flux_density": {"value": 0.0, "unit": "T"},
}
REQUIRED: dict[str, JsonObject] = {
    "temperature": {"tolerance": {"value": 1.0, "unit": "K"}},
    "shear_rate": {"tolerance": {"value": 0.0, "unit": "1/s"}},
    "magnetic_flux_density": {"tolerance": {"value": 1.0, "unit": "T"}},
    "density_kind": {"accept": ["apparent"]},
    "specimen_shape": {"accept": ["sphere", "cylinder"]},
    "test_method": {"accept": ["vibrating_sample_magnetometer", "squid_magnetometer"]},
}


# The codes of steps 12 and 13 a constant's read gives (`read_side_contract.md` section 3), and those of step
# 10. The target's requests want only what plain read gives, so `want_mismatch` comes from step 13 alone.
STEPS_12_AND_13 = frozenset({"stated_without_origin", "want_mismatch"})
STEP_10 = frozenset(code for code, row in REASONS["reasons"].items() if 10 in row.get("steps", []))


def passed_step_8(result: JsonValue) -> bool:
    """Whether a read's result, as the target takes it, is one of a field that passed step 8: "not yet", where
    a step not built yet decides it, or a result whose every reason a later step gives, none included."""
    if result == "not yet":
        return True
    reasons = result.get("reasons") if isinstance(result, dict) else None
    codes = (
        [reason.get("code") for reason in reasons if isinstance(reason, dict)]
        if isinstance(reasons, list)
        else []
    )
    return isinstance(reasons, list) and all(code in AFTER_STEP_8 | STEPS_12_AND_13 for code in codes)


def check_no_refusal_missing(field_name: str, field: JsonValue, result: JsonValue) -> None:
    """A field step 8 lets through (`passed_step_8`), a constant its row allows that holds no alternatives,
    is one the reader `$defs` take."""
    if not (isinstance(field, dict) and passed_step_8(result) and field.get("form") == "constant"):
        return
    if "alternatives" not in field and "constant" in VOCABULARY.fields[field_name].forms:
        assert READER_TAKES(field), f"step 8 passed a constant the reader $defs refuse: {WHY(field)[:1]}"


def same(stored: JsonValue, registered: JsonValue) -> bool:
    """`record_format.md` section 4.2: equal as strings, code point for code point, or, where a status object
    is registered, a status object of its token, whatever its reason."""
    if isinstance(registered, dict):
        return isinstance(stored, dict) and "status" in stored and stored["status"] == registered["status"]
    return isinstance(stored, str) and stored == registered


def units_refused(field_name: str, field: JsonObject) -> frozenset[tuple[str, str | None]]:
    """Step 9's reasons for a field step 8 passed, its own section holding no specimen: the field's unit, each
    known condition's and its plus or minus entries', a token condition's any unit, and each fact's whose row
    fixes one, in the field's specimen and, for a derived value, its inputs'."""
    found: set[tuple[str, str | None]] = set()
    if not same(field["unit"], VOCABULARY.fields[field_name].unit):
        found.add(("unit_mismatch", None))
    conditions = field["conditions"]
    assert isinstance(conditions, dict)
    for name, entry in conditions.items():
        spec = VOCABULARY.conditions.get(name)
        if spec is None or not isinstance(entry, dict) or "status" in entry:
            continue
        entries = entry.get("plus_minus")
        units = (
            [entry.get("unit")] + [item["unit"] for item in entries if isinstance(item, dict)]
            if isinstance(entries, list)
            else [entry.get("unit")]
        )
        if (spec.unit is None and "unit" in entry) or (
            spec.unit is not None and not all(same(unit, spec.unit) for unit in units)
        ):
            found.add(("unit_mismatch", name))
    specimens = [field.get("specimen")]
    provenance = field["provenance"]
    assert isinstance(provenance, dict)
    if provenance.get("origin") == "derived":
        derivation = provenance["derivation"]
        assert isinstance(derivation, dict)
        specimens += [item["specimen"] for item in derivation["input_specimens"] if isinstance(item, dict)]  # type: ignore[union-attr]
    for specimen in specimens:
        for name, fact in specimen.items() if isinstance(specimen, dict) else ():
            unit = VOCABULARY.facts[name].fixed.get("unit") if name in VOCABULARY.facts else None
            if (
                unit is not None
                and isinstance(fact, dict)
                and "status" not in fact
                and not same(fact["unit"], unit)
            ):
                found.add(("unit_mismatch", None))
    return frozenset(found)


def check_steps_9_and_10(
    field_name: str,
    field: JsonValue,
    operating: Mapping[str, JsonObject],
    required: Mapping[str, JsonObject],
    result: JsonValue,
) -> None:
    """A constant step 8 passed, which its row allows and which holds no alternatives, read with
    `operating` and `required`, is refused at step 9 exactly where a unit differs, with each of those reasons
    and no other; else gives step 10's reasons and entries as the oracle does, and is refused there exactly
    where the oracle gives a condition `not_met`; and else goes on to steps 12 and 13, whose reasons alone
    stand beside step 10's."""
    if not (isinstance(field, dict) and passed_step_8(result) and field.get("form") == "constant"):
        return
    if "alternatives" in field or "constant" not in VOCABULARY.fields[field_name].forms:
        return
    pairs = {(str(reason.get("code")), reason.get("condition")) for reason in objects(result, "reasons")}
    units = units_refused(field_name, field)
    if units:
        assert pairs == units, (
            f"step 9 gave {sorted(pairs, key=str)}, where its text gives {sorted(units, key=str)}"
        )
        return
    conditions = field["conditions"]
    specimen = field.get("specimen", {})
    assert isinstance(conditions, dict)
    assert isinstance(specimen, dict)
    expected = condition_oracle.expected(field_name, conditions, specimen, operating, required)
    statuses = expected.statuses or {}
    later = {pair for pair in pairs if pair[0] not in STEP_10}
    assert pairs - later == expected.reasons, (
        f"step 10 gave {sorted(pairs - later, key=str)}, its text {sorted(expected.reasons, key=str)}"
    )
    if "not_met" in statuses.values():
        assert not later, f"a read step 10 refused went on: {sorted(later, key=str)}"
    else:
        assert {code for code, _ in later} <= STEPS_12_AND_13, f"steps 11 to 13 gave {sorted(later, key=str)}"
    entries = objects(result, "conditions")
    assert {entry.get("name"): entry.get("status") for entry in entries} == statuses, entries


# HP1 and HP2 (the S2 design), on any result as the target takes it: section 2 item 2's codes that carry
# `condition` always, and those that may; the codes only steps before 10 give; and the statuses, best first.
WITH_A_CONDITION = frozenset(code for code in REASONS["reasons"] if code.startswith("condition_"))
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
BEFORE_STEP_10 = frozenset(
    code for code, row in REASONS["reasons"].items() if row.get("steps") and max(row["steps"]) < 10
)
BEST_FIRST = ("met", "unknown", "not_met")


def check_result_laws(result: JsonValue) -> None:
    """HP1: each code in the reason table, each `(code, condition)` once, `condition` on every `condition_*`
    reason and on no reason of a code that never concerns one. HP2: the status the worst of the codes'
    statuses, folded here from the table; and the members present as section 2 item 6 says, no declaration
    being in the target's requests: `value`, `specimen`, `statistics` and `provenance` exactly where the
    status is not `not_met` and the result rests on one value, `alternative_values` exactly under `no_pick`,
    `unit` beside either, no `assumption`, and `conditions` beside a value, never under `no_pick` or after a
    refusal before step 10. A form without a statistics block is the target's "not yet" until S2b."""
    if result == "not yet":
        return
    assert isinstance(result, dict), result
    pairs = [(str(reason.get("code")), reason.get("condition")) for reason in objects(result, "reasons")]
    assert len(set(pairs)) == len(pairs), f"a reason twice: {pairs}"
    for code, condition in pairs:
        assert code in REASONS["reasons"], f"{code} is no code of the table"
        if code in WITH_A_CONDITION:
            assert isinstance(condition, str), f"{code} without its condition"
        elif code not in PERHAPS_A_CONDITION:
            assert condition is None, f"{code} with the condition {condition}"
    statuses = [str(REASONS["reasons"][code]["status"]) for code, _ in pairs]
    worst = max(statuses, key=BEST_FIRST.index, default="met")
    assert result.get("status") == worst, f"the status {result.get('status')}, the worst reason's {worst}"
    no_pick = any(code == "no_pick" for code, _ in pairs)
    valued = worst != "not_met" and not no_pick
    assert {"reasons", "labels"} <= result.keys(), result
    for member in ("value", "specimen", "statistics", "provenance"):
        assert (member in result) == valued, f"{member} where the status is {worst}: {result}"
    assert ("alternative_values" in result) == no_pick, (
        f"alternative_values, no_pick being {no_pick}: {result}"
    )
    assert ("unit" in result) == (valued or no_pick), f"unit where the status is {worst}: {result}"
    assert "assumption" not in result, f"an assumption no declaration gives: {result}"
    if valued:
        assert "conditions" in result, f"no conditions beside the value: {result}"
    if no_pick or {code for code, _ in pairs} & BEFORE_STEP_10:
        assert "conditions" not in result, f"conditions after a refusal before step 10: {result}"


def objects(result: JsonValue, member: str) -> list[JsonObject]:
    """The objects of the list `member` of a result as the target takes it, none where it holds none."""
    found = result.get(member) if isinstance(result, dict) else None
    return [item for item in found if isinstance(item, dict)] if isinstance(found, list) else []


# HP12's open point `members_of_the_other_kind` (`test_model_properties.OPEN_POINTS`), its record half: a
# condition the reader knows, in the read field or one of its alternatives, holding a member of the other
# kind's shape. HP12 knows an open point by the plant its draw makes; a fuzzed field carries none, so the
# target knows this one by its shape, as `NOT_BUILT` knows each step not built by what the draw holds. Its
# request half, an implied condition, cannot arise here: the target's requests hold no acceptance.
OTHER_KIND = OPEN_POINTS["members_of_the_other_kind"]


def values_read(example: Example) -> list[JsonObject]:
    """The value objects at the request's field in the records its pin names: the field, or each of its
    alternatives."""
    request = request_of(example)
    target = request.get("target") if isinstance(request, dict) else None
    name = target.get("field") if isinstance(target, dict) else None
    if not isinstance(name, str):
        return []
    section_name, _, field_name = name.partition(".")
    found: list[JsonObject] = []
    for record in targets(example):
        body = record.get("body")
        sections = body.get("sections") if isinstance(body, dict) else None
        section = sections.get(section_name) if isinstance(sections, dict) else None
        fields = section.get("fields") if isinstance(section, dict) else None
        field = fields.get(field_name) if isinstance(fields, dict) else None
        held = field.get("alternatives") if isinstance(field, dict) else None
        found += [value for value in (held if isinstance(held, list) else [field]) if isinstance(value, dict)]
    return found


def holds_the_other_kind(example: Example) -> bool:
    """Whether the read field, or one of its alternatives, holds the open point's shape: a numeric condition
    holding `token`, or a token condition holding a member only a numeric one holds (the model's
    `NUMERIC_CONDITION_ONLY`); a token condition's `unit` has its own rule, step 9's."""
    for value in values_read(example):
        conditions = value.get("conditions")
        for name, condition in conditions.items() if isinstance(conditions, dict) else ():
            row = read_model.CONDITIONS.get(name)
            if row is None or not isinstance(condition, dict):
                continue
            other = ("token",) if row.shape == "numeric" else read_model.NUMERIC_CONDITION_ONLY
            if any(member in condition for member in other):
                return True
    return False


def check_against_the_model(
    sources: tuple[bytes, ...], request: JsonObject, claims: frozenset[Suite], implementation: Outcome
) -> None:
    """HP12 on the target's read, whose outcome the target took once (`read_outcome`): the core and the
    reference model agree, or diverge as a known divergence says (`test_model_properties.py`). Where the read
    field holds open point `members_of_the_other_kind`'s shape (`holds_the_other_kind`), the core is held to
    the model given the implementation's reading of it, the open point's seeded fault, as HP12 holds a draw
    that plants it; and a step not built is still found by `NOT_BUILT`, which a plant would skip."""
    example = Example("fuzzed", sources, json.dumps(request).encode(), claims)
    if not holds_the_other_kind(example):
        check_outcome(example, implementation)
        return
    with MUTANTS[OTHER_KIND.reading].applied():
        check_outcome(example, implementation)


def read_outcome(read: Callable[[], ReadResult]) -> tuple[JsonValue, Outcome]:
    """A read's result as the target takes it, "not yet" where a step not built yet would decide it, and its
    outcome as HP12 compares it; the read made once."""
    try:
        result = read()
    except NotImplementedError as error:
        return "not yet", Outcome("not_yet", why=str(error))
    written: JsonValue = json.loads(json.dumps(result.to_json()))
    return written, written_outcome(written)

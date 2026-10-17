# SPDX-License-Identifier: Apache-2.0
"""The oracles by which fuzz target 4 (`read_field_bytes.py`) sees a read go wrong, apart from the target,
which needs Atheris, so that a unit test can show each fails (`tests/unit/test_fuzz_oracle.py`).

The reference model (`tests/reference/read_model.py`) says what each read must give: the target holds every
read to it as HP12 does (`check_against_the_model`), so that a refusal step 8 gives wrongly is seen, which no
other oracle here can see (S2a-2's review, L3). Beside it, the target holds step 8 to T1's third relation
(`tests/spec_sync/test_t1.py`): what the reader `$defs` refuse, step 8 refuses. A constant, an interval or a
composition step 8 passes it holds to steps 9 and 10 as the text gives them: its units each compared with the
one registered for it, code point for code point, written here from `record_format.md` section 4.2 and step
9; and its conditions against the request by `condition_oracle.py`, HP7's oracle, written from section 5
alone.
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
from tests.property.test_model_properties import Outcome, check_outcome, written_outcome
from tests.spec_sync.schemas import BASE, takes, why_refused

JsonObject = dict[str, JsonValue]

# The forms step 8 reads, each with its reader definition. jsonschema-rs alone, on every input the target
# reaches: T1 holds its verdicts on those definitions to python-jsonschema's
# (`tests/property/test_validators_agree.py`).
READ_FORMS = ("constant", "interval", "composition")
DEFINITIONS = {form: f"record.reader.json#/$defs/{form}_field" for form in READ_FORMS}
READER_TAKES = {form: takes(definition) for form, definition in DEFINITIONS.items()}
WHY = {form: why_refused({"$ref": urljoin(BASE, definition)}) for form, definition in DEFINITIONS.items()}
# What a read of each form wants to get its own member (`read_side_contract.md` section 6).
WANT_OF = {"constant": "value", "interval": "bounds", "composition": "components"}

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


# The codes of steps 12 and 13 a read of those forms gives (`read_side_contract.md` section 3), and those of
# step 10. The target's requests want only what plain read gives, so `want_mismatch` comes from step 13 alone.
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


def read_form(field_name: str, field: JsonValue) -> str | None:
    """The form of `field`, where it is one step 8 reads and its row allows, and it holds no alternatives."""
    form = field.get("form") if isinstance(field, dict) else None
    if not isinstance(form, str) or form not in READ_FORMS or form not in VOCABULARY.fields[field_name].forms:
        return None
    return form if isinstance(field, dict) and "alternatives" not in field else None


def check_no_refusal_missing(field_name: str, field: JsonValue, result: JsonValue) -> None:
    """A field step 8 lets through (`passed_step_8`), of a form it reads and its row allows, holding no
    alternatives, is one the reader `$defs` take."""
    form = read_form(field_name, field)
    if form is not None and passed_step_8(result):
        assert READER_TAKES[form](field), (
            f"step 8 passed a field of form {form} the reader $defs refuse: {WHY[form](field)[:1]}"
        )


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
    """A field step 8 passed, of a form it reads and its row allows, holding no alternatives, read with
    `operating` and `required`, is refused at step 9 exactly where a unit differs, with each of those reasons
    and no other; else gives step 10's reasons and entries as the oracle does, and is refused there exactly
    where the oracle gives a condition `not_met`; and else goes on to steps 12 and 13, whose reasons alone
    stand beside step 10's."""
    if read_form(field_name, field) is None or not passed_step_8(result) or not isinstance(field, dict):
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
    refusal before step 10. Evidence, which holds no statistics block, is the target's "not yet" until
    S2b-2."""
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


def check_against_the_model(
    sources: tuple[bytes, ...], request: JsonObject, claims: frozenset[Suite], implementation: Outcome
) -> None:
    """HP12 on the target's read, whose outcome the target took once (`read_outcome`): the core and the
    reference model agree, or diverge as a known divergence says (`test_model_properties.py`)."""
    check_outcome(Example("fuzzed", sources, json.dumps(request).encode(), claims), implementation)


def read_outcome(read: Callable[[], ReadResult]) -> tuple[JsonValue, Outcome]:
    """A read's result as the target takes it, "not yet" where a step not built yet would decide it, and its
    outcome as HP12 compares it; the read made once."""
    try:
        result = read()
    except NotImplementedError as error:
        return "not yet", Outcome("not_yet", why=str(error))
    written: JsonValue = json.loads(json.dumps(result.to_json()))
    return written, written_outcome(written)

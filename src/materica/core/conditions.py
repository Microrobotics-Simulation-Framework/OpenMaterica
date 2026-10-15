# SPDX-License-Identifier: Apache-2.0
"""Step 10 of a read: the conditions (`read_side_contract.md` section 3, step 10, and section 5).

The conditions checked are those the record holds, those the field's row requires, those another condition
requires with the token it holds, and those the request's requirement names, each giving one entry of the
result's `conditions`. A condition the record states is compared with the request by section 5's table,
every comparison made on the exact values of the doubles, as rationals, so that no rounding of `r - v` passes
a value outside its tolerance; a stated `plus_minus` can only turn `met` into `unknown`.
"""

import copy
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import TypeGuard, get_type_hints

from materica import shapes
from materica.core.fields import RecordField
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.status import ReadStatus
from materica.core.value_shapes import JsonObject, is_status_object, status_row
from materica.core.vocabulary import VOCABULARY


@dataclass(frozen=True)
class ConditionEntry:
    """An entry of a result's `conditions` (`read_side_contract.md` section 2 item 6): its `record` is the
    record's entry, holding the members the reader knows, as stored; its `operating`, the request's operating
    condition. Either is None where there is none."""

    name: str
    status: ReadStatus
    record: JsonObject | None = None
    operating: shapes.OperatingCondition | None = None

    @classmethod
    def from_json(cls, entry: JsonObject) -> "ConditionEntry":
        name, status, record = entry["name"], entry["status"], entry.get("record")
        if not (isinstance(name, str) and isinstance(status, str) and status in _STATUSES):
            raise ValueError(f"not a condition entry: {entry!r}")
        if record is not None and not isinstance(record, dict):
            raise ValueError(f"not a condition entry's record: {record!r}")
        operating = entry.get("operating")
        return cls(name, _STATUSES[status], record, None if operating is None else _operating(operating))

    def to_json(self) -> JsonObject:
        entry: JsonObject = {"name": self.name, "status": self.status}
        if self.record is not None:
            entry["record"] = copy.deepcopy(self.record)
        if self.operating is not None:
            entry["operating"] = _operating_json(self.operating)
        return entry


@dataclass(frozen=True)
class ConditionsRead:
    """What step 10 found: its reasons, and the entries of the result's `conditions`."""

    reasons: tuple[Reason, ...]
    entries: tuple[ConditionEntry, ...]


def check_conditions(
    field: RecordField,
    operating: Mapping[str, shapes.OperatingCondition],
    required: Mapping[str, shapes.RequirementCondition],
) -> ConditionsRead:
    """Step 10 for `field`, which passed steps 8 and 9, against the request's operating conditions and the
    conditions its requirement names (step 0 gives a tolerance only with an operating condition)."""
    held = _object(_object(field.value)["conditions"])
    reasons: list[Reason] = []
    entries = tuple(
        _entry(name, held.get(name), operating.get(name), required.get(name), reasons)
        for name in _checked(held, field.spec.requires, required)
    )
    return ConditionsRead(tuple(reasons), entries)


def _token(entry: JsonValue | None) -> JsonValue:
    return entry.get("token") if isinstance(entry, dict) and not is_status_object(entry) else None


def _checked(held: JsonObject, requires: Collection[str], required: Mapping[str, object]) -> list[str]:
    """The names of the conditions checked, each once: those the record holds; those the row requires; those
    another condition requires with the token it holds (`provenance.md` section 6.1 item 9); and those the
    request's requirement names."""
    with_tokens = [
        spec.name
        for spec in VOCABULARY.conditions.values()
        for other, tokens in spec.required_with.items()
        if _token(held.get(other)) in tokens
    ]
    return list(dict.fromkeys([*held, *requires, *with_tokens, *required]))


def _entry(
    name: str,
    held: JsonValue | None,
    operating: shapes.OperatingCondition | None,
    required: shapes.RequirementCondition | None,
    reasons: list[Reason],
) -> ConditionEntry:
    """The entry of the condition `name` by section 5's table, its reason, if any, appended to `reasons`."""
    if name not in VOCABULARY.conditions:
        reasons.append(
            Reason("condition_unknown_name", name, f"{name} is a condition the reader does not know")
        )
        return ConditionEntry(name, "unknown")
    record = None if held is None else _as_read(name, _object(held))
    if held is None or is_status_object(held):
        reasons.append(Reason("condition_unstated", name, f"the source does not state {name}"))
        return ConditionEntry(name, "unknown", record, operating)
    found = _compared(name, _object(held), operating, required)
    if found is None:
        return ConditionEntry(name, "met", record, operating)
    reasons.append(found)
    return ConditionEntry(name, VOCABULARY.reasons[found.code].status, record, operating)


def _compared(
    name: str,
    condition: JsonObject,
    operating: shapes.OperatingCondition | None,
    required: shapes.RequirementCondition | None,
) -> Reason | None:
    """The reason a stated condition is not `met` against the request, or None where it is."""
    if required is None:
        return Reason("condition_unchecked", name, f"the request gives {name} no tolerance or accept list")
    if _accepts(required):
        if condition["token"] in required["accept"]:
            return None
        return Reason("condition_not_accepted", name, f"{name}'s token is not in the accept list")
    if operating is None or not _tolerates(required):
        raise ValueError("step 0 lets through no tolerance without its operating condition")
    tolerance = required["tolerance"]["value"]
    if not _within(condition, operating, tolerance, 0.0):
        return Reason("condition_outside", name, f"{name} is outside the tolerance")
    stated = [_object(entry) for entry in _list(condition.get("plus_minus", []))]
    bounds = [_number(entry["value"]) for entry in stated if entry["stated_as"] == "bound"]
    if bounds:
        assured = _within(condition, operating, tolerance, bounds[0])
    else:
        assured = not any(_number(entry["value"]) > 0 for entry in stated)
    if assured:
        return None
    return Reason(
        "condition_uncertain", name, f"{name}'s stated plus or minus leaves the tolerance unassured"
    )


def _within(
    condition: JsonObject, operating: shapes.OperatingCondition, tolerance: float, bound: float
) -> bool:
    """Whether every value within `bound` of the stated value or range lies within `tolerance` of the
    operating value or range, exactly. A value `r` is the range `[r, r]`, and so is an operating value, so
    that section 5's four rows, and its `plus_minus` rule, are one test: `a + u - t <= lo` and
    `hi <= b - u + t`."""
    a, b = (Fraction(end) for end in _stated_ends(condition))
    lo, hi = (Fraction(end) for end in _operating_ends(operating))
    slack = Fraction(tolerance) - Fraction(bound)
    return a - slack <= lo and hi <= b + slack


def _stated_ends(condition: JsonObject) -> tuple[float, float]:
    if "value" in condition:
        return _number(condition["value"]), _number(condition["value"])
    return _pair(condition["range"])


def _operating_ends(operating: shapes.OperatingCondition) -> tuple[float, float]:
    if _is_value(operating):
        return operating["value"], operating["value"]
    if _is_range(operating):
        return operating["range"]
    raise TypeError("step 0 lets through no operating condition but a value or a range")


# Which of their shapes a requirement's condition and an operating condition hold, step 0 having checked them.


def _accepts(required: shapes.RequirementCondition) -> TypeGuard[shapes.AcceptRequirement]:
    return "accept" in required


def _tolerates(required: shapes.RequirementCondition) -> TypeGuard[shapes.ToleranceRequirement]:
    return "tolerance" in required


def _is_value(operating: shapes.OperatingCondition) -> TypeGuard[shapes.OperatingValue]:
    return "value" in operating


def _is_range(operating: shapes.OperatingCondition) -> TypeGuard[shapes.OperatingRange]:
    return "range" in operating


# What a result returns of a record's condition: the members the reader's version defines, as stored
# (`read_side_contract.md` section 2 item 5), as the writer schema's shapes give them.
_STATUS_MEMBERS = tuple(get_type_hints(shapes.StatusObject))
_PLUS_MINUS_MEMBERS = tuple(get_type_hints(shapes.PlusMinusEntry))
_STATUSES: dict[str, ReadStatus] = {"met": "met", "not_met": "not_met", "unknown": "unknown"}


def _as_read(name: str, condition: JsonObject) -> JsonObject:
    if is_status_object(condition):
        return _known(condition, _STATUS_MEMBERS)
    found = _known(condition, status_row(shapes.Conditions, name)[1])
    if "plus_minus" in found:
        found["plus_minus"] = [_plus_minus_entry(_object(entry)) for entry in _list(found["plus_minus"])]
    return found


def _plus_minus_entry(entry: JsonObject) -> JsonValue:
    found = _known(entry, _PLUS_MINUS_MEMBERS)
    if is_status_object(found["stated_as"]):
        found["stated_as"] = _known(_object(found["stated_as"]), _STATUS_MEMBERS)
    return found


def _known(value: JsonObject, members: Collection[str]) -> JsonObject:
    return {name: copy.deepcopy(member) for name, member in value.items() if name in members}


def _operating(value: JsonValue) -> shapes.OperatingCondition:
    entry = _object(value)
    unit = entry["unit"]
    if not isinstance(unit, str):
        raise ValueError(f"not an operating condition: {entry!r}")
    if "value" in entry:
        return {"value": _number(entry["value"]), "unit": unit}
    return {"range": _pair(entry["range"]), "unit": unit}


def _operating_json(operating: shapes.OperatingCondition) -> JsonObject:
    if _is_value(operating):
        return {"value": operating["value"], "unit": operating["unit"]}
    lo, hi = _operating_ends(operating)
    return {"range": [lo, hi], "unit": operating["unit"]}


def _object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"step 8 lets through no {type(value).__name__} here")
    return value


def _list(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError(f"step 8 lets through no {type(value).__name__} here")
    return value


def _number(value: object) -> float:
    if not isinstance(value, float):
        raise TypeError(f"step 8 lets through no {type(value).__name__} here")
    return value


def _pair(value: object) -> tuple[float, float]:
    match value:
        case [float() as lo, float() as hi]:
            return lo, hi
        case _:
            raise TypeError(f"steps 0 and 8 let through no {type(value).__name__} here")

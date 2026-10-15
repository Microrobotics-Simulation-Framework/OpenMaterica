# SPDX-License-Identifier: Apache-2.0
"""A read of one field of one record (`read_side_contract.md` sections 1 to 3).

`read` checks the request on its own (step 0), resolves its target (steps 1 to 5, `resolve.resolve_record`),
finds the field (step 7, `fields.find_field`), checks its form and shape (step 8, `fields.form_problems`),
its units (step 9, `fields.unit_problems`) and its conditions (step 10, `conditions.check_conditions`), and
gives a `ReadResult`. Steps 11 to 13, which read the field's value, are not built yet, nor are overlays (step
6) and alternatives (step 7). A read that would need one raises `NotImplementedError`, and so does a request
whose answer a check still to come could change, whatever else is wrong with it: one with a region target or
acceptances. It raises rather than give an answer a later step would contradict.
"""

import json
from collections.abc import Collection
from dataclasses import dataclass
from typing import get_args

from materica import shapes
from materica.core import jsonio
from materica.core.conditions import ConditionEntry, check_conditions
from materica.core.fields import find_field, form_problems, unit_problems
from materica.core.identifiers import FIELD, MaterialRef
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason, merged
from materica.core.record import RecordStore
from materica.core.resolve import Refused, ResolvedRecord, resolve_record
from materica.core.slips import slipped
from materica.core.status import ReadStatus, worst
from materica.core.vocabulary import VOCABULARY, ConditionSpec
from materica.shapes import Suite, Want

# A request as JSON text, or as a value already read. A `str` is always text, as a JSON string is never a
# request.
RequestInput = str | bytes | bytearray | memoryview | JsonValue | shapes.ReadRequest

CLAIMS: frozenset[Suite] = frozenset({"plain_read", "hash"})
"""The suites a read claims unless told otherwise (README, "Suites and case numbers")."""

SUITES: frozenset[str] = frozenset(get_args(Suite))
_WANTS: dict[str, Want] = {want: want for want in get_args(Want)}
# The `want`s of section 6 that belong to a suite other than plain read.
_WANT_SUITES: dict[Want, Suite] = {
    "reference_data": "fits_and_reference_data",
    "fit": "fits_and_reference_data",
    "coverage": "fits_and_reference_data",
}
# The members section 1 names at each place of a request, those it refuses included: a member one slip from
# one of them is refused too, so that a misspelt member never drops what it holds.
_REQUEST_MEMBERS = ("records", "target", "operating_conditions", "requirement", "acceptances")
_TARGET_MEMBERS = ("record", "region", "field")
_RECORD_MEMBERS = ("id", "version", "content_hash")
_REQUIREMENT_MEMBERS = ("want", "conditions", "label", "represents", "population_level")
_OPERATING_MEMBERS = ("value", "range", "unit")
_REQUIREMENT_CONDITION_MEMBERS = ("tolerance", "accept")
_TOLERANCE_MEMBERS = ("value", "unit")
# What a declaration's requirement holds and a read checks none of (`declarations.md` section 1).
_DECLARATIONS_ONLY = ("label", "represents", "population_level")


@dataclass(frozen=True)
class ReadRequest:
    """A request that passed step 0, holding the members its shape names and no others (section 1)."""

    target: MaterialRef  # a region target arrives with scenes
    field: str
    want: Want
    operating_conditions: dict[str, shapes.OperatingCondition]
    conditions: dict[str, shapes.RequirementCondition]

    @classmethod
    def from_json(
        cls, request: RequestInput, claims: Collection[Suite] = CLAIMS
    ) -> "ReadRequest | tuple[Reason, ...]":
        """Step 0: the request, or every reason found against it, each code and condition once.

        `request` is JSON text, read by `record_format.md` section 1 item 6, as a `str` or bytes-like; any
        other value is read as the JSON text `json.dumps` writes of it. A request with acceptances or a region
        target raises `NotImplementedError`, and claims no reader makes raise `ValueError`, as in `read`.
        """
        _check(claims)
        value = _parsed(request)
        if isinstance(value, Reason):
            return (Reason("request_incomplete", detail=f"the request is not valid JSON: {value.detail}"),)
        if not isinstance(value, dict):
            return (Reason("request_incomplete", detail="the request is not an object"),)
        acceptances = value.get("acceptances", [])
        if isinstance(acceptances, list) and acceptances:
            raise NotImplementedError("a request's acceptances are not read yet")
        named = value.get("target")
        if isinstance(named, dict) and "region" in named:
            raise NotImplementedError("a region target resolves through a scene, which is not read yet")
        found: list[Reason] = []
        _slips(value, _REQUEST_MEMBERS, "the request", found)
        if not isinstance(acceptances, list):
            found.append(_incomplete("acceptances is not a list"))
        target = _target(named, found)
        requirement = _member(value, "requirement", found, required=True)
        _slips(requirement, _REQUIREMENT_MEMBERS, "requirement", found)
        for name in _DECLARATIONS_ONLY:
            if name in requirement:
                found.append(
                    _incomplete(f"requirement holds {name}, a declaration's, which a read never checks")
                )
        want = _want(requirement.get("want"), claims, found)
        operating = _member(value, "operating_conditions", found)
        conditions = _member(requirement, "conditions", found)
        checked_operating = {
            name: checked
            for name, entry in operating.items()
            if (checked := _operating_condition(name, entry, found)) is not None
        }
        checked_conditions = {
            name: required
            for name, entry in conditions.items()
            if (required := _requirement_condition(name, entry, name in operating, found)) is not None
        }
        if found or target is None or want is None:
            return merged(found)
        return cls(target[0], target[1], want, checked_operating, checked_conditions)

    def to_json(self) -> shapes.ReadRequest:
        target: shapes.Target = {"record": self.target.to_json(), "field": self.field}
        requirement: shapes.Requirement = {"want": self.want}
        if self.conditions:
            requirement["conditions"] = dict(self.conditions)
        request: shapes.ReadRequest = {"target": target, "requirement": requirement}
        if self.operating_conditions:
            request["operating_conditions"] = dict(self.operating_conditions)
        return request


@dataclass(frozen=True)
class ReadResult:
    """A read's result (section 2): its status, every reason found, its labels, and `conditions` once step 10
    has run to its end (item 6). The members that carry a value arrive with the steps that read one."""

    status: ReadStatus
    reasons: tuple[Reason, ...]
    labels: tuple[str, ...] = ()
    conditions: tuple[ConditionEntry, ...] | None = None

    @classmethod
    def from_json(cls, result: shapes.ReadResult) -> "ReadResult":
        reasons = tuple(Reason.from_json(reason) for reason in result["reasons"])
        conditions = result.get("conditions")
        return cls(
            result["status"],
            reasons,
            tuple(result.get("labels", [])),
            None if conditions is None else tuple(ConditionEntry.from_json(entry) for entry in conditions),
        )

    def to_json(self) -> shapes.ReadResult:
        reasons = [reason.to_json() for reason in self.reasons]
        if self.conditions is None:
            return {"status": self.status, "reasons": reasons, "labels": list(self.labels)}
        conditions = [entry.to_json() for entry in self.conditions]
        return {
            "status": self.status,
            "reasons": reasons,
            "conditions": conditions,
            "labels": list(self.labels),
        }


def read(request: RequestInput, store: RecordStore, *, claims: Collection[Suite] = CLAIMS) -> ReadResult:
    """Read the field `request` names among the records in `store`, as a reader that claims `claims`.

    It never raises for anything a request or a record holds (section 2 item 1). It raises `ValueError` for
    claims no reader makes: a suite not in the README's list, or claims without plain read, which every reader
    claims (README, "Suites and case numbers"); and `NotImplementedError` where a step not built yet decides
    the answer.
    """
    checked = ReadRequest.from_json(request, claims)
    if isinstance(checked, tuple):
        return _refused(checked)
    resolved = resolve_record(checked.target, store, claims)
    if isinstance(resolved, Refused):
        return _refused(resolved.reasons, resolved.labels)
    return _read_field(checked, resolved, claims)


def _read_field(request: ReadRequest, resolved: ResolvedRecord, claims: Collection[Suite]) -> ReadResult:
    """Steps 6 to 13, for a target that passed steps 1 to 5. Step 6 applies the overlays a request's
    acceptances name, and step 0 raised for any acceptance, so it has none to apply."""
    record = resolved.record.value
    if record["record_type"] != "material":
        raise NotImplementedError("a read whose target is an overlay is not built yet")
    field = find_field(record, VOCABULARY.fields[request.field])
    if isinstance(field, Reason):
        return _refused((field,), resolved.labels)
    if isinstance(field.value, dict) and "alternatives" in field.value:
        raise NotImplementedError("a field holding alternatives is read at step 7, which is not built yet")
    found = form_problems(field, record, claims)
    if _ends(found):
        return _refused(merged(found), resolved.labels)
    found += unit_problems(field)
    if _ends(found):
        return _refused(merged(found), resolved.labels)
    checked = check_conditions(field, request.operating_conditions, request.conditions)
    found += checked.reasons
    if _ends(found):
        reasons = merged(found)
        return ReadResult(_status(reasons), reasons, resolved.labels, checked.entries)
    raise NotImplementedError("steps 11 to 13, which read the field's value, are not built yet")


def _ends(found: list[Reason]) -> bool:
    """Whether the reasons a read has found end it: a step that gives `not_met` does (section 3)."""
    return _status(found) == "not_met"


def _check(claims: Collection[Suite]) -> None:
    if not set(claims) <= SUITES:
        raise ValueError(f"not suites: {sorted(set(claims) - SUITES)}")
    if "plain_read" not in claims:
        raise ValueError("every reader claims plain_read")


def _parsed(request: RequestInput) -> JsonValue | Reason:
    if isinstance(request, str):
        # A lone surrogate stays in the bytes as invalid UTF-8, which the reader refuses, rather than raise.
        return jsonio.parse(request.encode("utf-8", "surrogatepass"))
    if isinstance(request, bytes | bytearray | memoryview):
        return jsonio.parse(bytes(request))
    try:
        return jsonio.parse(json.dumps(request, allow_nan=False).encode())
    except (TypeError, ValueError, RecursionError) as error:
        return Reason("malformed", detail=str(error))


def _refused(reasons: tuple[Reason, ...], labels: tuple[str, ...] = ()) -> ReadResult:
    return ReadResult(_status(reasons), reasons, labels)


def _status(reasons: Collection[Reason]) -> ReadStatus:
    return worst(VOCABULARY.reasons[reason.code].status for reason in reasons)


def _incomplete(detail: str, condition: str | None = None) -> Reason:
    return Reason("request_incomplete", condition, detail)


def _slips(
    value: dict[str, JsonValue],
    named: Collection[str],
    where: str,
    found: list[Reason],
    condition: str | None = None,
) -> None:
    for member, name in slipped(value, named):
        found.append(_incomplete(f"{where} holds {member!r}, one slip from {name!r}", condition))


def _member(
    value: dict[str, JsonValue], name: str, found: list[Reason], *, required: bool = False
) -> dict[str, JsonValue]:
    """`value[name]`, an object; an empty one, with a reason where the shape calls for one, if it is not."""
    member = value.get(name, None if required else {})
    if isinstance(member, dict):
        return member
    found.append(_incomplete(f"{name} is {'missing or ' if required else ''}not an object"))
    return {}


def _target(value: JsonValue, found: list[Reason]) -> tuple[MaterialRef, str] | None:
    """The target's record and field. A target that names a region raised before this."""
    if not isinstance(value, dict):
        found.append(_incomplete("target is missing or not an object"))
        return None
    _slips(value, _TARGET_MEMBERS, "target", found)
    field = value.get("field")
    if not (isinstance(field, str) and FIELD.fullmatch(field)):
        found.append(_incomplete(f"target.field is not <section>.<field>: {field!r}"))
    elif field not in VOCABULARY.fields:
        found.append(
            _incomplete(f"target.field {field} is not registered: this reader's version does not know it")
        )
    if "record" not in value:
        found.append(_incomplete("target names neither record nor region"))
        return None
    record = value["record"]
    if not isinstance(record, dict):
        record = {}
    _slips(record, _RECORD_MEMBERS, "target.record", found)
    id_, version, pin = record.get("id"), record.get("version"), record.get("content_hash")
    if not (isinstance(id_, str) and isinstance(version, str) and isinstance(pin, str)):
        found.append(_incomplete("target.record is not an object with string id, version and content_hash"))
        return None
    return (MaterialRef(id_, version, pin), field) if isinstance(field, str) else None


def _want(value: JsonValue, claims: Collection[Suite], found: list[Reason]) -> Want | None:
    want = _WANTS.get(value) if isinstance(value, str) else None
    if want is None:
        found.append(_incomplete(f"requirement.want is not a token of section 6: {value!r}"))
    elif (suite := _WANT_SUITES.get(want, "plain_read")) not in claims:
        found.append(Reason("want_mismatch", detail=f"want {want} belongs to the suite {suite}"))
    return want


def _registered(name: str, found: list[Reason]) -> ConditionSpec | None:
    spec = VOCABULARY.conditions.get(name)
    if spec is None:
        found.append(_incomplete(f"{name} is not a registered condition", name))
    return spec


def _unit(spec: ConditionSpec, entry: dict[str, JsonValue], where: str, found: list[Reason]) -> str | None:
    """The entry's unit, where it is a string; one other than the registered unit is a mismatch, whatever else
    is wrong with the entry, compared code point for code point."""
    unit = entry.get("unit")
    if not isinstance(unit, str):
        found.append(_incomplete(f"{where}.unit is missing or not a string", spec.name))
        return None
    if unit != spec.unit:
        found.append(
            Reason("request_unit_mismatch", spec.name, f"{where}.unit {unit!a} is not {spec.unit!a}")
        )
        return None
    return unit


def _operating_condition(
    name: str, entry: JsonValue, found: list[Reason]
) -> shapes.OperatingCondition | None:
    spec = _registered(name, found)
    if spec is None:
        return None
    where = f"operating_conditions.{name}"
    if spec.shape == "token" or not isinstance(entry, dict):
        found.append(_incomplete(f"{where} is not a numeric condition's value or range", name))
        return None
    _slips(entry, _OPERATING_MEMBERS, where, found, name)
    unit = _unit(spec, entry, where, found)
    if ("value" in entry) == ("range" in entry):
        found.append(_incomplete(f"{where} gives both or neither of value and range", name))
        return None
    if "value" in entry:
        value = entry["value"]
        if not isinstance(value, float):
            found.append(_incomplete(f"{where}.value is not a number", name))
            return None
        return None if unit is None else {"value": value, "unit": unit}
    bounds = entry["range"]
    lo, hi = bounds if isinstance(bounds, list) and len(bounds) == 2 else (None, None)
    if not (isinstance(lo, float) and isinstance(hi, float)):
        found.append(_incomplete(f"{where}.range is not two numbers", name))
        return None
    if lo > hi:
        found.append(_incomplete(f"{where}.range has lo above hi", name))
        return None
    return None if unit is None else {"range": (lo, hi), "unit": unit}


def _requirement_condition(
    name: str, entry: JsonValue, operated: bool, found: list[Reason]
) -> shapes.RequirementCondition | None:
    spec = _registered(name, found)
    if spec is None:
        return None
    where = f"requirement.conditions.{name}"
    if not isinstance(entry, dict):
        found.append(_incomplete(f"{where} is not an object", name))
        return None
    _slips(entry, _REQUIREMENT_CONDITION_MEMBERS, where, found, name)
    if spec.shape == "token":
        accept = entry.get("accept")
        if "tolerance" in entry:
            found.append(_incomplete(f"{where} gives a tolerance for a token condition", name))
        if not (isinstance(accept, list) and all(isinstance(token, str) for token in accept)):
            found.append(_incomplete(f"{where}.accept is missing or not a list of strings", name))
        elif "tolerance" not in entry:
            return {"accept": [str(token) for token in accept]}
        return None
    tolerance = entry.get("tolerance")
    if "accept" in entry:
        found.append(_incomplete(f"{where} gives an accept list for a numeric condition", name))
    if not operated:
        found.append(_incomplete(f"{where} gives a tolerance with no operating condition", name))
    if not isinstance(tolerance, dict):
        found.append(_incomplete(f"{where}.tolerance is missing or not an object", name))
        return None
    _slips(tolerance, _TOLERANCE_MEMBERS, f"{where}.tolerance", found, name)
    unit = _unit(spec, tolerance, f"{where}.tolerance", found)
    value = tolerance.get("value")
    if not isinstance(value, float):
        found.append(_incomplete(f"{where}.tolerance.value is not a number", name))
    elif value < 0:
        found.append(_incomplete(f"{where}.tolerance.value is below zero", name))
    elif unit is not None and operated and "accept" not in entry:
        return {"tolerance": {"value": value, "unit": unit}}
    return None

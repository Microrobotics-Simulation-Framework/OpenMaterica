# SPDX-License-Identifier: Apache-2.0
"""A read of one field of one record (`read_side_contract.md` sections 1 to 3).

`read` checks the request on its own (step 0), resolves its target (steps 1 to 5, `resolve.resolve_record`),
finds the field (step 7, `fields.find_field`), and reads it (`read_value_field`): its form and shape (step 8,
`fields.form_problems`), its units (step 9, `fields.unit_problems`), its conditions (step 10,
`conditions.check_conditions`), its range (step 11), its origin and labels (step 12) and its value by `want`
(step 13), and gives a `ReadResult`. A field holding alternatives is read at step 7, each alternative as a
field, as far as S4's decision 12 lets S2 go: the list's shape, a fault of the request inside one alternative,
and `no_pick` or `want_mismatch` where no alternative has a reason of its own.

Of a request's acceptances, a read applies the two S2 builds (`declarations.md` section 4.1): an implied
condition at step 10, and a nominal at step 13, which supplies the value of an interval under `want: value`.
Step 0 refuses an acceptance of a kind a read does not take.

Overlays (step 6), picks, the rest of step 7 over alternatives, and a table are not built yet. A read that
would need one raises `NotImplementedError`, and so does a request whose answer a check still to come could
change, whatever else is wrong with it: one with a region target, or a pick, an overlay or an extrapolation
among its acceptances. It raises rather than give an answer a later step would contradict.

A result returns from a record the members the reader's version defines, each as stored and copied (section 2
item 5; the code design's rule 6): which members those are is read from the generated shapes, so that a
member the writer schema does not define is left out at every depth.
"""

import copy
import dataclasses
import json
import types
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from functools import cache
from typing import Union, cast, get_args, get_origin, get_type_hints, is_typeddict

from materica import shapes
from materica.core import jsonio
from materica.core.conditions import (
    ConditionEntry,
    ImpliedCondition,
    check_conditions,
    located_at,
    operating_json,
)
from materica.core.fields import (
    FIELD_SHAPES,
    RecordField,
    alternatives_problems,
    find_field,
    form_problems,
    unit_problems,
)
from materica.core.identifiers import FIELD, MaterialRef
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason, merged
from materica.core.record import RecordStore
from materica.core.resolve import Refused, ResolvedRecord, resolve_record
from materica.core.slips import slipped
from materica.core.status import ReadStatus, worst
from materica.core.value_shapes import FORM_MEMBERS, JsonObject, a_list, an_object
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
# The members section 1 or `declarations.md` names at each place of a request, those it refuses included: a
# member one slip from one of them is refused too, so that a misspelt member never drops what it holds. A
# declaration's requirement names its `field`, and each of its conditions a `reason` and a `consequence`
# (`declarations.md` section 1), which a read ignores.
_REQUEST_MEMBERS = ("records", "target", "operating_conditions", "requirement", "acceptances")
_TARGET_MEMBERS = ("record", "region", "field")
_RECORD_MEMBERS = ("id", "version", "content_hash")
_REQUIREMENT_MEMBERS = ("want", "conditions", "label", "represents", "population_level", "field")
_OPERATING_MEMBERS = ("value", "range", "unit")
_REQUIREMENT_CONDITION_MEMBERS = ("tolerance", "accept", "reason", "consequence")
_TOLERANCE_MEMBERS = ("value", "unit")
# What a declaration's requirement holds and a read checks none of (`declarations.md` section 1).
_DECLARATIONS_ONLY = ("label", "represents", "population_level")
# The members named at an implied condition's place (`declarations.md` section 4.1): every acceptance's
# kind, location, field and reason, the basis a read ignores (section 1), and its own; and at a condition's
# place in its `implies`, those of a record condition's shapes of either kind (`provenance.md` section 6.1),
# the `basis` and `inferred_from` a read ignores among them, and those an implied value may not hold, which
# are refused: a status object's, its `reason` ignored, `plus_minus`, `set_or_measured`, and those of the
# other kind of condition's shape, a `token` for a numeric condition and a `value`, `range` or `unit` for a
# token one (`read_side_contract.md` section 1).
_IMPLIED_CONDITION = "implied_condition"
_IMPLIED_MEMBERS = ("acceptance", "record", "region", "interval", "field", "reason", "basis", "fact", "token")
_IMPLIED_OWN = (*_IMPLIED_MEMBERS, "implies")
_LOCATION_MEMBERS = ("record", "region", "interval")
_IMPLIED_IGNORED = ("basis", "inferred_from", "reason")
_IMPLIED_REFUSED = ("plus_minus", "set_or_measured", "status")
_OF_THE_OTHER_KIND: dict[str, tuple[str, ...]] = {"numeric": ("token",), "token": _OPERATING_MEMBERS}
# The members a review names, a status object's included (`provenance.md` section 2 item 6), and a statistics
# block's counts (section 3, step 8), which a result writes as integers.
_REVIEW_DEFINES = tuple(get_type_hints(shapes.Review))
_REVIEW_MEMBERS = (*_REVIEW_DEFINES, *get_type_hints(shapes.StatusObject))
_COUNTS = ("n_specimens", "n_donors", "n_sources")
# What step 13 gives of each form step 8 reads, by `want` (section 6): its own member, as stored.
_WANT_OF_FORM: dict[str, Want] = {
    "constant": "value",
    "interval": "bounds",
    "composition": "components",
    "evidence": "evidence",
}
# The shape of each member of a field of each form step 8 reads, by name.
_FIELD_HINTS = {form: get_type_hints(shape) for form, shape in FIELD_SHAPES.items()}
# The kinds of acceptance a read takes but S2 does not apply (section 1): an extrapolation (S3), a pick and an
# overlay (S4). A request holding one raises, whatever else it holds.
_APPLIED_LATER = ("pick", "overlay", "extrapolation")
# The members named at a nominal's place (`declarations.md` section 4.1): every acceptance's kind, location,
# field, reason and basis, the last two of which a read ignores; its `value`; and `params`, which a parameter
# set's nominal holds in place of a value, and which a read of this version, whose rows take no parameter set,
# ignores.
_NOMINAL = "nominal"
_NOMINAL_MEMBERS = ("acceptance", *_LOCATION_MEMBERS, "field", "reason", "basis", "value", "params")


@dataclass(frozen=True)
class Nominal:
    """A nominal of a request's `acceptances` that passed step 0 (`declarations.md` section 4.1): its index
    there; the field it names; where it is located, as an implied condition's location is; and the value it
    supplies for an interval, in the field's registered unit."""

    index: int
    field: str
    location: JsonObject
    value: float

    def located_at(self, field: str, record: MaterialRef) -> bool:
        return located_at(self.field, self.location, field, record)

    def assumption(self) -> shapes.NominalAssumption:
        """The declaration a value it supplies rests on, as the request gives it, `basis` aside (section
        2)."""
        return {"acceptance": "nominal", "value": self.value}

    def to_json(self) -> JsonObject:
        return {
            "acceptance": _NOMINAL,
            **copy.deepcopy(self.location),
            "field": self.field,
            "value": self.value,
        }


@dataclass(frozen=True)
class ReadRequest:
    """A request that passed step 0, holding the members its shape names and no others (section 1)."""

    target: MaterialRef  # a region target arrives with scenes
    field: str
    want: Want
    operating_conditions: dict[str, shapes.OperatingCondition]
    conditions: dict[str, shapes.RequirementCondition]
    implied: tuple[ImpliedCondition, ...] = ()
    nominals: tuple[Nominal, ...] = ()

    @classmethod
    def from_json(
        cls, request: RequestInput, claims: Collection[Suite] = CLAIMS
    ) -> "ReadRequest | tuple[Reason, ...]":
        """Step 0: the request, or every reason found against it, each code and condition once.

        `request` is JSON text, read by `record_format.md` section 1 item 6, as a `str` or bytes-like; any
        other value is read as the JSON text `json.dumps` writes of it. A request with a region target, or
        with a pick, an overlay or an extrapolation, raises `NotImplementedError`, and claims no reader makes
        raise `ValueError`, as in `read`.
        """
        _check(claims)
        value = _parsed(request)
        if isinstance(value, Reason):
            return (Reason("request_incomplete", detail=f"the request is not valid JSON: {value.detail}"),)
        if not isinstance(value, dict):
            return (Reason("request_incomplete", detail="the request is not an object"),)
        acceptances = value.get("acceptances", [])
        if isinstance(acceptances, list) and any(map(_applied_later, acceptances)):
            raise NotImplementedError("a request's picks, overlays and extrapolations are not read yet")
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
        implied, nominals = _acceptances(acceptances if isinstance(acceptances, list) else [], found)
        if found or target is None or want is None:
            return merged(found)
        return cls(target[0], target[1], want, checked_operating, checked_conditions, implied, nominals)

    def to_json(self) -> shapes.ReadRequest:
        target: shapes.Target = {"record": self.target.to_json(), "field": self.field}
        requirement: shapes.Requirement = {"want": self.want}
        if self.conditions:
            requirement["conditions"] = dict(self.conditions)
        request: shapes.ReadRequest = {"target": target, "requirement": requirement}
        if self.operating_conditions:
            request["operating_conditions"] = dict(self.operating_conditions)
        acceptances: list[ImpliedCondition | Nominal] = sorted(
            (*self.implied, *self.nominals), key=lambda acceptance: acceptance.index
        )
        if acceptances:
            request["acceptances"] = [
                cast(shapes.Acceptance, acceptance.to_json()) for acceptance in acceptances
            ]
        return request

    def nominal(self) -> Nominal | None:
        """The nominal that applies to this read: the one, if any, located at its field and record (two
        nominals for one field are refused at step 0)."""
        return next(
            (nominal for nominal in self.nominals if nominal.located_at(self.field, self.target)), None
        )


@dataclass(frozen=True)
class ProvenanceSummary:
    """The provenance a read returns (section 2): the origin token; the review as `provenance.md` section 2
    item 6 reads it, as found or `{"status": "not_checked"}` (ruling C); the source's key, where there is one;
    and for origin `derived` the derivation, its `assumptions` included (SQ45)."""

    origin: str
    review: JsonObject
    source: str | None = None
    derivation: JsonObject | None = None

    @classmethod
    def of(cls, provenance: JsonObject) -> "ProvenanceSummary":
        """The summary of a provenance object that passed step 8."""
        source = provenance.get("source")
        derivation = provenance.get("derivation")
        return cls(
            str(provenance["origin"]),
            _review(provenance.get("review")),
            str(an_object(source)["key"]) if source is not None else None,
            an_object(_returned(derivation, shapes.Derivation))
            if provenance["origin"] == "derived"
            else None,
        )

    @classmethod
    def from_json(cls, provenance: shapes.ResultProvenance) -> "ProvenanceSummary":
        derivation = provenance.get("derivation")
        return cls(
            provenance["origin"],
            cast(JsonObject, dict(provenance["review"])),
            provenance.get("source"),
            None if derivation is None else cast(JsonObject, copy.deepcopy(derivation)),
        )

    def to_json(self) -> shapes.ResultProvenance:
        summary: JsonObject = {"origin": self.origin, "review": copy.deepcopy(self.review)}
        if self.source is not None:
            summary["source"] = self.source
        if self.derivation is not None:
            derivation = copy.deepcopy(self.derivation)
            for entry in a_list(derivation["input_specimens"]):
                an_object(entry)["input"] = _whole(an_object(entry)["input"])
            summary["derivation"] = derivation
        return cast(shapes.ResultProvenance, summary)


@dataclass(frozen=True)
class FieldRead:
    """Steps 8 to 13 of one value field, the field read or one of its alternatives (section 3).

    `reasons` are those steps 8 to 12 found, and `want_mismatch` step 13's (`nominal_invalid` in its place
    for a nominal outside an interval's bounds), kept apart since step 7 reports it for no alternative under
    `no_pick`. `conditions` are present once step 10 has run to its end, and `request_fault` says that step
    10 ended on a fault of the request (section 1: two implied conditions that disagree), which refuses a
    field holding alternatives whichever alternative found it. The other members are those a read returns,
    once step 8 has passed, as stored and copied: the form's member (`member`); the value as `want` shapes it,
    or as a nominal supplies it with its `assumption`, where it can (`value`); the unit, the specimen facts,
    the statistics block (none for evidence) and the provenance; and the labels step 12 adds. `applied` holds
    the indexes of the acceptances steps 10 and 13 applied."""

    reasons: tuple[Reason, ...]
    conditions: tuple[ConditionEntry, ...] | None = None
    applied: tuple[int, ...] = dataclasses.field(default=(), compare=False)
    request_fault: bool = False
    want_mismatch: Reason | None = None
    member: JsonValue = None
    value: JsonValue = None
    assumption: shapes.NominalAssumption | None = None
    unit: JsonValue = None
    specimen: JsonObject | None = None
    statistics: JsonObject | None = None
    provenance: ProvenanceSummary | None = None
    labels: tuple[str, ...] = ()

    @property
    def found(self) -> tuple[Reason, ...]:
        """Every reason of the read, step 13's included."""
        return merged((*self.reasons, *(() if self.want_mismatch is None else (self.want_mismatch,))))

    def entry_json(self, index: int) -> shapes.AlternativeValue:
        """Its entry of `alternative_values` (section 2): its index among the stored alternatives, its form's
        member as stored, and its members as a read of it alone gives them."""
        entry: JsonObject = {
            "alternative": index,
            "value": copy.deepcopy(self.member),
            "conditions": [condition.to_json() for condition in self.conditions or ()],
            "specimen": copy.deepcopy(self.specimen),
        }
        if self.statistics is not None:
            entry["statistics"] = _counted(self.statistics)
        if self.provenance is not None:
            entry["provenance"] = cast(JsonObject, self.provenance.to_json())
        entry["labels"] = list(self.labels)
        return cast(shapes.AlternativeValue, entry)


@dataclass(frozen=True)
class ReadResult:
    """A read's result (section 2): its status, the worst of its reasons; every reason found; its labels;
    `conditions` once step 10 has run to its end (item 6); and the members that carry a value, each present
    as item 6 says, as stored: `value` with its `unit`, `specimen`, `statistics` and `provenance`, and the
    `assumption` a nominal's value rests on (item 3), or under `no_pick` the `alternative_values`, each an
    alternative's read, with the `unit`."""

    status: ReadStatus
    reasons: tuple[Reason, ...]
    labels: tuple[str, ...] = ()
    conditions: tuple[ConditionEntry, ...] | None = None
    applied: tuple[int, ...] = dataclasses.field(default=(), compare=False)
    """Outside `to_json`, and so outside equality, which compares what section 2 gives: the indexes, in the
    request's `acceptances`, of those the read applied, the implied conditions that filled a condition and the
    nominal that supplied the value, which a build maps to what accepted the result."""
    value: JsonValue = dataclasses.field(default=None, kw_only=True)
    alternative_values: tuple[FieldRead, ...] | None = dataclasses.field(default=None, kw_only=True)
    unit: JsonValue = dataclasses.field(default=None, kw_only=True)
    specimen: JsonObject | None = dataclasses.field(default=None, kw_only=True)
    statistics: JsonObject | None = dataclasses.field(default=None, kw_only=True)
    provenance: ProvenanceSummary | None = dataclasses.field(default=None, kw_only=True)
    assumption: shapes.Assumption | None = dataclasses.field(default=None, kw_only=True)

    @classmethod
    def from_json(cls, result: shapes.ReadResult) -> "ReadResult":
        reasons = tuple(Reason.from_json(reason) for reason in result["reasons"])
        conditions = result.get("conditions")
        provenance = result.get("provenance")
        entries = result.get("alternative_values")
        return cls(
            result["status"],
            reasons,
            tuple(result.get("labels", [])),
            None if conditions is None else _entries(conditions),
            value=_stored(result.get("value")),
            alternative_values=None if entries is None else tuple(map(_alternative, entries)),
            unit=_stored(result.get("unit")),
            specimen=cast(JsonObject | None, _stored(result.get("specimen"))),
            statistics=cast(JsonObject | None, _stored(result.get("statistics"))),
            provenance=None if provenance is None else ProvenanceSummary.from_json(provenance),
            assumption=cast(shapes.Assumption | None, _stored(result.get("assumption"))),
        )

    def to_json(self) -> shapes.ReadResult:
        """The result as JSON, a copy that shares nothing with it: numbers as stored, `-0` included (PR-047),
        and each index or count written as an integer (the code design's rule 5). Its members hold the shapes
        `read_result.json` gives them, since step 8 checked each member the read returns; the result's shape
        is read-only, so it is written whole."""
        members: dict[str, object] = {
            "status": self.status,
            "reasons": [reason.to_json() for reason in self.reasons],
        }
        if self.value is not None:
            members["value"] = copy.deepcopy(self.value)
        if self.alternative_values is not None:
            members["alternative_values"] = [
                alternative.entry_json(index) for index, alternative in enumerate(self.alternative_values)
            ]
        if self.unit is not None:
            members["unit"] = copy.deepcopy(self.unit)
        if self.conditions is not None:
            members["conditions"] = [entry.to_json() for entry in self.conditions]
        if self.specimen is not None:
            members["specimen"] = copy.deepcopy(self.specimen)
        if self.statistics is not None:
            members["statistics"] = _counted(self.statistics)
        if self.provenance is not None:
            members["provenance"] = self.provenance.to_json()
        members["labels"] = list(self.labels)
        if self.assumption is not None:
            members["assumption"] = copy.deepcopy(self.assumption)
        return cast(shapes.ReadResult, members)


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
    acceptances name, and step 0 raised for any acceptance but an implied condition, so it has none to
    apply."""
    record = resolved.record.value
    if record["record_type"] != "material":
        raise NotImplementedError("a read whose target is an overlay is not built yet")
    field = find_field(record, VOCABULARY.fields[request.field])
    if isinstance(field, Reason):
        return _refused((field,), resolved.labels)
    nominal = request.nominal()
    if isinstance(field.value, dict) and "alternatives" in field.value:
        return _read_alternatives(field, record, request, claims, resolved.labels, nominal)
    found = read_value_field(field, record, request, claims, nominal)
    reasons = found.found
    status = _status(reasons)
    labels = tuple(dict.fromkeys((*resolved.labels, *found.labels)))
    if not _value_returned(status, found):
        return ReadResult(status, reasons, labels, found.conditions, found.applied)
    return ReadResult(
        status,
        reasons,
        labels,
        found.conditions,
        found.applied,
        value=found.value,
        unit=found.unit,
        specimen=found.specimen,
        statistics=found.statistics,
        provenance=found.provenance,
        assumption=found.assumption,
    )


def _value_returned(status: ReadStatus, found: FieldRead) -> bool:
    """Section 2 item 3: a read that steps 8 to 13 shaped a value for returns it unless it is `not_met`, a
    declared nominal aside, whose value a `not_met` read carries with its `assumption` (an extrapolation waits
    for S3)."""
    return found.value is not None and (status != "not_met" or found.assumption is not None)


def read_value_field(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    nominal: Nominal | None = None,
) -> FieldRead:
    """Steps 8 to 13 of `field`, a value field of `record`: the field read, or one of its alternatives, with
    `nominal` applied at step 13, where one applies (none under `no_pick`, section 6). A step that finds a
    `not_met` reason ends the read (section 3)."""
    found = form_problems(field, record, claims)
    if _ends(found):
        return FieldRead(merged(found))
    found += unit_problems(field)
    if _ends(found):
        return FieldRead(merged(found))
    implied = [
        condition for condition in request.implied if condition.located_at(request.field, request.target)
    ]
    checked = check_conditions(field, request.operating_conditions, request.conditions, implied)
    found += checked.reasons
    if checked.entries is None:
        return FieldRead(merged(found), request_fault=True)
    if _ends(found):
        return FieldRead(merged(found), checked.entries, checked.applied)
    # Step 11: a constant's range is its conditions, once they are met, and an interval, a composition and
    # evidence have none (section 5).
    value = an_object(field.value)
    form = str(value["form"])
    provenance = an_object(value["provenance"])
    found += _origin(provenance, field.spec.name)
    hints = _FIELD_HINTS[form]
    member = _counted_member(_returned(value[FORM_MEMBERS[form]], hints[FORM_MEMBERS[form]]))
    mismatch = _by_want(value, field.spec.name, form, request.want)
    supplied = None
    if mismatch is not None and nominal is not None and form == "interval" and request.want == "value":
        mismatch, supplied = _nominal_read(an_object(value["interval"]), field.spec.name, nominal)
    applied = checked.applied if supplied is None else tuple(sorted((*checked.applied, supplied.index)))
    return FieldRead(
        merged(found),
        checked.entries,
        applied,
        want_mismatch=mismatch,
        member=member,
        value=_value(member, mismatch, supplied),
        assumption=None if supplied is None else supplied.assumption(),
        unit=_returned(value["unit"], shapes.Unit),
        specimen=cast(JsonObject, _returned(field.specimen(), shapes.Specimen)),
        # Evidence has no statistics (section 2 item 6).
        statistics=cast(JsonObject, _returned(value["statistics"], hints["statistics"]))
        if "statistics" in hints
        else None,
        provenance=ProvenanceSummary.of(provenance),
        labels=_labels(value, provenance),
    )


def _value(member: JsonValue, mismatch: Reason | None, supplied: Nominal | None) -> JsonValue:
    """The value as `want` shapes it: the form's member, or a nominal's value, or none where step 13 gave a
    reason and no nominal supplied one."""
    if supplied is not None:
        return supplied.value
    return copy.deepcopy(member) if mismatch is None else None


def _origin(provenance: JsonObject, name: str) -> list[Reason]:
    """Step 12's reason: a value stated without origin, which a waiver may accept (section 2 item 4)."""
    if provenance["origin"] != "stated_without_origin":
        return []
    return [Reason("stated_without_origin", detail=f"{name} is stated with nothing behind it")]


def _labels(field: JsonObject, provenance: JsonObject) -> tuple[str, ...]:
    """Step 12's labels (section 2): the field's `label`, which step 8 found to be one its row names for its
    form, and `mixed_conditions` for a derived value whose inputs' conditions differ (SQ45)."""
    labels: list[str] = []
    if isinstance(label := field.get("label"), str):
        labels.append(label)
    derivation = provenance.get("derivation")
    if provenance["origin"] == "derived" and an_object(derivation).get("mixed_conditions") is True:
        labels.append("mixed_conditions")
    return tuple(labels)


def _is_interval(alternative: JsonValue) -> bool:
    return an_object(alternative)["form"] == "interval"


def _nominal_read(interval: JsonObject, name: str, nominal: Nominal) -> tuple[Reason, Nominal | None]:
    """Step 13 under `want: value` of an interval with a nominal that applies to the read (section 6): inside
    or on its bounds, compared exactly (a comparison of two doubles is), on the bounded side of a one-sided
    interval, the nominal supplies the value and the assumption beside `want_mismatch`; outside them, it gives
    `nominal_invalid` in place of `want_mismatch`, and no value."""
    lower, upper, given = interval["lower"], interval["upper"], nominal.value
    inside = (not isinstance(lower, float) or lower <= given) and (
        not isinstance(upper, float) or given <= upper
    )
    if inside:
        detail = f"want value cannot give {name}, an interval: the nominal {given!r} supplies it"
        return Reason("want_mismatch", detail=detail), nominal
    detail = f"the nominal {given!r} lies outside the bounds of {name}"
    return Reason("nominal_invalid", detail=detail), None


def _by_want(field: JsonObject, name: str, form: str, want: Want) -> Reason | None:
    """Step 13 (section 6): `want_mismatch` where `want` cannot give the field's form, none where it gives the
    form's own member as stored: a constant's number under `want: value`, an interval's bounds with their
    basis under `want: bounds`, a composition's basis, sum rule, stated sum and components under `want:
    components`, and evidence's list of reports under `want: evidence`. `want: fit` on a field holding a fit
    record is the fits and reference data suite's, not built yet."""
    if want == _WANT_OF_FORM[form]:
        return None
    if want == "fit" and "fit" in field:
        raise NotImplementedError("want: fit on a field holding a fit record is not read yet")
    return Reason("want_mismatch", detail=f"want {want} cannot give {name}, a field of form {form}")


def _read_alternatives(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    labels: tuple[str, ...],
    nominal: Nominal | None,
) -> ReadResult:
    """Step 7 over a field holding alternatives, as far as S4's decision 12 lets S2 go (section 3, step 7):
    the list's shape (`form_invalid`); a fault of the request inside one alternative, where no alternative has
    a reason of its own, which refuses the field; and two or more alternatives none of which has a reason of
    its own: `want_mismatch` where none has a form `want` can give, else `no_pick`, each in
    `alternative_values`, with no nominal applied, nor compared with the bounds (section 6). An interval
    counts as a form `want: value` can give where `nominal`, the request's nominal that applies to the read,
    is one, since a pick would let it apply. Any other outcome, which an alternative's own reasons decide,
    waits for S4."""
    holder = an_object(field.value)
    shape = alternatives_problems(holder, field.spec.name)
    if shape:
        return _refused(merged(shape), labels)
    reads = [
        read_value_field(RecordField(field.spec, alternative, field.section), record, request, claims)
        for alternative in a_list(holder["alternatives"])
    ]
    faults = [read for read in reads if read.request_fault]
    own = [read for read in reads if not read.request_fault and read.reasons]
    if (
        faults
        and not own
        and all(reason.code == "request_incomplete" for read in faults for reason in read.reasons)
    ):
        return _refused(merged(reason for read in faults for reason in read.reasons), labels)
    if faults or own:
        raise NotImplementedError(
            "an alternative's own reasons are read at step 7 by S4, which is not built yet"
        )
    if len(reads) == 1:
        raise NotImplementedError("the one alternative left is read at step 7 by S4, which is not built yet")
    gives = [
        read.want_mismatch is None
        or (nominal is not None and _is_interval(alternative) and request.want == "value")
        for read, alternative in zip(reads, a_list(holder["alternatives"]), strict=True)
    ]
    if not any(gives):
        mismatch = Reason(
            "want_mismatch", detail=f"want {request.want} can give no alternative of {field.spec.name}"
        )
        return _refused((mismatch,), labels)
    if any(read.unit != reads[0].unit for read in reads):
        # A constant never reaches this: an alternative with no reason of its own has passed step 9, so its
        # unit is the registered unit's string. A guard for the forms S2b, S3 and S4 read.
        raise NotImplementedError("alternatives whose units are stored differently wait for S4")
    no_pick = Reason("no_pick", detail=f"{field.spec.name} holds {len(reads)} alternatives and no pick")
    return ReadResult("unknown", (no_pick,), labels, alternative_values=tuple(reads), unit=reads[0].unit)


# What a result returns from a record: the members the reader's version defines, as stored (section 2 item 5).


def _returned(value: JsonValue, shape: object) -> JsonValue:
    """`value`, stored where `shape` describes it, holding at every depth only the members the shape defines,
    each as stored, in a copy that shares nothing with the record. A map's names are kept, each value as its
    shape gives it. An object holding `status` is the status object of a member whose row allows one; a member
    of a type no shape defines is returned whole."""
    if isinstance(value, list):
        items = [item for alternative in _alternatives(shape) for item in _item_types(alternative)]
        return [_returned(item, items[0] if items else None) for item in value]
    if not isinstance(value, dict):
        return value
    if get_origin(shape) is dict:
        return {name: _returned(member, get_args(shape)[1]) for name, member in value.items()}
    defined = _members(shape, status="status" in value)
    if defined is None:
        return copy.deepcopy(value)
    returned = {name: _returned(member, defined[name]) for name, member in value.items() if name in defined}
    if shape is shapes.Provenance:
        # A provenance returned whole, an evidence entry's (`record_format.md` section 4.3 item 2): its review
        # as `provenance.md` section 2 item 6 reads every review a reader returns.
        returned["review"] = _review(value.get("review"))
    return returned


def _alternatives(shape: object) -> tuple[object, ...]:
    if get_origin(shape) in (Union, types.UnionType):
        return get_args(shape)
    return (shape,)


def _item_types(shape: object) -> tuple[object, ...]:
    if get_origin(shape) in (list, tuple):
        return get_args(shape)[:1]
    return ()


@cache
def _members(shape: object, *, status: bool) -> dict[str, object] | None:
    """The members the object shapes among `shape`'s alternatives define, by name, each with its own shape:
    those of the status objects where `status`, those of the others where not. None where no alternative is
    an object shape."""
    objects = [alternative for alternative in _alternatives(shape) if is_typeddict(alternative)]
    if not objects:
        return None
    chosen = [shape_ for shape_ in objects if _is_status_shape(shape_) == status] or objects
    defined: dict[str, object] = {}
    for shape_ in chosen:
        for name, member in get_type_hints(shape_).items():
            defined[name] = member if name not in defined else defined[name] | member
    return defined


def _is_status_shape(shape: object) -> bool:
    return set(get_type_hints(shape)) <= {"status", "reason"}


def _review(review: JsonValue) -> JsonObject:
    """`provenance.md` section 2 item 6: a review as found in two cases only, each holding no member one slip
    from a member a review names, a status object holding `not_checked` and no `result`, or an object holding
    no `status` whose `result` is a token the reader knows; any other review reads as `not_checked`, since a
    review never refuses. A status object that breaks its shape (section 1 item 5: its `reason` not a string,
    or a member a review defines beside it, `result` among them) is read for nothing else, so it is another
    review."""
    not_checked: JsonObject = {"status": "not_checked"}
    if not isinstance(review, dict) or slipped(review, _REVIEW_MEMBERS):
        return not_checked
    if "status" in review:
        found = (
            review["status"] == "not_checked"
            and isinstance(review.get("reason", ""), str)
            and not any(name in review for name in _REVIEW_DEFINES)
        )
        return cast(JsonObject, _returned(review, shapes.StatusNotChecked)) if found else not_checked
    if review.get("result") in get_args(shapes.ReviewResult):
        return cast(JsonObject, _returned(review, shapes.Review))
    return not_checked


def _whole(number: JsonValue) -> JsonValue:
    """An index or a count, which step 8 found whole, as an integer (the code design's rule 5)."""
    return int(number) if isinstance(number, float) else number


def _counted(statistics: JsonObject) -> JsonObject:
    """A statistics block as JSON, its counts as integers."""
    block = copy.deepcopy(statistics)
    for name in _COUNTS:
        if name in block:
            block[name] = _whole(block[name])
    return block


def _counted_member(member: JsonValue) -> JsonValue:
    """A form's own member as returned, the counts of a composition component's statistics block as
    integers."""
    if not isinstance(member, dict) or not isinstance(member.get("components"), list):
        return member
    for component in a_list(member["components"]):
        statistics = an_object(component).get("statistics")
        if isinstance(statistics, dict):
            an_object(component)["statistics"] = _counted(statistics)
    return member


def _stored(value: object) -> JsonValue:
    return cast(JsonValue, copy.deepcopy(value))


def _entries(conditions: Sequence[shapes.ConditionEntry]) -> tuple[ConditionEntry, ...]:
    return tuple(ConditionEntry.from_json(cast(JsonObject, dict(entry))) for entry in conditions)


def _alternative(entry: shapes.AlternativeValue) -> FieldRead:
    statistics = entry.get("statistics")
    return FieldRead(
        (),
        _entries(entry["conditions"]),
        member=_stored(entry["value"]),
        value=_stored(entry["value"]),
        specimen=cast(JsonObject, _stored(entry["specimen"])),
        statistics=None if statistics is None else cast(JsonObject, _stored(statistics)),
        provenance=ProvenanceSummary.from_json(entry["provenance"]),
        labels=tuple(entry["labels"]),
    )


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
    return _numeric(spec, entry, where, found)


def _numeric(
    spec: ConditionSpec,
    entry: dict[str, JsonValue],
    where: str,
    found: list[Reason],
    named: Collection[str] = (),
) -> shapes.OperatingCondition | None:
    """A numeric condition's value or range and its unit, as an operating condition gives them, where
    `named` are the other members named at its place."""
    name = spec.name
    _slips(entry, (*_OPERATING_MEMBERS, *named), where, found, name)
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


def _applied_later(entry: JsonValue) -> bool:
    return isinstance(entry, dict) and entry.get("acceptance") in _APPLIED_LATER


def _acceptances(
    acceptances: list[JsonValue], found: list[Reason]
) -> tuple[tuple[ImpliedCondition, ...], tuple[Nominal, ...]]:
    """The implied conditions and nominals of a request's acceptances, each checked whatever field or location
    it names (section 1): an acceptance of another kind, or not an object, is refused, and so are two nominals
    that name one field, whatever else each holds. A pick, an overlay and an extrapolation raised before."""
    implied: list[ImpliedCondition] = []
    nominals: list[Nominal] = []
    named: list[str] = []
    for index, entry in enumerate(acceptances):
        kind = entry.get("acceptance") if isinstance(entry, dict) else None
        if isinstance(entry, dict) and kind == _IMPLIED_CONDITION:
            if (condition := _implied_condition(index, entry, found)) is not None:
                implied.append(condition)
        elif isinstance(entry, dict) and kind == _NOMINAL:
            if isinstance(field := entry.get("field"), str):
                named.append(field)
            if (nominal := _nominal(index, entry, found)) is not None:
                nominals.append(nominal)
        else:
            found.append(
                _incomplete(f"acceptances[{index}] is no acceptance of a kind a read takes: {kind!r}")
            )
    for field in sorted({field for field in named if named.count(field) > 1}):
        found.append(_incomplete(f"acceptances hold two nominals for {field}"))
    return tuple(implied), tuple(nominals)


def _nominal(index: int, entry: dict[str, JsonValue], found: list[Reason]) -> Nominal | None:
    """A nominal's shape (`declarations.md` section 4.1), whatever field or location it names: its field, as
    the target's is, and its `value`, a number. None, its reasons in `found`, where it breaks its shape."""
    where = f"acceptances[{index}]"
    before = len(found)
    _slips(entry, _NOMINAL_MEMBERS, where, found)
    field, value = entry.get("field"), entry.get("value")
    _acceptance_field(field, where, found)
    location = _acceptance_location(entry, where, found)
    if not isinstance(value, float):
        found.append(_incomplete(f"{where}.value is missing or not a number"))
    if len(found) > before or not (isinstance(field, str) and isinstance(value, float)):
        return None
    return Nominal(index, field, location, value)


def _acceptance_field(field: JsonValue, where: str, found: list[Reason]) -> None:
    if not (isinstance(field, str) and FIELD.fullmatch(field) and field in VOCABULARY.fields):
        found.append(_incomplete(f"{where}.field is not a registered <section>.<field>: {field!r}"))


def _acceptance_location(entry: dict[str, JsonValue], where: str, found: list[Reason]) -> JsonObject:
    return {name: _location(name, entry[name], where, found) for name in _LOCATION_MEMBERS if name in entry}


def _implied_condition(
    index: int, entry: dict[str, JsonValue], found: list[Reason]
) -> ImpliedCondition | None:
    """An implied condition's shape (`declarations.md` section 4.1), whatever field or location it names:
    its field, as the target's is; its fact, a specimen fact with tokens, and one of that fact's tokens; and
    its `implies`, a value for each registered condition, as an operating condition's for a numeric one and
    a token of its row for a token one. None, its reasons in `found`, where it breaks its shape."""
    where = f"acceptances[{index}]"
    before = len(found)
    _slips(entry, _IMPLIED_OWN, where, found)
    field, fact, token, implies = (entry.get(name) for name in ("field", "fact", "token", "implies"))
    _acceptance_field(field, where, found)
    spec = VOCABULARY.facts.get(fact) if isinstance(fact, str) else None
    if spec is None or not spec.tokens:
        found.append(_incomplete(f"{where}.fact is not a specimen fact with tokens: {fact!r}"))
    elif token not in spec.tokens:
        found.append(_incomplete(f"{where}.token is not one of {fact}'s tokens: {token!r}"))
    location = _acceptance_location(entry, where, found)
    values: dict[str, JsonObject] = {}
    if not isinstance(implies, dict):
        found.append(_incomplete(f"{where}.implies is missing or not an object"))
    else:
        for name, value in implies.items():
            if (implied := _implied_value(name, value, f"{where}.implies.{name}", found)) is not None:
                values[name] = implied
    if len(found) > before or not (
        isinstance(field, str) and isinstance(fact, str) and isinstance(token, str)
    ):
        return None
    return ImpliedCondition(index, field, location, fact, token, values)


def _location(name: str, value: JsonValue, where: str, found: list[Reason]) -> JsonValue:
    """A location as the acceptance gives it, a record by the members a reference names: where it is not
    the read's, the acceptance is not applied (`read_side_contract.md` section 1)."""
    if name != "record" or not isinstance(value, dict):
        return value
    _slips(value, _RECORD_MEMBERS, f"{where}.record", found)
    return {member: value[member] for member in _RECORD_MEMBERS if member in value}


def _implied_value(name: str, value: JsonValue, where: str, found: list[Reason]) -> JsonObject | None:
    """The value an implied condition gives a registered condition: a record condition's shape of its own
    kind without its `basis`, never a status object, `plus_minus`, `set_or_measured` or a member of the other
    kind's shape; a numeric one's unit compared as an operating condition's is."""
    spec = _registered(name, found)
    if spec is None:
        return None
    if not isinstance(value, dict):
        found.append(_incomplete(f"{where} is not an object", name))
        return None
    other = _OF_THE_OTHER_KIND[spec.shape]
    if refused := [member for member in _IMPLIED_REFUSED if member in value]:
        found.append(
            _incomplete(f"{where} holds {', '.join(refused)}, which an implied value never holds", name)
        )
    if another := [member for member in other if member in value]:
        found.append(
            _incomplete(
                f"{where} holds {', '.join(another)}, which a {spec.shape} condition never holds", name
            )
        )
    named = (*other, *_IMPLIED_IGNORED, *_IMPLIED_REFUSED)
    if spec.shape == "token":
        _slips(value, ("token", *named), where, found, name)
        token = value.get("token")
        if not (isinstance(token, str) and token in spec.tokens):
            found.append(_incomplete(f"{where}.token is not one of {name}'s tokens: {token!r}", name))
            return None
        return None if refused or another else {"token": token}
    checked = _numeric(spec, value, where, found, named)
    return None if checked is None or refused or another else operating_json(checked)

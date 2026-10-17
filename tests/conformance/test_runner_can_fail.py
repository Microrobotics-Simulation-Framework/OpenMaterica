# SPDX-License-Identifier: Apache-2.0
"""Broken implementations, one fault each: every one must fail at least one real case, the named one included.

Faults inside a function are injected by replacing that function for the test, so that the rest of the
implementation stays the one under test.
"""

import hashlib
import math
import unicodedata
from collections.abc import Callable, Collection, Iterable

import pytest

from materica import shapes
from materica.core import canonical, envelope, fields, hashing, jsonio, read, record, resolve, value_shapes
from materica.core.fields import RecordField
from materica.core.identifiers import MaterialRef
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.record import Record, RecordStore
from materica.core.resolve import Refused, ResolvedRecord
from materica.core.vocabulary import ConditionSpec, RecordFieldSpec
from materica.shapes import Suite
from tests.conformance import runner
from tests.conformance.runner import CONFIGURATIONS, EXECUTORS, Executor, JsonObject, Outcome
from tests.property.support import Searched

CASE_FILES = {case_file.path.name: case_file for case_file in runner.discover()}

# A broken implementation: the executor of the operation its catcher runs, after any faults are injected.
Fault = Callable[[pytest.MonkeyPatch], Executor]


def keeps_card(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def digest(value: JsonValue) -> str:
        view = hashing.hashable_view(value)
        if isinstance(value, dict) and isinstance(view, dict) and "card" in value:
            view["card"] = value["card"]
        return "sha256:" + hashlib.sha256(canonical.canonicalize(view)).hexdigest()

    return runner.content_hash_executor(digest=digest)


def removes_review_outside_provenance(monkeypatch: pytest.MonkeyPatch) -> Executor:
    return runner.content_hash_executor(digest=lambda value: hashing.content_hash(_without(value, "review")))


def orders_names_by_code_point(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def code_points(name: str) -> str:
        return name

    monkeypatch.setattr(canonical, "_utf16_units", code_points)
    return runner.content_hash_executor()


def orders_names_by_utf8_bytes(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def utf8_bytes(name: str) -> bytes:
        return name.encode("utf-8")

    monkeypatch.setattr(canonical, "_utf16_units", utf8_bytes)
    return runner.content_hash_executor()


def normalises_strings_to_nfc(monkeypatch: pytest.MonkeyPatch) -> Executor:
    return runner.content_hash_executor(digest=lambda value: hashing.content_hash(_nfc(value)))


def formats_numbers_with_repr(monkeypatch: pytest.MonkeyPatch) -> Executor:
    monkeypatch.setattr(canonical, "_number", repr)
    return runner.content_hash_executor()


def accepts_repeated_names(monkeypatch: pytest.MonkeyPatch) -> Executor:
    monkeypatch.setattr(jsonio, "_object", dict)
    return runner.content_hash_executor()


def counts_scalars_in_depth(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def parse(data: bytes) -> JsonValue | Reason:
        value = jsonio.parse(data)
        if not isinstance(value, Reason) and _depth_counting_scalars(value) > jsonio.MAX_DEPTH:
            return Reason("malformed")
        return value

    return runner.content_hash_executor(parse=parse)


def answers_a_constant(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def execute(case_file: runner.CaseFile, claims: frozenset[Suite]) -> JsonObject:
        return {"status": "met", "reasons": [], "value": "sha256:" + "0" * 64}

    return execute


# Reads and listings with one fault: the core's own code, with one function replaced.


def ignores_unreadable_sources(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def no_unreadable_source(self: RecordStore) -> list[tuple[str, Reason]]:
        return []

    monkeypatch.setattr(RecordStore, "unparsed", no_unreadable_source)
    return EXECUTORS["read"]


def counts_documents_as_unreadable(monkeypatch: pytest.MonkeyPatch) -> Executor:
    add = RecordStore.add

    def add_document_as_unreadable(self: RecordStore, source: str, data: bytes) -> None:
        value = jsonio.parse(data)
        if isinstance(value, dict) and "document_type" in value and "record_type" not in value:
            data = b"[]"  # parses to no record, so the source is unreadable
        add(self, source, data)

    monkeypatch.setattr(RecordStore, "add", add_document_as_unreadable)
    return EXECUTORS["read"]


def reads_the_first_of_copies_that_differ(monkeypatch: pytest.MonkeyPatch) -> Executor:
    candidate = resolve._candidate  # pyright: ignore[reportPrivateUsage]  # the function the fault replaces

    def first_pinned(ref: MaterialRef, store: RecordStore) -> Record | Reason:
        pinned = [
            copy
            for copy in store.get(ref.id, ref.version)
            if copy.value.get("content_hash") == ref.content_hash
        ]
        return pinned[0] if pinned else candidate(ref, store)

    monkeypatch.setattr(resolve, "_candidate", first_pinned)
    return EXECUTORS["read"]


def searches_the_id_pattern(monkeypatch: pytest.MonkeyPatch) -> Executor:
    patterns = envelope._PATTERNS  # pyright: ignore[reportPrivateUsage]  # the table the fault changes
    monkeypatch.setitem(patterns, "id", Searched(patterns["id"]))  # pyright: ignore[reportArgumentType]  # a duck-typed pattern
    return EXECUTORS["read"]


def refuses_another_patch(monkeypatch: pytest.MonkeyPatch) -> Executor:
    refusal = vars(Record)["version_refusal"].func  # the cached_property's own function

    def same_patch_only(self: Record) -> Reason | None:
        found = refusal(self)
        return Reason("other_version") if found is None and self.value["schema_version"] != "0.1.0" else found

    monkeypatch.setattr(Record, "version_refusal", property(same_patch_only))
    return EXECUTORS["list_records"]


def lists_interfaces(monkeypatch: pytest.MonkeyPatch) -> Executor:
    monkeypatch.setattr(record, "READABLE_TYPES", ("material", "overlay", "interface"))
    return EXECUTORS["list_records"]


def lists_broken_envelopes(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def no_refusal(self: Record) -> Reason | None:
        return None

    monkeypatch.setattr(Record, "envelope_refusal", property(no_refusal))
    return EXECUTORS["list_records"]


def hash_not_recomputed(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def stated_hash(value: JsonValue) -> str:
        assert isinstance(value, dict)
        return str(value["content_hash"])

    monkeypatch.setattr(resolve, "content_hash", stated_hash)
    return EXECUTORS["read"]


def checks_the_type_before_the_hash(monkeypatch: pytest.MonkeyPatch) -> Executor:
    resolve_record = resolve.resolve_record

    def type_first(
        ref: MaterialRef, store: RecordStore, claims: Collection[Suite]
    ) -> ResolvedRecord | Refused:
        resolved = resolve_record(ref, store, ())
        if isinstance(resolved, Refused) and resolved.reasons[0].code == "unknown_type":
            return Refused(resolved.reasons)
        return resolve_record(ref, store, claims)

    monkeypatch.setattr(read, "resolve_record", type_first)
    return EXECUTORS["read"]


def labels_every_result_without_the_hash_suite(monkeypatch: pytest.MonkeyPatch) -> Executor:
    resolve_record = resolve.resolve_record

    def labelled(ref: MaterialRef, store: RecordStore, claims: Collection[Suite]) -> ResolvedRecord | Refused:
        resolved = resolve_record(ref, store, claims)
        if isinstance(resolved, Refused) and "hash" not in claims:
            return Refused(resolved.reasons, ("hash_not_checked",))
        return resolved

    monkeypatch.setattr(read, "resolve_record", labelled)
    return EXECUTORS["read"]


def normalises_units(monkeypatch: pytest.MonkeyPatch) -> Executor:
    unit = read._unit  # pyright: ignore[reportPrivateUsage]  # the function the fault replaces

    def normalised(
        spec: ConditionSpec, entry: dict[str, JsonValue], where: str, found: list[Reason]
    ) -> str | None:
        written = entry.get("unit")
        if isinstance(written, str):
            entry = {**entry, "unit": unicodedata.normalize("NFKC", written)}
        return unit(spec, entry, where, found)

    monkeypatch.setattr(read, "_unit", normalised)
    return EXECUTORS["read"]


def refuses_unnamed_members(monkeypatch: pytest.MonkeyPatch) -> Executor:
    target = read._target  # pyright: ignore[reportPrivateUsage]  # the function the fault replaces

    def strict(value: JsonValue, found: list[Reason]) -> tuple[MaterialRef, str] | None:
        if isinstance(value, dict) and set(value) - {"record", "field"}:
            found.append(Reason("request_incomplete", detail="a member the shape does not name"))
        return target(value, found)

    monkeypatch.setattr(read, "_target", strict)
    return EXECUTORS["read"]


def repeats_reasons(monkeypatch: pytest.MonkeyPatch) -> Executor:
    monkeypatch.setattr(read, "merged", tuple)
    return EXECUTORS["read"]


def ignores_the_suite_of_a_want(monkeypatch: pytest.MonkeyPatch) -> Executor:
    monkeypatch.setattr(read, "_WANT_SUITES", {})
    return EXECUTORS["read"]


def refuses_a_tolerance_of_minus_zero(monkeypatch: pytest.MonkeyPatch) -> Executor:
    condition = read._requirement_condition  # pyright: ignore[reportPrivateUsage]  # the function the fault replaces

    def signed(name: str, entry: JsonValue, operated: bool, found: list[Reason]) -> object:
        tolerance = entry.get("tolerance") if isinstance(entry, dict) else None
        value = tolerance.get("value") if isinstance(tolerance, dict) else None
        if isinstance(value, float) and math.copysign(1.0, value) < 0:
            found.append(Reason("request_incomplete", name, "below zero"))
        return condition(name, entry, operated, found)

    monkeypatch.setattr(read, "_requirement_condition", signed)
    return EXECUTORS["read"]


# Step 8 with one fault: a check of `value_shapes` or `fields` left out, loosened or stopped early.


def ignores_slips(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def none_slipped(members: Iterable[str], named: Collection[str]) -> list[tuple[str, str]]:
        return []

    monkeypatch.setattr(value_shapes, "slipped", none_slipped)
    return EXECUTORS["read"]


def ignores_members_beside_a_status(monkeypatch: pytest.MonkeyPatch) -> Executor:
    status_object = value_shapes.status_object

    def only_status_and_reason(
        value: dict[str, JsonValue],
        where: str,
        tokens: Collection[str] | None,
        defines: Collection[str],
        found: list[Reason],
    ) -> None:
        kept = {name: member for name, member in value.items() if name in ("status", "reason")}
        status_object(kept, where, tokens, defines, found)

    monkeypatch.setattr(value_shapes, "status_object", only_status_and_reason)
    return EXECUTORS["read"]


def knows_no_token_of_another_member(monkeypatch: pytest.MonkeyPatch) -> Executor:
    monkeypatch.setattr(value_shapes, "KNOWN", {member: frozenset[str]() for member in value_shapes.KNOWN})
    return EXECUTORS["read"]


def leaves_the_section_unchecked(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def nothing(name: str, section: dict[str, JsonValue]) -> list[Reason]:
        return []

    monkeypatch.setattr(fields, "section_problems", nothing)
    return EXECUTORS["read"]


def allows_every_form(monkeypatch: pytest.MonkeyPatch) -> Executor:
    form = fields._form  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def unregistered_too(
        field: dict[str, JsonValue], spec: RecordFieldSpec, claims: Collection[Suite], found: list[Reason]
    ) -> tuple[str | None, bool]:
        own: list[Reason] = []
        found_form, _ = form(field, spec, claims, own)
        found += [reason for reason in own if reason.code != "form_not_registered"]
        return found_form, found_form is not None

    monkeypatch.setattr(fields, "_form", unregistered_too)
    return EXECUTORS["read"]


def reads_null_as_absent(monkeypatch: pytest.MonkeyPatch) -> Executor:
    members = value_shapes.members

    def without_nulls(
        value: JsonValue,
        where: str,
        found: list[Reason],
        required: value_shapes.Members,
        optional: value_shapes.Members | None = None,
        *,
        named: Collection[str] = (),
    ) -> dict[str, JsonValue] | None:
        if isinstance(value, dict):
            value = {name: member for name, member in value.items() if member is not None}
        return members(value, where, found, required, optional, named=named)

    monkeypatch.setattr(value_shapes, "members", without_nulls)
    return EXECUTORS["read"]


def reads_a_withheld_value(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def no_member_check(field: dict[str, JsonValue], name: str, form: str, found: list[Reason]) -> None:
        pass

    monkeypatch.setattr(fields, "_own_member", no_member_check)
    return EXECUTORS["read"]


def stops_at_the_first_refusal(monkeypatch: pytest.MonkeyPatch) -> Executor:
    form_problems = fields.form_problems

    def first(
        field: RecordField, record_value: dict[str, JsonValue], claims: Collection[Suite]
    ) -> list[Reason]:
        return form_problems(field, record_value, claims)[:1]

    monkeypatch.setattr(read, "form_problems", first)
    return EXECUTORS["read"]


def returns_bounds_without_their_basis(monkeypatch: pytest.MonkeyPatch) -> Executor:
    counted_member = read._counted_member  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def bare(member: JsonValue) -> JsonValue:
        returned = counted_member(member)
        if isinstance(returned, dict) and "lower" in returned:
            return {name: bound for name, bound in returned.items() if name != "basis"}
        return returned

    monkeypatch.setattr(read, "_counted_member", bare)
    return EXECUTORS["read"]


def reads_an_upper_none_as_the_largest_double(monkeypatch: pytest.MonkeyPatch) -> Executor:
    counted_member = read._counted_member  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def unbounded(member: JsonValue) -> JsonValue:
        returned = counted_member(member)
        if isinstance(returned, dict) and returned.get("upper") == {"status": "none"}:
            return {**returned, "upper": 1.7976931348623157e308}
        return returned

    monkeypatch.setattr(read, "_counted_member", unbounded)
    return EXECUTORS["read"]


def normalises_components(monkeypatch: pytest.MonkeyPatch) -> Executor:
    counted_member = read._counted_member  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def normalised(member: JsonValue) -> JsonValue:
        returned = counted_member(member)
        if not (isinstance(returned, dict) and isinstance(stored := returned.get("components"), list)):
            return returned
        components = [component for component in stored if isinstance(component, dict)]
        total = math.fsum(float(str(component["fraction"])) for component in components)
        for component in components:
            component["fraction"] = float(str(component["fraction"])) / total
        return {name: kept for name, kept in returned.items() if name != "stated_sum"}

    monkeypatch.setattr(read, "_counted_member", normalised)
    return EXECUTORS["read"]


def takes_bounds_out_of_order(monkeypatch: pytest.MonkeyPatch) -> Executor:
    interval = fields.OWN_MEMBERS["interval"]

    def ordered_first(value: JsonValue, where: str, found: list[Reason]) -> None:
        if isinstance(value, dict) and isinstance(value.get("lower"), float):
            lower, upper = value["lower"], value.get("upper")
            if isinstance(lower, float) and isinstance(upper, float) and lower > upper:
                value = {**value, "lower": upper, "upper": lower}
        interval(value, where, found)

    monkeypatch.setitem(fields.OWN_MEMBERS, "interval", ordered_first)
    return EXECUTORS["read"]


def takes_a_component_twice(monkeypatch: pytest.MonkeyPatch) -> Executor:
    composition = fields.OWN_MEMBERS["composition"]

    def each_once(value: JsonValue, where: str, found: list[Reason]) -> None:
        if isinstance(value, dict) and isinstance(stored := value.get("components"), list):
            kept = {
                str(component.get("component")): component
                for component in stored
                if isinstance(component, dict)
            }
            value = {**value, "components": list(kept.values())}
        composition(value, where, found)

    monkeypatch.setitem(fields.OWN_MEMBERS, "composition", each_once)
    return EXECUTORS["read"]


def reads_every_report_withheld_as_some(monkeypatch: pytest.MonkeyPatch) -> Executor:
    evidence = fields.OWN_MEMBERS["evidence"]

    def some(value: JsonValue, where: str, found: list[Reason]) -> None:
        evidence(value, where, found)
        found[:] = [Reason("entries_withheld") if reason.code == "withheld" else reason for reason in found]

    monkeypatch.setitem(fields.OWN_MEMBERS, "evidence", some)
    return EXECUTORS["read"]


def withholds_a_list_for_one_report(monkeypatch: pytest.MonkeyPatch) -> Executor:
    evidence = fields.OWN_MEMBERS["evidence"]

    def whole(value: JsonValue, where: str, found: list[Reason]) -> None:
        evidence(value, where, found)
        found[:] = [Reason("withheld") if reason.code == "entries_withheld" else reason for reason in found]

    monkeypatch.setitem(fields.OWN_MEMBERS, "evidence", whole)
    return EXECUTORS["read"]


def takes_a_report_withheld_in_part(monkeypatch: pytest.MonkeyPatch) -> Executor:
    evidence_entry = fields.evidence_entry

    def in_part(value: JsonValue, where: str, found: list[Reason]) -> bool:
        own: list[Reason] = []
        withheld = evidence_entry(value, where, own)
        found += [reason for reason in own if "withholding" not in (reason.detail or "")]
        return withheld

    monkeypatch.setattr(fields, "evidence_entry", in_part)
    return EXECUTORS["read"]


def takes_a_registered_condition_under_evidence(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def none(conditions: JsonValue, where: str, found: list[Reason]) -> None:
        pass

    monkeypatch.setattr(fields, "_no_registered_condition", none)
    return EXECUTORS["read"]


def cuts_a_reports_provenance_to_a_results(monkeypatch: pytest.MonkeyPatch) -> Executor:
    returned = read._returned  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def cut(value: JsonValue, shape: object) -> JsonValue:
        found = returned(value, shape)
        if shape is shapes.Provenance and isinstance(found, dict):
            return {name: member for name, member in found.items() if name in ("origin", "review")}
        return found

    monkeypatch.setattr(read, "_returned", cut)
    return EXECUTORS["read"]


def applies_a_nominal_outside_its_bounds(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def anywhere(
        interval: JsonObject, name: str, nominal: read.Nominal
    ) -> tuple[Reason, read.Nominal | None]:
        return Reason("want_mismatch"), nominal

    monkeypatch.setattr(read, "_nominal_read", anywhere)
    return EXECUTORS["read"]


def drops_a_nominals_value_under_not_met(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def unless_not_met(status: str, found: read.FieldRead) -> bool:
        return found.value is not None and status != "not_met"

    monkeypatch.setattr(read, "_value_returned", unless_not_met)
    return EXECUTORS["read"]


def applies_a_nominal_wherever_it_is_located(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def by_field(named: str, location: JsonObject, field: str, target: MaterialRef) -> bool:
        return named == field

    monkeypatch.setattr(read, "located_at", by_field)
    return EXECUTORS["read"]


def takes_two_nominals_for_one_field(monkeypatch: pytest.MonkeyPatch) -> Executor:
    acceptances = read._acceptances  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def one_each(entries: list[JsonValue], found: list[Reason]) -> object:
        own: list[Reason] = []
        checked = acceptances(entries, own)
        found += [reason for reason in own if "two nominals" not in (reason.detail or "")]
        return checked

    monkeypatch.setattr(read, "_acceptances", one_each)
    return EXECUTORS["read"]


def ignores_a_waiver(monkeypatch: pytest.MonkeyPatch) -> Executor:
    acceptances = read._acceptances  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def without_waivers(entries: list[JsonValue], found: list[Reason]) -> object:
        kept: list[JsonValue] = [
            entry
            for entry in entries
            if not (isinstance(entry, dict) and entry.get("acceptance") == "waiver")
        ]
        return acceptances(kept, found)

    monkeypatch.setattr(read, "_acceptances", without_waivers)
    return EXECUTORS["read"]


def compares_a_nominal_under_no_pick(monkeypatch: pytest.MonkeyPatch) -> Executor:
    read_alternatives = read._read_alternatives  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def compared(
        field: RecordField,
        record_value: JsonObject,
        request: read.ReadRequest,
        claims: Collection[Suite],
        labels: tuple[str, ...],
        nominal: read.Nominal | None,
    ) -> read.ReadResult:
        result = read_alternatives(field, record_value, request, claims, labels, nominal)
        bounds = [entry.member for entry in result.alternative_values or () if isinstance(entry.member, dict)]
        if nominal is None or not any(
            read._nominal_read(bound, field.spec.name, nominal)[1] is None  # pyright: ignore[reportPrivateUsage]
            for bound in bounds
            if "lower" in bound
        ):
            return result
        return read.ReadResult("not_met", (*result.reasons, Reason("nominal_invalid")), result.labels)

    monkeypatch.setattr(read, "_read_alternatives", compared)
    return EXECUTORS["read"]


def _without(value: JsonValue, removed: str) -> JsonValue:
    if isinstance(value, list):
        return [_without(item, removed) for item in value]
    if isinstance(value, dict):
        return {name: _without(member, removed) for name, member in value.items() if name != removed}
    return value


def _nfc(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", name): _nfc(member) for name, member in value.items()}
    return value


def _depth_counting_scalars(value: JsonValue) -> int:
    if isinstance(value, list):
        return 1 + max((_depth_counting_scalars(item) for item in value), default=0)
    if isinstance(value, dict):
        return 1 + max((_depth_counting_scalars(member) for member in value.values()), default=0)
    return 1


FAULTS: list[tuple[Fault, str]] = [
    (keeps_card, "HS-001.top_level_removed.json"),
    (removes_review_outside_provenance, "HS-001.outside_kept.json"),
    (orders_names_by_code_point, "HS-003.utf16_order_raw.json"),
    (orders_names_by_utf8_bytes, "HS-003.utf16_order_raw.json"),
    (normalises_strings_to_nfc, "HS-003.nfc_decomposed.json"),
    (formats_numbers_with_repr, "HS-003.number_1_0.json"),
    (accepts_repeated_names, "HS-003.malformed_duplicate_name.json"),
    (counts_scalars_in_depth, "HS-003.depth_64_scalar.json"),
    (answers_a_constant, "HS-003.malformed_bom.json"),
    (ignores_unreadable_sources, "PR-328.unparsed_source_malformed.json"),
    (counts_documents_as_unreadable, "PR-328.scene_manifest_absent.json"),
    (reads_the_first_of_copies_that_differ, "PR-329.two_with_hash_card_differs.json"),
    (searches_the_id_pattern, "PR-002.local_id_trailing_newline.json"),
    (refuses_another_patch, "PR-048.patch_0_1_7_listed.json"),
    (lists_interfaces, "PR-006.interface_skipped.json"),
    (lists_broken_envelopes, "PR-004.overlay_missing_name_not_listed.json"),
    (hash_not_recomputed, "HS-010.value_edited.json"),
    (checks_the_type_before_the_hash, "HS-010.type_edited.json"),
    (labels_every_result_without_the_hash_suite, "PR-327.pin_no_hs.json"),
    (normalises_units, "PR-320.operating_unit_kelvin_sign.json"),
    (refuses_unnamed_members, "PR-330.unknown_member_in_target.json"),
    (repeats_reasons, "PR-331.request_incomplete_once_per_condition.json"),
    (ignores_the_suite_of_a_want, "PR-332.fit_without_fd.json"),
    (refuses_a_tolerance_of_minus_zero, "PR-330.tolerance_negative_zero_accepted.json"),
    (ignores_slips, "PR-005.near_typo_crad.json"),
    (ignores_members_beside_a_status, "PR-110.sd_status_beside_other_member.json"),
    (knows_no_token_of_another_member, "PR-045.condition_token_of_another_row.json"),
    (leaves_the_section_unchecked, "PR-045.section_specimen_fault_refuses_section.json"),
    (allows_every_form, "PR-036.power_law_on_bulk_density.json"),
    (reads_null_as_absent, "PR-049.field_specimen_null.json"),
    (reads_a_withheld_value, "PR-105.withheld_value.json"),
    (stops_at_the_first_refusal, "PR-301.two_refusals_step_8.json"),
    (returns_bounds_without_their_basis, "PR-022.bounds_reported_range.json"),
    (reads_an_upper_none_as_the_largest_double, "PR-022.bounds_one_sided_upper_none.json"),
    (normalises_components, "PR-023.components_stated_sum.json"),
    (takes_bounds_out_of_order, "PR-050.lower_above_upper.json"),
    (takes_a_component_twice, "PR-051.repeated_component.json"),
    (reads_every_report_withheld_as_some, "PR-052.every_entry_withheld.json"),
    (withholds_a_list_for_one_report, "PR-052.some_entries_withheld.json"),
    (takes_a_report_withheld_in_part, "PR-052.entry_partly_withheld.json"),
    (takes_a_registered_condition_under_evidence, "PR-052.registered_condition_in_conditions.json"),
    (cuts_a_reports_provenance_to_a_results, "PR-038.evidence_list.json"),
    (applies_a_nominal_outside_its_bounds, "PR-338.nominal_outside.json"),
    (drops_a_nominals_value_under_not_met, "PR-302.nominal_value_under_not_met.json"),
    (applies_a_nominal_wherever_it_is_located, "PR-338.nominal_other_record.json"),
    (takes_two_nominals_for_one_field, "PR-330.two_nominals_one_field.json"),
    (ignores_a_waiver, "PR-310.waiver_refused.json"),
    (compares_a_nominal_under_no_pick, "PR-338.no_pick_nominal_outside_not_reported.json"),
]


def failed_cases(operation: str, executor: Executor) -> set[str]:
    runs = runner.run_all(
        CASE_FILES.values(), configurations=CONFIGURATIONS, executors={**EXECUTORS, operation: executor}
    )
    return {case_run.case_file.path.name for case_run in runs if case_run.outcome is Outcome.FAILED}


@pytest.mark.parametrize(("fault", "catcher"), FAULTS, ids=[fault.__name__ for fault, _ in FAULTS])
def test_a_broken_implementation_fails_a_real_case(
    fault: Fault, catcher: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_file = CASE_FILES[catcher]
    executors = {**EXECUTORS, case_file.operation: fault(monkeypatch)}
    assert runner.run(case_file, configurations=CONFIGURATIONS, executors=executors).outcome is Outcome.FAILED


@pytest.mark.parametrize("operation", sorted(EXECUTORS))
def test_the_implementation_itself_fails_none(operation: str) -> None:
    assert failed_cases(operation, EXECUTORS[operation]) == set()

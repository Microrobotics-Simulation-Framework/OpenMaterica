# SPDX-License-Identifier: Apache-2.0
"""Examples at the edges of the read up to step 5, which the cases and properties reach rarely or not at
all: versions longer than `int` reads, the forms a request may be given in, the misuses that raise, and the
steps not built yet, which raise rather than answer."""

import copy
import importlib
import inspect
import json
from collections.abc import Callable, Collection
from pathlib import Path
from types import ModuleType
from typing import Any, cast, get_type_hints

import pytest

import materica
from materica import shapes
from materica.core import value_shapes
from materica.core.hashing import content_hash
from materica.core.identifiers import FAMILY_ID, RECORD_ID, MaterialRef, Version, parse_version
from materica.core.jsonio import JsonValue
from materica.core.read import ReadRequest, ReadResult, read
from materica.core.reasons import Reason, merged
from materica.core.record import RecordStore
from materica.core.status import worst
from materica.core.value_shapes import FORM_MEMBERS, a_list, an_object
from materica.core.vocabulary import VOCABULARY
from materica.shapes import ReasonCode, Suite
from tests.spec_sync.schemas import validator

WATER = (
    Path(materica.__file__).parent / "data" / "conformance" / "plain_read" / "inputs" / "water_fixture.json"
)
PIN = "sha256:c21a2c7f46e66bcfb5e74f18d2a08644468d5a92bafb4fa57a03651facf96e2d"
REQUEST: shapes.ReadRequest = {
    "target": {
        "record": {"id": "conformance/water_fixture", "version": "2.0.0", "content_hash": PIN},
        "field": "fluid.dynamic_viscosity",
    },
    "operating_conditions": {"temperature": {"value": 310.15, "unit": "K"}},
    "requirement": {"want": "value", "conditions": {"temperature": {"tolerance": {"value": 1, "unit": "K"}}}},
}
ABSENT = ReadResult("not_met", (Reason("absent"),))


def with_members(**members: JsonValue) -> dict[str, JsonValue]:
    """REQUEST as parsed JSON, with `members` set at its top."""
    value: dict[str, JsonValue] = json.loads(json.dumps(REQUEST))
    return value | members


def store() -> RecordStore:
    return materica.load_records([WATER])


def test_components_beyond_ints_digit_limit_order_by_length_then_digits() -> None:
    longer = parse_version("1" + "0" * 5000 + ".0.0")
    shorter = parse_version("9" * 4999 + ".0.0")
    assert longer is not None
    assert shorter is not None
    assert shorter < longer
    ten = parse_version("0.10.0")
    assert ten is not None
    assert ten == Version("0", "10", "0")
    assert ten > Version("0", "9", "0")


@pytest.mark.parametrize(
    "components", [("01", "0", "0"), ("1", "00", "0"), ("1", "0", ""), ("\u0661", "0", "0"), ("1", "0", "1 ")]
)
def test_a_version_is_built_only_from_components_without_leading_zeros(
    components: tuple[str, str, str],
) -> None:
    # Ordering by length, then digits, holds only without them.
    with pytest.raises(ValueError, match="version component"):
        Version(*components)


def test_a_version_compares_only_with_a_version() -> None:
    version = Version("1", "0", "0")
    assert version.__lt__("1.0.0") is NotImplemented  # the method itself, as total_ordering calls it
    assert version != "1.0.0"  # type: ignore[comparison-overlap]  # the misuse under test
    with pytest.raises(TypeError):
        _ = version < "2.0.0"


@pytest.mark.parametrize("text", ["0.1.0\n", "01.0.0", "1.0", "\u0661.0.0", "1.0.0-rc1", " 1.0.0"])
def test_a_version_off_the_pattern_is_none(text: str) -> None:
    assert parse_version(text) is None


def test_identifiers_match_in_full() -> None:
    assert RECORD_ID.fullmatch("conformance/water_fixture")
    assert not RECORD_ID.fullmatch("conformance/water_fixture\n")
    assert FAMILY_ID.fullmatch("materica.fluid.newtonian.v1")
    assert not FAMILY_ID.fullmatch("materica.v1")
    assert not FAMILY_ID.fullmatch("materica.fluid.v01")


def test_a_request_reads_the_same_as_text_as_a_value_and_as_a_shape() -> None:
    text = json.dumps(REQUEST)
    for given in (text, text.encode(), bytearray(text.encode()), memoryview(text.encode())):
        assert read(given, store()) == ABSENT, type(given)
    assert read(json.loads(text), store()) == ABSENT
    assert read(REQUEST, store()) == ABSENT


@pytest.mark.parametrize(
    "request_value",
    [
        pytest.param({**REQUEST, "x": {1, 2}}, id="a_set"),
        pytest.param({**REQUEST, "x": float("nan")}, id="nan"),
        pytest.param(b"\xef\xbb\xbf{}", id="a_byte_order_mark"),
        pytest.param("\ufeff{}", id="a_byte_order_mark_in_text"),
        pytest.param('{"x": "\ud800"}', id="a_lone_surrogate_in_text"),
        pytest.param(json.dumps("a string"), id="a_json_string"),
    ],
)
def test_a_request_that_is_not_json_is_incomplete(request_value: object) -> None:
    result = read(request_value, store())  # type: ignore[arg-type]  # a misuse a consumer may still make
    assert result.status == "not_met"
    assert [reason.code for reason in result.reasons] == ["request_incomplete"]


def test_unknown_claims_are_a_misuse() -> None:
    with pytest.raises(ValueError, match="not suites"):
        read(REQUEST, store(), claims={"plain_read", "hashes"})  # type: ignore[arg-type]  # the misuse


WITHOUT_PLAIN_READ: list[set[shapes.Suite]] = [
    set(),
    {"hash"},
    {"fits_and_reference_data"},
    {"scene_documents", "hash"},
]


@pytest.mark.parametrize("claims", WITHOUT_PLAIN_READ)
def test_claims_without_plain_read_are_a_misuse(claims: set[shapes.Suite]) -> None:
    with pytest.raises(ValueError, match="plain_read"):
        read(REQUEST, store(), claims=claims)
    with pytest.raises(ValueError, match="plain_read"):
        ReadRequest.from_json(REQUEST, claims)


def test_steps_not_built_yet_raise_rather_than_answer() -> None:
    region = with_members(target={"region": "lumen", "field": "fluid.dynamic_viscosity"})
    with pytest.raises(NotImplementedError):
        read(region, store())
    # Whatever else is wrong with it: scenes may add reasons of their own.
    faults: list[dict[str, JsonValue]] = [
        {"operating_conditions": {"temperature": {"value": 310.15, "unit": "Cel"}}},
        {"requirement": {"want": "fit"}},
        {"target": {"region": 1.0, "record": {}, "field": "x"}},
    ]
    for fault in faults:
        with pytest.raises(NotImplementedError):
            read(region | fault, store())
    with pytest.raises(NotImplementedError):
        read(with_members(acceptances=[{"acceptance": "pick", "index": 0.0}]), store())
    with pytest.raises(NotImplementedError):
        read(with_members(acceptances=[1.0], target=None), store())
    refused = read(with_members(acceptances={"acceptance": "pick"}), store())
    assert refused.reasons == (Reason("request_incomplete"),)


INPUTS = WATER.parent


def stored(
    record: dict[str, JsonValue], field: str = "fluid.dynamic_viscosity"
) -> tuple[JsonValue, RecordStore]:
    """REQUEST for `field` of `record`, pinned by its hash recomputed, and a store holding it."""
    record = {**record, "content_hash": content_hash(record)}
    records = RecordStore()
    records.add("record", json.dumps(record).encode())
    pin = {name: record[name] for name in ("id", "version", "content_hash")}
    return with_members(target={"record": pin, "field": field}), records


def water() -> dict[str, JsonValue]:
    value: dict[str, JsonValue] = json.loads(WATER.read_text(encoding="utf-8"))
    return value


def with_field(name: str, field: JsonValue) -> dict[str, JsonValue]:
    """The water record with `field`, in the section `name` names, as its only field."""
    record = water()
    section, _, field_name = name.partition(".")
    record["body"] = {"sections": {section: {"fields": {field_name: field}}}}
    return record


def water_field() -> dict[str, JsonValue]:
    found: JsonValue = water()
    for step in ("body", "sections", "fluid", "fields", "dynamic_viscosity"):
        assert isinstance(found, dict)
        found = found[step]
    assert isinstance(found, dict)
    return found


@pytest.mark.parametrize(
    ("name", "form"),
    [
        ("fluid.dynamic_viscosity", "table"),
        ("biocompatibility.evidence", "evidence"),
    ],
)
def test_a_form_its_row_allows_whose_member_is_not_read_yet_raises_whatever_else_is_wrong(
    name: str, form: str
) -> None:
    """Its own member could add a reason, and every reason found is reported (`read_side_contract.md` section
    2 item 2): a table's unknown `scheme` beside a broken `unit` gives `unknown_token` too, once read."""
    field = {**water_field(), "form": form, form: {}}
    del field["label"]
    for broken in ({}, {"unit": None}, {"statistics": None, "label": "materica.fluid.newtonian.v1"}):
        with pytest.raises(NotImplementedError):
            read(*stored(with_field(name, {**field, **broken}), name))


@pytest.mark.parametrize(
    ("name", "form"),
    [
        ("bulk.density", "composition"),
        ("bulk.elemental_composition", "interval"),
        ("bulk.elemental_composition", "constant"),
        ("biocompatibility.evidence", "table"),
    ],
)
def test_a_form_its_row_does_not_allow_is_refused_with_every_shared_reason_and_not_its_member(
    name: str, form: str
) -> None:
    """The read neither uses nor returns the member of a form its row does not allow, so step 8 does not read
    it: a constant's `value` that is not a number adds nothing beside `form_not_registered`."""
    field = {**water_field(), "form": form, FORM_MEMBERS[form]: "not this form's member"}
    del field["label"]
    assert read(*stored(with_field(name, field), name)).reasons == (Reason("form_not_registered"),)
    refused = read(*stored(with_field(name, {**field, "unit": None}), name))
    assert {reason.code for reason in refused.reasons} == {"form_not_registered", "form_invalid"}


HYDROGEN: dict[str, JsonValue] = {"component": "element:H", "fraction": 0.102}
COMPOSITION: dict[str, JsonValue] = {
    "form": "composition",
    "unit": "1",
    "conditions": {},
    "statistics": water_field()["statistics"],
    "provenance": water_field()["provenance"],
}


@pytest.mark.parametrize(
    ("basis", "codes"),
    [
        ("mole_fraction", {"form_not_registered"}),
        ("volume_fraction", {"form_not_registered"}),
        ("mass_fraction", set[str]()),
        ("stated", {"form_invalid"}),
        ("bogus", {"unknown_token"}),
        (5.0, {"form_invalid"}),
    ],
)
def test_a_compositions_basis_is_checked_with_its_form_token(basis: JsonValue, codes: set[str]) -> None:
    """A basis of a composition's own list that the row does not allow is `form_not_registered`, as a form the
    row does not allow is (the S2 design's section 1.4, SQ43), beside every shared reason; any other basis is
    the composition's own member's to judge (`record_format.md` section 6, composition item 1)."""
    name = "bulk.elemental_composition"
    composition: dict[str, JsonValue] = {"basis": basis, "sum_rule": "partial", "components": [HYDROGEN]}
    field: dict[str, JsonValue] = {**COMPOSITION, "composition": composition}
    request, records = stored(with_field(name, field), name)
    assert isinstance(request, dict)
    request["requirement"] = {"want": "components"}
    # Past step 8, the read's one reason is step 10's for the temperature the request names and the field does
    # not state.
    found = {reason.code for reason in read(request, records).reasons} - {"condition_unstated"}
    assert found == codes
    statistics = {**COMPOSITION["statistics"], "n_specimens": -1.0}  # type: ignore[dict-item]
    request, records = stored(with_field(name, {**field, "statistics": statistics}), name)
    assert {reason.code for reason in read(request, records).reasons} == codes | {"form_invalid"}


STATED: dict[str, JsonValue] = {"basis": "stated"}
# Specimen facts that pass step 8 (None) or give these codes, each on the water field as its only fact.
FACTS: list[tuple[str, dict[str, JsonValue], tuple[str, ...] | None]] = [
    ("disease_and_treatment_state", {"token": "normal", **STATED}, None),
    ("disease_and_treatment_state", {"token": "diseased", "text": "fibrosis", **STATED}, None),
    ("disease_and_treatment_state", {"token": "treated", "text": "dialysis", **STATED}, None),
    ("disease_and_treatment_state", {"token": "normal", "text": "none", **STATED}, ("form_invalid",)),
    ("disease_and_treatment_state", {"token": "diseased", **STATED}, ("form_invalid",)),
    ("disease_and_treatment_state", {"token": "treated", **STATED}, ("form_invalid",)),
    ("disease_and_treatment_state", {"token": "remission", **STATED}, ("unknown_token",)),
    (
        "disease_and_treatment_state",
        {"token": "remission", "text": "since 2019", **STATED},
        ("unknown_token", "form_invalid"),
    ),
    ("post_mortem_interval", {"value": 60.0, "unit": "s", **STATED}, None),
    ("post_mortem_interval", {"value": 60.0, "unit": {"status": "unstated"}, **STATED}, ("unit_mismatch",)),
    ("post_mortem_interval", {"value": 1.0, "unit": "min", **STATED}, ("unit_mismatch",)),
    ("post_mortem_interval", {"value": 1.0, "unit": {"status": "approximate"}, **STATED}, ("unit_mismatch",)),
    ("post_mortem_interval", {"value": 1.0, "unit": 60.0, **STATED}, ("form_invalid",)),
    (
        "post_mortem_interval",
        {"value": 1.0, "unit": {"status": "unstated", "note": "x"}, **STATED},
        ("form_invalid",),
    ),
    ("donor_age", {"range": [1.0, 2.0], "unit": "a", **STATED}, ("unit_mismatch",)),
    ("donor_age", {"range": [1.0, 2.0], "unit": "s", **STATED}, None),
    ("mimics", {"text": "liver", **STATED}, None),
    ("mimics", {"text": "liver", "inferred_from": "Methods", **STATED}, None),
    ("mimics", {"text": "liver", "basis": "inferred", "inferred_from": "Methods"}, ("form_invalid",)),
    ("mimics", {"text": "liver", "basis": "guessed"}, ("unknown_token",)),
]


@pytest.mark.parametrize(("name", "fact", "codes"), FACTS)
def test_a_specimen_fact_takes_its_rows_shape_and_fixed_members(
    name: str, fact: dict[str, JsonValue], codes: tuple[str, ...] | None
) -> None:
    """A disease or treatment state's text is there exactly for `diseased` and `treated`; a basis its row
    fixes (`"basis": "stated"`) takes that token alone and leaves no `inferred_from` to name, so one there is
    ignored; and a fact's unit, which its row fixes too (`"unit": "s"`), is checked here only as a string or a
    status object, any token included, since step 9 alone compares it, and refuses another unit or any status
    object (maintainer, 2026-10-15)."""
    field: JsonValue = {**water_field(), "specimen": {name: fact}}
    if codes is None:
        assert past_step_9(read(*stored(with_field("fluid.dynamic_viscosity", field))))
    else:
        refused = read(*stored(with_field("fluid.dynamic_viscosity", field)))
        assert {reason.code for reason in refused.reasons} == set(codes)


def past_step_9(result: ReadResult) -> bool:
    """Whether steps 8 and 9 passed the read: step 10 then runs to its end, and gives `conditions`."""
    return result.conditions is not None


def test_a_read_whose_target_is_an_overlay_raises_rather_than_answer() -> None:
    overlay = json.loads((INPUTS / "water_overlay_fixture.json").read_text(encoding="utf-8"))
    with pytest.raises(NotImplementedError):
        read(*stored(overlay))


def test_a_request_keeps_only_the_members_its_shape_names() -> None:
    checked = ReadRequest.from_json(with_members(x_note=1.0, records=["a.json"]))
    assert isinstance(checked, ReadRequest)
    assert checked.target == MaterialRef("conformance/water_fixture", "2.0.0", PIN)
    expected = json.loads(json.dumps(REQUEST))
    expected["requirement"]["conditions"]["temperature"]["tolerance"]["value"] = 1.0
    assert checked.to_json() == expected


def with_member(place: tuple[str, ...], name: str, value: JsonValue = 1.0) -> dict[str, JsonValue]:
    """REQUEST as parsed JSON, with `name` set to `value` in the object at `place`."""
    request = with_members()
    parent: JsonValue = request
    for step in place:
        assert isinstance(parent, dict)
        parent = parent[step]
    assert isinstance(parent, dict)
    parent[name] = value
    return request


TEMPERATURE = ("requirement", "conditions", "temperature")
# A member one slip from one section 1 or `declarations.md` names at each place of a request, and the
# condition the place concerns.
SLIPS = [
    pytest.param((), "requirment", None, id="top"),
    pytest.param((), "record", None, id="top_records"),
    pytest.param((), "acceptance", None, id="top_acceptances"),
    pytest.param(("target",), "fields", None, id="target"),
    pytest.param(("target", "record"), "versions", None, id="target_record"),
    pytest.param(("requirement",), "wants", None, id="requirement"),
    pytest.param(("requirement",), "labels", None, id="requirement_refused_member"),
    pytest.param(("requirement",), "feild", None, id="requirement_declarations_field"),
    pytest.param(("operating_conditions", "temperature"), "units", "temperature", id="operating"),
    pytest.param(TEMPERATURE, "tolerances", "temperature", id="requirement_condition"),
    pytest.param(TEMPERATURE, "accepts", "temperature", id="requirement_condition_refused_member"),
    pytest.param(TEMPERATURE, "reasn", "temperature", id="requirement_condition_declarations_reason"),
    pytest.param(
        TEMPERATURE, "consequences", "temperature", id="requirement_condition_declarations_consequence"
    ),
    pytest.param((*TEMPERATURE, "tolerance"), "vaule", "temperature", id="tolerance"),
]


@pytest.mark.parametrize(("place", "name", "condition"), SLIPS)
def test_a_member_one_slip_from_a_named_one_is_refused_at_its_place(
    place: tuple[str, ...], name: str, condition: str | None
) -> None:
    refused = read(with_member(place, name), store())
    assert refused.reasons == (Reason("request_incomplete", condition),)


@pytest.mark.parametrize(("place", "name", "condition"), SLIPS)
def test_a_member_further_from_every_named_one_is_ignored(
    place: tuple[str, ...], name: str, condition: str | None
) -> None:
    assert read(with_member(place, f"x_{name}"), store()) == ABSENT


@pytest.mark.parametrize("field", ["fluid.surface_tension", "acoustic.sound_speed", "fluid.specimen"])
def test_a_field_the_vocabulary_does_not_register_is_refused(field: str) -> None:
    assert read(with_member(("target",), "field", field), store()).reasons == (Reason("request_incomplete"),)


@pytest.mark.parametrize("name", ["label", "represents", "population_level"])
def test_a_requirement_holding_a_declarations_member_is_refused(name: str) -> None:
    assert read(with_member(("requirement",), name, "x"), store()).reasons == (Reason("request_incomplete"),)


@pytest.mark.parametrize(
    ("place", "name"), [(("requirement",), "field"), (TEMPERATURE, "reason"), (TEMPERATURE, "consequence")]
)
def test_a_declarations_member_a_read_never_checks_is_ignored(place: tuple[str, ...], name: str) -> None:
    """`declarations.md` section 1 names a requirement's `field`, and a requirement condition's `reason` and
    `consequence`: a read ignores each, and refuses a member one slip from one (above)."""
    assert read(with_member(place, name, "fluid.dynamic_viscosity"), store()) == ABSENT


def test_a_result_reads_back_from_its_json() -> None:
    result = ReadResult(
        "not_met", (Reason("request_incomplete", "temperature", "below zero"),), ("hash_not_checked",)
    )
    assert ReadResult.from_json(result.to_json()) == result
    written = json.loads(json.dumps(result.to_json()))
    assert written["reasons"] == [
        {"code": "request_incomplete", "condition": "temperature", "detail": "below zero"}
    ]


def test_a_reason_given_twice_is_merged_with_both_details() -> None:
    (reason,) = merged(
        [Reason("request_incomplete", "temperature", "a"), Reason("request_incomplete", "temperature", "b")]
    )
    assert reason.detail == "a; b"


def test_the_worst_status_wins_and_none_is_met() -> None:
    assert worst([]) == "met"
    assert worst(["met", "unknown"]) == "unknown"
    assert worst(["unknown", "not_met", "met"]) == "not_met"
    assert VOCABULARY.reasons["no_pick"].status == "unknown"
    assert VOCABULARY.sections == {"bulk", "fluid", "magnetic", "biocompatibility"}


def test_a_store_sets_documents_aside_and_keeps_unreadable_sources_apart() -> None:
    records = RecordStore()
    records.add("manifest", b'{"document_type": "scene", "id": "conformance/a", "version": "1.0.0"}')
    records.add(
        "record",
        b'{"document_type": "x", "record_type": "material", "id": "conformance/a", "version": "1.0.0"}',
    )
    records.add("array", b"[]")
    records.add("bytes", b"\xff")
    assert [record.source for record in records.get("conformance/a", "1.0.0")] == ["record"]
    assert [source for source, _ in records.unparsed()] == ["array", "bytes"]
    assert records.list_records() == []


def claims_parameters(modules: list[ModuleType]) -> dict[str, object]:
    """The annotation of every `claims` parameter of a function or method defined in `modules`."""
    found: dict[str, object] = {}
    for module in modules:
        for _, member in inspect.getmembers(module):
            candidates: list[object] = list(vars(member).values()) if inspect.isclass(member) else [member]
            for candidate in candidates:
                function: object = getattr(candidate, "__func__", candidate)  # a classmethod's function
                if (
                    inspect.isfunction(function)
                    and function.__module__ == module.__name__
                    and "claims" in inspect.signature(function).parameters
                ):
                    found[function.__qualname__] = get_type_hints(function)["claims"]
    return found


CORE = [
    importlib.import_module(f"materica.core.{path.stem}")
    for path in sorted((Path(materica.__file__).parent / "core").glob("*.py"))
]


def test_each_claims_parameter_of_the_core_is_typed_by_the_suites() -> None:
    """So that a misspelt suite name does not type-check (S2a-2's review, L7)."""
    found = claims_parameters(CORE)
    assert {"form_problems", "_form", "read", "ReadRequest.from_json", "resolve_record"} <= found.keys()
    assert {name for name, hint in found.items() if hint != Collection[Suite]} == set()


def test_a_claims_parameter_typed_otherwise_is_found() -> None:
    module = ModuleType("loose")

    def loose(claims: Collection[str]) -> None:
        pass

    loose.__module__ = module.__name__
    module.loose = loose  # type: ignore[attr-defined]
    assert claims_parameters([module]) == {
        "test_a_claims_parameter_typed_otherwise_is_found.<locals>.loose": Collection[str]
    }


def test_a_label_is_judged_on_the_form_the_field_holds_and_on_no_form_where_it_holds_none() -> None:
    """S2a-2's review, L8: the row names a label for a field and its form, so a label beside a form token the
    reader does not know is refused for that form, and one beside a missing form is not judged on a form."""
    field = water_field()
    missing = read(
        *stored(with_field("fluid.dynamic_viscosity", {k: v for k, v in field.items() if k != "form"}))
    )
    assert missing.reasons == (Reason("form_invalid"),)
    assert "label" not in str(missing.reasons[0].detail)
    unknown = read(*stored(with_field("fluid.dynamic_viscosity", {**field, "form": "spline"})))
    details = {reason.code: str(reason.detail) for reason in unknown.reasons}
    assert details.keys() == {"unknown_token", "form_invalid"}
    assert "'spline', a form the reader does not know" in details["form_invalid"]
    composition = read(*stored(with_field("fluid.dynamic_viscosity", {**field, "form": "composition"})))
    assert {reason.code for reason in composition.reasons} == {"form_not_registered", "form_invalid"}
    assert "a field of form composition" in str(composition.reasons)


UNCERTAINTY: dict[str, JsonValue] = {
    "value": 0.02,
    "coverage_factor": 2.0,
    "coverage_probability": {"status": "unstated"},
    "distribution": "normal",
    "dof": {"status": "not_applicable"},
    "basis": "reported_uncertainty",
    "represents": "measurement",
    "precision_conditions": "repeatability",
}


def with_block(**members: JsonValue) -> dict[str, JsonValue]:
    statistics = water_field()["statistics"]
    assert isinstance(statistics, dict)
    return {**water_field(), "statistics": {**statistics, **members}}


def with_condition(name: str, condition: JsonValue) -> dict[str, JsonValue]:
    conditions = water_field()["conditions"]
    assert isinstance(conditions, dict)
    return {**water_field(), "conditions": {**conditions, name: condition}}


def with_fact(name: str, fact: JsonValue) -> dict[str, JsonValue]:
    return {**water_field(), "specimen": {name: fact}}


def unlabelled(**members: JsonValue) -> dict[str, JsonValue]:
    return {**{name: value for name, value in water_field().items() if name != "label"}, **members}


# The eleven rules S2a-2's review found no test checking (finding M1), each with a field that breaks it and
# the codes step 8 gives, and some with a field that keeps it, which passes step 8 (None). The label on a
# table, which no read reaches before S3, is `test_a_label_on_a_table_follows_its_rows_axis`.
RULES: list[tuple[str, dict[str, JsonValue], frozenset[str] | None]] = [
    (
        "a population level's within holds none alone of the statuses",
        with_block(
            represents="population", population_level={"level": "specimen", "within": {"status": "unstated"}}
        ),
        frozenset({"form_invalid"}),
    ),
    (
        "... and none passes",
        with_block(
            represents="population", population_level={"level": "specimen", "within": {"status": "none"}}
        ),
        None,
    ),
    (
        "an uncertainty's precision_conditions takes its tokens alone",
        with_block(relative_uncertainty={**UNCERTAINTY, "precision_conditions": "lab_to_lab"}),
        frozenset({"unknown_token"}),
    ),
    ("... and repeatability passes", with_block(relative_uncertainty=UNCERTAINTY), None),
    (
        "a constant's statistics takes withheld, never not_applicable",
        {**water_field(), "statistics": {"status": "not_applicable"}},
        frozenset({"form_invalid"}),
    ),
    (
        "a condition's basis takes stated or inferred",
        with_condition("temperature", {"value": 310.15, "unit": "K", "basis": "guessed"}),
        frozenset({"unknown_token"}),
    ),
    (
        "a fact's basis is no block's",
        with_fact("lot", {"text": "B-17", "basis": "reported_sd"}),
        frozenset({"form_invalid"}),
    ),
    (
        "a condition's status object refuses the members of either shape",
        with_condition("temperature", {"status": "unstated", "token": "apparent"}),
        frozenset({"form_invalid"}),
    ),
    (
        "a fact's token knows the conditions' tokens",
        with_fact("tissue_state", {"token": "tube", "basis": "stated"}),
        frozenset({"form_invalid"}),
    ),
    (
        "a condition's token knows the facts' tokens",
        with_condition("density_kind", {"token": "stock", "basis": "stated"}),
        frozenset({"form_invalid"}),
    ),
    (
        "a token condition's unit is a string or a status object",
        with_condition("measurement_geometry", {"token": "tube", "unit": 5.0, "basis": "stated"}),
        frozenset({"form_invalid"}),
    ),
    (
        "... which step 9 refuses",
        with_condition("measurement_geometry", {"token": "tube", "unit": "m", "basis": "stated"}),
        frozenset({"unit_mismatch"}),
    ),
    (
        "a fact's unit takes any status token at step 8, which step 9 refuses",
        with_fact(
            "post_mortem_interval", {"value": 60.0, "unit": {"status": "approximate"}, "basis": "stated"}
        ),
        frozenset({"unit_mismatch"}),
    ),
    (
        "the row's label beside a form the reader does not know",
        {**water_field(), "form": "spline"},
        frozenset({"unknown_token", "form_invalid"}),
    ),
    ("a form the reader does not know, alone", unlabelled(form="spline"), frozenset({"unknown_token"})),
    (
        "beside a form the reader does not know, every form's own member is named",
        unlabelled(form="spline", intervals={}),
        frozenset({"unknown_token", "form_invalid"}),
    ),
]


@pytest.mark.parametrize(("rule", "field", "codes"), RULES, ids=[rule for rule, _, _ in RULES])
def test_each_rule_the_review_found_untested(
    rule: str, field: dict[str, JsonValue], codes: frozenset[str] | None
) -> None:
    if codes is None:
        assert past_step_9(read(*stored(with_field("fluid.dynamic_viscosity", field))))
    else:
        refused = read(*stored(with_field("fluid.dynamic_viscosity", field)))
        assert {reason.code for reason in refused.reasons} == codes


TEMPERATURE_STATED: dict[str, JsonValue] = {"value": 310.15, "unit": "K"}
# Places a record names `basis` at, each with the field holding a token there.
BASES: list[tuple[str, Callable[[str], dict[str, JsonValue]]]] = [
    ("a condition's", lambda basis: with_condition("temperature", {**TEMPERATURE_STATED, "basis": basis})),
    ("a fact's", lambda basis: with_fact("tissue_state", {"token": "in_vivo", "basis": basis})),
    ("a statistics block's", lambda basis: with_block(basis=basis)),
]


@pytest.mark.parametrize(("place", "field"), BASES, ids=[place for place, _ in BASES])
def test_a_records_basis_implied_is_a_token_the_reader_knows_that_no_row_allows(
    place: str, field: Callable[[str], dict[str, JsonValue]]
) -> None:
    """A result's condition entry gives the basis `implied` (`read_side_contract.md` section 2 item 6), so the
    reader knows it for a member named `basis`: in a record it is `form_invalid`, as one the reader knows
    for no `basis` is `unknown_token` (section 3, step 8). S2a-4's review, L4."""
    for basis, code in [("implied", "form_invalid"), ("x_unknown", "unknown_token")]:
        refused = read(*stored(with_field("fluid.dynamic_viscosity", field(basis))))
        assert [reason.code for reason in refused.reasons] == [code], basis


@pytest.mark.parametrize(("axis", "allowed"), [("shear_rate", False), ("temperature", True)])
def test_a_label_on_a_table_follows_its_rows_axis(axis: str, allowed: bool) -> None:
    """Step 8's shared check of a field, which a read reaches for a table only once S3 reads tables."""
    field: dict[str, JsonValue] = {**water_field(), "form": "table", "table": {"axis": axis}}
    found = value_shapes.field_problems(field, VOCABULARY.fields["fluid.dynamic_viscosity"], "table")
    assert [reason.code for reason in found] == ([] if allowed else ["form_invalid"])


def test_withheld_is_given_beside_a_shared_refusal() -> None:
    """Each step makes all its checks (`read_side_contract.md` section 2 item 2): a withheld value beside a
    broken unit gives both. HP3 meets the pair only on its rarer two-fault draws, so the review's mutant that
    drops `withheld` there survived it in one run of six."""
    withheld: dict[str, JsonValue] = {
        **water_field(),
        "value": {"status": "withheld"},
        "statistics": {"status": "withheld"},
    }
    alone = read(*stored(with_field("fluid.dynamic_viscosity", withheld)))
    assert {reason.code for reason in alone.reasons} == {"withheld"}
    both = read(*stored(with_field("fluid.dynamic_viscosity", {**withheld, "unit": None})))
    assert {reason.code for reason in both.reasons} == {"withheld", "form_invalid"}


# A status object holding a token the reader does not know, broken in each way `provenance.md` section 1 item
# 5 names, and by a slip (section 10): it is read for nothing else, so its token gives no `unknown_token`.
UNKNOWN_STATUS = "x_unknown"
BROKEN_STATUSES: list[tuple[str, dict[str, JsonValue]]] = [
    ("beside a member where S is a number", with_block(sd={"status": UNKNOWN_STATUS, "note": 1.0})),
    ("beside a member S defines", with_block(relative_uncertainty={"status": UNKNOWN_STATUS, "value": 1.0})),
    ("with a reason that is no string", with_block(sd={"status": UNKNOWN_STATUS, "reason": 1.0})),
    ("beside a slip of reason", with_block(relative_uncertainty={"status": UNKNOWN_STATUS, "reasons": "x"})),
    ("as a condition", with_condition("temperature", {"status": UNKNOWN_STATUS, "unit": "K"})),
    ("as a fact", with_fact("lot", {"status": UNKNOWN_STATUS, "text": "B-17"})),
]


@pytest.mark.parametrize(("place", "field"), BROKEN_STATUSES, ids=[place for place, _ in BROKEN_STATUSES])
def test_a_status_object_that_breaks_its_shape_gives_no_reason_for_its_token(
    place: str, field: dict[str, JsonValue]
) -> None:
    refused = read(*stored(with_field("fluid.dynamic_viscosity", field)))
    assert [reason.code for reason in refused.reasons] == ["form_invalid"]


def test_an_unknown_status_token_alone_is_unknown_token() -> None:
    """The control: the same token, in an object that keeps its shape, gives its own reason."""
    kept = with_block(relative_uncertainty={"status": UNKNOWN_STATUS, "reason": "not stated"})
    refused = read(*stored(with_field("fluid.dynamic_viscosity", kept)))
    assert [reason.code for reason in refused.reasons] == ["unknown_token"]


DERIVED: dict[str, JsonValue] = {
    "origin": "derived",
    "derivation": {
        "method": "arrhenius_mixing",
        "inputs": [
            {
                "record": {"id": "conformance/a", "version": "1.0.0", "content_hash": "sha256:" + "0" * 64},
                "field": "fluid.dynamic_viscosity",
            }
        ],
        "assumptions": [],
        "input_specimens": [
            {"input": 0.0, "specimen": {"post_mortem_interval": {"value": 60.0, "unit": "min", **STATED}}}
        ],
    },
}
KELVIN_SIGN = chr(0x212A)
# Units step 9 compares (`read_side_contract.md` section 3, step 9), each changed in the water field, and the
# reasons, `(code, condition)`, it then gives; none where the field passes step 9.
UNITS: list[tuple[str, dict[str, JsonValue], set[tuple[str, str | None]] | None]] = [
    ("the field's unit as registered", water_field(), None),
    ("the field's unit with a space", {**water_field(), "unit": "Pa s"}, {("unit_mismatch", None)}),
    ("the field's unit in capitals", {**water_field(), "unit": "PA.S"}, {("unit_mismatch", None)}),
    (
        "a status object where a string is registered",
        {**water_field(), "unit": {"status": "unstated"}},
        {("unit_mismatch", None)},
    ),
    (
        "a condition's unit in another code",
        with_condition("temperature", {"value": 37.0, "unit": "Cel", "basis": "stated"}),
        {("unit_mismatch", "temperature")},
    ),
    (
        "a condition's unit as the Kelvin sign",
        with_condition("temperature", {"value": 310.15, "unit": KELVIN_SIGN, "basis": "stated"}),
        {("unit_mismatch", "temperature")},
    ),
    (
        "a condition's unit as a status object",
        with_condition("temperature", {"value": 310.15, "unit": {"status": "unstated"}, "basis": "stated"}),
        {("unit_mismatch", "temperature")},
    ),
    (
        "a plus_minus entry's unit, once with its condition's",
        with_condition(
            "temperature",
            {
                "value": 310.15,
                "unit": "Cel",
                "plus_minus": [{"stated_as": "bound", "value": 0.5, "unit": "Cel"}],
                "basis": "stated",
            },
        ),
        {("unit_mismatch", "temperature")},
    ),
    (
        "a plus_minus entry's unit alone",
        with_condition(
            "temperature",
            {
                "value": 310.15,
                "unit": "K",
                "plus_minus": [{"stated_as": "sd", "value": 0.5, "unit": {"status": "unstated"}}],
                "basis": "stated",
            },
        ),
        {("unit_mismatch", "temperature")},
    ),
    (
        "a unit on a token condition",
        with_condition("measurement_geometry", {"token": "bulk", "unit": "1", "basis": "stated"}),
        {("unit_mismatch", "measurement_geometry")},
    ),
    (
        "the field's unit and a condition's: one reason each",
        {**with_condition("shear_rate", {"value": 1.0, "unit": "s-1", "basis": "stated"}), "unit": "Pa*s"},
        {("unit_mismatch", None), ("unit_mismatch", "shear_rate")},
    ),
    (
        "a condition the reader does not know, compared with nothing",
        with_condition("pressure", {"value": 1.0, "unit": "bar", "basis": "stated"}),
        None,
    ),
    (
        "a condition held as a status object",
        with_condition("temperature", {"status": "unstated", "reason": "no unit given either"}),
        None,
    ),
    (
        "a field's fact in minutes",
        with_fact("post_mortem_interval", {"value": 1.0, "unit": "min", **STATED}),
        {("unit_mismatch", None)},
    ),
    (
        "a field's fact in seconds",
        with_fact("donor_age", {"range": [1.0e9, 2.0e9], "unit": "s", **STATED}),
        None,
    ),
    ("a field's fact as a status object", with_fact("donor_age", {"status": "unstated"}), None),
    (
        "a derived value's input fact in minutes",
        {**water_field(), "provenance": DERIVED},
        {("unit_mismatch", None)},
    ),
    (
        "an input fact in minutes where the origin is not derived, which step 8 does not check",
        {**water_field(), "provenance": {**DERIVED, "origin": "measured_by_contributor"}},
        None,
    ),
]


@pytest.mark.parametrize(("units", "field", "reasons"), UNITS, ids=[units for units, _, _ in UNITS])
def test_step_9_compares_each_unit_with_the_one_registered_for_it(
    units: str, field: dict[str, JsonValue], reasons: set[tuple[str, str | None]] | None
) -> None:
    """Code point for code point, a status object never equal to a string, each reason once with its
    condition; a field that passes goes on to step 10."""
    if reasons is None:
        assert past_step_9(read(*stored(with_field("fluid.dynamic_viscosity", field))))
        return
    result = read(*stored(with_field("fluid.dynamic_viscosity", field)))
    assert result.status == "not_met"
    assert {(reason.code, reason.condition) for reason in result.reasons} == reasons
    assert len(result.reasons) == len(reasons)


@pytest.mark.parametrize(
    ("fact", "reasons"),
    [
        ({"value": 60.0, "unit": "s", **STATED}, None),
        ({"value": 60.0, "unit": {"status": "not_applicable"}, **STATED}, {("unit_mismatch", None)}),
    ],
)
def test_step_9_compares_a_section_facts_unit_for_every_field_of_the_section(
    fact: dict[str, JsonValue], reasons: set[tuple[str, str | None]] | None
) -> None:
    record = water()
    section: dict[str, JsonValue] = {
        "specimen": {"post_mortem_interval": fact},
        "fields": {"dynamic_viscosity": water_field()},
    }
    record["body"] = {"sections": {"fluid": section}}
    if reasons is None:
        assert past_step_9(read(*stored(record)))
        return
    assert {(reason.code, reason.condition) for reason in read(*stored(record)).reasons} == reasons


def test_what_a_step_before_found_is_taken_as_found_and_anything_else_raises() -> None:
    """`value_shapes.an_object` and `a_list`, the pair steps 8 to 10 share: a defect of the core raises."""
    found: JsonValue = {"a": [1.0]}
    assert value_shapes.an_object(found) is found
    assert value_shapes.a_list(found["a"]) is found["a"]
    with pytest.raises(TypeError):
        value_shapes.an_object(found["a"])
    with pytest.raises(TypeError):
        value_shapes.a_list(found)


def test_a_field_unit_registered_as_a_status_object_takes_its_token_whatever_its_reason() -> None:
    """`biocompatibility.evidence`'s unit is `{"status": "not_applicable"}` (`record_format.md` section 4.2):
    step 9's comparison, apart from evidence's own member, which S2b-2 reads."""
    from materica.core.fields import same_unit

    registered = VOCABULARY.fields["biocompatibility.evidence"].unit
    assert same_unit({"status": "not_applicable", "reason": "a list of reports"}, registered)
    assert not same_unit({"status": "unstated"}, registered)
    assert not same_unit({"status": "bogus"}, registered)
    assert not same_unit("not_applicable", registered)
    assert same_unit("Pa.s", "Pa.s")
    assert not same_unit("Pa.s" + chr(0x200B), "Pa.s")
    assert not same_unit({"status": "unstated"}, "Pa.s")


IMPLIED: dict[str, JsonValue] = {
    "acceptance": "implied_condition",
    "record": {"id": "conformance/water_fixture", "version": "2.0.0", "content_hash": PIN},
    "field": "fluid.dynamic_viscosity",
    "fact": "tissue_state",
    "token": "in_vivo",
    "implies": {"temperature": {"value": 310.15, "unit": "K"}, "density_kind": {"token": "matrix"}},
    "reason": "body temperature in vivo",
}


def implied_with(**members: JsonValue) -> JsonValue:
    """REQUEST with one implied condition, `members` changed in it, None removing one."""
    acceptance: dict[str, JsonValue] = {
        name: value for name, value in {**IMPLIED, **members}.items() if value is not None
    }
    return with_members(acceptances=[acceptance])


# Implied conditions at step 0 (`read_side_contract.md` section 1), beyond the PR-330 arms: what is refused,
# with the condition it concerns, and what is ignored.
IMPLIED_AT_STEP_0: list[tuple[str, JsonValue, set[tuple[str, str | None]]]] = [
    ("implies not an object", implied_with(implies=[]), {("request_incomplete", None)}),
    (
        "a value that is not an object",
        implied_with(implies={"temperature": 310.15, "density_kind": {"token": "matrix"}}),
        {("request_incomplete", "temperature")},
    ),
    ("no implies", implied_with(implies=None), {("request_incomplete", None)}),
    ("no fact", implied_with(fact=None), {("request_incomplete", None)}),
    ("a field off the pattern", implied_with(field="viscosity"), {("request_incomplete", None)}),
    ("a slip beside its members", implied_with(facts="tissue_state"), {("request_incomplete", None)}),
    ("a slip of the basis a read ignores", implied_with(bases="x"), {("request_incomplete", None)}),
    (
        "a numeric value without its unit",
        implied_with(implies={"temperature": {"value": 310.15}}),
        {("request_incomplete", "temperature")},
    ),
    (
        "a numeric value in another unit",
        implied_with(implies={"shear_rate": {"value": 1.0, "unit": "s-1"}}),
        {("request_unit_mismatch", "shear_rate")},
    ),
    (
        "a token for a numeric condition",
        implied_with(implies={"temperature": {"token": "matrix"}}),
        {("request_incomplete", "temperature")},
    ),
    (
        "a value for a token condition",
        implied_with(implies={"density_kind": {"value": 1.0, "unit": "1"}}),
        {("request_incomplete", "density_kind")},
    ),
    (
        "a status object for a token condition",
        implied_with(implies={"density_kind": {"status": "unstated"}}),
        {("request_incomplete", "density_kind")},
    ),
    (
        "a token beside a numeric value, outside its row",
        implied_with(implies={"temperature": {"value": 310.15, "unit": "K", "token": "matrix"}}),
        {("request_incomplete", "temperature")},
    ),
    (
        "a slip of a token beside a numeric value",
        implied_with(implies={"temperature": {"value": 310.15, "unit": "K", "tokens": "matrix"}}),
        {("request_incomplete", "temperature")},
    ),
    (
        "a unit beside a token",
        implied_with(implies={"density_kind": {"token": "matrix", "unit": "K"}}),
        {("request_incomplete", "density_kind")},
    ),
    (
        "a range beside a token",
        implied_with(implies={"density_kind": {"token": "matrix", "range": [1.0, 2.0]}}),
        {("request_incomplete", "density_kind")},
    ),
    (
        "a slip of a value beside a token",
        implied_with(implies={"density_kind": {"token": "matrix", "valeu": 1.0}}),
        {("request_incomplete", "density_kind")},
    ),
    (
        "a slip of a status object's reason in a value",
        implied_with(implies={"temperature": {"value": 310.15, "unit": "K", "reasons": "x"}}),
        {("request_incomplete", "temperature")},
    ),
    (
        "two faults in two conditions",
        implied_with(implies={"temperature": {"range": [2.0, 1.0], "unit": "K"}, "pressure": {}}),
        {("request_incomplete", "temperature"), ("request_incomplete", "pressure")},
    ),
]


@pytest.mark.parametrize(
    ("fault", "request_value", "reasons"), IMPLIED_AT_STEP_0, ids=[fault for fault, _, _ in IMPLIED_AT_STEP_0]
)
def test_an_implied_condition_that_breaks_its_shape_is_refused_at_step_0(
    fault: str, request_value: JsonValue, reasons: set[tuple[str, str | None]]
) -> None:
    check_refused_at_step_0(request_value, reasons)


def check_refused_at_step_0(request_value: JsonValue, reasons: set[tuple[str, str | None]]) -> None:
    refused = read(request_value, store())
    assert refused.status == "not_met"
    assert {(reason.code, reason.condition) for reason in refused.reasons} == reasons


@pytest.mark.parametrize(
    "request_value",
    [
        pytest.param(implied_with(), id="as_given"),
        pytest.param(implied_with(basis="a datasheet", x_note=1.0), id="its_basis_and_an_unknown_member"),
        pytest.param(
            implied_with(implies={"temperature": {"value": 310.15, "unit": "K", "basis": "stated"}}),
            id="a_basis_in_a_value",
        ),
        pytest.param(
            implied_with(implies={"temperature": {"value": 310.15, "unit": "K", "reason": "x"}}),
            id="a_reason_in_a_value",
        ),
        pytest.param(
            implied_with(implies={"density_kind": {"token": "matrix", "inferred_from": "x"}}),
            id="an_inferred_from_beside_a_token",
        ),
        pytest.param(implied_with(record=None, region="lumen"), id="at_a_region"),
        pytest.param(implied_with(record="a reference of no shape"), id="at_no_reference"),
        pytest.param(implied_with(implies={}), id="implying_nothing"),
        pytest.param(implied_with(reason=None), id="without_its_reason"),
    ],
)
def test_an_implied_condition_that_keeps_its_shape_passes_step_0(request_value: JsonValue) -> None:
    """The record is version 2.0.0, which the store does not hold: the read goes on to step 1."""
    assert read(request_value, store()) == ABSENT


def test_an_acceptance_of_another_kind_raises_whatever_else_the_request_holds() -> None:
    """S2b-2 reads the other kinds and refuses a kind a read does not take (section 1)."""
    others: list[JsonValue] = [
        {"acceptance": "nominal", "value": 1.0},
        {"acceptance": "waiver"},
        1.0,
        {"acceptance": "implied"},
    ]
    for other in others:
        with pytest.raises(NotImplementedError):
            read(with_members(acceptances=[IMPLIED, other]), store())
        with pytest.raises(NotImplementedError):
            read(with_members(acceptances=[other], target=None), store())


def test_a_request_keeps_its_implied_conditions_with_the_members_their_shape_names() -> None:
    checked = ReadRequest.from_json(implied_with(x_note=1.0, basis="a datasheet"))
    assert isinstance(checked, ReadRequest)
    (implied,) = checked.implied
    assert implied.index == 0
    assert checked.to_json().get("acceptances") == [
        {
            "acceptance": "implied_condition",
            "record": IMPLIED["record"],
            "field": "fluid.dynamic_viscosity",
            "fact": "tissue_state",
            "token": "in_vivo",
            "implies": {"temperature": {"value": 310.15, "unit": "K"}, "density_kind": {"token": "matrix"}},
        }
    ]


def test_a_read_returns_the_implied_conditions_it_applied_outside_its_json() -> None:
    """A field in vivo with no temperature, read at 330 K: the implied 310.15 K fills it and is outside."""
    conditions: dict[str, JsonValue] = {"shear_rate": {"status": "unstated"}}
    field: dict[str, JsonValue] = {
        **water_field(),
        "conditions": conditions,
        "specimen": {"tissue_state": {"token": "in_vivo", **STATED}},
    }
    request, records = stored(with_field("fluid.dynamic_viscosity", field))
    assert isinstance(request, dict)
    target = request["target"]
    assert isinstance(target, dict)
    acceptance: dict[str, JsonValue] = {**IMPLIED, "record": target["record"]}
    request["acceptances"] = [acceptance]
    request["operating_conditions"] = {"temperature": {"value": 330.0, "unit": "K"}}
    result = read(request, records)
    assert set(result.reasons) == {
        Reason("condition_outside", "temperature"),
        Reason("condition_unstated", "shear_rate"),
        Reason("condition_unchecked", "density_kind"),
    }
    assert result.applied == (0,)
    assert "applied" not in result.to_json()
    assert ReadResult.from_json(result.to_json()) == result


# An implied condition located elsewhere (`read_side_contract.md` section 1): one naming another field,
# another record (another version or content hash), a region beside the record, an interval or no location
# is checked and not applied. Each implies a shear rate the record leaves unstated, beside a temperature
# outside its tolerance, which ends the read at step 10 so that its entries are returned: applied, the shear
# rate would be `condition_unchecked`, the request giving it no tolerance.
ELSEWHERE = (
    "another_field",
    "another_version",
    "another_content_hash",
    "a_region_beside_the_record",
    "an_interval",
    "no_location",
)
AT_THE_READ = "at_the_read"


def implying_a_shear_rate(where: str) -> tuple[JsonValue, RecordStore]:
    """A request at 330 K for a water field in vivo, its implied condition `AT_THE_READ` or at a location
    `ELSEWHERE`."""
    assert where in (AT_THE_READ, *ELSEWHERE)
    field: dict[str, JsonValue] = {
        **water_field(),
        "specimen": {"tissue_state": {"token": "in_vivo", **STATED}},
    }
    request, records = stored(with_field("fluid.dynamic_viscosity", field))
    assert isinstance(request, dict)
    target = request["target"]
    assert isinstance(target, dict)
    pin = target["record"]
    assert isinstance(pin, dict)
    acceptance: dict[str, JsonValue] = {
        **IMPLIED,
        "record": dict(pin),
        "implies": {"shear_rate": {"value": 100.0, "unit": "1/s"}},
    }
    if where == "another_field":
        acceptance["field"] = "bulk.density"
    elif where == "another_version":
        acceptance["record"] = {**pin, "version": "9.0.0"}
    elif where == "another_content_hash":
        acceptance["record"] = {**pin, "content_hash": "sha256:" + "f" * 64}
    elif where == "a_region_beside_the_record":
        acceptance["region"] = "lumen"
    elif where == "an_interval":
        del acceptance["record"]
        acceptance["interval"] = 0.0
    elif where == "no_location":
        del acceptance["record"]
    request["acceptances"] = [acceptance]
    request["operating_conditions"] = {"temperature": {"value": 330.0, "unit": "K"}}
    return request, records


def check_located_elsewhere(where: str) -> None:
    result = read(*implying_a_shear_rate(where))
    assert set(result.reasons) == {
        Reason("condition_outside", "temperature"),
        Reason("condition_unstated", "shear_rate"),
    }, where
    assert result.conditions is not None
    assert {entry.name: (entry.status, entry.record) for entry in result.conditions} == {
        "temperature": ("not_met", {"value": 310.15, "unit": "K", **STATED}),
        "shear_rate": ("unknown", {"status": "unstated"}),
    }, where
    assert result.applied == (), where


@pytest.mark.parametrize("where", ELSEWHERE)
def test_an_implied_condition_located_elsewhere_leaves_its_condition_unstated(where: str) -> None:
    check_located_elsewhere(where)


def test_an_implied_condition_at_the_reads_own_location_fills_its_condition() -> None:
    """The control: the same implied condition, located at the read, is applied."""
    result = read(*implying_a_shear_rate(AT_THE_READ))
    assert set(result.reasons) == {
        Reason("condition_outside", "temperature"),
        Reason("condition_unchecked", "shear_rate"),
    }
    assert result.applied == (0,)
    with pytest.raises(AssertionError):
        check_located_elsewhere(AT_THE_READ)


# Steps 11 to 13 for a constant, and the result (`read_side_contract.md` sections 2, 3 and 6).

SHEAR_RATE: dict[str, JsonValue] = {"range": [10.0, 1000.0], "unit": "1/s", **STATED}
MET_REQUEST: dict[str, JsonValue] = {
    "operating_conditions": {
        "temperature": {"value": 310.15, "unit": "K"},
        "shear_rate": {"value": 100.0, "unit": "1/s"},
    },
    "requirement": {
        "want": "value",
        "conditions": {
            "temperature": {"tolerance": {"value": 1.0, "unit": "K"}},
            "shear_rate": {"tolerance": {"value": 0.0, "unit": "1/s"}},
        },
    },
}


def met_field(**members: JsonValue) -> dict[str, JsonValue]:
    """The water constant, its every condition stated and met by `MET_REQUEST`, with `members` set."""
    field = water_field()
    conditions = field["conditions"]
    assert isinstance(conditions, dict)
    conditions["shear_rate"] = dict(SHEAR_RATE)
    return field | members


def read_met(
    field: JsonValue, *, want: str = "value", claims: Collection[Suite] = ("plain_read", "hash")
) -> ReadResult:
    request, records = stored(with_field("fluid.dynamic_viscosity", field))
    assert isinstance(request, dict)
    request.update(copy.deepcopy(MET_REQUEST))
    requirement = request["requirement"]
    assert isinstance(requirement, dict)
    requirement["want"] = want
    return read(request, records, claims=claims)


def test_a_met_constant_returns_its_value_and_the_members_beside_it() -> None:
    result = read_met(met_field())
    assert (result.status, result.reasons) == ("met", ())
    written = json.loads(json.dumps(result.to_json()))
    assert list(written) == [
        "status", "reasons", "value", "unit", "conditions", "specimen", "statistics", "provenance", "labels"
    ]  # fmt: skip
    assert written["value"] == 0.000692
    assert written["unit"] == "Pa.s"
    assert written["specimen"] == {}
    assert written["provenance"] == {
        "origin": "measured_by_contributor",
        "review": {
            "status": "not_checked",
            "reason": "conformance fixture: illustrative values, not a measurement",
        },
    }
    assert written["labels"] == ["materica.fluid.newtonian.v1"]


@pytest.mark.parametrize("held", [{"status": "withheld"}, {"status": "withheld", "reason": "licensed"}])
def test_a_statistics_block_held_as_a_status_object_is_returned_as_one(held: dict[str, JsonValue]) -> None:
    """`provenance.md` section 1 item 4: a reader returns a status as a status, here the one a constant's
    statistics row allows. Fuzz target 4 found it returned as an empty block, against the reference model."""
    written = json.loads(json.dumps(read_met(met_field(statistics=held)).to_json()))
    assert written["statistics"] == held


RESULT_SCHEMA = validator("read_result.json")
NOT_CHECKED: JsonValue = {"status": "not_checked"}
# A review a status object stands for, and what a read returns of it (`provenance.md` section 2 item 6): as
# found where it keeps its shape (section 1 item 5), else `not_checked`, since a review never refuses.
NOT_CHECKED_REVIEWS = [
    pytest.param(
        {"status": "not_checked", "reason": "r"}, {"status": "not_checked", "reason": "r"}, id="as_found"
    ),
    pytest.param(
        {"status": "not_checked", "reason": "r", "x_note": 1.0},
        {"status": "not_checked", "reason": "r"},
        id="an_unknown_member_left_out",
    ),
    pytest.param({"status": "not_checked", "reason": 5.0}, NOT_CHECKED, id="a_reason_not_a_string"),
    pytest.param({"status": "not_checked", "reason": None}, NOT_CHECKED, id="a_reason_null"),
    pytest.param(
        {"status": "not_checked", "reason": "r", "result": "reviewed"}, NOT_CHECKED, id="beside_a_result"
    ),
    pytest.param(
        {"status": "not_checked", "reason": "r", "reviewer": "a"}, NOT_CHECKED, id="beside_a_reviewer"
    ),
]


@pytest.mark.parametrize(("review", "returned"), NOT_CHECKED_REVIEWS)
def test_a_not_checked_review_is_returned_as_found_only_where_it_keeps_its_shape(
    review: JsonValue, returned: JsonValue
) -> None:
    """S2a-4's review, L5 (a `reason` that is no string was returned as found, and the result then failed
    `read_result.json`) and L3's M25 (a `reason` kept beside a `result`)."""
    field = met_field()
    field["provenance"] = {**an_object(field["provenance"]), "review": review}
    written = json.loads(json.dumps(read_met(field).to_json()))
    assert written["provenance"]["review"] == returned
    assert RESULT_SCHEMA(written) == []


DERIVED_OFF_PATTERN: dict[str, JsonValue] = {
    "origin": "derived",
    "review": {"status": "not_checked"},
    "derivation": {
        "method": "a conversion",
        "inputs": [
            {
                "record": {"id": "Not An Id", "version": "1.0", "content_hash": "sha256:x"},
                "field": "fluid.density",
            }
        ],
        "assumptions": [],
        "input_specimens": [{"input": 0.0, "specimen": {}}],
    },
}
SITE: dict[str, JsonValue] = {"uberon": "UBERON:liver", "label": "liver", "basis": "stated"}


def test_a_result_of_a_record_the_writer_refuses_validates_where_the_read_takes_it() -> None:
    """S2a-4's review, L1: step 8 checks an anatomical site's `uberon` and a derivation input's pinned record
    as strings alone (RC-039; `provenance.md` section 5), so a read takes both off their writer patterns, and
    `read_result.json` takes the result. It keeps the writer's closed structure: a member no shape defines,
    which a result never holds, inside a returned fact or input is refused."""
    field = met_field(specimen={"anatomical_site": SITE}, provenance=DERIVED_OFF_PATTERN)
    written = json.loads(json.dumps(read_met(field).to_json()))
    assert written["specimen"] == {"anatomical_site": SITE}
    assert written["provenance"]["derivation"]["inputs"][0]["record"]["id"] == "Not An Id"
    assert RESULT_SCHEMA(written) == []
    unknown = copy.deepcopy(written)
    unknown["specimen"]["anatomical_site"]["x_note"] = 1.0
    assert RESULT_SCHEMA(unknown) != []
    unknown = copy.deepcopy(written)
    unknown["provenance"]["derivation"]["inputs"][0]["record"]["x_note"] = 1.0
    assert RESULT_SCHEMA(unknown) != []


def test_a_want_the_constant_cannot_give_keeps_the_conditions_and_labels_but_returns_no_value() -> None:
    for want in ("bounds", "components", "evidence"):
        result = read_met(met_field(), want=want)
        assert (result.status, result.reasons) == ("not_met", (Reason("want_mismatch"),)), want
        written = json.loads(json.dumps(result.to_json()))
        assert set(written) == {"status", "reasons", "conditions", "labels"}, want
        assert "materica.fluid.newtonian.v1" in written["labels"], want


def test_the_suite_s_wants_on_a_constant_give_want_mismatch_but_fit_on_a_fitted_one_waits() -> None:
    """`read_side_contract.md` section 6: reference data on any other form, and a fit or a coverage on a field
    without one, give `want_mismatch`; reading a fitted field's fit record is the suite's, not built yet."""
    claims: tuple[Suite, ...] = ("plain_read", "hash", "fits_and_reference_data")
    for want in ("reference_data", "fit", "coverage"):
        result = read_met(met_field(), want=want, claims=claims)
        assert result.reasons == (Reason("want_mismatch"),), want
    with pytest.raises(NotImplementedError):
        read_met(met_field(fit={"model": "a fit record"}), want="fit", claims=claims)
    assert read_met(met_field(fit={"model": "a fit record"}), claims=claims).value == 0.000692


def test_a_result_writes_numbers_as_stored_and_each_count_and_index_as_an_integer() -> None:
    """`-0` stays `-0` (PR-047), never RFC 8785's form; a statistics block's counts and a derivation's input
    indexes are integers (the code design's rule 5)."""
    field = met_field(value=-0.0)
    statistics = field["statistics"]
    assert isinstance(statistics, dict)
    statistics["n_specimens"] = 3.0
    statistics["n_donors"] = -0.0
    field["provenance"] = DERIVED_INPUTS
    text = json.dumps(read_met(field).to_json())
    written = json.loads(text)
    assert '"value": -0.0' in text
    assert written["statistics"]["n_specimens"] == 3
    assert type(written["statistics"]["n_specimens"]) is int
    assert type(written["statistics"]["n_donors"]) is int
    inputs = written["provenance"]["derivation"]["input_specimens"]
    assert [entry["input"] for entry in inputs] == [0, 1]
    assert all(type(entry["input"]) is int for entry in inputs)


def test_a_result_shares_nothing_with_the_record_or_with_its_own_json() -> None:
    """The code design's rule 6: a member returned is a deep copy, and so is each result's JSON."""
    result = read_met(met_field())
    first = cast(dict[str, Any], result.to_json())
    first["statistics"]["central"] = "changed"
    first["provenance"]["review"]["status"] = "changed"
    again = cast(dict[str, Any], result.to_json())
    assert again["statistics"]["central"] == "stated"
    assert again["provenance"]["review"]["status"] == "not_checked"
    assert read_met(met_field()).to_json() == result.to_json()
    assert ReadResult.from_json(result.to_json()) == result


def test_a_derivation_returned_shares_nothing_with_the_stored_record() -> None:
    """Rule 6 through the Python API: a consumer that changes the derivation a result holds, the field's or
    an alternative's, changes no later read of the same store (S2a-4's review, L3's M51)."""
    alternatives: list[JsonValue] = [met_field(provenance=DERIVED_INPUTS)] * 2
    fields: list[JsonValue] = [met_field(provenance=DERIVED_INPUTS), {"alternatives": alternatives}]
    for field in fields:
        request, records = stored(with_field("fluid.dynamic_viscosity", field))
        assert isinstance(request, dict)
        request.update(copy.deepcopy(MET_REQUEST))
        first = read(request, records)
        reads = first.alternative_values or (first,)
        for each in reads:
            assert each.provenance is not None
            assert each.provenance.derivation is not None
            each.provenance.derivation["method"] = "changed"
            an_object(a_list(each.provenance.derivation["inputs"])[0])["field"] = "changed"
        later = read(request, records)
        for each in later.alternative_values or (later,):
            assert each.provenance is not None
            assert each.provenance.derivation == DERIVED_INPUTS["derivation"]


def test_a_review_returned_as_found_shares_nothing_with_the_stored_record() -> None:
    """Rule 6 for a member no shape types: a review never refuses, so a reviewed review is returned as found
    whatever its members hold, an object or a list of them included; a consumer that changes one through the
    Python API changes no later read of the same store (S2a-4's fix round: hand mutant M45, which the
    review's run saw killed by a monotonicity property, survived the whole suite here)."""
    review: dict[str, JsonValue] = {
        "result": "reviewed",
        "reviewer": {"name": "a"},
        "checklist": [{"item": "b"}],
    }
    field = met_field()
    field["provenance"] = {**an_object(field["provenance"]), "review": review}
    request, records = stored(with_field("fluid.dynamic_viscosity", field))
    assert isinstance(request, dict)
    request.update(copy.deepcopy(MET_REQUEST))
    first = read(request, records)
    assert first.provenance is not None
    assert first.provenance.review == review
    an_object(first.provenance.review["reviewer"])["name"] = "changed"
    an_object(a_list(first.provenance.review["checklist"])[0])["item"] = "changed"
    later = read(request, records)
    assert later.provenance is not None
    assert later.provenance.review == review


def test_only_a_derived_value_returns_its_derivation_and_its_mixed_conditions_label() -> None:
    """`provenance.md` section 2 item 6 checks `derivation` for origin `derived` alone, and SQ45 labels a
    derived value whose inputs' conditions differ: a derivation beside another origin is a member the read
    does not check, neither returned nor labelled (S2a-4's review, L3's M04 and M21)."""
    derivation = {**an_object(DERIVED_INPUTS["derivation"]), "mixed_conditions": True}
    for origin in ("derived", "measured_by_contributor"):
        provenance: dict[str, JsonValue] = {
            **an_object(met_field()["provenance"]),
            "origin": origin,
            "derivation": derivation,
        }
        written = json.loads(json.dumps(read_met(met_field(provenance=provenance)).to_json()))
        derived = origin == "derived"
        assert ("derivation" in written["provenance"]) is derived, origin
        assert ("mixed_conditions" in written["labels"]) is derived, origin


def test_a_derivation_inputs_reference_holding_status_returns_its_three_members() -> None:
    """A member named `status` where no status object stands is one the reader does not know (`provenance.md`
    section 1 item 5), left out of the reference returned (S2a-4's review, L3's M29)."""
    derivation = copy.deepcopy(an_object(DERIVED_INPUTS["derivation"]))
    reference = an_object(an_object(a_list(derivation["inputs"])[0])["record"])
    pin = dict(reference)
    reference["status"] = "not_checked"
    provenance: dict[str, JsonValue] = {**DERIVED_INPUTS, "derivation": derivation}
    written = json.loads(json.dumps(read_met(met_field(provenance=provenance)).to_json()))
    assert written["provenance"]["derivation"]["inputs"][0]["record"] == pin


def met_interval(**interval: JsonValue) -> dict[str, JsonValue]:
    """The water field as an interval met by `MET_REQUEST`, holding `interval`, and no label, which only a
    constant or a table may carry."""
    field = met_field(form="interval", interval=interval)
    del field["value"], field["label"]
    return field


def met_composition(**composition: JsonValue) -> dict[str, JsonValue]:
    """A composition read as `fluid.dynamic_viscosity` is, but for its row: `bulk.elemental_composition`."""
    return {**COMPOSITION, "conditions": met_field()["conditions"], "composition": composition}


def read_composition(field: JsonValue, *, want: str = "components") -> ReadResult:
    name = "bulk.elemental_composition"
    request, records = stored(with_field(name, field), name)
    assert isinstance(request, dict)
    request.update(copy.deepcopy(MET_REQUEST))
    requirement = request["requirement"]
    assert isinstance(requirement, dict)
    requirement["want"] = want
    return read(request, records)


def test_an_interval_returns_its_bounds_with_their_basis_as_stored_and_a_none_as_a_status() -> None:
    """`read_side_contract.md` section 6: `want: bounds` gives `{"lower", "upper", "basis"}`, as stored
    [PR-022]; section 2 item 5: numbers as read, status objects as status objects, a member the reader does
    not know left out."""
    stored_interval: dict[str, JsonValue] = {
        "lower": -0.0,
        "upper": {"status": "none"},
        "basis": "stated_bound",
    }
    result = read_met(met_interval(**stored_interval, x_unknown_member=1.0), want="bounds")
    assert (result.status, result.reasons) == ("met", ())
    text = json.dumps(result.to_json())
    assert json.loads(text)["value"] == stored_interval
    assert '"lower": -0.0' in text
    for want in ("value", "components", "evidence"):
        refused = read_met(met_interval(**stored_interval), want=want)
        assert (refused.status, refused.reasons, refused.value) == (
            "not_met",
            (Reason("want_mismatch"),),
            None,
        )


def test_a_composition_is_returned_as_stored_never_normalised_its_component_counts_as_integers() -> None:
    """`record_format.md` section 6, composition items 2 to 4: the basis, the sum rule, a stated sum and the
    components as stored, nothing normalised [PR-023], a component's statistics returned with it [PR-051];
    the code design's rule 5: a count is written as an integer, wherever its block sits."""
    statistics = {**cast(dict[str, JsonValue], COMPOSITION["statistics"]), "n_specimens": 3.0}
    oxygen: dict[str, JsonValue] = {"component": "element:O", "fraction": 0.723, "statistics": statistics}
    composition: dict[str, JsonValue] = {
        "basis": "mass_fraction",
        "sum_rule": "sums_to_one",
        "stated_sum": 0.825,
        "components": [HYDROGEN, {**oxygen, "x_unknown_member": 1.0}],
    }
    result = read_composition(met_composition(**composition))
    assert (result.status, result.reasons) == ("met", ())
    written = json.loads(json.dumps(result.to_json()))
    assert written["value"] == {**composition, "components": [HYDROGEN, {**oxygen, "statistics": statistics}]}
    assert type(written["value"]["components"][1]["statistics"]["n_specimens"]) is int
    for want in ("value", "bounds", "evidence"):
        refused = read_composition(met_composition(**composition), want=want)
        assert (refused.status, refused.reasons, refused.value) == (
            "not_met",
            (Reason("want_mismatch"),),
            None,
        )


BOUND_ORDER: list[tuple[dict[str, JsonValue], ReasonCode | None]] = [
    ({"lower": 2.0, "upper": 1.0}, "form_invalid"),
    ({"lower": {"status": "none"}, "upper": {"status": "none"}}, "form_invalid"),
    ({"lower": "0.4", "upper": 1.0}, "form_invalid"),
    ({"lower": {"status": "unstated"}, "upper": 1.0}, "form_invalid"),
    ({"lower": 1.0, "upper": 1.0}, None),
    ({"lower": 0.0, "upper": -0.0}, None),
    ({"lower": {"status": "none"}, "upper": 1.0}, None),
    ({"lower": 1.0e308, "upper": {"status": "none"}}, None),
]


@pytest.mark.parametrize(("bounds", "code"), BOUND_ORDER)
def test_an_intervals_bounds_are_numbers_at_most_one_none_and_in_order(
    bounds: dict[str, JsonValue], code: ReasonCode | None
) -> None:
    """`record_format.md` section 6, interval item 1 [PR-050]; numbers compare by value, so `-0` equals
    `0`."""
    result = read_met(met_interval(**bounds, basis="reported_range"), want="bounds")
    assert result.reasons == ((Reason(code),) if code else ()), bounds


COMPONENTS: list[tuple[JsonValue, ReasonCode | None]] = [
    ([], "form_invalid"),
    ({"component": "element:H", "fraction": 0.1}, "form_invalid"),
    ([HYDROGEN, {**HYDROGEN, "fraction": 0.2}], "form_invalid"),
    ([{**HYDROGEN, "fraction": -0.01}], "form_invalid"),
    ([{**HYDROGEN, "fraction": 1.01}], "form_invalid"),
    ([{**HYDROGEN, "fraction": "0.1"}], "form_invalid"),
    ([{"component": "element:H"}], "form_invalid"),
    ([{**HYDROGEN, "statistics": {"central": "stated"}}], "form_invalid"),
    ([{**HYDROGEN, "component": "element:Xx"}], "unknown_token"),
    ([{**HYDROGEN, "component": "water"}], "unknown_token"),
    ([{**HYDROGEN, "component": "element:h"}], "unknown_token"),
    ([{**HYDROGEN, "fraction": 0.0}, {"component": "element:O", "fraction": 1.0}], None),
    ([{**HYDROGEN, "fraction": -0.0}], None),
    ([{**HYDROGEN, "statistics": {"status": "withheld"}}], None),
]


@pytest.mark.parametrize(("components", "code"), COMPONENTS)
def test_a_compositions_components_are_a_non_empty_list_each_once_a_known_element_a_fraction_in_0_1(
    components: JsonValue, code: ReasonCode | None
) -> None:
    """`record_format.md` section 6, composition items 1, 3 and 5 [PR-051]."""
    composition: dict[str, JsonValue] = {
        "basis": "mass_fraction",
        "sum_rule": "partial",
        "components": components,
    }
    result = read_composition(met_composition(**composition))
    assert result.reasons == ((Reason(code),) if code else ()), components


DERIVED_INPUTS: dict[str, JsonValue] = {
    "origin": "derived",
    "review": {"status": "not_checked"},
    "derivation": {
        "method": "a mixing rule",
        "inputs": [
            {
                "record": {"id": "example/MAT-1", "version": "1.0.0", "content_hash": "sha256:" + "1" * 64},
                "field": "fluid.dynamic_viscosity",
            },
            {
                "record": {"id": "example/MAT-2", "version": "1.0.0", "content_hash": "sha256:" + "2" * 64},
                "field": "fluid.dynamic_viscosity",
            },
        ],
        "assumptions": ["ideal mixing"],
        "input_specimens": [{"input": 0.0, "specimen": {}}, {"input": 1.0, "specimen": {}}],
    },
}


# Step 7 over alternatives, as far as S4's decision 12 lets S2 go (`read_side_contract.md` section 3, step 7).


def test_two_alternatives_with_no_reason_of_their_own_give_no_pick_each_in_alternative_values() -> None:
    result = read_met({"alternatives": [met_field(), met_field(value=0.0007)]})
    assert (result.status, result.reasons) == ("unknown", (Reason("no_pick"),))
    written = json.loads(json.dumps(result.to_json()))
    assert set(written) == {"status", "reasons", "alternative_values", "unit", "labels"}
    assert [(entry["alternative"], entry["value"]) for entry in written["alternative_values"]] == [
        (0, 0.000692),
        (1, 0.0007),
    ]
    assert all(type(entry["alternative"]) is int for entry in written["alternative_values"])
    assert written["labels"] == []


def test_an_unknown_member_inside_an_alternative_is_ignored() -> None:
    """`record_format.md` section 10 item 1, inside an alternative (D05's half that S2a-4 decides)."""
    plain = read_met({"alternatives": [met_field(), met_field()]})
    unknown = read_met({"alternatives": [met_field(x_unknown_member=1.0), met_field()]})
    assert unknown == plain


def test_no_alternative_whose_form_want_can_give_is_want_mismatch_at_step_7() -> None:
    result = read_met({"alternatives": [met_field(), met_field()]}, want="bounds")
    assert (result.status, result.reasons, result.conditions) == ("not_met", (Reason("want_mismatch"),), None)
    assert set(json.loads(json.dumps(result.to_json()))) == {"status", "reasons", "labels"}


@pytest.mark.parametrize(
    ("field", "why"),
    [
        ({"alternatives": [met_field()]}, "the one alternative left"),
        ({"alternatives": [met_field(), water_field()]}, "an alternative's own unknown reason"),
        ({"alternatives": [met_field(), met_field(unit="mPa.s")]}, "an alternative's own refusal"),
        (
            {
                "alternatives": [
                    met_field(unit={"status": "unstated", "reason": "one"}),
                    met_field(unit={"status": "unstated", "reason": "two"}),
                ]
            },
            "each alternative's own refusal, its unit held as a status object",
        ),
    ],
)
def test_what_step_7_decides_beyond_decision_12_raises(field: dict[str, JsonValue], why: str) -> None:
    with pytest.raises(NotImplementedError):
        read_met(field)


PR_316_CASE = INPUTS.parent / "cases" / "PR-316.implied_two_disagree_in_alternative.json"
PR_316_RECORD = INPUTS / "water_alternatives_in_vivo_normal.json"


def disagreeing_in_one_alternative(other: dict[str, JsonValue]) -> tuple[JsonValue, RecordStore]:
    """PR-316's two implied conditions that disagree, which apply in the one alternative whose specimen states
    their facts (a fault of the request there), with `other` set in the provenance of the alternative they do
    not apply in."""
    record: dict[str, Any] = json.loads(PR_316_RECORD.read_text(encoding="utf-8"))
    alternatives = record["body"]["sections"]["fluid"]["fields"]["dynamic_viscosity"]["alternatives"]
    assert [bool(alternative.get("specimen")) for alternative in alternatives] == [True, False]
    alternatives[1]["provenance"].update(other)
    request, records = stored(record)
    case = json.loads(PR_316_CASE.read_text(encoding="utf-8"))
    assert isinstance(request, dict)
    pin = cast(dict[str, Any], request["target"])["record"]
    request.update({name: case["request"][name] for name in ("operating_conditions", "requirement")})
    request["acceptances"] = [{**acceptance, "record": pin} for acceptance in case["request"]["acceptances"]]
    return request, records


def test_a_request_fault_inside_one_alternative_refuses_the_field_where_no_other_has_a_reason() -> None:
    """S4's decision 12 (a): PR-316's arm, as its case file gives it."""
    refused = read(*disagreeing_in_one_alternative({}))
    assert (refused.status, refused.reasons) == ("not_met", (Reason("request_incomplete", "temperature"),))


def test_a_request_fault_inside_one_alternative_beside_anothers_own_reason_raises() -> None:
    """S4's decision 12 (a) gives S2 "a request fault inside one alternative"; S2a-4 builds that arm only
    where no alternative has a reason of its own, as the decision does `no_pick` and `want_mismatch` (S2a-4's
    decision log, phase A item 10, and its fix round, I2). Where another alternative has one, here
    `stated_without_origin`, PR-316's row reports it beside the refusal, carrying its `alternative`, which
    S4 gives a reason: so the read raises rather than drop it (S2a-4's review, L3's M09)."""
    with pytest.raises(NotImplementedError, match="an alternative's own reasons"):
        read(*disagreeing_in_one_alternative({"origin": "stated_without_origin"}))


@pytest.mark.parametrize(
    "field",
    [
        {"alternatives": [met_field(), {"alternatives": [met_field()]}]},
        {"alternatives": [met_field(), 1.0]},
        {"alternatives": [met_field(), met_field()], "alternative": []},
        {"alternatives": [met_field(), met_field()], "label": "materica.fluid.newtonian.v1"},
    ],
)
def test_alternatives_that_break_their_shape_are_refused_at_step_7(field: dict[str, JsonValue]) -> None:
    result = read_met(field)
    assert (result.status, result.reasons, result.conditions) == ("not_met", (Reason("form_invalid"),), None)

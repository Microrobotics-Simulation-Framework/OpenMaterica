# SPDX-License-Identifier: Apache-2.0
"""Examples at the edges of the read up to step 5, which the cases and properties reach rarely or not at
all: versions longer than `int` reads, the forms a request may be given in, the misuses that raise, and the
steps not built yet, which raise rather than answer."""

import importlib
import inspect
import json
from collections.abc import Collection
from pathlib import Path
from types import ModuleType
from typing import get_type_hints

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
from materica.core.value_shapes import FORM_MEMBERS
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite

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
    resolved = with_members(
        target={
            "record": {"id": "conformance/water_fixture", "version": "1.0.0", "content_hash": PIN},
            "field": "fluid.dynamic_viscosity",
        }
    )
    with pytest.raises(NotImplementedError):
        read(resolved, store())


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
        ("fluid.dynamic_viscosity", "interval"),
        ("bulk.elemental_composition", "composition"),
        ("biocompatibility.evidence", "evidence"),
    ],
)
def test_a_form_its_row_allows_whose_member_is_not_read_yet_raises_whatever_else_is_wrong(
    name: str, form: str
) -> None:
    """Its own member could add a reason, and every reason found is reported (`read_side_contract.md` section
    2 item 2): an interval's unknown `basis` beside a broken `unit` gives `unknown_token` too, once read."""
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
        ("mass_fraction", None),
        ("stated", None),
        ("bogus", None),
        (5.0, None),
    ],
)
def test_a_compositions_basis_is_checked_with_its_form_token(
    basis: JsonValue, codes: set[str] | None
) -> None:
    """A basis of a composition's own list that the row does not allow is `form_not_registered`, as a form the
    row does not allow is (the S2 design's section 1.4, SQ43), beside every shared reason; any other basis is
    the composition's own member's to judge, which S2b-1 reads."""
    name = "bulk.elemental_composition"
    field: dict[str, JsonValue] = {
        **COMPOSITION,
        "composition": {"basis": basis, "sum_rule": "partial", "components": []},
    }
    if codes is None:
        with pytest.raises(NotImplementedError):
            read(*stored(with_field(name, field), name))
        return
    assert {reason.code for reason in read(*stored(with_field(name, field), name)).reasons} == codes
    statistics = {**COMPOSITION["statistics"], "n_specimens": -1.0}  # type: ignore[dict-item]
    refused = read(*stored(with_field(name, {**field, "statistics": statistics}), name))
    assert {reason.code for reason in refused.reasons} == codes | {"form_invalid"}


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
    ("post_mortem_interval", {"value": 60.0, "unit": {"status": "unstated"}, **STATED}, None),
    ("post_mortem_interval", {"value": 1.0, "unit": "min", **STATED}, None),
    ("post_mortem_interval", {"value": 1.0, "unit": {"status": "approximate"}, **STATED}, None),
    ("post_mortem_interval", {"value": 1.0, "unit": 60.0, **STATED}, ("form_invalid",)),
    (
        "post_mortem_interval",
        {"value": 1.0, "unit": {"status": "unstated", "note": "x"}, **STATED},
        ("form_invalid",),
    ),
    ("donor_age", {"range": [1.0, 2.0], "unit": "a", **STATED}, None),
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
    status object, any token included, since step 9 alone compares it (a default for the maintainer,
    2026-10-15)."""
    field: JsonValue = {**water_field(), "specimen": {name: fact}}
    if codes is None:
        with pytest.raises(NotImplementedError):
            read(*stored(with_field("fluid.dynamic_viscosity", field)))
    else:
        refused = read(*stored(with_field("fluid.dynamic_viscosity", field)))
        assert {reason.code for reason in refused.reasons} == set(codes)


def test_a_constant_that_passes_step_8_raises_rather_than_answer() -> None:
    with pytest.raises(NotImplementedError):
        read(*stored(water()))
    with pytest.raises(NotImplementedError):
        read(*stored(water()), claims={"plain_read", "fits_and_reference_data"})


def test_a_field_holding_alternatives_raises_rather_than_answer() -> None:
    fields: list[JsonValue] = [{"alternatives": [water_field()]}, {**water_field(), "alternatives": []}]
    for field in fields:
        with pytest.raises(NotImplementedError):
            read(*stored(with_field("fluid.dynamic_viscosity", field)))


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
# A member one slip from one section 1 names at each place of a request, and the condition the place concerns.
SLIPS = [
    pytest.param((), "requirment", None, id="top"),
    pytest.param((), "record", None, id="top_records"),
    pytest.param((), "acceptance", None, id="top_acceptances"),
    pytest.param(("target",), "fields", None, id="target"),
    pytest.param(("target", "record"), "versions", None, id="target_record"),
    pytest.param(("requirement",), "wants", None, id="requirement"),
    pytest.param(("requirement",), "labels", None, id="requirement_refused_member"),
    pytest.param(("operating_conditions", "temperature"), "units", "temperature", id="operating"),
    pytest.param(TEMPERATURE, "tolerances", "temperature", id="requirement_condition"),
    pytest.param(TEMPERATURE, "accepts", "temperature", id="requirement_condition_refused_member"),
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
        "... which step 9 compares",
        with_condition("measurement_geometry", {"token": "tube", "unit": "m", "basis": "stated"}),
        None,
    ),
    (
        "a fact's unit takes any status token at step 8",
        with_fact(
            "post_mortem_interval", {"value": 60.0, "unit": {"status": "approximate"}, "basis": "stated"}
        ),
        None,
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
        with pytest.raises(NotImplementedError):
            read(*stored(with_field("fluid.dynamic_viscosity", field)))
    else:
        refused = read(*stored(with_field("fluid.dynamic_viscosity", field)))
        assert {reason.code for reason in refused.reasons} == codes


@pytest.mark.parametrize(("axis", "allowed"), [("shear_rate", False), ("temperature", True)])
def test_a_label_on_a_table_follows_its_rows_axis(axis: str, allowed: bool) -> None:
    """Step 8's shared check of a field, which a read reaches for a table only once S3 reads tables."""
    field: dict[str, JsonValue] = {**water_field(), "form": "table", "table": {"axis": axis}}
    found = value_shapes.field_problems(field, VOCABULARY.fields["fluid.dynamic_viscosity"], "table")
    assert [reason.code for reason in found] == ([] if allowed else ["form_invalid"])

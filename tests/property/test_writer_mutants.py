# SPDX-License-Identifier: Apache-2.0
"""Mutants of the writer schema's value-field part: each changes one constraint, and the property that must
kill it does so within the examples the `ci` profile gives a property, at both sizes, at the assertion named.

A mutant that loosens the schema dies when the refusal check of its family's property finds the schema taking
one of the faults it names, searched among those faults: the refusal properties draw each fault of a family
alike, and their feature audit holds each to its draw floor, so they meet them too. One that tightens the
schema dies when the acceptance property finds it refusing a field the text allows. The table is the S2a-1
review's 29 mutants and its two controls (M1 to M31, its numbering kept), then one per constraint added since
and a few that tighten, then those of the bindings the writer applies from the vocabulary (B1 to B12, TB1 to
TB4, maintainer 2026-10-15), which change the writer or a vocabulary file. Each test records the examples its
kill took as `examples_to_kill`.
"""

import copy
import json
from collections.abc import Callable
from dataclasses import replace
from typing import NamedTuple, TypeVar

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from tests.property import value_fields
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.support import MUTANT_SEARCH
from tests.property.test_writer_properties import BODY, VALUE_FIELD, Writer, check_refuses, check_takes
from tests.property.value_fields import Json, Plan, listing, mapping
from tests.spec_sync.schemas import SCHEMA

WRITER_FILE = "record.writer.json"
FIELDS_FILE = "vocabulary/fields.json"
CONDITIONS_FILE = "vocabulary/conditions.json"
ORIGINALS: dict[str, Json] = {
    name: json.loads((SCHEMA / name).read_text(encoding="utf-8"))
    for name in (WRITER_FILE, FIELDS_FILE, CONDITIONS_FILE)
}
TAKES = "takes"
REFUSED = "refused a field the text allows"


class WriterMutant(NamedTuple):
    name: str
    change: Callable[[Json], None]  # changes a copy of `file` in place
    killer: str  # TAKES, or the family of faults whose refusal property kills it
    intended: tuple[str, ...]  # the faults, one of which the kill must be, or REFUSED for TAKES
    file: str = WRITER_FILE  # the writer schema, or a vocabulary file whose bindings it applies


def node(schema: Json, path: tuple[str | int, ...]) -> JsonValue:
    found: JsonValue = schema
    for step in path:
        found = listing(found)[int(step)] if isinstance(step, int) else mapping(found)[step]
    return found


def setting(*path: str | int, to: JsonValue) -> Callable[[Json], None]:
    def change(schema: Json) -> None:
        container = node(schema, path[:-1])
        if isinstance(container, list):
            container[int(path[-1])] = copy.deepcopy(to)
        else:
            mapping(container)[str(path[-1])] = copy.deepcopy(to)

    return change


def deleting(*path: str | int) -> Callable[[Json], None]:
    def change(schema: Json) -> None:
        container = node(schema, path[:-1])
        if isinstance(container, list):
            del container[int(path[-1])]
        else:
            del mapping(container)[str(path[-1])]

    return change


def vocabulary(file: str, name: str) -> Json:
    return {"$ref": f"vocabulary/{file}#/$defs/{name}"}


D = "$defs"
P = "properties"
STATUS: Json = {"$ref": "#/$defs/status_object"}
RECIPE = tuple(f"withheld_{form}_without_recipe" for form in value_fields.FORMS if form != "evidence")
UNBOUND = tuple(
    f"{prefix}{name}"
    for prefix in ("", "alternative_")
    for name in ("form_not_registered", "unit_not_registered", "label_not_registered")
)

MUTANTS = [
    WriterMutant(
        "M1 an uncertainty's basis takes the block's",
        setting(D, "uncertainty", P, "basis", to=vocabulary("statistics.json", "statistics_basis")),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "M2 a block's represents takes an uncertainty's",
        setting(
            D,
            "statistics_block",
            P,
            "represents",
            "anyOf",
            0,
            to=vocabulary("statistics.json", "uncertainty_represents"),
        ),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "M3 an interval's basis takes a composition's",
        setting(D, "interval", P, "basis", to=vocabulary("forms.json", "composition_basis")),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "M4 a population level takes a search's inputs",
        setting(D, "population_level", P, "level", to=vocabulary("provenance.json", "search_inputs")),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "M5 a sum rule takes the bases",
        setting(D, "composition", P, "sum_rule", to=vocabulary("forms.json", "composition_basis")),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "M6 a block's distribution takes an uncertainty's",
        setting(
            D,
            "statistics_block",
            P,
            "distribution",
            "anyOf",
            0,
            to=vocabulary("statistics.json", "uncertainty_distribution"),
        ),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "M6b a block's distribution admits student_t (PR-154)",
        setting(
            D,
            "statistics_block",
            P,
            "distribution",
            "anyOf",
            0,
            to={"enum": ["normal", "lognormal", "student_t"]},
        ),
        "statistics_tokens",
        ("foreign_token_statistics.distribution",),
    ),
    WriterMutant(
        "M7 sd may be negative",
        deleting(D, "statistics_block", P, "sd", "anyOf", 0, "minimum"),
        "statistics",
        ("negative_sd", "component_block_negative_sd"),
    ),
    WriterMutant(
        "M8 a coverage probability above 1",
        deleting(D, "uncertainty", P, "coverage_probability", "anyOf", 0, "maximum"),
        "uncertainty",
        ("coverage_probability_above_one",),
    ),
    WriterMutant(
        "M9 a count may be negative",
        deleting(D, "count", "anyOf", 0, "minimum"),
        "statistics",
        ("count_negative",),
    ),
    WriterMutant(
        "M10 a fraction above 1",
        deleting(D, "composition_component", P, "fraction", "maximum"),
        "forms",
        ("fraction_outside_zero_to_one",),
    ),
    WriterMutant(
        "M11 an empty evidence list",
        deleting(D, "evidence_field", P, "evidence", "minItems"),
        "forms",
        ("evidence_empty",),
    ),
    WriterMutant(
        "M12 a derivation with no input",
        deleting(D, "derivation", P, "inputs", "minItems"),
        "provenance",
        ("derivation_without_input",),
    ),
    WriterMutant(
        "M13 plus_minus: two of one kind, or an unstated one beside a stated one",
        deleting(D, "plus_minus", "then"),
        "conditions",
        ("plus_minus_two_of_a_kind", "plus_minus_unstated_beside_stated"),
    ),
    WriterMutant(
        "M14 a numeric condition with neither value nor range",
        deleting(D, "numeric_condition", "else"),
        "conditions",
        ("condition_neither_value_nor_range",),
    ),
    WriterMutant(
        "M14b a numeric condition with both value and range",
        deleting(D, "numeric_condition", "then"),
        "conditions",
        ("condition_value_and_range",),
    ),
    WriterMutant(
        "M15 a block's conditional members free",
        deleting(D, "statistics_block", "allOf"),
        "statistics",
        (
            "population_level_missing",
            "n_sources_missing",
            "precision_conditions_missing",
            "conditional_member_elsewhere",
        ),
    ),
    WriterMutant(
        "M16 an uncertainty's conditional rules free",
        deleting(D, "uncertainty", "allOf"),
        "uncertainty",
        (
            "no_coverage_number",
            "dof_beside_another_distribution",
            "dof_missing_for_student_t",
            "uncertainty_precision_missing",
            "uncertainty_precision_elsewhere",
        ),
    ),
    WriterMutant(
        "M17 an interval with both bounds none",
        deleting(D, "interval", "not"),
        "forms",
        ("interval_both_none",),
    ),
    WriterMutant(
        "M18 provenance: source, derivation and formulation never required",
        deleting(D, "provenance", "allOf"),
        "provenance",
        (
            "source_missing",
            "derivation_missing",
            "formulation_missing",
            "derivation_missing_for_its_extraction",
            "formulation_missing_for_its_extraction",
        ),
    ),
    WriterMutant(
        "M19 fitted without fit", deleting(D, "field_members", "allOf", 0), "provenance", ("fit_missing",)
    ),
    WriterMutant(
        "M20 preservation other without text",
        deleting(D, "preservation", "then"),
        "specimen",
        ("preservation_other_without_text",),
    ),
    WriterMutant(
        "M21 inferred without inferred_from",
        deleting(D, "based", "then"),
        "conditions",
        ("condition_inferred_without_inferred_from",),
    ),
    WriterMutant(
        "M22 empty alternatives",
        deleting(D, "alternatives", P, "alternatives", "minItems"),
        "forms",
        ("alternatives_empty",),
    ),
    WriterMutant(
        "M23 a composition with no component",
        deleting(D, "composition", P, "components", "minItems"),
        "forms",
        ("composition_without_component",),
    ),
    WriterMutant(
        "M24 specimen open to unknown facts",
        deleting(D, "specimen", "additionalProperties"),
        "specimen",
        ("fact_unregistered",),
    ),
    WriterMutant(
        "M25 conditions open to unknown names",
        deleting(D, "conditions", "additionalProperties"),
        "conditions",
        ("condition_unregistered",),
    ),
    WriterMutant(
        "M26 a review without its checklist",
        setting(
            D, "review", "required", to=["result", "reviewer", "orcid", "date", "independent_of_extraction"]
        ),
        "provenance",
        ("review_member_missing",),
    ),
    WriterMutant(
        "M27 a quote beside its hash",
        deleting(D, "evidence", "not"),
        "provenance",
        ("quote_beside_its_hash",),
    ),
    WriterMutant(
        "M28 dof may be 0",
        deleting(D, "uncertainty", P, "dof", "anyOf", 0, "exclusiveMinimum"),
        "uncertainty",
        ("dof_not_positive",),
    ),
    WriterMutant(
        "M29 an extraction method without its member",
        deleting(D, "extraction", "allOf"),
        "provenance",
        ("extraction_member_missing",),
    ),
    WriterMutant(
        "M30 control: a constant's value holds any status",
        setting(D, "constant_field", P, "value", "anyOf", 1, to=STATUS),
        "status",
        ("status_not_allowed_value",),
    ),
    WriterMutant(
        "M31 control: a statistics member dropped",
        deleting(D, "statistics_block", P, "dispersion"),
        TAKES,
        (REFUSED,),
    ),
    # Since the review: the constraints the fix round adds, and more of those S2a-1 wrote.
    WriterMutant(
        "M32 a token condition's token unbound",
        setting(D, "condition_density_kind", P, "token", to={"type": "string"}),
        "tokens",
        ("foreign_token_conditions.density_kind.token",),
    ),
    WriterMutant(
        "M33 a token condition takes another row's tokens",
        setting(
            D, "condition_density_kind", P, "token", to=vocabulary("conditions.json", "specimen_shape_token")
        ),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "M34 a fact's unit unbound",
        setting(D, "post_mortem_interval", P, "unit", to={"anyOf": [{"type": "string"}, STATUS]}),
        "tokens",
        ("foreign_token_specimen.post_mortem_interval.unit",),
    ),
    WriterMutant(
        "M35 mimics takes an inferred basis",
        setting(D, "mimics", P, "basis", to=vocabulary("provenance.json", "basis")),
        "tokens",
        ("foreign_token_specimen.mimics.basis",),
    ),
    WriterMutant(
        "M36 a derivation's extraction without the derivation",
        deleting(D, "provenance", "allOf", 3),
        "provenance",
        ("derivation_missing_for_its_extraction",),
    ),
    WriterMutant(
        "M37 a formulation's extraction without the formulation",
        deleting(D, "provenance", "allOf", 4),
        "provenance",
        ("formulation_missing_for_its_extraction",),
    ),
    WriterMutant(
        "M38 a fit's extraction without the fit record",
        deleting(D, "field_members", "allOf", 1),
        "provenance",
        ("fit_missing_for_its_extraction",),
    ),
    WriterMutant(
        "M39 a spread across sources without its search",
        deleting(D, "field_members", "allOf", 2),
        "provenance",
        ("search_missing",),
    ),
    WriterMutant(
        "M40 a withheld value without its recipe", deleting(D, "field_members", "allOf", 3), "forms", RECIPE
    ),
    WriterMutant(
        "M41 a withheld evidence entry without its recipe",
        deleting(D, "withheld_evidence_entry", "then"),
        "forms",
        ("withheld_entry_without_recipe",),
    ),
    WriterMutant(
        "M42 a constant field open to unknown members",
        deleting(D, "constant_field", "unevaluatedProperties"),
        "forms",
        ("field_member_unknown",),
    ),
    WriterMutant(
        "M43 a status object holding another member",
        deleting(D, "status_object", "additionalProperties"),
        "status",
        ("status_beside_a_member",),
    ),
    WriterMutant(
        "M44 a standard's year any number",
        setting(D, "standard", P, "year", to={"type": "number"}),
        "forms",
        ("standard_year_not_whole",),
    ),
    WriterMutant(
        "M45 a plus_minus value below zero",
        deleting(D, "plus_minus_entry", P, "value", "minimum"),
        "conditions",
        ("plus_minus_value_negative",),
    ),
    WriterMutant(
        "M46 an uncertainty's value below zero",
        deleting(D, "uncertainty", P, "value", "minimum"),
        "uncertainty",
        ("uncertainty_value_negative",),
    ),
    WriterMutant(
        "M47 a coverage factor of 0",
        setting(D, "uncertainty", P, "coverage_factor", "anyOf", 0, to={"type": "number", "minimum": 0}),
        "uncertainty",
        ("coverage_factor_not_positive",),
    ),
    WriterMutant(
        "M48 an evidence entry withheld in part",
        setting(D, "status_not_withheld", P, "status", to={"enum": list(value_fields.ANY_STATUS)}),
        "forms",
        ("evidence_entry_partly_withheld", "withheld_entry_without_recipe"),
    ),
    WriterMutant(
        "M49 a quote's hash of any form",
        setting(D, "evidence", P, "quote_sha256", to={"type": "string"}),
        "provenance",
        ("quote_hash_malformed",),
    ),
    WriterMutant(
        "M50 an input's index of any number",
        setting(D, "input_specimen", P, "input", to={"type": "number"}),
        "provenance",
        ("input_specimen_index_not_whole",),
    ),
    WriterMutant(
        "M51 a page of any number",
        setting(D, "locator", P, "page", to={"type": "number"}),
        "provenance",
        ("locator_page_not_whole",),
    ),
    WriterMutant(
        "M52 a column's index from 0",
        deleting(D, "column", P, "index", "minimum"),
        "provenance",
        ("column_index_below_one",),
    ),
    WriterMutant(
        "M53 a numeric condition without its unit",
        setting(D, "numeric_condition", "required", to=[]),
        "conditions",
        ("condition_member_missing",),
    ),
    WriterMutant(
        "M54 a taxon of any number",
        setting(D, "species", P, "ncbi_taxon", to={"type": "number"}),
        "specimen",
        ("species_taxon_not_whole",),
    ),
    WriterMutant(
        "M55 an anatomical site of any text",
        setting(D, "anatomical_site", P, "uberon", to={"type": "string"}),
        "specimen",
        ("uberon_malformed",),
    ),
    WriterMutant(
        "M56 a placeholder holding any status",
        deleting(D, "placeholder", "not"),
        "status",
        tuple(
            f"status_not_allowed_{place}"
            for place in ("table", "power_law", "parameter_set", "reference_data", "provenance.assistance")
        ),
    ),
    WriterMutant(
        "M57 an evidence field with a statistics block",
        setting(D, "evidence_field", P, "statistics", to={"$ref": "#/$defs/field_statistics"}),
        "forms",
        ("evidence_beside_a_block",),
    ),
    WriterMutant(
        "M58 an evidence field under a registered condition",
        deleting(D, "evidence_field", P, "conditions", "propertyNames"),
        "forms",
        ("evidence_under_a_condition",),
    ),
    WriterMutant(
        "M59 a token condition holding a unit",
        setting(D, "condition_density_kind", P, "unit", to={"type": "string"}),
        "conditions",
        ("token_condition_unit",),
    ),
    WriterMutant(
        "M60 a normal state holding a text",
        deleting(D, "disease_and_treatment_state", "else"),
        "specimen",
        ("fact_member_beside_another_token",),
    ),
    WriterMutant(
        "M61 a diseased or treated state without its text",
        deleting(D, "disease_and_treatment_state", "then"),
        "specimen",
        ("fact_member_missing_for_its_token",),
    ),
    # The bindings (maintainer, 2026-10-15): a field's name, form, unit or label, a composition's basis, or a
    # numeric condition's unit, left unbound in the vocabulary or not applied by the writer.
    WriterMutant(
        "B1 a section's field names unbound",
        deleting(D, "sections", P, "bulk", P, "fields", "propertyNames"),
        "binding",
        ("field_unregistered",),
        FIELDS_FILE,
    ),
    WriterMutant(
        "B2 the writer applies no binding to the sections",
        deleting(D, "sections", "allOf"),
        "binding",
        ("field_unregistered", "composition_basis_not_allowed", *UNBOUND),
    ),
    WriterMutant(
        "B3 a field's forms unbound",
        deleting(D, "bulk.density", P, "form"),
        "binding",
        ("form_not_registered", "alternative_form_not_registered"),
        FIELDS_FILE,
    ),
    WriterMutant(
        "B4 a field's unit unbound",
        deleting(D, "fluid.dynamic_viscosity", P, "unit"),
        "binding",
        ("unit_not_registered", "alternative_unit_not_registered"),
        FIELDS_FILE,
    ),
    WriterMutant(
        "B5 a field with no label in its row takes one",
        deleting(D, "magnetic.remanence", P, "label"),
        "binding",
        ("label_not_registered", "alternative_label_not_registered"),
        FIELDS_FILE,
    ),
    WriterMutant(
        "B5b a field's label takes either label",
        setting(D, "magnetic.volume_susceptibility", P, "label", to={"$ref": "#/$defs/label"}),
        "binding",
        ("label_not_registered", "alternative_label_not_registered"),
        FIELDS_FILE,
    ),
    WriterMutant(
        "B6 a composition's basis unbound",
        deleting(D, "bulk.elemental_composition", P, "composition"),
        "binding",
        ("composition_basis_not_allowed",),
        FIELDS_FILE,
    ),
    WriterMutant(
        "B7 a field's alternatives unbound",
        deleting(D, "biocompatibility.evidence", P, "alternatives"),
        "binding",
        tuple(name for name in UNBOUND if name.startswith("alternative_")),
        FIELDS_FILE,
    ),
    WriterMutant(
        "B8 the writer applies no binding to replaces",
        deleting(D, "replaces", "allOf"),
        "binding",
        ("replaced_field_unregistered", *UNBOUND),
    ),
    WriterMutant(
        "B9 the replaced fields' names unbound",
        deleting(D, "replaces", "propertyNames"),
        "binding",
        ("replaced_field_unregistered",),
        FIELDS_FILE,
    ),
    WriterMutant(
        "B10 a numeric condition's unit unbound",
        deleting(D, "units", P, "temperature", P, "unit"),
        "conditions",
        ("condition_unit_not_registered",),
        CONDITIONS_FILE,
    ),
    WriterMutant(
        "B11 the writer applies no binding to the conditions",
        deleting(D, "conditions", "allOf"),
        "conditions",
        ("condition_unit_not_registered", "plus_minus_unit_not_registered"),
    ),
    WriterMutant(
        "B12 a plus_minus entry's unit unbound",
        deleting(D, "units", P, "temperature", P, "plus_minus"),
        "conditions",
        ("plus_minus_unit_not_registered",),
        CONDITIONS_FILE,
    ),
    # Tightened: each refuses a field the text allows.
    WriterMutant(
        "T1 an interval's basis without stated_bound",
        setting(
            D, "interval", P, "basis", to={"enum": ["reported_range", "proxy_range", "specification_limits"]}
        ),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "T2 a composition of two components or more",
        setting(D, "composition", P, "components", "minItems", to=2),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "T3 a checklist of one item or more",
        setting(D, "review", P, "checklist", "minItems", to=1),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "T4 one evidence entry at most",
        setting(D, "evidence_field", P, "evidence", "maxItems", to=1),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "T5 a label required",
        setting(D, "field_members", "required", to=["unit", "provenance", "label"]),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "T6 one plus_minus entry at most", setting(D, "plus_minus", "maxItems", to=1), TAKES, (REFUSED,)
    ),
    WriterMutant(
        "T7 a count of 1000 at most", setting(D, "count", "anyOf", 0, "maximum", to=1000), TAKES, (REFUSED,)
    ),
    WriterMutant(
        "T8 a basis stated only", setting(D, "based", P, "basis", to={"const": "stated"}), TAKES, (REFUSED,)
    ),
    WriterMutant(
        "T9 a text required in every disease or treatment state",
        setting(D, "disease_and_treatment_state", "required", to=["token", "text"]),
        TAKES,
        (REFUSED,),
    ),
    WriterMutant(
        "TB1 a field bound to another unit",
        setting(D, "bulk.density", P, "unit", to={"const": "g/cm3"}),
        TAKES,
        (REFUSED,),
        FIELDS_FILE,
    ),
    WriterMutant(
        "TB2 a form dropped from a field's row",
        setting(D, "bulk.density", P, "form", to={"enum": ["constant", "interval"]}),
        TAKES,
        (REFUSED,),
        FIELDS_FILE,
    ),
    WriterMutant(
        "TB3 a section's names short of one",
        setting(D, "sections", P, "bulk", P, "fields", "propertyNames", to={"enum": ["density"]}),
        TAKES,
        (REFUSED,),
        FIELDS_FILE,
    ),
    WriterMutant(
        "TB4 a numeric condition bound to another unit",
        setting(D, "units", P, "temperature", P, "unit", to={"const": "Cel"}),
        TAKES,
        (REFUSED,),
        CONDITIONS_FILE,
    ),
]


# The fields each tightening mutant's search draws, as the acceptance property draws them but of the form and
# with the parts in which the mutant refuses a field the text allows: as a loosening mutant's search is drawn
# among the faults it names. The acceptance property draws each form at least a third as often as measured.
CONSTANT = Plan(form="constant", withheld=False)
SEARCHED_ON = {
    "M1": replace(CONSTANT, rich=frozenset({"block", "uncertainty"})),
    "M2": replace(CONSTANT, represents="population"),
    "M3": Plan(form="interval", withheld=False),
    "M4": replace(CONSTANT, represents="population", rich=frozenset({"block"})),
    "M5": Plan(form="composition", withheld=False),
    "M6": replace(CONSTANT, rich=frozenset({"block"})),
    "M31": CONSTANT,
    "M33": replace(CONSTANT, rich=frozenset({"conditions"})),
    "T1": Plan(form="interval", withheld=False),
    "T2": Plan(form="composition", withheld=False),
    "T3": replace(CONSTANT, rich=frozenset({"provenance"})),
    "T4": Plan(form="evidence"),
    "T5": replace(CONSTANT, minimal=True),
    "T6": replace(CONSTANT, rich=frozenset({"conditions"})),
    "T7": replace(CONSTANT, rich=frozenset({"block"})),
    "T8": replace(CONSTANT, rich=frozenset({"conditions"})),
    "T9": replace(CONSTANT, rich=frozenset({"specimen"})),
    "TB1": Plan(registered="bulk.density"),
    "TB2": Plan(registered="bulk.density", form="table"),
    "TB3": Plan(registered="bulk.elemental_composition", place="fields"),
    "TB4": replace(CONSTANT, rich=frozenset({"conditions"})),
}


def identifier(mutant: WriterMutant) -> str:
    return mutant.name.partition(" ")[0]


Example = TypeVar("Example")


def kill(examples: st.SearchStrategy[Example], check: Callable[[Example], None]) -> tuple[int, str]:
    """The examples searched until `check` first fails, and its message; an AssertionError where it never
    does. Hypothesis runs the failing example once more to report it, which is not counted."""
    tried = 0
    first: list[tuple[int, str]] = []

    @MUTANT_SEARCH
    @given(examples)
    def search(example: Example) -> None:
        nonlocal tried
        tried += 1
        try:
            check(example)
        except AssertionError as error:
            first.append((tried, str(error)))
            raise

    try:
        search()
    except AssertionError:
        return first[0]
    raise AssertionError(f"the mutant survived {tried} examples")


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[identifier(mutant) for mutant in MUTANTS])
def test_the_writer_mutant_is_killed_at_its_assertion(
    mutant: WriterMutant, size: Size, record_property: Callable[[str, object], None]
) -> None:
    schema = copy.deepcopy(ORIGINALS[mutant.file])
    mutant.change(schema)
    if mutant.killer == TAKES:
        plan = SEARCHED_ON[identifier(mutant)]
        writer = Writer(BODY if plan.registered else VALUE_FIELD, [schema])
        fields = value_fields.bodies(plan, size) if plan.registered else value_fields.form_fields(plan, size)
        tried, message = kill(fields, lambda field: check_takes(writer, field))
    else:
        writer = Writer(BODY if mutant.killer == "binding" else VALUE_FIELD, [schema])
        faulty = value_fields.faulty_fields(mutant.killer, size, mutant.intended)
        tried, message = kill(faulty, lambda drawn: check_refuses(writer, drawn))
    record_property("examples_to_kill", tried)
    assert any(intended in message for intended in mutant.intended), message


def test_each_mutant_changes_the_schema() -> None:
    """A mutant whose path had moved would change nothing, and survive for the wrong reason; one naming a
    fault no family draws could never die at it."""
    names = {fault.name for fault in value_fields.FAULTS}
    for mutant in MUTANTS:
        schema = copy.deepcopy(ORIGINALS[mutant.file])
        mutant.change(schema)
        assert schema != ORIGINALS[mutant.file], mutant.name
        assert mutant.killer == TAKES or set(mutant.intended) <= names, mutant.name
        assert (mutant.killer == TAKES) == (identifier(mutant) in SEARCHED_ON), mutant.name

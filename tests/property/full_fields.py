# SPDX-License-Identifier: Apache-2.0
"""Value fields for the tests of step 8: full fields, which hold every member step 8 checks, and the records
that hold them.

A full field is valid against the writer schema and passes step 8 (`tests/spec_sync/test_t1.py` checks both).
The full fields are constants of `fluid.dynamic_viscosity`; the full forms an interval and a composition.
Between them the full fields hold each member of a value field, a condition, a specimen fact, a statistics
block, an uncertainty and the provenance members a read uses, and each value-or-status member as a status
object somewhere, so that a change at each of their places can be drawn or listed.
"""

import copy
import json

from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue

JsonObject = dict[str, JsonValue]

STATED: JsonObject = {"basis": "stated"}
INFERRED: JsonObject = {"basis": "inferred", "inferred_from": "Methods, p. 3"}
DOCUMENT: JsonObject = {"identifier": "doi:10.1000/xyz123", "version": "version_of_record"}
LOCATOR: JsonObject = {"type": "table", "label": "Table 2", "page": 5.0}


def _status(token: str, reason: str | None = None) -> JsonObject:
    return {"status": token} if reason is None else {"status": token, "reason": reason}


SPECIMEN: JsonObject = {
    "species": {"ncbi_taxon": 9606.0, "label": "Homo sapiens", **STATED},
    "anatomical_site": {"uberon": "UBERON:0002107", "label": "liver", **INFERRED},
    "tissue_state": {"token": "ex_vivo_fresh", **STATED},
    "disease_and_treatment_state": {"token": "treated", "text": "dialysis", **STATED},
    "preparation": {"text": "sliced, 2 mm", **STATED},
    "preservation": {"token": "other", "text": "kept on ice", **STATED},
    "post_mortem_interval": {"value": 3600.0, "unit": "s", **STATED},
    "donor_age": {"range": [1.0e9, 2.0e9], "unit": "s", **STATED},
    "mimics": _status("not_applicable"),
    "supply_form": _status("unstated", "the source does not say"),
    "lot": {"text": "B-17", **STATED},
}

UNCERTAINTY_T: JsonObject = {
    "value": 0.02,
    "coverage_factor": 2.306,
    "coverage_probability": _status("unstated"),
    "distribution": "student_t",
    "dof": 8.0,
    "basis": "reported_uncertainty",
    "represents": "measurement",
    "precision_conditions": "repeatability",
}
UNCERTAINTY_NORMAL: JsonObject = {
    "value": 1.0e-5,
    "coverage_factor": _status("unstated"),
    "coverage_probability": 0.95,
    "distribution": "normal",
    "dof": _status("not_applicable"),
    "basis": "digitising_error",
    "represents": "estimate",
}


def statistics(represents: JsonValue) -> JsonObject:
    """A full statistics block whose spread `represents` gives, with the member that calls for."""
    block: JsonObject = {
        "central": "mean",
        "n_specimens": 12.0,
        "n_donors": 4.0,
        "mean": 0.000692,
        "sd": 2.0e-5,
        "min": 0.00066,
        "max": 0.00072,
        "distribution": "normal",
        "basis": "reported_sd",
        "represents": represents,
        "dispersion": "reported",
        "relative_uncertainty": copy.deepcopy(UNCERTAINTY_T),
        "expanded_uncertainty": copy.deepcopy(UNCERTAINTY_NORMAL),
    }
    if represents == "population":
        block["population_level"] = {"level": "specimen", "within": _status("none")}
    elif represents == "across_sources":
        block["n_sources"] = 5.0
    elif represents == "measurement":
        block["precision_conditions"] = "intermediate"
    return block


STATUS_STATISTICS: JsonObject = {
    "central": _status("not_applicable"),
    "n_specimens": _status("unstated"),
    "n_donors": _status("not_applicable"),
    "mean": _status("unstated"),
    "sd": _status("none"),
    "min": _status("withheld"),
    "max": _status("not_checked"),
    "distribution": _status("unstated"),
    "basis": _status("not_applicable"),
    "represents": _status("unstated"),
    "dispersion": "not_reported",
    "relative_uncertainty": _status("none"),
    "expanded_uncertainty": _status("none"),
}

CONDITIONS: JsonObject = {
    "temperature": {
        "value": 310.15,
        "unit": "K",
        "plus_minus": [
            {"stated_as": "bound", "value": 0.5, "unit": "K"},
            {"stated_as": "sd", "value": 0.1, "unit": "K"},
        ],
        "set_or_measured": "measured",
        **INFERRED,
    },
    "shear_rate": {
        "range": [10.0, 1000.0],
        "unit": "1/s",
        "plus_minus": [{"stated_as": _status("unstated"), "value": 1.0, "unit": "1/s"}],
        **STATED,
    },
    "measurement_geometry": {"token": "tube", **STATED},
    "measurement_dimension": {"value": 5.0e-5, "unit": "m", **STATED},
    "test_method": {"token": "capillary_viscometer", **STATED},
    "magnetic_flux_density": _status("not_applicable"),
}

PROVENANCE_BY_SOURCE: JsonObject = {
    "origin": "measured_by_source",
    "source": {"key": "smith2019", "document": DOCUMENT, "locator": LOCATOR},
    "extraction": {"method": "table", "text_extraction": "pdftotext 24.02.0"},
    "evidence": {"quote": "0.692 mPa s", "locator": LOCATOR, "document": DOCUMENT},
    "assistance": _status("none"),
    "review": _status("not_checked"),
}
PIN = "sha256:" + "0" * 64
PROVENANCE_DERIVED: JsonObject = {
    "origin": "derived",
    "extraction": {"method": "derivation"},
    "search": {"inputs": "primary", "weighting": "inverse variance"},
    "assistance": _status("none"),
    "review": _status("not_checked"),
    "derivation": {
        "method": "arrhenius_mixing",
        "inputs": [
            {
                "record": {"id": "conformance/water_fixture", "version": "1.0.0", "content_hash": PIN},
                "field": "x.y",
            },
            {
                "record": {"id": "conformance/glycerol", "version": "1.0.0", "content_hash": PIN},
                "field": "x.y",
            },
        ],
        "assumptions": ["ideal mixing"],
        "input_specimens": [
            {
                "input": 1.0,
                "specimen": {"tissue_state": {"token": "phantom", **STATED}, "lot": _status("none")},
            }
        ],
        "mixed_conditions": True,
    },
}


def constant(provenance: JsonObject, represents: JsonValue, label: bool = True) -> JsonObject:
    field: JsonObject = {
        "form": "constant",
        "unit": "Pa.s",
        "value": 0.000692,
        "conditions": copy.deepcopy(CONDITIONS),
        "specimen": copy.deepcopy(SPECIMEN),
        "statistics": statistics(represents),
        "provenance": copy.deepcopy(provenance),
    }
    if label:
        field["label"] = "materica.fluid.newtonian.v1"
    return field


def full_fields() -> dict[str, JsonObject]:
    """Full fields of `fluid.dynamic_viscosity`, by what each adds to the others."""
    withheld = constant(PROVENANCE_BY_SOURCE, "population", label=False)
    withheld |= {"value": _status("withheld", "reference-only"), "statistics": _status("withheld")}
    recipe: JsonObject = {"steps": "Table 2, row 3, times 1e-3"}
    withheld["provenance"] = copy.deepcopy({**PROVENANCE_BY_SOURCE, "recipe": recipe})
    statuses = constant(PROVENANCE_BY_SOURCE, "population")
    statuses["statistics"] = copy.deepcopy(STATUS_STATISTICS)
    measurement = constant(PROVENANCE_BY_SOURCE, "measurement", label=False)
    measurement["fit"] = {"data": "the fit record's members are not named yet", "residual": 0.1}
    measurement["specimen"] = {
        **copy.deepcopy(SPECIMEN),
        "disease_and_treatment_state": {"token": "normal", **STATED},
        # The writer binds a fact's unit to its row's (maintainer, 2026-10-15): a fact whose unit the source
        # does not give is a status object as a whole. A unit held as one is in a host of the positions test.
        "post_mortem_interval": _status("unstated", "the source gives no unit"),
        "mimics": {"text": "human liver", **STATED},
    }
    return {
        "population": constant(PROVENANCE_BY_SOURCE, "population"),
        "across_sources": constant(PROVENANCE_DERIVED, "across_sources"),
        "measurement": measurement,
        "statuses": statuses,
        "withheld": withheld,
    }


def full_forms() -> dict[str, tuple[str, JsonObject]]:
    """Full fields of the other forms step 8 reads, each with the registered field that holds it: an interval
    with one bound `none`, and a composition with a stated sum whose components hold a full statistics block,
    one of status objects, a withheld one and none; and each of them withheld."""
    interval = constant(PROVENANCE_BY_SOURCE, "population", label=False)
    del interval["value"]
    interval |= {
        "form": "interval",
        "interval": {"lower": 0.00066, "upper": _status("none"), "basis": "specification_limits"},
    }
    composition: JsonObject = {
        "form": "composition",
        "unit": "1",
        "composition": {
            "basis": "mass_fraction",
            "sum_rule": "partial",
            "stated_sum": 0.994,
            "components": [
                {"component": "element:H", "fraction": 0.102, "statistics": statistics("population")},
                {"component": "element:O", "fraction": 0.723, "statistics": copy.deepcopy(STATUS_STATISTICS)},
                {"component": "element:C", "fraction": 0.143, "statistics": _status("withheld")},
                {"component": "element:N", "fraction": 0.026},
            ],
        },
        "conditions": {"temperature": copy.deepcopy(CONDITIONS["temperature"])},
        "specimen": copy.deepcopy(SPECIMEN),
        "statistics": statistics("measurement"),
        "provenance": copy.deepcopy(PROVENANCE_BY_SOURCE),
    }
    return {
        "interval": ("fluid.dynamic_viscosity", interval),
        "interval_withheld": ("fluid.dynamic_viscosity", _withheld(interval, "interval", "reference-only")),
        "composition": ("bulk.elemental_composition", composition),
        "composition_withheld": ("bulk.elemental_composition", _withheld(composition, "composition")),
    }


def _withheld(field: JsonObject, member: str, reason: str | None = None) -> JsonObject:
    """`field` as a reference-only value (`provenance.md` section 7): its own member and statistics withheld,
    its provenance holding a recipe."""
    recipe: JsonObject = {"steps": "Table 2, row 3"}
    return copy.deepcopy(
        {
            **field,
            member: _status("withheld", reason),
            "statistics": _status("withheld"),
            "provenance": {**PROVENANCE_BY_SOURCE, "recipe": recipe},
        }
    )


def record_of(field: JsonValue, name: str = "fluid.dynamic_viscosity", **section: JsonValue) -> JsonObject:
    """A material record holding `field` as `name`, with `section`'s other members, its hash recomputed."""
    section_name, _, field_name = name.partition(".")
    record: JsonObject = {
        "schema_version": "0.1.0",
        "record_type": "material",
        "id": "conformance/field_fixture",
        "version": "1.0.0",
        "name": "A value field (test fixture)",
        "licence": {"values": "CC0-1.0", "evidence": "excluded"},
        "content_hash": "",
        "body": {"sections": {section_name: {**section, "fields": {field_name: copy.deepcopy(field)}}}},
    }
    record["content_hash"] = content_hash(record)
    return record


def request_for(record: JsonObject, name: str = "fluid.dynamic_viscosity") -> JsonObject:
    pin = {member: record[member] for member in ("id", "version", "content_hash")}
    return {"target": {"record": pin, "field": name}, "requirement": {"want": "value"}}


def written(record: JsonObject) -> bytes:
    return json.dumps(record).encode()

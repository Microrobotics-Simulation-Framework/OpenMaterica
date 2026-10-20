# SPDX-License-Identifier: Apache-2.0
"""The safeguards of the names `name_overlaps.json` allows with two meanings and no text to keep them apart
(maintainer, 2026-10-15): a value of one meaning written where another belongs is refused there.

Each meaning of a guarded name has a value as the specification writes it, valid at its own place where a
schema gives one. Each place a schema gives the name refuses the values of the name's other meanings: in the
writer schema, a case file or a read request, and, where a read checks the member, in the reader schema too.
Every place the schemas give a guarded name is listed, so that a schema adding one (a parameter set's `mean`,
once its shape is written) must say what it refuses there; a place whose own meaning is free text takes any
string, and says so by refusing nothing a string holds.
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from materica.core.jsonio import JsonValue
from tests.spec_sync import name_overlaps
from tests.spec_sync.schemas import agreed
from tests.verdicts import Json

REPOSITORY = Path(__file__).resolve().parents[2]
HASH = "sha256:" + "0" * 64
PROVENANCE: JsonValue = {
    "origin": "measured_by_contributor",
    "extraction": {"method": "own_measurement"},
    "assistance": {"status": "none"},
    "review": {"status": "not_checked"},
}


@dataclass(frozen=True)
class Meaning:
    """One meaning of a name: a value as the specification writes it, and the place that takes it, a
    reference into the schemas, or None where no schema gives that place yet (with the text that does)."""

    value: JsonValue
    home: str | None
    text: str = ""


# Each guarded name's meanings, by a label of one's own.
MEANINGS: dict[str, dict[str, Meaning]] = {
    "evidence": {
        "licence": Meaning("excluded", "record.writer.json#/$defs/licence/properties/evidence"),
        "provenance": Meaning(
            {"quote": "1050 kg/m3", "locator": {"type": "table", "label": "Table 2"}},
            "record.writer.json#/$defs/provenance/properties/evidence",
        ),
        "test_reports": Meaning(
            [
                {
                    "endpoint": "cytotoxicity",
                    "standard": {"designation": "ISO 10993-5", "year": 2009},
                    "contact_category": {"status": "unstated"},
                    "contact_duration": {"status": "unstated"},
                    "material_form": {"status": "unstated"},
                    "processing": {"status": "unstated"},
                    "reported_result": "non-cytotoxic",
                    "provenance": PROVENANCE,
                }
            ],
            "record.writer.json#/$defs/evidence_field/properties/evidence",
        ),
    },
    "inputs": {
        "case_files": Meaning({"records": ["water_fixture.json"]}, "case.json#/properties/inputs"),
        "derivation": Meaning(
            [
                {
                    "record": {"id": "example/MAT-1", "version": "1.0.0", "content_hash": HASH},
                    "field": "bulk.density",
                }
            ],
            "record.writer.json#/$defs/derivation/properties/inputs",
        ),
        "search": Meaning("primary", "record.writer.json#/$defs/search/properties/inputs"),
    },
    "input": {
        "index": Meaning(0, "record.writer.json#/$defs/input_specimen/properties/input"),
        "check_point": Meaning({"H": 2.0e4}, None, "model_families.md section 6, a check point's `input`"),
    },
    "mean": {
        "statistic": Meaning(1050.0, "record.writer.json#/$defs/statistics_block/properties/mean"),
        "per_parameter": Meaning(
            {"mu": 7.6, "alpha": 4.2}, None, "uncertainty.md section 3, a multivariate normal's `mean`"
        ),
    },
    "method": {
        "extraction": Meaning("table", "record.writer.json#/$defs/extraction/properties/method"),
        "free_text": Meaning(
            "density_from_mass_and_volume", "record.writer.json#/$defs/derivation/properties/method"
        ),
    },
    "target": {
        "request": Meaning(
            {
                "record": {"id": "example/MAT-1", "version": "1.0.0", "content_hash": HASH},
                "field": "bulk.density",
            },
            "read_request.json#/properties/target",
        ),
        "declared_model": Meaning(
            {"species": {"ncbi_taxon": 9606}}, None, "declarations.md section 1, a model's `target`"
        ),
        "specimen_difference": Meaning(
            {"ncbi_taxon": 9606}, None, "declarations.md section 3, a specimen difference's `target`"
        ),
    },
}

# Each place a schema gives a guarded name, and the meanings whose values it refuses: every meaning but its
# own, but where its own is free text, which takes any string, or a member a read returns as found, which
# takes any JSON value (a test report's provenance, `record_format.md` section 4.3 item 2).
REFUSES: dict[str, dict[str, tuple[str, ...]]] = {
    "evidence": {
        "record.writer.json#/$defs/licence/properties/evidence": ("provenance", "test_reports"),
        "record.writer.json#/$defs/provenance/properties/evidence": ("licence", "test_reports"),
        "record.writer.json#/$defs/evidence_field/properties/evidence": ("licence", "provenance"),
        "record.reader.json#/properties/licence/properties/evidence": ("provenance", "test_reports"),
        "record.reader.json#/$defs/evidence_field/properties/evidence": ("licence", "provenance"),
        "read_result.json#/$defs/result_entry_provenance/properties/evidence": (),
    },
    "inputs": {
        "case.json#/properties/inputs": ("derivation", "search"),
        "record.writer.json#/$defs/derivation/properties/inputs": ("case_files", "search"),
        "record.writer.json#/$defs/search/properties/inputs": ("case_files", "derivation"),
        "record.reader.json#/$defs/derivation/properties/inputs": ("case_files", "search"),
    },
    "input": {
        "record.writer.json#/$defs/input_specimen/properties/input": ("check_point",),
        "record.reader.json#/$defs/input_specimen/properties/input": ("check_point",),
    },
    "mean": {
        "record.writer.json#/$defs/statistics_block/properties/mean": ("per_parameter",),
        "record.reader.json#/$defs/statistics_block/properties/mean": ("per_parameter",),
    },
    "method": {
        "record.writer.json#/$defs/extraction/properties/method": ("free_text",),
        "record.writer.json#/$defs/derivation/properties/method": (),
    },
    "target": {
        "read_request.json#/properties/target": ("declared_model", "specimen_difference"),
    },
}
GENERATED = "record.reader.json"


def check_refusals(name: str, files: tuple[Json, ...] = ()) -> None:
    """Each meaning with a schema of its own is taken there; each place refuses the meanings listed for it,
    and at least one place refuses something, or the safeguard could not fail. `files` replace the package's
    files of their `$id`s."""
    for label, meaning in MEANINGS[name].items():
        if meaning.home is not None:
            assert agreed(meaning.home, files)(meaning.value), (name, label)
        else:
            assert meaning.text, (name, label)
    assert any(REFUSES[name].values()), name
    for place, refused in REFUSES[name].items():
        for label in refused:
            assert not agreed(place, files)(MEANINGS[name][label].value), (name, place, label)


def places(root: Path, name: str) -> set[str]:
    """Each place the schemas give `name`, as the object holding it, `<file>#<pointer>`."""
    prefix = f"{name_overlaps.SCHEMA.as_posix()}/"
    return {
        namespace.origin.removeprefix(prefix)
        for namespace in name_overlaps.collect(root).namespaces
        if namespace.kind == "members" and name in namespace.shapes and namespace.origin.startswith(prefix)
    }


def check_places(root: Path, name: str) -> None:
    """Every place the writer, the case and the request schemas give the name is listed (the reader's are
    generated from the writer's, and listed where a read checks the member)."""
    listed = {
        place.removesuffix(f"/properties/{name}")
        for place in REFUSES[name]
        if not place.startswith(GENERATED)
    }
    assert places(root, name) == listed, name


GUARDED = sorted(MEANINGS)


@pytest.mark.parametrize("name", GUARDED)
def test_each_meaning_is_refused_at_the_others_places(name: str) -> None:
    check_refusals(name)
    check_places(REPOSITORY, name)


def test_every_guarded_name_is_an_allowlist_entry_that_names_this_test() -> None:
    """The safeguards here are those the allowlist cites, entry by entry, and no other."""
    allowlist = json.loads((REPOSITORY / "tests/spec_sync/name_overlaps.json").read_text(encoding="utf-8"))
    cited = {
        str(entry["safeguard"]["test"]).partition("[")[2].removesuffix("]")
        for entry in allowlist["entries"]
        if isinstance(entry.get("safeguard"), dict) and "test" in entry["safeguard"]
    }
    assert cited == set(GUARDED)


def opened(file: str, path: tuple[str, ...], to: JsonValue) -> tuple[Json]:
    """`file` with the subschema at `path` replaced by `to`."""
    schema = json.loads((REPOSITORY / "src/materica/schema/0.1" / file).read_text(encoding="utf-8"))
    node = schema
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = to
    return (schema,)


ANY_VALUE: JsonValue = {"$ref": "#/$defs/json_value"}
ANY_STRING: JsonValue = {"type": "string"}
ANY_OBJECT: JsonValue = {"type": "object"}


@pytest.mark.parametrize(
    ("name", "files"),
    [
        pytest.param(
            "evidence",
            opened("record.writer.json", ("$defs", "licence", "properties", "evidence"), ANY_VALUE),
            id="the_licence_takes_any_evidence",
        ),
        pytest.param(
            "inputs",
            opened("record.writer.json", ("$defs", "search", "properties", "inputs"), ANY_VALUE),
            id="a_search_takes_any_inputs",
        ),
        pytest.param(
            "input",
            opened("record.writer.json", ("$defs", "input_specimen", "properties", "input"), ANY_VALUE),
            id="an_input_specimen_takes_a_map",
        ),
        pytest.param(
            "mean",
            opened("record.reader.json", ("$defs", "statistics_block", "properties", "mean"), True),
            id="the_reader_takes_any_mean",
        ),
        pytest.param(
            "method",
            opened("record.writer.json", ("$defs", "extraction", "properties", "method"), ANY_STRING),
            id="an_extraction_takes_any_method",
        ),
        pytest.param(
            "target",
            opened("read_request.json", ("properties", "target"), ANY_OBJECT),
            id="a_request_takes_any_target",
        ),
        pytest.param(
            "inputs",
            opened("case.json", ("properties", "inputs"), True),
            id="a_case_files_inputs_take_anything",
        ),
    ],
)
def test_the_refusal_check_can_fail(name: str, files: tuple[Json]) -> None:
    with pytest.raises(AssertionError):
        check_refusals(name, files)


def test_the_place_check_fails_on_a_place_no_entry_lists(tmp_path: Path) -> None:
    """A review that gained `inputs` would be a place of the name that nothing here says the refusals of."""
    for tree in ("src/materica/schema/0.1", "docs/specification"):
        shutil.copytree(REPOSITORY / tree, tmp_path / tree)
    writer = tmp_path / "src/materica/schema/0.1/record.writer.json"
    text = writer.read_text(encoding="utf-8")
    old = '"checklist": {"type": "array", "items": {"type": "string"}}'
    assert text.count(old) == 1
    writer.write_text(text.replace(old, old + ', "inputs": {"type": "string"}'), encoding="utf-8")
    check_places(REPOSITORY, "inputs")
    with pytest.raises(AssertionError):
        check_places(tmp_path, "inputs")

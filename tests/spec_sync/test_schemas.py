# SPDX-License-Identifier: Apache-2.0
"""The specification's member tables equal the schemas', and the schemas' token lists the specification's.

Structure is edited in the schemas and checked here against the tables, so that the specification keeps its
prose (CONTRIBUTING, "Changing the schema"). The tokens the vocabulary holds are generated instead, and CI
checks those files with `scripts/gen_vocabulary.py --check`.
"""

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from scripts.freeze_schema import misplaced_ids
from scripts.gen_vocabulary import SPECIFICATION, codes, only_code, outside_parentheses, table
from tests.spec_sync.schemas import BASE, SCHEMA

WRITER = json.loads((SCHEMA / "record.writer.json").read_text(encoding="utf-8"))
CASE = json.loads((SCHEMA / "case.json").read_text(encoding="utf-8"))
REQUEST = json.loads((SCHEMA / "read_request.json").read_text(encoding="utf-8"))
RESULT = json.loads((SCHEMA / "read_result.json").read_text(encoding="utf-8"))


def document(name: str) -> str:
    return (SPECIFICATION / name).read_text(encoding="utf-8")


def test_the_envelope_table_is_the_writer_schemas() -> None:
    rows = table(document("record_format.md"), "## 2. The envelope")
    assert [only_code(row["Member"]) for row in rows] == list(WRITER["properties"])
    assert [only_code(row["Member"]) for row in rows if row["Required"] == "yes"] == WRITER["required"]


def test_the_request_table_is_the_request_schemas() -> None:
    rows = table(document("read_side_contract.md"), "## 1. The read request")
    members = [only_code(row["Member"]) for row in rows]
    # "Its shape, apart from `records`, which is supplied beside it" (section 1).
    assert members[0] == "records"
    assert members[1:] == list(REQUEST["properties"])


def test_the_result_table_is_the_result_schemas() -> None:
    rows = table(document("read_side_contract.md"), "## 2. The read result")
    assert [only_code(row["Member"]) for row in rows] == list(RESULT["properties"])


def _from_the_result(schema: JsonValue) -> JsonValue:
    """A part of read_result.json with its own references written from case.json, as case.json gives them."""
    if isinstance(schema, dict):
        return {
            key: f"read_result.json{value}"
            if key == "$ref" and isinstance(value, str) and value.startswith("#")
            else _from_the_result(value)
            for key, value in schema.items()
        }
    if isinstance(schema, list):
        return [_from_the_result(item) for item in schema]
    return schema


def test_a_cases_expected_members_are_the_results() -> None:
    """A case's `expected` holds the result's members it compares, each shaped as the result holds it, none
    required by itself (case.json requires `status` and `reasons` wherever `compare` names them)."""
    compared = CASE["$defs"]["compared_result"]
    assert compared["properties"] == _from_the_result(RESULT["properties"])
    assert "required" not in compared
    assert compared["additionalProperties"] is False


def test_the_sections_are_the_field_tables() -> None:
    assert set(WRITER["$defs"]["sections"]["properties"]) == VOCABULARY.sections


def test_the_record_types_are_the_type_tables() -> None:
    rows = table(document("record_format.md"), "## 3. Record types")
    assert {only_code(row["`record_type`"]) for row in rows} == set(WRITER["$defs"]["record_type"]["enum"])


def test_the_wants_are_section_6s() -> None:
    text = document("read_side_contract.md")
    section = text[text.index("## 6. What a read returns") : text.index("## 7. ")]
    rows = table(text, "## 6. What a read returns: `want`")
    wants = {only_code(row["`want`"]) for row in rows} | set(re.findall(r"`want: ([a-z_]+)`", section))
    assert wants == set(REQUEST["$defs"]["want"]["enum"])


def test_the_suites_are_the_readmes() -> None:
    sentence = re.search(r"`suite` is one of (.*?)\.", document("README.md"), re.DOTALL)
    assert sentence is not None
    assert codes(sentence[1]) == CASE["$defs"]["suite"]["enum"]


def test_the_operations_are_the_readmes() -> None:
    named = re.findall(r'\{"operation": "([a-z_]+)"', document("README.md"))
    assert sorted(named) == sorted(CASE["$defs"]["case_operation"]["properties"]["operation"]["enum"])


def item(document_name: str, start: str) -> str:
    """The text of the numbered item of `document_name` that begins with `start`, up to the next item."""
    found = re.search(rf"^{re.escape(start)}(.*?)(?=^\d+\. |^#|\Z)", document(document_name), re.M | re.S)
    assert found is not None, start
    return found[1]


def test_the_overlay_purposes_are_section_4_4s() -> None:
    purposes = item("record_format.md", "1. `purpose` is ")
    assert (
        codes(outside_parentheses(purposes))
        == WRITER["$defs"]["overlay_body"]["properties"]["purpose"]["enum"]
    )


def test_the_status_tokens_are_provenances() -> None:
    tokens = codes(outside_parentheses(item("provenance.md", "2. The five tokens are ")))
    assert len(tokens) == 5
    assert tokens == WRITER["$defs"]["status_object"]["properties"]["status"]["enum"]


def test_the_read_statuses_are_the_result_tables() -> None:
    (row,) = [
        row
        for row in table(document("read_side_contract.md"), "## 2. The read result")
        if row["Member"] == "`status`"
    ]
    statuses = codes(row["Contents"].partition(". ")[0])
    assert statuses == RESULT["$defs"]["read_status"]["enum"]


@pytest.mark.parametrize(
    ("check", "name", "old", "new"),
    [
        (test_the_overlay_purposes_are_section_4_4s, "record_format.md", "`measurement` (", "`measured` ("),
        (
            test_the_status_tokens_are_provenances,
            "provenance.md",
            "`not_checked` (a check",
            "`unchecked` (a check",
        ),
        (
            test_the_read_statuses_are_the_result_tables,
            "read_side_contract.md",
            "| `met`, `not_met` or `unknown`.",
            "| `met`, `partly_met`, `not_met` or `unknown`.",
        ),
        (
            test_the_operations_are_the_readmes,
            "README.md",
            '`{"operation": "transform_draws", "normals"',
            '`{"operation": "map_draws", "normals"',
        ),
    ],
    ids=["purpose", "status_object", "read_status", "operation"],
)
def test_the_token_checks_can_fail(
    check: Callable[[], None], name: str, old: str, new: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = document(name)
    assert old in original
    changed = original.replace(old, new)
    unchanged = document

    def changed_document(other: str) -> str:
        return changed if other == name else unchanged(other)

    monkeypatch.setattr(sys.modules[__name__], "document", changed_document)
    with pytest.raises(AssertionError):
        check()


def test_every_schema_files_id_is_where_it_is_published() -> None:
    assert sorted(path.name for path in SCHEMA.rglob("*.json"))
    assert misplaced_ids(SCHEMA, BASE) == []


def test_the_id_check_can_fail(tmp_path: Path) -> None:
    base = "https://example.org/schema/0.1/"
    (tmp_path / "vocabulary").mkdir()
    (tmp_path / "right.json").write_text(json.dumps({"$id": base + "right.json"}), encoding="utf-8")
    (tmp_path / "vocabulary" / "moved.json").write_text(
        json.dumps({"$id": base + "moved.json"}), encoding="utf-8"
    )
    (tmp_path / "none.json").write_text("{}", encoding="utf-8")
    assert misplaced_ids(tmp_path, base) == ["none.json: None", f"vocabulary/moved.json: {base}moved.json"]

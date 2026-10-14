# SPDX-License-Identifier: Apache-2.0
"""The generators of `scripts/`: each reads its source as specified, refuses one it cannot read faithfully,
and fails `--check` when a generated file differs. CI runs each with `--check`."""

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import gen_reader_schema, gen_shapes, gen_vocabulary
from scripts.gen_reader_schema import Json, SchemaError, reader_schema
from scripts.gen_vocabulary import TableError, cells, table


def test_a_table_is_read_by_its_headers_with_escaped_pipes() -> None:
    document = '## Words\n\n| Name | Shape |\n|---|---|\n| `a` | `{"t": "x" \\| "y"}` |\n\nAfter.\n'
    assert table(document, "## Words") == [{"Name": "`a`", "Shape": '`{"t": "x" | "y"}`'}]
    assert cells(r"| a | b \| c |") == ["a", "b | c"]


@pytest.mark.parametrize(
    ("document", "heading"),
    [
        pytest.param("## Words\n\nno table\n", "## Words", id="no_table"),
        pytest.param("## Words\n\n| A |\n|---|\n", "## Other", id="no_heading"),
        pytest.param("## Words\n\n| A | B |\n|---|---|\n| 1 |\n", "## Words", id="short_row"),
    ],
)
def test_a_table_that_cannot_be_read_is_refused(document: str, heading: str) -> None:
    with pytest.raises(TableError):
        table(document, heading)


def test_a_reason_row_with_an_unknown_status_is_refused() -> None:
    with pytest.raises(TableError):
        gen_vocabulary.reasons([{"Code": "`absent`", "Status": "maybe"}])


def test_a_numeric_condition_without_its_unit_first_is_refused() -> None:
    with pytest.raises(TableError):
        gen_vocabulary.conditions([{"Name": "`t`", "Shape": "numeric", "Unit or tokens": "kelvin, `K`"}])


TISSUE_STATE = (
    '`{"token": "in_vivo" \\| "ex_vivo_fresh" \\| "frozen_thawed" \\| "fixed" \\| "phantom", "basis"}`'
)


@pytest.mark.parametrize(
    "cell",
    [
        pytest.param('{"token":"normal" | "diseased" | "treated", "basis"}', id="no_space_after_the_colon"),
        pytest.param('{"token": "normal" | "dis-eased", "basis"}', id="a_hyphen"),
        pytest.param('{"token": "normal" | treated, "basis"}', id="an_unquoted_token"),
        pytest.param('{"token": "normal" or "treated", "basis"}', id="another_separator"),
    ],
)
def test_a_specimen_facts_tokens_are_read_in_full_or_refused(cell: str) -> None:
    with pytest.raises(TableError):
        gen_vocabulary.specimen_facts([{"Name": "`state`", "JSON shape": f"`{cell}`"}])


@pytest.mark.parametrize(
    ("reader", "row"),
    [
        (
            gen_vocabulary.conditions,
            {"Name": "`g`", "Shape": "token", "Unit or tokens": "`bulk`, tube, `gap`"},
        ),
        (gen_vocabulary.conditions, {"Name": "`g`", "Shape": "token", "Unit or tokens": "`bulk`; `gap`"}),
        (
            gen_vocabulary.fields,
            {
                "Section.field": "`bulk.density`",
                "Unit": "`kg/m3`",
                "Forms": "constant",
                "Requires": "`temperature`, density_kind",
                "Label": "none",
            },
        ),
        (
            gen_vocabulary.fields,
            {
                "Section.field": "`bulk.density`",
                "Unit": "`kg/m3`",
                "Forms": "constant",
                "Requires": "none",
                "Label": "the label `materica.fluid.newtonian.v1`",
            },
        ),
    ],
    ids=["unquoted_token", "another_separator", "unquoted_requirement", "label_not_first"],
)
def test_a_list_of_tokens_with_anything_else_in_it_is_refused(
    reader: Callable[[list[gen_vocabulary.Row]], gen_vocabulary.Vocabulary], row: gen_vocabulary.Row
) -> None:
    with pytest.raises(TableError):
        reader([row])


def test_a_token_table_change_is_read_in_full_or_stops_the_generator(tmp_path: Path) -> None:
    """The review's two examples: a token with a digit is read with the others, never in their place; a cell
    written without the space after the colon stops the generator rather than give no tokens."""
    specification = copy_tree(tmp_path, gen_vocabulary.SPECIFICATION)
    document = specification / "provenance.md"
    text = document.read_text(encoding="utf-8")
    assert TISSUE_STATE in text
    document.write_text(text.replace("ex_vivo_fresh", "ex_vivo_2h"), encoding="utf-8")
    facts = json.loads(gen_vocabulary.generate(specification)["specimen_facts.json"])["facts"]
    assert facts["tissue_state"]["tokens"] == ["in_vivo", "ex_vivo_2h", "frozen_thawed", "fixed", "phantom"]
    document.write_text(text.replace('{"token": "normal"', '{"token":"normal"'), encoding="utf-8")
    with pytest.raises(TableError):
        gen_vocabulary.generate(specification)


def copy_tree(tmp_path: Path, source: Path) -> Path:
    target = tmp_path / source.name
    shutil.copytree(source, target)
    return target


def test_the_vocabulary_check_fails_when_a_table_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    specification = copy_tree(tmp_path, gen_vocabulary.SPECIFICATION)
    monkeypatch.setattr(gen_vocabulary, "SPECIFICATION", specification)
    assert gen_vocabulary.main(["--check"]) == 0
    document = specification / "read_side_contract.md"
    document.write_text(
        document.read_text(encoding="utf-8").replace("| `absent` | not_met |", "| `absent` | unknown |")
    )
    assert gen_vocabulary.main(["--check"]) == 1
    assert "reasons.json differs" in capsys.readouterr().err


def test_the_vocabulary_check_fails_on_a_file_no_table_gives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vocabulary = copy_tree(tmp_path, gen_vocabulary.VOCABULARY)
    monkeypatch.setattr(gen_vocabulary, "VOCABULARY", vocabulary)
    (vocabulary / "stray.json").write_text("{}\n")
    assert gen_vocabulary.main(["--check"]) == 1


WRITER: dict[str, Json] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.org/writer.json",
    "title": "Record",
    "type": "object",
    "properties": {
        "id": {"$ref": "#/$defs/id"},
        "kind": {"enum": ["a", "b"]},
        "nested": {
            "type": "object",
            "properties": {"id": {"$ref": "#/$defs/id"}},
            "additionalProperties": False,
        },
        "field": {"$ref": "#/$defs/value_field"},
    },
    "additionalProperties": False,
    "$defs": {"id": {"type": "string", "pattern": "^[a-z]+(?![\\s\\S])"}, "value_field": {"type": "object"}},
}


def test_the_reader_schema_opens_the_writers_where_a_reader_is_open() -> None:
    reader = reader_schema(WRITER)
    assert reader["properties"] == {
        "id": {"type": "string", "pattern": "^[a-z]+(?![\\s\\S])"},
        "kind": {"type": "string"},
        "nested": {"type": "object", "properties": {"id": {"type": "string"}}},
        "field": True,
    }
    assert "additionalProperties" not in reader
    assert "$defs" not in reader


@pytest.mark.parametrize(
    ("place", "value"),
    [
        pytest.param("id", {"type": "string", "pattern": "^[a-z]+$"}, id="pattern_ending_with_dollar"),
        pytest.param("id", {"type": "string", "pattern": "[a-z]+(?![\\s\\S])"}, id="pattern_without_caret"),
        pytest.param("kind", {"enum": ["a", 1]}, id="enumeration_of_a_number"),
        pytest.param("kind", {"$ref": "#/$defs/nowhere"}, id="reference_to_nothing"),
        pytest.param("kind", {"$ref": "#/$defs/id", "minLength": 1}, id="reference_beside_a_keyword"),
    ],
)
def test_a_writer_schema_the_script_cannot_open_is_refused(place: str, value: Json) -> None:
    writer = json.loads(json.dumps(WRITER))
    writer["properties"][place] = value
    with pytest.raises(SchemaError):
        reader_schema(writer)


def test_the_reader_schema_check_fails_when_it_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = tmp_path / "record.reader.json"
    reader.write_text(gen_reader_schema.generate(), encoding="utf-8")
    monkeypatch.setattr(gen_reader_schema, "READER", reader)
    assert gen_reader_schema.main(["--check"]) == 0
    reader.write_text(
        reader.read_text(encoding="utf-8").replace('"pattern"', '"pattern "', 1), encoding="utf-8"
    )
    assert gen_reader_schema.main(["--check"]) == 1


def test_only_the_shapes_of_a_result_are_read_only() -> None:
    module = (
        '"""Shapes."""\n\nfrom typing import TypedDict\n\n\nclass Reason(TypedDict):\n    code: str\n\n\n'
        "class ReadRequest(TypedDict):\n    field: str\n"
    )
    stub = gen_shapes.read_only(module)
    assert "from typing_extensions import ReadOnly\nfrom typing import TypedDict" in stub
    assert "    code: ReadOnly[str]" in stub
    assert "    field: str" in stub


def test_a_long_docstring_line_is_wrapped_and_code_is_not() -> None:
    long = "word " * 30
    text = gen_shapes.wrapped(f'class A:\n    """\n    {long}\n    """\n\n    member: "{long}"\n')
    assert all(len(line) <= 110 for line in text.splitlines() if not line.startswith("    member"))
    assert f'    member: "{long}"' in text

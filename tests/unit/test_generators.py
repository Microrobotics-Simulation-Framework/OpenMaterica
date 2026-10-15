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


@pytest.mark.parametrize(
    ("cell", "given"),
    [
        ("1, 2, 3, 6", {"steps": [1, 2, 3, 6]}),
        ("0", {"steps": [0]}),
        ("USD read, engine adapter", {"procedures": ["USD read", "engine adapter"]}),
    ],
)
def test_a_reasons_step_is_read_as_steps_or_procedures(cell: str, given: dict[str, object]) -> None:
    assert gen_vocabulary.given_by(cell) == given


@pytest.mark.parametrize("cell", ["14", "07", "1, build", "the build", "1,2", "step 3"])
def test_a_reasons_step_of_another_form_is_refused(cell: str) -> None:
    with pytest.raises(TableError):
        gen_vocabulary.given_by(cell)


def test_a_fields_forms_are_read_with_the_bases_its_row_allows() -> None:
    assert gen_vocabulary.field_forms("constant, table, interval") == (["constant", "table", "interval"], {})
    assert gen_vocabulary.field_forms("composition (basis `mass_fraction`)") == (
        ["composition"],
        {"composition": ["mass_fraction"]},
    )
    assert gen_vocabulary.field_forms("evidence (section 4.3)") == (["evidence"], {})


@pytest.mark.parametrize(
    "cell",
    [
        "composition (basis mass_fraction)",
        "composition (bases `mass_fraction`)",
        "composition (`mass_fraction` only)",
        "constant; table",
        "Constant",
    ],
)
def test_a_forms_cell_of_another_form_is_refused(cell: str) -> None:
    with pytest.raises(TableError):
        gen_vocabulary.field_forms(cell)


GEOMETRY = {"measurement_geometry": ["bulk", "tube", "gap"]}


def test_required_with_is_read_as_a_token_condition_and_its_tokens() -> None:
    assert gen_vocabulary.required_with("\u2014", GEOMETRY) == {}
    assert gen_vocabulary.required_with("`measurement_geometry`: `tube`, `gap`", GEOMETRY) == {
        "measurement_geometry": ["tube", "gap"]
    }


@pytest.mark.parametrize(
    "cell",
    [
        pytest.param("`measurement_geometry`: `pipe`", id="a_token_not_the_conditions"),
        pytest.param("`temperature`: `tube`", id="not_a_token_condition"),
        pytest.param("measurement_geometry: `tube`", id="an_unquoted_condition"),
        pytest.param("`measurement_geometry`: tube", id="an_unquoted_token"),
        pytest.param("", id="empty"),
    ],
)
def test_required_with_of_another_form_is_refused(cell: str) -> None:
    with pytest.raises(TableError):
        gen_vocabulary.required_with(cell, GEOMETRY)


def test_a_list_in_prose_is_read_between_its_anchors() -> None:
    text = "the levels are `donor`, `lot` (a batch, `x`) [PR-156], `specimen` and `test` (rule 10)"
    assert gen_vocabulary.listed(text, "the levels are ", " (rule 10)") == [
        "donor",
        "lot",
        "specimen",
        "test",
    ]
    assert gen_vocabulary.listed("`a`, or `b` where it applies", None, " where") == ["a", "b"]


@pytest.mark.parametrize(
    ("text", "after", "before"),
    [
        pytest.param("are `a`, b or `c`.", "are ", ".", id="an_unquoted_token"),
        pytest.param("are `a`; `b`.", "are ", ".", id="another_separator"),
        pytest.param("are `a` and `B`.", "are ", ".", id="a_capital"),
        pytest.param("are `a`. are `b`.", "are ", ".", id="an_anchor_twice"),
        pytest.param("is `a`.", "are ", ".", id="no_anchor"),
        pytest.param("are `a`", "are ", ".", id="no_end"),
        pytest.param("are .", "are ", ".", id="no_token"),
    ],
)
def test_a_list_in_prose_of_another_form_is_refused(text: str, after: str, before: str) -> None:
    with pytest.raises(TableError):
        gen_vocabulary.listed(text, after, before)


def test_a_token_listed_twice_is_refused() -> None:
    with pytest.raises(TableError):
        gen_vocabulary.enumeration(["mean", "median", "mean"])


@pytest.mark.parametrize(
    ("document", "old", "new"),
    [
        pytest.param(
            "uncertainty.md", "`median`, `single_measurement`", "median, `single_measurement`", id="central"
        ),
        pytest.param("uncertainty.md", "the levels are `donor`", "the levels: `donor`", id="level_anchor"),
        pytest.param(
            "uncertainty.md",
            "- `basis` is `reported_uncertainty`",
            "- `basis`: `reported_uncertainty`",
            id="uncertainty",
        ),
        pytest.param("provenance.md", "`set_point` (the value", "set_point (the value", id="set_or_measured"),
        pytest.param(
            "provenance.md",
            "`measurement_geometry`: `tube`, `gap`",
            "`measurement_geometry`: `pipe`",
            id="required_with",
        ),
        pytest.param(
            "record_format.md",
            "`mole_fraction`. `component`",
            "mole fraction. `component`",
            id="composition_basis",
        ),
        pytest.param("record_format.md", "| 1 | `H` `He` |", "| 1 | `H` |", id="element_count"),
        pytest.param(
            "record_format.md",
            "`component` is `element:<symbol>`",
            "`component` is `<symbol>`",
            id="component_form",
        ),
        pytest.param(
            "read_side_contract.md", "| `at_edge` | not_met | 11 |", "| `at_edge` | not_met | 14 |", id="step"
        ),
        pytest.param("read_side_contract.md", "from this list only: ", "from this list: ", id="labels"),
    ],
)
def test_a_list_the_specification_rewords_stops_the_generator(
    tmp_path: Path, document: str, old: str, new: str
) -> None:
    specification = copy_tree(tmp_path, gen_vocabulary.SPECIFICATION)
    path = specification / document
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(TableError):
        gen_vocabulary.generate(specification)


@pytest.mark.parametrize(
    ("document", "old", "new", "file", "definition", "tokens"),
    [
        pytest.param(
            "uncertainty.md",
            "`reproducibility`, or",
            "`reproducibility`, `field_repeatability`, or",
            "statistics.json",
            "precision_conditions",
            ["repeatability", "intermediate", "reproducibility", "field_repeatability"],
            id="statistics",
        ),
        pytest.param(
            "record_format.md",
            "`stated_bound`. [RC-009]",
            "`stated_bound` or `tolerance_band`. [RC-009]",
            "forms.json",
            "interval_basis",
            ["reported_range", "proxy_range", "specification_limits", "stated_bound", "tolerance_band"],
            id="forms",
        ),
    ],
)
def test_a_token_added_to_a_list_in_prose_is_read_with_the_others(
    tmp_path: Path, document: str, old: str, new: str, file: str, definition: str, tokens: list[str]
) -> None:
    specification = copy_tree(tmp_path, gen_vocabulary.SPECIFICATION)
    path = specification / document
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    assert json.loads(gen_vocabulary.generate(specification)[file])["$defs"][definition]["enum"] == tokens


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

# SPDX-License-Identifier: Apache-2.0
"""The specification's member tables equal the schemas', and the schemas' token lists the specification's.

Structure is edited in the schemas and checked here against the tables, so that the specification keeps its
prose (CONTRIBUTING, "Changing the schema"). The tokens the vocabulary holds are generated instead, and CI
checks those files with `scripts/gen_vocabulary.py --check`.
"""

import copy
import json
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

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


def result_shape_problems(result: dict[str, JsonValue], writer: dict[str, JsonValue]) -> list[str]:
    """Where the result's shapes repeat the writer's: a condition entry's `record` takes each shape the
    writer's `conditions` gives a condition, and a review returned as found names the writer review's
    members."""
    result_defs = cast(dict[str, dict[str, JsonValue]], result["$defs"])
    writer_defs = cast(dict[str, dict[str, JsonValue]], writer["$defs"])
    record = cast(dict[str, dict[str, list[dict[str, str]]]], result_defs["condition_entry"]["properties"])
    taken = {alternative["$ref"] for alternative in record["record"]["anyOf"]}
    conditions = cast(dict[str, dict[str, list[dict[str, str]]]], writer_defs["conditions"]["properties"])
    problems = [
        f"a condition entry's record does not take {name}'s shape {alternative['$ref']}"
        for name, given in conditions.items()
        for alternative in given["anyOf"]
        if f"record.writer.json{alternative['$ref']}" not in taken
    ]
    returned = cast(dict[str, JsonValue], result_defs["result_review"]["properties"])
    written = cast(dict[str, JsonValue], writer_defs["review"]["properties"])
    if list(returned) != list(written):
        problems.append(f"a review returned names {list(returned)}, the writer's {list(written)}")
    return problems


def test_the_results_shapes_take_the_writers() -> None:
    assert result_shape_problems(RESULT, WRITER) == []


def test_a_result_shape_left_behind_is_found() -> None:
    shapes = copy.deepcopy(RESULT)
    del shapes["$defs"]["condition_entry"]["properties"]["record"]["anyOf"][1]
    del shapes["$defs"]["result_review"]["properties"]["orcid"]
    assert result_shape_problems(shapes, WRITER) == [
        "a condition entry's record does not take density_kind's shape #/$defs/condition_density_kind",
        "a review returned names ['result', 'reviewer', 'date', 'independent_of_extraction', 'checklist'], "
        "the writer's ['result', 'reviewer', 'orcid', 'date', 'independent_of_extraction', 'checklist']",
    ]


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


# What both libraries read alike (`tests/verdicts.py`, `tests/property/test_validators_agree.py`).
# jsonschema-rs reads a resource's `$schema` unless told the draft, and applies `dependencies`, a keyword
# draft 2020-12 dropped, even at 2020-12; python-jsonschema reads every file at 2020-12. So every file
# declares 2020-12 or nothing, and uses no keyword outside 2020-12's but the package's own `x-materica-*`
# and, at a vocabulary file's root, its table.
DRAFT = "https://json-schema.org/draft/2020-12/schema"
# Keywords whose value is a schema, a map of schemas by name, or a list of schemas.
IN_PLACE = {
    "items",
    "additionalProperties",
    "unevaluatedProperties",
    "unevaluatedItems",
    "not",
    "if",
    "then",
    "else",
    "contains",
    "propertyNames",
    "contentSchema",
}
BY_NAME = {"properties", "patternProperties", "$defs", "dependentSchemas"}
LISTED = {"allOf", "anyOf", "oneOf", "prefixItems"}
KEYWORDS = (
    IN_PLACE
    | BY_NAME
    | LISTED
    | {"$schema", "$id", "$ref", "$anchor", "$dynamicRef", "$dynamicAnchor", "$vocabulary", "$comment"}
    | {"type", "enum", "const", "multipleOf", "maximum", "exclusiveMaximum", "minimum", "exclusiveMinimum"}
    | {"maxLength", "minLength", "pattern", "maxItems", "minItems", "uniqueItems", "maxContains"}
    | {"minContains", "maxProperties", "minProperties", "required", "dependentRequired"}
    | {"title", "description", "default", "deprecated", "readOnly", "writeOnly", "examples"}
    | {"format", "contentEncoding", "contentMediaType"}
)
VOCABULARY_TABLES = {
    "vocabulary/acceptances.json": "kinds",
    "vocabulary/conditions.json": "conditions",
    "vocabulary/fields.json": "fields",
    "vocabulary/reasons.json": "reasons",
    "vocabulary/specimen_facts.json": "facts",
}


def schema_files(root: Path = SCHEMA) -> dict[str, dict[str, object]]:
    return {
        path.relative_to(root).as_posix(): json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(root.rglob("*.json"))
    }


def subschemas(schema: object, where: str = "") -> Iterator[tuple[str, dict[str, object]]]:
    """Each schema object in `schema`, with its JSON pointer: those its keywords hold, at any depth."""
    if not isinstance(schema, dict):
        return
    found = cast(dict[str, object], schema)
    yield where, found
    for keyword, value in found.items():
        if keyword in IN_PLACE:
            yield from subschemas(value, f"{where}/{keyword}")
        elif keyword in BY_NAME and isinstance(value, dict):
            for name, held in cast(dict[str, object], value).items():
                yield from subschemas(held, f"{where}/{keyword}/{name}")
        elif keyword in LISTED and isinstance(value, list):
            for index, held in enumerate(cast(list[object], value)):
                yield from subschemas(held, f"{where}/{keyword}/{index}")


def draft_problems(files: dict[str, dict[str, object]]) -> list[str]:
    """Each file that declares another draft than 2020-12, and each keyword outside 2020-12's."""
    problems = [
        f"{name} declares {file['$schema']}"
        for name, file in files.items()
        if file.get("$schema", DRAFT) != DRAFT
    ]
    for name, file in files.items():
        for where, schema in subschemas(file):
            own = {VOCABULARY_TABLES[name]} if where == "" and name in VOCABULARY_TABLES else set[str]()
            problems += [
                f"{name}#{where}: {keyword}"
                for keyword in schema
                if keyword not in KEYWORDS | own and not keyword.startswith("x-materica-")
            ]
    return problems


def test_every_schema_file_is_read_at_2020_12() -> None:
    assert draft_problems(schema_files()) == []


@pytest.mark.parametrize(
    ("path", "value", "problem"),
    [
        (
            ("$schema",),
            "http://json-schema.org/draft-07/schema#",
            "case.json declares http://json-schema.org/",
        ),
        (("dependencies",), {"case": ["inputs"]}, "case.json#: dependencies"),
        (("properties", "case", "definitions"), {}, "case.json#/properties/case: definitions"),
    ],
    ids=["draft-07", "dependencies", "nested"],
)
def test_the_draft_check_can_fail(path: tuple[str, ...], value: object, problem: str) -> None:
    files = schema_files()
    changed = files["case.json"]
    for step in path[:-1]:
        changed = cast(dict[str, object], changed[step])
    changed[path[-1]] = value
    assert any(found.startswith(problem) for found in draft_problems(files)), draft_problems(files)


# Every pattern starts with `^` and ends with `(?![\s\S])`, which both libraries read alike, as matching in
# full; a validator's `$` also matches before a final newline in python-jsonschema and not in jsonschema-rs.
# Between, no escape of a letter or digit (`\d`, `\w` and `\s` are ASCII in one library and Unicode in the
# other, and differently inside a lookaround), no `.` outside a class, no `$` and no POSIX class
# (`[[:alpha:]]` is a class in jsonschema-rs and a set of characters in python-jsonschema).
END = "(?![\\s\\S])"


def pattern_problems(pattern: str) -> list[str]:
    problems = [] if pattern.startswith("^") else ["no `^` at its start"]
    problems += [] if pattern.endswith(END) else [f"no `{END}` at its end"]
    body = pattern.removeprefix("^").removesuffix(END)
    in_class, index = False, 0
    while index < len(body):
        character = body[index]
        if character == "\\":
            escaped = body[index + 1 : index + 2]
            if escaped.isalnum():
                problems.append(f"the escape `\\{escaped}`")
            index += 2
            continue
        if body.startswith("[[:", index) or (in_class and body.startswith("[:", index)):
            problems.append("a POSIX class")
        if character == "[" and not in_class:
            in_class = True
        elif character == "]" and in_class:
            in_class = False
        elif character in ".$" and not in_class:
            problems.append(f"`{character}` outside a class")
        index += 1
    return problems


def patterns(files: dict[str, dict[str, object]]) -> Iterator[tuple[str, str]]:
    """Each pattern in `files`, a `pattern`'s or a `patternProperties` name, with where it is."""
    for name, file in files.items():
        for where, schema in subschemas(file):
            if isinstance(schema.get("pattern"), str):
                yield f"{name}#{where}/pattern", cast(str, schema["pattern"])
            for held in cast(dict[str, object], schema.get("patternProperties", {})):
                yield f"{name}#{where}/patternProperties", held


def test_every_pattern_reads_alike_in_both_libraries() -> None:
    found = dict(patterns(schema_files()))
    assert len(found) >= 13
    assert {
        where: pattern_problems(pattern) for where, pattern in found.items() if pattern_problems(pattern)
    } == {}


@pytest.mark.parametrize(
    ("pattern", "problem"),
    [
        ("^[0-9]+$", f"no `{END}` at its end"),
        ("[0-9]+(?![\\s\\S])", "no `^` at its start"),
        ("^\\d+(?![\\s\\S])", "the escape `\\d`"),
        ("^a\\wb(?![\\s\\S])", "the escape `\\w`"),
        ("^a\\sb(?![\\s\\S])", "the escape `\\s`"),
        ("^a.b(?![\\s\\S])", "`.` outside a class"),
        ("^a$b(?![\\s\\S])", "`$` outside a class"),
        ("^[[:alpha:]]+(?![\\s\\S])", "a POSIX class"),
    ],
)
def test_the_pattern_check_can_fail(pattern: str, problem: str) -> None:
    assert problem in pattern_problems(pattern)


def test_the_pattern_check_reads_every_file() -> None:
    """The control for the files: a pattern of `case.json` and one of `read_request.json`, changed, are
    found."""
    files = schema_files()
    case_properties = cast(dict[str, dict[str, object]], files["case.json"]["properties"])
    case_properties["case"]["pattern"] = "^[A-Z]{2}-\\d{3}(?![\\s\\S])"
    request_definitions = cast(dict[str, dict[str, object]], files["read_request.json"]["$defs"])
    request_definitions["field_name"]["pattern"] = "^[a-z0-9_]+.[a-z0-9_]+(?![\\s\\S])"
    found = {where for where, pattern in patterns(files) if pattern_problems(pattern)}
    assert found == {"case.json#/properties/case/pattern", "read_request.json#/$defs/field_name/pattern"}

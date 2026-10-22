# SPDX-License-Identifier: Apache-2.0
"""Each suite's `CASES.md`, the source for what each arm tests, matches the case files and the specification:
one row per case file, its expected column what the file states, and each heading the specification's row.
"""

import functools
import json
from collections.abc import Callable, Mapping, Sequence

import pytest

from materica.core.jsonio import JsonValue
from scripts.gen_vocabulary import SPECIFICATION, Row, only_code, table
from tests.conformance import runner
from tests.conformance.runner import CONFORMANCE, CaseFile, JsonObject

CASE_FILES = runner.discover()
SUITES = sorted(path.name for path in CONFORMANCE.iterdir() if path.is_dir())


def sections(suite: str) -> Mapping[str, tuple[str, str, Sequence[Mapping[str, str]]]]:
    """Per case heading in the suite's CASES.md: the document and row it quotes, and its table.

    Read once per suite, not once per case file, and shared by every caller: so it is typed read-only."""
    return _sections(suite)


@functools.cache
def _sections(suite: str) -> Mapping[str, tuple[str, str, Sequence[Mapping[str, str]]]]:
    text = (CONFORMANCE / suite / "CASES.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    found: dict[str, tuple[str, str, list[Row]]] = {}
    for index, line in enumerate(lines):
        if line.startswith("## "):
            document, _, quoted = lines[index + 2].partition(": ")
            found[line.removeprefix("## ")] = (only_code(document), quoted, table(text, line))
    return found


def specification_rows(document: str) -> dict[str, str]:
    rows = table((SPECIFICATION / document).read_text(encoding="utf-8"), "## Cases")
    return {row["Case"]: row["Tests"] for row in rows}


def code(value: JsonValue) -> str:
    return f"`{value}`"


def reason_text(reason: dict[str, JsonValue]) -> str:
    """A reason as `CASES.md` writes it: its code, then its condition and alternative where it has them."""
    inside = [str(reason["condition"])] if "condition" in reason else []
    alternative = reason.get("alternative")
    if isinstance(alternative, float):
        inside.append(f"alternative {int(alternative)}")
    return f"{reason['code']} ({', '.join(inside)})" if inside else str(reason["code"])


def found(entries: list[JsonValue]) -> str:
    """A record-check case's findings or listing as `CASES.md` writes them: each rule's case id, at its input
    and its JSON pointer there."""
    written = [
        f"`{entry['item']}` at `{entry['document']}#{entry['pointer']}`"
        for entry in entries
        if isinstance(entry, dict)
    ]
    return ", ".join(written) or "nothing"


def claims_text(case_file: CaseFile) -> str:
    return "claims " + ", ".join(
        code(f"{suite}: {str(claim).lower()}") for suite, claim in sorted(case_file.claims.items())
    )


def build_column(case_file: CaseFile) -> str:
    """A build-check case's column: its refusals, each its rule's case id at its JSON pointer, written as JSON
    so that the empty pointer shows; the report's members compared and expected absent; the rules it compares;
    its claims. A case expecting results, watches or unused (S7a-2 onwards) is written by the piece that adds
    the first."""
    expected = case_file.expected
    assert set(expected) <= {"refusals"}, f"{case_file.path.name}: write its results' column first"
    refusals = expected.get("refusals", [])
    assert isinstance(refusals, list)
    written = [
        f"{code(refusal['item'])} at {code(json.dumps(refusal['pointer']))}"
        for refusal in refusals
        if isinstance(refusal, dict)
    ]
    parts = ["refuses " + (", ".join(written) or "nothing")]
    absent = [code(member) for member in ("results", "watches", "unused") if member in case_file.members]
    if absent:
        parts.append(
            (", ".join(absent[:-1]) + " and " + absent[-1] if len(absent) > 1 else absent[0]) + " absent"
        )
    if case_file.rules:
        parts.append("rules " + ", ".join(code(rule) for rule in case_file.rules))
    if case_file.claims:
        parts.append(claims_text(case_file))
    return "; ".join(parts)


def expected_column(case_file: CaseFile) -> str:
    """The column as `CASES.md` writes it, from the case file: status and reasons with their condition and
    alternative, or that the two are not compared; the listing, the shortened hash, or a read's value, unit,
    alternative values and assumption, as JSON; then labels and claims (sorted) where the case states them. A
    table evaluation case's is its evaluations, as JSON, and its binary32 tolerance; a record-check case's its
    findings, its listing and the rules it compares; a `quote_sha256` operation's its status and shortened
    hash; a build-check case's its refusals (`build_column`)."""
    expected = case_file.expected
    if case_file.operation == "check_build":
        return build_column(case_file)
    if case_file.operation == "check":
        items, listing = expected["items"], expected["listing"]
        assert isinstance(items, list)
        assert isinstance(listing, list)
        rules = f"; rules {', '.join(code(rule) for rule in case_file.rules)}" if case_file.rules else ""
        return f"finds {found(items)}; lists {found(listing)}{rules}"
    if case_file.operation == "evaluate":
        tolerances = case_file.precision_tolerances
        assert tolerances is not None
        return (
            f"evaluations {code(json.dumps(expected['evaluations']))}; "
            f"binary32 tolerance {code(json.dumps(tolerances['binary32']))}"
        )
    # A case leaves `status` and `reasons` out where the text leaves them open (README, "Case files").
    left_out = [code(member) for member in ("status", "reasons") if member not in case_file.members]
    parts = [" and ".join(left_out) + " not compared"] if left_out else []
    if "status" in expected:
        parts.append(str(expected["status"]))
    reasons = expected.get("reasons", [])
    assert isinstance(reasons, list)
    if reasons:
        parts.append(", ".join(code(reason_text(reason)) for reason in reasons if isinstance(reason, dict)))
    if case_file.operation == "list_records":
        listed = expected["value"]
        assert isinstance(listed, list)
        entries = [f"{code(entry['id'])} {entry['version']}" for entry in listed if isinstance(entry, dict)]
        parts.append("lists " + (", ".join(entries) or "nothing"))
    elif case_file.operation in ("content_hash", "quote_sha256"):
        if "value" in expected:
            parts.append(code(str(expected["value"])[: len("sha256:") + 8] + "\u2026"))
    else:
        for member in ("value", "unit", "alternative_values", "assumption"):
            if member in expected:
                parts.append(f"{member} {code(json.dumps(expected[member]))}")
    labels = expected.get("labels")
    if isinstance(labels, list):
        parts.append("labels " + (", ".join(code(label) for label in labels) or "none"))
    if case_file.claims:
        parts.append(claims_text(case_file))
    return "; ".join(parts)


@pytest.mark.parametrize("suite", SUITES)
def test_one_row_per_case_file(suite: str) -> None:
    rows = [
        f"{case}.{only_code(row['Variant'])}.json"
        for case, (_, _, table_rows) in sections(suite).items()
        for row in table_rows
    ]
    assert sorted(rows) == sorted(path.name for path in (CONFORMANCE / suite / "cases").glob("*.json"))


@pytest.mark.parametrize("case_file", CASE_FILES, ids=[case_file.path.name for case_file in CASE_FILES])
def test_the_expected_column_is_the_case_files(case_file: CaseFile) -> None:
    _, _, rows = sections(case_file.suite)[case_file.case]
    (row,) = [row for row in rows if only_code(row["Variant"]) == case_file.variant]
    assert row["Expected"] == expected_column(case_file)


@pytest.mark.parametrize("suite", SUITES)
def test_each_heading_quotes_the_specifications_row(suite: str) -> None:
    for case, (document, quoted, _) in sections(suite).items():
        assert specification_rows(document).get(case) == quoted, case


def test_a_case_file_that_disagrees_with_its_row_is_found() -> None:
    case_file = next(
        case_file for case_file in CASE_FILES if case_file.path.name == "PR-301.three_codes_step0.json"
    )
    document = json.loads(case_file.path.read_bytes())
    document["expected"]["reasons"].pop()
    _, _, rows = sections("plain_read")["PR-301"]
    (row,) = [row for row in rows if only_code(row["Variant"]) == "three_codes_step0"]
    assert row["Expected"] == expected_column(case_file)
    assert row["Expected"] != expected_column(CaseFile.from_document(case_file.path, document))


def test_a_read_that_expects_a_value_shows_it_with_its_unit() -> None:
    case_file = next(case_file for case_file in CASE_FILES if case_file.path.name == "PR-310.absent.json")
    document = json.loads(case_file.path.read_bytes())
    document["expected"] = {
        "status": "unknown",
        "reasons": [{"code": "condition_unstated", "condition": "shear_rate"}],
        "value": 0.000692,
        "unit": "Pa.s",
        "labels": ["materica.fluid.newtonian.v1"],
    }
    document["compare"] = {"members": ["status", "reasons", "value", "unit", "labels"], "exact": True}
    assert expected_column(CaseFile.from_document(case_file.path, document)) == (
        'unknown; `condition_unstated (shear_rate)`; value `0.000692`; unit `"Pa.s"`; '
        "labels `materica.fluid.newtonian.v1`"
    )


def changed(name: str, change: Callable[[JsonObject], None]) -> CaseFile:
    """The case file `name`, changed by `change` on its document."""
    case_file = next(case_file for case_file in CASE_FILES if case_file.path.name == name)
    document = json.loads(case_file.path.read_bytes())
    change(document)
    return CaseFile.from_document(case_file.path, document)


def _member(case: JsonObject, name: str) -> JsonObject:
    member = case[name]
    assert isinstance(member, dict)
    return member


def _refusals(case: JsonObject) -> list[JsonValue]:
    refusals = _member(case, "expected")["refusals"]
    assert isinstance(refusals, list)
    return refusals


def _first_refusal(case: JsonObject) -> JsonObject:
    refusal = _refusals(case)[0]
    assert isinstance(refusal, dict)
    return refusal


def drop_a_refusal(case: JsonObject) -> None:
    _refusals(case).pop()


def move_the_pointer(case: JsonObject) -> None:
    _first_refusal(case)["pointer"] = "/models/0"


def change_the_rule(case: JsonObject) -> None:
    _first_refusal(case)["item"] = "BC-051"


def drop_the_rules(case: JsonObject) -> None:
    _member(case, "compare").pop("rules_compared")


def drop_the_claims(case: JsonObject) -> None:
    case.pop("claims")


def compare_no_unused(case: JsonObject) -> None:
    members = _member(case, "compare")["members"]
    assert isinstance(members, list)
    members.remove("unused")


@pytest.mark.parametrize(
    ("name", "change"),
    [
        ("BC-004.two_models_both_listed.json", drop_a_refusal),
        ("BC-048.empty_reason.json", move_the_pointer),
        ("BC-048.json_array.json", change_the_rule),
        ("BC-050.requirement_names_another_label.json", drop_the_rules),
        ("BC-051.checked_over_domain.json", drop_the_claims),
        ("BC-051.engine_over_records.json", compare_no_unused),
    ],
)
def test_a_build_check_case_that_disagrees_with_its_row_is_found(
    name: str, change: Callable[[JsonObject], None]
) -> None:
    case_file = next(case_file for case_file in CASE_FILES if case_file.path.name == name)
    _, _, rows = sections("build_checks")[case_file.case]
    (row,) = [row for row in rows if only_code(row["Variant"]) == case_file.variant]
    assert row["Expected"] == expected_column(case_file)
    assert row["Expected"] != expected_column(changed(name, change))

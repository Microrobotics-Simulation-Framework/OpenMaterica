# SPDX-License-Identifier: Apache-2.0
"""Each suite's `CASES.md`, the source for what each arm tests, matches the case files and the specification:
one row per case file, its expected column what the file states, and each heading the specification's row.
"""

import functools
import json
from collections.abc import Mapping, Sequence

import pytest

from materica.core.jsonio import JsonValue
from scripts.gen_vocabulary import SPECIFICATION, Row, only_code, table
from tests.conformance import runner
from tests.conformance.runner import CONFORMANCE, CaseFile

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


def expected_column(case_file: CaseFile) -> str:
    """The column as `CASES.md` writes it, from the case file: status and reasons with their condition and
    alternative, or that the two are not compared; the listing, the shortened hash, or a read's value, unit,
    alternative values and assumption, as JSON; then labels and claims (sorted) where the case states them. A
    table evaluation case's is its evaluations, as JSON, and its binary32 tolerance; a record-check case's its
    findings, its listing and the rules it compares; a `quote_sha256` operation's its status and shortened
    hash."""
    expected = case_file.expected
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
        parts.append(
            "claims "
            + ", ".join(
                code(f"{suite}: {str(claim).lower()}") for suite, claim in sorted(case_file.claims.items())
            )
        )
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

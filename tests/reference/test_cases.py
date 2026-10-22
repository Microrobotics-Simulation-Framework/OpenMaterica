# SPDX-License-Identifier: Apache-2.0
"""The reference model pinned to the conformance cases: it agrees with every case file of a read in the
repository, whatever step of the implementation runs it, or the case file is listed in `exceptions.py` under
its kind. The table evaluation and record-check suites are left out, being no reads (`cases.NOT_A_READ`).

The list is exact (the maintainer's ruling 3 on S2a-1's open points): a listed case file the model agrees with
is stale and fails, and so does a disagreement no kind lists. A case file on which the model gives no verdict
is a disagreement, never a pass. Where the model and a case disagree, the text decides: a fault of the model
is fixed; a case that contradicts the text is listed, with the quotes, and left for the maintainer, never
edited here (case files change through the case tools alone)."""

import re
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import pytest

from tests.conformance.runner import CaseFile
from tests.reference import read_model
from tests.reference.cases import Outcome, agreeing, answer, case_files, judged, outcome, read_case_files
from tests.reference.exceptions import EXCEPTIONS, Excepted
from tests.reference.strict_json import JsonObject


@pytest.mark.parametrize("case_file", read_case_files(), ids=lambda case_file: case_file.path.name)
def test_the_model_agrees_with_the_case_file(case_file: CaseFile) -> None:
    problem = judged(case_file.path.name, outcome(case_file), EXCEPTIONS)
    assert problem is None, problem


# The operations that are no read: a table evaluation, a record check and a quote hash.
NO_READ = ("evaluate", "check", "quote_sha256", "check_build")


def left_out_problems(every: tuple[CaseFile, ...], read: tuple[CaseFile, ...]) -> list[str]:
    """Each case file left out of the reads that is a read, and each kept that is none: an evaluation, a
    record check, a quote hash or a build check."""
    kept = {case_file.path.name for case_file in read}
    return [
        f"{case_file.path.name}: {'kept' if case_file.path.name in kept else 'left out'}"
        for case_file in every
        if (case_file.path.name in kept) == (case_file.operation in NO_READ)
    ]


def test_the_files_left_out_are_exactly_those_that_are_no_read() -> None:
    assert left_out_problems(case_files(), read_case_files()) == []
    assert len(case_files()) - len(read_case_files()) >= 35 + 197 + 50


def test_a_read_left_out_or_an_evaluation_or_check_kept_fails() -> None:
    read = read_case_files()
    assert left_out_problems(case_files(), read[1:]) == [f"{read[0].path.name}: left out"]
    for operation in NO_READ:
        other = next(case_file for case_file in case_files() if case_file.operation == operation)
        assert left_out_problems(case_files(), (*read, other)) == [f"{other.path.name}: kept"]


def test_every_listed_case_file_is_a_read_and_every_kind_gives_its_reason() -> None:
    names = {case_file.path.name for case_file in read_case_files()}
    for kind, excepted in EXCEPTIONS.items():
        assert excepted.reason.strip(), kind
        assert excepted.case_files, kind
        assert excepted.case_files <= names, sorted(excepted.case_files - names)


def test_no_verdict_is_listed_by_the_detail_it_gives() -> None:
    assert all(
        excepted.detail is not None for excepted in EXCEPTIONS.values() if excepted.outcome == "no verdict"
    )


DIFFERING = Excepted("a reason", "differs", frozenset({"listed.json"}))
TABLES = Excepted("a reason", "no verdict", frozenset({"listed.json"}), detail="a table")


@pytest.mark.parametrize(
    ("name", "found", "exceptions", "problem"),
    [
        ("listed.json", Outcome("agrees"), {}, None),
        ("listed.json", Outcome("differs"), {"kind": DIFFERING}, None),
        ("listed.json", Outcome("agrees"), {"kind": DIFFERING}, "a stale entry"),
        ("unlisted.json", Outcome("differs", "status"), {"kind": DIFFERING}, "no kind lists it"),
        ("unlisted.json", Outcome("no verdict", "a table"), {}, "no kind lists it"),
        ("listed.json", Outcome("no verdict"), {"kind": DIFFERING}, "but no verdict"),
        ("listed.json", Outcome("differs"), {"one": DIFFERING, "two": DIFFERING}, "listed under 2 kinds"),
        ("listed.json", Outcome("no verdict", "a table"), {"kind": TABLES}, None),
        ("listed.json", Outcome("no verdict", "a pick"), {"kind": TABLES}, "for 'a table', but 'a pick'"),
        ("listed.json", Outcome("agrees"), {"kind": TABLES}, "a stale entry"),
    ],
)
def test_the_list_can_fail(
    name: str, found: Outcome, exceptions: Mapping[str, Excepted], problem: str | None
) -> None:
    given = judged(name, found, exceptions)
    assert given == problem if problem is None else given is not None and problem in given


def test_a_fault_seeded_in_the_model_disagrees(monkeypatch: pytest.MonkeyPatch) -> None:
    """The comparison sees a model that drops the field's label (`read_side_contract.md` step 12)."""
    (case_file,) = [found for found in case_files() if found.path.name == "PR-035.linear_label_returned.json"]
    assert outcome(case_file).kind == "agrees"

    def no_labels(field_value: JsonObject, provenance: JsonObject) -> list[str]:
        return []

    monkeypatch.setattr(read_model, "step_12_labels", no_labels)
    assert outcome(case_file).kind == "differs"


# A case compares only the members its `compare` names (README.md, "Case files"), so no case file sees a
# member a result holds outside `read_side_contract.md` section 2's table. The model's whole result is held to
# the table's names here, read from the text.
RESULT_SECTION = "## 2. The read result"
SPECIFICATION = Path(__file__).resolve().parents[2] / "docs" / "specification"


def result_members() -> frozenset[str]:
    """The member names of `read_side_contract.md` section 2's table, as the text writes them."""
    text = (SPECIFICATION / "read_side_contract.md").read_text(encoding="utf-8")
    lines = text[text.index(RESULT_SECTION) :].splitlines()
    start = next(number for number, line in enumerate(lines) if line.startswith("|"))
    end = next(number for number, line in enumerate(lines[start:], start) if not line.startswith("|"))
    rows = lines[start + 2 : end]  # the header and its rule aside
    names = [re.match(r"^\| `([a-z_]+)` \|", row) for row in rows]
    assert all(names), rows
    return frozenset(name[1] for name in names if name)


def members_outside_the_table() -> Iterator[str]:
    """Each read's result, under each configuration of claims its case file allows, that holds a member the
    result table does not name."""
    members = result_members()
    for case_file in read_case_files():
        if case_file.operation != "read":
            continue
        for claims in agreeing(case_file):
            given = answer(case_file, claims)
            if isinstance(given, read_model.NoVerdict):
                break
            outside = sorted(set(given) - members)
            if outside:
                yield f"{case_file.path.name}, claiming {sorted(claims)}: {outside}"


def test_the_models_results_hold_no_member_outside_the_result_table() -> None:
    assert {"status", "reasons", "value", "labels", "assumption"} <= result_members()
    assert list(members_outside_the_table()) == []


def test_a_result_holding_a_labels_basis_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: a model that returns a field's `label_basis` beside the table's members, which the case files'
    comparisons pass (they compare only the members `compare` names)."""
    (case_file,) = [
        found for found in case_files() if found.path.name == "PR-030.label_basis_stated_not_returned.json"
    ]
    returned = read_model.result

    def with_its_basis(
        reasons: read_model.Reasons, labels: Sequence[str], members: JsonObject | None = None
    ) -> JsonObject:
        result = returned(reasons, labels, members)
        result["label_basis"] = {"basis": "stated"}
        return result

    monkeypatch.setattr(read_model, "result", with_its_basis)
    assert outcome(case_file).kind == "agrees"
    found = next(members_outside_the_table(), None)
    assert found is not None
    assert found.endswith("['label_basis']")

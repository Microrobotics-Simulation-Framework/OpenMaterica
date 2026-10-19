# SPDX-License-Identifier: Apache-2.0
"""The broken evaluators the conformance tests run (`EVALUATOR_FAULTS`) are the ones the table evaluation
suite's README names, each beside the files that should catch it and the difference it must fail them by.

The README's table, "The broken evaluators", is what the specification's cap on a file's `binary32` tolerance
counts: a file named beside no broken evaluator has no cap from that rule. So the list the tests run and the
table must be one list. A broken evaluator is compared by what the table states of it, the files and the
difference beside each, since the README names a fault in prose; two with the same files and differences
count twice.
"""

import re
from collections import Counter
from collections.abc import Iterable

from scripts.gen_vocabulary import Row, table
from tests.conformance.runner import CONFORMANCE, EVALUATOR_CLAIMS
from tests.conformance.test_runner_can_fail import (
    DERIVATIVE,
    EVALUATOR_FAULTS,
    IN_RANGE,
    NO_DERIVATIVE,
    NO_REFUSAL,
    NUMBER_BESIDE_THE_REFUSAL,
    REFUSAL_NOT_DUE,
    VALUE,
    Caught,
)

README = (CONFORMANCE / "table_evaluation" / "README.md").read_text(encoding="utf-8")
HEADING = "## The broken evaluators"

# What the README's "Fails by" column says for each difference the runner words.
FAILS_BY = {
    IN_RANGE: "`in_range`",
    NO_REFUSAL: "no refusal",
    NUMBER_BESIDE_THE_REFUSAL: "a number beside the refusal",
    NO_DERIVATIVE: "a derivative where none is due",
    REFUSAL_NOT_DUE: "a refusal where none is due",
    DERIVATIVE: "the derivative",
    VALUE: "the value",
    "raised ValueError": "raising",
}
# A cell of files: `TE-002 `linear`, TE-003 `just_outside_linear``, or more names after one file's series.
FILE = re.compile(r"(?:(TE-\d+) )?`([a-z0-9_]+)`")

Fault = frozenset[tuple[str, str]]


def listed_in_the_readme(rows: Iterable[Row]) -> Counter[Fault]:
    """Each README row as the (file, difference) pairs it states, counted."""
    found: Counter[Fault] = Counter()
    for row in rows:
        series = ""
        pairs: set[tuple[str, str]] = set()
        for token in row["Files that should catch it"].split(", "):
            matched = FILE.fullmatch(token)
            assert matched, f"a file cell not read: {token!r}"
            series = matched[1] or series
            pairs.add((f"{series}.{matched[2]}.json", row["Fails by"]))
        found[frozenset(pairs)] += 1
    return found


def run_by_the_tests(faults: Iterable[Caught]) -> Counter[Fault]:
    """Each broken evaluator the tests run as the (file, difference) pairs it must fail, counted."""
    by_fault: dict[str, set[tuple[str, str]]] = {}
    for caught in faults:
        by_fault.setdefault(caught.fault.__name__, set()).add((caught.catcher, FAILS_BY[caught.by]))
    return Counter(frozenset(pairs) for pairs in by_fault.values())


def differences(rows: Iterable[Row], faults: Iterable[Caught]) -> list[str]:
    """What the README's table names that the tests do not run, and what they run that it does not name."""
    named, run = listed_in_the_readme(rows), run_by_the_tests(faults)
    return [
        *(f"in the README only: {sorted(pairs)} x{count}" for pairs, count in (named - run).items()),
        *(f"in the tests only: {sorted(pairs)} x{count}" for pairs, count in (run - named).items()),
    ]


def test_the_broken_evaluators_the_tests_run_are_the_ones_the_readme_names() -> None:
    rows = table(README, HEADING)
    assert len(rows) >= 20
    assert differences(rows, EVALUATOR_FAULTS) == []


def test_only_the_bfloat16_evaluator_claims_binary32_alone() -> None:
    """The README says the `bfloat16` one claims `binary32` only, and every other claims all four."""
    assert "claims `binary32` only" in README
    named = [row for row in table(README, HEADING) if "bfloat16" in row["Fault"]]
    assert len(named) == 1
    partial = [caught for caught in EVALUATOR_FAULTS if caught.claims != EVALUATOR_CLAIMS]
    assert {caught.fault.__name__ for caught in partial} == {"rounds_binary32_results_to_bfloat16"}
    assert all({claim.precision for claim in caught.claims} == {"binary32"} for caught in partial)


def test_the_comparison_can_fail() -> None:
    rows = table(README, HEADING)
    # A row the tests do not run, a broken evaluator the README does not name, a file, a difference.
    assert differences(rows[1:], EVALUATOR_FAULTS)
    assert differences(rows, EVALUATOR_FAULTS[1:])
    assert differences(
        [{**rows[0], "Files that should catch it": "TE-002 `linear`, TE-002 `source_range_wide`"}, *rows[1:]],
        EVALUATOR_FAULTS,
    )
    assert differences([{**rows[0], "Fails by": "the value"}, *rows[1:]], EVALUATOR_FAULTS)
    assert differences(
        rows, [Caught(EVALUATOR_FAULTS[0].fault, "TE-003.narrowed.json", IN_RANGE), *EVALUATOR_FAULTS]
    )

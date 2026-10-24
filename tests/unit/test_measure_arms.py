# SPDX-License-Identifier: Apache-2.0
"""The measurement tool's judging arms, each held by a record or a run whose answer turns on it (the review of
the tool found most of them unheld: every arm here is one a hand mutant of `scripts/measure.py` survived).
`test_measure.py` holds the tool's plumbing; this file holds what it judges, the self-test's answers, the
base's own tree, and a fuzz control's find, miss and bar.

The floors record is the draft's own CI run (the self-test's floors job, 20 streams of
`test_one_slip_is_what_the_neighbour_generator_reaches`, counts as recorded); its pinned figures are an
independent computation (the review's, with its own binomial and the audits' `draw_floor`)."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import measure
from scripts.measure import Job
from tests.unit.test_measure import (
    SAMPLE,
    TARGET,
    fuzz_job,
    record,
    sample_tree,
)

SLIP = "tests/property/test_slip_properties.py::test_one_slip_is_what_the_neighbour_generator_reaches"
MODEL = {"cluster": 8, "shown": 5, "false_failure": 1e-6, "least_draws": 10, "judged_from": 20}

# The 20 streams' counts of the slip property's features, as CI recorded them.
SLIP_COUNTS: dict[str, list[int]] = json.loads(
    "{"
    '"added":[618,609,585,571,625,610,579,581,572,572,596,608,598,574,554,620,575,576,571,607],'
    '"far_swap":[150,122,132,113,108,122,123,112,131,137,129,132,128,101,119,120,135,150,148,128],'
    '"none":[797,877,858,876,810,873,908,842,878,881,903,883,820,857,900,850,878,852,856,855],'
    '"plural":[163,148,124,150,172,135,156,152,165,159,181,148,173,169,157,160,165,165,174,184],'
    '"substituted":[246,198,224,203,242,214,215,214,222,228,180,190,250,193,212,192,221,257,247,204],'
    '"swapped":[132,112,89,116,103,112,86,132,131,117,91,85,131,124,83,123,103,129,113,113],'
    '"through_an_empty_word":[303,335,308,309,279,348,352,333,320,277,343,306,278,328,311,310,318,303,310,325],'
    '"two_edits":[496,451,445,470,447,512,493,475,464,468,492,470,460,456,453,513,500,451,485,490],'
    '"underscore":[147,141,203,171,163,147,152,172,131,147,159,173,139,182,190,160,152,114,137,155]'
    "}"
)
SLIP_DECLARED = {
    "substituted": {"how": "features", "value": 0.021},
    "added": {"how": "features", "value": 0.048},
    "underscore": {"how": "features", "value": 0.018},
    "swapped": {"how": "features", "value": 0.012},
    "plural": {"how": "features", "value": 0.02},
    "none": {"how": "features", "value": 0.105},
    "two_edits": {"how": "features", "value": 0.042},
    "far_swap": {"how": "features", "value": 0.012},
    "through_an_empty_word": {"how": "chances", "value": 0.1},
}
# Mean, variance ratio, floor, then the false failure at the variance measured: at the mean share, at the
# share (the independent computation, to two figures).
SLIP_JUDGED = {
    "added": (0.295, 1.01, 96, 5.7e-174, 8.1e-156),
    "far_swap": (0.064, 1.49, 24, 7.6e-21, 1.7e-14),
    "none": (0.431, 1.78, 210, 3.3e-128, 1.1e-107),
    "plural": (0.080, 1.46, 40, 3.1e-22, 6.6e-14),
    "substituted": (0.109, 2.53, 42, 9.2e-22, 4.7e-16),
    "swapped": (0.056, 2.75, 24, 2.8e-10, 1.3e-06),
    "through_an_empty_word": (0.157, 1.77, 30, 4.7e-61, 3.5e-51),
    "two_edits": (0.237, 1.30, 84, 9.5e-100, 3.0e-89),
    "underscore": (0.078, 3.07, 36, 3.4e-12, 2.7e-07),
}


def drawn(
    node: str,
    stream: int,
    features: dict[str, int],
    declared: dict[str, dict[str, Any]],
    examples: int = 2000,
    floors: dict[str, int] | None = None,
    invalid: int = 0,
    outcome: str = "passed",
    model: dict[str, Any] = MODEL,
) -> dict[str, Any]:
    return {
        "node": node,
        "stream": stream,
        "examples": examples,
        "invalid": invalid,
        "features": features,
        "declared": declared,
        "floors": floors or {},
        "model": model,
        "outcome": outcome,
        "message": "AssertionError: x" if outcome != "passed" else "",
    }


def floors_record(
    runs: list[dict[str, Any]], job: Job | None = None, streams: list[int] | None = None
) -> dict[str, Any]:
    job = job or Job("floors-head-0-0", "floors", runs[0]["node"], 0, len(runs), expect="")
    return record(job) | {"runs": runs, "streams": streams or [run["stream"] for run in runs]}


def slip_runs(streams: range = range(20)) -> list[dict[str, Any]]:
    return [
        drawn(SLIP, stream, {name: counts[stream] for name, counts in SLIP_COUNTS.items()}, SLIP_DECLARED)
        | {"floors": {"through_an_empty_word": 30}}
        for stream in streams
    ]


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def table_rows(lines: list[str]) -> dict[str, list[str]]:
    return {cells(line)[1].strip("`"): cells(line) for line in lines[2:]}


# --- floors: the judgement at the variance measured ------------------------------------------------------


def test_floors_report_the_false_failure_at_the_mean_and_at_the_least_share_and_flag_the_least() -> None:
    lines, flags = measure.report_floors([floors_record(slip_runs())])
    rows = table_rows(lines)
    assert set(rows) == set(SLIP_JUDGED)
    for name, (mean, ratio, floor, at_mean, at_least) in SLIP_JUDGED.items():
        row = rows[name]
        assert float(row[4]) == pytest.approx(mean, abs=5e-4), name
        assert float(row[6]) == pytest.approx(ratio, abs=5e-3), name
        assert float(row[7]) == floor, name
        assert float(row[9]) == pytest.approx(at_mean, rel=0.05), name
        assert float(row[10]) == pytest.approx(at_least, rel=0.05), name
    assert float(rows["through_an_empty_word"][8]) == pytest.approx(5.8e-07, rel=0.05)  # at the model
    # `swapped` is under the bar at the mean share (2.8e-10) and over it at the least (1.3e-6): flagged.
    assert [flag.split("`")[1] for flag in flags] == ["swapped"], flags
    assert all(part in flags[0] for part in ("1.3e-06", "least share", "2.8e-10 at the mean"))


def test_floors_judge_a_feature_only_where_ci_does_and_flag_a_floor_it_fails_whatever_the_count() -> None:
    declared = {
        "thin": {"how": "features", "value": 0.005},  # 10 of 2,000: below JUDGED_FROM, not judged
        "deep": {"how": "deep_chances", "value": 0.3},  # judged at `deep` alone
        "low": {"how": "chances", "value": 0.0035},  # a floor of 8, below LEAST_DRAWS
        "held": {"how": "features", "value": 0.3},
    }
    counts = {"thin": 20, "deep": 600, "low": 30, "held": 900}
    runs = [drawn("n", stream, counts, declared, floors={"deep": 400, "low": 8}) for stream in range(3)]
    lines, flags = measure.report_floors([floors_record(runs)])
    rows = table_rows(lines)
    assert [rows[name][7] for name in ("thin", "deep", "low", "held")] == [
        "not at ci",
        "not at ci",
        "8",
        "600",
    ]
    assert flags == ["n `low`: a floor of 8, below 10, which `ci` fails whatever the count"], flags


def test_floors_flag_a_failed_run_and_a_run_that_rejects_over_the_audits_share() -> None:
    declared = {"a": {"how": "features", "value": 0.3}}
    runs = [
        drawn("n", 0, {"a": 900}, declared),
        drawn("n", 1, {"a": 900}, declared, outcome="failed"),
        drawn("n", 2, {"a": 900}, declared, invalid=1400),  # 1,400 of 3,400 draws: 41 %
    ]
    lines, flags = measure.report_floors([floors_record(runs)])
    assert flags == [
        "head n: stream 1 failed: AssertionError: x",
        "n: up to 41% of the draws rejected in a run, above the audit's 40%",
    ], flags
    assert table_rows(lines)["a"][-1] == "41%"
    runs[2]["invalid"] = 1300  # 39 %
    assert measure.report_floors([floors_record(runs)])[1] == flags[:1]


FAILING = """
import pytest
from hypothesis import given, settings, strategies as st


@settings(max_examples=50)
@given(st.integers())
def test_fails(number):
    assert False, "the check fails"
"""


def test_a_failing_check_ends_its_streams_run_and_is_recorded_as_failed_and_flagged(tmp_path: Path) -> None:
    tree = sample_tree(tmp_path / "tree")
    (tree / "tests" / "property" / "test_failing_properties.py").write_text(FAILING, encoding="utf-8")
    node = "tests/property/test_failing_properties.py::test_fails"
    done = measure.run_job(Job("j", "floors", node, 0, 2), tmp_path / "out", 2, tree)
    assert [run["outcome"] for run in done["runs"]] == ["failed", "failed"]
    assert all("the check fails" in run["message"] for run in done["runs"])
    _, flags = measure.report_floors([done | {"job": done["job"] | {"side": "head"}}])
    assert len(flags) == 2, flags
    assert all("failed: AssertionError: the check fails" in flag for flag in flags), flags


DIES = """
import os
from pathlib import Path
from hypothesis import given, settings, strategies as st


@settings(max_examples=50)
@given(st.integers())
def test_dies_in_its_second_stream(number):
    calls = Path(os.environ["CALLS"])
    calls.write_text(str(int(calls.read_text() or 0) + 1) if calls.exists() else "1")
    if int(calls.read_text()) > 75:
        os._exit(3)
"""


def test_a_stream_that_never_finished_is_named_and_its_process_status_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = sample_tree(tmp_path / "tree")
    (tree / "tests" / "property" / "test_dies_properties.py").write_text(DIES, encoding="utf-8")
    monkeypatch.setenv("CALLS", str(tmp_path / "calls"))
    node = "tests/property/test_dies_properties.py::test_dies_in_its_second_stream"
    done = measure.run_job(Job("j", "floors", node, 0, 2), tmp_path / "out", 1, tree)
    assert [run["stream"] for run in done["runs"]] == [0]
    assert done["problems"] == ["pytest 0 exited 3 (pytest-0.log)", f"{node}: no run of stream 1"], done[
        "problems"
    ]


# --- the self-test's answers --------------------------------------------------------------------------------


def self_floors(runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    runs = slip_runs() if runs is None else runs
    return floors_record(runs, Job("self0-floors", "floors", SLIP, 0, 20, expect="counted"))


def test_the_floors_answer_holds_for_the_recorded_counts_and_a_flag_does_not_fail_it() -> None:
    assert measure.SELF_FLOORS_STREAM_0 == {name: counts[0] for name, counts in SLIP_COUNTS.items()}
    found = self_floors()
    flags = measure.report([found])[1]
    assert len(flags) == 1  # `swapped`, at the least share
    assert measure.expectations([found], flags) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ("empty", "no run was counted"),
        ("zero_examples", "stream 3 counted no examples"),
        ("fewer_examples", "stream 2 drew 1999 examples, not 2000"),
        ("stream_0_moved", "stream 0 did not count what it counted before"),
        ("feature_never_counted", "the declared feature `swapped` was never counted"),
    ],
)
def test_the_floors_answer_fails_where_nothing_was_counted_or_not_what_was_recorded(
    change: str, problem: str
) -> None:
    runs = slip_runs()
    match change:
        case "empty":
            runs = []
        case "zero_examples":
            runs[3]["examples"] = 0
        case "fewer_examples":
            runs[2]["examples"] = 1999
        case "stream_0_moved":
            runs[0]["features"]["added"] += 1
        case "feature_never_counted":
            for run in runs:
                run["features"]["swapped"] = 0
        case _:
            raise AssertionError(change)
    problems = measure.expectations([self_floors(runs)], [])
    assert any(problem in each for each in problems), (change, problems)
    if change == "feature_never_counted":
        assert any("stream 0 did not count" in each for each in problems)  # both answers see it


def regions_pair(
    base_features: dict[str, int],
    head_features: dict[str, int],
    streams: int = 2,
    head_examples: int = 2000,
    head_outcome: str = "passed",
) -> list[dict[str, Any]]:
    declared = {"a": {"how": "features", "value": 0.3}}
    pair: list[dict[str, Any]] = []
    for side, features in (("base", base_features), ("head", head_features)):
        job = Job(f"self2-regions-{side}", "regions", SLIP, 0, streams, side, "c" * 40, expect="ratio_one")
        head = side == "head"
        runs = [
            drawn(
                SLIP,
                s,
                features,
                declared,
                examples=head_examples if head else 2000,
                outcome=head_outcome if head else "passed",
            )
            for s in range(streams)
        ]
        pair.append(floors_record(runs, job))
    return pair


def test_the_regions_answer_holds_for_equal_shares_and_fails_for_a_ratio_a_missing_side_or_no_count() -> None:
    same = regions_pair({"a": 600}, {"a": 600})
    flags = measure.report(same)[1]
    assert flags == []
    assert measure.expectations(same, flags) == []
    # a ratio other than 1: the report's flag is the answer failing
    off = regions_pair({"a": 600}, {"a": 300})
    flags = measure.report(off)[1]
    assert any("of the base's mean share" in flag for flag in flags)
    assert any("share ratio other than 1" in each for each in measure.expectations(off, flags))
    alone = measure.expectations(off, ["x: measured on the base alone"])
    assert any("share ratio other than 1" in each for each in alone)
    # a side missing
    assert measure.expectations(same[:1], []) == ["the regions self-test lacks a side"]
    # nothing counted on either side: a ratio of 0 over 0 is 1, and is no answer
    nothing = regions_pair({}, {})
    flags = measure.report(nothing)[1]
    problems = measure.expectations(nothing, flags)
    assert sum("the declared feature `a` was never counted" in each for each in problems) == 2, problems


def test_the_drift_answer_fails_where_stream_0_is_not_the_recorded_kill_or_none_is_recorded() -> None:
    def search(kill: int | None, recorded: int | None) -> dict[str, Any]:
        job = Job("self1-drift", "drift", "s", 0, 2, expect="recorded")
        runs = [{"node": "s", "stream": 0, "kill": kill, "status": "killed", "message": ""}]
        return record(job) | {"runs": runs, "recorded": {"s": recorded}}

    assert measure.expectations([search(7, 7)], []) == []
    assert measure.expectations([search(8, 7)], []) == ["self1-drift: stream 0 is not the recorded kill"]
    assert measure.expectations([search(None, None)], []) == [
        "self1-drift: stream 0 is not the recorded kill"
    ]
    assert measure.expectations([search(None, 7)], []) == ["self1-drift: stream 0 is not the recorded kill"]
    nothing = search(7, 7)
    nothing["runs"] = []
    assert measure.expectations([nothing], []) == ["self1-drift: stream 0 is not the recorded kill"]


KILLS: dict[str, Any] = {
    "tool": "measure",
    "measured": {"g": {"m1": {"small": 10, "original": 700}, "m2": {"small": 5, "original": 6}}},
    "base_recorded": {"g": {"m1": [10, 600], "m2": [5, 6]}},
    "head_recorded": {"g": {"m1": [10, 700], "m2": [7, 6]}},
    "problems": [],
}


def test_the_kills_answer_fails_where_a_kill_moved_from_the_heads_record() -> None:
    assert measure.kills_moved(KILLS | {"head_recorded": {"g": {"m1": [10, 700], "m2": [5, 6]}}})[1] == [
        "g m1 original: killed at 700, past the margin guard at 500"
    ]
    job = Job("self2-kills", "kills", base="c" * 40, expect="ratio_one")
    answer = record(job) | KILLS
    assert "self2-kills: a tree against itself moved a kill" in measure.expectations([answer], [])
    clean = (
        record(job)
        | KILLS
        | {"measured": {"g": {"m1": {"small": 10, "original": 500}}}}
        | {
            "base_recorded": {"g": {"m1": [10, 500]}},
            "head_recorded": {"g": {"m1": [10, 500]}},
        }
    )
    assert "self2-kills: a tree against itself moved a kill" not in measure.expectations([clean], [])


def test_kills_moved_lists_a_moved_kill_and_flags_one_past_the_guard_and_one_off_the_heads_record() -> None:
    lines, flags = measure.kills_moved(KILLS)
    assert lines[0] == "Mutant searches run at the head: 4; kills that moved from the base's record: 1."
    assert "| `g` | `m1` | original | 600 | 700 |" in lines
    assert flags == [
        "g m1 original: killed at 700, past the margin guard at 500",
        "g m2 small: killed at 5, the head records 7",
    ]
    none_moved = KILLS | {"base_recorded": {"g": {"m1": [10, 700], "m2": [5, 6]}}}
    assert measure.kills_moved(none_moved)[0] == [
        "Mutant searches run at the head: 4; kills that moved from the base's record: 0."
    ]
    assert (
        measure.kills_moved(KILLS | {"problems": ["a mutant search failed"]})[1][-1]
        == "a mutant search failed"
    )


SEARCHES = """
def test_a_search_that_records_its_kill_then_fails_its_assertion(record_property):
    record_property("examples_to_kill", 7)
    raise AssertionError("no_pick")


def test_a_search_that_survives(record_property):
    raise AssertionError("survived 2000")


def test_a_search_that_is_killed(record_property):
    record_property("examples_to_kill", 5)


def test_a_search_that_errors(record_property):
    raise ValueError("broken")
"""


def test_a_search_is_killed_killed_elsewhere_survived_or_in_error_as_it_ends(tmp_path: Path) -> None:
    tree = sample_tree(tmp_path / "tree")
    (tree / "tests" / "property" / "test_sample_mutants.py").write_text(SEARCHES, encoding="utf-8")
    nodes = " ".join(
        f"tests/property/test_sample_mutants.py::test_a_search_{each}"
        for each in (
            "that_records_its_kill_then_fails_its_assertion",
            "that_survives",
            "that_is_killed",
            "that_errors",
        )
    )
    done = measure.run_job(Job("j", "drift", nodes, 0, 1), tmp_path / "out", 1, tree)
    got = {run["node"].split("::")[1]: (run["status"], run["kill"]) for run in done["runs"]}
    assert got == {
        "test_a_search_that_records_its_kill_then_fails_its_assertion": ("killed elsewhere", 7),
        "test_a_search_that_survives": ("survived", None),
        "test_a_search_that_is_killed": ("killed", 5),
        "test_a_search_that_errors": ("error", None),
    }


def test_a_failed_stream_that_drew_examples_and_counted_features_is_a_problem_of_the_self_test() -> None:
    runs = slip_runs()
    runs[4] = drawn(SLIP, 4, runs[4]["features"], SLIP_DECLARED, outcome="failed")
    found = self_floors(runs)
    assert measure.counted_problems(found) == [f"self0-floors: {SLIP} stream 4 ended failed"]
    assert f"self0-floors: {SLIP} stream 4 ended failed" in measure.expectations([found], [])
    # the regions answer has no count of its own to catch it: a head whose every stream failed is a problem
    pair = regions_pair({"a": 600}, {"a": 600}, head_outcome="failed")
    flags = measure.report(pair)[1]
    assert flags, "the report flags the failed streams, and a flag does not fail the self-test"
    problems = measure.expectations(pair, flags)
    assert [each for each in problems if "ended failed" in each] == [
        f"self2-regions-head: {SLIP} stream {stream} ended failed" for stream in range(2)
    ]


def test_the_regions_answer_holds_each_stream_to_the_examples_the_floors_answer_does() -> None:
    assert measure.expectations(regions_pair({"a": 600}, {"a": 600}), []) == []
    pair = regions_pair({"a": 600}, {"a": 600}, head_examples=1999)
    problems = measure.expectations(pair, measure.report(pair)[1])
    assert problems == [
        f"self2-regions-head: stream {stream} drew 1999 examples, not 2000" for stream in range(2)
    ], problems


# --- the summary's report: the rule's count over a split job ------------------------------------------------


def split(first: int, last: int) -> dict[str, Any]:
    runs = slip_runs(range(first, last))
    job = Job(f"floors-head-0-{first}", "floors", SLIP, first, last - first)
    return floors_record(runs, job)


def test_a_count_below_the_rules_is_said_over_all_the_records_of_a_function_not_each_one() -> None:
    whole = measure.report([split(0, 10), split(10, 20)])[0]
    assert "fewer than the rule's" not in whole
    short = measure.report([split(0, 10)])[0]
    assert "10 streams, fewer than the rule's 20: this measures, and does not meet the rule." in short
    overlap = measure.report([split(0, 10), split(10, 15)])[0]
    assert "15 streams, fewer than the rule's 20" in overlap


def test_the_rules_count_is_held_against_the_least_function_the_least_side_and_the_least_fuzz_control() -> (
    None
):
    # two functions, 20 streams and 12: the least is the short one's, whichever job runs which
    other = "tests/property/test_other_properties.py::test_other"
    short = floors_record(
        [drawn(other, s, {"a": 600}, {"a": {"how": "features", "value": 0.3}}) for s in range(12)],
        Job("floors-head-1-0", "floors", other, 0, 12),
    )
    both = [split(0, 20), short]
    assert measure.least_counted(both) == 12
    assert "12 streams, fewer than the rule's 20: this measures" in measure.report(both)[0]
    # regions: 10 streams a side are 10, not the 20 of both sides; the short side is the count
    assert measure.least_counted(regions_pair({"a": 600}, {"a": 600}, streams=10)) == 10
    assert (
        "10 streams, fewer than the rule's 18" in measure.report(regions_pair({"a": 600}, {"a": 600}, 10))[0]
    )
    assert measure.least_counted(regions_pair({"a": 600}, {"a": 600}, streams=18)) == 18
    uneven = [regions_pair({"a": 600}, {"a": 600}, streams=18)[0], regions_pair({"a": 600}, {"a": 600}, 5)[1]]
    assert measure.least_counted(uneven) == 5
    # fuzz: a control's runs, the least over the controls and their faults
    assert measure.least_counted(fuzz_records(10, 10, 5.0)) == 10
    assert "fewer than the rule's" not in measure.report(fuzz_records(10, 10, 5.0))[0]
    assert "7 runs, fewer than the rule's 10" in measure.report(fuzz_records(7, 7, 5.0))[0]
    mixed = fuzz_records(10, 10, 5.0) + fuzz_records(0, 4, 180.0, "none")
    assert measure.least_counted(mixed) == 4
    # a job that wrote no run: the streams it was given
    assert (
        measure.least_counted(
            [floors_record([], Job("floors-head-0-0", "floors", SLIP, 0, 6), list(range(6)))]
        )
        == 6
    )


# --- regions: the base's own tree ---------------------------------------------------------------------------


FAKE_UV = """#!PYTHON
import os, sys
from pathlib import Path

args = sys.argv[1:]
if args[:4] != ["run", "--locked", "--quiet", "--directory"] or args[5:6] != ["python"]:
    print("uv: not the base's locked environment: " + " ".join(args), file=sys.stderr)
    sys.exit(97)
tree = Path(args[4])
with open("CALLS", "a", encoding="utf-8") as calls:
    calls.write(str(tree) + "\\n")
rest = args[6:]
pretend = tree / "pretend-python"
if rest[:1] == ["-c"] and pretend.exists():
    print(pretend.read_text().strip())
    sys.exit(0)
if "--collect-only" not in rest and (tree / "quiet-pytest").exists():
    sys.exit(0)
os.execv("PYTHON", ["PYTHON", *rest])
"""


def fake_uv(directory: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `uv` first on the PATH that stands for the base's own environment: it refuses any call but
    `uv run --locked --quiet --directory <tree> python ...`, runs the tree's pytest with this interpreter, and
    reports the Python a tree pretends to have (its file `pretend-python`), as a tree whose lock and Python
    differ from the head's would. It writes the tree of each call to the file it returns."""
    directory.mkdir()
    calls = directory / "calls.txt"
    uv = directory / "uv"
    uv.write_text(
        FAKE_UV.replace("PYTHON", sys.executable).replace("CALLS", str(calls)),
        encoding="utf-8",
    )
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return calls


def git(root: Path, *words: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *words],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def committed(tree: Path, message: str) -> str:
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "-m", message)
    return git(tree, "rev-parse", "HEAD")


def test_the_base_is_measured_in_its_own_exported_tree_and_environment_and_a_node_it_lacks_is_the_heads_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_uv(tmp_path / "bin", monkeypatch)
    thin_at = SAMPLE.index('\n\n@settings(max_examples=2000)\n@pytest.mark.drawn("common"')
    ways_only = SAMPLE[:thin_at] + "\n"
    tree = sample_tree(tmp_path / "tree")
    path = tree / "tests" / "property" / "test_sample_properties.py"
    path.write_text(ways_only, encoding="utf-8")
    (tree / "pretend-python").write_text("9.9.9\n", encoding="utf-8")  # the base's lock and Python differ
    git(tree, "init", "-q")
    base = committed(tree, "base: three ways, no thin property, its own Python")
    head_text = SAMPLE.replace("st.sampled_from(WAYS)", 'st.sampled_from(("a", "b"))')  # a way dropped
    path.write_text(head_text, encoding="utf-8")
    (tree / "pretend-python").unlink()
    committed(tree, "head: way c dropped, a thin property added")
    file = "tests/property/test_sample_properties.py"
    nodes = f"{file}::test_ways {file}::test_thin"
    # the base given as a ref: the record names the commit the archive resolved it to
    base_job = Job("b", "regions", nodes, 0, 2, "base", "HEAD~1")
    base_record = measure.run_job(base_job, tmp_path / "base", 2, tree)
    head_record = measure.run_job(Job("h", "regions", nodes, 0, 2, "head", base), tmp_path / "head", 2, tree)
    # run in the exported tree, which git archive named: the commit it holds and the Python of its environment
    assert base_record["commit"] == base
    assert base_record["python"] == "9.9.9"
    assert base_record["problems"] == [], base_record["problems"]
    assert {run["node"] for run in base_record["runs"]} == {f"{file}::test_ways"}
    assert head_record["commit"].startswith(git(tree, "rev-parse", "HEAD"))
    assert "python" not in head_record or head_record["python"] != "9.9.9"
    # every `uv run --locked` of the base was in a tree exported for it (the head's tree is not one)
    used = set(calls.read_text(encoding="utf-8").split())
    assert used
    assert all(Path(each).name.startswith("measure-base-") for each in used), used
    flags = measure.report_regions([base_record, head_record])[1]
    assert flags == [
        f"{file}::test_thin: measured on the head alone",
        f"{file}::test_ways `c`: 0.00 of the base's mean share, below 0.8",
        f"{file}::test_ways `c`: least share 0.0000 below its floor 245 of 2000",
    ], flags


@pytest.mark.parametrize("held", ["a file the base lacks", "a file the base holds no test in"])
def test_a_base_that_holds_none_of_the_nodes_is_a_flag_for_each_and_no_problem(
    held: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_uv(tmp_path / "bin", monkeypatch)
    tree = sample_tree(tmp_path / "tree")
    sample = tree / "tests" / "property" / "test_sample_properties.py"
    if held == "a file the base lacks":
        sample.unlink()
        (tree / "tests" / "property" / "test_other_properties.py").write_text(
            "def test_x():\n    pass\n", encoding="utf-8"
        )
    else:
        sample.write_text("# no test yet\n", encoding="utf-8")  # pytest exits 5: no tests collected
    git(tree, "init", "-q")
    base = committed(tree, "base")
    node = "tests/property/test_sample_properties.py::test_thin"
    done = measure.run_job(Job("b", "regions", node, 0, 2, "base", base), tmp_path / "base", 2, tree)
    assert done["problems"] == []
    assert done["runs"] == []


@pytest.mark.parametrize(
    ("break_it", "named"),
    [
        ("conftest", "ImportError"),  # pytest exits 4
        ("options", "unrecognized arguments"),  # pytest exits 4
        ("test_file", "SyntaxError"),  # pytest exits 2
    ],
)
def test_a_base_whose_own_collection_fails_is_a_problem_not_a_base_that_lacks_the_nodes(
    break_it: str, named: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_uv(tmp_path / "bin", monkeypatch)
    tree = sample_tree(tmp_path / "tree")
    match break_it:
        case "conftest":
            (tree / "tests" / "conftest.py").write_text(
                "import a_dependency_the_lock_lacks\n", encoding="utf-8"
            )
        case "options":
            (tree / "pytest.ini").write_text(
                (tree / "pytest.ini").read_text(encoding="utf-8") + "addopts = --a-flag-pytest-lacks\n",
                encoding="utf-8",
            )
        case _:
            (tree / "tests" / "property" / "test_sample_properties.py").write_text(
                "def (:\n", encoding="utf-8"
            )
    git(tree, "init", "-q")
    base = committed(tree, "base: a collection that fails")
    node = "tests/property/test_sample_properties.py::test_thin"
    with pytest.raises(measure.MeasureError) as raised:
        measure.run_job(Job("b", "regions", node, 0, 2, "base", base), tmp_path / "base", 2, tree)
    assert named in str(raised.value), raised.value


def test_a_base_with_nodes_whose_pytest_ran_none_of_them_is_a_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_uv(tmp_path / "bin", monkeypatch)
    tree = sample_tree(tmp_path / "tree")
    (tree / "quiet-pytest").write_text(
        "", encoding="utf-8"
    )  # the fake uv's pytest run exits 0 and writes nothing
    git(tree, "init", "-q")
    base = committed(tree, "base")
    node = "tests/property/test_sample_properties.py::test_thin"
    done = measure.run_job(Job("b", "regions", node, 0, 2, "base", base), tmp_path / "base", 2, tree)
    assert done["runs"] == []
    assert done["problems"] == ["no test of the job ran"], done["problems"]


# --- fuzz: the control's fault, find, miss and bar ----------------------------------------------------------

# A target that runs as libFuzzer does: its seconds when nothing is found, the find at once where the fault it
# is seeded with is its own.
FAULT_TARGET = """
import os, sys, time
from pathlib import Path
if "--seed" in sys.argv:
    Path(sys.argv[sys.argv.index("--seed") + 1]).mkdir()
    sys.exit(0)
if "--dict" in sys.argv:
    Path(sys.argv[sys.argv.index("--dict") + 1]).write_text("x")
    sys.exit(0)
if {corpus!r} and not Path(sys.argv[1]).is_dir():
    print("the corpus was not written")
    sys.exit(2)
limit = [int(a.partition("=")[2]) for a in sys.argv if a.startswith("-max_total_time=")][0]
print("#2\\tINITED cov: 1")
if os.environ.get("MATERICA_FUZZ_SEEDED_FAULT") == {fault!r}:
    print({line!r})
    sys.exit(1)
time.sleep(limit)
print("Done 4096 runs in 1 second(s)")
"""


def write_target(tree: Path, name: str, fault: str, line: str, corpus: bool = False) -> None:
    (tree / "tests" / "fuzz" / f"{name}.py").write_text(
        FAULT_TARGET.format(fault=fault, line=line, corpus=corpus), encoding="utf-8"
    )


def test_a_control_is_run_with_its_own_fault_and_its_corpus_written_first(tmp_path: Path) -> None:
    tree = sample_tree(tmp_path / "tree")
    line = "AssertionError: the implementation gives ['form_invalid'], the model []"
    write_target(tree, "read_field_bytes", "tables", line, corpus=True)
    found = measure.run_fuzz(
        Job("f", "fuzz", control="tables", fault="tables"), tmp_path / "found", 1, tree, seconds=3
    )
    assert (found["found"], found["line"], found["status"], found["problems"]) == (True, line, 1, [])
    # with none seeded the same target runs its seconds and finds nothing: the fault it found was its own
    none = measure.run_fuzz(
        Job("f", "fuzz", control="tables", fault="none"), tmp_path / "none", 1, tree, seconds=3
    )
    assert (none["found"], none["status"], none["problems"]) == (False, 0, [])
    assert measure.CONTROLS["tables"].fault == "tables"


def test_a_run_that_ended_early_without_the_find_or_ran_no_input_is_a_problem(tmp_path: Path) -> None:
    tree = sample_tree(tmp_path / "tree")
    (tree / "tests" / "fuzz" / "properties.py").write_text("raise SystemExit(1 / 0)\n", encoding="utf-8")
    for fault in ("none", "1"):  # a target that fails at import finds nothing with or without the fault
        done = measure.run_fuzz(fuzz_job(fault), tmp_path / fault, 1, tree, seconds=3)
        assert (done["found"], done["inputs"], done["status"]) == (False, 0, 1)
        assert done["problems"] == ["the target ran no input (see fuzz.log)"], done["problems"]
    (tree / "tests" / "fuzz" / "properties.py").write_text(
        TARGET.replace("time.sleep(limit)", ""), encoding="utf-8"
    )
    early = measure.run_fuzz(fuzz_job("none"), tmp_path / "early", 1, tree, seconds=3)
    assert (early["inputs"], early["status"]) == (4096, 0)
    assert early["problems"] == [
        "the target ended with status 0 after 0 s of its 3, without the control's find (see fuzz.log)"
    ], early["problems"]


def fuzz_records(
    finds: int, runs: int, seconds: float, fault: str = "1", name: str = "properties"
) -> list[dict[str, Any]]:
    return [
        record(Job(f"fuzz-{name}-{number}", "fuzz", first=number, control=name, fault=fault))
        | {
            "control": name,
            "fault": fault,
            "found": number < finds,
            "line": "IndexError: x",
            "seconds": seconds,
            "inputs": 1000,
            "limit": measure.CONTROLS[name].seconds,
        }
        for number in range(runs)
    ]


def test_a_control_that_missed_a_run_or_whose_pair_misses_over_the_bar_is_flagged() -> None:
    assert measure.report_fuzz(fuzz_records(10, 10, 5.0))[1] == []
    missed = measure.report_fuzz(fuzz_records(9, 10, 5.0))[1]
    assert missed == ["properties: 1 of 10 runs found no fault within 180 s"], missed
    # all ten found, at 78 s each: 0.0128 a second, a pair missing with 0.0099 (over 1e-3, under 1e-1)
    slow = measure.report_fuzz(fuzz_records(10, 10, 78.2))[1]
    assert len(slow) == 1
    assert slow[0].startswith("properties: a pair misses with 1.0e-02"), slow
    assert "above the bar of 1e-3" in slow[0]
    # at no fault, a find is the control's failure and a pair's bar is not asked
    assert measure.report_fuzz(fuzz_records(0, 10, 180.0, "none"))[1] == []
    assert measure.report_fuzz(fuzz_records(1, 10, 180.0, "none"))[1] == [
        "properties with no fault seeded found one: IndexError: x"
    ]


# --- fetch, where a download fails --------------------------------------------------------------------------


def test_fetch_downloads_the_artifacts_one_by_one_where_the_bulk_download_fails_and_counts_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    ids = {"record-a": "floors-head-0-0", "record-flaky": "floors-head-0-1", "record-bad": "floors-head-0-2"}
    payloads = {
        name: json.dumps(record(Job(job, "floors", SLIP, 0, 2)) | {"streams": [0, 1]})
        for name, job in ids.items()
    }
    # the matrix has a fourth job, which kept no record at all
    matrix = json.dumps([*ids.values(), "floors-head-0-3"])
    gh = bin_directory / "gh"
    gh.write_text(
        f"#!{sys.executable}\nimport sys, pathlib\nargs = sys.argv[1:]\n"
        "if args[0] == 'api':\n"
        "    print('record-a\\nrecord-flaky\\nrecord-bad\\nmeasure-table-1')\n    sys.exit(0)\n"
        "if '-p' in args:\n    sys.exit(1)\n"
        "name = args[args.index('-n') + 1]\n"
        "if name == 'record-bad':\n    sys.exit(1)\n"
        "flaky = pathlib.Path(sys.argv[0]).parent / 'flaky-tried'\n"
        "if name == 'record-flaky' and not flaky.exists():\n    flaky.write_text('x')\n    sys.exit(1)\n"
        "d = pathlib.Path(args[args.index('-D') + 1])\nd.mkdir(parents=True)\n"
        f"payloads = {payloads!r}\n"
        f"(d / 'matrix.json' if name.startswith('measure-table') else d / 'record.json').write_text("
        f"{matrix!r} if name.startswith('measure-table') else payloads[name])\n",
        encoding="utf-8",
    )
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_directory}{os.pathsep}{os.environ['PATH']}")
    assert measure.main(["fetch", "123"]) == 1
    out = capsys.readouterr().out
    assert "## floors" in out
    assert "1 artifacts not downloaded: record-bad" in out
    assert "record-flaky" not in out  # downloaded on its second try
    assert "2 records;" in out
    # counted against the matrix: the artifact that was not had and the job that never ran are both named
    assert "job floors-head-0-2: no record" in out
    assert "job floors-head-0-3: no record" in out
    assert "job floors-head-0-1: no record" not in out

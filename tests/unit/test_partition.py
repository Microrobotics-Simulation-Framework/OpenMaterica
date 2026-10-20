# SPDX-License-Identifier: Apache-2.0
"""The parts of a run (`tests/partition.py`) hold every selected test once, whatever the weights.

CI splits its longest jobs into parts that run side by side, and a test in none of a job's parts would run
nowhere, a test in two would run twice. So the assignment is held to a partition on many random selections,
weights and counts, with controls that fail where a test is in no part and where it is in two; the pytest
options that choose a part refuse what is not one; and the recorder of the weights reads a JUnit report as
it says. Which parts CI's matrices run, and that together they hold the real suite once, is
`test_ci_workflows.py`'s.
"""

import json
import os
import random
import subprocess
import sys
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

import pytest

from tests import partition

REPOSITORY = Path(__file__).resolve().parents[2]


def exactly_once(parts: Sequence[Collection[str]], whole: Collection[str]) -> list[str]:
    """Where the parts are no partition of the whole: a test in none of them, or in more than one, and a test
    in a part that is not in the whole."""
    seen = Counter(test for part in parts for test in part)
    return (
        [f"{test} is in no part" for test in sorted(set(whole) - seen.keys())]
        + [f"{test} is in {count} parts" for test, count in sorted(seen.items()) if count > 1]
        + [f"{test} is not in the whole" for test in sorted(seen.keys() - set(whole))]
    )


def parts_by_name(nodeids: Sequence[str], count: int, weights: Mapping[str, float]) -> list[list[str]]:
    assigned = partition.parts_of(nodeids, count, weights)
    return [
        [test for test, part in zip(nodeids, assigned, strict=True) if part == index]
        for index in range(count)
    ]


def random_selection(generator: random.Random) -> tuple[list[str], Mapping[str, float], int]:
    nodeids = [
        f"tests/unit/test_{generator.randrange(30)}.py::test_{number}"
        for number in range(generator.randrange(80))
    ]
    # Some listed, some not, ties and zeros among them.
    weights = {
        test: generator.choice([0.0, 1.0, 1.0, 2.5, generator.uniform(0, 300)])
        for test in nodeids
        if generator.random() < 0.6
    }
    return nodeids, weights, generator.randrange(1, 9)


def test_the_parts_of_a_selection_hold_every_test_once() -> None:
    generator = random.Random(20261020)
    for _ in range(400):
        nodeids, weights, count = random_selection(generator)
        parts = parts_by_name(nodeids, count, weights)
        assert len(parts) == count
        assert exactly_once(parts, nodeids) == []


def test_a_test_dropped_from_a_part_is_found_in_no_part() -> None:
    nodeids = [f"tests/unit/test_a.py::test_{number}" for number in range(10)]
    parts = parts_by_name(nodeids, 3, {})
    dropped, parts[1] = parts[1][0], parts[1][1:]
    assert exactly_once(parts, nodeids) == [f"{dropped} is in no part"]


def test_a_test_in_two_parts_is_found_in_two() -> None:
    nodeids = [f"tests/unit/test_a.py::test_{number}" for number in range(10)]
    parts = parts_by_name(nodeids, 3, {})
    parts[2] = [*parts[2], parts[0][0]]
    assert exactly_once(parts, nodeids) == [f"{parts[0][0]} is in 2 parts"]


def test_a_part_with_a_test_the_whole_lacks_is_found() -> None:
    nodeids = ["tests/unit/test_a.py::test_one", "tests/unit/test_a.py::test_two"]
    assert exactly_once([nodeids[:1], [*nodeids[1:], "tests/unit/test_a.py::test_three"]], nodeids) == [
        "tests/unit/test_a.py::test_three is not in the whole"
    ]


def test_a_part_count_of_one_holds_everything_and_none_is_refused() -> None:
    nodeids = ["tests/unit/test_a.py::test_one", "tests/unit/test_a.py::test_two"]
    assert partition.parts_of(nodeids, 1, {}) == [0, 0]
    with pytest.raises(ValueError, match="0 parts"):
        partition.parts_of(nodeids, 0, {})


def test_the_same_tests_come_out_the_same_in_any_order() -> None:
    """Every part computes the assignment from its own collection, so the order the tests are collected in
    must not matter, and a test must not move when the others are shuffled."""
    generator = random.Random(7)
    for _ in range(100):
        nodeids, weights, count = random_selection(generator)
        shuffled = generator.sample(nodeids, len(nodeids))
        before = dict(zip(nodeids, partition.parts_of(nodeids, count, weights), strict=True))
        after = dict(zip(shuffled, partition.parts_of(shuffled, count, weights), strict=True))
        assert before == after


def loads_of(taken: Sequence[float], assigned: Sequence[int], count: int) -> list[float]:
    loads = [0.0] * count
    for seconds, part in zip(taken, assigned, strict=True):
        loads[part] += seconds
    return loads


def is_even(loads: Sequence[float], taken: Sequence[float]) -> bool:
    """The bound that longest-processing-time-first keeps: the heaviest part is at most the mean part and the
    heaviest test less its share of one."""
    count = len(loads)
    return max(loads) <= sum(taken) / count + max(taken) * (1 - 1 / count) + 1e-9


def test_the_heaviest_tests_go_to_the_lightest_parts_so_that_no_part_is_far_from_the_mean() -> None:
    generator = random.Random(11)
    for _ in range(200):
        nodeids, weights, count = random_selection(generator)
        if not nodeids:
            continue
        taken = [weights.get(test, partition.DEFAULT_SECONDS) for test in nodeids]
        assert is_even(loads_of(taken, partition.parts_of(nodeids, count, weights), count), taken)


def test_the_evenness_check_can_fail() -> None:
    taken = [1.0] * 12
    assert not is_even(loads_of(taken, [0] * 12, 3), taken)
    assert is_even(loads_of(taken, [index % 3 for index in range(12)], 3), taken)


def test_the_assignment_of_the_real_weights_is_a_partition_of_the_tests_they_name() -> None:
    for profile in ("dev", "ci"):
        weights = partition.weights_for(profile)
        nodeids = sorted(weights)
        for count in (2, 4):
            assert exactly_once(parts_by_name(nodeids, count, weights), nodeids) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1/1", (1, 1)), ("2/4", (2, 4)), ("4/4", (4, 4)), ("10/12", (10, 12))],
)
def test_a_part_is_read_as_i_of_n(text: str, expected: tuple[int, int]) -> None:
    assert partition.parse_part(text) == expected


@pytest.mark.parametrize(
    "text", ["0/2", "3/2", "1/0", "1", "1/2/3", "a/b", "-1/2", "1/-2", " 1/2", "01/2", "1.5/2", ""]
)
def test_a_part_that_is_not_i_of_n_with_i_up_to_n_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="is not I/N"):
        partition.parse_part(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("agreement", ("agreement", None)),
        ("step8_mutants", ("step8_mutants", None)),
        ("agreement_1of2", ("agreement", (1, 2))),
        ("relations_2of2", ("relations", (2, 2))),
        ("step8_mutants_3of4", ("step8_mutants", (3, 4))),
        # Not a part: beyond the count, a single part, or no count.
        ("agreement_3of2", ("agreement_3of2", None)),
        ("agreement_1of1", ("agreement_1of1", None)),
        ("agreement_0of2", ("agreement_0of2", None)),
        ("agreement_of2", ("agreement_of2", None)),
    ],
)
def test_a_shard_is_a_name_or_a_part_of_one(text: str, expected: tuple[str, tuple[int, int] | None]) -> None:
    assert partition.split_shard(text) == expected


def collected(*options: str) -> subprocess.CompletedProcess[str]:
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *options,
            "tests/unit/test_partition.py",
        ],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_pytest_runs_the_parts_of_a_file_and_they_hold_its_tests_once() -> None:
    tests = {line for line in collected().stdout.splitlines() if "::" in line}
    parts = [
        {line for line in collected("--partition", f"{index}/3").stdout.splitlines() if "::" in line}
        for index in (1, 2, 3)
    ]
    assert tests
    assert all(parts)
    assert exactly_once(parts, tests) == []


@pytest.mark.parametrize(
    ("options", "complaint"),
    [
        (("--partition", "0/2"), "is not I/N"),
        (("--partition", "3/2"), "is not I/N"),
        (("--partition", "two"), "is not I/N"),
        (("--shard", "agreement_3of2"), "invalid choice"),
        (("--shard", "agreement_1of1"), "invalid choice"),
        (("--shard", "nothing_1of2"), "invalid choice"),
        (("--shard", "agreement_1of2", "--partition", "1/2"), "which is a part already"),
    ],
)
def test_pytest_refuses_what_is_not_a_part(options: tuple[str, ...], complaint: str) -> None:
    run = collected(*options)
    assert run.returncode != 0
    assert complaint in run.stdout + run.stderr


def write_report(path: Path, cases: Sequence[tuple[str, str, float, bool]]) -> Path:
    body = "".join(
        f'<testcase classname="{classname}" name="{name}" time="{taken}">'
        f"{'<skipped/>' if skipped else ''}</testcase>"
        for classname, name, taken, skipped in cases
    )
    path.write_text(f'<testsuites><testsuite name="pytest">{body}</testsuite></testsuites>', encoding="utf-8")
    return path


def test_the_recorder_lists_the_tests_that_ran_from_a_second_by_the_longest_time(tmp_path: Path) -> None:
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_a.py").write_text("", encoding="utf-8")
    first = write_report(
        tmp_path / "first.xml",
        [
            ("tests.unit.test_a", "test_slow[x]", 12.34, False),
            ("tests.unit.test_a", "test_quick", 0.4, False),
            ("tests.unit.test_a", "test_skipped", 99.0, True),
            ("tests.unit.test_a.TestInAClass", "test_method", 3.0, False),
        ],
    )
    second = write_report(tmp_path / "second.xml", [("tests.unit.test_a", "test_slow[x]", 20.0, False)])
    assert partition.seconds_in([first, second], tmp_path) == {
        "tests/unit/test_a.py::TestInAClass::test_method": 3.0,
        "tests/unit/test_a.py::test_slow[x]": 20.0,
    }


def test_the_recorder_refuses_a_test_of_no_file(tmp_path: Path) -> None:
    report = write_report(tmp_path / "report.xml", [("tests.unit.test_gone", "test_it", 5.0, False)])
    with pytest.raises(ValueError, match="no test file of this repository"):
        partition.seconds_in([report], tmp_path)


def test_the_recorder_writes_one_table_and_says_where_it_is_from(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("", encoding="utf-8")
    report = write_report(tmp_path / "report.xml", [("tests.test_a", "test_it", 5.0, False)])
    file = tmp_path / "weights.json"
    file.write_text(json.dumps({"ci": {"old": 1.0}, "sources": {"ci": "before"}}), encoding="utf-8")
    partition.recorded("dev", "a CI run", [report], file, tmp_path)
    assert json.loads(file.read_text(encoding="utf-8")) == {
        "ci": {"old": 1.0},
        "dev": {"tests/test_a.py::test_it": 5.0},
        "sources": {"ci": "before", "dev": "a CI run"},
    }
    assert partition.weights_for("deep", file) == {"old": 1.0}


def test_reports_of_one_job_keep_the_weights_of_the_files_they_do_not_hold(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    for name in ("test_a.py", "test_b.py"):
        (tmp_path / "tests" / name).write_text("", encoding="utf-8")
    report = write_report(
        tmp_path / "report.xml",
        [("tests.test_a", "test_it", 7.0, False), ("tests.test_a", "test_skipped", 99.0, True)],
    )
    file = tmp_path / "weights.json"
    before = {
        "tests/test_a.py::test_it": 1.0,
        "tests/test_a.py::test_gone": 50.0,
        "tests/test_b.py::test_other_job": 30.0,
    }
    file.write_text(json.dumps({"dev": before, "sources": {"dev": "before"}}), encoding="utf-8")
    partition.recorded("dev", "a job's reports", [report], file, tmp_path)
    found = json.loads(file.read_text(encoding="utf-8"))
    assert found["dev"] == {"tests/test_a.py::test_it": 7.0, "tests/test_b.py::test_other_job": 30.0}
    assert found["sources"]["dev"] == "before; a job's reports"


def test_the_weights_file_holds_a_table_for_each_profile_and_where_it_is_from() -> None:
    found = json.loads(partition.WEIGHTS_FILE.read_text(encoding="utf-8"))
    assert sorted(found) == ["ci", "dev", "sources"]
    assert sorted(found["sources"]) == ["ci", "dev"]
    for table in ("dev", "ci"):
        assert found[table], f"the {table} table is empty"
        assert all(
            isinstance(taken, float) and taken >= partition.LISTED_FROM_SECONDS
            for taken in found[table].values()
        )

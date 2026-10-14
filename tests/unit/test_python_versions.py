# SPDX-License-Identifier: Apache-2.0
"""The Python versions `pyproject.toml` claims (its classifiers and the floor of `requires-python`) are the
ones the `tests` job of `ci.yml` runs."""

import re
import tomllib
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
CLASSIFIER = re.compile(r"Programming Language :: Python :: (3\.\d+)")
MATRIX = re.compile(r"^\s+python:\s*\[(.*)\]\s*$")
FLOOR = re.compile(r">=\s*(\d+\.\d+)")


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def matrix_versions(workflow: str) -> list[str]:
    """The Python versions in the `python: [...]` line of the `tests` job."""
    in_tests_job = False
    for line in workflow.splitlines():
        if re.match(r"^  [\w-]+:", line):
            in_tests_job = line.rstrip() == "  tests:"
        elif in_tests_job and (found := MATRIX.match(line)):
            return sorted(re.findall(r'"([^"]+)"', found[1]), key=version_key)
    raise ValueError("no `python: [...]` matrix in the `tests` job")


def disagreements(classifiers: list[str], requires_python: str, matrix: list[str]) -> list[str]:
    claimed = sorted((m[1] for c in classifiers if (m := CLASSIFIER.fullmatch(c))), key=version_key)
    floor = FLOOR.search(requires_python)
    found: list[str] = []
    if claimed != matrix:
        found.append(f"classifiers name Python {claimed}, but the tests job runs {matrix}")
    if floor is None or floor[1] != matrix[0]:
        found.append(f"requires-python is {requires_python!r}, but the lowest version tested is {matrix[0]}")
    return found


def test_classifiers_and_floor_are_the_versions_ci_tests() -> None:
    project = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    workflow = (REPOSITORY / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert disagreements(project["classifiers"], project["requires-python"], matrix_versions(workflow)) == []


MATRIX_311_TO_315 = ["3.11", "3.12", "3.13", "3.14", "3.15"]
CLASSIFIERS = ["Programming Language :: Python :: 3"] + [
    f"Programming Language :: Python :: {version}" for version in MATRIX_311_TO_315
]


def test_agreeing_versions_are_not_reported() -> None:
    assert disagreements(CLASSIFIERS, ">=3.11", MATRIX_311_TO_315) == []


@pytest.mark.parametrize(
    ("classifiers", "requires_python", "matrix", "message"),
    [
        (CLASSIFIERS[:-1], ">=3.11", MATRIX_311_TO_315, "classifiers name"),
        (CLASSIFIERS, ">=3.11", [*MATRIX_311_TO_315, "3.16"], "classifiers name"),
        (
            [*CLASSIFIERS, "Programming Language :: Python :: 3.10"],
            ">=3.11",
            MATRIX_311_TO_315,
            "classifiers name",
        ),
        (CLASSIFIERS, ">=3.10", MATRIX_311_TO_315, "lowest version tested is 3.11"),
        (CLASSIFIERS, ">=3.12", MATRIX_311_TO_315, "lowest version tested is 3.11"),
        (CLASSIFIERS, "~=3.11", MATRIX_311_TO_315, "lowest version tested is 3.11"),
    ],
    ids=[
        "classifier-missing",
        "version-untagged",
        "version-untested",
        "floor-below",
        "floor-above",
        "no-floor",
    ],
)
def test_a_mismatch_is_reported(
    classifiers: list[str], requires_python: str, matrix: list[str], message: str
) -> None:
    found = disagreements(classifiers, requires_python, matrix)
    assert len(found) == 1
    assert message in found[0]


def test_versions_sort_numerically_not_as_text() -> None:
    workflow = '  tests:\n    strategy:\n      matrix:\n        python: ["3.9", "3.10", "3.11"]\n'
    assert matrix_versions(workflow) == ["3.9", "3.10", "3.11"]


def test_only_the_tests_job_matrix_counts() -> None:
    workflow = '  fuzz:\n    python: ["3.14"]\n  tests:\n    matrix:\n      python: ["3.11"]\n'
    assert matrix_versions(workflow) == ["3.11"]
    with pytest.raises(ValueError, match="no `python"):
        matrix_versions('  fuzz:\n    python: ["3.14"]\n')

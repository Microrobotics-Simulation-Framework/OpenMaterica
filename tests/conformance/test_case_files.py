# SPDX-License-Identifier: Apache-2.0
"""The case files themselves: each reads the same through `jsonio.parse`, which the runner uses, as through
the reference reader, which shares no code with it, so that the runner does not rest on the reader it tests;
and each is valid against `schema/0.1/case.json`."""

from pathlib import Path

import pytest

from materica.core import jsonio
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from tests.conformance import reference_reader
from tests.conformance.reference_reader import Refused, reference
from tests.conformance.runner import CONFORMANCE, JsonObject
from tests.property.support import same
from tests.spec_sync.schemas import validator

CASE_FILES = sorted(CONFORMANCE.glob("*/cases/*.json"))
INPUTS = sorted(CONFORMANCE.glob("*/inputs/*"))
CASE = validator("case.json")


@pytest.mark.parametrize("path", CASE_FILES, ids=lambda path: path.name)
def test_a_case_file_reads_as_the_reference_reads_it(path: Path) -> None:
    value, expected = jsonio.parse(path.read_bytes()), reference(path.read_bytes())
    assert not isinstance(expected, Refused), expected.fault
    assert not isinstance(value, Reason), value.detail
    assert same(expected, value)


@pytest.mark.parametrize("path", INPUTS, ids=lambda path: f"{path.parent.parent.name}/{path.name}")
def test_an_input_reads_or_is_refused_as_the_reference_has_it(path: Path) -> None:
    value, expected = jsonio.parse(path.read_bytes()), reference(path.read_bytes())
    if isinstance(expected, Refused):
        assert value == Reason("malformed"), expected.fault
    else:
        assert not isinstance(value, Reason), value.detail
        assert same(expected, value)


@pytest.mark.parametrize("path", CASE_FILES, ids=lambda path: path.name)
def test_a_case_file_is_valid_against_the_case_schema(path: Path) -> None:
    value = jsonio.parse(path.read_bytes())
    assert not isinstance(value, Reason), value.detail
    assert CASE(value) == []


TABLE: JsonObject = {
    "axis": "temperature",
    "axis_unit": "K",
    "x": [280.0, 300.0],
    "y": [1000.0, 996.0],
    "scheme": "linear",
    "edges": [],
}
INSIDE: JsonObject = {"in_range": True, "value": 1000.0, "derivative": -0.2}
OUTSIDE: JsonObject = {"in_range": False, "value": 996.0, "derivative": 0.0}
TOLERANCES: JsonObject = {"binary64": 1e-12, "binary32": 3e-7}


def table_evaluation(
    *,
    inputs: JsonValue = None,
    operation: JsonValue = "evaluate",
    at: JsonValue = None,
    expected: JsonValue = None,
    entries: JsonValue = None,
    tolerance: JsonValue = None,
) -> JsonObject:
    """A table evaluation case (README "Case files"), with one member replaced."""
    return {
        "case": "TE-002",
        "variant": "arm",
        "suite": "table_evaluation",
        "schema_version": "0.1.0",
        "inputs": {} if inputs is None else inputs,
        "request": {
            "operation": operation,
            "form": "table",
            "table": TABLE,
            "at": [280.0, 300.0, 310.0] if at is None else at,
        },
        "expected": {"evaluations": [INSIDE, {"refused": True}, OUTSIDE] if entries is None else entries}
        if expected is None
        else expected,
        "compare": {
            "members": ["evaluations"],
            "relative_tolerance": TOLERANCES if tolerance is None else tolerance,
        },
    }


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(table_evaluation(tolerance=3e-7), id="one_tolerance"),
        pytest.param(
            table_evaluation(tolerance={"binary64": 1e-9, "binary32": 3e-7}), id="binary64_not_1e-12"
        ),
        pytest.param(table_evaluation(inputs={"records": ["water_fixture.json"]}), id="inputs"),
        pytest.param(table_evaluation(expected={"status": "met", "reasons": []}), id="read_result"),
        pytest.param(
            table_evaluation(entries=[INSIDE, {"refused": True, "value": 1000.0}, OUTSIDE]),
            id="refused_number",
        ),
        pytest.param(
            table_evaluation(entries=[INSIDE, {"refused": True}, {**OUTSIDE, "derivative": -0.2}]),
            id="outside_slope",
        ),
        pytest.param(table_evaluation(entries=[{**INSIDE, "derivative": {"left": -0.2}}]), id="one_side"),
        pytest.param(table_evaluation(operation="content_hash"), id="operation"),
        pytest.param(table_evaluation(at=[]), id="no_point"),
    ],
)
def test_the_case_schema_holds_a_table_evaluation_case_to_its_shape(broken: JsonObject) -> None:
    assert CASE(table_evaluation()) == []
    assert CASE(broken) != []


def test_only_a_table_evaluation_case_has_a_tolerance_per_precision() -> None:
    read = jsonio.parse(
        (CONFORMANCE / "plain_read" / "cases" / "PR-015.constant_with_conditions.json").read_bytes()
    )
    assert isinstance(read, dict)
    assert isinstance(read["compare"], dict)
    assert CASE(read) == []
    read["compare"]["relative_tolerance"] = {"binary64": 1e-12, "binary32": 3e-7}
    read["compare"].pop("exact", None)
    assert CASE(read) != []


def _nested(depth: int) -> JsonValue:
    value: JsonValue = []
    for _ in range(depth - 1):
        value = [value]
    return value


@pytest.mark.parametrize(("depth", "deeper"), [(64, False), (65, True), (100_000, True)])
def test_the_reference_measures_depth_without_recursion(depth: int, deeper: bool) -> None:
    deeper_than = reference_reader._deeper_than  # pyright: ignore[reportPrivateUsage]  # the check under test
    assert deeper_than(_nested(depth), 64) is deeper

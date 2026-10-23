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


WATER: JsonObject = {
    "id": "conformance/water_fixture",
    "version": "1.0.0",
    "content_hash": "sha256:c21a2c7f46e66bcfb5e74f18d2a08644468d5a92bafb4fa57a03651facf96e2d",
}
RESULT: JsonObject = {
    "model": "drag",
    "record": WATER,
    "field": "fluid.dynamic_viscosity",
    "status": "unknown",
    "reasons": [{"code": "condition_unstated", "condition": "shear_rate"}],
    "accepted": True,
    "accepted_by": [0.0],
    "not_accepted": [],
}
WATCH: JsonObject = {
    "model": "drag",
    "record": WATER,
    "field": "fluid.dynamic_viscosity",
    "condition": "temperature",
    "unit": "K",
    "source": "tolerance",
    "interval": [309.15, 311.15],
}


COMPARING_RESULTS: JsonObject = {"members": ["results"], "result_members": ["accepted"]}


def build_check(
    *,
    inputs: JsonValue = None,
    request: JsonValue = None,
    expected: JsonValue = None,
    compare: JsonValue = None,
) -> JsonObject:
    """A build-check case (README "Case files"), with one member replaced."""
    return {
        "case": "BC-048",
        "variant": "arm",
        "suite": "build_checks",
        "schema_version": "0.1.0",
        "inputs": {"records": ["water_fixture.json"], "declaration": "declaration.json"}
        if inputs is None
        else inputs,
        "request": {"operation": "check_build"} if request is None else request,
        "expected": {"refusals": [{"item": "BC-048", "pointer": ""}]} if expected is None else expected,
        "compare": {"members": ["refusals", "results", "watches", "unused"]} if compare is None else compare,
    }


@pytest.mark.parametrize(
    "taken",
    [
        pytest.param(build_check(), id="refused"),
        pytest.param(
            build_check(compare={"members": ["refusals", "results"], "rules_compared": ["BC-051"]}),
            id="rules_compared",
        ),
        pytest.param(
            build_check(
                expected={
                    "refusals": [],
                    "results": [RESULT],
                    "watches": [WATCH],
                    "unused": [{"model": "drag", "acceptance": 1.0}],
                },
                compare={
                    "members": ["refusals", "results", "watches", "unused"],
                    "result_members": ["status", "reasons", "accepted", "accepted_by", "not_accepted"],
                    "exact": True,
                },
            ),
            id="results_watches_unused",
        ),
        pytest.param(
            build_check(
                expected={
                    "results": [
                        {
                            **{k: v for k, v in RESULT.items() if k != "field"},
                            "fields": ["bulk.density", "fluid.dynamic_viscosity"],
                        }
                    ]
                },
                compare={"members": ["results"], "result_members": ["accepted"]},
            ),
            id="combination",
        ),
    ],
)
def test_the_case_schema_takes_a_build_check_case(taken: JsonObject) -> None:
    assert CASE(taken) == []


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(build_check(inputs={"records": ["water_fixture.json"]}), id="no_declaration"),
        pytest.param(build_check(request={"operation": "content_hash"}), id="another_operation"),
        pytest.param(build_check(request={"operation": "check_build", "model": "drag"}), id="request_member"),
        pytest.param(
            build_check(
                request={
                    "target": {"record": WATER, "field": "fluid.dynamic_viscosity"},
                    "requirement": {"want": "value"},
                }
            ),
            id="read_request",
        ),
        pytest.param(build_check(expected={"status": "met", "reasons": []}), id="read_result"),
        pytest.param(build_check(compare={"members": ["refusals", "value"]}), id="read_member_compared"),
        pytest.param(build_check(expected={"refusals": [{"item": "BC-048"}]}), id="refusal_without_pointer"),
        pytest.param(
            build_check(expected={"refusals": [{"item": "BC-048", "pointer": "", "case": "BC-048"}]}),
            id="refusal_member",
        ),
        pytest.param(
            build_check(expected={"refusals": [{"item": "bc-048", "pointer": ""}]}), id="refusal_item"
        ),
        pytest.param(
            build_check(expected={"results": [{**RESULT, "x_note": 1.0}]}, compare=COMPARING_RESULTS),
            id="result_member",
        ),
        pytest.param(
            build_check(
                expected={"results": [{**RESULT, "fields": ["bulk.density", "fluid.dynamic_viscosity"]}]},
                compare=COMPARING_RESULTS,
            ),
            id="field_and_fields",
        ),
        pytest.param(
            build_check(
                expected={"refusals": [], "results": [RESULT]}, compare={"members": ["refusals", "results"]}
            ),
            id="results_without_result_members",
        ),
        pytest.param(
            build_check(
                expected={"results": [RESULT]}, compare={"members": ["results"], "result_members": ["x"]}
            ),
            id="result_members_unknown",
        ),
        pytest.param(
            build_check(expected={"watches": [{**WATCH, "accept": ["bulk"]}]}), id="interval_and_accept"
        ),
        pytest.param(build_check(expected={"watches": [{**WATCH, "source": "stated"}]}), id="watch_source"),
        pytest.param(build_check(expected={"unused": [{"model": "drag"}]}), id="unused_index"),
    ],
)
def test_the_case_schema_holds_a_build_check_case_to_its_shape(broken: JsonObject) -> None:
    assert CASE(build_check()) == []
    assert CASE(broken) != []


@pytest.mark.parametrize(
    ("place", "member", "value"),
    [("inputs", "declaration", "declaration.json"), ("compare", "result_members", ["accepted"])],
)
def test_a_read_case_names_no_declaration_and_no_results_members(
    place: str, member: str, value: JsonValue
) -> None:
    read = jsonio.parse(
        (CONFORMANCE / "plain_read" / "cases" / "PR-015.constant_with_conditions.json").read_bytes()
    )
    assert isinstance(read, dict)
    held = read[place]
    assert isinstance(held, dict)
    assert CASE(read) == []
    held[member] = value
    assert CASE(read) != []


def test_only_a_build_check_case_asks_for_check_build() -> None:
    read = jsonio.parse(
        (CONFORMANCE / "plain_read" / "cases" / "PR-015.constant_with_conditions.json").read_bytes()
    )
    assert isinstance(read, dict)
    assert CASE(read) == []
    read["request"] = {"operation": "check_build"}
    assert CASE(read) != []
    assert CASE(build_check()) == []


def engine_adapter(suite: str) -> JsonObject:
    """A case naming a declaration among its inputs, as an engine-adapter case does (README "Case files"); the
    adapter's stage, crosswalks and expected attributes come with that suite's cases, so it compares none."""
    return {
        "case": "EA-001",
        "variant": "arm",
        "suite": suite,
        "schema_version": "0.1.0",
        "inputs": {"records": ["water_fixture.json"], "declaration": "declaration.json"},
        "request": {"model": "drag"},
        "expected": {},
        "compare": {"members": []},
    }


def test_an_engine_adapter_case_names_a_declaration_and_asks_for_no_build() -> None:
    assert CASE(engine_adapter("engine_adapter")) == []
    assert CASE(engine_adapter("plain_read")) != []
    asks_for_the_build = engine_adapter("engine_adapter")
    asks_for_the_build["request"] = {"operation": "check_build"}
    assert CASE(asks_for_the_build) != []
    compares_results = engine_adapter("engine_adapter")
    compares_results["compare"] = {"members": [], "result_members": ["accepted"]}
    assert CASE(compares_results) != []


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


@pytest.mark.parametrize("member", ["status", "reasons"])
def test_a_read_case_holds_its_status_and_reasons_where_it_compares_them(member: str) -> None:
    """`expected` holds the members `compare` names (README, "Case files"). A case leaves `status` or
    `reasons` out of both where the text leaves it open (an alternative's own reasons beside `no_pick`), never
    out of `expected` alone."""
    read = jsonio.parse(
        (CONFORMANCE / "plain_read" / "cases" / "PR-015.constant_with_conditions.json").read_bytes()
    )
    assert isinstance(read, dict)
    expected, compare = read["expected"], read["compare"]
    assert isinstance(expected, dict)
    assert isinstance(compare, dict)
    members = compare["members"]
    assert isinstance(members, list)
    assert member in members
    del expected[member]
    assert CASE(read) != []
    compare["members"] = [name for name in members if name != member]
    assert CASE(read) == []


def _nested(depth: int) -> JsonValue:
    value: JsonValue = []
    for _ in range(depth - 1):
        value = [value]
    return value


@pytest.mark.parametrize(("depth", "deeper"), [(64, False), (65, True), (100_000, True)])
def test_the_reference_measures_depth_without_recursion(depth: int, deeper: bool) -> None:
    deeper_than = reference_reader._deeper_than  # pyright: ignore[reportPrivateUsage]  # the check under test
    assert deeper_than(_nested(depth), 64) is deeper

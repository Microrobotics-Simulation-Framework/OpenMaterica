# SPDX-License-Identifier: Apache-2.0
"""The comparator and the fold of variants fail where `docs/specification/README.md`, "Case files", says."""

from pathlib import Path

import pytest

from materica.core.jsonio import JsonValue
from materica.shapes import Suite
from tests.conformance import runner
from tests.conformance.runner import CaseFile, CaseFileError, JsonObject, Outcome

MALFORMED: JsonObject = {"code": "malformed"}
UNSTATED: JsonObject = {"code": "condition_unstated", "condition": "shear_rate"}


def case(
    expected: JsonObject,
    members: tuple[str, ...] = ("status", "reasons", "value"),
    *,
    operation: str = "content_hash",
    claims: JsonObject | None = None,
    **compare: JsonValue,
) -> CaseFile:
    document: JsonObject = {
        "case": "XX-001",
        "variant": "arm",
        "suite": "hash",
        "schema_version": "0.1.0",
        "inputs": {},
        "request": {"operation": operation},
        "expected": expected,
        "compare": {"members": list(members), **compare},
    }
    if claims is not None:
        document["claims"] = claims
    return CaseFile.from_document(Path("XX-001.arm.json"), document)


def differences(case_file: CaseFile, result: JsonObject) -> list[str]:
    return runner.compare(case_file, result)


def test_the_expected_answer_passes() -> None:
    expected: JsonObject = {"status": "unknown", "reasons": [UNSTATED, MALFORMED], "value": "sha256:0"}
    result: JsonObject = {"status": "unknown", "reasons": [MALFORMED, UNSTATED], "value": "sha256:0"}
    assert differences(case(expected), result) == []


def test_detail_is_never_compared() -> None:
    expected: JsonObject = {"status": "not_met", "reasons": [MALFORMED]}
    result: JsonObject = {"status": "not_met", "reasons": [{"code": "malformed", "detail": "anything"}]}
    assert differences(case(expected), result) == []


@pytest.mark.parametrize(
    "reasons",
    [
        pytest.param([MALFORMED, UNSTATED], id="extra"),
        pytest.param([], id="missing"),
        pytest.param([MALFORMED, MALFORMED], id="duplicated"),
        pytest.param([{"code": "malformed", "condition": "temperature"}], id="condition_added"),
        pytest.param([{"code": "absent"}], id="other_code"),
    ],
)
def test_reasons_are_a_multiset_of_code_and_condition(reasons: list[JsonValue]) -> None:
    expected: JsonObject = {"status": "not_met", "reasons": [MALFORMED]}
    assert differences(case(expected), {"status": "not_met", "reasons": reasons})


def test_a_wrong_condition_fails() -> None:
    expected: JsonObject = {"status": "unknown", "reasons": [UNSTATED]}
    result: JsonObject = {
        "status": "unknown",
        "reasons": [{"code": "condition_unstated", "condition": "frequency"}],
    }
    assert differences(case(expected), result)


OUTSIDE: JsonObject = {"code": "condition_outside", "condition": "temperature"}


def outside(index: JsonValue) -> JsonObject:
    return {**OUTSIDE, "alternative": index}


@pytest.mark.parametrize(
    "reasons",
    [
        pytest.param([OUTSIDE], id="dropped"),
        pytest.param([outside(1.0)], id="another_index"),
        pytest.param([outside(-0.0)], id="minus_zero_under_exact"),
        pytest.param([outside(False)], id="a_bool"),
        pytest.param([outside("0")], id="a_string"),
        pytest.param([outside(None)], id="null"),
        pytest.param([outside(0.0), OUTSIDE], id="one_more_without"),
    ],
)
def test_a_reason_s_alternative_is_compared(reasons: list[JsonValue]) -> None:
    expected: JsonObject = {"status": "not_met", "reasons": [outside(0.0)]}
    assert differences(case(expected, exact=True), {"status": "not_met", "reasons": [outside(0.0)]}) == []
    assert differences(case(expected, exact=True), {"status": "not_met", "reasons": reasons})


def test_two_reasons_that_differ_only_by_alternative_are_two() -> None:
    expected: JsonObject = {"status": "not_met", "reasons": [outside(0.0), outside(1.0)]}
    swapped: JsonObject = {"status": "not_met", "reasons": [outside(1.0), outside(0.0)]}
    assert differences(case(expected, exact=True), swapped) == []
    assert differences(
        case(expected, exact=True), {"status": "not_met", "reasons": [outside(0.0), outside(0.0)]}
    )


def test_an_alternative_is_never_compared_at_a_tolerance_and_needs_one() -> None:
    expected: JsonObject = {"status": "not_met", "reasons": [outside(0.0)]}
    tolerant = case(expected, relative_tolerance=0.5)
    assert differences(tolerant, {"status": "not_met", "reasons": [outside(-0.0)]}) == []
    assert differences(tolerant, {"status": "not_met", "reasons": [outside(0.25)]})
    with pytest.raises(CaseFileError):
        differences(case(expected), {"status": "not_met", "reasons": [outside(0.0)]})


def without_alternatives(reasons: JsonValue) -> list[JsonValue]:
    assert isinstance(reasons, list)
    return [
        {name: value for name, value in reason.items() if name != "alternative"}
        if isinstance(reason, dict)
        else reason
        for reason in reasons
    ]


def test_every_case_file_whose_reasons_hold_an_alternative_fails_without_it() -> None:
    """A control through the real case files: a reader that drops a reason's `alternative`, on the one
    alternative left or picked or anywhere, fails each file that expects one. Until S4's code can run them,
    the expected answer with its indexes dropped stands for that reader's result."""
    holding = [
        case_file
        for case_file in runner.discover()
        if without_alternatives(case_file.expected.get("reasons", []))
        != case_file.expected.get("reasons", [])
    ]
    assert [case_file for case_file in holding if "value" in case_file.expected]
    for case_file in holding:
        dropped: JsonObject = {
            **case_file.expected,
            "reasons": without_alternatives(case_file.expected["reasons"]),
        }
        assert differences(case_file, dict(case_file.expected)) == [], case_file.path.name
        assert differences(case_file, dropped), case_file.path.name


def test_a_member_compared_but_not_expected_must_be_absent() -> None:
    expected: JsonObject = {"status": "not_met", "reasons": [MALFORMED]}
    assert differences(case(expected), {"status": "not_met", "reasons": [MALFORMED], "value": "sha256:0"})
    assert (
        differences(
            case(expected, ("status", "reasons")), {"status": "not_met", "reasons": [MALFORMED], "value": 1.0}
        )
        == []
    )


def test_an_expected_member_missing_from_the_result_fails() -> None:
    expected: JsonObject = {"status": "met", "reasons": [], "value": "sha256:0"}
    assert differences(case(expected), {"status": "met", "reasons": []})


def test_status_is_compared() -> None:
    expected: JsonObject = {"status": "met", "reasons": []}
    assert differences(case(expected), {"status": "unknown", "reasons": []})


LABELLED = ("status", "reasons", "value", "labels")


def test_labels_are_a_set_and_absent_is_empty() -> None:
    expected: JsonObject = {
        "status": "met",
        "reasons": [],
        "labels": ["user_extracted", "no_independent_witness"],
    }
    result: JsonObject = {
        "status": "met",
        "reasons": [],
        "labels": ["no_independent_witness", "user_extracted"],
    }
    assert differences(case(expected, LABELLED), result) == []
    assert (
        differences(case({"status": "met", "reasons": []}, LABELLED), {"status": "met", "reasons": []}) == []
    )
    assert differences(case(expected, LABELLED), {"status": "met", "reasons": []})


def test_hash_not_checked_is_compared_only_under_a_hash_claim() -> None:
    expected: JsonObject = {"status": "not_met", "reasons": [MALFORMED], "labels": []}
    result: JsonObject = {"status": "not_met", "reasons": [MALFORMED], "labels": ["hash_not_checked"]}
    assert differences(case(expected, LABELLED), result) == []
    assert differences(case(expected, LABELLED, claims={"hash": False}), result)
    assert differences(case(expected, LABELLED, claims={"hash": True}), result)


def test_numbers_need_a_tolerance_or_exact() -> None:
    expected: JsonObject = {"status": "met", "reasons": [], "value": 0.000692}
    with pytest.raises(CaseFileError):
        differences(case(expected), {"status": "met", "reasons": [], "value": 0.000692})


def test_relative_tolerance() -> None:
    expected: JsonObject = {"status": "met", "reasons": [], "value": [1000.0, 0.0]}
    tolerant = case(expected, relative_tolerance=1e-6)
    assert differences(tolerant, {"status": "met", "reasons": [], "value": [1000.0009, 9e-7]}) == []
    assert differences(tolerant, {"status": "met", "reasons": [], "value": [1000.0011, 0.0]})
    assert differences(tolerant, {"status": "met", "reasons": [], "value": [1000.0, 1.1e-6]})


def test_a_table_evaluation_tolerance_is_one_per_precision() -> None:
    expected: JsonObject = {"evaluations": [{"refused": True}]}
    tolerances: JsonObject = {"binary64": 1e-12, "binary32": 3e-7}
    read = case(expected, ("evaluations",), operation="evaluate", relative_tolerance=tolerances)
    assert read.precision_tolerances == {"binary64": 1e-12, "binary32": 3e-7}
    assert read.relative_tolerance is None
    broken_tolerances: list[JsonValue] = [
        {"binary64": 1e-12},
        {"binary64": 1e-12, "binary32": -1.0},
        {**tolerances, "bfloat16": 1e-2},
    ]
    for broken in broken_tolerances:
        with pytest.raises(CaseFileError):
            case(expected, ("evaluations",), operation="evaluate", relative_tolerance=broken)
    with pytest.raises(CaseFileError):
        case(expected, ("evaluations",), operation="evaluate", relative_tolerance=tolerances, exact=True)


def test_exact_compares_bits() -> None:
    expected: JsonObject = {"status": "met", "reasons": [], "value": -0.0}
    assert differences(case(expected, exact=True), {"status": "met", "reasons": [], "value": -0.0}) == []
    assert differences(case(expected, exact=True), {"status": "met", "reasons": [], "value": 0.0})


def test_a_bool_never_equals_a_number() -> None:
    expected: JsonObject = {"status": "met", "reasons": [], "value": [1.0]}
    assert differences(case(expected, exact=True), {"status": "met", "reasons": [], "value": [True]})


def test_a_listing_is_a_set() -> None:
    water: JsonObject = {"id": "conformance/water_fixture", "version": "1.0.0"}
    glycerol: JsonObject = {"id": "conformance/glycerol_fixture", "version": "1.0.0"}
    listing = case({"status": "met", "reasons": [], "value": [water, glycerol]}, operation="list_records")
    assert differences(listing, {"status": "met", "reasons": [], "value": [glycerol, water]}) == []
    assert differences(listing, {"status": "met", "reasons": [], "value": [water]})
    assert differences(listing, {"status": "met", "reasons": [], "value": [water, glycerol, {"id": "x"}]})


TEMPERATURE: JsonObject = {
    "name": "temperature",
    "status": "met",
    "record": {"value": 310.15, "unit": "K", "basis": "stated"},
    "operating": {"value": 310.15, "unit": "K"},
}
SHEAR_RATE: JsonObject = {"name": "shear_rate", "status": "unknown", "record": {"status": "unstated"}}
HUMIDITY: JsonObject = {"name": "humidity", "status": "unknown"}
CONDITIONS = ("status", "reasons", "conditions")


def test_conditions_are_a_set_keyed_by_name() -> None:
    expected: JsonObject = {
        "status": "unknown",
        "reasons": [UNSTATED],
        "conditions": [TEMPERATURE, SHEAR_RATE],
    }
    compared = case(expected, CONDITIONS, exact=True)
    by_name: list[JsonValue] = [
        entry for entry in sorted((TEMPERATURE, SHEAR_RATE), key=lambda entry: str(entry["name"]))
    ]
    assert differences(compared, {**expected, "conditions": by_name}) == []
    assert differences(compared, {**expected, "conditions": [SHEAR_RATE, TEMPERATURE]}) == []
    wrong: list[list[JsonValue]] = [
        [TEMPERATURE],
        [TEMPERATURE, SHEAR_RATE, HUMIDITY],
        [TEMPERATURE, SHEAR_RATE, SHEAR_RATE],
        [TEMPERATURE, {**SHEAR_RATE, "status": "met"}],
        [TEMPERATURE, {"status": "unknown", "record": {"status": "unstated"}}],
    ]
    for entries in wrong:
        assert differences(compared, {**expected, "conditions": entries}), entries


def test_a_case_that_expects_a_condition_twice_is_a_defect() -> None:
    expected: JsonObject = {
        "status": "unknown",
        "reasons": [UNSTATED],
        "conditions": [SHEAR_RATE, SHEAR_RATE],
    }
    with pytest.raises(CaseFileError):
        differences(case(expected, CONDITIONS, exact=True), {**expected, "conditions": [SHEAR_RATE]})


def test_an_alternative_entry_compares_its_conditions_and_labels_as_the_results() -> None:
    first: JsonObject = {
        "alternative": 0.0,
        "value": 0.000692,
        "conditions": [TEMPERATURE, SHEAR_RATE],
        "labels": ["materica.fluid.newtonian.v1", "mixed_conditions"],
    }
    second: JsonObject = {"alternative": 1.0, "value": 0.000695, "conditions": [TEMPERATURE], "labels": []}
    expected: JsonObject = {
        "status": "unknown",
        "reasons": [{"code": "no_pick"}],
        "alternative_values": [first, second],
    }
    no_pick = case(expected, ("status", "reasons", "alternative_values"), exact=True)
    permuted: JsonObject = {
        **first,
        "conditions": [SHEAR_RATE, TEMPERATURE],
        "labels": ["mixed_conditions", "hash_not_checked", "materica.fluid.newtonian.v1"],
    }
    unlabelled: JsonObject = {key: value for key, value in second.items() if key != "labels"}
    assert differences(no_pick, {**expected, "alternative_values": [permuted, second]}) == []
    assert differences(no_pick, {**expected, "alternative_values": [first, unlabelled]}) == []
    wrong: list[list[JsonValue]] = [
        [second, first],
        [first],
        [{**first, "conditions": [TEMPERATURE]}, second],
        [{**first, "conditions": [TEMPERATURE, SHEAR_RATE, HUMIDITY]}, second],
        [{**first, "labels": ["materica.fluid.newtonian.v1"]}, second],
        [{**first, "specimen": {}}, second],
        [{key: value for key, value in first.items() if key != "value"}, second],
    ]
    for entries in wrong:
        assert differences(no_pick, {**expected, "alternative_values": entries}), entries
    hashed = case(expected, ("status", "reasons", "alternative_values"), exact=True, claims={"hash": True})
    assert differences(hashed, {**expected, "alternative_values": [permuted, second]})


@pytest.mark.parametrize(
    ("variants", "outcome"),
    [
        pytest.param([Outcome.PASSED, Outcome.PASSED], Outcome.PASSED, id="all_passed"),
        pytest.param([Outcome.PASSED, Outcome.NOT_RUN], Outcome.PASSED, id="one_ran"),
        pytest.param([Outcome.PASSED, Outcome.FAILED], Outcome.FAILED, id="one_failed"),
        pytest.param([Outcome.NOT_RUN, Outcome.NOT_YET_RUNNABLE], Outcome.NOT_RUN, id="none_ran"),
        pytest.param([Outcome.NOT_YET_RUNNABLE], Outcome.NOT_YET_RUNNABLE, id="no_executor"),
        pytest.param([], Outcome.NOT_RUN, id="no_variants"),
    ],
)
def test_a_case_that_did_not_run_never_passes(variants: list[Outcome], outcome: Outcome) -> None:
    assert runner.case_outcome(variants) is outcome


@pytest.mark.parametrize(
    ("claims", "claimed", "outcome"),
    [
        pytest.param({"hash": False}, {"hash"}, Outcome.NOT_RUN, id="claim_absent_but_claimed"),
        pytest.param(
            {"fits_and_reference_data": True}, {"hash"}, Outcome.NOT_RUN, id="claim_present_not_claimed"
        ),
        pytest.param({}, {"plain_read"}, Outcome.NOT_RUN, id="suite_not_claimed"),
        pytest.param({"fits_and_reference_data": False}, {"hash"}, Outcome.PASSED, id="control_claims_agree"),
    ],
)
def test_claims_decide_which_variants_run(claims: JsonObject, claimed: set[Suite], outcome: Outcome) -> None:
    ran: list[CaseFile] = []

    def execute(case_file: CaseFile, claims: frozenset[Suite]) -> JsonObject:
        ran.append(case_file)
        return {"status": "met", "reasons": []}

    case_file = case({"status": "met", "reasons": []}, claims=claims)
    run = runner.run(case_file, configurations=[frozenset(claimed)], executors={"content_hash": execute})
    assert run.outcome is outcome
    assert bool(ran) is (outcome is Outcome.PASSED)


def test_a_case_runs_under_every_configuration_that_agrees_and_fails_if_one_fails() -> None:
    without_fd: frozenset[Suite] = frozenset({"hash"})
    with_fd: frozenset[Suite] = frozenset({"hash", "fits_and_reference_data"})
    with_plain_read: frozenset[Suite] = frozenset({"plain_read", "hash", "fits_and_reference_data"})
    given: list[frozenset[Suite]] = []

    def execute(case_file: CaseFile, claims: frozenset[Suite]) -> JsonObject:
        given.append(claims)
        return {"status": "met" if claims == with_fd else "unknown", "reasons": []}

    case_file = case({"status": "met", "reasons": []}, claims={"fits_and_reference_data": True})
    run = runner.run(
        case_file,
        configurations=[without_fd, with_fd, with_plain_read],
        executors={"content_hash": execute},
    )
    assert given == [with_fd, with_plain_read]
    assert run.claimed == (with_fd, with_plain_read)
    assert run.outcome is Outcome.FAILED
    assert [difference.partition(":")[0] for difference in run.differences] == [
        "claiming fits_and_reference_data, hash, plain_read"
    ]

# SPDX-License-Identifier: Apache-2.0
"""The comparator and the fold of variants fail where `docs/specification/README.md`, "Case files", says."""

from pathlib import Path

import pytest

from materica.core.jsonio import JsonValue
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
def test_claims_decide_which_variants_run(claims: JsonObject, claimed: set[str], outcome: Outcome) -> None:
    ran: list[CaseFile] = []

    def execute(case_file: CaseFile) -> JsonObject:
        ran.append(case_file)
        return {"status": "met", "reasons": []}

    case_file = case({"status": "met", "reasons": []}, claims=claims)
    assert (
        runner.run(case_file, claimed=frozenset(claimed), executors={"content_hash": execute}).outcome
        is outcome
    )
    assert bool(ran) is (outcome is Outcome.PASSED)

# SPDX-License-Identifier: Apache-2.0
"""Broken implementations, one fault each: every one must fail at least one real case, the named one included.

Faults inside a function are injected by replacing that function for the test, so that the rest of the
implementation stays the one under test.
"""

import hashlib
import unicodedata
from collections.abc import Callable

import pytest

from materica.core import canonical, hashing, jsonio
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from tests.conformance import runner
from tests.conformance.runner import CLAIMED, EXECUTORS, Executor, JsonObject, Outcome

RUN = [
    case_file
    for case_file in runner.discover()
    if runner.not_run_because(case_file, claimed=CLAIMED, executors=EXECUTORS) is None
]

Fault = Callable[[pytest.MonkeyPatch], Executor]


def keeps_card(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def digest(value: JsonValue) -> str:
        view = hashing.hashable_view(value)
        if isinstance(value, dict) and isinstance(view, dict) and "card" in value:
            view["card"] = value["card"]
        return "sha256:" + hashlib.sha256(canonical.canonicalize(view)).hexdigest()

    return runner.content_hash_executor(digest=digest)


def removes_review_outside_provenance(monkeypatch: pytest.MonkeyPatch) -> Executor:
    return runner.content_hash_executor(digest=lambda value: hashing.content_hash(_without(value, "review")))


def orders_names_by_code_point(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def code_points(name: str) -> str:
        return name

    monkeypatch.setattr(canonical, "_utf16_units", code_points)
    return runner.content_hash_executor()


def orders_names_by_utf8_bytes(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def utf8_bytes(name: str) -> bytes:
        return name.encode("utf-8")

    monkeypatch.setattr(canonical, "_utf16_units", utf8_bytes)
    return runner.content_hash_executor()


def normalises_strings_to_nfc(monkeypatch: pytest.MonkeyPatch) -> Executor:
    return runner.content_hash_executor(digest=lambda value: hashing.content_hash(_nfc(value)))


def formats_numbers_with_repr(monkeypatch: pytest.MonkeyPatch) -> Executor:
    monkeypatch.setattr(canonical, "_number", repr)
    return runner.content_hash_executor()


def accepts_repeated_names(monkeypatch: pytest.MonkeyPatch) -> Executor:
    monkeypatch.setattr(jsonio, "_object", dict)
    return runner.content_hash_executor()


def counts_scalars_in_depth(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def parse(data: bytes) -> JsonValue | Reason:
        value = jsonio.parse(data)
        if not isinstance(value, Reason) and _depth_counting_scalars(value) > jsonio.MAX_DEPTH:
            return Reason("malformed")
        return value

    return runner.content_hash_executor(parse=parse)


def answers_a_constant(monkeypatch: pytest.MonkeyPatch) -> Executor:
    def execute(case_file: runner.CaseFile) -> JsonObject:
        return {"status": "met", "reasons": [], "value": "sha256:" + "0" * 64}

    return execute


def _without(value: JsonValue, removed: str) -> JsonValue:
    if isinstance(value, list):
        return [_without(item, removed) for item in value]
    if isinstance(value, dict):
        return {name: _without(member, removed) for name, member in value.items() if name != removed}
    return value


def _nfc(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", name): _nfc(member) for name, member in value.items()}
    return value


def _depth_counting_scalars(value: JsonValue) -> int:
    if isinstance(value, list):
        return 1 + max((_depth_counting_scalars(item) for item in value), default=0)
    if isinstance(value, dict):
        return 1 + max((_depth_counting_scalars(member) for member in value.values()), default=0)
    return 1


FAULTS: list[tuple[Fault, str]] = [
    (keeps_card, "HS-001.top_level_removed.json"),
    (removes_review_outside_provenance, "HS-001.outside_kept.json"),
    (orders_names_by_code_point, "HS-003.utf16_order_raw.json"),
    (orders_names_by_utf8_bytes, "HS-003.utf16_order_raw.json"),
    (normalises_strings_to_nfc, "HS-003.nfc_decomposed.json"),
    (formats_numbers_with_repr, "HS-003.number_1_0.json"),
    (accepts_repeated_names, "HS-003.malformed_duplicate_name.json"),
    (counts_scalars_in_depth, "HS-003.depth_64_scalar.json"),
    (answers_a_constant, "HS-003.malformed_bom.json"),
]


def failed_cases(executor: Executor) -> set[str]:
    executors = {"content_hash": executor}
    runs = runner.run_all(RUN, claimed=CLAIMED, executors=executors)
    return {case_run.case_file.path.name for case_run in runs if case_run.outcome is Outcome.FAILED}


@pytest.mark.parametrize(("fault", "catcher"), FAULTS, ids=[fault.__name__ for fault, _ in FAULTS])
def test_a_broken_implementation_fails_a_real_case(
    fault: Fault, catcher: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert catcher in failed_cases(fault(monkeypatch))


def test_the_implementation_itself_fails_none() -> None:
    assert failed_cases(EXECUTORS["content_hash"]) == set()

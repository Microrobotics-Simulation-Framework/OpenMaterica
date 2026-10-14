# SPDX-License-Identifier: Apache-2.0
"""The conformance-case runner, by `docs/specification/README.md`, "Case files" to "Operations".

It finds every case file, runs those whose operation has an executor under every configuration of claims that
agrees with the case's suite and claims, compares each result with the case's expected answer, and folds a
case's variants into the case's outcome. Later steps add executors; the rest stays as it is.
"""

import json
import re
import struct
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from functools import cache
from pathlib import Path
from typing import TypedDict

import materica
from materica.core import hashing, jsonio
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.reasons import Reason
from materica.io.plain import load_records
from materica.shapes import Suite

CONFORMANCE = Path(materica.__file__).parent / "data" / "conformance"
# Each case file's implementation step, and the steps done (`tests/spec_sync/test_case_steps.py`).
CASE_STEPS = Path(__file__).resolve().parent.parent / "spec_sync" / "case_steps.json"

JsonObject = dict[str, JsonValue]


class CaseFileError(Exception):
    """A case file that breaks the rules for case files: a defect in the case, never a pass."""


class Outcome(Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not run: its suite or claims disagree with every configuration of claims"
    NOT_YET_RUNNABLE = "not yet runnable: no executor for its operation, or its step not done"


@dataclass(frozen=True, eq=False)
class CaseFile:
    path: Path
    case: str
    variant: str
    suite: str
    operation: str
    claims: dict[str, bool]
    inputs: JsonObject
    request: JsonValue
    expected: JsonObject
    members: tuple[str, ...]
    relative_tolerance: float | None
    exact: bool

    @classmethod
    def from_document(cls, path: Path, document: JsonValue) -> "CaseFile":
        document = _object(document, "the case file")
        case = _string(document.get("case"), "case")
        variant = _string(document.get("variant"), "variant")
        if not re.fullmatch(r"[a-z0-9_]+", variant) or path.name != f"{case}.{variant}.json":
            raise CaseFileError(f"{path.name}: the file is not named <case>.<variant>.json")
        # A request may itself be broken on purpose (PR-330 gives an array and a string): that is a read too.
        request = document.get("request")
        operation = request.get("operation", "read") if isinstance(request, dict) else "read"
        compare = _object(document.get("compare"), "compare")
        members = tuple(
            _string(member, "compare.members") for member in _list(compare.get("members"), "members")
        )
        expected = _object(document.get("expected"), "expected")
        if not set(expected) <= set(members):
            raise CaseFileError(f"{path.name}: expected holds members compare does not name")
        tolerance = _tolerance(compare.get("relative_tolerance"))
        exact = compare.get("exact", False)
        if not isinstance(exact, bool):
            raise CaseFileError(f"{path.name}: compare's exact is not true or false")
        if tolerance is not None and exact:
            raise CaseFileError(f"{path.name}: compare gives both relative_tolerance and exact")
        claims = _object(document.get("claims", {}), "claims")
        if not all(isinstance(claimed, bool) for claimed in claims.values()):
            raise CaseFileError(f"{path.name}: a claim is not true or false")
        return cls(
            path=path,
            case=case,
            variant=variant,
            suite=_string(document.get("suite"), "suite"),
            operation=_string(operation, "request.operation"),
            claims={suite: claimed is True for suite, claimed in claims.items()},
            inputs=_object(document.get("inputs"), "inputs"),
            request=request,
            expected=expected,
            members=members,
            relative_tolerance=tolerance,
            exact=exact,
        )

    def input_bytes(self, member: str) -> bytes:
        return (self.path.parent.parent / "inputs" / _string(self.inputs.get(member), member)).read_bytes()

    def input_paths(self, member: str) -> list[Path]:
        names = _list(self.inputs.get(member), member)
        return [self.path.parent.parent / "inputs" / _string(name, member) for name in names]


# An executor runs one case file's operation as a reader claiming the given suites.
Executor = Callable[[CaseFile, frozenset[Suite]], JsonObject]


@dataclass(frozen=True)
class CaseRun:
    case_file: CaseFile
    outcome: Outcome
    differences: tuple[str, ...] = ()
    claimed: tuple[frozenset[Suite], ...] = ()  # the configurations it ran under


def discover(root: Path = CONFORMANCE) -> list[CaseFile]:
    case_files: list[CaseFile] = []
    for path in sorted(root.glob("*/cases/*.json")):
        document = jsonio.parse(path.read_bytes())
        if isinstance(document, Reason):
            raise CaseFileError(f"{path.name}: {document.detail}")
        case_file = CaseFile.from_document(path, document)
        if path.parent.parent.name != case_file.suite:
            raise CaseFileError(f"{path.name}: suite {case_file.suite!r} is not its directory's")
        case_files.append(case_file)
    return case_files


def agreeing(case_file: CaseFile, configurations: Iterable[frozenset[Suite]]) -> list[frozenset[Suite]]:
    """The configurations that claim the case's suite and agree with every claim the case states."""
    return [
        claimed
        for claimed in configurations
        if case_file.suite in claimed
        and all((suite in claimed) == claims for suite, claims in case_file.claims.items())
    ]


def steps(case_file: CaseFile, case_steps: Path = CASE_STEPS) -> tuple[str, ...]:
    """The implementation steps whose code the case file needs: one, or several whose order is not fixed.

    A case file the map does not name needs none here, so a missing entry never hides a case; the map's own
    test finds it.
    """
    entry = _case_steps(case_steps)["case_files"].get(case_file.path.name, ())
    return (entry,) if isinstance(entry, str) else tuple(entry)


def step_done(case_file: CaseFile, case_steps: Path = CASE_STEPS) -> bool:
    done = _case_steps(case_steps)["done"]
    return all(step in done for step in steps(case_file, case_steps))


class _CaseSteps(TypedDict):
    done: list[str]
    case_files: dict[str, str | list[str]]


@cache
def _case_steps(path: Path) -> _CaseSteps:
    loaded: _CaseSteps = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def not_run_because(
    case_file: CaseFile, *, configurations: Iterable[frozenset[Suite]], executors: Mapping[str, Executor]
) -> Outcome | None:
    if case_file.operation not in executors or not step_done(case_file):
        return Outcome.NOT_YET_RUNNABLE
    if not agreeing(case_file, configurations):
        return Outcome.NOT_RUN
    return None


def run(
    case_file: CaseFile, *, configurations: Iterable[frozenset[Suite]], executors: Mapping[str, Executor]
) -> CaseRun:
    """The case file run under every configuration that agrees with it; it fails if any run fails."""
    configurations = tuple(configurations)
    not_run = not_run_because(case_file, configurations=configurations, executors=executors)
    if not_run is not None:
        return CaseRun(case_file, not_run)
    claimed = tuple(agreeing(case_file, configurations))
    differences = [
        f"claiming {', '.join(sorted(claims))}: {difference}"
        for claims in claimed
        for difference in _run_once(case_file, claims, executors[case_file.operation])
    ]
    return CaseRun(case_file, Outcome.FAILED if differences else Outcome.PASSED, tuple(differences), claimed)


def _run_once(case_file: CaseFile, claims: frozenset[Suite], executor: Executor) -> list[str]:
    try:
        result = executor(case_file, claims)
    except CaseFileError:
        raise
    except Exception as error:
        # An implementation that raises for a case's content fails it: no read raises (PR-300).
        return [f"raised {type(error).__name__}: {error}"]
    return compare(case_file, result)


def run_all(
    case_files: Iterable[CaseFile],
    *,
    configurations: Iterable[frozenset[Suite]],
    executors: Mapping[str, Executor],
) -> list[CaseRun]:
    configurations = tuple(configurations)
    return [run(case_file, configurations=configurations, executors=executors) for case_file in case_files]


def case_outcome(variants: Iterable[Outcome]) -> Outcome:
    """A case passes when at least one variant ran and none failed; with none run, it is not run."""
    outcomes = set(variants)
    if Outcome.FAILED in outcomes:
        return Outcome.FAILED
    if Outcome.PASSED in outcomes:
        return Outcome.PASSED
    if outcomes == {Outcome.NOT_YET_RUNNABLE}:
        return Outcome.NOT_YET_RUNNABLE
    return Outcome.NOT_RUN


def case_outcomes(runs: Iterable[CaseRun]) -> dict[str, Outcome]:
    variants: dict[str, list[Outcome]] = {}
    for case_run in runs:
        variants.setdefault(case_run.case_file.case, []).append(case_run.outcome)
    return {case: case_outcome(outcomes) for case, outcomes in variants.items()}


def compare(case_file: CaseFile, result: Mapping[str, JsonValue]) -> list[str]:
    """How `result` differs from the case's expected answer; no difference is a pass.

    Raises `CaseFileError` for a case that compares a number with neither `relative_tolerance` nor `exact`.
    """
    differences: list[str] = []
    for member in case_file.members:
        if member == "labels":
            difference = _labels_differ(case_file, case_file.expected.get("labels"), result.get("labels"))
        elif member not in case_file.expected:
            difference = f"must be absent, got {result[member]!r}" if member in result else None
        elif member not in result:
            difference = "missing"
        elif member == "reasons":
            difference = _reasons_differ(case_file.expected[member], result[member])
        elif member == "value" and case_file.operation == "list_records":
            difference = _sets_differ(case_file.expected[member], result[member])
        elif member == "conditions":
            difference = _conditions_differ(case_file, case_file.expected[member], result[member])
        elif member == "alternative_values":
            difference = _alternative_values_differ(case_file, case_file.expected[member], result[member])
        else:
            difference = _values_differ(case_file, case_file.expected[member], result[member])
        if difference is not None:
            differences.append(f"{member}: {difference}")
    return differences


def _labels_differ(case_file: CaseFile, expected_labels: JsonValue, labels: JsonValue) -> str | None:
    expected = _label_set(expected_labels)
    if labels is not None and not (
        isinstance(labels, list) and all(isinstance(label, str) for label in labels)
    ):
        return f"not a list of labels: {labels!r}"
    actual = _label_set(labels)
    if "hash" not in case_file.claims:
        expected.discard("hash_not_checked")
        actual.discard("hash_not_checked")
    return None if actual == expected else f"expected {sorted(expected)}, got {sorted(actual)}"


def _label_set(labels: JsonValue) -> set[str]:
    return {label for label in labels if isinstance(label, str)} if isinstance(labels, list) else set()


def _reasons_differ(expected: JsonValue, actual: JsonValue) -> str | None:
    wanted = Counter(_reason_key(reason) for reason in _list(expected, "expected.reasons"))
    if not isinstance(actual, list):
        return f"not a list: {actual!r}"
    try:
        found = Counter(_reason_key(reason) for reason in actual)
    except CaseFileError as error:
        return str(error)
    if found == wanted:
        return None
    missing = sorted((wanted - found).elements(), key=repr)
    unexpected = sorted((found - wanted).elements(), key=repr)
    return f"missing {missing}, unexpected {unexpected}"


def _reason_key(reason: JsonValue) -> tuple[str, str | None]:
    reason = _object(reason, "a reason")
    condition = reason.get("condition")
    code = _string(reason.get("code"), "a reason's code")
    return (code, None if condition is None else _string(condition, "a reason's condition"))


def _conditions_differ(case_file: CaseFile, expected: JsonValue, actual: JsonValue) -> str | None:
    """Condition entries as a set keyed by `name`: each name once, in no set order."""
    wanted: dict[str, JsonValue] = {}
    for entry in _list(expected, "expected conditions"):
        name = _string(_object(entry, "an expected condition entry").get("name"), "a condition entry's name")
        if name in wanted:
            raise CaseFileError(f"{case_file.path.name} expects the condition {name!r} twice")
        wanted[name] = entry
    if not isinstance(actual, list):
        return f"not a list: {actual!r}"
    found: dict[str, JsonValue] = {}
    for entry in actual:
        key = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(key, str):
            return f"an entry without a string name: {entry!r}"
        if key in found:
            return f"{key!r} twice"
        found[key] = entry
    missing, unexpected = sorted(wanted.keys() - found.keys()), sorted(found.keys() - wanted.keys())
    if missing or unexpected:
        return f"missing {missing}, unexpected {unexpected}"
    differing = ((name, _values_differ(case_file, wanted[name], found[name])) for name in sorted(wanted))
    return next((f"{name}: {difference}" for name, difference in differing if difference is not None), None)


def _alternative_values_differ(case_file: CaseFile, expected: JsonValue, actual: JsonValue) -> str | None:
    """Entries in stored order, member by member, each entry's `labels` and `conditions` as the result's."""
    entries = _list(expected, "expected alternative_values")
    if not isinstance(actual, list) or len(actual) != len(entries):
        return f"expected {len(entries)} entries, got {actual!r}"
    for index, (expected_entry, found) in enumerate(zip(entries, actual, strict=True)):
        wanted = _object(expected_entry, "an expected alternative_values entry")
        if not isinstance(found, dict):
            return f"entry {index} is not an object: {found!r}"
        for name in sorted(wanted.keys() | found.keys()):
            if name == "labels":
                difference = _labels_differ(case_file, wanted.get(name), found.get(name))
            elif name not in found:
                difference = "missing"
            elif name not in wanted:
                difference = f"must be absent, got {found[name]!r}"
            elif name == "conditions":
                difference = _conditions_differ(case_file, wanted[name], found[name])
            else:
                difference = _values_differ(case_file, wanted[name], found[name])
            if difference is not None:
                return f"entry {index}, {name}: {difference}"
    return None


def _sets_differ(expected: JsonValue, actual: JsonValue) -> str | None:
    if not isinstance(actual, list):
        return f"not a list: {actual!r}"
    # A listing holds strings, so its entries compare exactly.
    wanted = {json.dumps(entry, sort_keys=True) for entry in _list(expected, "expected.value")}
    found = {json.dumps(entry, sort_keys=True) for entry in actual}
    if found == wanted:
        return None
    return f"missing {sorted(wanted - found)}, unexpected {sorted(found - wanted)}"


def _values_differ(case_file: CaseFile, expected: JsonValue, actual: JsonValue) -> str | None:
    mismatch = f"expected {expected!r}, got {actual!r}"
    if isinstance(expected, float):
        if not isinstance(actual, float):
            return mismatch
        return None if _numbers_agree(case_file, expected, actual) else mismatch
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return mismatch
        differing = (_values_differ(case_file, e, a) for e, a in zip(expected, actual, strict=True))
        return next((difference for difference in differing if difference is not None), None)
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            return mismatch
        differing = (_values_differ(case_file, expected[name], actual[name]) for name in expected)
        return next((difference for difference in differing if difference is not None), None)
    # None, a bool or a string: bool must not meet a number that equals it.
    return None if type(actual) is type(expected) and actual == expected else mismatch


def _numbers_agree(case_file: CaseFile, expected: float, actual: float) -> bool:
    if case_file.exact:
        return struct.pack(">d", expected) == struct.pack(">d", actual)
    if case_file.relative_tolerance is None:
        raise CaseFileError(
            f"{case_file.path.name} compares a number with neither relative_tolerance nor exact"
        )
    if expected == 0:
        return abs(actual) <= case_file.relative_tolerance
    return abs(actual - expected) <= case_file.relative_tolerance * abs(expected)


def _tolerance(value: JsonValue) -> float | None:
    if value is None or (isinstance(value, float) and value >= 0):
        return value
    raise CaseFileError(f"relative_tolerance is not a number at least 0: {value!r}")


def _object(value: JsonValue, what: str) -> JsonObject:
    if not isinstance(value, dict):
        raise CaseFileError(f"{what} is not an object")
    return value


def _list(value: JsonValue, what: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise CaseFileError(f"{what} is not a list")
    return value


def _string(value: JsonValue, what: str) -> str:
    if not isinstance(value, str):
        raise CaseFileError(f"{what} is not a string")
    return value


def reason_json(reason: Reason) -> JsonObject:
    shape: JsonObject = {"code": reason.code}
    if reason.condition is not None:
        shape["condition"] = reason.condition
    if reason.detail is not None:
        shape["detail"] = reason.detail
    return shape


def content_hash_executor(
    parse: Callable[[bytes], JsonValue | Reason] = jsonio.parse,
    digest: Callable[[JsonValue], str] = hashing.content_hash,
) -> Executor:
    """The `content_hash` operation (README, "Operations"), from the given parser and hash."""

    def execute(case_file: CaseFile, claims: frozenset[Suite]) -> JsonObject:
        value = parse(case_file.input_bytes("value"))
        if isinstance(value, Reason):
            return {"status": "not_met", "reasons": [reason_json(value)]}
        return {"status": "met", "reasons": [], "value": digest(value)}

    return execute


def read_executor() -> Executor:
    """A read of the case's request, or of the file `inputs.request` names, among `inputs.records`. The result
    goes through JSON text, as a consumer would receive it."""

    def execute(case_file: CaseFile, claims: frozenset[Suite]) -> JsonObject:
        store = load_records(case_file.input_paths("records"))
        request = case_file.input_bytes("request") if "request" in case_file.inputs else case_file.request
        written = jsonio.parse(json.dumps(read(request, store, claims=claims).to_json()).encode())
        assert not isinstance(written, Reason), written
        return _object(written, "the result")

    return execute


def list_records_executor() -> Executor:
    """The `list_records` operation (README, "Operations"): always `met`, listing the good records."""

    def execute(case_file: CaseFile, claims: frozenset[Suite]) -> JsonObject:
        listed = {
            (record.id, record.version)
            for record in load_records(case_file.input_paths("records")).list_records()
        }
        return {
            "status": "met",
            "reasons": [],
            "value": [{"id": id_, "version": version} for id_, version in sorted(listed)],
        }

    return execute


# The claims this implementation runs under, each case file under every one that agrees with it: plain read
# and HS, as by default; plain read alone, a reader without HS; and with the fits and reference data suite
# too, whose `want`s step 0 then accepts. A read under it ends by step 5 or raises, so claiming that suite
# gives no answer a step not built could change.
CONFIGURATIONS: tuple[frozenset[Suite], ...] = (
    frozenset({"plain_read", "hash"}),
    frozenset({"plain_read"}),
    frozenset({"plain_read", "hash", "fits_and_reference_data"}),
)
EXECUTORS: dict[str, Executor] = {
    "content_hash": content_hash_executor(),
    "read": read_executor(),
    "list_records": list_records_executor(),
}

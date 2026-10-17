# SPDX-License-Identifier: Apache-2.0
"""Every conformance case file of a read, run through the reference model under every configuration of claims
the case allows, and compared with its expected answer as `docs/specification/README.md` ("Case files") says.

Case files and their inputs are read with the model's own strict JSON, so that nothing the model is given
passes through `materica`; the comparison is the conformance runner's, whose own tests show it fails on wrong
answers (`tests/conformance/test_comparator.py`)."""

import itertools
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final, Literal

from tests.conformance.runner import CONFORMANCE, CaseFile, compare
from tests.reference import read_model
from tests.reference.exceptions import EXCEPTIONS, Excepted
from tests.reference.strict_json import JsonObject, JsonValue, NotStrictJson, parse

# The suites whose claim changes what a read gives (`read_side_contract.md` section 3: the hash at step 4, a
# parameter set at step 8, and the `want`s of step 0); every configuration claims plain read beside them.
SUITES: Final = ("hash", "fits_and_reference_data", "family_evaluation")
CONFIGURATIONS: Final = tuple(
    frozenset({"plain_read", *chosen})
    for size in range(len(SUITES) + 1)
    for chosen in itertools.combinations(SUITES, size)
)


@dataclass(frozen=True)
class Outcome:
    kind: Literal["agrees", "differs", "no verdict"]
    detail: str = ""


# The table evaluation suite is not a read. Each of its files asks an evaluator for a table's values at points
# (README.md:192 "A **table evaluation case** (`read_side_contract.md` section 7) names `{"operation":
# "evaluate"`), as a consumer's own evaluator does, outside the read; the model, a model of the read, has no
# answer to it, and those files are the table evaluator's to agree with.
NOT_A_READ: Final = "table_evaluation"


@cache
def case_files() -> tuple[CaseFile, ...]:
    return tuple(
        CaseFile.from_document(path, parse(path.read_bytes()))
        for path in sorted(CONFORMANCE.glob("*/cases/*.json"))
    )


@cache
def read_case_files() -> tuple[CaseFile, ...]:
    return tuple(case_file for case_file in case_files() if case_file.suite != NOT_A_READ)


@cache
def input_bytes(path: Path) -> bytes:
    return path.read_bytes()


def answer(case_file: CaseFile, claims: frozenset[str]) -> JsonObject | read_model.NoVerdict:
    """The model's answer to the case's operation: a read, `list_records` or `content_hash`."""
    if case_file.operation == "content_hash":
        return read_model.hash_operation(case_file.input_bytes("value"))
    sources = [input_bytes(path) for path in case_file.input_paths("records")]
    if case_file.operation == "list_records":
        return read_model.list_records(sources)
    request: JsonValue | NotStrictJson = case_file.request
    if "request" in case_file.inputs:
        try:
            request = parse(case_file.input_bytes("request"))
        except NotStrictJson as fault:
            request = fault
    return read_model.read(request, sources, claims)


def agreeing(case_file: CaseFile) -> list[frozenset[str]]:
    """The configurations that claim the case's suite and agree with every claim it states (README.md,
    "Claims")."""
    return [
        claimed
        for claimed in CONFIGURATIONS
        if case_file.suite in claimed
        and all((suite in claimed) == claim for suite, claim in case_file.claims.items())
    ]


def outcome(case_file: CaseFile) -> Outcome:
    """Whether the model agrees with the case file under every configuration of claims it allows."""
    configurations = agreeing(case_file)
    if not configurations:
        return Outcome("differs", "no configuration of claims agrees with the case")
    for claims in configurations:
        try:
            given = answer(case_file, claims)
        except Exception as error:  # a seeded fault may make the model raise: that is a disagreement too
            return Outcome("differs", f"claiming {sorted(claims)}, the model raised {error!r}")
        if isinstance(given, read_model.NoVerdict):
            return Outcome("no verdict", given.why)
        differences = compare(case_file, given)
        if differences:
            return Outcome("differs", f"claiming {sorted(claims)}: {'; '.join(differences)}")
    return Outcome("agrees")


def judged(name: str, found: Outcome, exceptions: Mapping[str, Excepted]) -> str | None:
    """What is wrong with the model's outcome on a case file, given the list of exceptions, or None."""
    kinds = [kind for kind, excepted in exceptions.items() if name in excepted.case_files]
    if len(kinds) > 1:
        return f"{name} is listed under {len(kinds)} kinds: {kinds}"
    if found.kind == "agrees":
        return (
            f"{name} agrees with the model, but is listed under {kinds[0]!r}: a stale entry"
            if kinds
            else None
        )
    if not kinds:
        return f"{name}: the model {found.kind}, and no kind lists it: {found.detail}"
    excepted = exceptions[kinds[0]]
    if excepted.outcome != found.kind:
        return f"{name} is listed under {kinds[0]!r} as {excepted.outcome}, but {found.kind}"
    if excepted.detail is not None and excepted.detail != found.detail:
        return f"{name} is listed under {kinds[0]!r} for {excepted.detail!r}, but {found.detail!r}"
    return None


def first_disagreement(
    judge: Callable[[CaseFile], Outcome] = outcome, exceptions: Mapping[str, Excepted] = EXCEPTIONS
) -> str | None:
    """The first case file of a read, in name order, whose outcome the list of exceptions does not give, or
    None."""
    for case_file in read_case_files():
        problem = judged(case_file.path.name, judge(case_file), exceptions)
        if problem is not None:
            return problem
    return None

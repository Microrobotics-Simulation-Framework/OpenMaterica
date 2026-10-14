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
from tests.conformance.runner import CONFORMANCE
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


def _nested(depth: int) -> JsonValue:
    value: JsonValue = []
    for _ in range(depth - 1):
        value = [value]
    return value


@pytest.mark.parametrize(("depth", "deeper"), [(64, False), (65, True), (100_000, True)])
def test_the_reference_measures_depth_without_recursion(depth: int, deeper: bool) -> None:
    deeper_than = reference_reader._deeper_than  # pyright: ignore[reportPrivateUsage]  # the check under test
    assert deeper_than(_nested(depth), 64) is deeper

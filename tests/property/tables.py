# SPDX-License-Identifier: Apache-2.0
"""The table evaluation cases, read as tables and entries, for the unit test of `core/evaluate.py`."""

from typing import NamedTuple

from materica.core.evaluate import Scheme
from materica.core.jsonio import JsonValue
from tests.conformance import runner

SCHEMES: tuple[Scheme, ...] = ("linear", "loglog")


class Table(NamedTuple):
    x: tuple[float, ...]
    y: tuple[float, ...]
    scheme: Scheme
    edges: tuple[float, ...]
    source_range: tuple[float, float] | None


class CaseEntry(NamedTuple):
    case: str  # the case file's name
    table: Table
    at: float
    expected: dict[str, JsonValue]  # its entry of `expected.evaluations`


def _numbers(value: JsonValue) -> tuple[float, ...]:
    assert isinstance(value, list), value
    assert all(isinstance(number, float) for number in value), value
    return tuple(number for number in value if isinstance(number, float))


def case_entries() -> list[CaseEntry]:
    """Every entry of every table evaluation case, with its table and its operating value."""
    found: list[CaseEntry] = []
    for case_file in runner.discover():
        if case_file.suite != "table_evaluation":
            continue
        request = case_file.request
        assert isinstance(request, dict), case_file.path.name
        table = request["table"]
        evaluations = case_file.expected["evaluations"]
        assert isinstance(table, dict), case_file.path.name
        assert isinstance(evaluations, list), case_file.path.name
        scheme = table["scheme"]
        assert scheme in SCHEMES, case_file.path.name
        source_range = _numbers(table["source_range"]) if "source_range" in table else None
        read = Table(
            _numbers(table["x"]),
            _numbers(table["y"]),
            "linear" if scheme == "linear" else "loglog",
            _numbers(table["edges"]),
            None if source_range is None else (source_range[0], source_range[1]),
        )
        for at, expected in zip(_numbers(request["at"]), evaluations, strict=True):
            assert isinstance(expected, dict), case_file.path.name
            found.append(CaseEntry(case_file.path.name, read, at, expected))
    return found

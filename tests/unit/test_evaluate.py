# SPDX-License-Identifier: Apache-2.0
"""The table evaluator (`core/evaluate.py`) against every table evaluation case, as the S3 design's section
5.4 item 4 asks: each entry's number and `in_range` at 1e-12 relative, and each refusal. OpenMaterica claims
no table evaluation (`read_side_contract.md` section 7): this ties the reader's numbers to the cases. A case's
derivative is not compared, since the reader computes none.

Each thing compared has a control in which a broken evaluator fails it, and the edges of the text are examples
below.
"""

import math
from collections.abc import Callable, Sequence

import pytest

from materica.core import evaluate
from tests.conformance.runner import CONFORMANCE
from tests.property.tables import CaseEntry, case_entries

TOLERANCE = 1e-12
ENTRIES = case_entries()


def disagreements(entries: Sequence[CaseEntry] = ENTRIES) -> list[str]:
    """Where `core/evaluate.py` and a case entry differ: a refusal, `in_range`, or the number beyond 1e-12
    relative, absolute where the case's number is zero."""
    found: list[str] = []
    for entry in entries:
        x, y, scheme, edges, source_range = entry.table
        number = evaluate.table_value(x, y, scheme, edges, source_range, entry.at)
        where = f"{entry.case} at {entry.at!r}"
        if entry.expected.get("refused") is True:
            if number is not None:
                found.append(f"{where}: {number!r}, not refused")
            continue
        if number is None:
            found.append(f"{where}: refused")
            continue
        if evaluate.in_readable_range(x, source_range, entry.at) is not entry.expected["in_range"]:
            found.append(f"{where}: in_range is not {entry.expected['in_range']}")
        expected = entry.expected["value"]
        assert isinstance(expected, float), where
        if abs(number - expected) > TOLERANCE * (abs(expected) or 1.0):
            found.append(f"{where}: {number!r}, not {expected!r}")
    return found


def test_the_evaluator_gives_every_number_in_range_and_refusal_of_the_table_evaluation_cases() -> None:
    assert disagreements() == []


def test_every_table_evaluation_case_file_is_compared() -> None:
    """So that a case file the reader of the cases skipped could not pass unseen."""
    on_disk = {path.name for path in (CONFORMANCE / "table_evaluation" / "cases").glob("*.json")}
    assert on_disk
    assert {entry.case for entry in ENTRIES} == on_disk
    assert any(entry.expected.get("refused") is True for entry in ENTRIES)
    assert any(entry.expected.get("in_range") is False for entry in ENTRIES)


def _source_range_ignored(x: Sequence[float], source_range: Sequence[float] | None) -> tuple[float, float]:
    return x[0], x[-1]


def _linear_in_log_space(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    return LOGLOG(x0, x1, y0, y1, at)


LOGLOG = evaluate.loglog
TABLE_VALUE = evaluate.table_value


def _clamped_to_x(
    x: Sequence[float],
    y: Sequence[float],
    scheme: evaluate.Scheme,
    edges: Sequence[float],
    source_range: Sequence[float] | None,
    at: float,
) -> float | None:
    """Outside the readable range, the value at `x[0]` or `x[-1]`, as NumPy's `interp` clamps."""
    number = TABLE_VALUE(x, y, scheme, edges, source_range, at)
    if number is None or evaluate.in_readable_range(x, source_range, at):
        return number
    return y[0] if at < evaluate.readable_range(x, source_range)[0] else y[-1]


# What each broken evaluator replaces, its fault, the replacement, and what the comparison must report.
CONTROLS: list[tuple[str, str, Callable[..., object], str]] = [
    ("readable_range", "source_range_ignored", _source_range_ignored, "in_range is not False"),
    ("on_edge", "edges_ignored", lambda *_: False, "not refused"),
    ("beyond_an_edge", "extrapolated_beyond_an_edge", lambda *_: False, "not refused"),
    ("loglog", "loglog_as_linear", evaluate.linear, "TE-004.loglog_values.json"),
    ("linear", "linear_in_log_space", _linear_in_log_space, "TE-004.linear_values.json"),
    ("table_value", "clamped_to_x", _clamped_to_x, "TE-002.source_range_narrow.json at 285.0: 1000.0"),
]


@pytest.mark.parametrize(("name", "fault", "broken", "reported"), CONTROLS, ids=[c[1] for c in CONTROLS])
def test_a_broken_evaluator_disagrees_with_the_cases(
    name: str, fault: str, broken: Callable[..., object], reported: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evaluate, name, broken)
    found = disagreements()
    assert any(reported in problem for problem in found), (fault, found[:5])


# The edges of the text, by example.


def test_a_log_log_interval_between_adjacent_doubles_never_divides_by_zero() -> None:
    """S3Q16: in doubles, `ln x1 - ln x0` is 0 for `x0 = 1e300` and the next double. Exactly, the reader
    gives each knot's `y` and never raises."""
    x0 = 1e300
    x1 = math.nextafter(x0, math.inf)
    x2 = math.nextafter(x1, math.inf)
    assert math.log(x1) - math.log(x0) == 0.0  # the control: doubles divide by zero here
    x, y = [x0, x2], [1.0, 4.0]
    assert evaluate.table_value(x, y, "loglog", [], None, x1) == 2.0
    assert evaluate.table_value(x, y, "loglog", [], None, x0) == 1.0
    assert evaluate.table_value(x, y, "loglog", [], None, x2) == 4.0


def test_a_linear_interval_whose_values_span_every_double_is_exact() -> None:
    """In doubles `y1 - y0` overflows; exactly, the midpoint between the largest doubles of each sign is 0."""
    largest = 1.7976931348623157e308
    assert largest - -largest == math.inf  # the control
    assert evaluate.table_value([0.0, 2.0], [-largest, largest], "linear", [], None, 1.0) == 0.0


def test_negative_zero_at_a_knot_is_returned_as_stored() -> None:
    """S3Q16: "At a knot that is no edge, the stored `y` is returned as stored, `-0` included", whichever
    zero the operating value is (table item 3: "compared by value")."""
    x, y = [-1.0, 0.0, 1.0], [1.0, -0.0, 1.0]
    for at in (0.0, -0.0):
        number = evaluate.table_value(x, y, "linear", [], None, at)
        assert number == 0.0
        assert number is not None
        assert math.copysign(1.0, number) == -1.0


def test_negative_zero_at_an_edge_at_zero_is_refused() -> None:
    """Table item 3: "`-0` lies at an end or an edge at `0`" (PR-018's arm)."""
    x, y, edges = [-1.0, 0.0, -0.0, 1.0], [1.0, 2.0, 3.0, 4.0], [0.0]
    for at in (0.0, -0.0):
        assert evaluate.on_edge(edges, at)
        assert evaluate.table_value(x, y, "linear", edges, None, at) is None
    # Either side, the interval on that side (table item 3, "strictly where an edge is concerned").
    assert evaluate.table_value(x, y, "linear", edges, None, -0.5) == 1.5
    assert evaluate.table_value(x, y, "linear", edges, None, 0.5) == 3.5


def test_an_edge_outside_the_readable_range_is_at_an_edge_and_outside() -> None:
    """S3Q8 rule 4, T11 of the cases: at 273, `at_edge` and `outside_range` both stand, and no number."""
    x, y, edges, source_range = (
        [263.0, 273.0, 273.0, 283.0],
        [918.0, 916.0, 1000.0, 999.5],
        [273.0],
        [275.0, 283.0],
    )
    assert evaluate.on_edge(edges, 273.0)
    assert not evaluate.in_readable_range(x, source_range, 273.0)
    assert evaluate.table_value(x, y, "linear", edges, source_range, 273.0) is None
    # Below it, beyond the edge from the range: no number; between it and the range, the end's.
    assert evaluate.beyond_an_edge(x, edges, source_range, 272.0)
    assert evaluate.table_value(x, y, "linear", edges, source_range, 272.0) is None
    assert evaluate.table_value(x, y, "linear", edges, source_range, 274.0) == 999.9

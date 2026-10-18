# SPDX-License-Identifier: Apache-2.0
"""Step 8's status rows (`value_shapes.status_row`, read from the generated shapes) against those of
`provenance.md` section 1 item 5 (`status_rows.py`, read from the text and the writer schema), at every place
of the writer schema where a status object may stand and step 8 reads it: the tokens, and the members of the
shape a status object stands for. The two sources share no code, so a fault in either shows here; step 8's
oracles read the second."""

from collections.abc import Callable

import pytest

from materica import shapes
from materica.core import value_shapes
from tests.spec_sync import status_rows
from tests.spec_sync.test_value_fields import DEFINITIONS, members

Row = Callable[[type, str], tuple[tuple[str, ...], tuple[str, ...]]]


def shape_of(definition: str) -> type | None:
    """The generated shape of a writer definition, named by datamodel-code-generator's rule."""
    found = getattr(shapes, "".join(word.capitalize() for word in definition.split("_")), None)
    return found if isinstance(found, type) else None


# The definitions whose status places step 8's shared checks read (`read_side_contract.md` section 3, step 8):
# a field's, a condition's and a fact's, the statistics block's and its parts'. The forms' own members are
# their readers' (`fields.py`), held to `provenance.md` section 1 item 5 by HP3's catalogue and the positions
# test; an evidence report's members take any of the five tokens there, where the writer splits them between
# a report and a withheld report.
READ = {
    "constant_field",
    "conditions",
    "plus_minus_entry",
    "specimen",
    "post_mortem_interval",
    "donor_age",
    "statistics_block",
    "population_level",
    "uncertainty",
}


def places() -> list[tuple[str, str]]:
    """Each member of a definition step 8 reads that may hold a status object, its own place or through the
    definition it refers to (a unit, a count)."""
    found: list[tuple[str, str]] = []
    for definition in sorted(READ):
        for member in members(DEFINITIONS, definition):
            try:
                status_rows.tokens(definition, member)
            except ValueError:
                continue
            found.append((definition, member))
    return found


def disagreements(row: Row) -> list[str]:
    found: list[str] = []
    for definition, member in places():
        shape = shape_of(definition)
        assert shape is not None, definition
        tokens, defines = row(shape, member)
        if definition == "conditions":
            defines = value_shapes.CONDITION_MEMBERS
        if set(tokens) != set(status_rows.tokens(definition, member)):
            found.append(f"{definition}.{member}: tokens {sorted(tokens)}")
        if set(defines) != set(status_rows.defines(definition, member)):
            found.append(f"{definition}.{member}: members {sorted(defines)}")
    return found


def test_step_8s_status_rows_are_the_texts() -> None:
    assert disagreements(value_shapes.status_row) == []
    assert set(value_shapes.CONDITION_MEMBERS) == set(status_rows.CONDITION_MEMBERS)


def test_every_place_step_8_reads_is_compared() -> None:
    compared = {definition for definition, _ in places()}
    assert compared == READ
    assert {("constant_field", "unit"), ("statistics_block", "n_specimens")} <= set(places())


def _defines_none(shape: type, member: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return value_shapes.status_row(shape, member)[0], ()


def _first_token_only(shape: type, member: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tokens, defines = value_shapes.status_row(shape, member)
    return tokens[:1], defines


@pytest.mark.parametrize("row", [_defines_none, _first_token_only], ids=["defines_none", "first_token_only"])
def test_a_status_row_of_step_8_with_a_fault_is_found(row: Row) -> None:
    assert disagreements(row) != []

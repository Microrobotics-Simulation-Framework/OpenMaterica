# SPDX-License-Identifier: Apache-2.0
"""The writer schema's mutant table (`test_writer_mutants.py`) read whole, in a module apart from its
searches, so that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

import copy

from tests.property import value_fields
from tests.property.test_writer_mutants import MUTANTS, ORIGINALS, SEARCHED_ON, TAKES, identifier


def test_each_mutant_changes_the_schema() -> None:
    """A mutant whose path had moved would change nothing, and survive for the wrong reason; one naming a
    fault no family draws could never die at it."""
    names = {fault.name for fault in value_fields.FAULTS}
    for mutant in MUTANTS:
        schema = copy.deepcopy(ORIGINALS[mutant.file])
        mutant.change(schema)
        assert schema != ORIGINALS[mutant.file], mutant.name
        assert mutant.killer == TAKES or set(mutant.intended) <= names, mutant.name
        assert (mutant.killer == TAKES) == (identifier(mutant) in SEARCHED_ON), mutant.name

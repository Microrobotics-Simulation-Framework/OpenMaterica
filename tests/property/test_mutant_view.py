# SPDX-License-Identifier: Apache-2.0
"""The hashable view that `test_mutants.py` writes again for its hash mutants is, without a fault, the core's
`hashable_view`: so each of those mutants differs from the core by its fault alone. In a module apart from the
mutant searches, so that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from hypothesis import given, settings

from materica.core.hashing import hashable_view
from materica.core.jsonio import JsonValue
from tests.conftest import EXAMPLES
from tests.property import test_hashing_properties as hashing_properties
from tests.property.strategies import SIZE
from tests.property.test_mutants import mutant_view


# This checks the mutants' own code, not the core's, so `deep` adds nothing to it: it searches as `ci` does at
# most, which saves `deep` some five minutes.
@settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
@given(hashing_properties.records(SIZE))
def test_the_view_without_a_fault_is_the_view(record: JsonValue) -> None:
    assert mutant_view(record) == hashable_view(record)

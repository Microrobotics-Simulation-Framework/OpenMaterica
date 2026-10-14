# SPDX-License-Identifier: Apache-2.0
# Atheris installs on Python 3.12 to 3.14 only; elsewhere its stub in typings/ stands in for it.
# pyright: reportMissingModuleSource=false
"""Fuzz target: Atheris drives the Hypothesis properties of the core in-process, through `fuzz_one_input`.

    python -m tests.fuzz.properties [CORPUS] [libFuzzer options]

The first byte picks the property, and the rest is the choices it draws. A failure is saved to the example
database and raised; `pytest tests/property`, under the same profile, then replays it first and shrinks it.
"""

import importlib
import sys
from collections.abc import Callable

import atheris

# Imported first, and inside this block, so that Atheris instruments the core for its coverage.
with atheris.instrument_imports(include=["materica"]):
    importlib.import_module("materica")

from hypothesis.core import HypothesisHandle

# The Hypothesis profiles, from MATERICA_HYPOTHESIS_PROFILE as under pytest: the properties' sizes come from
# the profile, and a failure replays only under the profile it was found with.
importlib.import_module("tests.conftest")

from tests.fuzz import seeded_fault  # noqa: E402
from tests.property import test_canonical_properties as canonical_properties  # noqa: E402
from tests.property import test_hashing_properties as hashing_properties  # noqa: E402
from tests.property import test_jsonio_properties as jsonio_properties  # noqa: E402

PROPERTIES: list[Callable[..., None]] = [
    jsonio_properties.test_any_bytes_give_a_value_or_malformed,
    jsonio_properties.test_written_values_read_back,
    jsonio_properties.test_every_number_reads_as_the_nearest_double,
    jsonio_properties.test_each_listed_fault_is_refused,
    jsonio_properties.test_odd_but_valid_text_is_read,
    canonical_properties.test_output_matches_rfc8785,
    canonical_properties.test_every_double_reads_back_from_its_shortest_form,
    canonical_properties.test_names_sort_by_utf16_code_units,
    hashing_properties.test_the_hash_ignores_what_it_leaves_out,
    hashing_properties.test_editing_any_leaf_the_hash_covers_changes_it,
]


def handle(test: Callable[..., None]) -> HypothesisHandle:
    found: HypothesisHandle = test.hypothesis  # type: ignore[attr-defined]  # @given adds it; its types do not say.
    return found


HANDLES = [handle(test) for test in PROPERTIES]


def test_one_input(data: bytes) -> None:
    if data:
        HANDLES[data[0] % len(HANDLES)].fuzz_one_input(data[1:])


def main(arguments: list[str]) -> None:
    seeded_fault.seed_if_asked()
    atheris.Setup(arguments, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main(sys.argv)

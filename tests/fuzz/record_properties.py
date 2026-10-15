# SPDX-License-Identifier: Apache-2.0
# Atheris installs on Python 3.12 to 3.14 only; elsewhere its stub in typings/ stands in for it.
# pyright: reportMissingModuleSource=false
"""Fuzz target 3: Atheris drives the Hypothesis properties of records and the read, in-process, through
`fuzz_one_input`: the envelope checks against the reader schema, versions, the read's laws, and step 8's.

    python -m tests.fuzz.record_properties [CORPUS] [libFuzzer options]

As in `properties.py`, the first byte picks the property and the rest is the choices it draws; the
properties' strategies build records, stores and requests, so the fuzzer works on their structure, not on
bytes. A failure is saved to the example database and raised; `pytest tests/property`, under the same
profile, then replays it first and shrinks it.
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
from tests.property import test_envelope_properties as envelope_properties  # noqa: E402
from tests.property import test_read_properties as read_properties  # noqa: E402
from tests.property import test_value_field_properties as value_field_properties  # noqa: E402
from tests.property import test_version_properties as version_properties  # noqa: E402

PROPERTIES: list[Callable[..., None]] = [
    envelope_properties.test_the_envelope_checks_agree_with_the_reader_schema,
    version_properties.test_versions_order_as_their_integers,
    version_properties.test_a_text_is_a_version_exactly_when_it_matches,
    read_properties.test_a_read_never_raises_and_gives_each_reason_once,
    read_properties.test_the_order_and_identical_copies_of_the_sources_change_nothing,
    read_properties.test_a_record_of_another_identity_changes_nothing,
    read_properties.test_an_unreadable_source_turns_only_absent_or_pin_mismatch_into_malformed,
    read_properties.test_a_request_member_the_shape_does_not_name_changes_nothing,
    read_properties.test_every_listed_record_resolves_under_its_own_hash,
    value_field_properties.test_one_fault_gives_its_refusal_and_no_other,
    value_field_properties.test_a_field_without_a_fault_passes_step_8,
    value_field_properties.test_members_the_reader_does_not_know_change_nothing,
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

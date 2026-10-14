# SPDX-License-Identifier: Apache-2.0
"""(4) The core's envelope checks and the generated reader schema agree (`record_format.md` section 1 item 2),
on records changed near each boundary the item draws. The mutants they kill are in `test_mutants.py`."""

from collections.abc import Callable

import pytest
from hypothesis import example, given

from materica.core.envelope import envelope_problems
from materica.core.jsonio import JsonValue
from tests.property import records
from tests.property.records import Envelope
from tests.property.support import feature
from tests.spec_sync.schemas import validator

READER = validator("record.reader.json")

Problems = Callable[[JsonValue], list[str]]


def check_all_agree(problems: Problems, envelopes: list[Envelope]) -> None:
    for envelope in envelopes:
        accepted = problems(envelope.record) == []
        assert accepted == (READER(envelope.record) == []), (envelope.changes, problems(envelope.record))


# A record no small draw reaches: every known section, an unknown one, and null in each place left unchecked.
EVERY_PLACE: JsonValue = {
    "schema_version": "0.1",
    "record_type": "material",
    "id": "conformance/w.a-t_1",
    "version": "10.0." + "9" * 300,
    "name": "",
    "licence": {"values": "", "evidence": "", "x_note": None},
    "content_hash": "sha256:" + "f" * 64,
    "x_note": None,
    "body": {
        "sections": {
            **{name: {"fields": {"x": None}, "specimen": None} for name in records.KNOWN_SECTIONS},
            "acoustic": None,
        },
        "extensions": {"acme": None},
    },
}


# Each planned change, accepted or refused. A removal or a change of type at the envelope, the licence, and
# the overlay's body and base always refuses; a near miss in the base or a place left unchecked never does.
@pytest.mark.features(
    envelope_refused=0.33,
    licence_refused=0.33,
    overlay_body_refused=0.33,
    overlay_base_refused=0.33,
    base_pattern_accepted=0.33,
    unchecked_accepted=0.33,
    card_accepted=0.11,
    card_refused=0.21,
    material_body_accepted=0.05,
    material_body_refused=0.27,
    known_section_accepted=0.15,
    known_section_refused=0.17,
    overlay_scope_accepted=0.08,
    overlay_scope_refused=0.23,
    pattern_accepted=0.18,
    pattern_refused=0.13,
    record_type_accepted=0.26,
    record_type_refused=0.06,
    mixed_accepted=0.17,
    mixed_refused=0.15,
)
@example([Envelope(EVERY_PLACE, ())])
@given(records.sweeps())
def test_the_envelope_checks_agree_with_the_reader_schema(envelopes: list[Envelope]) -> None:
    for envelope in envelopes:
        accepted = envelope_problems(envelope.record) == []
        feature(f"{envelope.planned}_{'accepted' if accepted else 'refused'}")
    check_all_agree(envelope_problems, envelopes)

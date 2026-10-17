# SPDX-License-Identifier: Apache-2.0
"""The schema verdicts' switch point (`tests/verdicts.py`, `tests/spec_sync/schemas.py`): where the two
libraries disagree on a value a test judges, the test fails at once, naming both verdicts, and never reads the
disagreement as a refusal; and both read every resource at draft 2020-12."""

import copy
from urllib.parse import urljoin

import pytest
from hypothesis import strategies as st

from tests.property.test_writer_mutants import kill
from tests.property.test_writer_properties import Writer, check_takes
from tests.spec_sync.schemas import BASE, Disagreement, agreed, validator
from tests.verdicts import DOCUMENTS, Json

FACTS = urljoin(BASE, "vocabulary/specimen_facts.json")
UBERON = "vocabulary/specimen_facts.json#/$defs/anatomical_site_uberon"


def dollar_ended() -> Json:
    """The vocabulary's anatomical-site pattern ended in `$`, which python-jsonschema reads as matching before
    a final newline as well, and jsonschema-rs only at the end: so `UBERON:1\\n` is taken by python-jsonschema
    alone."""
    facts = copy.deepcopy(DOCUMENTS[FACTS])
    definitions = facts["$defs"]
    assert isinstance(definitions, dict)
    definitions["anatomical_site_uberon"] = {"type": "string", "pattern": "^UBERON:[0-9]+$"}
    return facts


def test_a_value_jsonschema_rs_alone_refuses_fails_the_test_naming_both_verdicts() -> None:
    errors = validator(UBERON, [dollar_ended()])
    with pytest.raises(Disagreement, match="jsonschema-rs refuses, python-jsonschema takes 'UBERON:1\\\\n'"):
        errors("UBERON:1\n")


def test_a_value_both_refuse_gives_python_jsonschemas_messages_and_one_both_take_none() -> None:
    """The control: the same validator, where the two agree, raises nothing."""
    errors = validator(UBERON, [dollar_ended()])
    assert errors("UBERON:x") != []
    assert errors("UBERON:1") == []


def test_a_search_never_takes_a_disagreement_for_a_mutants_death() -> None:
    """A tightening mutant dies where the writer refuses a field the text allows, and its message holds
    python-jsonschema's: a disagreement there must fail the search, not kill the mutant."""
    writer = Writer({"$ref": urljoin(BASE, UBERON)}, [dollar_ended()])
    with pytest.raises(Disagreement):
        kill(st.just("UBERON:1\n"), lambda field: check_takes(writer, field))


def test_a_search_still_kills_where_both_refuse() -> None:
    """The control: a field both refuse is the mutant's death, as before."""
    writer = Writer({"$ref": urljoin(BASE, UBERON)}, [dollar_ended()])
    tried, message = kill(st.just("UBERON:x"), lambda field: check_takes(writer, field))
    assert tried == 1
    assert message.startswith("refused a field the text allows: ["), message


def declaring(draft: str) -> Json:
    """A resource declaring `draft`, whose `$ref` stands beside `minLength`: draft 7 ignores a keyword beside
    a `$ref`, so `ab` passes it there; 2020-12 applies both."""
    return {
        "$schema": draft,
        "$id": "https://example.test/beside.json",
        "$defs": {"text": {"type": "string"}},
        "$ref": "#/$defs/text",
        "minLength": 3,
    }


def test_both_libraries_read_a_resource_at_2020_12_whatever_draft_it_declares() -> None:
    resource = declaring("http://json-schema.org/draft-07/schema#")
    assert agreed(str(resource["$id"]), [resource])("ab") is False


def test_a_resource_declaring_2020_12_is_read_alike() -> None:
    """The control: the same resource at the draft both read, without the registry's say."""
    resource = declaring("https://json-schema.org/draft/2020-12/schema")
    assert agreed(str(resource["$id"]), [resource])("ab") is False
    assert agreed(str(resource["$id"]), [resource])("abc") is True

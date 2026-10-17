# SPDX-License-Identifier: Apache-2.0
"""(13) What a read must not look at (`invariance_strategies.py`): the S2 design's HP4 and HP10.

- **HP4, isolation** (`read_side_contract.md` section 3, steps 7 and 8; PR-033, PR-045). A fault in another
  field, registered or not, or in another section's `specimen`, never changes a read: its result equals the
  read of the record without it, every member, reason detail and label alike. A fault in the read field's
  own section's `specimen` refuses it: `not_met`, with `form_invalid` or `unknown_token` alone, and no value.
- **HP10, the byte form never matters** (`record_format.md` sections 1 and 9; PR-047). A read of sources and a
  request written again, in another member order, whitespace, escapes and number spellings that read as the
  same doubles, gives the result the original gives, as JSON of the same types, compared as section 2 compares
  results (its condition entries and reasons as sets): the content hash and pin of either are the same.
"""

import json

import pytest
from hypothesis import given

from materica.core.read import read
from materica.core.record import RecordStore
from materica.shapes import Suite
from tests.property import invariance_strategies as strategies
from tests.property.invariance_strategies import Isolated, Rewritten
from tests.property.model_strategies import Example
from tests.property.strategies import SIZE
from tests.property.support import feature, same
from tests.property.test_model_properties import compared
from tests.reference.strict_json import JsonValue

REFUSING_A_SECTION = frozenset({"form_invalid", "unknown_token"})


def written(sources: tuple[bytes, ...], request: bytes, claims: frozenset[Suite]) -> JsonValue:
    """The read's result as a consumer receives it, through JSON text; or how it ended without one."""
    store = RecordStore()
    for number, source in enumerate(sources):
        store.add(f"source_{number}", source)
    try:
        result = read(request, store, claims=claims)
    except NotImplementedError:
        return "not yet"
    except ValueError as error:
        if "plain_read" in claims:
            raise AssertionError(f"the read raised {error!r}") from error
        return "misuse"
    except Exception as error:
        raise AssertionError(f"the read raised {error!r}") from error
    value: JsonValue = json.loads(json.dumps(result.to_json()))
    return value


# HP4.

# The read field's form, drawn as HP6's is, a constant as often as an interval and a composition together, so
# that HP4 is held to the forms S2b-1 reads (PR #37's review, L2). Each is declared by its chance: over 48
# runs of each property at `ci` (seeds 6001 to 6048, 2026-10-17), means 0.50, 0.25 and 0.25 and least shares
# 0.432, 0.162 and 0.188, each declared at the lesser property's least share, rounded down. From the measured
# clusters, each falls below its draw floor with a probability below 1e-19 a run.
FORM_CHANCES = {"form_constant": 0.43, "form_interval": 0.16, "form_composition": 0.18}


def check_isolated(isolated: Isolated) -> None:
    base = isolated.base
    unchanged = written(
        (json.dumps(base.record).encode(),), json.dumps(base.request).encode(), isolated.claims
    )
    changed = written(
        (json.dumps(isolated.changed).encode(),),
        strategies.repointed(base.request, isolated.changed),
        isolated.claims,
    )
    assert same(unchanged, changed), (unchanged, changed)


@pytest.mark.chances(**FORM_CHANCES)
@pytest.mark.drawn(*strategies.ELSEWHERE)
@given(strategies.isolated(SIZE))
def test_a_fault_in_another_field_or_section_never_changes_the_read(isolated: Isolated) -> None:
    feature(isolated.way)
    feature(f"form_{isolated.form}")
    check_isolated(isolated)


def check_refused(isolated: Isolated) -> None:
    changed = written(
        (json.dumps(isolated.changed).encode(),),
        strategies.repointed(isolated.base.request, isolated.changed),
        isolated.claims,
    )
    assert isinstance(changed, dict), changed
    reasons = changed["reasons"]
    assert isinstance(reasons, list)
    codes = {str(reason["code"]) for reason in reasons if isinstance(reason, dict)}
    assert changed["status"] == "not_met", changed
    assert codes, changed
    assert codes <= REFUSING_A_SECTION, codes
    assert "value" not in changed, changed


@pytest.mark.chances(**FORM_CHANCES)
@given(strategies.own_section_faulted(SIZE))
def test_a_fault_in_the_read_fields_section_specimen_refuses_it(isolated: Isolated) -> None:
    feature(f"form_{isolated.form}")
    check_refused(isolated)


# HP10.


def outcome(example: Example) -> JsonValue:
    """The result as section 2 compares results, its sets in one order (`test_model_properties.compared`):
    the condition entries and reasons come in the order the record and the request write theirs."""
    result = written(example.sources, example.request, example.claims)
    return compared(result) if isinstance(result, dict) else result


def check_rewritten(drawn: Rewritten) -> None:
    original, again = outcome(drawn.original), outcome(drawn.rewritten)
    assert same(original, again), (original, again)


@pytest.mark.drawn(*strategies.REWRITTEN_KINDS)
@given(strategies.rewritten_reads(SIZE))
def test_the_byte_form_of_the_sources_and_the_request_never_changes_the_read(drawn: Rewritten) -> None:
    feature(drawn.original.kind)
    check_rewritten(drawn)

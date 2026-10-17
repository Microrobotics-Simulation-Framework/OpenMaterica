# SPDX-License-Identifier: Apache-2.0
"""Mutants of what a read must not look at (`test_invariance_properties.py`, HP4 and HP10), each with one
fault the property named must find within the examples the `ci` profile gives a property, at both sizes, at an
example of a way or kind it names, recording the examples its kill took as `examples_to_kill`. A fault is
injected where the core looks a name up when it runs."""

import dataclasses
from collections.abc import Callable, Collection
from typing import Any, NamedTuple

import pytest
from hypothesis import strategies as st

from materica.core import canonical, fields, jsonio, read, value_shapes
from materica.core.fields import RecordField
from materica.core.reasons import Reason
from materica.core.value_shapes import Found, JsonObject, an_object
from materica.core.vocabulary import VOCABULARY, RecordFieldSpec
from materica.shapes import Suite
from tests.property import invariance_strategies as strategies
from tests.property import test_invariance_properties as properties
from tests.property import test_value_field_mutants as value_field_mutants
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_condition_mutants import kill
from tests.property.test_mutants import setting

# A search stops at the first example that kills its mutant, which Hypothesis then writes out; those of these
# properties can pass 30 kB, which Hypothesis warns of, and which nobody reads.
pytestmark = pytest.mark.filterwarnings(
    "ignore:Generating overly large repr:hypothesis.errors.HypothesisWarning"
)


# Each property that kills a mutant, by name: its examples at a size, its check, and what an example shows.
KILLERS: dict[
    str, tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None], Callable[[Any], str]]
] = {
    "HP4": (strategies.isolated, properties.check_isolated, lambda isolated: isolated.way),
    "HP4 refusal": (strategies.own_section_faulted, properties.check_refused, lambda isolated: isolated.way),
    "HP10": (strategies.rewritten_reads, properties.check_rewritten, lambda drawn: drawn.original.kind),
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # ways or kinds, one of which the example that kills it must show


FIND_FIELD = fields.find_field
FORM_PROBLEMS = fields.form_problems
DOUBLE = jsonio._double  # pyright: ignore[reportPrivateUsage]


def sections_of(record: JsonObject) -> JsonObject:
    return an_object(an_object(record["body"])["sections"])


# HP4: isolation.


def _specimen_facts_merged_across_sections(record: JsonObject, spec: RecordFieldSpec) -> RecordField | Reason:
    """The S2 design's HP4 mutant: the field's section's facts are every section's."""
    found = FIND_FIELD(record, spec)
    if isinstance(found, Reason):
        return found
    facts: JsonObject = {}
    for section in sections_of(record).values():
        held = section.get("specimen") if isinstance(section, dict) else None
        facts.update(held if isinstance(held, dict) else {})
    own = found.section.get("specimen")
    facts.update(own if isinstance(own, dict) else {})
    return dataclasses.replace(found, section={**found.section, "specimen": facts})


def _every_field_checked(field: RecordField, record: JsonObject, claims: Collection[Suite]) -> Found:
    found = FORM_PROBLEMS(field, record, claims)
    for name, spec in VOCABULARY.fields.items():
        other = FIND_FIELD(record, spec)
        if name != field.spec.name and isinstance(other, RecordField):
            try:
                found += FORM_PROBLEMS(other, record, claims)
            except NotImplementedError:
                continue
    return found


def _every_section_checked(field: RecordField, record: JsonObject, claims: Collection[Suite]) -> Found:
    found = FORM_PROBLEMS(field, record, claims)
    for name, section in sections_of(record).items():
        if name != field.spec.section and isinstance(section, dict):
            found += value_shapes.section_problems(name, section)
    return found


def taken(name: str) -> Callable[[pytest.MonkeyPatch], None]:
    (found,) = [mutant for mutant in value_field_mutants.MUTANTS if mutant.name == name]
    inject: Callable[[pytest.MonkeyPatch], None] = found.inject
    return inject


# HP10: the byte form.


def _members_as_written(name: str) -> bytes:
    """The S2 design's HP10 mutant (B7): the recomputed hash taken over the members in the order the source
    writes them, not in RFC 8785's."""
    return b""


def _integers_as_integers(text: str) -> Any:
    """A number written without a fraction or an exponent read as an integer, not the double it names."""
    return int(text) if text.lstrip("-").isdigit() else DOUBLE(text)


MUTANTS = [
    Mutant(
        "specimen_facts_merged_across_sections",
        "HP4",
        setting(read, "find_field", _specimen_facts_merged_across_sections),
        ("another_section_specimen",),
    ),
    Mutant(
        "every_field_checked", "HP4", setting(read, "form_problems", _every_field_checked), ("another_field",)
    ),
    Mutant(
        "every_section_specimen_checked",
        "HP4",
        setting(read, "form_problems", _every_section_checked),
        ("another_section_specimen",),
    ),
    Mutant(
        "section_specimen_unchecked",
        "HP4 refusal",
        taken("section_specimen_unchecked"),
        ("own_section_specimen",),
    ),
    Mutant(
        "hash_over_members_as_written",
        "HP10",
        setting(canonical, "_utf16_units", _members_as_written),
        strategies.REWRITTEN_KINDS,
    ),
    Mutant(
        "integers_read_as_integers",
        "HP10",
        setting(jsonio, "_double", _integers_as_integers),
        strategies.REWRITTEN_KINDS,
    ),
]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_invariance_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    mutant.inject(monkeypatch)
    examples, check, shown = KILLERS[mutant.killer]
    tried, example = kill(examples(size), check)
    record_property("examples_to_kill", tried)
    assert shown(example) in mutant.dies_at, shown(example)

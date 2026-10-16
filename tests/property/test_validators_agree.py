# SPDX-License-Identifier: Apache-2.0
"""jsonschema-rs (`tests/verdicts.py`) and python-jsonschema, two independent implementations of JSON Schema,
give the same verdict:
- on T1's inputs (`tests/spec_sync/test_t1.py`): each example's field against the writer schema and the reader
  `$defs`, by its form's definition and by `value_field`, its section's specimen against both, and the field
  against its row's binding (`vocabulary/fields.json`); every example at `deep`, and a fixed share at `dev`
  and `ci`;
- on drawn value fields and record bodies, and on the base and the faulty field of each writer fault family
  (`tests/property/value_fields.py`), as many as the profile gives a property.
A disagreement fails whichever side is right. Controls: one side given a writer mutant, and both sides given a
`pattern` the two regex dialects read differently, must each make the check fail.
"""

import copy
from collections.abc import Callable, Iterable, Iterator
from functools import cache
from typing import NamedTuple
from urllib.parse import urljoin

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator

from materica.core.jsonio import JsonValue
from tests.conftest import PROFILE
from tests.property import value_fields
from tests.property.support import feature
from tests.property.test_writer_mutants import MUTANTS, ORIGINALS, WRITER_FILE, identifier, kill, setting
from tests.property.test_writer_properties import BODY, VALUE_FIELD
from tests.property.value_fields import FAMILIES, Faulty, Json
from tests.spec_sync import test_t1 as t1
from tests.spec_sync.schemas import BASE, registry
from tests.verdicts import verdict

Verdict = Callable[[JsonValue], bool]


class Pair(NamedTuple):
    """One schema's verdicts, by each implementation."""

    rust: Verdict
    python: Verdict


def python_verdict(schema: Json, files: Iterable[Json] = ()) -> Verdict:
    checker = Draft202012Validator(schema, registry=registry(files))

    def takes(value: JsonValue) -> bool:
        # types-jsonschema types its second overload's instance as unknown.
        return checker.is_valid(value)  # pyright: ignore[reportUnknownMemberType]

    return takes


def pair(schema: Json, rust_files: Iterable[Json] = (), python_files: Iterable[Json] = ()) -> Pair:
    return Pair(verdict(schema, rust_files), python_verdict(schema, python_files))


def said(taken: bool) -> str:
    return "takes" if taken else "refuses"


def disagreement(both: Pair, value: JsonValue) -> str | None:
    rust, python = both.rust(value), both.python(value)
    return None if rust == python else f"jsonschema-rs {said(rust)}, python-jsonschema {said(python)}"


# T1's inputs.

T1_FILES = ("record.writer.json", "record.reader.json")


def t1_inputs(example: t1.Example) -> Iterator[tuple[str, JsonValue]]:
    """Each definition T1 validates a part of `example` against, as a reference relative to schema 0.1's, with
    that part."""
    for file in T1_FILES:
        for shape in sorted({t1.field_shape(example.value), "value_field"}):
            yield f"{file}#/$defs/{shape}", example.value
        if "specimen" in example.section:
            yield f"{file}#/$defs/specimen", example.section["specimen"]
    yield f"vocabulary/fields.json#/$defs/{example.field}", example.value


def t1_disagreements(
    examples: list[t1.Example], rust_files: Iterable[Json] = (), python_files: Iterable[Json] = ()
) -> Iterator[str]:
    rust_files, python_files = tuple(rust_files), tuple(python_files)
    pairs: dict[str, Pair] = {}
    for example in examples:
        for reference, value in t1_inputs(example):
            if reference not in pairs:
                pairs[reference] = pair({"$ref": urljoin(BASE, reference)}, rust_files, python_files)
            found = disagreement(pairs[reference], value)
            if found is not None:
                yield f"{example.name}, {reference}: {found}"


# A whole pass over T1's examples, 5,066 of them, took 590 s summed over 8 workers of a shared machine, 110 s
# of wall time, nearly all of it python-jsonschema's: every STRIDE-th one, a tenth, 60 to 80 s (2026-10-16).
# The share takes them in turn through the bases and their changes, so that it holds each; a disagreement the
# share misses is left to `deep`, weekly.
STRIDE = 1 if PROFILE == "deep" else 10
PARTS = 12


@cache
def t1_share() -> list[t1.Example]:
    return t1.all_examples()[::STRIDE]


@pytest.mark.parametrize("part", range(PARTS))
def test_both_give_one_verdict_on_t1s_inputs(part: int) -> None:
    assert list(t1_disagreements(t1_share()[part::PARTS])) == []


def test_t1s_share_holds_both_verdicts() -> None:
    """A share that each schema took whole, or refused whole, could not tell the two apart."""
    for file in T1_FILES:
        takes = verdict(urljoin(BASE, f"{file}#/$defs/value_field"))
        taken = sum(takes(example.value) for example in t1_share())
        assert 0 < taken < len(t1_share()), file


# Drawn fields, bodies and faults.

FIELDS = pair(VALUE_FIELD)
BODIES = pair(BODY)
# Where each family's faults are judged: a binding's in a body, the others' in a value field.
PLACES = {"binding": BODIES}
FAULTY = {family: value_fields.faulty_fields(family) for family in FAMILIES}


@given(value_fields.fields())
def test_both_give_one_verdict_on_drawn_fields(field: JsonValue) -> None:
    assert disagreement(FIELDS, field) is None, disagreement(FIELDS, field)


@given(value_fields.bodies())
def test_both_give_one_verdict_on_drawn_bodies(body: Json) -> None:
    assert disagreement(BODIES, body) is None, disagreement(BODIES, body)


def check_agree(both: Pair, faulty: Faulty) -> None:
    for name, value in (("its base", faulty.base), (f"{faulty.fault} at {faulty.place}", faulty.field)):
        found = disagreement(both, value)
        assert found is None, f"{name}: {found}"


@pytest.mark.drawn(*FAMILIES)
@given(data=st.data())
def test_both_give_one_verdict_on_each_fault_familys_fields(data: st.DataObject) -> None:
    family = data.draw(st.sampled_from(FAMILIES))
    feature(family)
    check_agree(PLACES.get(family, FIELDS), data.draw(FAULTY[family]))


# Controls. A writer mutant of the table (`test_writer_mutants.py`) given to one side alone: M18, provenance
# that requires none of its members, which changes the writer's verdict on 70 of T1's examples, 10 of them in
# the share (2026-10-16); and M55, an anatomical site of any text, searched among the fault its family's
# property must kill it at.


def mutant(name: str) -> Json:
    (found,) = [candidate for candidate in MUTANTS if identifier(candidate) == name]
    schema = copy.deepcopy(ORIGINALS[found.file])
    found.change(schema)
    return schema


# Both mutants loosen the schema, so the side given one takes what the other refuses.
LOOSER = {
    "rust": "jsonschema-rs takes, python-jsonschema refuses",
    "python": "jsonschema-rs refuses, python-jsonschema takes",
}


@pytest.mark.parametrize("side", LOOSER)
def test_one_side_given_a_writer_mutant_disagrees_on_t1s_inputs(side: str) -> None:
    """To the first disagreement, over the examples the check above takes at this profile."""
    files = {side: (mutant("M18"),)}
    found = next(t1_disagreements(t1_share(), files.get("rust", ()), files.get("python", ())), None)
    assert found is not None
    assert found.endswith(LOOSER[side]), found


@pytest.mark.parametrize("side", LOOSER)
def test_one_side_given_a_writer_mutant_disagrees_on_drawn_faults(side: str) -> None:
    files = {side: (mutant("M55"),)}
    both = pair(VALUE_FIELD, files.get("rust", ()), files.get("python", ()))
    _, message = kill(
        value_fields.faulty_fields("specimen", only=("uberon_malformed",)),
        lambda faulty: check_agree(both, faulty),
    )
    assert "uberon_malformed at" in message, message
    assert LOOSER[side] in message, message


def test_a_pattern_the_two_dialects_read_differently_disagrees() -> None:
    """Python's `$` matches before a final newline as well as at the end; ECMA-262's, and jsonschema-rs's,
    only at the end. So the package's patterns end in `(?![\\s\\S])`, which both read alike. Ended in `$`, the
    anatomical site's pattern, given to both sides, takes `UBERON:1\\n` in python-jsonschema alone: a fault
    the specimen family draws."""
    writer = copy.deepcopy(ORIGINALS[WRITER_FILE])
    dollar_ended: JsonValue = {"type": "string", "pattern": "^UBERON:[0-9]+$"}
    setting("$defs", "anatomical_site", "properties", "uberon", to=dollar_ended)(writer)
    both = pair(VALUE_FIELD, (writer,), (writer,))
    _, message = kill(
        value_fields.faulty_fields("specimen", only=("uberon_malformed",)),
        lambda faulty: check_agree(both, faulty),
    )
    assert "uberon_malformed at" in message, message
    assert "jsonschema-rs refuses, python-jsonschema takes" in message, message

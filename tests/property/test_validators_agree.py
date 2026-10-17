# SPDX-License-Identifier: Apache-2.0
"""jsonschema-rs (`tests/verdicts.py`) and python-jsonschema, two independent implementations of JSON Schema,
give the same verdict:
- on T1's inputs (`tests/spec_sync/test_t1.py`): each example's field against the writer schema and the reader
  `$defs`, by its form's definition and by `value_field`, its section's specimen against both, and the field
  against its row's binding (`vocabulary/fields.json`); every example at `deep`, and a share that holds each
  kind of example at `dev` and `ci`;
- on drawn value fields, against the writer's and the reader's `value_field`; drawn record bodies, against the
  writer's; drawn records changed near each boundary of the envelope, and every conformance input, against
  the reader schema; and the base and the faulty field of each writer fault family, against both value
  fields (`tests/property/value_fields.py`, `records.py`), as many as the profile gives a property;
- along each writer mutant's own search (`test_writer_mutants.py`), up to the example at which the mutant's
  verdict first differs from the package's.
A disagreement fails whichever side is right. Controls: one side given a writer mutant or a reader mutant, and
both sides given a `pattern` the two regex dialects read differently, must each make the check fail.
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

from materica.core import jsonio
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from tests.conformance.runner import CONFORMANCE
from tests.conftest import PROFILE
from tests.property import records, value_fields
from tests.property.records import Envelope
from tests.property.strategies import ORIGINAL, SIZE, SMALL, Size
from tests.property.support import feature
from tests.property.test_writer_mutants import (
    MUTANTS,
    ORIGINALS,
    SEARCHED_ON,
    TAKES,
    WRITER_FILE,
    WriterMutant,
    deleting,
    identifier,
    kill,
    setting,
)
from tests.property.test_writer_properties import BODY, VALUE_FIELD
from tests.property.value_fields import FAMILIES, Faulty, Json
from tests.spec_sync import test_t1 as t1
from tests.spec_sync.schemas import BASE, Disagreement, registry
from tests.verdicts import DOCUMENTS, verdict

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


# A whole pass over T1's examples, 5,066 of them, took 590 s and 760 s summed over 8 workers of a shared
# machine, nearly all of it python-jsonschema's (2026-10-16). At `dev` and `ci` the share takes every
# STRIDE-th example of each group, from its first: the inputs that read each registered field, and the
# variants of each base by each change and origin. So it holds each registered field the inputs read, each
# base, each origin and each change, alone and beside each origin, which `share_misses` checks: T1's order
# cycles through the origins in a period of five, and a plain stride of 10 through all of T1 held none of the
# 117 variants that set `measured_by_source`. A disagreement the share misses is left to `deep`, weekly.
STRIDE = 1 if PROFILE == "deep" else 10
PARTS = 12


def t1_group(example: t1.Example) -> tuple[str, str, str]:
    """An input example's registered field, or a variant's base, change and origin."""
    return (example.base, example.change, example.origin) if example.change else (example.field, "", "")


@cache
def t1_share() -> list[t1.Example]:
    groups: dict[tuple[str, str, str], list[t1.Example]] = {}
    for example in t1.all_examples():
        groups.setdefault(t1_group(example), []).append(example)
    return [example for group in groups.values() for example in group[::STRIDE]]


# The kinds of T1's examples a share must hold one of each, as the comment above names them.
KINDS: dict[str, Callable[[t1.Example], object]] = {
    "registered field of an input": lambda example: "" if example.change else example.field,
    "base": lambda example: example.base,
    "origin": lambda example: example.origin,
    "change": lambda example: example.change,
    "change beside an origin": lambda example: (example.change, example.origin) if example.change else "",
}


def kinds(examples: Iterable[t1.Example]) -> set[tuple[str, object]]:
    return {(name, of(example)) for example in examples for name, of in KINDS.items()} - {
        (name, "") for name in KINDS
    }


def share_misses(share: Iterable[t1.Example]) -> list[str]:
    """Each kind of T1's examples, by `KINDS`, that `share` holds no example of."""
    return sorted(f"{name} {value}" for name, value in kinds(t1.all_examples()) - kinds(share))


@pytest.mark.parametrize("part", range(PARTS))
def test_both_give_one_verdict_on_t1s_inputs(part: int) -> None:
    assert list(t1_disagreements(t1_share()[part::PARTS])) == []


def test_t1s_share_holds_each_kind_of_example() -> None:
    assert share_misses(t1_share()) == []


def test_a_share_that_strides_through_t1s_order_misses_an_origin() -> None:
    """The control: every tenth example of T1 in its order, the share before it was taken by group."""
    assert "origin measured_by_source" in share_misses(t1.all_examples()[::10])


def test_t1s_share_holds_both_verdicts() -> None:
    """A share that each schema took whole, or refused whole, could not tell the two apart."""
    for file in T1_FILES:
        takes = verdict(urljoin(BASE, f"{file}#/$defs/value_field"))
        taken = sum(takes(example.value) for example in t1_share())
        assert 0 < taken < len(t1_share()), file


# Drawn fields, bodies, records and faults.

READER_FIELD: Json = {"$ref": urljoin(BASE, "record.reader.json#/$defs/value_field")}
READER_ID = urljoin(BASE, "record.reader.json")
RECORD: Json = {"$ref": READER_ID}


def places(rust_files: Iterable[Json] = (), python_files: Iterable[Json] = ()) -> dict[str, Pair]:
    """Each place drawn inputs are judged at, by both libraries, with each side's files in place of the
    package's file of their `$id`: the writer's value field and record body, the reader's value field, and
    the reader schema, which judges a record's envelope."""
    rust_files, python_files = tuple(rust_files), tuple(python_files)
    schemas = {"writer field": VALUE_FIELD, "reader field": READER_FIELD, "body": BODY, "record": RECORD}
    return {name: pair(schema, rust_files, python_files) for name, schema in schemas.items()}


PLACES = places()
FAULTY = {family: value_fields.faulty_fields(family) for family in FAMILIES}


def placed_at(family: str) -> tuple[str, ...]:
    """Where a family's faults are judged: a binding's in a body, the others' in a value field, by the
    writer and by the reader."""
    return ("body",) if family == "binding" else ("writer field", "reader field")


def faulty_values(faulty: Faulty) -> list[tuple[str, JsonValue]]:
    return [("its base", faulty.base), (f"{faulty.fault} at {faulty.place}", faulty.field)]


def check_agree(pairs: dict[str, Pair], at: Iterable[str], values: Iterable[tuple[str, JsonValue]]) -> None:
    for name, value in values:
        for place in at:
            found = disagreement(pairs[place], value)
            assert found is None, f"{name}, by the {place}: {found}"


@given(value_fields.fields())
def test_both_give_one_verdict_on_drawn_fields(field: JsonValue) -> None:
    check_agree(PLACES, ("writer field", "reader field"), [("the field", field)])


@given(value_fields.bodies())
def test_both_give_one_verdict_on_drawn_bodies(body: Json) -> None:
    check_agree(PLACES, ("body",), [("the body", body)])


@given(records.sweeps())
def test_both_give_one_verdict_on_drawn_records(envelopes: list[Envelope]) -> None:
    """The records the envelope property draws (`test_envelope_properties.py`), changed near each boundary."""
    check_agree(
        PLACES, ("record",), [(f"changed by {envelope.changes}", envelope.record) for envelope in envelopes]
    )


@pytest.mark.drawn(*FAMILIES)
@given(data=st.data())
def test_both_give_one_verdict_on_each_fault_familys_fields(data: st.DataObject) -> None:
    family = data.draw(st.sampled_from(FAMILIES))
    feature(family)
    check_agree(PLACES, placed_at(family), faulty_values(data.draw(FAULTY[family])))


def test_both_give_one_verdict_on_the_conformance_inputs() -> None:
    """Every conformance input that parses, as the envelope test judges it (`test_envelope.py`)."""
    inputs = sorted(CONFORMANCE.glob("*/inputs/*"))
    parsed = {f"{path.parent.parent.name}/{path.name}": jsonio.parse(path.read_bytes()) for path in inputs}
    check_agree(
        PLACES,
        ("record",),
        [(name, value) for name, value in parsed.items() if not isinstance(value, Reason)],
    )


# Along each writer mutant's search. The drawn faults meet each fault a few times a run at most, since
# Hypothesis shows one draw in several examples (`audits.CLUSTER`), so a difference of the reach of one writer
# mutant (`test_writer_mutants.py`), on one side alone, is met by chance: before this check, 12 of the 89
# mutants changed no verdict the test took in at least one of five samples, M35 in all five (2026-10-17). So
# each mutant's own search, as its table runs it, derandomized, is compared on the package's schema, both
# libraries at each example, up to the first example at which the mutant's verdict differs from the
# package's: there, a difference of that mutant's reach on either side would show.


def mutated(mutant: WriterMutant) -> Json:
    schema = copy.deepcopy(ORIGINALS[mutant.file])
    mutant.change(schema)
    return schema


def along(
    mutant: WriterMutant, size: Size, rust_files: Iterable[Json] = (), python_files: Iterable[Json] = ()
) -> int:
    """The examples of `mutant`'s search compared, with each side's files, up to the one at which the
    mutant's verdict first differs from the package's; a Disagreement at the first that the sides judge
    differently."""
    plan = SEARCHED_ON[identifier(mutant)] if mutant.killer == TAKES else None
    registered = plan is not None and plan.registered is not None
    place = BODY if registered or mutant.killer == "binding" else VALUE_FIELD
    both, package, changed = (
        pair(place, rust_files, python_files),
        verdict(place),
        verdict(place, [mutated(mutant)]),
    )

    def compare(values: list[tuple[str, JsonValue]]) -> None:
        for name, value in values:
            found = disagreement(both, value)
            if found is not None:
                raise Disagreement(f"{identifier(mutant)}'s search, {name}: {found}")
        assert all(changed(value) == package(value) for _, value in values)

    if plan is None:
        faulty = value_fields.faulty_fields(mutant.killer, size, mutant.intended)
        tried, _ = kill(faulty, lambda drawn: compare(faulty_values(drawn)))
    else:
        fields = value_fields.bodies(plan, size) if registered else value_fields.form_fields(plan, size)
        tried, _ = kill(fields, lambda field: compare([("the field", field)]))
    return tried


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[identifier(mutant) for mutant in MUTANTS])
def test_both_give_one_verdict_along_each_writer_mutants_search(mutant: WriterMutant, size: Size) -> None:
    along(mutant, size)


# Controls. A writer mutant of the table given to one side alone: M18, provenance that requires none of its
# members, on T1's share; M55, an anatomical site of any text, searched among the fault its family's property
# must kill it at; and each of the 12 mutants the drawn faults missed, along its own search. A reader mutant
# given to one side: the reader's derivation required of origin `derived` no longer, on drawn faults; and a
# record's `id` of any text, on drawn records.


def mutant_named(name: str) -> WriterMutant:
    (found,) = [candidate for candidate in MUTANTS if identifier(candidate) == name]
    return found


def mutant(name: str) -> Json:
    return mutated(mutant_named(name))


def reader_with(change: Callable[[Json], None]) -> Json:
    reader = copy.deepcopy(DOCUMENTS[READER_ID])
    change(reader)
    return reader


# Each mutant loosens the schema, so the side given one takes what the other refuses.
LOOSER = {
    "rust": "jsonschema-rs takes, python-jsonschema refuses",
    "python": "jsonschema-rs refuses, python-jsonschema takes",
}


def sides(side: str, files: Iterable[Json]) -> tuple[tuple[Json, ...], tuple[Json, ...]]:
    """`files` given to `side` alone: the rust side's files, then the python side's."""
    files = tuple(files)
    return (files, ()) if side == "rust" else ((), files)


@pytest.mark.parametrize("side", LOOSER)
def test_one_side_given_a_writer_mutant_disagrees_on_t1s_inputs(side: str) -> None:
    """To the first disagreement, over the examples the check above takes at this profile."""
    found = next(t1_disagreements(t1_share(), *sides(side, [mutant("M18")])), None)
    assert found is not None
    assert found.endswith(LOOSER[side]), found


@pytest.mark.parametrize("side", LOOSER)
def test_one_side_given_a_writer_mutant_disagrees_on_drawn_faults(side: str) -> None:
    pairs = places(*sides(side, [mutant("M55")]))
    _, message = kill(
        value_fields.faulty_fields("specimen", only=("uberon_malformed",)),
        lambda faulty: check_agree(pairs, placed_at("specimen"), faulty_values(faulty)),
    )
    assert "uberon_malformed at" in message, message
    assert LOOSER[side] in message, message


MISSED = ("M6b", "M9", "M10", "M22", "M27", "M29", "M35", "M42", "M50", "M52", "M53", "B12")


@pytest.mark.parametrize("side", LOOSER)
@pytest.mark.parametrize("name", MISSED)
def test_one_side_given_a_writer_mutant_disagrees_along_its_search(name: str, side: str) -> None:
    with pytest.raises(Disagreement, match=LOOSER[side]):
        along(mutant_named(name), SIZE, *sides(side, [mutant(name)]))


@pytest.mark.parametrize("side", LOOSER)
def test_one_side_given_a_reader_mutant_disagrees_on_drawn_faults(side: str) -> None:
    unrequired = reader_with(deleting("$defs", "provenance", "allOf", 1))
    pairs = places(*sides(side, [unrequired]))
    _, message = kill(
        value_fields.faulty_fields("provenance", only=("derivation_missing",)),
        lambda faulty: check_agree(pairs, ("reader field",), faulty_values(faulty)),
    )
    assert "derivation_missing at" in message, message
    assert LOOSER[side] in message, message


@pytest.mark.parametrize("side", LOOSER)
def test_one_side_given_a_reader_mutant_disagrees_on_drawn_records(side: str) -> None:
    any_text = reader_with(setting("properties", "id", to={"type": "string"}))
    pairs = places(*sides(side, [any_text]))
    _, message = kill(
        records.sweeps(),
        lambda envelopes: check_agree(
            pairs,
            ("record",),
            [(f"changed by {envelope.changes}", envelope.record) for envelope in envelopes],
        ),
    )
    assert LOOSER[side] in message, message


def test_a_pattern_the_two_dialects_read_differently_disagrees() -> None:
    """Python's `$` matches before a final newline as well as at the end; ECMA-262's, and jsonschema-rs's,
    only at the end. So the package's patterns end in `(?![\\s\\S])`, which both read alike. Ended in `$`, the
    anatomical site's pattern, given to both sides, takes `UBERON:1\\n` in python-jsonschema alone: a fault
    the specimen family draws."""
    writer = copy.deepcopy(ORIGINALS[WRITER_FILE])
    dollar_ended: JsonValue = {"type": "string", "pattern": "^UBERON:[0-9]+$"}
    setting("$defs", "anatomical_site", "properties", "uberon", to=dollar_ended)(writer)
    pairs = places((writer,), (writer,))
    _, message = kill(
        value_fields.faulty_fields("specimen", only=("uberon_malformed",)),
        lambda faulty: check_agree(pairs, placed_at("specimen"), faulty_values(faulty)),
    )
    assert "uberon_malformed at" in message, message
    assert "jsonschema-rs refuses, python-jsonschema takes" in message, message

# SPDX-License-Identifier: Apache-2.0
# Atheris installs on Python 3.12 to 3.14 only; elsewhere its stub in typings/ stands in for it.
# pyright: reportMissingModuleSource=false
"""Fuzz target 5: raw bytes as one entry of a request's `acceptances` (`declarations.md` section 4.1;
`read_side_contract.md` sections 1 to 3 and 5), the S3 design's target 4, `read_acceptance_bytes`.

    python -m tests.fuzz.read_acceptance_bytes --seed CORPUS     # copy the seed corpus into CORPUS
    python -m tests.fuzz.read_acceptance_bytes --dict FILE       # write the dictionary of acceptances
    python -m tests.fuzz.read_acceptance_bytes CORPUS -dict=FILE [libFuzzer options]

`jsonio.parse` reads the bytes, which stand as the one entry of the acceptances of fixed requests: two tables
of the conformance inputs read at the places `acceptance_oracle.PLACES` names, outside their readable ranges,
at and beyond an edge, inside, and under `want: bounds`. Each request is read twice. The target fails when a
read raises anything but `NotImplementedError` (a pick and an overlay, which S4 reads, and a `trainable`
acceptance, which S7a-4 reads), when two reads differ, when an extrapolation that breaks its shape is not
refused (`acceptance_oracle.check_shape_refused`), when a result breaks HP1 and HP2 as an acceptance leaves
them, an extrapolation's `assumption` its entry's own (`acceptance_oracle.check_acceptance_laws`), or holds
`table` other than beside its value (`field_oracle.check_table_member`), when the status is better than the
same read without the entry (`acceptance_oracle.check_no_better`), or when the reference model
(`tests/reference/read_model.py`) and the read disagree but as HP12 lists
(`field_oracle.check_against_the_model`). The seeds are every acceptance of every conformance case's request,
its extrapolations located at the two records the target reads among them.
"""

import importlib
import json
import sys
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import atheris

# Imported first, and inside this block, so that Atheris instruments the core for its coverage.
with atheris.instrument_imports(include=["materica"]):
    from materica.core import jsonio
    from materica.core.read import ReadResult, read
    from materica.core.record import RecordStore

from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite

# The Hypothesis profiles, as under pytest: HP12's check, which the oracle takes, imports the property tests'
# strategies, whose sizes come from the profile.
importlib.import_module("tests.conftest")

from tests.fuzz import seeded_fault  # noqa: E402
from tests.fuzz.acceptance_oracle import (  # noqa: E402
    FIELD,
    INPUTS,
    PLACES,
    RECORDS,
    Place,
    check_acceptance_laws,
    check_no_better,
    check_shape_refused,
    record_of,
    request_at,
)
from tests.fuzz.field_oracle import check_against_the_model, check_table_member, read_outcome  # noqa: E402

PACKAGE = Path(jsonio.__file__).parents[1]
CASES = PACKAGE / "data" / "conformance" / "plain_read" / "cases"
WITH_HASH: frozenset[Suite] = frozenset({"plain_read", "hash"})
SOURCES = tuple((INPUTS / name).read_bytes() for name in RECORDS)
STORE = RecordStore()
for name, data in zip(RECORDS, SOURCES, strict=True):
    STORE.add(name, data)


def field_of(name: str) -> JsonValue:
    """The density field the record `name` holds."""
    found: JsonValue = record_of(name)
    for step in ("body", "sections", "bulk", "fields", "density"):
        assert isinstance(found, dict), found
        found = found[step]
    return found


FIELDS = {name: field_of(name) for name in RECORDS}


def read_json(request: dict[str, JsonValue]) -> JsonValue:
    """The result as a consumer receives it, or "not yet" where a step not built yet would decide it."""
    try:
        result: ReadResult = read(request, STORE, claims=WITH_HASH)
    except NotImplementedError:
        return "not yet"
    written: JsonValue = json.loads(json.dumps(result.to_json()))
    return written


# Each place's read without an acceptance, the same for every input.
WITHOUT = {place: read_json(request_at(place, [])) for place in PLACES}


def check_place(place: Place, entry: JsonValue) -> None:
    request = request_at(place, [entry])
    first, outcome = read_outcome(partial(read, request, STORE, claims=WITH_HASH))
    assert read_json(request) == first, "two reads differ"
    check_shape_refused(first, entry)
    check_acceptance_laws(first, entry)
    check_table_member(FIELDS[place.record], first)
    check_no_better(first, WITHOUT[place])
    check_against_the_model(SOURCES, request, WITH_HASH, outcome)


def test_one_input(data: bytes) -> None:
    entry = jsonio.parse(data)
    if isinstance(entry, Reason):
        return
    for place in PLACES:
        check_place(place, entry)


# The seeds, and the dictionary.


def seeds() -> Iterator[tuple[str, bytes]]:
    """Every acceptance of every conformance case's request, each once."""
    seen: set[bytes] = set()
    for path in sorted(CASES.glob("*.json")):
        case: JsonValue = json.loads(path.read_text(encoding="utf-8"))
        request = case.get("request") if isinstance(case, dict) else None
        acceptances = request.get("acceptances") if isinstance(request, dict) else None
        entries: list[JsonValue] = acceptances if isinstance(acceptances, list) else []
        for index, entry in enumerate(entries):
            data = json.dumps(entry).encode()
            if data not in seen:
                seen.add(data)
                yield f"{path.stem}-{index}", data


def seed_corpus(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in seeds():
        (directory / name).write_bytes(data)


def dictionary() -> Iterator[str]:
    """JSON's structure; the names an acceptance's place holds and the kinds of acceptance; an extrapolation's
    methods; the registered fields and conditions; and the two records' references."""
    yield from ('"{"', '"}"', '"["', '"]"', '":"', '","', '"null"', '"true"', '"false"', '"-0"', '"1e308"')
    names = {
        "acceptance",
        "record",
        "region",
        "interval",
        "field",
        "reason",
        "basis",
        "method",
        "law",
        "value",
        "params",
        "fact",
        "token",
        "implies",
        "index",
        "overlay",
        "id",
        "version",
        "content_hash",
        "unit",
        "range",
        *VOCABULARY.acceptance_kinds,
        *VOCABULARY.token_lists["extrapolation_method"],
        *VOCABULARY.fields,
        *VOCABULARY.conditions,
        FIELD,
    }
    for name in RECORDS:
        record = record_of(name)
        names |= {str(record["id"]), str(record["version"]), str(record["content_hash"])}
    for name in sorted(names):
        yield json.dumps(json.dumps(name))


def main(arguments: list[str]) -> None:
    if arguments[1:2] == ["--seed"]:
        seed_corpus(Path(arguments[2]))
        return
    if arguments[1:2] == ["--dict"]:
        Path(arguments[2]).write_text("\n".join(dictionary()) + "\n", encoding="utf-8")
        return
    seeded_fault.seed_extrapolation_method_if_asked(atheris.instrument_func)
    atheris.Setup(arguments, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main(sys.argv)

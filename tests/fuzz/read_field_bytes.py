# SPDX-License-Identifier: Apache-2.0
# Atheris installs on Python 3.12 to 3.14 only; elsewhere its stub in typings/ stands in for it.
# pyright: reportMissingModuleSource=false
"""Fuzz target 4: raw bytes into steps 7 to 13 of a read (`read_side_contract.md` section 3), the S2 design's
`read_field_bytes`.

    python -m tests.fuzz.read_field_bytes --seed CORPUS     # copy the seed corpus into CORPUS
    python -m tests.fuzz.read_field_bytes --dict FILE       # write the dictionary of S2's names and tokens
    python -m tests.fuzz.read_field_bytes CORPUS -dict=FILE [libFuzzer options]

The first byte picks a registered field, and `jsonio.parse` reads the rest, which stands in that field's place
in a record that is valid otherwise; the record's hash is recomputed and pinned. Each input is read with each
`want` of plain read, at operating conditions with a tolerance or an accept list for each condition the
field's row requires, twice, and once more without the hash suite. The target fails when a read raises
anything but `NotImplementedError`, when two reads of one request differ, when a result is other than steps 7
to 13 give (every code one of them gives, and HP1 and HP2: each code and condition once, `condition` where
section 2 item 2 puts it, the status the worst of the codes', and the members present as item 6 says), when
the read without the hash suite differs from the read with it by more than the label `hash_not_checked`, when
the read under `want: value`, the `want` every step decides under, and the reference model disagree but as
HP12 lists (a refusal step 8 misses or gives wrongly among them: held under every `want`, the model's read
slowed the target so that the control's seeded fault went unfound in five local runs of six, where under
`want: value` alone it is found as often as without the model), when step 8 lets through a constant its row
allows that the reader `$defs` refuse (T1's third relation, but for one divergence of the `$defs` that
`field_oracle.py` names), or when steps 9 and 10 read such a constant otherwise than their text, its units by
code point and its conditions by HP7's oracle (`field_oracle.py`). `NotImplementedError` is a step not built
yet: its form's own member waits for S2b or S3, or it holds alternatives beyond what S4's decision 12 lets S2
read. The seeds are every value field of every conformance input.
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

from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.vocabulary import STATUS_TOKENS, VOCABULARY
from materica.shapes import Suite

# The Hypothesis profiles, as under pytest: HP12's check, which the oracle takes, imports the property tests'
# strategies, whose sizes come from the profile.
importlib.import_module("tests.conftest")

from tests.fuzz import seeded_fault  # noqa: E402
from tests.fuzz.field_oracle import (  # noqa: E402
    OPERATING,
    REQUIRED,
    check_against_the_model,
    check_no_refusal_missing,
    check_result_laws,
    check_steps_9_and_10,
    objects,
    read_outcome,
)

PACKAGE = Path(jsonio.__file__).parents[1]
CONFORMANCE = PACKAGE / "data" / "conformance"
REASONS = json.loads((PACKAGE / "schema" / "0.1" / "vocabulary" / "reasons.json").read_text(encoding="utf-8"))
JsonObject = dict[str, JsonValue]
# The codes of the steps built that a read of a field gives: 7, finding it, to 13, its value by `want`.
BUILT_CODES = frozenset(
    code for code, row in REASONS["reasons"].items() if set(range(7, 14)) & set(row.get("steps", []))
)
FIELDS = sorted(VOCABULARY.fields)
WANTS = ("value", "bounds", "components", "evidence")


def record_holding(field_name: str, field: JsonValue) -> JsonObject:
    section, _, name = field_name.partition(".")
    record: JsonObject = {
        "schema_version": "0.1.0",
        "record_type": "material",
        "id": "conformance/fuzz_fixture",
        "version": "1.0.0",
        "name": "A value field from the fuzzer",
        "licence": {"values": "CC0-1.0", "evidence": "excluded"},
        "content_hash": "",
        "body": {"sections": {section: {"fields": {name: field}}}},
    }
    record["content_hash"] = content_hash(record)
    return record


WITH_HASH: frozenset[Suite] = frozenset({"plain_read", "hash"})
WITHOUT_HASH: frozenset[Suite] = frozenset({"plain_read"})


def read_json(request: JsonObject, store: RecordStore, claims: frozenset[Suite]) -> JsonValue:
    """The result as a consumer receives it, or "not yet" where a step not built yet would decide it."""
    try:
        result: ReadResult = read(request, store, claims=claims)
    except NotImplementedError:
        return "not yet"
    written: JsonValue = json.loads(json.dumps(result.to_json()))
    return written


def check_result(result: JsonValue) -> None:
    """HP1 and HP2 (`field_oracle.check_result_laws`), every code one the steps built give."""
    check_result_laws(result)
    if result == "not yet":
        return
    codes = {str(reason.get("code")) for reason in objects(result, "reasons")}
    assert codes <= BUILT_CODES, f"codes steps 7 to 13 do not give: {sorted(codes - BUILT_CODES)}"


def without_hash_label(result: JsonValue) -> JsonValue:
    labels = result.get("labels") if isinstance(result, dict) else None
    if isinstance(result, dict) and isinstance(labels, list):
        return {**result, "labels": [label for label in labels if label != "hash_not_checked"]}
    return result


def test_one_input(data: bytes) -> None:
    if not data:
        return
    field_name = FIELDS[data[0] % len(FIELDS)]
    field = jsonio.parse(data[1:])
    if isinstance(field, Reason):
        return
    record = record_holding(field_name, field)
    data = json.dumps(record).encode()
    store = RecordStore()
    store.add("record", data)
    pin = {member: record[member] for member in ("id", "version", "content_hash")}
    requires = VOCABULARY.fields[field_name].requires
    operating = {name: value for name, value in OPERATING.items() if name in requires}
    required = {name: value for name, value in REQUIRED.items() if name in requires}
    for want in WANTS:
        request: JsonObject = {
            "target": {"record": pin, "field": field_name},
            "operating_conditions": dict(operating),
            "requirement": {"want": want, "conditions": dict(required)},
        }
        first, outcome = read_outcome(partial(read, request, store, claims=WITH_HASH))
        assert read_json(request, store, WITH_HASH) == first, "two reads differ"
        check_result(first)
        check_no_refusal_missing(field_name, field, first)
        check_steps_9_and_10(field_name, field, operating, required, first)
        if want == "value":
            check_against_the_model((data,), request, WITH_HASH, outcome)
        plain = read_json(request, store, WITHOUT_HASH)
        assert without_hash_label(plain) == first, "the hash suite changed more than its label"


# The seeds, and the dictionary.


def seeds() -> Iterator[tuple[str, bytes]]:
    """Every value field of every conformance input, the byte that picks its field before it."""
    for path in sorted(CONFORMANCE.glob("*/inputs/*")):
        value = jsonio.parse(path.read_bytes())
        body = value.get("body") if isinstance(value, dict) else None
        sections = body.get("sections") if isinstance(body, dict) else None
        for section_name, section in sections.items() if isinstance(sections, dict) else ():
            fields = section.get("fields") if isinstance(section, dict) else None
            for name, field in fields.items() if isinstance(fields, dict) else ():
                if f"{section_name}.{name}" in FIELDS:
                    index = FIELDS.index(f"{section_name}.{name}")
                    yield f"{path.stem}-{section_name}.{name}", bytes([index]) + json.dumps(field).encode()


def seed_corpus(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in seeds():
        (directory / name).write_bytes(data)


def dictionary() -> Iterator[str]:
    """JSON's structure, and every member name and token a value field of S2 holds: the members of the
    writer schema's value-field part, the vocabulary's tokens but the components, and the status tokens."""
    yield from ('"{"', '"}"', '"["', '"]"', '":"', '","', '"null"', '"true"', '"false"', '"-0"', '"1e308"')
    writer = json.loads((PACKAGE / "schema" / "0.1" / "record.writer.json").read_text(encoding="utf-8"))
    names: set[str] = set(STATUS_TOKENS) | set(VOCABULARY.conditions) | set(VOCABULARY.facts)
    for definition in writer["$defs"].values():
        names |= set(definition.get("properties", {}))
    for list_name, tokens in VOCABULARY.token_lists.items():
        if list_name not in ("component", "reason_code"):
            names |= set(tokens)
    for name in sorted(names):
        yield json.dumps(json.dumps(name))


def main(arguments: list[str]) -> None:
    if arguments[1:2] == ["--seed"]:
        seed_corpus(Path(arguments[2]))
        return
    if arguments[1:2] == ["--dict"]:
        Path(arguments[2]).write_text("\n".join(dictionary()) + "\n", encoding="utf-8")
        return
    seeded_fault.seed_step_10_if_asked(atheris.instrument_func)
    atheris.Setup(arguments, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main(sys.argv)

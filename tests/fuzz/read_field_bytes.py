# SPDX-License-Identifier: Apache-2.0
# Atheris installs on Python 3.12 to 3.14 only; elsewhere its stub in typings/ stands in for it.
# pyright: reportMissingModuleSource=false
"""Fuzz target 4: raw bytes into step 8 of a read (`read_side_contract.md` section 3), the S2 design's
`read_field_bytes`.

    python -m tests.fuzz.read_field_bytes --seed CORPUS     # copy the seed corpus into CORPUS
    python -m tests.fuzz.read_field_bytes --dict FILE       # write the dictionary of S2's names and tokens
    python -m tests.fuzz.read_field_bytes CORPUS -dict=FILE [libFuzzer options]

The first byte picks a registered field, and `jsonio.parse` reads the rest, which stands in that field's place
in a record that is valid otherwise; the record's hash is recomputed and pinned. Each input is read with each
`want` of plain read, twice, and once more without the hash suite. The target fails when a read raises
anything but `NotImplementedError`, when two reads of one request differ, when a result is other than a
refusal step 8 gives (`not_met`, every code one step 8 gives, each code and condition once, the status the
worst of the codes'), or when the read without the hash suite differs from the read with it by more than the
label `hash_not_checked`. `NotImplementedError` is a step not built yet: the field passed step 8, or its
form's own member waits for S2b or S3, or it holds alternatives. The seeds are every value field of every
conformance input.
"""

import json
import sys
from collections.abc import Iterator
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
from materica.core.status import worst
from materica.core.vocabulary import STATUS_TOKENS, VOCABULARY
from materica.shapes import Suite
from tests.fuzz import seeded_fault

PACKAGE = Path(jsonio.__file__).parents[1]
CONFORMANCE = PACKAGE / "data" / "conformance"
REASONS = json.loads((PACKAGE / "schema" / "0.1" / "vocabulary" / "reasons.json").read_text(encoding="utf-8"))
STEP_8_CODES = frozenset(code for code, row in REASONS["reasons"].items() if 8 in row.get("steps", []))
FIELDS = sorted(VOCABULARY.fields)
WANTS = ("value", "bounds", "components", "evidence")
JsonObject = dict[str, JsonValue]


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
    if result == "not yet":
        return
    assert isinstance(result, dict), result
    reasons = result["reasons"]
    assert isinstance(reasons, list), result
    assert reasons, f"step 8 gives a result only to refuse: {result}"
    keys = [(reason["code"], reason.get("condition")) for reason in reasons if isinstance(reason, dict)]
    assert len(set(keys)) == len(keys), f"a reason twice: {keys}"
    codes = {str(code) for code, _ in keys}
    assert codes <= STEP_8_CODES, f"codes step 8 does not give: {sorted(codes - STEP_8_CODES)}"
    assert result["status"] == worst(VOCABULARY.reasons[code].status for code in codes), result


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
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    pin = {member: record[member] for member in ("id", "version", "content_hash")}
    for want in WANTS:
        request: JsonObject = {"target": {"record": pin, "field": field_name}, "requirement": {"want": want}}
        first = read_json(request, store, WITH_HASH)
        assert read_json(request, store, WITH_HASH) == first, "two reads differ"
        check_result(first)
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
    seeded_fault.seed_step_8_if_asked(atheris.instrument_func)
    atheris.Setup(arguments, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main(sys.argv)

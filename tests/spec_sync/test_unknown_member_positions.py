# SPDX-License-Identifier: Apache-2.0
"""Every position where a member the reader does not know is ignored or refused
(`unknown_member_positions.json`), against the text, the schemas and the read.

- Each position quotes the sentence that decides it, which must stay in its document.
- The members named at a position are the schema's (the writer schema's for a record, `read_request.json`'s
  for a request), with any other member the text names there given with its reason. Every object definition a
  read reaches in a record has a position, and every member of one that may hold a status object a status
  position, but where a `deferred` position names the piece that will read it (a table, a request's pick,
  overlay or extrapolation): it fails once that piece is done. Every object in a host is found by a
  position's path. An implied condition's and a nominal's members are those the text
  names at each place, in `read_request.json`, in an implied condition's rows' `also` and in the read's
  tuples.
- At each position of a few valid records and a valid request, at every place the pattern finds, the read
  meets the verdict: a member named `x_unknown_member` is ignored, or refused where every unknown name is, or
  as the row of a status object says; a member one slip from each named member (the name with a character
  added) is refused where the verdict is `ignored` or `refused` and ignored where it is `condition_names` or
  `not_checked`; and a status object beside a member of the shape it stands for is refused. A refusal adds
  `form_invalid` (`request_incomplete` in a request) to what the host gave, and may take away a `withheld` or
  an `entries_withheld` the changed status object no longer gives.
- Every position is found in some host, so that no row is dead.

The hosts are the full fields and forms of `tests/property/full_fields.py`, each in a record with a section
specimen and extensions, read under the `want` its form gives, and a request for one of them; three of them
also hold a unit as a status object in a token condition, a field's, a section's and a derivation input's
fact, which the writer refuses. Each field host is read again with its field wrapped as the field's only
alternative, which reads as the field (`read_side_contract.md` section 3, step 7), so that every position at
a field's place is read inside an alternative too. A position that names a `form` is read in the hosts of
that form. A read that passes steps 8 and 9 goes on to steps 10 to 13, where a name `condition_names` leaves
to step 10 adds its `condition_unknown_name` and nothing else; one that raises `NotImplementedError`, a step
not built yet, has the outcome "past step 8".
"""

import copy
import json
import re
from collections.abc import Callable, Iterator
from functools import cache
from pathlib import Path
from typing import NamedTuple, cast

import pytest

from materica.core import fields, value_shapes
from materica.core import read as read_module
from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.record import RecordStore
from materica.core.status import ReadStatus, worst
from materica.core.vocabulary import VOCABULARY
from scripts.gen_vocabulary import SPECIFICATION
from tests.property.full_fields import SPECIMEN, full_fields, full_forms, record_of
from tests.spec_sync import status_rows
from tests.spec_sync.schemas import SCHEMA
from tests.spec_sync.test_case_steps import KNOWN, PIECES, STEPS

JsonObject = dict[str, JsonValue]
Path_ = tuple[str | int, ...]
TABLE_PATH = Path(__file__).with_name("unknown_member_positions.json")
SCHEMAS = {
    "record": json.loads((SCHEMA / "record.writer.json").read_text(encoding="utf-8")),
    "request": json.loads((SCHEMA / "read_request.json").read_text(encoding="utf-8")),
}
UNKNOWN = "x_unknown_member"
UNSTATED: JsonObject = {"status": "unstated"}
FIELD = "fluid.dynamic_viscosity"
# What a read of each form wants, so that it reaches step 13 (`read_side_contract.md` section 6).
WANT = {
    "constant": "value",
    "table": "value",
    "interval": "bounds",
    "composition": "components",
    "evidence": "evidence",
}
PAST_STEP_8 = "past step 8"
REFUSAL = {"record": "form_invalid", "request": "request_incomplete"}
# The one `unknown` reason step 8 gives (`read_side_contract.md` section 4), which a refusal there keeps
# beside it: some of an evidence list's entries withheld.
STEP_8_UNKNOWN = frozenset({"entries_withheld"})


def an_object(value: JsonValue) -> JsonObject:
    assert isinstance(value, dict)
    return value


def a_list(value: JsonValue) -> list[JsonValue]:
    assert isinstance(value, list)
    return value


def table(path: Path = TABLE_PATH) -> list[JsonObject]:
    loaded: JsonObject = json.loads(path.read_text(encoding="utf-8"))
    return [an_object(position) for position in a_list(loaded["positions"])]


TABLE = table()


class Outcome(NamedTuple):
    status: str
    codes: frozenset[str]
    conditions: bool = False  # step 10 ran to its end


# The hosts, and the read of one.


class Host(NamedTuple):
    name: str
    record: JsonObject
    request: JsonObject | None  # a request host's request, its target pinned to `record`
    field: str = FIELD  # the registered field read
    form: str = "constant"  # the form of the field read


def pin(record: JsonObject) -> JsonObject:
    return {member: record[member] for member in ("id", "version", "content_hash")}


@cache
def hosts() -> tuple[Host, ...]:
    """Each full field and form in a record with a section specimen and extensions; and a request for the
    first. A derivation input's fact holds its unit as a status object, a derived field's and a derived
    evidence report's."""
    found: list[Host] = []
    fields = {name: (FIELD, field) for name, field in full_fields().items()} | full_forms()
    for name, (registered, field) in fields.items():
        section_specimen = copy.deepcopy(SPECIMEN)
        if name == "statuses":
            # A condition's unit as a status object: the text allows one on a numeric condition
            # (`provenance.md` section 6.1 item 1) and on a token condition (step 9 refuses it), though the
            # writer binds a numeric condition's unit to the registered one and gives a token condition none.
            conditions = an_object(field["conditions"])
            conditions["measurement_dimension"] = {"value": 5.0e-5, "unit": UNSTATED, "basis": "stated"}
            conditions["measurement_geometry"] = {"token": "tube", "unit": UNSTATED, "basis": "stated"}
            # And a field's fact's unit, which the writer binds to its row's (maintainer, 2026-10-15).
            facts = an_object(field["specimen"])
            facts["post_mortem_interval"] = {"value": 60.0, "unit": UNSTATED, "basis": "stated"}
        if name == "measurement":
            section_specimen["donor_age"] = {"range": [1.0e9, 2.0e9], "unit": UNSTATED, "basis": "stated"}
        if name in ("across_sources", "evidence"):
            provenance = (
                field["provenance"]
                if name == "across_sources"
                else an_object(a_list(field["evidence"])[1])["provenance"]
            )
            derivation = an_object(an_object(provenance)["derivation"])
            inputs = an_object(a_list(derivation["input_specimens"])[0])
            facts = an_object(inputs["specimen"])
            facts["post_mortem_interval"] = {"value": 60.0, "unit": UNSTATED, "basis": "stated"}
        if name == "table":
            # A host whose table holds its `axis_unit` as a status object, which step 9 refuses, beside the
            # one whose read passes steps 8 and 9 (`provenance.md` section 1 item 5: a unit "any").
            unstated = copy.deepcopy(field)
            an_object(unstated["table"])["axis_unit"] = UNSTATED
            unstated_record = record_of(unstated, registered, specimen=copy.deepcopy(section_specimen))
            an_object(unstated_record["body"])["extensions"] = {"acme": {"sections": {"x": 1.0}}}
            unstated_record["content_hash"] = content_hash(unstated_record)
            found.append(Host("table_axis_unit_unstated", unstated_record, None, registered, "table"))
        record = record_of(field, registered, specimen=section_specimen)
        record_body = record["body"]
        assert isinstance(record_body, dict)
        record_body["extensions"] = {"acme": {"sections": {"x": 1.0}}}
        record["content_hash"] = content_hash(record)
        found.append(Host(name, record, None, registered, str(field["form"])))
    # And each, wrapped as the field's only alternative, which reads as the field (HP28's P5), so that every
    # position at a field's place is read inside an alternative too (`found_by`).
    for host in list(found):
        record = copy.deepcopy(host.record)
        section, _, name = host.field.partition(".")
        fields_of = an_object(an_object(an_object(an_object(record["body"])["sections"])[section])["fields"])
        fields_of[name] = {"alternatives": [fields_of[name]]}
        record["content_hash"] = content_hash(record)
        found.append(host._replace(name=f"{host.name}, its only alternative", record=record))
    # An implied condition the read applies (its fact and token are the field's), holding a numeric and a
    # token condition the record does not.
    implied: JsonObject = {
        "acceptance": "implied_condition",
        "record": pin(found[0].record),
        "field": FIELD,
        "fact": "tissue_state",
        "token": "ex_vivo_fresh",
        "implies": {"specimen_size": {"value": 1.0e-3, "unit": "m"}, "density_kind": {"token": "apparent"}},
        "reason": "a fixture's",
    }
    # And a nominal, which a constant leaves unused.
    nominal: JsonObject = {
        "acceptance": "nominal",
        "record": pin(found[0].record),
        "field": FIELD,
        "value": 0.0007,
        "basis": "a fixture's",
    }
    request: JsonObject = {
        "acceptances": [implied, nominal],
        "target": {"record": pin(found[0].record), "field": FIELD},
        "operating_conditions": {
            "temperature": {"value": 310.15, "unit": "K"},
            "shear_rate": {"range": [10.0, 100.0], "unit": "1/s"},
        },
        "requirement": {
            "want": "value",
            "conditions": {
                "temperature": {"tolerance": {"value": 1.0, "unit": "K"}},
                "shear_rate": {"tolerance": {"value": 0.0, "unit": "1/s"}},
                "measurement_geometry": {"accept": ["tube"]},
            },
        },
    }
    found.append(Host("request", found[0].record, request))
    return tuple(found)


def outcome(record: JsonObject, request: JsonObject | None, host: Host) -> Outcome:
    """The read of `request`, or of `host`'s field of `record` pinned by its recomputed hash."""
    if request is None:
        record = {**record, "content_hash": content_hash(record)}
        target: JsonObject = {"record": pin(record), "field": host.field}
        request = {"target": target, "requirement": {"want": WANT[host.form]}}
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    try:
        result = read(request, store)
    except NotImplementedError:
        return Outcome(PAST_STEP_8, frozenset())
    codes = frozenset(reason.code for reason in result.reasons)
    return Outcome(result.status, codes, result.conditions is not None)


def unknown_name_added(before: Outcome) -> Outcome:
    """What a read gives once a condition name it does not know is added: step 10's `unknown` reason for it
    beside what it gave (section 5, first row)."""
    statuses = cast(tuple[ReadStatus, ...], (before.status, "unknown"))
    return Outcome(worst(statuses), before.codes | {"condition_unknown_name"}, conditions=True)


# Where a position is in a host.


def fits(step: str, key: str, member: JsonValue, field: str) -> bool:
    held = isinstance(member, dict) and "status" not in member
    condition = VOCABULARY.conditions.get(key)
    if step == "{section}":
        return key == field.partition(".")[0]
    if step == "{field}":
        return key == field.partition(".")[2]
    if step in ("{numeric}", "{token}", "{condition}"):
        return held and condition is not None and step in ("{condition}", f"{{{condition.shape}}}")
    if step == "{fact}":
        return held and key in VOCABULARY.facts
    if step == "{status}":
        return isinstance(member, dict) and "status" in member
    return key in step.split("|")


def places(position: JsonObject, host: Host) -> Iterator[Path_]:
    """Each path in `host`'s record or request, as the position's `in` says, that its pattern finds, to an
    object: none in a host of another form than the position names."""
    if position.get("form", host.form) != host.form or (host.request is None) != (position["in"] == "record"):
        return
    document = host.request if host.request is not None else host.record
    yield from found_by(document, [str(step) for step in a_list(position["path"])], host.field)


def found_by(value: JsonValue, pattern: list[str], field: str, here: Path_ = ()) -> Iterator[Path_]:
    """Each path in `value` that `pattern` finds. A field's place is also each alternative's, where the field
    holds them: "each alternative is read alone, as a field" (`read_side_contract.md` section 3, step 7)."""
    if not pattern:
        if isinstance(value, dict):
            yield here
        return
    step, rest = pattern[0], pattern[1:]
    if step.startswith("[") and isinstance(value, list):
        kinds = step[1:-1].split("|")
        for index, item in enumerate(value):
            if step == "[*]" or (isinstance(item, dict) and item.get("acceptance") in kinds):
                yield from found_by(item, rest, field, (*here, index))
    elif isinstance(value, dict):
        for key, member in value.items():
            if not step.startswith("[") and fits(step, key, member, field):
                yield from found_by(member, rest, field, (*here, key))
                alternatives = member.get("alternatives") if isinstance(member, dict) else None
                if step == "{field}" and isinstance(alternatives, list):
                    for index, alternative in enumerate(alternatives):
                        yield from found_by(alternative, rest, field, (*here, key, "alternatives", index))


def at(value: JsonValue, path: Path_) -> JsonValue:
    for step in path:
        value = an_object(value)[step] if isinstance(step, str) else a_list(value)[step]
    return value


# The members named at a place.


def members_of(document: JsonObject, name: str) -> list[str]:
    """A definition's own members and those of each definition its `allOf` refers to, or the schema's root's
    for `$root`."""
    definition = document if name == "$root" else an_object(an_object(document["$defs"])[name])
    found: list[str] = []
    for conjunct in a_list(definition.get("allOf", [])):
        reference = an_object(conjunct).get("$ref", "")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            found += members_of(document, reference.removeprefix("#/$defs/"))
    return found + list(an_object(definition.get("properties", {})))


def definition_of(map_name: str, name: str) -> str:
    """The definition the writer schema gives a condition or a fact of `name`, beside the status object."""
    choices = at(SCHEMAS["record"], ("$defs", map_name, "properties", name, "anyOf"))
    return str(an_object(a_list(choices)[0])["$ref"]).removeprefix("#/$defs/")


def parent(position: JsonObject, path: Path_) -> str:
    """The definition of the object holding a status object at `path`, which a status position's `schema`
    names first: the condition's or the fact's own where it says `per_condition` or `per_fact`. Another it
    names holds the same members, each a status object standing for the same shape (a withheld report's
    beside a report's)."""
    schema = a_list(position["schema"])[0]
    if schema in ("per_condition", "per_fact"):
        return definition_of("conditions" if schema == "per_condition" else "specimen", str(path[-2]))
    return str(schema)


def named(position: JsonObject, path: Path_) -> list[str]:
    """The members named at `path`, where `position` finds it."""
    document = SCHEMAS[str(position["in"])]
    found: list[str] = []
    for schema in a_list(position.get("schema", [])):
        if schema == "$fields_of_section":
            found += [
                field.partition(".")[2] for field in VOCABULARY.fields if field.startswith(f"{path[2]}.")
            ]
        elif schema == "$conditions":
            found += list(VOCABULARY.conditions)
        elif schema == "per_condition":
            found += members_of(document, definition_of("conditions", str(path[-1])))
        elif schema == "per_fact":
            found += members_of(document, definition_of("specimen", str(path[-1])))
        else:
            found += members_of(document, str(schema))
    also = position.get("also", {})
    assert isinstance(also, dict)
    return list(dict.fromkeys([*found, *also]))


# What the read must give.


def injections(position: JsonObject, host: Host, path: Path_) -> Iterator[tuple[str, JsonValue, bool]]:
    """Each member to add at `path`, its value, and whether the read must refuse it."""
    verdict = position["verdict"]
    target = at(host.request if position["in"] == "request" else host.record, path)
    assert isinstance(target, dict)
    if verdict == "status":
        defines = status_rows.defines(parent(position, path), str(path[-1]))
        yield UNKNOWN, 1.0, not defines
        yield "statusq", "x", True
        if defines:
            yield defines[-1], 1.0, True
        return
    yield UNKNOWN, 1.0, verdict == "refused"
    names = (
        named(position, path) if verdict != "not_checked" else [name for name in target if name != UNKNOWN]
    )
    for name in names:
        yield name + "q", 1.0, verdict in ("ignored", "refused")


def problems(position: JsonObject) -> list[str]:
    """Each injection at `position` whose read the verdict does not give, and a position found nowhere."""
    found: list[str] = []
    reached = False
    for host in hosts():
        document = host.request if host.request is not None else host.record
        before = outcome(host.record, host.request, host)
        for path in places(position, host):
            reached = True
            for name, value, refused in injections(position, host, path):
                changed = copy.deepcopy(document)
                parent = at(changed, path)
                assert isinstance(parent, dict)
                parent[name] = value
                after = (
                    outcome(changed, None, host)
                    if host.request is None
                    else outcome(host.record, changed, host)
                )
                refusal = REFUSAL[str(position["in"])]
                kept = before.codes if before.status == "not_met" else before.codes & STEP_8_UNKNOWN
                allowed = kept | {refusal}
                if refused:
                    meets = after.status == "not_met" and refusal in after.codes and after.codes <= allowed
                elif position["verdict"] == "condition_names" and before.conditions:
                    meets = after == unknown_name_added(before)
                else:
                    meets = after == before
                if not meets:
                    found.append(
                        f"{position['id']} {host.name} {'.'.join(map(str, path)) or '$'} {name}: {after}"
                    )
    if not reached:
        found.append(f"{position['id']}: found in no host")
    return found


LIVE = [position for position in TABLE if "deferred" not in position]


@pytest.mark.parametrize("position", LIVE, ids=[str(position["id"]) for position in LIVE])
def test_the_read_meets_each_positions_verdict(position: JsonObject) -> None:
    assert problems(position) == []


# The steps built in pieces: `done` names their pieces, never the step itself.
IN_PIECES = {re.sub(r"^(S[0-9]+).*", r"\1", piece) for piece in PIECES}


def done_too_soon(positions: list[JsonObject], done: list[str]) -> list[str]:
    """Each deferred position whose piece is done, or that names no piece, an unknown one or a verdict; and
    each that names a step built in pieces, which `done` never holds, so that the position would wait for
    ever."""
    found: list[str] = []
    for position in positions:
        pieces = [str(piece) for piece in a_list(position.get("deferred", []))]
        if "deferred" in position and (not pieces or "verdict" in position or set(pieces) - KNOWN):
            found.append(f"{position['id']}: a deferred position names its known pieces and no verdict")
        found += [
            f"{position['id']}: {piece} is built in pieces, so it is never done: name the piece"
            for piece in pieces
            if piece in IN_PIECES
        ]
        found += [
            f"{position['id']}: {piece} is done, so the position needs its verdict"
            for piece in pieces
            if piece in done
        ]
    return found


def test_a_deferred_position_waits_for_a_piece_not_done() -> None:
    """A position no read of this version reaches yet: the test fails once the first piece that builds it is
    done, until the position gets its verdict and is read; and where it names a step built in pieces, which is
    never done."""
    done = [str(piece) for piece in STEPS["done"]]
    assert done_too_soon(TABLE, done) == []
    assert done_too_soon(TABLE, [*done, "S4b"]) == ["D06: S4b is done, so the position needs its verdict"]
    assert done_too_soon([{**BY_ID["D06"], "deferred": ["S2c"]}], done) != []
    # The table's row as it stood before S3a, which built it: deferred, and now due.
    deferred_table = {name: value for name, value in BY_ID["R78"].items() if name != "verdict"}
    assert done_too_soon([{**deferred_table, "deferred": ["S3a"]}], done) == [
        "R78: S3a is done, so the position needs its verdict"
    ]
    # The rows as they stood before S4a, which named S3 and S4 once those were built in pieces.
    assert done_too_soon([{**deferred_table, "deferred": ["S3"]}], [*done, "S3c"]) == [
        "R78: S3 is built in pieces, so it is never done: name the piece"
    ]
    assert done_too_soon([{**BY_ID["D06"], "deferred": ["S3", "S4"]}], [*done, "S4a", "S4b", "S4c"]) == [
        "D06: S3 is built in pieces, so it is never done: name the piece",
        "D06: S4 is built in pieces, so it is never done: name the piece",
    ]


# The table against the text and the schemas.


Documents = Callable[[str], str]


def flowing(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def unquoted(positions: list[JsonObject], read_document: Documents) -> list[str]:
    return [
        str(position["id"])
        for position in positions
        if flowing(str(position["quote"])) not in flowing(read_document(str(position["cite"])))
    ]


def document(name: str) -> str:
    return (SPECIFICATION / name).read_text(encoding="utf-8")


def test_each_position_quotes_the_sentence_that_decides_it() -> None:
    assert unquoted(TABLE, document) == []


WRITE_ONLY = "x-materica-write-only"


def reachable(name: str, seen: set[str] | None = None) -> set[str]:
    """The writer's definitions of objects with named members that step 8 reads from `name`: through members,
    choices and items, never into a member marked write-only `true`. A member marked write-only `unless` a
    condition holds is one step 8 reads where it holds (a derived value's `derivation`)."""
    seen = set() if seen is None else seen
    if name in seen:
        return seen
    seen.add(name)
    definitions = SCHEMAS["record"]["$defs"]

    def walk(node: JsonValue) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            reference = node.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/$defs/"):
                reachable(reference.removeprefix("#/$defs/"), seen)
            for keyword, value in node.items():
                if keyword == "properties" and isinstance(value, dict):
                    walk(
                        [
                            member
                            for member in value.values()
                            if not (isinstance(member, dict) and member.get(WRITE_ONLY) is True)
                        ]
                    )
                elif keyword in ("allOf", "anyOf", "oneOf", "items", "additionalProperties"):
                    walk(value)

    walk(definitions[name])
    return seen


def objects(names: set[str]) -> set[str]:
    definitions = SCHEMAS["record"]["$defs"]
    return {name for name in names if isinstance(definitions[name].get("properties"), dict)}


def test_a_member_read_under_a_condition_is_reached() -> None:
    """A derivation, which step 8 reads for origin `derived` alone, and the objects inside it."""
    derivation = {"derivation", "derivation_input", "input_specimen", "pinned_record"}
    assert derivation <= objects(reachable("constant_field"))


# Where a read starts in a record: a value field of each form some row of schema 0.1 allows, alternatives and
# a section's specimen. A power law, a parameter set and reference data, which no row allows, are refused for
# their form, their own member read by no reader of this version; the members they share have a constant's
# positions.
STARTS = (
    "constant_field",
    "table_field",
    "interval_field",
    "composition_field",
    "evidence_field",
    "alternatives",
)
NO_ROW_ALLOWS = {"power_law_field", "parameter_set_field", "reference_data_field"}


def expanded(names: set[str]) -> set[str]:
    """`names`, with every condition's and fact's definition for `per_condition` and `per_fact`."""
    if "per_condition" in names:
        names = names | {definition_of("conditions", name) for name in VOCABULARY.conditions}
    if "per_fact" in names:
        names = names | {definition_of("specimen", name) for name in VOCABULARY.facts}
    return names


def status_members(definition: str) -> list[str]:
    """The members of `definition` that may hold a status object (`status_rows.py`)."""
    found: list[str] = []
    for member in members_of(SCHEMAS["record"], definition):
        try:
            status_rows.tokens(definition, member)
        except ValueError:
            continue
        found.append(member)
    return found


def uncovered(positions: list[JsonObject]) -> set[str]:
    """Each object definition a read reaches in a record that no position names, the ones `based` and
    `field_members` lend their members to others aside; and each member of such a definition that may hold a
    status object, `<definition>.<member>`, whose definition no status position names. A deferred position
    covers both kinds for the definitions it names."""
    objects_named: set[str] = set()
    statuses_named: set[str] = set()
    for position in positions:
        if position["in"] != "record":
            continue
        named_here = expanded({str(schema) for schema in a_list(position.get("schema", []))})
        if position.get("verdict") != "status":
            objects_named |= named_here
        if position.get("verdict") == "status" or "deferred" in position:
            statuses_named |= named_here
    lent = {"based", "field_members"}
    reached = objects(set[str]().union(*(reachable(start) for start in (*STARTS, "specimen"))))
    reached -= lent | NO_ROW_ALLOWS | {name for name in reached if name.startswith("status_")}
    found = reached - objects_named
    for definition in reached - statuses_named:
        found |= {
            f"{definition}.{member}"
            for member in status_members(definition)
            if (definition, member) not in unchecked(positions)
        }
    return found


def unchecked(positions: list[JsonObject]) -> set[tuple[str, str]]:
    """The members a `not_checked` position names, each with the name of the object holding it, which is its
    definition's (`provenance`'s `review` and `assistance`)."""
    found: set[tuple[str, str]] = set()
    for position in positions:
        path = [str(step) for step in a_list(position["path"])]
        if position.get("verdict") == "not_checked" and len(path) >= 2:
            found |= {(path[-2], name) for name in path[-1].split("|")}
    return found


def test_every_object_step_8_reads_has_a_position() -> None:
    assert uncovered(TABLE) == set()


# Controls: a read with one fault, and a table with one fault. Each must make a check fail.


def _refusing_the_unknown(value: JsonObject, named_members: object, where: str, found: list[object]) -> None:
    SLIPS(value, named_members, where, found)  # type: ignore[arg-type]
    if UNKNOWN in value:
        found.append(value_shapes.invalid(f"{where} holds {UNKNOWN}"))


SLIPS = value_shapes.slips


def _no_slip(members: object, names: object) -> list[tuple[str, str]]:
    return []


NAMED_AT_A_NOMINAL = read_module._NOMINAL_MEMBERS  # pyright: ignore[reportPrivateUsage]
ALTERNATIVES_PROBLEMS = fields.alternatives_problems


def _refusing_the_unknown_in_an_alternative(holder: JsonObject, name: str) -> list[object]:
    found: list[object] = list(ALTERNATIVES_PROBLEMS(holder, name))
    if any(
        isinstance(alternative, dict) and UNKNOWN in alternative
        for alternative in a_list(holder["alternatives"])
    ):
        found.append(value_shapes.invalid(f"{name} holds an alternative holding {UNKNOWN}"))
    return found


BY_ID = {str(position["id"]): position for position in TABLE}


@pytest.mark.parametrize(
    ("module", "name", "value", "position"),
    [
        pytest.param(value_shapes, "slips", _refusing_the_unknown, "R22", id="an_unknown_member_refused"),
        pytest.param(value_shapes, "slips", _refusing_the_unknown, "R47", id="in_an_interval"),
        pytest.param(value_shapes, "slips", _refusing_the_unknown, "R52", id="in_a_component"),
        pytest.param(fields, "slips", _refusing_the_unknown, "R62", id="in_an_evidence_report"),
        pytest.param(value_shapes, "slips", _refusing_the_unknown, "R65", id="in_a_reports_provenance"),
        pytest.param(value_shapes, "slipped", _no_slip, "R64", id="a_slip_in_a_reports_standard_ignored"),
        pytest.param(value_shapes, "slipped", _no_slip, "R49", id="a_slip_in_a_composition_field_ignored"),
        pytest.param(value_shapes, "slipped", _no_slip, "R28", id="a_slip_ignored"),
        pytest.param(read_module, "slipped", _no_slip, "Q04", id="a_slip_in_a_request_ignored"),
        pytest.param(read_module, "slipped", _no_slip, "Q13", id="a_slip_in_an_implied_value_ignored"),
        pytest.param(read_module, "_IMPLIED_REFUSED", (), "Q14", id="an_implied_value_holding_a_status"),
        pytest.param(read_module, "_NOMINAL_MEMBERS", NAMED_AT_A_NOMINAL[:-1], "Q15", id="a_slip_of_params"),
        pytest.param(
            read_module,
            "alternatives_problems",
            _refusing_the_unknown_in_an_alternative,
            "R77",
            id="an_unknown_member_in_an_alternative_refused",
        ),
    ],
)
def test_a_read_against_the_verdict_is_found(
    module: object, name: str, value: object, position: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, name, value)
    assert problems(BY_ID[position]) != []


def test_a_wrong_verdict_a_dead_row_and_a_lost_quote_are_found() -> None:
    assert problems({**BY_ID["R22"], "verdict": "not_checked"}) != []
    assert problems({**BY_ID["R22"], "path": ["body", "nowhere"]}) == ["R22: found in no host"]
    assert problems({**BY_ID["Q10"], "path": ["acceptances", "[pick]"]}) == ["Q10: found in no host"]
    assert problems({**BY_ID["Q12"], "verdict": "ignored"}) != []
    assert uncovered([position for position in TABLE if position["id"] != "R77"]) == {"alternatives"}
    assert unquoted([{**BY_ID["R01"], "quote": "A reader ignores every member"}], document) == ["R01"]
    assert uncovered([position for position in TABLE if position["id"] not in ("R26", "R58")]) == {
        "uncertainty"
    }
    assert uncovered([position for position in TABLE if position["id"] not in ("R23", "R55")]) == {
        f"statistics_block.{member}" for member in status_members("statistics_block")
    }
    assert uncovered([position for position in TABLE if position["id"] != "R63"]) == {
        f"{definition}.{member}"
        for definition in ("evidence_entry", "withheld_evidence_entry")
        for member in status_members(definition)
    }
    composition = ("R49", "R50", "R51", "R52", "R53")
    assert uncovered([position for position in TABLE if position["id"] not in composition]) == {
        "composition_field",
        "composition",
        "composition_component",
        *(f"composition_field.{member}" for member in ("composition", "statistics", "unit")),
        "composition_component.statistics",
    }


def test_a_position_at_a_fields_place_is_read_inside_its_only_alternative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control of the wrapped hosts: a read that refuses an unknown member in a status object's place is
    found there inside an alternative, as in the field."""
    monkeypatch.setattr(value_shapes, "slips", _refusing_the_unknown)
    found = problems(BY_ID["R22"])
    assert [problem for problem in found if "its only alternative" in problem] != []
    assert [problem for problem in found if "its only alternative" not in problem] != []


def objects_in(value: JsonValue, here: Path_ = ()) -> Iterator[Path_]:
    """The path of every object in `value`."""
    if isinstance(value, dict):
        yield here
        for name, member in value.items():
            yield from objects_in(member, (*here, name))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from objects_in(item, (*here, index))


def unfound(positions: list[JsonObject]) -> list[str]:
    """Each object in a host that no position's path finds, outside a place step 8 does not check."""
    found: list[str] = []
    for host in hosts():
        document = host.request if host.request is not None else host.record
        reached: set[Path_] = set()
        unchecked: set[Path_] = set()
        for position in positions:
            paths = set(places(position, host))
            reached |= paths
            if position.get("verdict") == "not_checked":
                unchecked |= paths
        for path in objects_in(document):
            inside = any(path[: len(place)] == place for place in unchecked)
            if path not in reached and not inside:
                found.append(f"{host.name}: {'.'.join(map(str, path)) or '$'}")
    return sorted(set(found))


def test_every_object_in_a_host_is_found_by_a_position() -> None:
    """The review's three missing kinds included: a section's or a derivation input's fact held as a status
    object, and a fact's member or a token condition's unit held as one; and an implied condition, which the
    deferred row of the other acceptances does not find."""
    assert unfound(TABLE) == []
    assert unfound([position for position in TABLE if position["id"] != "R39"]) != []
    assert unfound([position for position in TABLE if position["id"] != "Q10"]) == ["request: acceptances.0"]


# An implied condition's members against the text (D06's first piece): rows Q10, Q13 and Q14 name them by
# `also`, `read_request.json` by its definitions (S2b-2), and the read by `read.py`'s `_IMPLIED_*` tuples.
# Each member, at its place, with what a read does with it and the sentence that names it there.

AN_IMPLIED_CONDITION = "an implied condition"
A_NUMERIC_VALUE = "a value of `implies` for a numeric condition"
A_TOKEN_VALUE = "a value of `implies` for a token condition"


class Named(NamedTuple):
    place: str
    use: str  # `read`, a `location`, `ignored`, `refused`, or refused as the `other kind`'s
    members: tuple[str, ...]
    cite: str
    quote: str  # names each member, in backticks or in double quotes


SHAPES = '`{"value", "unit"}` or `{"range": [lo, hi], "unit"}` for a numeric one'
WITHOUT = (
    "a record condition's shapes without `basis` (one there is ignored), `plus_minus` or `set_or_measured`"
)
# Ignored with the basis it goes with: S2a-3's reading.
INFERRED = "or `inferred` with an `inferred_from` text"
STATUS = "an object holding `status` is a status object"
# A status object's other member, which an implied value may not be: named there, so a slip of it is refused
# (S2a-4's fix round, as the reference model reads it).
STATUS_REASON = "where its `status` or `reason` is not a string"
TOKEN_SHAPE = '`{"token"}`, with a token of its row'
IMPLIED_NAMES = [
    Named(AN_IMPLIED_CONDITION, "read", ("acceptance",), "declarations.md", "Every entry has `acceptance`"),
    Named(AN_IMPLIED_CONDITION, "read", ("field",), "declarations.md", "names the `field`"),
    Named(
        AN_IMPLIED_CONDITION,
        "ignored",
        ("reason", "basis"),
        "read_side_contract.md",
        "its `reason` and `basis`",
    ),
    Named(
        AN_IMPLIED_CONDITION,
        "location",
        ("record", "region", "interval"),
        "declarations.md",
        "| `implied_condition` | `region`, `interval` or `record` |",
    ),
    Named(AN_IMPLIED_CONDITION, "read", ("fact",), "declarations.md", "`fact`, a specimen fact whose shape"),
    Named(AN_IMPLIED_CONDITION, "read", ("token",), "declarations.md", "and `token`, one of its tokens"),
    Named(
        AN_IMPLIED_CONDITION, "read", ("implies",), "declarations.md", "`implies`, per registered condition"
    ),
    Named(A_NUMERIC_VALUE, "read", ("value", "range", "unit"), "declarations.md", SHAPES),
    Named(A_TOKEN_VALUE, "read", ("token",), "declarations.md", TOKEN_SHAPE),
    # The other kind's shape, refused (the maintainer's ruling of 2026-10-18).
    Named(
        A_NUMERIC_VALUE,
        "other kind",
        ("token",),
        "read_side_contract.md",
        "gives a numeric condition a `token`",
    ),
    Named(
        A_TOKEN_VALUE,
        "other kind",
        ("value", "range", "unit"),
        "read_side_contract.md",
        "or a token condition a `value`, `range` or `unit`",
    ),
    *(
        named_here
        for place in (A_NUMERIC_VALUE, A_TOKEN_VALUE)
        for named_here in (
            Named(place, "ignored", ("basis",), "declarations.md", WITHOUT),
            Named(place, "ignored", ("inferred_from",), "provenance.md", INFERRED),
            Named(place, "ignored", ("reason",), "provenance.md", STATUS_REASON),
            Named(place, "refused", ("plus_minus", "set_or_measured"), "declarations.md", WITHOUT),
            Named(place, "refused", ("status",), "provenance.md", STATUS),
        )
    ),
]


class ReadNames(NamedTuple):
    """`read.py`'s names of an implied condition's members."""

    own: tuple[str, ...]
    locations: tuple[str, ...]
    ignored: tuple[str, ...]
    refused: tuple[str, ...]
    other_kind: dict[str, tuple[str, ...]]


READ_NAMES = ReadNames(
    read_module._IMPLIED_OWN,  # pyright: ignore[reportPrivateUsage]
    read_module._LOCATION_MEMBERS,  # pyright: ignore[reportPrivateUsage]
    read_module._IMPLIED_IGNORED,  # pyright: ignore[reportPrivateUsage]
    read_module._IMPLIED_REFUSED,  # pyright: ignore[reportPrivateUsage]
    read_module._OF_THE_OTHER_KIND,  # pyright: ignore[reportPrivateUsage]
)


def quote_problems(names: list[Named], read_document: Documents) -> list[str]:
    """Each quote of `names` its document no longer holds, and each member a quote does not name."""
    found = [
        f"{named.members} at {named.place}: {named.cite} no longer says {named.quote!r}"
        for named in names
        if flowing(named.quote) not in flowing(read_document(named.cite))
    ]
    found += [
        f"{member} at {named.place}: {named.quote!r} does not name it"
        for named in names
        for member in named.members
        if f"`{member}`" not in named.quote and f'"{member}"' not in named.quote
    ]
    return found


def implied_name_problems(
    names: list[Named], rows: dict[str, JsonObject], read_names: ReadNames, read_document: Documents
) -> list[str]:
    """Each way `names`, the rows' `also` lists, `read_request.json`'s definition and the read's tuples
    part: a quote lost or not naming its members, and a row, a definition or a tuple that names other members
    than the text at its place."""
    found = quote_problems(names, read_document)

    def at(places: tuple[str, ...], *uses: str) -> set[str]:
        return {
            member
            for named in names
            if named.place in places and (not uses or named.use in uses)
            for member in named.members
        }

    acceptance, numeric, token = (AN_IMPLIED_CONDITION,), (A_NUMERIC_VALUE,), (A_TOKEN_VALUE,)
    values = (A_NUMERIC_VALUE, A_TOKEN_VALUE)
    shape = {
        *members_of(SCHEMAS["request"], "operating_value"),
        *members_of(SCHEMAS["request"], "operating_range"),
    }
    held_and_named = {
        "Q10's also": (set(an_object(rows["Q10"]["also"])), at(acceptance)),
        "read_request.json's implied condition": (
            set(members_of(SCHEMAS["request"], "implied_condition_acceptance")),
            at(acceptance),
        ),
        "Q13's schema and also": (shape | set(an_object(rows["Q13"]["also"])), at(numeric)),
        "Q14's also": (set(an_object(rows["Q14"]["also"])), at(token)),
        "read._IMPLIED_OWN": (set(read_names.own), at(acceptance)),
        "read._LOCATION_MEMBERS": (set(read_names.locations), at(acceptance, "location")),
        "read._IMPLIED_IGNORED": (set(read_names.ignored), at(values, "ignored")),
        "read._IMPLIED_REFUSED": (set(read_names.refused), at(values, "refused")),
        "read._OF_THE_OTHER_KIND's numeric": (
            set(read_names.other_kind["numeric"]),
            at(numeric, "other kind"),
        ),
        "read._OF_THE_OTHER_KIND's token": (set(read_names.other_kind["token"]), at(token, "other kind")),
    }
    found += [
        f"{where} names {sorted(held - named)} beyond the text and lacks {sorted(named - held)}"
        for where, (held, named) in held_and_named.items()
        if held != named
    ]
    return found


def test_an_implied_conditions_members_are_those_the_text_names_at_each_place() -> None:
    assert implied_name_problems(IMPLIED_NAMES, BY_ID, READ_NAMES, document) == []


def without_also(row: str, *members: str) -> dict[str, JsonObject]:
    also = {name: reason for name, reason in an_object(BY_ID[row]["also"]).items() if name not in members}
    return {**BY_ID, row: {**BY_ID[row], "also": also}}


def test_an_implied_conditions_member_dropped_or_its_quote_lost_is_found() -> None:
    """The review's probe: `interval` and `basis` out of Q10's `also`, `inferred_from` out of Q13's."""
    assert implied_name_problems(
        IMPLIED_NAMES, without_also("Q10", "interval", "basis"), READ_NAMES, document
    )
    assert implied_name_problems(IMPLIED_NAMES, without_also("Q13", "inferred_from"), READ_NAMES, document)
    assert implied_name_problems(IMPLIED_NAMES, without_also("Q14", "status"), READ_NAMES, document)
    unrefusing = READ_NAMES._replace(refused=("plus_minus", "set_or_measured"))
    assert implied_name_problems(IMPLIED_NAMES, BY_ID, unrefusing, document)
    elsewhere = READ_NAMES._replace(locations=("record", "region"))
    assert implied_name_problems(IMPLIED_NAMES, BY_ID, elsewhere, document)
    of_one_kind = READ_NAMES._replace(other_kind={"numeric": (), "token": ("value", "range", "unit")})
    assert implied_name_problems(IMPLIED_NAMES, BY_ID, of_one_kind, document) == [
        "read._OF_THE_OTHER_KIND's numeric names [] beyond the text and lacks ['token']"
    ]
    assert implied_name_problems(IMPLIED_NAMES, without_also("Q14", "unit"), READ_NAMES, document) == [
        "Q14's also names [] beyond the text and lacks ['unit']"
    ]
    lost = [named._replace(quote="its `reason` and `basis` are read") for named in IMPLIED_NAMES[2:3]]
    assert implied_name_problems([*IMPLIED_NAMES[:2], *lost, *IMPLIED_NAMES[3:]], BY_ID, READ_NAMES, document)


# The sentence that refuses an implied value a member of the other kind of condition's shape.
THE_RULING = (
    "It breaks its shape too (`request_incomplete`, with that `condition`) where `implies` gives a numeric "
    "condition a `token`, or a token condition a `value`, `range` or `unit`, whatever that member holds"
)


def test_an_implied_value_refused_the_other_kinds_members_by_no_sentence_is_found() -> None:
    """Without the sentence, nothing in the text refuses them: the shapes `declarations.md` section 4.1 names
    are not a refusal, and the check names both directions."""

    def without_the_ruling(name: str) -> str:
        return flowing(document(name)).replace(THE_RULING, "")

    assert THE_RULING in flowing(document("read_side_contract.md"))
    assert implied_name_problems(IMPLIED_NAMES, BY_ID, READ_NAMES, without_the_ruling) == [
        f"{members} at {place}: read_side_contract.md no longer says {quote!r}"
        for members, place, quote in [
            (("token",), A_NUMERIC_VALUE, "gives a numeric condition a `token`"),
            (("value", "range", "unit"), A_TOKEN_VALUE, "or a token condition a `value`, `range` or `unit`"),
        ]
    ]


# A nominal's members against the text: `read_request.json`'s definition, which row Q15 names, and the read's
# tuple.

A_NOMINAL = "a nominal"
NOMINAL_OWN = "`value`, `basis`; for a parameter set, `params` in place of `value`"
NOMINAL_NAMES = [
    Named(A_NOMINAL, "read", ("acceptance",), "declarations.md", "Every entry has `acceptance`"),
    Named(A_NOMINAL, "read", ("field",), "declarations.md", "names the `field`"),
    Named(A_NOMINAL, "ignored", ("reason", "basis"), "read_side_contract.md", "its `reason` and `basis`"),
    Named(
        A_NOMINAL,
        "location",
        ("record", "region", "interval"),
        "declarations.md",
        "| `nominal` | `region`, `interval` or `record` |",
    ),
    Named(A_NOMINAL, "read", ("value",), "declarations.md", NOMINAL_OWN),
    Named(A_NOMINAL, "ignored", ("params",), "declarations.md", NOMINAL_OWN),
]


def nominal_name_problems(
    names: list[Named], definition: str, read_names: tuple[str, ...], read_document: Documents
) -> list[str]:
    """Each way `names`, `read_request.json`'s `definition` and the read's tuple part."""
    named = {member for named in names for member in named.members}
    held = {
        "read_request.json's nominal": set(members_of(SCHEMAS["request"], definition)),
        "read._NOMINAL_MEMBERS": set(read_names),
    }
    return quote_problems(names, read_document) + [
        f"{where} names {sorted(members - named)} beyond the text and lacks {sorted(named - members)}"
        for where, members in held.items()
        if members != named
    ]


def test_a_nominals_members_are_those_the_text_names() -> None:
    assert nominal_name_problems(NOMINAL_NAMES, "nominal_acceptance", NAMED_AT_A_NOMINAL, document) == []


def test_a_nominals_member_dropped_or_its_quote_lost_is_found() -> None:
    assert nominal_name_problems(NOMINAL_NAMES, "nominal_acceptance", NAMED_AT_A_NOMINAL[:-1], document)
    assert nominal_name_problems(NOMINAL_NAMES, "implied_condition_acceptance", NAMED_AT_A_NOMINAL, document)
    lost = NOMINAL_NAMES[4]._replace(quote="`value` alone")
    assert nominal_name_problems(
        [*NOMINAL_NAMES[:4], lost], "nominal_acceptance", NAMED_AT_A_NOMINAL, document
    )

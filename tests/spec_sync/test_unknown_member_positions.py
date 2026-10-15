# SPDX-License-Identifier: Apache-2.0
"""Every position where a member the reader does not know is ignored or refused
(`unknown_member_positions.json`), against the text, the schemas and the read.

- Each position quotes the sentence that decides it, which must stay in its document.
- The members named at a position are the schema's (the writer schema's for a record, `read_request.json`'s
  for a request), with any other member the text names there given with its reason. Every object definition a
  read reaches in a record has a position, and every member of one that may hold a status object a status
  position, but where a `deferred` position names the piece that will read it (an interval, a composition,
  evidence, a table, alternatives, a request's acceptances): it fails once that piece is done. Every object in
  a host is found by a position's path.
- At each position of a few valid records and a valid request, at every place the pattern finds, the read
  meets the verdict: a member named `x_unknown_member` is ignored, or refused where every unknown name is, or
  as the row of a status object says; a member one slip from each named member (the name with a character
  added) is refused where the verdict is `ignored` or `refused` and ignored where it is `condition_names` or
  `not_checked`; and a status object beside a member of the shape it stands for is refused. A refusal adds
  `form_invalid` (`request_incomplete` in a request) to what the host gave, and may take away a `withheld` the
  changed status object no longer gives.
- Every position is found in some host, so that no row is dead.

The hosts are the full fields of `tests/property/full_fields.py`, each in a record with a section specimen
and extensions, and a request for one of them; three of them also hold a unit as a status object in a token
condition, a section's fact and a derivation input's fact. A read that passes step 8 raises
`NotImplementedError` until steps 9 to 13 are built: the outcome "past step 8".
"""

import copy
import json
import re
from collections.abc import Callable, Iterator
from functools import cache
from pathlib import Path
from typing import NamedTuple

import pytest

from materica.core import read as read_module
from materica.core import value_shapes
from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from scripts.gen_vocabulary import SPECIFICATION
from tests.property.full_fields import SPECIMEN, full_fields, record_of
from tests.spec_sync import status_rows
from tests.spec_sync.schemas import SCHEMA
from tests.spec_sync.test_case_steps import KNOWN, STEPS

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
PAST_STEP_8 = "past step 8"
REFUSAL = {"record": "form_invalid", "request": "request_incomplete"}


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


# The hosts, and the read of one.


class Host(NamedTuple):
    name: str
    record: JsonObject
    request: JsonObject | None  # a request host's request, its target pinned to `record`


def pin(record: JsonObject) -> JsonObject:
    return {member: record[member] for member in ("id", "version", "content_hash")}


@cache
def hosts() -> tuple[Host, ...]:
    """Each full field in a record with a section specimen and extensions; and a request for the first."""
    found: list[Host] = []
    for name, field in full_fields().items():
        section_specimen = copy.deepcopy(SPECIMEN)
        if name == "statuses":
            # A condition's unit as a status object: the text allows one on a numeric condition
            # (`provenance.md` section 6.1 item 1) and on a token condition (step 9 refuses it), though the
            # writer binds a numeric condition's unit to the registered one and gives a token condition none.
            conditions = an_object(field["conditions"])
            conditions["measurement_dimension"] = {"value": 5.0e-5, "unit": UNSTATED, "basis": "stated"}
            conditions["measurement_geometry"] = {"token": "tube", "unit": UNSTATED, "basis": "stated"}
        if name == "measurement":
            section_specimen["donor_age"] = {"range": [1.0e9, 2.0e9], "unit": UNSTATED, "basis": "stated"}
        if name == "across_sources":
            derivation = an_object(an_object(field["provenance"])["derivation"])
            inputs = an_object(a_list(derivation["input_specimens"])[0])
            facts = an_object(inputs["specimen"])
            facts["post_mortem_interval"] = {"value": 60.0, "unit": UNSTATED, "basis": "stated"}
        record = record_of(field, specimen=section_specimen)
        record_body = record["body"]
        assert isinstance(record_body, dict)
        record_body["extensions"] = {"acme": {"sections": {"x": 1.0}}}
        record["content_hash"] = content_hash(record)
        found.append(Host(name, record, None))
    request: JsonObject = {
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


def outcome(record: JsonObject, request: JsonObject | None) -> Outcome:
    """The read of `request`, or of the host field of `record` pinned by its recomputed hash."""
    if request is None:
        record = {**record, "content_hash": content_hash(record)}
        request = {"target": {"record": pin(record), "field": FIELD}, "requirement": {"want": "value"}}
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    try:
        result = read(request, store)
    except NotImplementedError:
        return Outcome(PAST_STEP_8, frozenset())
    return Outcome(result.status, frozenset(reason.code for reason in result.reasons))


# Where a position is in a host.


def fits(step: str, key: str, member: JsonValue) -> bool:
    held = isinstance(member, dict) and "status" not in member
    condition = VOCABULARY.conditions.get(key)
    if step == "{section}":
        return key == FIELD.partition(".")[0]
    if step == "{field}":
        return key == FIELD.partition(".")[2]
    if step in ("{numeric}", "{token}", "{condition}"):
        return held and condition is not None and step in ("{condition}", f"{{{condition.shape}}}")
    if step == "{fact}":
        return held and key in VOCABULARY.facts
    if step == "{status}":
        return isinstance(member, dict) and "status" in member
    return key in step.split("|")


def places(value: JsonValue, pattern: list[str], here: Path_ = ()) -> Iterator[Path_]:
    """Each path in `value` the position's pattern finds, to an object."""
    if not pattern:
        if isinstance(value, dict):
            yield here
        return
    step, rest = pattern[0], pattern[1:]
    if step == "[*]" and isinstance(value, list):
        for index, item in enumerate(value):
            yield from places(item, rest, (*here, index))
    elif isinstance(value, dict):
        for key, member in value.items():
            if step != "[*]" and fits(step, key, member):
                yield from places(member, rest, (*here, key))


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
    names: the condition's or the fact's own where it says `per_condition` or `per_fact`."""
    (schema,) = a_list(position["schema"])
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
        if (host.request is None) != (position["in"] == "record"):
            continue
        document = host.request if host.request is not None else host.record
        before = outcome(host.record, host.request)
        for path in places(document, [str(step) for step in a_list(position["path"])]):
            reached = True
            for name, value, refused in injections(position, host, path):
                changed = copy.deepcopy(document)
                parent = at(changed, path)
                assert isinstance(parent, dict)
                parent[name] = value
                after = outcome(changed, None) if host.request is None else outcome(host.record, changed)
                refusal = REFUSAL[str(position["in"])]
                allowed = (before.codes if before.status == "not_met" else frozenset[str]()) | {refusal}
                meets = (
                    after.status == "not_met" and refusal in after.codes and after.codes <= allowed
                    if refused
                    else after == before
                )
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


def done_too_soon(positions: list[JsonObject], done: list[str]) -> list[str]:
    """Each deferred position whose piece is done, or that names no piece, an unknown one or a verdict."""
    found: list[str] = []
    for position in positions:
        pieces = [str(piece) for piece in a_list(position.get("deferred", []))]
        if "deferred" in position and (not pieces or "verdict" in position or set(pieces) - KNOWN):
            found.append(f"{position['id']}: a deferred position names its known pieces and no verdict")
        found += [
            f"{position['id']}: {piece} is done, so the position needs its verdict"
            for piece in pieces
            if piece in done
        ]
    return found


def test_a_deferred_position_waits_for_a_piece_not_done() -> None:
    """A position no read of this version reaches yet: the test fails once the first piece that builds it is
    done, until the position gets its verdict and is read."""
    done = [str(piece) for piece in STEPS["done"]]
    assert done_too_soon(TABLE, done) == []
    assert done_too_soon(TABLE, [*done, "S2b-1"]) == [
        "D01: S2b-1 is done, so the position needs its verdict",
        "D02: S2b-1 is done, so the position needs its verdict",
    ]
    assert done_too_soon([{**BY_ID["D04"], "deferred": ["S2c"]}], done) != []


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
    choices and items, never into a member marked write-only."""
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
                            if not (isinstance(member, dict) and member.get(WRITE_ONLY))
                        ]
                    )
                elif keyword in ("allOf", "anyOf", "oneOf", "items", "additionalProperties"):
                    walk(value)

    walk(definitions[name])
    return seen


def objects(names: set[str]) -> set[str]:
    definitions = SCHEMAS["record"]["$defs"]
    return {name for name in names if isinstance(definitions[name].get("properties"), dict)}


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


BY_ID = {str(position["id"]): position for position in TABLE}


@pytest.mark.parametrize(
    ("module", "name", "value", "position"),
    [
        pytest.param(value_shapes, "slips", _refusing_the_unknown, "R22", id="an_unknown_member_refused"),
        pytest.param(value_shapes, "slipped", _no_slip, "R28", id="a_slip_ignored"),
        pytest.param(read_module, "slipped", _no_slip, "Q04", id="a_slip_in_a_request_ignored"),
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
    assert unquoted([{**BY_ID["R01"], "quote": "A reader ignores every member"}], document) == ["R01"]
    assert uncovered([position for position in TABLE if position["id"] != "R26"]) == {"uncertainty"}
    assert uncovered([position for position in TABLE if position["id"] != "R23"]) == {
        f"statistics_block.{member}" for member in status_members("statistics_block")
    }
    assert uncovered([position for position in TABLE if position["id"] != "D02"]) == {
        "composition_field",
        "composition",
        "composition_component",
        *(f"composition_field.{member}" for member in ("composition", "statistics", "unit")),
        "composition_component.statistics",
    }


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
        kind = "record" if host.request is None else "request"
        reached: set[Path_] = set()
        unchecked: set[Path_] = set()
        for position in positions:
            if position["in"] == kind:
                paths = set(places(document, [str(step) for step in a_list(position["path"])]))
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
    object, and a fact's member or a token condition's unit held as one."""
    assert unfound(TABLE) == []
    assert unfound([position for position in TABLE if position["id"] != "R39"]) != []

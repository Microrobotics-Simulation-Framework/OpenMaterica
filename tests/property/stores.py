# SPDX-License-Identifier: Apache-2.0
"""Strategies for the read procedure's laws: sources a store holds, a request, and the suites claimed.

The sources are records of three identities, each built to end its read at a known step: valid, or stating
a stale hash, an ill-formed hash, another schema version, an ill-formed one, a broken envelope, or a type no
0.1 reader reads; with sources no reference can resolve to beside them, and documents. Stale hashes come from
a pool of two, so that copies of one identity that state one hash and differ are drawn often, as are the
other cases of step 1 (`read_side_contract.md` section 3).
"""

import json
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.shapes import Suite
from tests.property import records

IDENTITIES = (("conformance/a", "1.0.0"), ("conformance/a", "2.0.0"), ("conformance/b", "1.0.0"))
STALE = ("sha256:" + "a" * 64, "sha256:" + "b" * 64)
VARIANTS = (
    "valid",
    "valid",
    "stale",
    "ill_formed_hash",
    "other_version",
    "ill_formed_version",
    "broken_envelope",
    "interface",
    "unknown_type",
)
# Sources no reference resolves to: bytes that do not parse, values that are not records, and a document.
UNREADABLE = (
    b"\xef\xbb\xbf{}",
    b"[]",
    b"1",
    b'"conformance/a"',
    b'{"id": "conformance/a"}',
    b'{"id": 1, "version": "1.0.0"}',
)
DOCUMENT = b'{"document_type": "scene_manifest", "id": "conformance/a", "version": "1.0.0"}'
CLAIMS: tuple[frozenset[Suite], ...] = (
    frozenset({"plain_read", "hash"}),
    frozenset({"plain_read"}),
    frozenset({"plain_read", "hash", "fits_and_reference_data"}),
)
# Claims without plain read, which every reader claims (README, "Suites and case numbers"): a misuse of the
# API, drawn in one world in four.
MISUSED: tuple[frozenset[Suite], ...] = (
    frozenset(),
    frozenset({"hash"}),
    frozenset({"hash", "fits_and_reference_data"}),
)


class Stored(NamedTuple):
    record: dict[str, JsonValue]
    variant: str
    data: bytes


@st.composite
def stored_records(draw: st.DrawFn, identities: tuple[tuple[str, str], ...] = IDENTITIES) -> Stored:
    """A record of one of `identities`, as one variant, written compactly or indented: copies of one content
    with different bytes."""
    id_, version = draw(st.sampled_from(identities))
    record = draw(
        records.records(records.SAMPLES, draw(st.sampled_from(["material", "material", "overlay"])))
    )
    record |= {"id": id_, "version": version}
    variant = draw(st.sampled_from(VARIANTS))
    if variant == "other_version":
        record["schema_version"] = "0.2.0"
    elif variant == "ill_formed_version":
        record["schema_version"] = draw(st.sampled_from(["0.1", "0.1.0\n", None]))
    elif variant == "broken_envelope":
        del record["name"]
    elif variant in ("interface", "unknown_type"):
        record["record_type"] = "interface" if variant == "interface" else "acme:thing"
    record["content_hash"] = content_hash(record)
    if variant == "stale":
        record["content_hash"] = draw(st.sampled_from(STALE))
    elif variant == "ill_formed_hash":
        record["content_hash"] = draw(st.sampled_from([str(record["content_hash"]).upper(), None, 1.0]))
    data = json.dumps(record, indent=draw(st.sampled_from([None, None, 1]))).encode()
    return Stored(record, variant, data)


# Sources beside the target's: records of the other identities, sources no reference resolves to, documents.
def others(target: tuple[str, str]) -> st.SearchStrategy[bytes]:
    identities = tuple(identity for identity in IDENTITIES if identity != target)
    return st.one_of(
        stored_records(identities).map(lambda stored: stored.data), st.sampled_from([*UNREADABLE, DOCUMENT])
    )


class World(NamedTuple):
    sources: tuple[bytes, ...]
    request: JsonValue
    claims: frozenset[Suite]
    case: str  # of CASES


# The cases step 1 tells apart, for the target's `id` and `version`: no copy; one that states the pin; two
# that state it, identical or not; and copies none of which states it, beside a copy whose hash is ill-formed
# or not. Each is drawn as often as another, whatever the sources beside it.
CASES = ("none", "pinned", "copies_identical", "copies_differ", "unpinned", "unpinned_ill_formed")


@st.composite
def worlds(draw: st.DrawFn) -> World:
    target = draw(st.sampled_from(IDENTITIES))
    case = draw(st.sampled_from(CASES))
    stored = draw(stored_records((target,)))
    stated = str(stored.record["content_hash"])
    sources = [] if case == "none" else [stored.data]
    if case == "copies_identical":
        sources.append(stored.data)
    elif case == "copies_differ":
        # Another record of the target's that states the same hash; read alone, it would often end otherwise.
        other = draw(stored_records((target,)))
        sources.append(json.dumps({**other.record, "content_hash": stored.record["content_hash"]}).encode())
    elif case == "unpinned_ill_formed":
        sources.append(json.dumps({**stored.record, "content_hash": stated.upper()}).encode())
    sources += draw(st.lists(others(target), max_size=4))
    pin = (
        draw(st.sampled_from([hash_ for hash_ in STALE if hash_ != stated]))
        if case.startswith("unpinned")
        else stated
    )
    claims = draw(st.sampled_from(CLAIMS * 3 + MISUSED))
    return World(tuple(sources), draw(requests(target, pin)), claims, case)


@st.composite
def requests(draw: st.DrawFn, target: tuple[str, str], pin: str) -> dict[str, JsonValue]:
    """A request for `target` pinned by `pin`; one in four with faults its own check finds, one reason's
    twice where two fall on `temperature` or have no condition."""
    request: dict[str, JsonValue] = {
        "target": {
            "record": {"id": target[0], "version": target[1], "content_hash": pin},
            "field": "fluid.dynamic_viscosity",
        },
        "operating_conditions": {"temperature": {"value": 310.15, "unit": "K"}},
        "requirement": {
            "want": draw(st.sampled_from(["value", "value", "bounds", "fit"])),
            "conditions": {"temperature": {"tolerance": {"value": 1.0, "unit": "K"}}},
        },
    }
    if draw(st.integers(0, 3)) == 3:
        for place, value in draw(st.lists(st.sampled_from(FAULTS), min_size=1, max_size=3)):
            records.changed(request, place, value)
    return request


# Faults of step 0, each a place and a value.
FAULTS: list[tuple[records.Place, JsonValue]] = [
    (("target", "field"), "fluid"),
    (("requirement", "want"), "values"),
    (("requirement", "conditions", "temperature", "tolerance", "value"), -1.0),
    (("operating_conditions", "temperature", "value"), "310.15"),
    (("operating_conditions", "temperature", "unit"), "Cel"),
    (("operating_conditions", "shear_rate"), {"range": [2.0, 1.0], "unit": "1/s"}),
]

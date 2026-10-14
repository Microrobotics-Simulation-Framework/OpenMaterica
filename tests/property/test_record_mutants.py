# SPDX-License-Identifier: Apache-2.0
"""Mutants of the record checks: the envelope checks, versions and the read up to step 5, each with one fault,
and the property that must kill each one. As in `test_mutants.py`, each must die within the examples the `ci`
profile gives a property, at both sizes, and records the examples its kill took as `examples_to_kill`.
"""

import re
from collections.abc import Callable, Collection, Mapping

import pytest
from hypothesis import strategies as st

from materica.core import envelope, identifiers, jsonio, read, resolve
from materica.core.envelope import envelope_problems
from materica.core.identifiers import CONTENT_HASH, RECORD_ID, VERSION, MaterialRef, Version, parse_version
from materica.core.jsonio import JsonValue
from materica.core.read import ReadResult
from materica.core.reasons import Reason
from materica.core.record import Record, RecordStore
from materica.shapes import Suite
from tests.property import records, stores
from tests.property import test_envelope_properties as envelope_properties
from tests.property import test_read_properties as read_properties
from tests.property import test_version_properties as version_properties
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.support import Searched
from tests.property.test_mutants import Mutant, killed_by, setting


def setting_item(
    target: Mapping[str, object], key: str, value: object
) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection that sets `target[key]` to `value` for the test."""

    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(target, key, value)

    return inject


# Envelope checks with one fault: a place left unchecked, one checked that the reader schema leaves open, or a
# pattern matched otherwise than in full. `ignoring` and `adding` give the core's checks without, or with, a
# check; the rest change the core in place.


def ignoring(*places: str) -> envelope_properties.Problems:
    """The core's envelope checks, blind to the problems at `places`."""
    return lambda value: [problem for problem in envelope_problems(value) if not problem.startswith(places)]


def adding(extra: Callable[[dict[str, JsonValue]], list[str]]) -> envelope_properties.Problems:
    """The core's envelope checks, with `extra` refusing more."""
    return lambda value: envelope_problems(value) + (extra(value) if isinstance(value, dict) else [])


def _members_of(value: JsonValue, *place: str) -> dict[str, JsonValue]:
    for step in place:
        value = value.get(step) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else {}


def _unknown_sections_checked(record: dict[str, JsonValue]) -> list[str]:
    sections = _members_of(record, "body", "sections") if record.get("record_type") == "material" else {}
    return [
        f"{name} checked"
        for name, section in sections.items()
        if not (isinstance(section, dict) and isinstance(section.get("fields"), dict))
    ]


def _specimens_checked(record: dict[str, JsonValue]) -> list[str]:
    sections = _members_of(record, "body", "sections") if record.get("record_type") == "material" else {}
    return [
        f"{name}.specimen checked"
        for name, section in sections.items()
        if isinstance(section, dict) and "specimen" in section and not isinstance(section["specimen"], dict)
    ]


def _interface_bodies_checked(record: dict[str, JsonValue]) -> list[str]:
    body = record.get("body")
    if record.get("record_type") != "interface" or not isinstance(body, dict):
        return []
    return envelope._material_body(body)  # pyright: ignore[reportPrivateUsage]  # the check the fault applies


def _base_patterns_checked(record: dict[str, JsonValue]) -> list[str]:
    base = _members_of(record, "body", "base") if record.get("record_type") == "overlay" else {}
    patterns = {"id": RECORD_ID, "version": VERSION, "content_hash": CONTENT_HASH}
    return [
        f"base.{name} checked"
        for name, pattern in patterns.items()
        if isinstance(base.get(name), str) and not pattern.fullmatch(str(base[name]))
    ]


def _schema_version_checked(record: dict[str, JsonValue]) -> list[str]:
    stated = record.get("schema_version")
    return ["schema_version checked"] if isinstance(stated, str) and not VERSION.fullmatch(stated) else []


def _null_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    members = envelope._members  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def without_nulls(
        value: dict[str, JsonValue],
        where: str,
        required: envelope.Members,
        optional: envelope.Members | None = None,
    ) -> list[str]:
        return members(
            {name: member for name, member in value.items() if member is not None}, where, required, optional
        )

    monkeypatch.setattr(envelope, "_members", without_nulls)


def sweeps(size: Size) -> st.SearchStrategy[list[records.Envelope]]:
    return records.sweeps(size)


def agreement_kills(problems: envelope_properties.Problems) -> Callable[[Size], int]:
    return killed_by(sweeps, lambda envelopes: envelope_properties.check_all_agree(problems, envelopes))


ENVELOPE = envelope._PATTERNS  # pyright: ignore[reportPrivateUsage]  # the table the faults change
ENVELOPE_MUTANTS = [
    Mutant("card_unchecked", agreement_kills(ignoring("card "))),
    Mutant("record_type_unchecked", agreement_kills(ignoring("record_type "))),
    Mutant("licence_evidence_unchecked", agreement_kills(ignoring("licence.evidence "))),
    Mutant("known_sections_unchecked", agreement_kills(ignoring("body.sections."))),
    Mutant("extensions_unchecked", agreement_kills(ignoring("body.extensions "))),
    Mutant("scope_model_unchecked", agreement_kills(ignoring("body.scope.model"))),
    Mutant("unknown_sections_checked", agreement_kills(adding(_unknown_sections_checked))),
    Mutant("specimens_checked", agreement_kills(adding(_specimens_checked))),
    Mutant("interface_bodies_checked", agreement_kills(adding(_interface_bodies_checked))),
    Mutant("base_patterns_checked", agreement_kills(adding(_base_patterns_checked))),
    Mutant("schema_version_pattern_checked", agreement_kills(adding(_schema_version_checked))),
    Mutant("null_taken_as_absent", agreement_kills(envelope_problems), _null_as_absent),
    Mutant(
        "id_pattern_searched",
        agreement_kills(envelope_problems),
        setting_item(ENVELOPE, "id", Searched(RECORD_ID)),
    ),
    Mutant(
        "content_hash_in_any_case",
        agreement_kills(envelope_problems),
        setting_item(ENVELOPE, "content_hash", re.compile(CONTENT_HASH.pattern, re.IGNORECASE)),
    ),
    Mutant(
        "version_with_leading_zeros",
        agreement_kills(envelope_problems),
        setting_item(ENVELOPE, "version", re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")),
    ),
]


# Versions with one fault: ordered otherwise than by length and then digits, or parsed by another pattern.


def pairs(size: Size) -> st.SearchStrategy[records.VersionPair]:
    return records.version_pairs()


def texts(size: Size) -> st.SearchStrategy[str]:
    return records.near_versions()


def ordered_by(key: Callable[[Version], tuple[object, ...]]) -> Callable[[pytest.MonkeyPatch], None]:
    return lambda monkeypatch: monkeypatch.setattr(Version, "_key", key)


def _parts(version: Version) -> tuple[str, str, str]:
    return (version.major, version.minor, version.patch)


ORDER_KILLS = killed_by(pairs, lambda pair: version_properties.check_order(parse_version, pair))
PARSE_KILLS = killed_by(texts, lambda text: version_properties.check_parse(parse_version, text))
VERSION_MUTANTS = [
    Mutant("versions_ordered_as_strings", ORDER_KILLS, ordered_by(_parts)),
    Mutant(
        "versions_ordered_by_length",
        ORDER_KILLS,
        ordered_by(lambda version: tuple(map(len, _parts(version)))),
    ),
    Mutant(
        "versions_ordered_as_doubles",
        ORDER_KILLS,
        ordered_by(lambda version: tuple(map(float, _parts(version)))),
    ),
    Mutant(
        "versions_of_any_unicode_digit",
        PARSE_KILLS,
        setting(identifiers, "VERSION", re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")),
    ),
    Mutant(
        "versions_with_leading_zeros",
        PARSE_KILLS,
        setting(identifiers, "VERSION", re.compile(r"(\d+)\.(\d+)\.(\d+)", re.A)),
    ),
    Mutant("versions_searched", PARSE_KILLS, setting(identifiers, "VERSION", Searched(identifiers.VERSION))),
]

# Reads with one fault: a function of the core wrapped or replaced, the rest of it as it is.

CANDIDATE = resolve._candidate  # pyright: ignore[reportPrivateUsage]  # the function the faults wrap


def _pinned(ref: MaterialRef, store: RecordStore) -> list[Record]:
    return [
        copy for copy in store.get(ref.id, ref.version) if copy.value.get("content_hash") == ref.content_hash
    ]


def _first_pinned_copy(ref: MaterialRef, store: RecordStore) -> Record | Reason:
    pinned = _pinned(ref, store)
    return pinned[0] if pinned else CANDIDATE(ref, store)


def _identical_copies_refused(ref: MaterialRef, store: RecordStore) -> Record | Reason:
    return Reason("malformed") if len(_pinned(ref, store)) > 1 else CANDIDATE(ref, store)


def ill_formed_hash_counted(of_the_id_only: bool) -> Callable[[MaterialRef, RecordStore], Record | Reason]:
    """Step 1 counting an ill-formed hash of any candidate, or of any version of the reference's id."""

    def candidate(ref: MaterialRef, store: RecordStore) -> Record | Reason:
        found = CANDIDATE(ref, store)
        candidates = [
            record
            for (id_, _), records in vars(store)["_candidates"].items()
            if id_ == ref.id or not of_the_id_only
            for record in records
        ]
        ill_formed = any(
            not CONTENT_HASH.fullmatch(str(record.value.get("content_hash"))) for record in candidates
        )
        return Reason("malformed") if found == Reason("pin_mismatch") and ill_formed else found

    return candidate


def _unreadable_refuses_every_read(ref: MaterialRef, store: RecordStore) -> Record | Reason:
    return Reason("malformed") if store.unparsed() else CANDIDATE(ref, store)


def _raising_on_arrays(monkeypatch: pytest.MonkeyPatch) -> None:
    add = RecordStore.add

    def add_or_raise(self: RecordStore, source: str, data: bytes) -> None:
        if isinstance(jsonio.parse(data), list):
            raise IndexError("an array source")
        add(self, source, data)

    monkeypatch.setattr(RecordStore, "add", add_or_raise)


def _refusals_raising(reasons: tuple[Reason, ...], labels: tuple[str, ...] = ()) -> ReadResult:
    raise NotImplementedError("a refusal")


def _strict_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    target = read._target  # pyright: ignore[reportPrivateUsage]  # the function the fault wraps

    def strict(value: JsonValue, found: list[Reason]) -> tuple[MaterialRef, str] | None:
        if isinstance(value, dict) and set(value) - {"record", "field"}:
            found.append(Reason("request_incomplete", detail="a member the shape does not name"))
        return target(value, found)

    monkeypatch.setattr(read, "_target", strict)


def _claims_unchecked(claims: Collection[Suite]) -> None:
    pass


def _no_unreadable_source(self: RecordStore) -> list[tuple[str, Reason]]:
    return []


def listing_without(step: str) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection that lists the candidates passing steps 2, 3 and 5 but `step`, the name of its refusal."""

    def listed(self: RecordStore) -> list[Record]:
        refusals = [name for name in ("version_refusal", "envelope_refusal", "type_refusal") if name != step]
        candidates = [record for records in vars(self)["_candidates"].values() for record in records]
        return [record for record in candidates if all(getattr(record, name) is None for name in refusals)]

    return setting(RecordStore, "list_records", listed)


def worlds(size: Size) -> st.SearchStrategy[stores.World]:
    return stores.worlds()


def shuffled(size: Size) -> st.SearchStrategy[read_properties.Shuffled]:
    return read_properties.shuffled()


ORDER_LAW = killed_by(shuffled, read_properties.check_order_and_copies)
UNREADABLE_LAW = killed_by(lambda size: read_properties.with_unreadables(), read_properties.check_unreadable)
LISTING_LAW = killed_by(worlds, read_properties.check_listed)
OTHER_IDENTITY_LAW = killed_by(
    lambda size: read_properties.with_others(), read_properties.check_other_identity
)
READ_MUTANTS = [
    Mutant(
        "raises_on_an_array_source",
        killed_by(worlds, read_properties.check_one_read, IndexError),
        _raising_on_arrays,
    ),
    Mutant(
        "refusals_raise_not_implemented",
        killed_by(worlds, read_properties.check_one_read),
        setting(read, "_refused", _refusals_raising),
    ),
    Mutant(
        "reasons_repeated", killed_by(worlds, read_properties.check_one_read), setting(read, "merged", tuple)
    ),
    Mutant(
        "claims_without_plain_read_accepted",
        killed_by(worlds, read_properties.check_one_read),
        setting(read, "_check", _claims_unchecked),
    ),
    Mutant("first_pinned_copy_read", ORDER_LAW, setting(resolve, "_candidate", _first_pinned_copy)),
    Mutant("identical_copies_refused", ORDER_LAW, setting(resolve, "_candidate", _identical_copies_refused)),
    Mutant(
        "ill_formed_hash_of_another_id_counts",
        OTHER_IDENTITY_LAW,
        setting(resolve, "_candidate", ill_formed_hash_counted(of_the_id_only=False)),
    ),
    Mutant(
        "ill_formed_hash_of_another_version_counts",
        OTHER_IDENTITY_LAW,
        setting(resolve, "_candidate", ill_formed_hash_counted(of_the_id_only=True)),
    ),
    Mutant(
        "unreadable_sources_ignored", UNREADABLE_LAW, setting(RecordStore, "unparsed", _no_unreadable_source)
    ),
    Mutant(
        "unreadable_source_refuses_every_read",
        UNREADABLE_LAW,
        setting(resolve, "_candidate", _unreadable_refuses_every_read),
    ),
    Mutant(
        "unnamed_members_refused",
        killed_by(lambda size: read_properties.unnamed_requests(), read_properties.check_unnamed),
        _strict_targets,
    ),
    Mutant("listing_skips_the_version", LISTING_LAW, listing_without("version_refusal")),
    Mutant("listing_skips_the_envelope", LISTING_LAW, listing_without("envelope_refusal")),
    Mutant("listing_skips_the_type", LISTING_LAW, listing_without("type_refusal")),
]

RECORD_MUTANTS = ENVELOPE_MUTANTS + VERSION_MUTANTS + READ_MUTANTS


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", RECORD_MUTANTS, ids=[mutant.name for mutant in RECORD_MUTANTS])
def test_the_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    mutant.inject(monkeypatch)
    record_property("examples_to_kill", mutant.search(size))

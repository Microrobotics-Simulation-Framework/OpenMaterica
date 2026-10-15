# SPDX-License-Identifier: Apache-2.0
"""(6) Laws of a read up to step 5 (`read_side_contract.md` sections 1 to 3), over stores drawn near each case
of step 1. The mutants they kill are in `test_record_mutants.py`.

Every check reads through `check_read`, so every law also holds the first two: a read never raises, except
`NotImplementedError` once its target has resolved and the steps not built yet would read the field, and
`ValueError` for claims without plain read, a misuse; and a reason appears at most once per code and
condition. The records drawn here hold no field a request names, so a read whose target resolves ends at step
7 with `absent`, or raises for an overlay's; `test_value_field_properties.py` reads fields.
"""

import copy
import json
from collections.abc import Sequence
from typing import NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core.identifiers import CONTENT_HASH, MaterialRef
from materica.core.jsonio import JsonValue
from materica.core.read import ReadRequest, read
from materica.core.reasons import Reason
from materica.core.record import RecordStore
from materica.core.resolve import Refused, ResolvedRecord, resolve_record
from tests.property import records, stores
from tests.property.stores import World
from tests.property.strategies import SIZE
from tests.property.support import feature

PAST_STEP_5 = "past step 5"
MISUSE = "misuse"


class Outcome(NamedTuple):
    status: str  # the result's; PAST_STEP_5 where the read went on to the steps not built yet; or MISUSE
    reasons: tuple[tuple[str, str], ...]  # code and condition, sorted
    labels: tuple[str, ...]


def store_of(sources: Sequence[bytes]) -> RecordStore:
    store = RecordStore()
    for index, data in enumerate(sources):
        store.add(f"source {index}", data)
    return store


def check_read(world: World) -> Outcome:
    """The read's outcome, after checking that it did not raise but where it may, and that no reason is given
    twice."""
    store = store_of(world.sources)
    if "plain_read" not in world.claims:
        try:
            read(world.request, store, claims=world.claims)
        except ValueError as error:
            refused = "plain_read" in str(error)
        else:
            refused = False
        assert refused, "claims without plain read, which every reader claims, were taken"
        return Outcome(MISUSE, (), ())
    try:
        result = read(world.request, store, claims=world.claims)
    except NotImplementedError:
        checked = ReadRequest.from_json(world.request, world.claims)
        assert isinstance(checked, ReadRequest)
        assert isinstance(checked.target, MaterialRef)
        assert isinstance(resolve_record(checked.target, store, world.claims), ResolvedRecord), "raised early"
        return Outcome(PAST_STEP_5, (), ())
    keys = [(reason.code, reason.condition or "") for reason in result.reasons]
    assert len(set(keys)) == len(keys), f"a reason given twice: {keys}"
    return Outcome(result.status, tuple(sorted(keys)), tuple(sorted(result.labels)))


ABSENT = (("absent", ""),)
PIN_MISMATCH = (("pin_mismatch", ""),)
MALFORMED = Outcome("not_met", (("malformed", ""),), ())


def resolves(world: World) -> bool:
    """Whether the request passes step 0 and its target passes steps 1 to 5."""
    checked = ReadRequest.from_json(world.request, world.claims)
    return isinstance(checked, ReadRequest) and isinstance(
        resolve_record(checked.target, store_of(world.sources), world.claims), ResolvedRecord
    )


def outcome_features(outcome: Outcome, world: World) -> None:
    """The reasons' codes, and whether the read went past step 5: on to a step not built yet, or to step 7,
    which finds no field the drawn records hold."""
    past = outcome.status == PAST_STEP_5 or (outcome.reasons == ABSENT and resolves(world))
    feature(PAST_STEP_5.replace(" ", "_"), past)
    for code in {code for code, _ in outcome.reasons}:
        feature(code)


# Least shares, measured at both sizes, of the outcomes every law's worlds give.
OUTCOMES = {
    "past_step_5": 0.027,
    "absent": 0.017,
    "malformed": 0.12,
    "pin_mismatch": 0.024,
    "hash_mismatch": 0.004,
    "other_version": 0.002,
    "unknown_type": 0.008,
    "request_incomplete": 0.04,
    "request_unit_mismatch": 0.008,
    "want_mismatch": 0.03,
}


# (a, f) A read never raises, and gives each reason once.


def check_one_read(world: World) -> None:
    check_read(world)


@pytest.mark.features(
    **OUTCOMES, **{f"case_{case}": 0.047 for case in stores.CASES}, hash_not_checked=0.003, misuse=0.04
)
@given(stores.worlds())
def test_a_read_never_raises_and_gives_each_reason_once(world: World) -> None:
    outcome = check_read(world)
    outcome_features(outcome, world)
    feature(f"case_{world.case}")
    feature("hash_not_checked", "hash_not_checked" in outcome.labels)
    feature("misuse", outcome.status == MISUSE)


# (b) The order of the sources, and identical copies of them, change nothing.


class Shuffled(NamedTuple):
    world: World
    order: tuple[int, ...]  # the sources, permuted
    copies: tuple[int, ...]  # sources added again, byte for byte


@st.composite
def shuffled(draw: st.DrawFn) -> Shuffled:
    world = draw(stores.worlds())
    count = len(world.sources)
    copies = draw(st.lists(st.integers(0, count - 1), max_size=3)) if count else []
    return Shuffled(world, tuple(draw(st.permutations(range(count)))), tuple(copies))


def check_order_and_copies(shuffled: Shuffled) -> None:
    sources = [shuffled.world.sources[index] for index in (*shuffled.order, *shuffled.copies)]
    assert check_read(shuffled.world._replace(sources=tuple(sources))) == check_read(shuffled.world)


def differing_copies(sources: Sequence[bytes]) -> bool:
    """Whether two sources are copies of one record, stating one hash, that differ in their bytes."""
    store = store_of(sources)
    candidates = [record for record in store.list_records()] + [
        record for id_, version in stores.IDENTITIES for record in store.get(id_, version)
    ]
    stated = {
        (record.id, record.version, str(record.value.get("content_hash"))): record.data
        for record in candidates
    }
    return any(
        stated[(record.id, record.version, str(record.value.get("content_hash")))] != record.data
        for record in candidates
    )


@pytest.mark.features(**OUTCOMES, differing_copies=0.06, copies_added=0.14, reordered=0.16)
@given(shuffled())
def test_the_order_and_identical_copies_of_the_sources_change_nothing(shuffled: Shuffled) -> None:
    outcome_features(check_read(shuffled.world), shuffled.world)
    feature("differing_copies", differing_copies(shuffled.world.sources))
    feature("copies_added", bool(shuffled.copies))
    feature("reordered", list(shuffled.order) != sorted(shuffled.order))
    check_order_and_copies(shuffled)


# (c) A record of another identity, another id or another version of the target's, changes nothing: step 1
# looks only at the candidates of the reference's id and version.


class WithOther(NamedTuple):
    world: World
    other: stores.Stored


@st.composite
def with_others(draw: st.DrawFn) -> WithOther:
    world = draw(stores.worlds())
    target = tuple(records.at(world.request, ("target", "record", name)) for name in ("id", "version"))
    identities = tuple(
        identity for identity in (*stores.IDENTITIES, ("conformance/z", "1.0.0")) if identity != target
    )
    other = draw(stores.stored_records(identities))
    if draw(st.booleans()):
        # Half the others state an ill-formed hash, whatever else they are: step 1 weighs one only among the
        # candidates of the target's id and version.
        record = {**other.record, "content_hash": str(other.record["content_hash"]).upper()}
        other = other._replace(record=record, data=json.dumps(record).encode())
    return WithOther(world, other)


def check_other_identity(with_other: WithOther) -> None:
    world = with_other.world
    assert check_read(world._replace(sources=(*world.sources, with_other.other.data))) == check_read(world)


@pytest.mark.features(
    **OUTCOMES,
    **{f"other_{variant}": 0.018 for variant in stores.VARIANTS},
    other_version_of_the_id=0.07,
    other_hash_ill_formed=0.12,
)
@given(with_others())
def test_a_record_of_another_identity_changes_nothing(with_other: WithOther) -> None:
    outcome_features(check_read(with_other.world), with_other.world)
    feature(f"other_{with_other.other.variant}")
    target = records.at(with_other.world.request, ("target", "record", "id"))
    feature("other_version_of_the_id", with_other.other.record["id"] == target)
    feature("other_hash_ill_formed", not CONTENT_HASH.fullmatch(str(with_other.other.record["content_hash"])))
    check_other_identity(with_other)


# (d) An unreadable source turns only step 1's `absent` or `pin_mismatch` into `malformed`: a reference whose
# record is found is read whatever else is supplied, so step 7's `absent` stands.


class WithUnreadable(NamedTuple):
    world: World
    unreadable: bytes


def check_unreadable(with_unreadable: WithUnreadable) -> None:
    world = with_unreadable.world
    before = check_read(world)
    after = check_read(world._replace(sources=(*world.sources, with_unreadable.unreadable)))
    unresolved = before.reasons in (ABSENT, PIN_MISMATCH) and not resolves(world)
    assert after == (MALFORMED if unresolved else before), (before, after)


def with_unreadables() -> st.SearchStrategy[WithUnreadable]:
    return st.builds(WithUnreadable, stores.worlds(), st.sampled_from(stores.UNREADABLE))


@pytest.mark.features(**OUTCOMES)
@given(with_unreadables())
def test_an_unreadable_source_turns_only_absent_or_pin_mismatch_into_malformed(
    with_unreadable: WithUnreadable,
) -> None:
    outcome_features(check_read(with_unreadable.world), with_unreadable.world)
    check_unreadable(with_unreadable)


# (e) A request member its shape does not name changes nothing.

# The objects of a request whose members the shape names, so that a name of its own is one it does not.
OBJECTS: tuple[records.Place, ...] = (
    (),
    ("target",),
    ("target", "record"),
    ("requirement",),
    ("operating_conditions", "temperature"),
    ("requirement", "conditions", "temperature"),
    ("requirement", "conditions", "temperature", "tolerance"),
)


class Unnamed(NamedTuple):
    world: World
    additions: tuple[tuple[records.Place, str, JsonValue], ...]


ADDITIONS = st.tuples(
    st.sampled_from(OBJECTS), st.text(max_size=4).map("x-{}".format), records.trees(SIZE).values
)


def check_unnamed(unnamed: Unnamed) -> None:
    request = copy.deepcopy(unnamed.world.request)
    for place, name, value in unnamed.additions:
        records.changed(request, (*place, name), value)
    assert check_read(unnamed.world._replace(request=request)) == check_read(unnamed.world)


def unnamed_requests() -> st.SearchStrategy[Unnamed]:
    return st.builds(Unnamed, stores.worlds(), st.lists(ADDITIONS, min_size=1, max_size=4).map(tuple))


@pytest.mark.features(**OUTCOMES, **{f"added_at_{'.'.join(place) or 'top'}": 0.06 for place in OBJECTS})
@given(unnamed_requests())
def test_a_request_member_the_shape_does_not_name_changes_nothing(unnamed: Unnamed) -> None:
    outcome_features(check_read(unnamed.world), unnamed.world)
    for place, _, _ in unnamed.additions:
        feature(f"added_at_{'.'.join(place) or 'top'}")
    check_unnamed(unnamed)


# (g) Every record a listing gives, read under its own hash, passes steps 1 to 3 and 5: step 1 refuses it only
# where another copy states its hash and differs in its bytes.


def check_listed(world: World) -> None:
    store = store_of(world.sources)
    for record in store.list_records():
        ref = MaterialRef(record.id, record.version, str(record.value["content_hash"]))
        resolved = resolve_record(ref, store, {"plain_read"})
        copies = [
            copy
            for copy in store.get(record.id, record.version)
            if copy.value["content_hash"] == ref.content_hash
        ]
        if any(copy.data != record.data for copy in copies):
            assert resolved == Refused((Reason("malformed"),)), resolved
        else:
            assert isinstance(resolved, ResolvedRecord), resolved


@pytest.mark.features(listed=0.19, listed_two=0.08, listed_stale=0.045, listed_copies_differ=0.04)
@given(stores.worlds())
def test_every_listed_record_resolves_under_its_own_hash(world: World) -> None:
    listed = store_of(world.sources).list_records()
    feature("listed", bool(listed))
    feature("listed_two", len(listed) >= 2)
    feature("listed_stale", any(record.value["content_hash"] in stores.STALE for record in listed))
    feature("listed_copies_differ", differing_copies(world.sources) and bool(listed))
    check_listed(world)

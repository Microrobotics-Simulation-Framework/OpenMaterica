# SPDX-License-Identifier: Apache-2.0
"""Properties of the content hash (`record_format.md` section 9). The mutants they kill are in
`test_mutants.py`."""

import copy
import random
from collections.abc import Callable
from typing import NamedTuple

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from materica.core import jsonio
from materica.core.canonical import canonicalize
from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from tests.property import strategies
from tests.property.strategies import SIZE, Size
from tests.property.support import feature

Digest = Callable[[JsonValue], str]
Path = tuple[str | int, ...]

TOP_LEVEL_REMOVED = ("content_hash", "card")
REMOVED_IN_PROVENANCE = ("review", "copy")
NEAR_MISSES = ("Provenance", "Review", "reviews", "content-hash")
# The names the hash treats apart, and near misses of them, come up at every depth, beside any text.
NAMES = st.one_of(
    st.sampled_from(["provenance", *TOP_LEVEL_REMOVED, *REMOVED_IN_PROVENANCE, *NEAR_MISSES]),
    st.text(max_size=3),
)


def trees(size: Size) -> st.SearchStrategy[JsonValue]:
    return strategies.json_values(names=NAMES, size=size)


def objects(size: Size) -> st.SearchStrategy[dict[str, JsonValue]]:
    return st.lists(st.tuples(NAMES, trees(size)), max_size=size.members).map(dict[str, JsonValue])


@st.composite
def records(draw: st.DrawFn, size: Size = SIZE) -> JsonValue:
    """Objects holding a provenance object and a scalar `name`, so that each has a leaf the hash covers, and
    up to `size.members` members beside each, every one a tree within `size`.

    Half of them also hold a provenance object inside an array, and a quarter one inside a provenance that
    is an array: shapes section 9 item 1 tells apart, which random trees seldom reach. In half of them the
    provenance object holds a `card` or a `content_hash`, which the hash keeps below the top.
    """
    record: dict[str, JsonValue] = {**draw(objects(size)), "name": draw(strategies.SCALARS)}
    provenance = draw(objects(size))
    if draw(st.booleans()):
        provenance[draw(st.sampled_from(TOP_LEVEL_REMOVED))] = draw(trees(size))
    record["provenance"] = provenance
    placement = draw(st.integers(0, 3))
    if placement:
        items = draw(st.lists(trees(size), max_size=size.members))
        items.insert(draw(st.integers(0, len(items))), {"provenance": draw(objects(size))})
        record["held" if placement == 2 else "items"] = {"provenance": items} if placement == 2 else items
    return record


# A record with more members than small trees draw, holding every name the hash treats apart: at the top,
# nested, inside and outside provenance objects, in later array items, and four deep.
MANY: JsonValue = {
    **{f"member {index}": float(index) for index in range(40)},
    "name": "many",
    "card": "prose",
    "content_hash": "sha256:stated",
    "review": {"kept": 1.0},
    "Provenance": {"review": "kept"},
    "nested": {"card": "kept", "content_hash": "kept"},
    "provenance": {
        "review": "removed",
        "copy": [1.0],
        "evidence": {"items": [{"review": 1.0}, {"later": {"copy": 2.0}}]},
        "deep": {"a": {"b": {"review": "removed four deep"}}},
    },
    "values": [
        {"provenance": {"review": "removed"}},
        {"provenance": [{"provenance": {"copy": "removed"}}, {"review": "kept"}]},
    ],
}


class Place(NamedTuple):
    """Where an object sits, as section 9 item 1 tells removal apart."""

    depth: int = 0  # 0 outside provenance objects; 1 for a provenance's object value; one more for each level
    later_item: bool = False  # inside provenance, through an array item after the first
    in_array: bool = False  # outside provenance, below an array
    under_non_object: bool = False  # outside provenance, below a provenance whose value is not an object
    opened_in_array: bool = False  # its provenance object sits below an array
    opened_under_non_object: bool = False  # its provenance object sits below a non-object provenance


OUTSIDE = Place()


def provenance_objects(value: JsonValue, place: Place = OUTSIDE) -> list[tuple[dict[str, JsonValue], Place]]:
    """Every object that is a provenance's value, or lies inside one, with its place."""
    found: list[tuple[dict[str, JsonValue], Place]] = []
    if isinstance(value, dict):
        if place.depth:
            found.append((value, place))
        for name, member in value.items():
            if place.depth:
                below = place._replace(depth=place.depth + 1)
            elif name == "provenance" and isinstance(member, dict):
                below = place._replace(
                    depth=1, opened_in_array=place.in_array, opened_under_non_object=place.under_non_object
                )
            elif name == "provenance":
                below = place._replace(under_non_object=True)
            else:
                below = place
            found += provenance_objects(member, below)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if place.depth:
                below = place._replace(depth=place.depth + 1, later_item=place.later_item or index > 0)
            else:
                below = place._replace(in_array=True)
            found += provenance_objects(item, below)
    return found


def names_with_depth(value: JsonValue, depth: int = 1) -> list[tuple[str, int]]:
    if isinstance(value, list):
        return [found for item in value for found in names_with_depth(item, depth + 1)]
    if isinstance(value, dict):
        return [(name, depth) for name in value] + [
            found for member in value.values() for found in names_with_depth(member, depth + 1)
        ]
    return []


def _most_members(value: JsonValue) -> int:
    if isinstance(value, list):
        return max((_most_members(item) for item in value), default=0)
    if isinstance(value, dict):
        return max([len(value), *(_most_members(member) for member in value.values())])
    return 0


def names_inside_provenance(value: JsonValue, inside: bool = False) -> list[tuple[str, bool]]:
    """Every member name, and whether its object lies inside a provenance object."""
    if isinstance(value, list):
        return [found for item in value for found in names_inside_provenance(item, inside)]
    if isinstance(value, dict):
        return [(name, inside) for name in value] + [
            found
            for name, member in value.items()
            for found in names_inside_provenance(
                member, inside or (name == "provenance" and isinstance(member, dict))
            )
        ]
    return []


def record_features(record: JsonValue) -> None:
    found = provenance_objects(record)
    names = names_with_depth(record)
    feature("card_below_the_top", any(name in TOP_LEVEL_REMOVED and depth > 1 for name, depth in names))
    feature("near_miss_name", any(name in NEAR_MISSES for name, _ in names))
    placed = names_inside_provenance(record)
    inside = {name for name, within in placed if within and name in REMOVED_IN_PROVENANCE}
    outside = {name for name, within in placed if not within and name in REMOVED_IN_PROVENANCE}
    feature("review_inside_and_outside_provenance", bool(inside and outside))
    feature("provenance_in_an_array", any(place.opened_in_array for _, place in found))
    feature("provenance_in_a_non_object_provenance", any(place.opened_under_non_object for _, place in found))
    feature("three_members_to_sort", _most_members(record) >= 3)


def parsed(text: str) -> JsonValue:
    value = jsonio.parse(text.encode("utf-8"))
    assert not isinstance(value, Reason), value
    return value


# The invariance laws: the hash does not change when the record is written another way, its members are
# reordered, a card is added, or `review` or `copy` is added anywhere inside a provenance object. One record
# is drawn for all four, and each law fails with its own message.


class Variants(NamedTuple):
    record: JsonValue
    writings: tuple[str, str]
    reordered: JsonValue
    new_card: JsonValue
    reviewed: JsonValue
    places: tuple[Place, ...]  # where `review` or `copy` was added


def _reordered(order: random.Random, value: JsonValue) -> JsonValue:
    if isinstance(value, list):
        return [_reordered(order, item) for item in value]
    if isinstance(value, dict):
        names = list(value)
        order.shuffle(names)
        return {name: _reordered(order, value[name]) for name in names}
    return value


def variants_of(
    record: JsonValue, writing: random.Random, card: JsonValue, reviewed: JsonValue, places: tuple[Place, ...]
) -> Variants:
    assert isinstance(record, dict)
    writings = (strategies.render(writing, record), strategies.render(writing, record))
    return Variants(record, writings, _reordered(writing, record), {**record, "card": card}, reviewed, places)


@st.composite
def variants(draw: st.DrawFn, size: Size = SIZE) -> Variants:
    record = draw(records(size))
    reviewed = copy.deepcopy(record)
    places: list[Place] = []
    for _ in range(draw(st.integers(1, 3))):
        found = provenance_objects(reviewed)
        target, place = found[draw(st.integers(0, len(found) - 1))]
        target[draw(st.sampled_from(REMOVED_IN_PROVENANCE))] = draw(trees(size))
        places.append(place)
    return variants_of(record, draw(strategies.WRITINGS), draw(trees(size)), reviewed, tuple(places))


def every_place_reviewed(record: JsonValue) -> Variants:
    """`record`'s variants, with `review` added to every object inside a provenance object."""
    reviewed = copy.deepcopy(record)
    found = provenance_objects(reviewed)
    for target, _ in found:
        target["review"] = "added"
    return variants_of(record, random.Random(0), "a new card", reviewed, tuple(place for _, place in found))


def check_invariance(
    digest: Digest, variants: Variants, hash_text: Callable[[str], str] | None = None
) -> None:
    expected = digest(variants.record)
    for text in variants.writings:
        written = hash_text(text) if hash_text is not None else digest(parsed(text))
        assert written == expected, "writing the record another way changed its hash"
    assert digest(variants.reordered) == expected, "reordering members changed the hash"
    assert digest(variants.new_card) == expected, "a new card changed the hash"
    assert digest(variants.reviewed) == expected, "review or copy added inside a provenance object changed it"


# Each feature whose least share failed a `dev` run too often is declared by its chance: its share at `ci`
# over 64 runs (2026-10-15), rounded down to two places. From the measured clusters, those least shares failed
# a `dev` run with a probability of about 6.5e-5 (at most 6e-3; `audits.JUDGED_FROM`); neither is judged at
# `dev` now, and at `ci` each falls below its draw floor with a probability below 1e-20. Over 48 runs on main
# (2026-10-20, derandomised, each its own stream) their least shares were 0.386 and 0.395, below the chances;
# since `records` holds a provenance object in an array in half its records, and a `card` or `content_hash`
# in its provenance object in half, they show in 0.717 and 0.645 of the examples, least 0.655 and 0.588 over
# 48 runs, and fall below their floors with a probability below 1e-26 by `audits.py`'s model.
@pytest.mark.chances(card_below_the_top=0.44, provenance_in_an_array=0.46)
@pytest.mark.features(
    near_miss_name=0.20,
    review_inside_and_outside_provenance=0.05,
    provenance_in_a_non_object_provenance=0.06,
    three_members_to_sort=0.25,
    review_or_copy_added_three_deep=0.08,
    review_or_copy_added_in_a_later_item=0.03,
)
@example(every_place_reviewed(MANY))
@given(variants())
def test_the_hash_ignores_what_it_leaves_out(variants: Variants) -> None:
    record_features(variants.record)
    feature("review_or_copy_added_three_deep", any(place.depth >= 3 for place in variants.places))
    feature("review_or_copy_added_in_a_later_item", any(place.later_item for place in variants.places))
    check_invariance(content_hash, variants)


# The sensitivity law: editing any leaf the hash covers, at a path drawn at random, changes the hash. It is
# the property that shows the hash can fail.


class Edit(NamedTuple):
    original: JsonValue
    edited: JsonValue
    path: Path


def leaves(value: JsonValue, path: Path = ()) -> list[Path]:
    """The paths of the scalars and empty containers in `value`."""
    if isinstance(value, list) and value:
        return [leaf for index, item in enumerate(value) for leaf in leaves(item, (*path, index))]
    if isinstance(value, dict) and value:
        return [leaf for name, member in value.items() for leaf in leaves(member, (*path, name))]
    return [path]


def removed(root: JsonValue, path: Path) -> bool:
    """Whether section 9 item 1 removes the leaf at `path`, read from the path as the item words it."""
    nodes = _nodes(root, path)
    if isinstance(root, dict) and path and path[0] in TOP_LEVEL_REMOVED:
        return True
    inside_provenance = False
    for index, step in enumerate(path):
        if isinstance(nodes[index], dict):
            if inside_provenance and step in REMOVED_IN_PROVENANCE:
                return True
            if step == "provenance" and isinstance(nodes[index + 1], dict):
                inside_provenance = True
    return False


def _nodes(root: JsonValue, path: Path) -> list[JsonValue]:
    """The values along `path`, from `root` to the leaf."""
    nodes = [root]
    for step in path:
        node = nodes[-1]
        if isinstance(node, dict) and isinstance(step, str):
            nodes.append(node[step])
        else:
            assert isinstance(node, list)
            assert isinstance(step, int)
            nodes.append(node[step])
    return nodes


def edit_at(original: JsonValue, path: Path, new: JsonValue) -> Edit:
    if canonicalize(new) == canonicalize(_nodes(original, path)[-1]):
        new = "edited" if new != "edited" else "edited again"
    edited = copy.deepcopy(original)
    parent, step = _nodes(edited, path)[-2], path[-1]
    if isinstance(parent, dict) and isinstance(step, str):
        parent[step] = new
    else:
        assert isinstance(parent, list)
        assert isinstance(step, int)
        parent[step] = new
    return Edit(original, edited, path)


def provenances_opened(root: JsonValue, path: Path) -> list[bool]:
    """For each `provenance` along `path`, whether its value is an object, which item 1 opens."""
    nodes = _nodes(root, path)
    return [isinstance(nodes[index + 1], dict) for index, step in enumerate(path) if step == "provenance"]


def below_review_or_copy_in_a_non_object_provenance(root: JsonValue, path: Path) -> bool:
    """Whether the leaf at `path` lies below a `review` or `copy` member of an object inside a provenance
    whose value is not an object: the hash keeps it, since item 1 removes the two names inside a provenance
    object alone."""
    nodes = _nodes(root, path)
    in_a_non_object_provenance = False
    for index, step in enumerate(path):
        if isinstance(nodes[index], dict):
            if in_a_non_object_provenance and step in REMOVED_IN_PROVENANCE:
                return True
            if step == "provenance" and not isinstance(nodes[index + 1], dict):
                in_a_non_object_provenance = True
    return False


def placed_below_a_non_object_provenance(
    draw: st.DrawFn,
    record: dict[str, JsonValue],
    member: str,
    size: Size,
    inside: st.SearchStrategy[JsonValue] | None = None,
    only_kept: bool = True,
) -> Edit:
    """`record` given `member`, `{"provenance": [...]}`, whose array holds, among other items and up to two
    arrays deep, an object with `review` or `copy`; and an edit of a leaf below that name the hash keeps (or,
    with `only_kept=False`, of any leaf below it). `inside` draws the tree below the name (`trees(size)` where
    none is given)."""
    name = draw(st.sampled_from(REMOVED_IN_PROVENANCE))
    node: JsonValue = {**draw(objects(size)), name: draw(trees(size) if inside is None else inside)}
    below: Path = (name,)
    for _ in range(draw(st.integers(0, 2))):
        node, below = [node], (0, *below)
    items = draw(st.lists(trees(size), max_size=size.members))
    index = draw(st.integers(0, len(items)))
    items.insert(index, node)
    record[member] = {"provenance": items}
    prefix: Path = (member, "provenance", index, *below)
    # A leaf the hash keeps: one below a provenance object nested in the tree is removed with it, and where
    # every leaf is, the whole of `review` or `copy` is the edit.
    below_the_prefix = [leaf for leaf in leaves(record) if leaf[: len(prefix)] == prefix]
    kept = [leaf for leaf in below_the_prefix if not removed(record, leaf)]
    path = draw(st.sampled_from((kept or [prefix]) if only_kept else below_the_prefix))
    return edit_at(record, path, draw(strategies.SCALARS))


@st.composite
def edits_below_a_non_object_provenance(
    draw: st.DrawFn,
    size: Size,
    inside: st.SearchStrategy[JsonValue] | None = None,
    only_kept: bool = True,
) -> Edit:
    """A record whose `held` is a provenance that is an array (`placed_below_a_non_object_provenance`), and an
    edit below a `review` or `copy` in it: the planned search of `a_non_object_provenance_opens`
    (`test_mutants.py`). `inside` and `only_kept=False` are for `test_mutant_view.py`, which plans draws that
    reach a leaf the hash removes, to show its control refuses the strategy without the filter."""
    record = draw(records(size))
    assert isinstance(record, dict)
    return placed_below_a_non_object_provenance(draw, record, "held", size, inside, only_kept)


# Where an edit below `review` or `copy` in a provenance that is not an object is placed beside the record's
# own members: longer than any name `NAMES` draws, so that no member is replaced.
BESIDE = "beside the record"


@st.composite
def edits(draw: st.DrawFn, size: Size = SIZE) -> Edit:
    """An edit of a leaf the hash covers, at a path drawn at random. In about three draws in ten of those
    outside every provenance object (0.26 of the examples, measured), the record is given a provenance that is
    an array and the edit is of a leaf below a `review` or `copy` in it
    (`placed_below_a_non_object_provenance`), which a path drawn at random reaches in about one draw in 200:
    the edits inside a provenance object, and the record's own members, are as drawn."""
    original = draw(records(size))
    path = draw(st.sampled_from([path for path in leaves(original) if not removed(original, path)]))
    if not any(provenances_opened(original, path)) and draw(st.integers(0, 5)) == 0:
        assert isinstance(original, dict)
        return placed_below_a_non_object_provenance(draw, original, BESIDE, size)
    return edit_at(original, path, draw(strategies.SCALARS))


def check_edit(digest: Digest, edit: Edit) -> None:
    assert digest(edit.original) != digest(edit.edited), f"editing {edit.path} left the hash unchanged"


# As above: those least shares failed a `dev` run with a probability of about 1.8e-4 (at most 1e-2). Over 48
# runs on main (2026-10-20) the least shares of the first, second, third and fourth were 0.419, 0.426, 0.3335
# and 0.295, below their chances (with the two of the property above, six chances lay above their least
# shares); with `records` as above, the four show in 0.727, 0.643, 0.590 and 0.387 of the
# examples, least 0.678, 0.593, 0.536 and 0.345 over 48 runs, and fall below their floors with a probability
# below 1e-10 by `audits.py`'s model.
@pytest.mark.chances(
    card_below_the_top=0.46,
    provenance_in_an_array=0.46,
    edited_below_a_kept_special_name=0.36,
    edited_inside_a_provenance_object=0.33,
    # Where `a_non_object_provenance_opens` shows, below its least share over 48 runs at `ci` (2026-10-20,
    # derandomised, each its own stream; mean 0.257, least 0.218). By `audits.py`'s model, 250 draws each
    # shown in 5 examples, a run falls below its floor of 95 examples with a probability of 5e-14, and with
    # 1e-38 at the variance measured (3.7 times a binomial count's).
    edited_below_review_or_copy_in_a_non_object_provenance=0.18,
)
@pytest.mark.features(
    near_miss_name=0.20,
    review_inside_and_outside_provenance=0.05,
    provenance_in_a_non_object_provenance=0.06,
    three_members_to_sort=0.25,
    edited_below_a_non_object_provenance=0.03,
)
@example(edit_at(MANY, ("nested", "card"), "edited"))
@example(edit_at(MANY, ("review", "kept"), 2.0))
@example(edit_at(MANY, ("values", 1, "provenance", 1, "review"), "edited"))
@given(edits())
def test_editing_any_leaf_the_hash_covers_changes_it(edit: Edit) -> None:
    record_features(edit.original)
    special = (*TOP_LEVEL_REMOVED, *REMOVED_IN_PROVENANCE, *NEAR_MISSES)
    feature("edited_below_a_kept_special_name", any(step in special for step in edit.path))
    opened = provenances_opened(edit.original, edit.path)
    feature("edited_inside_a_provenance_object", any(opened))
    feature("edited_below_a_non_object_provenance", not all(opened))
    feature(
        "edited_below_review_or_copy_in_a_non_object_provenance",
        below_review_or_copy_in_a_non_object_provenance(edit.original, edit.path),
    )
    check_edit(content_hash, edit)

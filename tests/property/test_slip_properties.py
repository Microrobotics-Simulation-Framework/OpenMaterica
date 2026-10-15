# SPDX-License-Identifier: Apache-2.0
"""(9) The one-slip relation (`core/slips.py`, `record_format.md` section 10), against a neighbour generator
written from section 10's list of slips, which builds names from a name instead of comparing two: `one_slip`
finds a slip between two names exactly where the generator reaches one from the other, and names a kind it
reaches it by. The read (step 0 and step 8) and the name-overlap check share the relation, so a fault in it
is a fault of both; the generator is the oracle neither shares (the S2a-1 review, verdict 19).

The mutants it kills are in `test_mutants.py`.
"""

from collections.abc import Iterator
from typing import NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core import slips
from tests.property.support import feature

SUBSTITUTED = "a character substituted"
ADDED = "a character added"
UNDERSCORE = "an underscore added"
SWAPPED = "two characters swapped"
PLURAL = "singular or plural"
# Section 10's irregular plurals, as the text lists them.
IRREGULAR = (("datum", "data"), ("index", "indices"), ("matrix", "matrices"))


def plurals(word: str) -> Iterator[str]:
    """The plurals of a word section 10 lists: `s` or `es` added, a final `y` made `ies`, and the irregular
    ones."""
    yield word + "s"
    yield word + "es"
    if word.endswith("y"):
        yield word[:-1] + "ies"
    yield from (plural for singular, plural in IRREGULAR if singular == word)


def built(name: str, alphabet: str) -> Iterator[tuple[str, str]]:
    """Each name one slip of section 10 builds from `name`, with the slip's kind: a character of `alphabet`
    substituted or inserted, two adjacent characters swapped, or a word, between underscores and not empty,
    made plural or singular."""
    for index, here in enumerate(name):
        for character in alphabet:
            if character != here:
                yield name[:index] + character + name[index + 1 :], SUBSTITUTED
    for index in range(len(name) + 1):
        for character in alphabet:
            yield name[:index] + character + name[index:], UNDERSCORE if character == "_" else ADDED
    for index in range(len(name) - 1):
        if name[index] != name[index + 1]:
            yield name[:index] + name[index + 1] + name[index] + name[index + 2 :], SWAPPED
    words = name.split("_")
    for index, word in enumerate(words):
        if word:
            singulars = [word[: -len(end)] for end in ("s", "es") if word.endswith(end)]
            if word.endswith("ies"):
                singulars.append(word[:-3] + "y")
            singulars += [singular for singular, plural in IRREGULAR if plural == word]
            for other in [*plurals(word), *singulars]:
                if other and other != word:
                    yield "_".join([*words[:index], other, *words[index + 1 :]]), PLURAL


def kinds(a: str, b: str) -> set[str]:
    """The kinds of slip by which the generator reaches `b` from `a`, or `a` from `b`; none where neither."""
    alphabet = "".join(sorted(set(a) | set(b)))
    return {kind for name, kind in built(a, alphabet) if name == b} | {
        kind for name, kind in built(b, alphabet) if name == a
    }


class Pair(NamedTuple):
    a: str
    b: str
    edits: int  # the slips `b` was drawn by, from `a`; 0 for an unrelated name


WORDS = (
    *("unit", "units", "basis", "box", "boxes", "body", "bodies", "datum", "data", "index", "indices"),
    *("matrix", "matrices", "value", "s", "es", "y", "ies"),
)
LETTERS = "abeisxy_"


@st.composite
def names(draw: st.DrawFn) -> str:
    """A name of words, as section 10's are, some of them a plural's; or, in one draw in three, of letters and
    underscores, empty words among them."""
    if draw(st.integers(0, 2)) == 0:
        return draw(st.text(LETTERS, max_size=8))
    return "_".join(draw(st.lists(st.sampled_from(WORDS), min_size=1, max_size=3)))


def slips_of(name: str) -> dict[str, list[str]]:
    """The names one slip of each kind builds from `name`, its characters from `LETTERS`, a character or an
    underscore deleted among them."""
    found: dict[str, list[str]] = {kind: [] for kind in (SUBSTITUTED, ADDED, UNDERSCORE, SWAPPED, PLURAL)}
    for built_name, kind in built(name, LETTERS):
        found[kind].append(built_name)
    for index, character in enumerate(name):
        found[UNDERSCORE if character == "_" else ADDED].append(name[:index] + name[index + 1 :])
    return found


@st.composite
def edited(draw: st.DrawFn, name: str) -> str:
    """`name` after one slip, its kind drawn first, each as often as another that `name` allows."""
    by_kind = {kind: names for kind, names in slips_of(name).items() if names}
    return draw(st.sampled_from(by_kind[draw(st.sampled_from(sorted(by_kind)))]))


def far_swaps(name: str) -> list[str]:
    """`name` with two differing characters swapped that are not adjacent: two slips, a near miss of one."""
    return [
        name[:i] + name[j] + name[i + 1 : j] + name[i] + name[j + 1 :]
        for i in range(len(name))
        for j in range(i + 2, len(name))
        if name[i] != name[j]
    ]


@st.composite
def pairs(draw: st.DrawFn) -> Pair:
    """A name, and another: one slip from it in half the draws, two slips or unrelated in a quarter each; of
    two slips, half are two characters swapped that are not adjacent, where the name allows it."""
    a = draw(names())
    edits = draw(st.sampled_from((1, 1, 0, 2)))
    if edits == 2 and far_swaps(a) and draw(st.booleans()):
        return Pair(a, draw(st.sampled_from(far_swaps(a))), edits)
    b = draw(names()) if edits == 0 else draw(edited(a))
    if edits == 2:
        b = draw(edited(b))
    return Pair(a, b, edits)


def check_one_slip(pair: Pair) -> None:
    found, expected = slips.one_slip(pair.a, pair.b), kinds(pair.a, pair.b)
    assert (found is None) == (not expected), (pair, found, expected)
    assert found is None or found in expected, (pair, found, expected)
    assert (slips.one_slip(pair.b, pair.a) is None) == (found is None), pair


# Least shares, about a third of the least measured at `ci` over four seeds.
@pytest.mark.features(
    substituted=0.021,
    added=0.048,
    underscore=0.018,
    swapped=0.012,
    plural=0.02,
    none=0.105,
    two_edits=0.042,
    far_swap=0.012,
)
@given(pairs())
def test_one_slip_is_what_the_neighbour_generator_reaches(pair: Pair) -> None:
    expected = kinds(pair.a, pair.b)
    for kind, name in ((SUBSTITUTED, "substituted"), (ADDED, "added"), (UNDERSCORE, "underscore")):
        feature(name, kind in expected)
    feature("swapped", SWAPPED in expected)
    feature("plural", PLURAL in expected)
    feature("none", not expected)
    feature("two_edits", pair.edits == 2)
    feature("far_swap", pair.b in far_swaps(pair.a))
    check_one_slip(pair)


def test_the_generator_reaches_section_10s_examples_and_no_further() -> None:
    """The oracle's own control: each kind reached as section 10's examples of it are, and two slips not."""
    assert kinds("unit", "unti") == {SWAPPED}
    assert kinds("unit", "units") == {ADDED, PLURAL}
    assert kinds("body", "bodies") == {PLURAL}
    assert kinds("datum", "data") == {PLURAL}
    assert kinds("plus_minus", "plusminus") == {UNDERSCORE}
    assert kinds("value", "vaule") == {SWAPPED}
    assert kinds("value", "valve") == {SUBSTITUTED}
    assert kinds("value", "vlaue_") == set()
    assert kinds("x__y", "x_es_y") == set()

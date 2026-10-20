# SPDX-License-Identifier: Apache-2.0
"""Mutants: the core with one fault each, and the property that must kill each one.

Every mutant must die within the examples the `ci` profile gives a property, both at the small size `dev` and
`ci` draw and at the original size `deep` draws (`strategies.Size`). Each test records how many examples the
kill took as `examples_to_kill`, which `--junitxml` writes out.
"""

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Callable
from typing import NamedTuple, TypeVar

import pytest
from hypothesis import strategies as st

from materica.core import canonical, jsonio, slips
from materica.core.canonical import canonicalize
from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from tests.property import strategies
from tests.property import test_canonical_properties as canonical_properties
from tests.property import test_hashing_properties as hashing_properties
from tests.property import test_jsonio_properties as jsonio_properties
from tests.property import test_slip_properties as slip_properties
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.support import examples_to_kill

Example = TypeVar("Example")


def _nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    pass


class Mutant(NamedTuple):
    name: str
    search: Callable[[Size], int]  # the property's search for the fault, at a size: the examples it took
    inject: Callable[[pytest.MonkeyPatch], None] = _nothing  # the fault, where it is inside the core


def setting(
    target: object, name: str, value: object, *, raising: bool = True
) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection that sets `target.<name>` to `value` for the test."""

    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(target, name, value, raising=raising)

    return inject


def killed_by(
    examples: Callable[[Size], st.SearchStrategy[Example]],
    check: Callable[[Example], None],
    error: type[Exception] = AssertionError,
) -> Callable[[Size], int]:
    return lambda size: examples_to_kill(examples(size), check, error)


# Readers with one fault.


def stdlib_json(data: bytes) -> JsonValue | Reason:
    """Python's json as it comes: integers stay int, and its errors escape."""
    value: JsonValue = json.loads(data)
    return value


def _depth_counting_scalars(value: JsonValue) -> int:
    if isinstance(value, list):
        return 1 + max((_depth_counting_scalars(item) for item in value), default=0)
    if isinstance(value, dict):
        return 1 + max((_depth_counting_scalars(member) for member in value.values()), default=0)
    return 1


def counting_scalars_in_depth(data: bytes) -> JsonValue | Reason:
    value = jsonio.parse(data)
    if not isinstance(value, Reason) and _depth_counting_scalars(value) > jsonio.MAX_DEPTH:
        return Reason("malformed")
    return value


def skipping_a_byte_order_mark(data: bytes) -> JsonValue | Reason:
    return jsonio.parse(data.removeprefix(b"\xef\xbb\xbf"))


def refusing_noncharacters(data: bytes) -> JsonValue | Reason:
    value = jsonio.parse(data)
    if any(char in data.decode("utf-8", "replace") for char in strategies.NONCHARACTERS):
        return Reason("malformed")
    return value


def _constant(name: str) -> float:
    return float(name)


def documents(size: Size) -> st.SearchStrategy[tuple[JsonValue, str]]:
    return strategies.documents(size)


def faulty(size: Size) -> st.SearchStrategy[tuple[str, bytes]]:
    return strategies.faulty_documents(size)


def odd(size: Size) -> st.SearchStrategy[tuple[JsonValue, str]]:
    return strategies.odd_documents(size)


def literals(size: Size) -> st.SearchStrategy[str]:
    return strategies.number_literals()


READER_MUTANTS = [
    Mutant(
        "stdlib_json_lets_errors_escape",
        killed_by(
            jsonio_properties.any_bytes,
            lambda data: jsonio_properties.check_any_bytes(stdlib_json, data),
            ValueError,
        ),
    ),
    Mutant(
        "stdlib_json_keeps_integers",
        killed_by(documents, lambda document: jsonio_properties.check_reads_back(stdlib_json, document)),
    ),
    Mutant(
        "stdlib_json_keeps_integer_literals",
        killed_by(literals, lambda literal: jsonio_properties.check_number(stdlib_json, literal)),
    ),
    Mutant(
        "repeated_names_accepted",
        killed_by(faulty, lambda document: jsonio_properties.check_fault_refused(jsonio.parse, document)),
        setting(jsonio, "_object", dict),
    ),
    Mutant(
        "depth_counted_with_scalars",
        killed_by(
            odd, lambda document: jsonio_properties.check_odd_but_valid(counting_scalars_in_depth, document)
        ),
    ),
    Mutant(
        "nesting_limit_63",
        killed_by(odd, lambda document: jsonio_properties.check_odd_but_valid(jsonio.parse, document)),
        setting(jsonio, "MAX_DEPTH", 63),
    ),
    Mutant(
        "nesting_limit_65",
        killed_by(faulty, lambda document: jsonio_properties.check_fault_refused(jsonio.parse, document)),
        setting(jsonio, "MAX_DEPTH", 65),
    ),
    Mutant(
        "unpaired_surrogates_accepted",
        killed_by(faulty, lambda document: jsonio_properties.check_fault_refused(jsonio.parse, document)),
        setting(jsonio, "_SURROGATE", re.compile("(?!)")),
    ),
    Mutant(
        "nan_and_infinity_accepted",
        killed_by(faulty, lambda document: jsonio_properties.check_fault_refused(jsonio.parse, document)),
        setting(jsonio, "_constant", _constant),
    ),
    Mutant(
        "infinity_from_a_number_accepted",
        killed_by(literals, lambda literal: jsonio_properties.check_number(jsonio.parse, literal)),
        setting(jsonio, "_double", float),
    ),
    Mutant(
        "byte_order_mark_skipped",
        killed_by(
            faulty,
            lambda document: jsonio_properties.check_fault_refused(skipping_a_byte_order_mark, document),
        ),
    ),
    Mutant(
        "noncharacters_refused",
        killed_by(
            odd, lambda document: jsonio_properties.check_odd_but_valid(refusing_noncharacters, document)
        ),
    ),
]


# Canonical forms with one fault.


def values(size: Size) -> st.SearchStrategy[JsonValue]:
    return canonical_properties.rfc8785_values(size)


def doubles(size: Size) -> st.SearchStrategy[float]:
    return strategies.DOUBLES


def objects_across_surrogates(size: Size) -> st.SearchStrategy[dict[str, JsonValue]]:
    return canonical_properties.OBJECTS_ACROSS_SURROGATES


def replacing(
    name: str, faulty: Callable[[Callable[..., str]], Callable[..., str]]
) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection that replaces `canonical.<name>` with `faulty(original)`."""

    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(canonical, name, faulty(vars(canonical)[name]))

    return inject


def _code_points(name: str) -> str:
    return name


def _utf8_bytes(name: str) -> bytes:
    return name.encode("utf-8")


def _one_pass_of_exchanges(names: dict[str, JsonValue], key: Callable[[str], bytes]) -> list[str]:
    """Orders two members, and not always three."""
    order = list(names)
    for index in range(len(order) - 1):
        if key(order[index + 1]) < key(order[index]):
            order[index], order[index + 1] = order[index + 1], order[index]
    return order


def _seventeen_digits(number: float) -> str:
    return f"{number:.17g}"


def _exponent_without_its_sign(original: Callable[..., str]) -> Callable[..., str]:
    def write(number: float) -> str:
        return original(number).replace("e+", "e")

    return write


def _normalised_to_nfc(original: Callable[..., str]) -> Callable[..., str]:
    def write(text: str) -> str:
        return original(unicodedata.normalize("NFC", text))

    return write


def _minus_zero_kept(original: Callable[..., str]) -> Callable[..., str]:
    def write(number: float) -> str:
        return "-0" if number == 0 and math.copysign(1.0, number) < 0 else original(number)

    return write


CANONICAL_MUTANTS = [
    Mutant(
        "numbers_written_by_repr",
        killed_by(values, canonical_properties.check_matches_rfc8785),
        setting(canonical, "_number", repr),
    ),
    Mutant(
        "numbers_written_with_17_digits",
        killed_by(doubles, canonical_properties.check_shortest_round_trip),
        setting(canonical, "_number", _seventeen_digits),
    ),
    Mutant(
        "negative_zero_written_as_minus_0",
        killed_by(doubles, canonical_properties.check_shortest_round_trip),
        replacing("_number", _minus_zero_kept),
    ),
    Mutant(
        "exponent_written_without_its_sign",
        killed_by(values, canonical_properties.check_matches_rfc8785),
        replacing("_number", _exponent_without_its_sign),
    ),
    Mutant(
        "names_sorted_by_code_point",
        killed_by(objects_across_surrogates, canonical_properties.check_utf16_order),
        setting(canonical, "_utf16_units", _code_points),
    ),
    Mutant(
        "names_sorted_by_utf8_bytes",
        killed_by(objects_across_surrogates, canonical_properties.check_utf16_order),
        setting(canonical, "_utf16_units", _utf8_bytes),
    ),
    Mutant(
        "names_sorted_by_one_pass_of_exchanges",
        killed_by(values, canonical_properties.check_matches_rfc8785),
        setting(canonical, "sorted", _one_pass_of_exchanges, raising=False),
    ),
    Mutant(
        "strings_normalised_to_nfc",
        killed_by(values, canonical_properties.check_matches_rfc8785),
        replacing("_string", _normalised_to_nfc),
    ),
    Mutant(
        "non_ascii_escaped",
        killed_by(values, canonical_properties.check_matches_rfc8785),
        setting(canonical, "_string", json.dumps),
    ),
]


# Hashes with one fault: section 9 item 1's view written again, wrong in one way.


def mutant_view(value: JsonValue, fault: str = "") -> JsonValue:
    """The hashable view with `fault`; with none, `hashable_view` itself (`test_mutant_view.py`)."""

    def view(node: JsonValue, depth: int, top: bool) -> JsonValue:
        if isinstance(node, list):
            if depth and fault == "removal_skips_later_array_items":
                return [view(node[0], depth + 1, False), *node[1:]] if node else []
            return [view(item, depth + 1 if depth else 0, False) for item in node]
        if not isinstance(node, dict):
            return node
        kept: dict[str, JsonValue] = {}
        for name, member in node.items():
            if (
                top
                and name in hashing_properties.TOP_LEVEL_REMOVED
                and not (fault == "card_hashed" and name == "card")
            ):
                continue
            if fault == "card_removed_at_every_depth" and name in hashing_properties.TOP_LEVEL_REMOVED:
                continue
            if fault == "review_removed_outside_provenance" and name == "review":
                continue
            if (
                fault == "review_and_copy_removed_everywhere"
                and name in hashing_properties.REMOVED_IN_PROVENANCE
            ):
                continue
            in_reach = fault != "removal_only_to_depth_2" or depth <= 2
            if (
                depth
                and in_reach
                and fault != "nothing_removed_inside_provenance"
                and name in ("review", "copy")
            ):
                continue
            opens = name == "provenance" and (
                isinstance(member, dict) or fault == "a_non_object_provenance_opens"
            )
            kept[name] = view(member, depth + 1 if depth else int(opens), False)
        return kept

    return view(value, 0, True)


def mutant_digest(fault: str) -> Callable[[JsonValue], str]:
    return lambda value: "sha256:" + hashlib.sha256(canonicalize(mutant_view(value, fault))).hexdigest()


def variants(size: Size) -> st.SearchStrategy[hashing_properties.Variants]:
    return hashing_properties.variants(size)


def edits(size: Size) -> st.SearchStrategy[hashing_properties.Edit]:
    return hashing_properties.edits(size)


def _as_inserted(name: str) -> int:
    return 0


def _bytes_as_written(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def invariance_kills(fault: str) -> Callable[[Size], int]:
    return killed_by(variants, lambda v: hashing_properties.check_invariance(mutant_digest(fault), v))


def edit_kills(fault: str) -> Callable[[Size], int]:
    return killed_by(edits, lambda edit: hashing_properties.check_edit(mutant_digest(fault), edit))


def edit_below_a_non_object_provenance_kills(fault: str) -> Callable[[Size], int]:
    """The planned search of an edit below a `review` or `copy` in a provenance that is not an object, which
    the hash keeps: drawn whole, a search took up to 872 of 2,000 examples, before `edits` drew such an edit
    in about three draws in ten of those outside every provenance object."""
    return killed_by(
        hashing_properties.edits_below_a_non_object_provenance,
        lambda edit: hashing_properties.check_edit(mutant_digest(fault), edit),
    )


HASH_MUTANTS = [
    Mutant("card_hashed", invariance_kills("card_hashed")),
    Mutant("nothing_removed_inside_provenance", invariance_kills("nothing_removed_inside_provenance")),
    Mutant("removal_only_to_depth_2", invariance_kills("removal_only_to_depth_2")),
    Mutant("removal_skips_later_array_items", invariance_kills("removal_skips_later_array_items")),
    Mutant(
        "the_bytes_as_written_hashed",
        killed_by(
            variants, lambda v: hashing_properties.check_invariance(content_hash, v, _bytes_as_written)
        ),
    ),
    Mutant(
        "members_hashed_as_inserted",
        killed_by(variants, lambda v: hashing_properties.check_invariance(content_hash, v)),
        setting(canonical, "_utf16_units", _as_inserted),
    ),
    Mutant("review_removed_outside_provenance", edit_kills("review_removed_outside_provenance")),
    Mutant("review_and_copy_removed_everywhere", edit_kills("review_and_copy_removed_everywhere")),
    Mutant(
        "a_non_object_provenance_opens",
        edit_below_a_non_object_provenance_kills("a_non_object_provenance_opens"),
    ),
    Mutant("card_removed_at_every_depth", edit_kills("card_removed_at_every_depth")),
    Mutant(
        "a_constant_answer",
        killed_by(edits, lambda edit: hashing_properties.check_edit(lambda value: "sha256:0", edit)),
    ),
]

# The one-slip relation with one fault each, killed by its property against the neighbour generator.

ONE_SLIP = slips.one_slip
PLURAL_OF = slips.plural_of


def _without_kind(kind: str) -> Callable[[str, str], str | None]:
    def relation(a: str, b: str) -> str | None:
        slip = ONE_SLIP(a, b)
        return None if slip == kind else slip

    return relation


def _underscore_as_a_character(a: str, b: str) -> str | None:
    slip = ONE_SLIP(a, b)
    return "a character added" if slip == "an underscore added" else slip


def _two_characters_added(a: str, b: str) -> str | None:
    shorter, longer = sorted((a, b), key=len)
    if len(longer) - len(shorter) == 2 and longer.startswith(shorter):
        return "a character added"
    return ONE_SLIP(a, b)


def _plural_without_ies(a: str, b: str) -> bool:
    singular, plural = sorted((a, b), key=len)
    return not (singular.endswith("y") and plural == singular[:-1] + "ies") and PLURAL_OF(a, b)


def _plural_without_es(a: str, b: str) -> bool:
    singular, plural = sorted((a, b), key=len)
    return plural != singular + "es" and PLURAL_OF(a, b)


def _empty_word_made_plural(a: str, b: str) -> bool:
    singular, plural = sorted((a, b), key=len)
    return (not singular and plural in ("s", "es")) or PLURAL_OF(a, b)


def _swap_of_any_two(a: str, b: str) -> str | None:
    differing = [index for index, (x, y) in enumerate(zip(a, b, strict=False)) if x != y]
    if len(a) == len(b) and len(differing) == 2 and sorted(a) == sorted(b):
        return "two characters swapped"
    return ONE_SLIP(a, b)


SLIPS = killed_by(lambda size: slip_properties.pairs(), slip_properties.check_one_slip)
# The planned search of `empty_word_made_plural`: (9)'s pairs through an empty word alone. Drawn whole, a
# search took 629 of 2,000 examples, before (9) drew them in about one draw in six.
EMPTY_WORDS = killed_by(
    lambda size: slip_properties.pairs_through_an_empty_word(), slip_properties.check_one_slip
)


@st.composite
def pairs_through_an_irregular_plural(draw: st.DrawFn) -> slip_properties.Pair:
    """A name holding one of section 10's irregular singulars, among words of section 10's and words of
    letters, and the same with its plural in its place, in either order: one slip apart, a plural only the
    irregular list makes (`irregular_plurals_missed`), which (9)'s pairs give in about one example in 250."""
    words = draw(
        st.lists(
            st.one_of(
                st.sampled_from(slip_properties.WORDS),
                st.text(slip_properties.LETTERS, min_size=1, max_size=4),
            ),
            max_size=2,
        )
    )
    index = draw(st.integers(0, len(words)))
    singular, plural = draw(st.sampled_from(slip_properties.IRREGULAR))
    a = "_".join([*words[:index], singular, *words[index:]])
    b = "_".join([*words[:index], plural, *words[index:]])
    return slip_properties.Pair(a, b, 1) if draw(st.booleans()) else slip_properties.Pair(b, a, 1)


@st.composite
def pairs_through_an_ies_plural(draw: st.DrawFn) -> slip_properties.Pair:
    """A name holding a word that ends in `y`, among words of section 10's and words of letters, and the same
    with that `y` made `ies`, in either order: one slip apart, the plural `ies_plural_missed` misses."""
    words = draw(
        st.lists(
            st.one_of(
                st.sampled_from(slip_properties.WORDS),
                st.text(slip_properties.LETTERS, min_size=1, max_size=4),
            ),
            max_size=2,
        )
    )
    stems = sorted({word[:-1] for word in slip_properties.WORDS if word.endswith("y")})
    stem = draw(
        st.one_of(st.sampled_from(stems), st.text(slip_properties.LETTERS.replace("_", ""), max_size=3))
    )
    index = draw(st.integers(0, len(words)))
    a = "_".join([*words[:index], stem + "y", *words[index:]])
    b = "_".join([*words[:index], stem + "ies", *words[index:]])
    return slip_properties.Pair(a, b, 1) if draw(st.booleans()) else slip_properties.Pair(b, a, 1)


# The planned search of `ies_plural_missed`: drawn with (9) whole, its search died past the 500th example on
# 88 of 400 streams on main and 80 once (9) drew a pair through an empty word (2026-10-20), and at the 700th
# on the recorded stream.
IES_PLURALS = killed_by(lambda size: pairs_through_an_ies_plural(), slip_properties.check_one_slip)
# The planned search of `irregular_plurals_missed`: (9)'s searches drawn whole took past the 500th example on
# about one stream in nine on main and one in six once (9) drew a pair through an empty word (2026-10-20).
IRREGULAR_PLURALS = killed_by(
    lambda size: pairs_through_an_irregular_plural(), slip_properties.check_one_slip
)
SLIP_MUTANTS = [
    *[
        Mutant(f"{name}_missed", SLIPS, setting(slips, "one_slip", _without_kind(kind)))
        for name, kind in (
            ("substitution", slip_properties.SUBSTITUTED),
            ("insertion", slip_properties.ADDED),
            ("underscore", slip_properties.UNDERSCORE),
            ("swap", slip_properties.SWAPPED),
            ("plural", slip_properties.PLURAL),
        )
    ],
    Mutant("underscore_read_as_a_character", SLIPS, setting(slips, "one_slip", _underscore_as_a_character)),
    Mutant("two_characters_added_one_slip", SLIPS, setting(slips, "one_slip", _two_characters_added)),
    Mutant("swap_of_any_two_characters", SLIPS, setting(slips, "one_slip", _swap_of_any_two)),
    Mutant("ies_plural_missed", IES_PLURALS, setting(slips, "plural_of", _plural_without_ies)),
    Mutant("es_plural_missed", SLIPS, setting(slips, "plural_of", _plural_without_es)),
    Mutant("irregular_plurals_missed", IRREGULAR_PLURALS, setting(slips, "_IRREGULAR_PLURALS", {})),
    Mutant("empty_word_made_plural", EMPTY_WORDS, setting(slips, "plural_of", _empty_word_made_plural)),
]

MUTANTS = READER_MUTANTS + CANONICAL_MUTANTS + HASH_MUTANTS + SLIP_MUTANTS


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    mutant.inject(monkeypatch)
    record_property("examples_to_kill", mutant.search(size))

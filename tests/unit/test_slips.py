# SPDX-License-Identifier: Apache-2.0
"""`slipped`, which picks out the members `record_format.md` section 10 item 5 refuses. The relation itself,
`one_slip`, is checked with the name-overlap check that shares it (`tests/spec_sync/test_name_overlaps.py`)
and against a neighbour generator (`tests/property/test_slip_properties.py`)."""

from materica.core.slips import one_slip, slipped

NAMED = ("value", "unit", "basis", "plus_minus")


def test_a_member_one_slip_from_a_named_one_is_picked_out_with_that_name() -> None:
    members = ["unit", "units", "vaule", "basiss", "plus_minsu", "plus_minuses", "x_note", "temperature"]
    assert slipped(members, NAMED) == [
        ("units", "unit"),
        ("vaule", "value"),
        ("basiss", "basis"),
        ("plus_minsu", "plus_minus"),
        ("plus_minuses", "plus_minus"),
    ]


def test_a_named_member_is_never_picked_out_even_one_slip_from_another() -> None:
    assert slipped(["lot", "lots"], ("lot", "lots")) == []


def test_a_member_one_slip_from_two_names_is_picked_out_once_with_the_first() -> None:
    assert slipped(["bat"], ("cat", "bag")) == [("bat", "bag")]


def test_nothing_is_picked_out_where_nothing_is_named() -> None:
    assert slipped(["value", "units"], ()) == []


def test_the_empty_string_between_two_underscores_is_no_word() -> None:
    assert one_slip("x__y", "x_s_y") == "a character added"
    assert one_slip("x__y", "x_es_y") is None
    assert one_slip("unit", "units") == "singular or plural"

# SPDX-License-Identifier: Apache-2.0
"""No two names one slip apart at one place, and no name with two meanings, unless `name_overlaps.json` allows
it with its reason and safeguard (`name_overlaps.py`; `record_format.md` section 10).

The controls run the whole check on a copy of the schemas and the specification with one fault seeded, each
in one of the check's inputs, and assert first that the text they seed into is there."""

import copy
import json
import shutil
import warnings
from pathlib import Path

import pytest

from materica.core.jsonio import JsonValue
from materica.core.slips import one_slip
from tests.spec_sync import name_overlaps
from tests.spec_sync.name_overlaps import (
    AwaitingTheMaintainer,
    Corpus,
    Flag,
    Shape,
    awaiting,
    check,
    rule_a,
    rule_b,
)

REPOSITORY = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = Path(__file__).with_name("name_overlaps.json")
ALLOWLIST = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def report_awaiting(allowlist: dict[str, JsonValue]) -> None:
    """Warns of each entry marked `pending`: its rename is proposed, and the check passes until the maintainer
    has answered (maintainer, 2026-10-15)."""
    if pending := awaiting(allowlist):
        warnings.warn(
            f"awaiting the maintainer's answer on a rename: {pending}", AwaitingTheMaintainer, stacklevel=2
        )


@pytest.mark.filterwarnings("default::tests.spec_sync.name_overlaps.AwaitingTheMaintainer")
def test_every_name_overlap_is_allowed_with_its_reason_and_safeguard() -> None:
    remaining, problems = check(REPOSITORY, ALLOWLIST)
    assert [*map(str, remaining), *problems] == []
    report_awaiting(ALLOWLIST)


@pytest.mark.parametrize(
    ("a", "b", "slip"),
    [
        ("lot", "lots", "singular or plural"),
        ("process", "processes", "singular or plural"),
        ("entry", "entries", "singular or plural"),
        ("input_specimen", "input_specimens", "singular or plural"),
        ("datum", "data", "singular or plural"),
        ("index", "indices", "singular or plural"),
        ("matrix", "matrices", "singular or plural"),
        ("fill_in", "fillin", "an underscore added"),
        ("form", "from", "two characters swapped"),
        ("reported_sd", "reported_se", "a character substituted"),
        ("plot", "lot", "a character added"),
        ("specimen", "specimne", "two characters swapped"),
        ("crad", "card", "two characters swapped"),
        ("fluid", "fluids", "singular or plural"),
    ],
)
def test_each_slip_section_10_names_is_one_slip(a: str, b: str, slip: str) -> None:
    assert one_slip(a, b) == slip
    assert one_slip(b, a) == slip


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("form", "farm_"),
        ("unit", "tinu"),
        ("abcd", "badc"),
        ("value", "valeu_"),
        ("vertex", "vertices"),
        ("criterion", "criteria"),
        ("lot", "lot"),
    ],
)
def test_names_further_apart_are_not_one_slip(a: str, b: str) -> None:
    assert one_slip(a, b) is None


def corpus(*namespaces: tuple[str, str, dict[str, Shape]]) -> Corpus:
    found = Corpus()
    for kind, owner, shapes in namespaces:
        namespace = found.new("members" if kind == "members" else "tokens", owner, f"{owner}.json")
        for name, shape in shapes.items():
            namespace.add(name, shape)
    return found


TOKENS = Shape("tokens", frozenset({"a1", "b1", "c1"}))
NUMBER = Shape("number")


def flagged(flags: list[Flag]) -> set[tuple[str, tuple[str, ...]]]:
    return {(flag.rule, flag.names) for flag in flags}


@pytest.mark.parametrize(
    ("namespaces", "flag"),
    [
        pytest.param(
            [
                ("members", "x", {"size": NUMBER}),
                ("members", "y", {"size": Shape("object", frozenset({"a"}))}),
            ],
            ("A", ("size",)),
            id="number_and_object",
        ),
        pytest.param(
            [
                ("members", "x", {"kind": TOKENS}),
                ("members", "y", {"kind": Shape("tokens", frozenset({"d1"}))}),
            ],
            ("A", ("kind",)),
            id="two_token_lists",
        ),
        pytest.param(
            [
                ("members", "x", {"kind": TOKENS}),
                ("members", "y", {"kind": Shape("string", frozenset({"free"}))}),
            ],
            ("A", ("kind",)),
            id="a_list_and_a_value_outside_it",
        ),
        pytest.param(
            [("members", "x", {"basis": TOKENS, "represents": Shape("tokens", frozenset({"c1", "d1"}))})],
            ("A", ("c1",)),
            id="a_token_of_two_sibling_lists",
        ),
        pytest.param(
            [("members", "x", {"lots": NUMBER, "lot": NUMBER})],
            ("B", ("lot", "lots")),
            id="one_slip_in_an_object",
        ),
        pytest.param(
            [("tokens", "purpose", {"fill_in": NUMBER, "fillin": NUMBER})],
            ("B", ("fill_in", "fillin")),
            id="one_slip_in_a_token_list",
        ),
    ],
)
def test_each_rule_flags_its_overlap(
    namespaces: list[tuple[str, str, dict[str, Shape]]], flag: tuple[str, tuple[str, ...]]
) -> None:
    found = corpus(*namespaces)
    assert flag in flagged(rule_a(found) + rule_b(found))


@pytest.mark.parametrize(
    "namespaces",
    [
        pytest.param(
            [
                ("members", "x", {"kind": TOKENS}),
                ("members", "y", {"kind": Shape("tokens", frozenset({"a1"}))}),
            ],
            id="a_list_restricted",
        ),
        pytest.param(
            [
                ("members", "x", {"kind": Shape("tokens", frozenset({"alpha"}))}),
                ("members", "y", {"kind": Shape("tokens", frozenset({"omega"}))}),
                ("tokens", "kinds", {"alpha": NUMBER, "omega": NUMBER}),
            ],
            id="two_restrictions_of_one_list",
        ),
        pytest.param(
            [
                ("members", "x", {"kind": TOKENS}),
                ("members", "y", {"kind": Shape("string", frozenset({"b1"}))}),
            ],
            id="an_example_value_of_the_list",
        ),
        pytest.param([("members", "x", {"x": NUMBER, "y": NUMBER})], id="single_letters"),
    ],
)
def test_what_is_one_meaning_is_not_flagged(namespaces: list[tuple[str, str, dict[str, Shape]]]) -> None:
    found = corpus(*namespaces)
    assert not rule_a(found) + rule_b(found)


def test_a_registered_name_used_as_a_member_is_flagged() -> None:
    found = corpus(("members", "evidence_entry", {"temperature": NUMBER, "note": NUMBER}))
    found.registered["temperature"] = "a condition"
    assert ("A", ("temperature",)) in flagged(rule_a(found))


def test_a_member_holding_another_members_tokens_and_more_is_flagged() -> None:
    found = corpus(
        ("members", "statistics", {"level": Shape("tokens", frozenset({"donor", "specimen", "test"}))})
    )
    holder = found.new("members", "population", "example.md:1")
    holder.add("unit", Shape("string"), {"donor", "specimen"})
    holder.add("unit", Shape("string"), {"K"})
    assert ("A", ("unit",)) in flagged(rule_a(found))


# The controls on files: each edit, applied to a copy of the inputs, and the flag or allowlist problem it must
# give. An edit is a document, the text that must be there, and the text that replaces it.
Edit = tuple[str, str, str]
FACTS = "src/materica/schema/0.1/vocabulary/specimen_facts.json"
WRITER = "src/materica/schema/0.1/record.writer.json"
SET_OR_MEASURED = '"set_or_measured": {"$ref": "vocabulary/provenance.json#/$defs/set_or_measured"}'
# Each form's value field holds the members of `field_members` by `allOf`, beside its own `form`.
FORMS = json.loads(
    (REPOSITORY / "src/materica/schema/0.1/vocabulary/forms.json").read_text(encoding="utf-8")
)["$defs"]["form"]["enum"]


def copied(tmp_path: Path, edits: list[Edit]) -> Path:
    for tree in ("src/materica/schema/0.1", "docs/specification"):
        shutil.copytree(REPOSITORY / tree, tmp_path / tree)
    for document, old, new in edits:
        path = tmp_path / document
        text = path.read_text(encoding="utf-8")
        assert old in text, (document, old)
        path.write_text(text.replace(old, new), encoding="utf-8")
    return tmp_path


SUPPLY_FORM = [
    ("docs/specification/provenance.md", "| `supply_form` |", "| `material_form` |"),
    (FACTS, '"supply_form"', '"material_form"'),
    (WRITER, '"supply_form": {"anyOf"', '"material_form": {"anyOf"'),
]
LOTS = [
    (
        "docs/specification/provenance.md",
        '| `lot` | `{"text": <the lot or batch, as the source names it>, "basis"}` |',
        '| `lot` | `{"text": <the lot or batch, as the source names it>, "basis"}` |\n'
        '| `lots` | `{"text": <every lot a pooled value covers>, "basis"}` |',
    ),
    (
        FACTS,
        '    "lot": {\n      "tokens": []\n    }',
        '    "lot": {\n      "tokens": []\n    },\n    "lots": {\n      "tokens": []\n    }',
    ),
]


@pytest.mark.parametrize(
    ("edits", "flags"),
    [
        pytest.param(
            SUPPLY_FORM,
            {"[A] material_form (owner *)", "[A] material_form (owner registered)"},
            id="material_form_reused",
        ),
        pytest.param(LOTS, {"[B] lot ~ lots (owner facts)"}, id="lots_beside_lot"),
        pytest.param(
            [
                (
                    WRITER,
                    '"purpose": {"enum": ["fit", "fill_in",',
                    '"purpose": {"enum": ["fit", "fill_in", "fillin",',
                )
            ],
            {"[B] fill_in ~ fillin (owner purpose)"},
            id="fillin_in_a_schema_enumeration",
        ),
        pytest.param(
            [
                (
                    "docs/specification/provenance.md",
                    '  "origin": "measured_by_source",',
                    '  "origin": "measured_by_source", "origins": "fitted",',
                )
            ],
            {"[B] origin ~ origins (owner provenance)"},
            id="origins_in_an_example",
        ),
        pytest.param(
            [
                (
                    WRITER,
                    '"unit": {"$ref": "#/$defs/unit"},\n        "specimen": {"$ref": "#/$defs/specimen"},',
                    '"unit": {"$ref": "#/$defs/unit"},\n        "forms": {"type": "string"},\n'
                    '        "specimen": {"$ref": "#/$defs/specimen"},',
                )
            ],
            {f"[B] form ~ forms (owner {form}_field)" for form in FORMS},
            id="forms_in_the_members_every_form_takes",
        ),
        pytest.param(
            [
                (
                    WRITER,
                    f"{SET_OR_MEASURED}\n      }},",
                    f'{SET_OR_MEASURED},\n        "bases": {{"type": "string"}}\n      }},',
                )
            ],
            {"[B] bases ~ basis (owner numeric_condition)"},
            id="bases_beside_the_basis_a_condition_takes",
        ),
    ],
)
def test_a_seeded_overlap_is_flagged(tmp_path: Path, edits: list[Edit], flags: set[str]) -> None:
    remaining, problems = check(copied(tmp_path, edits), ALLOWLIST)
    assert not problems
    assert {str(found).partition(":")[0] for found in remaining} == flags


@pytest.mark.parametrize(
    ("edits", "problem"),
    [
        pytest.param(
            [
                (
                    "docs/specification/uncertainty.md",
                    "`reported_se` with `represents: estimate`, and",
                    "`reported_se` with `represents: estimate`; and",
                )
            ],
            "['reported_sd', 'reported_se']: its safeguard is gone from docs/specification/uncertainty.md",
            id="safeguard_gone",
        ),
        pytest.param(
            [("src/materica/schema/0.1/vocabulary/statistics.json", '"reported_se"', '"reported_sem"')],
            "['reported_sd', 'reported_se']: allows no flag",
            id="entry_stale",
        ),
    ],
)
def test_an_allowlist_entry_can_fail(tmp_path: Path, edits: list[Edit], problem: str) -> None:
    _, problems = check(copied(tmp_path, edits), ALLOWLIST)
    assert problem in problems


def test_a_new_meaning_flags_an_allowed_name_again(tmp_path: Path) -> None:
    """`basis` is allowed with six meanings; a seventh, a region's basis token in a scene document's example,
    flags it again."""
    edits = [("docs/specification/geometry.md", '"name": "lumen"', '"name": "lumen", "basis": ["segmented"]')]
    remaining, _ = check(copied(tmp_path, edits), ALLOWLIST)
    assert [found.names for found in remaining] == [("basis",)]


def changed(changes: dict[tuple[str, ...], dict[str, JsonValue | None]]) -> dict[str, JsonValue]:
    """The allowlist with each entry named by its names, and its owner where two share them, changed: each
    member set, or removed for None."""
    allowlist: dict[str, JsonValue] = copy.deepcopy(ALLOWLIST)
    entries = allowlist["entries"]
    assert isinstance(entries, list)
    for key, change in changes.items():
        found = [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and (*listing(entry["names"]), *([entry["owner"]] if "owner" in entry else [])) == key
        ]
        assert len(found) == 1, key
        for member, value in change.items():
            if value is None:
                found[0].pop(member, None)
            else:
                found[0][member] = value
    return allowlist


def listing(value: JsonValue) -> list[JsonValue]:
    assert isinstance(value, list)
    return value


SAFEGUARDS = (
    "tests/spec_sync/test_name_overlap_safeguards.py::test_each_meaning_is_refused_at_the_others_places"
)


@pytest.mark.parametrize(
    ("key", "change", "problem"),
    [
        pytest.param(
            ("ranges",), {"no_safeguard_because": None}, "no reason why none is possible", id="no_reason"
        ),
        pytest.param(("ranges",), {"maintainer": None}, "no maintainer's flag", id="no_flag"),
        pytest.param(
            ("ranges",), {"maintainer": "approved"}, "no maintainer's flag", id="a_flag_of_another_name"
        ),
        pytest.param(
            ("evidence", "registered"),
            {"maintainer": "pending"},
            "a safeguard beside a maintainer's flag",
            id="a_safeguard_and_a_flag",
        ),
        pytest.param(
            ("mean",),
            {
                "safeguard": {
                    "test": "tests/spec_sync/test_name_overlap_safeguards.py::test_gone[mean]",
                    "what": ".",
                }
            },
            "its safeguard is gone",
            id="a_test_gone",
        ),
        pytest.param(
            ("mean",),
            {"safeguard": {"test": f"{SAFEGUARDS}[means]", "what": "."}},
            "its safeguard is gone",
            id="a_name_the_test_does_not_guard",
        ),
    ],
)
def test_an_entry_without_a_safeguard_needs_the_maintainers_flag_and_a_reason(
    key: tuple[str, ...], change: dict[str, JsonValue | None], problem: str
) -> None:
    """An entry with no safeguard says why none is possible and carries `pending`, `approved_no_safeguard` or
    `approved_safeguard_deferred` (maintainer, 2026-10-15); one with a safeguard carries no flag; a test named
    as a safeguard must be there, guarding that name."""
    _, problems = check(REPOSITORY, changed({key: change}))
    assert any(problem in found for found in problems), problems


def test_an_entry_approved_with_no_safeguard_passes() -> None:
    _, problems = check(REPOSITORY, changed({("ranges",): {"maintainer": "approved_no_safeguard"}}))
    assert problems == []


def test_a_pending_entry_fails_now_that_the_maintainer_has_answered() -> None:
    """The maintainer answered the renames proposed with S2a-1 (2026-10-15): no entry is `pending`, and none
    is warned of. The control: `ranges` marked `pending` again is a problem, and the same entry passes, warned
    of, only while `renames` is `proposed`."""
    assert ALLOWLIST["renames"] == "answered"
    assert awaiting(ALLOWLIST) == []
    pending = changed({("ranges",): {"maintainer": "pending"}})
    _, problems = check(REPOSITORY, pending)
    assert problems == ["['ranges']: still pending, though the maintainer has answered"]
    _, problems = check(REPOSITORY, {**pending, "renames": "proposed"})
    assert problems == []
    with pytest.warns(AwaitingTheMaintainer, match="ranges"):
        report_awaiting(pending)


# A writer schema that gives `ranges` a place: a review holding it beside its checklist.
RANGES_PLACED = [
    (
        WRITER,
        '"checklist": {"type": "array", "items": {"type": "string"}}',
        '"checklist": {"type": "array", "items": {"type": "string"}}, "ranges": {"type": "object"}',
    )
]


def test_a_safeguard_deferred_to_the_shapes_is_due_once_a_schema_gives_the_name_a_place(
    tmp_path: Path,
) -> None:
    """`ranges` keeps both meanings, its safeguard deferred to the parameter set's and the fit's shapes
    (maintainer, 2026-10-15): it passes while no schema gives `ranges` a place, and fails once one does, where
    the same entry approved with no safeguard still passes, so it is the flag that fails it."""
    deferred = [entry for entry in ALLOWLIST["entries"] if entry["names"] == ["ranges"]]
    assert [entry["maintainer"] for entry in deferred] == ["approved_safeguard_deferred"]
    _, problems = check(REPOSITORY, ALLOWLIST)
    assert problems == []
    placed = copied(tmp_path, RANGES_PLACED)
    remaining, problems = check(placed, ALLOWLIST)
    assert problems == ["['ranges']: its safeguard is due, since a schema now gives ['ranges'] a place"]
    assert [found.names for found in remaining] == [("ranges",)]
    approved = changed({("ranges",): {"maintainer": "approved_no_safeguard"}})
    assert check(placed, approved) == ([], [])


def test_the_corpus_reads_each_of_its_inputs() -> None:
    """A check that read nothing would flag nothing: each input gives namespaces."""
    found = name_overlaps.collect(REPOSITORY)
    origins = {namespace.origin.partition("#")[0].partition(":")[0] for namespace in found.namespaces}
    assert {
        "src/materica/schema/0.1/record.writer.json",
        "src/materica/schema/0.1/read_request.json",
        "src/materica/schema/0.1/case.json",
        "src/materica/schema/0.1/vocabulary/statistics.json",
        "vocabulary/fields.json",
        "docs/specification/provenance.md",
        "docs/specification/declarations.md",
    } <= origins
    assert {"status", "unit"} <= set(found.name_keyed)


def test_a_binding_of_the_vocabulary_declares_no_namespace() -> None:
    """A binding restricts members the writer declares (a field's `unit` to its registered one), as a
    condition does: its names and lists are no namespace, and its conjunct adds no member to the definition
    that applies it. The control: the vocabulary's lists of tokens are read."""
    files = name_overlaps.load(REPOSITORY)
    fields = name_overlaps.mapping(name_overlaps.mapping(files["vocabulary/fields.json"])["$defs"])
    assert name_overlaps.binding(fields["sections"], "vocabulary/fields.json")
    assert not name_overlaps.binding(fields["label"], "vocabulary/fields.json")
    origins = [namespace.origin for namespace in name_overlaps.collect(REPOSITORY).namespaces]
    vocabulary = "src/materica/schema/0.1/vocabulary/"
    bindings = (f"{vocabulary}fields.json#/$defs/sections", f"{vocabulary}conditions.json#/$defs/units")
    assert not [origin for origin in origins if origin.startswith(bindings)]
    assert f"{vocabulary}fields.json#/$defs/label" in origins
    replaces = [origin for origin in origins if origin.endswith("record.writer.json#/$defs/replaces")]
    assert replaces == []

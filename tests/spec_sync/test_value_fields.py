# SPDX-License-Identifier: Apache-2.0
"""The value-field part of the writer schema against the specification: the member tables of a value field,
the provenance object, the statistics block, the conditions and the specimen facts; the members that may hold
a status object, with their tokens (`provenance.md` section 1 item 5); the specification's examples of these
shapes; and the members a read does not check, marked `x-materica-write-only`, or checks only under a
condition, marked write-only `unless` it holds (`read_side_contract.md` section 3, step 8).

Structure is edited in the writer schema and checked here against the text, so that the specification keeps
its prose (CONTRIBUTING, "Changing the schema"). Each check takes the schema's definitions and the documents
it reads, so that its controls can give it a changed copy of either.
"""

import copy
import json
import re
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import urljoin

import pytest
from jsonschema import Draft202012Validator
from referencing.jsonschema import DRAFT202012

from materica.core.jsonio import JsonValue
from scripts import gen_vocabulary
from scripts.gen_vocabulary import (
    SPECIFICATION,
    between,
    cell_of,
    codes,
    identifier_patterns,
    only_code,
    prose,
    specimen_facts,
    table,
)
from tests.spec_sync.schemas import BASE, REGISTRY, SCHEMA, validator

Schema = dict[str, JsonValue]
Definitions = dict[str, Schema]
Documents = Callable[[str], str]

WRITER = json.loads((SCHEMA / "record.writer.json").read_text(encoding="utf-8"))
DEFINITIONS: Definitions = WRITER["$defs"]
FORMS = json.loads((SCHEMA / "vocabulary" / "forms.json").read_text(encoding="utf-8"))["$defs"]["form"][
    "enum"
]
WRITE_ONLY = "x-materica-write-only"
ANY = frozenset({"unstated", "not_checked", "none", "not_applicable", "withheld"})


def document(name: str) -> str:
    return (SPECIFICATION / name).read_text(encoding="utf-8")


def mapping(value: JsonValue) -> Schema:
    assert isinstance(value, dict)
    return value


def listing(value: JsonValue) -> list[JsonValue]:
    assert isinstance(value, list)
    return value


def at(definitions: Definitions, name: str, *path: str) -> JsonValue:
    """The subschema at `path`, a path of names, inside the definition `name`."""
    found: JsonValue = definitions[name]
    for step in path:
        found = mapping(found)[step]
    return found


def local(subschema: JsonValue) -> str | None:
    """The definition `subschema` refers to, or None for a subschema that is not a local `$ref`."""
    target = subschema.get("$ref") if isinstance(subschema, dict) else None
    return (
        target.removeprefix("#/$defs/") if isinstance(target, str) and target.startswith("#/$defs/") else None
    )


def members(definitions: Definitions, name: str) -> dict[str, JsonValue]:
    """A definition's members, with those of each definition its `allOf` refers to."""
    found: Schema = {}
    for conjunct in listing(definitions[name].get("allOf", [])):
        if (base := local(conjunct)) is not None:
            found |= members(definitions, base)
    return found | mapping(definitions[name].get("properties", {}))


def required(definitions: Definitions, name: str) -> set[str]:
    found: set[str] = set()
    for conjunct in listing(definitions[name].get("allOf", [])):
        if (base := local(conjunct)) is not None:
            found |= required(definitions, base)
    return found | {str(member) for member in listing(definitions[name].get("required", []))}


def alternatives(subschema: JsonValue) -> list[str]:
    """The definitions a member's subschema refers to, itself or as one of its `anyOf`."""
    if (name := local(subschema)) is not None:
        return [name]
    choices = listing(subschema.get("anyOf", [])) if isinstance(subschema, dict) else []
    return [name for choice in choices if (name := local(choice)) is not None]


def forms(definitions: Definitions) -> dict[str, str]:
    """Each form token, and the definition of a value field of that form."""
    found: dict[str, str] = {}
    for choice in listing(at(definitions, "form_field", "oneOf")):
        name = local(choice)
        assert name is not None
        found[str(mapping(members(definitions, name)["form"])["const"])] = name
    return found


def form_member(form: str) -> str:
    """`record_format.md` section 5: "`value` for a constant; otherwise the member named like the form"."""
    return "value" if form == "constant" else form


def check_value_field_table(definitions: Definitions, read: Documents) -> None:
    rows = table(read("record_format.md"), "## 5. Value fields")
    assert list(forms(definitions)) == FORMS
    for form, name in forms(definitions).items():
        expected: set[str] = set()
        expected_required: set[str] = set()
        for row in rows:
            member = form_member(form) if row["Member"] == "the form's member" else only_code(row["Member"])
            # "`statistics` | yes, except for `evidence`": a field of form evidence has no statistics block
            # (`uncertainty.md` section 1).
            if re.search(rf"except for `{form}`", row["Required"]):
                continue
            expected.add(member)
            if row["Required"].startswith("yes"):
                expected_required.add(member)
        assert set(members(definitions, name)) == expected, form
        assert required(definitions, name) == expected_required, form
    beside = {
        str(listing(mapping(conjunct)["required"])[0])
        for conjunct in listing(at(definitions, "alternatives", "not", "anyOf"))
    }
    named = {only_code(row["Member"]) for row in rows if row["Member"] != "the form's member"}
    assert beside == named | {form_member(form) for form in FORMS}


def check_provenance_table(definitions: Definitions, read: Documents) -> None:
    rows = table(read("provenance.md"), "## 2. The provenance object")
    assert [only_code(row["Member"]) for row in rows] == list(members(definitions, "provenance"))
    assert {only_code(row["Member"]) for row in rows if row["Required"] == "yes"} == required(
        definitions, "provenance"
    )


def check_statistics_table(definitions: Definitions, read: Documents) -> None:
    text = read("uncertainty.md")
    rows = table(text, "## 1. The statistics block")
    named = [member for row in rows for member in codes(row["Member"])]
    assert named == list(members(definitions, "statistics_block"))
    conditional = codes(between(prose(text), "1. Every member is present", "each present exactly where"))
    assert required(definitions, "statistics_block") == set(named) - set(conditional)
    shape = re.match(r"`(\{[^`]*\})`, with `([a-z_]+)` where", cell_of(rows, "relative_uncertainty"))
    assert shape is not None
    sketched = re.findall(r'"([a-z_]+)"', shape[1])
    assert list(members(definitions, "uncertainty")) == [*sketched, shape[2]]
    assert required(definitions, "uncertainty") == set(sketched)


def token_condition(name: str) -> str:
    """The definition of the token condition `name`, which binds its `token` to its own row's tokens."""
    return f"condition_{name}"


def check_conditions_table(definitions: Definitions, read: Documents) -> None:
    text = read("provenance.md")
    rows = table(text, "### 6.1 Conditions of schema 0.1.0")
    shapes = {only_code(row["Name"]): row["Shape"] for row in rows}
    assert {
        name: alternatives(condition) for name, condition in members(definitions, "conditions").items()
    } == {
        name: ["numeric_condition" if shape == "numeric" else token_condition(name), "status_object"]
        for name, shape in shapes.items()
    }
    based = set(members(definitions, "based"))
    assert based <= set(codes(between(prose(text), "each shape except a status object carries", ".")))
    numeric, _, token = between(prose(text), "1. A numeric condition holds ", "[RC-047]").partition(
        "a token condition holds "
    )
    added = codes(between(numeric, "MAY add ", " (items"))
    assert set(members(definitions, "numeric_condition")) == sketched(numeric) | set(added) | based
    for name in (name for name, shape in shapes.items() if shape == "token"):
        assert set(members(definitions, token_condition(name))) == sketched(token) | based, name
        assert at(definitions, token_condition(name), "properties", "token") == {
            "$ref": f"vocabulary/conditions.json#/$defs/{name}_token"
        }, name
    entry = between(prose(text), "6. `plus_minus` records ", "`stated_as` is ")
    assert (
        set(members(definitions, "plus_minus_entry"))
        == sketched(entry)
        == required(definitions, "plus_minus_entry")
    )


def test_a_token_condition_takes_its_own_rows_tokens_and_no_other() -> None:
    """The writer refuses a token of another row, as `PR-045.condition_token_of_another_row` puts it, and one
    of no row (`PR-033`'s `porous`), and takes each of the row's own."""
    rows = json.loads((SCHEMA / "vocabulary" / "conditions.json").read_text(encoding="utf-8"))["conditions"]
    tokens: dict[str, set[str]] = {
        name: set(row["tokens"]) for name, row in rows.items() if row["shape"] == "token"
    }
    every = set[str]().union(*tokens.values())
    conditions = validator("record.writer.json#/$defs/conditions")
    for name, own in tokens.items():
        for token in sorted(own):
            assert conditions({name: {"token": token, "basis": "stated"}}) == [], (name, token)
        for token in sorted(every - own | {"porous"}):
            assert conditions({name: {"token": token, "basis": "stated"}}) != [], (name, token)


def sketched(text: str) -> set[str]:
    """The member names of the shapes sketched in the code spans of `text`: `{"value", "unit"}`."""
    return {
        name
        for shape in re.findall(r"`(\{[^`]*\})`", text)
        for name in re.findall(r'(?:\{|, )"([a-z_]+)"', shape)
    }


FACTS_VOCABULARY = "vocabulary/specimen_facts.json#/$defs/"


def check_specimen_table(definitions: Definitions, read: Documents) -> None:
    """Each fact's members; its `token` bound to the vocabulary's list of its row's tokens, each member its
    row fixes to one value (`"unit": "s"`) to the list of that value, and each identifier its row writes
    (`"UBERON:<digits>"`) to the vocabulary's pattern of that form; and no other member bound to either."""
    rows = table(read("provenance.md"), "### 6.2 Specimen facts of schema 0.1.0")
    facts = members(definitions, "specimen")
    assert [only_code(row["Name"]) for row in rows] == list(facts)
    entries: JsonValue = json.loads(json.dumps(specimen_facts(rows)["facts"]))
    fixed = {
        (name, "token" if member == "tokens" else member)
        for name, entry in mapping(entries).items()
        for member, value in mapping(entry).items()
        if value
    } | {
        (only_code(row["Name"]), member) for row in rows for member in identifier_patterns(row["JSON shape"])
    }
    bound: set[tuple[str, str]] = set()
    for row in rows:
        name = only_code(row["Name"])
        fact, status = alternatives(facts[name])
        assert status == "status_object", name
        # A basis the row fixes to `stated` leaves no `inferred_from`, which goes with `inferred` alone.
        based = set[str]() if (name, "basis") in fixed else set(members(definitions, "based"))
        assert set(members(definitions, fact)) == sketched(row["JSON shape"]) | based, name
        for member, subschema in mapping(definitions[fact].get("properties", {})).items():
            choices = listing(subschema.get("anyOf", [subschema])) if isinstance(subschema, dict) else []
            targets = [str(choice.get("$ref")) for choice in choices if isinstance(choice, dict)]
            if f"{FACTS_VOCABULARY}{name}_{member}" in targets:
                bound.add((name, member))
    assert bound == fixed


# A row's sentence giving a member as present exactly with some of its fact's tokens.
PRESENT_EXACTLY = re.compile(
    r"`([a-z_]+)`[^`]* is present exactly when `token` is (`[a-z_]+`(?:(?:,|, or| or) `[a-z_]+`)*)"
)


def present_exactly(definitions: Definitions, name: str) -> set[tuple[str, tuple[str, ...]]]:
    """The members the writer's definition `name` holds exactly with some tokens: a condition on its `token`
    whose `then` requires the member and whose `else` refuses it."""
    definition = definitions[name]
    rule = (definition.get("if"), definition.get("then"), definition.get("else"))
    if not all(isinstance(part, dict) for part in rule):
        return set()
    tested, then, otherwise = map(mapping, rule)
    if "token" not in mapping(tested.get("properties", {})):
        return set()
    choices = mapping(mapping(tested.get("properties", {})).get("token", {})).get("anyOf", [])
    tokens = tuple(str(mapping(choice)["const"]) for choice in listing(choices))
    (member,) = listing(then["required"])
    assert otherwise == {"not": {"required": [member]}}, name
    assert tested.get("required") == ["token"], name
    return {(str(member), tokens)}


def check_present_exactly(definitions: Definitions, read: Documents) -> None:
    """Each member a row of section 6.2 gives as present exactly with some tokens is so in the writer, and is
    required nowhere else; and no other fact holds such a rule."""
    rows = table(read("provenance.md"), "### 6.2 Specimen facts of schema 0.1.0")
    facts = members(definitions, "specimen")
    expected: dict[str, set[tuple[str, tuple[str, ...]]]] = {}
    for row in rows:
        name = only_code(row["Name"])
        if found := PRESENT_EXACTLY.search(row["JSON shape"]):
            expected[name] = {(found[1], tuple(codes(found[2])))}
    assert expected, "no row gives a member as present exactly with some tokens"
    for name in facts:
        (fact, _) = alternatives(facts[name])
        assert present_exactly(definitions, fact) == expected.get(name, set()), name
        for member, _ in expected.get(name, set()):
            assert member not in required(definitions, fact), name


def test_a_member_present_exactly_with_some_tokens_is_so_in_the_writer() -> None:
    check_present_exactly(DEFINITIONS, document)


@pytest.mark.parametrize(
    ("token", "text", "taken"),
    [
        ("normal", None, True),
        ("normal", "no lesion seen", False),
        ("diseased", "hepatic steatosis", True),
        ("diseased", None, False),
        ("treated", "after radiotherapy", True),
        ("treated", None, False),
    ],
)
def test_a_disease_or_treatment_state_holds_a_text_exactly_for_diseased_and_treated(
    token: str, text: str | None, taken: bool
) -> None:
    """`provenance.md` section 6.2 (maintainer, 2026-10-15): `normal` with a text is refused, and so is
    `diseased` or `treated` without one; the writer and the reader's `$defs` agree, since step 8 checks a
    known fact's shape."""
    fact: JsonValue = {"token": token, "basis": "stated", **({"text": text} if text is not None else {})}
    for schema in ("record.writer.json", "record.reader.json"):
        specimen = validator(f"{schema}#/$defs/specimen")
        assert (specimen({"disease_and_treatment_state": fact}) == []) is taken, (schema, token, text)


@pytest.mark.parametrize(
    ("fact", "valid", "invalid"),
    [
        (
            "post_mortem_interval",
            {"value": 7200, "unit": "s", "basis": "stated"},
            {"value": 120, "unit": "min", "basis": "stated"},
        ),
        (
            "donor_age",
            {"range": [1.0e9, 2.0e9], "unit": "s", "basis": "stated"},
            {"range": [30, 60], "unit": "a", "basis": "stated"},
        ),
        (
            "mimics",
            {"text": "liver parenchyma", "basis": "stated"},
            {"text": "liver parenchyma", "basis": "inferred", "inferred_from": "the maker's datasheet"},
        ),
    ],
)
def test_a_member_a_facts_row_fixes_takes_that_value_alone(
    fact: str, valid: JsonValue, invalid: JsonValue
) -> None:
    specimen = validator("record.writer.json#/$defs/specimen")
    assert specimen({fact: valid}) == []
    assert specimen({fact: invalid}) != []


def test_each_form_has_its_value_fields_members() -> None:
    check_value_field_table(DEFINITIONS, document)


def test_the_provenance_table_is_the_provenance_objects() -> None:
    check_provenance_table(DEFINITIONS, document)


def test_the_statistics_table_is_the_blocks_and_its_uncertainties() -> None:
    check_statistics_table(DEFINITIONS, document)


def test_the_conditions_table_is_the_conditions_and_their_shapes() -> None:
    check_conditions_table(DEFINITIONS, document)


def test_the_specimen_facts_table_is_the_facts_and_their_shapes() -> None:
    check_specimen_table(DEFINITIONS, document)


# Each row of `provenance.md` section 1's table, by the start of its Member cell, its Tokens cell as written,
# and the places of the writer schema it covers with the tokens each may hold: a definition and its member, or
# a definition with no member for one that is itself a choice between a shape and a status object. The rows of
# shapes that are still placeholders (a power law, a parameter set, an uncertainty structure) cover none.
STATUS_ROWS: list[tuple[str, str, dict[tuple[str, str | None], frozenset[str]]]] = [
    (
        "a form's member (",
        "`withheld`",
        {
            (form, form_member(token)): frozenset({"withheld"})
            for token, form in forms(DEFINITIONS).items()
            if token != "evidence"
        },
    ),
    (
        "`statistics`, wherever a block sits",
        "`withheld`; on reference data, `not_applicable` (`fits_and_reference_data.md` section 1)",
        {
            ("field_statistics", None): frozenset({"withheld"}),
            ("reference_data_field", "statistics"): frozenset({"withheld", "not_applicable"}),
        },
    ),
    (
        "in a statistics block, `central` and `basis`",
        "`not_applicable`",
        {("statistics_block", member): frozenset({"not_applicable"}) for member in ("central", "basis")},
    ),
    (
        "in a statistics block, `represents`",
        "`unstated`, `not_applicable`",
        {("statistics_block", "represents"): frozenset({"unstated", "not_applicable"})},
    ),
    (
        "in a statistics block, `distribution` and `precision_conditions`",
        "`unstated`",
        {
            (block, member): frozenset({"unstated"})
            for block, member in [
                ("statistics_block", "distribution"),
                ("statistics_block", "precision_conditions"),
                ("uncertainty", "distribution"),
                ("uncertainty", "represents"),
                ("uncertainty", "precision_conditions"),
            ]
        },
    ),
    (
        "in a statistics block, `population_level`",
        "`unstated`; in its `within`, `none`",
        {
            ("statistics_block", "population_level"): frozenset({"unstated"}),
            ("population_level", "within"): frozenset({"none"}),
        },
    ),
    (
        "in a statistics block, `n_specimens`",
        "any",
        {
            ("count", None): ANY,
            **{
                ("statistics_block", member): ANY
                for member in ("mean", "sd", "min", "max", "relative_uncertainty", "expanded_uncertainty")
            },
            **{("uncertainty", member): ANY for member in ("coverage_factor", "coverage_probability", "dof")},
        },
    ),
    (
        "an interval's `lower` and `upper`",
        "`none`",
        {("interval", member): frozenset({"none"}) for member in ("lower", "upper")},
    ),
    ("a power law's `range`", "`unstated`", {}),
    (
        "a condition, and a specimen fact",
        "any",
        {
            **{("conditions", name): ANY for name in members(DEFINITIONS, "conditions")},
            **{("specimen", name): ANY for name in members(DEFINITIONS, "specimen")},
        },
    ),
    (
        "a `plus_minus` entry's `stated_as`",
        "`unstated`",
        {("plus_minus_entry", "stated_as"): frozenset({"unstated"})},
    ),
    (
        "a `unit` or `axis_unit`, wherever it sits",
        "any, compared only at step 9 (`read_side_contract.md` section 3)",
        {("unit", None): ANY, ("post_mortem_interval", "unit"): ANY, ("donor_age", "unit"): ANY},
    ),
    (
        "each member of an evidence entry but `provenance`",
        "any; `withheld` only in every one of them at once (section 7 item 2)",
        {
            ("report_text", None): ANY - {"withheld"},
            ("evidence_entry", "standard"): ANY - {"withheld"},
            **{
                ("withheld_evidence_entry", member): frozenset({"withheld"})
                for member in members(DEFINITIONS, "withheld_evidence_entry")
                if member != "provenance"
            },
        },
    ),
    (
        "`review`, in a provenance object",
        "`not_checked` (section 2 item 6)",
        {("provenance", "review"): frozenset({"not_checked"})},
    ),
    ("`assistance`, in a provenance object", "`none`", {("provenance", "assistance"): frozenset({"none"})}),
    ("a parameter set's `params`", "`not_applicable`", {}),
    ("a parameter set's `witness`", "`none`; in its `datum`, `withheld`", {}),
    ("an `ensemble`'s `counts`", "any", {}),
    ("a `marginals` structure's `dependence`", "`unstated`", {}),
]


def status_tokens(definitions: Definitions, name: str) -> frozenset[str] | None:
    """The tokens a status object of definition `name` holds, or None for a definition that is not one."""
    if name != "status_object" and not name.startswith("status_"):
        return None
    status = members(definitions, name)["status"]
    assert isinstance(status, dict)
    tokens = status["enum"]
    assert isinstance(tokens, list)
    return frozenset(str(token) for token in tokens)


def status_places(definitions: Definitions) -> dict[tuple[str, str | None], frozenset[str]]:
    """Every place of the writer schema where a status object may stand, and the tokens it may hold there."""
    found: dict[tuple[str, str | None], frozenset[str]] = {}
    for name, definition in definitions.items():
        places: list[tuple[str | None, JsonValue]] = [(None, definition)]
        places += list(mapping(definition.get("properties", {})).items())
        for member, subschema in places:
            tokens = [status_tokens(definitions, choice) for choice in alternatives(subschema)]
            if held := frozenset[str]().union(*[found for found in tokens if found is not None]):
                found[(name, member)] = held
    return found


def check_status_objects(definitions: Definitions, read: Documents) -> None:
    rows = table(read("provenance.md"), "## 1. Status objects")
    assert len(rows) == len(STATUS_ROWS)
    for row, (start, tokens, _) in zip(rows, STATUS_ROWS, strict=True):
        assert row["Member"].startswith(start), start
        assert row["Tokens"] == tokens, start
    allowed = {place: held for _, _, places in STATUS_ROWS for place, held in places.items()}
    assert status_places(definitions) == allowed


def test_a_status_object_stands_where_section_1_allows_it_and_nowhere_else() -> None:
    check_status_objects(DEFINITIONS, document)


# The specification's examples of the shapes a value field holds, each a member of a fenced JSON block: the
# document, the text the block follows, and the definition it must be valid against.
EXAMPLES = [
    ("provenance.md", "## 2. The provenance object", "provenance"),
    ("provenance.md", "## 6. Conditions and specimen facts", "conditions"),
    ("uncertainty.md", "## 1. The statistics block", "statistics_block"),
    ("record_format.md", "**Interval.**", "interval"),
    ("record_format.md", "**Composition.**", "composition"),
]


@pytest.mark.parametrize(("name", "after", "definition"), EXAMPLES, ids=[example[2] for example in EXAMPLES])
def test_the_specifications_example_is_a_valid_shape(name: str, after: str, definition: str) -> None:
    text = document(name)
    block = re.search(r"```json\n(.*?)\n```", text[text.index(after) :], re.S)
    assert block is not None
    ((_, example),) = json.loads("{" + block[1] + "}").items()
    assert validator(f"record.writer.json#/$defs/{definition}")(example) == []


# The rules that join members of different objects (`provenance.md` sections 2, 3 and 7). Each case is a
# field that meets the rule's condition without the member it requires, the member that completes it, and the
# field again with the condition not met and the member still absent.
POPULATION: JsonValue = {
    "central": "mean",
    "n_specimens": 12,
    "n_donors": 4,
    "mean": 1050.0,
    "sd": 12.0,
    "min": 1031.0,
    "max": 1072.0,
    "distribution": {"status": "unstated"},
    "basis": "reported_sd",
    "represents": "population",
    "population_level": {"level": "specimen", "within": {"status": "none"}},
    "dispersion": "reported",
    "relative_uncertainty": {"status": "none"},
    "expanded_uncertainty": {"status": "none"},
}
ACROSS_SOURCES: JsonValue = {
    **mapping(copy.deepcopy(POPULATION)),
    "basis": "across_sources",
    "represents": "across_sources",
    "n_sources": 3,
}
del mapping(ACROSS_SOURCES)["population_level"]
PROVENANCE: JsonValue = {
    "origin": "measured_by_contributor",
    "extraction": {"method": "own_measurement"},
    "assistance": {"status": "none"},
    "review": {"status": "not_checked"},
}
CONSTANT: JsonValue = {
    "form": "constant",
    "unit": "kg/m3",
    "value": 1050.0,
    "conditions": {"temperature": {"value": 310.15, "unit": "K", "basis": "stated"}},
    "statistics": POPULATION,
    "provenance": PROVENANCE,
}
INTERVAL: JsonValue = {
    **{member: value for member, value in mapping(CONSTANT).items() if member != "value"},
    "form": "interval",
    "interval": {"lower": 1000.0, "upper": 1100.0, "basis": "reported_range"},
}
DERIVATION: JsonValue = {
    "method": "density_from_mass_and_volume",
    "inputs": [
        {
            "record": {"id": "example/MAT-1", "version": "1.0.0", "content_hash": "sha256:" + "0" * 64},
            "field": "bulk.density",
        }
    ],
    "assumptions": [],
    "input_specimens": [],
}
WITHHELD: JsonValue = {"status": "withheld"}
REPORT = ("endpoint", "standard", "contact_category", "contact_duration", "material_form", "processing")


def edited(base: JsonValue, *edits: tuple[tuple[str, ...], JsonValue]) -> JsonValue:
    """A copy of `base` with each value set at its path of names."""
    found = copy.deepcopy(base)
    for path, value in edits:
        *inner, last = path
        node = found
        for name in inner:
            node = mapping(node)[name]
        mapping(node)[last] = value
    return found


def evidence(entry: JsonValue) -> JsonValue:
    return {
        "form": "evidence",
        "unit": {"status": "not_applicable"},
        "evidence": [entry],
        "conditions": {},
        "provenance": PROVENANCE,
    }


WITHHELD_ENTRY: JsonValue = {
    **{member: WITHHELD for member in (*REPORT, "reported_result")},
    "provenance": PROVENANCE,
}
REPORTED_ENTRY: JsonValue = {
    **{member: {"status": "unstated"} for member in REPORT},
    "standard": {"designation": "ISO 10993-5", "year": 2009},
    "reported_result": "non-cytotoxic",
    "provenance": PROVENANCE,
}
JOINED: list[tuple[str, JsonValue, tuple[tuple[str, ...], JsonValue], JsonValue]] = [
    (
        "derivation_extracted_by_derivation",
        edited(CONSTANT, (("provenance", "extraction", "method"), "derivation")),
        (("provenance", "derivation"), DERIVATION),
        CONSTANT,
    ),
    (
        "formulation_extracted_by_formulation",
        edited(CONSTANT, (("provenance", "extraction", "method"), "formulation")),
        (("provenance", "formulation"), {"name": "IAPWS-95", "version": "2018"}),
        CONSTANT,
    ),
    (
        "fit_extracted_by_fit",
        edited(CONSTANT, (("provenance", "extraction", "method"), "fit")),
        (("fit",), {"procedure": "least squares"}),
        CONSTANT,
    ),
    (
        "search_across_sources",
        edited(CONSTANT, (("statistics",), ACROSS_SOURCES)),
        (("provenance", "search"), {"inputs": "primary"}),
        CONSTANT,
    ),
    (
        "recipe_for_a_withheld_value",
        edited(CONSTANT, (("value",), WITHHELD), (("statistics",), WITHHELD)),
        (("provenance", "recipe"), {"steps": "Table 2, row liver"}),
        CONSTANT,
    ),
    (
        "recipe_for_a_withheld_interval",
        edited(INTERVAL, (("interval",), WITHHELD), (("statistics",), WITHHELD)),
        (("provenance", "recipe"), {"steps": "Table 2, row liver"}),
        INTERVAL,
    ),
    (
        "recipe_for_a_withheld_evidence_entry",
        evidence(WITHHELD_ENTRY),
        (("evidence", "0", "provenance", "recipe"), {"steps": "Table 4"}),
        evidence(REPORTED_ENTRY),
    ),
]


@pytest.mark.parametrize(
    ("place", "shape"),
    [
        *[((form,), {"rows": []}) for form in ("table", "power_law", "parameter_set", "reference_data")],
        (("provenance", "assistance"), {"tool": "a drafting tool"}),
    ],
    ids=["table", "power_law", "parameter_set", "reference_data", "assistance"],
)
def test_a_placeholder_beside_a_status_object_holds_no_other_status(
    place: tuple[str, ...], shape: JsonValue
) -> None:
    """`provenance.md` section 1 item 5: in a member that may hold a status object, an object holding
    `status` is one, and holds a token its row allows. A placeholder's shape, any object until its members are
    named, takes every other object; the control is that shape and the row's own token."""
    own: JsonValue = {"status": "none" if place[-1] == "assistance" else "withheld"}
    base = mapping(CONSTANT)
    if len(place) == 1:
        # Another form, whose member is the placeholder; withheld, it needs its recipe (section 7 item 2).
        base = {member: value for member, value in base.items() if member != "value"}
        base = mapping(edited(base, (("form",), place[0]), (("provenance", "recipe"), {"steps": "Table 2"})))
    writer = validator("record.writer.json#/$defs/value_field")
    held: list[tuple[JsonValue, bool]] = [(shape, True), (own, True), ({"status": "unstated"}, False)]
    for value, taken in held:
        assert (writer(edited(base, (place, value))) == []) is taken, (place, value)


def completed(field: JsonValue, member: tuple[tuple[str, ...], JsonValue]) -> JsonValue:
    (path, value) = member
    found = copy.deepcopy(field)
    node = found
    for name in path[:-1]:
        node = listing(node)[int(name)] if name.isdigit() else mapping(node)[name]
    mapping(node)[path[-1]] = value
    return found


@pytest.mark.parametrize(
    ("field", "member", "unmet"),
    [(field, member, unmet) for _, field, member, unmet in JOINED],
    ids=[case[0] for case in JOINED],
)
def test_a_rule_across_objects_requires_its_member_where_its_condition_holds(
    field: JsonValue, member: tuple[tuple[str, ...], JsonValue], unmet: JsonValue
) -> None:
    """The writer refuses the field without the member and takes it with it; the control is the field with
    the condition not met, taken without the member. A read applies none of these rules (step 8 checks
    neither `extraction`, `search`, `recipe` nor `fit`), so the reader's `$defs` take the field either way."""
    writer = validator("record.writer.json#/$defs/value_field")
    reader = validator("record.reader.json#/$defs/value_field")
    assert writer(field) != []
    assert writer(completed(field, member)) == []
    assert writer(unmet) == []
    assert reader(field) == []


# The members a read does not check, each with the text that says so: `read_side_contract.md` section 3, step
# 8, and `provenance.md` section 2 item 6.
UNCHECKED = {
    ("field_members", "fit"): (
        "read_side_contract.md",
        "the other members of a value field are left to the record checks",
    ),
    **{
        ("provenance", member): ("provenance.md", "The other members are checked on the write side only.")
        for member in (
            "extraction",
            "evidence",
            "assistance",
            "formulation",
            "search",
            "import",
            "per_parameter",
            "recipe",
        )
    },
    ("provenance", "review"): ("provenance.md", "`review` never refuses the field."),
    ("source", "document"): (
        "provenance.md",
        "(its `document` and `locator` are the record checks', RC-044)",
    ),
    ("source", "locator"): ("provenance.md", "(its `document` and `locator` are the record checks', RC-044)"),
}
# The members a read checks only where members of their object hold tokens, marked write-only `unless` they
# do, each with those tokens and the text that names the member and each of them: `provenance.md` section 2
# item 6.
CHECKED_WHERE = {
    ("provenance", "derivation"): (
        {"origin": "derived"},
        "provenance.md",
        "`derivation` for origin `derived` (section 5)",
    ),
}
# What step 8 checks, which no member marked write-only may be, by the text that names it.
STEP_8 = (
    "the form's member; `unit`, only as a string or a status object (`record_format.md` section 4.2), since "
    "step 9 alone compares it; each condition and specimen fact whose name the reader knows; the statistics "
    "block and its uncertainties, a composition component's block included; `label`; and in `provenance` its "
    "`origin`, its `source` (present for origin `measured_by_source`, and its `key` wherever present) and a "
    "`derivation`"
)
CHECKED = (
    {("field_members", member) for member in ("unit", "specimen", "provenance", "label")}
    | {("provenance", member) for member in ("origin", "source", "derivation")}
    | {("source", "key")}
)


def write_only(definitions: Definitions) -> set[tuple[str, str]]:
    return {
        (name, member)
        for name, definition in definitions.items()
        for member, subschema in mapping(definition.get("properties", {})).items()
        if isinstance(subschema, dict) and subschema.get(WRITE_ONLY) is True
    }


def write_only_unless(definitions: Definitions) -> dict[tuple[str, str], JsonValue]:
    """Each member marked write-only `unless` members of its object hold tokens, with those tokens."""
    return {
        (name, member): mapping(subschema[WRITE_ONLY]).get("unless")
        for name, definition in definitions.items()
        for member, subschema in mapping(definition.get("properties", {})).items()
        if isinstance(subschema, dict) and isinstance(subschema.get(WRITE_ONLY), dict)
    }


def check_write_only(definitions: Definitions, read: Documents) -> None:
    for name, quote in [*UNCHECKED.values(), ("read_side_contract.md", STEP_8)]:
        assert quote in prose(read(name)), quote
    assert write_only(definitions) == set(UNCHECKED)
    for form, name in forms(definitions).items():
        own = {(name, member) for member in ("form", form_member(form), "conditions", "statistics")}
        assert not write_only(definitions) & (own | CHECKED), form
    for (_, member), (tokens, name, quote) in CHECKED_WHERE.items():
        assert quote in prose(read(name)), quote
        assert f"`{member}`" in quote
        assert all(f"{held} `{token}`" in quote for held, token in tokens.items())
    assert write_only_unless(definitions) == {
        place: tokens for place, (tokens, _, _) in CHECKED_WHERE.items()
    }
    assert set(CHECKED_WHERE) <= CHECKED


def test_the_members_marked_write_only_are_those_step_8_does_not_check() -> None:
    check_write_only(DEFINITIONS, document)


def constants(node: JsonValue) -> Iterator[str]:
    if isinstance(node, dict):
        if isinstance(constant := node.get("const"), str):
            yield constant
        for value in node.values():
            yield from constants(value)
    elif isinstance(node, list):
        for value in node:
            yield from constants(value)


def enumerated(node: JsonValue) -> Iterator[str]:
    if isinstance(node, dict):
        if isinstance(tokens := node.get("enum"), list):
            yield from (str(token) for token in tokens)
        for value in node.values():
            yield from enumerated(value)
    elif isinstance(node, list):
        for value in node:
            yield from enumerated(value)


def test_every_token_the_writer_schema_writes_out_is_one_it_lists() -> None:
    """A `const` (a form's token, or one an `if` tests) is written by hand, so it must be a token of the
    vocabulary or of the schema's own enumerations; and the check of a `plus_minus` names every kind an entry
    may state."""
    vocabulary = {
        token
        for path in (SCHEMA / "vocabulary").glob("*.json")
        for token in enumerated(json.loads(path.read_text(encoding="utf-8")))
    }
    assert set(constants(WRITER)) <= vocabulary | set(enumerated(WRITER))
    stated_as = json.loads((SCHEMA / "vocabulary" / "provenance.json").read_text(encoding="utf-8"))
    kinds = list(constants(at(DEFINITIONS, "plus_minus", "then")))
    assert kinds == stated_as["$defs"]["stated_as"]["enum"]


def changed_document(name: str, old: str, new: str) -> Documents:
    """The documents, `name` with `old`, which must be there, replaced by `new`."""
    changed = document(name)
    assert old in changed, old
    changed = changed.replace(old, new, 1)
    return lambda other: changed if other == name else document(other)


def setting(value: JsonValue, name: str, *path: str) -> Callable[[Definitions], None]:
    """A change of the definitions: `value` set at `path` inside the definition `name`."""

    def change(definitions: Definitions) -> None:
        *inner, last = path
        mapping(at(definitions, name, *inner))[last] = value

    return change


def removing(name: str, *path: str) -> Callable[[Definitions], None]:
    """A change of the definitions: the member at `path` inside the definition `name` removed."""

    def change(definitions: Definitions) -> None:
        *inner, last = path
        del mapping(at(definitions, name, *inner))[last]

    return change


def dropping_last(name: str, *path: str) -> Callable[[Definitions], None]:
    """A change of the definitions: the list at `path` inside the definition `name` without its last item."""

    def change(definitions: Definitions) -> None:
        listing(at(definitions, name, *path)).pop()

    return change


@pytest.mark.parametrize(
    ("check", "read", "change"),
    [
        pytest.param(
            check_value_field_table,
            changed_document("record_format.md", "| `fit` | where", "| `fits` | where"),
            None,
            id="value_field_member_renamed",
        ),
        pytest.param(
            check_value_field_table,
            changed_document("record_format.md", "| `specimen` | no |", "| `specimen` | yes |"),
            None,
            id="value_field_member_required",
        ),
        pytest.param(
            check_value_field_table,
            document,
            dropping_last("alternatives", "not", "anyOf"),
            id="alternatives_beside_a_member",
        ),
        pytest.param(
            check_provenance_table,
            changed_document("provenance.md", "| `assistance` | yes |", "| `assistance` | no |"),
            None,
            id="provenance_member_optional",
        ),
        pytest.param(
            check_statistics_table,
            changed_document("uncertainty.md", '"basis", "represents"}`, with', '"basis"}`, with'),
            None,
            id="uncertainty_member_dropped",
        ),
        pytest.param(
            check_conditions_table,
            changed_document("provenance.md", "| `specimen_size` | numeric |", "| `specimen_size` | token |"),
            None,
            id="condition_shape",
        ),
        pytest.param(
            check_conditions_table,
            changed_document("provenance.md", '`{"stated_as",', '`{"stated_as", "note",'),
            None,
            id="plus_minus_entry",
        ),
        pytest.param(
            check_conditions_table,
            document,
            setting({"type": "string"}, "condition_density_kind", "properties", "token"),
            id="condition_token_unbound",
        ),
        pytest.param(
            check_conditions_table,
            document,
            setting(
                {"$ref": "vocabulary/conditions.json#/$defs/specimen_shape_token"},
                "condition_density_kind",
                "properties",
                "token",
            ),
            id="condition_token_of_another_row",
        ),
        pytest.param(
            check_specimen_table,
            changed_document(
                "provenance.md", '`{"text": <text>, "basis"}` |', '`{"text": <text>, "note", "basis"}` |'
            ),
            None,
            id="fact_member_added",
        ),
        pytest.param(
            check_specimen_table,
            document,
            setting(
                {
                    "anyOf": [
                        {"type": "string", "pattern": "^s(?![\\s\\S])"},
                        {"$ref": "#/$defs/status_object"},
                    ]
                },
                "post_mortem_interval",
                "properties",
                "unit",
            ),
            id="fact_unit_written_by_hand",
        ),
        pytest.param(
            check_specimen_table,
            document,
            removing("mimics", "properties", "basis"),
            id="fact_basis_unbound",
        ),
        pytest.param(
            check_specimen_table,
            document,
            setting(
                {"type": "string", "pattern": "^UBERON:[0-9]+(?![\\s\\S])"},
                "anatomical_site",
                "properties",
                "uberon",
            ),
            id="fact_identifier_written_by_hand",
        ),
        pytest.param(
            check_specimen_table,
            changed_document("provenance.md", '"uberon": "UBERON:<digits>"', '"uberon": <text>'),
            None,
            id="fact_identifier_no_longer_written",
        ),
        pytest.param(
            check_specimen_table,
            changed_document(
                "provenance.md", '`{"text": <text>, "basis": "stated"}`', '`{"text": <text>, "basis"}`'
            ),
            None,
            id="fact_basis_no_longer_fixed",
        ),
        pytest.param(
            check_present_exactly,
            changed_document("provenance.md", "`token` is `diseased` or `treated`", "`token` is `diseased`"),
            None,
            id="present_exactly_with_another_token",
        ),
        pytest.param(
            check_present_exactly,
            changed_document(
                "provenance.md", ", and is present exactly when `token` is", ", whenever `token` is"
            ),
            None,
            id="present_exactly_no_longer_said",
        ),
        pytest.param(
            check_present_exactly,
            document,
            removing("disease_and_treatment_state", "else"),
            id="present_beside_another_token",
        ),
        pytest.param(
            check_present_exactly,
            document,
            setting(["token", "text"], "disease_and_treatment_state", "required"),
            id="required_with_every_token",
        ),
        pytest.param(
            check_status_objects,
            changed_document(
                "provenance.md",
                "| in a statistics block, `represents` | `unstated`, `not_applicable` |",
                "| in a statistics block, `represents` | `unstated` |",
            ),
            None,
            id="status_tokens_reworded",
        ),
        pytest.param(
            check_status_objects,
            document,
            setting(
                {"anyOf": [{"type": "integer"}, {"$ref": "#/$defs/status_object"}]},
                "standard",
                "properties",
                "year",
            ),
            id="status_object_elsewhere",
        ),
        pytest.param(
            check_status_objects,
            document,
            setting(
                {"anyOf": [{"type": "number"}, {"$ref": "#/$defs/status_object"}]},
                "interval",
                "properties",
                "lower",
            ),
            id="status_token_widened",
        ),
        pytest.param(
            check_write_only,
            document,
            removing("provenance", "properties", "search", WRITE_ONLY),
            id="write_only_unmarked",
        ),
        pytest.param(
            check_write_only,
            document,
            setting(True, "field_members", "properties", "label", WRITE_ONLY),
            id="checked_member_marked",
        ),
        pytest.param(
            check_write_only,
            changed_document(
                "provenance.md",
                "The other members are checked on the write side only.",
                "The other members are checked at read.",
            ),
            None,
            id="write_only_quote_gone",
        ),
        pytest.param(
            check_write_only,
            document,
            removing("provenance", "properties", "derivation", WRITE_ONLY),
            id="derivation_checked_beside_every_origin",
        ),
        pytest.param(
            check_write_only,
            document,
            setting(True, "provenance", "properties", "derivation", WRITE_ONLY),
            id="derivation_marked_write_only",
        ),
        pytest.param(
            check_write_only,
            document,
            setting({"unless": {"origin": "fitted"}}, "provenance", "properties", "derivation", WRITE_ONLY),
            id="derivation_checked_beside_another_origin",
        ),
        pytest.param(
            check_write_only,
            document,
            setting({"unless": {"origin": "derived"}}, "provenance", "properties", "source", WRITE_ONLY),
            id="source_checked_under_a_condition",
        ),
        pytest.param(
            check_write_only,
            changed_document(
                "provenance.md", "`derivation` for origin `derived` (section 5)", "`derivation` (section 5)"
            ),
            None,
            id="derivation_condition_gone_from_the_text",
        ),
    ],
)
def test_each_value_field_check_can_fail(
    check: Callable[[Definitions, Documents], None],
    read: Documents,
    change: Callable[[Definitions], None] | None,
) -> None:
    definitions = copy.deepcopy(DEFINITIONS)
    if change is not None:
        change(definitions)
    with pytest.raises(AssertionError):
        check(definitions, read)


# Where the writer schema leaves a record open: a placeholder holding any JSON, or an object it does not
# close, such as a map keyed by names it does not bind.
ANY_JSON = ("json_object", "json_value")
VOCABULARY = "vocabulary/"
# A vocabulary file by name, read from this tree; the controls give a changed copy.
Files = Callable[[str], Schema]


def vocabulary_file(name: str) -> Schema:
    return mapping(json.loads((SCHEMA / "vocabulary" / name).read_text(encoding="utf-8")))


def bindings_of(definition: Schema, files: Files) -> list[Schema]:
    """The bindings of the vocabulary that the `allOf` of `definition` applies."""
    found: list[Schema] = []
    for conjunct in listing(definition.get("allOf", [])):
        target = mapping(conjunct).get("$ref")
        if isinstance(target, str) and target.startswith(VOCABULARY):
            name, _, pointer = target.removeprefix(VOCABULARY).partition("#")
            node: JsonValue = files(name)
            for step in filter(None, pointer.split("/")):
                node = mapping(node)[step]
            found.append(mapping(node))
    return found


def names_closed(binding: JsonValue) -> bool:
    return isinstance(binding, dict) and "enum" in mapping(binding.get("propertyNames", {}))


def is_map(subschema: JsonValue, definitions: Definitions) -> bool:
    """Whether a member holding `subschema` holds an object keyed by names: one whose `additionalProperties`
    is a schema."""
    held = local(subschema)
    return held is not None and isinstance(definitions[held].get("additionalProperties"), dict)


def bound_maps(definitions: Definitions, files: Files) -> set[str]:
    """The map members whose names a binding of the vocabulary closes wherever the writer reaches them: a
    binding applied to a map's own definition (`replaces`), or one applied to a definition that gives, under
    each of its members, the names of each map that member holds (each section's `fields`)."""
    closed: dict[str, list[bool]] = {}
    for name, definition in definitions.items():
        for binding in bindings_of(definition, files):
            if names_closed(binding):
                for owner in definitions.values():
                    for member, subschema in mapping(owner.get("properties", {})).items():
                        if local(subschema) == name:
                            closed.setdefault(member, []).append(True)
            for member, subschema in mapping(definition.get("properties", {})).items():
                held = local(subschema)
                bound = mapping(mapping(binding.get("properties", {})).get(member, {}))
                for inner, inner_schema in mapping(
                    definitions[held].get("properties", {}) if held else {}
                ).items():
                    if is_map(inner_schema, definitions):
                        inner_binding = mapping(bound.get("properties", {})).get(inner)
                        closed.setdefault(inner, []).append(names_closed(inner_binding))
    return {member for member, places in closed.items() if all(places)}


def opens(subschema: JsonValue, definitions: Definitions, seen: frozenset[str] = frozenset()) -> bool:
    """Whether a member holding `subschema` may hold what the writer schema does not define: through a
    `$ref`, a choice or an array's items, a placeholder or an object without `additionalProperties` or
    `unevaluatedProperties` false."""
    if not isinstance(subschema, dict):
        return False
    if (name := local(subschema)) is not None:
        return name in ANY_JSON or (name not in seen and opens(definitions[name], definitions, seen | {name}))
    parts = [*listing(subschema.get("anyOf", [])), *listing(subschema.get("oneOf", []))]
    parts += [subschema.get("items"), *listing(subschema.get("prefixItems", []))]
    if any(opens(part, definitions, seen) for part in parts):
        return True
    if subschema.get("type") != "object" and "properties" not in subschema:
        return False
    closing = (subschema.get("additionalProperties"), subschema.get("unevaluatedProperties"))
    return subschema.get("propertyNames") is not False and False not in closing


def open_members(writer: Schema, definitions: Definitions, files: Files) -> set[str]:
    owners = [writer, *definitions.values()]
    return {
        member
        for owner in owners
        for member, subschema in mapping(owner.get("properties", {})).items()
        if opens(subschema, definitions)
    } - bound_maps(definitions, files)


def check_description(writer: Schema, definitions: Definitions, files: Files = vocabulary_file) -> None:
    """The writer's description says it is closed but for the members it names, each in a code span: exactly
    those that open it, a map whose names a binding of the vocabulary closes being closed."""
    description = str(writer["description"])
    assert "closed in its structure" in description
    assert set(re.findall(r"`([a-z_]+)`", description)) == open_members(writer, definitions, files)


def test_the_writer_schema_is_closed_but_where_its_description_says() -> None:
    check_description(WRITER, DEFINITIONS)


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(removing("interval", "additionalProperties"), id="a_shape_opened"),
        pytest.param(
            setting({"$ref": "#/$defs/json_object"}, "standard", "properties", "designation"),
            id="a_placeholder",
        ),
        pytest.param(
            setting(
                {"type": "object", "additionalProperties": {"type": "string"}},
                "copy",
                "properties",
                "retrieved",
            ),
            id="a_map",
        ),
    ],
)
def test_the_description_check_can_fail(change: Callable[[Definitions], None]) -> None:
    writer = copy.deepcopy(WRITER)
    change(writer["$defs"])
    with pytest.raises(AssertionError):
        check_description(writer, writer["$defs"])


def test_the_description_check_fails_on_a_place_left_unnamed() -> None:
    writer = copy.deepcopy(WRITER)
    writer["description"] = str(writer["description"]).replace("`digitisation`", "digitisation")
    with pytest.raises(AssertionError):
        check_description(writer, writer["$defs"])


def changed_file(name: str, change: Callable[[Schema], None]) -> Files:
    """The vocabulary files, `name` changed by `change`."""
    changed = vocabulary_file(name)
    change(changed)
    return lambda other: changed if other == name else vocabulary_file(other)


def editing(*path: str, to: JsonValue = None) -> Callable[[Schema], None]:
    """A change of a vocabulary file: the member at `path` of its `$defs` set to `to`, or removed for None."""

    def change(contents: Schema) -> None:
        *inner, last = path
        node = mapping(contents["$defs"])
        for name in inner:
            node = mapping(node[name])
        if to is None:
            del node[last]
        else:
            node[last] = to

    return change


SECTION_NAMES = ("sections", "properties", "magnetic", "properties", "fields", "propertyNames")


@pytest.mark.parametrize(
    ("change", "files"),
    [
        pytest.param(
            removing("sections", "allOf"), vocabulary_file, id="the_writer_applies_no_section_binding"
        ),
        pytest.param(
            removing("replaces", "allOf"), vocabulary_file, id="the_writer_applies_no_replaces_binding"
        ),
        pytest.param(
            None, changed_file("fields.json", editing(*SECTION_NAMES)), id="one_sections_names_open"
        ),
        pytest.param(
            None, changed_file("fields.json", editing("replaces", "propertyNames")), id="replaced_names_open"
        ),
    ],
)
def test_the_description_check_fails_where_a_binding_no_longer_closes_a_map(
    change: Callable[[Definitions], None] | None, files: Files
) -> None:
    """The description no longer names `fields` and `replaces`, which the vocabulary's bindings close: a map a
    binding leaves open, in one section or in the writer, is a place the description must name."""
    writer = copy.deepcopy(WRITER)
    if change is not None:
        change(writer["$defs"])
    with pytest.raises(AssertionError):
        check_description(writer, writer["$defs"], files)


# The bindings of the rows (maintainer, 2026-10-15): `record_format.md` section 4.1's, which close each
# section's field names and an overlay's replaced fields and bind each field's forms, bases, unit and label,
# and `provenance.md` section 6.1's numeric units. The vocabulary generates each from its rows; the writer
# schema applies each by `allOf`, at the one definition named here, and writes no list of its own.
APPLIED = {
    "sections": "vocabulary/fields.json#/$defs/sections",
    "replaces": "vocabulary/fields.json#/$defs/replaces",
    "conditions": "vocabulary/conditions.json#/$defs/units",
}


def status_unit(token: str) -> Schema:
    """A unit registered as a status object: one holding the same token, whatever its reason (section 4.2)."""
    return {"type": "object", "required": ["status"], "properties": {"status": {"const": token}}}


def field_binding(qualified: str, row: Schema) -> Schema:
    unit = row["unit"]
    bases = mapping(row.get("bases", {}))
    label = row.get("label")
    return {
        "properties": {
            "form": {"enum": row["forms"]},
            "unit": {"const": unit} if isinstance(unit, str) else status_unit(str(mapping(unit)["status"])),
            "label": False if label is None else {"const": label},
            **{form: {"properties": {"basis": {"enum": allowed}}} for form, allowed in bases.items()},
            "alternatives": {"items": {"$ref": f"#/$defs/{qualified}"}},
        }
    }


def check_bindings(definitions: Definitions, files: Files) -> None:
    """Each binding applied by the definition named for it and by no other, holding exactly what the
    vocabulary's rows give: each section's field names, the replaced fields, each field's row, and each
    numeric condition's unit, in its `unit` and its `plus_minus` entries'."""
    applied: dict[str, list[str]] = {}
    for name, definition in definitions.items():
        for conjunct in listing(definition.get("allOf", [])):
            if str(target := mapping(conjunct).get("$ref")).startswith(VOCABULARY):
                applied.setdefault(name, []).append(str(target))
    assert applied == {name: [target] for name, target in APPLIED.items()}
    rows = mapping(files("fields.json")["fields"])
    bound = mapping(files("fields.json")["$defs"])
    sections: dict[str, list[str]] = {}
    for qualified in rows:
        section, _, name = qualified.partition(".")
        sections.setdefault(section, []).append(name)
    assert list(members(definitions, "sections")) == list(sections)
    assert mapping(bound["sections"])["properties"] == {
        section: {
            "properties": {
                "fields": {
                    "propertyNames": {"enum": names},
                    "properties": {name: {"$ref": f"#/$defs/{section}.{name}"} for name in names},
                }
            }
        }
        for section, names in sections.items()
    }
    replaces = mapping(bound["replaces"])
    assert replaces["propertyNames"] == {"enum": list(rows)}
    assert replaces["properties"] == {qualified: {"$ref": f"#/$defs/{qualified}"} for qualified in rows}
    for qualified, row in rows.items():
        assert bound[qualified] == field_binding(qualified, mapping(row)), qualified
    conditions = mapping(files("conditions.json")["conditions"])
    units = {
        name: mapping(row)["unit"] for name, row in conditions.items() if mapping(row)["shape"] == "numeric"
    }
    assert mapping(mapping(files("conditions.json")["$defs"])["units"])["properties"] == {
        name: {
            "properties": {
                "unit": {"const": unit},
                "plus_minus": {"items": {"properties": {"unit": {"const": unit}}}},
            }
        }
        for name, unit in units.items()
    }


def test_the_writer_binds_each_name_to_its_row_through_the_vocabulary() -> None:
    check_bindings(DEFINITIONS, vocabulary_file)


@pytest.mark.parametrize(
    ("change", "files"),
    [
        pytest.param(removing("sections", "allOf"), vocabulary_file, id="sections_unbound"),
        pytest.param(removing("replaces", "allOf"), vocabulary_file, id="replaces_unbound"),
        pytest.param(removing("conditions", "allOf"), vocabulary_file, id="condition_units_unbound"),
        pytest.param(
            setting([{"$ref": "vocabulary/fields.json#/$defs/sections"}], "section", "allOf"),
            vocabulary_file,
            id="a_binding_applied_elsewhere",
        ),
        pytest.param(
            setting({"$ref": "#/$defs/section"}, "sections", "properties", "thermal"),
            vocabulary_file,
            id="a_section_with_no_row",
        ),
        pytest.param(
            None,
            changed_file("fields.json", editing(*SECTION_NAMES)),
            id="a_sections_names_open",
        ),
        pytest.param(
            None,
            changed_file(
                "fields.json", editing("bulk.density", "properties", "form", to={"enum": ["constant"]})
            ),
            id="a_form_dropped",
        ),
        pytest.param(
            None,
            changed_file("fields.json", editing("bulk.density", "properties", "unit", to=None)),
            id="a_unit_unbound",
        ),
        pytest.param(
            None,
            changed_file("fields.json", editing("magnetic.remanence", "properties", "label", to=None)),
            id="a_label_unbound",
        ),
        pytest.param(
            None,
            changed_file(
                "fields.json", editing("bulk.elemental_composition", "properties", "composition", to=None)
            ),
            id="a_basis_unbound",
        ),
        pytest.param(
            None,
            changed_file(
                "fields.json", editing("fluid.dynamic_viscosity", "properties", "alternatives", to=None)
            ),
            id="alternatives_unbound",
        ),
        pytest.param(
            None,
            changed_file("conditions.json", editing("units", "properties", "temperature", to=None)),
            id="a_condition_unit_unbound",
        ),
        pytest.param(
            None,
            changed_file(
                "conditions.json",
                editing("units", "properties", "shear_rate", "properties", "plus_minus", to=None),
            ),
            id="a_plus_minus_unit_unbound",
        ),
    ],
)
def test_the_binding_check_can_fail(change: Callable[[Definitions], None] | None, files: Files) -> None:
    definitions = copy.deepcopy(DEFINITIONS)
    if change is not None:
        change(definitions)
    with pytest.raises(AssertionError):
        check_bindings(definitions, files)


def test_a_field_the_text_adds_is_taken_by_the_writer_as_it_stands(tmp_path: Path) -> None:
    """The writer schema holds no list of field names, forms or units: a row added to a copy of the text,
    generated into the vocabulary, is a field the unchanged writer takes, and the vocabulary in this tree,
    where the row is absent, refuses."""
    specification = tmp_path / "specification"
    shutil.copytree(SPECIFICATION, specification)
    path = specification / "record_format.md"
    row = "| `bulk.density` | `kg/m3` | constant, table, interval | `temperature`, `density_kind` | none |"
    text = path.read_text(encoding="utf-8")
    assert row in text
    path.write_text(text.replace(row, row + "\n| `bulk.porosity` | `1` | constant | none | none |"), "utf-8")
    generated = json.loads(gen_vocabulary.generate(specification)["fields.json"])
    porosity = edited(CONSTANT, (("unit",), "1"))
    body: JsonValue = {"sections": {"bulk": {"fields": {"porosity": porosity}}}}
    registry = REGISTRY.with_resource(str(generated["$id"]), DRAFT202012.create_resource(generated))
    checker = Draft202012Validator(
        {"$ref": urljoin(BASE, "record.writer.json#/$defs/material_body")}, registry=registry
    )

    def with_the_row(value: JsonValue) -> list[str]:
        # types-jsonschema types its second overload's instance as unknown.
        return [error.message for error in checker.iter_errors(value)]  # pyright: ignore[reportUnknownMemberType]

    assert with_the_row(body) == []
    assert validator("record.writer.json#/$defs/material_body")(body) != []
    assert with_the_row(edited(body, (("sections", "bulk", "fields", "porosity", "unit"), "kg/m3"))) != []

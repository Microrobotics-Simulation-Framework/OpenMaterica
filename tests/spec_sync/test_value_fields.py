# SPDX-License-Identifier: Apache-2.0
"""The value-field part of the writer schema against the specification: the member tables of a value field,
the provenance object, the statistics block, the conditions and the specimen facts; the members that may hold
a status object, with their tokens (`provenance.md` section 1 item 5); the specification's examples of these
shapes; and the members a read does not check, marked `x-materica-write-only` (`read_side_contract.md` section
3, step 8).

Structure is edited in the writer schema and checked here against the text, so that the specification keeps
its prose (CONTRIBUTING, "Changing the schema"). Each check takes the schema's definitions and the documents
it reads, so that its controls can give it a changed copy of either.
"""

import copy
import json
import re
from collections.abc import Callable, Iterator

import pytest

from materica.core.jsonio import JsonValue
from scripts.gen_vocabulary import SPECIFICATION, between, cell_of, codes, only_code, prose, table
from tests.spec_sync.schemas import SCHEMA, validator

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


def check_conditions_table(definitions: Definitions, read: Documents) -> None:
    text = read("provenance.md")
    kinds = {"numeric": "numeric_condition", "token": "token_condition"}
    assert {
        name: alternatives(condition) for name, condition in members(definitions, "conditions").items()
    } == {
        only_code(row["Name"]): [kinds[row["Shape"]], "status_object"]
        for row in table(text, "### 6.1 Conditions of schema 0.1.0")
    }
    based = set(members(definitions, "based"))
    assert based <= set(codes(between(prose(text), "each shape except a status object carries", ".")))
    numeric, _, token = between(prose(text), "1. A numeric condition holds ", "[RC-047]").partition(
        "a token condition holds "
    )
    added = codes(between(numeric, "MAY add ", " (items"))
    assert set(members(definitions, "numeric_condition")) == sketched(numeric) | set(added) | based
    assert set(members(definitions, "token_condition")) == sketched(token) | based
    entry = between(prose(text), "6. `plus_minus` records ", "`stated_as` is ")
    assert (
        set(members(definitions, "plus_minus_entry"))
        == sketched(entry)
        == required(definitions, "plus_minus_entry")
    )


def sketched(text: str) -> set[str]:
    """The member names of the shapes sketched in the code spans of `text`: `{"value", "unit"}`."""
    return {
        name
        for shape in re.findall(r"`(\{[^`]*\})`", text)
        for name in re.findall(r'(?:\{|, )"([a-z_]+)"', shape)
    }


def check_specimen_table(definitions: Definitions, read: Documents) -> None:
    rows = table(read("provenance.md"), "### 6.2 Specimen facts of schema 0.1.0")
    facts = members(definitions, "specimen")
    assert [only_code(row["Name"]) for row in rows] == list(facts)
    for row in rows:
        name = only_code(row["Name"])
        fact, status = alternatives(facts[name])
        assert status == "status_object", name
        assert set(members(definitions, fact)) == sketched(row["JSON shape"]) | set(
            members(definitions, "based")
        )


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
        {("unit", None): ANY, ("seconds", None): ANY},
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


def check_write_only(definitions: Definitions, read: Documents) -> None:
    for name, quote in [*UNCHECKED.values(), ("read_side_contract.md", STEP_8)]:
        assert quote in prose(read(name)), quote
    assert write_only(definitions) == set(UNCHECKED)
    for form, name in forms(definitions).items():
        own = {(name, member) for member in ("form", form_member(form), "conditions", "statistics")}
        assert not write_only(definitions) & (own | CHECKED), form


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
            check_specimen_table,
            changed_document(
                "provenance.md", '`{"text": <text>, "basis"}` |', '`{"text": <text>, "note", "basis"}` |'
            ),
            None,
            id="fact_member_added",
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

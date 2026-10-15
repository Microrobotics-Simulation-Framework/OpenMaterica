# SPDX-License-Identifier: Apache-2.0
"""Generate `src/materica/schema/0.1/vocabulary/*.json` from the tables and token lists of the specification.

    python scripts/gen_vocabulary.py            # write the files
    python scripts/gen_vocabulary.py --check    # fail if a file differs from what the specification gives

Tokens live in the specification and structure in the writer schemas (CONTRIBUTING, "Changing the schema"), so
each file holds tokens and none of the prose around them: a rule written in prose (when a field's label
applies) is code with its own cases. Most tokens sit in tables; the rest sit in lists in a table cell or a
sentence (`a`, `b` or `c`), each found after a quoted piece of text that must occur exactly once, up to the
quoted text that ends it. A cell or a list not of the form expected stops the script, and so does a name
listed twice in one table; every list of tokens is read in full or not at all: the specification is the
source, and a change to it must change a file or fail here, never drop a token. A parenthetical in a list is
prose and is read as none of its tokens; in a table cell of tokens, a code span inside one stops the script.
"""

import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
SPECIFICATION = REPOSITORY / "docs" / "specification"
VOCABULARY = REPOSITORY / "src" / "materica" / "schema" / "0.1" / "vocabulary"
# Where the files are published: each file's `$id` is this and its name (`tests/spec_sync/test_schemas.py`).
VOCABULARY_ID = "https://w3id.org/materica/schema/0.1/vocabulary/"

Row = dict[str, str]
Vocabulary = dict[str, object]
# A document of the specification by its file name, as text.
Documents = Callable[[str], str]

_CODE = re.compile(r"`([^`]+)`")
_TOKEN = re.compile(r"[a-z0-9_]+")
_CODE_LIST = re.compile(r"`[a-z0-9_]+`(?:, `[a-z0-9_]+`)*")
# Tokens joined as prose joins them: `a`, `b` or `c`; `a`, `b`, and `c`; `a`, or `b`.
_PROSE_LIST = re.compile(r"`[a-z0-9_]+`(?:(?:,| or|, or| and|, and) `[a-z0-9_]+`)*")
# A specimen fact's `token` member, as the JSON shape writes it: `"token": "a" | "b"`, up to the next member.
_TOKEN_MEMBER = re.compile(r'"token": ("[a-z0-9_]+"(?: \| "[a-z0-9_]+")*)(?=, |\})')
_SYMBOLS = re.compile(r"`[A-Z][a-z]?`(?: `[A-Z][a-z]?`)*")
# A family identifier (`record_format.md` section 7 item 3), the form a label takes.
_LABEL = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)+\.v[1-9][0-9]*")
# A field's Label cell: the label's code span, then ` on ` and the prose saying where it applies.
_LABEL_CELL = re.compile(r"`([^`]+)` on ([^`]*(?:`[^`]*`[^`]*)*)")
# A numeric condition's cell: its unit's code span alone, or followed by a parenthetical or `: ` and prose.
_UNIT_CELL = re.compile(r"`([^`]+)`(?: \([^`()]*\)|: [^`]*)?")
# The procedures section 4's `Step` column names for a code no step of the read gives (its paragraph above).
PROCEDURES = ("scene", "USD read", "engine adapter", "build", "family evaluation", "mixing")
# The steps of `read_side_contract.md` section 3.
STEPS = range(14)


class TableError(ValueError):
    """A table, one of its cells, or a list of tokens, not of the form this script reads."""


def table(document: str, heading: str) -> list[Row]:
    """The first table below the line `heading`, a row per dict keyed by the column headers."""
    lines = document.splitlines()
    if heading not in lines:
        raise TableError(f"no heading {heading!r}")
    rows: list[list[str]] = []
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith("|"):
            rows.append(cells(line))
        elif rows or line.startswith("#"):
            break
    if len(rows) < 3:
        raise TableError(f"no table with rows below {heading!r}")
    header, _, *body = rows
    if any(len(row) != len(header) for row in body):
        raise TableError(f"a row below {heading!r} has another number of cells than its header")
    return [dict(zip(header, row, strict=True)) for row in body]


def cells(line: str) -> list[str]:
    """A table row's cells, with a pipe escaped inside one (`\\|`) unescaped."""
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def codes(cell: str) -> list[str]:
    return _CODE.findall(cell)


def only_code(cell: str) -> str:
    if not re.fullmatch(r"`[^`]+`", cell):
        raise TableError(f"expected one code span, got {cell!r}")
    return cell[1:-1]


def code_list(text: str, cell: str) -> list[str]:
    """The tokens of `text`, which must be code spans and nothing else: `a`, `b`."""
    if not _CODE_LIST.fullmatch(text):
        raise TableError(f"expected a list of code spans in {cell!r}")
    return codes(text)


def outside_parentheses(cell: str) -> str:
    """`cell` without its parentheticals, each of which must hold no code span: a token there would be
    dropped."""
    if any("`" in aside for aside in re.findall(r"\([^)]*\)", cell)):
        raise TableError(f"a code span inside a parenthetical in {cell!r}")
    return re.sub(r"\s*\([^)]*\)", "", cell)


def without_asides(text: str) -> str:
    """`text` without its parentheticals, nested ones included, and its case tags (`[PR-333]`). A
    parenthetical is prose: a code span inside one is no token of the list around it."""
    text = re.sub(r"\s*\[(?:[A-Z]{2}-\d{3}|not yet covered)\]", "", text)
    while True:
        shorter = re.sub(r"\s*\([^()]*\)", "", text)
        if shorter == text:
            return text
        text = shorter


def prose(document: str) -> str:
    """`document` with each run of whitespace one space, so that a sentence reads the same however wrapped."""
    return re.sub(r"\s+", " ", document)


def once(text: str, piece: str) -> int:
    """Where `piece` starts in `text`, which must hold it exactly once."""
    if text.count(piece) != 1:
        raise TableError(f"expected {piece!r} exactly once, found it {text.count(piece)} times")
    return text.index(piece)


def between(text: str, after: str | None, before: str | None) -> str:
    """The text between `after`, which must occur once, and the first `before` that follows it; from the
    start, or to the end, where either is None."""
    start = 0 if after is None else once(text, after) + len(after)
    end = len(text) if before is None else text.find(before, start)
    if end < 0:
        raise TableError(f"no {before!r} after {after!r}")
    return text[start:end]


def listed(text: str, after: str | None, before: str | None) -> list[str]:
    """The tokens of the list between `after` and `before` in `text` (`between`): code spans joined by
    commas, `or` and `and`, each perhaps followed by a parenthetical or a case tag, and nothing else."""
    found = without_asides(between(text, after, before)).strip()
    if not _PROSE_LIST.fullmatch(found):
        raise TableError(f"expected a list of tokens after {after!r}, got {found!r}")
    return codes(found)


def cell_of(rows: list[Row], member: str, column: str = "Contents") -> str:
    """The cell in `column` of the row whose first cell is the code span `member`."""
    found = [row[column] for row in rows if next(iter(row.values())) == f"`{member}`"]
    if len(found) != 1:
        raise TableError(f"expected one row for `{member}`, found {len(found)}")
    return found[0]


def enumeration(found: list[str]) -> dict[str, object]:
    if len(set(found)) != len(found):
        raise TableError(f"a token is listed twice in {found!r}")
    return {"enum": found}


def names(rows: list[Row], column: str) -> list[str]:
    """The code span of each row's `column`, a name each row gives once: a second row would replace the
    first's."""
    found = [only_code(row[column]) for row in rows]
    if repeated := sorted({name for name in found if found.count(name) > 1}):
        raise TableError(f"a name listed twice in the table: {repeated}")
    return found


def reasons(rows: list[Row]) -> Vocabulary:
    statuses: dict[str, object] = {}
    for code, row in zip(names(rows, "Code"), rows, strict=True):
        if row["Status"] not in ("met", "not_met", "unknown"):
            raise TableError(f"not a read status: {row['Status']!r}")
        statuses[code] = {"status": row["Status"], **given_by(row["Step"])}
    return {"$defs": {"reason_code": {"enum": list(statuses)}}, "reasons": statuses}


def given_by(cell: str) -> dict[str, object]:
    """The steps of section 3 that give a code, or the procedures that give one no step gives."""
    named = cell.split(", ")
    if all(re.fullmatch(r"0|[1-9][0-9]*", step) and int(step) in STEPS for step in named):
        return {"steps": [int(step) for step in named]}
    if all(procedure in PROCEDURES for procedure in named):
        return {"procedures": named}
    raise TableError(f"expected steps of section 3, or procedures, in {cell!r}")


def fields(rows: list[Row]) -> Vocabulary:
    entries: dict[str, object] = {}
    labels: list[str] = []
    for name, row in zip(names(rows, "Section.field"), rows, strict=True):
        unit = only_code(row["Unit"])
        forms, bases = field_forms(row["Forms"])
        entry: dict[str, object] = {
            "unit": json.loads(unit) if unit.startswith("{") else unit,
            "forms": forms,
            "requires": [] if row["Requires"] == "none" else code_list(row["Requires"], row["Requires"]),
        }
        if bases:
            entry["bases"] = bases
        if row["Label"] != "none":
            label = field_label(row["Label"])
            entry["label"] = label
            labels += [] if label in labels else [label]
        entries[name] = entry
    return {"$defs": {"label": {"enum": labels}}, "fields": entries}


def field_label(cell: str) -> str:
    """The label a Label cell names: one code span, a family identifier, then ` on ` and prose saying where it
    applies, which is code (`record_format.md` section 4.1, "Labels") and names no second label."""
    found = _LABEL_CELL.fullmatch(cell)
    if found is None or not _LABEL.fullmatch(found[1]):
        raise TableError(f"expected a label's code span, then ' on ' and where it applies, in {cell!r}")
    if any(_LABEL.fullmatch(code) for code in codes(found[2])):
        raise TableError(f"a second label in {cell!r}")
    return found[1]


def field_forms(cell: str) -> tuple[list[str], dict[str, list[str]]]:
    """A field's forms, and for a form the row restricts, the bases it allows: `composition (basis `a`)`. A
    reference to the section that defines a form (`evidence (section 4.3)`) is prose."""
    forms: list[str] = []
    bases: dict[str, list[str]] = {}
    for item in re.split(r", (?![^()]*\))", re.sub(r" \(section [0-9.]+\)", "", cell)):
        form = re.fullmatch(r"([a-z0-9_]+)(?: \(basis (`[a-z0-9_]+`(?:, `[a-z0-9_]+`)*)\))?", item)
        if form is None:
            raise TableError(f"expected forms, each perhaps with its bases, in {cell!r}")
        forms.append(form[1])
        if form[2] is not None:
            bases[form[1]] = codes(form[2])
    return forms, bases


def conditions(rows: list[Row]) -> Vocabulary:
    entries: dict[str, dict[str, object]] = {}
    token_conditions: dict[str, list[str]] = {}
    for name, row in zip(names(rows, "Name"), rows, strict=True):
        cell = row["Unit or tokens"]
        if row["Shape"] == "numeric":
            unit = _UNIT_CELL.fullmatch(cell)
            if unit is None:
                raise TableError(
                    f"expected a unit's code span, then nothing, an aside or ': ' and prose: {cell!r}"
                )
            entries[name] = {"shape": "numeric", "unit": unit[1]}
        elif row["Shape"] == "token":
            token_conditions[name] = code_list(outside_parentheses(cell), cell)
            entries[name] = {"shape": "token", "tokens": token_conditions[name]}
        else:
            raise TableError(f"not a condition's shape: {row['Shape']!r}")
    for row in rows:
        entries[only_code(row["Name"])]["required_with"] = required_with(
            row["Required with"], token_conditions
        )
    return {"conditions": entries}


def required_with(cell: str, token_conditions: dict[str, list[str]]) -> dict[str, list[str]]:
    """The conditions and tokens with which a condition is required (`provenance.md` section 6.1 item 9):
    a dash (U+2014), or `other`: `a`, `b`, each `other` a token condition of the table and each token one of
    its own."""
    if cell == "\u2014":
        return {}
    found: dict[str, list[str]] = {}
    for part in cell.split("; "):
        named = re.fullmatch(r"`([a-z0-9_]+)`: (.+)", part)
        if named is None:
            raise TableError(f"expected `condition`: `token`, ... in {cell!r}")
        listed_tokens = code_list(named[2], cell)
        if not set(listed_tokens) <= set(token_conditions.get(named[1], [])):
            raise TableError(f"not a token condition of the table and its tokens: {part!r}")
        found[named[1]] = listed_tokens
    return found


def specimen_facts(rows: list[Row]) -> Vocabulary:
    """Each fact's tokens, those its `token` member takes; its members are structure, the writer schema's."""
    entries: dict[str, object] = {}
    definitions: dict[str, object] = {}
    for name, row in zip(names(rows, "Name"), rows, strict=True):
        shape = row["JSON shape"]
        found: list[str] = []
        for named in re.finditer(r'"token"', shape):
            member = _TOKEN_MEMBER.match(shape, named.start())
            if member is None:
                raise TableError(f'expected "token": "a" | "b" in {shape!r}')
            found += re.findall(r'"([a-z0-9_]+)"', member[1])
        entries[name] = {"tokens": found}
        if found:
            definitions[f"{name}_token"] = enumeration(found)
    return {"$defs": definitions, "facts": entries}


def acceptance_kinds(rows: list[Row]) -> Vocabulary:
    return {"kinds": names(rows, "`acceptance`")}


def forms(read: Documents) -> Vocabulary:
    """`record_format.md` sections 5 and 6: the form tokens, an interval's and a composition's tokens, and the
    components, `element:<symbol>` for each symbol of the element table."""
    document = read("record_format.md")
    text = prose(document)
    members = table(document, "## 5. Value fields")
    interval = between(text, "**Interval.**", "**Composition.**")
    composition = between(text, "**Composition.**", "**Model parameter set.**")
    once(composition, "`component` is `element:<symbol>`")
    heading = re.search(r"^The element symbols are IUPAC's (\d+) .*:$", document, re.M)
    if heading is None:
        raise TableError("no line introducing the element table")
    symbols: list[str] = []
    for period in table(document, heading[0]):
        if not _SYMBOLS.fullmatch(period["Symbols"]):
            raise TableError(f"expected element symbols in {period['Symbols']!r}")
        symbols += codes(period["Symbols"])
    if len(symbols) != int(heading[1]):
        raise TableError(f"the element table holds {len(symbols)} symbols, not the {heading[1]} it states")
    return {
        "$defs": {
            "form": enumeration(listed(cell_of(members, "form"), "one of ", None)),
            "interval_basis": enumeration(listed(interval, "2. `basis` is ", ".")),
            "composition_basis": enumeration(listed(composition, "1. `basis` is ", ". `component`")),
            "sum_rule": enumeration(listed(composition, "2. `sum_rule` is ", ". Where")),
            "component": enumeration([f"element:{symbol}" for symbol in symbols]),
        }
    }


def statistics(read: Documents) -> Vocabulary:
    """`uncertainty.md` sections 1 and 4: the statistics block's tokens, an uncertainty's, and the
    distribution tokens a record or a declaration may name."""
    document = read("uncertainty.md")
    members = table(document, "## 1. The statistics block")
    uncertainty = between(prose(document), "In a relative or expanded uncertainty:", "Every uncertainty")
    return {
        "$defs": {
            "central": enumeration(listed(cell_of(members, "central"), "a constant's `value` is: ", ";")),
            "statistics_distribution": enumeration(
                listed(cell_of(members, "distribution"), "the block gives: ", " where the source states one")
            ),
            "statistics_basis": enumeration(listed(cell_of(members, "basis"), "spread comes from: ", ";")),
            "represents": enumeration(listed(cell_of(members, "represents"), "spread describes: ", ";")),
            "level": enumeration(
                listed(cell_of(members, "population_level"), "the levels are ", " (rule 10)")
            ),
            "precision_conditions": enumeration(
                listed(cell_of(members, "precision_conditions"), "is `measurement`: ", ", or `{")
            ),
            "dispersion": enumeration(
                listed(cell_of(members, "dispersion"), None, " where the source gives")
            ),
            "uncertainty_distribution": enumeration(listed(uncertainty, "- `distribution` is ", " or `{")),
            "uncertainty_basis": enumeration(listed(uncertainty, "- `basis` is ", ";")),
            "uncertainty_represents": enumeration(listed(uncertainty, "- `represents` is ", " or `{")),
            "distribution": enumeration(
                [only_code(token["Token"]) for token in table(document, "## 4. Distribution tokens")]
            ),
        }
    }


def provenance(read: Documents) -> Vocabulary:
    """`provenance.md`: the origins, a review's result, the extraction methods, the locator types, a search's
    inputs, a condition's or fact's basis, and a condition's `plus_minus` and `set_or_measured` tokens."""
    document = read("provenance.md")
    text = prose(document)
    members = table(document, "## 2. The provenance object")
    methods = table(document, "## 3. Extraction")
    return {
        "$defs": {
            "origin": enumeration(listed(cell_of(members, "origin"), None, None)),
            "review_result": enumeration(listed(text, "whose `result` is a token the reader knows (", ")")),
            "extraction_method": enumeration(
                [method for row in methods for method in code_list(row["Method"], row["Method"])]
            ),
            "locator_type": enumeration(listed(text, "A `locator` names its `type` (", ")")),
            "search_inputs": enumeration(listed(cell_of(members, "search"), "and `inputs`: ", None)),
            "basis": enumeration(listed(text, "a status object carries a `basis`: ", " with an")),
            "stated_as": enumeration(listed(text, "`stated_as` is ", " or `{")),
            "set_or_measured": enumeration(listed(text, "`set_or_measured` is ", ";")),
        }
    }


def labels(read: Documents) -> Vocabulary:
    """`read_side_contract.md` section 2: the labels a result may hold beside the field's own."""
    members = table(read("read_side_contract.md"), "## 2. The read result")
    found = listed(cell_of(members, "labels"), "from this list only: ", ", and the field's `label`")
    return {"$defs": {"result_label": enumeration(found)}}


def from_table(
    document: str, heading: str, read_rows: Callable[[list[Row]], Vocabulary]
) -> Callable[[Documents], Vocabulary]:
    return lambda read: read_rows(table(read(document), heading))


# Each file, where in the specification its tokens are, and how they are read.
SOURCES: dict[str, tuple[str, Callable[[Documents], Vocabulary]]] = {
    "reasons.json": (
        "read_side_contract.md, 4. Reason codes",
        from_table("read_side_contract.md", "## 4. Reason codes", reasons),
    ),
    "fields.json": (
        "record_format.md, 4.1 Sections and fields of schema 0.1.0",
        from_table("record_format.md", "### 4.1 Sections and fields of schema 0.1.0", fields),
    ),
    "conditions.json": (
        "provenance.md, 6.1 Conditions of schema 0.1.0",
        from_table("provenance.md", "### 6.1 Conditions of schema 0.1.0", conditions),
    ),
    "specimen_facts.json": (
        "provenance.md, 6.2 Specimen facts of schema 0.1.0",
        from_table("provenance.md", "### 6.2 Specimen facts of schema 0.1.0", specimen_facts),
    ),
    "acceptances.json": (
        "declarations.md, 4.1 The list",
        from_table("declarations.md", "### 4.1 The list", acceptance_kinds),
    ),
    "forms.json": ("record_format.md, 5. Value fields and 6. The value forms", forms),
    "statistics.json": ("uncertainty.md, 1. The statistics block and 4. Distribution tokens", statistics),
    "provenance.json": (
        "provenance.md, 2. The provenance object, 3. Extraction and 6. Conditions",
        provenance,
    ),
    "labels.json": ("read_side_contract.md, 2. The read result", labels),
}


def generate(specification: Path = SPECIFICATION) -> dict[str, str]:
    """Each vocabulary file's name and text."""

    def read(document: str) -> str:
        return (specification / document).read_text(encoding="utf-8")

    files: dict[str, str] = {}
    for name, (source, tokens_of) in SOURCES.items():
        contents = {
            "$id": VOCABULARY_ID + name,
            "$comment": f"Generated by scripts/gen_vocabulary.py from docs/specification/{source}. "
            "Edit the specification.",
            **tokens_of(read),
        }
        files[name] = json.dumps(contents, indent=2, ensure_ascii=False) + "\n"
    return files


def main(arguments: Sequence[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if list(arguments) not in ([], ["--check"]):
        print("usage: python scripts/gen_vocabulary.py [--check]", file=sys.stderr)
        return 2
    files = generate(SPECIFICATION)
    if arguments:
        differing = sorted(
            name
            for name, text in files.items()
            if not (VOCABULARY / name).is_file() or (VOCABULARY / name).read_text(encoding="utf-8") != text
        )
        stray = sorted({path.name for path in VOCABULARY.glob("*.json")} - files.keys())
        for name in differing:
            print(
                f"{name} differs from the specification: run scripts/gen_vocabulary.py",
                file=sys.stderr,
            )
        for name in stray:
            print(f"{name} comes from no table", file=sys.stderr)
        return 1 if differing or stray else 0
    VOCABULARY.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (VOCABULARY / name).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

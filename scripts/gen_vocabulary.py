# SPDX-License-Identifier: Apache-2.0
"""Generate `src/materica/schema/0.1/vocabulary/*.json` from the tables of the specification.

    python scripts/gen_vocabulary.py            # write the files
    python scripts/gen_vocabulary.py --check    # fail if a file differs from what the tables give

Tokens live in the specification's tables and structure in the writer schemas (CONTRIBUTING, "Changing the
schema"), so each file holds the tokens of one table and none of its prose: a rule written in prose (a field's
label rule, a form's basis) is code with its own cases. A cell not of the form expected stops the script, and
every list of tokens is read in full or not at all: the tables are the source, and a change to one must change
a file or fail here, never drop a token.
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

_CODE = re.compile(r"`([^`]+)`")
_TOKEN = re.compile(r"[a-z0-9_]+")
_CODE_LIST = re.compile(r"`[a-z0-9_]+`(?:, `[a-z0-9_]+`)*")
# A specimen fact's `token` member, as the JSON shape writes it: `"token": "a" | "b"`, up to the next member.
_TOKEN_MEMBER = re.compile(r'"token": ("[a-z0-9_]+"(?: \| "[a-z0-9_]+")*)(?=, |\})')


class TableError(ValueError):
    """A table, or one of its cells, not of the form this script reads."""


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


def tokens(found: list[str], cell: str) -> list[str]:
    if not found or not all(_TOKEN.fullmatch(token) for token in found):
        raise TableError(f"expected tokens in {cell!r}")
    return found


def code_list(text: str, cell: str) -> list[str]:
    """The tokens of `text`, which must be code spans and nothing else: `a`, `b`."""
    if not _CODE_LIST.fullmatch(text):
        raise TableError(f"expected a list of code spans in {cell!r}")
    return codes(text)


def outside_parentheses(cell: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", cell)


def reasons(rows: list[Row]) -> Vocabulary:
    statuses: dict[str, object] = {}
    for row in rows:
        if row["Status"] not in ("met", "not_met", "unknown"):
            raise TableError(f"not a read status: {row['Status']!r}")
        statuses[only_code(row["Code"])] = {"status": row["Status"]}
    return {"$defs": {"reason_code": {"enum": list(statuses)}}, "reasons": statuses}


def fields(rows: list[Row]) -> Vocabulary:
    entries: dict[str, object] = {}
    for row in rows:
        unit = only_code(row["Unit"])
        forms = outside_parentheses(row["Forms"]).split(", ")
        entry: dict[str, object] = {
            "unit": json.loads(unit) if unit.startswith("{") else unit,
            "forms": tokens(forms, row["Forms"]),
            "requires": [] if row["Requires"] == "none" else code_list(row["Requires"], row["Requires"]),
        }
        if row["Label"] != "none":
            # The token only: when the label applies is prose (`record_format.md` section 4.1, "Labels").
            label = re.match(r"`([^`]+)`(?= |$)", row["Label"])
            if label is None:
                raise TableError(f"expected a label's code span first in {row['Label']!r}")
            entry["label"] = label[1]
        entries[only_code(row["Section.field"])] = entry
    return {"fields": entries}


def conditions(rows: list[Row]) -> Vocabulary:
    entries: dict[str, object] = {}
    for row in rows:
        cell = row["Unit or tokens"]
        if row["Shape"] == "numeric":
            unit = codes(cell)[0] if codes(cell) else ""
            if not cell.startswith(f"`{unit}`"):
                raise TableError(f"a numeric condition's cell starts with its unit: {cell!r}")
            entries[only_code(row["Name"])] = {"shape": "numeric", "unit": unit}
        elif row["Shape"] == "token":
            entries[only_code(row["Name"])] = {
                "shape": "token",
                "tokens": code_list(outside_parentheses(cell), cell),
            }
        else:
            raise TableError(f"not a condition's shape: {row['Shape']!r}")
    return {"conditions": entries}


def specimen_facts(rows: list[Row]) -> Vocabulary:
    """Each fact's tokens, those its `token` member takes; its members are structure, the writer schema's."""
    entries: dict[str, object] = {}
    for row in rows:
        shape = row["JSON shape"]
        found: list[str] = []
        for named in re.finditer(r'"token"', shape):
            member = _TOKEN_MEMBER.match(shape, named.start())
            if member is None:
                raise TableError(f'expected "token": "a" | "b" in {shape!r}')
            found += re.findall(r'"([a-z0-9_]+)"', member[1])
        entries[only_code(row["Name"])] = {"tokens": found}
    return {"facts": entries}


def acceptance_kinds(rows: list[Row]) -> Vocabulary:
    return {"kinds": [only_code(row["`acceptance`"]) for row in rows]}


# Each file, the table it comes from, and how its rows become the file's members.
SOURCES: dict[str, tuple[str, str, Callable[[list[Row]], Vocabulary]]] = {
    "reasons.json": ("read_side_contract.md", "## 4. Reason codes", reasons),
    "fields.json": ("record_format.md", "### 4.1 Sections and fields of schema 0.1.0", fields),
    "conditions.json": ("provenance.md", "### 6.1 Conditions of schema 0.1.0", conditions),
    "specimen_facts.json": ("provenance.md", "### 6.2 Specimen facts of schema 0.1.0", specimen_facts),
    "acceptances.json": ("declarations.md", "### 4.1 The list", acceptance_kinds),
}


def generate(specification: Path = SPECIFICATION) -> dict[str, str]:
    """Each vocabulary file's name and text."""
    files: dict[str, str] = {}
    for name, (document, heading, read) in SOURCES.items():
        rows = table((specification / document).read_text(encoding="utf-8"), heading)
        source = f"docs/specification/{document}, {heading.lstrip('# ')}"
        contents = {
            "$id": VOCABULARY_ID + name,
            "$comment": f"Generated by scripts/gen_vocabulary.py from {source}. Edit the table.",
            **read(rows),
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
                f"{name} differs from the specification's table: run scripts/gen_vocabulary.py",
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

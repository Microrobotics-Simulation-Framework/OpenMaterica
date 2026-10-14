# SPDX-License-Identifier: Apache-2.0
"""The specification's references to itself resolve, its case tags and its Cases rows agree, and no list in it
numbers two items alike.

The documents are `docs/specification/*.md`, the architecture draft (AD) and the documentation plan, each
read outside its fenced code blocks. A reference is checked only in a form that names its target without the
sentence around it:

- `section N`, `sections N and M`, `section N item M`, `section N, steps M to K`, and the section sign
  (U+00A7) before N: in the document named in code just before (`` `record_format.md` section 1 item 6 ``),
  in the AD after `AD` or "architecture draft", and otherwise in the citing document itself;
- `AD N` and `DA N` (the documentation plan, as AD section 12 abbreviates it), in lists and ranges
  (`AD 4.1 to 4.4, 5.2`), with the section's title where one follows in italics;
- `` `file.md` N `` and `this document N`, as the reason codes' "Defined in" column writes them.

A range is checked at its ends, and an item in its section's own text, above any subsection. Not checked: a
section after a name in capitals (`MADDENING section 9.7`, `UCUM 2.2, sections 22 and 46`), whose document is
not here; `item N` or `step N` alone, whose list is the one around it; `SD` and `RS`, drafts outside this
repository; and principles, rules and constraints, which are not numbered items.
"""

import re
from pathlib import Path
from typing import NamedTuple

import pytest

from scripts.gen_vocabulary import table

REPOSITORY = Path(__file__).resolve().parents[2]
ARCHITECTURE_DRAFT = "ARCHITECTURE_DRAFT.md"
DOCUMENTATION_PLAN = "DOCUMENTATION_ARCHITECTURE.md"


def read_documents(root: Path) -> dict[str, str]:
    """Each document's text, by its file name, which is how a reference names it."""
    paths = [
        *sorted((root / "docs" / "specification").glob("*.md")),
        root / "design" / ARCHITECTURE_DRAFT,
        root / DOCUMENTATION_PLAN,
    ]
    return {path.name: path.read_text(encoding="utf-8") for path in paths}


DOCUMENTS = read_documents(REPOSITORY)

_FENCE = re.compile(r" *(?:```|~~~)")


def outside_code(text: str) -> list[str]:
    """The lines of `text`, those inside fenced code blocks emptied so that line numbers stay."""
    lines: list[str] = []
    fenced = False
    for line in text.split("\n"):
        if _FENCE.match(line):
            fenced = not fenced
            lines.append("")
        else:
            lines.append("" if fenced else line)
    return lines


# `## 4. Title`, `### 4.1 Title`, `## Appendix A. Title` and `### A.1 Title`.
_HEADING = re.compile(
    r"#+ (?:Appendix )?(?P<number>[0-9]+(?:\.[0-9]+)*|[A-Z](?:\.[0-9]+)*)[.:]? (?P<title>.+)"
)
_ITEM = re.compile(r"(?P<indent> *)(?P<number>[0-9]+)\. ")


class Section(NamedTuple):
    title: str
    items: frozenset[int]


def sections(text: str) -> dict[str, Section]:
    """Each numbered section by its number, with the numbers of the items in its own text."""
    titles: dict[str, str] = {}
    items: dict[str, set[int]] = {}
    current: set[int] | None = None
    for line in outside_code(text):
        if line.startswith("#"):
            heading = _HEADING.fullmatch(line)
            current = None
            if heading:
                titles[heading["number"]] = heading["title"]
                current = items[heading["number"]] = set()
        elif current is not None and (item := _ITEM.match(line)):
            current.add(int(item["number"]))
    return {number: Section(title, frozenset(items[number])) for number, title in titles.items()}


_NUMBER = r"(?:[0-9]+(?:\.[0-9]+)*|[A-Z]\.[0-9]+)"
_JOINED = r"(?:,\s*|\s+and\s+|\s+or\s+|\s+to\s+)"
# Each number may carry a parenthesis, as in `AD 3.5 (rule 3) and 4.12`.
_NUMBERS = rf"{_NUMBER}(?:\s+\([^()]*\))?(?:{_JOINED}{_NUMBER}(?:\s+\([^()]*\))?)*"
_ITEMS = rf"(?:,?\s+(?:items?|steps?)\s+(?P<items>[0-9]+(?:{_JOINED}[0-9]+)*))?"
_FILE = r"`(?:[\w./-]*/)?(?P<file>[\w.-]+\.md)`"
# What may stand just before `section`: a name in capitals, whose document is not checked here (`MADDENING`,
# `UCUM 2.2,`); a file name in code; or the AD.
_FOREIGN = r"(?P<foreign>\b(?!AD\b|DA\b)[A-Z]{2,}(?:\s+[0-9.]+)?,?)"
_QUALIFIER = rf"(?:{_FOREIGN}|{_FILE}|(?P<draft>\barchitecture\s+draft,?|\bAD))\s+"
_REFERENCES = (
    re.compile(rf"(?:{_QUALIFIER})?(?:\b[Ss]ections?\s+|\u00a7\s*)(?P<numbers>{_NUMBERS}){_ITEMS}"),
    re.compile(rf"\b(?P<abbreviation>AD|DA)\s+(?P<numbers>{_NUMBERS})(?:\s+\*(?P<title>[^*]+)\*)?{_ITEMS}"),
    re.compile(rf"(?:{_FILE}|\bthis\s+document)\s+(?P<numbers>{_NUMBERS})"),
)


def target(reference: re.Match[str], citing: str) -> str | None:
    """The document a reference names, or None where it names one not checked here."""
    named = reference.groupdict()
    if named.get("foreign"):
        return None
    if named.get("file"):
        return named["file"]
    if named.get("draft") or named.get("abbreviation") == "AD":
        return ARCHITECTURE_DRAFT
    if named.get("abbreviation") == "DA":
        return DOCUMENTATION_PLAN
    return citing


def missing(reference: re.Match[str], name: str, headings: dict[str, dict[str, Section]]) -> list[str]:
    if name not in headings:
        return [f"no document {name}"]
    numbers = re.findall(_NUMBER, re.sub(r"\s+\([^()]*\)", "", reference["numbers"]))
    absent = [f"no section {number} in {name}" for number in numbers if number not in headings[name]]
    if absent or len(numbers) != 1:
        return absent
    section = headings[name][numbers[0]]
    named = reference.groupdict()
    for item in re.findall(r"[0-9]+", named.get("items") or ""):
        if int(item) not in section.items:
            absent.append(f"no item {item} in section {numbers[0]} of {name}")
    if named.get("title") and named["title"] != section.title:
        absent.append(f"section {numbers[0]} of {name} is titled {section.title!r}")
    return absent


def unresolved_references(documents: dict[str, str]) -> list[str]:
    """Each reference to a document, section, item or title that is not there, as `document:line: the words
    before it and the reference: what is missing`."""
    headings = {name: sections(text) for name, text in documents.items()}
    found: list[str] = []
    for citing, text in documents.items():
        prose = "\n".join(outside_code(text))
        for pattern in _REFERENCES:
            for reference in pattern.finditer(prose):
                name = target(reference, citing)
                if name is None:
                    continue
                line = prose.count("\n", 0, reference.start()) + 1
                excerpt = " ".join(prose[max(0, reference.start() - 30) : reference.end()].split())
                found += [
                    f"{citing}:{line}: {excerpt}: {absent}" for absent in missing(reference, name, headings)
                ]
    return found


# References that are right but that the forms above read wrongly, each by its document and the words that
# find it, with the reason. An entry that finds nothing fails, so that it goes when its text does.
ALLOWED = {
    (DOCUMENTATION_PLAN, "MADDENING's (section 9.7"): "MADDENING's section, named before the parenthesis",
    (DOCUMENTATION_PLAN, "MADDENING's (section 9.8"): "MADDENING's section, named before the parenthesis",
}


def allowed(finding: str, entry: tuple[str, str]) -> bool:
    document, words = entry
    return finding.startswith(f"{document}:") and words in finding


FINDINGS = unresolved_references(DOCUMENTS)


def test_every_reference_resolves() -> None:
    assert [finding for finding in FINDINGS if not any(allowed(finding, entry) for entry in ALLOWED)] == []


def test_every_allowed_reference_is_still_found() -> None:
    assert [entry for entry in ALLOWED if not any(allowed(finding, entry) for finding in FINDINGS)] == []


@pytest.mark.parametrize(
    ("name", "old", "new", "finding"),
    [
        (
            "README.md",
            "`record_format.md` section 7 item 1",
            "`record_format.md` section 7 item 9",
            "no item 9 in section 7 of record_format.md",
        ),
        (
            "README.md",
            "`record_format.md` section 7 item 1",
            "`record_formats.md` section 7 item 1",
            "no document record_formats.md",
        ),
        (
            "model_families.md",
            "(section 9). [RC-076]",
            "(section 19). [RC-076]",
            "no section 19 in model_families.md",
        ),
        (
            "model_families.md",
            "(section 9). [RC-076]",
            "(\u00a719). [RC-076]",
            "no section 19 in model_families.md",
        ),
        (
            "uncertainty.md",
            "AD 4.9, 7.3 and 9.4",
            "AD 4.9, 7.3 and 9.14",
            "no section 9.14 in ARCHITECTURE_DRAFT.md",
        ),
        (
            ARCHITECTURE_DRAFT,
            "DA 6.5 *CI checks*",
            "DA 6.5 *CI jobs*",
            "section 6.5 of DOCUMENTATION_ARCHITECTURE.md is titled 'CI checks'",
        ),
        (
            "read_side_contract.md",
            "| another schema version | `record_format.md` 8 |",
            "| another schema version | `record_format.md` 18 |",
            "no section 18 in record_format.md",
        ),
    ],
    ids=["item", "document", "section", "section_sign", "ad_list", "title", "defined_in"],
)
def test_the_reference_check_can_fail(name: str, old: str, new: str, finding: str) -> None:
    assert DOCUMENTS[name].count(old) == 1
    after = unresolved_references({**DOCUMENTS, name: DOCUMENTS[name].replace(old, new)})
    added = [found for found in after if found not in FINDINGS]
    assert len(added) == 1
    assert added[0].startswith(f"{name}:")
    assert added[0].endswith(f": {finding}")


_CASE_TAG = re.compile(r"\[([A-Z]{2}-[0-9]{3})\]")


def case_rows(documents: dict[str, str]) -> dict[str, str]:
    """Each case in a Cases table, by the document whose table holds it."""
    return {
        row["Case"]: name
        for name, text in documents.items()
        if "## Cases" in text.splitlines()
        for row in table(text, "## Cases")
    }


def case_tags(documents: dict[str, str]) -> dict[str, list[str]]:
    """Each case tag, by where it stands (`document:line`), table rows included."""
    tags: dict[str, list[str]] = {}
    for name, text in documents.items():
        for number, line in enumerate(outside_code(text), 1):
            for case in _CASE_TAG.findall(line):
                tags.setdefault(case, []).append(f"{name}:{number}")
    return tags


def tags_without_a_row(documents: dict[str, str]) -> list[str]:
    rows = case_rows(documents)
    return [
        f"{place}: [{case}]"
        for case, places in case_tags(documents).items()
        if case not in rows
        for place in places
    ]


def uncited_rows(documents: dict[str, str]) -> list[str]:
    tags = case_tags(documents)
    return [f"{name}: {case}" for case, name in case_rows(documents).items() if case not in tags]


def test_every_case_tag_names_a_row() -> None:
    assert case_rows(DOCUMENTS)
    assert tags_without_a_row(DOCUMENTS) == []


def test_every_case_row_is_cited_by_a_tag() -> None:
    assert uncited_rows(DOCUMENTS) == []


def line_of(text: str, words: str) -> int:
    return text[: text.index(words)].count("\n") + 1


def test_the_case_checks_can_fail() -> None:
    declarations = DOCUMENTS["declarations.md"]
    # BC-002's one tag stands in a table row, BC-003's in prose.
    for case in ("BC-002", "BC-003"):
        assert declarations.count(f"[{case}]") == 1
        assert uncited_rows({**DOCUMENTS, "declarations.md": declarations.replace(f"[{case}]", "")}) == [
            f"declarations.md: {case}"
        ]
    assert DOCUMENTS["mixing_rules.md"].count("[MX-012]") == 1
    seeded = {**DOCUMENTS, "mixing_rules.md": DOCUMENTS["mixing_rules.md"].replace("[MX-012]", "[MX-912]")}
    assert tags_without_a_row(seeded) == [
        f"mixing_rules.md:{line_of(seeded['mixing_rules.md'], '[MX-912]')}: [MX-912]"
    ]
    assert uncited_rows(seeded) == ["mixing_rules.md: MX-012"]


def repeated_items(text: str) -> list[str]:
    """Each item numbered as an earlier item of its list, as `line: item N, as at line M`. A list is a run of
    items at one indentation; it ends at an item less indented, and at any other line, a heading included, no
    deeper than its items."""
    found: list[str] = []
    # Each open list, outermost first: its items' indentation, and the line of each number.
    lists: list[tuple[int, dict[int, int]]] = []
    for line_number, line in enumerate(outside_code(text), 1):
        if not line.strip():
            continue
        item = _ITEM.match(line)
        indent = len(item["indent"]) if item else len(line) - len(line.lstrip(" "))
        while lists and (lists[-1][0] > indent or (item is None and lists[-1][0] == indent)):
            lists.pop()
        if item is None:
            continue
        if not lists or lists[-1][0] < indent:
            lists.append((indent, {}))
        number = int(item["number"])
        if number in lists[-1][1]:
            found.append(f"{line_number}: item {number}, as at line {lists[-1][1][number]}")
        lists[-1][1][number] = line_number
    return found


@pytest.mark.parametrize("name", sorted(DOCUMENTS))
def test_no_list_numbers_two_items_alike(name: str) -> None:
    assert repeated_items(DOCUMENTS[name]) == []


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("1. a\n   b\n2. c\n2. d\n", ["4: item 2, as at line 3"]),
        ("1. a\n   1. b\n   1. c\n2. d\n", ["3: item 1, as at line 2"]),
        ("0. a\n\n   b\n\n1. c\n0. d\n", ["6: item 0, as at line 1"]),
        ("1. a\n\nText.\n\n1. b\n", []),
        ("1. a\n   1. b\n2. c\n   1. d\n", []),
        ("## 1. A\n\n1. a\n\n## 2. B\n\n1. b\n", []),
    ],
    ids=["repeated", "nested", "across_paragraphs", "two_lists", "two_nested_lists", "two_sections"],
)
def test_the_item_check_can_fail(text: str, found: list[str]) -> None:
    assert repeated_items(text) == found


def test_the_item_check_finds_the_repeated_item_found_by_hand() -> None:
    families = DOCUMENTS["model_families.md"]
    assert families.count("7. A reference-only parameter set") == 1
    seeded = families.replace("7. A reference-only parameter set", "6. A reference-only parameter set")
    line = line_of(seeded, "6. A reference-only parameter set")
    assert repeated_items(seeded) == [
        f"{line}: item 6, as at line {line_of(seeded, '6. Check points show only')}"
    ]

# SPDX-License-Identifier: Apache-2.0
"""Each rule of the reference model, and of the reference evaluator of tables beside it, cites the
specification as `file:line` and a short quote; each quote is found at its line, so that a citation that
drifts from the text fails, and so does a `file:line` without a quote, which nothing could check. A quote
holds `"` only inside a code span, as the text's JSON stands, so that it ends at the first `"` outside one.
The same holds of every test module that cites the text as `file:line`: the seeded faults of the model hold
their citation in a string (the `rule` of a `Mutant`), the rest in a comment or a docstring, and a module
that cites the text and is not listed here fails the check that lists them.
Each point the text leaves open is listed once in `OPEN_POINTS` and named
where the model applies it, and the two agree."""

import ast
import io
import re
import tokenize
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from tests.reference import read_model

REPOSITORY = Path(__file__).resolve().parents[2]
SPECIFICATION = REPOSITORY / "docs" / "specification"
MODEL_SOURCES = ("read_model.py", "strict_json.py")
EVALUATOR_SOURCE = REPOSITORY / "tests" / "reference" / "table_evaluator.py"
SOURCES = [*(REPOSITORY / "tests" / "reference" / name for name in MODEL_SOURCES), EVALUATOR_SOURCE]
# The test modules that cite the text, in the strings, comments and docstrings they hold it in.
TEST_SOURCES = [
    REPOSITORY / "tests" / path
    for path in (
        "reference/mutants.py",
        "reference/cases.py",
        "property/test_model_mutants.py",
        "property/test_model_properties.py",
    )
]
SEEDED_FAULTS_SOURCE = REPOSITORY / "tests" / "reference" / "mutants.py"
MUTANT_KILLS_SOURCE = REPOSITORY / "tests" / "property" / "test_model_mutants.py"
# A quote's text: characters but `"` and a backtick, and code spans, which may hold `"`.
QUOTED = r'"((?:[^"`]|`[^`]*`)+)"'
REFERENCE = re.compile(r"(?P<file>[A-Za-z_]+\.md):(?P<start>\d+)(?:-(?P<end>\d+))?")
CITATION = re.compile(
    REFERENCE.pattern + r"\s+(?P<quotes>" + QUOTED + r"(?:\s*(?:and|or|,|;|\.\.\.)\s*" + QUOTED + r")*)"
)
QUOTE = re.compile(QUOTED)
OPEN_POINT = re.compile(r"Open point: (?P<name>[a-z0-9_]+)")
OPEN_POINT_NAMED = re.compile(r"OPEN_POINTS: ([a-z0-9_]+)")


def comments(source: str) -> list[str]:
    """The comments of `source`, each run of comment lines joined."""
    texts: list[str] = []
    run: list[str] = []
    last = 0
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        if run and token.start[0] != last + 1:
            texts.append(" ".join(run))
            run = []
        run.append(token.string.lstrip("#").strip())
        last = token.start[0]
    if run:
        texts.append(" ".join(run))
    return [" ".join(text.split()) for text in texts]


def prose(source: str) -> list[str]:
    """The comments of `source`, each run of comment lines joined, and its docstrings."""
    texts = comments(source)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            docstring = ast.get_docstring(node)
            if docstring:
                texts.append(" ".join(docstring.split()))
    return texts


def strings(source: str) -> list[str]:
    """Every string literal of `source`, its adjacent literals joined: a docstring, and the `rule` a `Mutant`
    holds as an argument, which `prose` does not read."""
    return [
        " ".join(node.value.split())
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def held_in(source: str) -> list[str]:
    """What a test module holds citations in: its comments and every string, a `Mutant`'s `rule` too."""
    return [*comments(source), *strings(source)]


def specification_lines(file: str) -> list[str] | None:
    path = SPECIFICATION / file
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else None


def begins_before(quote: str, window: str, limit: int) -> bool:
    """Whether `quote` begins in `window` before `limit`: on a cited line, though it may run on past it."""
    position = window.find(quote)
    while position != -1:
        if position < limit:
            return True
        position = window.find(quote, position + 1)
    return False


def citation_problems(texts: Iterable[str]) -> list[str]:
    """Each citation whose file is not in the specification, or whose quote does not begin at its lines (it
    may run on to the line after the last one cited); and each `file:line` with no quote."""
    problems: list[str] = []
    for text in texts:
        quoted = {citation.start() for citation in CITATION.finditer(text)}
        problems.extend(
            f"{reference[0]}: no quote"
            for reference in REFERENCE.finditer(text)
            if reference.start() not in quoted
        )
        for citation in CITATION.finditer(text):
            file, start = citation["file"], int(citation["start"])
            end = int(citation["end"] or start)
            lines = specification_lines(file)
            if lines is None:
                problems.append(f"{citation[0]}: no file {file} in the specification")
                continue
            cited = " ".join(" ".join(lines[start - 1 : end]).split())
            window = " ".join(" ".join(lines[start - 1 : end + 1]).split())
            problems.extend(
                f"{file}:{start}: {quote!r} is not at lines {start} to {end}"
                for quote in QUOTE.findall(citation["quotes"])
                if not begins_before(quote, window, len(cited))
            )
    return problems


def open_point_problems(texts: Iterable[str], listed: Mapping[str, str]) -> list[str]:
    named = {match["name"] for text in texts for match in OPEN_POINT.finditer(text)}
    return [f"named but not listed: {name}" for name in sorted(named - set(listed))] + [
        f"listed but named nowhere: {name}" for name in sorted(set(listed) - named)
    ]


def model_prose() -> list[str]:
    return [text for path in SOURCES for text in prose(path.read_text(encoding="utf-8"))]


def test_every_quote_is_at_the_lines_it_cites() -> None:
    assert citation_problems(model_prose()) == []


def test_the_test_modules_that_cite_the_text_hold_to_the_same_rules() -> None:
    held = {path: held_in(path.read_text(encoding="utf-8")) for path in TEST_SOURCES}
    assert [problem for texts in held.values() for problem in citation_problems(texts)] == []
    cited = {path.name: sum(len(CITATION.findall(text)) for text in texts) for path, texts in held.items()}
    assert cited["mutants.py"] >= 120
    assert all(count >= 1 for count in cited.values()), cited


def test_every_test_module_that_cites_the_text_is_listed() -> None:
    """A module that cites the specification as `file:line` and is neither a source of the model nor listed
    in `TEST_SOURCES` has citations nothing reads. This module holds the examples that must fail."""
    files = {path.name for path in SPECIFICATION.iterdir() if path.suffix == ".md"}
    citing = {
        path
        for path in (REPOSITORY / "tests").rglob("*.py")
        if any(match["file"] in files for match in REFERENCE.finditer(path.read_text(encoding="utf-8")))
    }
    assert sorted(citing - {*SOURCES, *TEST_SOURCES, Path(__file__).resolve()}) == []


def test_every_seeded_fault_cites_the_text_or_names_the_open_point_it_rests_on() -> None:
    tree = ast.parse(SEEDED_FAULTS_SOURCE.read_text(encoding="utf-8"))
    mutants = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Mutant"
    ]
    rules = [
        str(rule.value) for rule in (mutant.args[1] for mutant in mutants) if isinstance(rule, ast.Constant)
    ]
    assert len(rules) == len(mutants)
    assert len(rules) > 120
    named = [OPEN_POINT_NAMED.search(rule) for rule in rules if not REFERENCE.search(rule)]
    assert all(match and match[1] in read_model.OPEN_POINTS for match in named), named


def test_the_model_cites_the_text_for_its_rules() -> None:
    cited = [citation for text in model_prose() for citation in CITATION.finditer(text)]
    assert len(cited) > 150
    assert {citation["file"] for citation in cited} >= {
        "read_side_contract.md",
        "record_format.md",
        "provenance.md",
        "uncertainty.md",
        "declarations.md",
        "README.md",
    }


def test_every_open_point_is_listed_once_and_named_where_it_is_applied() -> None:
    assert open_point_problems(model_prose(), read_model.OPEN_POINTS) == []
    assert all(choice.strip() for choice in read_model.OPEN_POINTS.values())


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ('read_side_contract.md:231 "Find the field (`absent`)"', None),
        ('read_side_contract.md:230-231 "Find the field (`absent`)"', None),
        ('read_side_contract.md:232 "Find the field (`absent`)"', "is not at lines 232 to 232"),
        ('read_side_contract.md:230 "Find the field (`absent`)"', "is not at lines 230 to 230"),
        ('read_side_contract.md:231 "Find the record"', "is not at lines 231 to 231"),
        ('read_side_contract.md:231 "Find the field" and "a quote not there"', "'a quote not there'"),
        ('read_side_contracts.md:222 "Find the field"', "no file read_side_contracts.md"),
        (
            'record_format.md:591 "Two names are **one slip** apart when one becomes the other by '
            'inserting,"',
            None,
        ),
        ("read_side_contract.md:231, where the field is found", "read_side_contract.md:231: no quote"),
        ('see read_side_contract.md:230-231 (step 7), "Find the field"', "read_side_contract.md:230-231: no"),
        (
            'provenance.md:265-266 "or `{"status": "unstated"}` (a ± whose kind the source does not state)"',
            None,
        ),
        (
            'provenance.md:265-266 "or `{"status": "unstated"}` (a ± whose kind the source does state)"',
            "is not at lines 265 to 266",
        ),
        ('provenance.md:97 "`{"status": "not_checked"}`, or" and "with who checked"', None),
        ('provenance.md:97 "`{"status": "not_checked"}`, or `{"result"" and "with who', "no quote"),
    ],
)
def test_a_citation_that_drifts_fails(text: str, problem: str | None) -> None:
    found = citation_problems([text])
    assert found == [] if problem is None else len(found) == 1 and problem in found[0]


def test_an_open_point_named_and_listed_apart_fails() -> None:
    listed = {"known": "a choice", "unused": "another"}
    assert open_point_problems(["Open point: known.", "Open point: unknown."], listed) == [
        "named but not listed: unknown",
        "listed but named nowhere: unused",
    ]


def test_the_evaluator_is_held_to_the_same_citation_rules() -> None:
    texts = prose(EVALUATOR_SOURCE.read_text(encoding="utf-8"))
    assert sum(len(CITATION.findall(text)) for text in texts) >= 20
    assert citation_problems(texts) == []
    assert EVALUATOR_SOURCE in SOURCES


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        pytest.param(
            "read_side_contract.md:557 ", "read_side_contract.md:566 ", "is not at lines 566", id="line"
        ),
        pytest.param('"Linear interpolation within', '"Linear interpolation outside', "outside", id="quote"),
        pytest.param(
            "read_side_contract.md:557 ", "read_contract.md:557 ", "no file read_contract.md", id="file"
        ),
    ],
)
def test_a_citation_of_the_evaluator_that_drifts_fails(old: str, new: str, problem: str) -> None:
    """The evaluator's own source, with one of its citations drifted, fails the check that passes it."""
    source = EVALUATOR_SOURCE.read_text(encoding="utf-8")
    assert source.count(old) == 1
    assert citation_problems(prose(source)) == []
    found = citation_problems(prose(source.replace(old, new)))
    assert len(found) == 1
    assert problem in found[0]


@pytest.mark.parametrize(
    ("source", "old", "new", "problem"),
    [
        pytest.param(
            SEEDED_FAULTS_SOURCE,
            "read_side_contract.md:139 ",
            "read_side_contract.md:140 ",
            "lines 140 to 140",
            id="mutants-one-line-after",
        ),
        pytest.param(
            SEEDED_FAULTS_SOURCE,
            "read_side_contract.md:139 ",
            "read_side_contract.md:138 ",
            "lines 138 to 138",
            id="mutants-one-line-before",
        ),
        pytest.param(
            SEEDED_FAULTS_SOURCE,
            ' "A reason carries `condition` exactly when it concerns one condition"',
            "",
            "read_side_contract.md:139: no quote",
            id="mutants-no-quote",
        ),
        pytest.param(
            SEEDED_FAULTS_SOURCE,
            "A reason carries `condition` exactly when",
            "A reason carries `alternative` exactly when",
            "is not at lines 139 to 139",
            id="mutants-quote-changed",
        ),
        pytest.param(
            MUTANT_KILLS_SOURCE,
            "(provenance.md:51-53 ",
            "(provenance.md:52-54 ",
            "lines 52 to 54",
            id="properties",
        ),
    ],
)
def test_a_citation_of_a_seeded_fault_that_drifts_fails(
    source: Path, old: str, new: str, problem: str
) -> None:
    """The source of the seeded faults and the test of their kills, with one citation drifted, fail the check
    that passes them: a citation there is a string or a docstring, which `prose` alone does not read."""
    text = source.read_text(encoding="utf-8")
    assert text.count(old) == 1
    assert citation_problems(held_in(text)) == []
    found = citation_problems(held_in(text.replace(old, new)))
    assert len(found) == 1
    assert problem in found[0]

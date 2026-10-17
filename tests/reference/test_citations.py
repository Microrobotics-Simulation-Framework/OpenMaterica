# SPDX-License-Identifier: Apache-2.0
"""Each rule of the reference model cites the specification as `file:line` and a short quote; each quote is
found at its line, so that a citation that drifts from the text fails, and so does a `file:line` without a
quote, which nothing could check. A quote holds `"` only inside a code span, as the text's JSON stands, so
that it ends at the first `"` outside one. Each point the text leaves open is listed once in `OPEN_POINTS`
and named where the model applies it, and the two agree."""

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
SOURCES = [REPOSITORY / "tests" / "reference" / name for name in ("read_model.py", "strict_json.py")]
# A quote's text: characters but `"` and a backtick, and code spans, which may hold `"`.
QUOTED = r'"((?:[^"`]|`[^`]*`)+)"'
REFERENCE = re.compile(r"(?P<file>[A-Za-z_]+\.md):(?P<start>\d+)(?:-(?P<end>\d+))?")
CITATION = re.compile(
    REFERENCE.pattern + r"\s+(?P<quotes>" + QUOTED + r"(?:\s*(?:and|or|,|;|\.\.\.)\s*" + QUOTED + r")*)"
)
QUOTE = re.compile(QUOTED)
OPEN_POINT = re.compile(r"Open point: (?P<name>[a-z0-9_]+)")


def prose(source: str) -> list[str]:
    """The comments of `source`, each run of comment lines joined, and its docstrings."""
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
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            docstring = ast.get_docstring(node)
            if docstring:
                texts.append(docstring)
    return [" ".join(text.split()) for text in texts]


def specification_lines(file: str) -> list[str] | None:
    path = SPECIFICATION / file
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else None


def citation_problems(texts: Iterable[str]) -> list[str]:
    """Each citation whose file is not in the specification, or whose quote is not at its lines (a quote may
    run on to the line after the last one cited); and each `file:line` with no quote."""
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
            window = " ".join(" ".join(lines[start - 1 : end + 1]).split())
            problems.extend(
                f"{file}:{start}: {quote!r} is not at lines {start} to {end}"
                for quote in QUOTE.findall(citation["quotes"])
                if quote not in window
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
        ('read_side_contract.md:225 "Find the field (`absent`)"', None),
        ('read_side_contract.md:224-225 "Find the field (`absent`)"', None),
        ('read_side_contract.md:226 "Find the field (`absent`)"', "is not at lines 226 to 226"),
        ('read_side_contract.md:225 "Find the record"', "is not at lines 225 to 225"),
        ('read_side_contract.md:225 "Find the field" and "a quote not there"', "'a quote not there'"),
        ('read_side_contracts.md:222 "Find the field"', "no file read_side_contracts.md"),
        (
            'record_format.md:581 "Two names are **one slip** apart when one becomes the other by '
            'inserting,"',
            None,
        ),
        ("read_side_contract.md:225, where the field is found", "read_side_contract.md:225: no quote"),
        ('see read_side_contract.md:224-225 (step 7), "Find the field"', "read_side_contract.md:224-225: no"),
        (
            'provenance.md:246-247 "or `{"status": "unstated"}` (a ± whose kind the source does not state)"',
            None,
        ),
        (
            'provenance.md:246-247 "or `{"status": "unstated"}` (a ± whose kind the source does state)"',
            "is not at lines 246 to 247",
        ),
        ('provenance.md:96 "`{"status": "not_checked"}`, or" and "with who checked"', None),
        ('provenance.md:96 "`{"status": "not_checked"}`, or `{"result"" and "with who', "no quote"),
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

# SPDX-License-Identifier: Apache-2.0
"""The anomaly check passes a registry that keeps every rule, and fails a copy with any one fault, naming that
rule; its YAML reader reads what PyYAML reads, and refuses what it does not read. On registries written here,
never on the repository's own, which the gate checks on every change."""

import datetime
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# `packaging` comes with pytest, which depends on it.
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from scripts import check_anomalies

VERSION = "0.1.0.dev1"
SCRIPT = Path(check_anomalies.__file__)

# A registry that keeps every rule, its two entries holding every field between them, in each form the reader
# reads: values quoted both ways and plain, folded and literal block scalars, lists, null, `~` and comments.
REGISTRY = """\
# A registry for the tests.
schema_version: "1.0"
materica_version: "0.1.0.dev1"
generated_date: "2026-10-17"

anomalies:
  - anomaly_id: "OMAT-ANO-001"
    title: "A wrong unit conversion"
    description: >
      The reader converts the field to the wrong unit
      under one condition:
        - a list item, kept on its own line;

      found by a conformance case.
    severity: "major"
    safety_relevance: "context_dependent"
    safety_relevance_rationale: |
      A silent wrong value
        reaches a consumer's simulation.
    affected_components:
      - "reader:read"
      - "schema:MatericaAcousticAPI"
      - "method:OMAT-MTH-002"
      - "model:materica.mechanical.ogden_incompressible.v1"
      - "data:MAT-0003"
    affected_versions: ">=0.1.0.dev0"
    workaround: 'Convert the value by hand; it''s exact.'
    resolution_status: open
    resolution_version: null
    verification: []
    residual_risk: "None known."
    github_issue: ~

  - anomaly_id: "OMAT-ANO-002"
    title: "A defect no release carried"
    description: "Introduced and fixed within one development cycle."
    severity: "minor"
    safety_relevance: "not_safety_relevant"
    safety_relevance_rationale: "A loud failure."  # a comment after a value
    affected_versions: "none"
    resolution_status: "resolved"
    resolution_version: "0.1.0.dev1"
"""


def problems(tmp_path: Path, text: str = REGISTRY, version: str = VERSION) -> list[str]:
    registry = tmp_path / "registry.yaml"
    registry.write_text(text, encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(f'[project]\nname = "openmaterica"\nversion = "{version}"\n', encoding="utf-8")
    found = check_anomalies.registry_problems(registry, pyproject)
    return [problem.removeprefix(f"{registry}: ") for problem in found]


def with_fault(old: str, new: str) -> str:
    """The registry with one change, `old`, which it holds once, made `new`."""
    assert REGISTRY.count(old) == 1, old
    return REGISTRY.replace(old, new)


def test_a_registry_that_keeps_every_rule_passes(tmp_path: Path) -> None:
    assert problems(tmp_path) == []


def test_an_empty_registry_passes(tmp_path: Path) -> None:
    empty = (
        'schema_version: "1.0"\nmaterica_version: "0.1.0.dev1"\ngenerated_date: "2026-10-17"\nanomalies: []\n'
    )
    assert problems(tmp_path, empty) == []


def test_the_registry_is_read_as_pyyaml_reads_it() -> None:
    assert check_anomalies.read_registry(REGISTRY) == yaml.safe_load(REGISTRY)


ENTRY_TWO = '    title: "A defect no release carried"\n'
NOT_A_RANGE = "neither a PEP 440 version specifier set nor 'none'"


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        # The prefix, and the identifier's three digits.
        (
            '"OMAT-ANO-002"',
            '"MADD-ANO-002"',
            "MADD-ANO-002: the anomaly_id is not OMAT-ANO- and three digits",
        ),
        ('"OMAT-ANO-002"', '"OMAT-ANO-2"', "OMAT-ANO-2: the anomaly_id is not OMAT-ANO- and three digits"),
        # materica_version in place of maddening_version.
        (
            "materica_version:",
            "maddening_version:",
            "the version field is materica_version, not MADDENING's maddening_version",
        ),
        # affected_versions: a PEP 440 version specifier set, or none, on every entry.
        (
            '">=0.1.0.dev0"',
            '">=0.1.0.dev0 <0.2.0"',
            f"OMAT-ANO-001: affected_versions is '>=0.1.0.dev0 <0.2.0', {NOT_A_RANGE}",
        ),
        ('">=0.1.0.dev0"', '"0.1.0.dev0"', f"OMAT-ANO-001: affected_versions is '0.1.0.dev0', {NOT_A_RANGE}"),
        ('">=0.1.0.dev0"', '">=0.1.*"', f"OMAT-ANO-001: affected_versions is '>=0.1.*', {NOT_A_RANGE}"),
        (
            '">=0.1.0.dev0"',
            '">=0.1.0.dev0,"',
            f"OMAT-ANO-001: affected_versions is '>=0.1.0.dev0,', {NOT_A_RANGE}",
        ),
        ('"none"', '"None"', f"OMAT-ANO-002: affected_versions is 'None', {NOT_A_RANGE}"),
        ('"none"', '""', f"OMAT-ANO-002: affected_versions is '', {NOT_A_RANGE}"),
        ('    affected_versions: "none"\n', "", f"OMAT-ANO-002: affected_versions is None, {NOT_A_RANGE}"),
        # Severity, as DOCUMENTATION_ARCHITECTURE.md section 8.2 defines it, and MADDENING's other values.
        (
            '"minor"',
            '"low"',
            "OMAT-ANO-002: the severity 'low' is none of critical, major, minor, enhancement",
        ),
        (
            '"not_safety_relevant"',
            '"not_relevant"',
            "OMAT-ANO-002: the safety_relevance 'not_relevant' is none of safety_relevant, "
            "not_safety_relevant, context_dependent",
        ),
        (
            "resolution_status: open",
            "resolution_status: closed",
            "OMAT-ANO-001: the resolution_status 'closed' is none of open, resolved, partially_resolved, "
            "wont_fix, duplicate",
        ),
        # Component names: a kind and a name.
        *(
            (
                '"data:MAT-0003"',
                f'"{component}"',
                f"OMAT-ANO-001: the affected component '{component}' is not schema:, reader:, method:, "
                "model: or data: and a name",
            )
            for component in ("MAT-0003", "material:MAT-0003", "data:", "data:MAT 0003")
        ),
        (
            '    affected_versions: "none"\n',
            '    affected_versions: "none"\n    affected_components: "data:MAT-0003"\n',
            "OMAT-ANO-002: affected_components is not a list",
        ),
        # Unique identifiers.
        ('"OMAT-ANO-002"', '"OMAT-ANO-001"', "OMAT-ANO-001: another entry has this anomaly_id"),
        # materica_version, the package's version.
        (
            'materica_version: "0.1.0.dev1"',
            'materica_version: "0.1.0.dev0"',
            "materica_version is '0.1.0.dev0', but the package's version (pyproject.toml) is '0.1.0.dev1': a "
            "version's bump updates the registry too",
        ),
        # MADDENING's record: its required fields, each a non-empty string, and no other field.
        (ENTRY_TWO, "", "OMAT-ANO-002: title is missing, or not a quoted, non-empty string"),
        (
            '"A loud failure."',
            '""',
            "OMAT-ANO-002: safety_relevance_rationale is missing, or not a quoted, non-empty string",
        ),
        (ENTRY_TWO, "    title: []\n", "OMAT-ANO-002: title is missing, or not a quoted, non-empty string"),
        (
            "    residual_risk:",
            "    residual_risks:",
            "OMAT-ANO-001: the field residual_risks is not one of MADDENING's record",
        ),
        # Its top level.
        (
            'schema_version: "1.0"\n',
            'schema_version: "1.0"\nproject: "openmaterica"\n',
            "the top-level field project is not one of MADDENING's (schema_version, materica_version, "
            "generated_date, anomalies)",
        ),
        ('generated_date: "2026-10-17"\n', "", "the top-level field generated_date is missing"),
        ('schema_version: "1.0"', "schema_version: ''", "schema_version is not a quoted, non-empty string"),
        ('"2026-10-17"', '"2026-10-32"', "generated_date is '2026-10-32', not a date written YYYY-MM-DD"),
        ('"2026-10-17"', '"20261017"', "generated_date is '20261017', not a date written YYYY-MM-DD"),
    ],
)
def test_a_registry_with_one_fault_fails_that_rule(tmp_path: Path, old: str, new: str, problem: str) -> None:
    assert problems(tmp_path, with_fault(old, new)) == [problem]


@pytest.mark.parametrize(
    ("anomalies", "problem"),
    [
        ('anomalies: "none"\n', "anomalies is not a list (`[]` when empty)"),
        ("anomalies:\n", "anomalies is not a list (`[]` when empty)"),
        ('anomalies:\n  - "OMAT-ANO-001"\n', "entry 1 is not a mapping"),
    ],
)
def test_anomalies_that_are_not_a_list_of_entries_fail(tmp_path: Path, anomalies: str, problem: str) -> None:
    head = 'schema_version: "1.0"\nmaterica_version: "0.1.0.dev1"\ngenerated_date: "2026-10-17"\n'
    assert problems(tmp_path, head + anomalies) == [problem]


@pytest.mark.parametrize(
    "affected",
    [">=0.1.0.dev0, <0.1.0", "==0.1.*", "!=0.1.0+local.7", "~=0.1", "===0.1.0-anything", " none "],
)
def test_every_pep_440_specifier_set_passes(tmp_path: Path, affected: str) -> None:
    assert problems(tmp_path, with_fault('">=0.1.0.dev0"', f'"{affected}"')) == []


# Specifier sets that `packaging` reads, and some it refuses, without an empty specifier, which it skips.
SPECIFIER_SETS = [
    ">=0.1.0.dev0",
    ">=0.1.0.dev0, <0.2.0",
    ">= 1.0 , < 2.0",
    "==0.1.*",
    "==1!2.0.post3.dev4+local.5",
    "!=1.0+abc",
    "~=0.1",
    "~=1.0rc1",
    "===anything-at-all",
    "<1.0rc1",
    ">1.0-1",
    "==v1.0",
    "== 1.0.0-alpha.1",
    "0.1.0",
    "~=1",
    "~=1.0.*",
    ">=0.1.*",
    "<1.0+local",
    ">=0.1.0 <0.2.0",
    "=>1.0",
    ">=",
    "==1.0.*.1",
    ">=1.0;",
    "1.0",
    "latest",
]


@pytest.mark.parametrize("text", SPECIFIER_SETS)
def test_a_specifier_set_is_read_as_packaging_reads_it(text: str) -> None:
    try:
        SpecifierSet(text)
    except InvalidSpecifier:
        valid = False
    else:
        valid = True
    assert check_anomalies.is_specifier_set(text) == valid


@pytest.mark.parametrize("text", ["", " ", ">=1.0,", ">=1.0, ,<2.0"])
def test_an_empty_specifier_is_refused_where_packaging_skips_it(text: str) -> None:
    """PEP 440 has no empty specifier, and an empty set would admit every version (MADDENING refuses one)."""
    SpecifierSet(text)
    assert not check_anomalies.is_specifier_set(text)


BACKSLASH = "\\"

# Documents in each form the reader reads, which it must read as PyYAML does.
READ_ALIKE = {
    "folded": "a: >\n  one\n  two\n\n  three\n\n\n  four\nb: x\n",
    "folded, a line indented past the others": "a: >\n  one\n    two\n  three\n",
    "folded, blank lines around one indented past": "a: >\n  one\n\n    two\n\n  three\n  four\n",
    "folded, trailing spaces kept": "a: >\n  one  \n  two\n",
    "literal": "a: |\n  one\n    two\n\n  three\n",
    "strip": "a: >-\n  one\n\n\nb: null\n",
    "keep": "a: >+\n  one\n\n\nb: ~\n",
    "keep, to the end": "a: |+\n  one\n\n",
    "keep, before a comment": "a: |+\n  one\n\n# c\n\nb: null\n",
    "a comment's mark inside a block": "a: |\n  one\n  # not a comment\nb: []\n",
    "a comment after a block": "a: |\n  one\n# c\n\nb: [ ]\n",
    "a comment after a block's header": "a: > # c\n  x\n",
    "double-quoted escapes": (
        'a: "'
        + f" {BACKSLASH}".join(["/", "N", "_", "L", "P", "e", "x41", "u00e9", "U0001F600", "0", " ", "t"])
        + f' {BACKSLASH}" {BACKSLASH}{BACKSLASH} # not a comment"  # a comment\n'
    ),
    "single-quoted": "a: 'it''s # not a comment'\n",
    "plain words": "a: open\nb: MIME-ANO-001\nc: v1.2_x\n",
    "an indentless sequence": "a:\n- 'x'\n- \"y\"\nb: null\n",
    "an empty value": "a:\nb: ~\n",
    "a sequence of mappings": (
        "a:\n  -   k: '1'\n      l: '2'\n  - k: '3'\n    m:\n    - 'q'\n    n: >\n      x\n\n      y\nb: []\n"
    ),
    "comments between items": "a:\n  # c\n  - 'x'  # d\n\n  - \"y\"\n# e\nb: 'z'\n",
}


@pytest.mark.parametrize("text", READ_ALIKE.values(), ids=READ_ALIKE.keys())
def test_the_reader_reads_as_pyyaml_reads(text: str) -> None:
    assert check_anomalies.read_registry(text) == yaml.safe_load(text)


# Documents the reader refuses, and what it says.
REFUSED = {
    "a number unquoted": ("a: 0.10\n", "line 1 has the value '0.10' unquoted"),
    "a date unquoted": ("a: 2026-10-17\n", "line 1 has the value '2026-10-17' unquoted"),
    "a boolean unquoted": ("a: Yes\n", "line 1 has the value 'Yes' unquoted"),
    "null in capitals": ("a: NULL\n", "line 1 has the value 'NULL' unquoted"),
    "a key given twice": ("a: 'x'\nb: 'y'\na: 'z'\n", "line 3 gives 'a' a second time"),
    "a key read as a boolean": (
        "on: 'x'\n",
        "line 1 has the key 'on', which YAML reads as a boolean or null",
    ),
    "a tab in the indentation": ("a:\n\t- 'x'\n", "line 2 is indented with a tab"),
    "a value below its key": ("a:\n  one\n", "line 2 holds a value below its key"),
    "a nested mapping": ("a:\n  b: 'x'\n", "line 2 holds a value below its key"),
    "a quoted value over two lines": (
        'a: "one\n  two"\n',
        "line 1 has a quoted value that does not end on it",
    ),
    "an anchor": ("a: &x 'one'\n", "line 1 has the value \"&x 'one'\" unquoted"),
    "a flow mapping": ("a: {b: 'x'}\n", "line 1 has the value \"{b: 'x'}\" unquoted"),
    "a document marker": ("---\na: 'x'\n", "line 1 is not `key: value`"),
    "an indentation indicator": ("a: |2\n  x\n", "line 1 has a block scalar header other than"),
    "a blank line opening a block": ("a: >\n\n  x\n", "line 2 is blank before a block scalar's first line"),
    "a block with no line": ("a: >\nb: 'x'\n", "line 1 starts a block scalar with no line"),
    "spaces past a block's indentation": ("a: |\n  x\n     \n  y\n", "line 3 holds spaces past its block"),
    "a line separator": (f"a: 'x{chr(0x2028)}y'\n", "line 1 holds U+2028"),
    "a carriage return": ("a: 'x'\r\nb: 'y'\r\n", "line 1 holds U+000D"),
    "no final line break": ("a: 'x'", "its last line has no line break"),
    "an escape YAML does not define": (
        f'a: "{BACKSLASH}q"\n',
        "line 1 has the escape \\q is not one YAML defines",
    ),
    "text after a quoted value": ('a: "x"#c\n', "line 1 has '#c' after a quoted value"),
    "an indented top level": ("  a: 'x'\n", "line 1 is indented"),
    "a sequence at the top": ("- 'x'\n", "line 1 is a sequence's item where a key belongs"),
    "nothing": ("# only a comment\n", "it holds no mapping"),
}


@pytest.mark.parametrize(("text", "message"), REFUSED.values(), ids=REFUSED.keys())
def test_the_reader_refuses_what_it_does_not_read(text: str, message: str) -> None:
    with pytest.raises(check_anomalies.RegistryFormatError) as refused:
        check_anomalies.read_registry(text)
    assert message in str(refused.value)


@pytest.mark.parametrize(
    ("plain", "read"),
    [("0.10", 0.1), ("2026-10-17", datetime.date(2026, 10, 17)), ("Yes", True), ("NULL", None)],
)
def test_the_plain_values_refused_are_those_pyyaml_reads_as_no_string(plain: str, read: object) -> None:
    """Why the reader refuses them: a version or a date unquoted reaches a check as a number or a date."""
    assert yaml.safe_load(f"a: {plain}\n") == {"a": read}


def test_a_key_given_twice_is_read_by_pyyaml_as_its_last() -> None:
    """Why the reader refuses it: PyYAML keeps the last value, silently, so the first goes unchecked."""
    assert yaml.safe_load("a: 'x'\nb: 'y'\na: 'z'\n") == {"a": "z", "b": "y"}


def test_the_command_exits_nonzero_and_names_each_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    problems(tmp_path)
    registry, pyproject = str(tmp_path / "registry.yaml"), str(tmp_path / "pyproject.toml")
    assert check_anomalies.main([registry, "--pyproject", pyproject]) == 0
    problems(tmp_path, with_fault('"minor"', '"low"'))
    assert check_anomalies.main([registry, "--pyproject", pyproject]) == 1
    assert "OMAT-ANO-002: the severity 'low' is none of" in capsys.readouterr().err


def test_the_check_runs_on_the_standard_library_alone(tmp_path: Path) -> None:
    """The gate runs it before any dependency is installed: so it runs in a Python that sees no installed
    package (`-S`), passing the registry and failing it with a fault. The control shows the flag hides one."""
    problems(tmp_path)
    command = [sys.executable, "-I", "-S", str(SCRIPT), str(tmp_path / "registry.yaml")]
    command += ["--pyproject", str(tmp_path / "pyproject.toml")]
    passed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert passed.returncode == 0, passed.stderr
    problems(tmp_path, version="0.1.0.dev2")
    failed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert failed.returncode == 1
    assert "but the package's version (pyproject.toml) is '0.1.0.dev2'" in failed.stderr
    control = subprocess.run(
        [sys.executable, "-I", "-S", "-c", "import yaml"], capture_output=True, check=False
    )
    assert control.returncode != 0

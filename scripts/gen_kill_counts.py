# SPDX-License-Identifier: Apache-2.0
"""Write the kill counts of `tests/property/README.md` from the recorded kill points; hold both to the runs.

    python scripts/gen_kill_counts.py                      # write the README's counts from kill_points.json
    python scripts/gen_kill_counts.py --check              # fail where they differ, or where a kill is late
    python scripts/gen_kill_counts.py --record REPORT ...  # record the kills of JUnit reports, then write
    python scripts/gen_kill_counts.py --against REPORT ... # fail where a report's kills are not the recorded
    uv run python scripts/gen_kill_counts.py --measure [--record] [--workers N]

Every mutant search records the examples its kill took as `examples_to_kill`, which pytest's `--junitxml`
writes out. `tests/property/kill_points.json` holds them, one group per test function and one line per
mutant, `[small, original]`, under `kills`; this script alone writes it, from such reports. A search is
derandomised, draws none of the harvested constants and has the `ci` profile's examples whatever the
profile, so its kill point is fixed by the code and by what Hypothesis seeds it from.

What the kill points depend on, besides the strategies and checks a search draws, is recorded under `inputs`:
the Hypothesis version (`uv.lock`), and, for each of the `kill` helpers that runs a search (a function
decorated `@MUTANT_SEARCH`) and for `MUTANT_SEARCH` itself, a digest of its source (blank and comment-only
lines left out, as Hypothesis leaves them out of its own). A derandomised search is seeded from the digest of
its function, which is the same text for every mutant a helper searches: renaming a local in the helper moves
hundreds of kills at once, with nothing about the mutants changed. `--check` and `--against` fail first,
naming the input that differs from the tree, so a re-seed is never an unexplained wall of moved kills;
the cure is `--measure --record`. A digest is of the text, so it also flags an edit that moves nothing
(a comment after code on a line): the cost is one re-recording, which then moves no kill.

In the README, a comment line names the group of the table under it, `<!-- kill points of every search of
<file>::<function> (scripts/gen_kill_counts.py) -->` for a table that holds a row for each of the group's
mutants, or `of some searches of` for one that holds some. The last cell of each row, whose first cell names
one mutant, is written as `small, original`. The sentence between `<!-- kill points summary
(scripts/gen_kill_counts.py) -->` and `<!-- end of kill points summary -->` is written whole. Every recorded
group has a table, but the ones listed in `NO_TABLE`: a deleted comment line would otherwise take a table out
of this script's hands.

`--check` fails where the README differs from what the file gives, the file is not in this script's layout,
its inputs differ from the tree's, a recorded group has no table, a table of every search lacks a row for a
recorded mutant of its group, or a kill point lies after the 500th example (the margin guard). A row of a
mutant the file does not hold yet passes `--check`: `--against` holds it, at the head, against the run of
every search.

`--record` replaces each group a report holds with the report's kill points: a report of part of a module
records part of it, unless the inputs changed, when only a run of every search can be recorded. `--against`
holds the file to a run of every search: it fails where a report's kill point differs from the recorded one, a
search it ran is not recorded, a recorded search of a group it holds did not record a kill, a row of such a
group's table names a mutant it did not run, a recorded group is missing from the run (a renamed or deleted
test function leaves counts nothing runs: `--measure --record` drops it), or a search passed without
recording `examples_to_kill`, which the file, the README and the margin guard cannot see. `--partial` is for a
hand-run report of part of the searches: groups it lacks are not required. CI's `controls` job runs
`--against` on its report of every search. `--measure` runs every search (`pytest tests/property
--property-controls only`) into a temporary report, then checks it as `--against` does, or with `--record`
records it, the file then holding exactly the groups of that run; it needs the project's environment
(`uv run`).
"""

import argparse
import ast
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

REPOSITORY = Path(__file__).resolve().parents[1]
KILL_POINTS = REPOSITORY / "tests" / "property" / "kill_points.json"
README = REPOSITORY / "tests" / "property" / "README.md"
PROPERTY_TESTS = REPOSITORY / "tests" / "property"
LOCK = REPOSITORY / "uv.lock"

# The margin guard: a kill after this example fails `--check` (maintainer, 2026-10-19). A search is
# derandomised, so its kill point is one seed's; a late one is a thin margin to the 2,000 examples, which a
# change of seed (a Hypothesis upgrade) can cross.
MARGIN = 500
SIZES = ("small", "original")

# The recorded groups the README has no table for. Every other recorded group has one, which `--check`
# demands: a deleted marker line would otherwise take its table out of this script's hands.
NO_TABLE = frozenset(
    {
        "test_record_mutants.py::test_the_mutant_is_killed",
        "test_writer_mutants.py::test_the_writer_mutant_is_killed_at_its_assertion",
    }
)
# What a derandomised search is seeded from, in the tests: a function decorated with this, and its definition.
SEARCH_SETTINGS = "MUTANT_SEARCH"
HYPOTHESIS = "hypothesis"

GROUP = re.compile(r"test_\w+\.py::test_\w+")
MARKER = re.compile(
    r"<!-- kill points of (?P<extent>every search|some searches) of (?P<group>\S+)"
    r" \(scripts/gen_kill_counts\.py\) -->"
)
SUMMARY_START = "<!-- kill points summary (scripts/gen_kill_counts.py) -->"
SUMMARY_END = "<!-- end of kill points summary -->"
CELL_BORDER = re.compile(r"(?<!\\)\|")
NAMED = re.compile(r"`([^`\s]+)`")

# Each group's kill points, by mutant: (small, original).
KillPoints = dict[str, dict[str, tuple[int, int]]]
# A report's kills: by group, by mutant, by size.
Reported = dict[str, dict[str, dict[str, int]]]
# What the kill points depend on: the Hypothesis version, and a digest of each seeding function's source.
Inputs = dict[str, str]


@dataclass(frozen=True)
class Record:
    """The file: what the kill points were recorded with, and the kill points."""

    inputs: Inputs
    kills: KillPoints


@dataclass(frozen=True)
class Report:
    """What reports hold: the kills, and the searches that passed without recording one."""

    kills: Reported
    silent: tuple[str, ...] = ()


class CountsError(Exception):
    """A file or report this script cannot read as it is specified."""


# --- the recorded file -------------------------------------------------------------------------------------


def load(text: str) -> Record:
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise CountsError(f"{KILL_POINTS.name} is not JSON: {error}") from None
    if not isinstance(data, dict) or set(cast(dict[str, object], data)) != {"inputs", "kills"}:
        raise CountsError(f"{KILL_POINTS.name} is not an object of `inputs` and `kills`")
    parts = cast(dict[str, object], data)
    inputs, groups = parts["inputs"], parts["kills"]
    if (
        not isinstance(inputs, dict)
        or not inputs
        or not all(isinstance(name, str) and isinstance(value, str) for name, value in inputs.items())  # pyright: ignore[reportUnknownVariableType]
    ):
        raise CountsError(f"{KILL_POINTS.name}: `inputs` is not an object of strings")
    if not isinstance(groups, dict):
        raise CountsError(f"{KILL_POINTS.name}: `kills` is not an object of groups")
    recorded: KillPoints = {}
    for group, mutants in cast(dict[str, object], groups).items():
        if not GROUP.fullmatch(group):
            raise CountsError(f"{group!r} is not a group, <file>::<test function>")
        if not isinstance(mutants, dict) or not mutants:
            raise CountsError(f"{group}: not an object of mutants")
        recorded[group] = {}
        for mutant, kills in cast(dict[str, object], mutants).items():
            pair = cast(list[object], kills) if isinstance(kills, list) else []
            small, original = pair if len(pair) == len(SIZES) else [None, None]
            if not (type(small) is int and type(original) is int and small >= 1 and original >= 1):
                raise CountsError(f"{group}: {mutant}: not [small, original], two kill points from 1")
            recorded[group][mutant] = (small, original)
    return Record(cast(Inputs, inputs), recorded)


def dump(record: Record) -> str:
    """The file's one layout: inputs, groups and mutants in name order, one line each."""
    inputs = ",\n".join(
        f"    {json.dumps(name)}: {json.dumps(value)}" for name, value in sorted(record.inputs.items())
    )
    groups: list[str] = []
    for group in sorted(record.kills):
        lines = [
            f"      {json.dumps(mutant)}: [{small}, {original}]"
            for mutant, (small, original) in sorted(record.kills[group].items())
        ]
        groups.append(f"    {json.dumps(group)}: {{\n" + ",\n".join(lines) + "\n    }")
    kills = "{\n" + ",\n".join(groups) + "\n  }" if groups else "{}"
    return '{\n  "inputs": {\n' + inputs + '\n  },\n  "kills": ' + kills + "\n}\n"


# --- what the kill points depend on ------------------------------------------------------------------------


def digest(lines: Sequence[str]) -> str:
    """Twelve hex digits of the lines, without blank or comment-only lines and trailing whitespace, as
    Hypothesis cleans the source it seeds a search from (and with the indentation, which it keeps)."""
    kept = [line.rstrip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return hashlib.sha256("\n".join(kept).encode()).hexdigest()[:12]


def is_search_settings(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == SEARCH_SETTINGS


def seeding_sources(path: Path) -> dict[str, str]:
    """The digests of the definitions in a test module that seed a derandomised search: each function
    decorated with the search settings (named by the function it is defined in), and the settings."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    where = path.relative_to(REPOSITORY).as_posix()
    found: dict[str, str] = {}

    def add(name: str, source: Sequence[str]) -> None:
        if name in found:
            raise CountsError(f"{name}: two definitions seed searches under one name")
        found[name] = digest(source)

    def visit(node: ast.AST, enclosing: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            inside = enclosing
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(is_search_settings(decorator) for decorator in child.decorator_list):
                    first = min([child.lineno, *(decorator.lineno for decorator in child.decorator_list)])
                    add(f"{where}::{enclosing or child.name}", lines[first - 1 : child.end_lineno])
                inside = enclosing or child.name
            elif isinstance(child, ast.Assign) and any(
                is_search_settings(target) for target in child.targets
            ):
                add(f"{where}::{SEARCH_SETTINGS}", lines[child.lineno - 1 : child.end_lineno])
            visit(child, inside)

    visit(ast.parse(text), None)
    return found


def locked_hypothesis() -> str:
    """The Hypothesis version `uv.lock` pins."""
    try:
        packages = tomllib.loads(LOCK.read_text(encoding="utf-8")).get("package", [])
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CountsError(f"{LOCK}: cannot read the Hypothesis version: {error}") from None
    versions = [package.get("version") for package in packages if package.get("name") == HYPOTHESIS]
    if len(versions) != 1 or not isinstance(versions[0], str):
        raise CountsError(f"{LOCK}: holds no one Hypothesis version")
    return versions[0]


def inputs_of_tree() -> Inputs:
    """What the tree's kill points depend on: the pinned Hypothesis version, and the seeding sources."""
    inputs: Inputs = {HYPOTHESIS: locked_hypothesis()}
    for path in sorted(PROPERTY_TESTS.glob("*.py")):
        inputs.update(seeding_sources(path))
    return inputs


def installed_hypothesis() -> str | None:
    try:
        return importlib.metadata.version(HYPOTHESIS)
    except importlib.metadata.PackageNotFoundError:
        return None


RECORD_AGAIN = "record again with --measure --record"


def stale(recorded: Inputs, tree: Inputs) -> list[str]:
    """Where the kill points were recorded with other inputs than the tree's, each named with its cause."""
    problems: list[str] = []
    for name in sorted(set(recorded) | set(tree)):
        if recorded.get(name) == tree.get(name):
            continue
        if name == HYPOTHESIS:
            problems.append(
                f"Hypothesis changed (recorded {recorded.get(name)}, uv.lock {tree.get(name)}): it seeds"
                f" every search, so any kill may have moved: {RECORD_AGAIN}"
            )
        elif name not in tree:
            problems.append(f"{name} is recorded as an input but is no longer in the tree: {RECORD_AGAIN}")
        elif name not in recorded:
            problems.append(f"{name} seeds searches and is not a recorded input: {RECORD_AGAIN}")
        else:
            problems.append(
                f"{name} changed: Hypothesis seeds each search from the source of this function, so every"
                f" search through it may have moved (the kills below are not evidence that a mutant"
                f" changed): {RECORD_AGAIN}"
            )
    return problems


# --- JUnit reports -----------------------------------------------------------------------------------------

CASE = re.compile(r"(?P<function>test_\w+)\[(?P<mutant>.+)-(?P<size>small|original)\]")
MODULE = re.compile(r"tests\.property\.(?P<module>test_\w+)")


def reported(paths: Iterable[Path]) -> Report:
    """The kills the reports hold: each test case with `examples_to_kill`, by its group, mutant and size; and
    each passed case of a mutant module at a size that has none, which no check can hold to a kill."""
    kills: Reported = {}
    silent: list[str] = []
    for path in paths:
        try:
            cases = ElementTree.parse(path).iter("testcase")
        except (OSError, ElementTree.ParseError) as error:
            raise CountsError(f"{path}: not a JUnit report pytest wrote: {error}") from None
        for case in cases:
            name, classname = case.get("name", ""), case.get("classname", "")
            found = [
                prop.get("value") for prop in case.iter("property") if prop.get("name") == "examples_to_kill"
            ]
            matched, module = CASE.fullmatch(name), MODULE.fullmatch(classname)
            if not found:
                passed = not any(
                    case.find(outcome) is not None for outcome in ("failure", "error", "skipped")
                )
                if (
                    passed
                    and matched is not None
                    and module is not None
                    and module["module"].endswith("mutants")
                ):
                    silent.append(
                        f"{module['module']}.py::{matched['function']}[{matched['mutant']}-{matched['size']}]"
                    )
                continue
            if matched is None or module is None:
                raise CountsError(
                    f"{path}: {classname}::{name}: not a mutant search of tests/property at a size"
                )
            if len(found) != 1 or not (found[0] or "").isdigit():
                raise CountsError(f"{path}: {classname}::{name}: examples_to_kill is {found}")
            group = f"{module['module']}.py::{matched['function']}"
            by_size = kills.setdefault(group, {}).setdefault(matched["mutant"], {})
            size, kill = matched["size"], int(found[0] or "0")
            if by_size.get(size, kill) != kill:
                raise CountsError(f"{group}: {matched['mutant']} at the {size} size killed at two examples")
            by_size[size] = kill
    return Report(kills, tuple(silent))


def recorded_from(kills: Reported) -> KillPoints:
    recorded: KillPoints = {}
    for group, mutants in kills.items():
        for mutant, by_size in mutants.items():
            missing = [size for size in SIZES if size not in by_size]
            if missing:
                raise CountsError(f"{group}: {mutant}: the reports hold no kill at the {missing[0]} size")
            recorded.setdefault(group, {})[mutant] = (by_size["small"], by_size["original"])
    return recorded


# --- the README --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    line: int  # its index in the README's lines
    mutant: str


@dataclass(frozen=True)
class Table:
    group: str
    every: bool
    rows: tuple[Row, ...]


def cells(line: str) -> list[str]:
    """A table row's cells, split at the pipes that are not escaped."""
    if not line.startswith("|") or not line.rstrip().endswith("|"):
        raise CountsError(f"not a table row: {line!r}")
    return CELL_BORDER.split(line.rstrip()[1:-1])


def tables(lines: Sequence[str]) -> list[Table]:
    found: list[Table] = []
    for number, line in enumerate(lines):
        marker = MARKER.fullmatch(line)
        if marker is None:
            if "kill points of" in line and line.startswith("<!--"):
                raise CountsError(f"README line {number + 1}: a kill points comment this script cannot read")
            continue
        body: list[int] = []
        for index in range(number + 1, len(lines)):
            if not lines[index].startswith("|"):
                break
            body.append(index)
        if len(body) < 3:
            raise CountsError(f"README line {number + 1}: no table of rows under the comment")
        rows: list[Row] = []
        for index in body[2:]:
            names = NAMED.findall(cells(lines[index])[0])
            if len(names) != 1:
                raise CountsError(
                    f"README line {index + 1}: the first cell names {len(names)} mutants, not one"
                )
            rows.append(Row(index, names[0]))
        found.append(Table(marker["group"], marker["extent"] == "every search", tuple(rows)))
    return found


def ordinal(number: int) -> str:
    suffix = "th" if number % 100 in (11, 12, 13) else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number:,}{suffix}"


def summary(recorded: KillPoints) -> str:
    kills = [
        (kill, group, mutant, size)
        for group, mutants in recorded.items()
        for mutant, pair in mutants.items()
        for size, kill in zip(SIZES, pair, strict=True)
    ]
    latest = max(kill for kill, *_ in kills)
    where = "; ".join(f"`{mutant}`, {size} size" for kill, _, mutant, size in sorted(kills) if kill == latest)
    mutants = sum(len(group) for group in recorded.values())
    return (
        f"`kill_points.json` records {len(kills):,} searches, {mutants:,} mutants each at both sizes; the"
        f" latest kill is at the {ordinal(latest)} example ({where})."
    )


def rendered(readme: str, recorded: KillPoints) -> tuple[str, list[str]]:
    """The README with its counts written from `recorded`, and what keeps it from holding them all."""
    lines = readme.split("\n")
    problems: list[str] = []
    found = tables(lines)
    for group in sorted(set(recorded) - NO_TABLE - {table.group for table in found}):
        problems.append(f"{group}: recorded, and the README holds no kill points comment above its table")
    for table in found:
        if table.group not in recorded:
            problems.append(f"{table.group}: a table of a group kill_points.json does not hold")
            continue
        mutants = recorded[table.group]
        named = [row.mutant for row in table.rows]
        for mutant in sorted({name for name in named if named.count(name) > 1}):
            problems.append(f"{table.group}: `{mutant}` has two rows")
        if table.every:
            for mutant in sorted(set(mutants) - set(named)):
                problems.append(f"{table.group}: `{mutant}` is recorded but has no row in its table")
        for row in table.rows:
            if row.mutant in mutants:
                parts = cells(lines[row.line])
                small, original = mutants[row.mutant]
                parts[-1] = f" {small:,}, {original:,} "
                lines[row.line] = "|" + "|".join(parts) + "|"
    starts = [number for number, line in enumerate(lines) if line == SUMMARY_START]
    ends = [number for number, line in enumerate(lines) if line == SUMMARY_END]
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        raise CountsError("the README holds no one summary between its two comment lines")
    lines[starts[0] + 1 : ends[0]] = [summary(recorded)]
    return "\n".join(lines), problems


def late(recorded: KillPoints, reseeded: bool = False) -> list[str]:
    """The margin guard: each kill after the `MARGIN`th example. Where the inputs changed, the kills are the
    old seed's: the advice is to record first."""
    advice = "if it is still late after recording again, plan its search" if reseeded else "plan its search"
    return [
        f"{group}: `{mutant}` dies at the {ordinal(kill)} example at the {size} size, after the"
        f' {ordinal(MARGIN)}: {advice} (tests/property/README.md, "Mutants")'
        for group, mutants in sorted(recorded.items())
        for mutant, pair in sorted(mutants.items())
        for size, kill in zip(SIZES, pair, strict=True)
        if kill > MARGIN
    ]


def differences(report: Report, recorded: KillPoints, readme: str, partial: bool = False) -> list[str]:
    """Where the reports' kills are not the recorded ones, for each group the reports hold; and, unless the
    reports are of part of the searches, each recorded group they lack."""
    kills = report.kills
    problems: list[str] = []
    for name in report.silent:
        problems.append(
            f"{name} passed without recording examples_to_kill: its kill is held to no recorded point and"
            f" to no margin"
        )
    if not partial:
        for group in sorted(set(recorded) - set(kills)):
            problems.append(
                f"{group}: recorded, but the run holds no search of it (a test function renamed or deleted,"
                f" or a module not run): --measure --record drops a group that is gone; --partial is for a"
                f" report of part of the searches"
            )
    for group in sorted(kills):
        held = recorded.get(group, {})
        for mutant in sorted(kills[group]):
            for size, kill in sorted(kills[group][mutant].items()):
                if mutant not in held:
                    problems.append(
                        f"{group}: `{mutant}` ran, killed at {kill:,} ({size}), and is not recorded"
                    )
                    break
                wanted = held[mutant][SIZES.index(size)]
                if kill != wanted:
                    problems.append(
                        f"{group}: `{mutant}` at the {size} size: killed at {kill:,}, recorded {wanted:,}"
                    )
            if mutant in held:
                for size in SIZES:
                    if size not in kills[group][mutant]:
                        problems.append(
                            f"{group}: `{mutant}` is recorded, but the reports hold no kill of it at"
                            f" the {size} size"
                        )
        for mutant in sorted(set(held) - set(kills[group])):
            problems.append(f"{group}: `{mutant}` is recorded, but the reports hold no kill of it")
    for table in tables(readme.split("\n")):
        if table.group in kills:
            for row in table.rows:
                if row.mutant not in kills[table.group]:
                    problems.append(
                        f"{table.group}: README line {row.line + 1} names `{row.mutant}`, which did not run"
                    )
    return problems


# --- the command -------------------------------------------------------------------------------------------


def measured(workers: int, directory: Path) -> Path | None:
    """Every mutant search, run into a JUnit report in `directory`; None where pytest failed."""
    report = directory / "kill_points.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/property",
        "--property-controls",
        "only",
        "-n",
        str(workers),
        "--dist",
        "worksteal",
        "-q",
        "--tb=short",
        f"--junitxml={report}",
    ]
    print("$ " + " ".join(command), flush=True)
    return report if subprocess.run(command, cwd=REPOSITORY, check=False).returncode == 0 else None


def failed(problems: Sequence[str], what: str) -> int:
    print(f"{what}:", file=sys.stderr)
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    return 1


def written(record: Record, check: bool) -> int:
    readme = README.read_text(encoding="utf-8")
    text, problems = rendered(readme, record.kills)
    if check:
        changed = stale(record.inputs, inputs_of_tree())
        problems = changed + problems + late(record.kills, reseeded=bool(changed))
        if dump(record) != KILL_POINTS.read_text(encoding="utf-8"):
            problems.append(f"{KILL_POINTS.name} is not in this script's layout: record it again (--record)")
        if text != readme:
            problems.append(f"{README.name}'s kill counts differ from {KILL_POINTS.name}: run this script")
    else:
        if text != readme:
            README.write_text(text, encoding="utf-8")
        if problems:
            problems.append("the README's other counts are written")
    return failed(problems, "the kill counts") if problems else 0


def recorded_with(report: Report, whole: bool) -> Record:
    """The file with each group the reports hold replaced by theirs, or, for a run of every search, holding
    those groups alone; written. Reports of part of the searches cannot be recorded where the inputs changed:
    the groups they lack would keep kills of the old seed."""
    if report.silent:
        raise CountsError(
            "searches passed without recording examples_to_kill, so their kills are not known: "
            + ", ".join(report.silent[:3])
            + (" ..." if len(report.silent) > 3 else "")
        )
    previous = load(KILL_POINTS.read_text(encoding="utf-8")) if KILL_POINTS.exists() else Record({}, {})
    tree = inputs_of_tree()
    held = recorded_from(report.kills)
    kills = dict(held) if whole else {**previous.kills, **held}
    if not whole and stale(previous.inputs, tree) and set(previous.kills) - set(held):
        raise CountsError(
            "the kill points' inputs changed, so every kill may have moved, and these reports lack"
            f" {len(set(previous.kills) - set(held))} recorded groups: record a run of every search"
            " (--measure --record)\n  " + "\n  ".join(stale(previous.inputs, tree))
        )
    for group in sorted(set(previous.kills) - set(kills)):
        print(f"dropped {group}: the run holds no search of it", file=sys.stderr)
    record = Record(tree, kills)
    KILL_POINTS.write_text(dump(record), encoding="utf-8")
    return record


def against(reports: Sequence[Path], partial: bool = False) -> int:
    record = load(KILL_POINTS.read_text(encoding="utf-8"))
    problems = stale(record.inputs, inputs_of_tree())
    installed = installed_hypothesis()
    if installed is not None and installed != record.inputs.get(HYPOTHESIS):
        problems.append(
            f"Hypothesis {installed} is installed, and the kill points were recorded with"
            f" {record.inputs.get(HYPOTHESIS)}: {RECORD_AGAIN}"
        )
    problems += differences(reported(reports), record.kills, README.read_text(encoding="utf-8"), partial)
    if problems:
        problems.append("record them: uv run python scripts/gen_kill_counts.py --measure --record")
        return failed(problems, "the kill points the run gives are not the recorded ones")
    return 0


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write and check the mutant searches' kill counts.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="write nothing; fail where a count differs or is late"
    )
    mode.add_argument("--record", nargs="*", metavar="REPORT", help="record the kill points of JUnit reports")
    mode.add_argument("--against", nargs="+", metavar="REPORT", help="fail where a report's kills differ")
    parser.add_argument(
        "--partial",
        action="store_true",
        help="with --against: the reports are of part of the searches; recorded groups they lack are fine",
    )
    parser.add_argument(
        "--measure", action="store_true", help="run every mutant search, then check or record"
    )
    parser.add_argument("--workers", type=int, default=12, help="pytest-xdist workers for --measure (12)")
    options = parser.parse_args(arguments)
    if options.measure and (options.check or options.against or options.record):
        parser.error("--measure records with a bare --record, and checks without it; it takes no report")
    if options.partial and not options.against:
        parser.error(
            "--partial goes with --against: only a hand-run report of part of the searches is partial"
        )
    if options.record == [] and not options.measure:
        parser.error("--record takes a report, or --measure to run one")
    try:
        if options.measure:
            with tempfile.TemporaryDirectory() as directory:
                report = measured(options.workers, Path(directory))
                if report is None:
                    print("a mutant search failed, so its kill is not known: fix it first", file=sys.stderr)
                    changed = stale(load(KILL_POINTS.read_text(encoding="utf-8")).inputs, inputs_of_tree())
                    if changed:
                        failed(
                            changed,
                            "the kill points were recorded with other inputs than the tree's, so a search"
                            " may have been re-seeded to an example that fails its own check",
                        )
                    return 1
                if options.record is not None:
                    return written(recorded_with(reported([report]), whole=True), check=False)
                return against([report])
        if options.against:
            return against([Path(path) for path in options.against], options.partial)
        if options.record:
            return written(
                recorded_with(reported(Path(path) for path in options.record), whole=False), check=False
            )
        return written(load(KILL_POINTS.read_text(encoding="utf-8")), check=options.check)
    except (CountsError, OSError) as error:
        print(f"gen_kill_counts: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

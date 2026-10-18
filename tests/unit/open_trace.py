# SPDX-License-Identifier: Apache-2.0
"""A pytest plugin that records which repository files each test file opens and which directories it lists.

`tests/unit/test_pre_review.py` runs the tests under it (`-p tests.unit.open_trace`, `OPEN_TRACE_OUT` the file
to write, `OPEN_TRACE_ROOT` the repository) and compares the record with what `scripts/pre_review.py` selects.
Each line is a JSON list: `["opened", test_file, path]` or `["listed", test_file, directory]`, paths relative
to the repository, once each. A file is attributed to the test file that was being imported or run when it was
opened; what pytest itself reads between two test files is attributed to none.

It keeps the first test of each test function: a parametrised test reads what its first case reads, and the
property modules are imported but not run (the trace is of what a test file reads, not of what a property
draws). It sees what the test process opens, not what a subprocess of it opens. Importing the module does
nothing; pytest's `pytest_configure` starts the trace.
"""

import json
import os
import sys
from pathlib import Path
from typing import ClassVar, cast

import pytest

IGNORED = (".venv", ".git", ".hypothesis", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")


class Trace:
    root: ClassVar[Path]
    out: ClassVar[Path]
    current: ClassVar[str | None] = None
    seen: ClassVar[set[tuple[str, str, str]]] = set()


def relative(path: object) -> str | None:
    if not isinstance(path, (str, bytes, os.PathLike)):
        return None
    try:
        text = os.fsdecode(cast("str | bytes | os.PathLike[str]", path))
        resolved = Path(os.path.realpath(Path.cwd() / text))
    except (OSError, ValueError):
        return None
    if resolved != Trace.root and Trace.root not in resolved.parents:
        return None
    parts = resolved.relative_to(Trace.root).parts
    return None if any(part in IGNORED for part in parts) else "/".join(parts)


def record(kind: str, path: object) -> None:
    test = Trace.current
    found = relative(path)
    if test is None or found is None or (kind, test, found) in Trace.seen:
        return
    Trace.seen.add((kind, test, found))
    with Trace.out.open("a", encoding="utf-8") as out:
        out.write(json.dumps([kind, test, found]) + "\n")


def by_the_import_system() -> bool:
    """Whether the import machinery itself is listing the directory to find a module, which reads no file of
    it. (A test module's own code runs under the import system too, so only the caller is looked at.)"""
    caller = sys._getframe(2)  # pyright: ignore[reportPrivateUsage]
    return caller.f_code.co_filename.startswith("<frozen importlib")


def hook(event: str, arguments: tuple[object, ...]) -> None:
    if event == "open":
        record("opened", arguments[0])
    elif event in {"os.listdir", "os.scandir"} and arguments and arguments[0] is not None:
        if not by_the_import_system():
            record("listed", arguments[0])


def pytest_configure() -> None:
    Trace.root = Path(os.environ["OPEN_TRACE_ROOT"]).resolve()
    Trace.out = Path(os.environ["OPEN_TRACE_OUT"])
    sys.addaudithook(hook)


def pytest_collectstart(collector: pytest.Collector) -> None:
    if isinstance(collector, pytest.Module):
        Trace.current = relative(collector.path)


def pytest_collectreport() -> None:
    Trace.current = None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    first: set[tuple[str, str]] = set()
    kept: list[pytest.Item] = []
    for item in items:
        function = (str(item.path), getattr(item, "originalname", item.name))
        if "tests/property/" in item.path.as_posix() or function in first:
            continue
        first.add(function)
        kept.append(item)
    items[:] = kept


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    Trace.current = relative(item.path)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    Trace.current = relative(item.path)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    Trace.current = relative(item.path)


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport() -> None:
    Trace.current = None

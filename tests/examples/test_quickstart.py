# SPDX-License-Identifier: Apache-2.0
"""The quickstart (`docs/user_guide/quickstart.md`) runs as a doctest: every `pycon` block, in order, in a
directory holding the example record it starts from, each line's output compared with the page's. Its control
changes an output the page shows, and the run must fail."""

import doctest
import re
import shutil
from pathlib import Path

import pytest

# The page's code imports these. Imported here too, so that a change to the package selects this test in the
# pre-review script, which follows imports: the doctest's own import opens no file, and the trace sees none.
from materica import content_hash as content_hash
from materica import load_records as load_records
from materica import read as read

REPOSITORY = Path(__file__).resolve().parents[2]
QUICKSTART = REPOSITORY / "docs" / "user_guide" / "quickstart.md"
WATER = REPOSITORY / "examples" / "records" / "water.json"
BLOCK = re.compile(r"^```pycon\n(.*?)^```$", re.MULTILINE | re.DOTALL)


def run(page: str, directory: Path) -> tuple[doctest.TestResults, int, str]:
    """The page's `pycon` blocks run as one doctest in `directory`: the results, the number of examples the
    blocks hold, and what the runner printed."""
    records = directory / "examples" / "records"
    records.mkdir(parents=True)
    shutil.copyfile(WATER, records / WATER.name)
    source = "\n".join(BLOCK.findall(page))
    test = doctest.DocTestParser().get_doctest(source, {}, QUICKSTART.name, str(QUICKSTART), 0)
    printed: list[str] = []
    results = doctest.DocTestRunner(verbose=False).run(test, out=printed.append)
    return results, len(test.examples), "".join(printed)


def problems(page: str, directory: Path) -> str:
    """What is wrong with a run of `page`, or an empty string: an example that failed, was skipped (counted
    as attempted from Python 3.13, not before, so both are looked at), or did not run, against the number
    the blocks hold, which is one per `>>>` line inside them."""
    results, examples, printed = run(page, directory)
    if results.failed:
        return printed
    if skipped := getattr(results, "skipped", 0):
        return f"{skipped} example(s) skipped"
    held = "".join(BLOCK.findall(page)).count(">>> ")
    if not results.attempted == examples == held:
        return f"attempted {results.attempted} of {examples} examples, and the blocks hold {held}"
    return "" if examples >= 10 else f"only {examples} examples"


def test_the_quickstart_runs_as_shown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert problems(QUICKSTART.read_text(encoding="utf-8"), tmp_path) == ""


def test_the_quickstart_check_fails_where_an_example_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skipped example has no output compared, and no later example needs it, so only the count of
    skipped (Python 3.13 and later) or of attempted (before) can see it."""
    monkeypatch.chdir(tmp_path)
    page = QUICKSTART.read_text(encoding="utf-8")
    line = """>>> density["value"], density["unit"], density["conditions"]["temperature"]"""
    assert page.count(line) == 1
    assert problems(page.replace(line, f"{line}  # doctest: +SKIP"), tmp_path)


@pytest.mark.parametrize(
    ("shown", "changed"),
    [
        ("('met', 993.33, 'kg/m3')", "('met', 993.34, 'kg/m3')"),
        ("('not_met', None)", "('unknown', None)"),
        ("[('condition_outside', 'temperature')]", "[('condition_unchecked', 'temperature')]"),
        (
            "'evaluated_from_formulation', 'iapws_r6_95_2018', 'not_checked'",
            "'measured_by_source', None, 'x'",
        ),
    ],
    ids=["met-value", "refusal-status", "refusal-reason", "provenance"],
)
def test_the_quickstart_fails_where_its_output_is_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shown: str, changed: str
) -> None:
    monkeypatch.chdir(tmp_path)
    page = QUICKSTART.read_text(encoding="utf-8")
    assert page.count(shown) == 1
    results, _, printed = run(page.replace(shown, changed), tmp_path)
    assert results.failed == 1, printed

# SPDX-License-Identifier: Apache-2.0
"""A derandomized run draws none of the constants Hypothesis harvests from the loaded modules, and every
other run still does (`tests/harvested_constants.py`).

The pin goes through Hypothesis's private names, so these tests are its canary. The behavioural one runs in a
fresh process, so that the module it loads stays out of this one's pool: it loads a module of 500 fresh
strings from outside `tests/`, which Hypothesis harvests once it is loaded, and compares what one search
draws before and after. Derandomized, under the pin, the draws are the same and hold none of those strings.
The controls: the same search with the pin off draws otherwise and draws some of those strings, so the
comparison can fail and Hypothesis still harvests; and a run at a fixed seed, not derandomized, draws
otherwise too, so the pin leaves the other runs their pool. Should Hypothesis rename those names, the pin
fails at import or here; should it stop harvesting, the first control fails, and the pin can go.

Two more fresh processes hold the rest. One loads the module first and then runs a search at a fixed seed
(not derandomized), a derandomized one, the first again, a derandomized one, the first a third time: each
run at the seed draws what the first did, the module's strings among them, so that a pin that empties the
cache on one switch only, and leaves a later run at random without the pool, fails (a switch to random is
the case the first test cannot tell, since loading the module there refills the pool). The other collects
what CI's Hypothesis shards collect, `tests/property` alone, and what a developer's unit run collects,
`tests/unit` alone, and requires the pin installed after each collection: it lives in `tests/conftest.py`,
which every invocation loads, and a pin moved to a conftest of one directory leaves the other's runs unpinned.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import Phase, given, settings
from hypothesis import strategies as st
from hypothesis.internal.conjecture import providers

from tests import harvested_constants
from tests.property.support import MUTANT_SEARCH

REPOSITORY = Path(__file__).resolve().parents[2]

# Each string at most 20 characters, as Hypothesis harvests, and fewer than its 1,024 constants a module.
FRESH = [f"fresh{index:03d}" for index in range(500)]

# Ten strings an example, 300 examples: the module's strings are most of the pool once it is loaded, and a
# string draw takes one from the pool about once in forty, so the unpinned search draws dozens of them.
SETUP = """
import json

from hypothesis import Phase, given, seed, settings, strategies

import materica
from tests import harvested_constants

harvested_constants.pin()


def drawn(derandomize):
    found = []

    @seed(20261018)
    @settings(
        derandomize=derandomize, database=None, max_examples=300, phases=[Phase.generate], deadline=None
    )
    @given(strategies.lists(strategies.text(), min_size=10, max_size=10))
    def search(strings):
        found.append(strings)

    search()
    return found
"""

DRAWING = (
    SETUP
    + """

def runs():
    pinned, seeded = drawn(True), drawn(False)
    derandomized = harvested_constants.derandomized
    harvested_constants.derandomized = lambda: False
    unpinned = drawn(True)
    harvested_constants.derandomized = derandomized
    return {"pinned": pinned, "seeded": seeded, "unpinned": unpinned}


before = runs()
import fresh_strings
print(json.dumps({"before": before, "after": runs()}))
"""
)

# The module is loaded first, then the searches alternate: at a fixed seed, derandomized, at a fixed seed...
ALTERNATING = (
    SETUP
    + """
import fresh_strings

order = [False, True, False, True, False]
print(json.dumps([drawn(derandomize) for derandomize in order]))
"""
)

# Collects what a run collects and says whether the pin is installed once it has.
COLLECTING = """
import sys

import pytest


class Probe:
    def pytest_collection_finish(self, session):
        # Imported here: Hypothesis is a pytest plugin, and loaded before pytest starts it is not rewritten.
        from hypothesis.internal.conjecture import providers
        from tests import harvested_constants

        print("PINNED", providers._get_local_constants is harvested_constants.constants_in_use)


sys.exit(pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", sys.argv[1]], plugins=[Probe()]))
"""


def test_the_pin_is_in_place_and_the_mutant_searches_are_derandomized() -> None:
    installed = providers._get_local_constants  # pyright: ignore[reportPrivateUsage]
    assert installed is harvested_constants.constants_in_use
    assert harvested_constants.HARVESTED.__module__ == providers.__name__
    assert harvested_constants.HARVESTED.__name__ == "_get_local_constants"
    assert MUTANT_SEARCH.derandomize is True  # pyright: ignore[reportUnknownMemberType]


def pool_seen(derandomize: bool) -> int:
    """The size of the pool a run sees, derandomized or not."""
    seen: list[int] = []

    @settings(derandomize=derandomize, database=None, max_examples=1, phases=[Phase.generate], deadline=None)
    @given(st.none())
    def run(_: None) -> None:
        seen.append(len(providers._get_local_constants()))  # pyright: ignore[reportPrivateUsage]

    run()
    return seen[0]


def test_a_derandomized_run_sees_no_harvested_constant_and_any_other_run_sees_them() -> None:
    # The package's modules are loaded here, so the harvested pool is not empty.
    assert pool_seen(derandomize=True) == 0
    assert pool_seen(derandomize=False) > 0
    assert pool_seen(derandomize=True) == 0


def in_fresh_process(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """`python -c` with these arguments, run in `directory` with this repository importable and none of the
    runner's Hypothesis settings."""
    environment = {
        name: value for name, value in os.environ.items() if not name.startswith(("HYPOTHESIS_", "PYTEST_"))
    }
    return subprocess.run(
        [sys.executable, "-c", *arguments],
        cwd=directory,
        env={**environment, "PYTHONPATH": str(REPOSITORY)},
        capture_output=True,
        text=True,
        check=False,
    )


def strings(run: list[list[str]]) -> set[str]:
    return {string for example in run for string in example}


def test_a_module_loaded_changes_no_derandomized_draw_and_every_other_draw(tmp_path: Path) -> None:
    (tmp_path / "fresh_strings.py").write_text(f"STRINGS = {FRESH!r}\n", encoding="utf-8")
    ran = in_fresh_process(tmp_path, DRAWING)
    assert ran.returncode == 0, ran.stderr
    drawn = json.loads(ran.stdout)
    before, after = drawn["before"], drawn["after"]

    assert after["pinned"] == before["pinned"]
    assert not strings(after["pinned"]) & set(FRESH)
    # The controls.
    assert after["unpinned"] != before["unpinned"]
    assert strings(after["unpinned"]) & set(FRESH)
    assert after["seeded"] != before["seeded"]


def test_a_run_at_random_after_a_derandomized_one_draws_the_pool_as_before(tmp_path: Path) -> None:
    (tmp_path / "fresh_strings.py").write_text(f"STRINGS = {FRESH!r}\n", encoding="utf-8")
    ran = in_fresh_process(tmp_path, ALTERNATING)
    assert ran.returncode == 0, ran.stderr
    first, pinned, second, pinned_again, third = json.loads(ran.stdout)

    # The module is loaded before the first run, so the pool is the same in all three runs at the seed, and
    # the cache a run reads is the one the last switch left: a switch back to random that leaves the cache
    # of the derandomized run makes the second and third run draw otherwise, and no string of the module.
    assert strings(first) & set(FRESH)
    assert second == first
    assert third == first
    # The control: the derandomized runs draw one thing, and none of the module.
    assert pinned_again == pinned
    assert not strings(pinned) & set(FRESH)
    assert pinned != first


@pytest.mark.parametrize("directory", ["tests/property", "tests/unit"])
def test_the_pin_is_installed_in_a_run_that_collects_only_one_directory(directory: str) -> None:
    ran = in_fresh_process(REPOSITORY, COLLECTING, directory)
    assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
    # The control: the collection is of tests, not of nothing.
    assert re.search(r"\d+ tests collected", ran.stdout), ran.stdout[-500:]
    assert "PINNED True" in ran.stdout.splitlines(), ran.stdout[-500:]

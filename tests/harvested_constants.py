# SPDX-License-Identifier: Apache-2.0
"""A derandomized run draws none of the constants Hypothesis harvests from the loaded modules.

Hypothesis (since 6.131.1; 6.169 here) reads the literal constants of every module in `sys.modules` whose file
is local and not a test file (`hypothesis/internal/constants_ast.py`), and in about one integer, string or
bytes draw in twenty (one float draw in seven) takes a constant instead, from its own list or that pool alike
(`HypothesisProvider._maybe_draw_constant`). `derandomize=True` fixes the seed, not that pool. So a
derandomized search drew other examples whenever the process had loaded one more module with a string in it,
or a loaded module's strings changed. The review of #43 found it: a module holding the one string `X = "zzz"`
changed a mutant search's draws; across 12 pools, the hashing mutant `a_non_object_provenance_opens` died
after 74 to 913 examples; and with #43's `scripts/check_anomalies.py` collected (its unit tests import it, 77
strings), it survived all 2,000. Any change that added or edited a string in `src/` or `scripts/` could move
any kill, or let a mutant survive.

Hypothesis has no setting or environment variable that turns the pool off (its 6.169 changelog and
documentation), and an alternative backend (`settings.backend`, experimental) also leaves out the engine's
tree of choices and its mutations, which would change the searches themselves. So the pool is pinned, empty,
through private names, for every run whose settings are derandomized: `providers._get_local_constants`,
which each test case's provider calls once, before its first constant, is replaced; and
`providers.CONSTANTS_CACHE`, which keeps the constants each kind of draw may take, is emptied whenever the
pool in use changes. During a run, Hypothesis's engine makes the test's settings the current ones
(`settings.default`); that is how a derandomized run is told. `tests/unit/test_harvested_constants.py` fails
if these names go or the pin stops having effect.

Every other run keeps the pool: a property drawn at random meets, now and then, one of the package's own
strings or numbers (a field name, a token, a limit), which a strategy aimed elsewhere would seldom draw. Its
draws were never the same from one run to the next.

Two interleavings escape the pin. No test in this repository does either, so nothing guards them (the review
of this pin measured both with a module of 600 harvestable strings, on Hypothesis 6.169):

- A search run inside the body of another that draws with `st.data()`, derandomized in one and random in the
  other. Hypothesis reads the pool once a test case, but `CONSTANTS_CACHE` is shared by both and keyed
  without the pool, so the inner run's switch leaves the outer's later draws with the wrong one. With the
  same strategy in both, 6,000 outer draws after the inner run: a derandomized outer around a random inner
  drew 81 of the module's strings (0 before the inner run), and a random outer around a derandomized inner
  drew 0 (106 before). The two random runs, and the two derandomized, were unchanged (100 against 114; 0
  against 0).
- A derandomized test that calls `settings.load_profile` in its body. `settings.default` is what the pin
  reads, so it follows the profile, and the draws after the call came from a random one: 14 of 2,400 were
  the module's strings.

A test of either kind has to be written with that in view, or the pin extended to key on the test case.
"""

from hypothesis import settings
from hypothesis.internal.conjecture import providers
from hypothesis.internal.constants_ast import Constants

HARVESTED = providers._get_local_constants  # pyright: ignore[reportPrivateUsage]
NONE_HARVESTED = Constants()


def derandomized() -> bool:
    """Whether the run drawing now is derandomized."""
    current = settings.default
    # Hypothesis leaves its settings' properties unannotated.
    return current is not None and current.derandomize is True  # pyright: ignore[reportUnknownMemberType]


class Cached:
    """Which pool filled `providers.CONSTANTS_CACHE`, if any yet: the pinned one, or the harvested one."""

    pinned: bool | None = None


def constants_in_use() -> Constants:
    """The constants the run drawing now may draw beside Hypothesis's own: none where it is derandomized, and
    those harvested otherwise."""
    pinned = derandomized()
    if pinned != Cached.pinned:
        providers.CONSTANTS_CACHE.cache.clear()
        Cached.pinned = pinned
    return NONE_HARVESTED if pinned else HARVESTED()


def pin() -> None:
    providers._get_local_constants = constants_in_use  # pyright: ignore[reportPrivateUsage]

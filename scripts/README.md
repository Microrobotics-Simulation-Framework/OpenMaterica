# Scripts

Development and CI tools. They use Python's standard library only, so the sign-off check runs before any
dependency is installed, and nothing in the package imports them.

| Script | What it checks | When CI runs it |
|---|---|---|
| `check_signoff.py <base> <head>` | every commit in `base..head` carries a DCO `Signed-off-by` from its author (CONTRIBUTING constraint 1); the design commits made before the first code commit are exempt, by ancestry of one pinned commit | on every pull request, in the first job, whatever the change touches |
| `check_wheel.py <wheel>` | the built wheel holds `py.typed`, every conformance file byte for byte and no other, the licence as an SPDX expression with its file (PEP 639), no run-time dependency, and nothing outside the package | in the static job, after `uv build`, when a change touches code |

Each has tests in `tests/unit/` that show it failing on what it must refuse.

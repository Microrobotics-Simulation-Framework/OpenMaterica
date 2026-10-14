# Fuzzing

Two Atheris targets, which run coverage-guided fuzzing against the core. They live under `tests/` because they
are tests of the core, outside the package and its layers: they reuse the property tests' strategies, profiles
and example database, and are typed, linted and SPDX-checked with the other tests. pytest does not collect
them. Atheris ships no types, so `typings/atheris/` holds stubs for the part of it the targets use.

| Target | Drives | Fails when |
|---|---|---|
| `jsonio_bytes.py` | raw bytes into `jsonio.parse`, from a seed corpus of every conformance input and with `json.dict`, JSON's tokens and the escapes and bytes `record_format.md` section 1 item 6 turns on | `parse` raises; or it disagrees with a reference reader built from the standard library's json, with hooks that refuse exactly the faults the item lists: a value it accepts differs, numbers bit for bit, or it refuses what the reference accepts, or the reverse |
| `properties.py` | the Hypothesis properties of `tests/property/`, through `fuzz_one_input`, in-process; the first byte picks the property | a property fails. The failure goes into the example database, and `pytest tests/property`, under the same `MATERICA_HYPOTHESIS_PROFILE`, replays it first and shrinks it |

## Running

Atheris 3.1.0 installs on Linux x86_64 with Python 3.12 to 3.14 only; elsewhere the `fuzz` group installs
nothing.

```sh
uv sync --group fuzz
uv run python -m tests.fuzz.jsonio_bytes --seed corpus
uv run python -m tests.fuzz.jsonio_bytes corpus -dict=tests/fuzz/json.dict -max_len=4096 -max_total_time=300
MATERICA_HYPOTHESIS_PROFILE=ci uv run python -m tests.fuzz.properties -max_total_time=300
MATERICA_HYPOTHESIS_PROFILE=ci uv run pytest tests/property     # replays and shrinks what was found
mkdir smaller && uv run python -m tests.fuzz.jsonio_bytes -merge=1 smaller corpus   # what adds coverage
```

Run them from the repository root. libFuzzer writes new inputs into the corpus directory it is given, so it is
a copy, never `src/materica/data/conformance/`. To merge a corpus or minimise a crash, libFuzzer re-executes
its first argument; `jsonio_bytes.py` passes it `jsonio_bytes.sh`, which runs the module again with the same
interpreter. A replayed failure keeps the whitespace it was written with: the properties choose how a value
is written with a seeded `random.Random`, which shrinking cannot simplify, so only the value shrinks.

## Showing that it can fail

`seeded_fault.py` makes `parse` raise for an array whose first item is an empty object, a shape no seed
holds. With `MATERICA_FUZZ_SEEDED_FAULT=1`, both targets must find it, and
`python -m pytest -p tests.fuzz.seeded_fault tests/property/...` must replay what `properties.py` saved and
shrink it. CI's fuzz job does this first, against an empty example database, before it fuzzes the core.

## In CI

The `fuzz` job runs weekly and on a manual run only, on Python 3.14, after the Hypothesis job: the control
above, then each target for `fuzz_seconds` (300 by default, an input of the manual run), then
`pytest tests/property` to replay and shrink what was found. It starts from the example database the
Hypothesis job just saved, or the latest saved where that job did not run (a manual run with `fuzz_only`), and
saves the two jobs' finds together. Target 1's corpus is cached from run to run, seeded afresh each time, and
merged into a fresh directory before it is saved, so that it keeps only the inputs that add coverage. The job
keeps the inputs that failed.

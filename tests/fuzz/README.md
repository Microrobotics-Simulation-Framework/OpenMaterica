# Fuzzing

Four Atheris targets, which run coverage-guided fuzzing against the core. They live under `tests/` because
they are tests of the core, outside the package and its layers: they reuse the property tests' strategies,
profiles and example database, and are typed, linted and SPDX-checked with the other tests. pytest does not
collect them. Atheris ships no types, so `typings/atheris/` holds stubs for the part of it the targets use.

| Target | Drives | Fails when |
|---|---|---|
| `jsonio_bytes.py` | raw bytes into `jsonio.parse`, from a seed corpus of every conformance input and with `json.dict`, JSON's tokens and the escapes and bytes `record_format.md` section 1 item 6 turns on | `parse` raises; or it disagrees with the reference reader (`tests/conformance/reference_reader.py`), the standard library's json with hooks that refuse exactly the faults the item lists: a value it accepts differs, numbers bit for bit, or it refuses what the reference accepts, or the reverse |
| `properties.py` | the JSON properties of `tests/property/` (the reader, RFC 8785, the hash), through `fuzz_one_input`, in-process; the first byte picks the property | a property fails. The failure goes into the example database, and `pytest tests/property`, under the same `MATERICA_HYPOTHESIS_PROFILE`, replays it first and shrinks it |
| `record_properties.py` | the record properties of `tests/property/` (the envelope checks, versions, the read's laws, step 8's laws) in the same way: structure-aware, since their strategies build records, stores and requests from the bytes Atheris gives | as above |
| `read_field_bytes.py` | raw bytes into step 8 of a read: the first byte picks a registered field, and the rest, read by `jsonio.parse`, stands in that field's place in a record valid otherwise, pinned by its recomputed hash; seeded with every value field of every conformance input, with a dictionary of S2's member names and tokens that `--dict` writes from the schema and the vocabulary | a read raises anything but `NotImplementedError`; two reads differ; a result is not a refusal step 8 gives (`not_met`, codes of step 8 only, each once, the worst status); or the read without the hash suite differs by more than the label `hash_not_checked` |

## Running

Atheris 3.1.0 installs on Linux x86_64 with Python 3.12 to 3.14 only; elsewhere the `fuzz` group installs
nothing.

```sh
uv sync --group fuzz
uv run python -m tests.fuzz.jsonio_bytes --seed corpus
uv run python -m tests.fuzz.jsonio_bytes corpus -dict=tests/fuzz/json.dict -max_len=4096 -max_total_time=300
MATERICA_HYPOTHESIS_PROFILE=ci uv run python -m tests.fuzz.properties -max_total_time=300
MATERICA_HYPOTHESIS_PROFILE=ci uv run python -m tests.fuzz.record_properties -max_total_time=300
uv run python -m tests.fuzz.read_field_bytes --seed fields && uv run python -m tests.fuzz.read_field_bytes --dict value_field.dict
uv run python -m tests.fuzz.read_field_bytes fields -dict=value_field.dict -max_total_time=300
MATERICA_HYPOTHESIS_PROFILE=ci uv run pytest tests/property     # replays and shrinks what was found
mkdir smaller && uv run python -m tests.fuzz.jsonio_bytes -merge=1 smaller corpus   # what adds coverage
```

Run them from the repository root. libFuzzer writes new inputs into the corpus directory it is given, so it is
a copy, never `src/materica/data/conformance/`. To merge a corpus or minimise a crash, libFuzzer re-executes
its first argument; `jsonio_bytes.py` passes it `jsonio_bytes.sh`, which runs the module again with the same
interpreter. A replayed failure keeps the whitespace it was written with: the properties choose how a value
is written with a seeded `random.Random`, which shrinking cannot simplify, so only the value shrinks.

## Showing that it can fail

`seeded_fault.py` seeds three faults, each with its own message. One makes `parse` raise for an array whose
first item is an empty object, a shape no seed holds; another makes the read raise where two copies of the
target state its pin and are identical byte for byte, which a read must take as one record, beside an
unreadable source and without the hash suite: three draws that must meet. The third makes step 8 raise for a
statistics block that represents a spread across sources over a number of sources above 2.5 and not whole:
two seeds hold the first, one of them a count that is not whole but 2.5, so a mutation has to meet all three.
Only the fourth target seeds it, since the property targets draw fields too, and it is instrumented by Atheris,
as the core is, so that its comparisons guide the search. In four local runs of 180 s it was found after 10 to
94 s (Python 3.14, 2026-10-15). With `MATERICA_FUZZ_SEEDED_FAULT=1`, the first two targets must find the first,
the third target the second and the fourth the third, and
`python -m pytest -p tests.fuzz.seeded_fault tests/property/...` must replay what the property targets saved
and shrink it. CI's fuzz job does this first, against an empty example database, before it fuzzes the core,
and checks each step for the message of the fault it must find.

## In CI

The `fuzz` job runs weekly and on a manual run only, on Python 3.14, after the Hypothesis job: the control
above, then each target for `fuzz_seconds` (300 by default, an input of the manual run), then
`pytest tests/property` to replay and shrink what was found. It starts from the union of the example databases
the Hypothesis job's `json` and `records` shards just saved, or the latest each saved where that job did not run (a manual run
with `fuzz_only`), and saves the two jobs' finds together, for each shard. Target 1's corpus is cached from run
to run, seeded afresh each time, and merged into a fresh directory before it is saved, so that it keeps only
the inputs that add coverage. The job keeps the inputs that failed.

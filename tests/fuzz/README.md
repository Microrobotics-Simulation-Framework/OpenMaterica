# Fuzzing

Four Atheris targets, which run coverage-guided fuzzing against the core. They live under `tests/` because
they are tests of the core, outside the package and its layers: they reuse the property tests' strategies,
profiles and example database, and are typed, linted and SPDX-checked with the other tests. pytest does not
collect them. Atheris ships no types, so `typings/atheris/` holds stubs for the part of it the targets use.

| Target | Drives | Fails when |
|---|---|---|
| `jsonio_bytes.py` | raw bytes into `jsonio.parse`, from a seed corpus of every conformance input and with `json.dict`, JSON's tokens and the escapes and bytes `record_format.md` section 1 item 6 turns on | `parse` raises; or it disagrees with the reference reader (`tests/conformance/reference_reader.py`), the standard library's json with hooks that refuse exactly the faults the item lists: a value it accepts differs, numbers bit for bit, or it refuses what the reference accepts, or the reverse |
| `properties.py` | the JSON properties of `tests/property/` (the reader, RFC 8785, the hash), through `fuzz_one_input`, in-process; the first byte picks the property | a property fails. The failure goes into the example database, and `pytest tests/property`, under the same `MATERICA_HYPOTHESIS_PROFILE`, replays it first and shrinks it |
| `record_properties.py` | the record properties of `tests/property/` (the envelope checks, versions, the read's laws, step 8's over a constant, an interval and a composition, steps 9 and 10's, and the S2 design's HP1, HP2, HP4, HP6, HP10, HP11 and HP12, the agreement with the reference model) in the same way: structure-aware, since their strategies build records, stores and requests from the bytes Atheris gives | as above |
| `read_field_bytes.py` | raw bytes into steps 7 to 13 of a read: the first byte picks a registered field, and the rest, read by `jsonio.parse`, stands in that field's place in a record valid otherwise, pinned by its recomputed hash, read at operating conditions with a tolerance or an accept list for each condition its row requires; seeded with every value field of every conformance input, with a dictionary of the member names and tokens a value field holds, a table's reserved `points` among them, that `--dict` writes from the schema and the vocabulary | a read raises anything but `NotImplementedError`; two reads differ; a result breaks HP1 or HP2 (a code of the table, of steps 7 to 13 only, each with its condition once and `condition` where section 2 item 2 puts it, the worst status, the members item 6 gives); the read without the hash suite differs by more than the label `hash_not_checked`; the read under the `want` that gives the field's form (`value`, or `bounds` for an interval, `components` for a composition and `evidence` for evidence) and the reference model (`tests/reference/read_model.py`) disagree but as HP12 lists (`field_oracle.check_against_the_model`), which sees a refusal step 8 misses or gives wrongly, a condition holding a member of the other kind's shape among them (HP12's open point `members_of_the_other_kind`, which the target knew by its shape until the maintainer ruled it fail closed, 2026-10-19); step 8 lets through a constant, a table, an interval, a composition or evidence its row allows that the reader `$defs` refuse (`field_oracle.py`, T1's third relation); or steps 9 and 10 read such a field otherwise than their text: its units by code point, a table's `axis_unit` among them, and its conditions by HP7's oracle (`tests/property/condition_oracle.py`), a table that step 9 passes giving "not yet". `NotImplementedError` is "not yet": a table that steps 8 and 9 pass, whose steps 10 to 13 are S3b-2's, alone or as an alternative; a field holding alternatives is read by S4a's step 7, which the model decides too |

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
unreadable source and without the hash suite: three draws that must meet. The third makes step 10 raise for a
temperature above 311 K stated with a plus or minus, beside a shear rate stated as a range other than 10 to
1000 1/s: no seed holds two of the three (18 hold a plus or minus on a temperature, at 310.15 K or below;
three state another range, with no plus or minus; none a temperature above 311 K), so the fuzzer has to change
two numbers of one seed, keeping the field through steps 8 and 9. Only the fourth target seeds it, since the
property targets draw conditions too, and it is instrumented by Atheris, as the core is, so that each part met
is new coverage. In ten local runs, six at a time, it was found after 84, 126, 147, 189, 216, 225, 236, 483,
531 and 601 s (Python 3.14, 2026-10-16), so the control runs the target twice side by side, each for up to 900
s, and passes where either finds it. The target's runs, the control's and the weekly one, pass
`-entropic_scale_per_exec_time=1`, which runs slow inputs less often and keeps every seed: one seed of 261 KB
costs about 52 times the others' mean an input, and without the flag the corpus fills with its derivatives
and a run slows as it goes (S2a-4's review B, M2). Four runs of 1,800 s each way, two at a time
(2026-10-17): with the flag 528 inputs a second, the fault found in two runs; without it 237, found in none. Rarer conjunctions tried first were missed: a temperature stated as a
range, with an `sd` entry, measured rather than set, in 600 s; one ending above 1000 1/s, in two runs of 600
s, since libFuzzer picks the number it changes after a random offset and an upper end two bytes after its
lower is seldom picked; one starting above 10 1/s, in one run of seven. The fault replaced, in S2a-3, the
step-8 fault of S2a-2's fix round (a constant above 1, measured above 311 K, whose statistics block represents
a population's spread, found after 22 to 279 s), once the target read steps 9 and 10; that one had replaced a
fault one digit from a seed that held two of its three parts. A refusal steps 8 to 10 miss is the oracles' to
see, which `tests/unit/test_fuzz_oracle.py` shows failing. With `MATERICA_FUZZ_SEEDED_FAULT=1`, the first two
targets must find the first, the third target the second and the fourth the third, and `python -m pytest -p
tests.fuzz.seeded_fault tests/property/...` must replay what the property targets saved and shrink it: the
read's properties, and HP12's and HP10's, which draw the stores the fault in the read lives in. With every HP
in the third target, it still found that fault after 6 to 15 s in eight local runs (Python 3.14, 2026-10-17),
each time by the read's own properties. CI's fuzz job does this first, against an empty example database,
before it fuzzes the core, and checks each step for the message of the fault it must find.

The S2 design's own control (its section 1.7) is a fourth fault, which S2b-1 put in real composition code: an
exception escapes for a composition whose `components` is empty, which step 8 must refuse.
`MATERICA_FUZZ_SEEDED_FAULT=composition` seeds it alone, in the third and the fourth target. The fourth finds
it at once, from PR-051's `no_component` among its seeds (1.7 s, Python 3.14, 2026-10-17; 1.5 s at S2b-2's
head, which reads evidence too, 2026-10-18). The third did not
find it, run as CI runs its control (180 s), nor in 600 s, nor in 600 s with inputs of up to 8,192 bytes from
the start (`-max_len=8192 -len_control=0`), nor in 600 s with the property strategies instrumented too, so
that each fault drawn is coverage, with inputs short or long. Random bytes given to HP3's third part alone
draw the fault in 17 of 3,000 inputs. The target's inputs are not random bytes: by default they grow from a
few bytes, where a record HP3 draws takes hundreds, a property among 35 takes their first byte, and each is a
mutation of one the fuzzer kept for new coverage. So CI's control keeps the three faults above, and the
composition's waits for a ruling on how target 3 should reach whole records (S2b-1's report).

S4a's control is a fault of another kind: one the read answers wrongly rather than raises at, so that only
the oracle can find it, here the reference model, which since S4a decides step 7 over alternatives with no
pick and no overlay as the read does. `MATERICA_FUZZ_SEEDED_FAULT=alternatives` seeds it alone, in the fourth
target: an alternative refused at step 9 for its unit alone is set aside where it is the third or a later
stored alternative (`seeded_fault.faulty_standing`). Of the 56 seed fields that hold alternatives, two hold
three or more, and none a unit other than the registered one past the second, so the fuzzer has to change
one; the target then fails at the model's assertion, "the implementation gives ..., the model ...".
`tests/unit/test_fuzz_oracle.py` shows the oracle failing on that shape. In two local runs side by side, as
CI's control runs the target, it was found after 6 and 80 s, each by one change to the third unit of the seed
that holds three density alternatives (`kg/m3` made `+g/m3` and `kg/m2`), each at the model's assertion
(Python 3.14, 2026-10-19). It is not in CI's control step: the control's runs and their length are the
maintainer's to set.

S3a's control is of S4a's kind, in step 8: a table over temperature whose first knot lies below 250 is refused
(`form_invalid`) where the text and the model read it through step 9 (`seeded_fault.faulty_points`).
`MATERICA_FUZZ_SEEDED_FAULT=tables` seeds it alone, in the fourth target. Of the seed fields that hold a
table over temperature (106 of 816 at S3a's head, read as JSON, 2026-10-20), none starts below 250 (the least
first knot is 250, and one table's `x` is empty, which item 1 refuses already), so the fuzzer has to lower
one's first knot, in a table no other fault makes `form_invalid`; the target then fails at the model's
assertion. In two local runs side by
side, as CI's control runs the target, it was found after 26 and 319 s, each by one change to a first knot of
280: a `-` inserted, in a table holding `points`, and the number halved, in a table stored as an alternative
(Python 3.14, 2026-10-20). Two faults tried first were missed by two such runs of 600 s, about 1.2 million
inputs each: a log-log table holding a `source_range`, which no seed holds, since `linear` has to be
overwritten whole or a `source_range` written in; and a `source_range` reaching above 400, which 15 seed
tables are one change from, its upper end two bytes after its lower, as above. It is not in CI's control step
either.

## In CI

The `fuzz` job runs weekly and on a manual run only, on Python 3.14, after the Hypothesis job: the control
above, then each target for `fuzz_seconds` (300 by default, an input of the manual run), then `pytest
tests/property`, but the writer's properties and the mutant tables, to replay and shrink what was found. It
starts from the union of the example databases the Hypothesis job's `json`, `records`, `conditions` and
`relations` shards just saved, or the latest each saved where that job did not run (a manual run with
`fuzz_only`), and saves the two jobs' finds together, for each shard. Target 1's corpus is cached from run to
run, seeded afresh each time, and merged into a fresh directory before it is saved, so that it keeps only the
inputs that add coverage. The job keeps the inputs that failed.

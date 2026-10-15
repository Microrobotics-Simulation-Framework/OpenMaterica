# Property tests

Hypothesis properties of the core, in two groups, and of the writer schema, in a third.

- **JSON:** the JSON reader (`docs/specification/record_format.md` section 1 item 6), RFC 8785 (section 9 item
  2) and the content hash (section 9). `strategies.py` builds what they draw: JSON values, texts that write a
  value in many valid ways, and texts holding exactly one fault the specification lists. Trees are drawn
  top-down within a leaf budget, so no draw is thrown away.
- **Records:** (4) the envelope checks agree with the generated reader schema (section 1 item 2); (5) versions
  order as their integers, for components hundreds of digits long, and a text is a version exactly when it
  matches section 8's pattern; (6) the laws of a read up to step 5 (`read_side_contract.md` sections 1 to 3):
  it never raises but where a step not built yet would decide it, or for claims without plain read, a misuse;
  a reason appears once per code and condition; the order of the sources, identical copies of them, and records
  of another identity (another id, or another version of the target's) change nothing; an unreadable source
  turns only `absent` or `pin_mismatch` into `malformed`; a request member the shape does not name changes
  nothing; and every listed record, read under its own hash, passes steps 1 to 3 and 5. `records.py` builds
  records and versions, `stores.py` stores and requests.

  The first law is checked against the specification only where the read refuses. Where the implementation's
  own `resolve_record` resolves the target, a `NotImplementedError` is allowed, so a resolution that wrongly
  succeeds is invisible to it; the case files and the other laws are the oracle there.

- **Writer schema:** (7) the writer schema (`record_format.md` section 1 item 2) takes every value field the
  specification allows, and refuses each field it forbids by one fault. `value_fields.py` builds the fields
  from the text alone, never from the schema: tokens from the vocabulary (generated from the specification),
  a specimen fact's members from `provenance.md` section 6.2's JSON shapes, and the rest from the member
  tables and rules each builder cites. A fault is one change the text says breaks a field (a member missing,
  a bound crossed, a token of another member's list or of none, a status token its row does not allow, a rule
  across objects broken), 153 of them in eight families, each drawn as often as another of its family on a
  field planned so that its place exists. The refusal is checked on a field the schema takes, the same field
  but for the fault, so that it is the fault's.

The record strategies draw each case the specification tells apart as often as another. An example of (4) is
a sweep: one record changed at each aspect the reader schema checks (removed, of another JSON type, or `null`),
one near miss in each pattern, one other record type, one place left unchecked, and one record changed at
random. Drawn one change at a time, the rarer boundaries came up in under 1% of examples, and a mutant's
search took up to 1,900 examples to meet them. An example of (6) is a store built for one of the cases step 1
tells apart (no copy of the target; one, or two identical or differing, that state the pin; none that does,
beside an ill-formed hash or not), with sources of other identities, unreadable ones and documents beside it,
and claims with plain read or, in one world in four, without it.

## Profiles and sizes

`tests/conftest.py` sets how many examples each property draws, from `MATERICA_HYPOTHESIS_PROFILE`, and
`strategies.SIZE` how large its trees are, from the same profile:

| Profile | Examples per property | Trees | Where it runs |
|---|---|---|---|
| `dev` | 200 | small: 10 scalars, 3 members, depth 5 | the default: locally, and on every Python in CI's test matrix |
| `ci` | 2,000 | small | CI's Hypothesis job, when the core, its schemas and vocabulary, these tests or their configuration change, and on every code change to main |
| `deep` | 20,000 | original: 30 scalars, 5 members, depth 6 | the same job, weekly and on a manual run |

The original size is the one the properties were first written with, or larger. Content is never narrowed:
text is full Unicode half the time and built from the characters the specification treats apart the other
half, and numbers cover every double. Shapes that small trees cannot reach are explicit examples, run under
every profile: nesting 64, 65 and 100,000 deep, objects and records with many members, and a record with every
section and null in each place the envelope checks leave alone. A record with a change planned in a sweep
varies in its structure, its unchecked places holding a few values of each JSON type; the record changed at
random, and every change into a place left unchecked, draw full trees.

Every profile keeps its examples in `.hypothesis/examples` at the repository root (git-ignored, cached by CI),
so an example that failed once, under `deep` or any other profile, is tried first on every later run; a
failure prints a blob that replays it anywhere.

## Shards

CI runs the three groups side by side, each in a job of its own: `pytest tests/property --shard json`,
`--shard records` and `--shard writer` (`SHARDS` in `tests/conftest.py`). The writer schema's properties
validate each field with `jsonschema` against the writer's value field, a choice among eight forms, which
costs about 30 ms a field: so each family of faults is a property of its own, run in parallel. Each module is
in exactly one shard (`tests/unit/test_source_files.py`), and each shard keeps its own example database in CI.

## Mutants

`test_mutants.py` (JSON) and `test_record_mutants.py` (records) give the core one fault at a time and require
the property aimed at it to find the fault within the examples of the `ci` profile, at the small size and at
the original one. The faults include those the conformance runner's self-tests use, and faults that only some
sizes or contents could show: a nesting limit off by one, removal that stops at depth 2, sorting by one pass of
exchanges, a pattern searched where it must match in full, versions ordered as strings or as doubles, an
unreadable source ignored, the first of two differing copies read. Each test records the examples its kill
took as `examples_to_kill`, which `--junitxml` writes out. A fault that died only at the original size would
mean the small size misses it.

`test_writer_mutants.py` gives the writer schema one change at a time: the S2a-1 review's 29 mutants of its
value-field part and its two controls (M1 to M31, its numbering kept), one for each constraint written since
(M6b, M14b, M32 to M59), and eight that tighten it (T1 to T8). Each names the property that kills it and the
assertion it must die at: a loosening mutant dies when the refusal property of its family finds the schema
taking one of the faults it names, its search drawn among those faults, which the family's property draws as
often as any other (the feature audit holds it to a third of that share); a tightening one dies when the
acceptance property finds it refusing a field the text allows, its search drawn on fields of the form and
with the parts in which it refuses one. Both sizes, as above. Two mutants of the review
die at a fault besides the one they were written for, both by the rule they break: M13, without `plus_minus`'s
`then`, also takes an unstated kind beside a stated one, and M48, with `withheld` among an entry's other
statuses, also takes a withheld entry without its recipe.

## Audits

`conftest.py` runs every test here under the two audits of `audits.py`:

- **draw rejection**: a test that throws away more than 40% of its draws (by `assume` or `.filter`) fails,
  and so does a Hypothesis test whose draws the audit could not see;
- **features**: a property declares, with `@pytest.mark.features(name=least_share, ...)`, the least share of
  its examples that must show each feature the specification distinguishes, and records each example's
  features with `support.feature`. A share below its least fails, and so does a feature recorded but not
  declared. Each least share is about a third of the share measured at both sizes. A share is judged only
  where the run's examples make at least 20 expected at the least share: `ci` and `deep` judge every share,
  `dev` those of 10% or more.

## Adding a property

Write the check as a function of the implementation and the example, and the property as a `test_...`
function that records its features and calls the check. Declare the features with their least shares,
measured. Add a mutant that the property must kill, to the mutant file of its group, and the module to a shard.
Never set `max_examples` on a property: the profile decides it. Build strategies so that they draw what they
need rather than filter it, take their size from `strategies.SIZE`, and build each strategy once rather than
in every draw: Hypothesis spends more building and checking a strategy than drawing from it.

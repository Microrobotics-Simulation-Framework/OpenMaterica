# Property tests

Hypothesis properties of the core: the JSON reader (`docs/specification/record_format.md` section 1 item 6),
RFC 8785 (section 9 item 2) and the content hash (section 9). `strategies.py` builds what they draw: JSON
values, texts that write a value in many valid ways, and texts holding exactly one fault the specification
lists. Trees are drawn top-down within a leaf budget, so no draw is thrown away.

## Profiles and sizes

`tests/conftest.py` sets how many examples each property draws, from `MATERICA_HYPOTHESIS_PROFILE`, and
`strategies.SIZE` how large its trees are, from the same profile:

| Profile | Examples per property | Trees | Where it runs |
|---|---|---|---|
| `dev` | 200 | small: 10 scalars, 3 members, depth 5 | the default: locally, and on every Python in CI's test matrix |
| `ci` | 2,000 | small | CI's Hypothesis job, when the core, these tests or their configuration change, and on every code change to main |
| `deep` | 20,000 | original: 30 scalars, 5 members, depth 6 | the same job, weekly and on a manual run |

The original size is the one the properties were first written with, or larger. Content is never narrowed:
text is full Unicode half the time and built from the characters the specification treats apart the other
half, and numbers cover every double. Shapes that small trees cannot reach are explicit examples, run under
every profile: nesting 64, 65 and 100,000 deep, and objects and records with many members.

Every profile keeps its examples in `.hypothesis/examples` at the repository root (git-ignored, cached by CI),
so an example that failed once, under `deep` or any other profile, is tried first on every later run; a
failure prints a blob that replays it anywhere.

## Mutants

`test_mutants.py` gives the core one fault at a time and requires the property aimed at it to find the fault
within the examples of the `ci` profile, at the small size and at the original one. The faults include those
the conformance runner's self-tests use, and faults that only some sizes or contents could show: a nesting
limit off by one, removal that stops at depth 2 or at the first array item, sorting by one pass of exchanges,
non-ASCII escaped. Each test records the examples its kill took as `examples_to_kill`, which `--junitxml`
writes out. A fault that died only at the original size would mean the small size misses it.

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
measured. Add a mutant to `test_mutants.py` that the property must kill. Never set `max_examples` on a
property: the profile decides it. Build strategies so that they draw what they need rather than filter it,
and take their size from `strategies.SIZE`.

# Property tests

Hypothesis properties of the core, in eight groups, of the writer schema, in a ninth, and of the anomaly
check's reader (the last bullet).

- **JSON:** the JSON reader (`docs/specification/record_format.md` section 1 item 6), RFC 8785 (section 9 item
  2) and the content hash (section 9). `strategies.py` builds what they draw: JSON values, texts that write a
  value in many valid ways, and texts holding exactly one fault the specification lists. Trees are drawn
  top-down within a leaf budget, so no draw is thrown away. RFC 8785's property draws names across the
  surrogate range one name in three and negative zero one number in four, which its trees alone held in under
  5% of examples, too seldom for the feature audit at `ci` (below). With them, (9) the one-slip relation
  (`core/slips.py`, section 10), which the read and the name-overlap check share, against a neighbour generator
  written from section 10's list (`test_slip_properties.py`): two names are one slip apart exactly where the
  generator reaches one from the other, by a kind it reaches it by. The generator builds names from a name, as
  the relation compares two, and is the oracle neither shares (the S2a-1 review, verdict 19). Each kind is
  drawn alike, with two slips, unrelated names and two characters swapped far apart as near misses.
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
  specification allows, and refuses each field it forbids by one fault; and it takes every registered field in
  its place, a section's `fields` or an overlay's `replaces`, bound to its row of section 4.1, refusing one
  under a name its section does not register or holding a form, a unit, a label or a composition's basis its
  row does not give, or a specimen fact's unit other than the one its row fixes, a status object included
  (maintainer, 2026-10-15). `value_fields.py` builds the fields from the text alone, never from the schema or
  the bindings it applies: tokens and each field's row from the vocabulary (generated from the specification),
  a specimen fact's members from `provenance.md` section 6.2's JSON shapes, and the rest from the member tables
  and rules each builder cites. A fault is one change the text says breaks a field (a
  member missing, a bound crossed, a token of another member's list or of none, a status token its row does
  not allow, a rule across objects broken, a unit other than the registered one, a field under a name or
  holding what its row does not give), 167 of them in ten families, each drawn as often as another of its
  family on a field, or a body, planned so that its place exists; a family of more than 15 faults is drawn
  in parts of at most 15, each a property of its own, so that the feature audit at `ci` can judge each fault
  (below).
  The refusal is checked on one the schema takes, the same but for the fault, so that it is the fault's.
  And what the writer takes in a body, step 9 of a read passes (the relation its unit bindings exist for):
  a body the text allows passes step 9, and one with every condition and fact, its unit changed at one place
  step 9 compares (the field's, a numeric condition's, a `plus_minus` entry's, a token condition's, a fact's),
  is one the writer refuses. A table's `axis_unit` is not among the places: S3 writes the table's shape, and
  adds it there.
- **Step 8:** (8) the laws of step 8 of a read (`read_side_contract.md` section 3), in the part step 8
  decides, the S2 design's HP3 and HP5: one fault of a catalogue written from the text gives exactly the codes
  its rule gives, and two faults in two parts of the record give both (each step makes all its checks);
  members the reader does not know, added where they may go, never change the outcome, two slips off a named
  member included. `value_field_strategies.py` builds a record holding one constant that passes step 8, each
  member its row's shape or a status object its row allows, and anything at all in the members a read does not
  check; and the catalogue, by region of the record, each fault with the codes its rule gives: 21 regions
  since S2a-2's fix round, which wrote faults for each value step 8 checks, the derivation and `source`
  included, slips beside a named member or of an optional one, and the eleven rules its review found untested.
  HP3 runs in two parts, a property each, the regions taken in turn: each draws its first fault's region among
  its own, before the record, so that the feature audit at `ci` can judge each region (below); the mutant
  searches draw HP3 whole. A third law, the label's rule, holds a label on a table to the Label column, read
  by the test itself, through step 8's shared check, since no read reaches a table before S3. A read that
  passes step 8 is refused at step 9 or 10 or, until steps 11 to 13 are built, raises `NotImplementedError`:
  either is the outcome "past step 8".
- **Steps 9 and 10:** (10) the laws of steps 9 and 10 (`read_side_contract.md` sections 3 and 5), the S2
  design's HP7, HP8 and HP9, and HP3 and HP5 for the part steps 9 and 10 decide
  (`test_condition_properties.py`). HP7: step 10 gives each condition the entry and reason of an oracle
  written from section 5 alone (`condition_oracle.py`, which imports nothing from `core/conditions.py`), on
  the exact rationals the doubles are: each numeric row at each boundary its exactness turns on (an operating
  end anywhere; at `fl(r + t)`; the double next to the exact bound `r + t`, inside it or outside, at ordinary
  magnitudes and among subnormals; a tolerance that is the rounded difference; PR-335's mixed magnitudes, a
  large stated value, a small operating one and a tolerance the double next to their exact difference, at or
  above it or below it; negative zero), each at the lower or the upper end of the stated span, a stated plus
  or minus of each kind, the table's other rows (an accept list holding, beside the row's tokens, a token
  capitalised, a prefix of one and another row's token; a name the reader does not know, held as a value or a
  status object) and the conditions checked, and implied conditions that fill, never override, and disagree.
  Step 10's `met` and `unknown` entries are not returned before S2a-4, so HP7 calls `check_conditions` as the
  read does. HP9: a field's specimen is the section's facts, each overridden by the field's (a dict merge
  written in the test), and an implied condition applies exactly where that merge states its fact and token.
  HP8, end to end through the read: the registered unit passes however escapes write it in the record's text,
  at each place a unit sits (a field's, a condition's, either of two `plus_minus` entries', a fact's in the
  section, the field and a derived value's inputs); any other, equal under NFKC or case folding, or but for a
  space, another registered unit, any text or a status object, gives `unit_mismatch` with its condition, and
  so does any unit on a token condition. HP3: one fault of a catalogue of steps 9 and 10, written from the
  text, on a read every condition of which is stated and met, gives exactly the reasons its rule gives; in one
  draw in four, two faults of two parts of the read give step 9's alone, or two implied conditions that
  disagree alone, or every reason of step 10, its `conditions` returned where one ends the read. HP5: members
  the reader does not know, added to a condition, a `plus_minus` entry, a fact, the request's operating
  conditions, requirement and tolerances, and an implied condition, its record and its values, change nothing,
  the returned `conditions` included. `condition_strategies.py` draws each, its kind first, so that the
  feature audit holds each kind to its draw floor.

  HP7's oracle is a second reading of section 5's rows, written out row by row where the code folds them
  into one test, but not of everything: S2a-3's implementer wrote it after `core/conditions.py`, and it
  repeats three readings the text left open, each the implementer's default in the decision log (section
  "S2a-3 (branch feat/s2a-3)"): a value never agrees with the range `[v, v]` (the entry on two implied
  conditions that "supply different values", now written in section 1 with the fix round's default that `0`
  and `-0` differ); of two implied values that agree, one fills the condition, alike in any order since they
  agree bit for bit (the same entry); and `applied` lists every implied condition that fills, both of two that
  agree (the entry on the result's `applied`). S2a-4's reference model (`tests/reference/read_model.py`, on
  its branch), written from the text by another agent, is to check the three through HP12.

  HP7's boundary kinds reach these sides of their bound, measured over 3,000 derandomised draws a kind
  (2026-10-16, S2a-3's fix round): `one_ulp_inside`, `subnormal_inside` and `mixed_magnitudes_inside` are
  `met` in every draw, and their `_outside` twins `not_met` in every draw, by construction (a draw whose
  window holds no double outside it is built at its other bound, or within the stated span); the property
  asserts it of each example, so that each side is a drawn feature the audit holds to its floor. `anywhere`
  (`met` in 1,625), `at_the_tolerance` (2,747) and `rounded_difference` (2,523) reach both, by where they draw
  and by rounding, and `minus_zero` is `met` but where its edge at `fl(r + t)` rounds outside (2,998).
  Floating point as written disagrees with the exact test in `anywhere`, `at_the_tolerance`,
  `one_ulp_outside`, `rounded_difference` and `minus_zero` (34, 253, 306, 213 and 2 draws), and section 5's
  first row as written, `|r - v| <= t`, also in `mixed_magnitudes_outside` (1,127 of 3,000 value rows): the
  kinds those mutants die at. Which end of the stated span the boundary sits at, and a bound's window, are
  features declared by their chances.
- **The result:** (11) the laws of a read's result (`read_side_contract.md` section 2), the S2 design's HP1,
  HP2, HP6 and HP11 (`test_result_properties.py`), over reads that end at each step S2 builds, the kind drawn
  first (`result_strategies.py`): a record that passes steps 1 to 10, under each `want` of plain read; a
  fault of step 8's catalogue or of steps 9 and 10's; a read that ends before step 4, at step 5 or at step 7;
  and alternatives the request meets, or whose list breaks its shape. HP1: the read gives a result, raising
  `NotImplementedError` for a step not built yet alone, which only step 8's faults reach here; every code is
  the table's, each `(code, condition)` once, `condition` on every `condition_*` reason and on no reason of a
  code that never concerns one. HP2: the status is the worst of the reasons' statuses, which the oracle folds
  from the vocabulary itself, and the members are present as item 6 says (a value with its unit, specimen,
  statistics and provenance exactly where the status is not `not_met` and one value stands; the alternative
  values exactly under `no_pick`; `conditions` beside a value, never under `no_pick` or after a refusal
  before step 10). HP6: what a read returns of a met constant, or of each alternative under `no_pick`,
  equals the stored member, numbers bit for bit and status objects as status objects, holding the members
  the generated `TypedDict`s define (the oracle walks the shapes itself, never the reader's filter), each
  count and index an integer, the review as `provenance.md` section 2 item 6 reads it; and emptying what a
  result returns, its JSON or its members, changes neither a later JSON of it nor a later read of the same
  store. Its draws give the field a value of `-0` in one in four, each way a review reads in one in three,
  and a member the reader does not know in its statistics block, a fact or a condition in one in two, each
  declared by its chance. HP11: without the hash suite, `hash_not_checked` marks exactly a read that reached
  step 4, which the draw knows, and the two reads differ by that label alone. Step 10's faults that leave the
  read to go on (`unchecked`, `unstated`, `unknown_name`, `uncertain`) are a kind of their own, beside a token
  the request does not accept in half its draws, so that a result holds reasons of both statuses; step 8's
  kind draws two faults always in half its draws; and HP6 draws a constant's statistics held as the status
  object its row allows in one draw in four (fuzz target 4 found it returned as an empty block).
- **The reference model:** (12) the S2 design's HP12 (`test_model_properties.py`): the read agrees with the
  test-only reference model (`tests/reference/read_model.py`), given the same sources, request text and
  claims, compared as section 2 compares results (the status; the reasons as a set of their code, condition
  and alternative; the labels as a set; condition entries by name; alternative values in order; every other
  member bit for bit; counts and indexes as the integers rule 5 writes), or both "not yet" (a
  `NotImplementedError`, a no verdict). Five parts, each drawing its kinds first (`model_strategies.py`):
  values and alternatives (a constant met as drawn, at one of section 5's boundaries as HP7 draws them, or
  filled by an implied condition, beside another section's specimen in one draw in three; alternatives met,
  broken, or refused by a request fault); faults of steps 8 to 10, one or two; two faults of one of steps 0,
  8, 9 and 10 that give two reasons (the design's B5, a step that stops at its first fault); step 0's
  catalogue of 52 faults and near misses, and six texts that are no JSON, written from `read_side_contract.md`
  section 1, and reads that end before step 8; and the rules no case file pins (the model's survivors), each
  planted. The known divergences are listed by kind with their reasons and held exactly, failing on any other:
  three steps not built that the model decides (an overlay as the target, S4's decision 8; a form S2b reads;
  an acceptance other than an implied condition), found by the implementation's own `NotImplementedError` and
  held to the draw and to what the model gives; and one open point on which the two read the text differently,
  open point 1's record half (`members_of_the_other_kind`: a record condition holding a member of the other
  kind), where the model must refuse as it fails closed, and the model given the implementation's reading must
  agree with it. Open point 1's request half (an implied value holding a member of the other kind's shape) and
  a slip of a name a declaration gives a requirement (`names_a_declaration_gives_a_requirement`), which the
  text decides, are planted too, and the two must agree on them (S2a-4's fix round). Can-fail controls of the
  check itself: `test_model_controls.py`.
- **What a read must not look at:** (13) the S2 design's HP4 and HP10 (`test_invariance_properties.py`,
  `invariance_strategies.py`). HP4: a fault in another field, registered or not, or in another section's
  specimen never changes a read (the oracle, the read of the record without it); one in the read field's own
  section's specimen refuses it, `form_invalid` or `unknown_token` alone. HP10: sources and request written
  again, members reordered and whitespace, escapes and number spellings drawn, give the original's result,
  compared as section 2 compares; sources identical byte for byte are written again alike, since two copies
  of a pin whose bytes differ are another read.
- **Information monotonicity:** (14) the maintainer's "more checks of the same kind" (2026-10-14): the
  fail-closed spike's relations S2's forms reach, each a property (`test_monotonicity_properties.py`), over a
  world on the spike's grids, half cooperative, and one change (`monotonicity_strategies.py`): N1r, N2, N3r,
  N4, N5r, N6, N8 (information lost never helps), P1 to P4 (added never hurts), S1 and S2 (must degrade) and
  S5 (section 5's rows on the exact values), restricted as the spike's limits say. N7r, P5 to P7, S3 and S4
  speak of tables, picks and alternatives set aside: S3's and S4's. Where a fault's trigger is rare on random
  worlds, a relation draws its way first, a world the read meets with the trigger built in; each relation
  holds, applied with a verdict on both sides and not vacuous, in a declared least share of its examples.
- **The anomaly check's reader:** the YAML reader of `scripts/check_anomalies.py` and its specifier syntax
  against PyYAML's `safe_load` and `packaging` (`test_anomaly_reader_properties.py`, in the `agreement` shard).
  A document the reader reads is read as PyYAML reads it; one PyYAML refuses is refused; one inside the subset
  the reader names is read. Documents are drawn whole, with one or two choices outside the subset, with an edit
  to a valid one, and as single plain words, characters, escapes and boolean words; controls run each on a
  reader with one rule weakened. The reader is a gate script that installs nothing, so these are its only tests
  against a second implementation.

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

Every profile takes Hypothesis's own defaults as its parent, so a machine's environment changes no setting
(`tests/unit/test_hypothesis_profiles.py`). CI therefore draws new examples on every run, as a local run does,
and a run given `--hypothesis-seed` draws there what it draws on any machine. Until #38 it did not: GitHub sets
`CI`, on which Hypothesis loads its built-in `ci` profile at import, and the profiles, registered without a
parent, inherited its `derandomize=True`, which Hypothesis applies before any seed. Every job that ran the
properties drew, for each, the same examples on every run of the same code: the test matrix and the per-commit
job at `dev`, the Hypothesis job at `ci`, and the one `deep` run before #38 (run 39002750375, by hand on
2026-10-17), with that run's fuzz job's replay at `ci`. Every profile also suppresses the `too_slow` health
check, as that built-in profile did on CI: a draw slowed by a loaded runner is not a fault of the code. The
mutant searches, the audits' tests and controls, and T1's variants are derandomised by their own settings, on
purpose.

Every profile keeps its examples in `.hypothesis/examples` at the repository root (git-ignored, cached by CI),
so an example that failed once, under `deep` or any other profile, is tried first on every later run; a
failure prints a blob that replays it anywhere.

## Shards

CI runs the groups in seven shards side by side, each in a job of its own: `pytest tests/property --shard
json`, `--shard records`, which holds the record and step-8 groups, `--shard writer`, `--shard agreement`, the
two validators' agreement (below), `--shard step8_mutants`, step 8's mutant searches, which keep no example
database and were most of the records shard's time, `--shard conditions`, steps 9 and 10's group and the
result's with their mutant searches, which take seconds and set no example database (112 s on four local
workers at `ci`, 2026-10-16; 155 s with the result's, 2026-10-17; 151 s beside the relations' shard,
2026-10-17), and `--shard relations`, the reference model's, isolation and byte form's, and monotonicity
groups with their mutant searches, each example reading two records or a read twice (198 s on four local
workers at `ci`, 2026-10-17; `SHARDS` in `tests/conftest.py`). Each family of faults is a property of its own,
run in parallel. The agreement shard's drawn properties run python-jsonschema on every example, and are the
longest tests of any shard: on 4 workers locally (2026-10-17), the shard took 4.0 and 8.0 minutes at `ci`, its
longest property 1.9 and 4.7 (at loads of 4 to 7 and 15 to 17), and 112 minutes at `deep`, its longest
property 70 (load 18 to 30). `deep` has not yet run on CI, whose cores are 1.6 to 4 times slower: there it may
not fit in the 6 hours GitHub gives a job. Each module is in exactly one shard
(`tests/unit/test_source_files.py`), and each shard but step 8's mutant searches' keeps its own example
database in CI.

## The two validators

Every verdict the tests take from the package's JSON Schemas comes from jsonschema-rs (`tests/verdicts.py`),
alone or beside python-jsonschema's (`tests/spec_sync/schemas.py`). `validator` and `agreed`, for tests that
take few verdicts, run both libraries on every value and fail the test with a `Disagreement` where they
differ. `takes` and the writer properties' `Writer`, for loops, give jsonschema-rs's verdict alone;
python-jsonschema gives the messages a failure prints, and fails the test at once where it finds none. Both
read every resource at draft 2020-12. python-jsonschema takes 32 to 120 ms of CPU a field against the writer's
value field, a choice among eight forms, and 6 to 20 ms against the reader's; jsonschema-rs, 0.01 to 0.08 ms
(drawn fields at `ci`'s size and T1's fields, 2026-10-17, at loads of 13 to 22, which move CPU time too).

`test_validators_agree.py`, the `agreement` shard, holds the two to one verdict:
- on T1's inputs (`tests/spec_sync/test_t1.py`): each field against the writer schema and the reader `$defs`,
  by its form's definition and by `value_field`, its section's specimen against both, and the field against
  its row's binding. Every example at `deep`; at `dev` and `ci`, every tenth example of each group (the inputs
  that read one registered field, and the variants of one base by one change and origin), 670 of the 5,066,
  which holds each registered field, base, origin and change, alone and beside each origin (`share_misses`). A
  whole pass took 590 s and 760 s summed over 8 workers on a loaded machine (2026-10-16).
- on drawn fields, against the writer's and the reader's `value_field`; drawn bodies, against the writer's;
  drawn records changed near each boundary of the envelope (`records.sweeps()`), and every conformance input
  that parses, against the reader schema; and the base and faulty field of each fault family, against both
  value fields; as many as the profile gives.
- along each writer mutant's own search (`test_writer_mutants.py`), as its table runs it, up to the example at
  which the mutant's verdict first differs from the package's. There a difference of that mutant's reach, on
  either side, shows on every run. The drawn faults alone meet such a difference by chance: Hypothesis shows
  one draw in about eight examples, so 2,000 examples give each of the 166 faults one or two draws, and in the
  review of 2026-10-17, 12 of the 89 mutants changed no compared verdict in at least one of five samples.

It lists every place in the tests that takes jsonschema-rs's verdict alone, with the tests that compare that
schema or the reason it is left out, and checks that the list is exact by reading the tests' sources. Its
controls: writer mutants given to one side (M18 on T1's share, M55 on the drawn faults, each of the 12 along
its own search, and U1 to U3 along theirs, which draw bodies with a unit changed) and reader mutants given to
one side (on drawn faults and on drawn records), each found as the side given it taking what the other
refuses; a pattern ended in `$`, given to both, which python-jsonschema reads as matching before a final
newline and jsonschema-rs, as ECMA-262 does, not; the pairs the properties use, each of both libraries; and
T1's inputs, naming every definition T1 judges an example by. `tests/spec_sync/test_schemas.py` holds every
schema file to draft 2020-12 and every pattern to what both libraries read alike: anchored at both ends, by
`^` and `(?![\s\S])`, with no escape of a letter or digit, no `.` or `$` outside a class and no POSIX class.

## Mutants

`test_mutants.py` (JSON) and `test_record_mutants.py` (records) give the core one fault at a time and require
the property aimed at it to find the fault within the examples of the `ci` profile, at the small size and at
the original one. The faults include those the conformance runner's self-tests use, and faults that only some
sizes or contents could show: a nesting limit off by one, removal that stops at depth 2, sorting by one pass of
exchanges, a pattern searched where it must match in full, versions ordered as strings or as doubles, an
unreadable source ignored, the first of two differing copies read. Each test records the examples its kill
took as `examples_to_kill`, which `--junitxml` writes out. A fault that died only at the original size would
mean the small size misses it.

A derandomized run draws none of the constants Hypothesis harvests from the loaded modules
(`tests/harvested_constants.py`), so a search's examples, and its count, depend on the code alone: the mutant,
the property's strategy and check, and the versions of Hypothesis and Python, not which other modules the
process imported or in what order. Until 2026-10-18 they did not: Hypothesis (6.169) takes a constant in about
one draw in twenty, half the time one it found in a loaded module outside `tests/`, and `derandomize=True`
fixes the seed, not those constants, so a module added for any reason could move kills in every shard or let a
mutant survive. #43's `scripts/check_anomalies.py`, collected through its unit tests, moved 13 of the 544
kills that `--property-controls only` measures, and `a_non_object_provenance_opens` survived 2,000 examples at
the original size; a module of 270 other constants loaded beside the suite moved 47, and each mutant module
collected alone, 62. With the constants pinned, none of the 544 moved in any of those runs, nor on Python 3.11
against 3.15 (measured 2026-10-18, as are the counts below). Each mutant dies within its 2,000 examples, at
both sizes; the latest kill is at the 276th example (`id_pattern_searched`, small size), and none of the 544
comes after the 500th (measured 2026-10-18, after the three searches below were planned).

Three searches were planned because their kill sat in a long tail. With the pin, a search's kill is fixed by
the code, but where the kill is late, a change that moves the seed (a Hypothesis upgrade, or any other change to
what Hypothesis hashes into a search's seed) can move it past the budget. Each of
the three was reseeded 24 times with the code unchanged (a pytest plugin salting `hypothesis.core.
function_digest`, salts `v1` to `v24`: the strategies and the code are the same, only the seed differs), drawn whole: `a_non_object_provenance_opens` took 872 examples at the original size
and 455 at the small (pinned), up to 1,875 and 1,311 over the salts, and survived 2,000 at the small size in
one salt; `empty_word_made_plural` 629, up to 945; `row_requirements_ignored` 536, up to 1,363, and survived
2,000 in one salt (both sizes). Each fault shows in a thin region of its property's examples (below), so each
is now searched in that region, in records the core passes, and the property itself is unchanged:

| Mutant | Where the fault shows | The planned search |
|---|---|---|
| `a_non_object_provenance_opens` | an edit of a leaf below a `review` or `copy` in a provenance whose value is an array, which the hash keeps (item 1 removes them inside a provenance object only): the hash's `edits` must draw such a provenance, an object inside it holding one of the names, and that leaf among the record's | The hash's record, a `held` member `{"provenance": [...]}` holding an object (in up to two further arrays) with `review` or `copy`, and an edit of a leaf below it |
| `empty_word_made_plural` | `x__y` against `x_s_y` (one character added) or `x_es_y` (two): (9)'s `pairs` must draw a name with an empty word, then the slip that puts `s` or `es` in exactly that word | a name of words with one empty, the same with `s` or `es` in it, in either order |
| `row_requirements_ignored` | a condition the field's row requires that the record does not hold and the request does not name: `table_cases` names every one in the request, so it needs the `unchecked` kind to remove one from the request and `absent_but_required` to remove the same from the record | HP7's table case with one required condition removed from the record and from the request |

Each is meant to draw only examples the core passes, and three controls check that, on fresh random draws of the
same strategy, not on the search's own derandomized 2,000: 200 at `dev` and 2,000 at `ci` and `deep`. The hash's
(`test_mutant_view.py`) runs at both sizes, small and original, in two arms: the strategy as the search draws it,
and the strategy with the tree below `review` or `copy` planned to hold a provenance object that removes a leaf,
alone or beside a kept one, which is the draw that tells a search that edits a removed leaf from the planned one.
The first draft of the hash's strategy, without the filter that picks a kept leaf, failed the core on 1 of 5,000
random examples at the small size and 6 of 5,000 at the original (the review's measurement), so the first arm
alone would catch it in a run of 2,000 (`ci`) with a probability of 33% at the small size and 91% at the original,
and in a run of 200 (`dev`) 4% and 21%; the second arm catches it at the first example of every run (the first
draw of its `one_of` is a tree with no kept leaf, and a random draw fails three times in four, so 200 draws miss
it with a probability below 1e-100; measured 40 runs of 200 in 40, at each size), and a third test runs the
strategy without the filter against the control and asserts that it fails, at both sizes. The slips' control (`test_mutant_view.py`, `pairs_through_an_empty_word`, which takes no
size) and the conditions' (`test_condition_mutant_table.py`, `table_cases_without_a_requirement`, no size either)
draw their one strategy. The three mutants, by the searches in `test_mutants.py` and `test_condition_mutants.py`,
fail on every one of the 2,000 examples of each search, at both sizes, at the assertion that names their fault:
`check_edit`'s "left the hash unchanged", `check_one_slip`'s first or second assertion, and
`check_against_the_oracle`'s reasons. Each search dies at its first example at both sizes, and in each of the
24 salts (measured 2026-10-18). That is by construction: Hypothesis draws the example of all zero choices
first, whatever the seed, and every planned example kills, so the kill point is 1 and a salt cannot move it. It
is not a margin. What it shows is the number of the planned examples that kill: 2,000 of 2,000 for each of the
three (the slip's first draw, `Pair('s', '')`, is the degenerate whole name `''` against `s`, not `x__y` against
`x_s_y`; 1,996 of its 2,000 contain an underscore).

CI's test matrix runs the mutant modules, `test_*mutants*`, on the supported range's ends alone
(`--property-controls` in `tests/conftest.py`), so a mutant module holds mutant searches only. The checks of
the mutants' own code, which run on every Python, are in modules of their own: `test_mutant_view.py` (the hash
mutants' view, without a fault, is the core's), `test_value_field_mutant_table.py`,
`test_writer_mutant_table.py`, `test_condition_mutant_table.py`, `test_result_mutant_table.py`,
`test_model_mutant_table.py` with HP12's controls in `test_model_controls.py`,
`test_invariance_mutant_table.py` and `test_monotonicity_mutant_table.py`.

`test_mutants.py` also gives the one-slip relation twelve faults, each killed by (9) (its strategy has no size,
so both sizes take the same examples; measured 2026-10-18):

| Mutant | Fault | Examples |
|---|---|---|
| `substitution_missed`, `insertion_missed`, `underscore_missed`, `swap_missed`, `plural_missed` | a kind of slip missed | 19, 1, 28, 3, 23 |
| `underscore_read_as_a_character` | an underscore added is named a character added | 28 |
| `two_characters_added_one_slip` | two characters added at the end are one slip | 38 |
| `swap_of_any_two_characters` | two characters swapped far apart are one slip | 11 |
| `ies_plural_missed`, `es_plural_missed`, `irregular_plurals_missed` | a plural section 10 lists missed | 155, 38, 114 |
| `empty_word_made_plural` | the empty string between two underscores is a word, `s` its plural | 1 (planned) |

The last is the relation as it stood until the property found it: `x__y` and `x_s_y` are one character apart,
but `x__y` and `x_es_y` two, which it called one plural.

`test_writer_mutants.py` gives the writer schema one change at a time: the S2a-1 review's 29 mutants of its
value-field part and its two controls (M1 to M31, its numbering kept), one for each constraint written since
(M6b, M14b, M32 to M61), and nine that tighten it (T1 to T9); then the bindings it applies from the
vocabulary, each changed in the vocabulary file or no longer applied by the writer: a section's field names, a
field's forms, unit, label or composition basis, its alternatives, the replaced fields, a numeric condition's
unit and its `plus_minus` entries', a specimen fact's fixed unit (B1 to B14, with B5b), and five that tighten
them (TB1 to TB5); and three of those bindings removed again (U1 to U3: the specimen facts', a field's unit,
the conditions'), each killed by the relation to step 9 at a body with a unit changed where it held, searched
among those places (each at its first example, both sizes; measured 2026-10-16). Each names
the property that kills it and the assertion it must die at: a loosening mutant dies when the refusal property
of its family finds the schema taking one of the faults it names, its search drawn among those faults, which
the family's property draws as often as any other (the feature audit holds it to its draw floor); a
tightening one dies when the acceptance property finds it refusing a field the text allows, its search drawn
on fields of the form and with the parts in which it refuses one. Both sizes, as above. Two mutants of the
review die at a fault besides the one they were written for, both by the rule they break: M13, without
`plus_minus`'s `then`, also takes an unstated kind beside a stated one, and M48, with `withheld` among an
entry's other statuses, also takes a withheld entry without its recipe.

### Step 8's mutants

`test_value_field_mutants.py`. Each fault is injected where the core looks a name up when it runs, or in the
tables it builds, rebuilt under the fault. The first 25 (S2a-2's 24, and its fix round's
`fact_unit_judged_at_step_8`) were searched with their property whole; the 23 of them HP3 kills are now
planned too (below), and HP5's two are still searched whole. The other 22 are the fix round's: the eleven
rules S2a-2's review found no test checked (M1; the fact unit's is `fact_unit_judged_at_step_8`), and parts of
the text HP3 had no fault for or could not tell from a missing member (M2). One, `label_on_any_table`, dies to
the label's rule. The other 21 each name the faults they must die at, and their search is planned, as the
writer's are: HP3 draws its first fault among them, and the kill must hold one. Drawn with HP3 whole, 17 of
those 21 were measured: each died within its 2,000 examples at both sizes but `within_any_status` and
`label_beside_an_unknown_form_as_on_a_constant`, which died at the original size alone (884 and 845). HP3
whole meets one fault of 154 too seldom to kill each such mutant every time at `ci`, so the planned search is
what shows HP3 refuses each fault, and the region audit that HP3 draws it; each of the review's eleven rules
also has a deterministic read in `tests/unit/test_read.py`. The kill is the examples the derandomised search
took, at the small and the original size (measured 2026-10-18).

Two of the first 25, `missing_represents_accepted` and `named_state_text_unchecked`, have had planned searches
since 2026-10-16: searched with HP3 whole, each survived 2,000 examples at the small size once the suite held
`scripts/report_test_durations.py`, which its unit tests import, and died where their module ran alone. At
S2a-3's head, `named_state_text_unchecked` also survived 2,000 examples at the original size where its shard
ran alone, as CI runs it, and died where the whole suite ran: S2a-3's code added constants. Hypothesis (6.169)
draws, among its values, constants it finds in the project's modules the process has loaded, test modules
aside, so the examples a derandomised search meets changed with the code and with what else a process imported
(no longer: Mutants, above). Emptying that pool, the search killed it alone and after the unit tests alike
(measured 2026-10-16). Planned,
each dies at its first example at both sizes, alone, after the whole suite's collection, on Python 3.11 and
3.15. The other 21 that HP3 kills, which could each meet the same at any change, have been planned since S2a-3
came onto main (maintainer, 2026-10-16): each names the faults of HP3's catalogue that test the rule it
breaks, chosen from a search on each of the 154 faults alone against each mutant at both sizes (a fault that
killed it only beside a second fault was left out), and dies at its first example at both sizes, alone and
after the whole suite's collection, on Python 3.11 and 3.15 (measured 2026-10-17). Searched whole, they had
died after 3 to 1,297 examples. HP5's two, `unknown_members_refused` and `two_slips_refused`, are still
searched whole: HP5 draws no fault of the catalogue to name, and nearly every example it draws kills each, at
the second example at both sizes in each of those runs.

| Mutant | Fault | Killed by | Dies at | Examples |
|---|---|---|---|---|
| `unknown_tokens_ignored` | a token the reader knows for no member of its name is accepted | HP3 | the 13 faults of a token unknown to its member (`UNKNOWN_TOKENS`) | 1, 1 |
| `unknown_token_read_as_a_shape_fault` | such a token gives `form_invalid` | HP3 | those 13, `statistics_statuses.status_unknown` and `field.label_unknown` | 1, 1 |
| `status_tokens_unchecked` | a status object takes any status token | HP3 | `statistics_statuses.block_status_not_allowed`, `.status_not_allowed`, `.status_unknown`, `.within_status_not_allowed`, `field.value_status_not_allowed` | 1, 1 |
| `members_beside_a_status_ignored` | a status object beside a member of the shape it stands for is read as one | HP3 | `statistics_statuses.uncertainty_status_beside_a_member`, `condition_tokens.status_beside_a_token`, `.status_beside_unit`, `specimen_tokens.fact_status_beside_its_token` | 1, 1 |
| `missing_represents_accepted` | a statistics block without `represents` passes (the S2 design's HP3 mutant) | HP3 | `statistics_members.represents_missing` | 1, 1 |
| `null_read_as_absent` | `null` in an optional member reads as the member absent (HP3's) | HP3 | `condition_tokens.set_or_measured_null`, `provenance.source_null` | 1, 1 |
| `unknown_condition_names_checked` | a condition name the reader does not know is checked as a numeric condition (HP3's "read as known") | HP3 | `condition_tokens.name_unknown` | 1, 1 |
| `plus_minus_kinds_unchecked` | a `plus_minus` list is checked only as a list | HP3 | `conditions.plus_minus_empty`, `.plus_minus_negative`, `.plus_minus_two_bounds`, `.plus_minus_unit_not_a_string`, `.plus_minus_unstated_beside_sd` | 1, 1 |
| `range_order_unchecked` | a range's `lo` may lie above its `hi` | HP3 | `conditions.range_reversed`, `.range_reversed_on_shear_rate`, `specimen.fact_range_reversed` | 1, 1 |
| `counts_not_whole` | `n_specimens` takes any number | HP3 | `statistics_numbers.count_not_whole` | 1, 1 |
| `conditional_members_unchecked` | `population_level`, `n_sources` and `precision_conditions` may sit beside any `represents` | HP3 | `statistics_members.n_sources_elsewhere`, `.population_level_elsewhere`, `.population_level_missing`, `.precision_conditions_missing`, `uncertainty.uncertainty_precision_missing` | 1, 1 |
| `uncertainty_rules_unchecked` | an uncertainty's coverage, `dof` and precision rules go | HP3 | `uncertainty.dof_status_under_student_t`, `.dof_under_normal`, `.no_coverage_number`, `.uncertainty_precision_missing` | 1, 1 |
| `named_state_text_unchecked` | a disease or treatment state's text may sit beside any token, or be missing | HP3 | `specimen.fact_text_beside_normal`, `specimen.fact_treated_without_text` | 1, 1 |
| `fixed_basis_unchecked` | `mimics`'s basis takes either token, not the one its row fixes | HP3 | `specimen_tokens.fact_basis_not_its_rows` | 1, 1 |
| `fact_unit_judged_at_step_8` | a fact's unit is judged at step 8, `s` alone and a status object of the five tokens only, where step 9 alone compares it (a default for the maintainer, 2026-10-15) | HP3 | `specimen.fact_unit_not_its_rows`, `.fact_unit_status_any_token` | 1, 1 |
| `record_structure_unchecked` | a slip in the envelope, the body or a section is ignored | HP3 | `record.body_slip`, `.envelope_slip`, `.licence_slip`, `.section_name_slip` | 1, 1 |
| `section_specimen_unchecked` | a section's `specimen` is not checked | HP3 | `section_specimen.section_fact_name_slip`, `.section_fact_not_its_shape` | 1, 1 |
| `first_refusal_only` | step 8 gives its first reason only (the S2 design's HP12 mutant) | HP3 | `field_form.form_unknown_beside_a_slip`, one fault that gives two reasons | 1, 1 |
| `slip_by_substitution_missed` | the one-slip relation misses a character substituted | HP3 | `statistics_slips_beside.slip_beside_substituted`, `field_slips_optional.slip_substituted` | 1, 1 |
| `slip_by_insertion_missed` | it misses a character inserted or deleted | HP3 | `statistics_slips_beside.slip_beside_inserted`, `.slip_beside_deleted`, `field_slips_optional.slip_inserted`, `.slip_deleted` | 1, 1 |
| `slip_by_swap_missed` | it misses two adjacent characters swapped | HP3 | `statistics_slips_beside.slip_beside_swapped`, `conditions.plus_minus_slip`, `field_slips_optional.slip_swapped` | 1, 1 |
| `slip_by_plural_missed` | it misses a word made plural or singular | HP3 | `statistics_slips_beside.slip_beside_plural`, `field_slips_optional.slip_plural` | 1, 1 |
| `slip_by_underscore_missed` | it misses an underscore added or removed | HP3 | `statistics_slips_beside.slip_beside_underscore`, `field_slips_optional.slip_underscore` | 1, 1 |
| `unknown_members_refused` | every member a place does not name is refused | HP5 | any of its property | 2, 2 |
| `two_slips_refused` | names two characters off a named member are refused too | HP5 | any of its property | 2, 2 |
| `within_any_status` | a population level's `within` takes any status token, where `none` alone is allowed | HP3 | `statistics_statuses.within_status_not_allowed` | 1, 1 |
| `uncertainty_precision_any_string` | an uncertainty's `precision_conditions` takes any string | HP3 | `uncertainty_tokens.uncertainty_precision_unknown` | 1, 1 |
| `statistics_not_applicable_on_a_constant` | a constant's `statistics` takes `not_applicable`, which only reference data's takes | HP3 | `statistics_statuses.block_status_not_allowed` | 1, 1 |
| `basis_any_string` | a condition's and a fact's `basis` take any string | HP3 | `condition_tokens.basis_unknown`, `specimen_tokens.fact_basis_of_another_member` | 14, 42 |
| `condition_status_refuses_its_own_shapes_members_only` | a condition's status object refuses only its own shape's members, so `token` beside a numeric condition's passes | HP3 | `condition_tokens.status_beside_a_token` | 1, 1 |
| `token_known_within_its_kind` | a condition's `token` knows only the conditions' tokens and a fact's only the facts', so `tube` in `tissue_state` is `unknown_token` | HP3 | `condition_tokens.token_of_a_fact`, `specimen_tokens.fact_token_of_a_condition` | 1, 1 |
| `token_condition_unit_unchecked` | a token condition's `unit` takes anything | HP3 | `condition_tokens.token_condition_unit_not_a_string` | 1, 1 |
| `label_on_any_table` | a label goes on a table whatever its axis | the label's rule | its oracle, on a table on its row's axis | 3, 35 |
| `label_beside_an_unknown_form_as_on_a_constant` | a label beside a form the reader does not know is judged as on a constant | HP3 | `field_form.form_unknown_beside_the_label` | 2, 2 |
| `no_form_member_named_beside_an_unknown_form` | beside a form the reader does not know, no form's own member is named, so `intervals` is ignored | HP3 | `field_form.form_unknown_beside_a_slip` | 1, 1 |
| `statistics_block_slips_ignored` | a slip among a statistics block's members is ignored | HP3 | `statistics_slips_beside.*` | 1, 1 |
| `field_level_slips_ignored` | a slip among a field's members is ignored | HP3 | `field_slips_optional.*` | 1, 1 |
| `status_object_slips_ignored` | a slip inside a status object is ignored | HP3 | `statistics_statuses.status_slip` | 1, 1 |
| `derivation_unchecked` | a derived value's derivation is not checked | HP3 | `derivation.*` and `derivation_inputs.*` but `derivation_missing` | 1, 1 |
| `derivation_inputs_may_be_empty` | a derivation's `inputs` may be empty | HP3 | `derivation.inputs_empty`, its input specimens emptied with it, since an index past no input would refuse alone | 1, 1 |
| `block_mean_any` | a statistics block's `mean` takes any value | HP3 | `statistics_numbers.mean_not_a_number` | 1, 1 |
| `block_precision_any_string` | a statistics block's `precision_conditions` takes any string | HP3 | `statistics_tokens.precision_conditions_unknown` | 1, 1 |
| `neither_value_nor_range_allowed` | a numeric condition may hold neither `value` nor `range` | HP3 | `conditions.neither_value_nor_range` | 1, 1 |
| `n_sources_any_number` | `n_sources` takes any number | HP3 | `statistics_numbers.n_sources_not_whole`, `.n_sources_negative` | 1, 1 |
| `dof_of_zero_allowed` | an uncertainty's `dof` may be 0 | HP3 | `uncertainty.dof_zero` | 1, 1 |
| `coverage_probability_of_zero_allowed` | an uncertainty's `coverage_probability` may be 0 | HP3 | `uncertainty.coverage_probability_zero` | 1, 1 |
| `population_level_any_string` | a population level's `level` takes any string | HP3 | `statistics_tokens.level_unknown` | 1, 1 |

The S2 design's HP5 mutant, an unknown member returned, waits for the result's members (S2a-4), but in a
condition's entry, which steps 9 and 10's HP5 kills (`unknown_members_returned_in_an_entry`, below).

### Steps 9 and 10's mutants

`test_condition_mutants.py`, injected as step 8's are: a module-level function of `conditions`, `fields` or
`read`, or `RecordField.specimen`. Each names the property that kills it; the search draws that property's
examples, the parametrised ones (HP7's rows, HP8's places) drawn among their parameters, and where it names
the labels it must die at (the kind an example was drawn of, a unit's place and kind, a read's faults, the
places of its additions), the example that kills it must hold one. HP7's and HP9's examples hold no tree, so
both sizes take the same examples. Three rules no property draws are searched alike over the deterministic
tables of `tests/unit/test_read.py` that check them: an implied condition located elsewhere, read end to end
("located elsewhere"), and the implied conditions step 0 refuses ("step 0"). The kill is the examples the
derandomised search took, at the small and the original size (measured 2026-10-18).

Seven of these are the mutants of S2a-3's review that survived the whole suite (its M2), each a rule no test
checked: `implied_not_located`, `located_at_without_its_hash`, `accept_list_case_folded`,
`accept_list_by_prefix`, `unknown_name_status_read_as_unstated`, `only_the_first_plus_minus_unit` and
`implies_value_not_an_object_ignored`. The first two and the last die to the deterministic tables written for
them; the other four survived 2,000 examples at both sizes until HP7's token kinds drew accept lists holding
strings outside the row, its `unknown_name` kind a status object as often as a value, and HP8's `plus_minus`
place the unit in either entry of two.

One of HP3's searches is planned. `conditions_withheld_from_a_refusal` empties step 10's entries, which the
read takes for two implied conditions that disagree, so on a read step 10 does not end it ends the read there
too, with neither `value` nor `conditions`. HP3 drawn whole meets such a read first (an `unstated` one, at the
original size, once the harvested constants were pinned), and there the assertion that fails is HP3's for a
read past step 10, not the refusal's the mutant was written for. Its search ("HP3, a refusal at step 10")
draws HP3's first fault among step 10's four that end the read and keep its `conditions` (`ENDING`), and it
dies at an `outside` read at both sizes. As a control, where HP3 expected a refusal to hold no `conditions`,
the planned search let it survive 2,000 examples at both sizes, and HP3 whole still killed it, at reads past
step 10 (measured 2026-10-18).

| Mutant | Fault | Killed by | Dies at | Examples |
|---|---|---|---|---|
| `floating_point_as_written` | section 5's tests computed in floating point | HP7 | `anywhere`, `at_the_tolerance`, `one_ulp_outside`, `rounded_difference`, `minus_zero` | 9, 9 |
| `value_row_difference_in_floating_point` | section 5's first row as written, `\|r - v\| <= t`, computed in floating point | HP7 | `anywhere`, `at_the_tolerance`, `one_ulp_outside`, `rounded_difference`, `mixed_magnitudes_outside` | 9, 9 |
| `strict_inequalities` | `<` for `<=` | HP7 | any of its examples | 1, 1 |
| `stated_range_as_its_low_end` | a stated range read as its `lo` | HP7 | any of its examples | 75, 75 |
| `operating_range_as_its_low_end` | an operating range read as its `lo` | HP7 | any of its examples | 26, 26 |
| `plus_minus_ignored` | a stated plus or minus ignored | HP7, plus or minus | `bound`, `sd`, `unstated`, `bound_beside_sd` | 3, 3 |
| `plus_minus_makes_not_met` | a stated plus or minus turns `met` into `not_met` | HP7, plus or minus | `bound`, `sd`, `unstated`, `bound_beside_sd` | 3, 3 |
| `sd_ignored` | an `sd` or unstated entry ignored where no bound sits | HP7, plus or minus | `sd`, `unstated` | 3, 3 |
| `bound_moves_the_low_end_only` | a bound narrows the window at its low end alone | HP7, plus or minus | `bound`, `bound_beside_sd` | 24, 24 |
| `unchecked_read_as_met` | a stated condition with no tolerance or accept list is `met` | HP7, table | any of its examples | 3, 3 |
| `not_accepted_read_as_unknown` | a token outside the accept list is `unknown` | HP7, table | any of its examples | 7, 7 |
| `accept_list_case_folded` | a token matched against an accept list after case folding | HP7, table | any of its examples | 7, 7 |
| `accept_list_by_prefix` | a token matched by an entry of the accept list that begins with its first three characters | HP7, table | any of its examples | 83, 83 |
| `unknown_name_status_read_as_unstated` | a name the reader does not know, held as a status object, read as `condition_unstated` | HP7, table | any of its examples | 5, 5 |
| `unknown_name_read_as_unstated` | a name the reader does not know is `condition_unstated` | HP7, table | any of its examples | 5, 5 |
| `required_with_ignored` | a condition another requires with its token is not checked | HP7, table | any of its examples | 3, 3 |
| `row_requirements_ignored` | the row's required conditions are not checked | HP7, table (planned) | any of its examples | 1, 1 |
| `status_object_not_returned` | an entry held as a status object returns no `record` | HP7, table | any of its examples | 1, 1 |
| `operating_returned_only_with_a_requirement` | `operating` returned only where a tolerance is given | HP7, table | any of its examples | 34, 34 |
| `implied_overrides_a_stated_value` | an implied condition fills a stated condition | HP7, implied | `never_over_a_stated_value`, `never_over_another_status` | 2, 2 |
| `implied_fills_any_status` | an implied condition fills any status object | HP7, implied | `never_over_another_status` | 21, 21 |
| `disagreement_ignored` | two implied conditions that disagree, the first wins | HP7, implied | `two_that_disagree`, `a_value_beside_a_range`, `minus_zero_beside_zero` | 8, 8 |
| `a_value_agrees_with_its_range` | a value agrees with the range `[v, v]` | HP7, implied | `a_value_beside_a_range` | 25, 25 |
| `minus_zero_agrees_with_zero` | implied values compared as numbers, `-0` agreeing with `0` (S2a-3's first reading, until its fix round's default) | HP7, implied | `minus_zero_beside_zero` | 8, 8 |
| `implied_applies_without_its_fact` | an implied condition applies whatever the specimen states | HP7, implied | `its_fact_not_stated` | 73, 73 |
| `applied_not_recorded` | `applied` holds no implied condition | HP7, implied | any of its examples | 1, 1 |
| `implied_not_located` | every implied condition applied, wherever it is located | located elsewhere | any of its rows | 1, 1 |
| `located_at_without_its_hash` | a location compared by `id` and `version`, without its `content_hash` | located elsewhere | `another_content_hash` | 3, 3 |
| `implies_value_not_an_object_ignored` | an implied value that is not an object dropped without a reason | step 0 | `a value that is not an object` | 2, 2 |
| `section_facts_win` | the section's fact overrides the field's (the S2 design's HP9 mutant) | HP9 | `the_field_another_token`, `the_field_a_status_object`, `the_section_a_status_object` | 7, 7 |
| `a_status_fact_overrides_nothing` | a field's fact held as a status object leaves the section's | HP9 | `the_field_a_status_object` | 22, 22 |
| `nfkc_before_comparing` | units compared after NFKC (the S2 design's HP8 mutant) | HP8, another unit | `compatibility_equal` | 1, 1 |
| `case_folded` | units compared after case folding (the S2 design's HP8 mutant) | HP8, another unit | `case_folded`, `compatibility_equal` | 2, 2 |
| `spaces_ignored` | spaces and zero-width spaces dropped from a unit | HP8, another unit | `spaced` | 11, 11 |
| `a_status_object_where_a_string_is_registered` | a status object takes a string's place | HP8, another unit | `status_object` | 35, 5 |
| `plus_minus_units_unchecked` | a `plus_minus` entry's unit not compared | HP8, another unit | `plus_minus` | 2, 2 |
| `only_the_first_plus_minus_unit` | only the first `plus_minus` entry's unit compared | HP8, another unit | `plus_minus` | 9, 87 |
| `token_condition_units_unchecked` | a `unit` on a token condition passes | HP8, another unit | `token_condition` | 179, 3 |
| `section_facts_unchecked` | the section's facts' units not compared | HP8, another unit | `section_fact` | 34, 6 |
| `input_facts_unchecked` | a derived value's input facts' units not compared | HP8, another unit | `input_fact` | 4, 52 |
| `condition_dropped_from_unit_mismatch` | a condition's `unit_mismatch` carries no condition | HP8, another unit | `condition`, `plus_minus`, `token_condition` | 2, 2 |
| `plus_minus_against_the_field_unit` | a `plus_minus` unit compared with the field's unit | HP8, the registered unit | any of its examples | 1, 1 |
| `facts_against_the_field_unit` | a fact's unit compared with the field's unit | HP8, the registered unit | any of its examples | 1, 1 |
| `step_10_after_a_refusal_at_step_9` | step 10 runs after step 9's `not_met` | HP3 | a fault of step 9 | 1, 1 |
| `first_unit_reason_only` | step 9 gives its first reason only | HP3 | a fault of step 9 | 1, 1 |
| `unknown_reasons_dropped_beside_not_met` | step 10's `unknown` reasons dropped beside a `not_met` | HP3 | `unchecked`, `unstated`, `unknown_name`, `uncertain` | 7, 98 |
| `conditions_withheld_from_a_refusal` | a read step 10 ends returns no `conditions` | HP3, a refusal at step 10 (planned) | `outside`, `range_outside`, `not_accepted`, `implied_outside` | 2, 2 |
| `disagreement_checks_the_others` | two implied conditions that disagree, and the conditions checked all the same | HP3 | `disagreeing` | 102, 9 |
| `unknown_members_returned_in_an_entry` | a condition's entry returns members the reader does not know | HP5 | `condition`, `plus_minus_entry` | 5, 10 |
| `two_slips_refused_in_a_request` | a request's names two characters off a named one refused | HP5 | any of its examples | 4, 4 |
| `unknown_request_members_refused` | every member a request's place does not name refused | HP5 | `operating`, `requirement_condition`, `tolerance`, `implied`, `implied_record`, `implied_value` | 4, 3 |

A mutant first written for HP5, step 0 keeping an implied value's unknown members, was dropped: no read can
tell it from the core, since step 10 returns a filled condition with the members the reader knows alone.

### The result's mutants

`test_result_mutants.py`, injected as steps 9 and 10's are: a module-level function or name of `read`,
`conditions` or `resolve`. Each names the property that kills it and the kinds or features (`-0`, an unknown
member, a review's way, a statistics status object) one of which the example that kills it must show. The kill
is the examples the derandomised search took, at the small and the original size (measured 2026-10-17, S2a-4's
phase B, in the conditions shard). Phase A's `condition_unchecked_without_its_condition` died at 1,079 of
2,000 at the small size; since its fault's kind is drawn as one of its own (`unknown_at_step_10`), over twelve
random seeds a search it dies within 507, `reasons_not_merged` within 115 and `best_status` within 310 (they
took up to 1,459 and 1,587 over 24). Two HP1 mutants die at a fault of step 8 and at one of steps 9 and 10
alike, as the comments above them in `test_result_mutants.py` say; their kills are measured with the pin
(2026-10-18). The S2 design's other HP6 mutant, an interval's `upper: none` read as infinity, waits for S2b-1,
which reads intervals.

| Mutant | Fault | Killed by | Dies at | Examples |
|---|---|---|---|---|
| `condition_unchecked_without_its_condition` | `condition_unchecked` given without its condition (the S2 design's HP1 mutant) | HP1 | `step_8_fault`, `step_9_or_10_fault`, `unknown_at_step_10` | 9, 1,172 |
| `stated_without_origin_with_a_condition` | `stated_without_origin` given a condition | HP1 | `met`, `step_9_or_10_fault`, `unknown_at_step_10` | 186, 283 |
| `a_code_outside_the_table` | step 13's refusal under a code the table does not hold | HP1 | `met` | 79, 11 |
| `reasons_not_merged` | a reason found twice given twice | HP1 | `step_8_fault`, `step_9_or_10_fault` | 55, 39 |
| `value_beside_condition_outside` | a read step 10 refuses goes on, and returns its value (the S2 design's HP2 mutant) | HP2 | `step_9_or_10_fault`, `unknown_at_step_10` | 9, 146 |
| `best_status` | the status the best of the reasons' | HP2 | any kind | 9, 468 |
| `conditions_beside_no_pick` | a `no_pick` result holds the first alternative's `conditions` | HP2 | `alternatives` | 97, 3 |
| `no_unit_beside_alternative_values` | a `no_pick` result holds no `unit` | HP2 | `alternatives` | 97, 3 |
| `expanded_uncertainty_divided_by_its_k` | an expanded uncertainty returned divided by its coverage factor (the S2 design's) | HP6 | `met`, `alternatives` | 11, 9 |
| `results_share_the_record` | a member with nothing to leave out returned as the record's own object (the S2 design's) | HP6 | `met`, `alternatives` | 1, 1 |
| `json_shares_the_result` | a result's JSON shares its objects with the result | HP6 | `met`, `alternatives` | 1, 1 |
| `negative_zero_as_zero` | a value of `-0` returned as `0` | HP6 | `negative_zero` | 1, 1 |
| `unknown_members_returned` | the members a returned object holds kept whole, those the reader does not know included | HP6 | `unknown_member` | 3, 9 |
| `review_as_it_holds` | a review returned as the record holds it, whatever it holds | HP6 | a review's way | 5, 12 |
| `counts_as_doubles` | a count or an index written as a double | HP6 | `met`, `alternatives` | 5, 9 |
| `statistics_status_object_emptied` | a constant's statistics read by the block's shape alone, so that its status object comes back empty (the fault fuzz target 4 found) | HP6 | `statistics_withheld` | 1, 1 |
| `labelled_before_step_4` | `hash_not_checked` on a read that ended before step 4 (the S2 design's HP11 mutant) | HP11 | `before_step_4` | 11, 6 |
| `labelled_beside_the_hash_suite` | `hash_not_checked` on a read under the hash suite | HP11 | any kind that reaches step 4 | 1, 1 |

### HP12's mutants

`test_model_mutants.py`. Of the implementation, injected as the other groups' are: a step that stops at its
first fault (the S2 design's HP12 mutant, killed on two faults of one step, B5), the design's mutants of HP1
to HP11 that a result can show, taken from their modules, the broken status object that reports its token,
the fault HP12 found, and open point 1's request half as the implementation read it before S2a-4's fix round.
Of the model, applied to `tests/reference/read_model.py` while the core stays as it is:
its faults no case file kills, and five of the ten one case file alone kills. Each dies within the `ci`
profile's examples at both sizes, at an example that shows one of the parts, ways, steps or planted rules it
names; a search marked "planned" draws step 8's faults among those named first, or the first part's constants
at a boundary, as HP3's planned searches do, where HP12's own draws meet the fault too seldom for a safe
margin (each measured over six to twelve random seeds). Kills in the relations shard, 2026-10-17.

| Mutant | Fault | Part | Dies at | Examples |
|---|---|---|---|---|
| `step_0_stops_at_its_first_fault` | step 0 gives its first reason only | two of one step | `step_0` | 1, 1 |
| `step_8_stops_at_its_first_fault` | step 8 gives its first reason only | two of one step | `step_8` | 2, 2 |
| `step_9_stops_at_its_first_fault` | step 9 gives its first reason only | two of one step | `step_9` | 6, 40 |
| `step_10_stops_at_its_first_fault` | step 10 gives its first reason only | two of one step | `step_10` | 4, 5 |
| `broken_status_object_reports_its_token` | a status object that breaks its shape gives its token's `unknown_token` too | unpinned | `broken_status_object` | 91, 8 |
| `declaration_names_ignored` | a slip of a requirement's `field`, or of its conditions' `reason` or `consequence`, ignored | unpinned | `names_a_declaration_gives_a_requirement` | 50, 60 |
| `implied_members_of_the_other_kind_ignored` | an implied value's member of the other kind's shape, and a slip of one, ignored | unpinned | `implied_member_of_the_other_kind` | 41, 6 |
| `condition_unchecked_without_its_condition` | HP1's | faults | `unchecked` | 661, 10 |
| `value_beside_condition_outside` | HP2's | faults | step 10's ending faults | 149, 6 |
| `unknown_tokens_ignored` | HP3's: an unknown token ignored | faults | `step_8` | 90, 26 |
| `missing_represents_accepted` | HP3's (planned) | faults | `statistics_members.represents_missing` | 1, 1 |
| `null_read_as_absent` | HP3's (planned) | faults | `condition_tokens.set_or_measured_null`, `provenance.source_null` | 1, 1 |
| `unknown_condition_names_checked` | HP3's (planned) | faults | `condition_tokens.name_unknown` | 1, 1 |
| `specimen_facts_merged_across_sections` | HP4's | values | `another_section` | 82, 53 |
| `unknown_members_returned` | HP5's and HP6's: an unknown member returned | values | `unknown_member` | 3, 3 |
| `expanded_uncertainty_divided_by_its_k` | HP6's | values | `valued`, `alternatives` | 3, 3 |
| `floating_point_as_written` | HP7's (planned) | values at a boundary | `at_a_boundary` | 9, 204 |
| `strict_inequalities` | HP7's | values | `valued`, `alternatives` | 1, 1 |
| `plus_minus_ignored` | HP7's (planned) | values at a boundary | `at_a_boundary` | 11, 79 |
| `plus_minus_makes_not_met` | HP7's (planned) | values at a boundary | `at_a_boundary` | 11, 79 |
| `nfkc_before_comparing` | HP8's | faults | `steps_9_and_10` | 2, 2 |
| `case_folded` | HP8's | faults | `steps_9_and_10` | 2, 2 |
| `section_facts_win` | HP9's | values | `valued`, `alternatives` | 281, 6 |
| `hash_over_members_as_written` | HP10's (B7) | values | `valued`, `alternatives` | 11, 6 |
| `labelled_before_step_4` | HP11's | early | `before_step_4`, `stores` | 2, 2 |

| Fault of the model | Part | Dies at | Examples |
|---|---|---|---|
| `plurals_not_slips` | unpinned | `plural_of_two_characters` | 10, 3 |
| `member_checked_off_its_row` | unpinned | `form_off_its_row` | 117, 6 |
| `composition_checked_beyond_its_basis` | unpinned | `composition_basis_off_its_row` | 49, 7 |
| `broken_status_object_reports_its_token` | unpinned | `broken_status_object` | 91, 8 |
| `members_of_the_other_kind_read` | unpinned, at the open point's refusal or the implied value's | `members_of_the_other_kind`, `implied_member_of_the_other_kind` | 41, 5 |
| `members_of_the_other_kind_ignored` | unpinned, at the open point's refusal or the implied value's | `members_of_the_other_kind`, `implied_member_of_the_other_kind` | 41, 5 |
| `slips_of_alternatives_ignored` | unpinned | `alternatives_slip_beside` | 1, 1 |
| `declaration_names_not_named_in_a_request` | unpinned | `names_a_declaration_gives_a_requirement` | 50, 60 |
| `population_level_checks_stop_at_a_missing_member` | unpinned | `checks_beside_a_broken_object` | 6, 37 |
| `dof_token_unchecked_under_student_t` | unpinned | `checks_beside_a_broken_object` | 19, 59 |
| `every_status_object_an_unstated_kind` | unpinned | `checks_beside_a_broken_object` | 7, 127 |
| `every_forms_member_named_at_a_field` | unpinned | `another_forms_member_slipped` | 2, 2 |
| `input_specimens_optional` | faults (planned) | `derivation.input_specimens_missing` | 1, 1 |
| `hash_not_checked_before_step_4` | early | `request`, `before_step_4`, `stores` | 1, 1 |
| `token_condition_unit_accepted` | faults | `unit_token_condition` | 58, 34 |
| `plus_minus_units_unchecked` | faults | `unit_plus_minus` | 8, 11 |
| `implied_values_compared_by_value` | unpinned | `implied_zero_beside_minus_zero` | 4, 10 |
| `stated_without_origin_unreported` | values | `valued`, `alternatives` | 127, 209 |

Listed, with the reason no read S2 builds shows them: `evidence_entry_provenance_unchecked` and
`entry_withheld_in_part_read` (an evidence entry, read by S2b-2: the core raises at it),
`unit_returned_without_its_reason` (only `biocompatibility.evidence` registers a unit held as a status
object), `two_nominals_for_one_field`, `nominal_ignored_over_alternatives` and `nominal_applied_under_no_pick`
(the core raises for any acceptance but an implied condition until S2b-2), and `results_share_the_record` (a
shared object never shows in JSON; HP6 holds the core to sharing nothing). The design's other mutants not
searched here: HP6's `upper: none` as infinity (S2b-1) and its result sharing the stored object (JSON again).

### HP4 and HP10's mutants

`test_invariance_mutants.py`, at the ways (HP4) and kinds (HP10) each names; relations shard, 2026-10-17.

| Mutant | Fault | Killed by | Dies at | Examples |
|---|---|---|---|---|
| `specimen_facts_merged_across_sections` | a field's specimen holds every section's facts (the S2 design's HP4 mutant) | HP4 | `another_section_specimen` | 7, 66 |
| `every_field_checked` | step 8 checks every field of the record | HP4 | `another_field` | 1, 1 |
| `every_section_specimen_checked` | step 8 checks every section's specimen | HP4 | `another_section_specimen` | 6, 3 |
| `section_specimen_unchecked` | the read field's own section's specimen not checked (HP3's) | HP4, refusal | `own_section_specimen` | 1, 1 |
| `hash_over_members_as_written` | the recomputed hash taken over the members in the order the source writes them (the S2 design's HP10 mutant, B7) | HP10 | any kind | 3, 7 |
| `integers_read_as_integers` | a number spelled without a fraction or exponent read as an integer | HP10 | any kind | 1, 1 |

### The monotonicity relations' mutants

`test_monotonicity_mutants.py`, each searched with the relation it names (the spike's mutants that S2's forms
reach, under its names where the core has them; with a world's trigger built in where the relation draws a way
first). Over twelve random seeds a search, each died within 927 examples, `floating_point_as_written` the
slowest. Relations shard, 2026-10-17.

| Mutant | Fault | Relation | Examples |
|---|---|---|---|
| `row_requirements_ignored` | a condition the row requires, absent, not checked (the spike's `absent_required_skipped`) | N1r | 2, 2 |
| `required_with_ignored` | a condition another requires with its token not checked | N1r | 6, 4 |
| `requested_absent_skipped` | a condition the request names and the record lacks skipped | N1r | 8, 6 |
| `origin_default` | an absent origin read as `measured_by_contributor` | N2 | 454, 254 |
| `status_object_passes` | a condition held as a status object gives a met entry | N3r | 77, 5 |
| `status_in_any_member` | a status object in `origin` passes step 8 | N3r | 2, 2 |
| `plus_minus_widens` | a bound widens the tolerance instead of narrowing it | N4 | 2, 2 |
| `tolerance_inverted` | a value met where it lies outside the tolerance | N5r | 2, 2 |
| `missing_operating_met` | a tolerance with no operating condition passes step 0 and gives a met entry | N6 | 170, 48 |
| `implied_overrides_a_stated_value` | an implied condition overrides a stated one (`implied_overrides`) | N8 | 2, 2 |
| `tolerance_inverted_widened` | as `tolerance_inverted` | P1 | 2, 2 |
| `plus_minus_widens_removed` | as `plus_minus_widens` | P2 | 2, 2 |
| `accept_list_as_its_last_token` | an accept list read as its last token alone | P3 | 2, 2 |
| `operating_conditions_checked` | every condition the request operates checked, as one with no tolerance | P4 | 2, 2 |
| `sd_ignored` | an `sd` or unstated plus or minus ignored | S1 | 3, 5 |
| `status_object_read_as_met` | as `status_object_passes` | S2 | 1, 1 |
| `not_applicable_anywhere` | `not_applicable` read as met on any condition | S2 | 3, 41 |
| `floating_point_as_written` | section 5's comparisons in floating point (`float_compare`) | S5 | 209, 3 |

The unrestricted twins, N1 (any condition removed) and N3 (any member made a status object), fail on the core
as they must, by their counterexamples drawn first: an unchecked condition beside a met read, removed (1, 1);
`unstated` where an implied condition fills it (12, 11).

## Audits

`conftest.py` runs every test here under the two audits of `audits.py`:

- **draw rejection**: a test that throws away more than 40% of its draws (by `assume` or `.filter`) fails,
  and so does a Hypothesis test whose draws the audit could not see;
- **features**: a property declares, with `@pytest.mark.features(name=least_share, ...)`, the least share of
  its examples that must show each feature the specification distinguishes, and records each example's
  features with `support.feature`. A share below its least fails, and so does a feature recorded but not
  declared. Each least share is about a third of the share measured at both sizes. At `ci` and `deep` a share
  is judged only where the run's examples make at least 20 expected at the least share: `ci` judges the shares
  of 1% or more, and `deep` every share declared (the least is 0.2%); `dev` holds a declared feature to a
  floor instead (below). A property that draws one of several features alike as its first choice, as a
  refusal property draws its fault, names them with `@pytest.mark.drawn(name, ...)` instead. At `ci` each is
  held to its draw floor: Hypothesis keeps an example's first choice through up to 8 examples (the example
  and the mutations it makes of it), so the floor counts 2,000 examples as 250 draws, each shown in 5
  examples (5.7 to 7.0 measured, by fault), and is the count a fault falls below with a probability of at
  most 1e-6. A floor below 10 cannot be judged, and fails: those features must be drawn among fewer. `deep`
  holds each to a third of its share, and `dev` to its draw floor where that is at least 10, judging no other
  (below). A property that knows the chance that one draw shows each feature declares it with
  `@pytest.mark.chances(name=chance, ...)`, as the writer schema's acceptance properties do with their shares
  measured at `ci`: at `ci` each is held to the draw floor of its chance, a floor below 10 failing (draw it
  more often, its family in parts); at `dev` to that floor where it
  is at least 10, judging no other; and at `deep` to a third of its chance. Hypothesis's clusters make a least
  share less safe than independent examples would: at the gate of 20 expected, a feature shown by whole
  clusters falls below its least share in about one run in a hundred (`audits.JUDGED_FROM`). So the json and
  records shards' properties declare by its chance each feature whose least share failed a run with a
  probability above 1e-6 at `ci` or 1e-3 at `dev` (the bound `dev` was held to then), computed from the
  clusters measured on each property (2026-10-15); RFC 8785's values and HP3's parts draw their features often
  enough to have a floor. Steps 9 and 10's properties draw each kind first among at most ten (a floor of 30 at
  `ci`), and declare it drawn;
  their HP3's two faults are declared by their chance, one in four, and HP7's end of the span and a bound's
  window by the least share measured. The result's properties draw their kind first among at most nine, and
  HP6 declares its field's `-0`, its review's way, its statistics status object and its unknown member by
  their chances. HP12's parts draw their kinds, steps or planted rules first (at most ten), HP4 its ways and
  HP10 its kinds, each declared drawn; each monotonicity relation declares the least share of its examples on
  which it held (applied, a verdict on both sides, not vacuous: a third of the share measured at both sizes),
  and those that draw a way first declare their ways drawn. For each such
  property, five of steps 9 and 10's and two of the result's (HP1 by a kind, HP6 by a chance),
  `tests/unit/test_audit_controls.py` runs it at `ci`'s examples with a generator that stops producing one of
  those features: its audit fails, on that feature alone. One of the five runs a parametrised property, HP8's
  other units, on one parameter, its `plus_minus` place, held to the features that parameter's marks declare,
  as the audit holds each parameter to its own;
- **each profile's rule** (`audits.RULES`): `ci` holds the drawn features and those declared by their chances
  to their draw floors, and a declared feature to its least share; `deep` holds each feature to its least
  share, a third of its share or chance where it is drawn or declared by its chance; and `dev` holds every
  feature to its draw floor where that is at least 10, judging no other (2026-10-18). There a declared feature
  counts as drawn with three times its least share, and is never held above its least share. So, at the chance
  its floor assumes, no feature `dev` judges fails a correct run with a probability above 1e-6 by the floors'
  model, as no floor at `ci` does; a feature whose measured share falls below the chance its floor assumes
  fails a correct run more often, and is fixed where it is declared (a lower least share or chance), not in
  the rule. With 200 examples the model counts 25 draws, and a floor reaches 10 only at
  a chance of one half or more: `dev` judges the features drawn among two, those declared by a chance of one
  half or more, and declared features of a least share of about 0.17 or more (35 features of the properties on
  main, 2026-10-18). The features it leaves are judged at `ci` and `deep`. Until 2026-10-18 `dev` held a
  declared feature to its least share where 20 were expected, and features drawn among three or fewer to a
  third of their share, with a bound of about 1e-3 a feature set before CI's per-commit job (#30) ran every
  property at `dev` once for each commit: three of about 75 `dev` jobs of pull requests #35 and #37 failed so
  by chance that day, each a feature drawn among three. `tests/unit/test_audits.py` holds those three runs'
  counts, pins what `ci` and `deep` judge (in runs of any size, with `interesting` and `invalid` draws), and fails if a feature judged by a floor, at any profile and any
  declaration on a grid, fails a correct run with a probability above 1e-6 by the model.

An audit judges random draws, so a sound property fails it now and then by chance. By the floors' model, each
feature judged at `dev` fails a correct run with a probability of at most 1e-6, and a run of every property on
main at most about 1.3e-5 in all (3.2e-5 with the properties of pull requests #35 and #37). The model takes
the fewest draws a run can hold, and overstates: it gave the least shares `dev` judged until 2026-10-18 about
one failure a run of every property with #35's and #37's (0.36 on main), where CI's `dev` jobs failed about
one run in 25. Over seeds 1 to 100, run locally at `dev` on #37's head (every audited property then written),
the audited properties failed 2 runs of 100 by the rule `dev` had (features drawn among three, in 5.5% and
9.5% of the examples, against 11%), and none of the 8,900 audits failed by its rule now (2026-10-18). The
bound rests on the chance each floor assumes. Over those runs each declared feature of main that `dev` judges
showed 0.94 to 1.26 times the share its floor assumes, three times its least share; of the features declared
by their chances, measured at `ci`, `test_output_matches_rfc8785`'s `non_ascii_character` showed 0.57 at `dev`
against 0.66, which puts its floor's false failure at about 3e-5 by the model, as before 2026-10-18. At `ci`
each floor holds a feature to 1e-6 as well; the least shares of the properties whose clusters were measured,
the json and records shards' and the writer schema's acceptance properties, fail a run of them with a
probability of about 2e-6 (`audits.py`); the other least shares judged at `ci` have no figure. CI draws at
random since #38 ("Profiles and sizes"), so each of its `dev` runs is a sample of its own: by the model, a
pull request's 50 or so `dev` jobs, the test matrix's five Pythons and the per-commit job's one for each
earlier commit, fail by chance with a probability of at most about 1.6e-3; the controls job, derandomised,
adds nothing (`.github/workflows/README.md`). An audit that
fails a run Hypothesis drew at random names the seed of that run and how to draw it again: the failing job's
own pytest command, at its profile and on its Python, with `-k <test> --hypothesis-seed=<seed>`, or with
`@seed(<seed>)` on the test. A run that collects less draws other examples under the same seed, since
Hypothesis also draws constants from the modules outside `tests/` that are loaded: on the whole suite, a
property's run replayed exactly under the job's command with `-k`, on one worker or four, and drew 25 of its
200 examples otherwise from its file alone (2026-10-17; `tests/unit/test_audit_replay.py` holds the message to
this). To tell chance from a fault, dispatch `repeat.yml` on the failing test at its profile (`tests/README.md`,
"Repeat runs on CI"): after a chance failure nearly every run passes, while a change that lowers a share fails
most runs. It cannot measure rates this small, since 200 runs without a failure bound the rate at 1.5%; it
tells a rare failure from a frequent one.

## Adding a property

Write the check as a function of the implementation and the example, and the property as a `test_...` function
that records its features and calls the check. Declare the features with their least shares, or their chances,
measured. Add a mutant that the property must kill, to the mutant file of its group, and the module to a
shard. Never set `max_examples` on a property: the profile decides it. Build strategies so that they draw what
they need rather than filter it, take their size from `strategies.SIZE`, and build each strategy once rather
than in every draw: Hypothesis spends more building and checking a strategy than drawing from it.

# Property tests

Hypothesis properties of the core, in four groups, and of the writer schema, in a fifth.

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
and a run given `--hypothesis-seed` draws there what it draws on any machine. Until 2026-10-17 it did not:
GitHub sets `CI`, on which Hypothesis loads its built-in `ci` profile at import, and the profiles, registered
without a parent, inherited its `derandomize=True`, which Hypothesis applies before any seed: the test matrix
at `dev` and the Hypothesis job at `ci` drew, for each property, the same examples on every run of the same
code. Every profile also suppresses the `too_slow` health check, as that built-in profile did on CI: a draw
slowed by a loaded runner is not a fault of the code. The mutant searches, the audits' tests and controls, and
T1's variants are derandomised by their own settings, on purpose.

Every profile keeps its examples in `.hypothesis/examples` at the repository root (git-ignored, cached by CI),
so an example that failed once, under `deep` or any other profile, is tried first on every later run; a
failure prints a blob that replays it anywhere.

## Shards

CI runs the groups in six shards side by side, each in a job of its own: `pytest tests/property --shard json`,
`--shard records`, which holds the record and step-8 groups, `--shard writer`, `--shard agreement`, the two
validators' agreement (below), `--shard step8_mutants`, step 8's mutant searches, which keep no example
database and were most of the records shard's time, and `--shard conditions`, steps 9 and 10's group with its
mutant searches, which take seconds and set no example database (112 s on four local workers at `ci`,
2026-10-16; `SHARDS` in `tests/conftest.py`). Each family of faults is a property of its own, run in parallel.
The agreement shard's drawn properties run python-jsonschema on every example, and are the longest tests of
any shard: on 4 workers locally (2026-10-17), the shard took 4.0 and 8.0 minutes at `ci`, its longest property
1.9 and 4.7 (at loads of 4 to 7 and 15 to 17), and 112 minutes at `deep`, its longest property 70 (load 18 to
30). `deep` has not yet run on CI, whose cores are 1.6 to 4 times slower: there it may not fit in the 6 hours
GitHub gives a job. Each module is in exactly one shard (`tests/unit/test_source_files.py`), and each shard
but step 8's mutant searches' keeps its own example database in CI.

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
took as `examples_to_kill`, which `--junitxml` writes out. Hypothesis also draws constants from the project's
modules a process has imported, the tests excepted, and every shard run imports every property module: an
import added to one can move kills in every shard, so compare counts only between runs that import the same
modules. A fault that died only at the original size would mean the small size misses it.

CI's test matrix runs the mutant modules, `test_*mutants*`, on the supported range's ends alone
(`--property-controls` in `tests/conftest.py`), so a mutant module holds mutant searches only. The checks of
the mutants' own code, which run on every Python, are in modules of their own: `test_mutant_view.py` (the hash
mutants' view, without a fault, is the core's), `test_value_field_mutant_table.py`,
`test_writer_mutant_table.py` and `test_condition_mutant_table.py`.

`test_mutants.py` also gives the one-slip relation twelve faults, each killed by (9) (its strategy has no size,
so both sizes take the same examples; measured 2026-10-15):

| Mutant | Fault | Examples |
|---|---|---|
| `substitution_missed`, `insertion_missed`, `underscore_missed`, `swap_missed`, `plural_missed` | a kind of slip missed | 19, 1, 28, 3, 23 |
| `underscore_read_as_a_character` | an underscore added is named a character added | 28 |
| `two_characters_added_one_slip` | two characters added at the end are one slip | 38 |
| `swap_of_any_two_characters` | two characters swapped far apart are one slip | 11 |
| `ies_plural_missed`, `es_plural_missed`, `irregular_plurals_missed` | a plural section 10 lists missed | 155, 38, 114 |
| `empty_word_made_plural` | the empty string between two underscores is a word, `s` its plural | 333 |

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
took, at the small and the original size (measured 2026-10-15, S2a-2's fix round).

Two of the first 25, `missing_represents_accepted` and `named_state_text_unchecked`, have had planned searches
since 2026-10-16: searched with HP3 whole, each survived 2,000 examples at the small size once the suite held
`scripts/report_test_durations.py`, which its unit tests import, and died where their module ran alone. At
S2a-3's head, `named_state_text_unchecked` also survived 2,000 examples at the original size where its shard
ran alone, as CI runs it, and died where the whole suite ran: S2a-3's code added constants. Hypothesis (6.169)
draws, among its values, constants it finds in the project's modules the process has loaded, test modules
aside, so the examples a derandomised search meets change with the code and with what else a process imported.
Emptying that pool, the search killed it alone and after the unit tests alike (measured 2026-10-16). Planned,
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
| `basis_any_string` | a condition's and a fact's `basis` take any string | HP3 | `condition_tokens.basis_unknown`, `specimen_tokens.fact_basis_of_another_member` | 14, 10 |
| `condition_status_refuses_its_own_shapes_members_only` | a condition's status object refuses only its own shape's members, so `token` beside a numeric condition's passes | HP3 | `condition_tokens.status_beside_a_token` | 1, 1 |
| `token_known_within_its_kind` | a condition's `token` knows only the conditions' tokens and a fact's only the facts', so `tube` in `tissue_state` is `unknown_token` | HP3 | `condition_tokens.token_of_a_fact`, `specimen_tokens.fact_token_of_a_condition` | 1, 1 |
| `token_condition_unit_unchecked` | a token condition's `unit` takes anything | HP3 | `condition_tokens.token_condition_unit_not_a_string` | 1, 1 |
| `label_on_any_table` | a label goes on a table whatever its axis | the label's rule | its oracle, on a table on its row's axis | 54, 59 |
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
derandomised search took, at the small and the original size (measured 2026-10-16, S2a-3's fix round).

Seven of these are the mutants of S2a-3's review that survived the whole suite (its M2), each a rule no test
checked: `implied_not_located`, `located_at_without_its_hash`, `accept_list_case_folded`,
`accept_list_by_prefix`, `unknown_name_status_read_as_unstated`, `only_the_first_plus_minus_unit` and
`implies_value_not_an_object_ignored`. The first two and the last die to the deterministic tables written for
them; the other four survived 2,000 examples at both sizes until HP7's token kinds drew accept lists holding
strings outside the row, its `unknown_name` kind a status object as often as a value, and HP8's `plus_minus`
place the unit in either entry of two.

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
| `accept_list_by_prefix` | a token matched by an entry of the accept list that begins with its first three characters | HP7, table | any of its examples | 122, 122 |
| `unknown_name_status_read_as_unstated` | a name the reader does not know, held as a status object, read as `condition_unstated` | HP7, table | any of its examples | 5, 5 |
| `unknown_name_read_as_unstated` | a name the reader does not know is `condition_unstated` | HP7, table | any of its examples | 5, 5 |
| `required_with_ignored` | a condition another requires with its token is not checked | HP7, table | any of its examples | 3, 3 |
| `row_requirements_ignored` | the row's required conditions are not checked | HP7, table | any of its examples | 308, 308 |
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
| `spaces_ignored` | spaces and zero-width spaces dropped from a unit | HP8, another unit | `spaced` | 11, 46 |
| `a_status_object_where_a_string_is_registered` | a status object takes a string's place | HP8, another unit | `status_object` | 26, 12 |
| `plus_minus_units_unchecked` | a `plus_minus` entry's unit not compared | HP8, another unit | `plus_minus` | 2, 2 |
| `only_the_first_plus_minus_unit` | only the first `plus_minus` entry's unit compared | HP8, another unit | `plus_minus` | 9, 69 |
| `token_condition_units_unchecked` | a `unit` on a token condition passes | HP8, another unit | `token_condition` | 150, 3 |
| `section_facts_unchecked` | the section's facts' units not compared | HP8, another unit | `section_fact` | 34, 11 |
| `input_facts_unchecked` | a derived value's input facts' units not compared | HP8, another unit | `input_fact` | 4, 21 |
| `condition_dropped_from_unit_mismatch` | a condition's `unit_mismatch` carries no condition | HP8, another unit | `condition`, `plus_minus`, `token_condition` | 2, 2 |
| `plus_minus_against_the_field_unit` | a `plus_minus` unit compared with the field's unit | HP8, the registered unit | any of its examples | 1, 1 |
| `facts_against_the_field_unit` | a fact's unit compared with the field's unit | HP8, the registered unit | any of its examples | 1, 1 |
| `step_10_after_a_refusal_at_step_9` | step 10 runs after step 9's `not_met` | HP3 | a fault of step 9 | 1, 1 |
| `first_unit_reason_only` | step 9 gives its first reason only | HP3 | a fault of step 9 | 1, 1 |
| `unknown_reasons_dropped_beside_not_met` | step 10's `unknown` reasons dropped beside a `not_met` | HP3 | `unchecked`, `unstated`, `unknown_name`, `uncertain` | 7, 198 |
| `conditions_withheld_from_a_refusal` | a read step 10 ends returns no `conditions` | HP3 | `outside`, `range_outside`, `not_accepted`, `implied_outside` | 7, 7 |
| `disagreement_checks_the_others` | two implied conditions that disagree, and the conditions checked all the same | HP3 | `disagreeing` | 155, 111 |
| `unknown_members_returned_in_an_entry` | a condition's entry returns members the reader does not know | HP5 | `condition`, `plus_minus_entry` | 5, 10 |
| `two_slips_refused_in_a_request` | a request's names two characters off a named one refused | HP5 | any of its examples | 4, 4 |
| `unknown_request_members_refused` | every member a request's place does not name refused | HP5 | `operating`, `requirement_condition`, `tolerance`, `implied`, `implied_record`, `implied_value` | 4, 3 |

A mutant first written for HP5, step 0 keeping an implied value's unknown members, was dropped: no read can
tell it from the core, since step 10 returns a filled condition with the members the reader knows alone.

## Audits

`conftest.py` runs every test here under the two audits of `audits.py`:

- **draw rejection**: a test that throws away more than 40% of its draws (by `assume` or `.filter`) fails,
  and so does a Hypothesis test whose draws the audit could not see;
- **features**: a property declares, with `@pytest.mark.features(name=least_share, ...)`, the least share of
  its examples that must show each feature the specification distinguishes, and records each example's
  features with `support.feature`. A share below its least fails, and so does a feature recorded but not
  declared. Each least share is about a third of the share measured at both sizes. A share is judged only
  where the run's examples make at least 20 expected at the least share: `ci` and `deep` judge every share,
  `dev` those of 10% or more. A property that draws one of several features alike as its first choice, as a
  refusal property draws its fault, names them with `@pytest.mark.drawn(name, ...)` instead. At `ci` each is
  held to its draw floor: Hypothesis keeps an example's first choice through up to 8 examples (the example
  and the mutations it makes of it), so the floor counts 2,000 examples as 250 draws, each shown in 5
  examples (5.7 to 7.0 measured, by fault), and is the count a fault falls below with a probability of at
  most 1e-6. A floor below 10 cannot be judged, and fails: those features must be drawn among fewer. `deep`
  holds each to a third of its share, and `dev` judges none. A property that knows the chance that one draw
  shows each feature declares it with `@pytest.mark.chances(name=chance, ...)`, as the writer schema's
  acceptance properties do with their shares measured at `ci`: at `ci` each is held to the draw floor of its
  chance, a floor below 10 failing (draw it more often, its family in parts); at `dev` to that floor where it
  is at least 10, judging no other; and at `deep` to a third of its chance. Hypothesis's clusters make a least
  share less safe than independent examples would: at the gate of 20 expected, a feature shown by whole
  clusters falls below its least share in about one run in a hundred (`audits.JUDGED_FROM`). So the json and
  records shards' properties declare by its chance each feature whose least share failed a run with a
  probability above 1e-6 at `ci` or 1e-3 at `dev`, computed from the clusters measured on each property
  (2026-10-15); RFC 8785's values and HP3's parts draw their features often enough to have a floor. Steps 9
  and 10's properties draw each kind first among at most ten (a floor of 30 at `ci`), and declare it drawn;
  their HP3's two faults are declared by their chance, one in four, and HP7's end of the span and a bound's
  window by the least share measured. For each such property, and five of steps 9 and 10's,
  `tests/unit/test_audit_controls.py` runs it at `ci`'s examples with a generator that stops producing one of
  those features: its audit fails, on that feature alone. One of the five runs a parametrised property, HP8's
  other units, on one parameter, its `plus_minus` place, held to the features that parameter's marks declare,
  as the audit holds each parameter to its own.

An audit judges random draws, so a sound property fails it now and then by chance. From `audits.py`'s figures,
a run of every property at `dev` fails about once in 2,000 (5e-4, nearly all of it the json and records shards'
least shares, `card_accepted`'s 4e-4 the most), and a run at `ci` about once in 500,000 (2e-6). CI draws at
random since #38 ("Profiles and sizes"), so each of its `dev` runs is a sample of its own: the test matrix's
five Pythons make a push red by chance about once in 400 (2.5e-3), and the per-commit job adds 5e-4 for each
earlier commit it checks, about once in 220 for a pull request of five commits (4.5e-3); the Hypothesis job
adds about 2e-6, and the controls job, derandomised, nothing (`.github/workflows/README.md`). An audit that
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

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
  row does not give (maintainer, 2026-10-15). `value_fields.py` builds the fields from the text alone, never
  from the schema or the bindings it applies: tokens and each field's row from the vocabulary (generated from
  the specification), a specimen fact's members from `provenance.md` section 6.2's JSON shapes, and the rest
  from the member tables and rules each builder cites. A fault is one change the text says breaks a field (a
  member missing, a bound crossed, a token of another member's list or of none, a status token its row does
  not allow, a rule across objects broken, a unit other than the registered one, a field under a name or
  holding what its row does not give), 166 of them in ten families, each drawn as often as another of its
  family on a field, or a body, planned so that its place exists; a family of more than 15 faults is drawn
  in parts of at most 15, each a property of its own, so that the feature audit at `ci` can judge each fault
  (below).
  The refusal is checked on one the schema takes, the same but for the fault, so that it is the fault's.
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
  by the test itself, through step 8's shared check, since no read reaches a table before S3. Until steps 9 to
  13 are built, a read that passes step 8 raises `NotImplementedError`, the outcome "past step 8".
- **Tables:** (10) the table evaluator (`core/evaluate.py`; `record_format.md` section 6, table items 3 and 4;
  `read_side_contract.md` sections 5 and 7), the S3 design's HP17 to HP19, against an oracle written from the
  text (`test_evaluate_properties.py`). HP17: the evaluator agrees with it over drawn tables and operating
  values, never raising: where each value lies (at an edge, in the readable range, beyond an edge) exactly, and
  the number, a linear one bit for bit and a log-log one within 1e-15. HP18: a read at a knot that is no edge,
  or beyond the readable range's end where that is one, gives the stored `y` bit for bit, `-0` included. HP19:
  the knots that bracket a read are the interval the text names and its value lies between their two `y`; and
  over monotone `y` with no edge, reads are monotone. `tables.py` draws tables step 8 accepts by choices made
  first (the scheme; the magnitude: ordinary, any double, doubles a few units apart, or subnormal; edges;
  signed zeros; and a `source_range` absent, narrower, wider, across an end, or of one point), and reads each
  at every place table item 3 tells apart: each knot and edge, the readable range's ends and `source_range`'s,
  the double either side of each, both zeros, a value inside each interval with room, one beyond each end of
  the readable range, and the largest doubles. Each property first checks its table against the text's rules
  (`accepted`), a check that found two faults of the generator while it was written. The oracle compares as
  fractions, finds a read's interval by scanning every pair of knots, and computes in another arrangement, a
  linear value exactly and a log-log one in decimal at 80 digits where the evaluator works at 50; its own
  control is that it gives every number and refusal of the table evaluation cases.

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

CI runs the groups in four shards side by side, each in a job of its own: `pytest tests/property --shard
json`, which also holds the tables group, `--shard records`, which holds the record and step-8 groups, `--shard writer`, and `--shard
step8_mutants`, step 8's mutant searches, which keep no example database and were most of the records shard's
time (`SHARDS` in `tests/conftest.py`). The writer schema's properties validate each field with `jsonschema`
against the writer's value field, a choice among eight forms, which costs about 30 ms a field: so each family
of faults is a property of its own, run in parallel. Each module is in exactly one shard
(`tests/unit/test_source_files.py`), and each shard but the mutant searches' keeps its own example database in
CI.

## Mutants

`test_mutants.py` (JSON) and `test_record_mutants.py` (records) give the core one fault at a time and require
the property aimed at it to find the fault within the examples of the `ci` profile, at the small size and at
the original one. The faults include those the conformance runner's self-tests use, and faults that only some
sizes or contents could show: a nesting limit off by one, removal that stops at depth 2, sorting by one pass of
exchanges, a pattern searched where it must match in full, versions ordered as strings or as doubles, an
unreadable source ignored, the first of two differing copies read. Each test records the examples its kill
took as `examples_to_kill`, which `--junitxml` writes out. A fault that died only at the original size would
mean the small size misses it.

CI's test matrix runs the mutant modules, `test_*mutants*`, on the supported range's ends alone
(`--property-controls` in `tests/conftest.py`), so a mutant module holds mutant searches only. The checks of
the mutants' own code, which run on every Python, are in modules of their own: `test_mutant_view.py` (the hash
mutants' view, without a fault, is the core's), `test_value_field_mutant_table.py` and
`test_writer_mutant_table.py`.

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
unit and its `plus_minus` entries' (B1 to B12, with B5b), and four that tighten them (TB1 to TB4). Each names
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
`fact_unit_judged_at_step_8`) are searched with their property whole. The other 22 are the fix round's: the
eleven rules S2a-2's review found no test checked (M1; the fact unit's is `fact_unit_judged_at_step_8`), and
parts of the text HP3 had no fault for or could not tell from a missing member (M2). One,
`label_on_any_table`, dies to the label's rule. The other 21 each name the faults they must die at, and their
search is planned, as the writer's are: HP3 draws its first fault among them, and the kill must hold one.
Drawn with HP3 whole, 17 of those 21 were measured: each died within its 2,000 examples at both sizes but
`within_any_status` and `label_beside_an_unknown_form_as_on_a_constant`, which died at the original size alone
(884 and 845). HP3 whole meets one fault of 154 too seldom to kill each such mutant every time at `ci`, so the
planned search is what shows HP3 refuses each fault, and the region audit that HP3 draws it; each of the
review's eleven rules also has a deterministic read in `tests/unit/test_read.py`. The kill is the examples the
derandomised search took, at the small and the original size (measured 2026-10-15, S2a-2's fix round).

Two of the first 25, `missing_represents_accepted` and `named_state_text_unchecked`, have had planned searches
since 2026-10-16: searched with HP3 whole, each survived 2,000 examples at the small size once the suite held
`scripts/report_test_durations.py`, which its unit tests import, and died where their module ran alone.
Hypothesis (6.169) draws, among its values, constants it finds in the project's modules the process has loaded,
test modules aside, so the examples a derandomised search meets change with the code and with what else a
process imported. Planned, each dies at its first example at both sizes, alone, after the whole suite's
collection, on Python 3.11 and 3.15. The other 23 searched whole may meet the same at any change.

| Mutant | Fault | Killed by | Dies at | Examples |
|---|---|---|---|---|
| `unknown_tokens_ignored` | a token the reader knows for no member of its name is accepted | HP3 | any of its property | 3, 12 |
| `unknown_token_read_as_a_shape_fault` | such a token gives `form_invalid` | HP3 | any of its property | 3, 12 |
| `status_tokens_unchecked` | a status object takes any status token | HP3 | any of its property | 11, 137 |
| `members_beside_a_status_ignored` | a status object beside a member of the shape it stands for is read as one | HP3 | any of its property | 121, 12 |
| `missing_represents_accepted` | a statistics block without `represents` passes (the S2 design's HP3 mutant) | HP3 | `statistics_members.represents_missing` | 1, 1 |
| `null_read_as_absent` | `null` in an optional member reads as the member absent (HP3's) | HP3 | any of its property | 322, 401 |
| `unknown_condition_names_checked` | a condition name the reader does not know is checked as a numeric condition (HP3's "read as known") | HP3 | any of its property | 128, 30 |
| `plus_minus_kinds_unchecked` | a `plus_minus` list is checked only as a list | HP3 | any of its property | 3, 24 |
| `range_order_unchecked` | a range's `lo` may lie above its `hi` | HP3 | any of its property | 534, 139 |
| `counts_not_whole` | `n_specimens` takes any number | HP3 | any of its property | 192, 318 |
| `conditional_members_unchecked` | `population_level`, `n_sources` and `precision_conditions` may sit beside any `represents` | HP3 | any of its property | 170, 48 |
| `uncertainty_rules_unchecked` | an uncertainty's coverage, `dof` and precision rules go | HP3 | any of its property | 20, 125 |
| `named_state_text_unchecked` | a disease or treatment state's text may sit beside any token, or be missing | HP3 | `specimen.fact_text_beside_normal`, `specimen.fact_treated_without_text` | 1, 1 |
| `fixed_basis_unchecked` | `mimics`'s basis takes either token, not the one its row fixes | HP3 | any of its property | 360, 98 |
| `fact_unit_judged_at_step_8` | a fact's unit is judged at step 8, `s` alone and a status object of the five tokens only, where step 9 alone compares it (a default for the maintainer, 2026-10-15) | HP3 | any of its property | 224, 1297 |
| `record_structure_unchecked` | a slip in the envelope, the body or a section is ignored | HP3 | any of its property | 58, 111 |
| `section_specimen_unchecked` | a section's `specimen` is not checked | HP3 | any of its property | 70, 4 |
| `first_refusal_only` | step 8 gives its first reason only (the S2 design's HP12 mutant, on HP3's two-fault draws) | HP3 | any of its property | 3, 12 |
| `slip_by_substitution_missed` | the one-slip relation misses a character substituted | HP3 | any of its property | 102, 111 |
| `slip_by_insertion_missed` | it misses a character inserted or deleted | HP3 | any of its property | 22, 57 |
| `slip_by_swap_missed` | it misses two adjacent characters swapped | HP3 | any of its property | 9, 83 |
| `slip_by_plural_missed` | it misses a word made plural or singular | HP3 | any of its property | 36, 6 |
| `slip_by_underscore_missed` | it misses an underscore added or removed | HP3 | any of its property | 237, 188 |
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

The S2 design's HP5 mutant, an unknown member returned, waits for the result's members (S2a-4).

### The table evaluator's mutants

`test_evaluate_mutants.py`. Each fault replaces one of `core/evaluate.py`'s module-level functions, which the
evaluator looks up when it runs, and each mutant names the assertions its kill may fail: an assertion's
message begins with its label, and the search fails where the first failure is another's. HP17 checks where
every operating value lies before any number, so that a fault of range or edge dies as one, not by the end
value it leads to. The first eight are the S3 design's (section 6.6). Of the other nine, six are broken
evaluators of the table evaluation suite's README made a reader's, the text's rules since the design among
them (no number beyond an edge, the readable range's end value); one raises where a read returns a refusal
(the code design's rule 1); and two reach the assertions no design mutant does (`interval`, `monotone`). The
kill is the examples the derandomised search took, at the small and the original size (measured 2026-10-17,
the `json` shard at `ci`).

| Mutant | Fault | Killed by | Dies at | Examples |
|---|---|---|---|---|
| `bracket_search_off_by_one_at_a_knot` | the bracket search one past a knot (`bisect_right`): a knot read through the interval above it, the last one past the end | HP17 | `raised`, `value` | 1, 1 |
| `loglog_interpolated_linearly` | a log-log table interpolated linearly | HP17 | `value` | 3, 8 |
| `log10_for_x_beside_ln_for_y` | the log-log slope taken with `log10` for `x` and `ln` for `y` | HP17 | `value` | 3, 8 |
| `formulas_in_doubles` | `read_side_contract.md` section 7 item 2's formulas in doubles, as written, a knot read through the interval below it (one unit off at upper knots; dividing by zero between adjacent doubles) | HP17 | `raised`, `value` | 2, 2 |
| `source_range_ignored` | the readable range is `[x[0], x[-1]]` | HP17 | `position` | 5, 5 |
| `source_range_widening` | a `source_range` wider than `x` widens the readable range | HP17 | `position` | 5, 5 |
| `knot_through_a_fraction` | a knot's `y` returned through a fraction, which loses `-0` | HP18 | `stored` | 11, 8 |
| `t_from_the_upper_knot` | `t` computed as `(x - x1) / (x1 - x0)` | HP19 | `between` | 18, 5 |
| `extrapolated_beyond_an_edge` | beyond an edge from the readable range, the end value | HP17 | `position` | 5, 7 |
| `range_judged_before_the_edge` | the readable range judged before the edge, so that an edge outside it reads as outside (the S3 design's HP20 mutant) | HP17 | `position` | 5, 8 |
| `edges_ignored` | no operating value lies at an edge | HP17 | `position` | 3, 7 |
| `end_value_at_the_ends_of_x` | outside the readable range, the value at `x[0]` or `x[-1]`, as NumPy's `interp` clamps | HP17 | `value` | 5, 5 |
| `refusal_raised` | at or beyond an edge, an exception in place of no number | HP17 | `raised` | 3, 7 |
| `ends_excluded` | the readable range's ends excluded (`<`) | HP17 | `position` | 1, 1 |
| `below_an_edge_from_the_interval_above` | just below an edge, the interval above it | HP17 | `value` | 3, 8 |
| `between_knots_the_interval_above` | between two knots, the interval above them | HP19 | `interval` | 3, 5 |
| `interval_read_backwards` | `t` computed as `(x1 - x) / (x1 - x0)`: inside its interval's `y`, run the wrong way | HP19 monotone | `monotone` | 20, 7 |

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
  (2026-10-15); RFC 8785's values and HP3's parts draw their features often enough to have a floor. For each
  such property, `tests/unit/test_audit_controls.py` runs it at `ci`'s examples with a generator that stops
  producing one of those features: its audit fails, on that feature alone. The table evaluator's properties
  declare every feature by its chance: the least share it showed in eight runs of 2,000 examples (seeds 1 to
  4, at both sizes, 2026-10-17), rounded down; each has a control, on a choice no other feature it declares
  depends on.

## Adding a property

Write the check as a function of the implementation and the example, and the property as a `test_...` function
that records its features and calls the check. Declare the features with their least shares, or their chances,
measured. Add a mutant that the property must kill, to the mutant file of its group, and the module to a
shard. Never set `max_examples` on a property: the profile decides it. Build strategies so that they draw what
they need rather than filter it, take their size from `strategies.SIZE`, and build each strategy once rather
than in every draw: Hypothesis spends more building and checking a strategy than drawing from it.

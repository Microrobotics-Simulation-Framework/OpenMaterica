# The reference model

A test-only model of a read of one field of one record (`docs/specification/read_side_contract.md` sections 1
to 3), written from the specification's text alone, for the conformance cases, HP12 and the fuzz targets (the
S2 design's SQ49), as S3 keeps a test-only reference evaluator. It never ships, and imports nothing from
`materica`, at any depth.

| File | What it holds |
|---|---|
| `strict_json.py` | strict JSON (`record_format.md` section 1 item 6), RFC 8785 and the content hash (section 9), from the standard library |
| `read_model.py` | the model: the text's tables, steps 0 to 13, the result, `list_records` and `content_hash`; its open points in `OPEN_POINTS` |
| `cases.py` | every case file of a read run through the model under every configuration of claims it allows, and compared |
| `exceptions.py` | the case files the model does not agree with, by kind, each kind with its reason: today, reads outside its scope, on which it gives no verdict |
| `test_cases.py` | the model agrees with every case file of a read, or the case file is listed under its kind |
| `test_tables.py` | the model's tables against the generated vocabulary, so that a drift of either fails |
| `test_citations.py` | each quote the model cites is at the line it cites; each open point is listed once and named where it is applied |
| `test_layering.py` | the model reaches no `materica` module, by the imports it writes or in a fresh interpreter |
| `mutants.py`, `test_seeded_faults.py` | seeded faults of the model, each killed by a case file or listed as a survivor with its reason; not named `test_*mutants*`, since they are no Hypothesis search and run on every Python (`tests/conftest.py`, `PROPERTY_CONTROLS`) |

## What it decides

Steps 0 to 13 for the forms constant, interval, composition and evidence; implied conditions and nominals;
the operations `list_records` and `content_hash`; and alternatives as far as S4's decision 12 lets S2 go
(maintainer, 2026-10-15): the shape of `alternatives`, a request fault inside one alternative, and `no_pick`
or step 7's `want_mismatch` where no alternative has a reason of its own.

Anything else gives `NoVerdict`, an outcome of its own, which a test counts and never reads as a pass: a table
the field's row allows (S3), a pick or an overlay (S4), an extrapolation (S3 and S4), a region target (the
scene suite), `want: fit` on a field holding a fit record (the fits and reference data suite), and
alternatives beyond decision 12.

Each rule cites the text as `file:line` and a short quote. Where the text leaves a point open, the model takes
the maintainer's ruling where there is one, else the fail-closed choice, each listed once in `OPEN_POINTS` and
named where it is applied:

| Open point | The model's choice |
|---|---|
| `form_not_allowed_by_its_row` | a composition whose basis the row does not allow is refused as a form the row does not allow is: `form_not_registered` and the shared checks' reasons, its member not checked (maintainer, 2026-10-15; the text says so of a form) |
| `alternatives_within_decision_12` | decision 12's three cases only (maintainer, 2026-10-15) |
| `members_of_the_other_kind` | `token` on a numeric condition, or `value`, `range`, `plus_minus` or `set_or_measured` on a token condition, breaks its shape (fail closed); a token condition's `unit` keeps its own rule, step 9's `unit_mismatch` |
| `alternatives_named_at_a_field` | `alternatives` is named at a field's place, so a slip of it is refused (fail closed) |
| `evidence_entry_provenance` | an entry's `provenance` is checked as the field's is, and returned with every member the provenance table names, its review read as `provenance.md` section 2 item 6 reads one (fail closed) |
| `names_a_declaration_gives_a_requirement` | `field`, and a requirement condition's `reason` and `consequence`, are named at a request's requirement by `declarations.md`, so a slip of one is refused |

The model was first written to check the expected answers of S2's case files on 2026-10-15, as an independent
reader of the text, and brought to the text of this branch here. Two rulings it took then, a form the row does
not allow left unchecked and a status object breaking its shape giving `form_invalid` alone, are the text's
since S3 (`read_side_contract.md` section 3, step 8; `provenance.md` section 1), and so is the shape of
`alternatives` (`record_format.md` section 5): the model cites them there.

## Agreement with the cases

`test_cases.py` runs every case file of a read in the repository, 1,223 on `main` at `6c9ab9f` (1,136 reads,
25 listings and 11 reads of the hash suite, and 51 content hashes), whichever step of the implementation runs
it, under each of the 8 configurations of claims (plain read, with or without the hash, the fits and reference
data, and the family evaluation suites) that agrees with the case's suite and claims. Each is compared as the
specification's README says ("Case files"), by the conformance runner's comparison. The table evaluation
suite's 35 files are left out, and a test holds the files left out to exactly those whose operation is
`evaluate`: each asks for a table's values at points, as a consumer's own evaluator does, which is no read.

The model agrees with 894 files, under every configuration each allows (6,776 runs), and gives no verdict on
329, each listed in `exceptions.py` under the kind its outcome names: a table its row allows (147), an overlay
(71), an extrapolation (55), a pick (35), and an alternative with reasons of its own (21). It disagrees with
none. A case file the model disagrees with, or gives no verdict on, fails unless a kind lists it, for the
detail that kind names; a listed one it agrees with fails as stale.

## The mutant table

`test_seeded_faults.py` gives the model one fault at a time and requires a case file to give an outcome the list of
exceptions does not (a disagreement, a no verdict no kind lists, or an agreement with a listed file), or the
fault to be listed as a survivor with its reason: each survivor is a rule no case pins, which the properties
of S2a-4's phase B must kill. The search stops at the first such case file; the count is of all of them,
measured 2026-10-17 on `main` at `6c9ab9f`. 75 faults: 60 killed, 15 survive.

| Mutant | Fault | Case files that kill it |
|---|---|---|
| `want_outside_section_6` | a `want` that is none of section 6's tokens is read | 2 |
| `fits_wants_without_their_suite` | `fit`, `coverage` and `reference_data` read by a reader without their suite | 6 |
| `tolerance_without_an_operating_condition` | a tolerance with no operating condition accepted | 3 |
| `request_units_not_compared` | an operating condition's, a tolerance's or an implied value's unit not compared | 29 |
| `negative_zero_tolerance_refused` | a tolerance of `-0` read as below zero | 2 |
| `declaration_members_in_a_requirement_read` | a requirement holding `label`, `represents` or `population_level` read | 3 |
| `acceptances_applied_anywhere` | an acceptance applied at another record, a region, an interval or no location | 13 |
| `two_nominals_for_one_field` | two nominals naming one field read as the first | 1, `PR-330.two_nominals_one_field` alone |
| `unregistered_field_requested` | a field the reader's version does not register read, and found absent | 5 |
| `every_slip_ignored` | a member one slip from a named one ignored, in a request and in a record | 39 |
| `plurals_not_slips` | a word made plural or singular not one slip | survives: each plural slip in the cases adds an `s` (`fluids`), and so is one character inserted |
| `envelope_body_and_section_slips_ignored` | a slip in the envelope, the body or a section refuses no field | 6 |
| `unreadable_sources_ignored` | an unreadable source never turns `absent` or `pin_mismatch` into `malformed` | 49 |
| `first_of_differing_copies_read` | of two copies with the pin whose bytes differ, the first read | 2 |
| `hash_not_checked_before_step_4` | `hash_not_checked` on a result that ends before step 4 | 1, `PR-327.pin_no_hs` alone |
| `hash_never_recomputed` | a reader claiming HS never recomputes the hash | 8 |
| `other_minor_versions_read` | a record of another `MAJOR.MINOR` read | 15 |
| `alternatives_shape_unchecked` | an `alternatives` that is empty, not a list or beside a value field's members read | 5 |
| `want_mismatch_beside_no_pick` | `want_mismatch` reported under `no_pick` for an alternative whose form `want` cannot give | 4 |
| `conditions_kept_under_no_pick` | a `no_pick` result holding `conditions` of its own | 6 |
| `alternatives_counted_from_one` | an `alternative_values` entry's index counted from one | 6 |
| `labels_raised_from_an_alternative` | an alternative's labels on the `no_pick` result's own | 2 |
| `nominal_ignored_over_alternatives` | an interval beside other alternatives not counted as a form `want: value` gives under a nominal | 1, `PR-338.no_pick_two_intervals_nominal` alone |
| `nominal_applied_under_no_pick` | a nominal applied to an interval alternative under `no_pick` | 1, `PR-338.no_pick_two_intervals_nominal` alone |
| `unknown_tokens_read_as_shape_faults` | a token the reader knows for no member of that name gives `form_invalid` | 26 |
| `status_tokens_unchecked` | a status object takes any token, in any member | 3 |
| `member_checked_off_its_row` | the member of a form the row does not allow checked as on a row allowing it | survives: each member of a form its row does not allow is well formed in the cases |
| `composition_checked_beyond_its_basis` | a composition whose basis the row does not allow checked further | survives: each composition whose basis its row does not allow is otherwise well formed in the cases |
| `family_suite_ignored` | a parameter set read without the family evaluation suite not `family_suite_absent` | 7 |
| `entry_withheld_in_part_read` | an evidence entry withheld in some members but not every one read | 1, `PR-052.entry_partly_withheld` alone |
| `missing_label_refused` | a field without its row's label refused | 97 |
| `unreadable_review_refuses` | a review the reader cannot read refuses the field | 8 |
| `null_read_as_absent` | `null` in a member step 8 checks read as the member absent | 7 |
| `statistics_unchecked` | a statistics block not checked | 47 |
| `uncertainties_unchecked` | a relative or expanded uncertainty not checked | 14 |
| `derivation_unchecked` | a derived value's derivation not checked | 14 |
| `input_specimens_optional` | a derivation without `input_specimens` read | survives: every derivation in the cases holds `input_specimens` |
| `population_level_checks_stop_at_a_missing_member` | a population level missing a member has its `level` and `within` left unchecked | survives: no case holds a population level missing a member beside a token of its own |
| `dof_token_unchecked_under_student_t` | a `dof` held as a status object under a Student's t distribution has its token left unchecked | survives: no case holds such a `dof` of an unknown token |
| `every_forms_member_named_at_a_field` | every form's member named at a field's place, so that a slip of another form's refuses a constant | survives: no case holds a slip of another form's member beside a form the reader knows |
| `every_status_object_an_unstated_kind` | a `plus_minus` entry whose `stated_as` holds any status object counted as of unstated kind | survives: no case holds a `stated_as` of another status token beside an entry of a stated kind |
| `section_specimen_unchecked` | a section's `specimen` not checked for a field read from it | 3 |
| `condition_shapes_unchecked` | a condition of a name the reader knows not checked | 19 |
| `broken_status_object_reports_its_token` | a status object that breaks its shape gives its token's `unknown_token` beside `form_invalid` | survives: no case holds a status object breaking its shape with a token the reader does not know |
| `members_of_the_other_kind_read` | a numeric condition holding `token`, or a token condition holding `value`, read | survives: no case holds a condition with a member of the other kind's shape: the text leaves it open |
| `members_of_the_other_kind_ignored` | a numeric condition's `token`, or a token condition's `value`, ignored as a member the reader does not know: not refused, and not returned | survives: no case holds a condition with a member of the other kind's shape: the text leaves it open |
| `slips_of_alternatives_ignored` | a member one slip from `alternatives` beside a value field's members ignored | survives: no case holds a member one slip from `alternatives`: the text leaves it open |
| `evidence_entry_provenance_unchecked` | an evidence entry's `provenance` not checked | survives: each evidence entry's `provenance` in the cases is well formed: the text leaves it open |
| `declaration_names_not_named_in_a_request` | a slip of a requirement's `field`, or of its conditions' `reason` or `consequence`, ignored | survives: no case holds a slip of `field`, `reason` or `consequence` in a requirement |
| `units_compared_after_case_folding` | a record's units compared after case folding | 2 |
| `fact_units_unchecked` | a specimen fact's unit not compared with the one its row fixes | 3 |
| `token_condition_unit_accepted` | a `unit` on a token condition passes step 9 | 1, `PR-037.unit_on_token_condition` alone |
| `plus_minus_units_unchecked` | a `plus_minus` entry's unit not compared | 1, `PR-037.plus_minus_unit` alone |
| `floating_point_as_written` | section 5's tests computed in floating point as written | 3 |
| `strict_inequalities` | `<` for `<=` in section 5's table | 10 |
| `plus_minus_ignored` | a stated plus or minus ignored | 15 |
| `unchecked_read_as_met` | a stated condition the request gives no tolerance or accept list for read as `met` | 3 |
| `operating_omitted_from_entries` | a condition entry without the request's operating condition | 204 |
| `implied_fills_any_condition` | an implied condition fills a stated condition, or one held as another status object | 2 |
| `disagreeing_implied_conditions_read` | two implied conditions that disagree read as the first | 7 |
| `implied_values_compared_by_value` | two implied values compared as numbers, so that `0` and `-0` agree | 1, `PR-316.implied_zero_beside_minus_zero` alone |
| `required_with_ignored` | a condition another condition requires with its token not checked | 4 |
| `unknown_condition_names_ignored` | a condition name the reader does not know gives no entry and no reason | 6 |
| `stated_without_origin_unreported` | a value stated without origin not `unknown` | 1, `PR-309.stated_without_origin` alone |
| `step_12_labels_dropped` | the field's label and `mixed_conditions` not added | 151 |
| `bounds_given_by_a_constant` | `want: bounds` gives a constant's value | 3 |
| `value_given_by_an_interval` | `want: value` gives an interval's bounds without a nominal | 16 |
| `nominal_outside_supplies_the_value` | a nominal outside an interval's bounds supplies the value | 2 |
| `best_status` | the status the best of the reasons, not the worst | 3 |
| `value_beside_not_met` | a value returned beside `not_met` without an assumption, as beside `condition_outside` | 20 |
| `unknown_members_returned` | a member the reader does not know returned | 13 |
| `review_returned_as_its_result` | a known review returned as its `result` alone | 2 |
| `unit_returned_without_its_reason` | a unit held as a status object returned without its `reason` | 1, `PR-010.evidence_unit_status_with_reason` alone |
| `section_facts_not_merged` | the result's `specimen` the field's facts alone | 26 |
| `results_share_the_record` | a result shares its members with the record read | survives: a case compares a result's JSON, in which no object is shared |

Ten faults die to one case file alone; a change to that file would let each live, so the properties of phase
B should kill them as well. Of the nine survivors, four are the open points (`members_of_the_other_kind_read`,
`slips_of_alternatives_ignored`, `evidence_entry_provenance_unchecked`,
`declaration_names_not_named_in_a_request`), which no case pins because the text leaves them open; one is
the rule that a status object breaking its shape gives no reason of its own
(`broken_status_object_reports_its_token`), a ruling the text took up with S3, whose example is a table's,
on which the model gives no verdict; two are the rule that a form's member is unchecked off its row
(`member_checked_off_its_row`, `composition_checked_beyond_its_basis`), which only S3's cases show, again
for tables; one needs a plural of two characters or more (`plurals_not_slips`); and one cannot show through
JSON at all (`results_share_the_record`, HP6's). The tenth, `input_specimens_optional`, is the model's own
reading until S2a-4's phase B, whose agreement property (HP12) found that the text requires the list
(`provenance.md` section 5 item 3, "A derived value carries the specimen facts of each input"); the model was
fixed, and the fault seeded. The eleventh, `members_of_the_other_kind_ignored`, is the implementation's
reading of that open point (S2a-4's phase B): HP12 lists the point as a known divergence, held exactly by
this fault (`tests/property/test_model_properties.py`). The last four are the model's readings until fuzz
target 4, held to the model, found them on its first minutes: a population level whose `within` is missing
or slipped had its `level` token left unchecked, so did a `dof` status object under a Student's t
distribution, against `read_side_contract.md` section 2 item 2, "Each step makes all its checks before the
read stops"; and a `stated_as` of any status token counted as of unstated kind, where `provenance.md` section
6.1 item 6 names `{"status": "unstated"}`; and every form's member named at a constant's place, so that a
slip of `table` refused it, where `record_format.md` section 5 names "the form's member", `value` for a
constant (step 8 names every form's member only beside a form the reader does not know). Each was fixed and
seeded.

## Running

```sh
uv run pytest tests/reference -n 6
```

The whole directory runs in about 14 s on eight workers, the mutant searches most of it.

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
| `test_citations.py` | each quote the model, and the table evaluator beside it, cites is at the line it cites; each open point is listed once and named where it is applied |
| `test_layering.py` | the model and the table evaluator reach no `materica` module, by the imports they write or in a fresh interpreter |
| `mutants.py`, `test_seeded_faults.py` | seeded faults of the model, each killed by a case file or listed as a survivor with its reason; not named `test_*mutants*`, since they are no Hypothesis search and run on every Python (`tests/conftest.py`, `PROPERTY_CONTROLS`) |

## What it decides

Steps 0 to 13 for the forms constant, interval, composition and evidence; implied conditions and nominals;
the operations `list_records` and `content_hash`; and step 7 over alternatives read with no pick and no
overlay (S4a): the shape of `alternatives`, each alternative read alone and set aside, kept or refusing the
field, and the outcome with its reasons, each found reading one alternative carrying its index, and its
members. S4a's step 7 was written from the text by an agent that did not read the implementation's.

Anything else gives `NoVerdict`, an outcome of its own, which a test counts and never reads as a pass: a table
the field's row allows (S3), alone or as one alternative, a pick or an overlay (S4), an extrapolation (S3 and
S4), a region target (the scene suite), and `want: fit` on a field holding a fit record (the fits and
reference data suite).

Each rule cites the text as `file:line` and a short quote. Where the text leaves a point open, the model takes
the maintainer's ruling where there is one, else the fail-closed choice, each listed once in `OPEN_POINTS` and
named where it is applied:

| Open point | The model's choice |
|---|---|
| `form_not_allowed_by_its_row` | a composition whose basis the row does not allow is refused as a form the row does not allow is: `form_not_registered` and the shared checks' reasons, its member not checked (maintainer, 2026-10-15; the text says so of a form) |
| `alternatives_without_a_pick` | step 7 for a read with no pick and no overlay (S4a); a table alternative gives no verdict wherever it stands among the others, since every alternative is read before the outcome is decided, and step 11's set-aside, `at_edge` and `request_incomplete` are a table's |
| `evidence_entry_provenance` | an entry's `provenance` is returned whole, holding the members the version defines at every depth, read from the writer schema below the provenance table's own, since the text names them in part only |

The model was first written to check the expected answers of S2's case files on 2026-10-15, as an independent
reader of the text, and brought to the text of this branch here. Two rulings it took then, a form the row does
not allow left unchecked and a status object breaking its shape giving `form_invalid` alone, are the text's
since S3 (`read_side_contract.md` section 3, step 8; `provenance.md` section 1), and so is the shape of
`alternatives` (`record_format.md` section 5): the model cites them there. So are the maintainer's rulings of
2026-10-19 and 2026-10-20 on three points the model once listed: an evidence entry's `provenance` is checked as
a field's, every review it holds at any depth read as every review is (`record_format.md` section 4.3 item 2);
a record's condition holding a member of the other kind of condition's shape breaks it (`provenance.md`
section 6.1 item 1); and a slip of `alternatives` at a field's place is refused (`record_format.md` sections 5
and 10, as built).

## Agreement with the cases

`test_cases.py` runs every case file of a read in the repository, 1,260 at S4a's head (1,173 reads, 25
listings and 11 reads of the hash suite, and 51 content hashes), whichever step of the implementation runs
it, under each of the 8 configurations of claims (plain read, with or without the hash, the fits and reference
data, and the family evaluation suites) that agrees with the case's suite and claims. Each is compared as the
specification's README says ("Case files"), by the conformance runner's comparison. The table evaluation
suite's 35 files are left out, and a test holds the files left out to exactly those whose operation is
`evaluate`: each asks for a table's values at points, as a consumer's own evaluator does, which is no read.

The model agrees with 952 files, under every configuration each allows (7,240 runs), and gives no verdict on
308, each listed in `exceptions.py` under the kind its outcome names: a table its row allows (147), an overlay
(71), an extrapolation (55) and a pick (35). It disagrees with none. Until S4a it also gave no verdict on 21
files of alternatives with reasons of their own, with which it now agrees, as with S4a's three cases of
`unit` under `no_pick`. A case file the model disagrees with, or gives no verdict on, fails unless a kind lists it, for the
detail that kind names; a listed one it agrees with fails as stale.

## The mutant table

`test_seeded_faults.py` gives the model one fault at a time and requires a case file to give an outcome the list of
exceptions does not (a disagreement, a no verdict no kind lists, or an agreement with a listed file), or the
fault to be listed as a survivor with its reason: each survivor is a rule no case pins, which the properties
of S2a-4's phase B must kill. The search stops at the first such case file; the count is of all of them,
measured 2026-10-17 on `main` at `6c9ab9f`, but `member_checked_off_its_row`'s, which PR #37's review's cases
kill (the same day). 75 faults: 61 killed, 14 survive; S2a-4's review added five survivors, each a rule no
case pins (below the table), so 80 faults: 61 killed, 19 survive. The two cases of the maintainer's token
ruling (2026-10-18) kill two of the survivors, so 63 killed, 17 survive. S4a replaced the fifth survivor
S2a-4's review added, `units_stored_differently_read_as_no_pick`, which the maintainer's ruling on `unit`
under `no_pick` (2026-10-19) made the text's reading, by `unit_of_the_last_remaining_alternative`, which that
ruling's cases kill, and added 16 faults of its step 7, each killed, measured 2026-10-19 at S4a's head: 96
faults, 80 killed, 16 survive. The maintainer's rulings of 2026-10-19 and 2026-10-20 bring cases that kill two
more, `evidence_entry_provenance_unchecked` and `slips_of_alternatives_ignored`, and a fault their cases kill,
`nested_reviews_returned_as_found`, so 97 faults: 83 killed, 14 survive. The rows these rulings change are
measured with them, and so are those their cases move that were current before them,
`condition_shapes_unchecked`, `every_slip_ignored` and `null_read_as_absent`; the others are as stamped.

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
| `every_slip_ignored` | a member one slip from a named one ignored, in a request and in a record | 41 |
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
| `member_checked_off_its_row` | the member of a form the row does not allow checked as on a row allowing it | 2, `PR-036.broken_composition_on_density` and `PR-036.broken_interval_on_elemental_composition` |
| `composition_checked_beyond_its_basis` | a composition whose basis the row does not allow checked further | survives: each composition whose basis its row does not allow is otherwise well formed in the cases |
| `family_suite_ignored` | a parameter set read without the family evaluation suite not `family_suite_absent` | 7 |
| `entry_withheld_in_part_read` | an evidence entry withheld in some members but not every one read | 1, `PR-052.entry_partly_withheld` alone |
| `missing_label_refused` | a field without its row's label refused | 97 |
| `unreadable_review_refuses` | a review the reader cannot read refuses the field | 8 |
| `null_read_as_absent` | `null` in a member step 8 checks read as the member absent | 8 |
| `statistics_unchecked` | a statistics block not checked | 47 |
| `uncertainties_unchecked` | a relative or expanded uncertainty not checked | 14 |
| `derivation_unchecked` | a derived value's derivation not checked | 14 |
| `input_specimens_optional` | a derivation without `input_specimens` read | survives: every derivation in the cases holds `input_specimens` |
| `population_level_checks_stop_at_a_missing_member` | a population level missing a member has its `level` and `within` left unchecked | survives: no case holds a population level missing a member beside a token of its own |
| `dof_token_unchecked_under_student_t` | a `dof` held as a status object under a Student's t distribution has its token left unchecked | survives: no case holds such a `dof` of an unknown token |
| `every_forms_member_named_at_a_field` | every form's member named at a field's place, so that a slip of another form's refuses a constant | survives: no case holds a slip of another form's member beside a form the reader knows |
| `every_status_object_an_unstated_kind` | a `plus_minus` entry whose `stated_as` holds any status object counted as of unstated kind | survives: no case holds a `stated_as` of another status token beside an entry of a stated kind |
| `section_specimen_unchecked` | a section's `specimen` not checked for a field read from it | 3 |
| `condition_shapes_unchecked` | a condition of a name the reader knows not checked | 25 |
| `broken_status_object_reports_its_token` | a status object that breaks its shape gives its token's `unknown_token` beside `form_invalid` | survives: no case holds a status object breaking its shape with a token the reader does not know |
| `members_of_the_other_kind_read` | a numeric condition holding `token`, or a token condition holding `value`, read | 7: `PR-330.implied_token_for_numeric_condition` and `PR-330.implied_unit_for_token_condition`, the implied half, which the token ruling settled; `PR-045.numeric_condition_holding_token`, `PR-045.numeric_condition_holding_token_status`, `PR-045.token_condition_holding_value`, `PR-045.token_condition_holding_value_null` and `PR-301.other_kind_beside_unknown_basis`, the record half, ruled on 2026-10-19 |
| `members_of_the_other_kind_ignored` | a numeric condition's `token`, or a token condition's `value`, ignored as a member the reader does not know: not refused, and not returned | 7, the same seven, the implied half's two and the record half's five |
| `slips_of_alternatives_ignored` | a member one slip from `alternatives` beside a value field's members ignored | 1, `PR-030.near_typo_alternative_beside_constant` alone, the case of the maintainer's ruling (2026-10-19) |
| `evidence_entry_provenance_unchecked` | an evidence entry's `provenance` not checked | 1, `PR-052.entry_provenance_origin_unknown` alone, the case of the maintainer's ruling (2026-10-19) |
| `nested_reviews_returned_as_found` | a review inside a provenance an evidence entry's `per_parameter` maps a parameter to returned as found, and none where that provenance holds none | 2, `PR-052.entry_provenance_per_parameter_review_unknown` and `PR-052.entry_provenance_per_parameter_review_absent`, the cases of the maintainer's ruling (2026-10-20) |
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
| `ies_not_a_plural` | a final `y` exchanged with `ies` not one slip | survives: no case holds a slip of a final `y` made `ies` |
| `donor_age_of_neither_accepted` | a `donor_age` holding neither `value` nor `range` accepted | survives: no case holds one |
| `review_of_both_shapes_read_as_its_status` | a review holding both `status` and `result` read as its status object | survives: no case holds one |
| `reviewed_review_keeps_a_status_objects_members` | a reviewed review returned with a status object's members, its `reason` among them | survives: no case holds one |
| `unit_of_the_last_remaining_alternative` | under `no_pick`, the result's `unit` the last remaining alternative's | 3, the three `PR-013.evidence_unit*` arms |
| `refused_alternative_set_aside` | an alternative refused at step 8 or 9 set aside, not refusing the field | 9 |
| `set_aside_alternative_refuses` | an alternative whose conditions give `not_met` at step 10 refusing the field, not set aside | 6 |
| `request_fault_sets_aside` | an alternative whose read a fault of the request ends set aside, not refusing the field | 1, `PR-316.implied_two_disagree_in_alternative` alone |
| `want_mismatch_sets_aside` | an alternative whose form `want` cannot give set aside, not kept | 9 |
| `set_aside_reasons_dropped_where_refused` | the set-aside alternatives' reasons dropped where another refuses the field | 3 |
| `waiting_reasons_dropped_where_refused` | the `not_met` reasons of an alternative that stays dropped where the field is refused | 2, `PR-044.refused_reports_waiting_nominal_invalid` and `PR-044.refused_reports_waiting_want_mismatch` |
| `labels_kept_where_refused` | the alternatives' labels on the result where the field is refused or every alternative set aside | 2, `PR-316.implied_two_disagree_in_alternative` and `PR-336.refused_over_alternatives_no_hs` |
| `set_aside_reasons_beside_the_one_left` | the set-aside alternatives' reasons reported beside the one left | 5 |
| `one_left_reasons_without_their_alternative` | the one left's reasons without their `alternative` | 3 |
| `nominal_not_applied_to_the_one_left` | a nominal not applied to the interval left, which gives no value | 1, `PR-338.one_left_interval_nominal_applied` alone |
| `not_met_reasons_beside_no_pick` | the `not_met` reasons of the alternatives that stay reported beside `no_pick` or `want_mismatch` | 7 |
| `unknown_reasons_dropped_beside_no_pick` | the `unknown` reasons of the alternatives that stay dropped beside `no_pick` or `want_mismatch` | 1, `PR-013.index_past_set_aside_and_unknown_reasons` alone |
| `set_aside_reasons_beside_no_pick` | the set-aside alternatives' reasons reported beside `no_pick` or `want_mismatch` | 1, `PR-013.index_past_set_aside_and_unknown_reasons` alone |
| `request_fault_given_an_alternative` | a fault of the request found reading one alternative given that `alternative` | 2, PR-316's two arms in an alternative |
| `index_among_those_that_stay` | an alternative's index counted among the alternatives that stay, in its reasons and its entry | 2, `PR-013.index_past_set_aside_and_unknown_reasons` and `PR-044.one_left_after_set_aside` |
| `unit_of_the_first_stored_alternative` | under `no_pick`, the result's `unit` the first stored alternative's, set aside or not | 1, `PR-013.evidence_unit_of_the_first_that_stays` alone |

Ten faults die to one case file alone; a change to that file would let each live, so the properties of phase
B should kill them as well. Of the eight survivors, three were the open points (`members_of_the_other_kind_read`,
`slips_of_alternatives_ignored`, `evidence_entry_provenance_unchecked`), which no case pinned while the text left
them open (the maintainer's rulings brought cases that kill all three: the token ruling's and the record
half's, `PR-030.near_typo_alternative_beside_constant` and `PR-052.entry_provenance_origin_unknown`); one is a
rule of the text that no case pins either, since S2a-4's fix round
(`declaration_names_not_named_in_a_request`: `read_side_contract.md:40-41` and `declarations.md:30` and `:64` name
a requirement's `field` and its conditions' `reason` and `consequence`, and a read refuses a slip of one: the
former open point `names_a_declaration_gives_a_requirement`, decided by the text as S2a-4's review read it,
approved by the maintainer on 2026-10-18 and confirmed on 2026-10-19); one is
the rule that a status object breaking its shape gives no reason of its own
(`broken_status_object_reports_its_token`), a ruling the text took up with S3, whose example is a table's,
on which the model gives no verdict; one is the rule that a composition whose basis its row does not allow
is checked no further (`composition_checked_beyond_its_basis`), which only S3's cases show, again for tables;
one needs a plural of two characters or more (`plurals_not_slips`); and one cannot show through JSON at all
(`results_share_the_record`, HP6's). The same rule for a form the row does not allow
(`member_checked_off_its_row`) survived until PR #37's review added two cases that kill it, a composition with
no component on `bulk.density` and an interval upside down on `bulk.elemental_composition`, each
`form_not_registered` alone. The ninth, `input_specimens_optional`, is the model's own
reading until S2a-4's phase B, whose agreement property (HP12) found that the text requires the list
(`provenance.md` section 5 item 3, "A derived value carries the specimen facts of each input"); the model was
fixed, and the fault seeded. The tenth, `members_of_the_other_kind_ignored`, was the implementation's
reading of that open point's record half (S2a-4's phase B), which HP12 listed as a known divergence, held
exactly by this fault, until the maintainer ruled it fail closed (2026-10-19) and the implementation came to
refuse it; HP12 lists no divergence of it since. It and `members_of_the_other_kind_read` also ignore the
implied half, since the model reads both halves by one function, and so the two cases of the maintainer's
token ruling kill both, as the two of the record half's ruling do; neither is a survivor since. The last four are the model's readings until fuzz
target 4, held to the model, found them on its first minutes: a population level whose `within` is missing
or slipped had its `level` token left unchecked, so did a `dof` status object under a Student's t
distribution, against `read_side_contract.md` section 2 item 2, "Each step makes all its checks before the
read stops"; and a `stated_as` of any status token counted as of unstated kind, where `provenance.md` section
6.1 item 6 names `{"status": "unstated"}`; and every form's member named at a constant's place, so that a
slip of `table` refused it, where `record_format.md` section 5 names "the form's member", `value` for a
constant (step 8 names every form's member only beside a form the reader does not know). Each was fixed and
seeded.

S2a-4's review pinned the five it added: the first four are rules no case or HP12 draw held, the fourth the
model's own reading until then (a reviewed review's `reason` was returned, which `provenance.md` section 2
item 6 does not name for a reviewed review), fixed and seeded; the fifth was a step S4 owns, which no read S2
built reached, and S4a replaced it (above).

S4a's sixteen break each rule of step 7 the model decides for a read with no pick and no overlay: an
alternative's standing (set aside, staying or refusing the field), the reasons each outcome reports and
withholds, each reason's `alternative`, the nominal on the one left, the labels of a result that rests on no
single alternative, the entries' indexes and the `unit` under `no_pick`. Five die to one case file alone:
`request_fault_sets_aside`, `nominal_not_applied_to_the_one_left`, `unknown_reasons_dropped_beside_no_pick`,
`set_aside_reasons_beside_no_pick` and `unit_of_the_first_stored_alternative`, whose case S4a wrote for it,
three evidence alternatives the first of which an implied condition sets aside: only a unit registered as a
status object can be stored differently, which only evidence's is, and evidence holds no registered
condition of its own, so an implied condition is the one way to set an evidence alternative aside.

The agreement property HP12 (`tests/property/test_model_properties.py`) kills 13 of the 14 survivors, the two
the token ruling's cases kill, and `member_checked_off_its_row`, which it searched as a survivor before two
cases came to kill it, every one of the 17 faults one case file alone kills (S4a's five among them, and
`evidence_entry_provenance_unchecked` and `slips_of_alternatives_ignored`, survivors HP12 searched until the
cases of their rulings came), and
`nominal_outside_supplies_the_value`, which two kill, each with the model given the fault and the core as it
is (`tests/property/test_model_mutants.py`); S2b-2, which reads evidence and nominals, brought the six that
waited for it. The other one is listed there with the reason no read shows it: a shared object never shows
in JSON.

## Running

```sh
uv run pytest tests/reference -n 6
```

The whole directory runs in about 14 s on eight workers, the mutant searches most of it.

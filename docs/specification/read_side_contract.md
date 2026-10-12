# Read-side contract

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 3.5, 4.4 and 7.5. This
document defines what a read takes and gives, the order of its steps, how a condition is checked, and every
reason a read can give. The shapes it reads are defined in the other documents.

## 1. The read request

A read asks for one field of one material, at stated operating conditions.

| Member | Contents |
|---|---|
| `records` | the records the reader may resolve references against (a case file supplies them) |
| `target` | `{"record": {"id", "version", "content_hash"}, "field": "<section>.<field>"}`; in a scene, `{"region", "field"}`, resolved through the scene (`geometry.md`) |
| `operating_conditions` | per condition, `{"value", "unit"}` or `{"range": [lo, hi], "unit"}`, in the condition's registered unit |
| `requirement` | `want` (section 6), required; and `conditions`: per condition either `{"tolerance": {"value", "unit"}}` (absolute, in the condition's unit) or `{"accept": [<tokens>]}` |
| `acceptances` | the consumer's acceptances for this read that change what is read: a pick, an overlay, an extrapolation or a nominal, an implied condition (`declarations.md`) |

A request is refused, with the reason `request_incomplete`, when it has no `want`, gives a tolerance for a
condition with no operating condition, or reads a table or power law with no operating value for its axis.
[PR-308] A request whose operating condition or tolerance is in a unit other than the condition's registered
unit is refused, with the reason `request_unit_mismatch`. [PR-320] A table or power law read over an operating
range of its axis gives `want_mismatch` until a read over a band is specified (section 6). [PR-321]

## 2. The read result

| Member | Contents |
|---|---|
| `status` | `met`, `not_met` or `unknown`. A build result adds the model, the region and what accepted it (`declarations.md`) |
| `reasons` | a list of `{"code", "condition"?, "detail"?}`, one per reason, codes from section 4; empty only when `met` |
| `value` | present unless `not_met` without an assumption; its shape follows `want` (section 6) |
| `values` | in place of `value` for `no_pick`: every remaining alternative's value, in stored order |
| `unit` | the field's unit |
| `conditions` | one entry per condition checked (section 5): `{"name", "status", "record", "operating"}` |
| `specimen` | the field's specimen facts, the section's merged with the field's |
| `statistics` | as stored |
| `provenance` | `{"origin", "review", "source"}`: the origin token; the review's `result`, or its status object; the source key, where there is one |
| `labels` | the result's labels, from this list only: `user_extracted` (read through a fill-in), `no_independent_witness` (a parameter set), `hash_not_checked` (section 3), `initial_value_only` (a trainable field, `declarations.md`), and the field's `label` |
| `assumption` | where the value rests on a declared extrapolation or nominal: the declaration it rests on |

1. A read never stops with an error for anything a record or request contains. [PR-300]
2. Every reason found is reported, not only the first. The status is the worst of them: `not_met` over
   `unknown` over `met`. [PR-301]
3. An `unknown` result carries the value the record holds, so that a waiver has something to use. A `not_met`
   result carries no value, except where a declared extrapolation or nominal covers it: the status stays
   `not_met`, the value is present, and `assumption` names the declaration. [PR-302] [PR-307]
4. A value whose origin is `stated_without_origin` (a number found in code or a datasheet with nothing behind
   it) gives `unknown` with the reason `stated_without_origin`, which a waiver may accept, so that the
   material input sheet records it (AD 4.7). [PR-309]

## 3. The read procedure

A reader takes these steps in this order. A step that gives `not_met` ends the read, with the reasons found so
far; a step that gives `unknown` does not.

1. **Parse** the file as JSON (`malformed`). [PR-002]
2. **Version.** Read `schema_version` and refuse another version (`record_format.md` section 8:
   `other_version`). [PR-026]
3. **Validate** the envelope against the reader schema of the reader's version (`malformed`); a shape error
   inside one field is left to step 8.
4. **Hash.** Every reader compares the record's stated `content_hash` with any hash the request or a
   reference pins, and refuses a difference (`pin_mismatch`). A reader that claims the HS profile also
   recomputes the hash (`record_format.md` section 9) and refuses a record whose recomputed hash differs from
   its stated one (`hash_mismatch`); one that does not labels every result `hash_not_checked`. [HS-010]
   [HS-011] [PR-327]
5. **Type.** Refuse a referenced record of a type the reader cannot read (`unknown_type`).
6. **Overlays.** Apply the overlays the acceptances name, and refuse a base mismatch or a conflict, by
   `record_format.md` section 4.4. The overlay's scope is compared by the build, not here (`declarations.md`
   section 5).
7. **Field.** Find the field (`absent`). For alternatives, read each, set aside those whose conditions give
   `not_met` (step 10), and with more than one left and no pick give `unknown` (`no_pick`); with none left,
   give `not_met` with the reasons of each. A pick's index counts the stored alternatives, set-aside ones
   included. [PR-304]
8. **Form and tokens.** Refuse a form the field's row does not allow (`form_not_registered`), a form that
   breaks the structural rules of `record_format.md` section 6 (`form_invalid`), a token the reader does not
   know (`unknown_token`), and a withheld value (`withheld`). [PR-322]
9. **Units.** Refuse a field unit, `axis_unit` or condition unit other than the registered one
   (`unit_mismatch`).
10. **Conditions**, by section 5.
11. **Form.** Evaluate the form at the operating conditions, within its range (section 5, last rows).
12. **Origin and fill-in.** Give `unknown` for a value stated without origin (`stated_without_origin`) and for
    a fill-in from another version of the document (`fill_in_version_mismatch`); add the labels of section 2.
13. **Want.** Shape the value by `want` (section 6).

A parameter set needs the family evaluation profile (`model_families.md`); sampling, the sampling profile
(`uncertainty.md`); a scene, the scene profile (`geometry.md`).

## 4. Reason codes

Every reason a read can give. A document that defines a new reason adds it here.

| Code | Status | Meaning | Defined in |
|---|---|---|---|
| `malformed` | not_met | invalid JSON, or an envelope invalid against the reader schema | `record_format.md` 1 |
| `other_version` | not_met | another schema version | `record_format.md` 8 |
| `hash_mismatch` | not_met | the recomputed hash differs from the record's own | `record_format.md` 9 |
| `pin_mismatch` | not_met | the stated hash, or with HS the recomputed hash, differs from a pin | this document 3 |
| `unknown_type` | not_met | a referenced record of a type the reader cannot read | `record_format.md` 3 |
| `absent` | not_met | the section or field is absent, or a referenced record is not among the records supplied | `record_format.md` 1, 4 |
| `no_pick` | unknown | alternatives remain and no pick is declared | `record_format.md` 5 |
| `form_not_registered` | not_met | a form the field's row does not allow | `record_format.md` 4.1 |
| `form_invalid` | not_met | a form that breaks the structural rules of its section (a table's lengths, order, knots, edges, or a non-positive log-log value) | `record_format.md` 6 |
| `unknown_token` | not_met | a token the reader does not know | `record_format.md` 10 |
| `withheld` | not_met | a reference-only value, not filled in | `provenance.md` 7 |
| `fill_in_version_mismatch` | unknown | a fill-in's document identifier or version differs from its base's | `provenance.md` 7 |
| `unit_mismatch` | not_met | a unit other than the registered one | `record_format.md` 4.2 |
| `condition_unstated` | unknown | the source does not state the condition | section 5 |
| `condition_unknown_name` | unknown | a condition name the reader does not know | `record_format.md` 10 |
| `condition_unchecked` | unknown | the record holds a condition the request gives no tolerance or accept list for | section 5 |
| `condition_outside` | not_met | a stated condition outside the tolerance | section 5 |
| `condition_not_accepted` | not_met | a token condition not in the accept list | section 5 |
| `outside_range` | not_met | outside the form's range, with no declared extrapolation | section 5 |
| `at_edge` | not_met | a table read exactly at a declared edge | `record_format.md` 6 |
| `range_unstated` | unknown | a power law with no stated range; only an extrapolation accepts it | `record_format.md` 6 |
| `want_mismatch` | not_met | a `want` the form cannot give | section 6 |
| `stated_without_origin` | unknown | a value with nothing behind it | section 2 |
| `family_profile_absent` | not_met | a parameter set, read without family evaluation | `record_format.md` 6 |
| `overlay_base_mismatch` | not_met | an overlay whose base differs from the record in use; never accepted | `record_format.md` 4.4 |
| `overlay_scope_mismatch` | not_met | an overlay scoped to another consumer, model or configuration (a build check) | `declarations.md` 5 |
| `overlay_conflict` | not_met | two declared overlays replace one field | `record_format.md` 4.4 |
| `request_incomplete` | not_met | no `want`; a tolerance for a condition with no operating condition; a table or power law with no operating value for its axis | section 1 |
| `request_unit_mismatch` | not_met | an operating condition or tolerance in another unit than the registered one | section 1 |
| `owner_ambiguous` | not_met | regions with no or tied priority claim one point | `geometry.md` |
| `no_material` | not_met | no region claims a point and the scene declares no background | `geometry.md` |
| `domain_undeclared` | not_met | a domain the consumer did not declare | `geometry.md` |
| `orientation_missing` | not_met | a direction-dependent value for a region with no orientation | `geometry.md` |
| `geometry_unresolved` | not_met | a region's external geometry has no inside test the reader can use | `geometry.md` |
| `geometry_hash_mismatch` | not_met | an external geometry whose SHA-256 differs from the one stated | `geometry.md` |
| `representation_unsupported` | not_met | a 0.1.0 manifest holding precedence, a label volume or a field override | `geometry.md` |
| `homogeneity_undeclared` | not_met | a layered path without its lateral-homogeneity declaration | `geometry.md` |
| `outside_path` | not_met | a layered path read before its start or at or beyond its end | `geometry.md` |
| `label_unmapped` | not_met | a label with no material in the label mapping | `geometry.md` |
| `unauthored_attribute` | not_met | a value-bearing Vesalius attribute nobody authored | `usd_binding.md` |
| `stage_units_unauthored` | not_met | a stage with no authored `metersPerUnit` | `usd_binding.md` |
| `units_uncompensated` | not_met | geometry in other units with no compensating transform | `usd_binding.md` |
| `binding_missing` | not_met | a region with no physics binding | `usd_binding.md` |
| `binding_refused` | not_met | an all-purpose, purpose-less, collection or conflicting binding, or one to a prim with no `vesalius:id` | `usd_binding.md` |
| `path_arrays_mismatch` | not_met | a layered path whose arrays differ in length, or an index out of range | `usd_binding.md` |
| `no_requirement` | unknown | a field a model reads with no requirement declared for it | `declarations.md` |
| `label_mismatch` | not_met | a required label differs or is absent | `declarations.md` |
| `unknown_family` | not_met | a family identifier or version the consumer does not know | `model_families.md` |
| `parameters_mismatch` | not_met | a parameter set missing a parameter its family names, or holding an extra one | `model_families.md` |
| `check_point_failed` | not_met | the consumer's evaluation misses a check point | `model_families.md` |
| `inadmissible` | not_met | a parameter set that fails its family's admissibility constraints | `model_families.md` |
| `outside_check_points` | unknown | an evaluation outside the span of the check points | `model_families.md` |
| `outside_coverage` | unknown | a state outside the parameter set's coverage | `model_families.md` |
| `fractions_invalid` | not_met | volume or mass fractions that do not sum to one within the declared precision | `mixing_rules.md` |
| `mixing_refused` | not_met | a field with no general rule, a rule not declared, or a zero value in a harmonic or Wood mean | `mixing_rules.md` |

This table is the only list of reasons; a document that defines a new reason adds it here and does not keep a
copy. Labels are not reasons (section 2). Which acceptance, if any, covers each reason is defined only in
`declarations.md` section 4.2; a read reports the reason and never applies an acceptance itself, except the
ones the request carries (section 1). [PR-310]

## 5. How a condition is checked

The conditions checked are those the record holds, those the field's row requires (`record_format.md` section
4.1), and those the request's `requirement.conditions` names. Each gives one entry in the result's
`conditions`, and the field's status takes the worst. A record condition is compared with the request as
follows. [PR-311]

| Record holds | Request gives | Entry |
|---|---|---|
| `{"status": "not_applicable"}`, on the form's own axis | anything | the entry is `met` when the read lies in the form's range; the form checks it (last rows) [PR-312] |
| any other status object, on any condition; or the condition is absent | anything | `unknown` (`condition_unstated`) [PR-305] [PR-323] |
| a name the reader does not know | anything | `unknown` (`condition_unknown_name`) [PR-031] |
| any stated value, range or token | no tolerance and no accept list for it | `unknown` (`condition_unchecked`) [PR-313] |
| a value `r` | operating value `v`, tolerance `t` | `met` when `abs(r - v) <= t`, else `not_met` (`condition_outside`) [PR-306] |
| a value `r` | operating range `[lo, hi]`, tolerance `t` | `met` when `r - t <= lo` and `hi <= r + t`: the whole operating range lies within the tolerance of the one value measured [PR-324] |
| a range `[a, b]` | operating value `v`, tolerance `t` | `met` when `a - t <= v <= b + t` [PR-314] |
| a range `[a, b]` | operating range `[lo, hi]`, tolerance `t` | `met` when `a - t <= lo` and `hi <= b + t` [PR-325] |
| a token | an accept list | `met` when the token is in the list, else `not_met` (`condition_not_accepted`) [PR-315] |
| a value implied by an acceptance (`declarations.md`) | as for a stated value | as for a stated value, with basis `implied` [PR-316] |

Tolerances are absolute, in the condition's registered unit. There are no relative tolerances in schema 0.1.0.

**The form's range.** A **constant's** range is its conditions: once they are met, it is read; step 11 adds
nothing. A **table** is read at the operating value of its axis, which must lie within `[x[0], x[-1]]`; the
tolerance never widens a table. A **power law** is read inside its `range`. Outside the range, the result is
`not_met` (`outside_range`), unless the request carries a declared extrapolation, in which case the result
carries the value at the nearest end of the range, the operating value, and `assumption`: the consumer
computes the extrapolated value by its declared method (`declarations.md`). [PR-317] [PR-307]

## 6. What a read returns: `want`

| `want` | constant, table, power law | interval | composition | evidence |
|---|---|---|---|---|
| `value` | the number at the operating conditions [PR-318] | `not_met` (`want_mismatch`); a declared nominal supplies `value` and `assumption` | `not_met` (`want_mismatch`) | `not_met` (`want_mismatch`) |
| `bounds` | `not_met` (`want_mismatch`) | `{"lower", "upper"}`, as stored [PR-022] | `not_met` (`want_mismatch`) | `not_met` (`want_mismatch`) |
| `components` | `not_met` (`want_mismatch`) | `not_met` (`want_mismatch`) | the components, as stored [PR-023] | `not_met` (`want_mismatch`) |
| `evidence` | `not_met` (`want_mismatch`) | `not_met` (`want_mismatch`) | `not_met` (`want_mismatch`) | the list of reports [PR-038] |

`want: reference_data` returns the whole reference-data payload, and only for the reference-data form (the
fits and reference data profile, `fits_and_reference_data.md`); on any other form it gives `want_mismatch`.
[PR-319] `want: fit` returns a fitted field's `fit` record and `want: coverage` a parameter set's `coverage`,
in the same profile; on a field without one they give `want_mismatch`. [PR-326] A read that wants a parameter
set is a family evaluation (`model_families.md`), whose result adds the outcome of each check point. A read of
a whole table over a band, for a consumer that integrates over it, is planned for the minor version that
brings such a consumer. [not yet covered]

## 7. Evaluating a table or power law in a consumer's own code

A consumer that evaluates a value form in its own code (for example in JAX, to take gradients) is an
evaluator. Vesalius's code never runs inside a consumer's computation (AD principle 2), so the consumer writes
the evaluator and checks it against the table evaluation cases. Numbers are compared with a relative tolerance
of 1e-12, taken from the case file.

1. An evaluator returns, beside the value, `in_range`: whether its condition lies inside the form's range
   (`false` for a power law whose range is unstated). It MUST NOT only clamp: a clamped value outside the
   range is an extrapolation, which needs the consumer's declaration, or `in_range` false stops the run
   (`declarations.md`). [TE-002] [TE-003]
2. Linear interpolation within `[x0, x1]` is `y0 + (x - x0) * (y1 - y0) / (x1 - x0)`. Log-log interpolation is
   `exp(ln y0 + (ln x - ln x0) * (ln y1 - ln y0) / (ln x1 - ln x0))`, in natural logarithms. [TE-004]
3. At an interior knot the derivative depends on the side. An evaluator states which side it returns there
   (`left` or `right`), and the cases give both. JAX's `jnp.interp` returns the right-hand derivative at
   interior knots and the lower end (measured in prototype P5). [TE-005] [TE-006]
4. At a table's ends, the derivative is the one from inside the range. At a repeated knot (a declared edge),
   the value and derivative below it come from the interval below, and above it from the interval above.
   [TE-007] [TE-011]
5. For a log-log table, the derivative within an interval is `(y / x) * (ln y1 - ln y0) / (ln x1 - ln x0)`.
   [TE-008]
6. For a power law, the derivative is `a * b * x^(b - 1)`, inside its range. [TE-009]
7. At a declared edge, an evaluator refuses, as the reader does. [TE-010]
8. An evaluator that cannot report `in_range` or its derivative side does not claim the table evaluation
   profile.

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-300 | plain read | no read raises; every read returns a result |
| PR-301 | plain read | every reason is reported; the status is the worst |
| PR-302 | plain read | an `unknown` result carries the value; `not_met` carries none |
| PR-304 | plain read | an absent field gives `not_met`; alternatives without a pick give `unknown` with `values` |
| PR-305 | plain read | an unstated or absent condition gives `unknown` |
| PR-306 | plain read | a stated value outside the tolerance gives `not_met`; at exactly the tolerance, `met` |
| PR-307 | plain read | outside a form's range under a declared extrapolation: `not_met`, the end value, the assumption |
| PR-308 | plain read | no `want`, a tolerance with no operating condition, or no operating value for an axis: `request_incomplete` |
| PR-309 | plain read | a value stated without origin gives `unknown` |
| PR-310 | plain read | every reason code a read gives is one of the table's |
| PR-311 | plain read | the conditions the record holds, the row requires and the request names all appear in `conditions` |
| PR-312 | plain read | the form's own axis entry is `met` when the read lies in the form's range |
| PR-313 | plain read | a stated condition with no tolerance or accept list gives `unknown` (`condition_unchecked`) |
| PR-314 | plain read | a record range against an operating value, widened by the tolerance |
| PR-315 | plain read | a token condition against an accept list |
| PR-316 | plain read | an implied condition is checked like a stated one |
| PR-317 | plain read | a constant's range is its conditions; a table's tolerance never widens the table |
| PR-318 | plain read | `want: value` on each form |
| PR-319 | plain read | `want: reference_data` on reference data and on another form |
| PR-320 | plain read | an operating condition or tolerance in another unit is refused (`request_unit_mismatch`) |
| PR-321 | plain read | a table read over an operating range of its axis gives `want_mismatch` |
| PR-322 | plain read | a table breaking a structural rule gives `form_invalid` for that field only |
| PR-323 | plain read | a condition holding `withheld`, `none`, `not_checked`, or `not_applicable` off the axis, gives `unknown` |
| PR-324 | plain read | one measured value against an operating range: met only when the whole range lies within its tolerance |
| PR-325 | plain read | a record range against an operating range, widened by the tolerance |
| PR-326 | plain read | `want: fit` and `want: coverage` on fields with and without them |
| PR-327 | plain read | a reader without HS labels its results `hash_not_checked` and still refuses a stated hash that differs from a pin |
| HS-010 | hash | a record whose recomputed hash differs from its own is refused (`hash_mismatch`) |
| HS-011 | hash | a record whose stated hash differs from a pin is refused (`pin_mismatch`), by every reader |

| TE-002 | table evaluation | `in_range` is reported beside the value, inside and outside the range |
| TE-003 | table evaluation | an evaluator that only clamps fails |
| TE-004 | table evaluation | linear and log-log values match the stated formulas |
| TE-005 | table evaluation | the left and right derivatives at each interior knot |
| TE-006 | table evaluation | the evaluator's declared side matches what it returns |
| TE-007 | table evaluation | at a table's ends, the inside derivative only |
| TE-008 | table evaluation | the derivative of a log-log table |
| TE-009 | table evaluation | the derivative of a power law inside its range |
| TE-010 | table evaluation | an evaluator refuses at a declared edge |
| TE-011 | table evaluation | values and derivatives on each side of a repeated knot |

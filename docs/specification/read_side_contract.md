# Read-side contract

Schema 0.1.0, draft. Conventions, suites and case numbers: `README.md`. Rationale: AD 3.5, 4.4 and 7.5. This
document defines what a read takes and gives, the order of its steps, how a condition is checked, and every
reason a read can give. The shapes it reads are defined in the other documents.

## 1. The read request

A read asks for one field of one material, at stated operating conditions.

| Member | Contents |
|---|---|
| `records` | the records the reader may resolve references against, each a JSON text (a case file supplies them as files; how an implementation accepts records in another form is outside this specification) |
| `target` | `{"record": {"id", "version", "content_hash"}, "field": "<section>.<field>"}`; in a scene, `{"region", "field"}`, resolved through the scene (`geometry.md`) |
| `operating_conditions` | per condition, `{"value", "unit"}` or `{"range": [lo, hi], "unit"}`, in the condition's registered unit |
| `requirement` | `want` (section 6), required; and `conditions`: per condition either `{"tolerance": {"value", "unit"}}` (absolute, in the condition's unit) or `{"accept": [<tokens>]}` |
| `acceptances` | the consumer's acceptances for this read that change what is read: a pick, an overlay, an extrapolation or a nominal, an implied condition (`declarations.md`) |

A request is read as JSON by `record_format.md` section 1 item 6, and checked on its own before any record is
read (section 3, step 0). Its shape, apart from `records`, which is supplied beside it, is exactly this:
`target` (required) holds `field` (required) and exactly one of `record`, with string `id`, `version` and
`content_hash`, and `region`; `requirement` (required) holds a string `want` and optionally `conditions`;
`operating_conditions` and `requirement.conditions` are objects keyed by condition name; an operating
condition is exactly one of `{"value", "unit"}` and `{"range": [lo, hi], "unit"}`, with numbers and a string
unit, and is given only for a numeric condition; a requirement condition is `{"tolerance": {"value", "unit"}}`
for a numeric condition or `{"accept": [<strings>]}` for a token condition (`provenance.md` section 6.1);
`acceptances` hold the shapes `declarations.md` gives. A request is refused, with the reason
`request_incomplete`, when:
- it is not valid JSON by that item, or departs from that shape in any way: a member missing or of the wrong
  JSON type, a target with both or neither of record and region, a `range` that is not two numbers, a
  `tolerance` for a token condition or an `accept` list for a numeric one;
- its field does not match `^[a-z0-9_]+\.[a-z0-9_]+$` in full;
- its `want` is not one of section 6's tokens;
- it names a condition that is not registered (`provenance.md` section 6.1);
- it gives a tolerance for a condition with no operating condition, a tolerance below zero (`-0` is not), or
  an operating range whose `lo` is greater than its `hi`. [PR-308] [PR-330]

Where the fault concerns one condition (it lies inside that condition's entry, names a condition that is not
registered, or is one of the last item's checks), the reason carries that `condition`. A tolerance whose
condition has no operating entry because `operating_conditions` is not an object gives `request_incomplete`
with that `condition`, beside the member's own `request_incomplete`, which carries none. [PR-330] A request
whose `want` belongs to a suite the reader does not claim is refused at the same step, with the reason
`want_mismatch` (section 6). [PR-332] A request is refused, with the reason `request_unit_mismatch` and that
`condition`, where an operating condition or tolerance of a registered numeric condition has a string `unit`
other than the condition's registered unit, whatever else is wrong with that entry. Units are compared as
strings, after JSON escapes are decoded, code point for code point; none is parsed or converted, so `"Cel"` is
not `"K"`, and nor is `"K"` written with U+212A KELVIN SIGN. An operating condition's or tolerance's `unit`
that is not a string is a fault of shape only (`request_incomplete`), and one on an entry for a token
condition or a condition that is not registered is compared with nothing, since neither has a registered unit.
[PR-320] A member that the shape above, or for `acceptances` `declarations.md`, does not name at that place is
ignored, at any depth (a `unit` beside an `accept` list, say), except a `tolerance` or an `accept` list given
for the other kind of condition, which is refused as above. [PR-330]

Two checks need the form, so they are made when the form is evaluated (section 3, step 11): a table or power
law read with no operating value for its axis is refused with `request_incomplete` [PR-308], and one read over
an operating range of its axis gives `want_mismatch` until a read over a band is specified (section 6).
[PR-321]

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
   `unknown` over `met`. Each step makes all its checks before the read stops. A reason, identified by its
   `code` and its `condition`, appears at most once in a result; where a check fails more than once, its
   `detail` SHOULD say so. `detail` is text for people: a reader SHOULD say there what failed, and no case
   compares it. [not yet covered] A reason carries `condition` exactly when it concerns one condition or a
   form's axis: every `condition_*` reason; `request_incomplete`, `request_unit_mismatch` and `unit_mismatch`
   where they concern one condition (an unregistered condition name included) or an axis; `outside_range`,
   `at_edge` and `range_unstated`; and `want_mismatch` for a read over a range of an axis. [PR-301] [PR-331]
3. An `unknown` result carries the value the record holds, so that a waiver has something to use. A `not_met`
   result carries no value, except where a declared extrapolation or nominal covers it: the status stays
   `not_met`, the value is present, and `assumption` names the declaration. [PR-302] [PR-307]
4. A value whose origin is `stated_without_origin` (a number found in code or a datasheet with nothing behind
   it) gives `unknown` with the reason `stated_without_origin`, which a waiver may accept, so that the
   material input sheet records it (AD 4.7). [PR-309]

## 3. The read procedure

A reader takes these steps in this order. A step that gives `not_met` ends the read, with the reasons found so
far; a step that gives `unknown` does not.

0. **Request.** Check the request on its own (section 1: `request_incomplete`, `want_mismatch` for a suite the
   reader does not claim, `request_unit_mismatch`). [PR-308] [PR-320] [PR-330]
1. **Resolve.** A material reference in a request or a scene document (the target's record, a scene's region
   or background, `geometry.md` section 1 item 3) is resolved among the records supplied (`records`) as
   follows; on a USD stage, records are found through their bindings instead (`usd_binding.md` section 5), and
   an overlay's base is compared with the record in use at step 6, not resolved.
   - Every supplied source is read as JSON (`record_format.md` section 1 item 6). An object with a
     `document_type` and no `record_type` is set aside (`record_format.md` section 3 item 2). A source that
     did not parse, or parsed to a value that is neither a set-aside document nor an object with a string `id`
     and a string `version`, is **unreadable**.
   - Every other object whose `id` and `version` are strings is a **candidate** for that `id` and `version`,
     whatever else is wrong with it, so that a record with an envelope the reader schema refuses is found,
     and refused at step 3.
   - With no candidate of the reference's `id` and `version`, the read gives `absent`, unless a supplied
     source is unreadable: then it gives `malformed`, because the record may be that source.
   - Among the candidates of the reference's `id` and `version`, the reader takes those whose stated
     `content_hash` equals the reference's. With one, the read goes on, whatever else was supplied: the pinned
     record is found, so an unreadable source beside it does not matter. With two or more whose bytes are all
     identical, it reads one; with two or more whose bytes differ, the read gives `malformed`.
   - With none whose stated hash equals the reference's, the read gives `malformed` when a supplied source is
     unreadable, or when one of the candidates of the reference's `id` and `version` has a `content_hash` that
     is absent, not a string, or not `sha256:` and 64 lowercase hexadecimal digits (`record_format.md` section
     2), because the record may be that source or that candidate; otherwise it gives `pin_mismatch`. [PR-002]
     [PR-328] [PR-329]
2. **Version.** Read `schema_version`: absent, not a string, or not matching `record_format.md` section 8's
   pattern gives `malformed`; another `MAJOR.MINOR` (before 1.0.0) gives `other_version` (`record_format.md`
   section 8). [PR-026] [PR-048]
3. **Validate** the envelope and the body's structure against the reader schema of the reader's version
   (`malformed`, `record_format.md` section 1 item 2); a shape error inside one value field is left to step 8.
4. **Hash.** Step 1 has compared the stated `content_hash` with the reference's pin. A reader that claims the
   HS suite also recomputes the hash (`record_format.md` section 9) and, when it differs from the stated one,
   gives `hash_mismatch` and, since the recomputed hash then differs from the pin as well, one `pin_mismatch`.
   A reader that does not claim HS labels `hash_not_checked` every result that reaches this step; a result
   that ends before it carries no such label. An overlay's pin on its base is compared at step 6, not here.
   [HS-010] [HS-011] [PR-327]
5. **Type.** Refuse a referenced record of a type the reader cannot read (`unknown_type`).
6. **Overlays.** Once the target has passed steps 1 to 5, resolve each overlay the acceptances name as step 1
   resolves a reference, and take it through steps 2 to 5; then apply it, and refuse a base mismatch or a
   conflict, by `record_format.md` section 4.4. The overlay's scope is compared by the build, not here
   (`declarations.md` section 5).
7. **Field.** Find the field (`absent`). For alternatives, read each, set aside those whose conditions give
   `not_met` (step 10), and with more than one left and no pick give `unknown` (`no_pick`); with none left,
   give `not_met` with the reasons of each. A pick's index counts the stored alternatives, set-aside ones
   included. [PR-304]
8. **Form and tokens.** Refuse a form the field's row does not allow (`form_not_registered`), a value field,
   form or section `specimen` that breaks its shape (`record_format.md` sections 5 and 6, `provenance.md`),
   such as a member missing or of the wrong JSON type, or `null` outside a member the reader does not know
   (`form_invalid`), a token the reader does not know (`unknown_token`), and a withheld value (`withheld`).
   [PR-322]
9. **Units.** Refuse a field unit, `axis_unit` or condition unit other than the registered one
   (`unit_mismatch`).
10. **Conditions**, by section 5.
11. **Form.** Evaluate the form at the operating conditions, within its range (section 5, last rows), with the
    two request checks that need the form (section 1). [PR-308] [PR-321]
12. **Origin and fill-in.** Give `unknown` for a value stated without origin (`stated_without_origin`) and for
    a fill-in from another version of the document (`fill_in_version_mismatch`); add the labels of section 2.
13. **Want.** Shape the value by `want` (section 6).

A parameter set needs the family evaluation suite (`model_families.md`); sampling, the sampling suite
(`uncertainty.md`); a scene, the scene suite (`geometry.md`).

## 4. Reason codes

Every reason a read can give. A document that defines a new reason adds it here.

| Code | Status | Meaning | Defined in |
|---|---|---|---|
| `malformed` | not_met | not valid JSON (`record_format.md` section 1 item 6); a `schema_version` that is absent or ill-formed; an envelope or body structure the reader schema refuses; a reference with no candidate holding its hash whose record may be an unreadable source (one that did not parse, or parsed to neither a set-aside document nor an object with a string `id` and `version`) or a candidate of the reference's `id` and `version` whose `content_hash` is ill-formed; two supplied copies of one record that differ | `record_format.md` 1; this document 3 |
| `other_version` | not_met | another schema version | `record_format.md` 8 |
| `hash_mismatch` | not_met | the recomputed hash differs from the record's own | `record_format.md` 9 |
| `pin_mismatch` | not_met | the stated hash, or with HS the recomputed hash, differs from a pin (where no candidate holds the pin, `malformed` instead when a supplied source is unreadable or a candidate of the reference's `id` and `version` has an ill-formed `content_hash`: section 3, step 1) | this document 3 |
| `unknown_type` | not_met | a referenced record of a type the reader cannot read | `record_format.md` 3 |
| `absent` | not_met | the section or field is absent, or no supplied record has the reference's `id` and `version` (`malformed` instead when a supplied source is unreadable: section 3, step 1) | `record_format.md` 1, 4; this document 3 |
| `no_pick` | unknown | alternatives remain and no pick is declared | `record_format.md` 5 |
| `form_not_registered` | not_met | a form the field's row does not allow | `record_format.md` 4.1 |
| `form_invalid` | not_met | a value field, form or section `specimen` that breaks its shape (a field that is not an object; a member missing, of the wrong JSON type or `null`; a table's lengths, order, knots or edges; a non-positive log-log value) | `record_format.md` 1, 5, 6 |
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
| `want_mismatch` | not_met | a `want` the form cannot give, or one belonging to a suite the reader does not claim | section 6 |
| `stated_without_origin` | unknown | a value with nothing behind it | section 2 |
| `family_suite_absent` | not_met | a parameter set, read without family evaluation | `record_format.md` 6 |
| `overlay_base_mismatch` | not_met | an overlay whose base differs from the record in use; never accepted | `record_format.md` 4.4 |
| `overlay_scope_mismatch` | not_met | an overlay scoped to another consumer, model or configuration (a build check) | `declarations.md` 5 |
| `overlay_conflict` | not_met | two declared overlays replace one field | `record_format.md` 4.4 |
| `request_incomplete` | not_met | a request that is not valid JSON or departs from the request's shape (a member missing or of the wrong JSON type, a reference without its `id`, `version` or `content_hash`, a target with both or neither of record and region, a field off the pattern); a `want` not in section 6; a condition that is not registered; a tolerance with no operating condition, or one below zero; an operating range with `lo` above `hi`; a table or power law with no operating value for its axis; a label given by both number and name (`geometry.md`) | section 1 |
| `request_unit_mismatch` | not_met | an operating condition or tolerance of a numeric condition whose `unit` is a string other than the registered one, compared code point for code point after JSON escapes are decoded, whatever else is wrong with the entry | section 1 |
| `owner_ambiguous` | not_met | regions with no or tied priority claim one point | `geometry.md` |
| `no_material` | not_met | no region claims a point and the scene declares no background | `geometry.md` |
| `domain_undeclared` | not_met | a domain the consumer did not declare | `geometry.md` |
| `orientation_missing` | not_met | a direction-dependent value for a region with no orientation | `geometry.md` |
| `geometry_unresolved` | not_met | a region's external geometry has no inside test the reader can use | `geometry.md` |
| `geometry_hash_mismatch` | not_met | an external geometry whose SHA-256 differs from the one stated | `geometry.md` |
| `representation_unsupported` | not_met | a 0.1.0 manifest holding precedence, a label volume or a field override | `geometry.md` |
| `homogeneity_undeclared` | not_met | a layered path without its lateral-homogeneity declaration | `geometry.md` |
| `outside_path` | not_met | a layered path read before its start or at or beyond its end | `geometry.md` |
| `label_unmapped` | not_met | a label with no material in the label crosswalk | `geometry.md` |
| `anatomy_mismatch` | not_met | a label read with another anatomy than the crosswalk's | `geometry.md` |
| `unauthored_attribute` | not_met | a value-bearing OpenMaterica attribute nobody authored | `usd_binding.md` |
| `stage_units_unauthored` | not_met | a stage with no authored `metersPerUnit` | `usd_binding.md` |
| `units_uncompensated` | not_met | geometry in other units with no compensating transform | `usd_binding.md` |
| `binding_missing` | not_met | a region with no `materica`-purpose binding | `usd_binding.md` |
| `binding_refused` | not_met | an all-purpose binding to an OpenMaterica material, a `materica`-purpose collection binding, a `materica` binding with more than one target, a conflicting `materica` binding inside a region, one to a prim with no `materica:id`, or a prim with `materica:region:` attributes that is not a region | `usd_binding.md` |
| `payload_unloaded` | not_met | a point, domain or region read that reaches an unloaded payload | `usd_binding.md` |
| `region_in_prototype` | not_met | a region under a point instancer's prototype | `usd_binding.md` |
| `time_sampled` | not_met | an OpenMaterica attribute with time samples | `usd_binding.md` |
| `engine_crosswalk_invalid` | not_met | an engine crosswalk not passed, with no source for its units, whose hash differs from its pin, that does not validate, that differs from its pinned schema file, in `materica/` but not shipped by OpenMaterica, or with a held crosswalk's id and version and another hash | `usd_binding.md` |
| `engine_value_invalid` | not_met | a declared engine value of another type than its attribute's, or a token outside the attribute's allowed tokens | `usd_binding.md` |
| `engine_attribute_unset` | not_met | an engine attribute with neither an OpenMaterica field nor a declared value | `usd_binding.md` |
| `engine_value_sourced` | not_met | a declared engine value for an attribute the crosswalk sources from a field | `usd_binding.md` |
| `engine_binding_overridden` | not_met | a region whose engine binding a foreign stronger or subset `physics` binding would override | `usd_binding.md` |
| `engine_region_instanced` | not_met | a region inside an instance, which the adapter cannot bind per region | `usd_binding.md` |
| `engine_material_missing` | not_met | a simulated shape with no engine material, or only the physics scene's | `declarations.md` |
| `engine_material_foreign` | not_met | an engine material with no stamp, or stamped for another material, or stamped with the `stage` convention for other stage units | `declarations.md` |
| `engine_material_stale` | not_met | a stamp that does not re-derive, or that differs from the current declaration | `declarations.md` |
| `engine_density_overridden` | not_met | an authored, non-zero `MassAPI` density that differs from the material's | `declarations.md` |
| `engine_mass_not_comparable` | unknown | an authored, non-zero mass, so the density cannot be compared | `declarations.md` |
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
fits and reference data suite, `fits_and_reference_data.md`); on any other form it gives `want_mismatch`.
[PR-319] `want: fit` returns a fitted field's `fit` record and `want: coverage` a parameter set's `coverage`,
in the same suite; on a field without one they give `want_mismatch`. [PR-326] A reader that does not claim the
suite a `want` belongs to gives `want_mismatch` for it, at step 0 (section 1). [PR-332] A read that wants a
parameter set is a family evaluation (`model_families.md`), whose result adds the outcome of each check point.
A read of a whole table over a band, for a consumer that integrates over it, is planned for the minor version
that brings such a consumer. [not yet covered]

## 7. Evaluating a table or power law in a consumer's own code

A consumer that evaluates a value form in its own code (for example in JAX, to take gradients) is an
evaluator. OpenMaterica's code never runs inside a consumer's computation (AD principle 2), so the consumer
writes the evaluator and checks it against the table evaluation cases. Numbers are compared with a relative
tolerance of 1e-12, taken from the case file.

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
   suite.

## Cases

| Case | Suite | Tests |
|---|---|---|
| PR-300 | plain read | no read raises; every read returns a result |
| PR-301 | plain read | every reason is reported; the status is the worst; each step makes all its checks |
| PR-302 | plain read | an `unknown` result carries the value; `not_met` carries none |
| PR-304 | plain read | an absent field gives `not_met`; alternatives without a pick give `unknown` with `values` |
| PR-305 | plain read | an unstated or absent condition gives `unknown` |
| PR-306 | plain read | a stated value outside the tolerance gives `not_met`; at exactly the tolerance, `met` |
| PR-307 | plain read | outside a form's range under a declared extrapolation: `not_met`, the end value, the assumption |
| PR-308 | plain read | no `want`, a tolerance with no operating condition (both at step 0), or no operating value for an axis (at step 11): `request_incomplete` |
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
| PR-320 | plain read | an operating condition or tolerance of a numeric condition with a string unit other than the registered one is refused (`request_unit_mismatch`, with that `condition`), whatever else is wrong with the entry; units are compared code point for code point (`Cel`, `k`, `K` with U+212A); an operating condition's or tolerance's unit that is not a string gives only `request_incomplete`; a unit on a token or unregistered condition is compared with nothing, and the entry gives `request_incomplete` only where its own shape is wrong or its condition is not registered |
| PR-321 | plain read | a table read over an operating range of its axis gives `want_mismatch` |
| PR-322 | plain read | a table breaking a structural rule gives `form_invalid` for that field only |
| PR-323 | plain read | a condition holding `withheld`, `none`, `not_checked`, or `not_applicable` off the axis, gives `unknown` |
| PR-324 | plain read | one measured value against an operating range: met only when the whole range lies within its tolerance |
| PR-325 | plain read | a record range against an operating range, widened by the tolerance |
| PR-326 | plain read | `want: fit` and `want: coverage` on fields with and without them |
| PR-327 | plain read | a reader without HS labels `hash_not_checked` the results that reach step 4, and still refuses, at step 1 and without that label, a stated hash that differs from a pin |
| PR-328 | plain read | a reference with no candidate gives `malformed` when a supplied source did not parse, or parsed to a value that is neither a set-aside document nor an object with a string `id` and `version` (an array, an object with only an `id`); otherwise `absent`; a scene manifest or an engine crosswalk among the sources is set aside and never resolved |
| PR-329 | plain read | candidates of one `id` and `version`: the one with the reference's hash is read, and identical copies are read once; none with the hash gives `pin_mismatch`, whether there is one candidate or several, unless one has an absent, `null` or ill-formed `content_hash`, or a supplied source is unreadable, which gives `malformed`; two with the hash whose bytes differ give `malformed` |
| PR-330 | plain read | `request_incomplete` for: a request that is not valid JSON, or not an object; a member missing or of the wrong JSON type; a target with neither or both of record and region; a reference without its hash; a field off the pattern (`fluid`, `a.b.c`, `Fluid.x`); a `want` not in section 6; a condition that is not registered; a `range` of three numbers; a tolerance for a token condition (with that `condition`); a tolerance below zero; an operating range with `lo` above `hi`; `operating_conditions` that is not an object beside a tolerance, with a second reason carrying the tolerance's `condition`; a tolerance of `-0` is accepted; a member the shape does not name at that place, at any depth, is ignored (a `unit` beside an `accept` list) |
| PR-331 | plain read | a reason appears once per code and condition, however many times its check fails; `condition` is present exactly on the codes section 2 lists |
| PR-332 | plain read | a `want` of a suite the reader does not claim (`fit`, `coverage`, `reference_data` without the fits and reference data suite) gives `want_mismatch` at step 0 |
| HS-010 | hash | a record whose recomputed hash differs from its own is refused (`hash_mismatch`), with one `pin_mismatch`, since its stated hash equals the pin |
| HS-011 | hash | a reader with HS refuses a record whose stated hash differs from a pin (`pin_mismatch`), and one edited after pinning whose stated hash still equals the pin (`hash_mismatch` and one `pin_mismatch`); a reader without HS refuses the first as well (PR-327's pin arm) |
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

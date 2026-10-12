# Read-side contract

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 3.5, 4.4 and 7.5. This
document gathers what any reader does, in order, and every case in which it refuses. The rules themselves are
defined where each item points; this document adds only the order, the result of a read, and what an
evaluator reports.

## 1. The result of a read

1. Every read returns a result with `status` (`met`, `not_met` or `unknown`), `reason` (text, empty only for
   `met`) and, where the record holds a value, `value`. A read never raises an error for anything a record
   contains. [PR-300]
2. An `unknown` result carries the value the record holds, so that a waiver has something to use. A `not_met`
   result carries no value. [PR-301]
3. `declarations.md` defines the members a build check adds (the requirement, the waiver, the record's
   identifier and hash) and how results are recorded in the material input sheet.

## 2. The read procedure

A reader performs these steps in this order, and stops at the first that refuses.

1. **Parse.** Read the file as JSON. A malformed record is refused for every read (`record_format.md` section
   1). [PR-302]
2. **Version.** Read `schema_version`; refuse another major version (`record_format.md` section 8).
3. **Hash.** Where the consumer pins the record by content hash, recompute the hash (`record_format.md`
   section 9) and refuse on a mismatch. Recomputing needs an RFC 8785 serialiser and SHA-256 beside the JSON
   parser. [PR-303]
4. **Type.** Skip a record of a type the reader cannot read when listing; refuse it when referenced
   (`record_format.md` section 3).
5. **Find the material.** In a plain scene, by the scene manifest's rules (`geometry.md` section 2); on a USD
   stage, from the `physics` binding authored on the region prim, never from
   `ComputeBoundMaterial("physics")`'s fall-back to an all-purpose binding (`usd_binding.md` section 5). Apply
   an overlay only when the consumer declared it (`record_format.md` section 4.4).
6. **Find the field.** An absent section or field gives `not_met`. A field with `alternatives` gives `unknown`
   unless the consumer declared its pick (`record_format.md` section 5). [PR-304]
7. **Check the unit and the tokens.** Refuse a unit other than the registered one, and a token the reader
   does not know (`record_format.md` sections 4.2 and 10).
8. **Check the conditions** against the operating conditions the consumer declared, with their tolerances
   (`declarations.md`):
   - a condition the record states as unstated gives `unknown`; [PR-305]
   - a condition name the reader does not know gives `unknown` (`record_format.md` section 10);
   - a stated condition outside the declared tolerance gives `not_met`; [PR-306]
   - the axis of a table or power law is not checked again as a condition: the form checks it (section 4).
     [TE-001]
   - specimen facts are compared with the consumer's target and reported as differences, never graded
     (`provenance.md`).
9. **Evaluate the form** (`record_format.md` section 6). Refuse outside the form's range unless the consumer
   declared an extrapolation with its basis (`declarations.md`). [PR-307]
10. **Evaluate a parameter set** only with the family evaluation profile, after its check points pass
    (`model_families.md`).
11. **Sample** only as the declared uncertainty structure allows (`uncertainty.md`).

## 3. Every refusal

A reader refuses (`not_met`), never guesses, in each of these cases. Each is defined in the document named.

| Case | Defined in |
|---|---|
| malformed JSON, or a record invalid against its schema | `record_format.md` 1 |
| a record of another major schema version | `record_format.md` 8 |
| a content hash that does not verify, for a pinned record | `record_format.md` 9 |
| a referenced record of a type the reader cannot read | `record_format.md` 3 |
| an absent section or field | `record_format.md` 1, 4 |
| a unit other than the field's registered unit | `record_format.md` 4.2 |
| a token the reader does not know in an enumerated member | `record_format.md` 10 |
| a stated condition outside the consumer's declared tolerance | `declarations.md` |
| a value outside its form's range, with no declared extrapolation | `record_format.md` 6 |
| a table read exactly at an edge, or across one | `record_format.md` 6 |
| a nominal value asked of an interval, or an interval sampled, with no declaration | `record_format.md` 6 |
| reference data asked for as a property | `record_format.md` 6 |
| a parameter set without the family evaluation profile; an unknown family or version; a failed check point | `model_families.md` |
| sampling an undeclared uncertainty structure, or `marginals` jointly | `uncertainty.md` |
| an overlay whose base hash or scope differs and is not accepted | `record_format.md` 4.4; `usd_binding.md` 6 |
| a point claimed by regions with no or tied priority; overlapping representations with no precedence | `geometry.md` 2 |
| a direction-dependent value for a region with no orientation | `geometry.md` 2.4 |
| an interface binding, in 0.1.0 | `geometry.md` 2.6 |
| a layered path without a homogeneity declaration, or read at a boundary or beyond its end | `geometry.md` 3 |
| an unmapped label | `geometry.md` 4 |
| a stage with no authored `metersPerUnit`; geometry in other units with no compensating scale | `usd_binding.md` 2 |
| an unauthored Vesalius attribute; a material prim whose hash does not verify | `usd_binding.md` 1, 3 |
| a binding a reader must refuse (all-purpose, or a different physics binding inside a region) | `usd_binding.md` 5 |
| a layered path whose arrays differ in length | `usd_binding.md` 7 |
| mixing a field with no general rule | `mixing_rules.md` |

Two cases give `unknown`, not `not_met`: an unstated condition, and a condition name the reader does not
know. Both carry the value (section 1).

## 4. Evaluating a table or power law in a consumer's own code

A consumer that evaluates a value form in its own code (for example in JAX, to take gradients) is an
evaluator. Vesalius's code never runs inside a consumer's computation (AD principle 2), so the consumer writes
the evaluator and checks it against the cases of the table evaluation profile.

1. An evaluator returns, beside the value, `in_range`: whether its condition is inside the form's range. It
   MUST NOT only clamp: a clamped value outside the range is an extrapolation, which needs the consumer's
   declaration, or `in_range` false stops the run (`declarations.md`). [TE-002] [TE-003]
2. An evaluator gives the same value as the reference reader at every knot and end of a table, and between
   them by the declared scheme. [TE-004]
3. At an interior knot of a table, the derivative depends on the side. An evaluator states which side's
   derivative it returns there (`left` or `right`), and the conformance cases give both. JAX's `jnp.interp`
   returns the right-hand derivative at interior knots (recalled from prototype P5). [TE-005] [TE-006]
4. At a table's ends, the derivative is the one from inside the range; nothing outside it is defined.
   [TE-007]
5. For a log-log table, the derivative is that of the interpolant in log-log space, mapped back:
   `dy/dx = (y / x) * (ln y1 - ln y0) / (ln x1 - ln x0)` within an interval. [TE-008]
6. For a power law, the derivative is `a * b * x^(b - 1)`, inside its range. [TE-009]
7. At a declared edge, an evaluator refuses, as the reader does. [TE-010]
8. An evaluator that cannot report `in_range` or its derivative side does not claim the table evaluation
   profile.

## 5. What a reader never does

A reader never converts units, normalises a composition, picks among alternatives, applies an undeclared
overlay, reads a USD fallback, infers a domain from which sections a material has, or extrapolates without a
declaration. Each of these is a consumer's declaration or nothing (AD principle 9).

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-300 | plain read | every read returns `status`, `reason` and, where held, `value`; no read raises |
| PR-301 | plain read | an `unknown` result carries the value; `not_met` carries none |
| PR-302 | plain read | the procedure stops at the first refusal, in the stated order |
| PR-303 | plain read | a pinned record whose recomputed hash differs is refused |
| PR-304 | plain read | an absent field gives `not_met`; alternatives without a pick give `unknown` |
| PR-305 | plain read | an unstated condition gives `unknown`, with the value |
| PR-306 | plain read | a stated condition outside the declared tolerance gives `not_met` |
| PR-307 | plain read | outside a form's range: refused, or read under a declared extrapolation |
| TE-001 | table evaluation | a table's or power law's own axis is not checked again as a condition |
| TE-002 | table evaluation | `in_range` is reported beside the value, inside and outside the range |
| TE-003 | table evaluation | an evaluator that only clamps fails |
| TE-004 | table evaluation | values at every knot and end, and between them, match the reference reader |
| TE-005 | table evaluation | the left and right derivatives at each interior knot |
| TE-006 | table evaluation | the evaluator's declared side matches what it returns |
| TE-007 | table evaluation | at a table's ends, the inside derivative only |
| TE-008 | table evaluation | the derivative of a log-log table |
| TE-009 | table evaluation | the derivative of a power law inside its range |
| TE-010 | table evaluation | an evaluator refuses at a declared edge |

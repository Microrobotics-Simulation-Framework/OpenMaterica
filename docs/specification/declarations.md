# Declarations

Schema 0.1.0, draft. Conventions, suites and case numbers: `README.md`. Rationale: AD 3.5, 4.2, 4.11, 5.5
and 9.6.

A record holds facts. A consumer declares its choices. The build checks the declarations against the records,
by the read of `read_side_contract.md`, and records both in the material input sheet. This document defines
the declaration, the result of a check, what accepts which reason, the run-time watches and the sheet.

## 1. The declaration

A consumer writes one declaration per experiment: its operating conditions, declared once, and one entry per
model that reads material fields.

```json
{
  "consumer": {"name": "mime", "version": "0.3.0"},
  "operating_conditions": {
    "temperature": {"value": 310.15, "unit": "K"},
    "shear_rate": {"range": [50.0, 500.0], "unit": "1/s"}
  },
  "models": [{
    "model": {"name": "stokes_drag", "version": "0.3.0"},
    "model_configuration_hash": "sha256:...",
    "checked_over": {"domain": "lumen"},
    "target": {"species": {"ncbi_taxon": 9606}},
    "reads": ["fluid.dynamic_viscosity"],
    "consumer_parameters": ["fluid.mu"],
    "requirements": [{
      "field": "fluid.dynamic_viscosity", "want": "value", "label": "materica.fluid.newtonian.v1",
      "conditions": {
        "temperature": {"tolerance": {"value": 1.0, "unit": "K"},
                        "reason": "viscosity falls about 2 % per kelvin near 37 °C",
                        "consequence": "1 K moves drag by about 2 %"},
        "shear_rate": {"tolerance": {"value": 0.0, "unit": "1/s"},
                       "reason": "the Newtonian label must hold over the operating shear rates"}}}],
    "families": {},
    "mixing": {"fraction_sum_tolerance": 1e-9, "rules": {"fluid.dynamic_viscosity": "refuse"}},
    "combinations": [],
    "acceptances": [
      {"acceptance": "waiver", "region": "lumen", "field": "fluid.dynamic_viscosity",
       "condition": "shear_rate", "code": "condition_unstated",
       "reason": "water is Newtonian over the band (recalled); the source states no shear rate"},
      {"acceptance": "accepted_difference", "section": "fluid", "fact": "species",
       "value": {"status": "not_applicable"}, "reason": "water has no species"}],
    "chains": [],
    "trainable": []
  }]
}
```

| Member | Contents |
|---|---|
| `consumer` | who declares: name and version |
| `operating_conditions` | per condition, `{"value", "unit"}` or `{"range": [lo, hi], "unit"}`, in the condition's registered unit, declared once for the experiment [BC-001] |
| `sampling` | for the experiment, where any requirement samples: `{"min_acceptance", "reason", "independence"}` (items 8 and 9) [BC-044] |
| `region_conditions` | per model, optional: region to operating conditions that override the experiment's there, such as a heated region [BC-001] |
| `model` | the model's name and version |
| `model_configuration_hash` | a hash of the model's whole configuration with every value read from records removed, by a procedure the consumer names in the sheet (for MIME, the graph's configuration minus the parameters the sheet derives from records) |
| `checked_over` | where requirements are checked: `{"domain": <name>}` (the regions of a scene domain, `geometry.md`), `{"path": <name>}` (every interval of a layered path, by the path's `name`) or `{"records": [<material references>]}` (records read with no scene) [BC-002] |
| `target` | the specimen facts the model stands for, each in the record's fact shape (`provenance.md` section 6.2) without `basis`; differences are computed against it (section 3) |
| `reads` | every field the model reads |
| `consumer_parameters` | every consumer parameter a record feeds; each needs a derivation in the sheet (section 9) |
| `requirements` | per field: `want` (`read_side_contract.md` section 6), required; `conditions`, per condition either `tolerance` (absolute, in the condition's unit) or `accept` (a token list), each with its `reason` and, where known, its `consequence`; optionally `label`, the label the model assumes; and `represents`, the spread its question needs where it samples (`uncertainty.md`); and, where `represents` is `population` and the field is sampled, `population_level`: `{"level", "within"}` as in `uncertainty.md` section 1, or `{"level", "balanced_over": <level>}` for a balanced draw from an ensemble [BC-043] |
| `families` | for each parameter-set field, the family version the model's evaluator implements (`model_families.md`) |
| `mixing` | `fraction_sum_tolerance`, set by the model's precision, and per field the rule the model applies in a cell holding more than one material: `identity`, a named rule, or `refuse` (`mixing_rules.md`) |
| `combinations` | lists of fields of one material, from different sections, that the model combines into one quantity (section 3) |
| `acceptances` | every pick, waiver, implied condition, accepted difference, extrapolation, nominal, distribution and overlay (section 4) |
| `chains` | hand-overs at events, as pairs of family and record (section 6) |
| `trainable` | fields the model fits, each with its region, interval or record (section 7) |
| `precision` | per model, the floating-point precision it evaluates in, `binary32` or `binary64`, where the model evaluates tables or parameter sets [BC-047] |
| `engine` | for a model that is a physics engine: `crosswalk`, the pin of its engine crosswalk (`usd_binding.md` section 10.1), OpenMaterica's or one the consumer writes and passes to the build with the declaration; `values`, per crosswalk attribute with no OpenMaterica field, `{"value", "unit", "reason", "basis"}` in SI, with no `unit` for an attribute with no dimension; and optionally `region_values`, per region, values that override `values` there, as `region_conditions` does for conditions [BC-039] |

1. Only a model that reads a field declares anything about it. A field in `reads` with no requirement gives
   `unknown` with the reason `no_requirement`. [BC-003]
2. A requirement belongs to the model that reads the field, never to the experiment as a whole. [not yet
   covered]
3. A tolerance or accept list MUST carry its reason; the build refuses one without. [BC-004]
4. Every acceptance MUST carry a `reason`; an extrapolation, a nominal and a distribution also carry the
   `basis` of their number. The build refuses one without. [BC-005]
5. A requirement with a `label` gives `not_met` with the reason `label_mismatch` when the field's label
   differs or is absent. [BC-027]
6. A layered path read with `checked_over: {"path": ...}` is named by its `name` member (`geometry.md`), and
   its intervals by their 0-based index. [BC-036]
7. A model with `engine` reads the fields its crosswalk sources, with `want` `value`, and is checked over a
   domain that does not include the background; one checked over a path or records, over a domain that
   includes the background, or with another `want`, is refused at build. A declared engine value without
   `reason` and `basis`, or for an attribute the crosswalk sources from a field, is refused at build, and so
   is a pinned crosswalk that is not passed or does not validate (`engine_crosswalk_invalid`), and two engine
   models whose domains share a region (`usd_binding.md` section 10.1 item 10). Its per-field results (section
   2) gate what the adapter writes; its engine results (section 2 item 6), after the adapter has written, gate
   the build. [BC-039] [BC-040]
8. `sampling.min_acceptance` is a number in (0, 1]: the lowest joint acceptance the consumer accepts for the
   run, below which a sampler refuses (`uncertainty.md` section 3 rule 11), with its `reason`. A declaration
   in which a requirement samples, without it or with one outside (0, 1], is refused at build. [BC-044]
9. `sampling.independence` is a list of `{"fields": [<location and field>, ...], "reason", "basis"}`. Each
   entry declares that the fields listed are sampled as independent. Every pair of fields a run samples must
   fall within one entry; a pair outside every entry is refused at build. The entries are recorded in the
   sheet. [BC-046]
10. `precision` is recorded in the sheet, and a model that evaluates tables or parameter sets without it is
    refused at build. [BC-047]

## 2. Results

The build reads every required field in every region, interval or record a model is checked over, by the read
of `read_side_contract.md`, and returns one result each: the read result (`read_side_contract.md` section 2)
with `model`, the location it was read for, `record`, `specimen_differences`, `accepted` and `accepted_by`
added. A read applies an acceptance only at its own record or region (`read_side_contract.md` section 1), and
a read request names no interval, so the build reads an interval by its record and gives that read the
acceptances located at that interval as located at that record. [not yet covered]

```json
{"model": "stokes_drag", "region": "lumen", "field": "fluid.dynamic_viscosity",
 "record": {"id": "materica/MAT-0002", "version": "1.0.0", "content_hash": "sha256:..."},
 "status": "unknown", "reasons": [{"code": "condition_unstated", "condition": "shear_rate"}],
 "value": 0.000692, "unit": "Pa.s",
 "conditions": [{"name": "temperature", "status": "met",
                 "record": {"value": 310.15, "unit": "K", "basis": "stated"},
                 "operating": {"value": 310.15, "unit": "K"}},
                {"name": "shear_rate", "status": "unknown", "record": {"status": "unstated"},
                 "operating": {"range": [50.0, 500.0], "unit": "1/s"}}],
 "specimen_differences": [{"section": "fluid", "fact": "species",
                           "record": {"status": "not_applicable"}, "target": {"ncbi_taxon": 9606}}],
 "labels": ["materica.fluid.newtonian.v1"],
 "accepted": true, "accepted_by": [0, 1]}
```

1. `status` is one of three: `met`, `not_met` or `unknown`. It states a fact about the record against the
   requirement, and declarations never change it. [BC-006]
2. The result carries `model`, and the region, interval or record it was read for. [BC-028]
3. `specimen_differences` lists, for each fact the target names, the record's fact where it differs from the
   target, as facts, never as a grade (section 3). [BC-008]
4. `accepted` is true when each reason and each specimen difference of the result is covered as the table in
   section 4.2 says, and `accepted_by` lists the 0-based indexes, in the model's `acceptances`, of every
   acceptance used, the ones the read itself applied (a pick, an overlay, an implied condition) included.
   [BC-009]
5. The build MUST refuse to build while any result is not accepted, and reports every such result, not only
   the first. [BC-010]
6. **Engine results.** A model with `engine` is judged in order: the build reads its fields; the adapter
   writes where those results are accepted (`usd_binding.md` section 10); the stage check runs; and the build
   then gives one engine result per shape of the model's regions, `{"model", "region", "shape", "status",
   "reasons"}`. An engine result states a fact about the stage, not a record. Its status is `met` unless one
   of these applies:
   - `engine_material_missing` (not_met): no engine material, or only the physics scene's (`usd_binding.md`
     section 9 item 8);
   - `engine_material_foreign` (not_met): an engine material with no stamp, or stamped for another material,
     or stamped with the `stage` convention for other stage units (item 6);
   - `engine_material_stale` (not_met): a stamp that does not re-derive (item 7), or whose crosswalk pin, read
     requests, acceptances or declared values differ from those the current declaration gives for that
     region, so engine materials written at 293 K fail a declaration at 310 K;
   - `engine_density_overridden` (not_met): an authored, non-zero effective density from
     `UsdPhysics.MassAPI` that differs (item 5);
   - `engine_mass_not_comparable` (unknown): an authored, non-zero `physics:mass` on the shape or an
     ancestor (item 5).

   The build refuses while any engine result is not accepted (section 4.2). [BC-039] [BC-041]

## 3. Specimen differences

1. For each fact the target names, the build compares the record's fact (the section's merged with the
   field's) with the target's: a species by NCBI Taxonomy identifier; an anatomical site by UBERON identifier;
   a token fact by token; a numeric fact by value, the target's value (or every value of its range) lying
   within the record's value or range. Text members are never compared. [BC-011]
2. A fact the target names that the record holds as any status object, or does not hold at all, is a
   difference, listed with the record's status object, or with no `record` where the record does not hold the
   fact. [BC-012]
3. Facts the target does not name are not compared. [not yet covered]
4. The build MAY add the ontology's relation where one exists (`relation`: `part_of`, `sibling`). [not yet
   covered]
5. A difference is listed per section, so one accepted difference for a section covers every field of it.
   [BC-013]
6. **Combinations.** A model that combines fields of one material from different sections into one quantity
   (an impedance from `bulk.density` and an acoustic sound speed) lists them in `combinations`. The build
   compares the specimen facts of those fields with each other, by the rules of item 1, and returns one result
   per combination: `{"model", location, "record", "fields": [...], "specimen_differences": [...],
   "accepted", "accepted_by"}`, each difference accepted like a difference from the target. Two fields may
   describe different specimens even when each matches the target (AD 4.2). [BC-014]

## 4. Acceptances

### 4.1 The list

One list, `acceptances`. Every entry has `acceptance`, one of the kinds below; names where it applies; names
the `field`; holds its kind's own members; and carries `reason`.

| `acceptance` | Location | Own members | Effect |
|---|---|---|---|
| `pick` | `record` (pinned by hash) | `index` (0-based, into the stored `alternatives`) | the read uses that alternative, read like any field; if its conditions are not met, its own reasons stand [BC-015] |
| `waiver` | `region`, `interval` or `record` | `code`, and `condition` where the code names one | covers one reason of one result (section 4.2) [BC-016] |
| `implied_condition` | `region`, `interval` or `record` | `fact`, a specimen fact whose shape has a `token` member, and `token`, one of its tokens (`provenance.md` section 6.2); `implies`, per registered condition `{"value", "unit"}` or `{"range": [lo, hi], "unit"}` for a numeric one and `{"token"}`, with a token of its row, for a token one: a record condition's shapes without `basis` (one there is ignored), `plus_minus` or `set_or_measured`, and never a status object (`provenance.md` section 6.1) | supplies a value for a condition the record leaves unstated, on fields whose specimen states that fact and token; the value is checked like a stated one, with basis `implied` [BC-017] |
| `accepted_difference` | optional: absent, every location the model is checked over | `section`, `fact`, `value` (in the fact's shape, or `"any"`) | covers specimen differences in that section and fact whose record value equals `value` under section 3 item 1 [BC-018] |
| `extrapolation` | `region`, `interval` or `record` | `method` (`constant` or `consumer_law`), `law` (text), `basis` | the result carries the end value and the operating value; the consumer computes the extrapolated value by its method, and the sheet records it [BC-019] |
| `nominal` | `region`, `interval` or `record` | `value`, `basis`; for a parameter set, `params` in place of `value` | supplies a value for an interval, in the field's registered unit, or the parameter vector held for a parameter set (under any structure, for one-at-a-time variation, or where `params` is not applicable), with exactly the family's parameters and passing its admissibility; refused: a value outside the interval's bounds (in a read, `nominal_invalid`), a vector with a missing or extra parameter or outside an `interval` structure's box, and an inadmissible vector [BC-020] [BC-042] |
| `distribution` | `region`, `interval` or `record` | `distribution`, `space`, `distribution_parameters`, `basis` | sampling where the record gives no distribution (section 4.3) [BC-021] |
| `overlay` | none | `overlay` (identifier, version, hash) | applies that overlay (section 5) [BC-022] |
| `overlay_scope` | none | `overlay`, `accepts` (any of `consumer`, `model`, `configuration`) | covers `overlay_scope_mismatch` for that overlay, in the members named [BC-023] |

An acceptance whose kind needs a location and names none is refused. [BC-037]

1. An implied condition never overrides a stated condition: it fills only an unstated one, which is a
   condition the record holds as `{"status": "unstated"}` or does not hold, never one holding another status
   object. A room-temperature experiment that implies 310.15 K for in vivo values still fails a 1 K tolerance
   at 293 K. [BC-017]
2. An accepted difference with `value` `"any"` accepts every value of that fact in that section; one that
   names a value accepts only that value, so accepting water's `not_applicable` species for the fluid section
   does not accept porcine blood. [BC-018]
3. An evaluator that clamps outside its range is extrapolating by a constant: it needs an extrapolation of
   method `constant`, or its in-range flag MUST stop the run (`read_side_contract.md` section 7). [not yet
   covered]

### 4.2 What covers which reason

This table is the only place that says which acceptance covers which reason (other documents cite it). A
reason not listed is never accepted. [BC-038]

| Reason | Status | Covered by |
|---|---|---|
| `condition_unstated`, `condition_unknown_name`, `condition_unchecked`, `condition_uncertain` | unknown | a `waiver` naming that condition and code |
| `no_requirement`, `stated_without_origin`, `outside_check_points`, `fill_in_version_mismatch`, `entries_withheld` | unknown | a `waiver` naming that code |
| `no_pick` | unknown | a `pick` only |
| `range_unstated`, `outside_coverage` | unknown | an `extrapolation` only |
| `outside_range` | not_met | an `extrapolation` |
| `want_mismatch`, for a value read from an interval, or a vector read from a parameter set with none | not_met | a `nominal`, only on a result whose `assumption` names it |
| `engine_mass_not_comparable` | unknown | a `waiver` naming that code |
| `overlay_scope_mismatch` | not_met | an `overlay_scope` naming every member that differs |
| a specimen difference | (not a status) | an `accepted_difference` |
| a condition reason, `outside_range`, `range_unstated`, `outside_coverage` or a specimen difference, on a field listed in `trainable` | any | its `trainable` entry (section 7) |

### 4.3 A declared distribution

```json
{"acceptance": "distribution", "region": "tissue", "field": "bulk.density", "distribution": "normal",
 "space": "identity", "distribution_parameters": {"mean": 1050.0, "sd": 25.0},
 "basis": "midpoint and quarter-width of the proxy range 1000 to 1100 kg/m3",
 "reason": "the record gives an interval only"}
```

`distribution` takes a token of `uncertainty.md` section 4 (`normal`, `lognormal`, `uniform`, `triangular`,
`student_t`, `beta`), and `distribution_parameters` that token's parameters, named as there (a lognormal's
`mean` and `sd` are of the value itself, in the field's unit); `space` is `identity` or `log` (natural
logarithms); `basis` says why. A sampler draws from it as declared, and the sheet records it as the
consumer's assumption, never as the record's statistics (`uncertainty.md` section 3).
[BC-021]

## 5. Overlays

The reader applies a declared overlay and refuses a base mismatch or a conflict (`record_format.md` section
4.4). The build compares its scope.

1. A model applies an overlay only if an `overlay` acceptance names it by identifier, version and content
   hash. [BC-022]
2. For an overlay of purpose `fit` or `scene_override`, the build compares `scope.consumer` with the declaring
   consumer's `name`, `scope.model` (name and version) with the declaring model's, and
   `scope.model_configuration_hash` with the model's, each as strings, code point for code point; a scope
   names no consumer version, so none is compared, and one without `model` or `model_configuration_hash`
   differs. For an overlay of purpose `measurement`, it compares `scope.consumer` only. A difference gives
   `overlay_scope_mismatch` (section 4.2). A `fill_in` overlay's scope names the user in `scope.consumer`, and
   is not compared. [BC-023]
3. An applied overlay replaces whole fields of its base, and the sheet records it. [BC-025]

## 6. Chains of families

```json
"chains": [{"from": {"family": "acme.thermal.arrhenius_damage.v1",
                     "record": {"id": "acme/liver_native", "version": "1.0.0", "content_hash": "sha256:..."}},
            "event": "damage_complete",
            "to": {"family": "acme.thermal.arrhenius_damage.v1",
                   "record": {"id": "acme/liver_coagulated", "version": "1.0.0",
                              "content_hash": "sha256:..."}},
            "state_mapping": {"damage": "damage"}}]
```

1. A chain names the event that ends the first family's range and the family and record that take over, with
   a mapping of state. Each `record` is a material reference, `{"id", "version", "content_hash"}`, pinned by
   its content hash as every record a consumer names is (`record_format.md` section 7 item 1). A family never
   names its successor (`model_families.md` section 5). [BC-026]
2. The build records each chain in the sheet. The run records each hand-over with its time. [not yet covered]

## 7. Trainable fields

1. A field listed in `trainable`, with its region, interval or record, is a parameter the consumer fits. Its
   result carries the label `initial_value_only`: the record's value is used only as the initial value.
2. For a trainable field, the reasons about conditions, the form's range and specimen differences are
   reported, not refused, because the consumer will move the value. Every other `not_met` reason (a malformed
   record, a hash or pin mismatch, a unit mismatch, a withheld value, an overlay's base) still refuses.
   [BC-029]
3. A fitted result is written back only as an overlay of purpose `fit` (`record_format.md` section 4.4).
   [not yet covered]

## 8. Run-time watches

1. The build emits one watch for every condition entry of every result that a tolerance or accept list
   checked: `{"model", location, "field", "condition", "unit", "source": "tolerance"}` with either `interval`
   or `accept`. The interval is the set of values the condition may take while the entry stays met:
   `[r - t, r + t]` for a stated value `r`, `[a - t, b + t]` for a stated range; where the condition's
   `plus_minus` holds a bound u, which narrows the check (`read_side_contract.md` section 5),
   `[r - t + u, r + t - u]` and `[a - t + u, b + t - u]`. Each end is its exact value rounded inward to a
   double, so that every double inside the watch keeps the entry met. An accept-list entry's watch holds the
   accept list. A constant has no axis, but a run that heats it can still leave its tolerance. An entry a
   waiver accepted as `condition_uncertain` gets the interval of a record that states no ±, `[r - t, r + t]`
   or `[a - t, b + t]`, rounded inward too. [BC-030]
2. For a table or power law, the build emits a watch with `source` `form_range`: the form's own range, never
   widened. [BC-031]
3. The consumer checks its watches during the run, on the condition, not only on the value derived from it. A
   model-validity guard on the value itself MAY stay beside them. When a watch fires, the consumer marks the
   results from that point. [not yet covered]
4. The build notes, in the sheet, a declared operating condition that sits exactly on a table knot, because a
   derivative there depends on the evaluator's side (`read_side_contract.md` section 7). [BC-032]

## 9. The material input sheet

The sheet is one JSON document per build. [BC-033]

| Member | Contents |
|---|---|
| `consumer` | as declared, with, per model, the configuration hash and the name of the procedure that computed it |
| `records` | every record read: identifier, version, schema version and content hash |
| `declaration` | the declaration as given, acceptances included |
| `results` | every result of sections 2 and 3, each with its `provenance` (origin, review result, source key, tier where the source registry is available, assistance present or not, witness and fit-reproduction status for a parameter set) and its `labels` (`read_side_contract.md` section 2) |
| `derivations` | for every consumer parameter that a record fed: the base record and field, overlays applied, unit conversions, mixing rule and fractions, derivations, any extrapolated value the consumer computed, and the parameter it reached |
| `watches` | every watch of section 8 |
| `notes` | operating conditions on table knots; anything reported but not refused |

1. Every parameter in a model's `consumer_parameters` appears in `derivations`; one with no derivation is
   reported as unexplained. [BC-034]
2. A value read through a fill-in overlay shows its label (`user_extracted`) and its review result in the
   sheet, and a value stated without origin its reason (`stated_without_origin`), so a run on a user-typed
   value never looks like a run on a curated one. [BC-035]
3. A review is reported as found in the record. The content hash does not cover reviews (`record_format.md`
   section 9), so a pinned record does not pin its review. [not yet covered]
4. The sheet is stored in the run's provenance and, where the scene is a USD stage, on the stage
   (`usd_binding.md`). [not yet covered]

## Cases

| Case | Suite | Tests |
|---|---|---|
| BC-001 | build checks | requirements are checked against the declared operating conditions, per region where overridden |
| BC-002 | build checks | requirements are checked only over what `checked_over` names: a domain's regions, a path's intervals, or listed records |
| BC-003 | build checks | a field read with no requirement gives `unknown` (`no_requirement`) |
| BC-004 | build checks | a tolerance or accept list without a reason is refused |
| BC-005 | build checks | an acceptance without a reason, or a basis where its kind needs one, is refused |
| BC-006 | build checks | declarations never change a result's status |
| BC-008 | build checks | specimen differences are listed as facts |
| BC-009 | build checks | `accepted` follows section 4.2, with `accepted_by` indexes, in-read acceptances included |
| BC-010 | build checks | the build refuses while any result is not accepted, and lists them all |
| BC-011 | build checks | each fact shape is compared with the target as stated; text members never |
| BC-012 | build checks | a fact holding a status object (unstated, not applicable, withheld), or absent from the record, against a named target fact is a difference |
| BC-013 | build checks | one accepted difference for a section covers every field of it |
| BC-014 | build checks | a combination's fields with different specimens give one combination result needing acceptance |
| BC-015 | build checks | a pick by stored index selects that alternative, which is then read like any field |
| BC-016 | build checks | a waiver covers only its own location, condition and code |
| BC-017 | build checks | an implied condition fills only an unstated or absent condition, never one holding another status object, and is checked against the tolerance |
| BC-018 | build checks | an accepted difference covers only its value, or every value with `any` |
| BC-019 | build checks | an extrapolation covers `outside_range`, `range_unstated` and `outside_coverage`; undeclared, they stand |
| BC-020 | build checks | a nominal covers a value read from an interval; one outside the bounds is refused; it covers `want_mismatch` only on a result whose `assumption` names it, never step 0's or step 7's |
| BC-021 | build checks | a declared distribution is sampled as declared and recorded as the consumer's assumption |
| BC-022 | build checks | an overlay is applied only when an acceptance names it |
| BC-023 | build checks | an overlay scope difference gives `overlay_scope_mismatch`, accepted only in the members named; `scope.consumer` is compared with the consumer's `name`; a `fit` scope without `model` or `model_configuration_hash` differs |
| BC-025 | build checks | an applied overlay is recorded in the sheet (planned with R7) |
| BC-026 | build checks | a chain is recorded as pairs of family and record (planned with R7) |
| BC-027 | build checks | a required label that differs or is absent gives `label_mismatch` |
| BC-028 | build checks | every result names its model and the region, interval or record it was read for |
| BC-029 | build checks | a trainable field's condition, range and specimen reasons are reported; its other refusals stand |
| BC-030 | build checks | a tolerance watch holds the interval, or the accept list, within which the entry stays met, narrowed by a stated bound, each end rounded inward; a waived `condition_uncertain` gets the tolerance's interval |
| BC-031 | build checks | a form-range watch is emitted for every table or power law, unwidened |
| BC-032 | build checks | an operating condition on a table knot is noted (planned with R7) |
| BC-033 | build checks | the sheet holds every member of section 9 (planned with R7) |
| BC-034 | build checks | a parameter with no derivation is reported as unexplained (planned with R7) |
| BC-035 | build checks | a fill-in value shows its label and review result, an origin-less value its reason, in the sheet (planned with R7) |
| BC-036 | build checks | a layered path is named by its `name` and its intervals by 0-based index |
| BC-037 | build checks | an acceptance with no location where its kind needs one is refused |
| BC-038 | build checks | a reason not in section 4.2's table is never accepted |
| BC-039 | build checks | an engine model's engine results: `met` on the adapter's own output; `engine_material_missing` before it writes; `engine_material_foreign` for an Isaac-bound material; `engine_material_stale` when a declaration at 310 K meets materials written at 293 K; `engine_density_overridden` under a differing `MassAPI` density |
| BC-040 | build checks | refused at build: a declared engine value without reason or basis, or for an attribute sourced from a field; a pinned crosswalk not passed, or that does not validate; two engine models whose domains share a region; an engine model checked over a path, over records, or over a domain that includes the background; one whose requirement wants anything but `value` |
| BC-041 | build checks | an explicit mass gives `engine_mass_not_comparable`, which a waiver accepts and nothing else does |
| BC-042 | build checks | a nominal vector for `ensemble`, `marginals`, `independent` or `interval`: accepted when complete and admissible, and recorded; a missing parameter, an inadmissible vector, or one outside the box is refused; it covers `want_mismatch` on a set with no vector |
| BC-043 | build checks | a sampled population requirement without `population_level` is refused at build |
| BC-044 | build checks | a declaration with a sampled requirement and no `sampling.min_acceptance`, or one outside (0, 1], is refused at build |
| BC-046 | build checks | a run that samples two fields outside every `sampling.independence` entry is refused at build; the entries are recorded |
| BC-047 | build checks | a model that evaluates tables or parameter sets without `precision` is refused at build; the precision is recorded |

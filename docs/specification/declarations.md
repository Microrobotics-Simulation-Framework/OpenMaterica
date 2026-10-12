# Declarations

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 3.5, 4.2, 4.11, 5.5
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
    "parameters": ["fluid.mu"],
    "requirements": [{
      "field": "fluid.dynamic_viscosity", "want": "value", "label": "vesalius.fluid.newtonian.v1",
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
| `region_conditions` | per model, optional: region to operating conditions that override the experiment's there, such as a heated region [BC-001] |
| `model` | the model's name and version |
| `model_configuration_hash` | a hash of the model's whole configuration with every value read from records removed, by a procedure the consumer names in the sheet (for MIME, the graph's configuration minus the parameters the sheet derives from records) |
| `checked_over` | where requirements are checked: `{"domain": <name>}` (the regions of a scene domain, `geometry.md`), `{"path": <name>}` (every interval of a layered path, by the path's `name`) or `{"records": [<material references>]}` (records read with no scene) [BC-002] |
| `target` | the specimen facts the model stands for, each in the record's fact shape (`provenance.md` section 6.2) without `basis`; differences are computed against it (section 3) |
| `reads` | every field the model reads |
| `parameters` | every consumer parameter a record feeds; each needs a derivation in the sheet (section 9) |
| `requirements` | per field: `want` (`read_side_contract.md` section 6), required; `conditions`, per condition either `tolerance` (absolute, in the condition's unit) or `accept` (a token list), each with its `reason` and, where known, its `consequence`; optionally `label`, the label the model assumes; and `represents`, the spread its question needs where it samples (`uncertainty.md`) |
| `families` | for each parameter-set field, the family version the model's evaluator implements (`model_families.md`) |
| `mixing` | `fraction_sum_tolerance`, set by the model's precision, and per field the rule the model applies in a cell holding more than one material: `identity`, a named rule, or `refuse` (`mixing_rules.md`) |
| `combinations` | lists of fields of one material, from different sections, that the model combines into one quantity (section 3) |
| `acceptances` | every pick, waiver, implied condition, accepted difference, extrapolation, nominal, distribution and overlay (section 4) |
| `chains` | hand-overs at events, as pairs of family and record (section 6) |
| `trainable` | fields the model fits, each with its region, interval or record (section 7) |

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

## 2. Results

The build reads every required field in every region, interval or record a model is checked over, by the read
of `read_side_contract.md`, and returns one result each: the read result (`read_side_contract.md` section 2)
with `model`, the location it was read for, `record`, `specimen_differences`, `accepted` and `accepted_by`
added.

```json
{"model": "stokes_drag", "region": "lumen", "field": "fluid.dynamic_viscosity",
 "record": {"id": "vesalius/VES-MAT-0002", "version": "1.0.0", "content_hash": "sha256:..."},
 "status": "unknown", "reasons": [{"code": "condition_unstated", "condition": "shear_rate"}],
 "value": 0.000692, "unit": "Pa.s",
 "conditions": [{"name": "temperature", "status": "met",
                 "record": {"value": 310.15, "unit": "K", "basis": "stated"},
                 "operating": {"value": 310.15, "unit": "K"}},
                {"name": "shear_rate", "status": "unknown", "record": {"status": "unstated"},
                 "operating": {"range": [50.0, 500.0], "unit": "1/s"}}],
 "specimen_differences": [{"section": "fluid", "fact": "species",
                           "record": {"status": "not_applicable"}, "target": {"ncbi_taxon": 9606}}],
 "labels": ["vesalius.fluid.newtonian.v1"],
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

## 3. Specimen differences

1. For each fact the target names, the build compares the record's fact (the section's merged with the
   field's) with the target's: a species by NCBI Taxonomy identifier; an anatomical site by UBERON identifier;
   a token fact by token; a numeric fact by value, the target's value (or every value of its range) lying
   within the record's value or range. Text members are never compared. [BC-011]
2. A record fact that is `{"status": "unstated"}` or `{"status": "not_applicable"}` against a fact the target
   names is a difference, listed with the record's status object. [BC-012]
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
| `implied_condition` | `region`, `interval` or `record` | `fact`, `token`, `implies` (conditions with values) | supplies a value for a condition the record leaves unstated, on fields whose specimen states that fact and token; the value is checked like a stated one, with basis `implied` [BC-017] |
| `accepted_difference` | optional: absent, every location the model is checked over | `section`, `fact`, `value` (in the fact's shape, or `"any"`) | covers specimen differences in that section and fact whose record value equals `value` under section 3 item 1 [BC-018] |
| `extrapolation` | `region`, `interval` or `record` | `method` (`constant` or `consumer_law`), `law` (text), `basis` | the result carries the end value and the operating value; the consumer computes the extrapolated value by its method, and the sheet records it [BC-019] |
| `nominal` | `region`, `interval` or `record` | `value`, `basis` | supplies a value for an interval; a nominal outside the interval's bounds is refused [BC-020] |
| `distribution` | `region`, `interval` or `record` | `distribution`, `space`, `parameters`, `basis` | sampling where the record gives no distribution (section 4.3) [BC-021] |
| `overlay` | none | `overlay` (identifier, version, hash) | applies that overlay (section 5) [BC-022] |
| `overlay_scope` | none | `overlay`, `accepts` (any of `consumer`, `model`, `configuration`) | covers `overlay_scope_mismatch` for that overlay, in the members named [BC-023] |

An acceptance whose kind needs a location and names none is refused. [BC-037]

1. An implied condition never overrides a stated condition: it fills only an unstated one. A room-temperature
   experiment that implies 310.15 K for in vivo values still fails a 1 K tolerance at 293 K. [BC-017]
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
| `condition_unstated`, `condition_unknown_name`, `condition_unchecked` | unknown | a `waiver` naming that condition and code |
| `no_requirement`, `stated_without_origin`, `outside_check_points`, `fill_in_version_mismatch` | unknown | a `waiver` naming that code |
| `no_pick` | unknown | a `pick` only |
| `range_unstated`, `outside_coverage` | unknown | an `extrapolation` only |
| `outside_range` | not_met | an `extrapolation` |
| `want_mismatch`, for a value read from an interval | not_met | a `nominal` |
| `overlay_scope_mismatch` | not_met | an `overlay_scope` naming every member that differs |
| a specimen difference | (not a status) | an `accepted_difference` |

### 4.3 A declared distribution

```json
{"acceptance": "distribution", "region": "tissue", "field": "bulk.density", "distribution": "normal",
 "space": "identity", "parameters": {"mean": 1050.0, "sd": 25.0},
 "basis": "midpoint and quarter-width of the proxy range 1000 to 1100 kg/m3",
 "reason": "the record gives an interval only"}
```

`distribution` takes the tokens and parameters of `uncertainty.md` section 4 (`normal`, `lognormal`,
`uniform`, `triangular`; a lognormal's `mean` and `sd` are of the value itself, in the field's unit); `space`
is `identity` or `log` (natural logarithms); `basis` says why. A sampler draws from it as declared, and the
sheet records it as the consumer's assumption, never as the record's statistics (`uncertainty.md` section 3).
[BC-021]

## 5. Overlays

The reader applies a declared overlay and refuses a base mismatch or a conflict (`record_format.md` section
4.4). The build compares its scope.

1. A model applies an overlay only if an `overlay` acceptance names it by identifier, version and content
   hash. [BC-022]
2. For an overlay of purpose `fit` or `scene_override`, the build compares `scope.consumer` and `scope.model`
   (name and version) with the declaring consumer and model, and `scope.model_configuration_hash` with the
   model's. For an overlay of purpose `measurement`, it compares `scope.consumer` only. A difference gives
   `overlay_scope_mismatch` (section 4.2). A `fill_in` overlay's scope names `scope.user` and is not compared.
   [BC-023]
3. An applied overlay replaces whole fields of its base, and the sheet records it. [BC-025]

## 6. Chains of families

```json
"chains": [{"from": {"family": "acme.thermal.arrhenius_damage.v1", "record": "acme/liver_native"},
            "event": "damage_complete",
            "to": {"family": "acme.thermal.arrhenius_damage.v1", "record": "acme/liver_coagulated"},
            "state_mapping": {"damage": "damage"}}]
```

1. A chain names the event that ends the first family's range and the family and record that take over, with
   a mapping of state. A family never names its successor (`model_families.md` section 5). [BC-026]
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
   `[r - t, r + t]` for a stated value `r`, `[a - t, b + t]` for a stated range. An accept-list entry's watch
   holds the accept list. A constant has no axis, but a run that heats it can still leave its tolerance.
   [BC-030]
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

1. Every parameter in a model's `parameters` appears in `derivations`; one with no derivation is reported as
   unexplained. [BC-034]
2. A value read through a fill-in overlay, or stated without origin, shows its label and its review result in
   the sheet, so a run on a user-typed value never looks like a run on a curated one. [BC-035]
3. A review is reported as found in the record. The content hash does not cover reviews (`record_format.md`
   section 9), so a pinned record does not pin its review. [not yet covered]
4. The sheet is stored in the run's provenance and, where the scene is a USD stage, on the stage
   (`usd_binding.md`). [not yet covered]

## Cases

| Case | Profile | Tests |
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
| BC-012 | build checks | an unstated or not-applicable fact against a named target fact is a difference |
| BC-013 | build checks | one accepted difference for a section covers every field of it |
| BC-014 | build checks | a combination's fields with different specimens give one combination result needing acceptance |
| BC-015 | build checks | a pick by stored index selects that alternative, which is then read like any field |
| BC-016 | build checks | a waiver covers only its own location, condition and code |
| BC-017 | build checks | an implied condition fills only an unstated condition and is checked against the tolerance |
| BC-018 | build checks | an accepted difference covers only its value, or every value with `any` |
| BC-019 | build checks | an extrapolation covers `outside_range`, `range_unstated` and `outside_coverage`; undeclared, they stand |
| BC-020 | build checks | a nominal covers a value read from an interval; one outside the bounds is refused |
| BC-021 | build checks | a declared distribution is sampled as declared and recorded as the consumer's assumption |
| BC-022 | build checks | an overlay is applied only when an acceptance names it |
| BC-023 | build checks | an overlay scope difference gives `overlay_scope_mismatch`, accepted only in the members named |
| BC-025 | build checks | an applied overlay is recorded in the sheet |
| BC-026 | build checks | a chain is recorded as pairs of family and record |
| BC-027 | build checks | a required label that differs or is absent gives `label_mismatch` |
| BC-028 | build checks | every result names its model and the region, interval or record it was read for |
| BC-029 | build checks | a trainable field's condition, range and specimen reasons are reported; its other refusals stand |
| BC-030 | build checks | a tolerance watch holds the interval, or the accept list, within which the entry stays met |
| BC-031 | build checks | a form-range watch is emitted for every table or power law, unwidened |
| BC-032 | build checks | an operating condition on a table knot is noted |
| BC-033 | build checks | the sheet holds every member of section 9 |
| BC-034 | build checks | a parameter with no derivation is reported as unexplained |
| BC-035 | build checks | a fill-in or origin-less value shows its label and review result in the sheet |
| BC-036 | build checks | a layered path is named by its `name` and its intervals by 0-based index |
| BC-037 | build checks | an acceptance with no location where its kind needs one is refused |
| BC-038 | build checks | a reason not in section 4.2's table is never accepted |

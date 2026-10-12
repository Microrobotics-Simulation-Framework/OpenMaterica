# Declarations

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 3.5, 4.11, 5.5 and
9.6.

A record holds facts. A consumer declares its choices. The build checks the declarations against the records
and records both in the material input sheet. This document defines the declaration, the result of a check,
the run-time watches and the sheet.

## 1. The declaration

A consumer writes one declaration per experiment: operating conditions declared once, and one entry per model
that reads material fields.

```json
{
  "consumer": {"name": "mime", "version": "0.3.0", "model_configuration_hash": "sha256:..."},
  "operating_conditions": {"temperature": {"value": 310.15, "unit": "K"}},
  "models": [{
    "model": "stokes_drag",
    "domain": "lumen",
    "target": {"species": "NCBITaxon:9606", "tissue_state": "in_vivo"},
    "requirements": [{
      "field": "fluid.dynamic_viscosity", "unit": "Pa.s", "want": "value",
      "conditions": {"temperature": {"tolerance": 1.0, "unit": "K",
                     "reason": "viscosity falls about 2 % per kelvin near 37 °C",
                     "consequence": "1 K moves drag by about 2 %"}}}],
    "families": {},
    "mixing": {"fluid.dynamic_viscosity": "refuse"},
    "picks": [],
    "waivers": [],
    "implied_conditions": [],
    "accepted_differences": [],
    "assumptions": [],
    "overlays": [],
    "chains": [],
    "trainable": ["fluid.dynamic_viscosity"]
  }]
}
```

| Member | Contents |
|---|---|
| `consumer` | who declares, and a hash of the consumer's whole model configuration (for MIME, the graph's `to_dict()` with mesh, time step and precision) |
| `operating_conditions` | the conditions the experiment runs at, declared once; every requirement is checked against them [BC-001] |
| `domain` | the declared domain the model computes in (`geometry.md`); requirements are checked over its regions only [BC-002] |
| `target` | the specimen facts the model stands for (`provenance.md`); differences are computed against it (section 3) |
| `requirements` | per field: the unit, `want` (`value`, `bounds` or `parameter_set`) and, per condition, a tolerance with its `reason` and, where known, its `consequence` |
| `families` | for each parameter-set field, the family version the model's evaluator implements |
| `mixing` | per field, the rule the model applies in a cell holding more than one material (`mixing_rules.md`), or `refuse` |
| `picks` | for a field with alternatives, which one, with a reason (`record_format.md` section 5) |
| `waivers` | an `unknown` result accepted, per region, field and condition, with a reason |
| `implied_conditions` | a specimen fact taken to imply a condition ("values measured in vivo are at body temperature"), with a reason; it replaces a waiver per field |
| `accepted_differences` | a difference between a record's specimen and the target accepted, per section and fact, with a reason |
| `assumptions` | what the model assumes where a record gives nothing: an `extrapolation` outside a range, a `nominal` for an interval, or a `distribution` to sample, each with its method and basis |
| `overlays` | overlays the model applies, by identifier and hash, and whether it accepts a difference of scope |
| `chains` | hand-overs at events, as pairs of family and record (section 5) |
| `trainable` | fields the model will fit (section 6) |

1. Only a model that reads a field declares anything about it. A field a model reads with no requirement
   declared for it gives `unknown`. [BC-003]
2. A requirement belongs to the model that reads the field, never to the experiment as a whole. [not yet
   covered]
3. A tolerance MUST carry its reason. The build refuses a tolerance without one. [BC-004]
4. Every pick, waiver, implied condition, accepted difference, assumption and overlay MUST carry a reason or a
   basis; the build refuses one without. [BC-005]

## 2. Results

The build checks every requirement for every region of the model's domain and returns one result each.

```json
{"region": "lumen", "field": "fluid.dynamic_viscosity",
 "record": {"id": "vesalius/VES-MAT-0002", "content_hash": "sha256:..."},
 "status": "unknown", "value": 0.000692, "reason": "condition 'shear_rate' unstated",
 "specimen_differences": [{"fact": "species", "record": "NCBITaxon:9913", "target": "NCBITaxon:9606"}],
 "accepted": true, "accepted_by": [{"waiver": 0}, {"accepted_difference": 2}]}
```

1. `status` is one of three: `met`, `not_met` or `unknown`. It states a fact about the record against the
   requirement, and declarations never change it. [BC-006]
2. An `unknown` result carries the value the record holds, so a waiver has something to use. A `not_met`
   result carries no value, except where an assumption covers it (item 4). [BC-007]
3. `specimen_differences` lists each fact in which the record's specimen differs from the target, as facts,
   never as a grade (`provenance.md`). [BC-008]
4. `accepted` is true only when the status is `met`, or `unknown` with a waiver or an implied condition that
   covers it, or `not_met` only because the value lies outside a range or is an interval, with an assumption
   that covers it; and when every specimen difference has an accepted difference. `accepted_by` names the
   declarations used. [BC-009]
5. The build MUST refuse to build while any result is not accepted, and reports every such result, not only
   the first. [BC-010]

## 3. Picks, waivers and assumptions

1. A field with alternatives gives `unknown` until a pick names one (`record_format.md` section 5). [BC-011]
2. A waiver applies only to `unknown`. It never accepts `not_met`. [BC-012]
3. An implied condition applies to every field whose specimen states the named fact, and is recorded once.
   [BC-013]
4. An accepted difference names a section and a fact (and MAY name the value), so "accept porcine data for
   acoustics" is one declaration. [BC-014]
5. An `extrapolation` assumption names the field, the region and the method (a stated law, a temperature
   coefficient, a constant). An evaluator that clamps outside its range is extrapolating by a constant: it
   needs this declaration, or its in-range flag MUST stop the run (`read_side_contract.md`). [BC-015]
6. A `nominal` assumption names the value the model uses for an interval and its basis; a `distribution`
   assumption names the distribution to sample and its basis (`uncertainty.md`). [BC-016]

## 4. Overlays

1. A model applies an overlay only if `overlays` names it by identifier and content hash. [BC-017]
2. The build compares the overlay's `scope.model_configuration_hash` with the consumer's. A difference gives
   `not_met`, unless the declaration accepts the difference of scope with a reason. [BC-018]
3. An applied overlay replaces whole fields of its base (`record_format.md` section 4.4), and the sheet
   records it. [BC-019]

## 5. Chains of families

```json
"chains": [{"from": {"family": "acme.thermal.arrhenius_damage.v1", "record": "acme/liver_native"},
            "event": "damage_complete",
            "to": {"family": "acme.thermal.arrhenius_damage.v1", "record": "acme/liver_coagulated"},
            "state_mapping": {"damage": "damage"}}]
```

1. A chain names the event that ends the first family's range and the family and record that take over, with
   a mapping of state. A family never names its successor (`model_families.md` section 5). [BC-020]
2. The build records each chain in the sheet. The run records each hand-over with its time. [not yet covered]

## 6. Trainable fields

1. A field listed in `trainable` is a parameter the consumer fits. The sheet marks it "record value used only
   as the initial value", and its result describes the initial value only. [BC-021]
2. A fitted result is written back only as an overlay, scoped as in `record_format.md` section 4.4.

## 7. Run-time watches

1. The build emits a watch for every declared (region, field, condition, tolerance): the interval the
   condition may move within, in its unit. A constant has no axis, but a run that heats it can still leave
   its tolerance. [BC-022]
2. The build also emits a watch for every table or power-law evaluator's own range. [BC-023]
3. The consumer checks its watches during the run, on the condition, not only on the value derived from it.
   A model-validity guard on the value itself MAY stay beside them. When a watch fires, the consumer marks the
   results from that point. [not yet covered]
4. The build reports, as a note in the sheet, a declared operating condition that sits exactly on a table
   knot, because a derivative there depends on the evaluator's side (`read_side_contract.md`). [BC-024]

## 8. The material input sheet

The sheet is one JSON document per build. [BC-025]

| Member | Contents |
|---|---|
| `consumer` | as declared, with the model configuration hash |
| `records` | every record read: identifier, version, schema version and content hash |
| `declaration` | the declaration as given |
| `results` | every result of section 2 |
| `derivations` | for every consumer parameter that a record fed: the base record and field, overlays applied, unit conversions, mixing rule and fractions, derivations, and the parameter it reached |
| `assumptions` | every pick, waiver, implied condition, accepted difference, assumption and overlay applied |
| `watches` | every watch of section 7 |
| `notes` | operating conditions on table knots; trainable fields; anything reported but not refused |

1. Every consumer parameter that a record fed appears in `derivations`; a parameter with no derivation is
   reported as unexplained. [BC-026]
2. The sheet is stored in the run's provenance and, where the scene is a USD stage, on the stage beside the
   simulation graph (`usd_binding.md`). [not yet covered]

## Cases

| Case | Profile | Tests |
|---|---|---|
| BC-001 | build checks | a requirement is checked against the declared operating conditions |
| BC-002 | build checks | a requirement is checked over the domain's regions only |
| BC-003 | build checks | a field read with no requirement declared gives `unknown` |
| BC-004 | build checks | a tolerance without a reason is refused |
| BC-005 | build checks | a waiver, pick, assumption or overlay without a reason or basis is refused |
| BC-006 | build checks | declarations never change a result's status |
| BC-007 | build checks | an `unknown` result carries the record's value |
| BC-008 | build checks | specimen differences are listed as facts |
| BC-009 | build checks | `accepted` follows exactly the rules of section 2 |
| BC-010 | build checks | the build refuses while any result is not accepted, and lists them all |
| BC-011 | build checks | alternatives without a pick give `unknown` |
| BC-012 | build checks | a waiver never accepts `not_met` |
| BC-013 | build checks | an implied condition covers every field stating its fact |
| BC-014 | build checks | an accepted difference by section and fact covers all fields of that section |
| BC-015 | build checks | an extrapolation is refused when undeclared and recorded when declared; a clamping evaluator without one stops the run |
| BC-016 | build checks | a nominal or distribution for an interval is used only when declared |
| BC-017 | build checks | an undeclared overlay is not applied |
| BC-018 | build checks | an overlay whose configuration hash differs gives `not_met` unless the difference is accepted |
| BC-019 | build checks | an applied overlay is recorded in the sheet |
| BC-020 | build checks | a chain is recorded as pairs of family and record |
| BC-021 | build checks | a trainable field is marked "record value used only as the initial value" |
| BC-022 | build checks | a watch is emitted for every declared condition with its tolerance |
| BC-023 | build checks | a watch is emitted for every table or power-law evaluator's range |
| BC-024 | build checks | an operating condition on a table knot is noted |
| BC-025 | build checks | the sheet holds every member of section 8 |
| BC-026 | build checks | a consumer parameter with no derivation is reported as unexplained |

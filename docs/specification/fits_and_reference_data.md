# Fits and reference data

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Member names: `record_format.md`.
Reason codes: `read_side_contract.md` section 4. Rationale: AD 4.4, 4.6, 4.10 and 5.5. Profile: FD, optional
until the minor version that brings its first consumer (README).

A fitted value is not an intrinsic property of a material. It belongs to a material, a model, a test protocol
and a fitting procedure together, and its coverage is a fact about the fit, never a validated regime (AD
4.10). Whether a fit applies at an operating point is the consumer's declaration, checked against the coverage
(`declarations.md`).

## 1. Reference data

Reference data are the measured responses that fits are made to and witnesses are taken from. They are a value
form of their own (`record_format.md` section 6). A reader returns them only to a request whose `want` is
`reference_data`, whole, and never as a property's value. [FD-001]

```json
"reference_data": {
  "shape": "curves",
  "axes": [{"quantity": "stretch", "measure": "stretch_ratio", "unit": "1"},
           {"quantity": "stress", "measure": "nominal_stress", "unit": "Pa"}],
  "curves": [{"label": "specimen 3", "x": [1.0, 1.05, 1.10], "y": [0.0, 1.2e3, 3.1e3],
              "use": "used_in_fit", "digitised": true,
              "digitiser": {"tool": "...", "axis_calibration": {"x": [[1.0, 112], [1.2, 498]],
                                                                "y": [[0.0, 610], [1.0e4, 87]],
                                                                "scale": ["linear", "linear"]},
                            "digitising_error": {"x": 0.002, "y": 50.0}},
              "provenance": {}}]
}
```

1. `shape` is `points` or `curves`. [FD-001]
2. `axes` names each axis's quantity, the measure it is expressed in (nominal or Cauchy stress, stretch or
   strain), and its unit. The measure is quoted from the source in the evidence, because a curve read under
   the wrong measure is fitted perfectly by the wrong parameters (AD 4.6). The value field's `unit` is the
   last axis's unit. [RC-080]
3. Each point or curve carries its own `provenance`, with its own origin, and a `use`: `used_in_fit`,
   `held_out` (left out of every fit, so it can witness one), or `not_used`. [FD-002] [RC-081]
4. A digitised curve carries `"digitised": true` and the digitiser's tool, axis calibration (two known points
   per axis, in data and pixel coordinates, and each axis's scale) and digitising error. A reader returns
   these with the curve. [FD-003] [RC-082]
5. `points` is a list of `{"x": [<one number per axis but the last>], "y": <number>, "use", "provenance"}`;
   `curves` is a list of `{"label", "x": [...], "y": [...], "use", "provenance"}`, `x` and `y` of equal
   length, for two axes. [FD-004]
6. A reference-data field's `statistics` holds `{"status": "not_applicable"}`; a spread, where stated, sits on
   the point or curve as its digitising error or its own statistics block (`uncertainty.md`). [FD-005]

## 2. The fit record

A value field whose `provenance.origin` is `fitted` carries `fit` (`record_format.md` section 5): a fitted
parameter set, and equally a fitted constant, such as a viscosity a consumer fitted to a trajectory and wrote
back as an overlay (`record_format.md` section 4.4). [FD-006]

```json
"fit": {
  "data": [{"record": {"id": "vesalius/VES-MAT-0007", "version": "1.0.0", "content_hash": "sha256:..."},
            "field": "mechanical.uniaxial_response"},
           {"external": {"document": {"identifier": "doi:10.1000/xyz123", "version": "version_of_record"},
                         "sha256": "...",
                         "locator": {"type": "figure", "label": "Figure 3", "page": 7}}}],
  "method_type": "single_fit",
  "procedure": {"method": "least_squares", "objective": "...", "weights": "...",
                "bounds": {}, "initial_values": {}, "software": "..."},
  "n_data": 42, "n_params": 3,
  "determination": "overdetermined",
  "residual": {"metric": "rms", "value": 850.0, "unit": "Pa"},
  "reproduction_tolerance": {"relative": 1.0e-3, "absolute": 0.0, "reason": "least-squares stopping tolerance"}
}
```

1. `data` names every dataset the fit used: reference data in a record, by identifier, version, content hash
   and field; or data not shipped, by the `document` and `locator` shapes of `provenance.md` section 2 and the
   SHA-256 of the file used. [RC-083]
2. `procedure` states the method, objective, weights, bounds, initial values and software. [RC-083]
3. `determination` is `overdetermined` where `n_data > n_params`, `exactly_determined` where they are equal,
   and `underdetermined` where `n_data < n_params`. An exactly determined fit's residual is zero by
   construction and shows nothing, and an underdetermined fit's parameters are not determined by its data: a
   reader returns the determination with the residual, and a checker never counts either as evidence. [FD-007]
   [RC-084]
4. `method_type` is `single_fit`, or `mean_of_specimen_fits` for a parameter set that is the mean of
   per-specimen fits. Such a mean may describe no specimen (`uncertainty.md` section 2). Its witness is taken
   against per-specimen data, or it has none and is reported "no independent witness"; its residual against
   the source's mean curve never sets a witness tolerance (`model_families.md`). [RC-085]
5. Several fits that describe one curve equally well are kept as alternatives (`record_format.md` section 5),
   and sources are compared on curves, not on parameters (AD 4.10). [not yet covered]
6. A tolerance passes when `abs(d) <= absolute + relative * abs(expected)`, its `reason` saying why it was
   chosen. [FD-008]

## 3. Coverage

`coverage` states what the fit, or the source of a reported parameter set, covered. It is a fact about the
data, and never says that the model holds there.

```json
"coverage": {
  "modes": [
    {"mode": "uniaxial_tension", "ranges": {"stretch": [1.0, 1.25]},
     "histories": [{"shape": "ramp", "strain_rate": {"range": [1.0e-3, 1.0e-1], "unit": "1/s"}}]},
    {"mode": "simple_shear", "ranges": {"shear_strain": [0.0, 0.3]}}
  ],
  "invariant": {"measure": "principal_stretches",
                "ranges": [[1.0, 1.25], [0.89, 1.0], [0.86, 1.0]],
                "rate": {"range": [1.0e-3, 1.0e-1], "unit": "1/s"}}
}
```

1. `modes` is a list: one entry per loading mode, with the ranges and, for an evolution family, the histories
   (`shape` is `ramp`, `step`, `hold` or `oscillation`, each with its rates, hold times or frequencies)
   covered in it. Modes fitted separately never make a joint range: a reader returns the list and never merges
   it into a box. [FD-009] [FD-010] [RC-086]
2. A mode's `mode` takes the tokens its family's definition lists for its loading modes
   (`model_families.md`); coverage has no global vocabulary of modes. [RC-089]
3. `invariant` restates the coverage in a measure that does not depend on the loading mode: one of the
   family's `coverage_measures` (`model_families.md`), such as `principal_stretches`, with the rate. Principal
   stretches are listed in descending order, `λ1 >= λ2 >= λ3`; in the example, incompressible tension to a
   stretch of 1.25 takes the lateral stretches to 0.894, and simple shear to a shear of 0.3 takes the smallest
   to 0.861. The ranges are each measure's envelope over the modes, so a general state inside them is reported
   "inside the invariant envelope", never as inside a fitted mode; a state outside them gives `unknown`
   (`outside_coverage`; what accepts it: `declarations.md` section 4.2). [FD-011]
4. A history-valued requirement (strain rates up to 1 per second) is checked against `histories`
   (`declarations.md`). [FD-012]

## 4. Fit reproduction

1. A checker evaluates the fitted value, with its family's reference implementation where it is a parameter
   set, against every dataset in `data` that it can read, and requires the recomputed residual to match the
   stated one within `reproduction_tolerance` (section 2.6). [RC-087]
2. Where any dataset is not shipped, the result is `{"status": "not_checked"}`, reported as such and never as
   a pass. [RC-088]
3. Fit reproduction cannot fail on a misread axis or the wrong measure, so it is never shown as evidence that
   the parameters match their source. That is the witness's job (`model_families.md`). [FD-013]

## Cases

| Case | Profile | Tests |
|---|---|---|
| FD-001 | fits and reference data | reference data of both shapes are read whole by `want: reference_data`, never as a property |
| FD-002 | fits and reference data | each point and curve is returned with its own origin and use |
| FD-003 | fits and reference data | a digitised curve is returned with its calibration and digitising error |
| FD-004 | fits and reference data | points and curves in their stated shapes; unequal curve arrays are refused |
| FD-005 | fits and reference data | a reference-data field's statistics are not applicable; per-point spreads are returned |
| FD-006 | fits and reference data | a fitted constant is returned with its fit record |
| FD-007 | fits and reference data | exactly determined and underdetermined fits are returned with their determination |
| FD-008 | fits and reference data | a tolerance combines its absolute and relative parts |
| FD-009 | fits and reference data | coverage is returned as a list of modes, never merged into a box |
| FD-010 | fits and reference data | coverage histories are returned with their shapes and rates, hold times or frequencies |
| FD-011 | fits and reference data | principal-stretch coverage in descending order; a state inside the envelope is reported as such |
| FD-012 | fits and reference data | a history-valued requirement is checked against the histories |
| FD-013 | fits and reference data | fit reproduction is never reported as evidence about a value |
| RC-080 | record checks | an axis without its quantity, measure and unit, or a measure not quoted, is flagged |
| RC-081 | record checks | a point or curve without its origin or use is flagged |
| RC-082 | record checks | a digitised curve without calibration or digitising error is flagged |
| RC-083 | record checks | a fit record without its data, procedure, counts or residual, or on a value not `fitted`, is flagged |
| RC-084 | record checks | a determination that does not match the counts is flagged |
| RC-085 | record checks | a mean of specimen fits witnessed by its mean curve is flagged |
| RC-086 | record checks | coverage written as one box across modes fitted separately is flagged |
| RC-087 | record checks | the recomputed residual matches the stated one within the stated tolerance |
| RC-088 | record checks | a fit to data not shipped reports `not_checked`, never a pass |
| RC-089 | record checks | a coverage mode whose loading mode is not one its family lists is flagged |

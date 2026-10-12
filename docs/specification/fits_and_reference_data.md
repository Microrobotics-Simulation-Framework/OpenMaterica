# Fits and reference data

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Member names: `record_format.md`.
Rationale: AD 4.4, 4.6 and 4.10.

A fitted parameter set is not an intrinsic property of a material. It belongs to a material, a model, a test
protocol and a fitting procedure together, and its coverage is a fact about the fit, never a validated
regime (AD 4.10). Whether a fit applies at an operating point is the consumer's declaration, checked against
the coverage (`declarations.md`).

## 1. Reference data

Reference data are the measured responses that fits are made to and witnesses are taken from. They are a
value form of their own (`record_format.md` section 6), and a reader never returns them as a property's value.

```json
"reference_data": {
  "kind": "curves",
  "axes": [{"quantity": "stretch", "measure": "stretch_ratio", "unit": "1"},
           {"quantity": "stress", "measure": "nominal_stress", "unit": "Pa"}],
  "curves": [{"label": "specimen 3", "x": [1.0, 1.05, 1.10], "y": [0.0, 1.2e3, 3.1e3],
              "status": "used_in_fit", "digitised": true,
              "digitiser": {"tool": "...", "axis_calibration": {"x": [[1.0, 112], [1.2, 498]],
                                                                "y": [[0.0, 610], [1.0e4, 87]],
                                                                "scale": ["linear", "linear"]},
                            "digitising_error": {"x": 0.002, "y": 50.0}},
              "provenance": {}}]
}
```

1. `kind` is `points` or `curves`. [PR-200]
2. `axes` names each axis's quantity, the measure it is expressed in (nominal or Cauchy stress, stretch or
   strain), and its unit. The measure is quoted from the source in the evidence, because a curve read under
   the wrong measure is fitted perfectly by the wrong parameters (AD 4.6). The value field's `unit` is the
   last axis's unit. [RC-080]
3. Each point or curve carries its own `provenance`, with its own origin, and a `status`: `used_in_fit`,
   `held_out` (left out of every fit, so it can witness one), or `not_used`. [PR-201] [RC-081]
4. A digitised curve carries `"digitised": true` and the digitiser's tool, axis calibration (two known points
   per axis, in data and pixel coordinates, and each axis's scale) and digitising error. A reader returns
   these with the curve. [PR-202] [RC-082]
5. Points carry `x` as an array of one value per axis but the last, and `y`; curves carry arrays.

## 2. The fit record

A fitted parameter set holds `fit` and `coverage` beside its parameters (`model_families.md`).

```json
"fit": {
  "data": [{"record": {"id": "vesalius/VES-MAT-0007", "content_hash": "sha256:..."},
            "field": "mechanical.uniaxial_response"},
           {"external": {"doi": "10.1000/xyz123", "sha256": "...", "locator": "Figure 3"}}],
  "kind": "single_fit",
  "procedure": {"method": "least_squares", "objective": "...", "weights": "...",
                "bounds": {}, "initial_values": {}, "software": "..."},
  "n_data": 42, "n_params": 3,
  "determination": "overdetermined",
  "residual": {"metric": "rms", "value": 850.0, "unit": "Pa"},
  "reproduction_tolerance": {"relative": 1.0e-3}
}
```

1. `data` names every dataset the fit used: reference data in a record, by identifier, content hash and field;
   or data not shipped, by DOI, the SHA-256 of the file used, and a locator. [RC-083]
2. `procedure` states the method, objective, weights, bounds, initial values and software. [RC-083]
3. `determination` is `overdetermined` where `n_data` exceeds `n_params`, and `exactly_determined` otherwise.
   An exactly determined fit's residual is zero by construction and shows nothing: a reader returns the
   determination with the residual, and a checker never counts that residual as evidence. [PR-203] [RC-084]
4. `kind` is `single_fit`, or `mean_of_specimen_fits` for a parameter set that is the mean of per-specimen
   fits. Such a mean may describe no specimen (`uncertainty.md` section 2). Its witness is taken against
   per-specimen data, or its witness is `{"status": "none"}` and it is reported as "no independent
   witness"; its residual against the source's mean curve never sets a witness tolerance
   (`model_families.md`). [RC-085]
5. Several fits that describe one curve equally well are kept as alternatives (`record_format.md` section 5),
   and sources are compared on curves, not on parameters (AD 4.10). [not yet covered]

## 3. Coverage

`coverage` states what the fit, or the source of a reported parameter set, covered. It is a fact about the
data, and never says that the model holds there.

```json
"coverage": {
  "modes": [
    {"loading_mode": "uniaxial_tension", "ranges": {"stretch": [1.0, 1.25]},
     "histories": [{"kind": "ramp", "strain_rate": {"range": [1.0e-3, 1.0e-1], "unit": "1/s"}}]},
    {"loading_mode": "simple_shear", "ranges": {"shear_strain": [0.0, 0.3]}}
  ],
  "invariant": {"measure": "principal_stretches",
                "ranges": [[0.89, 1.25], [0.89, 1.06], [0.89, 1.06]],
                "rate": {"range": [1.0e-3, 1.0e-1], "unit": "1/s"}}
}
```

1. `modes` is a list: one entry per loading mode, with the ranges and, for an evolution family, the histories
   (`ramp`, `step`, `hold`, `oscillation`, each with its rates, hold times or frequencies) covered in it.
   Modes fitted separately never make a joint range: a reader returns the list and never merges it into a
   box. [PR-204] [RC-086]
2. `invariant` restates the coverage in a measure that does not depend on the loading mode (`measure` is one
   of the family's `coverage_measures`, `model_families.md`, such as `principal_stretches` or `invariants`),
   with the rate, so a consumer whose state is a general deformation,
   inside a solver, can be checked against it. A general state outside it is `unknown` unless the consumer
   declares it (`declarations.md`). [PR-205]
3. A history-valued requirement (strain rates up to 1 per second) is checked against `histories`
   (`declarations.md`). [PR-206]

## 4. Fit reproduction

1. A checker evaluates the parameter set, with its family's reference implementation, against every dataset
   in `data` that it can read, and requires the recomputed residual to match the stated one within
   `reproduction_tolerance`. [RC-087]
2. Where any dataset is not shipped, the result is `{"status": "not_checked"}`, reported as such and never as
   a pass. [RC-088]
3. Fit reproduction cannot fail on a misread axis or the wrong measure, so it is never shown as evidence that
   the parameters match their source. That is the witness's job (`model_families.md`). [RC-089]

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-200 | plain read | reference data of both kinds are read with their axes, never as a property |
| PR-201 | plain read | each point and curve is returned with its own origin and status |
| PR-202 | plain read | a digitised curve is returned with its calibration and digitising error |
| PR-203 | plain read | an exactly determined fit's residual is returned with its determination |
| PR-204 | plain read | coverage is returned as a list of modes, never merged into a box |
| PR-205 | plain read | mode-independent coverage is returned with its measure and rate |
| PR-206 | plain read | coverage histories are returned with their rates, hold times or frequencies |
| RC-080 | record checks | an axis without its quantity, measure and unit, or a measure not quoted, is flagged |
| RC-081 | record checks | a point or curve without its origin or status is flagged |
| RC-082 | record checks | a digitised curve without calibration or digitising error is flagged |
| RC-083 | record checks | a fit record without its data, procedure, counts or residual is flagged |
| RC-084 | record checks | a fit with no more data than parameters not marked exactly determined is flagged |
| RC-085 | record checks | a mean of specimen fits witnessed by its mean curve is flagged |
| RC-086 | record checks | coverage written as one box across modes fitted separately is flagged |
| RC-087 | record checks | the recomputed residual matches the stated one within the stated tolerance |
| RC-088 | record checks | a fit to data not shipped reports `not_checked`, never a pass |
| RC-089 | record checks | fit reproduction is never reported as evidence about a value |

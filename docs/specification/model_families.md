# Model families

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 4.5, 4.6, 4.10 and
7.6. The family evaluation profile (FE) is optional in 0.1.0; its first consumer arrives with Vesalius 0.2
(AD 12.1, R5).

## 1. What a family is

1. A model family is a namespaced, versioned definition of a model, identified as
   `<namespace>.<path>.v<N>` (`record_format.md` section 7), for example `vesalius.magnetic.langevin.v1`. A
   common name alone never identifies a family (AD 4.5). [RC-060]
2. A family version is frozen once released. Changing anything in it (an equation, a parameter, a golden
   vector, its reference implementation) creates a new version. Each family version has its own content hash,
   computed as for records (`record_format.md` section 9) over its definition manifest, vectors and reference
   implementation. [RC-061]
3. A reader that meets a family identifier or version it does not know MUST refuse the value. [FE-001]
4. A record holds parameters only in its family's own convention. A conversion to a solver's convention is an
   adapter outside the record, with its own vectors showing that the solver's form reproduces the family's
   outputs. [not yet covered]

## 2. Entry and admission

1. Only reviewed pull requests to Vesalius's repositories publish under `vesalius.`. [not yet covered]
2. A family enters `vesalius.` when an in-scope record uses it (AD 1, AD 4.5). Until then it lives in its
   consumer's namespace. [RC-062]
3. A family under `vesalius.` is admitted with a definition (section 3), golden vectors (section 4), a
   reference implementation and a named consumer. A consumer that cannot be named publicly may be attested
   instead, on the conditions in `CONTRIBUTING.md`. A family with no consumer for two releases is deprecated.
   [RC-063]
4. A family in a publisher's own namespace needs no admission. The library's CI runs no third-party code: it
   reports the check points and witnesses of a family outside `vesalius.` as "not checked (third-party
   family)", never as passed. [RC-064]

## 3. The family definition

A family is a directory in `vesalius-families` holding `family.json` (the manifest below), a definition
document, `vectors/` and the reference implementation. The definition document is normative for that family
version; this section says what it MUST fix. [RC-065]

```json
{
  "id": "vesalius.mechanical.kelvin_voigt_1d.v1",
  "kind": {"strain_control": "static", "stress_control": "evolution"},
  "inputs": [{"name": "strain", "measure": "engineering_strain", "unit": "1"},
             {"name": "strain_rate", "measure": "engineering_strain_rate", "unit": "1/s", "role": "input"}],
  "outputs": [{"name": "stress", "measure": "nominal_stress", "unit": "Pa"}],
  "conversions": [{"from": "nominal_stress", "to": "cauchy_stress",
                   "vectors": "vectors/convert_cauchy.json"}],
  "parameters": [{"name": "E", "unit": "Pa", "meaning": "spring modulus"},
                 {"name": "eta", "unit": "Pa.s", "meaning": "dashpot viscosity"}],
  "state": [],
  "events": [],
  "coverage_measures": ["principal_stretches", "strain_rate"],
  "content_hash": "sha256:..."
}
```

| Item | What the definition MUST fix |
|---|---|
| Kind | per loading control: `static` (a response to the current input) or `evolution` (internal state and a time axis, optionally events). One model may be both, under different controls [RC-066] |
| Rates | every rate the family takes, marked `input` (a history the consumer supplies) or `test_condition` (the rate the parameters were measured at); one MUST NOT be fed as the other [RC-067] |
| Measures | the input measure and the output measure, both required, with conversion vectors between the measures a consumer may use; every measure and symbol named, since one name can cover two measures (AD 4.5) [RC-068] |
| Equations | the energy or response function, normatively; the treatment of incompressibility; the domain of each term, where the definition switches between forms |
| Parameters | names, units, meaning, order |
| Admissibility | the constraints a parameter set MUST satisfy, with admissibility vectors on both sides of each constraint |
| Golden vectors | section 4 |
| Reference implementation | plain numpy, written for clarity, shipped with the family, never in the core; for an evolution family, its integrator and its event location |
| Coverage measures | the measures in which a parameter set's coverage is stated (section 7) |

## 4. Golden vectors

1. Golden vectors are data files in `vectors/`, each case with its inputs, expected outputs and the precision
   they are stated to. They are frozen with the family version. [RC-069]
2. They include edge cases and admissibility cases; cases on both sides of every switch between forms of a
   function; and consistency cases wherever continuity fixes a derived constant. [RC-070]
3. For an evolution family, a case is an initial state and an input history, with the state, the outputs and
   the event times expected at stated times, and tolerances that allow for the integrator's discretisation.
   Analytic cases pin the integrator and the event location: relaxation after a step, creep under constant
   load, a threshold reached at a known time. [RC-071]

## 5. The evolution form

1. An evolution family states its state variables, their initial values and the equations that evolve them in
   continuous time, never as a discrete update, so a time step never becomes a material parameter.
   [not yet covered]
2. A rate enters as an input history. The rates a fit covered are part of its coverage (section 7).
3. An event is a condition on state and input that crosses zero in a stated direction, and what follows: the
   state changes, or the family's range of states ends. An event's time is computed, never given.
   [not yet covered]
4. An event MUST NOT name the model that takes over when a family's range ends. The consumer declares the
   chain as pairs of family and record (`declarations.md`). [RC-072]
5. A linear history-dependent family MAY also be stored in its static frequency-domain form (a complex
   modulus against frequency). The exact conversion between the two forms is an adapter with its own vectors.

## 6. Parameter sets in records

```json
"parameter_set": {
  "family": "vesalius.magnetic.langevin.v1",
  "params": {"M_s": 1.20e5, "a": 3.6e3},
  "uncertainty": {"structure": "none", "represents": "estimate"},
  "check_points": {"points": [{"input": {"H": 2.0e4}, "output": {"M": 98403.58693485391}}],
                   "tolerance": {"relative": 1e-9, "absolute": 0.0,
                                 "reason": "x = H/a gives 9.84e4, x = 3H/a gives 1.13e5"},
                   "baked_with": {"family_hash": "sha256:..."}},
  "witness": {"status": "independent", "datum": {"reference_data": "..."},
              "independent_of": "fit", "through_test_model": false,
              "tolerance": {"relative": 0.03, "basis": "fit_residual and stated-state precision"}},
  "coverage": {"modes": [{"loading_mode": "uniaxial_field", "ranges": {"H": [0.0, 1.6e6]}}],
               "invariant": {"measure": "field_magnitude", "ranges": [[0.0, 1.6e6]]}},
  "fit": {}
}
```

1. `params` holds every parameter the family names, in the family's convention and units. A missing or extra
   parameter refuses the value. [FE-002]
2. Before using `params`, a consumer evaluates its own implementation at every check point and compares
   within the stated tolerance. A mismatch refuses the value. [FE-003]
3. `uncertainty` is specified in `uncertainty.md`; `fit` in `fits_and_reference_data.md`.
4. A parameter set that fails the family's admissibility constraints is refused. [FE-004]

## 7. Check points

1. Check points are input-output pairs (for an evolution family, a standard history with its outputs and
   event times) computed by the family's reference implementation from the stored parameters, with the
   family's content hash recorded in `baked_with`. They are required for every shipped parameter set.
   [RC-073]
2. They span the parameter set's coverage and the family's branch points: a change of loading mode, a switch
   between two forms of a function. [RC-074]
3. Their tolerance is set by what they must tell apart (a convention error, a wrong branch) and by the
   precision consumers declare, and states that reason. A check point at a state where every candidate
   convention gives the same output (an undeformed state) MUST NOT be written. [RC-075]
4. A consumer that evaluates a parameter set outside the span of its check points gets `unknown`: its own
   evaluator is unverified there. [FE-005]
5. Check points show only that a consumer evaluates the parameters as the reference implementation does, at
   the states checked. They are never reported as evidence about the values (AD 4.6).
6. A reference-only parameter set ships no check points, because they would publish its parameters
   (section 9). [RC-076]

## 8. Witnesses and coverage

1. Every parameter set taken from a source has a convention witness: a response the source itself reports,
   which the parameters MUST reproduce under their family version within a stated tolerance. [FE-006]
2. A witness MUST be independent of how the parameters were obtained: for a fit, data used in the fit cannot
   witness it. The witness records which fit it is independent of. [RC-077]
3. A witness's tolerance comes from the fit's residual and from the precision to which the source states the
   state, never from the spread between specimens. [RC-078]
4. A parameter set that is the mean of per-specimen fits is witnessed against per-specimen data, or recorded
   "no independent witness".
5. A witness that depends on a model of the test (a puncture force) records that model. `vesalius check`
   reports it "not checked by `vesalius check`", and it counts towards admission only if the model of the test
   is itself a family with golden vectors. [RC-079]
6. Without an independent witness, a parameter set is not admitted to the curated library. Elsewhere it
   carries the flag "no independent witness" (`witness.status: "none"`), which is reported, never shown as a
   pass; a consumer MAY refuse it. [FE-007]
7. Coverage is a set of loading modes, each with its ranges, not a box: modes fitted separately do not make a
   joint range. It is also stated in a measure that does not depend on the mode, one of the family's
   `coverage_measures` (principal stretches or invariants for mechanics, the field's magnitude for a magnetic
   family), with the rate, so a general state can be checked. Its shape is `fits_and_reference_data.md`
   section 3's. A state outside the coverage gives `unknown` unless the consumer declares otherwise
   (`declarations.md`). [FE-008]

## 9. Reference-only parameter sets

1. A reference-only parameter set ships its locator, its witness's locator and an extraction recipe, but no
   parameter values and no check points (`provenance.md`).
2. The user fills in the parameters and the witness datum from their own copy, and `vesalius check` runs the
   witness locally. The fill-in tool records the identifier and version of the user's copy and compares them
   with the record's; a mismatch gives `unknown`. [FE-009]
3. The result is reported as "fill-in consistent with the user's copy", never as reviewed. [FE-010]

## Cases

| Case | Profile | Tests |
|---|---|---|
| FE-001 | family evaluation | an unknown family identifier or version is refused |
| FE-002 | family evaluation | a parameter set with a missing or extra parameter is refused |
| FE-003 | family evaluation | a failed check point refuses the value; a deliberately wrong-convention evaluator fails |
| FE-004 | family evaluation | an inadmissible parameter set is refused |
| FE-005 | family evaluation | evaluation outside the check points' span gives `unknown` |
| FE-006 | family evaluation | a witness is reproduced within its tolerance; a misread axis fails it |
| FE-007 | family evaluation | "no independent witness" is reported, never shown as a pass |
| FE-008 | family evaluation | a state outside coverage, in mode or in mode-independent measures, gives `unknown` |
| FE-009 | family evaluation | a fill-in from a copy of another version gives `unknown` |
| FE-010 | family evaluation | a consistent fill-in is reported as consistent with the user's copy |
| RC-060 | record checks | a family identifier not of the form `<namespace>.<path>.v<N>` is flagged |
| RC-061 | record checks | a changed definition with an unchanged version is flagged (hash mismatch) |
| RC-062 | record checks | a `vesalius.` family that no in-scope record uses is flagged |
| RC-063 | record checks | a `vesalius.` family without vectors, reference implementation or consumer is flagged |
| RC-064 | record checks | a third-party family's checks are reported "not checked (third-party family)" |
| RC-065 | record checks | a family directory without manifest, definition, vectors or implementation is flagged |
| RC-066 | record checks | a manifest without a kind per loading control is flagged |
| RC-067 | record checks | a rate not marked `input` or `test_condition` is flagged |
| RC-068 | record checks | a manifest without both measures, or without conversion vectors, is flagged |
| RC-069 | record checks | golden vectors changed under a frozen version are flagged |
| RC-070 | record checks | a switch without vectors on both sides is flagged |
| RC-071 | record checks | an evolution family without analytic history cases is flagged |
| RC-072 | record checks | an event naming a successor model is flagged |
| RC-073 | record checks | a shipped parameter set without check points, or without `baked_with`, is flagged |
| RC-074 | record checks | check points that do not span coverage and branch points are flagged |
| RC-075 | record checks | a check point where every candidate convention agrees, or a tolerance without a reason, is flagged |
| RC-076 | record checks | a reference-only parameter set shipping check points is flagged |
| RC-077 | record checks | a witness drawn from the fitted data is flagged |
| RC-078 | record checks | a witness tolerance based on between-specimen spread is flagged |
| RC-079 | record checks | a witness through a model of a test is reported "not checked by `vesalius check`" |

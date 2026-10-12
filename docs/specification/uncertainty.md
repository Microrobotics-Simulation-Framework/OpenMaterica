# Statistics and uncertainty

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Member names: `record_format.md`.
Rationale: AD 4.9, 7.3 and 9.4.

A spread is a fact about a source, and what it represents is part of that fact. Which spread a question needs,
and any distribution assumed beyond what a source gives, is the consumer's declaration (`declarations.md`).

## 1. The statistics block

A constant carries `statistics`; a table entry, a composition component or a parameter MAY carry one too.
[RC-050]

```json
"statistics": {
  "n_specimens": 12, "n_donors": 4,
  "mean": 1050.0, "sd": 12.0, "min": 1031.0, "max": 1072.0,
  "distribution": {"status": "unstated"},
  "basis": "reported_sd",
  "represents": "population",
  "dispersion": "reported",
  "relative_uncertainty": {"status": "none"},
  "expanded_uncertainty": {"status": "none"}
}
```

| Member | Contents |
|---|---|
| `n_specimens`, `n_donors` | integers, or a status (`provenance.md` section 1) |
| `mean`, `sd`, `min`, `max` | numbers in the field's unit, or a status |
| `distribution` | `normal` or `lognormal` where the source states one; otherwise `{"status": "unstated"}` |
| `basis` | where the spread comes from: `reported_sd`, `reported_se`, `reported_range`, `across_sources`, `digitising_error`, `specification_limits`, `reported_uncertainty` |
| `represents` | what the spread describes: `population` (variation between specimens or donors), `estimate` (the uncertainty of an estimate: a standard error, a fit's covariance), `measurement` (measurement error), `across_sources`, or `unstated` |
| `dispersion` | `reported`, or `not_reported` where the source gives no spread |
| `relative_uncertainty` | a number (unit `1`), or a status |
| `expanded_uncertainty` | `{"value": <number in the field's unit>, "coverage_factor": <number>}`, or a status |

1. Every member is present, holding a number, a token or a status. [RC-051]
2. `represents` is required. A population spread and the uncertainty of a mean differ by about the square
   root of the number of specimens, so a reader never substitutes one for the other. [PR-150]
3. `dispersion: not_reported` is not "exact". A reader returns it as stated and never reads the spread as
   zero. [PR-151]
4. `basis: specification_limits` marks a datasheet's minimum and maximum: a promise about a product, not a
   measured spread. A reader returns it with its basis and never as a population spread. [PR-152]
5. An expanded uncertainty is returned with its coverage factor. A reader never converts it to a standard
   deviation; that needs a distribution, which is the consumer's declaration. [PR-153]
6. Consistency a checker enforces: `reported_se` with `represents: estimate`; `n_donors` no greater than
   `n_specimens`; `min` ≤ `mean` ≤ `max` where all three are numbers; `across_sources` with a search record
   (`provenance.md` section 2). [RC-052]
7. A value known only as bounds is an interval, not a statistics block (`record_format.md` section 6).

## 2. Uncertainty structures

A parameter set declares `uncertainty`: a structure, what it represents, and the structure's own members.
There is no default structure. [RC-053]

| `structure` | Members | Notes |
|---|---|---|
| `ensemble` | `members`: one parameter vector per specimen or donor, each with its specimen label | preferred: it keeps the dependence between parameters without assuming a distribution |
| `multivariate_normal` | `space` (per parameter, `identity` or `log`), `mean`, `covariance` (`order` and `matrix`) | the form a fit's covariance arrives in; it assumes the family is right, so it excludes model-form error |
| `independent` | `marginals` (per parameter, a distribution and its parameters), `justification` | only with a stated justification for independence |
| `marginals` | `statistics` (per parameter, a statistics block), `dependence: "not_reported"` | the commonest literature form, mean and standard deviation per parameter over n specimens |
| `interval` | `bounds` (per parameter, `lower`, `upper`, `basis`) | for corner and sweep analyses |
| `none` | nothing | nominal values only |

```json
"uncertainty": {"structure": "multivariate_normal", "represents": "estimate",
                "space": {"mu": "log", "alpha": "identity"},
                "mean": {"mu": 7.6, "alpha": 4.2},
                "covariance": {"order": ["mu", "alpha"], "matrix": [[0.04, -0.01], [-0.01, 0.09]]}}
```

1. `represents` takes the tokens of section 1 and is required for every structure but `none`. [RC-054]
2. A `multivariate_normal` covariance is square in the order given, symmetric and positive semi-definite, and
   its mean lies in the declared space. [RC-055]
3. `independent` without a `justification` is refused by a checker, because fitted parameters are strongly
   correlated as a rule. [RC-056]
4. Every `ensemble` member, and every corner of an `interval` box, passes the family's admissibility
   constraints; a corner of a box can describe a material that does not exist (`model_families.md`).
   [RC-057]
5. A reader refuses a structure token it does not know. [PR-154]
6. An `ensemble` has no nominal member. A reader refuses a request for a nominal parameter vector from an
   ensemble; its mean may describe no specimen. A consumer that uses one declares it (`declarations.md`).
   [PR-155]
7. A reader returns `marginals` with `dependence: "not_reported"`, never as `independent`. [PR-156]

## 3. Sampling

These rules bind every sampler: Vesalius's reference sampler and a consumer's own (AD 7.3). A sampler that
cannot honour a declared structure refuses to sample. [not yet covered]

1. A sampler samples only the spread the consumer declared its question needs (`represents`); where the
   record's `represents` differs, it refuses. [SA-001]
2. It refuses to sample a constant whose `dispersion` is `not_reported`, unless the consumer declared a
   distribution for it, which the material input sheet records. [SA-002]
3. It refuses to sample an interval, as a form or as a structure, unless the consumer declared a
   distribution. An interval is not a uniform distribution. [SA-003]
4. It converts `specification_limits` or an expanded uncertainty into a distribution only from a consumer's
   declaration. [SA-004]
5. `multivariate_normal`: it draws in the declared space and maps the draw back. [SA-005]
6. `ensemble`: it draws members, never a synthetic vector between them. [SA-006]
7. `independent`: it draws each parameter from its own marginal. [SA-007]
8. `marginals`: it never draws parameters jointly. It MAY vary one parameter at a time, the others held at
   values the consumer declares, for sensitivity. [SA-008]
9. `none`: it refuses to sample. [SA-009]
10. It rejects every draw that violates the family's admissibility constraints and reports how many it
    rejected. [SA-010]
11. A result produced with the reference sampler is labelled as such in the material input sheet. [SA-011]

**A declared distribution.** Where a consumer declares a distribution (`declarations.md`, `assumptions`), it
has this shape:

```json
{"field": "bulk.density", "distribution": "normal", "space": "identity",
 "parameters": {"mean": 1050.0, "sd": 25.0}, "basis": "midpoint and quarter-width of a proxy range"}
```

`distribution` is `uniform` (`lower`, `upper`), `normal` (`mean`, `sd`), `lognormal` (`mu`, `sigma`, in log
space) or `triangular` (`lower`, `mode`, `upper`); `space` is `identity` or `log`; `basis` says why. A sampler
draws from it as declared, and the material input sheet records it as the consumer's assumption, never as the
record's statistics. [SA-012]

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-150 | plain read | `represents` is returned with the spread; a population spread is never offered as an estimate's |
| PR-151 | plain read | `dispersion: not_reported` is returned as stated, never as zero spread |
| PR-152 | plain read | specification limits are returned with their basis, never as a population spread |
| PR-153 | plain read | an expanded uncertainty is returned with its coverage factor, unconverted |
| PR-154 | plain read | an unknown uncertainty structure refuses the field |
| PR-155 | plain read | a nominal vector from an ensemble is refused |
| PR-156 | plain read | `marginals` is returned with dependence not reported |
| SA-001 | sampling | a spread that does not represent what the question declares is not sampled |
| SA-002 | sampling | a constant with no reported spread is not sampled without a declared distribution |
| SA-003 | sampling | an interval is not sampled without a declared distribution |
| SA-004 | sampling | specification limits and expanded uncertainties become distributions only by declaration |
| SA-005 | sampling | a multivariate normal is drawn in its declared space and mapped back |
| SA-006 | sampling | an ensemble is sampled by members only |
| SA-007 | sampling | independent marginals are drawn one by one |
| SA-008 | sampling | marginals are never drawn jointly; one-at-a-time variation is allowed |
| SA-009 | sampling | `none` is never sampled |
| SA-010 | sampling | inadmissible draws are rejected and counted |
| SA-011 | sampling | results from the reference sampler are labelled |
| SA-012 | sampling | a declared distribution is sampled as declared and recorded as the consumer's assumption |
| RC-050 | record checks | a constant without a statistics block is flagged |
| RC-051 | record checks | a statistics member that is missing or `null` instead of a status is flagged |
| RC-052 | record checks | inconsistent basis, counts, ordering, or a pooled statistic without a search record is flagged |
| RC-053 | record checks | a parameter set without an uncertainty structure is flagged |
| RC-054 | record checks | a structure without `represents` is flagged |
| RC-055 | record checks | a covariance of the wrong shape, asymmetric or not positive semi-definite is flagged |
| RC-056 | record checks | `independent` without a justification is flagged |
| RC-057 | record checks | an inadmissible ensemble member or interval corner is flagged |

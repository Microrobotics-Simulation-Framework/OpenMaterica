# Statistics and uncertainty

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Member names: `record_format.md`.
Reason codes: `read_side_contract.md` section 4. Rationale: AD 4.9, 7.3 and 9.4.

A spread is a fact about a source, and what it represents is part of that fact. Which spread a question needs,
and any distribution assumed beyond what a source gives, is the consumer's declaration (`declarations.md`).

## 1. The statistics block

Every value field carries `statistics`, except a field of form `evidence` (`record_format.md` section 5). In a
reference-only value it holds `{"status": "withheld"}` (`provenance.md` section 7). [RC-050]

```json
"statistics": {
  "central": "mean",
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
| `central` | which statistic a constant's `value` is: `mean`, `median`, `single_measurement` or `stated` (the source gives one number and no statistic); `{"status": "not_applicable"}` for other forms |
| `n_specimens`, `n_donors` | integers, or a status object (`provenance.md` section 1) |
| `mean`, `sd`, `min`, `max` | numbers in the field's unit, or a status object |
| `distribution` | `normal` or `lognormal` where the source states one; otherwise `{"status": "unstated"}`. For `lognormal`, `mean` and `sd` are of the value itself, in the field's unit, not of its logarithm |
| `basis` | where the spread comes from: `reported_sd`, `reported_se`, `reported_range`, `across_sources`, `digitising_error`, `specification_limits`, `reported_uncertainty` |
| `represents` | what the spread describes: `population` (variation between specimens or donors), `estimate` (the uncertainty of an estimate: a standard error, a fit's covariance), `measurement` (measurement error) or `across_sources`; or `{"status": "unstated"}` |
| `dispersion` | `reported`, or `not_reported` where the source gives no spread |
| `relative_uncertainty` | `{"value": <number, unit 1>, "coverage_factor": <number>}`, or a status object |
| `expanded_uncertainty` | `{"value": <number in the field's unit>, "coverage_factor": <number>}`, or a status object |

1. Every member is present, holding a number, a token, an object of its row's shape, or a status object.
   [RC-051]
2. **Tables and power laws.** A block on a table or a power law applies to every value the form gives: its
   `mean`, `min` and `max` hold `{"status": "not_applicable"}`, and its spread members (`sd`,
   `relative_uncertainty`, `expanded_uncertainty`) apply to each value. A table entry with a spread of its own
   carries a block in the table's `points` (`record_format.md` section 6), which replaces the table's for that
   entry. A composition component and a parameter MAY carry a block of their own. [PR-157]
3. `represents` is required. A population spread and the uncertainty of a mean differ by about the square
   root of the number of specimens, so a reader never substitutes one for the other. [PR-150]
4. `dispersion: not_reported` is not "exact". A reader returns it as stated and never reads the spread as
   zero. [PR-151]
5. `basis: specification_limits` marks a datasheet's minimum and maximum: a promise about a product, not a
   measured spread. A reader returns it with its basis and never as a population spread. [PR-152]
6. A relative or expanded uncertainty is returned with its coverage factor. A reader never converts it to a
   standard deviation; that needs a distribution, which is the consumer's declaration. [PR-153]
7. Consistency a checker enforces: `reported_se` with `represents: estimate`; `n_donors` no greater than
   `n_specimens`; `min <= mean <= max` where all three are numbers; `across_sources` with a search record
   (`provenance.md` section 2); a constant's `value` equal to `mean` when `central` is `mean`, and inside
   `[min, max]` where both are numbers; and `dispersion: reported` with at least one numeric spread member
   (`sd`, `min` and `max`, or an uncertainty). [RC-052] [RC-058]
8. A value known only as bounds is an interval, not a statistics block (`record_format.md` section 6). An
   interval's own statistics block holds `{"status": "not_applicable"}` in `mean`, `min` and `max`, and says
   what its bounds represent. [not yet covered]
9. A power law's uncertainty structure over `a` and `b` sits in the power law's `statistics` block, as
   `structure` with the shapes of section 2. [not yet covered]

## 2. Uncertainty structures

A parameter set declares `uncertainty`: a structure, what it represents, and the structure's own members.
There is no default structure. A power law MAY carry one over its `a` and `b`, beside its statistics block.
[RC-053]

| `structure` | Members | Notes |
|---|---|---|
| `ensemble` | `members`: a list of `{"label": <text>, "params": {<name>: <number>}}`, one per specimen or donor | preferred: it keeps the dependence between parameters without assuming a distribution |
| `multivariate_normal` | `space` (per parameter, `identity` or `log`), `mean`, `covariance` (`order` and `matrix`) | the form a fit's covariance arrives in; it assumes the family is right, so it excludes model-form error |
| `independent` | `marginals`: `{<name>: {"distribution": <token>, "parameters": {...}}}`, with the tokens and parameters of section 4; `justification` | only with a stated justification for independence |
| `marginals` | `statistics`: `{<name>: <statistics block>}`; `dependence`: `{"status": "unstated"}` | the commonest literature form, mean and standard deviation per parameter over n specimens |
| `interval` | `bounds`: `{<name>: {"lower", "upper", "basis"}}`, the shapes of `record_format.md`'s interval | for corner and sweep analyses |
| `none` | nothing | nominal values only |

```json
"uncertainty": {"structure": "multivariate_normal", "represents": "estimate",
                "space": {"mu": "log", "alpha": "identity"},
                "mean": {"mu": 7.6, "alpha": 4.2},
                "covariance": {"order": ["mu", "alpha"], "matrix": [[0.04, -0.01], [-0.01, 0.09]]}}
```

1. `represents` takes the tokens of section 1 and is required for every structure but `none`. [RC-054]
2. `log` means the natural logarithm. In a `multivariate_normal`, the mean and covariance of a parameter whose
   space is `log` are those of its natural logarithm. The covariance is square in the order given, symmetric
   and positive semi-definite. [RC-055]
3. `independent` without a `justification` is refused by a checker, because fitted parameters are strongly
   correlated as a rule. [RC-056]
4. Every `ensemble` member, and every corner of an `interval` box, passes the family's admissibility
   constraints; a corner of a box can describe a material that does not exist (`model_families.md`).
   [RC-057]
5. A consumer that evaluates parameter sets refuses a structure token it does not know, with the reason
   `unknown_token`. [FE-040]
6. An `ensemble` has no nominal member. A reader refuses a request for a nominal parameter vector from an
   ensemble; its mean may describe no specimen. A consumer that uses one declares it (`declarations.md`).
   [FE-041]
7. A consumer returns `marginals` with its dependence unstated, never as `independent`. [FE-042]

## 3. Sampling

These rules bind every sampler: Vesalius's reference sampler and a consumer's own (AD 7.3). A sampler that
cannot honour a declared structure refuses to sample. [SA-001]

1. A sampler samples only the spread whose `represents` matches the one the consumer's requirement names
   (`declarations.md`); where the record's differs, or is unstated, it refuses. [SA-001]
2. It refuses to sample a constant whose `dispersion` is `not_reported`, unless the consumer declared a
   distribution for it, which the material input sheet records. [SA-002]
3. It refuses to sample a statistics block whose `distribution` is unstated, unless the consumer declared a
   distribution for it. A mean and a standard deviation are not a normal distribution. [SA-013]
4. It refuses to sample an interval, as a form or as a structure, unless the consumer declared a
   distribution. An interval is not a uniform distribution. [SA-003]
5. It converts `specification_limits`, a relative uncertainty or an expanded uncertainty into a distribution
   only from a consumer's declaration. [SA-004]
6. `multivariate_normal`: it draws in the declared space and maps the draw back (exponentiating a `log`
   parameter). [SA-005]
7. `ensemble`: it draws members, never a synthetic vector between them. [SA-006]
8. `independent`: it draws each parameter from its own marginal. [SA-007]
9. `marginals`: it never draws parameters jointly. It MAY vary one parameter at a time, the others held at
   values the consumer declares, for sensitivity. [SA-008]
10. `none`: it refuses to sample. [SA-009]
11. It rejects every draw that violates the family's admissibility constraints and reports how many it
    rejected. [SA-010]
12. A result produced with the reference sampler is noted as such in the material input sheet's `notes`.
    [SA-011]
13. A distribution the consumer declares (its shape is in `declarations.md`) is drawn from as declared and
    recorded in the material input sheet as the consumer's assumption, never as the record's statistics.
    [SA-012]

## 4. Distribution tokens

Where a record or a declaration names a distribution, it uses these tokens and parameters, in the value's
unit unless the space is `log`.

| Token | Parameters |
|---|---|
| `normal` | `mean`, `sd` |
| `lognormal` | `mean`, `sd`, of the value itself; a sampler derives the logarithm's parameters as `sigma^2 = ln(1 + sd^2 / mean^2)` and `mu = ln(mean) - sigma^2 / 2` [SA-014] |
| `uniform` | `lower`, `upper` |
| `triangular` | `lower`, `mode`, `upper` |

A token a reader does not know refuses the field (`unknown_token`). [PR-154]

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-150 | plain read | `represents` is returned with the spread; a population spread is never offered as an estimate's |
| PR-151 | plain read | `dispersion: not_reported` is returned as stated, never as zero spread |
| PR-152 | plain read | specification limits are returned with their basis, never as a population spread |
| PR-153 | plain read | relative and expanded uncertainties are returned with their coverage factors, unconverted |
| PR-154 | plain read | an unknown distribution token refuses the field |
| FE-040 | family evaluation | an unknown uncertainty-structure token refuses the parameter set |
| FE-041 | family evaluation | a nominal vector from an ensemble is refused |
| FE-042 | family evaluation | `marginals` is returned with dependence unstated |
| PR-157 | plain read | a table's block applies to each value; an entry's own block replaces it |
| SA-001 | sampling | a spread whose `represents` differs from the requirement's, or is unstated, is not sampled |
| SA-002 | sampling | a constant with no reported spread is not sampled without a declared distribution |
| SA-003 | sampling | an interval is not sampled without a declared distribution |
| SA-004 | sampling | specification limits and relative or expanded uncertainties become distributions only by declaration |
| SA-005 | sampling | a multivariate normal is drawn in its declared space and mapped back |
| SA-006 | sampling | an ensemble is sampled by members only |
| SA-007 | sampling | independent marginals are drawn one by one |
| SA-008 | sampling | marginals are never drawn jointly; one-at-a-time variation is allowed |
| SA-009 | sampling | `none` is never sampled |
| SA-010 | sampling | inadmissible draws are rejected and counted |
| SA-011 | sampling | results from the reference sampler are labelled |
| SA-012 | sampling | a declared distribution is sampled as declared and recorded as the consumer's assumption |
| SA-013 | sampling | a mean and standard deviation with an unstated distribution are not sampled without a declaration |
| SA-014 | sampling | a lognormal given by the value's mean and sd is sampled with matching moments |
| RC-050 | record checks | a value field without a statistics block, or a reference-only one whose block is not withheld, is flagged |
| RC-051 | record checks | a statistics member that is missing, `null`, or of the wrong shape is flagged |
| RC-052 | record checks | inconsistent basis, counts, ordering, or a pooled statistic without a search record is flagged |
| RC-053 | record checks | a parameter set without an uncertainty structure is flagged |
| RC-054 | record checks | a structure without `represents` is flagged |
| RC-055 | record checks | a covariance of the wrong shape, asymmetric or not positive semi-definite is flagged |
| RC-056 | record checks | `independent` without a justification is flagged |
| RC-057 | record checks | an inadmissible ensemble member or interval corner is flagged |
| RC-058 | record checks | a `value` that disagrees with its `central` statistic, or a reported dispersion with no spread, is flagged |

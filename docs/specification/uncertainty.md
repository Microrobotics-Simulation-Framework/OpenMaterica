# Statistics and uncertainty

Schema 0.1.0, draft. Conventions, suites and case numbers: `README.md`. Member names: `record_format.md`.
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
  "population_level": {"level": "specimen", "within": {"status": "none"}},
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
| `distribution` | the distribution of the values whose `mean` and `sd` the block gives: `normal` or `lognormal` where the source states one; otherwise `{"status": "unstated"}`. For `lognormal`, `mean` and `sd` are of the value itself, in the field's unit, not of its logarithm |
| `basis` | where the block's own spread comes from: `reported_sd`, `reported_se`, `reported_range`, `across_sources`, `digitising_error`, `specification_limits`; or `{"status": "not_applicable"}` where the block has no numeric `sd`, `min` or `max` and is not an interval's block |
| `represents` | what the block's own spread describes: `population` (variation between specimens or donors), `estimate` (the uncertainty of an estimate: a standard error, a fit's covariance), `measurement` (measurement error) or `across_sources`; or `{"status": "unstated"}`; or `{"status": "not_applicable"}` where the block has no numeric `sd`, `min` or `max` and is not an interval's block |
| `population_level` | present exactly where `represents` is `population`: the level the spread is taken over, `{"level": <level>, "within": <level> or {"status": "none"}}`, or `{"status": "unstated"}`; the levels are `donor`, `lot`, `specimen` and `test` (rule 10) |
| `n_sources` | present exactly where `represents` is `across_sources`: the number of sources the spread is taken across, an integer, or a status object (rule 12) |
| `precision_conditions` | present exactly where `represents` is `measurement`: `repeatability`, `intermediate` or `reproducibility`, or `{"status": "unstated"}` (rule 13) |
| `dispersion` | `reported`, or `not_reported` where the source gives no spread |
| `relative_uncertainty` | `{"value", "coverage_factor", "coverage_probability", "distribution", "dof", "basis", "represents"}`, with `precision_conditions` where its `represents` is `measurement`; or a status object. `value` has unit 1 and is relative to the value it qualifies |
| `expanded_uncertainty` | the same shape, with `value` in the field's unit |

In a relative or expanded uncertainty:
- `coverage_factor` and `coverage_probability` are each a number or a status object, and at least one is a
  number; a standard uncertainty is one whose `coverage_factor` is 1;
- `distribution` is `normal`, `student_t` or `{"status": "unstated"}`;
- `dof` is the effective degrees of freedom the source states: a number where `distribution` is `student_t`,
  otherwise a status object;
- `basis` is `reported_uncertainty` or `digitising_error`;
- `represents` is `measurement`, `estimate` or `{"status": "unstated"}`. [PR-155] [PR-158] [RC-051]

Every uncertainty statement a source makes, standard or expanded, absolute or relative, goes into these two
members; the block's own `mean`, `sd`, `min`, `max`, `basis` and `represents` describe the values, or an
interval's bounds (rule 8). [not yet covered]

1. Every member is present, holding a number, a token, an object of its row's shape, or a status object,
   except `population_level`, `n_sources` and `precision_conditions`, each present exactly where the
   `represents` beside it is `population`, `across_sources` or `measurement`. One present elsewhere, or
   missing there, breaks the block's shape. [RC-051] [PR-158]
2. **Tables and power laws.** A block on a table or a power law applies to every value the form gives: its
   `mean`, `min` and `max` hold `{"status": "not_applicable"}`, and its spread members (`sd`,
   `relative_uncertainty`, `expanded_uncertainty`) apply to each value. A table entry with a spread of its own
   carries a block in the table's `points` (`record_format.md` section 6), which replaces the table's for that
   entry. A composition component and a parameter MAY carry a block of their own. [PR-157]
3. `represents` is required, on the block and on each uncertainty, and each describes only its own spread. A
   population spread and the uncertainty of a mean differ by about the square root of the number of specimens,
   so a reader never substitutes one for the other. [PR-150] [PR-155]
4. `dispersion: not_reported` is not "exact". A reader returns it as stated and never reads the spread as
   zero. [PR-151]
5. `basis: specification_limits` marks a datasheet's minimum and maximum: a promise about a product, not a
   measured spread. A reader returns it with its basis and never as a population spread. [PR-152]
6. A relative or expanded uncertainty is returned as stored; a reader never converts it. With a coverage
   factor, its standard uncertainty u is `value / coverage_factor` by definition (GUM); a relative one is
   relative to the value it qualifies. Anything further needs a distribution: for `normal`, u is the standard
   deviation; for `student_t`, u is the scale, and the standard deviation is `u * sqrt(dof / (dof - 2))`,
   defined only for `dof > 2`. With a coverage probability and no coverage factor, u itself needs the
   distribution. The distribution is the source's, or the consumer's declaration. [PR-153]
7. Consistency a checker enforces: `reported_se` with `represents: estimate`, and `reported_sd` never with
   it; `n_donors` no greater than
   `n_specimens`; `min <= mean <= max` where all three are numbers; `across_sources` with a search record
   (`provenance.md` section 2); a constant's `value` equal to `mean` when `central` is `mean`, and inside
   `[min, max]` where both are numbers; `basis` and `represents` other than `not_applicable` where the block
   has a numeric `sd`, `min` or `max`; and `dispersion: reported` with at least one numeric spread member
   (`sd`, `min` and `max`, or an uncertainty). These apply to the block's own spread and to each uncertainty
   separately. [RC-052] [RC-058]
8. A value known only as bounds is an interval, not a statistics block (`record_format.md` section 6). An
   interval's own statistics block holds `{"status": "not_applicable"}` in `mean`, `min` and `max`, and says
   what its bounds represent. [not yet covered]
9. A power law's uncertainty structure over `a` and `b` sits in the power law's `statistics` block, as
   `structure` with the shapes of section 2. [not yet covered]
10. `population_level` says which level a population spread is taken over: its `level` is what one value of
    the population is, and `within` the level it is taken inside, or `{"status": "none"}`. Between donors:
    `{"level": "donor", "within": {"status": "none"}}`. Within one donor: `{"level": "specimen", "within":
    "donor"}`. Specimens pooled across donors: `{"level": "specimen", "within": {"status": "none"}}`. [PR-156]
11. A checker lists, never as a finding, a relative or expanded uncertainty whose coverage factor and coverage
    probability disagree under the distribution it states. [RC-162]
12. `n_sources` counts the sources a pooled statistic is taken across (publications, studies), and
    `n_specimens` and `n_donors` never count sources: an average of five publications has `n_sources` 5, and
    its specimen and donor counts as its sources state them, or a status object. [not yet covered]
13. `precision_conditions` names the conditions a measurement's spread was obtained under (VIM 2.20, 2.22 and
    2.24): one procedure, operator, measuring system and place over a short time (`repeatability`); some of
    these varied within one laboratory (`intermediate`); different laboratories (`reproducibility`). Which one
    a question needs is the consumer's declaration. [not yet covered]

## 2. Uncertainty structures

A parameter set declares `uncertainty`: a structure, what it represents, and the structure's own members.
There is no default structure. A power law MAY carry one over its `a` and `b`, beside its statistics block.
[RC-053]

| `structure` | Members | Notes |
|---|---|---|
| `ensemble` | `levels`: an ordered list of grouping levels, outermost first, the last being the members' own unit (`donor`, `lot`, `specimen`, `test`); `counts`: `{<level>: <integer or status object>}`; `members`: a list of `{"label": <text>, "groups": {<level>: <label or status object>}, "params": {<name>: <number>}}`, with a group for every level but the last | preferred: it keeps the dependence between parameters without assuming a distribution |
| `multivariate_normal` | `parameter_spaces` (per parameter, `identity` or `log`), `mean`, `covariance` (`order` and `matrix`) | the form a fit's covariance arrives in; it assumes the family is right, so it excludes model-form error |
| `independent` | `marginals`: `{<name>: {"distribution": <token>, "distribution_parameters": {...}}}`, with the tokens and parameters of section 4; `justification` | only with a stated justification for independence |
| `marginals` | `parameter_statistics`: `{<name>: <statistics block>}`; `dependence`: `{"status": "unstated"}` | the commonest literature form, mean and standard deviation per parameter over n specimens |
| `interval` | `bounds`: `{<name>: {"lower", "upper", "basis"}}`, the shapes of `record_format.md`'s interval | for corner and sweep analyses |
| `none` | nothing | nominal values only |

```json
"uncertainty": {"structure": "multivariate_normal", "represents": "estimate",
                "parameter_spaces": {"mu": "log", "alpha": "identity"},
                "mean": {"mu": 7.6, "alpha": 4.2},
                "covariance": {"order": ["mu", "alpha"], "matrix": [[0.04, -0.01], [-0.01, 0.09]]}}
```

1. `represents` takes the tokens of section 1 and is required for every structure but `none`. [RC-054]
2. `log` means the natural logarithm. In a `multivariate_normal`, the mean and covariance of a parameter whose
   space in `parameter_spaces` is `log` are those of its natural logarithm. The covariance is square in the
   order given, symmetric and positive semi-definite. [RC-055] `parameter_spaces` gives each parameter the
   space in which the source states its normal approximation or, for a fit, the space its producer chose,
   which the fit record names (`fits_and_reference_data.md` section 2). A record never holds a source's
   covariance re-expressed in another space. [not yet covered]
3. `independent` without a `justification` is refused by a checker, because fitted parameters are strongly
   correlated as a rule. [RC-056]
4. Ensemble members and the corners of an `interval` box may fail the family's admissibility constraints:
   they are the source's fits and the source's bounds. A checker lists them, never as findings. A family's
   admissibility applies to a `params` vector (`model_families.md` section 6). [RC-057]
5. A consumer that evaluates parameter sets refuses a structure token it does not know, with the reason
   `unknown_token`. [FE-040]
6. An `ensemble` has no nominal member. A reader refuses a request for a nominal parameter vector from an
   ensemble; its mean may describe no specimen. A consumer that uses one declares it (`declarations.md`).
   [FE-041]
7. A consumer returns `marginals` with its dependence unstated, never as `independent`. [FE-042]
8. Every member of an `ensemble` stands for one unit of its last level and is equally likely. A weighted
   ensemble or a mixture is not an `ensemble`. [SA-017]
9. Group labels are local to the record. Where every label of a level is stated, that level's count equals the
   number of distinct labels. [RC-160]
10. An `ensemble`'s members are fits to distinct units of its levels. Restarts of one fitting procedure,
    posterior draws and fits kept by their loss are not members, because a sampler would draw them as a
    population. [not yet covered]
11. A `multivariate_normal` keeps `mean` beside the set's `params`: in `log` space it is the centre of the
    logarithms, which need not equal the source's vector. A checker lists, never as findings, a centre that
    fails the family's admissibility constraints, a centre on one of its fit's stated `procedure.bounds`, and,
    for `represents: estimate`, a `mean` that differs from `params` mapped into each parameter's space in
    `parameter_spaces`. [RC-059]

## 3. Sampling

These rules bind every sampler: OpenMaterica's reference sampler and a consumer's own (AD 7.3). A sampler that
cannot honour a declared structure refuses to sample. [SA-001]

1. A sampler samples only the spread whose `represents` matches the one the consumer's requirement names
   (`declarations.md`); where the record's differs, or is unstated, it refuses. [SA-001]
2. It refuses to sample a constant whose `dispersion` is `not_reported`, unless the consumer declared a
   distribution for it, which the material input sheet records. [SA-002]
3. It refuses to sample a statistics block whose `distribution` is unstated, unless the consumer declared a
   distribution for it. A mean and a standard deviation are not a normal distribution. [SA-013]
4. It refuses to sample an interval, as a form or as a structure, unless the consumer declared a
   distribution. An interval is not a uniform distribution. [SA-003]
5. It converts `specification_limits` into a distribution only from a consumer's declaration. It samples a
   relative or expanded uncertainty from the distribution the source states for it, with u as section 1 rule 6
   gives, and the material input sheet records it as the record's statistics; where the source states none,
   only from a consumer's declaration. [SA-004] [SA-018]
6. `multivariate_normal`: it draws in the record's space and maps the draw back (exponentiating a `log`
   parameter). [SA-005]
7. `ensemble`: it draws members, never a synthetic vector between them, at the level the requirement's
   `population_level` names (`declarations.md` section 1):
   - the members' own level: members uniformly;
   - an outer level L: members uniformly, where every L-group has exactly one member; otherwise it refuses;
   - balanced over L (`{"level", "balanced_over": L}`): an L-group uniformly, then one of its members
     uniformly. It refuses where any member's L-group is unstated, and the result says it drew a unit of an L
     drawn uniformly;
   - each member once: the result reports each member's weight under the requirement.

   [SA-006] [SA-016] [SA-023]
8. `independent`: it draws each parameter from its own marginal. [SA-007]
9. `marginals`: it never draws parameters jointly. It MAY vary one parameter at a time, as it may for
   `independent`: the others are held at the vector the consumer declares as a `nominal` (`declarations.md`
   section 4.1), and with none it refuses. Each point is checked for admissibility; inadmissible points are
   listed with the constraints they fail, not evaluated, and never dropped silently. No acceptance rate
   applies to a sweep. [SA-008] [SA-020]
10. `none`: it refuses to sample. [SA-009]
11. It rejects every draw that violates the family's admissibility constraints. It reports the number drawn,
    the number accepted, the acceptance rate for the run and for each block, and, for each named constraint,
    the number of draws it rejects, counting a draw against every constraint it fails. A constraint the
    consumer adds of its own is counted apart from the family's. Below the minimum joint acceptance the
    consumer declares for the run (`declarations.md` section 1, `sampling`), it refuses. It refuses a
    `multivariate_normal` with `represents: estimate` whose centre lies on one of its fit's stated bounds,
    unless the consumer declares a distribution. [SA-010] [SA-015]
12. A result produced with the reference sampler is noted as such in the material input sheet's `notes`.
    [SA-011]
13. A distribution the consumer declares (its shape is in `declarations.md`) is drawn from as declared and
    recorded in the material input sheet as the consumer's assumption, never as the record's statistics.
    [SA-012]
14. A sampler reports, for each structure, whether it sampled it, held it (not sampled, listed, at the
    record's value or a declared nominal) or refused it. Where a requirement samples a field, a `dispersion:
    not_reported` constant, an unstated distribution or an interval is sampled only from a distribution the
    consumer declared (rules 2 to 4), and refused without one; `none` is refused, and is never sampled (rule
    10). Where no requirement samples a field, it is held. A sampler never holds a field a requirement
    samples. [SA-021]
15. A corner or sweep analysis over an `interval` structure evaluates each corner's admissibility and lists
    every inadmissible corner with the constraints it fails; lists a parameter with one bound as not cornered;
    never drops, moves or clips a corner; and states a worst case from corners only where every corner is
    admissible, the family's constraints are all `bound` or `linear`, and the consumer has declared the
    quantity monotone in each parameter. [SA-019]
16. Where a requirement samples a population spread, a sampler refuses a block whose `population_level` is
    unstated or differs from the level the requirement names, unless the consumer declared a distribution
    (`declarations.md` section 4.3), which it then draws as declared and records. [SA-025]

## 4. Distribution tokens

Where a record or a declaration names a distribution, it uses these tokens and parameters, in the value's
unit unless the space is `log`.

| Token | Parameters |
|---|---|
| `normal` | `mean`, `sd` |
| `lognormal` | `mean`, `sd`, of the value itself; a sampler derives the logarithm's parameters as `sigma^2 = ln(1 + sd^2 / mean^2)` and `mu = ln(mean) - sigma^2 / 2` [SA-014] |
| `uniform` | `lower`, `upper` |
| `triangular` | `lower`, `mode`, `upper` |
| `student_t` | `location`, `scale`, `dof`: a t distribution with `dof` degrees of freedom, shifted by `location` and scaled by `scale`; its standard deviation is `scale * sqrt(dof / (dof - 2))`, defined only for `dof > 2` |
| `beta` | `lower`, `upper`, `p`, `q`: a beta distribution with shapes `p` and `q`, stretched onto `[lower, upper]` |

A record names `normal` or `lognormal` for a statistics block, and `normal` or `student_t` for a relative or
expanded uncertainty (section 1); a declaration may name any of them. A token a reader knows for no member of
that name refuses the field (`unknown_token`: `bulk` in a `distribution`); a token it knows for a member of
that name, in a member whose row does not allow it (`student_t` in a block's `distribution`, or
`reported_uncertainty` in a block's `basis`), breaks the block's shape (`form_invalid`)
(`read_side_contract.md` section 3, step 8). [PR-154] [PR-158]

## Cases

| Case | Suite | Tests |
|---|---|---|
| PR-150 | plain read | `represents` is returned with the spread; a population spread is never offered as an estimate's |
| PR-151 | plain read | `dispersion: not_reported` is returned as stated, never as zero spread |
| PR-152 | plain read | specification limits are returned with their basis, never as a population spread |
| PR-153 | plain read | relative and expanded uncertainties are returned as stored, every member unconverted |
| PR-154 | plain read | an unknown distribution token refuses the field (`unknown_token`), in the block or in an uncertainty, and so does a token known only for another member (`bulk`); a known one the member does not allow (`student_t` or `uniform` in the block) refuses it as `form_invalid` |
| PR-155 | plain read | each uncertainty's `represents`, `basis` and `precision_conditions` are returned with it; a block with a population `sd` and a measurement uncertainty returns both meanings; an unknown token in an uncertainty refuses the field |
| PR-156 | plain read | `population_level` and `n_sources` are returned with the block |
| PR-158 | plain read | a statistics member missing or of the wrong shape, an uncertainty with neither coverage factor nor probability a number, a conditional member present where its `represents` does not call for it, or missing where it does, a known token the member does not allow (`reported_uncertainty` in the block's `basis`), a negative `sd`, a coverage factor of 0, a coverage probability of 1.5, and a count that is not whole, each refuse the field (`form_invalid`); a `dof` of 7.5 does not |
| FE-040 | family evaluation | an unknown uncertainty-structure token refuses the parameter set |
| FE-041 | family evaluation | a nominal vector from an ensemble is refused |
| FE-042 | family evaluation | `marginals` is returned with dependence unstated |
| PR-157 | plain read | a table's block applies to each value; an entry's own block replaces it |
| SA-001 | sampling | a spread whose `represents` differs from the requirement's, or is unstated, is not sampled |
| SA-002 | sampling | a constant with no reported spread is not sampled without a declared distribution |
| SA-003 | sampling | an interval is not sampled without a declared distribution |
| SA-004 | sampling | specification limits become a distribution only by declaration; a relative or expanded uncertainty is sampled from the distribution its source states, and only by declaration where it states none |
| SA-005 | sampling | a multivariate normal is drawn in its record's space and mapped back |
| SA-006 | sampling | an ensemble is sampled by members only |
| SA-007 | sampling | independent marginals are drawn one by one |
| SA-008 | sampling | marginals are never drawn jointly; one-at-a-time variation is allowed |
| SA-009 | sampling | `none` is never sampled |
| SA-010 | sampling | inadmissible draws are rejected and counted |
| SA-011 | sampling | results from the reference sampler are labelled |
| SA-012 | sampling | a declared distribution is sampled as declared and recorded as the consumer's assumption |
| SA-013 | sampling | a mean and standard deviation with an unstated distribution are not sampled without a declaration |
| SA-014 | sampling | a lognormal given by the value's mean and sd is sampled with matching moments |
| SA-015 | sampling | joint and per-block acceptance and every-fail counts are reported; below the run's declared minimum, refused; an `estimate` centred on a fit bound is refused without a declaration |
| SA-016 | sampling | donors with 1, 1 and 10 specimens: balanced over donors, each donor near 1/3 and each member of the ten near 1/30; a draw at the donor level is refused; a balanced draw with an unstated donor is refused; each member once reports the weights |
| SA-017 | sampling | at the members' own level, member frequencies lie within the case's exact region |
| SA-018 | sampling | normal with k = 2: sd U/2; `student_t` with dof 8 and k = 2.306: scale U/k and sd 1.155·U/k, a runner using U/k as the sd failing; p = 0.95 with no k under a stated normal: u = U/1.95996; p only, distribution unstated: refused without a declaration |
| SA-019 | sampling | x + y ≤ 1.5 on [0, 1]²: (1, 1) listed and no worst case; a `defined` constraint with every corner admissible: no worst case; no monotonicity declared: no worst case; a one-sided parameter listed as not cornered |
| SA-020 | sampling | one at a time: refused with no nominal; inadmissible points listed, none silently dropped; no acceptance reported |
| SA-021 | sampling | each structure's outcome, sampled, held or refused, with and without a requirement that samples it; a sampler that holds a field a requirement samples fails |
| SA-022 | sampling | a correlated normal with two linear constraints: acceptance and every-fail counts within exact regions; sampling the parameters independently fails |
| SA-023 | sampling | an ensemble with one inadmissible member, evaluated each member once: exact counts |
| SA-024 | sampling | given normals and uniforms (`transform_draws`): vectors, verdicts and acceptance at relative 1e-12 for a multivariate normal in mixed spaces, a lognormal, an ensemble and a balanced draw |
| SA-025 | sampling | a population block whose level is unstated, or differs from the requirement's, is refused unless a distribution is declared |
| RC-050 | record checks | a value field without a statistics block, or a reference-only one whose block is not withheld, is flagged |
| RC-051 | record checks | a statistics member that is missing, `null`, or of the wrong shape, a conditional member where its `represents` does not call for it, and an uncertainty with neither coverage factor nor probability a number are flagged |
| RC-052 | record checks | inconsistent basis or `represents`, counts, ordering, or a pooled statistic without a search record is flagged, for the block and for each uncertainty |
| RC-053 | record checks | a parameter set without an uncertainty structure is flagged |
| RC-054 | record checks | a structure without `represents` is flagged |
| RC-055 | record checks | a covariance of the wrong shape, asymmetric or not positive semi-definite is flagged |
| RC-056 | record checks | `independent` without a justification is flagged |
| RC-057 | record checks | inadmissible ensemble members and interval corners are listed, not flagged |
| RC-058 | record checks | a `value` that disagrees with its `central` statistic, or a reported dispersion with no spread, is flagged |
| RC-059 | record checks | listed, not flagged: an inadmissible centre; a centre on a fit bound; for `estimate`, a `mean` that differs from `params` mapped into each parameter's space in `parameter_spaces` |
| RC-160 | record checks | `levels` missing or holding an unknown token, a member without a group for an outer level, and counts that differ from the distinct stated labels are flagged |
| RC-162 | record checks | listed, not flagged: a coverage factor and probability that disagree under the stated distribution (k = 3 at 95 % under a normal) |

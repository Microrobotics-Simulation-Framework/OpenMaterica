# Schema changes

Each schema version, what changed, and the conformance cases that came with it
(`DOCUMENTATION_ARCHITECTURE.md` section 7.2). Before 1.0.0 a reader reads only its own minor version
(`README.md`), so a minor version may change any shape; each change is listed here.

## 0.1.0 (draft, 2026-10-12)

The first version. It specifies records (the envelope, record types `material` and `overlay` with `interface`
reserved, the bulk, fluid, magnetic and biocompatibility sections, the eight form tokens, units, identifiers,
versions and the content hash), provenance, uncertainty, model families, fits and reference data, scene
documents, the USD binding, mixing rules, declarations and the read-side contract. Its cases are those listed
at the end of each document. Scene documents, layered paths, label crosswalks, the USD binding, the stage
check and the engine adapter are in 0.1.0; families, fits and reference data, and mixing are specified but
their suites are optional until the minor version that brings their first consumer (`README.md`). In USD a
region binds its material with the purpose `materica`; the `physics` purpose is left to engines, whose
materials an engine adapter writes from a declared engine model by an engine crosswalk, stamped with the reads
they came from, and which the stage check re-derives per shape (`usd_binding.md` sections 5, 9 and 10).
OpenMaterica ships one engine crosswalk, for `UsdPhysics`; a consumer writes the crosswalk for any other
engine it runs, drafted by a scaffold. Acoustic attenuation is registered in `/m`.

Settled before the first code (maintainer, 2026-10-13): a reader refuses as malformed exactly what RFC 8259's
grammar refuses and a listed set of further faults, follows I-JSON except that noncharacters are legal, and
reads every number as the nearest double, ties to even (`record_format.md` section 1 item 6; PR-002, PR-047);
`null` is read by where it is, and ignored inside a member the reader does not know (PR-049); records' and
other documents' schema versions match one pattern, and a missing or ill-formed `schema_version` is malformed
(`record_format.md` section 8; PR-048), as is a scene document's `scene_schema_version` (SC-002), while an
engine crosswalk with
an ill-formed or other `crosswalk_schema_version` is invalid (RC-140); the reader schema, in JSON Schema
2020-12, checks the envelope with the patterns of `id`, `version` and `content_hash`, and the body's structure
as far as the reader's version knows it, never a value field, form or section `specimen`, whose shape errors
refuse only the fields they affect, nor an unknown section or anything inside `extensions`
(`record_format.md` section 1 items 2
and 3; PR-008, PR-034, PR-045); an object with `document_type` and no `record_type` is not a record (PR-006);
a material reference resolves among the records supplied by hash, giving `malformed` where the record may be a
source that did not parse, one without a string `id` and `version`, or a candidate with an ill-formed
`content_hash`, or where two copies differ in their bytes (`read_side_contract.md` section 3, step 1; PR-328,
PR-329); the request has an exact shape and is checked on its own first, with structural, `want`,
condition-name, range and tolerance checks, and the two checks that need the form at step 11 (PR-330); a
`want` of a suite the reader does not claim gives `want_mismatch` at step 0 (PR-332); a reason appears once
per code and condition, with `condition` on a listed set of codes, and each step makes all its checks
(PR-331); with HS, a recomputed hash that differs gives `hash_mismatch` and one `pin_mismatch` (HS-010,
HS-011), and `hash_not_checked` labels only results that reach step 4; an overlay is resolved after the
target, and its base pin compared at step 6; the hash vectors widened (HS-003); case files gain claims,
variants (one file per arm, a case passing when a variant ran and none failed), exact comparison, a request
file for requests that break item 6, the `content_hash` operation and the `list_records` operation (always
`met`, listing only the good records), a `cases/` and `inputs/` layout, `labels` compared without
`hash_not_checked` unless a hash claim is stated, and reasons compared as a multiset of code and condition
(`README.md`, "Case files"); a request's unit is compared with the registered unit code point for code point,
after JSON escapes are decoded, on any operating condition or tolerance of a registered numeric condition
whose unit is a string, whatever else is wrong with the entry, and a request member the shape does not name at
that place is ignored (PR-320, PR-330); a reference with no candidate holding its hash gives `malformed`, not
`pin_mismatch`, when a supplied source is unreadable (PR-329); strings are hashed with no Unicode
normalisation (`record_format.md` section 9 item 2; HS-003); and the namespace `conformance` is reserved for
conformance fixtures, whose contents are illustrative: a record check flags one given from outside a
conformance tree, and a check of a whole library leaves conformance trees out (`record_format.md` section 7;
RC-121). Names (maintainer, 2026-10-14): the project, formerly Vesalius, is OpenMaterica; the reserved
namespace, the family namespace, the USD binding purpose and the attribute namespace are `materica`, where
drafts before that date used `vesalius`; the schema class prefix is `Materica`; and the local ids in
`materica` are `MAT-NNNN` and `INT-NNNN` (`record_format.md` section 7; RC-012, RC-013). Settled with S1's
review (maintainer, 2026-10-14): a tolerance whose condition has no operating entry because
`operating_conditions` is not an object gives `request_incomplete` with that `condition`, beside the member's
own `request_incomplete` (`read_side_contract.md` section 1; PR-330); and the vocabulary files are published
with the schemas, under `schema/0.1/vocabulary/` (`provenance.md` section 6).

Settled for the read of values (maintainer, 2026-10-14). The read: a record's units are compared with the
registered unit code point for code point, a unit held as a status object by its token, at step 9 alone, step
8 checking only that a unit is a string or a status object (`record_format.md` section 4.2; PR-010, PR-037); a
request for a field the reader does not know is `request_incomplete` (PR-330); step 8 checks the members a
read uses or returns, the statistics block among them, a composition component's included, and lists the
values it checks: counts whole and not negative, ranges and bounds in order, a ± and a standard deviation not
below zero, and coverage factors, coverage probabilities and degrees of freedom in range (PR-051, PR-158);
`family_suite_absent` is given at step 8 (PR-036); `source` is required for origin `measured_by_source` and
checked for its `key` only, and `derivation` by the shapes `provenance.md` section 5 now gives; `review` never
refuses a read, and a review that is `null`, absent or not an object, holds both `status` and `result`, or
holds a status token other than `not_checked` or an unknown `result` token reads as `{"status":
"not_checked"}` (PR-109); `null` refuses a field only in a member step 8 checks (PR-049); `provenance.md`
section 1 lists every member that may hold a status object, with its tokens, and an object holding `status`
there is a status object, one that also holds a member of the shape it stands for, or any member but `reason`
where that shape is a number, a string or a token (which amends, for those positions only, the earlier ruling
that other members beside it are ignored), being a shape error, as is a token its row does not allow, each
refusing at read only in a member step 8 checks, and a key `status` in `conditions` or `specimen` naming a
condition or a fact (PR-110); a token the reader knows for a member of that name, in a member whose row does
not allow it, is `form_invalid`, and one it knows for no member of that name `unknown_token`, labels included
(PR-053, PR-154, PR-158); a result holds only the members the reader's version defines, in every member it
returns from a record, with its members present by the step the read reached and its condition entries
compared by name (PR-336, PR-337); a derived value's derivation, its assumptions included, is returned, with
the label `mixed_conditions` (PR-102); a label the row does not name for the field refuses it, and a missing
one is not refused at read (PR-035, PR-053; RC-122); alternatives may differ in form, and none is set aside
for its form, so a grade's specification limits beside a lot's constant give `no_pick` until a pick, while a
`want` that no remaining alternative's form can give is `want_mismatch`; under `no_pick`, `alternative_values`
holds one entry per remaining alternative, with its index, its value or its form's member as stored, and its
own conditions, specimen, statistics, provenance and labels, the result holding no conditions, specimen,
statistics or provenance of its own, and no nominal is applied (PR-013, PR-338). Conditions: every comparison
is exact on the numbers as read, so "exactly at the tolerance" holds for the doubles (PR-306, PR-335); a
numeric condition may carry `plus_minus`, a bound, a standard deviation, both, or one of unstated kind, and
`set_or_measured`, and a bound narrows a met condition while any other ± alone turns it into `unknown`
(`condition_uncertain`), never `not_met` (PR-108, PR-334); a run-time watch is narrowed by a stated bound, its
ends rounded inward, and a waived `condition_uncertain` gets the tolerance's interval (BC-030); a condition
another requires is checked like a required one, an implied token included (`provenance.md` section 6.1,
"Required with"; PR-311); `test_method` gains `hysteresigraph` and is required on remanence and saturation
magnetisation, `specimen_shape` staying required beside it (PR-305, PR-311, PR-315); a test method that probes
a length below the specimen's enters only with a condition stating that length. The forms: `want: bounds`
returns the interval's basis, and bounds are in order (PR-022, PR-050); `want: components` returns the
composition's basis and sum rule, its element symbols come from a table, and a repeated component, a fraction
outside [0, 1] or an empty list is refused (PR-023, PR-051); evidence entries are withheld one by one, each
whole, every member but provenance, or not at all, an entry withheld in part being refused, a partly withheld
list giving `unknown` (`entries_withheld`) and a wholly withheld one `withheld`, while an entry's members may
hold any other status object; an empty evidence list, an entry missing a member and a registered condition
under evidence are refused (PR-038, PR-052). Acceptances: a read takes only `pick`, `overlay`,
`extrapolation`, `nominal` and `implied_condition`, any other kind being `request_incomplete`; each is checked
at step 0 whatever field it names, that field registered, and applies only to its own; an implied condition
names a token fact and one of its tokens, and supplies values of a record condition's shapes without `basis`,
`plus_minus` or `set_or_measured`, and never a status object; two nominals naming one field, and two implied
conditions that apply and disagree, whether or not the record states that condition, are `request_incomplete`,
which ends the read even where they disagree in one alternative; an implied condition fills only an unstated
or absent condition, which is then checked, its unit checked like an operating condition's; a nominal inside
or on an interval's bounds supplies the value, one outside them gives `nominal_invalid`, and `assumption`
holds no `basis` (PR-302, PR-316, PR-318, PR-320, PR-330, PR-338). Statistics: each relative or expanded
uncertainty carries its own `represents`, `basis`, `distribution` (`normal` or `student_t`, by scale),
`coverage_factor` or `coverage_probability`, and `dof`, and `reported_uncertainty` leaves the block's `basis`;
`population_level`, `n_sources` and `precision_conditions` are present exactly where `represents` calls for
them; `student_t` and `beta` are registered distribution tokens; a record check lists, without failing, a
coverage factor and probability that disagree (`uncertainty.md` section 1; PR-153, PR-155, PR-156, PR-158,
RC-051, RC-162). Provenance and vocabulary: the specimen facts `supply_form` and `lot`, with one record per
grade or product and measurements on particular lots as alternatives naming their `lot`; a record fact holding
any status object differs from a target's fact (BC-012); `use` gains `used_in_selection`, never a witness
(RC-077); a database source names its release and entry (RC-200); the search record gains `weighting` and
`inputs` (RC-201); and schema 0.1.0 has no origin for a value predicted by a model. Specified, with suites
optional until their minor version (`README.md`): `params` per uncertainty structure, check points without a
vector, and the label `mean_of_specimen_fits` (PR-333, FE-014, RC-184); the space of a `multivariate_normal`
and `covariance_space` (RC-059, RC-083); named admissibility constraints (FE-013, RC-180 to RC-183); ensemble
levels and groups, with members that are fits to distinct units (RC-160, SA-016, SA-017); ensemble members and
interval corners listed, not flagged (RC-057, SA-019); nominal vectors (BC-042, SA-020); the sampling
contract, with the `transform_draws` operation and exact regions (SA-015, SA-018, SA-021 to SA-025); the
declaration's `sampling` (BC-044, BC-046), `population_level` (BC-043) and `precision` (BC-047); and the table
evaluation suite's tolerance per precision (TE-012). Record checks gain a listing that never fails
(`README.md`, "Case files"), and case ranges RC-160 to RC-179 (`uncertainty.md`), RC-180 to RC-199
(`model_families.md`) and RC-200 to RC-219 (`provenance.md`).

Settled after two checks of this text, one for names a slip could swap and one for reads that give `met` where
doubt remains. Names (maintainer, 2026-10-14): a population level's `unit` is `level` (`uncertainty.md`
sections 1 and 3, `declarations.md` section 1; PR-156, SA-016, BC-043), a `marginals` structure's `statistics`
is `parameter_statistics` (FE-042), the read result's `values` is `alternative_values` (PR-013), and a
digitised curve's or figure's `digitiser` is `digitisation` (FD-003, RC-029); an overlay scope's `consumer` is
compared with the declaring consumer's `name`, its version not compared, and a fill-in's scope names its user
there (BC-023); a chain's records are pinned material references (BC-026); `reported_sd` never stands beside
`represents: estimate` (RC-052); and where a member the reader does not know is ignored, one that is one slip
from a member named at its place (a character inserted, deleted or substituted, two adjacent ones swapped, a
plural or singular, an underscore added or removed) is refused, `form_invalid` in a record and
`request_incomplete` in a request, the names valid at one place being kept more than one slip apart
(`record_format.md` section 10; PR-005, PR-008, PR-030, PR-108, PR-109, PR-330). The read: an overlay whose
`purpose` is none of the four is `unknown_token`, and one of another purpose than `fill_in` that replaces a
withheld value is `withheld` (PR-042); `alternatives` is a list of at least one value field and stands alone
(PR-044); a fill-in whose document, or whose base's, does not state a string identifier and version gives
`fill_in_version_mismatch` (PR-107); an interval left beside other alternatives counts as a form `want: value`
can give where a nominal applies, so the read gives `no_pick` (PR-338); a requirement holding `label`,
`represents` or `population_level` is `request_incomplete` (PR-330); an acceptance applies only at the record
or region it names, never at an interval or with no location (PR-316); step 11's `request_incomplete` ends the
read as step 10's does (PR-308); a status object whose `status` or `reason` is not a string, and a `unit` on a
token condition, are refused (PR-110, PR-037); and what a pick naming no stored alternative gives is not yet
specified, but it is never another alternative. The build: a nominal covers `want_mismatch` only on a result
whose `assumption` names it (BC-020); a fact the target names that the record lacks is a difference (BC-012);
a `fit` or `scene_override` scope without a model or configuration hash differs (BC-023); and an interval's
acceptances reach the read of its record. `read_side_contract.md` section 4 names the step or procedure that
gives each reason.

Settled for the schema files (maintainer, 2026-10-14): until a schema version is released, its files under
`schema/<MAJOR.MINOR>/` may change; once released they never change, and a later minor version gets a
directory of its own; a reader validates against the schema files shipped with it and never fetches a schema
by its `$id` (`README.md`, "Versions and stability").

Settled with S2's conformance cases (maintainer, 2026-10-15), six points the cases raised: two implied
conditions that apply and disagree are checked first at step 10, and where they do, neither value fills the
condition, no condition is checked and the read ends, its result holding no `conditions` (PR-316);
`conditions` is present only once step 10 has run to its end, so not after a step-7 `want_mismatch` over
alternatives (PR-013); a review holding a known `result` is returned as found, as `provenance.md` section 2
item 6 already said, and `read_side_contract.md` section 2 now says so too (PR-109); a unit held as a status
object, the evidence field's included, is returned as stored, its `reason` with it (PR-010); an evidence entry
is returned with its `provenance` whole (PR-038); and which of an alternative's own reasons a `no_pick` result
reports is not yet specified.

A seventh point (maintainer, 2026-10-15): a review returned as found and an evidence entry's `provenance`
returned whole hold the members `read_side_contract.md` section 2 item 5 defines, so a member the reader does
not know is left out there too (PR-337).

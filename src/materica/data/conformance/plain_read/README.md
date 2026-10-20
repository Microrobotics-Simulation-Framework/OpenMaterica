# Plain-read cases

The cases of the plain-read suite: what a read of one field of one record gives, from the request's own check
(step 0) through the type check (step 5) to the value (steps 6 to 13) of
`docs/specification/read_side_contract.md` section 3, and the `list_records` operation. `CASES.md` lists every
case file with what it tests, where the read ends and the expected answer. The conformance tree's `README.md`
explains how to read a case.

## How the arms end early

The cases that end by step 5 read no value. So each of them is built to stop at a known step, and three
devices recur in them:
- **The interface record.** A read that passes steps 1 to 4 on `interface_fixture.json`, or on
  `water_fixture_as_interface.json`, stops at step 5 with `unknown_type`: schema 0.1.0 reserves `interface`,
  and no 0.1.0 reader reads it. So `unknown_type`, and nothing before it, shows that the earlier steps passed.
- **The unsupplied version.** A request whose target is `conformance/water_fixture` 2.0.0, with only version
  1.0.0 supplied, passes step 0 and stops at step 1 with `absent`. So `absent`, and nothing at step 0, shows
  that the request was accepted: the escaped `K`, a well-formed `accept` list, a `unit` beside it.
- **Listings.** `list_records` lists the sources that are candidates and pass steps 2, 3 and 5 on their own.
  It shows what a reader accepts without a read: a record nested 64 deep, a noncharacter, an overlay with a
  complete scope.

## The reads of values

The cases that go past step 5 read a value. Each compares every member a result can hold (`status`, `reasons`,
`value`, `alternative_values`, `unit`, `conditions`, `specimen`, `statistics`, `provenance`, `labels`,
`assumption`), so a member it does not expect must be absent, and compares numbers `exact`, except a read that
gives a table's value (below). A read refused before step 12 expects `labels` empty: the field's label is
added at step 12, and `hash_not_checked` is compared only where a case claims `hash`.
- **Two base reads recur.** `water_fixture.json` under the default request (310.15 K, tolerance 1 K) reads
  `unknown`, its shear rate unstated, with the value. `water_shear_stated.json`, the same record with its
  shear rate stated as [10, 1000] 1/s, read with an operating shear rate of 100 1/s and a tolerance of 0,
  reads `met`. Most arms are one of them with one thing changed, so the reason or member that differs shows
  the rule.
- **Boundaries are exact.** Each arm at a tolerance's edge was checked with exact rationals, not decimals or
  floating point. PR-335's arms are those where floating point as written and the exact comparison disagree,
  at least one for each row of section 5, with and without a stated ±, and `decimal_310_15`, where the two
  agree and the decimals written are not the doubles read.
- **Each side fails somewhere.** Every row of section 5, with and without a stated ±, has an arm that fails on
  its lower side and one that fails on its upper side, so a reader that checks one inequality is refused.
- **They wait for their code.** `tests/spec_sync/case_steps.json` names the implementation step that first
  runs each; until it is done the tests report the file as not yet runnable, never as passed.

## Tables and extrapolations

The cases of S3 read a table: its structure and tokens (step 8), its `axis_unit` (step 9), its axis entry
(step 10), its readable range, edges and `source_range` (step 11), and its value; and they read under an
extrapolation, whose shape step 0 checks.
- **A table's value is compared at a relative tolerance of 1e-12.** The text gives the interval a read uses
  and the formula, not the reader's arithmetic, so an arm that gives a table's value (as `value`, in an
  `alternative_values` entry or under an extrapolation) compares its numbers at that tolerance; every other
  arm compares `exact`. Each expected value was computed from the interval the arm names, exactly
  (`fractions` for a linear table, `decimal` at 80 digits for a log-log one), and rounded once.
- **Two base tables recur.** `density_table.json`, `bulk.density` over temperature at x 280, 300, 320 and 340
  K (y 1000, 996, 990 and 986 kg/m3), read accepting `density_kind` `apparent`, with no tolerance on the axis;
  and `density_edge_table.json`, a table with an edge at 273 K (x 263, 273, 273, 283; y 918, 916, 1000,
  999.5). Their `source_range` variants narrow or widen the readable range, and put an edge inside it, on its
  end or outside it.
- **Points beside a knot or an edge** lie one double from it, and the two `-0` arms, at an end and at an edge
  at 0, compare their numbers at the relative tolerance, under which `-0` and `0` agree, so that they test
  only where `-0` lies; their twin `PR-018.minus_zero_operating_kept_at_edge` compares `exact`, so that the
  axis entry's `operating` keeps the sign of the request's `-0`.
- **An extrapolation** in a request is an acceptance of kind `extrapolation` located at the read's record,
  with a `method`, a `law`, a `basis` and a `reason`. Where the read applies it, the result keeps
  `outside_range`, carries the value at the readable range's nearest end, and names the extrapolation in
  `assumption` without its `basis`.

## Alternatives and picks

The cases of S4 read a field that holds `alternatives`, with no pick or with one (`read_side_contract.md`
section 3, step 7): which alternatives are set aside, which stay and which refuse the field, the outcome, and
the members it holds.
- **A reason found reading one alternative names it.** Every such reason carries `alternative`, the
  alternative's index among the stored ones; a fault of the request carries none, and neither does a reason
  step 7 gives of its own (`no_pick`, `pick_invalid`, `want_mismatch` over two or more). Each expected reason
  holds it, and the runner compares it.
- **The density alternatives.** Most arms read `conformance/density_alternatives_fixture`, whose
  `bulk.density` holds alternatives built from a constant at a stated temperature (`density_kind` `apparent`
  unless the arm says), S3's density table (x 280 to 340 K) and edge table (an edge at 273 K), and an
  interval, read at 310 K with a tolerance of 1 K, accepting `apparent`. A constant at 330 K, or of
  `density_kind` `matrix`, is set aside for its conditions; a table read outside its readable range, off every
  edge, is set aside for its range unless an extrapolation would cover it; one read at an edge, a constant
  with the unit `kg.m-3`, and an alternative step 8 refuses (a form `spline`, a power law, a table holding
  `points`, a parameter set) refuse the field. A list of one alternative is still alternatives: set aside, it
  gives no `conditions`.
- **Every outcome.** One alternative left, read as a field; `no_pick`, each remaining alternative's `unknown`
  reasons beside it; step 7's `want_mismatch`; every alternative set aside; and the refusal, which comes first
  and reports every alternative's reasons, the set-aside ones' and those that wait in an alternative that
  stays included. Two arms store the refusing alternative first and last, and two PR-308 arms the table with
  no operating value, so a reader whose answer depends on the order of reading fails one of each pair. A
  `no_pick` entry holds the labels step 12 gives its alternative, even one whose read ended at step 11, a
  table read over an operating range (`PR-013.table_over_operating_range_keeps_labels`; S4-spec's default for
  the maintainer).
- **The unit under `no_pick`** (the maintainer's ruling, 2026-10-19). Three PR-013 arms read evidence
  alternatives whose units hold `not_applicable` with different `reason`s, or a `reason` in one alone: the
  result's `unit` is the first remaining alternative's, and another's `reason` is not returned. In the third,
  an implied temperature of 300 K, which applies where the specimen states `tissue_state` `in_vivo`, sets the
  first alternative aside at 310.15 K, so the unit is the second's, not the first stored one's.
- **Picks.** Step 0 checks a pick's `index` (a number with no fractional part, not below zero; `1e0` and `-0`
  are written as such in their requests) and refuses two picks for one field. Step 7 then reads only the
  alternative a pick names, counting every stored alternative, or gives `pick_invalid`.

## Overlays and fill-ins

The cases of S4 that read through an overlay (`record_format.md` section 4.4; `read_side_contract.md` section
3, steps 5 to 7): which overlays a read resolves and applies, which faults refuse the read, what the field
read is, a pick at an overlay, and fill-ins of a reference-only value.
- **The overlaid material.** `conformance/overlaid_material_fixture` holds the met water viscosity in a fluid
  section whose specimen names a lot, and a density. A `measurement` overlay replaces the viscosity with
  0.000695 Pa·s, its own specimen (a preparation, no lot) and its own review, read with the met request of
  "The reads of values". Each overlay is named by an `overlay` acceptance for the field read; the base's
  `id`, `version` and `content_hash` are those of the record in use, except where an arm changes one.
- **Strict.** Every overlay named for the field read must apply: one not supplied, of another version, whose
  base differs, that replaces a field its base lacks, or that does not replace the field read refuses the
  read, and none is skipped. One named for another field is not resolved at all.
- **What reaches the overlaid field.** A slip in the envelope or body of the base or of the overlay refuses it
  (`form_invalid`, at step 8); a fault in the base's section, its specimen included, or in the base field
  the overlay replaces, does not, and neither does a broken field the overlay replaces beside the one read.
- **Withheld bases and fill-ins.** An overlay of any purpose but `fill_in` is refused (`withheld`) where it
  replaces a field its base holds withheld: in a single value, in one alternative, in an evidence report, with
  a marker that breaks its shape (`"reasn"`) in `value` and `statistics` or in `value` alone, in a `value`
  beside a form token no reader knows (`constnt`), or in `statistics` alone, whichever key of `replaces` holds
  it, and whatever the overlay's purpose, `fil_in` included. A `fill_in` overlay is read, labelled
  `user_extracted`, with its own review; its `evidence.document` is compared with the base's
  `source.document`, and each of its alternatives with its own index.

## The fixtures

All are illustrative, in the namespace `conformance`. See the conformance tree's `README.md`.

| Input | What it is |
|---|---|
| `water_fixture.json` | the base record: `conformance/water_fixture` 1.0.0, a material with `fluid.dynamic_viscosity` constant at 0.000692 Pa·s, temperature 310.15 K stated, shear rate unstated. Most arms are this record with one thing changed |
| `water_fixture_v2.json` | version 2.0.0 of it |
| `glycerol_fixture.json` | a second material (`bulk.density`), for listings and for sources beside the target |
| `interface_fixture.json`, `water_fixture_as_interface.json` | records of type `interface`, which a 0.1.0 reader cannot read: the step-5 stop above |
| `water_overlay_fixture.json` | an overlay on the water record, whose base pins it |
| `unknown_type_fixture.json`, `namespaced_type_fixture.json` | records of a type no 0.1.0 reader knows, and of a namespaced type |
| `scene_manifest_fixture.json`, `engine_crosswalk_fixture.json` | documents, not records: set aside at step 1 and never resolved |
| `water_shear_stated.json` | the water record with its shear rate stated: the base of the reads that are `met` |
| `magnet_fixture.json` | `conformance/magnet_fixture`: `magnetic.remanence` 1.2 T at 293.15 K on a cylinder, by `hysteresigraph`, and `magnetic.volume_susceptibility` 0.0005 with the linear label |
| `grade_density_*` | `conformance/polymer_grade_fixture`: `bulk.density` as an interval, specification limits [1150, 1250] kg/m3 with `lot` not applicable, and the same beside a lot's constant (`grade_density_limits_and_lot.json`) |
| `composition_*` | `conformance/composition_fixture`: `bulk.elemental_composition`, a partial mass-fraction composition, and its faults |
| `evidence_fixture.json`, `evidence_*` | `conformance/evidence_fixture`: `biocompatibility.evidence`, two reports, and its faults |
| `mixture_*` | `conformance/mixture_fixture`: a derived viscosity whose derivation names the water and glycerol records |
| `form_*` | `conformance/form_fixture`: a form on a field whose row does not allow it (`form_table_on_*`: a well-formed table, on evidence without its axis condition, or holding it, which evidence's `conditions` may not hold whatever the form, `record_format.md` section 4.3 item 3, the maintainer's ruling of 2026-10-19; `form_broken_table_on_*`: a table without `edges`) |
| `density_table*.json` | `conformance/density_table_fixture`: `bulk.density` as a linear table over temperature, x [280, 300, 320, 340] K, and its variants: a `source_range` (`density_table_range_*`), a fault of structure, member or token, `points`, a statistics block, 10,000 knots, and alternatives beside a constant, an interval or a second table |
| `density_edge*.json` | `conformance/density_edge_fixture`: the same over x [263, 273, 273, 283] K with an edge at 273 K, and its `source_range` and structural variants (the edge below, inside, on an end of and above the readable range), and alternatives beside a constant or an interval |
| `viscosity_table*.json` | `conformance/viscosity_table_fixture`: `fluid.dynamic_viscosity` as a linear table over temperature, shear rate stated, the Newtonian label; once stated without origin |
| `shear_thinning*.json` | `conformance/shear_thinning_fixture`: the viscosity as a log-log table over shear rate, x [1, 10, 100, 1000] 1/s, and its variants |
| `susceptibility*.json` | `conformance/susceptibility_table_fixture`: `magnetic.volume_susceptibility` as a table over flux density, x [0, 1, 2] T, or with an edge at 0 T, and over temperature with the linear label |
| `water_with_broken_density_table.json` | the met water record beside a density table without `edges` |
| `density_alternatives_*` | `conformance/density_alternatives_fixture`: `bulk.density` as `alternatives` of constants, tables and an interval, for step 7 and picks, or one alternative alone (`_one_outside`); `_form_spline_`, `_power_law_`, `_table_points_` and `_parameter_set_and_met.json` hold an alternative step 8 refuses beside a met constant; `density_alternatives_empty.json`, `_entry_not_object`, `_entry_holds_alternatives` and `_beside_value` break the list itself |
| `overlaid_material*.json` | `conformance/overlaid_material_fixture`: a material whose fluid section, its specimen naming a lot, holds the met water viscosity, and whose bulk section holds a density. Its variants break its envelope (`crad`), body (`fluids`) or section, or the viscosity the overlays replace, or hold a withheld value: a marker that breaks its shape (in `value` and `statistics`, or in `value` alone), a withheld `value` under the form token `constnt`, `statistics` alone, the density. `overlaid_material_alternatives.json` (`conformance/overlaid_alternatives_fixture`) holds the viscosity as two alternatives |
| `viscosity_overlay*.json`, `viscosity_alternatives_overlay.json`, `second_viscosity_overlay.json`, `density_overlay*.json`, `density_table_overlay.json`, `viscosity_and_density_overlay*.json` | `measurement` overlays on those materials, origin `measured_by_contributor`, each replaced field with its own specimen (a preparation that names no material) and review; `viscosity_alternatives_overlay.json` replaces the viscosity of `overlaid_material_alternatives.json` with two alternatives, and `density_table_overlay.json` the density table of `density_table.json` with a table 1 kg/m3 higher; their variants break the overlay's envelope, body, purpose (`fil_in`), base or a replaced field, replace a field the base lacks (a whole section, or `bulk.elemental_composition` in the section it holds), are edited after pinning, or are written against schema 0.2.0 |
| `fit_overlay*.json` | `conformance/fit_overlay_fixture`: a `fit` overlay, its scope naming a model and configuration, its viscosity of origin `fitted` with a `fit` record |
| `reference_only*.json` | `conformance/reference_only_fixture`: a reference-only viscosity, its value and statistics withheld, origin `measured_by_source`, a recipe and the curator's review; or two alternatives, one of them withheld; the variants leave out the source's `document` or give its version as a number |
| `fill_in*.json` | `conformance/fill_in_fixture`: `fill_in` overlays of the reference-only viscosity, in the user's namespace and licence (`LicenseRef-user-extracted`), with the user's review and the `evidence` of the user's copy; the variants name another document version or identifier, none, or an identifier or a version that is a number, or hold alternatives |
| `measured_evidence_overlay.json` | a `measurement` overlay replacing the biocompatibility evidence whose base holds one report withheld |
| `viscosity_alternatives_table_and_constant.json` | `conformance/viscosity_alternatives_fixture`: `fluid.dynamic_viscosity` as two alternatives, S3's viscosity table and the met constant, both with the Newtonian label, read over an operating range |

The inputs come in families, named by what they break:

| Family | What it holds |
|---|---|
| `water_fault_*` | the water record broken as JSON: a byte-order mark, UTF-16 and UTF-32 text, overlong, truncated and encoded-surrogate UTF-8, a comment, a raw control character, a trailing comma, trailing content, truncated text, `NaN`, `Infinity`, `-Infinity`, unpaired surrogate escapes, a repeated member (also after unescaping), numbers that overflow, nesting 65 and 100000 deep |
| `water_schema_*` | `schema_version` absent, `null`, a number, an array, off the pattern (leading zeros, `0.1`, a trailing newline or space, Arabic-Indic digits, a pre-release, 100-digit parts), other versions (0.0.1, 0.1.7, 0.10.0, 1.0.0, 1.1.0, 2.0.0), and 0.2.0 with envelope faults (refused at step 2, before step 3 sees them) |
| `water_missing_*`, `water_*_wrong_type`, `water_null_*` | an envelope member missing or of the wrong JSON type, and `null` in each envelope member and each place of the body's structure |
| `water_content_hash_*`, `water_id_*`, `water_local_id_*`, `water_version_*`, `water_licence_*` | those envelope members off their patterns or shapes |
| other `water_*` | body structure (`sections` missing, `sections`, `fields` or `extensions` an array, a section a number or without `fields`), `document_type` without or beside `record_type`, `record_type` capitalised, `null` in an unknown member, an escaped U+0000, noncharacters, nesting exactly 64 |
| `water_fixture_*` | copies of the water record: edited after pinning (stale or recomputed hash), with another card, reformatted, as CBOR, TOML or YAML, under schema 0.2.0, and the 2.0.0 record with an uppercase hash |
| `interface_*` | the interface record, copied, edited, and with envelope faults |
| `overlay_*` | the overlay body's members missing, of the wrong type or `null`: `base`, `scope` with its `model`, `replaces`, `purpose`. Twelve are `fit` overlays, so that their scope may name a model |
| `unknown_type_*`, `namespaced_type_*` | the unknown-type records, also with envelope faults (refused at step 3 before the type is checked) |
| `source_*`, `empty_file.json`, `record_binary_bytes.json` | sources that are not records: a number, a string, an array, an object with only an `id`, an empty file, bytes that are not text |
| `request_*` | requests that are not valid JSON, used through `inputs.request` (PR-330) |
| `water_*`, read to the value | the water record with one change a read of the value checks: units (`water_field_unit_*`, `water_condition_unit_*`), tokens (`water_token_*`, `water_form_*`), statistics (`water_statistics_*`), status objects (`water_status_*`, `water_temperature_*`), reviews (`water_review_*`), a ± (`water_plus_minus_*`), conditions (`water_shear_*`, `water_tube_*`, `water_gap_*`, `water_condition_*`), specimen facts (`water_fact_*`, and for implied conditions `water_in_vivo*`, `water_ex_vivo*`), alternatives (`water_alternatives_*`, `water_two_constant_alternatives.json`), near-typos (`water_near_typo_*`), `null` in a value field's member (`water_plus_minus_null.json` and the like), unknown members (`water_unknown_*`) |
| `glycerol_*`, `magnet_test_method_absent.json` | the density and the remanence with one such change |

## What the cases cannot show

- **A tolerance on a token condition, on its own** (PR-330). Such a tolerance always also lacks an operating
  condition, which gives the same reason with the same condition. So a reader that ignored the rule would
  pass. The rule is kept because it states why such an entry is refused. The arms with it are right but cannot
  fail on that rule alone.
- **PR-006's set-aside arms.** A document set aside at step 1 and a source that is simply not the target give
  the same answer. PR-328 holds the arms where setting aside changes the answer.
- **A power-law alternative outside its range.** Step 7 sets one aside as it does a table, but no 0.1.0 field
  takes a power law, and step 8 refuses one (`form_not_registered`, PR-036) before step 11. That refusal of
  the field is tested (`PR-044.refused_form_not_registered`); only the set-aside rule for a power law's range
  is unreachable.
- **A power law** (PR-020, PR-021, TE-009): no 0.1.0 field takes one; its arms come with the acoustic section.
- **Acceptances located at a region.** Regions belong to the scene suite. An acceptance located at an
  `interval` is checked and not applied (`PR-316.implied_at_interval`, `PR-338.nominal_at_interval`,
  `PR-307.at_interval`, `PR-304.pick_at_interval_not_applied`), and so is one located at the read's record and
  an interval, a pick included (`PR-316.implied_at_record_and_interval`,
  `PR-338.nominal_at_record_and_interval`, `PR-307.at_record_and_interval`,
  `PR-304.pick_at_record_and_interval_not_applied`). A pick naming a region beside the read's record is a
  plain read's, and is not applied, since a plain read has no region
  (`PR-304.pick_at_record_and_region_not_applied`).
- **Two faults in one overlay, where its base differs.** Step 6 makes all its checks, and every reason is
  reported (`read_side_contract.md` section 2 item 2), so two faults are reported where the answer does not
  depend on which base is meant: one overlay with an unknown purpose that does not replace the read field, or
  that replaces a field its base, the record in use, holds withheld
  (`PR-042.purpose_fil_in_not_replacing_read_field`, `PR-042.purpose_fil_in_over_withheld`), and two overlays,
  one not supplied and one whose base differs (`PR-310.two_overlays_two_faults`). Where an overlay's base
  differs from the record in use, the text does not say which base "lacks" a key of `replaces` or holds a
  withheld value, so no arm puts a base mismatch beside another fault of the same overlay. Nor does it say
  whether an overlay refused for its base still conflicts with another.
- **An `overlay` acceptance that names a location** (`record`, say): an overlay names none, and the text does
  not say whether one that does breaks its shape or is ignored.
- **An overlay in a scene's roles** (a region's or the background's material, a layered path's interval): the
  scene suite's cases.
- **What the build does with overlays and alternatives:** selecting overlays by their base's `id`, reporting
  one that applies to no read, comparing a scope (`overlay_scope_mismatch`), and whether a waiver names a
  reason's `alternative`, are the build checks'.

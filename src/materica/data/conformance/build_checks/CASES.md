# Build-check cases: what each case file tests

One row per file in `cases/`, grouped by case id; each heading quotes the case's row in
`docs/specification/declarations.md`, which holds where the two differ. **Decided by** names the text of
`declarations.md` (or `record_format.md`) that decides the answer. **Expected** is read from the case file: the
refusals the build gives the declaration checked on its own, each the case id of the rule broken and the JSON
pointer into the declaration (`""` is the empty pointer, the declaration itself), then the report's members that
must be absent (a refused declaration gives no results, no watches and nothing unused), the rules whose refusals
the case compares where it names any, and the claims the case states. See `README.md` beside this file for the
fixtures and what the cases cannot show.

## BC-004

`declarations.md`: a tolerance or accept list without a reason is refused

| Variant | Arm | Decided by | Expected |
|---|---|---|---|
| `accept_list_without_reason` | the `test_method` accept list of the model's one requirement carries no `reason` | `declarations.md` 1 item 3; the refusal paragraph (pointer, precedence) | refuses `BC-004` at `"/models/0/requirements/0/conditions/test_method"`; `results`, `watches` and `unused` absent |
| `tolerance_without_reason` | the `temperature` tolerance of the model's one requirement carries no `reason` | `declarations.md` 1 item 3; the refusal paragraph (pointer, precedence) | refuses `BC-004` at `"/models/0/requirements/0/conditions/temperature"`; `results`, `watches` and `unused` absent |
| `two_models_both_listed` | two models, `drag` with a tolerance and `lift` with an accept list each without `reason`: both refused, in one report | `declarations.md` 1 item 3; the refusal paragraph (every refusal found) | refuses `BC-004` at `"/models/0/requirements/0/conditions/temperature"`, `BC-004` at `"/models/1/requirements/0/conditions/test_method"`; `results`, `watches` and `unused` absent |

## BC-005

`declarations.md`: an acceptance without a reason, or a basis where its kind needs one, is refused

| Variant | Arm | Decided by | Expected |
|---|---|---|---|
| `accepted_difference_without_reason` | an `accepted_difference` (the fluid section's species `not_applicable`), beside the valid waiver, without `reason` | `declarations.md` 1 item 4; the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `empty_reason` | a `waiver` whose `reason` is the empty string: BC-005 at the `reason` alone, not BC-048 as well | `declarations.md` 1 item 4 and its row (a string of at least one character); the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/0/reason"`; `results`, `watches` and `unused` absent |
| `extrapolation_without_basis` | an `extrapolation` (method `constant`), beside the valid waiver, with its `reason` and without `basis` | `declarations.md` 1 item 4; the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `implied_condition_without_reason` | an `implied_condition` (`tissue_state` `in_vivo` implying 310.15 K), beside the valid waiver, without `reason` | `declarations.md` 1 item 4; the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `nominal_without_basis` | a `nominal` (a value at the water record), beside the valid waiver, with its `reason` and without `basis` | `declarations.md` 1 item 4; the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `overlay_scope_without_reason` | an `overlay_scope` accepting `consumer`, beside the valid waiver, without `reason` | `declarations.md` 1 item 4; the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `overlay_without_reason` | an `overlay` naming an overlay by identifier, version and hash, beside the valid waiver, without `reason` | `declarations.md` 1 item 4; the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `pick_without_reason` | a `pick` (index 0 at the water record), beside the valid waiver, without `reason` | `declarations.md` 1 item 4; the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `waiver_without_reason` | a `waiver` (record, field, condition, code) without `reason` | `declarations.md` 1 item 4; the refusal paragraph (pointer, precedence) | refuses `BC-005` at `"/models/0/acceptances/0"`; `results`, `watches` and `unused` absent |

## BC-037

`declarations.md`: an acceptance with no location where its kind needs one is refused

| Variant | Arm | Decided by | Expected |
|---|---|---|---|
| `accepted_difference_without_location_accepted` | an `accepted_difference` naming no location, which its row allows, beside a `waiver` naming none: the waiver alone is refused | `declarations.md` 4.1 (the `accepted_difference` row's location; the rule after the table); the refusal paragraph (every refusal found) | refuses `BC-037` at `"/models/0/acceptances/0"`; `results`, `watches` and `unused` absent |
| `extrapolation_without_location` | an `extrapolation`, beside the valid waiver, naming no location | `declarations.md` 4.1 (the location column, and the rule after the table); the refusal paragraph (pointer, precedence) | refuses `BC-037` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `implied_condition_without_location` | an `implied_condition`, beside the valid waiver, naming no location | `declarations.md` 4.1 (the location column, and the rule after the table); the refusal paragraph (pointer, precedence) | refuses `BC-037` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `nominal_without_location` | a `nominal`, beside the valid waiver, naming no location | `declarations.md` 4.1 (the location column, and the rule after the table); the refusal paragraph (pointer, precedence) | refuses `BC-037` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `pick_without_location` | a `pick`, beside the valid waiver, naming no location | `declarations.md` 4.1 (the location column, and the rule after the table); the refusal paragraph (pointer, precedence) | refuses `BC-037` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent |
| `waiver_without_location` | a `waiver` naming no `record`, `region` or `interval` | `declarations.md` 4.1 (the location column, and the rule after the table); the refusal paragraph (pointer, precedence) | refuses `BC-037` at `"/models/0/acceptances/0"`; `results`, `watches` and `unused` absent |

## BC-048

`declarations.md`: a declaration that departs from its shape is refused at build, before any read, each refusal its rule's case and a JSON pointer by the precedence and pointer rules: not JSON or not an object; a member missing, of another JSON type, empty where one entry or more is required, not named at its place or one slip from a named one, a `basis` inside an implied condition's `implies` aside; a token or registered name its member does not take; a name given twice; a requirement or `trainable` entry for a field not in `reads`, or a `trainable` entry at a location the model is not checked over; a value that breaks a constraint its row's Holds column states (a `range` whose `lo` is above its `hi`, a unit other than the registered one, a number below zero, an `index` with a fractional part, a combination of fewer than two fields or of fields of one section, two of a member's mutually exclusive alternatives, an empty `law`, a distribution's parameters other than its token's, a repeated `accepts` token); nothing is read for a refused declaration

| Variant | Arm | Decided by | Expected |
|---|---|---|---|
| `duplicate_member_not_json` | the model entry names `reads` twice, so the text is not valid JSON: one refusal at the empty pointer, not at the member | `record_format.md` 1 item 6; `declarations.md` 1, the departures and the pointer rule | refuses `BC-048` at `""`; `results`, `watches` and `unused` absent |
| `empty_checked_over_records` | `checked_over` holds `records: []`, where the table asks for at least one | `declarations.md` 1, the `checked_over` row and the departures (empty where one entry or more is asked) | refuses `BC-048` at `"/models/0/checked_over/records"`; `results`, `watches` and `unused` absent |
| `extrapolation_method_linear` | an extrapolation, beside the valid waiver, whose `method` is `linear` | `declarations.md` 1, the acceptance row (an extrapolation's `method`, `constant` or `consumer_law`) and the departures | refuses `BC-048` at `"/models/0/acceptances/1/method"`; `results`, `watches` and `unused` absent |
| `field_twice_in_reads` | `reads` lists `fluid.dynamic_viscosity` twice: refused at the later entry | `declarations.md` 1, the `reads` row, the departures (a name given twice) and the pointer rule (the field in `reads` itself) | refuses `BC-048` at `"/models/0/reads/1"`; `results`, `watches` and `unused` absent |
| `json_array` | the declaration is a JSON array holding the valid declaration: one refusal at the empty pointer | `declarations.md` 1, the departures and the pointer rule | refuses `BC-048` at `""`; `results`, `watches` and `unused` absent |
| `member_of_another_type` | `model_configuration_hash` holds a number, not a string | `declarations.md` 1, the shape table and the pointer rule (a member of another JSON type) | refuses `BC-048` at `"/models/0/model_configuration_hash"`; `results`, `watches` and `unused` absent |
| `operating_condition_not_registered` | `operating_conditions` names `pressure`, a condition schema 0.1.0 does not register | `declarations.md` 1, the `operating_conditions` row, the shape paragraph (a registered name) and the departures | refuses `BC-048` at `"/operating_conditions/pressure"`; `results`, `watches` and `unused` absent |
| `record_listed_twice` | `checked_over.records` lists the water record twice: refused at the later entry | `declarations.md` 1, the `checked_over` row, the departures (a name given twice) and the pointer rule (the later entry) | refuses `BC-048` at `"/models/0/checked_over/records/1"`; `results`, `watches` and `unused` absent |
| `requirement_for_field_not_read` | a second requirement, for `bulk.density`, which the model does not list in `reads`: refused at its `field` | `declarations.md` 1, the requirement row (a field in `reads`), the departures and the pointer rule (the member at fault) | refuses `BC-048` at `"/models/0/requirements/1/field"`; `results`, `watches` and `unused` absent |
| `review_in_another_case` | the requirement holds `review: "Reviewed"`, the token in another case | `declarations.md` 1, the `review` row, item 11 and the departures (a token in another case) | refuses `BC-048` at `"/models/0/requirements/0/review"`; `results`, `watches` and `unused` absent |
| `review_not_a_token` | the requirement holds `review: "yes"` | `declarations.md` 1, the `review` row, item 11 and the departures (a token not its member's) | refuses `BC-048` at `"/models/0/requirements/0/review"`; `results`, `watches` and `unused` absent |
| `slip_acceptance_for_acceptances` | the model entry names its acceptances `acceptance`, one slip from `acceptances`: one refusal, at the slip, `acceptances` being optional | `declarations.md` 1, the departures (one slip from a named member) and the `acceptances` row; `record_format.md` 10 (one slip) | refuses `BC-048` at `"/models/0/acceptance"`; `results`, `watches` and `unused` absent |
| `target_and_reads_missing` | the model entry has neither `target` nor `reads` (and no `requirements`, which would name a field it does not read): one refusal, at the model entry | `declarations.md` 1, the shape table, the pointer rule (one refusal per case and pointer) | refuses `BC-048` at `"/models/0"`; `results`, `watches` and `unused` absent |
| `target_fact_holding_basis` | the target's `species` holds `basis`, a member the table does not name there | `declarations.md` 1, the `target` row (without `basis`), the departures (a member not named at its place) and the pointer rule | refuses `BC-048` at `"/models/0/target/species/basis"`; `results`, `watches` and `unused` absent |
| `target_missing` | the model entry has no `target`: one refusal, at the model entry | `declarations.md` 1, the shape table (`target` required) and the pointer rule | refuses `BC-048` at `"/models/0"`; `results`, `watches` and `unused` absent |
| `trainable_field_not_read` | a `trainable` entry for `bulk.density` at the water record, a field the model does not read: refused at its `field` | `declarations.md` 1, the trainable entry's row, the departures and the pointer rule (the member at fault) | refuses `BC-048` at `"/models/0/trainable/0/field"`; `results`, `watches` and `unused` absent |
| `trainable_record_not_checked_over` | a `trainable` entry for the viscosity at the glycerol record, which the store holds and `checked_over` does not list: refused at its `record` | `declarations.md` 1, the trainable entry's row, the departures and the pointer rule (the member at fault) | refuses `BC-048` at `"/models/0/trainable/0/record"`; `results`, `watches` and `unused` absent |
| `two_models_of_one_name` | two model entries named `drag` (versions 1.0.0 and 2.0.0): refused at the later entry, whole | `declarations.md` 1, the `model` row, the departures (a name given twice) and the pointer rule (the later entry) | refuses `BC-048` at `"/models/1"`; `results`, `watches` and `unused` absent |
| `two_requirements_for_one_field` | two requirements for `fluid.dynamic_viscosity` (tolerances of 1 K and 2 K): refused at the later requirement, whole | `declarations.md` 1, the `requirements` row (at most one per field), the departures and the pointer rule (the later entry) | refuses `BC-048` at `"/models/0/requirements/1"`; `results`, `watches` and `unused` absent |
| `waiver_code_not_a_reason` | a waiver whose `code` is `condition_unstate`, no reason of `read_side_contract.md` 4 (and which names no `condition`) | `declarations.md` 1, the acceptance row (a waiver's `code`, a reason of `read_side_contract.md` 4) and the departures | refuses `BC-048` at `"/models/0/acceptances/0/code"`; `results`, `watches` and `unused` absent |
| `want_slip_values` | the requirement wants `values`, one slip from the token `value` | `declarations.md` 1, the requirement row (a token of `read_side_contract.md` 6) and the departures (a slip of a token) | refuses `BC-048` at `"/models/0/requirements/0/want"`; `results`, `watches` and `unused` absent |

## BC-050

`declarations.md`: a waiver naming a `label` is refused at build unless the requirement for its field names that label and holds `review: "reviewed"`; it covers only a result whose stored label is that label and trusted, stated by the source or on a value whose review is completed

| Variant | Arm | Decided by | Expected |
|---|---|---|---|
| `requirement_names_another_label` | a waiver naming `materica.magnetic.linear.v1`, whose requirement names `materica.fluid.newtonian.v1` and holds `review: "reviewed"`: refused at the waiver's `label` (BC-050's refusals alone compared) | `declarations.md` 4.1 item 4; the refusal paragraph (the waiver's `label`; the precedence) | refuses `BC-050` at `"/models/0/acceptances/0/label"`; `results`, `watches` and `unused` absent; rules `BC-050` |
| `requirement_without_review` | a waiver naming `materica.fluid.newtonian.v1`, whose requirement names that label and holds no `review`: refused at the waiver's `label` | `declarations.md` 4.1 item 4; the refusal paragraph (the waiver's `label`) | refuses `BC-050` at `"/models/0/acceptances/0/label"`; `results`, `watches` and `unused` absent |

## BC-051

`declarations.md`: a build that does not claim the scene suite, USD read or the sampling suite refuses at build what needs it: a model checked over a domain or a path, `region_conditions`, an acceptance or `trainable` entry at a region or an interval; a model with `engine`; `sampling`, a requirement's `represents` or `population_level`, a `distribution` acceptance; where items 7 and 8 or the `population_level` rule refuse the same declaration, their refusal alone

| Variant | Arm | Decided by | Expected |
|---|---|---|---|
| `checked_over_domain` | a model checked over the domain `lumen`, by a build that does not claim the scene suite | `declarations.md` 1 item 12; the refusal paragraph (pointer) | refuses `BC-051` at `"/models/0/checked_over/domain"`; `results`, `watches` and `unused` absent; claims `scene_documents: false` |
| `checked_over_path` | a model checked over the path `vessel`, by a build that does not claim the scene suite | `declarations.md` 1 item 12; the refusal paragraph (pointer) | refuses `BC-051` at `"/models/0/checked_over/path"`; `results`, `watches` and `unused` absent; claims `scene_documents: false` |
| `distribution_acceptance` | a valid `distribution` acceptance (`normal` at the water record), beside the waiver, by a build that does not claim the sampling suite | `declarations.md` 1 item 12; the refusal paragraph (pointer) | refuses `BC-051` at `"/models/0/acceptances/1"`; `results`, `watches` and `unused` absent; claims `sampling: false` |
| `engine_over_records` | a model with `engine` checked over records, its crosswalk not passed, by a build that does not claim USD read: item 7 refuses it, and item 12 gives no refusal (BC-051's refusals alone compared) | `declarations.md` 1 items 7 and 12 (items 7 and 8 come first); the refusal paragraph | refuses nothing; `results`, `watches` and `unused` absent; rules `BC-051`; claims `usd_read: false` |
| `population_without_level_beside_sampling` | a requirement holding `represents: "population"` without `population_level`, beside a valid `sampling`, by a build that does not claim the sampling suite: BC-043 at the requirement, and `sampling`'s BC-051 | `declarations.md` 1, the members table (`population_level`) and item 12 (that rule comes first); the refusal paragraph | refuses `BC-043` at `"/models/0/requirements/0"`, `BC-051` at `"/sampling"`; `results`, `watches` and `unused` absent; claims `sampling: false` |
| `region_conditions` | a model over records holding `region_conditions` (300 K in `lumen`), by a build that does not claim the scene suite | `declarations.md` 1 item 12; the refusal paragraph (pointer) | refuses `BC-051` at `"/models/0/region_conditions"`; `results`, `watches` and `unused` absent; claims `scene_documents: false` |
| `represents_beside_sampling` | a requirement holding `represents: "measurement"` beside a valid `sampling`, by a build that does not claim the sampling suite: two refusals | `declarations.md` 1 item 12; the refusal paragraph (every refusal found) | refuses `BC-051` at `"/models/0/requirements/0/represents"`, `BC-051` at `"/sampling"`; `results`, `watches` and `unused` absent; claims `sampling: false` |
| `represents_without_sampling` | a requirement holding `represents: "measurement"` and no `sampling`, by a build that does not claim the sampling suite: BC-044 alone, at the declaration | `declarations.md` 1 items 8 and 12 (item 8 comes first); the refusal paragraph (the object that should hold the member) | refuses `BC-044` at `""`; `results`, `watches` and `unused` absent; claims `sampling: false` |
| `sampling_block` | a valid `sampling` block, no requirement sampling, by a build that does not claim the sampling suite | `declarations.md` 1 item 12; the refusal paragraph (pointer) | refuses `BC-051` at `"/sampling"`; `results`, `watches` and `unused` absent; claims `sampling: false` |

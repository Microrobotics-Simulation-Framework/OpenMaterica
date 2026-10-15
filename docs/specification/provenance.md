# Provenance, conditions and specimen facts

Schema 0.1.0, draft. Conventions, suites and case numbers: `README.md`. Member names: `record_format.md`.
Reason codes: `read_side_contract.md` section 4. Rationale: AD 4.3, 4.7, 4.8, 4.11, 6.1 and 6.2.

## 1. Status objects

1. A required member with no ordinary value holds a status object: an object whose only members are `status`
   and, optionally, `reason` (a text). [RC-020] An optional member with nothing to say is omitted. `null` and
   an empty value never stand for a status (README; `record_format.md` RC-015).
2. The five tokens are `unstated` (the source does not state it), `not_checked` (a check has not run), `none`
   (there is nothing: no assistance, no witness, no upper bound), `not_applicable` (the member does not apply
   here) and `withheld` (a reference-only value, section 7).
3. In `conditions`, `not_applicable` is used only for the form's own axis (`read_side_contract.md` section 5).
   A specimen fact may hold it where the fact cannot apply (the tissue state of a magnet). [RC-043]
4. A reader returns a status as a status. It never reads one as a value, a zero or a pass. [PR-100]
5. Some members of a record may hold either a shape S of their own or a status object in its place: exactly
   those in the table below, each with the tokens it may hold ("any" is any of the five). The writer schema
   (`record_format.md` section 1 item 2) gives exactly these members as a choice between S and a status
   object, and in no other member does a status object stand.

| Member | Tokens |
|---|---|
| a form's member (`value` for a constant, otherwise the member named like the form), except `evidence`, which never holds one | `withheld` |
| `statistics`, wherever a block sits (`uncertainty.md` section 1) | `withheld`; on reference data, `not_applicable` (`fits_and_reference_data.md` section 1) |
| in a statistics block, `central` and `basis` | `not_applicable` |
| in a statistics block, `represents` | `unstated`, `not_applicable` |
| in a statistics block, `distribution` and `precision_conditions`; in a relative or expanded uncertainty, `distribution`, `represents` and `precision_conditions` | `unstated` |
| in a statistics block, `population_level` | `unstated`; in its `within`, `none` |
| in a statistics block, `n_specimens`, `n_donors`, `n_sources`, `mean`, `sd`, `min`, `max`, `relative_uncertainty` and `expanded_uncertainty`; in a relative or expanded uncertainty, `coverage_factor`, `coverage_probability` and `dof` | any |
| an interval's `lower` and `upper`, in the interval form or an `interval` structure | `none` |
| a power law's `range` | `unstated` |
| a condition, and a specimen fact | any |
| a `plus_minus` entry's `stated_as` (section 6.1) | `unstated` |
| a `unit` or `axis_unit`, wherever it sits | any, compared only at step 9 (`read_side_contract.md` section 3) |
| each member of an evidence entry but `provenance` (`record_format.md` section 4.3) | any; `withheld` only in every one of them at once (section 7 item 2) |
| `review`, in a provenance object | `not_checked` (section 2 item 6) |
| `assistance`, in a provenance object | `none` |
| a parameter set's `params` | `not_applicable` |
| a parameter set's `witness` | `none`; in its `datum`, `withheld` |
| an `ensemble`'s `counts` and its members' `groups`, per level (`uncertainty.md` section 2) | any |
| a `marginals` structure's `dependence` | `unstated` |

In a member of this table, an object holding `status` is a status object. It breaks its shape, and refuses the
field it belongs to (`form_invalid`), where its `status` or `reason` is not a string, or where it also holds a
member S defines (for a condition, `value`, `range`, `token`, `unit`, `basis`, `inferred_from`, `plus_minus`
and `set_or_measured`; a fact's members; a statistics block's members). Where S is a number, a string or a
token, and there only, it does so also where it holds any member but `status` and `reason`. Elsewhere a member
beside `status` and `reason` that S does not define is ignored, as a member the reader does not know
(`record_format.md` section 10). A status token its row does not allow refuses the field as `form_invalid`,
and one the reader does not know as `unknown_token`. A status object that breaks its shape is read for nothing
else, so its token gives no reason of its own: one holding `withheld` beside a table's members refuses its
field as `form_invalid` alone, not as a withheld value too (section 7 item 5). At read, these refusals apply
to the members step 8 checks (`read_side_contract.md` section 3); in any other member they are left to the
record checks. Two members are read otherwise: `review` never refuses (section 2 item 6), and a unit's token,
known or not, is compared only at step 9 (`record_format.md` section 4.2), the rest of this paragraph holding
for a unit at step 8. In a member not in this table, an object holding `status` is not a status object: it is
read as the member's own shape, in which `status` is a member the reader does not know. The keys of
`conditions` and of `specimen` are names, so `status` there names a condition or a fact, never a status.
[PR-110]

## 2. The provenance object

Every value field has a `provenance` object. A parameter set's provenance applies to all its parameters,
except where `per_parameter` maps a parameter name to a provenance object of its own, which replaces the set's
for that parameter. [RC-021]

```json
"provenance": {
  "origin": "measured_by_source",
  "source": {"key": "smith2019",
             "document": {"identifier": "doi:10.1000/xyz123", "version": "version_of_record"},
             "locator": {"type": "table", "label": "Table 2", "page": 5,
                         "column": {"header": "Density (g cm-3)", "index": 3}, "row": "liver"}},
  "extraction": {"method": "table", "source_unit": "g/cm3", "conversion": "multiplied by 1000",
                 "text_extraction": "pdftotext 24.02.0"},
  "evidence": {"quote": "Liver 1.06 ± 0.02",
               "locator": {"type": "table", "label": "Table 2", "page": 5,
                           "column": {"header": "Density (g cm-3)", "index": 3}, "row": "liver"},
               "document": {"identifier": "doi:10.1000/xyz123", "version": "version_of_record"},
               "copy": {"sha256": "...", "retrieved": "2026-10-11"}},
  "assistance": {"status": "none"},
  "review": {"result": "reviewed", "reviewer": "...", "orcid": "0000-0000-0000-0000", "date": "2026-10-12",
             "independent_of_extraction": true,
             "checklist": ["value", "unit", "conditions", "specimen", "statistic", "primary_or_cited"]}
}
```

| Member | Required | Contents |
|---|---|---|
| `origin` | yes | `measured_by_source`, `measured_by_contributor`, `fitted`, `derived`, `evaluated_from_formulation` or `stated_without_origin` (a number found in code or on a datasheet with nothing behind it; a read of it gives `unknown`, `read_side_contract.md` section 2) |
| `source` | for origin `measured_by_source`, and for `stated_without_origin` where a document states the number; for `fitted` the fit record's `data` names the data instead, for `derived` the `derivation`'s inputs do | `key` in the source registry (section 8); `document`, its `identifier` (a DOI as `doi:<DOI>`, or a URL) and `version`; `locator`, valid for that version |
| `extraction` | yes | section 3 |
| `evidence` | where section 4 requires it | `quote` (or `quote_sha256`), `locator`, `document`, `copy` |
| `assistance` | yes | `{"status": "none"}`, or the tool, model and provider as reported, the prompt version and the date. Assistance never changes the origin |
| `review` | yes | `{"status": "not_checked"}`, or `{"result": "reviewed", ...}` with who checked the value against the source, their ORCID, the date, whether they are independent of whoever or whatever extracted it, and the checklist items covered |
| `derivation` | when the origin is `derived` | section 5 |
| `formulation` | when the origin is `evaluated_from_formulation` | the formulation's name and version and the evaluation that produced the value; this is its evidence in place of a quote |
| `search` | when `statistics.represents` is `across_sources` | the queries, databases, date and inclusion criteria that found the sources; `weighting`, the source's own weighting of what it pools where it has one, recorded and never re-applied; and `inputs`: `primary` (the sources pooled report measurements), `secondary` (they are compilations) or `mixed` [RC-201] |
| `import` | no | what an importer found (a citation beside a number in code, the number as found); a lead only |
| `per_parameter` | no | parameter name to provenance, in a parameter set |
| `recipe` | in a reference-only value | section 7 |

1. A checker flags a provenance object without a member its row requires. [RC-044]
2. A `locator` names its `type` (`table`, `figure`, `page`, `equation`, `text`, `dataset`) and holds for the
   document version named beside it. A table locator quotes the column header and gives its index, counting
   from 1 as printed. [RC-022] [RC-023]
3. A checker refuses an origin token it does not know (`record_format.md` section 10). [RC-024]
4. `import` is never provenance. A reader never reports it as the value's source, and a checker flags a
   record whose `source` has no review beyond what `import` holds. In the importer prototype every citation
   found in code that could be checked carried an error (AD 4.7). [PR-101] [RC-025]
5. A record drafted with assistance has its review set by a person before it can be shipped (section 7).
   [RC-026]
6. When it reads a value (`read_side_contract.md` section 3, step 8), a reader checks `origin`; `source`,
   present where the origin is `measured_by_source` and, wherever present, an object whose `key` is a string,
   since a result returns the key alone (its `document` and `locator` are the record checks', RC-044); and
   `derivation` for origin `derived` (section 5). The other members are checked on the write side only.
   `review` never refuses the field. A reader returns it as found in two cases only, each holding no member
   one slip from a member a review names (`record_format.md` section 10 item 5): a status object holding
   `not_checked` and no `result`; or an object holding no `status` whose `result` is a token the reader knows
   (`reviewed`). Every other review reads as `{"status": "not_checked"}`: one that is `null`, absent or not an
   object, one holding both `status` and `result`, and one holding a status token other than `not_checked` or
   a `result` token the reader does not know. A review lies outside the content hash (`record_format.md`
   section 9), so a refusal on it would let an edit no pin covers refuse a pinned record. [PR-109]
7. A source that is a release of a database names the release in `document.version`, and its locator, of
   type `dataset`, names in `entry` the entry's identifier, one that does not change between releases.
   [RC-200]
8. Schema 0.1.0 has no origin for a value predicted by a model of the substance (from first principles, or
   learned from other data): such a value cannot be recorded until a minor version adds one with a consumer.
   [not yet covered]

## 3. Extraction

`extraction.method` is one of:

| Method | Also requires |
|---|---|
| `table`, `text` | `text_extraction`: which text extraction of the document matched the quote |
| `digitised_figure` | `digitisation`: the tool, the axis calibration (two known points per axis, and the axis scale) and an estimate of digitising error |
| `supplementary_dataset` | `dataset_licence` |
| `own_measurement` | nothing more |
| `derivation` | `derivation` in the provenance object |
| `fit` | the value field's `fit` record (`fits_and_reference_data.md` section 2), on a parameter set or any other value whose origin is `fitted` |
| `formulation` | `formulation` in the provenance object |

1. A method without the members its row requires is flagged. [RC-045]
2. Where the source's unit differs from the stored SI unit, `source_unit` records it and `conversion` the
   step taken. [RC-027]
3. For attenuation, `attenuation_coefficient` records `amplitude` or `intensity` as the source reported it,
   and the conversion to the stored amplitude coefficient (`record_format.md` section 6). It arrives with the
   acoustic section, and its case with it. [RC-028]
4. A digitised figure without its axis calibration or digitising error is flagged. [RC-029]

## 4. Evidence

1. Where a quote is present, a checker verifies it in every namespace. The curated library's own policy
   requires a verbatim `quote` for every value extracted from text or a table, with the conditions and, for a
   power law, the exponent quoted too; its record check flags one without. Other namespaces MAY omit quotes.
   [RC-030]
2. `document` names the document's identifier and version; `copy` holds the SHA-256 of the copy read and the
   retrieval date. A copy's hash identifies that copy, not the document: publishers stamp copies, so
   re-verification means the quote occurs in your own copy at the locator. `copy` is excluded from the content
   hash (`record_format.md` section 9). [RC-031]
3. A checker with a copy confirms that the quote occurs at its locator and contains the value's numbers. With
   no copy it reports `not_checked`, never a pass. [RC-032]
4. Where quotes may not ship (a source whose redistribution status is `values_only`, or a ruling of the legal
   review, AD 6.5), `quote_sha256` replaces `quote`. It is `sha256:` and the lowercase hexadecimal SHA-256 of
   the quote's UTF-8 bytes after normalising it to Unicode NFKC, replacing every run of characters with the
   Unicode `White_Space` property by one space (U+0020), and trimming both ends. The text stays in the
   curator's private store, and re-verification compares hashes. The conformance suite has test vectors.
   [RC-033]
5. A withheld value carries neither `quote` nor `quote_sha256`: a quote is a template around the value, and
   numbers can be enumerated until the hash matches. [RC-046]
6. A copy stamped with personal data (a downloader's name or address) never ships, in any form. [RC-034]
7. For a digitised figure, evidence is the locator and the copy's hash. For a formulation, it is
   `formulation`.

## 5. Derivations

1. A derived value's `derivation` holds `method`, the method's identifier, a string; `inputs`, a non-empty
   list of `{"record": {"id", "version", "content_hash"}, "field"}`, `id`, `version`, `content_hash` and
   `field` each a string; and `assumptions`, a list of texts. [RC-035] [PR-102]
2. A conversion that needs another quantity (per mass to per volume, which needs a density) is a derivation;
   a rescaling (millimetres to metres) is a unit conversion (AD 4.3). [not yet covered]
3. A derived value carries the specimen facts of each input in `derivation.input_specimens`, a list of
   `{"input": <index into inputs>, "specimen": {...}}`, each `input` a whole number below the length of
   `inputs` and each `specimen` a map of specimen facts (section 6.2). Where its inputs' conditions differ,
   `derivation` holds `"mixed_conditions": true`; where present, the member is a boolean. A reader checks
   these shapes and those of item 1 at step 8 (section 2 item 6), and returns both. [PR-102] [RC-036]

## 6. Conditions and specimen facts

Conditions describe the test, specimen shape and size included; specimen facts describe the thing tested (AD
4.8; `record_format.md` section 4.1). Each is a map from a name to one of these shapes, and each shape except
a status object carries a `basis`: `stated`, or `inferred` with an `inferred_from` text (a figure's caption,
say). [RC-037]

```json
"conditions": {
  "temperature":           {"value": 310.15, "unit": "K", "basis": "stated"},
  "shear_rate":            {"range": [100, 1000], "unit": "1/s", "basis": "stated"},
  "density_kind":          {"token": "apparent", "basis": "inferred", "inferred_from": "Methods, p. 3"},
  "measurement_geometry":  {"token": "tube", "basis": "stated"},
  "measurement_dimension": {"value": 5.0e-5, "unit": "m", "basis": "stated"},
  "magnetic_flux_density": {"status": "unstated"}
}
```

The tables below are the vocabulary of schema 0.1.0. The files in `schema/0.1/vocabulary/` are generated from
them; where the two differ, these tables hold. The vocabulary grows by minor versions. [not yet covered]

### 6.1 Conditions of schema 0.1.0

| Name | Shape | Unit or tokens | Required with |
|---|---|---|---|
| `temperature` | numeric | `K` | — |
| `shear_rate` | numeric | `1/s` | — |
| `magnetic_flux_density` | numeric | `T` (the applied field during the measurement) | — |
| `density_kind` | token | `apparent` (the whole specimen, pores included), `matrix` (the solid phase only) | — |
| `specimen_shape` | token | `sphere`, `cylinder`, `prolate_spheroid`, `oblate_spheroid`, `slab`, `film`, `irregular` | — |
| `specimen_size` | numeric | `m`: the specimen's characteristic dimension (a sphere's diameter, a cylinder's diameter, a slab's or film's thickness) | — |
| `measurement_geometry` | token | `bulk`, `tube`, `gap` | — |
| `measurement_dimension` | numeric | `m`: a tube's inner diameter or a gap's width | `measurement_geometry`: `tube`, `gap` |
| `test_method` | token | `rotational_rheometer`, `capillary_viscometer`, `vibrating_sample_magnetometer`, `squid_magnetometer`, `hysteresigraph` (a closed magnetic circuit, as in ASTM A977/A977M and IEC 60404-5, in which the specimen's demagnetisation does not enter; makers also write "hysteresisgraph"), `pycnometer` | — |

1. A numeric condition holds `{"value", "unit"}` or `{"range": [lo, hi], "unit"}` with `lo <= hi`, its `unit`
   a string or a status object (`record_format.md` section 4.2), compared with the condition's unit at step 9
   alone (`read_side_contract.md` section 3), and MAY add `plus_minus` and `set_or_measured` (items 6 and 7);
   a token condition holds `{"token"}`, and registers no unit, so a `unit` on one gives `unit_mismatch` at
   step 9; either may instead hold a status object. [RC-047] [PR-037]
2. A condition name a reader does not know gives `unknown`; a token it does not know refuses the field
   (`record_format.md` section 10). [PR-103]
3. A check against an `unstated` condition gives `unknown`, never `met`, and the result carries the value
   (`read_side_contract.md` section 5). [PR-104]
4. A table's or power law's axis is a numeric condition of this table, and its unit is that condition's unit.
   [RC-038]
5. Conditions for the sections still to come arrive with them: `frequency`, `wavelength`, `strain_rate`,
   `loading_mode`, `propagation_direction` and `specimen_orientation`, and the acoustic test methods.
   Whether a specimen fact (a porosity, say) may serve as a table's axis is settled with the first consumer
   that needs one (AD 12.2). A test method that probes a length below the specimen's (indentation by a small
   tip, the tracking of small particles, atomic force microscopy) enters the vocabulary only together with a
   numeric condition stating the length it probes, which every field measured by that method then requires.
   [not yet covered]
6. `plus_minus` records the ± a source states for a numeric condition: a non-empty list of `{"stated_as",
   "value", "unit"}`. `stated_as` is `bound` (the source states the condition was held within ± `value`),
   `sd` (a standard deviation the source states) or `{"status": "unstated"}` (a ± whose kind the source does
   not state); `value` is a number not below zero; `unit` is a string or a status object (`record_format.md`
   section 4.2), compared with the condition's unit at step 9 alone, as the condition's own is
   (`unit_mismatch`, `read_side_contract.md` section 3). The list holds at most one entry of each kind, and an
   entry of unstated kind stands alone. An unstated kind cannot sit beside a stated one, since it might be a
   second entry of that kind. A list that breaks these rules breaks the condition's shape. How the check uses
   it is `read_side_contract.md` section 5's. [PR-108] [PR-037] [RC-047]
7. `set_or_measured` is `set_point` (the value the apparatus was set to) or `measured` (a value measured on
   the specimen or its medium); absent, the source does not say. A reader returns it, and the check does not
   use it. [PR-108]
8. A ± is recorded in `plus_minus`, never as a range: a range says what the value covers
   (`read_side_contract.md` section 5). [not yet covered]
9. A condition whose "Required with" entry names another condition and a token MUST be present on a field
   where that other condition holds that token, holding `{"status": "unstated"}` if the source does not state
   it. A read checks it as one the field's row requires wherever that other condition holds that token, in
   the record or by an implied condition the read applies (`read_side_contract.md` section 5). [RC-006]
   [PR-311]

### 6.2 Specimen facts of schema 0.1.0

| Name | JSON shape |
|---|---|
| `species` | `{"ncbi_taxon": <integer>, "label": <text>, "basis"}`, an NCBI Taxonomy identifier |
| `anatomical_site` | `{"uberon": "UBERON:<digits>", "label": <text>, "basis"}` |
| `tissue_state` | `{"token": "in_vivo" \| "ex_vivo_fresh" \| "frozen_thawed" \| "fixed" \| "phantom", "basis"}` |
| `disease_and_treatment_state` | `{"token": "normal" \| "diseased" \| "treated", "text": <which>, "basis"}`: `text` names the disease or the treatment, and is present exactly when `token` is `diseased` or `treated` |
| `preparation` | `{"text": <text>, "basis"}` |
| `preservation` | `{"token": "none" \| "refrigerated" \| "frozen" \| "fixed_formalin" \| "other", "text": <text, required for other>, "basis"}` |
| `post_mortem_interval` | `{"value", "unit": "s", "basis"}` |
| `donor_age` | `{"value", "unit": "s", "basis"}` or `{"range": [lo, hi], "unit": "s", "basis"}` |
| `mimics` | `{"text": <text>, "basis": "stated"}`: what a phantom or substitute was made to mimic, as its maker states it; its `basis` is fixed to `stated`, so it takes no `inferred_from` |
| `supply_form` | `{"token": "stock" \| "coupon" \| "finished_component", "basis"}`: a manufactured material as supplied, a coupon made or cut for the test, or a finished component tested as a specimen of its material |
| `lot` | `{"text": <the lot or batch, as the source names it>, "basis"}` |

1. Every fact takes its row's shape or a status object. A checker flags a malformed ontology identifier, a
   shape other than its row's, and a fact name not in this table. [RC-039]
2. Specimen facts may sit on a section and on a field; the field's fact overrides the section's, fact by fact
   (`record_format.md` section 4). [PR-009]
3. A consumer's target uses these shapes without `basis` (`declarations.md`), and the build compares fact by
   fact there. [not yet covered]
4. `mimics` is a fact about a phantom's design. It never makes the phantom stand in for anything; a consumer
   accepts stand-ins in its declarations. [not yet covered]
5. A commercial material has one record per grade or product. A value that holds for the grade or product as
   a whole, such as its datasheet's limits, holds `lot` as `{"status": "not_applicable"}`; a measurement on a
   particular lot is a further alternative of the field (`record_format.md` section 5), naming its `lot`.
   [not yet covered] A read of such a field with no pick gives `no_pick` under `want: value` and under
   `want: bounds` alike, each alternative in its own entry of `alternative_values` (`read_side_contract.md`
   section 3, step 7). [PR-013]

## 7. Tiers, reference-only values and fill-ins

1. A record never states its tier. A checker computes it from the source registry: a value whose source's
   redistribution status is `permitted` or `values_only` is shipped (a `values_only` source's quotes ship as
   `quote_sha256`); one whose status is `not_permitted` or `unknown` is reference-only; private values never
   enter a published repository. A value drafted with assistance stays reference-only until a person has set
   its review and its source's redistribution status. [RC-040]
2. In a reference-only value, the form's member and `statistics` both hold `{"status": "withheld"}` (a mean or
   a range would publish the value), and `provenance.recipe` gives the locator and the steps to extract the
   value from one's own copy, including the exact arithmetic that turns the source's number into the stored
   one. No quote, quote hash or check point ships with it. In a reference-only entry of biocompatibility
   evidence (`record_format.md` section 4.3), every member but `provenance` holds `{"status": "withheld"}`,
   never only some of them, and the entry's provenance carries the recipe; the source's words are quotes, so
   none ships. [RC-041] [PR-052]
3. The withheld status is what the repository holds, not what a release strips: the number never enters the
   public repository or its history, and lives only in the curator's private store. A record check runs on the
   repository, not only on a release. [RC-048]
4. The curator's own witness result at review is recorded in the reference-only record (`model_families.md`).
   [not yet covered]
5. A reader refuses a withheld value, with the reason `withheld`. [PR-105]
6. **A user fills in a reference-only value with an overlay** of purpose `fill_in` in the user's own
   namespace, whose base is the reference-only record by identifier, version and content hash
   (`record_format.md` section 4.4). The curated record never changes. The overlay's replaced field carries
   the values the user extracted and their statistics; its `provenance` holds the origin the source gives, the
   `evidence` from the user's copy (`document` and `copy`), and the user's `review`, which is `{"status":
   "not_checked"}` until someone checks it; the overlay's `licence.values` is the user's, and
   `LicenseRef-user-extracted` for a source that does not permit redistribution. A reader labels every value
   it reads through the overlay `user_extracted` and reports the overlay's review, never the curator's.
   [PR-106]
7. The fill-in's `evidence.document` is compared with the base's `source.document`. Unless both are present,
   each with a string `identifier` and `version`, and the two are equal in both, compared code point for code
   point, every read of the value gives `unknown`, with the reason `fill_in_version_mismatch`: a document
   either side leaves unstated cannot show that the user read the version the base cites. A check of a
   fill-in is reported as "fill-in consistent with the user's copy" at most. [PR-107] Where the base's field
   holds alternatives, no document of the base is compared, and every read of the value gives
   `fill_in_version_mismatch`: a fill-in replaces the whole field and does not say which alternative it fills
   in. Where the fill-in's own field holds alternatives, each alternative's `evidence.document` is compared
   with the base's `source.document` as above, and a mismatch gives the reason with that alternative's index
   (`read_side_contract.md` section 2 item 2). Where both fields hold alternatives, each fill-in alternative's
   read gives the reason with its own index, since the reason is found while reading it
   (`read_side_contract.md` section 3, step 12). A pick located at the fill-in names one of its alternatives
   (`read_side_contract.md` section 3, step 7). [PR-107]
8. A fill-in tool converts the source's number to the stored one by the recipe's arithmetic in decimal, then
   rounds once to double precision, so two users who type the same number store the same double. [not yet
   covered]

## 8. The source registry

The library repository holds one registry entry per source; a value's `source.key` names one. The registry's
file format is outside this specification; its content is: [RC-042]

| Member | Contents |
|---|---|
| `key`, `citation` | a citation key and its BibTeX |
| `identifier` | a DOI as `doi:<DOI>`, or a URL |
| `publication_licence`, `dataset_licence` | as stated by the publisher |
| `redistribution` | `state` (`permitted`, `values_only`, `not_permitted`, `unknown`), `reason`, `judged_by`, `date`. Only a person sets it; it stays `unknown` until then |
| `role` | why the source is in the library |
| `copies` | per copy a curator holds: its retrieval route, its document version, the licence it came under, its SHA-256, and whether it is stamped with personal data |

A model never sets a redistribution state or a review (AD 8.2). [not yet covered]

## Cases

| Case | Suite | Tests |
|---|---|---|
| PR-100 | plain read | a status is returned as a status, never as a value or a pass |
| PR-101 | plain read | an `import` lead is never reported as the source |
| PR-102 | plain read | a derived value returns its derivation's `method`, `inputs` and `assumptions`, its inputs' specimen facts and its mixed-conditions flag, with the label `mixed_conditions` where the flag is true; a derivation that breaks the shapes of section 5 refuses the field (`form_invalid`) |
| PR-103 | plain read | an unknown condition name gives `unknown`; an unknown condition token refuses the field |
| PR-104 | plain read | a check against an unstated condition gives `unknown`, carrying the value |
| PR-105 | plain read | a withheld value is refused (`withheld`) |
| PR-106 | plain read | a value read through a fill-in overlay is labelled `user_extracted`, with the overlay's review |
| PR-107 | plain read | a fill-in from another document identifier or version gives `unknown` (`fill_in_version_mismatch`), and so does one whose `evidence.document`, or whose base's `source.document`, is absent or lacks a string `identifier` or `version`; so does a fill-in over a base field holding alternatives, whatever their documents; where the fill-in's field holds alternatives, each one's document is compared, a mismatch carrying its `alternative`; where both hold alternatives, each fill-in alternative gives the reason with its `alternative` |
| PR-108 | plain read | `plus_minus` and `set_or_measured` are returned with the condition; a list with two entries of one kind, an unstated entry beside another, a negative value or an empty list refuses the field (`form_invalid`), and so does `plus_minsu` beside a condition's `value` |
| PR-109 | plain read | a provenance member a read does not check, broken or `null` (`"extraction": null`), does not refuse the field, nor does a `source` broken beyond its `key`, while a `source` missing where the origin is `measured_by_source` does (`form_invalid`); a `review` that is `null`, absent or not an object, holds both `status` and `result`, holds a status token other than `not_checked`, holds an unknown `result` token, or holds a member one slip from one a review names (`reviewr`) reads as `{"status": "not_checked"}`, and one holding the known `result` `reviewed` is returned as found |
| PR-110 | plain read | an object holding `status` beside a member of the shape it stands in for refuses the field (a condition's `unit` or `basis`), and so does one beside any member but `reason` where that shape is a number, string or token (an interval's `upper`, a statistics `sd`, a `unit` on evidence); beside an unknown member of an object shape it is a status object; a status token its row does not allow refuses the field (`form_invalid`: a constant's `value` holding `unstated`, an `interval` holding `none`), and so does a `status` or `reason` that is not a string; none of these refuses in a member step 8 does not check (`assistance` holding `unstated`); a `status` member where no status object is allowed is a member the reader does not know; a `status` key in `conditions` names a condition (`condition_unknown_name`) |
| RC-020 | record checks | a status object with members other than `status` and `reason` is flagged |
| RC-021 | record checks | `per_parameter` names only parameters of its set |
| RC-022 | record checks | a locator without the document's identifier and version is flagged |
| RC-023 | record checks | a table locator without its column header and index is flagged |
| RC-024 | record checks | an unknown origin token is flagged |
| RC-025 | record checks | a source supported only by an `import` lead is flagged |
| RC-026 | record checks | an assisted value whose review is `not_checked` is not shipped |
| RC-027 | record checks | a converted value without `source_unit` and `conversion` is flagged |
| RC-028 | record checks | attenuation without its amplitude-or-intensity fact is flagged (with the acoustic section) |
| RC-029 | record checks | a digitised figure without calibration or digitising error is flagged |
| RC-030 | record checks | a quote present is verified; a curated value from text or a table without one is flagged |
| RC-031 | record checks | evidence without the document's identity and version beside the copy's hash is flagged |
| RC-032 | record checks | a quote absent at its locator, or not containing the value's numbers, fails; with no copy, `not_checked` |
| RC-033 | record checks | `quote_sha256` vectors: NFKC, White_Space runs, trimming, lowercase hexadecimal |
| RC-034 | record checks | a stamped copy, or anything taken from it, in a release is flagged |
| RC-035 | record checks | a derivation without its method, inputs with hashes, and assumptions is flagged |
| RC-036 | record checks | a derivation from inputs at different conditions without the flag is flagged |
| RC-037 | record checks | a condition or fact without a basis, or `inferred` without `inferred_from`, is flagged |
| RC-038 | record checks | a table or power-law axis that is not a numeric condition, or with another unit, is flagged |
| RC-039 | record checks | malformed ontology identifiers, wrong fact shapes and unknown fact names are flagged, `supply_form` and `lot` among the facts |
| RC-040 | record checks | the computed tier matches what the repository and a release hold, for each value and each evidence entry |
| RC-041 | record checks | a reference-only value that holds its value, statistics, quote, quote hash or check points, or a reference-only evidence entry holding anything but `withheld` in a member other than its provenance, is flagged |
| RC-042 | record checks | a `source.key` missing from the registry is flagged |
| RC-043 | record checks | `not_applicable` in a condition other than the form's axis is flagged |
| RC-044 | record checks | a provenance object without a required member is flagged |
| RC-045 | record checks | an extraction method without the members its row requires is flagged |
| RC-046 | record checks | a withheld value or evidence entry carrying a quote or a quote hash is flagged |
| RC-047 | record checks | a condition of the wrong shape, a reversed range, a unit other than the condition's, or a `plus_minus` breaking item 6 of section 6.1 is flagged |
| RC-048 | record checks | a reference-only value that held a number in any earlier commit of the repository is flagged |
| RC-200 | record checks | a database source whose `document.version` names no release, or whose locator names no `entry`, is flagged |
| RC-201 | record checks | a `search` record without `inputs`, or with an unknown token there, is flagged |

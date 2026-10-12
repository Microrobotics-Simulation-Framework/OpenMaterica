# Provenance, conditions and specimen facts

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Member names: `record_format.md`.
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
| `search` | when `statistics.represents` is `across_sources` | the queries, databases, date and inclusion criteria that found the sources |
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

## 3. Extraction

`extraction.method` is one of:

| Method | Also requires |
|---|---|
| `table`, `text` | `text_extraction`: which text extraction of the document matched the quote |
| `digitised_figure` | `digitiser`: the tool, the axis calibration (two known points per axis, and the axis scale) and an estimate of digitising error |
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

1. A derived value's `derivation` names its method identifier, its `inputs` (each a record identifier,
   version, content hash and field) and its assumptions. [RC-035]
2. A conversion that needs another quantity (per mass to per volume, which needs a density) is a derivation;
   a rescaling (millimetres to metres) is a unit conversion (AD 4.3). [not yet covered]
3. A derived value carries the specimen facts of each input in `derivation.input_specimens`, a list of
   `{"input": <index into inputs>, "specimen": {...}}`. Where its inputs' conditions differ, `derivation`
   holds `"mixed_conditions": true`. A reader returns both. [PR-102] [RC-036]

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

The tables below are the vocabulary of schema 0.1.0. Vocabulary files under `data/vocabulary/` are generated
from them; where the two differ, these tables hold. The vocabulary grows by minor versions. [not yet covered]

### 6.1 Conditions of schema 0.1.0

| Name | Shape | Unit or tokens |
|---|---|---|
| `temperature` | numeric | `K` |
| `shear_rate` | numeric | `1/s` |
| `magnetic_flux_density` | numeric | `T` (the applied field during the measurement) |
| `density_kind` | token | `apparent` (the whole specimen, pores included), `matrix` (the solid phase only) |
| `specimen_shape` | token | `sphere`, `cylinder`, `prolate_spheroid`, `oblate_spheroid`, `slab`, `film`, `irregular` |
| `specimen_size` | numeric | `m`: the specimen's characteristic dimension (a sphere's diameter, a cylinder's diameter, a slab's or film's thickness) |
| `measurement_geometry` | token | `bulk`, `tube`, `gap` |
| `measurement_dimension` | numeric | `m`: a tube's inner diameter or a gap's width; required when `measurement_geometry` is `tube` or `gap` |
| `test_method` | token | `rotational_rheometer`, `capillary_viscometer`, `vibrating_sample_magnetometer`, `squid_magnetometer`, `pycnometer` |

1. A numeric condition holds `{"value", "unit"}` or `{"range": [lo, hi], "unit"}` with `lo <= hi`, in the
   condition's unit; a token condition holds `{"token"}`; either may instead hold a status object. [RC-047]
2. A condition name a reader does not know gives `unknown`; a token it does not know refuses the field
   (`record_format.md` section 10). [PR-103]
3. A check against an `unstated` condition gives `unknown`, never `met`, and the result carries the value
   (`read_side_contract.md` section 5). [PR-104]
4. A table's or power law's axis is a numeric condition of this table, and its unit is that condition's unit.
   [RC-038]
5. Conditions for the sections still to come arrive with them: `frequency`, `wavelength`, `strain_rate`,
   `loading_mode`, `propagation_direction` and `specimen_orientation`, and the acoustic test methods.
   Whether a specimen fact (a porosity, say) may serve as a table's axis is settled with the first consumer
   that needs one (AD 12.2). [not yet covered]

### 6.2 Specimen facts of schema 0.1.0

| Name | JSON shape |
|---|---|
| `species` | `{"ncbi_taxon": <integer>, "label": <text>, "basis"}`, an NCBI Taxonomy identifier |
| `anatomical_site` | `{"uberon": "UBERON:<digits>", "label": <text>, "basis"}` |
| `tissue_state` | `{"token": "in_vivo" \| "ex_vivo_fresh" \| "frozen_thawed" \| "fixed" \| "phantom", "basis"}` |
| `disease_and_treatment_state` | `{"token": "normal" \| "diseased" \| "treated", "text": <which>, "basis"}` |
| `preparation` | `{"text": <text>, "basis"}` |
| `preservation` | `{"token": "none" \| "refrigerated" \| "frozen" \| "fixed_formalin" \| "other", "text": <text, required for other>, "basis"}` |
| `post_mortem_interval` | `{"value", "unit": "s", "basis"}` |
| `donor_age` | `{"value", "unit": "s", "basis"}` or `{"range": [lo, hi], "unit": "s", "basis"}` |
| `mimics` | `{"text": <text>, "basis": "stated"}`: what a phantom or substitute was made to mimic, as its maker states it |

1. Every fact takes its row's shape or a status object. A checker flags a malformed ontology identifier, a
   shape other than its row's, and a fact name not in this table. [RC-039]
2. Specimen facts may sit on a section and on a field; the field's fact overrides the section's, fact by fact
   (`record_format.md` section 4). [PR-009]
3. A consumer's target uses these shapes without `basis` (`declarations.md`), and the build compares fact by
   fact there. [not yet covered]
4. `mimics` is a fact about a phantom's design. It never makes the phantom stand in for anything; a consumer
   accepts stand-ins in its declarations. [not yet covered]

## 7. Tiers, reference-only values and fill-ins

1. A record never states its tier. A checker computes it from the source registry: a value whose source's
   redistribution status is `permitted` or `values_only` is shipped (a `values_only` source's quotes ship as
   `quote_sha256`); one whose status is `not_permitted` or `unknown` is reference-only; private values never
   enter a published repository. A value drafted with assistance stays reference-only until a person has set
   its review and its source's redistribution status. [RC-040]
2. In a reference-only value, the form's member and `statistics` both hold `{"status": "withheld"}` (a mean or
   a range would publish the value), and `provenance.recipe` gives the locator and the steps to extract the
   value from one's own copy, including the exact arithmetic that turns the source's number into the stored
   one. No quote, quote hash or check point ships with it. [RC-041]
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
7. The fill-in's `evidence.document` is compared with the base's `source.document`. Where the identifier or
   the version differs, every read of the value gives `unknown`, with the reason `fill_in_version_mismatch`.
   A check of a fill-in is reported as "fill-in consistent with the user's copy" at most. [PR-107]
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

| Case | Profile | Tests |
|---|---|---|
| PR-100 | plain read | a status is returned as a status, never as a value or a pass |
| PR-101 | plain read | an `import` lead is never reported as the source |
| PR-102 | plain read | a derived value returns its inputs' specimen facts and its mixed-conditions flag |
| PR-103 | plain read | an unknown condition name gives `unknown`; an unknown condition token refuses the field |
| PR-104 | plain read | a check against an unstated condition gives `unknown`, carrying the value |
| PR-105 | plain read | a withheld value is refused (`withheld`) |
| PR-106 | plain read | a value read through a fill-in overlay is labelled `user_extracted`, with the overlay's review |
| PR-107 | plain read | a fill-in from another document identifier or version gives `unknown` (`fill_in_version_mismatch`) |
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
| RC-039 | record checks | malformed ontology identifiers, wrong fact shapes and unknown fact names are flagged |
| RC-040 | record checks | the computed tier matches what the repository and a release hold |
| RC-041 | record checks | a reference-only value that holds its value, statistics, quote, quote hash or check points is flagged |
| RC-042 | record checks | a `source.key` missing from the registry is flagged |
| RC-043 | record checks | `not_applicable` in a condition other than the form's axis is flagged |
| RC-044 | record checks | a provenance object without a required member is flagged |
| RC-045 | record checks | an extraction method without the members its row requires is flagged |
| RC-046 | record checks | a withheld value carrying a quote or a quote hash is flagged |
| RC-047 | record checks | a condition of the wrong shape, a reversed range, or a unit other than the condition's is flagged |
| RC-048 | record checks | a reference-only value that held a number in any earlier commit of the repository is flagged |

# Provenance, conditions and specimen facts

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Member names: `record_format.md`.
Rationale: AD 4.3, 4.7, 4.8, 4.11, 6.1 and 6.2.

## 1. Statuses

1. Wherever a member has no result, it holds a status object, never an empty value, `null` or a missing
   member: `{"status": <token>}`, optionally with `"reason": <text>`. [RC-020]
2. The tokens are `unstated` (the source does not state it), `not_checked` (a check has not run), `none`
   (there is nothing: no assistance, no witness), `not_applicable` (the member does not apply to this value's
   type) and `withheld` (a reference-only value, section 7).
3. A reader returns a status as a status. It never reads one as a value, a zero or a pass. [PR-100]

## 2. The provenance object

Every value field has a `provenance` object. A parameter set's provenance applies to all its parameters,
except where `per_parameter` maps a parameter name to a provenance object of its own, which replaces the
set's for that parameter. [RC-021]

```json
"provenance": {
  "origin": "measured_by_source",
  "source": {"key": "smith2019",
             "document": {"identifier": "doi:10.1000/xyz123", "version": "version_of_record"},
             "locator": {"kind": "table", "label": "Table 2", "page": 5,
                         "column": {"header": "Density (g cm-3)", "index": 3}, "row": "liver"}},
  "extraction": {"method": "table", "source_unit": "g/cm3", "conversion": "multiplied by 1000",
                 "text_extraction": "pdftotext 24.02.0"},
  "evidence": {"quote": "Liver 1.06 ± 0.02", "locator": {"kind": "table", "label": "Table 2", "page": 5},
               "document": {"identifier": "doi:10.1000/xyz123", "version": "version_of_record"},
               "copy": {"sha256": "...", "retrieved": "2026-10-11"}},
  "assistance": {"status": "none"},
  "review": {"status": "reviewed", "reviewer": "...", "orcid": "0000-0000-0000-0000", "date": "2026-10-12",
             "independent_of_extraction": true, "checklist": ["value", "unit", "conditions", "specimen",
             "statistic", "primary_or_cited"]}
}
```

| Member | Required | Contents |
|---|---|---|
| `origin` | yes | `measured_by_source`, `measured_by_contributor`, `fitted`, `derived`, `evaluated_from_formulation` or `stated_without_origin` (a number found in code or on a datasheet with nothing behind it) |
| `source` | unless the origin is `measured_by_contributor` | `key` in the source registry (section 8); `document`, its identifier and version; `locator`, valid for that version |
| `extraction` | yes | section 3 |
| `evidence` | section 4 | quote, locator, document, copy |
| `assistance` | yes | `{"status": "none"}`, or the tool, model and provider as reported, the prompt version and the date. Assistance never changes the origin |
| `review` | yes | `{"status": "not_checked"}`, or who checked the value against the source, their ORCID, the date, whether they are independent of whoever or whatever extracted it, and the checklist items covered |
| `derivation` | when the origin is `derived` | section 5 |
| `formulation` | when the origin is `evaluated_from_formulation` | the formulation's name and version and the evaluation that produced the value; this is its evidence in place of a quote |
| `search` | when `statistics.represents` is `across_sources` | the queries, databases, date and inclusion criteria that found the sources |
| `import` | no | what an importer found (a citation beside a number in code, the number as found); a lead only |
| `per_parameter` | no | parameter name to provenance, in a parameter set |

1. A `locator` names its `kind` (`table`, `figure`, `page`, `equation`, `text`, `dataset`) and holds for the
   document version named beside it. A table locator quotes the column header and gives its index. [RC-022]
   [RC-023]
2. A checker refuses an origin token it does not know (`record_format.md` section 10). [RC-024]
3. `import` is never provenance. A reader never reports it as the value's source, and a checker flags a
   record whose `source` has no review beyond what `import` holds. In the importer prototype every citation
   found in code that could be checked carried an error (AD 4.7). [PR-101] [RC-025]
4. A record drafted with assistance has its review status set by a person before it can be shipped
   (section 7). [RC-026]

## 3. Extraction

`extraction.method` is one of:

| Method | Also requires |
|---|---|
| `table`, `text` | `text_extraction`: which text extraction of the document matched the quote |
| `digitised_figure` | `digitiser`: the tool, the axis calibration (two known points per axis, and the axis scale) and an estimate of digitising error |
| `supplementary_dataset` | `dataset_licence` |
| `own_measurement` | nothing more |
| `derivation` | `derivation` in the provenance object |
| `fit` | the parameter set's fit record (`fits_and_reference_data.md`) |
| `formulation` | `formulation` in the provenance object |

1. Where the source's unit differs from the stored SI unit, `source_unit` records it and `conversion` the
   step taken. [RC-027]
2. For attenuation, `attenuation_coefficient` records `amplitude` or `intensity` as the source reported it,
   and the conversion to the stored amplitude coefficient (`record_format.md` section 6). [RC-028]
3. A digitised figure without its axis calibration or digitising error is flagged. [RC-029]

## 4. Evidence

1. In the curated library every value extracted from text or a table carries a verbatim `quote`, with the
   conditions and, for a power law, the exponent quoted too. Other namespaces MAY omit it. Where a quote is
   present, a checker verifies it in every namespace. [RC-030]
2. `document` names the document's identifier and version; `copy` holds the SHA-256 of the copy read and the
   retrieval date. A copy's hash identifies that copy, not the document: publishers stamp copies, so
   re-verification means the quote occurs in your own copy at the locator. `copy` is excluded from the content
   hash (`record_format.md` section 9). [RC-031]
3. A checker with a copy confirms that the quote occurs at its locator and contains the value's numbers. With
   no copy it reports `not_checked`, never a pass. [RC-032]
4. Where quotes may not ship (a source whose redistribution status is `values_only`, or a ruling of the legal
   review, AD 6.5), `quote_sha256` replaces `quote`: the SHA-256 of the quote normalised to Unicode NFC, its
   whitespace runs collapsed to one space and trimmed. The text stays in the curator's private store, and
   re-verification compares hashes. [RC-033]
5. A copy stamped with personal data (a downloader's name or address) never ships, in any form. [RC-034]
6. For a digitised figure, evidence is the locator and the copy's hash. For a formulation, it is
   `formulation`.

## 5. Derivations

1. A derived value's `derivation` names its method identifier, its inputs (each a record identifier, content
   hash and field) and its assumptions. [RC-035]
2. A conversion that needs another quantity (per mass to per volume, which needs a density) is a derivation;
   a rescaling (millimetres to metres) is a unit conversion (AD 4.3).
3. A derived value carries the specimen facts of all its inputs. Where its inputs' conditions differ, it
   carries `"mixed_conditions": true`. [PR-102] [RC-036]

## 6. Conditions and specimen facts

Conditions describe the test; specimen facts describe the thing tested (AD 4.8). Each is a map from a name to
one of these shapes, and each shape except `unstated` carries a `basis`: `stated`, or `inferred` with an
`inferred_from` text (a figure's caption, say). [RC-037]

```json
"conditions": {
  "temperature":  {"value": 310.15, "unit": "K", "basis": "stated"},
  "shear_rate":   {"range": [100, 1000], "unit": "1/s", "basis": "stated"},
  "density_kind": {"token": "apparent", "basis": "inferred", "inferred_from": "Methods, p. 3"},
  "measurement_geometry": {"token": "tube", "parameters": {"inner_diameter": {"value": 5.0e-5, "unit": "m"}},
                           "basis": "stated"},
  "frequency":    {"status": "unstated"}
}
```

### 6.1 Conditions of schema 0.1.0

| Name | Shape | Unit or tokens |
|---|---|---|
| `temperature` | numeric | `K` |
| `frequency` | numeric | `Hz` |
| `wavelength` | numeric | `m` |
| `shear_rate` | numeric | `1/s` |
| `strain_rate` | numeric | `1/s` |
| `magnetic_flux_density` | numeric | `T` (the applied field during the measurement) |
| `density_kind` | token | `apparent` (the whole specimen, pores included), `matrix` (the solid phase only) |
| `loading_mode` | token | `uniaxial_tension`, `uniaxial_compression`, `confined_compression`, `simple_shear`, `equibiaxial_tension`, `indentation` |
| `test_method` | token | `rotational_rheometer`, `capillary_viscometer`, `vibrating_sample_magnetometer`, `squid_magnetometer`, `pycnometer`, `pulse_echo`, `through_transmission` |
| `propagation_direction` | token | `material_axis_1`, `material_axis_2`, `material_axis_3` (the material's principal axes) |
| `measurement_geometry` | token, with `parameters` | `bulk`, `tube` (`inner_diameter`), `gap` (`gap_width`) |
| `specimen_orientation` | token | `longitudinal`, `transverse`, `radial`, `oblique` (relative to the anatomy it was cut from) |

1. Tokens and names come from the vocabulary files under `data/vocabulary/`, which are normative and grow by
   minor versions. A condition name a reader does not know gives `unknown`; a token it does not know refuses
   the field (`record_format.md` section 10). [PR-103]
2. A check against an `unstated` condition gives `unknown`, never `met`, and the result carries the value
   (`declarations.md`). [PR-104]
3. A table's or power law's axis is a condition name, and its unit is that condition's unit. [RC-038]

### 6.2 Specimen facts of schema 0.1.0

| Name | Shape |
|---|---|
| `species` | `{"ncbi_taxon": <integer>, "label": <text>}`, an NCBI Taxonomy identifier |
| `anatomical_site` | `{"uberon": "UBERON:<digits>", "label": <text>}` |
| `tissue_state` | token: `in_vivo`, `ex_vivo_fresh`, `frozen_thawed`, `fixed`, `phantom` |
| `disease_and_treatment_state` | token `normal`, `diseased` or `treated`, with a `text` saying which |
| `preparation` | `text` |
| `preservation` | token: `none`, `refrigerated`, `frozen`, `fixed_formalin`, `other` with `text` |
| `post_mortem_interval` | numeric, `s` |
| `donor_age` | numeric value or range, `s` |
| `shape` | token `sphere`, `cylinder`, `prolate_spheroid`, `oblate_spheroid`, `slab`, `film`, `irregular`, with `parameters` giving its dimensions in `m` |
| `mimics` | `text`: what a phantom or substitute was made to mimic, as its maker states it |

1. Every fact takes the shapes of section 6, the `unstated` status included, plus `not_applicable` where a
   fact cannot apply (the tissue state of a magnet). [RC-039]
2. Specimen facts may sit on a section and on a field; the field's fact overrides the section's, fact by fact
   (`record_format.md` section 4).
3. `mimics` is a fact about a phantom's design. It never makes the phantom stand in for anything; a consumer
   accepts stand-ins in its declarations, and the comparison with its target is in `declarations.md`.

## 7. Tiers and fill-ins

1. A record never states its tier. A checker computes it from the source registry: a value whose source's
   redistribution status is `permitted` or `values_only` is shipped (a `values_only` source's quotes ship as
   `quote_sha256`); one whose status is `not_permitted` or `unknown` is reference-only; private values never
   enter a published release. A value drafted with assistance stays reference-only until a person has set
   its review status and its source's redistribution status. [RC-040]
2. In a reference-only value the form's member is `{"status": "withheld"}`, and `provenance.recipe` gives the
   locator and the steps to extract the value from one's own copy. No quote and no check point ships with it.
   [RC-041]
3. A reader refuses a withheld value, with the reason that it must be filled in from the user's own copy.
   [PR-105]
4. A filled-in value carries `provenance.fill_in`: an `evidence` object naming the `document` (identifier and
   version) and the `copy` of the user's copy, and a `review` that is `{"status": "not_checked"}` until
   someone checks it. That `copy` and that `review` are excluded from the content hash like any other
   (`record_format.md` section 9), so two users who type the same numbers from the same document version get
   the same hash. [PR-106]
5. Where `fill_in.evidence.document` differs from `source.document` in identifier or version, every read of
   the value gives `unknown`, and a check of it is reported as "fill-in consistent with the user's copy" at
   most. [PR-107]

## 8. The source registry

The library repository holds one registry entry per source; a value's `source.key` names one. [RC-042]

| Member | Contents |
|---|---|
| `key`, `citation` | a citation key and its BibTeX |
| `identifier` | a DOI or URL |
| `publication_licence`, `dataset_licence` | as stated by the publisher |
| `redistribution` | `status` (`permitted`, `values_only`, `not_permitted`, `unknown`), `reason`, `judged_by`, `date`. Only a person sets it; it stays `unknown` until then |
| `role` | why the source is in the library |
| `copies` | per copy a curator holds: its retrieval route, its document version, the licence it came under, its SHA-256, and whether it is stamped with personal data |

A model never sets a redistribution status or a review status (AD 8.2). [not yet covered]

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-100 | plain read | a status is returned as a status, never as a value or a pass |
| PR-101 | plain read | an `import` lead is never reported as the source |
| PR-102 | plain read | a derived value returns the specimen facts of all its inputs and its mixed-conditions flag |
| PR-103 | plain read | an unknown condition name gives `unknown`; an unknown condition token refuses the field |
| PR-104 | plain read | a check against an unstated condition gives `unknown`, carrying the value |
| PR-105 | plain read | a withheld value is refused with its reason |
| PR-106 | plain read | a filled-in value is read, labelled user-extracted and unreviewed; its hash ignores copy and review |
| PR-107 | plain read | a fill-in from another document version gives `unknown` |
| RC-020 | record checks | an empty member, `null` or missing member in place of a status is flagged |
| RC-021 | record checks | `per_parameter` names only parameters of its set |
| RC-022 | record checks | a locator without the document's identifier and version is flagged |
| RC-023 | record checks | a table locator without its column header and index is flagged |
| RC-024 | record checks | an unknown origin token is flagged |
| RC-025 | record checks | a source supported only by an `import` lead is flagged |
| RC-026 | record checks | an assisted value with review status `not_checked` is not shipped |
| RC-027 | record checks | a converted value without `source_unit` and `conversion` is flagged |
| RC-028 | record checks | attenuation without its amplitude-or-intensity fact is flagged |
| RC-029 | record checks | a digitised figure without calibration or digitising error is flagged |
| RC-030 | record checks | a curated value from text or a table without a quote is flagged |
| RC-031 | record checks | evidence without the document's identity and version beside the copy's hash is flagged |
| RC-032 | record checks | a quote absent at its locator, or not containing the value's numbers, fails; with no copy, `not_checked` |
| RC-033 | record checks | `quote_sha256` is computed on the normalised quote and verifies |
| RC-034 | record checks | a stamped copy, or anything taken from it, in a release is flagged |
| RC-035 | record checks | a derivation without its method, inputs with hashes, and assumptions is flagged |
| RC-036 | record checks | a derivation from inputs at different conditions without the flag is flagged |
| RC-037 | record checks | a condition or fact without a basis, or `inferred` without `inferred_from`, is flagged |
| RC-038 | record checks | a table or power-law axis that is not a condition name, or with another unit, is flagged |
| RC-039 | record checks | malformed ontology identifiers and unknown fact names are flagged |
| RC-040 | record checks | the computed tier matches what a release ships |
| RC-041 | record checks | a reference-only value that ships its value, quote or check points is flagged |
| RC-042 | record checks | a `source.key` missing from the registry is flagged |

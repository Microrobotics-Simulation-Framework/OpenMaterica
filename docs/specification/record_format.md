# Record format

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 4.1 to 4.4, 5.2, 5.5
and 5.6. What a reader does with a record, in order, and every reason it returns: `read_side_contract.md`.

## 1. Records and validity

1. A record is one JSON object in one file. Records are JSON only; no other serialisation is a record.
   [PR-001]
2. Each schema version has two JSON Schemas, published with the specification in `schema/` (README):
   - the **writer schema** is closed: no member it does not define, and every enumerated member limited to its
     listed tokens. A record check validates against it. [RC-003]
   - the **reader schema** is open: it checks the structure a reader relies on (the envelope's members and
     their JSON types, the shape of each value form) and allows members it does not define and any string in
     an enumerated member. A reader validates against the reader schema of the version it knows. [PR-002]
3. A record is **malformed** when it is not valid JSON, or its envelope is not valid against that reader
   schema. A reader never stops with an error on a malformed record: every read from it gives `not_met` with
   the reason `malformed`. A shape error inside one field (a table whose structure breaks section 6, a member
   of the wrong JSON type) refuses only that field, with the reason `form_invalid`; a token the reader does
   not know refuses only its field (section 10). [PR-002] [PR-033] [PR-045]
4. A field that is absent has no value. There are no default or fallback values anywhere in a record, and a
   writer MUST NOT write a placeholder in place of an unknown value. [PR-003] [RC-001]
5. `null` appears nowhere in a record. A member with no ordinary value holds a status object (README); an
   optional member with nothing to say is omitted. [RC-015]

## 2. The envelope

Every record, of every type, has these members. In schema 0.1.0 the envelope is **experimental**: its exact
members are settled with the first namespaced record type (AD 13). [PR-004]

| Member | Required | Contents |
|---|---|---|
| `schema_version` | yes | the schema version the record was written against (section 8) |
| `record_type` | yes | `material`, `interface` or `overlay` (section 3) |
| `id` | yes | `<namespace>/<local id>` (section 7) |
| `version` | yes | the record's own version (section 8) |
| `name` | yes | a human-readable name; informative only |
| `licence` | yes | `{"values": <SPDX licence expression>, "evidence": "excluded"}`: the licence of the values; quoted evidence text is never covered by it (AD 6.4) [RC-002] |
| `content_hash` | yes | `sha256:` and 64 lowercase hexadecimal digits (section 9) |
| `card` | no | prose for the record's card (AD 6.6); informative, excluded from the hash |
| `body` | yes | the type's body (sections 4 and 4.4) |

A writer MUST NOT add other top-level members (the writer schema refuses them). A reader ignores a top-level
member it does not know, and keeps it for hashing (section 9). [RC-003] [PR-005]

## 3. Record types

| `record_type` | Body | Stability in 0.1.0 |
|---|---|---|
| `material` | a substance: its sections (section 4) | experimental |
| `overlay` | a replacement of some fields of one material, applied only when a consumer declares it (section 4.4) | experimental |
| `interface` | a property of a pair (AD 4.13) | name reserved; body specified in a later minor version |

1. A reader that meets a record of a type it cannot read (an unknown type, a namespaced type, or `interface`
   in 0.1.0) MUST skip it when listing records, and MUST refuse it, with the reason `unknown_type`, when the
   record is referenced: by a binding, an overlay's base, a pin, a layered-path interval or an interface
   member. [PR-006] [PR-007]
2. Other namespaces may later define their own record types (`<namespace>:<type>`, AD 4.1). The first is
   specified only after a consumer has prototyped one, so a 0.1.0 writer MUST NOT write a record of a
   namespaced type. [RC-004]

## 4. The material body

```json
{
  "sections": {
    "bulk":  {"specimen": {}, "fields": {"density": {}, "elemental_composition": {}}},
    "fluid": {"specimen": {}, "fields": {"dynamic_viscosity": {}}}
  },
  "extensions": {"acme": {"sections": {}}}
}
```

1. `sections` maps a section name to a section. Every section is optional. A reader ignores a section it does
   not use, and reads the sections it knows from a record that also holds sections it does not know. [PR-008]
2. A section holds `fields`, a map from a field name to a value field (section 5), and optionally `specimen`,
   the specimen facts shared by its fields (`provenance.md`). A field's own `specimen` overrides the
   section's, fact by fact. [PR-009]
3. A section's presence says what is known about a material. It never says where that physics applies; a
   consumer declares that (`declarations.md`).
4. `extensions` maps a registered namespace to sections in that namespace, using the same value fields. Their
   meaning belongs to that namespace. A reader ignores `extensions`, and no requirement can name a field in
   it. Records in the curated library carry none. [PR-034] [RC-005]

### 4.1 Sections and fields of schema 0.1.0

Each field registers one unit, the value forms it may take, and the conditions it requires. A required
condition MUST be present, holding `{"status": "unstated"}` if the source does not state it, or `{"status":
"not_applicable"}` if it is the form's own axis (`read_side_contract.md` section 5). [RC-006] Every field is
**experimental** in 0.1.0 (README "Versions").

| Section.field | Unit | Forms | Requires | Label |
|---|---|---|---|---|
| `bulk.density` | `kg/m3` | constant, table, interval | `temperature`, `density_kind` | none |
| `bulk.elemental_composition` | `1` | composition (basis `mass_fraction`) | none | none |
| `fluid.dynamic_viscosity` | `Pa.s` | constant, table, interval | `temperature`, `shear_rate` | `vesalius.fluid.newtonian.v1` on a constant, or on a table whose axis is not `shear_rate` |
| `magnetic.remanence` | `T` | constant, interval | `temperature`, `specimen_shape` | none |
| `magnetic.saturation_magnetisation` | `A/m` | constant, interval | `temperature`, `specimen_shape` | none |
| `magnetic.volume_susceptibility` | `1` | constant, table, interval | `temperature`, `specimen_shape`, `magnetic_flux_density` | `vesalius.magnetic.linear.v1` on a constant, or on a table whose axis is not `magnetic_flux_density` |
| `biocompatibility.evidence` | `{"status": "not_applicable"}` | evidence (section 4.3) | none | none |

- `density_kind` is `apparent` (the whole specimen, pores included) or `matrix` (the solid phase only).
  [PR-315]
- Every unit registered here, for a field or a condition, is a valid UCUM 2.2 expression in which no special
  unit (the neper, the bel, the degree Celsius) is part of a product or quotient; the registry's tests check
  each with a UCUM validator. [RC-120]
- `magnetic.volume_susceptibility` is the SI volume susceptibility. A CGS value is 4π times smaller and is
  converted on the write side. [not yet covered]
- `specimen_shape` and `specimen_size` are conditions, not specimen facts: they change what a value means (a
  sphere's demagnetisation, AD 4.8), so a consumer matches them by requirement (`provenance.md` section 6).
  [PR-315]
- **Labels.** A label names the trivial model a single value implies (AD 4.4). `vesalius.fluid.newtonian.v1`:
  the viscosity does not depend on shear rate over the stated `shear_rate` condition.
  `vesalius.magnetic.linear.v1`: the magnetisation is proportional to the field over the stated
  `magnetic_flux_density` condition, with no saturation. A label is not a family: `model_families.md`'s
  refusal of an unknown family does not apply to it, and a reader returns it with the value. A consumer may
  require a label (`declarations.md`). [PR-035]
- A field whose form is not one its row allows is refused with the reason `form_not_registered`. [PR-036]
- Reserved section names, specified in later minor versions: `acoustic`, `radiological`, `mechanical`,
  `optical`, `thermal`, `dielectric`. Reserved because the USD binding uses them as attribute namespaces:
  `region`, `scene`, `domain`, `overlay`, `path`, `inputSheet` (`usd_binding.md`). Reserved field names in
  every section: `specimen`.

### 4.2 Units

A value field's `unit` MUST equal its field's registered unit. A reader refuses a field whose unit differs,
with the reason `unit_mismatch`; it never converts. The same holds for a table's `axis_unit` and a condition's
`unit`, against the condition's registered unit (`provenance.md` section 6). [PR-010] [PR-037] The source's
own unit, and any conversion, are extraction facts (`provenance.md`).

### 4.3 Biocompatibility evidence

`biocompatibility.evidence` is a value field of form `evidence`: `"unit": {"status": "not_applicable"}`,
`"conditions": {}`, and `"evidence": [...]`, a list of test reports for the material, never a status. Each
entry holds `endpoint`, `standard` (`{"designation": "ISO 10993-5", "year": 2009}`), `contact_category`,
`contact_duration`, `material_form`, `processing`, `reported_result` (the source's words, verbatim) and
`provenance`. A device's biocompatibility is declared on the device by its maker and is never derived from
these entries (AD 4.2). No member of an entry states a conclusion about safety. [PR-038] [RC-007] The token
lists of `contact_category`, `contact_duration` and `material_form` will follow ISO 10993-1's categories
(recalled); until they are listed, these members hold the source's words. [not yet covered]

### 4.4 The overlay body

```json
{
  "purpose": "fit",
  "base": {"id": "vesalius/VES-MAT-0002", "version": "1.0.0", "content_hash": "sha256:..."},
  "scope": {"consumer": "mime", "model": {"name": "stokes_drag", "version": "0.3.0"},
            "model_configuration_hash": "sha256:...", "run": "run-2026-10-12-01"},
  "replaces": {"fluid.dynamic_viscosity": {}}
}
```

1. `purpose` is `fit` (a consumer's fitted value), `fill_in` (a user's own copy of a withheld value),
   `measurement` (an organisation's own measurement) or `scene_override`. [not yet covered]
2. `base` names one material by identifier, version and content hash. `replaces` maps `<section>.<field>` to a
   whole value field, with its own `specimen` (it never inherits the base section's), which replaces the
   base's field entirely, provenance included. `replaces` names only fields the base holds; a reader refuses
   an overlay that replaces a field its base lacks, with the reason `absent`. [PR-011] [RC-016] [PR-046]
3. `scope` names the consumer, the model (name and version) and a hash of the model's configuration with every
   value read from records removed (for MIME, the graph's configuration minus the parameters its material
   input sheet derives from records), and optionally the run. A `measurement` overlay's scope names the
   consumer only; a `fill_in` overlay's names `user` and no model. The build compares the scope
   (`declarations.md` section 5). [not yet covered]
4. A reader applies an overlay only when a declaration names it (`declarations.md`). [PR-012]
5. A reader refuses an overlay whose base differs from the record in use, with the reason
   `overlay_base_mismatch`; no declaration accepts it. [PR-039]
6. Two declared overlays that replace the same field of the same base are refused, with the reason
   `overlay_conflict`. [PR-041]
7. **Fill-ins.** A user fills in a reference-only value with an overlay of purpose `fill_in`, in the user's
   own namespace, whose base is the reference-only record. The curated record never changes, so every user and
   every scene that pins it holds the same record. The fill-in overlay states the user's licence for the
   values (for a source that does not permit redistribution, `LicenseRef-user-extracted`), the evidence from
   the user's copy, and the user's review (`provenance.md` section 7). A reader labels every value it reads
   through a fill-in `user_extracted`. [PR-042]

## 5. Value fields

A value field is an object with these members, or an `alternatives` object (below).

| Member | Required | Contents |
|---|---|---|
| `form` | yes | one of `constant`, `table`, `power_law`, `interval`, `composition`, `parameter_set`, `reference_data`, `evidence` [PR-043] |
| `unit` | yes | the field's registered unit |
| the form's member | yes | `value` for a constant; otherwise the member named like the form (`table`, `power_law`, `interval`, `composition`, `parameter_set`, `reference_data`, `evidence`). In a reference-only value it holds `{"status": "withheld"}` (`provenance.md` section 7) |
| `conditions` | yes | the conditions the value was measured at (`provenance.md`) |
| `specimen` | no | specimen facts, overriding the section's |
| `statistics` | yes, except for `evidence` | the statistics block (`uncertainty.md`). For a table or a power law it applies to every value the form gives, unless table entries carry their own. In a reference-only value it holds `{"status": "withheld"}` |
| `provenance` | yes | origin, source, extraction, evidence, review (`provenance.md`) |
| `label` | where the field's row names one | the field's label (section 4.1) |
| `fit` | where `provenance.origin` is `fitted` | the fit record (`fits_and_reference_data.md` section 2) |

**Alternatives.** Where sources disagree, or one source gives values at several conditions, the field is
`{"alternatives": [<value field>, ...]}`: every alternative found, each complete, none marked as the default.
Writers MUST NOT reorder or drop alternatives once a record is released; a new alternative is appended.
[RC-017] A reader first sets aside every alternative whose conditions give `not_met`. If more than one
remains, it gives `unknown` with the reason `no_pick`, carrying every remaining value in stored order, unless
the consumer declared a pick, which names one alternative by its index among the stored alternatives
(`declarations.md`). If every alternative is set aside, the result is `not_met` with the reasons of each. A
waiver never accepts a `no_pick`; only a pick does. [PR-013] [PR-044]

## 6. The value forms

Every form carries the range it covers: a constant through its conditions, a table through its abscissae, a
power law through its `range`, a parameter set through its coverage. How a read is checked against that range,
and against a declared extrapolation, is in `read_side_contract.md` section 5. [PR-014]

**Constant.** `"value": <number>`. [PR-015]

**Table.**

```json
"table": {"axis": "temperature", "axis_unit": "K",
          "x": [293.15, 298.15, 303.15], "y": [0.001002, 0.000890, 0.000797],
          "scheme": "linear", "edges": [], "source_range": [273.15, 373.15]}
```

1. `axis` is a condition name and `axis_unit` its registered unit. `x` holds at least two distinct values and
   is non-decreasing. `edges` is a list of numbers; each edge appears in `x` exactly twice, consecutively, the
   two entries giving the values below and above it, and no other x value repeats. [RC-008] [RC-018]
2. `scheme` is `linear` or `loglog`. A `loglog` table holds only positive `x` and `y`. [RC-019] [PR-016] A
   reader refuses a table that breaks item 1 or item 2, with the reason `form_invalid`. [PR-045]
3. The table is read between `x[0]` and `x[-1]`, inclusive. A read exactly at an edge is refused (the value is
   two-sided); otherwise the interval used is the one whose two knots bracket the read, strictly where an edge
   is concerned, so a read just below an edge uses the knot below it. [PR-017] [PR-018]
4. `source_range`, where present, is the range the source says the values hold over. It never extends the
   readable range. [PR-019]
5. A table MAY carry `points`: a list as long as `x`, each entry holding that knot's own `provenance` and
   optionally `statistics`, where entries came from different places in a source. [not yet covered]

**Power law.**

```json
"power_law": {"a": 5.6e-6, "b": 1.1, "axis": "frequency", "axis_unit": "Hz",
              "range": [1.0e6, 5.0e6], "exponent_basis": "fitted"}
```

1. The value is `a * x^b`, in the field's unit, for `x` in `axis_unit`. [PR-020]
2. `range` is the band the source states, or `{"status": "unstated"}`, in which case every read gives
   `unknown` with the reason `range_unstated`, which only a declared extrapolation accepts
   (`declarations.md`). [PR-021] (planned with the acoustic section)
3. `exponent_basis` is `fitted`, `assumed` or `theoretical`. [not yet covered]
4. Attenuation, in any section, is stored as an amplitude coefficient in nepers per metre, registered as `/m`,
   with `x` in hertz. The neper is dimensionless, and UCUM does not allow a special unit in a quotient, so
   `Np/m` is not a valid UCUM expression (UCUM 2.2, sections 22 and 46). Decibels, nepers, per-centimetre and
   per-megahertz units and intensity coefficients are converted on the write side and recorded as extraction
   facts. No 0.1.0 field takes a power law; the first arrives with the acoustic
   section, and its cases with it. [not yet covered]

**Interval.**

```json
"interval": {"lower": 0.4, "upper": {"status": "none"}, "basis": "stated_bound"}
```

1. `lower` and `upper` are numbers, and at most one holds `{"status": "none"}` (a one-sided interval).
   [RC-010]
2. `basis` is `reported_range`, `proxy_range` (a range taken from other tissues), `specification_limits` (a
   datasheet's limits: a promise about a product, not a measured spread) or `stated_bound`. [RC-009]
3. A reader returns the bounds. A nominal value or a sample is the consumer's declaration
   (`declarations.md`). [PR-022]

**Composition.**

```json
"composition": {"basis": "mass_fraction", "sum_rule": "partial",
                "components": [{"component": "element:H", "fraction": 0.102},
                               {"component": "element:O", "fraction": 0.723}]}
```

1. `basis` is `mass_fraction`, `volume_fraction` or `mole_fraction`. `component` is `element:<symbol>`, the
   symbol as IUPAC writes it. Named components (water, lipid, haemoglobin) come with the optical section.
   [RC-011]
2. `sum_rule` is `sums_to_one` or `partial` (the source lists only some components). Where the source's own
   fractions do not sum to one, `stated_sum` records the sum the source gives, and nothing is normalised. A
   checker flags a `sums_to_one` composition whose fractions sum to more than 1e-6 away from one with no
   `stated_sum`. [RC-011]
3. A component MAY carry its own `statistics`. [not yet covered]
4. A reader returns the components as stored. [PR-023]

**Model parameter set.** `"parameter_set": {...}`, specified in `model_families.md`. A reader that does not
claim the family evaluation profile refuses it, with the reason `family_profile_absent`. [PR-024]

**Reference data.** `"reference_data": {...}`, specified in `fits_and_reference_data.md`. A reader never
returns reference data as a property's value; it is read only by a request for reference data (FD profile).
[PR-025]

**Evidence.** Section 4.3.

## 7. Identifiers

Every pattern below is anchored at both ends.

1. A namespace matches `[a-z0-9_]+`. Namespaces are registered first come first served in the library's
   `publishers.yaml`, whose format is outside this specification; an unregistered namespace is not unique, so
   a consumer pins records by content hash, not by identifier alone. `vesalius` and `mime` are reserved.
   [RC-012]
2. A record identifier is `<namespace>/<local id>`, the local id matching `[A-Za-z0-9_.-]+`. In `vesalius`,
   local ids are `VES-MAT-NNNN` for materials and `VES-INT-NNNN` for interfaces. [RC-013]
3. A family identifier is `<namespace>.<segment>(.<segment>)*.v<N>`, each segment matching `[a-z0-9_]+` and
   `N` a positive integer without leading zeros. [not yet covered]

## 8. Versions

1. `schema_version` and a record's `version` are `MAJOR.MINOR.PATCH`, each a non-negative integer without
   leading zeros, with no pre-release or build part. [RC-014]
2. **Before 1.0.0**, a reader reads only records of its own `MAJOR.MINOR` and refuses every other, with the
   reason `other_version`. From 1.0.0, a reader of `M.m` reads a record of `M.n` for any `n` by the rules of
   section 10, and refuses another major version. [PR-026] [PR-027]
3. A record's `version` changes **major** when a value changes by more than the uncertainty its record states
   for that value (a population's spread is not that measure; where the record states none, any change of
   value), a condition changes, or a parameter set moves to another family version; **minor** for a new value
   or section; **patch** for provenance wording (`DOCUMENTATION_ARCHITECTURE.md` section 7.1). [not yet
   covered]

## 9. The content hash

1. `content_hash` is computed over the record as stored, every member a reader does not know included, with
   these removed: the top-level `content_hash` and `card`; and every member named `review` or `copy` at any
   depth inside any object that is the value of a member named `provenance`. [HS-001]
2. The remaining JSON is serialised by the JSON Canonicalization Scheme, RFC 8785 (recalled), and hashed with
   SHA-256. `content_hash` is `sha256:` followed by the 64 lowercase hexadecimal digits of the digest.
   [HS-002]
3. So a second review, or a reworded card, does not change a record's hash, and changing anything else, its
   type and licence included, does.
4. The conformance suite has hash test vectors, including numbers whose canonical form differs from their
   written form, and a record holding members the reader does not know. [HS-003]
5. When and against what a reader checks the hash: `read_side_contract.md` section 3.

## 10. Reading a record of a newer minor version (from 1.0.0)

A reader of `M.m` reading a record of `M.n`, `n > m`:

1. ignores an object member it does not know, except as items 2 to 4 say; [PR-030]
2. gives `unknown` for a condition name it does not know, never "present and unchecked"; [PR-031]
3. refuses a field holding a token it does not know in an enumerated member (a form, a scheme, a basis, a
   structure, a status), with the reason `unknown_token`, never reading it as a token it knows; [PR-032]
4. skips a section it does not know (section 4), and skips or refuses a record type it does not know (section
   3). [PR-006] [PR-007] [PR-008]

The same rules apply before 1.0.0 to a token, condition or member a reader does not know within its own minor
version. [PR-032]

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-001 | plain read | a record in another serialisation is not read as a record |
| PR-002 | plain read | invalid JSON and an envelope invalid against the reader schema give `malformed` for every read, never a crash |
| PR-003 | plain read | an absent field has no value |
| PR-004 | plain read | every record type carries the envelope |
| PR-005 | plain read | an unknown top-level member is ignored |
| PR-006 | plain read | an unknown record type is skipped when listing |
| PR-007 | plain read | a referenced record of an unknown type is refused (`unknown_type`) |
| PR-008 | plain read | a record with an unknown section is read for the sections the reader knows |
| PR-009 | plain read | a field's specimen fact overrides its section's |
| PR-010 | plain read | a field whose unit differs from the registered one is refused (`unit_mismatch`) |
| PR-011 | plain read | an overlay replaces a whole field, provenance included, with its own specimen |
| PR-012 | plain read | an undeclared overlay is not applied |
| PR-013 | plain read | alternatives with no pick give `unknown` (`no_pick`) with every value; a waiver does not accept it |
| PR-014 | plain read | every form carries its range |
| PR-015 | plain read | a constant is returned with its conditions |
| PR-016 | plain read | linear and log-log tables interpolate by their scheme |
| PR-017 | plain read | outside the tabulated range is refused (`outside_range`) |
| PR-018 | plain read | exactly at an edge is refused; just below and just above an edge read the correct side |
| PR-019 | plain read | `source_range` does not extend the readable range |
| PR-020 | plain read | a power law evaluates in the field's unit (planned with the acoustic section) |
| PR-021 | plain read | a power law with an unstated range gives `unknown` (`range_unstated`) |
| PR-022 | plain read | an interval returns its bounds, a one-sided one included |
| PR-023 | plain read | a composition is returned as stored, never normalised |
| PR-024 | plain read | a parameter set is refused by a reader without family evaluation |
| PR-025 | plain read | reference data is never returned as a property |
| PR-026 | plain read | before 1.0.0, a record of another minor version is refused (`other_version`) |
| PR-027 | plain read | a record of another major version is refused (`other_version`) |
| PR-030 | plain read | an unknown member inside a field is ignored |
| PR-031 | plain read | an unknown condition name gives `unknown` |
| PR-032 | plain read | an unknown token in an enumerated member refuses the field only (`unknown_token`) |
| PR-033 | plain read | a record with one unknown token is not malformed; its other fields are read |
| PR-034 | plain read | `extensions` is ignored |
| PR-035 | plain read | a label is returned with the value and never refused as an unknown family |
| PR-036 | plain read | a form the field's row does not allow is refused (`form_not_registered`) |
| PR-037 | plain read | an `axis_unit` or condition unit other than the registered one is refused (`unit_mismatch`) |
| PR-038 | plain read | biocompatibility evidence is returned as a list of reports |
| PR-039 | plain read | an overlay whose base differs from the record in use is refused (`overlay_base_mismatch`) |
| PR-041 | plain read | two declared overlays replacing one field are refused (`overlay_conflict`) |
| PR-042 | plain read | a value read through a fill-in overlay is labelled `user_extracted` |
| PR-043 | plain read | the form tokens are exactly the eight listed |
| PR-044 | plain read | alternatives whose conditions are not met are set aside; all set aside gives `not_met` |
| PR-045 | plain read | a shape error inside one field refuses that field (`form_invalid`); the other fields are read |
| PR-046 | plain read | an overlay replacing a field its base lacks is refused (`absent`) |
| HS-001 | hash | the hash excludes exactly the listed members, at any depth |
| HS-002 | hash | the content hash verifies (RFC 8785, SHA-256, lowercase hexadecimal) |
| HS-003 | hash | hash vectors: numbers whose canonical form differs; members the reader does not know are hashed |
| RC-001 | record checks | a placeholder written for an unknown value is flagged |
| RC-002 | record checks | the licence member names the values' licence and excludes evidence |
| RC-003 | record checks | a record invalid against the closed writer schema is flagged |
| RC-004 | record checks | a 0.1.0 record of a namespaced type is flagged |
| RC-005 | record checks | a curated record carrying extensions is flagged |
| RC-006 | record checks | a field missing a required condition is flagged |
| RC-007 | record checks | a biocompatibility entry member stating a conclusion about safety is flagged |
| RC-008 | record checks | a repeated x value that is not a declared edge, or an edge not repeated, is flagged |
| RC-009 | record checks | an interval basis outside the four tokens is flagged |
| RC-010 | record checks | an interval with neither bound, or with both `none`, is flagged |
| RC-011 | record checks | a malformed component, or a composition that does not sum to one with no stated sum, is flagged |
| RC-012 | record checks | a namespace outside `[a-z0-9_]+` is flagged |
| RC-013 | record checks | a malformed record identifier is flagged |
| RC-014 | record checks | a malformed version is flagged |
| RC-015 | record checks | `null` anywhere in a record is flagged |
| RC-016 | record checks | an overlay that replaces a field its base lacks, or whose field has no specimen, is flagged |
| RC-017 | record checks | a released record whose alternatives were reordered or dropped is flagged |
| RC-018 | record checks | a table with fewer than two distinct x values is flagged |
| RC-019 | record checks | a log-log table with a non-positive x or y is flagged |
| RC-120 | record checks | every registered unit passes a UCUM validator; `Np/m` fails |

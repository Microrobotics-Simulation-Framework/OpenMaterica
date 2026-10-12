# Record format

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 4.1 to 4.4, 5.2 and
5.6.

## 1. Records

1. A record is one JSON object, in one file, valid against the record JSON Schema of its schema version.
   Records are JSON only; no other serialisation is a record. [PR-001]
2. A reader MUST NOT stop with an error on a malformed record (invalid JSON, or invalid against the schema).
   It refuses every read from that record, with the reason. [PR-002]
3. A field that is absent has no value. There are no default or fallback values anywhere in a record, and a
   writer MUST NOT write a placeholder in place of an unknown value. [PR-003] [RC-001]

## 2. The envelope

Every record, of every type, has these members. [PR-004]

| Member | Required | Contents |
|---|---|---|
| `schema_version` | yes | the schema version the record was written against, `MAJOR.MINOR.PATCH` |
| `record_type` | yes | `material`, `interface`, `overlay`, or a namespaced type `<namespace>:<type>` (section 3) |
| `id` | yes | `<namespace>/<local id>` (section 7) |
| `version` | yes | the record's own version, `MAJOR.MINOR.PATCH` (section 8) |
| `name` | yes | a human-readable name; informative only |
| `licence` | yes | `{"values": <SPDX identifier>, "evidence": "excluded"}`: the licence of the values; quoted evidence text is never covered by it (AD 6.4) [RC-002] |
| `content_hash` | yes | `sha256:` and 64 lowercase hexadecimal digits (section 9) |
| `card` | no | prose for the record's card (AD 6.6); informative, excluded from the hash |
| `body` | yes | the type's body (sections 3 to 5) |

A writer MUST NOT add other top-level members. A reader MUST ignore a top-level member it does not know
(section 10). [RC-003] [PR-005]

## 3. Record types

| `record_type` | Body | Status in 0.1.0 |
|---|---|---|
| `material` | a substance: its sections (section 4) | specified |
| `overlay` | a replacement of some fields of a material, applied only when a consumer declares it (section 4.4) | specified |
| `interface` | a property of a pair (AD 4.13) | name reserved; body specified in a later minor version |
| `<namespace>:<type>` | defined by that namespace | allowed; the first one is specified only after a consumer has prototyped one (AD 4.1) |

1. A reader that meets a record of a type it cannot read (an unknown type, a namespaced type, or `interface`
   in 0.1.0) MUST skip it when listing records, and MUST refuse it when the record is referenced: by a
   binding, an overlay's base, a pin, a layered-path interval or an interface member. [PR-006] [PR-007]
2. For a namespaced type, a checker validates the envelope only. It never reports the body as checked.
   [RC-004]

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

1. `sections` maps a section name to a section. Every section is optional. A reader MUST ignore a section it
   does not use, and MUST read the sections it knows from a record that also holds sections it does not know.
   [PR-008]
2. A section holds `fields`, a map from a field name to a value field (section 5), and optionally `specimen`,
   the specimen facts shared by its fields (`provenance.md`). A field's own `specimen` overrides the
   section's, fact by fact. [PR-009]
3. A section's presence says what is known about a material. It never says where that physics applies; a
   consumer declares that (`declarations.md`).
4. `extensions` maps a registered namespace to sections in that namespace, using the same value fields. Their
   meaning belongs to that namespace. Records in the curated library carry none. [RC-005]

### 4.1 Sections and fields of schema 0.1.0

Each field registers one unit, the value forms it may take, and the conditions or specimen facts it requires.
A required condition MUST be present, even if its status is "unstated" (`provenance.md`). [RC-006]

| Section.field | Unit | Forms | Requires |
|---|---|---|---|
| `bulk.density` | `kg/m3` | constant, table, interval | conditions `temperature`, `density_kind` (`apparent`: the whole specimen, pores included; `matrix`: the solid phase only) |
| `bulk.elemental_composition` | `1` | composition (basis `mass_fraction`) | none |
| `fluid.dynamic_viscosity` | `Pa.s` | constant, table, interval | conditions `temperature`, `shear_rate`; `family_label` (section 5) |
| `magnetic.remanence` | `T` | constant, interval | condition `temperature`; specimen fact `shape` |
| `magnetic.saturation_magnetisation` | `A/m` | constant, interval | condition `temperature`; specimen fact `shape` |
| `magnetic.volume_susceptibility` | `1` | constant, table, interval | condition `temperature`; specimen fact `shape`; `family_label` |
| `biocompatibility.evidence` | none | a list of test evidence (section 4.3) | none |

Reserved section names, specified in later minor versions: `acoustic`, `radiological`, `mechanical`,
`optical`, `thermal`, `dielectric`.

### 4.2 Units

A value field's `unit` MUST equal its field's registered unit. A reader refuses a field whose unit differs
[PR-010]; it never converts. The source's own unit, and any conversion, are extraction facts
(`provenance.md`).

### 4.3 Biocompatibility evidence

`biocompatibility.evidence` is a list of test reports for the material, never a status. Each entry holds
`endpoint`, `standard` (with its part and year), `contact_category`, `contact_duration`, `material_form`,
`processing`, `reported_result` (the source's words) and `provenance`. A device's biocompatibility is declared
on the device by its maker and is never derived from these entries (AD 4.2). A checker refuses an entry that
states a safety conclusion of its own. [RC-007]

### 4.4 The overlay body

```json
{
  "base": {"id": "vesalius/VES-MAT-0002", "content_hash": "sha256:..."},
  "scope": {"consumer": "mime", "model_configuration_hash": "sha256:...", "run": "..."},
  "replaces": {"fluid.dynamic_viscosity": {}}
}
```

1. `base` names one material by identifier and content hash. `replaces` maps `<section>.<field>` to a whole
   value field, which replaces the base's field entirely, provenance included, never member by member.
   [PR-011]
2. `scope` states what the overlay belongs to: the consumer, a hash of the consumer's whole model
   configuration, and optionally the run. Its use is a declaration (`declarations.md`).
3. A reader MUST NOT apply an overlay that no declaration names. [PR-012]

## 5. Value fields

A value field is an object with these members, or an `alternatives` object (below).

| Member | Required | Contents |
|---|---|---|
| `form` | yes | one of the seven forms (section 6) |
| `unit` | yes | the field's registered unit |
| the form's member | yes | named after the form: `value` for a constant, `table`, `power_law`, `interval`, `composition`, `parameter_set` or `reference_data`; in a reference-only value, `{"status": "withheld"}` instead (`provenance.md` section 7) |
| `conditions` | yes | the conditions the value was measured at (`provenance.md`) |
| `specimen` | no | specimen facts, overriding the section's |
| `statistics` | for a constant | the statistics block (`uncertainty.md`) |
| `provenance` | yes | origin, source, extraction, evidence, review (`provenance.md`) |
| `family_label` | where the field requires it | the trivial family a single value implies, such as `vesalius.fluid.newtonian.v1` for one viscosity (AD 4.4). It is a label: such a constant is a scalar for the witness and statistics rules, not a parameter set |

**Competing values.** Where sources disagree, the field is `{"alternatives": [<value field>, ...]}`: every
alternative found, each complete, none marked as the default. A reader MUST NOT return any of them unless the
consumer has declared its pick; without one the result is `unknown`. [PR-013] A writer MUST NOT drop an
alternative it found. [not yet covered]

## 6. The seven value forms

Every form carries the range it covers: a constant through its conditions, a table through its abscissae, a
power law through its `range`, a parameter set through its coverage. A reader refuses outside that range
unless the consumer declared an extrapolation (`declarations.md`). [PR-014]

**Constant.** `"value": <number>`. Read at the conditions it was measured at. [PR-015]

**Sampled table.**

```json
"table": {"axis": "temperature", "axis_unit": "K",
          "x": [293.15, 298.15, 303.15], "y": [0.001002, 0.000890, 0.000797],
          "scheme": "linear", "edges": [], "source_range": [273.15, 373.15]}
```

1. `axis` is a condition name and `axis_unit` its unit. `x` is non-decreasing. An x value may repeat only at
   a declared edge, where the two entries give the values below and above it. [RC-008]
2. `scheme` is `linear` or `loglog`. A reader interpolates by the declared scheme only. [PR-016]
3. A reader refuses: outside `[x[0], x[-1]]`; exactly at an edge; between two knots that bracket an edge.
   [PR-017] [PR-018]
4. `source_range`, where present, is the range the source says the values hold over. It does not extend the
   readable range, which is the tabulated one. [PR-019]
5. A table may carry `points`: one provenance per entry, where entries came from different places in a source
   (`provenance.md`).

**Power law.**

```json
"power_law": {"a": 5.6e-6, "b": 1.1, "axis": "frequency", "axis_unit": "Hz",
              "range": [1.0e6, 5.0e6], "exponent_basis": "fitted"}
```

1. The value is `a * x^b`, in the field's unit, for `x` in `axis_unit`. [PR-020]
2. `range` is the band the source states, or `{"status": "unstated"}`, in which case every read is `unknown`.
   [PR-021]
3. `exponent_basis` is `fitted`, `assumed` or `theoretical`.
4. The power law's own axis is not checked again as a condition (covered in `read_side_contract.md`).
5. Attenuation, in any section, is stored as an amplitude coefficient, in `Np/m` at `x` in hertz. Decibels,
   per-centimetre and per-megahertz units, and intensity coefficients (twice the amplitude coefficient) are
   converted on the write side and recorded as extraction facts. [RC-009]

**Interval.**

```json
"interval": {"lower": 0.4, "upper": null, "basis": "stated_bound"}
```

1. At least one of `lower` and `upper` is a number; the other may be `null` (a one-sided interval).
   [RC-010]
2. `basis` is `reported_range`, `proxy_range` (a range taken from other tissues), `specification_limits` (a
   datasheet's limits: a promise about a product, not a measured spread) or `stated_bound`.
3. A reader returns the bounds. It refuses a nominal value for an interval, and refuses to sample one,
   unless the consumer declared a nominal or a distribution (`declarations.md`). [PR-022]

**Composition.**

```json
"composition": {"basis": "mass_fraction",
                "components": [{"component": "element:H", "fraction": 0.102},
                               {"component": "element:O", "fraction": 0.723}],
                "sum_rule": "sums_to_one", "stated_sum": null}
```

1. `basis` is `mass_fraction`, `volume_fraction` or `mole_fraction`. `component` is `element:<symbol>` with
   an IUPAC symbol; named components (water, lipid, haemoglobin) come with the optical section.
2. `sum_rule` is `sums_to_one` or `partial` (the source lists only some components). Where the source's own
   fractions do not sum to one, `stated_sum` records the sum the source gives, and nothing is normalised.
   A checker flags a `sums_to_one` composition whose fractions sum to more than 1e-6 away from one with no
   `stated_sum`. [RC-011]
3. A component may carry its own `statistics`.
4. A reader returns the components as stored. [PR-023]

**Model parameter set.** `"parameter_set": {"family": ..., "params": ..., "uncertainty": ..., "check_points":
..., "witness": ..., "coverage": ..., "fit": ...}`. Specified in `model_families.md`. A plain-read reader that
does not implement family evaluation refuses it. [PR-024]

**Reference data.** `"reference_data": {...}`, specified in `fits_and_reference_data.md`. A reader never
returns reference data as a property's value. [PR-025]

## 7. Identifiers

1. A namespace is `[a-z0-9_]+`. Namespaces are registered first come first served in the library's
   `publishers.yaml`; an unregistered namespace is not unique, so a consumer pins records by content hash,
   not by identifier alone. `vesalius` and `mime` are reserved. [RC-012]
2. A record identifier is `<namespace>/<local id>`, the local id matching `[A-Za-z0-9_.-]+`. In `vesalius`,
   local ids are `VES-MAT-NNNN` for materials and `VES-INT-NNNN` for interfaces. [RC-013]
3. A family identifier is `<namespace>.<path>.v<N>`. A namespaced record type is `<namespace>:<type>`.

## 8. Versions

1. `schema_version`: a reader that knows schema `M.m` reads a record of schema `M.n` for any `n`, reading what
   it knows and refusing exactly what it cannot interpret (section 10). It refuses every record of another
   major version. [PR-026] [PR-027]
2. A record's `version` changes **major** when a value changes by more than the uncertainty its record states
   for that value, a condition or specimen fact changes, or a parameter set moves to another family version;
   **minor** for a new value or section; **patch** for provenance wording (`DOCUMENTATION_ARCHITECTURE.md`
   section 7.1). [not yet covered]

## 9. The content hash

1. `content_hash` is computed over the record with these members removed: the top-level `content_hash` and
   `card`; and every member named `review` or `copy` at any depth inside a `provenance` object, including
   inside its `fill_in` (`provenance.md`). [RC-014]
2. The remaining JSON is serialised by the JSON Canonicalization Scheme, RFC 8785 (recalled), and hashed with
   SHA-256. `content_hash` is `sha256:` followed by the 64 lowercase hexadecimal digits of the digest.
   [PR-028]
3. So a second review, a reworded card, or a fill-in from another copy of the same document does not change a
   record's hash, and changing anything else, its type and licence included, does.
4. The conformance suite has hash test vectors, including numbers whose canonical form differs from their
   written form. [PR-029]

## 10. Forward compatibility

A reader reading a record of a newer minor schema version:

1. ignores an object member it does not know, except as items 2 to 4 say; [PR-030]
2. gives `unknown` for a condition name it does not know, never "present and unchecked" (`provenance.md`);
   [PR-031]
3. refuses a field holding a token it does not know in an enumerated member (a form, a scheme, a basis, a
   structure, a status), never reading it as a token it knows; [PR-032]
4. skips a section it does not know, and skips or refuses a record type it does not know (section 3). [PR-008]

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-001 | plain read | a record in another serialisation is not read as a record |
| PR-002 | plain read | malformed JSON and a schema-invalid record are refused, never a crash |
| PR-003 | plain read | an absent field has no value |
| PR-004 | plain read | every record type carries the envelope |
| PR-005 | plain read | an unknown top-level member is ignored |
| PR-006 | plain read | an unknown record type is skipped when listing |
| PR-007 | plain read | a referenced record of an unknown type is refused |
| PR-008 | plain read | a newer-minor record with an unknown section is read for the sections the reader knows |
| PR-009 | plain read | a field's specimen fact overrides its section's |
| PR-010 | plain read | a field whose unit differs from the registered one is refused |
| PR-011 | plain read | an overlay replaces a whole field, provenance included |
| PR-012 | plain read | an undeclared overlay is not applied |
| PR-013 | plain read | a field with alternatives and no pick gives `unknown` |
| PR-014 | plain read | a read outside a form's range is refused without a declared extrapolation |
| PR-015 | plain read | a constant is returned with its conditions |
| PR-016 | plain read | linear and log-log tables interpolate by their scheme |
| PR-017 | plain read | outside the tabulated range is refused |
| PR-018 | plain read | at an edge, and between knots bracketing one, is refused |
| PR-019 | plain read | `source_range` does not extend the readable range |
| PR-020 | plain read | a power law evaluates in the field's unit |
| PR-021 | plain read | a power law with an unstated range gives `unknown` |
| PR-022 | plain read | an interval returns bounds; a nominal is refused |
| PR-023 | plain read | a composition is returned as stored, never normalised |
| PR-024 | plain read | a parameter set is refused by a reader without family evaluation |
| PR-025 | plain read | reference data is never returned as a property |
| PR-026 | plain read | a newer-minor record is read |
| PR-027 | plain read | a record of another major version is refused |
| PR-028 | plain read | the content hash verifies |
| PR-029 | plain read | hash vectors, with numbers whose canonical form differs from their written form |
| PR-030 | plain read | an unknown member inside a field is ignored |
| PR-031 | plain read | an unknown condition gives `unknown` |
| PR-032 | plain read | an unknown token in an enumerated member refuses the field |
| RC-001 | record checks | a placeholder written for an unknown value is flagged |
| RC-002 | record checks | the licence member names the values' licence and excludes evidence |
| RC-003 | record checks | an extra top-level member is flagged |
| RC-004 | record checks | a namespaced type's body is reported as not checked |
| RC-005 | record checks | a curated record carrying extensions is flagged |
| RC-006 | record checks | a field missing a required condition or specimen fact is flagged |
| RC-007 | record checks | a biocompatibility entry stating a safety conclusion is flagged |
| RC-008 | record checks | a repeated x value that is not a declared edge is flagged |
| RC-009 | record checks | attenuation stored in decibels or as an intensity coefficient is flagged |
| RC-010 | record checks | an interval with neither bound is flagged |
| RC-011 | record checks | a composition that does not sum to one, with no stated sum, is flagged |
| RC-012 | record checks | a namespace outside `[a-z0-9_]+` is flagged |
| RC-013 | record checks | a malformed record identifier is flagged |
| RC-014 | record checks | the hash excludes exactly the listed members |

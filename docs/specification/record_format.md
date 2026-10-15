# Record format

Schema 0.1.0, draft. Conventions, suites and case numbers: `README.md`. Rationale: AD 4.1 to 4.4, 5.2, 5.5
and 5.6. What a reader does with a record, in order, and every reason it returns: `read_side_contract.md`.

## 1. Records and validity

1. A record is one JSON object in one file. Records are JSON only; no other serialisation is a record.
   [PR-001]
2. Each schema version has two JSON Schemas, in the dialect of JSON Schema 2020-12, published with the
   specification in `schema/` (README):
   - the **writer schema** is closed: no member it does not define, and every enumerated member limited to its
     listed tokens. A record check validates against it. [RC-003]
   - the **reader schema** is open. It checks the envelope: every member section 2 marks required is present
     and every member is of its JSON type; `id`, `version` and `content_hash` match their patterns (sections
     7, 8 and 9); `licence` is an object whose `values` and `evidence` (both required) are strings. It checks
     the body's structure as far as the reader's version knows it: in a material body, `sections` (required)
     and `extensions` are objects, and each member of `sections` named as a section of that version is an
     object whose `fields` (required) is an object; a section of another name, and everything inside
     `extensions`, is not checked (section 4 items 1 and 4); in an overlay body (section 4.4), whose four
     members are all required, `purpose` is a string, `base` an object whose `id`, `version` and
     `content_hash` (all required) are strings, `scope` an object whose `consumer` (required) is a string,
     whose `model`, where present, is an object with a string `name` and `version` (both required), and whose
     `model_configuration_hash` and `run`, where present, are strings, and `replaces` an object. It allows
     members it does not define and any string in an enumerated member. No subschema reachable from its root
     describes a value field (the members of a known section's `fields`, and of `replaces`), a form or a
     section's `specimen`, so a reader that validates a record against it never applies their shapes: they are
     checked when a field is read, and a field that is not an object is refused then (`read_side_contract.md`
     section 3, step 8). The reader schema MAY define those shapes for that use. Where a schema and this
     specification's text differ, the text holds. [PR-002] [PR-045]
3. A record is **malformed** when it is not valid JSON under item 6, when its `schema_version` is absent, is
   not a string, or does not match section 8's pattern, or when its envelope or body structure is not valid
   against the reader schema of the version the reader knows. A reader never stops with an error on a
   malformed record: a read whose reference may be that record gives `not_met` with the reason `malformed`
   (`read_side_contract.md` section 3, steps 1 to 3), unless an earlier step ends the read first (a record of
   another version gives `other_version` at step 2). [PR-002] [PR-048] A shape error inside one value field (a
   table whose structure breaks section 6, a member missing or of the wrong JSON type) refuses only that
   field, with the reason `form_invalid`; one in a section's `specimen` refuses, with the same reason, each
   field read from that section; a token the reader does not know refuses only its field (section 10).
   [PR-033] [PR-045] Which members of a value field a reader checks is `read_side_contract.md` section 3, step
   8's. [PR-109]
4. A field that is absent has no value. There are no default or fallback values anywhere in a record, and a
   writer MUST NOT write a placeholder in place of an unknown value. [PR-003] [RC-001]
5. `null` appears nowhere in a record. A member with no ordinary value holds a status object (README); an
   optional member with nothing to say is omitted. [RC-015] `null` is nevertheless valid JSON (item 6), so a
   reader that meets it reads it by where it is. Anywhere inside a member the reader does not know, wherever
   that member sits, it is ignored. Otherwise: in the envelope or the body's structure (item 2), where another
   type is required, the record is malformed; inside a value field, or a section's `specimen`, that a field
   the reader reads depends on, that field is refused (`form_invalid`) where `null` stands in a member step 8
   checks (`read_side_contract.md` section 3), and in any other member it is left to the record checks; a
   `review` never refuses (`provenance.md` section 2 item 6). The content hash covers it as RFC 8785 writes it
   (section 9). [PR-049] [PR-109] [HS-003]
6. **Strict JSON.** Records follow I-JSON (RFC 7493), with the one difference below on noncharacters. A reader
   refuses as not valid JSON, so that the record is malformed, exactly: text that is not a JSON text by RFC
   8259's grammar (a trailing comma, a comment, an unescaped control character in a string, among others);
   and the following, which that grammar allows or does not decide:
   - bytes that are not well-formed UTF-8: an overlong form, a surrogate code point encoded in UTF-8, a
     truncated sequence (text in UTF-16 or UTF-32 is refused by this rule or by the grammar);
   - a byte-order mark at the start;
   - a member name repeated within one object, names compared after their escapes are decoded and without
     Unicode normalisation;
   - the tokens `NaN`, `Infinity` and `-Infinity`;
   - a string escape that leaves a surrogate unpaired;
   - a number that rounds to an infinity: under IEEE 754 rounding to nearest, ties to even, one whose
     magnitude is at least 2^1024 − 2^970 (so `1.7976931348623158e308` reads as the largest double and
     `1.7976931348623159e308` is refused);
   - arrays and objects nested more than 64 deep, the top-level value having depth 1 and each array or object
     inside another adding 1 (scalars do not count).

   Every number is the IEEE 754 double nearest it, ties to even, integers included: `9007199254740993` reads
   as `9007199254740992`, a number too small for a normal double reads as the nearest subnormal or zero (so
   `3e-324` reads as `5e-324`, `1e-400` as `0` and `-1e-400` as `-0`), as JavaScript reads them. A member that
   must be an integer is a double with no fractional part; whether it is whole is a check of its value, made
   where the member is used, not of its JSON type. An escaped U+0000 is a legal character. Noncharacters
   (U+FFFE, U+FFFF, U+FDD0 to U+FDEF and the like), which I-JSON forbids, are legal here, because common
   parsers accept them and they make no reading ambiguous. These rules apply also to scene documents, engine
   crosswalks, read requests and conformance case files. Most JSON libraries need configuring to keep them: a
   stock parser call accepts some of what this list refuses (README, "Conventions"). [PR-002] [PR-047]

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

`licence` and `body` are objects; every other member is a string. A writer MUST NOT add other top-level
members (the writer schema refuses them). A reader ignores a top-level member it does not know, unless it is
one slip from a member of this table (section 10 item 5), and keeps it for hashing (section 9). [RC-003]
[PR-005]

## 3. Record types

| `record_type` | Body | Stability in 0.1.0 |
|---|---|---|
| `material` | a substance: its sections (section 4) | experimental |
| `overlay` | a replacement of some fields of one material, applied only when a consumer declares it (section 4.4) | experimental |
| `interface` | a property of a pair (AD 4.13) | name reserved; body specified in a later minor version |

1. A reader that meets a record of a type it cannot read (an unknown type, a namespaced type, or `interface`
   in 0.1.0) MUST skip it when listing records, and MUST refuse it, with the reason `unknown_type`
   (`read_side_contract.md` section 3, step 5, unless an earlier step refuses it first), when the record is
   referenced: by a request's target, a binding, a pin, a layered-path interval or an interface member.
   [PR-006] [PR-007] A record of a type the reader can read is refused in the same way where it is referenced
   in a role its type does not fill: a target, named directly or through a scene's region, whose record is not
   a `material`, and a record an `overlay` acceptance names that is not an `overlay`
   (`read_side_contract.md` section 3, step 6). [PR-007]
2. An object with a `document_type` member and no `record_type` member is a scene document (`geometry.md`), an
   engine crosswalk (`usd_binding.md` section 10.1) or another OpenMaterica document, not a record: a reader
   that lists records never lists it, and sets it aside before resolving a reference (`read_side_contract.md`
   section 3, step 1), so a reference never resolves to it. [PR-006] [PR-328]
3. Other namespaces may later define their own record types (`<namespace>:<type>`, AD 4.1). The first is
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

1. `sections` maps a section name to a section. Every section is optional. A reader skips a section it does
   not know, whatever it holds, unless its name is one slip from a known section's (section 10 item 5), and
   reads the sections it knows from a record that also holds sections it does not know; a known section it
   does not read is still checked as structure (section 1 item 2). [PR-008]
2. A section holds `fields`, a map from a field name to a value field (section 5), and optionally `specimen`,
   the specimen facts shared by its fields (`provenance.md`). A field's own `specimen` overrides the
   section's, fact by fact. [PR-009]
3. A section's presence says what is known about a material. It never says where that physics applies; a
   consumer declares that (`declarations.md`).
4. `extensions` maps a registered namespace to sections in that namespace, using the same value fields. Their
   meaning belongs to that namespace. A reader ignores what `extensions` holds (it checks only that
   `extensions` is an object, section 1 item 2), and no requirement can name a field in it. Records in the
   curated library carry none. [PR-034] [RC-005]

### 4.1 Sections and fields of schema 0.1.0

Each field registers one unit, the value forms it may take, and the conditions it requires. A required
condition MUST be present, holding `{"status": "unstated"}` if the source does not state it, or `{"status":
"not_applicable"}` if it is the form's own axis (`read_side_contract.md` section 5). [RC-006] Every field is
**experimental** in 0.1.0 (README "Versions").

| Section.field | Unit | Forms | Requires | Label |
|---|---|---|---|---|
| `bulk.density` | `kg/m3` | constant, table, interval | `temperature`, `density_kind` | none |
| `bulk.elemental_composition` | `1` | composition (basis `mass_fraction`) | none | none |
| `fluid.dynamic_viscosity` | `Pa.s` | constant, table, interval | `temperature`, `shear_rate` | `materica.fluid.newtonian.v1` on a constant, or on a table whose axis is not `shear_rate` |
| `magnetic.remanence` | `T` | constant, interval | `temperature`, `specimen_shape`, `test_method` | none |
| `magnetic.saturation_magnetisation` | `A/m` | constant, interval | `temperature`, `specimen_shape`, `test_method` | none |
| `magnetic.volume_susceptibility` | `1` | constant, table, interval | `temperature`, `specimen_shape`, `magnetic_flux_density` | `materica.magnetic.linear.v1` on a constant, or on a table whose axis is not `magnetic_flux_density` |
| `biocompatibility.evidence` | `{"status": "not_applicable"}` | evidence (section 4.3) | none | none |

- `density_kind` is `apparent` (the whole specimen, pores included) or `matrix` (the solid phase only).
  [PR-315]
- Every unit code registered for a field (here) or a condition (`provenance.md` section 6) is a valid UCUM 2.2
  expression in which no special unit (UCUM's table of special units: the neper, the bel, the degree Celsius
  among them) is part of a product or quotient; a unit held as a status object is exempt. A test over both
  tables checks each code with a UCUM 2.2 parser and that rule. [RC-120]
- `magnetic.volume_susceptibility` is the SI volume susceptibility. A CGS value is 4π times smaller and is
  converted on the write side. [not yet covered]
- `specimen_shape` and `specimen_size` are conditions, not specimen facts: they change what a value means (a
  sphere's demagnetisation, AD 4.8), so a consumer matches them by requirement (`provenance.md` section 6).
  [PR-315]
- **Labels.** A label names the trivial model a single value implies (AD 4.4). `materica.fluid.newtonian.v1`:
  the viscosity does not depend on shear rate over the stated `shear_rate` condition.
  `materica.magnetic.linear.v1`: the magnetisation is proportional to the field over the stated
  `magnetic_flux_density` condition, with no saturation. A label is not a family: `model_families.md`'s
  refusal of an unknown family does not apply to it, and a reader returns it with the value. A consumer may
  require a label (`declarations.md`). [PR-035] On a constant, the Newtonian label claims only what the
  stated `shear_rate` condition covers; it is no evidence about other shear rates. [not yet covered] A label
  the reader does not know refuses the field as a token it does not know (`unknown_token`, section 10), and a
  label it knows that the row does not name for the field and its form refuses it as `form_invalid`. A
  missing label is not refused at read, since the value does not depend on it: a model that assumes the label
  refuses its absence (`declarations.md` section 1 item 5), and a record check flags it. [PR-053] [RC-122]
- `test_method` is required on remanence and saturation magnetisation: a closed magnetic circuit
  (`hysteresigraph`, as in ASTM A977/A977M and IEC 60404-5; makers also write "hysteresisgraph") measures
  without the specimen's demagnetisation and an open-circuit magnetometer with it, so on one specimen shape
  the two describe different things. [PR-311] `specimen_shape` stays required beside a closed-circuit method,
  although the shape does not enter there: a datasheet that gives no shape holds it `unstated`, and a consumer
  that accepts such a value waives `condition_unstated` for it (`declarations.md` section 4.2). [PR-305]
- A field whose form is not one its row allows is refused with the reason `form_not_registered`, and so is a
  composition whose basis the row does not allow. [PR-036]
- Reserved section names, specified in later minor versions: `acoustic`, `radiological`, `mechanical`,
  `optical`, `thermal`, `dielectric`. Reserved because the USD binding uses them as attribute namespaces:
  `region`, `scene`, `domain`, `overlay`, `path`, `inputSheet` (`usd_binding.md`). Reserved field names in
  every section: `specimen`.

### 4.2 Units

A value field's `unit` MUST equal its field's registered unit. A reader refuses a field whose unit differs,
with the reason `unit_mismatch`; it never converts. The same holds for a table's `axis_unit` and a condition's
`unit`, against the condition's registered unit (`provenance.md` section 6). [PR-010] [PR-037] The source's
own unit, and any conversion, are extraction facts (`provenance.md`). Units are compared as strings, after
JSON escapes are decoded, code point for code point, as a request's are (`read_side_contract.md` section 1);
none is parsed. A unit registered as a status object equals one holding the same `status` token, whatever its
`reason`. A unit is compared at step 9 alone (`read_side_contract.md` section 3), a condition's and a
`plus_minus` entry's included: step 8 checks only that it is a string or a status object, the latter by
`provenance.md` section 1 item 5 (so one holding a member besides `status` and `reason` is a shape error), and
one that is neither is a shape error (`form_invalid`). [PR-010] [PR-037] [PR-110]

### 4.3 Biocompatibility evidence

`biocompatibility.evidence` is a value field of form `evidence`: `"unit": {"status": "not_applicable"}`,
`"conditions": {}`, and `"evidence": [...]`, a list of test reports for the material, never a status. Each
entry holds `endpoint`, `standard` (`{"designation": "ISO 10993-5", "year": 2009}`), `contact_category`,
`contact_duration`, `material_form`, `processing`, `reported_result` (the source's words, verbatim) and
`provenance`. A device's biocompatibility is declared on the device by its maker and is never derived from
these entries (AD 4.2). No member of an entry states a conclusion about safety. [PR-038] [RC-007] The token
lists of `contact_category`, `contact_duration` and `material_form` will follow ISO 10993-1's categories
(recalled); until they are listed, these members hold the source's words. [not yet covered]

1. The list holds at least one entry; an empty list is a shape error (`form_invalid`), since an absent field
   already says there is no evidence (section 1 item 4). Every member of an entry is present, and
   `standard`'s `year` is a whole number. [PR-052]
2. An entry from a source whose redistribution status makes it reference-only holds `{"status": "withheld"}`
   in every member but `provenance` (`provenance.md` section 7). An entry is withheld whole, its provenance
   kept, or not at all: one holding `withheld` in some of those members and not in every one breaks its
   shape (`form_invalid`). Any other status stands in an entry's member as in any required member
   (`provenance.md` section 1), `unstated` for a contact duration the source does not give, say. A reader
   returns an entry with its statuses and its `provenance` whole, holding the members `read_side_contract.md`
   section 2 item 5 defines, never cut to the members a result's own `provenance` holds. [PR-038] [PR-337] A
   read gives `withheld` when every entry is withheld, and `unknown` with the reason `entries_withheld` when
   some are (`read_side_contract.md` section 3, step 8). [PR-052]
3. `conditions` holds no registered condition: one there is a shape error (`form_invalid`), while a name the
   reader does not know gives `unknown`, as anywhere (section 10). [PR-052] [PR-031]

### 4.4 The overlay body

```json
{
  "purpose": "fit",
  "base": {"id": "materica/MAT-0002", "version": "1.0.0", "content_hash": "sha256:..."},
  "scope": {"consumer": "mime", "model": {"name": "stokes_drag", "version": "0.3.0"},
            "model_configuration_hash": "sha256:...", "run": "run-2026-10-12-01"},
  "replaces": {"fluid.dynamic_viscosity": {}}
}
```

1. `purpose` is `fit` (a consumer's fitted value), `fill_in` (a user's own copy of a withheld value),
   `measurement` (an organisation's own measurement) or `scene_override`. [not yet covered]
2. `base` names one material by identifier, version and content hash. `replaces` maps `<section>.<field>` to a
   whole value field, with its own `specimen` (it never inherits the base section's), which replaces the
   base's field entirely, provenance included. A field an overlay replaces is read from `replaces`, not from
   the base's section. So a fault in the base's envelope or body that refuses each field read from the base
   (section 10 item 5) refuses it, as one in the overlay's own envelope or body does; a fault in the base
   section's `specimen`, or in the base field it replaces, does not. [PR-011] `replaces` names only fields the
   base holds. A reader refuses an overlay that replaces a field its base lacks, whichever key of `replaces`
   that is, with the reason `absent`. It refuses, with the same reason, an overlay named for the field read
   that does not replace that field. [RC-016] [PR-046]
3. `scope` names the consumer, the model (name and version) and a hash of the model's configuration with every
   value read from records removed (for MIME, the graph's configuration minus the parameters its material
   input sheet derives from records), and optionally the run. A `measurement` overlay's scope names the
   consumer only; a `fill_in` overlay's names the user in `consumer`, and no model. The build compares the
   scope (`declarations.md` section 5). [not yet covered]
4. A reader applies an overlay only when an `overlay` acceptance the request carries names it, for the field
   read (`read_side_contract.md` section 1). Every overlay so named must apply. Where this section, or steps 1
   to 5 of the read, refuses one, the read is refused. [PR-012] [PR-039]
5. A reader refuses an overlay whose base differs from the record in use, with the reason
   `overlay_base_mismatch`; no declaration accepts it. The base differs where its `id`, `version` or
   `content_hash` differs from the record's, compared as strings, code point for code point. So a stale
   overlay, whose base names another version of the record, is refused. So is one whose base `content_hash`
   is not `sha256:` and 64 lowercase hexadecimal digits, since the reader schema checks only that it is a
   string (section 1 item 2). [PR-039]
6. Two declared overlays that replace the same field of the same base are refused, with the reason
   `overlay_conflict`. [PR-041]
7. **Fill-ins.** A user fills in a reference-only value with an overlay of purpose `fill_in`, in the user's
   own namespace, whose base is the reference-only record. The curated record never changes, so every user and
   every scene that pins it holds the same record. The fill-in overlay states the user's licence for the
   values (for a source that does not permit redistribution, `LicenseRef-user-extracted`), the evidence from
   the user's copy, and the user's review (`provenance.md` section 7). A reader labels every value it reads
   through a fill-in `user_extracted`. [PR-042]
8. A reader refuses an overlay whose `purpose` is none of item 1's, with the reason `unknown_token`, and one
   of another purpose than `fill_in` that replaces a field in which its base holds a withheld value or
   evidence entry, one alternative's included, whichever key of `replaces` that field is, with the reason
   `withheld`: only a fill-in fills one in, and only a fill-in's value is compared with the base's document
   and labelled `user_extracted` (item 7, `provenance.md` section 7). [PR-042]

## 5. Value fields

A value field is an object with these members, or an `alternatives` object (below).

| Member | Required | Contents |
|---|---|---|
| `form` | yes | one of `constant`, `table`, `power_law`, `interval`, `composition`, `parameter_set`, `reference_data`, `evidence` [PR-043] |
| `unit` | yes | the field's registered unit |
| the form's member | yes | `value` for a constant; otherwise the member named like the form (`table`, `power_law`, `interval`, `composition`, `parameter_set`, `reference_data`, `evidence`). In a reference-only value it holds `{"status": "withheld"}` (`provenance.md` section 7) |
| `conditions` | yes | the conditions the value was measured at (`provenance.md`) |
| `specimen` | no | specimen facts, overriding the section's |
| `statistics` | yes, except for `evidence` | the statistics block (`uncertainty.md`). For a table or a power law it applies to every value the form gives (`uncertainty.md` section 1 rule 2). In a reference-only value it holds `{"status": "withheld"}` |
| `provenance` | yes | origin, source, extraction, evidence, review (`provenance.md`) |
| `label` | where the field's row names one; a reader does not refuse its absence (section 4.1) | the field's label (section 4.1) |
| `fit` | where `provenance.origin` is `fitted` | the fit record (`fits_and_reference_data.md` section 2) |

**Alternatives.** Where sources disagree, or one source gives values at several conditions, or a grade's
datasheet sits beside measurements on its lots (`provenance.md` section 6.2 item 5), the field is
`{"alternatives": [<value field>, ...]}`: every alternative found, each complete, none marked as the default.
`alternatives` is a non-empty list. Each entry is an object, and none holds `alternatives` of its own. The
object holding `alternatives` holds no member of a value field. Anything else breaks the field's shape
(`form_invalid`, at `read_side_contract.md` section 3, step 7, before any pick is checked): an empty list, one
that is not a list, an entry that is not an object or that holds `alternatives`, or `alternatives` beside
`form`, a form's member or another member of the table above. An entry that breaks a value field's shape in
another way is that alternative's own fault, found when it is read (`read_side_contract.md` section 3, step
8). [PR-044]
Alternatives may differ in form. Writers MUST NOT reorder or drop alternatives once a record is released; a
new alternative is appended. [RC-017] A reader reads alternatives as follows. `read_side_contract.md` section
3, step 7, gives every outcome with its reasons and members. [PR-013] [PR-044]

1. **A pick.** A consumer's pick names one alternative by its index among the stored alternatives
   (`declarations.md`). A reader then reads that alternative only, as a field. Where an overlay replaces the
   field, a pick located at the overlay names one of the overlay's alternatives, and one located at the base
   gives `pick_invalid` (`read_side_contract.md` section 3, step 7). [PR-304]
2. **Set aside.** Without a pick, a reader reads each alternative alone, as a field. It sets aside an
   alternative whose conditions, the form's own axis aside, give `not_met`. It sets aside an alternative read
   outside its form's range, a table's or a power law's (`outside_range` without `at_edge`), unless an
   extrapolation the request carries would cover it (`read_side_contract.md` section 5). [PR-044]
3. **Stay.** It sets aside no other. An alternative whose read gives no `not_met` stays. So does one that an
   extrapolation the request carries would cover, since a pick would let it apply. So does one whose form
   `want` cannot give, a table read over an operating range of its axis included. The `not_met` reasons of an
   alternative that stays are reported only once a pick names it, once it is the one left, or once the field
   is refused. [PR-013] [PR-338]
4. **Refuse.** Any other `not_met` in an alternative's read refuses the field. A table alternative read
   exactly at a declared edge (`at_edge`) refuses the field, wherever the edge lies, even where
   `outside_range` stands beside it. An alternative whose read reaches step 11 with no operating value for its
   form's axis refuses the field too, with `request_incomplete` (`read_side_contract.md` section 1). One set
   aside for its conditions never reaches step 11, so it refuses nothing. [PR-044] [PR-308]
5. **The outcome** is the first of these that applies. [PR-013] [PR-044]
   - Where an alternative refuses the field, or every alternative is set aside, the result is `not_met`, with
     the reasons of each, those that wait included. Each reason names its alternative by index, a fault of the
     request aside.
   - Where one alternative stays, the result is that alternative's read.
   - Where more than one stays and none has a form `want` can give, the result is `not_met` (`want_mismatch`).
     A table read over an operating range of its axis counts as a form `want` cannot give.
   - Otherwise the result is `unknown`, with the reason `no_pick`. It carries each alternative that stays, in
     stored order, with its own conditions, specimen, statistics and provenance (`read_side_contract.md`
     section 2). Each one's `unknown` reasons stand beside `no_pick`, each naming it by index. No
     extrapolation is applied: the entry of an alternative kept outside its form's range holds its form's
     member as stored. A waiver never accepts a `no_pick`; only a pick does.

## 6. The value forms

Every form carries the range it covers: a constant through its conditions, a table through its abscissae and
`source_range` (table item 3), a power law through its `range`, a parameter set through its coverage. How a
read is checked against that range, and against a declared extrapolation, is in `read_side_contract.md`
section 5. [PR-014]

**Constant.** `"value": <number>`. [PR-015]

**Table.**

```json
"table": {"axis": "temperature", "axis_unit": "K",
          "x": [293.15, 298.15, 303.15], "y": [0.001002, 0.000890, 0.000797],
          "scheme": "linear", "edges": [], "source_range": [273.15, 373.15]}
```

1. `axis` names the table's axis, a numeric condition, and the field's `conditions` holds that condition as
   `{"status": "not_applicable"}` (section 4.1). `axis_unit` is a string or a status object; step 9 alone
   compares it with that condition's registered unit (section 4.2). `x` holds at least two distinct values and
   is non-decreasing, and `y` holds one number for each entry of `x`. `edges` is required: a list of numbers,
   empty where the table has none, with no number twice; each edge lies strictly between `x[0]` and `x[-1]`
   and appears in `x` exactly twice, consecutively, the two entries giving the values below and above it, and
   no other x value repeats. Numbers are compared by value, so `-0` equals `0`. [RC-008] [RC-018] [PR-322]
2. `scheme` is `linear` or `loglog`. A `loglog` table holds only positive `x` and `y`. [RC-019] [PR-016] A
   reader refuses a table that breaks item 1 or item 2, with the reason `form_invalid`. [PR-045] A `scheme`
   that is a string other than these two is a token the reader does not know: the field is refused with the
   reason `unknown_token` (section 10 item 3), not `form_invalid` for the scheme. An `axis` that is a string
   naming no numeric condition the reader knows, a token condition's name included, is a token the reader
   does not know for that member: the field is refused with the reason `unknown_token` (section 10 item 3),
   not `form_invalid` for the axis, and item 1's rule on the axis condition is not checked. An `axis` that is
   not a string breaks item 1. [PR-032]
3. The table is read over its **readable range**: from `x[0]`, or `source_range[0]` where that is greater, to
   `x[-1]`, or `source_range[1]` where that is smaller, inclusive. An operating value is compared with these
   ends and with the edges by value and exactly (`read_side_contract.md` section 5, "Exactness"), so `-0` lies
   at an end or an edge at `0`. A read exactly at an edge is refused (the value is two-sided), wherever the
   edge lies. Where the edge lies outside the readable range, the refusal at the edge decides: the table gives
   no value, no extrapolation applies, and `outside_range` stands beside `at_edge`. Beyond an edge that lies
   outside the readable range or on its end, on the far side from the range, no extrapolation applies either,
   so the table gives no value there (`read_side_contract.md` section 5, "The form's range"). Otherwise the
   interval used is the one whose two knots bracket the read, strictly where an edge is concerned, so a read
   just below an edge uses the knot below it; a knot outside `source_range` is used where it brackets a read
   inside the readable range. [PR-017] [PR-018] [PR-019]
4. `source_range`, where present, is the range the source says the values hold over: two numbers in the
   table's `axis_unit`, the first not greater than the second, sharing with `[x[0], x[-1]]` at least one value
   that is no edge. A reader refuses one that is not (`form_invalid`). It never extends the readable range,
   and narrows it where it is narrower (item 3). [PR-019] [RC-008]
5. `points` is a reserved member name in a table. It is kept for what a knot carries of its own, such as its
   provenance or its spread, where knots come from different places in a source or carry different spreads.
   Its shape, and how a read uses it, will be specified with its first consumer. A 0.1.0 writer MUST NOT write
   it; the closed writer schema refuses it (section 1 item 2). [RC-003] A 0.1.0 reader refuses a table that
   holds `points`, whatever it holds (`null` and `[]` included), with the reason `points_unsupported`, so that
   a knot's own spread or origin is never replaced by the table's. [PR-157] `null` there also gives
   `form_invalid` (section 1 item 5). [PR-049] For section 10 item 5, `points` counts as a member named at a
   table's place, so a member one slip from it, such as `point`, is refused. [PR-030]

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
4. Acoustic attenuation, longitudinal or shear, is stored as an amplitude coefficient in nepers per metre,
   registered as `/m`, with `x` in hertz; another section's attenuation coefficients are defined with that
   section. The neper is dimensionless, and UCUM does not allow a special unit in a quotient, so
   `Np/m` is not a valid UCUM expression (UCUM 2.2, sections 22 and 46). Decibels, nepers, per-centimetre and
   per-megahertz units and intensity coefficients are converted on the write side and recorded as extraction
   facts. No 0.1.0 field takes a power law; the first arrives with the acoustic
   section, and its cases with it. [not yet covered]

**Interval.**

```json
"interval": {"lower": 0.4, "upper": {"status": "none"}, "basis": "stated_bound"}
```

1. `lower` and `upper` are numbers, at most one holds `{"status": "none"}` (a one-sided interval), and
   `lower <= upper` where both are numbers; an interval that breaks this is a shape error (`form_invalid`).
   [RC-010] [PR-050]
2. `basis` is `reported_range`, `proxy_range` (a range taken from other tissues), `specification_limits` (a
   datasheet's limits: a promise about a product, not a measured spread) or `stated_bound`. [RC-009]
3. A reader returns the bounds with their basis. A nominal value or a sample is the consumer's declaration
   (`declarations.md`). [PR-022]

**Composition.**

```json
"composition": {"basis": "mass_fraction", "sum_rule": "partial",
                "components": [{"component": "element:H", "fraction": 0.102},
                               {"component": "element:O", "fraction": 0.723}]}
```

1. `basis` is `mass_fraction`, `volume_fraction` or `mole_fraction`. `component` is `element:<symbol>`, the
   symbol as IUPAC writes it, one of the table below. Another symbol, or a component of another kind, is a
   token the reader does not know (`unknown_token`). Named components (water, lipid, haemoglobin) come with
   the optical section. [RC-011] [PR-051]
2. `sum_rule` is `sums_to_one` or `partial` (the source lists only some components). Where the source's own
   fractions do not sum to one, `stated_sum` records the sum the source gives, and nothing is normalised. A
   checker flags a `sums_to_one` composition whose fractions sum to more than 1e-6 away from one with no
   `stated_sum`. [RC-011]
3. A component MAY carry its own `statistics`, a statistics block (`uncertainty.md` section 1), which a read
   checks as it checks the field's and returns with the component. [PR-051]
4. A reader returns the composition as stored: its basis, sum rule, stated sum where present, and components.
   [PR-023]
5. `components` holds at least one component; no component appears twice; and each `fraction` is a number from
   0 to 1. A composition that breaks this is a shape error (`form_invalid`). [PR-051] [RC-011] A source's
   "trace" or a bound on a fraction cannot be recorded in schema 0.1.0. [not yet covered]

The element symbols are IUPAC's 118 (the last four named on 28 November 2016):

| Period | Symbols |
|---|---|
| 1 | `H` `He` |
| 2 | `Li` `Be` `B` `C` `N` `O` `F` `Ne` |
| 3 | `Na` `Mg` `Al` `Si` `P` `S` `Cl` `Ar` |
| 4 | `K` `Ca` `Sc` `Ti` `V` `Cr` `Mn` `Fe` `Co` `Ni` `Cu` `Zn` `Ga` `Ge` `As` `Se` `Br` `Kr` |
| 5 | `Rb` `Sr` `Y` `Zr` `Nb` `Mo` `Tc` `Ru` `Rh` `Pd` `Ag` `Cd` `In` `Sn` `Sb` `Te` `I` `Xe` |
| 6 | `Cs` `Ba` `La` `Ce` `Pr` `Nd` `Pm` `Sm` `Eu` `Gd` `Tb` `Dy` `Ho` `Er` `Tm` `Yb` `Lu` `Hf` `Ta` `W` `Re` `Os` `Ir` `Pt` `Au` `Hg` `Tl` `Pb` `Bi` `Po` `At` `Rn` |
| 7 | `Fr` `Ra` `Ac` `Th` `Pa` `U` `Np` `Pu` `Am` `Cm` `Bk` `Cf` `Es` `Fm` `Md` `No` `Lr` `Rf` `Db` `Sg` `Bh` `Hs` `Mt` `Ds` `Rg` `Cn` `Nh` `Fl` `Mc` `Lv` `Ts` `Og` |

**Model parameter set.** `"parameter_set": {...}`, specified in `model_families.md`. A reader that does not
claim the family evaluation suite refuses it, with the reason `family_suite_absent`. [PR-024]

**Reference data.** `"reference_data": {...}`, specified in `fits_and_reference_data.md`. A reader never
returns reference data as a property's value; it is read only by a request for reference data (FD suite).
[PR-025]

**Evidence.** Section 4.3.

## 7. Identifiers

Every pattern below must match in full: a full match, not a search, so a trailing newline does not match.

1. A namespace matches `[a-z0-9_]+`. Namespaces are registered first come first served in the library's
   `publishers.yaml`, whose format is outside this specification; an unregistered namespace is not unique, so
   a consumer pins records by content hash, not by identifier alone. `materica`, `mime` and `conformance` are
   reserved. `conformance` names only conformance fixtures, the records and documents case files supply
   (`README.md`, "Case files"): their values, provenance and sources are illustrative, chosen to exercise a
   rule, and state nothing about any material, whatever their tokens say. A conformance tree is a directory
   named `conformance` whose parent directory is named `data`. A record check flags a record or document in
   `conformance` unless the path it is given for it lies in a conformance tree; a check of a whole library or
   repository leaves its conformance trees out, since their files break rules on purpose. [RC-012] [RC-121]
2. A record identifier is `<namespace>/<local id>`, the local id matching `[A-Za-z0-9_.-]+`. In `materica`,
   local ids are `MAT-NNNN` for materials and `INT-NNNN` for interfaces. [RC-013]
3. A family identifier is `<namespace>.<segment>(.<segment>)*.v<N>`, each segment matching `[a-z0-9_]+` and
   `N` a positive integer without leading zeros. [not yet covered]

## 8. Versions

1. `schema_version` and a record's `version` are `MAJOR.MINOR.PATCH`: a string that matches in full, in ASCII
   (a full match, so `"0.1.0\n"` does not match, although a regular-expression search with `$` would accept
   it), `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`, with no pre-release or build part. Components
   are compared as numbers; with no leading zeros, comparing their lengths and then their digits gives the
   same order with no overflow. The same rule holds for the schema versions of other OpenMaterica documents: a
   scene document's `scene_schema_version` and an engine crosswalk's `crosswalk_schema_version`. Other
   versions a document names (a consumer's, a model's, an engine's, a source's) are not bound by it. [RC-014]
   [PR-048]
2. **Before 1.0.0**, a reader reads only records of its own `MAJOR.MINOR`, whatever their patch, and refuses
   every other, with the reason `other_version`. From 1.0.0, a reader of `M.m` reads a record of `M.n` for any
   `n` by the rules of section 10, and refuses another major version. [PR-026] [PR-027]
3. A record's `version` changes **major** when a value changes by more than the uncertainty its record states
   for that value (a population's spread is not that measure; where the record states none, any change of
   value), a condition changes, or a parameter set moves to another family version; **minor** for a new value
   or section; **patch** for provenance wording (`DOCUMENTATION_ARCHITECTURE.md` section 7.1). From 1.0.0, a
   re-issue that makes a field unreadable to a reader of an earlier minor schema version is **major** too,
   even where no value changes, so that a consumer that pinned the record is told that the field broke. A
   spread re-stated under a name reserved in advance (section 10) is such a re-issue. Before 1.0.0 the rule
   does not arise: a reader reads only records of its own minor version (item 2). [not yet covered]

## 9. The content hash

1. `content_hash` is computed over the record as stored, every member a reader does not know included, with
   these removed: the top-level `content_hash` and `card`; and every member named `review` or `copy` at any
   depth inside any object that is the value of a member named `provenance`, through the objects and arrays it
   holds; a `provenance` whose value is not an object has nothing removed for its own sake, though an object
   that is the value of another member named `provenance` inside it is treated as above. [HS-001]
2. The remaining JSON is serialised by the JSON Canonicalization Scheme, RFC 8785 (recalled), and hashed with
   SHA-256. Strings, member names included, are serialised as they are, with no Unicode normalisation.
   `content_hash` is `sha256:` followed by the 64 lowercase hexadecimal digits of the digest. Each number is
   serialised as the double it was read as (section 1 item 6), so an integer beyond 2^53 is hashed as its
   nearest double and an integer written as `1000000000000000000000` is serialised as `1e+21`. [HS-002]
   [HS-003]
3. So a second review, or a reworded card, does not change a record's hash, and changing anything else, its
   type and licence included, does.
4. The conformance suite has hash test vectors, including numbers whose canonical form differs from their
   written form, and a record holding members the reader does not know. [HS-003]
5. When and against what a reader checks the hash: `read_side_contract.md` section 3.

## 10. Reading a record of a newer minor version (from 1.0.0)

A reader of `M.m` reading a record of `M.n`, `n > m`:

1. ignores an object member it does not know, except as items 2 to 5 say; [PR-030]
2. gives `unknown` for a condition name it does not know, never "present and unchecked"; [PR-031]
3. refuses a field holding a token it does not know in an enumerated member (a form, a scheme, a basis, a
   structure, a status), with the reason `unknown_token`, never reading it as a token it knows; [PR-032]
4. skips a section it does not know (section 4), except as item 5 says, and skips or refuses a record type it
   does not know (section 3); [PR-006] [PR-007] [PR-008]
5. refuses a member it does not know, where items 1 and 4 would ignore or skip it, that is one slip (below)
   from a member the shape names at that place. It is a shape error there, and each field it affects is
   refused with the reason `form_invalid` (`read_side_contract.md` section 3, step 8): in a value field, that
   field; in a section, its `specimen` and the names in its `fields` included, each field read from that
   section; in the envelope or the body, the names in `sections` included, each field read from that record,
   or through that overlay. The reader schema does not check it, so step 3 still passes the record. Inside
   `extensions` nothing is checked (section 4 item 4); inside a member step 8 does not check, it is left to
   the record checks; and a `review` holding one reads as `{"status": "not_checked"}`, since a review never
   refuses (`provenance.md` section 2 item 6). [PR-030] [PR-108]

The same rules apply before 1.0.0 to a token, condition or member a reader does not know within its own minor
version. [PR-032]

Two names are **one slip** apart when one becomes the other by inserting, deleting or substituting one
character, an underscore included, or by swapping two adjacent characters, counting code points; or by making
one of its `_`-separated words plural or singular: `s` or `es` added at its end or taken off it, a final `y`
exchanged with `ies`, or `datum` with `data`, `index` with `indices` or `matrix` with `matrices`. A member
more than one slip from every member named at its place is ignored, as item 1 says. The members named at one
place, refused ones included, are kept more than one slip apart, single letters aside (`x` and `y`, a power
law's `a` and `b`, a beta distribution's `p` and `q`), which every reader of the version knows. A later minor
version adds no member one slip from one already named at its place, refused ones included. So item 5 never
refuses a member that a version names at its place. [not yet covered]

From 1.0.0, a later minor version adds a member that changes how existing members are read only (a) under a
name reserved in advance, which every earlier reader of the same major version already refuses, as it refuses
a table's `points` (section 6, table item 5), or (b) with a new token in an existing enumerated member that
such a reader checks in each field the member changes (`unknown_token`, item 3). The later version requires
that name or token wherever the member appears: without it, an earlier reader ignores the member (item 1) and
reads each field as if the member were absent. Any other such member waits for a new major version of the
schema, a new `MAJOR` in `schema_version`, not in a record's `version` (section 8;
`DOCUMENTATION_ARCHITECTURE.md` section 7.1). [not yet covered]

## Cases

| Case | Suite | Tests |
|---|---|---|
| PR-001 | plain read | a record in another serialisation is not read as a record |
| PR-002 | plain read | each of these, in the record a read's target names, gives `malformed`, never a crash: invalid JSON; a trailing comma; UTF-16 and UTF-32 text; an overlong form (`C0 80`); an encoded surrogate (`ED A0 80`); a byte-order mark before valid JSON; a member name repeated after unescaping (`{"a":1,"\u0061":2}`); `NaN`; `Infinity`; an unpaired surrogate escape; `1.7976931348623159e308`; nesting 65 deep, and 100000 deep without a crash; an envelope member missing or of the wrong JSON type; a `content_hash` that is not `sha256:` and 64 lowercase hexadecimal digits; a record `version` off the pattern (`"1.0"`, the target naming that same string); a known section whose `fields` is an array; and, when a read applies it (`read_side_contract.md` section 3, step 6), an overlay whose `base` has no `content_hash`. A record with nesting 64 deep, an escaped U+0000 or a noncharacter is read |
| PR-003 | plain read | an absent field has no value |
| PR-004 | plain read | every record type carries the envelope |
| PR-005 | plain read | an unknown top-level member is ignored; one that is one slip from an envelope member (`crad`) refuses every field read from the record (`form_invalid`) |
| PR-006 | plain read | an unknown record type is skipped when listing; so is an object with `document_type` and no `record_type` |
| PR-007 | plain read | a referenced record of an unknown type is refused (`unknown_type`); so is a target that is not a `material` (an overlay record, at step 5), and a record an `overlay` acceptance names that is not an `overlay` (at step 6) |
| PR-008 | plain read | a record with an unknown section is read for the sections the reader knows, whatever the unknown section holds (`null`, a number, an object); a section whose name is one slip from a known section's (`fluids`) refuses every field read from the record (`form_invalid`) |
| PR-009 | plain read | a field's specimen fact overrides its section's |
| PR-010 | plain read | a field whose unit differs from the registered one is refused (`unit_mismatch`), compared code point for code point (`kg.m-3`, `Pa s`, `pa.s`); an escaped `\u0050a.s` is `Pa.s`; a status object where a string is registered, or a string on evidence, is refused (`unit_mismatch`, at step 9); a unit that is neither a string nor a status object gives `form_invalid` at step 8; a unit held as a status object is returned as stored, its `reason` included |
| PR-011 | plain read | an overlay replaces a whole field, provenance included, with its own specimen; a slip in the base's envelope or body (`crad`, `fluids`) refuses the field read through it, as one in the overlay's does, while a fault in the base section's `specimen` or in the replaced base field does not |
| PR-012 | plain read | an undeclared overlay, or one an acceptance names for another field, is not applied |
| PR-013 | plain read | alternatives with no pick give `unknown` (`no_pick`), with one `alternative_values` entry per remaining alternative, holding its index, value, conditions, specimen, statistics, provenance and labels, and no `conditions`, `specimen`, `statistics` or `provenance` of the result's own; a waiver does not accept it; an entry's index counts set-aside alternatives, one stored past a set-aside alternative included; each remaining alternative's own `unknown` reasons stand beside `no_pick`, each with its `alternative` (`condition_unstated`), a set-aside one's not; a grade's `specification_limits` interval beside a lot's constant gives `no_pick` under `want: value` and under `want: bounds`, neither set aside for its form, the interval's entry holding its bounds as stored under `want: value`, with no nominal applied; under `want: components`, which neither form gives, `not_met` (`want_mismatch`), with no `conditions`; a table alternative kept outside its readable range, since an extrapolation the request carries would cover it, or read over an operating range of its axis has its table as stored in its entry, with no extrapolation applied; a kept table's step-12 `unknown` reasons stand beside `no_pick` (`stated_without_origin`), its `outside_range` not; two tables both read over an operating range of their axis give `not_met` (`want_mismatch`), not `no_pick` |
| PR-014 | plain read | every form carries its range |
| PR-015 | plain read | a constant is returned with its conditions |
| PR-016 | plain read | linear and log-log tables interpolate by their scheme |
| PR-017 | plain read | outside the tabulated range is refused (`outside_range`) |
| PR-018 | plain read | exactly at an edge is refused, wherever the edge lies; outside the readable range, `at_edge` and `outside_range`, and no value; just below and just above an edge read the correct side; `-0` at an edge at `0` is at it |
| PR-019 | plain read | `source_range` never extends the readable range, and narrows it where it is narrower; one that is not two ordered numbers sharing with `[x[0], x[-1]]` a value that is no edge (out of order, of another length, disjoint from it, or meeting it only at an edge) refuses the field (`form_invalid`) |
| PR-020 | plain read | a power law evaluates in the field's unit (planned with the acoustic section) |
| PR-021 | plain read | a power law with an unstated range gives `unknown` (`range_unstated`), its axis entry `unknown` |
| PR-022 | plain read | an interval returns its bounds with their basis, a one-sided one included |
| PR-023 | plain read | a composition is returned as stored, its basis, sum rule and stated sum included, never normalised |
| PR-024 | plain read | a parameter set is refused by a reader without family evaluation |
| PR-025 | plain read | reference data is never returned as a property |
| PR-026 | plain read | before 1.0.0, a record of another minor version is refused (`other_version`) |
| PR-027 | plain read | a record of another major version is refused (`other_version`) |
| PR-030 | plain read | an unknown member inside a field is ignored; one that is one slip from a member named at its place refuses the field (`form_invalid`): a field's `specimne`, and in a section's `specimen` a fact `tissue_stat`, which refuses each field read from the section; one inside a `review` reads it as `{"status": "not_checked"}`, and one inside `extraction` refuses nothing |
| PR-031 | plain read | an unknown condition name gives `unknown` |
| PR-032 | plain read | an unknown token in an enumerated member refuses the field only (`unknown_token`) |
| PR-033 | plain read | a record with one unknown token is not malformed; its other fields are read |
| PR-034 | plain read | `extensions` is ignored, whatever its members hold |
| PR-035 | plain read | a label is returned with the value and never refused as an unknown family |
| PR-036 | plain read | a form the field's row does not allow is refused (`form_not_registered`): a power law, a parameter set and reference data on every 0.1.0 field, a parameter set also `family_suite_absent` without the family evaluation suite; a composition basis the row does not allow; the member of a form the row does not allow is not checked |
| PR-037 | plain read | an `axis_unit`, condition unit or `plus_minus` unit other than the registered one is refused (`unit_mismatch`), compared code point for code point, and so is a `unit` on a token condition, and a specimen fact's unit other than the one its row fixes, a status object there included |
| PR-038 | plain read | biocompatibility evidence is returned as a list of reports, each with its `provenance` whole |
| PR-039 | plain read | an overlay whose base differs from the record in use is refused (`overlay_base_mismatch`): another `id`, a stale `version` or `content_hash`, compared as strings, and a base `content_hash` that is ill-formed, which is not `malformed` |
| PR-041 | plain read | two different declared overlays replacing one field are refused (`overlay_conflict`); one overlay named twice for one field gives `request_incomplete` |
| PR-042 | plain read | a value read through a fill-in overlay is labelled `user_extracted`; an overlay whose `purpose` is none of the four (`fil_in`) is refused (`unknown_token`), and one of another purpose replacing a field its base holds withheld is refused (`withheld`), whichever key of `replaces` holds that field, the read's or another, and where one alternative of the base's field is withheld |
| PR-043 | plain read | the form tokens are exactly the eight listed |
| PR-044 | plain read | alternatives whose conditions are not met are set aside, a table never for its own axis entry; an alternative outside its form's range (a table's readable range) is set aside, unless an extrapolation the request carries would cover it; one read at a declared edge refuses the field, outside a narrowed readable range too, and so does any other `not_met` in an alternative, `want`'s and that of an alternative kept for an extrapolation aside (`form_invalid`, `unit_mismatch`, `withheld`), the result holding every alternative's reasons, each with its `alternative`, those that wait in an alternative that stays included, and no `conditions`; one alternative left is read as a field, the set-aside ones' reasons not reported, unless its read refuses the field, which then reports every alternative's reasons, with no `conditions`; all set aside gives `not_met`, with every alternative's reasons; an empty `alternatives`, one that is not a list, one holding an entry that is not an object or that holds `alternatives` of its own, and one beside `form` or `value` refuse the field (`form_invalid`), before any pick is checked |
| PR-045 | plain read | a shape error inside one field refuses that field (`form_invalid`); the other fields are read; a shape error in a section's `specimen` refuses each field read from that section, and fields of other sections are read |
| PR-046 | plain read | an overlay replacing a field its base lacks is refused (`absent`), whichever key of `replaces` that is; so is one named for the field read that does not replace it |
| PR-047 | plain read | numbers read as the nearest double, ties to even, compared exactly: `9007199254740993` as `9007199254740992`; `1e-400` as `0`; `-1e-400` as `-0`, not `0`; `3e-324` as `5e-324`; `2.4703282292062327e-324` as `0`; `1.7976931348623158e308` as the largest double |
| PR-048 | plain read | a record whose `schema_version` is absent, not a string, or does not match the pattern (`"0.1"`, `"0.1.0-rc1"`, `"00.1.0"`, `"0.1.0 "`, `"0.1.0\n"`, Arabic-Indic digits) is malformed; a major or minor component of a hundred digits gives `other_version`, not a crash; `0.1.7` is read by a 0.1 reader |
| PR-049 | plain read | `null` in the envelope (`"card": null`) makes the record malformed; inside a value field (`"unit": null`) it refuses that field (`form_invalid`); inside a member the reader does not know, at the top level or inside a value field, it is ignored; in a member step 8 does not check (`"extraction": null`), it does not refuse the field |
| PR-050 | plain read | an interval with `lower` above `upper` is refused (`form_invalid`) |
| PR-051 | plain read | a composition with a repeated component, a fraction outside [0, 1] or no component is refused (`form_invalid`); `element:Xx` is refused (`unknown_token`); a component's own statistics block is checked and returned as the field's is |
| PR-052 | plain read | an evidence list with some entries withheld gives `unknown` (`entries_withheld`), each withheld entry returned with its statuses; with every entry withheld, `withheld`; an empty list, a registered condition in its `conditions`, an entry withholding some of its members but not every one but `provenance`, `form_invalid`; an entry member holding `unstated` or `not_applicable` is returned with its status |
| PR-053 | plain read | a missing label is not refused; a label the reader knows that the row does not name for the field and its form refuses the field (`form_invalid`), and one it does not know refuses it too (`unknown_token`) |
| HS-001 | hash | the hash excludes exactly the listed members, at any depth |
| HS-002 | hash | the content hash verifies (RFC 8785, SHA-256, lowercase hexadecimal) |
| HS-003 | hash | hash vectors: numbers whose canonical form differs (`1.0`, `1e2`, `0.0000001`, `-0`, an integer written as `1000000000000000000000`, 9007199254740993); `true` beside `1`; `null` in a member the reader does not know; member order by UTF-16 code units; members the reader does not know are hashed; `review` and `copy` removed at any depth inside a provenance object and kept outside one |
| RC-001 | record checks | a placeholder written for an unknown value is flagged |
| RC-002 | record checks | the licence member names the values' licence and excludes evidence |
| RC-003 | record checks | a record invalid against the closed writer schema is flagged |
| RC-004 | record checks | a 0.1.0 record of a namespaced type is flagged |
| RC-005 | record checks | a curated record carrying extensions is flagged |
| RC-006 | record checks | a field missing a required condition is flagged |
| RC-007 | record checks | a biocompatibility entry member stating a conclusion about safety, or an entry missing a member, is flagged |
| RC-008 | record checks | a table breaking table item 1 or 4 of section 6 is flagged: a repeated x value that is not a declared edge, an edge not repeated, at an end or listed twice, `y` of another length than `x`, an axis condition absent or not `not_applicable`, a `source_range` out of order, disjoint from `[x[0], x[-1]]` or meeting it only at an edge |
| RC-009 | record checks | an interval basis outside the four tokens is flagged |
| RC-010 | record checks | an interval with neither bound, with both `none`, or with `lower` above `upper` is flagged |
| RC-011 | record checks | a malformed or repeated component, a fraction outside [0, 1], a symbol not in the table, or a composition that does not sum to one with no stated sum, is flagged |
| RC-012 | record checks | a namespace outside `[a-z0-9_]+` is flagged |
| RC-013 | record checks | a malformed record identifier is flagged |
| RC-014 | record checks | a malformed version is flagged |
| RC-015 | record checks | `null` anywhere in a record is flagged |
| RC-016 | record checks | an overlay that replaces a field its base lacks, or whose field has no specimen, is flagged |
| RC-017 | record checks | a released record whose alternatives were reordered or dropped is flagged |
| RC-018 | record checks | a table with fewer than two distinct x values is flagged |
| RC-019 | record checks | a log-log table with a non-positive x or y is flagged |
| RC-120 | record checks | every registered unit code, for fields and conditions, parses as UCUM 2.2 with no special unit in a product or quotient; `Np/m` is refused by that rule; `/m` passes |
| RC-121 | record checks | a record or document in the `conformance` namespace given from a path outside a conformance tree (a directory `conformance` whose parent is `data`) is flagged, and one given from inside it is not; a check of a whole library leaves conformance trees out |
| RC-122 | record checks | a field missing the label its row names, or holding a label the row does not name for it, is flagged |

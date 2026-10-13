# Geometry

Schema 0.1.0, draft. Conventions, suites and case numbers: `README.md`. Rationale: AD 3.5 (rule 3), 5.1 and
5.2. The USD form of everything here is in `usd_binding.md`. A reader that claims the scene documents suite
(SC) offers the operations of section 2.

## 1. Scene documents

1. A scene document describes a scene, not a substance. It is not a record: it has no `record_type`, and a
   reader that lists records never lists it. [SC-001]
2. Every scene document is one JSON object with `scene_schema_version` (`MAJOR.MINOR.PATCH`, read under the
   version rules of `record_format.md` section 8: before 1.0.0 a reader reads only its own minor version) and
   `document_type`: `scene_manifest`, `layered_path` or `label_crosswalk`. A scene document that is not valid
   JSON, or not valid against the reader schema, gives `malformed` for every operation on it; one of another
   version gives `other_version`. Unknown members and tokens follow `record_format.md` section 10. [SC-002]
3. A scene document refers to a record by a **material reference**: `{"id": "<namespace>/<local id>",
   "version": "1.2.0", "content_hash": "sha256:..."}`. A reader resolves it against the records it was given
   (a case file supplies them; `read_side_contract.md` section 1), compares the resolved record's stated hash
   (and, with the hash suite, its recomputed hash) with the reference's, and refuses a difference
   (`pin_mismatch`), when no record with that identifier and
   version was given (`absent`), or when the record is of a type it cannot read (`unknown_type`). [SC-003]
4. Lengths and coordinates in plain scene documents are in metres, in the scene's frame, right-handed.
   [SC-004]
5. Scene documents carry no content hash member. A consumer that records one serialises the whole document by
   RFC 8785 and hashes it with SHA-256, excluding nothing. [not yet covered]
6. Region and domain names match `[a-z0-9_]+`. `background` is reserved and never names a region. [RC-090]

## 2. Scene operations

Every operation returns a result as `read_side_contract.md` section 2 defines it (`status`, `reasons`,
`value`). A conformance case calls one of them.

| Operation | Value |
|---|---|
| `owner(point)` | the name of the region that owns the point, or `background` (section 3.2) |
| `domain_regions(name)` | the domain's region names, and whether it includes the background (section 3.3) |
| `in_domain(point, name)` | `true` or `false` (section 3.3) |
| `intervals(path)` | the layered path's intervals in order, each with its start, end, thickness and material reference (section 4) |
| `material_at(path, s)` | the material reference at distance `s` along the path (section 4) |
| `label_material(crosswalk, number or name, anatomy)` | the material reference for a label (section 5) |

A read of a field at a point resolves the point's material through `owner`, then reads the field as
`read_side_contract.md` says. [SC-005]

## 3. The scene manifest

```json
{
  "scene_schema_version": "0.1.0",
  "document_type": "scene_manifest",
  "regions": [
    {"name": "tissue",
     "material": {"id": "vesalius/VES-MAT-0003", "version": "1.0.0", "content_hash": "sha256:..."},
     "priority": 10,
     "geometry": {"primitive": "cylinder", "centre": [0, 0, 0], "axis": [0, 0, 1],
                  "radius": 0.01, "length": 0.05}},
    {"name": "lumen",
     "material": {"id": "vesalius/VES-MAT-0004", "version": "1.0.0", "content_hash": "sha256:..."},
     "priority": 20,
     "geometry": {"uri": "lumen.stl", "format": "stl", "metres_per_unit": 0.001,
                  "sha256": "9f2c..."}}
  ],
  "background": {
    "material": {"id": "vesalius/VES-MAT-0001", "version": "1.0.0", "content_hash": "sha256:..."}},
  "domains": {"flow": ["lumen"], "xray": ["tissue", "lumen", "background"]},
  "interfaces": [
    {"regions": ["lumen", "tissue"],
     "record": {"id": "vesalius/VES-INT-0001", "version": "1.0.0", "content_hash": "sha256:..."}}]
}
```

### 3.1 Regions

1. A region has a `name`, unique in the manifest, a `material` reference and a `geometry`, and optionally a
   `priority` and an `orientation`. Every name in a domain's list is a region of the manifest or `background`.
   [RC-091]
2. `geometry` is an **analytic primitive** or an **external reference**. A point is inside a primitive when
   (all in metres, `a`, `n` unit vectors, `d = p - centre`):
   - `sphere` (`centre`, `radius`): `d·d <= radius²`;
   - `cylinder` (`centre` at the middle of its axis, `axis`, `radius`, `length`): with `t = d·a`,
     `abs(t) <= length / 2` and `d·d - t² <= radius²`;
   - `slab` (`point` on its mid-plane, `normal`, `thickness`): `abs((p - point)·n) <= thickness / 2`.
   A point on a surface is inside. The tests use squared distances and no square roots, in IEEE 754 double
   precision, in the order written; case points are exactly representable. [SC-006] [SC-007] [RC-092]
3. An external reference is `{"uri", "format", "metres_per_unit"}`, with an optional `sha256` of the file's
   bytes. Vesalius never parses an external geometry file: its inside test is supplied by the consumer, and a
   reader with none gives `not_met` (`geometry_unresolved`). Where `sha256` is present, whoever opens the file
   checks its bytes and refuses a mismatch (`geometry_hash_mismatch`). `metres_per_unit` states the file's
   length unit and is required. [SC-008] [RC-093]

### 3.2 Who owns a point

1. `priority`, where authored, is an integer. A point that one region claims belongs to that region. [SC-009]
2. A point that several regions claim belongs to the claimant with the strictly highest priority. If any
   claimant has no authored priority, or the highest priority is tied, `owner` gives `not_met`
   (`owner_ambiguous`). There is no default from nesting, from the order of `regions`, or from any hierarchy.
   [SC-010] [SC-011]
3. A point that no region claims belongs to the `background`, if the scene declares one. Without one, `owner`
   gives `not_met` (`no_material`). [SC-012]

### 3.3 Domains

1. `domains` maps a domain name to a list of region names. `domain_regions` and `in_domain` give `not_met`
   (`domain_undeclared`) for a name the manifest does not declare: there is no default domain, a domain of one
   region included, and a reader never infers one from which sections the regions' materials have. [SC-013]
   [SC-014]
2. The reserved name `background` in a domain's list puts the background inside that domain: points no region
   claims then belong to the domain, and mixing where a region meets the background is mixing inside it. A
   domain that does not list it excludes those points. [SC-015]
3. A domain is the consumer's declaration of where a model computes (`declarations.md`). Requirements are
   checked over its regions only, and at its edge a model gets geometry and interface records, never an
   average of the materials on either side (`declarations.md`, `mixing_rules.md`).
4. A domain that changes during a run is out of scope in 0.1.0 (AD 5.1).

### 3.4 Orientation

1. `orientation` is `{"quaternion": [w, x, y, z], "frame": "scene"}`: a unit quaternion (norm within 1e-12 of
   one) that rotates the material's principal axes into the frame named. `scene` is the only frame token in
   0.1.0. [RC-094]
2. A read of a direction-dependent value (one whose conditions include a direction condition) in a region with
   no orientation gives `not_met` (`orientation_missing`). Schema 0.1.0 has no direction condition; the first
   arrives with the acoustic section, and this case with it. [SC-016]

### 3.5 Interface bindings

`interfaces` binds an interface record to a pair of distinct regions. In 0.1.0 the `interface` record type is
reserved (`record_format.md` section 3), so using an interface binding gives `not_met` (`unknown_type`). The
shape is fixed now so that manifests do not change when the type arrives. [SC-017] [RC-095]

### 3.6 Other representations

In 0.1.0 a manifest holds regions only. `precedence` (the representations from strongest to weakest, with the
tokens `field_override`, `label_volume` and `region`), `label_volumes` and `field_overrides` are planned with
their first consumer (AD 12.1, A1); a 0.1.0 reader gives `not_met` (`representation_unsupported`) for every
operation on a manifest that holds any of them, so a point they would claim is never read from a region
instead. [SC-018] Their planned shapes:

- a label volume is `{"name", "volume": <external reference>, "crosswalk": <label crosswalk, inline or as an
  external reference>}`; [not yet covered]
- a field override is a sampled table over space for one field: `{"field": "<section>.<field>", "unit",
  "volume": <external reference>, "frame", "conditions", "provenance", "statistics"}`, following the rules of
  a value field (`record_format.md` sections 4.2 and 5). Its provenance names the calibration that produced
  it, or says it has none. `frame` is `scene` or `reference_configuration:<region name>`, and a declaration
  that binds a `scene`-frame override to a region the consumer deforms is refused. [not yet covered]
- with more than one representation, a point that two claim and no declared `precedence` orders is refused;
  there is no default order. [not yet covered]

## 4. Layered paths

```json
{
  "scene_schema_version": "0.1.0",
  "document_type": "layered_path",
  "name": "needle_path",
  "entry_point": [0.0, 0.0, 0.0],
  "direction": [0.0, 0.0, 1.0],
  "intervals": [
    {"thickness": 0.002,
     "material": {"id": "vesalius/VES-MAT-0010", "version": "1.0.0", "content_hash": "sha256:..."}},
    {"thickness": 0.010,
     "material": {"id": "vesalius/VES-MAT-0011", "version": "1.0.0", "content_hash": "sha256:..."}},
    {"thickness": 0.015,
     "material": {"id": "vesalius/VES-MAT-0012", "version": "1.0.0", "content_hash": "sha256:..."}},
    {"thickness": 0.003,
     "material": {"id": "vesalius/VES-MAT-0011", "version": "1.0.0", "content_hash": "sha256:..."}},
    {"thickness": 0.002,
     "material": {"id": "vesalius/VES-MAT-0010", "version": "1.0.0", "content_hash": "sha256:..."}}
  ],
  "lateral_homogeneity": "assumed"
}
```

The five intervals are skin, fat, muscle, fat and skin: 2, 10, 15, 3 and 2 mm.

1. A layered path has a `name` matching `[a-z0-9_]+`, an `entry_point` and either a unit `direction` or a
   `curve` (an external reference, as
   in section 3.1, to the curve it was derived along). Thicknesses are positive, in metres in the plain form;
   on a USD stage, in the units of the layer that holds them, converted to metres before any sum
   (`usd_binding.md` sections 2 and 7). [RC-096]
2. `intervals` are ordered from the entry point. A material may appear in any number of intervals.
   `intervals(path)` returns them in order; a ray or beam consumer integrates over them and reads no point.
   [SC-019]
3. `lateral_homogeneity` is required, with the token `assumed`: the path declares that each layer is the same
   across the path's width. Every operation on a path that does not declare it gives `not_met`
   (`homogeneity_undeclared`). [SC-020]
4. Interval `i` spans `[S(i-1), S(i))`, half-open, where `S(0) = 0` and `S(i)` is the sum of the first `i`
   thicknesses, added from the first in IEEE 754 double precision. `material_at(path, s)` gives the material
   of the interval containing `s`; so `s` exactly at a boundary belongs to the interval after it, and a
   consumer that needs both sides of a boundary reads `intervals`. For `s < 0` or `s >= S(n)` it gives
   `not_met` (`outside_path`). [SC-021] [SC-022]
5. A layered path may carry `provenance` for its thicknesses (an anatomical atlas, an image), under the rules
   of `provenance.md`. [not yet covered]

## 5. Label crosswalks

1. A label crosswalk maps the labels of a reference anatomy to material references: `{"scene_schema_version":
   "0.1.0", "document_type": "label_crosswalk", "anatomy": {"name", "version"}, "labels": {"5": {"material":
   {...}}, "6": {"material": {...}}}}`. `anatomy` names the segmenter or atlas, and its version, whose label
   numbers the crosswalk uses. A label MAY also carry `name`, that vocabulary's own name for it, and an
   `uberon` identifier. Names are unique within a crosswalk after Unicode case folding, and never consist of
   digits only. [RC-097]
2. `label_material` gives `not_met` (`label_unmapped`) for a label the crosswalk does not map. [SC-023]
3. `label_material` takes a label's `number` or its `name`, never both (`request_incomplete`), and the
   `anatomy` (`{"name", "version"}`) the caller's labels come from. A name is matched exactly. An anatomy
   other than the crosswalk's gives `not_met` (`anatomy_mismatch`), because label numbers and names belong to
   one segmenter or atlas. Tools such as Isaac for Healthcare's patient twin identify a structure by its
   segmenter's name, hence the name. Codes are never joined across vocabularies: TotalSegmentator's SNOMED
   mapping codes the liver 10200004, while UBERON's cross-reference for the liver is 181268008 (ecosystem
   survey, 2026-10-12). [SC-024] [SC-025]

## 6. What is not represented in 0.1.0

Thin structures thinner than a voxel (a shell with a thickness), orientation fields that vary in space, and
domains that change during a run have no representation yet (AD 5.1, 13). Label crosswalks, interface bindings
and the representations of section 3.6 have no USD form in 0.1.0 (`usd_binding.md` section 8).

## Cases

| Case | Suite | Tests |
|---|---|---|
| SC-001 | scene documents | a scene document is never listed as a record |
| SC-002 | scene documents | `scene_schema_version` under the version rules; a malformed document gives `malformed` |
| SC-003 | scene documents | a material reference whose resolved hash differs is refused (`pin_mismatch`); a missing record gives `absent` |
| SC-004 | scene documents | plain lengths are metres in the scene frame |
| SC-005 | scene documents | a read at a point resolves its material through `owner` |
| SC-006 | scene documents | the three primitives' inside tests, points inside, outside and on each surface |
| SC-007 | scene documents | a cylinder's extent is half its length either side of its centre; a slab's half its thickness |
| SC-008 | scene documents | an external geometry: no inside test gives `geometry_unresolved`; bytes that do not match `sha256` refused |
| SC-009 | scene documents | a point one region claims belongs to it |
| SC-010 | scene documents | the owner of a point in nested regions with authored priorities |
| SC-011 | scene documents | two claimants with no or tied priority give `owner_ambiguous` |
| SC-012 | scene documents | an unclaimed point takes the background, or gives `no_material` without one |
| SC-013 | scene documents | an undeclared domain, a one-region domain included, gives `domain_undeclared` |
| SC-014 | scene documents | a region whose material has a fluid section is in no domain unless listed |
| SC-015 | scene documents | the background inside a domain that lists it, outside one that does not |
| SC-016 | scene documents | a direction-dependent value with no orientation gives `orientation_missing` (planned with the acoustic section) |
| SC-017 | scene documents | using an interface binding gives `unknown_type` in 0.1.0 |
| SC-018 | scene documents | a manifest holding `precedence`, label volumes or field overrides gives `representation_unsupported` |
| SC-019 | scene documents | a layered path with a repeated material (skin, fat, muscle, fat, skin), read with `intervals` |
| SC-020 | scene documents | a layered path with no `lateral_homogeneity` gives `homogeneity_undeclared` |
| SC-021 | scene documents | `material_at` at each boundary gives the interval after it |
| SC-022 | scene documents | `material_at` before the entry point and at the path's end gives `outside_path` |
| SC-023 | scene documents | an unmapped label gives `label_unmapped` |
| SC-024 | scene documents | a label read by its name gives the material of its number; an unknown name gives `label_unmapped`; a read naming both is refused (`request_incomplete`) |
| SC-025 | scene documents | a read with another anatomy gives `anatomy_mismatch` |
| RC-090 | record checks | a name outside `[a-z0-9_]+`, or a region named `background`, flagged |
| RC-091 | record checks | duplicate region names, or a domain naming no such region, flagged |
| RC-092 | record checks | a malformed primitive, or a non-unit axis or normal, flagged |
| RC-093 | record checks | an external reference without `metres_per_unit` flagged |
| RC-094 | record checks | a non-unit quaternion or an unknown frame token flagged |
| RC-095 | record checks | an interface binding that does not name two distinct regions flagged |
| RC-096 | record checks | a non-unit direction or a non-positive thickness flagged |
| RC-097 | record checks | a label crosswalk with malformed material references, two names that fold to one, or an all-digit name, flagged |

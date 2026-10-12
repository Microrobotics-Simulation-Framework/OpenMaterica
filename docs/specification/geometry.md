# Geometry

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 3.5 (rule 3), 5.1 and
5.2. The USD form of everything here is in `usd_binding.md`.

## 1. Scene documents

1. A scene document describes a scene, not a substance. It is not a record: it has no `record_type`, and a
   reader that lists records never lists it. [PR-250]
2. Every scene document is one JSON object with `scene_schema_version` (the schema version it was written
   against, `MAJOR.MINOR.PATCH`, read under the rules of `record_format.md` section 8) and `document_type`:
   `scene_manifest`, `layered_path` or `label_mapping`. [PR-251]
3. A scene document refers to a record by a **material reference**:
   `{"id": "<namespace>/<local id>", "version": "1.2.0", "content_hash": "sha256:..."}`. A reader resolves it
   to the record with that identifier and version, and refuses when the record's content hash differs, or
   when the record is of a type it cannot read (`record_format.md` section 3). [PR-252]
4. Lengths in plain scene documents are in metres; coordinates are in the scene's frame, right-handed.
   [PR-253]
5. Scene documents carry no content hash member. A consumer that records one computes it as
   `record_format.md` section 9 does, over the whole document.

## 2. The scene manifest

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
     "geometry": {"uri": "lumen.stl", "format": "stl", "metres_per_unit": 0.001}},
    {"name": "cortex",
     "material": {"id": "vesalius/VES-MAT-0009", "version": "1.0.0", "content_hash": "sha256:..."},
     "priority": 30,
     "geometry": {"uri": "bone.vtk", "format": "vtk", "metres_per_unit": 1.0},
     "orientation": {"quaternion": [1, 0, 0, 0], "frame": "scene"}}
  ],
  "background": {
    "material": {"id": "vesalius/VES-MAT-0001", "version": "1.0.0", "content_hash": "sha256:..."}},
  "domains": {"flow": ["lumen"], "xray": ["tissue", "lumen", "cortex", "background"]},
  "precedence": ["region"],
  "interfaces": [
    {"regions": ["lumen", "tissue"],
     "record": {"id": "vesalius/VES-INT-0001", "version": "1.0.0", "content_hash": "sha256:..."}}]
}
```

### 2.1 Regions

1. A region has a `name`, unique in the manifest, a `material` reference, and a `geometry`. Every name in a
   domain's list is a region of the manifest or `background`. [RC-090]
2. `geometry` is either an **analytic primitive** in metres (`sphere`: `centre`, `radius`; `cylinder`:
   `centre`, `axis`, `radius`, `length`; `slab`: `point`, `normal`, `thickness`), or an **external reference**
   `{"uri", "format", "metres_per_unit"}` that the consumer resolves in its own code. Vesalius never reads an
   external geometry file; `metres_per_unit` states the file's length unit and is required. [PR-254] [RC-091]
3. Whether a point is inside a region is decided by its geometry: exactly for primitives, by the consumer for
   external references. A point on a region's surface is inside it. [PR-255]

### 2.2 Who owns a point

1. `priority`, where authored, is an integer. A point that one region claims belongs to that region.
2. A point that several regions claim belongs to the claimant with the strictly highest priority. If any
   claimant has no authored priority, or the highest priority is tied, the reader refuses for that point.
   There is no default from nesting, from the order of `regions`, or from any hierarchy. [PR-256] [PR-257]
3. A point that no region claims belongs to the `background`, if the scene declares one. Without one, it has
   no material, and a consumer that needs one there refuses. [PR-258]

### 2.3 Domains

1. `domains` maps a domain name to a list of region names. Every domain a consumer uses is declared here,
   including a domain of one region; there is no default domain. [PR-259]
2. The reserved name `background` in a domain's list puts the background inside that domain: points no region
   claims then belong to the domain, and mixing where a region meets the background is mixing inside it. A
   domain that does not list it excludes those points. [PR-260]
3. A domain is a set of regions in which a consumer's model computes. It is the consumer's declaration
   (`declarations.md`); a reader never infers one from which sections the regions' materials have. [PR-261]
4. Requirements are checked over a domain's regions only, and at a domain's edge a model gets geometry and
   interface records, never an average of the materials on either side (`declarations.md`,
   `mixing_rules.md`).
5. A domain that changes during a run is out of scope in 0.1.0 (AD 5.1).

### 2.4 Orientation

1. `orientation` is `{"quaternion": [w, x, y, z], "frame": "scene"}`: a unit quaternion that rotates the
   material's principal axes into the frame named. `scene` is the only frame token in 0.1.0. [RC-092]
2. A reader refuses a direction-dependent value (one whose conditions include `propagation_direction` or
   `specimen_orientation`) for a region with no orientation. [PR-262]

### 2.5 Precedence among representations

Where a scene uses more than one representation (region bindings, label volumes, field overrides),
`precedence` lists them from strongest to weakest, with the tokens `field_override`, `label_volume` and
`region`. A reader refuses a point that two representations claim when the manifest declares no precedence.
There is no default order. [PR-263]

### 2.6 Interface bindings

`interfaces` binds an interface record to a pair of distinct regions. In 0.1.0 the `interface` record type is
reserved (`record_format.md` section 3), so a reader refuses every interface binding it is asked to use; the
shape is fixed now so that manifests do not change when the type arrives. [PR-264] [RC-093]

## 3. Layered paths

```json
{
  "scene_schema_version": "0.1.0",
  "document_type": "layered_path",
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

1. A layered path has an `entry_point` and either a unit `direction` or a `curve` (an external reference, as
   in section 2.1, to the curve it was derived along). Thicknesses are in metres and positive. [RC-094]
2. `intervals` are ordered from the entry point. A material may appear in any number of intervals.
   [PR-265]
3. `lateral_homogeneity` is required, with the token `assumed`: the path declares that each layer is the same
   across the path's width. A reader refuses a path that does not declare it. [PR-266]
4. The material at distance `s` along the path is the material of the interval containing `s`. A reader
   refuses exactly at a boundary between intervals (an edge, `record_format.md` section 6), and beyond the
   last interval. [PR-267]
5. A layered path may carry `provenance` for its thicknesses (an anatomical atlas, an image), under the rules
   of `provenance.md`. [not yet covered]

## 4. Label mappings and label volumes

1. A label mapping maps the labels of a reference anatomy to material references: `{"document_type":
   "label_mapping", "anatomy": {"name": "...", "version": "..."}, "labels": {"5": {"material": {...}}, "6":
   {"material": {...}}}}`. A label may also carry an `uberon` identifier. [RC-095]
2. A reader refuses a point whose label the mapping does not map. [PR-268]
3. In a manifest, a label volume is `{"name", "volume": <external reference>, "mapping": <label mapping,
   inline or as an external reference>}` under `label_volumes`. Its sampling into volume fractions is the
   consumer's, or Vesalius's L5 (AD 3.2). [not yet covered]

## 5. Field overrides

1. A field override is a sampled table over space for one field, under `field_overrides` in a manifest:
   `{"field": "<section>.<field>", "unit": "...", "volume": <external reference>, "frame": "scene",
   "provenance": {...}, "statistics": {...}}`. It follows the rules of a value field (`record_format.md`
   sections 4.2 and 5): its unit is the field's registered unit, and its provenance names the calibration that
   produced it, or says it has none. [RC-096]
2. `frame` is `scene` or `reference_configuration:<region name>`. A reader refuses to move a `scene`-frame
   field with a deforming region. [PR-269]

## 6. What is not represented in 0.1.0

Thin structures thinner than a voxel (a shell with a thickness), orientation fields that vary in space, and
domains that change during a run have no representation yet (AD 5.1, 13).

## Cases

| Case | Profile | Tests |
|---|---|---|
| PR-250 | plain read | a scene document is never listed as a record |
| PR-251 | plain read | `scene_schema_version` read under the record version rules; another major refused |
| PR-252 | plain read | a material reference whose hash differs from the record's is refused |
| PR-253 | plain read | plain lengths are metres in the scene frame |
| PR-254 | plain read | the three primitives, in metres; an external reference without `metres_per_unit` refused |
| PR-255 | plain read | a point on a primitive's surface is inside it |
| PR-256 | plain read | the owner of a point in nested regions with authored priorities |
| PR-257 | plain read | two claimants with no or tied priority refused |
| PR-258 | plain read | an unclaimed point takes the background, or has no material without one |
| PR-259 | plain read | no default domain; a single-region domain must be declared |
| PR-260 | plain read | the background inside a domain that lists it, outside one that does not |
| PR-261 | plain read | a domain is never inferred from sections |
| PR-262 | plain read | a direction-dependent value for a region with no orientation refused |
| PR-263 | plain read | overlapping representations with no declared precedence refused |
| PR-264 | plain read | an interface binding refused in 0.1.0 |
| PR-265 | plain read | a layered path with a repeated material (skin, fat, muscle, fat, skin) |
| PR-266 | plain read | a layered path with no `lateral_homogeneity` refused |
| PR-267 | plain read | a read at an interval boundary, or beyond the last interval, refused |
| PR-268 | plain read | an unmapped label refused |
| PR-269 | plain read | a scene-frame field override on a deforming region refused |
| RC-090 | record checks | duplicate region names, or a domain naming no such region, flagged |
| RC-091 | record checks | malformed primitives, and external references without `metres_per_unit`, flagged |
| RC-092 | record checks | a non-unit quaternion or an unknown frame token flagged |
| RC-093 | record checks | an interface binding that does not name two distinct regions flagged |
| RC-094 | record checks | a non-unit direction or a non-positive thickness flagged |
| RC-095 | record checks | a label mapping with malformed material references flagged |
| RC-096 | record checks | a field override without provenance, unit or frame flagged |

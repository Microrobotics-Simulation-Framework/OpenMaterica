# USD binding

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 5.3 to 5.5. The plain
forms this binds are in `record_format.md` and `geometry.md`; section 8 lists the plain cases with no USD form
in 0.1.0. Every read gives a result as `read_side_contract.md` defines it.

## 1. Schemas, and what a reader needs

1. Vesalius's USD schemas are resource-only: `schema.usda` is the source, and `generatedSchema.usda` and
   `plugInfo.json` are the registered form, with `schemaIdentifier` in the plug-in entry. Registering them is
   the writer's concern. [RC-109]
2. A reader reads Vesalius attributes by name and needs no plug-in. It detects an applied API schema by its
   name in the prim's composed `apiSchemas` (`UsdPrim.GetPrimTypeInfo().GetAppliedAPISchemas()`): without the
   plug-in, `HasAPI` and `GetAppliedSchemas()` omit unregistered schemas, so a reader using them would find no
   regions (checked with USD 0.26.5). [UR-014] In 0.1.0 the single-apply API schemas are
   `VesaliusBulkAPI`, `VesaliusFluidAPI`, `VesaliusMagneticAPI`, `VesaliusBiocompatibilityAPI` (one per
   section of `record_format.md` section 4.1), `VesaliusRegionAPI` and `VesaliusSceneAPI`; the typed schemas
   are `VesaliusOverlay` and `VesaliusLayeredPath`. The names `VesaliusAcousticAPI`,
   `VesaliusRadiologicalAPI`, `VesaliusMechanicalAPI`, `VesaliusOpticalAPI`, `VesaliusThermalAPI` and
   `VesaliusDielectricAPI` are reserved. [not yet covered]
3. No attribute in these schemas has a fallback value a reader may use. A reader refuses a **value-bearing**
   attribute that has no authored value (USD's `HasAuthoredValue`), with the reason `unauthored_attribute`:
   every field attribute (section 3.2), every required envelope attribute (section 3.3), and every attribute
   this document marks required. [UR-002]
4. These attributes may be absent, and their absence has a stated meaning: `vesalius:card` and
   `vesalius:extensions` (none); `vesalius:region:priority` (no priority); `vesalius:region:orientation`
   (no orientation; `vesalius:region:orientationFrame` is required when it is present);
   `vesalius:scene:background` and `vesalius:scene:backgroundMaterial` (no background; both or neither);
   `vesalius:domain:<name>:includesBackground` (false); one of `vesalius:path:direction` and
   `vesalius:path:curve` (the other is used). [UR-031]
5. **Instances.** A reader finds regions, domain members and layered paths with instance proxies traversed
   (`Usd.TraverseInstanceProxies()`), and identifies a region by its path on the stage, an instance proxy's
   included. Every instance of a prototype carries the prototype's regions and bindings. The default traversal
   skips them (checked with USD 0.26.5). [UR-038]
6. **Time samples.** A Vesalius attribute with time samples is refused (`time_sampled`): a reader reads the
   default value, while a tool reading at a time code reads the sample (checked). [UR-039]

## 2. Units

1. **Values are SI whatever the stage says.** A Vesalius field's value is in its registered unit
   (`record_format.md` section 4.2), whatever the stage's `metersPerUnit` or `kilogramsPerUnit`. The field's
   JSON carries its `unit`, and a reader checks it. A value referenced from an SI library layer into a stage
   in centimetres arrives unchanged (checked with USD 0.26.5). [UR-003]
2. **Geometry is in the units of the layer that holds it.** Points, primitives' dimensions, entry points and
   layered-path thicknesses are lengths in the `metersPerUnit` of the layer that holds the strongest opinion
   on the attribute (for a mesh, on `points`). This rule is stated once, here, for every geometry attribute.
3. A reader refuses a stage with no authored `metersPerUnit`, with the reason `stage_units_unauthored`, for
   every read from it: USD's fallback is centimetres (checked). [UR-004]
4. USD does not rescale a referenced layer to the stage's units. Where the layer holding a geometry attribute
   has a `metersPerUnit` other than the stage's, a reader uses it only when the prim's local-to-world
   transform compensates exactly: its 3×3 part is a uniform scale `k` (the cube root of its determinant) times
   a rotation (each column's norm within 1e-9 relative of `k`, the columns orthogonal within 1e-9), and `k`
   equals that layer's `metersPerUnit` divided by the stage's within 1e-9 relative. Otherwise it refuses the
   region or path, with the reason `units_uncompensated`. [UR-005]
5. **Copies an engine reads are written by an engine adapter, never shipped** (section 10).

## 3. Material prims

1. A **Vesalius material** is a `UsdShade.Material` prim carrying `vesalius:id`, with the API schemas of its
   sections applied. [UR-007]
2. **One JSON string per field, and nothing beside it.** A field is the attribute
   `vesalius:<section>:<field>`, of type `string`, holding the field's plain form (`record_format.md` section
   5, alternatives included) serialised by RFC 8785. No other attribute carries any part of a field's value. A
   section's shared specimen facts are the string attribute `vesalius:<section>:specimen`; `specimen` is a
   reserved field name for this reason (`record_format.md` section 4.1). [UR-008] [RC-100]
3. **The envelope on the prim.** The record's envelope members are string attributes on the material prim:
   `vesalius:schema_version`, `vesalius:record_type`, `vesalius:id`, `vesalius:version`, `vesalius:name`,
   `vesalius:licence` (the object as JSON), `vesalius:content_hash`, and, where present, `vesalius:card` and
   `vesalius:extensions` (as JSON). [UR-009]
4. **Reserved names.** `region`, `scene`, `domain`, `overlay`, `path` and `inputSheet` are never section
   names, because `vesalius:<word>:...` attributes with these words belong to the scene (sections 5 to 7).
   [RC-111]
5. **Reassembly.** A reader rebuilds the plain record from a material prim: the envelope from the attributes
   of item 3; then every attribute `vesalius:<section>:<field>` whose `<section>` is not a reserved name and
   not an envelope member, each parsed as JSON into `body.sections.<section>.fields.<field>`, with
   `vesalius:<section>:specimen` parsed into `body.sections.<section>.specimen`; `vesalius:extensions` into
   `body.extensions`. Sections it does not know are kept, so that the hash covers them. [UR-010]
6. **The hash.** Every reader compares `vesalius:content_hash` with the hash a region, a background or a path
   pins, and refuses a difference (`pin_mismatch`, sections 5 and 7). A reader with the hash profile also
   recomputes the reassembled record's hash as `record_format.md` section 9 says, and refuses the material
   when it differs from `vesalius:content_hash` (`hash_mismatch`). So a field edited in a stronger layer
   without rewriting `vesalius:content_hash` is refused; a stronger layer that edits both composes a
   consistent, different record, which only a pin catches. A reader that does not claim the hash profile
   labels its results `hash_not_checked` (`read_side_contract.md` section 3). [UR-011] [UR-032]
7. **Prim names carry no identity.** A reader identifies a material by `vesalius:id`, never by its prim's name
   or path; `VES-MAT-0001` is not a valid prim name (checked). [UR-012]
8. A material prim whose `vesalius:record_type` is a type the reader cannot read is skipped when listing
   material prims and refused when a binding or a relationship targets it (`unknown_type`,
   `record_format.md` section 3). [UR-013]

## 4. Shipped layers

1. A layer generated for a release holds no composition arcs (sublayers, references, payloads) and no asset
   paths; an aggregate layer is flattened. [RC-101]
2. Library materials live under a scope of their own (`/VesaliusLibrary/...`), never under
   `/Materials/<name>`, where they would merge with display materials of the same name. [RC-102]
3. Shipped layers do not apply `UsdPhysics.MaterialAPI` (section 10). [RC-103]
4. A generated layer authors `metersPerUnit = 1`, `kilogramsPerUnit = 1` and `upAxis = "Z"` as layer
   metadata. Isaac Sim and SimReady's validators expect Z-up; a library layer holds no geometry, so the axis
   changes nothing a reader reads. [RC-104]

## 5. Regions, bindings and scenes

1. **Region marker.** A region is a prim with `VesaliusRegionAPI` applied. Its attributes are
   `vesalius:region:material` (required: the material reference, `{"id", "version", "content_hash"}` as JSON),
   `vesalius:region:priority` (`int`), `vesalius:region:orientation` (`quatd`, real part first, unit within
   1e-12) and `vesalius:region:orientationFrame` (`token`, `scene`). [UR-014]
2. **Region geometry.** A region's geometry is the region prim, if it is a `UsdGeom.Gprim`, and its descendant
   `UsdGeom.Gprim`s, whose computed purpose (`UsdGeom.Imageable.ComputePurpose()`) is `default`. The walk
   stops at a nested region: its prims belong to it. Prims with computed purpose `render`, `proxy` or `guide`
   add nothing. [UR-015]
3. **Binding.** A region's material is the target of the `vesalius`-purpose binding authored on the region's
   prim (`UsdShade.MaterialBindingAPI`, relationship `material:binding:vesalius`), and a writer applies
   `MaterialBindingAPI` to that prim. The `physics` purpose is the engines' (item 9). A reader never calls
   `ComputeBoundMaterial`: where no `vesalius` binding is authored it falls back to the all-purpose binding,
   usually a display material (checked with USD 0.26.5), and `bindingStrength` would decide what a reader
   reads. The target's envelope must match `vesalius:region:material`, or the region is refused
   (`pin_mismatch`). A relationship authored with no targets counts as no binding (`binding_missing`); one
   with more than one target is refused (`binding_refused`); USD resolves neither (checked). [UR-016] [UR-017]
   [UR-020]
4. **Refused bindings.** A reader refuses the region, with every read that resolves to it, in each of these
   cases; the stage and the other regions stay readable:
   - the region's prim has no authored `vesalius`-purpose binding (`binding_missing`); [UR-017]
   - the binding's target carries no `vesalius:id` (`binding_refused`); [UR-018]
   - any prim inside the region, the region's own prim included, carries an all-purpose binding to a Vesalius
     material, direct or through a collection (`material:binding:collection:<name>`), or a `vesalius`-purpose
     collection binding (`material:binding:collection:vesalius:<name>`, checked) (`binding_refused`);
     [UR-020]
   - a prim inside the region that is not itself a region, a `UsdGeom.Subset` included, carries a
     `vesalius`-purpose binding to a different material from the region's own, compared by envelope
     (`vesalius:id`, `vesalius:version`, `vesalius:content_hash`) (`binding_refused`): there are no
     per-element Vesalius materials in 0.1.0. [UR-021]

   A region whose only binding is an all-purpose one to a Vesalius material matches the first and third
   cases, and both codes are reported.
   The reason codes are those of `read_side_contract.md` section 4.
5. A region's binding applies to its own geometry (item 2) and never across into a nested region; a nested
   region carries its own binding. [UR-022]
6. **Scene.** `VesaliusSceneAPI` is applied to the prim that declares a scene's domains. Its attributes are
   `vesalius:scene:background` (a relationship to a material prim) with `vesalius:scene:backgroundMaterial`
   (its material reference as JSON, checked like a region's), and, per domain,
   `vesalius:domain:<name>:includesBackground` (`bool`). [UR-023]
7. **Domains.** A domain is a `UsdCollectionAPI` instance on the scene prim, named `vesalius_domain_<name>`,
   with `<name>` matching `[a-z0-9_]+` (`geometry.md` section 1), so its properties are
   `collection:vesalius_domain_<name>:...`. A collection's membership includes descendants, so a reader takes
   from it only the prims that carry `VesaliusRegionAPI`, with instance proxies traversed (section 1 item 5).
   The collection's paths resolve relative to the scene prim, so a scene referenced into another keeps its
   domains. [UR-024]
8. The rules on owning a point, the background, domains and orientation are those of `geometry.md` section 3,
   applied to the composed stage; its scene cases exist in USD form, except those section 8 lists. [UR-025]
9. **Engine bindings are the engines'.** A `physics`-purpose binding, direct or through a collection, of any
   strength, on the region's prim, on a prim or subset inside it, or above it, belongs to an engine: a reader
   neither reads it nor refuses on it, and the region stays readable. NVIDIA's tools write that slot, and a
   mesh may need a rigid and a deformable engine material, or one per subset, which a slot shared with
   Vesalius could not hold (AD 5.4). The stage check sets the two side by side (section 9). [UR-037]
10. **Unloaded payloads.** What an unloaded payload holds is not on the stage, so a reader refuses, with the
    reason `payload_unloaded`, a point read on a stage that holds one, a read over a domain whose collection
    includes a path under one, and a read of a region whose subtree holds one (checked: the region's geometry
    is empty while it is unloaded). [UR-040]
11. **Point instancers.** A region under a prim that a `UsdGeom.PointInstancer`'s `prototypes` relationship
    targets is refused (`region_in_prototype`): a prototype is drawn and simulated only where it is
    instanced, never at its own place. [UR-041]
12. **Broken regions.** A prim that carries a `vesalius:region:` attribute without `VesaliusRegionAPI` in its
    composed `apiSchemas` is a refused region (`binding_refused`): a point inside its geometry, taken as item
    2 says, is refused, never given to an enclosing region or the background. A stronger layer that deletes
    the schema leaves the binding and the attribute behind (checked). A `vesalius` binding alone on a
    non-region prim is judged by item 4 inside a region (a binding to the region's own material is redundant
    and readable) and reported by the stage check outside every region. [UR-042] [UR-021]

## 6. Overlays and the input sheet

1. An overlay record is a `VesaliusOverlay` prim carrying the envelope attributes of section 3.3,
   `vesalius:overlay:purpose` (`token`), the relationship `vesalius:overlay:base` to its base material prim
   for navigation, `vesalius:overlay:baseRecord` (the base's `{"id", "version", "content_hash"}` as JSON),
   `vesalius:overlay:scope` (the scope as JSON), and the replaced fields as
   `vesalius:<section>:<field>` string attributes, each with its own `specimen` inside it. The plain overlay
   is reassembled from these as section 3.5 says, and its hash checked as section 3.6 says. [UR-026]
2. A reader applies an overlay only when the consumer declares it, and refuses it by `record_format.md`
   section 4.4: a base whose envelope differs from `vesalius:overlay:baseRecord` (`overlay_base_mismatch`),
   two declared overlays on one field (`overlay_conflict`). The scope is compared by the build
   (`declarations.md` section 5). [UR-027] [UR-028]
3. An overlay never edits its base prim's attributes: the base's own hash still verifies with the overlay on
   the stage. [UR-029]
4. **The material input sheet.** A consumer that saves its run on a stage writes the material input sheet
   (`declarations.md`) as one JSON string attribute, `vesalius:inputSheet`, on the scene prim whose domains it
   used, or, where it used no scene on the stage, on the stage's default prim. MADDENING-based consumers place
   that prim beside their graph layers. The sheet is R7, planned with Vesalius 0.2 (AD 12.1), and its case
   with it. [UR-030]

## 7. Layered paths

```usda
def VesaliusLayeredPath "NeedlePath"
{
    point3d vesalius:path:entryPoint = (0, 0, 0)
    vector3d vesalius:path:direction = (0, 0, 1)
    double[] vesalius:path:thicknesses = [0.2, 1.0, 1.5, 0.3, 0.2]
    rel vesalius:path:materials = [</VesaliusLibrary/Skin>, </VesaliusLibrary/Fat>, </VesaliusLibrary/Muscle>]
    string vesalius:path:materialRefs = '[{"id": "...", "version": "...", "content_hash": "..."}, ...]'
    int[] vesalius:path:materialIndices = [0, 1, 2, 1, 0]
    token vesalius:path:lateralHomogeneity = "assumed"
}
```

1. `vesalius:path:materials` targets the distinct materials the path uses, and `vesalius:path:materialRefs`
   holds their material references in the same order, each checked against its target's envelope
   (`pin_mismatch`). `vesalius:path:materialIndices` gives each interval's index into them. USD keeps a
   relationship's targets in order only when they are distinct and removes repeats (checked with USD 0.26.5:
   skin, fat, muscle, fat, skin reads back as three targets), so one target per interval would drop layers.
   [UR-033]
2. A reader refuses a path whose `thicknesses` and `materialIndices` differ in length, whose `materialRefs`
   and `materials` differ in length, or whose index falls outside `materials` (`path_arrays_mismatch`).
   [UR-034]
3. The entry point and thicknesses are lengths by section 2's layer rule; in the example the stage is in
   centimetres. A reader converts each thickness to metres first, multiplying it by its layer's
   `metersPerUnit`, and then takes the prefix sums of the metre values left to right, so a distance along the
   path is in metres and a boundary falls where it would in the plain form. A path may target a curve, through
   `vesalius:path:curve`, in place of a direction. The operations of `geometry.md` section 4 apply. [UR-035]
4. `vesalius:path:lateralHomogeneity` is required (`homogeneity_undeclared`, `geometry.md` section 4).
   [UR-036]

## 8. Plain cases with no USD form in 0.1.0

Label mappings and label volumes, field overrides and `precedence` (`geometry.md` sections 3.6 and 5),
interface bindings (`geometry.md` section 3.5), and external geometry references (`geometry.md` section 3.1:
on a stage, geometry is on the stage) have no USD form in 0.1.0. Label volumes and field overrides will use
`UsdVol` (`OpenVDBAsset`, `Field3DAsset`), specified with their first consumer (AD 12.1, A1), under three
constraints known now: a volume prim is a `Gprim` that renderers draw, so it sits outside region geometry
(outside every region, or with purpose `guide`); its field relationships are named
`field:vesalius:<name>`, never `field:density`, which a renderer reads as smoke (checked: a volume's field
relationships always take the `field:` prefix); and its asset paths are allowed in scene layers, never in
shipped ones (section 4). [not yet covered]

## 9. The stage check

`vesalius check --stage` reports, without changing the stage, the items below. It needs the engine profiles of
section 10 to recognise engine schemas and attributes.

A **shape** is a prim an engine simulates: a prim with `UsdPhysics.CollisionAPI`, or with a body API an engine
profile lists, found with instance proxies traversed. A shape belongs to the innermost region whose prim is
the shape or one of its ancestors, whatever the shape's purpose: a collider with purpose `guide` still
collides. A shape's **engine materials** are those OpenUSD's reference physics parser
(`UsdPhysics.UsdPhysicsLoadStageFromPrimRange`; `LoadUsdPhysicsFromRange` is its deprecated name) reports for
it, and, for a body API, the material `ComputeBoundMaterial("physics")` resolves on the prim its profile
names. The parser reports a binding inherited from an ancestor only when the shape has `MaterialBindingAPI`
applied (checked), and engines built on it behave the same, so the check follows the parser. To list materials
per subset, the check resolves each of the shape's `GeomSubset`s of family `materialBind` with
`ComputeBoundMaterial("physics")`. A material counts only if an engine's material API is in its composed
`apiSchemas` (section 1 item 2), so the fall-back to an all-purpose display material is not one. For an engine
material with no stamp, the check uses the held profile whose material APIs it carries; with none, or more
than one, its attributes are listed and its density is not compared. The check judges each shape, never the
region prim, because engines bind colliders and simulation meshes, not regions (checked with the reference
parser in the review of 2026-10-12).

1. a stage with no authored `metersPerUnit`, or with no authored `kilogramsPerUnit` where an engine attribute
   whose dimension includes mass is authored; [RC-105]
2. a layer holding geometry whose `metersPerUnit` differs from the stage's with no compensating transform
   (section 2 item 4); [RC-107]
3. a material prim whose content hash does not verify, or a region, background or path whose pinned reference
   does not match its target (section 3.6); [RC-108]
4. per shape, its region, the region's Vesalius material and its engine materials; [RC-112]
5. a shape whose **effective density** differs, by more than 1e-6 relative after conversion (section 10.3),
   from the stamped read's value where its engine material is stamped, else from its region's Vesalius bulk
   density when that is a constant; a table-valued density is not compared. The effective density follows
   `UsdPhysics`'s precedence: an authored `physics:density` from `UsdPhysics.MassAPI` on the shape or its
   nearest ancestor that has one, else the authored, non-zero density attribute its profile names on the
   engine material. An authored `physics:mass` makes the shape "not comparable", which is reported, not
   flagged; [RC-106]
6. a shape inside a region whose engine material, or a subset's, has no `vesalius:engineSource` (a foreign
   material, such as one Isaac Lab bound), names another material than the region's, compared by envelope, or
   was stamped for other stage units than the stage's; [RC-115]
7. a stamped engine material that does not re-derive: an attribute its profile lists that is not authored; an
   authored attribute in the profile's namespaces that the profile does not list; a stamped read request that,
   re-run against the stage's material prims, gives another value or a result that is neither `met` nor
   accepted; a written value that differs from its stamped SI value converted to the stage's units (section
   10.3) at its type's precision; or a stamped profile the check does not hold, or whose hash differs from
   the stamp's; [RC-118]
8. a shape inside a region with no engine material, or only a material bound to the physics scene prim, which
   PhysX uses as its default (recalled), so that the engine uses a material nobody converted from the
   region's; [RC-116]
9. a `vesalius`-purpose binding on a prim without `MaterialBindingAPI` applied (USD resolves it, with a
   warning; checked), or on a prim that is neither a region nor inside one; [RC-117]
10. an engine API, or an attribute in a namespace an engine profile lists or in `physics:`, on a prim that
    carries `vesalius:id` (section 10.4); [RC-114]
11. a time-sampled attribute on an engine material. [RC-119]

Items 5 to 8 also give a declared engine model's engine results, one per shape, after its adapter has
written (`declarations.md` section 2 item 6).

## 10. Engine materials and adapters

An engine never reads a Vesalius field: it reads typed attributes in its own schemas, in the units its profile
states. A Vesalius value reaches an engine only through an **engine adapter**, which writes engine materials
for a model the consumer declares. The adapter is in `vesalius-authoring`; the engine profiles are data in
`vesalius`, because the stage check needs them (AD 7.1). Adapters claim the profile EA.

### 10.1 Engine profiles

1. An engine profile describes what one engine version reads: `{"profile_schema_version": "0.1.0",
   "document_type": "engine_profile", "id": "<namespace>/<name>", "version", "engine": {"name", "version"},
   "units": {"convention", "source"}, "material_apis": [{"name", "attributes": [...]}], "body_apis":
   [{"name", "material_prim"}], "namespaces": [...]}`. [RC-140]
2. Each attribute is `{"name", "type", "dimension", "source", "engine_fallback", "doc"}`: `type`, its USD
   value type; `dimension`, the exponents `{"M", "L", "T"}` of its SI dimension, with time in seconds;
   `source`, either `{"field": "<section>.<field>"}` or `"declared"`; `engine_fallback`, the value the engine
   uses when the attribute is unauthored, in the engine's units, so that a reviewer sees what an omission
   would give; and `doc`, a locator (`provenance.md`) to the engine's own documentation of the attribute.
   [RC-140]
3. `units.convention` is `stage` (the engine reads lengths and masses in the stage's `metersPerUnit` and
   `kilogramsPerUnit`, and time in seconds) or `si`; `units.source` is a locator to the engine's documentation
   of it. A profile without one is invalid and the adapter refuses it (`engine_profile_invalid`): an engine
   whose mass unit is undocumented cannot be written to. [EA-001]
4. `material_prim` names, for a body API, the prim whose `physics` binding the engine reads for that body:
   `self`, or a relationship on the body prim that targets it, such as a simulation mesh. [RC-140]
5. A profile is pinned by `{"id", "version", "sha256"}`, the SHA-256 of its RFC 8785 serialisation; a profile
   whose hash differs from its pin is refused (`engine_profile_invalid`). [EA-002]
6. Engine schemas are detected by name in the composed `apiSchemas` (section 1 item 2), because they are
   rarely registered where Vesalius runs: PhysX's deformable material API is invisible to `HasAPI` without its
   plug-in (checked with USD 0.26.5). [RC-141]

### 10.2 What the adapter reads

1. The adapter writes for one model of a consumer's declaration that carries `engine` (`declarations.md`
   section 1), for the regions of its `checked_over` domain and nothing else. The model's `reads` are the
   fields its profile sources; its requirements, operating conditions, region conditions and acceptances
   apply as for any model. [EA-003]
2. For each region and each attribute sourced from a field, the adapter makes the model's read request and
   writes the value only where the build result is `met` or accepted (`declarations.md` section 4.2);
   otherwise it refuses that region, with the result's reasons. A table read over an operating range of its
   axis gives `want_mismatch`, as any read does, so an engine, which takes one number, gets a value at an
   operating value. [EA-004]
3. Every other attribute the profile lists takes its value from the model's `engine.values`, with `reason` and
   `basis`. Its `unit` is a UCUM code for a coherent SI unit (no prefix, the kilogram's apart) whose dimension
   is the attribute's, such as `Pa` or `N/m`; another unit is refused (`request_unit_mismatch`). An attribute
   with neither a field nor a declared value is refused (`engine_attribute_unset`); a declared value for an
   attribute the profile sources from a field is refused (`engine_value_sourced`), so a value Vesalius holds
   is never replaced by a number in a configuration. [EA-005]
4. The adapter refuses a stage with no authored `metersPerUnit`, or no authored `kilogramsPerUnit` where an
   attribute's dimension includes mass (`stage_units_unauthored`). [EA-006]

### 10.3 Conversion

1. For a profile whose convention is `stage`, a value of SI dimension M^a L^b T^c is written as
   v × mpu^(−b) × kpu^(−a), with `mpu` the stage's `metersPerUnit` and `kpu` its `kilogramsPerUnit`; seconds
   are unchanged. For `si`, the value is written as it is. [RC-110]

   | Quantity | Dimension (M, L, T) | Grams and centimetres | Kilograms and centimetres |
   |---|---|---|---|
   | density, 1050 kg/m³ | (1, −3, 0) | 1.05 | 1.05e-3 |
   | modulus or stress, 5000 Pa | (1, −1, −2) | 5.0e4 | 50 |
   | dynamic viscosity, 1 Pa·s | (1, −1, −1) | 10 | 0.01 |
   | length, 1 m | (0, 1, 0) | 100 | 100 |
   | stiffness, 100 N/m | (1, 0, −2) | 1.0e5 | 100 |
   | bending stiffness, 1e-6 N·m² | (1, 3, −2) | 1.0e3 | 1 |
   | rate, 2 /s | (0, 0, −1) | 2 | 2 |

2. The computed value, in double precision, equals the table's within 1e-12 relative; the written attribute
   equals it rounded to the attribute's type. A `float` attribute is single precision, so 1.05e-3 reads back
   about 4e-8 relative off (checked). [RC-110]

### 10.4 Engine materials and the stamp

1. The adapter writes one engine material per region and profile, under a scope of its own
   (`/VesaliusEngine/...`), never under `/Materials/<name>` (section 4 item 2) and never as attributes on a
   Vesalius material prim, where a converted copy would sit beside the field's JSON string (section 3 item
   2). It authors every attribute of every material API its profile lists for that material, so that no
   engine fallback stands in for a value: PhysX's deformable Young's modulus falls back to 5e7 in stage units
   (ecosystem survey, 2026-10-12). [EA-007]
2. It binds the engine material directly, with the `physics` purpose and the default strength, on every shape
   of the region (section 9) and, for a body API, on the prim its profile names, applying `MaterialBindingAPI`
   there. One region has one material, so a mesh whose elements hold several tissues needs a region per
   tissue, on separate meshes, in 0.1.0. [EA-008]
3. It refuses a region where its binding would not be the one an engine reads: a shape under a foreign
   `physics` binding of strength `strongerThanDescendants`, or with a foreign `physics` binding on one of its
   subsets (`engine_binding_overridden`); and a region inside an instance (`engine_region_instanced`), since a
   binding cannot be authored on an instance proxy and a per-region binding cannot be expressed from the
   instance's root (checked: USD refuses the edit). A scene that needs one makes the region's prims not
   instanceable. [EA-010]
4. Each engine material carries `vesalius:engineSource`, a JSON string: `{"profile": {"id", "version",
   "sha256"}, "stage_units": {"metersPerUnit", "kilogramsPerUnit"}, "region": "<path>", "material": {"id",
   "version", "content_hash"}, "attributes": {"<name>": ...}}`. Each attribute holds either `{"source":
   "field", "request", "accepted_by", "value", "unit"}`, with the complete read request of
   `read_side_contract.md` section 1 and, in `accepted_by`, the acceptances themselves (waivers and accepted
   differences included) that made its build result accepted; or `{"source": "declared", "value", "unit",
   "reason", "basis"}`. Values are SI. [EA-009]
5. The stage check re-derives every stamped engine material (section 9 item 7): it re-runs each request and
   judges the result with the stamped acceptances by `declarations.md` section 4.2. A stronger layer that
   retunes an attribute, a stamp edited by hand, an overlay or a pick the stamp does not name, and a scene
   layer written for other units and referenced into this stage are all reported. [RC-118]

## Cases

| Case | Profile | Tests |
|---|---|---|
| UR-002 | USD read | an unauthored value-bearing attribute is refused, never read as its fallback |
| UR-003 | USD read | an SI library layer referenced into a centimetre stage gives the same SI value |
| UR-004 | USD read | a stage with no authored `metersPerUnit` is refused (`stage_units_unauthored`) |
| UR-005 | USD read | geometry from a layer in other units, with an exact uniform compensating scale, and with a sheared or wrong one |
| UR-007 | USD read | a material prim is recognised by `vesalius:id` |
| UR-008 | USD read | each field is one JSON string equal to the plain record's field |
| UR-009 | USD read | the envelope attributes on a material prim |
| UR-010 | USD read | the plain record reassembled from a prim, an unknown section included, equals the original |
| UR-011 | USD read | a field edited in a stronger layer without its hash is refused (`hash_mismatch`) |
| UR-012 | USD read | two prims named alike with different identifiers are told apart by `vesalius:id` |
| UR-013 | USD read | a targeted prim of an unknown record type is refused (`unknown_type`) |
| UR-014 | USD read | a region marker with material reference, priority and orientation, read with the plug-in not registered |
| UR-015 | USD read | region geometry by computed purpose; the region prim included; a nested region's prims excluded |
| UR-016 | USD read | a binding whose target does not match `vesalius:region:material` is refused (`pin_mismatch`) |
| UR-017 | USD read | a region with no `vesalius`-purpose binding, with only a `physics` binding, or with an empty target list is refused (`binding_missing`); other regions stay readable |
| UR-018 | USD read | a binding to a prim with no `vesalius:id` is refused |
| UR-020 | USD read | an all-purpose binding to a Vesalius material, direct or through a collection, a `vesalius`-purpose collection binding, or a `vesalius` binding with two targets, inside a region, is refused |
| UR-021 | USD read | a `vesalius`-purpose binding to another material, compared by envelope, on a non-region prim or a subset inside a region is refused; one to the region's own material on a child mesh is readable |
| UR-022 | USD read | a binding never crosses into a nested region |
| UR-023 | USD read | the scene's background, with its pinned reference, and background inclusion per domain |
| UR-024 | USD read | a domain collection named `vesalius_domain_<name>`; membership counts only region prims |
| UR-025 | USD read | the scene cases of `geometry.md` in USD form, except those section 8 lists |
| UR-026 | USD read | an overlay prim reassembled into its plain form, hash verified |
| UR-027 | USD read | an undeclared overlay is not applied |
| UR-028 | USD read | an overlay whose base differs from `vesalius:overlay:baseRecord` is refused |
| UR-029 | USD read | the base prim's hash still verifies with an overlay on the stage |
| UR-030 | USD read | the material input sheet read back from the stage equals the one written (planned with R7) |
| UR-031 | USD read | each optional attribute's absence means what section 1 item 4 says |
| UR-032 | USD read | a field and its hash both edited in a stronger layer pass the hash and fail the region's pin |
| UR-033 | USD read | skin, fat, muscle, fat, skin read through the index array and the material references |
| UR-034 | USD read | mismatched array lengths, or an index out of range, refused (`path_arrays_mismatch`) |
| UR-035 | USD read | a layered path in a centimetre stage |
| UR-036 | USD read | a layered path with no homogeneity declaration refused |
| UR-037 | USD read | a `physics` binding on the region's prim, a stronger one on an ancestor, one on a descendant mesh, one on a subset, and a `physics` collection binding: the region reads its Vesalius material in each |
| UR-038 | USD read | regions, domain members and a layered path inside an instanceable prim are found through instance proxies |
| UR-039 | USD read | a time-sampled field is refused (`time_sampled`) |
| UR-040 | USD read | a point read, a domain read and a region read that reach an unloaded payload are refused (`payload_unloaded`) |
| UR-041 | USD read | a region under a point instancer's prototype is refused (`region_in_prototype`) |
| UR-042 | USD read | a point in a prim whose `VesaliusRegionAPI` a stronger layer deleted, leaving its `vesalius:region:material`, is refused, not given to the background |
| RC-100 | record checks | a value attribute beside a field's JSON string is flagged |
| RC-101 | record checks | a shipped layer with a composition arc or an asset path is flagged |
| RC-102 | record checks | a library material under `/Materials/` is flagged |
| RC-103 | record checks | `UsdPhysics.MaterialAPI` in a shipped layer is flagged |
| RC-104 | record checks | a generated layer without authored units or `upAxis = "Z"` is flagged |
| RC-105 | record checks | the stage check reports unauthored stage units, `kilogramsPerUnit` where an engine attribute's dimension includes mass |
| RC-106 | record checks | the stage check compares each shape's effective density, `MassAPI` included, with the stamped read's value or a constant bulk density; a density written through a declared overlay passes; an explicit mass is not comparable; an unauthored density is not compared |
| RC-107 | record checks | the stage check reports a layer in other units with no compensating transform |
| RC-108 | record checks | the stage check reports a hash that does not verify, or a pin that does not match |
| RC-109 | record checks | the plug-in registers with `schemaIdentifier`; the API schemas apply by name |
| RC-110 | record checks | the conversion rule gives every value of section 10.3's table in both unit systems within 1e-12; a written `float` equals the value rounded to single precision |
| RC-111 | record checks | a section named with a reserved word is flagged |
| RC-112 | record checks | the stage check lists each shape, with its region, its Vesalius material and its engine materials, for a region on an Xform whose colliders are its child meshes |
| RC-114 | record checks | an engine API, an attribute in a profile's namespaces, or a `physics:` attribute on a Vesalius material prim is flagged |
| RC-115 | record checks | a shape's engine material that is foreign (one Isaac Lab bound, no stamp), stamped for another material, or stamped for other stage units is flagged, a subset's included |
| RC-116 | record checks | a simulated shape in a region with no engine material, or only the physics scene's, is flagged |
| RC-117 | record checks | a `vesalius` binding without `MaterialBindingAPI` applied, or outside every region, is flagged |
| RC-118 | record checks | a stamped engine material with an attribute missing, unlisted, retuned in a stronger layer, or re-read to another value, and a centimetre scene layer referenced into a metre stage, are flagged |
| RC-119 | record checks | a time-sampled engine attribute is flagged |
| RC-140 | record checks | an engine profile validates; one with an attribute missing its dimension, source or locator is flagged |
| RC-141 | record checks | engine schemas are found by name in the composed `apiSchemas` with their plug-ins not registered |
| EA-001 | engine adapters | a profile with no unit source is refused (`engine_profile_invalid`) |
| EA-002 | engine adapters | a profile whose SHA-256 differs from its pin is refused |
| EA-003 | engine adapters | the adapter writes for every region of the model's `checked_over` domain, and for nothing else |
| EA-004 | engine adapters | an `unknown` read not accepted refuses its region with its reasons; one accepted by a waiver is written; a table over an operating range gives `want_mismatch` |
| EA-005 | engine adapters | an attribute with neither source is refused (`engine_attribute_unset`); a declared value for a sourced attribute is refused (`engine_value_sourced`); a declared `kPa` is refused (`request_unit_mismatch`) |
| EA-006 | engine adapters | a stage without `kilogramsPerUnit` is refused when an attribute's dimension includes mass |
| EA-007 | engine adapters | the engine material is outside `/Materials/`, never on a Vesalius prim, and authors every attribute its profile lists |
| EA-008 | engine adapters | every collider of a region is bound `physics` directly, with `MaterialBindingAPI` applied, and a body's named simulation prim |
| EA-009 | engine adapters | the adapter's own output, a density read accepted by a waiver of its unstated temperature included, gives no item 5 to 8 report from the stage check |
| EA-010 | engine adapters | a region under a foreign stronger `physics` binding, or with a foreign subset binding, is refused (`engine_binding_overridden`); a region inside an instance is refused (`engine_region_instanced`) |

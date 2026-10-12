# USD binding

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 5.3 to 5.5. The plain
forms this binds are in `record_format.md` and `geometry.md`; section 8 lists the plain cases with no USD form
in 0.1.0. Every read gives a result as `read_side_contract.md` defines it.

## 1. Schemas, and what a reader needs

1. Vesalius's USD schemas are resource-only: `schema.usda` is the source, and `generatedSchema.usda` and
   `plugInfo.json` are the registered form, with `schemaIdentifier` in the plug-in entry. Registering them is
   the writer's concern. [RC-109]
2. A reader reads Vesalius attributes by name and needs no plug-in. In 0.1.0 the single-apply API schemas are
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
5. **Copies an engine reads in stage units are written by a scene adapter, never shipped.** An engine reads
   typed attributes in its own schema and in the stage's units, never a Vesalius field, so a Vesalius value
   reaches an engine only through an adapter. The adapter reads each region's material through a reader, so
   every rule of `read_side_contract.md` applies, and refuses if either stage unit is unauthored. With `mpu`
   the stage's `metersPerUnit` and `kpu` its `kilogramsPerUnit`, it writes:

   | Quantity | Registered unit | Value written |
   |---|---|---|
   | density | `kg/m3` | ρ × mpu³ / kpu |
   | a modulus or a stress (Young's, shear, the Lamé parameters) | `Pa` | E × mpu / kpu |
   | dynamic viscosity | `Pa.s` | η × mpu / kpu |
   | a length | `m` | L / mpu |
   | a rate | `/s` | unchanged |
   | a dimensionless value (Poisson's ratio) | `1` | unchanged |

   In a stage in centimetres and kilograms, 1050 kg/m³ is written as 1.05e-3 and 5000 Pa as 50, each within
   1e-12 relative. [RC-110]
6. **An adapter's engine materials** are prims of their own in a scene layer, never attributes on a Vesalius
   material prim, where a converted copy would sit beside the field's JSON string (section 3 item 2). Each:
   - authors every attribute of every engine API applied to it, because an engine's fallback reads like a
     value (PhysX's deformable Young's modulus falls back to 5e7 Pa); an attribute with no Vesalius source (a
     friction coefficient until interfaces arrive, a position-based solver's viscosity or compliance, a
     contact stiffness) takes its value from the consumer's declared engine configuration and is labelled as
     such, or the adapter refuses;
   - carries `vesalius:convertedFrom`, the `{"id", "version", "content_hash"}` of the Vesalius material it was
     converted from, as JSON;
   - is bound with the `physics` purpose to the region's prims, or to whichever prims and subsets the engine
     needs (section 5 item 9). [RC-113]

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
3. Shipped layers do not apply `UsdPhysics.MaterialAPI` (section 2, item 5). [RC-103]
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
   (`pin_mismatch`). [UR-016]
4. **Refused bindings.** A reader refuses the region, with every read that resolves to it, in each of these
   cases; the stage and the other regions stay readable:
   - the region's prim has no authored `vesalius`-purpose binding (`binding_missing`); [UR-017]
   - the binding's target carries no `vesalius:id` (`binding_refused`); [UR-018]
   - any prim inside the region, the region's own prim included, carries an all-purpose binding to a Vesalius
     material, or a `vesalius`-purpose collection binding (`material:binding:collection:vesalius:<name>`,
     checked) (`binding_refused`); [UR-020]
   - a prim inside the region that is not itself a region, a `UsdGeom.Subset` included, carries a
     `vesalius`-purpose binding to a different material from the region's own (`binding_refused`): there are
     no per-element Vesalius materials in 0.1.0. [UR-021]

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
   from it only the prims that carry `VesaliusRegionAPI`. The collection's paths resolve relative to the scene
   prim, so a scene referenced into another keeps its domains. [UR-024]
8. The rules on owning a point, the background, domains and orientation are those of `geometry.md` section 3,
   applied to the composed stage; its scene cases exist in USD form, except those section 8 lists. [UR-025]
9. **Engine bindings are the engines'.** A `physics`-purpose binding, direct or through a collection, of any
   strength, on the region's prim, on a prim or subset inside it, or above it, belongs to an engine: a reader
   neither reads it nor refuses on it, and the region stays readable. NVIDIA's tools write that slot, and a
   mesh may need a rigid and a deformable engine material, or one per subset, which a slot shared with
   Vesalius could not hold (AD 5.4). The stage check sets the two side by side (section 9). [UR-037]

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
   that prim beside their graph layers. [UR-030]

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
(outside every region, or with purpose `guide`); its fields are named in Vesalius's namespace, never
`field:density`, which a renderer reads as smoke; and its asset paths are allowed in scene layers, never in
shipped ones (section 4). Label mappings will name their structures with `UsdSemantics` labels. [not yet
covered]

## 9. The stage check

`vesalius check --stage` reports, without changing the stage, the items below. A prim's **engine material** is
the material `ComputeBoundMaterial("physics")` resolves for it, when that material has an engine's material
API applied (`UsdPhysics.MaterialAPI`, a PhysX or deformable material API, `NewtonMaterialAPI`); the fall-back
to an all-purpose display material is not one.

1. a stage with no authored `metersPerUnit`, or with no authored `kilogramsPerUnit` where a `physics:density`
   is authored; [RC-105]
2. a region whose engine material (resolved as an engine resolves it, honouring binding strength) has a
   `physics:density` that differs from the region's Vesalius bulk density, converted
   as section 2 item 5 says, by more than 1e-6 relative, when that density is a constant; a table-valued
   density is not compared; [RC-106]
3. a layer holding geometry whose `metersPerUnit` differs from the stage's with no compensating transform
   (section 2 item 4); [RC-107]
4. a material prim whose content hash does not verify, or a region, background or path whose pinned reference
   does not match its target (section 3.6); [RC-108]
5. per region, its engine material, and that of each subset inside it with a `physics` binding of its own,
   beside the region's Vesalius material; [RC-112]
6. a region's engine material whose `vesalius:convertedFrom` is absent, or names another
   material, version or hash than the region's: an engine would simulate one material while a reader reads
   another; [RC-115]
7. a region whose geometry an engine simulates (a prim with `UsdPhysics.CollisionAPI` or a deformable-body
   API) and has no engine material, so that the engine would use its own defaults; [RC-116]
8. a `vesalius`-purpose binding on a prim without `MaterialBindingAPI` applied (USD resolves it, with a
   warning; checked), or on a prim that is neither a region nor inside one; [RC-117]
9. an engine API, or an attribute in an engine's namespace (`physics:`, `physx`, `newton:`), on a prim that
   carries `vesalius:id` (section 2 item 6). [RC-114]

A consumer's build may refuse a run on items 6 and 7.

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
| UR-014 | USD read | a region marker with material reference, priority and orientation |
| UR-015 | USD read | region geometry by computed purpose; the region prim included; a nested region's prims excluded |
| UR-016 | USD read | a binding whose target does not match `vesalius:region:material` is refused (`pin_mismatch`) |
| UR-017 | USD read | a region with no `vesalius`-purpose binding is refused (`binding_missing`); other regions stay readable |
| UR-018 | USD read | a binding to a prim with no `vesalius:id` is refused |
| UR-020 | USD read | an all-purpose binding to a Vesalius material, or a `vesalius`-purpose collection binding, inside a region is refused |
| UR-021 | USD read | a different `vesalius`-purpose binding on a non-region prim or a subset inside a region is refused |
| UR-022 | USD read | a binding never crosses into a nested region |
| UR-023 | USD read | the scene's background, with its pinned reference, and background inclusion per domain |
| UR-024 | USD read | a domain collection named `vesalius_domain_<name>`; membership counts only region prims |
| UR-025 | USD read | the scene cases of `geometry.md` in USD form, except those section 8 lists |
| UR-026 | USD read | an overlay prim reassembled into its plain form, hash verified |
| UR-027 | USD read | an undeclared overlay is not applied |
| UR-028 | USD read | an overlay whose base differs from `vesalius:overlay:baseRecord` is refused |
| UR-029 | USD read | the base prim's hash still verifies with an overlay on the stage |
| UR-030 | USD read | the material input sheet read back from the stage equals the one written |
| UR-031 | USD read | each optional attribute's absence means what section 1 item 4 says |
| UR-032 | USD read | a field and its hash both edited in a stronger layer pass the hash and fail the region's pin |
| UR-033 | USD read | skin, fat, muscle, fat, skin read through the index array and the material references |
| UR-034 | USD read | mismatched array lengths, or an index out of range, refused (`path_arrays_mismatch`) |
| UR-035 | USD read | a layered path in a centimetre stage |
| UR-036 | USD read | a layered path with no homogeneity declaration refused |
| UR-037 | USD read | a `physics` binding on the region's prim, a stronger one on an ancestor, and one on a subset: the region reads its Vesalius material in each |
| RC-100 | record checks | a value attribute beside a field's JSON string is flagged |
| RC-101 | record checks | a shipped layer with a composition arc or an asset path is flagged |
| RC-102 | record checks | a library material under `/Materials/` is flagged |
| RC-103 | record checks | `UsdPhysics.MaterialAPI` in a shipped layer is flagged |
| RC-104 | record checks | a generated layer without authored units or `upAxis = "Z"` is flagged |
| RC-105 | record checks | the stage check reports unauthored stage units |
| RC-106 | record checks | the stage check reports an engine material's density that disagrees with a constant bulk density |
| RC-107 | record checks | the stage check reports a layer in other units with no compensating transform |
| RC-108 | record checks | the stage check reports a hash that does not verify, or a pin that does not match |
| RC-109 | record checks | the plug-in registers with `schemaIdentifier`; the API schemas apply by name |
| RC-110 | record checks | an adapter writes 1.05e-3 for 1050 kg/m³ and 50 for 5000 Pa in centimetres and kilograms, within 1e-12; refuses without units |
| RC-111 | record checks | a section named with a reserved word is flagged |
| RC-112 | record checks | the stage check lists each region's engine materials, subsets included, beside its Vesalius material |
| RC-113 | record checks | an adapter's engine material authors every attribute of its APIs and carries `vesalius:convertedFrom`; an attribute with no source and no declared configuration makes the adapter refuse |
| RC-114 | record checks | an engine attribute on a Vesalius material prim is flagged |
| RC-115 | record checks | an engine material converted from another material, version or hash than its region's is flagged |
| RC-116 | record checks | a simulated region with no engine material is flagged |
| RC-117 | record checks | a `vesalius` binding without `MaterialBindingAPI` applied, or outside every region, is flagged |

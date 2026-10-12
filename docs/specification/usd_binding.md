# USD binding

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 5.3 to 5.5. The plain
forms this binds are in `record_format.md` and `geometry.md`; the two forms say the same thing.

## 1. The schema plug-in

1. Vesalius's USD schemas are resource-only: `schema.usda` is the source, and `generatedSchema.usda` and
   `plugInfo.json` are the registered form. There is no compiled library. The plug-in entry carries
   `schemaIdentifier`. [UR-001]
2. In 0.1.0 the single-apply API schemas are `VesaliusBulkAPI`, `VesaliusFluidAPI`, `VesaliusMagneticAPI`,
   `VesaliusBiocompatibilityAPI` (one per section of `record_format.md` section 4.1), `VesaliusRegionAPI` and
   `VesaliusSceneAPI`; the typed schemas are `VesaliusOverlay` and `VesaliusLayeredPath`. The names
   `VesaliusAcousticAPI`, `VesaliusRadiologicalAPI`, `VesaliusMechanicalAPI`, `VesaliusOpticalAPI`,
   `VesaliusThermalAPI` and `VesaliusDielectricAPI` are reserved.
3. No attribute in these schemas has a fallback value that a reader may use. A reader MUST refuse every
   Vesalius attribute that has no authored value (USD's `HasAuthoredValue`). [UR-002]

## 2. Units

1. **Values are SI whatever the stage says.** A Vesalius attribute's value is in the field's registered unit
   (`record_format.md` section 4.2), whatever the stage's `metersPerUnit` or `kilogramsPerUnit`. The value's
   JSON carries its `unit`, and a reader checks it. A value referenced from an SI library layer into a stage
   in centimetres arrives unchanged (checked with USD 0.26.5). [UR-003]
2. **Geometry is in stage units.** Points, entry points, primitives and layered-path thicknesses on a stage
   are in the units of the layer that defines them. A reader MUST refuse a stage with no authored
   `metersPerUnit`: USD's fallback is centimetres (checked). [UR-004]
3. USD does not rescale a referenced layer to the stage's units. A reader takes geometry from a layer whose
   authored `metersPerUnit` differs from the stage's only when the referencing prim's composed transform
   scales by exactly that layer's `metersPerUnit` divided by the stage's (relative difference 1e-9 or less);
   otherwise it refuses. [UR-005]
4. **Copies an engine reads in stage units are written by a scene adapter, never shipped.** An adapter that
   authors `UsdPhysics.MaterialAPI` density for an engine writes ρ × `metersPerUnit`³ / `kilogramsPerUnit`,
   with ρ the bulk density in kg/m³, and refuses if either stage unit is unauthored. In a stage in centimetres
   and kilograms, 1050 kg/m³ is written as 1.05e-3. [UR-006]

## 3. Material prims

1. A material is a `UsdShade.Material` prim with the API schemas of its sections applied. [UR-007]
2. **One JSON string per field, and nothing beside it.** A field is the attribute
   `vesalius:<section>:<field>`, of type `string`, holding the field's plain form (`record_format.md` section
   5, alternatives included) serialised by RFC 8785. No other attribute carries any part of a field's value.
   A section's shared specimen facts are the string attribute `vesalius:<section>:specimen`. [UR-008] [RC-100]
3. **The envelope on the prim.** The record's envelope members are string attributes on the material prim:
   `vesalius:schema_version`, `vesalius:record_type`, `vesalius:id`, `vesalius:version`, `vesalius:name`,
   `vesalius:licence` (the object as JSON), `vesalius:content_hash`, and, where present, `vesalius:card` and
   `vesalius:extensions` (as JSON). [UR-009]
4. **The record is recoverable.** A reader reassembles the plain record from these attributes; it MUST equal
   the plain record, and its content hash, computed as `record_format.md` section 9 says, MUST equal
   `vesalius:content_hash`. A reader refuses a material prim whose hash does not verify: an edit of any field
   in a stronger layer is detected this way, because only an overlay may replace a field (section 6).
   [UR-010] [UR-011]
5. **Prim names carry no identity.** A reader identifies a material by `vesalius:id`, never by its prim's name
   or path; `VES-MAT-0001` is not a valid prim name (checked). [UR-012]
6. A record of a type the reader cannot read is skipped when listing material prims and refused when a binding
   or a relationship targets it (`record_format.md` section 3). [UR-013]

## 4. Shipped layers

1. A layer generated for a release holds no composition arcs (sublayers, references, payloads) and no asset
   paths; an aggregate layer is flattened. [RC-101]
2. Library materials live under a scope of their own (`/VesaliusLibrary/...`), never under
   `/Materials/<name>`, where they would merge with display materials of the same name. [RC-102]
3. Shipped layers do not apply `UsdPhysics.MaterialAPI` (section 2, item 4). [RC-103]
4. A generated layer authors `metersPerUnit = 1` and `kilogramsPerUnit = 1` as layer metadata. [RC-104]

## 5. Regions, bindings and scenes

1. **Region marker.** A region is a prim with `VesaliusRegionAPI` applied. Its attributes are
   `vesalius:region:priority` (`int`; unauthored means no priority, `geometry.md` section 2.2),
   `vesalius:region:orientation` (`quatd`, real part first) and `vesalius:region:orientationFrame` (`token`,
   `scene`). A region's geometry is its descendant geometry prims (`UsdGeom.Gprim`) with purpose `default`;
   prims with purpose `render`, `proxy` or `guide` add nothing to it. [UR-014] [UR-015]
2. **Binding.** A region's material is the target of the `physics`-purpose binding authored on the region's
   prim (`UsdShade.MaterialBindingAPI`, relationship `material:binding:physics`). A reader MUST refuse:
   - a region whose only binding to a Vesalius material is an all-purpose binding (`material:binding`), which
     `ComputeBoundMaterial("physics")` would fall back to; [UR-016]
   - an all-purpose binding that targets a Vesalius material anywhere inside a region; [UR-017]
   - a `physics` binding on a prim inside a region that is not itself a region and targets a different
     material from the region's own. [UR-018]
3. A region's binding applies to its descendants and never across into a nested region; a nested region
   carries its own binding. [UR-019]
4. **Scene.** `VesaliusSceneAPI` is applied to the prim that declares a scene's domains. Its attributes are
   `vesalius:scene:background` (a relationship to a material prim), `vesalius:scene:precedence` (`token[]`,
   `geometry.md` section 2.5) and, per domain, `vesalius:domain:<name>:includesBackground` (`bool`). [UR-020]
5. **Domains.** A domain is a `UsdCollectionAPI` instance on the declaring prim, named
   `vesalius_domain_<name>` (the instance-naming form is to be confirmed in the schema's prototype). A
   collection's membership includes descendants, so a reader takes from it only the prims that carry
   `VesaliusRegionAPI`. A domain's paths resolve relative to the declaring prim, so a scene referenced into
   another keeps its domains. [UR-021] [not yet covered]
6. The rules on owning a point, the background, orientation and precedence are those of `geometry.md`
   sections 2.2 to 2.5, applied to the composed stage. Every scene case there exists in both forms. [UR-022]
7. Interface bindings have no USD form in 0.1.0; it comes with the interface body.

## 6. Overlays

1. An overlay record is a `VesaliusOverlay` prim carrying the envelope attributes of section 3.3, the
   relationship `vesalius:overlay:base` to its base material prim, `vesalius:overlay:scope` (the scope as
   JSON), and the replaced fields as `vesalius:<section>:<field>` string attributes. [UR-023]
2. A reader applies an overlay only when the consumer declares it (`declarations.md`), and refuses it when the
   base prim's content hash differs from the one the overlay names, or when the consumer's model configuration
   hash differs from the overlay's scope and the consumer has not accepted it. [UR-024] [UR-025]
3. An overlay never edits its base prim's attributes. [UR-011]

**The material input sheet.** A consumer that saves its run on a stage writes the material input sheet
(`declarations.md`) as one JSON string attribute, `vesalius:inputSheet`, on the prim that holds its
experiment or graph, beside MADDENING's graph layers. [UR-030]

## 7. Layered paths

```usda
def VesaliusLayeredPath "NeedlePath"
{
    point3d vesalius:path:entryPoint = (0, 0, 0)
    vector3d vesalius:path:direction = (0, 0, 1)
    double[] vesalius:path:thicknesses = [0.2, 1.0, 1.5, 0.3, 0.2]
    rel vesalius:path:materials = [</VesaliusLibrary/Skin>, </VesaliusLibrary/Fat>, </VesaliusLibrary/Muscle>]
    int[] vesalius:path:materialIndices = [0, 1, 2, 1, 0]
    token vesalius:path:lateralHomogeneity = "assumed"
}
```

1. `vesalius:path:materials` targets the distinct materials the path uses; `vesalius:path:materialIndices`
   gives each interval's index into it. USD keeps a relationship's targets in order only when they are
   distinct and removes repeats (checked with USD 0.26.5: skin, fat, muscle, fat, skin reads back as three
   targets), so one target per interval would drop layers. [UR-026]
2. A reader refuses a path whose `thicknesses` and `materialIndices` differ in length, or whose index falls
   outside `materials`. [UR-027]
3. The entry point and thicknesses are in the stage's length units (section 2). In the example the stage is in
   centimetres. A path may target a curve, through `vesalius:path:curve`, in place of a direction. [UR-028]
4. `vesalius:path:lateralHomogeneity` is required, as in `geometry.md` section 3. [UR-029]

## 8. Label volumes and field overrides

Label volumes and field overrides use `UsdVol` (`OpenVDBAsset`, `Field3DAsset`). Their attributes are
specified with their first consumer (AD 12.1, A1). [not yet covered]

## 9. The stage check

`vesalius check --stage` reports, without changing the stage:

1. a stage with no authored `metersPerUnit`, or with no authored `kilogramsPerUnit` where a `physics:density`
   is authored; [RC-105]
2. a `physics:density` on a prim whose Vesalius material's bulk density, converted as section 2 item 4 says,
   differs from it by more than 1e-6 relative; [RC-106]
3. a composed layer whose `metersPerUnit` differs from the stage's with no compensating transform (section 2
   item 3); [RC-107]
4. a material prim whose content hash does not verify (section 3 item 4). [RC-108]

## Cases

| Case | Profile | Tests |
|---|---|---|
| UR-001 | USD read | the plug-in registers with `schemaIdentifier`; the API schemas apply by name |
| UR-002 | USD read | an unauthored Vesalius attribute is refused, never read as its fallback |
| UR-003 | USD read | an SI library layer referenced into a centimetre stage gives the same SI value |
| UR-004 | USD read | a stage with no authored `metersPerUnit` is refused |
| UR-005 | USD read | geometry from a layer in other units, with and without a compensating scale |
| UR-006 | USD read | an adapter writes 1.05e-3 for 1050 kg/m³ in centimetres and kilograms; refuses without units |
| UR-007 | USD read | a material prim with its section API schemas |
| UR-008 | USD read | each field is one JSON string equal to the plain record's field |
| UR-009 | USD read | the envelope attributes on a material prim |
| UR-010 | USD read | the plain record reassembled from a prim equals the original |
| UR-011 | USD read | a field edited in a stronger layer fails the hash and is refused |
| UR-012 | USD read | two prims named alike with different identifiers are told apart by `vesalius:id` |
| UR-013 | USD read | a referenced prim of an unknown record type is refused |
| UR-014 | USD read | a region marker with priority and orientation |
| UR-015 | USD read | a render-purpose child adds nothing to a region's geometry |
| UR-016 | USD read | a material reached only through an all-purpose binding is refused |
| UR-017 | USD read | an all-purpose binding to a Vesalius material inside a region is refused |
| UR-018 | USD read | a different physics binding on a non-region prim inside a region is refused |
| UR-019 | USD read | a binding never crosses into a nested region |
| UR-020 | USD read | the scene's background, precedence and background inclusion |
| UR-021 | USD read | domain membership counts only region prims |
| UR-022 | USD read | the scene cases of `geometry.md`, in USD form |
| UR-023 | USD read | an overlay prim's attributes |
| UR-024 | USD read | an undeclared overlay is not applied |
| UR-025 | USD read | an overlay whose base hash or scope differs is refused unless accepted |
| UR-026 | USD read | skin, fat, muscle, fat, skin read through the index array |
| UR-027 | USD read | mismatched array lengths, or an index out of range, refused |
| UR-028 | USD read | a layered path in a centimetre stage |
| UR-029 | USD read | a layered path with no homogeneity declaration refused |
| UR-030 | USD read | the material input sheet read back from the stage equals the one written |
| RC-100 | record checks | a value attribute beside a field's JSON string is flagged |
| RC-101 | record checks | a shipped layer with a composition arc or an asset path is flagged |
| RC-102 | record checks | a library material under `/Materials/` is flagged |
| RC-103 | record checks | `UsdPhysics.MaterialAPI` in a shipped layer is flagged |
| RC-104 | record checks | a generated layer without authored units is flagged |
| RC-105 | record checks | the stage check reports unauthored stage units |
| RC-106 | record checks | the stage check reports a physics density that disagrees with the bulk density |
| RC-107 | record checks | the stage check reports a layer in other units with no compensating transform |
| RC-108 | record checks | the stage check reports a material prim whose hash does not verify |

# USD binding

Schema 0.1.0, draft. Conventions, suites and case numbers: `README.md`. Rationale: AD 5.3 to 5.5. The plain
forms this binds are in `record_format.md` and `geometry.md`; section 8 lists the plain cases with no USD form
in 0.1.0. Every read gives a result as `read_side_contract.md` defines it.

## 1. Schemas, and what a reader needs

1. OpenMaterica's USD schemas are resource-only: `schema.usda` is the source, and `generatedSchema.usda` and
   `plugInfo.json` are the registered form, with `schemaIdentifier` in the plug-in entry. Registering them is
   the writer's concern. [RC-109]
2. A reader reads OpenMaterica attributes by name and needs no plug-in. It detects an applied API schema by
   its name in the prim's composed `apiSchemas` (`UsdPrim.GetPrimTypeInfo().GetAppliedAPISchemas()`): without
   the plug-in, `HasAPI` and `GetAppliedSchemas()` omit unregistered schemas, so a reader using them would
   find no regions (checked with USD 0.26.5). [UR-014] In 0.1.0 the single-apply API schemas are
   `MatericaBulkAPI`, `MatericaFluidAPI`, `MatericaMagneticAPI`, `MatericaBiocompatibilityAPI` (one per
   section of `record_format.md` section 4.1), `MatericaRegionAPI` and `MatericaSceneAPI`; the typed schemas
   are `MatericaOverlay` and `MatericaLayeredPath`. The names `MatericaAcousticAPI`,
   `MatericaRadiologicalAPI`, `MatericaMechanicalAPI`, `MatericaOpticalAPI`, `MatericaThermalAPI` and
   `MatericaDielectricAPI` are reserved. [not yet covered]
3. No attribute in these schemas has a fallback value a reader may use. A reader refuses a **value-bearing**
   attribute that has no authored value (USD's `HasAuthoredValue`), with the reason `unauthored_attribute`:
   every field attribute (section 3 item 2), every required envelope attribute (section 3 item 3), and every
   attribute this document marks required. [UR-002]
4. These attributes may be absent, and their absence has a stated meaning: `materica:card` and
   `materica:extensions` (none); `materica:region:priority` (no priority); `materica:region:orientation`
   (no orientation; `materica:region:orientationFrame` is required when it is present);
   `materica:scene:background` and `materica:scene:backgroundMaterial` (no background; both or neither);
   `materica:domain:<name>:includesBackground` (false); one of `materica:path:direction` and
   `materica:path:curve` (the other is used). [UR-031]
5. **Instances.** A reader finds regions, domain members and layered paths with instance proxies traversed
   (`Usd.TraverseInstanceProxies()`), and identifies a region by its path on the stage, an instance proxy's
   included. Every instance of a prototype carries the prototype's regions and bindings. The default traversal
   skips them (checked with USD 0.26.5). [UR-038]
6. **Time samples.** An OpenMaterica attribute with time samples is refused (`time_sampled`): a reader reads
   the default value, while a tool reading at a time code reads the sample (checked). [UR-039]

## 2. Units

1. **Values are SI whatever the stage says.** An OpenMaterica field's value is in its registered unit
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

1. An **OpenMaterica material** is a `UsdShade.Material` prim carrying `materica:id`, with the API schemas of
   its sections applied. [UR-007]
2. **One JSON string per field, and nothing beside it.** A field is the attribute
   `materica:<section>:<field>`, of type `string`, holding the field's plain form (`record_format.md` section
   5, alternatives included) serialised by RFC 8785. No other attribute carries any part of a field's value. A
   section's shared specimen facts are the string attribute `materica:<section>:specimen`; `specimen` is a
   reserved field name for this reason (`record_format.md` section 4.1). [UR-008] [RC-100]
3. **The envelope on the prim.** The record's envelope members are string attributes on the material prim:
   `materica:schema_version`, `materica:record_type`, `materica:id`, `materica:version`, `materica:name`,
   `materica:licence` (the object as JSON), `materica:content_hash`, and, where present, `materica:card` and
   `materica:extensions` (as JSON). [UR-009]
4. **Reserved names.** `region`, `scene`, `domain`, `overlay`, `path` and `inputSheet` are never section
   names, because `materica:<word>:...` attributes with these words belong to the scene (sections 5 to 7).
   [RC-111]
5. **Reassembly.** A reader rebuilds the plain record from a material prim: the envelope from the attributes
   of item 3; then every attribute `materica:<section>:<field>` whose `<section>` is not a reserved name and
   not an envelope member, each parsed as JSON into `body.sections.<section>.fields.<field>`, with
   `materica:<section>:specimen` parsed into `body.sections.<section>.specimen`; `materica:extensions` into
   `body.extensions`. Sections it does not know are kept, so that the hash covers them. [UR-010]
6. **The hash.** Every reader compares `materica:content_hash` with the hash a region, a background or a path
   pins, and refuses a difference (`pin_mismatch`, sections 5 and 7). A reader with the hash suite also
   recomputes the reassembled record's hash as `record_format.md` section 9 says, and refuses the material
   when it differs from `materica:content_hash` (`hash_mismatch`), and compares that recomputed hash with the
   pin too (`pin_mismatch`, given once, `read_side_contract.md` section 3, step 4). So a field edited in a
   stronger layer without rewriting `materica:content_hash` is refused; a stronger layer that edits both
   composes a consistent, different record, which only a pin catches. A reader that does not claim the hash
   suite labels `hash_not_checked` the results that reach the hash step (`read_side_contract.md` section 3,
   step 4). [UR-011] [UR-032]
7. **Prim names carry no identity.** A reader identifies a material by `materica:id`, never by its prim's name
   or path; `MAT-0001` is not a valid prim name (checked). [UR-012]
8. A material prim whose `materica:record_type` is a type the reader cannot read is skipped when listing
   material prims and refused when a binding or a relationship targets it (`unknown_type`,
   `record_format.md` section 3). [UR-013]

## 4. Shipped layers

1. A layer generated for a release holds no composition arcs (sublayers, references, payloads) and no asset
   paths; an aggregate layer is flattened. [RC-101]
2. Library materials live under a scope of their own (`/MatericaLibrary/...`), never under
   `/Materials/<name>`, where they would merge with display materials of the same name. [RC-102]
3. Shipped layers do not apply `UsdPhysics.MaterialAPI` (section 10). [RC-103]
4. A generated layer authors `metersPerUnit = 1`, `kilogramsPerUnit = 1` and `upAxis = "Z"` as layer
   metadata. Isaac Sim and SimReady's validators expect Z-up; a library layer holds no geometry, so the axis
   changes nothing a reader reads. [RC-104]

## 5. Regions, bindings and scenes

1. **Region marker.** A region is a prim with `MatericaRegionAPI` applied. Its attributes are
   `materica:region:material` (required: the material reference, `{"id", "version", "content_hash"}` as JSON),
   `materica:region:priority` (`int`), `materica:region:orientation` (`quatd`, real part first, unit within
   1e-12) and `materica:region:orientationFrame` (`token`, `scene`). [UR-014]
2. **Region geometry.** A region's geometry is the region prim, if it is a `UsdGeom.Gprim`, and its descendant
   `UsdGeom.Gprim`s, whose computed purpose (`UsdGeom.Imageable.ComputePurpose()`) is `default`. The walk
   stops at a nested region: its prims belong to it. Prims with computed purpose `render`, `proxy` or `guide`
   add nothing. [UR-015]
3. **Binding.** A region's material is the target of the `materica`-purpose binding authored on the region's
   prim (`UsdShade.MaterialBindingAPI`, relationship `material:binding:materica`), and a writer applies
   `MaterialBindingAPI` to that prim. The `physics` purpose is the engines' (item 9). A reader never calls
   `ComputeBoundMaterial`: where no `materica` binding is authored it falls back to the all-purpose binding,
   usually a display material (checked with USD 0.26.5), and `bindingStrength` would decide what a reader
   reads. The target's envelope must match `materica:region:material`, or the region is refused
   (`pin_mismatch`). A relationship authored with no targets counts as no binding (`binding_missing`); one
   with more than one target is refused (`binding_refused`); USD resolves neither (checked). [UR-016] [UR-017]
   [UR-020]
4. **Refused bindings.** A reader refuses the region, with every read that resolves to it, in each of these
   cases; the stage and the other regions stay readable:
   - the region's prim has no authored `materica`-purpose binding (`binding_missing`); [UR-017]
   - the binding's target carries no `materica:id` (`binding_refused`); [UR-018]
   - any prim inside the region, the region's own prim included, carries an all-purpose binding to an
     OpenMaterica material, direct or through a collection (`material:binding:collection:<name>`), or a
     `materica`-purpose collection binding (`material:binding:collection:materica:<name>`, checked)
     (`binding_refused`); [UR-020]
   - a prim inside the region that is not itself a region, a `UsdGeom.Subset` included, carries a
     `materica`-purpose binding to a different material from the region's own, compared by envelope
     (`materica:id`, `materica:version`, `materica:content_hash`) (`binding_refused`): there are no
     per-element OpenMaterica materials in 0.1.0. [UR-021]

   A region whose only binding is an all-purpose one to an OpenMaterica material matches the first and third
   cases, and both codes are reported.
   The reason codes are those of `read_side_contract.md` section 4.
5. A region's binding applies to its own geometry (item 2) and never across into a nested region; a nested
   region carries its own binding. [UR-022]
6. **Scene.** `MatericaSceneAPI` is applied to the prim that declares a scene's domains. Its attributes are
   `materica:scene:background` (a relationship to a material prim) with `materica:scene:backgroundMaterial`
   (its material reference as JSON, checked like a region's), and, per domain,
   `materica:domain:<name>:includesBackground` (`bool`). [UR-023]
7. **Domains.** A domain is a `UsdCollectionAPI` instance on the scene prim, named `materica_domain_<name>`,
   with `<name>` matching `[a-z0-9_]+` (`geometry.md` section 1), so its properties are
   `collection:materica_domain_<name>:...`. A collection's membership includes descendants, so a reader takes
   from it only the prims that carry `MatericaRegionAPI`, with instance proxies traversed (section 1 item 5).
   The collection's paths resolve relative to the scene prim, so a scene referenced into another keeps its
   domains. [UR-024]
8. The rules on owning a point, the background, domains and orientation are those of `geometry.md` section 3,
   applied to the composed stage; its scene cases exist in USD form, except those section 8 lists. [UR-025]
9. **Engine bindings are the engines'.** A `physics`-purpose binding, direct or through a collection, of any
   strength, on the region's prim, on a prim or subset inside it, or above it, belongs to an engine: a reader
   neither reads it nor refuses on it, and the region stays readable. NVIDIA's tools write that slot, and a
   mesh may need a rigid and a deformable engine material, or one per subset, which a slot shared with
   OpenMaterica could not hold (AD 5.4). The stage check sets the two side by side (section 9). [UR-037]
10. **Unloaded payloads.** What an unloaded payload holds is not on the stage, so a reader refuses, with the
    reason `payload_unloaded`, a point read on a stage that holds one, a read over a domain whose collection
    includes a path under one, and a read of a region whose subtree holds one (checked: the region's geometry
    is empty while it is unloaded). [UR-040]
11. **Point instancers.** A region under a prim that a `UsdGeom.PointInstancer`'s `prototypes` relationship
    targets is refused (`region_in_prototype`): a prototype is drawn and simulated only where it is
    instanced, never at its own place. [UR-041]
12. **Broken regions.** A prim that carries a `materica:region:` attribute without `MatericaRegionAPI` in its
    composed `apiSchemas` is a refused region (`binding_refused`): a point inside its geometry, taken as item
    2 says, is refused, never given to an enclosing region or the background. A stronger layer that deletes
    the schema leaves the binding and the attribute behind (checked). A `materica` binding alone on a
    non-region prim is judged by item 4 inside a region (a binding to the region's own material is redundant
    and readable) and reported by the stage check outside every region. [UR-042] [UR-021]

## 6. Overlays and the input sheet

1. An overlay record is a `MatericaOverlay` prim carrying the envelope attributes of section 3 item 3,
   `materica:overlay:purpose` (`token`), the relationship `materica:overlay:base` to its base material prim
   for navigation, `materica:overlay:baseRecord` (the base's `{"id", "version", "content_hash"}` as JSON),
   `materica:overlay:scope` (the scope as JSON), and the replaced fields as
   `materica:<section>:<field>` string attributes, each with its own `specimen` inside it. The plain overlay
   is reassembled from these as section 3 item 5 says, and its hash checked as section 3 item 6 says. [UR-026]
2. A reader applies an overlay only when the consumer declares it, and refuses it by `record_format.md`
   section 4.4: a base whose envelope differs from `materica:overlay:baseRecord` (`overlay_base_mismatch`),
   two declared overlays on one field (`overlay_conflict`). The scope is compared by the build
   (`declarations.md` section 5). [UR-027] [UR-028]
3. An overlay never edits its base prim's attributes: the base's own hash still verifies with the overlay on
   the stage. [UR-029]
4. **The material input sheet.** A consumer that saves its run on a stage writes the material input sheet
   (`declarations.md`) as one JSON string attribute, `materica:inputSheet`, on the scene prim whose domains it
   used, or, where it used no scene on the stage, on the stage's default prim. MADDENING-based consumers place
   that prim beside their graph layers. The sheet is R7, planned with OpenMaterica 0.2 (AD 12.1), and its case
   with it. [UR-030]

## 7. Layered paths

```usda
def MatericaLayeredPath "NeedlePath"
{
    point3d materica:path:entryPoint = (0, 0, 0)
    vector3d materica:path:direction = (0, 0, 1)
    double[] materica:path:thicknesses = [0.2, 1.0, 1.5, 0.3, 0.2]
    rel materica:path:materials = [</MatericaLibrary/Skin>, </MatericaLibrary/Fat>, </MatericaLibrary/Muscle>]
    string materica:path:materialRefs = '[{"id": "...", "version": "...", "content_hash": "..."}, ...]'
    int[] materica:path:materialIndices = [0, 1, 2, 1, 0]
    token materica:path:lateralHomogeneity = "assumed"
}
```

1. `materica:path:materials` targets the distinct materials the path uses, and `materica:path:materialRefs`
   holds their material references in the same order, each checked against its target's envelope
   (`pin_mismatch`). `materica:path:materialIndices` gives each interval's index into them. USD keeps a
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
   `materica:path:curve`, in place of a direction. The operations of `geometry.md` section 4 apply. [UR-035]
4. `materica:path:lateralHomogeneity` is required (`homogeneity_undeclared`, `geometry.md` section 4).
   [UR-036]

## 8. Plain cases with no USD form in 0.1.0

Label crosswalks and label volumes, field overrides and `precedence` (`geometry.md` sections 3.6 and 5),
interface bindings (`geometry.md` section 3.5), and external geometry references (`geometry.md` section 3.1:
on a stage, geometry is on the stage) have no USD form in 0.1.0. Label volumes and field overrides will use
`UsdVol` (`OpenVDBAsset`, `Field3DAsset`), specified with their first consumer (AD 12.1, A1), under three
constraints known now: a volume prim is a `Gprim` that renderers draw, so it sits outside region geometry
(outside every region, or with purpose `guide`); its field relationships are named
`field:materica:<name>`, never `field:density`, which a renderer reads as smoke (checked: a volume's field
relationships always take the `field:` prefix); and its asset paths are allowed in scene layers, never in
shipped ones (section 4). [not yet covered]

## 9. The stage check

`materica check --stage` reports, without changing the stage, the items below. It **holds** every version of
OpenMaterica's engine crosswalk for `UsdPhysics` and every valid engine crosswalk passed to it
(`--crosswalk`); a build passes the crosswalks its declaration pins (section 10.1 items 5 and 7). It knows an
engine's schemas through the crosswalks it holds and the stamps on the stage, and lists what it does not
recognise (item 4).

A **shape** is a prim an engine simulates: a prim with `UsdPhysics.CollisionAPI`, or with a body API a held
crosswalk lists, found with instance proxies traversed. A body API no held crosswalk lists is not recognised
as one, and is listed as an unrecognised API (item 4). A shape belongs to the innermost region whose prim is
the shape or one of its ancestors, whatever the shape's purpose: a collider with purpose `guide` still
collides.

A shape's **engine materials** are the materials `ComputeBoundMaterial("physics")` resolves on the shape, on
each of its `GeomSubset`s of family `materialBind`, and, for a body API, on the prim its crosswalk names,
through a binding of purpose `physics`, or through the all-purpose fall-back when the material it reaches
carries `PhysicsMaterialAPI` or an API a held crosswalk lists; a fall-back to a display material, which
carries neither, is not one. The purpose is read from the name of the relationship the call returns (checked).
A binding, authored on the prim or inherited from an ancestor, counts only where the prim it is resolved for
has `MaterialBindingAPI` applied: OpenUSD's reference physics parser ignores it otherwise, on shapes and on
subsets, and reports an all-purpose binding to a material with `PhysicsMaterialAPI` (checked in the review of
2026-10-13), and engines built on the parser behave the same. The check does not take materials from the
parser itself, which reports only materials that carry `PhysicsMaterialAPI` (checked), so a consumer's engine
whose material API is another would be reported as having none. A material reached so is an engine material
whatever its APIs; one with no stamp is foreign (item 6). For an engine material with no stamp, the check
compares the density attribute that every held crosswalk whose material APIs it carries sources from
`bulk.density`; where no held crosswalk matches, or the matching crosswalks name different attributes, its
attributes are listed and its density is not compared. The check judges each shape, never the region prim,
because engines bind colliders and simulation meshes, not regions (checked with the reference parser in the
review of 2026-10-12).

1. a stage with no authored `metersPerUnit`, or with no authored `kilogramsPerUnit` where an engine attribute
   whose dimension includes mass is authored on an engine material of the `stage` convention; [RC-105]
2. a layer holding geometry whose `metersPerUnit` differs from the stage's with no compensating transform
   (section 2 item 4); [RC-107]
3. a material prim whose content hash does not verify, or a region, background or path whose pinned reference
   does not match its target (section 3 item 6); [RC-108]
4. per shape, its region, the region's OpenMaterica material and its engine materials, each with the crosswalk
   it was checked against and whether that crosswalk was held, matched by its APIs, matched ambiguously or not
   matched; the crosswalks held; and every **unrecognised API**: an applied API schema on a prim in a region,
   or on a material bound there, that is not OpenMaterica's, not one of the API schemas usd-core 0.26.5
   defines (a list the check holds; an instance of a multiple-apply API, such as `SemanticsLabelsAPI:tag`, is
   matched by the name before its colon), not listed by a held crosswalk and not named by the stamp of the
   material it is on; [RC-112]
5. a shape whose **effective density** differs, by more than 1e-6 relative after conversion (section 10.3),
   from the stamped read's value where its engine material is stamped, else from its region's OpenMaterica
   bulk density when that is a constant; a table-valued density is not compared. The effective density follows
   `UsdPhysics`'s precedence: an authored, non-zero `physics:density` from `UsdPhysics.MassAPI` on the shape
   or its nearest ancestor that has one, in stage units, else the authored, non-zero density attribute on the
   engine material, in its stamp's or its crosswalk's convention: the attribute whose stamped read is of
   `bulk.density`, or, with no stamp, the one chosen as above. `UsdPhysics` ignores a `MassAPI` density or
   mass of 0 (checked in the review of 2026-10-13). An authored, non-zero `physics:mass` makes the shape "not
   comparable", which is reported, not flagged; [RC-106]
6. a shape inside a region whose engine material, or a subset's, has no `materica:engineSource` (a foreign
   material, such as one Isaac Lab bound), names another material than the region's, compared by envelope, or
   was stamped with the `stage` convention for other stage units than the stage's; [RC-115]
7. a stamped engine material that does not re-derive. With no crosswalk needed: an API the stamp names that is
   not in the material's composed `apiSchemas`; an attribute the stamp names that is not authored, or whose
   authored type differs from the stamped type; a stamped dimension that differs from the dimension of the
   stamped unit, which for a field read is its field's registered unit; a stamped read request that, re-run
   against the stage's material prims, gives another value or a result that is neither `met` nor accepted; and
   a written value that differs from its stamped SI value converted by its stamped dimension and convention to
   the stage's units (section 10.3) at its type's precision. Where the check holds the stamped crosswalk,
   also: a stamped convention, or an attribute's stamped type, dimension or source (the field it reads, or
   declared), that differs from the crosswalk's; an attribute the crosswalk lists that the stamp does not name
   or that is not authored; and an authored attribute in the crosswalk's namespaces that the crosswalk does
   not list. A stamped crosswalk the check does not hold is listed (item 4), not flagged: without it, the
   convention and a declared attribute's dimension, beyond agreeing with its unit, are the stamp's own claims,
   and completeness is not checked; [RC-118]
8. a shape inside a region with no engine material, which includes one whose only binding is on a prim without
   `MaterialBindingAPI`, or only a material bound to the physics scene prim, which PhysX uses as its default
   (recalled), so that the engine uses a material nobody converted from the region's; [RC-116]
9. a `materica`-purpose binding on a prim without `MaterialBindingAPI` applied (USD resolves it, with a
   warning; checked), or on a prim that is neither a region nor inside one; [RC-117]
10. on a prim that carries `materica:id`, an API schema that is not OpenMaterica's and is either listed by a
    held crosswalk or not one of usd-core 0.26.5's own, or an attribute in `physics:` or in a namespace a held
    crosswalk lists (section 10.4); [RC-114]
11. a time-sampled attribute on an engine material; [RC-119]
12. a crosswalk passed to the check that does not validate (section 10.1), which is reported and not held;
    and, for each API of every held crosswalk, whether it was compared with its pinned schema file, or why
    not. [RC-140] [RC-143]

Items 5 to 8 also give a declared engine model's engine results, one per shape, after its adapter has
written (`declarations.md` section 2 item 6).

## 10. Engine materials and adapters

An engine never reads an OpenMaterica field: it reads typed attributes in its own schemas, in the units it
documents. An OpenMaterica value reaches an engine only through an **engine adapter**, which writes engine
materials for a model the consumer declares, by an **engine crosswalk**: a data document stating what one
engine version reads and where each value comes from. OpenMaterica specifies the crosswalk's format, the
conversion, the stamp and the stage check, none of them written for one engine's schema, and ships one
crosswalk, for OpenUSD's `UsdPhysics`. A crosswalk for any other engine is written and pinned by the consumer
that runs it (section 10.1 item 7; AD 5.4). The adapter is in `openmaterica-authoring`, with a scaffold that
drafts crosswalks (section 10.1 item 9); the shipped crosswalk is data in `materica`, because the stage check
holds it (AD 7.1). Adapters claim the suite EA.

### 10.1 Engine crosswalks

1. An engine crosswalk describes one engine version: `{"crosswalk_schema_version": "0.1.0", "document_type":
   "engine_crosswalk", "id": "<namespace>/<name>", "version", "engine": {"name", "version"}, "units":
   {"convention", "source"}, "material_apis": [{"name", "schema", "attributes": [...]}], "body_apis":
   [{"name", "schema", "material_prim"}], "namespaces": [...]}`. Its `id` is in its writer's namespace, as a
   record's identifier is; only crosswalks OpenMaterica ships use `materica/`. Its `crosswalk_schema_version`
   follows `record_format.md` section 8's pattern. A crosswalk that is not valid JSON by `record_format.md`
   section 1 item 6, whose `crosswalk_schema_version` is absent or ill-formed, or whose
   `crosswalk_schema_version` has another `MAJOR.MINOR` than the reader's (before 1.0.0) is invalid
   (`engine_crosswalk_invalid`). `schema` pins the schema file that defines the API (item 8). A multiple-apply
   API, whose class in its schema file has `__INSTANCE_NAME__` in its property names (checked), cannot be
   described in 0.1.0, nor can an API one of whose built-ins is multiple-apply. [RC-140]
2. `material_apis` lists every attribute of each API as that engine version defines it, because the adapter
   authors them all (section 10.4 item 1). Each attribute is `{"name", "type", "dimension", "source",
   "allowed_tokens"?, "doc"}`: `type`, its USD value type; `dimension`, the exponents of its SI dimension over
   the base units `{"kg", "m", "s", "A", "K", "mol", "cd"}`, an absent one being zero; `source`, either
   `{"field": "<section>.<field>"}` or `"declared"`; `allowed_tokens`, for a token attribute whose schema
   restricts it; and `doc`, a locator (`provenance.md`) to the engine's own documentation of the attribute.
   Every numeric type (integers and floating point, and their vectors and arrays, taken component by
   component) has a dimension; a token, string, boolean or asset has `dimension: null`, and is written as
   declared, never converted. An attribute sourced from a field has the dimension of that field's registered
   unit (`record_format.md` section 4.2). An attribute in a unit that is not coherent SI, such as an angle in
   degrees, or in another convention than the crosswalk's, cannot be described in 0.1.0. [RC-140]
3. `units.convention` is `stage` (the engine reads lengths and masses in the stage's `metersPerUnit` and
   `kilogramsPerUnit`, and every other base unit as SI) or `si`; `units.source` is a locator to the engine's
   documentation of it. A crosswalk without one is invalid and the adapter refuses it
   (`engine_crosswalk_invalid`): an engine whose mass unit is undocumented cannot be written to. [EA-001]
4. `material_prim` names, for a body API, the prim whose `physics` binding the engine reads for that body:
   `self`, or a relationship on the body prim that targets it, such as a simulation mesh. [RC-140]
5. A crosswalk is pinned by `{"id", "version", "sha256"}`, the SHA-256 of its RFC 8785 serialisation. A
   crosswalk whose hash differs from its pin, a crosswalk in `materica/` that OpenMaterica did not ship, and a
   crosswalk with a held crosswalk's id and version but another hash are refused (`engine_crosswalk_invalid`).
   [EA-002]
6. Engine schemas are detected by name in the composed `apiSchemas` (section 1 item 2), because they are
   rarely registered where OpenMaterica runs: PhysX's deformable material API is invisible to `HasAPI` without
   its plug-in (checked with USD 0.26.5). Composed `apiSchemas` never lists an API's built-in APIs (checked in
   the review of 2026-10-13), so the adapter applies every API a crosswalk lists by name, built-ins included.
   [RC-141]
7. **Who writes crosswalks.** OpenMaterica ships one crosswalk, `materica/usdphysics`, for `UsdPhysics` as USD
   0.26.5 defines it: engine `{"name": "OpenUSD", "version": "0.26.5"}`; convention `stage`, with its source
   in OpenUSD's `UsdPhysics` documentation; one material API, `PhysicsMaterialAPI`, pinned to usd-core
   0.26.5's `usdPhysics/resources/generatedSchema.usda` (SHA-256
   `681cac0463546c032ba903ae77e0dd245265bbb75d2db4719fe6696debe9bf47`, checked), whose four `float` attributes
   are `physics:density`, sourced from `bulk.density`, and `physics:staticFriction`, `physics:dynamicFriction`
   and `physics:restitution`, declared until interfaces arrive (AD 4.13); no body APIs; and the namespace
   `physics`. Every version of it that OpenMaterica releases keeps shipping and is always held. OpenMaterica
   will add a version as `UsdPhysics` grows; NVIDIA's deformable schema is written to become part of it
   (ecosystem survey, 2026-10-12). A crosswalk for any other engine, such as Isaac Sim's deformable materials
   or Newton, is written by the consumer that runs the engine, pinned in its declaration (`declarations.md`
   section 1) and passed to the build with it; the build resolves each pin against the crosswalks passed to it
   and OpenMaterica's own. OpenMaterica does not ship, review or update consumers' crosswalks. [RC-142]
8. **Compared with a pinned schema file, never with what is installed.** Each API's `schema` is `{"sha256",
   "doc"}`: the SHA-256 of the bytes of the `generatedSchema.usda` that defines it, and a locator naming the
   plug-in and version it comes from. Only a file passed explicitly counts: with `--schema`, in the build's
   inputs, or in a case's `inputs.schemas`. A registered plug-in's file is never consulted, because it changes
   with the install (checked: usd-core's `usdPhysics` file has the pinned hash in 0.26.5 and another in
   0.25.5). Where a passed file has the pinned hash, the API's class is read from it with Sdf, without
   registering it. For a material API the class is compared with the crosswalk: every attribute the class
   defines locally, apart from the built-ins' overrides its `customData` names in
   `apiSchemaOverridePropertyNames`, is listed, and every listed attribute is defined there, with the same
   type and, for a token, the same allowed tokens; and every built-in API of the class is itself listed by the
   crosswalk. For a body API, whose attributes the adapter never writes, the class must exist, be single-apply
   and, where `material_prim` names a relationship, define it. Relationships of a material API are not
   compared, since the adapter writes none on a material. A difference makes the crosswalk invalid
   (`engine_crosswalk_invalid`). Where no passed file has the pinned hash, the API is listed as not compared
   (section 9 item 12), and its completeness is its writer's claim. So a result depends on the crosswalk and
   the files passed, never on what is installed. Schema files hold no units, so a crosswalk's dimensions and
   convention are always its writer's claim, backed by its `doc` and `units.source` locators. `materica check
   --crosswalk <file>` validates a crosswalk on its own. [RC-143] [EA-011]
9. **The scaffold.** `openmaterica-authoring` drafts a crosswalk from a schema file, read with Sdf without
   registering it: for each API named, the file's hash, its locally defined attributes' names and types
   (built-ins' overrides apart), their allowed tokens, and its built-in APIs; `dimension`, `source`, `doc` and
   `units` are left for the writer, since the file holds none of them (checked with USD 0.26.5:
   `PhysicsMaterialAPI`'s four `float` attributes have an empty documentation and only a one-line
   `userDocBrief` in their custom data, with no unit). A draft is not a crosswalk until every member is filled
   and it validates. The scaffold refuses an API the file does not define. It is a tool, tested in
   `openmaterica-authoring`, not a conformance case.
10. **One engine model per region.** Two engine models whose domains share a region are refused at build,
    since each adapter binds every shape of its regions directly and the second would replace the first's
    bindings. A consumer whose engine reads two material APIs on one shape, a rigid and a deformable one,
    writes one crosswalk that lists both. [BC-040]

### 10.2 What the adapter reads

1. The adapter writes for one model of a consumer's declaration that carries `engine` (`declarations.md`
   section 1), by the crosswalk its `engine.crosswalk` pins, for the regions of its `checked_over` domain and
   nothing else. The model's `reads` are the fields its crosswalk sources; its requirements, operating
   conditions, region conditions and acceptances apply as for any model. A pinned crosswalk that is not
   passed, or that does not validate (section 10.1), is refused (`engine_crosswalk_invalid`). [EA-003]
   [EA-011]
2. For each region and each attribute sourced from a field, the adapter makes the model's read request and
   writes the value only where the build result is `met` or accepted (`declarations.md` section 4.2);
   otherwise it refuses that region, with the result's reasons. A table read over an operating range of its
   axis gives `want_mismatch`, as any read does, so an engine, which takes one number, gets a value at an
   operating value. [EA-004]
3. Every other attribute the crosswalk lists takes its value from the model's `engine.values`, with `reason`
   and `basis`. A numeric value's `unit` is a UCUM code for a coherent SI unit (no prefix, the kilogram's
   apart) whose dimension is the attribute's, such as `Pa`, `N/m`, `W/(m.K)` or `1`; another unit is refused
   (`request_unit_mismatch`). An attribute with no dimension takes a value of its type and no unit; a value of
   another type, or a token outside the attribute's `allowed_tokens`, is refused (`engine_value_invalid`). An
   attribute with neither a field nor a declared value is refused (`engine_attribute_unset`); a declared value
   for an attribute the crosswalk sources from a field is refused (`engine_value_sourced`), so a value
   OpenMaterica holds is never replaced by a number in a configuration. [EA-005]
4. For a crosswalk whose convention is `stage`, the adapter refuses a stage with no authored `metersPerUnit`,
   or no authored `kilogramsPerUnit` where an attribute's dimension includes mass (`stage_units_unauthored`).
   [EA-006]

### 10.3 Conversion

1. For a crosswalk whose convention is `stage`, a value whose dimension has the exponent a for `kg` and b for
   `m` is written as v × mpu^(−b) × kpu^(−a), with `mpu` the stage's `metersPerUnit` and `kpu` its
   `kilogramsPerUnit`; the other base units are unchanged. For `si`, the value is written as it is. An
   attribute with no dimension is written as declared. [RC-110]

   | Quantity | Dimension (kg, m, s) | Grams and centimetres | Kilograms and centimetres |
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

1. The adapter writes one engine material per region and crosswalk, under a scope of its own
   (`/MatericaEngine/...`), never under `/Materials/<name>` (section 4 item 2) and never as attributes on an
   OpenMaterica material prim, where a converted copy would sit beside the field's JSON string (section 3 item
   2). It applies by name every material API its crosswalk lists for that material, and authors every
   attribute of each, so that no fallback stands in for a value: PhysX's deformable Young's modulus falls back
   to 5e7 in stage units (ecosystem survey, 2026-10-12), and `UsdPhysics` computes mass with 1000 kg/m³ where
   a material's density is unauthored or 0 (checked in the review of 2026-10-13). [EA-007]
2. It binds the engine material directly, with the `physics` purpose and the default strength, on every shape
   of the region (section 9) and, for a body API, on the prim its crosswalk names, applying
   `MaterialBindingAPI` there. One region has one material, so a mesh whose elements hold several tissues
   needs a region per tissue, on separate meshes, in 0.1.0. [EA-008]
3. It refuses a region where its binding would not be the one an engine reads: a shape under a foreign
   `physics` binding of strength `strongerThanDescendants`, or with a foreign `physics` binding on one of its
   subsets (`engine_binding_overridden`); and a region inside an instance (`engine_region_instanced`), since a
   binding cannot be authored on an instance proxy and a per-region binding cannot be expressed from the
   instance's root (checked: USD refuses the edit). A scene that needs one makes the region's prims not
   instanceable. [EA-010]
4. Each engine material carries `materica:engineSource`, a JSON string: `{"crosswalk": {"id", "version",
   "sha256"}, "convention", "stage_units": {"metersPerUnit", "kilogramsPerUnit"}, "region": "<path>",
   "material": {"id", "version", "content_hash"}, "apis": [...], "attributes": {"<name>": ...}}`. `apis` names
   every API the adapter applied. Each attribute holds its `type` and `dimension` as the crosswalk gives them,
   and either `{"source": "field", "request", "accepted_by", "value", "unit"}`, with the complete read request
   of `read_side_contract.md` section 1 and, in `accepted_by`, the acceptances themselves (waivers and
   accepted differences included) that made its build result accepted; or `{"source": "declared", "value",
   "unit", "reason", "basis"}`. Values are SI. The stamp describes itself: with the stage's units it gives
   every written value without the crosswalk, and the check verifies what it can of it without the crosswalk
   (section 9 item 7). [EA-009]
5. The stage check re-derives every stamped engine material (section 9 item 7): it re-runs each request,
   judges the result with the stamped acceptances by `declarations.md` section 4.2, and recomputes each
   written value from the stamp. A stronger layer that retunes an attribute or deletes an API, an overlay or a
   pick the stamp does not name, a scene layer written for other units and referenced into this stage, and a
   stamp edited by hand so that its dimensions no longer agree with its units are reported with or without the
   crosswalk; a stamp whose convention or dimensions were edited consistently is reported only with the
   crosswalk held. [RC-118]

## Cases

| Case | Suite | Tests |
|---|---|---|
| UR-002 | USD read | an unauthored value-bearing attribute is refused, never read as its fallback |
| UR-003 | USD read | an SI library layer referenced into a centimetre stage gives the same SI value |
| UR-004 | USD read | a stage with no authored `metersPerUnit` is refused (`stage_units_unauthored`) |
| UR-005 | USD read | geometry from a layer in other units, with an exact uniform compensating scale, and with a sheared or wrong one |
| UR-007 | USD read | a material prim is recognised by `materica:id` |
| UR-008 | USD read | each field is one JSON string equal to the plain record's field |
| UR-009 | USD read | the envelope attributes on a material prim |
| UR-010 | USD read | the plain record reassembled from a prim, an unknown section included, equals the original |
| UR-011 | USD read | a field edited in a stronger layer without its hash is refused (`hash_mismatch`) |
| UR-012 | USD read | two prims named alike with different identifiers are told apart by `materica:id` |
| UR-013 | USD read | a targeted prim of an unknown record type is refused (`unknown_type`) |
| UR-014 | USD read | a region marker with material reference, priority and orientation, read with the plug-in not registered |
| UR-015 | USD read | region geometry by computed purpose; the region prim included; a nested region's prims excluded |
| UR-016 | USD read | a binding whose target does not match `materica:region:material` is refused (`pin_mismatch`) |
| UR-017 | USD read | a region with no `materica`-purpose binding, with only a `physics` binding, or with an empty target list is refused (`binding_missing`); other regions stay readable |
| UR-018 | USD read | a binding to a prim with no `materica:id` is refused |
| UR-020 | USD read | an all-purpose binding to an OpenMaterica material, direct or through a collection, a `materica`-purpose collection binding, or a `materica` binding with two targets, inside a region, is refused |
| UR-021 | USD read | a `materica`-purpose binding to another material, compared by envelope, on a non-region prim or a subset inside a region is refused; one to the region's own material on a child mesh is readable |
| UR-022 | USD read | a binding never crosses into a nested region |
| UR-023 | USD read | the scene's background, with its pinned reference, and background inclusion per domain |
| UR-024 | USD read | a domain collection named `materica_domain_<name>`; membership counts only region prims |
| UR-025 | USD read | the scene cases of `geometry.md` in USD form, except those section 8 lists |
| UR-026 | USD read | an overlay prim reassembled into its plain form, hash verified |
| UR-027 | USD read | an undeclared overlay is not applied |
| UR-028 | USD read | an overlay whose base differs from `materica:overlay:baseRecord` is refused |
| UR-029 | USD read | the base prim's hash still verifies with an overlay on the stage |
| UR-030 | USD read | the material input sheet read back from the stage equals the one written (planned with R7) |
| UR-031 | USD read | each optional attribute's absence means what section 1 item 4 says |
| UR-032 | USD read | a field and its hash both edited in a stronger layer pass the hash and fail the region's pin |
| UR-033 | USD read | skin, fat, muscle, fat, skin read through the index array and the material references |
| UR-034 | USD read | mismatched array lengths, or an index out of range, refused (`path_arrays_mismatch`) |
| UR-035 | USD read | a layered path in a centimetre stage |
| UR-036 | USD read | a layered path with no homogeneity declaration refused |
| UR-037 | USD read | a `physics` binding on the region's prim, a stronger one on an ancestor, one on a descendant mesh, one on a subset, and a `physics` collection binding: the region reads its OpenMaterica material in each |
| UR-038 | USD read | regions, domain members and a layered path inside an instanceable prim are found through instance proxies |
| UR-039 | USD read | a time-sampled field is refused (`time_sampled`) |
| UR-040 | USD read | a point read, a domain read and a region read that reach an unloaded payload are refused (`payload_unloaded`) |
| UR-041 | USD read | a region under a point instancer's prototype is refused (`region_in_prototype`) |
| UR-042 | USD read | a point in a prim whose `MatericaRegionAPI` a stronger layer deleted, leaving its `materica:region:material`, is refused, not given to the background |
| RC-100 | record checks | a value attribute beside a field's JSON string is flagged |
| RC-101 | record checks | a shipped layer with a composition arc or an asset path is flagged |
| RC-102 | record checks | a library material under `/Materials/` is flagged |
| RC-103 | record checks | `UsdPhysics.MaterialAPI` in a shipped layer is flagged |
| RC-104 | record checks | a generated layer without authored units or `upAxis = "Z"` is flagged |
| RC-105 | record checks | the stage check reports unauthored stage units, `kilogramsPerUnit` where an engine attribute's dimension includes mass; not `kilogramsPerUnit` for an `si` engine material |
| RC-106 | record checks | the stage check compares each shape's effective density, `MassAPI` included, with the stamped read's value or a constant bulk density; a density written through a declared overlay passes; an explicit mass is not comparable; an unauthored density is not compared; a `MassAPI` density or mass of 0 is ignored |
| RC-107 | record checks | the stage check reports a layer in other units with no compensating transform |
| RC-108 | record checks | the stage check reports a hash that does not verify, or a pin that does not match |
| RC-109 | record checks | the plug-in registers with `schemaIdentifier`; the API schemas apply by name |
| RC-110 | record checks | the conversion rule gives every value of section 10.3's table in both unit systems within 1e-12; a written `float` equals the value rounded to single precision |
| RC-111 | record checks | a section named with a reserved word is flagged |
| RC-112 | record checks | the stage check lists each shape, with its region, its OpenMaterica material and its engine materials, each with its crosswalk and that crosswalk's status, for a region on an Xform whose colliders are its child meshes; the crosswalks held; and as unrecognised APIs a deformable body whose crosswalk is not held and a foreign material's PhysX API; `SemanticsLabelsAPI` is not listed |
| RC-114 | record checks | on an OpenMaterica material prim, `PhysicsMaterialAPI`, a PhysX API with no crosswalk held, an attribute in a held crosswalk's namespaces, or a `physics:` attribute is flagged; `MaterialBindingAPI` and `SemanticsLabelsAPI` are not |
| RC-115 | record checks | a shape's engine material that is foreign (one Isaac Lab bound, no stamp; one of an engine with no crosswalk held, on a collider and on a subset), stamped for another material, or stamped `stage` for other stage units is flagged, a subset's included; an `si` stamp is not flagged for stage units; an unstamped material that both a consumer's PhysX crosswalk and OpenMaterica's crosswalk match has its density compared |
| RC-116 | record checks | a simulated shape in a region with no engine material, or only the physics scene's, is flagged; so is the adapter's collider after a stronger layer deletes its `MaterialBindingAPI` |
| RC-117 | record checks | a `materica` binding without `MaterialBindingAPI` applied, or outside every region, is flagged |
| RC-118 | record checks | a stamped engine material with a stamped attribute missing, retuned in a stronger layer, of another type, or re-read to another value, with a stamped API deleted, with a stamped dimension that disagrees with its unit, and a centimetre scene layer referenced into a metre stage, are flagged, with the crosswalk held and without it; an attribute the crosswalk does not list, an attribute the crosswalk lists that the stamp omits, and a stamp whose convention and value were edited together are flagged with the crosswalk held, and listed as not checked without it |
| RC-119 | record checks | a time-sampled engine attribute is flagged |
| RC-140 | record checks | an engine crosswalk validates; one with an attribute missing its source or locator, a field-sourced attribute whose dimension differs from its field's unit, a `float` with a `null` dimension, a token with a dimension, or a consumer's id in `materica/` is flagged; so is one that is not valid JSON by `record_format.md` section 1 item 6, or whose `crosswalk_schema_version` is absent, ill-formed or of another `MAJOR.MINOR`; a magnetic attribute's dimension in amperes validates |
| RC-141 | record checks | engine schemas are found by name in the composed `apiSchemas` with their plug-ins not registered |
| RC-142 | record checks | OpenMaterica's `UsdPhysics` crosswalk validates and compares clean with usd-core 0.26.5's `usdPhysics` schema file, passed; a stage-check arm lists every version OpenMaterica released as held |
| RC-143 | record checks | a crosswalk compared with its pinned schema file: an omitted attribute, an attribute the file does not define, a wrong type, different allowed tokens, an unlisted built-in API, a multiple-apply API and a body API whose named relationship the class lacks are flagged; a built-in's override is not required in the crosswalk; a body API's attributes are not compared; with no passed file of the pinned hash, the API is listed as not compared, whatever is registered |
| EA-001 | engine adapters | a crosswalk with no unit source is refused (`engine_crosswalk_invalid`) |
| EA-002 | engine adapters | a crosswalk whose SHA-256 differs from its pin is refused |
| EA-003 | engine adapters | the adapter writes for every region of the model's `checked_over` domain, and for nothing else |
| EA-004 | engine adapters | an `unknown` read not accepted refuses its region with its reasons; one accepted by a waiver is written; a table over an operating range gives `want_mismatch` |
| EA-005 | engine adapters | an attribute with neither source is refused (`engine_attribute_unset`); a declared value for a sourced attribute is refused (`engine_value_sourced`); a declared `kPa` is refused (`request_unit_mismatch`); a token attribute takes its declared token, unconverted; a token outside `allowed_tokens` is refused (`engine_value_invalid`) |
| EA-006 | engine adapters | a stage without `kilogramsPerUnit` is refused when an attribute's dimension includes mass, for a `stage` crosswalk and not for an `si` one |
| EA-007 | engine adapters | the engine material is outside `/Materials/`, never on an OpenMaterica prim, applies every API its crosswalk lists by name, a built-in included, and authors every attribute of each |
| EA-008 | engine adapters | every collider of a region is bound `physics` directly, with `MaterialBindingAPI` applied, and a body's named simulation prim |
| EA-009 | engine adapters | the adapter's own output, a density read accepted by a waiver of its unstated temperature included, gives no item 5 to 8 report from the stage check, with its crosswalk held and with it not held |
| EA-010 | engine adapters | a region under a foreign stronger `physics` binding, or with a foreign subset binding, is refused (`engine_binding_overridden`); a region inside an instance is refused (`engine_region_instanced`) |
| EA-011 | engine adapters | a consumer's crosswalk that is not passed, that RC-140 flags, or that differs from its pinned schema file (RC-143) is refused (`engine_crosswalk_invalid`); with no passed file of the pinned hash it is written, whatever is registered |

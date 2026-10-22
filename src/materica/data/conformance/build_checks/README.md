# Build-check cases (BC)

The cases of a consumer's build check, which checks a declaration against records
(`docs/specification/declarations.md`; `docs/specification/README.md`, "Suites and case numbers"). A
build-check case holds for an implementation that claims build checks with plain read. The suite holds, so
far, the cases of the declaration checked on its own, which the build refuses before any read:
- a tolerance or accept list without its reason (BC-004);
- an acceptance without its reason, or without the basis its kind needs (BC-005);
- an acceptance with no location where its kind needs one (BC-037);
- a declaration that departs from its shape: not JSON or not an object, a member missing, of another type,
  unknown or one slip from a named one, a token its member does not take, a name given twice, a requirement or
  `trainable` entry against `reads` and `checked_over` (BC-048);
- a waiver resting on a label whose requirement does not name that label with `review: "reviewed"` (BC-050);
- what a build refuses because it does not claim the scene suite, USD read or the sampling suite, with the
  rules that come before it (BC-051).

None runs yet: S7a-1 builds the declaration's own check, and with it the runner's `check_build` executor
(`tests/spec_sync/case_steps.json` maps each file to `S7a-1`). `CASES.md` beside this file gives one row per
case file: what the arm tests, the text that decides it, and the refusals it expects. Start there.

## Reading a case

A build-check case names its records in `inputs.records` and its declaration in `inputs.declaration`, and its
`request` is `{"operation": "check_build"}` (`docs/specification/README.md`, "Case files"). In this suite:

- `expected.refusals` lists the declaration's refusals, each `{"item", "pointer"}`: the case id of the rule
  broken and a JSON pointer (RFC 6901) into the declaration, `""` being the declaration itself. They are
  compared as a set; `detail` is never compared.
- `compare.members` names `refusals`, `results`, `watches` and `unused`, and `expected` holds `refusals` alone:
  a declaration refused on its own gives no results, no watches and nothing unused (`declarations.md` section
  2), so a build that refuses and still reads fails every file.
- Two files compare one rule's refusals alone (`compare.rules_compared`), where the text fixes another rule's
  refusal of the same declaration less exactly than the rule the arm tests:
  `BC-050.requirement_names_another_label` (the waiver's label is also not one its field registers, a fault
  the token rule names too) and `BC-051.engine_over_records` (item 7 refuses the engine model, at pointers the
  text does not fix; the arm tests that item 12 then gives none).
- BC-051's files state the claim their answer rests on: `{"scene_documents": false}`, `{"usd_read": false}`
  or `{"sampling": false}`.

## The fixtures

Every record here is a conformance fixture (`record_format.md` section 7 item 1): illustrative, stating
nothing about any material.

- **The records**, `water_fixture.json` and `glycerol_fixture.json`, are the plain-read suite's inputs of the
  same names, byte for byte: `conformance/water_fixture` 1.0.0, the viscosity as a constant at 310.15 K with its
  shear rate unstated, and `conformance/glycerol_fixture` 1.0.0, a density. Every declaration lists the water
  record in `checked_over.records`; the glycerol record is supplied with the one arm that names it, a
  `trainable` entry at a record the model is not checked over.
- **The declarations**, one per file, named after the case and variant (`bc048_json_array.json`), are one base
  declaration with the arm's fault planted. The base: the consumer `conformance_consumer` 1.0.0; operating
  conditions of 310.15 K and 50 to 500 1/s; one model, `drag` 1.0.0, checked over the water record, with an
  empty `target`, reading the viscosity, with one requirement (a temperature tolerance of 1 K, a shear rate
  tolerance of 0 1/s and a `test_method` accept list, each with its reason) and one acceptance, a waiver of the
  unstated shear rate at the water record. An acceptance an arm adds is valid but for the fault planted: an
  `overlay` and an `overlay_scope` name an overlay no case supplies, and an `engine` pins a crosswalk no case
  passes. The base declaration passes its own check, so it is no case of this suite: a build reads for it.

## What the cases cannot show

- **Anything a build gives after reading**: results, watches and unused acceptances, which S7a-2 to S7a-4's
  files compare, and a consumer's run against its watches.
- **A review added after a pin.** A review lies outside the content hash (`declarations.md` section 1 item 11),
  so a pinned record's review can change while the pin holds; a case supplies one copy of a record.
- **One refusal given twice.** Refusals are compared as a set, so a build that reports a refusal twice, where
  "Two faults with one case and one pointer are one refusal", passes every file. The build's property tests
  hold that rule.
- **The claims' other side.** BC-051's files hold for a build that does not claim the suite each names; what a
  build claiming it gives comes with that suite's cases.
- **BC-040's refusals.** The engine arm compares BC-051's refusals alone; item 7's are BC-040's own cases.
- **An engine model checked over a domain** by a build that claims neither the scene suite nor USD read. The
  design planned the arm, but item 12's first sentence refuses a model checked over a domain, and its last says
  a model with `engine` that item 7 refuses gives no refusal under item 12, which item 7 does when no crosswalk
  is passed: the arm waits for the text to say which holds.

## How they were made and checked

The cases were drafted with AI assistance (Claude, Anthropic) from the specification text alone, by a pass
shown no implementation; the code that runs them did not exist. Each arm states the sentences its answer rests
on, checked against the text, and was then checked by:
- the case schema (`schema/0.1/case.json`), every file; the reference reader
  (`tests/conformance/reference_reader.py`), every input read alike, the one that is not JSON refused alike;
  both records' hashes recomputed by two RFC 8785 implementations, and every pin of them in a declaration;
- a build of the declaration's check written from `declarations.md` sections 1 and 4.1 alone, which agrees
  with every file under the claims it states;
- a control per arm, the arm's declaration with the one thing it tests removed, which gives that build another
  answer; for the two arms whose point is a refusal not given (an `accepted_difference` with no location, and
  item 12 yielding to item 7), a seeded fault of that build which the arm catches instead;
- 39 seeded faults of that build, each of which some file catches;
- a draft schema of the declaration, against which every control that passes its own check is valid and every
  refused declaration invalid, except those whose rule a schema cannot state (a name given twice by a member's
  value, a field against `reads`, a location against `checked_over`, the label rule, the build's claims), and
  the one that is not JSON.

The scripts that generated and checked these files are not part of the repository. The files are the source.

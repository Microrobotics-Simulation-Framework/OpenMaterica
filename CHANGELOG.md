# Changelog

All notable changes to OpenMaterica will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Additional sections per release: **Schema**, **Data**, **Verification**, **Security** and **Known Anomalies**.
The schema, each model family and each library material carry their own versions; see
`DOCUMENTATION_ARCHITECTURE.md` section 7. Once the material library has its own repository, its changes are
recorded in that repository's CHANGELOG. This file is the core's: `openmaterica-authoring` and
`openmaterica-families` keep changelogs of their own, in their directories, from their first releases, and
every family entry goes in `families/CHANGELOG.md`.

## [Unreleased]

### Added
- The project's artwork in `assets/`: the logo (`images/logo.png`, and `images/logo-full.png` at full size),
  the favicon and app icons (`images/favicon/`), and an animation of the logo for talks and posts
  (`video/logo-animation.mp4`). The logo heads the README and the site; the site serves the logo and favicons
  from its root, and its content security policy allows images and the web manifest from the site itself, and
  still nothing from elsewhere.
- The read's steps 7 and 8 (S2a-2; `read_side_contract.md` section 3). Step 7 finds the target field, and
  gives `absent` where the record holds none; a field holding alternatives raises `NotImplementedError`, since
  alternatives are read at step 7, with S2a-4 (`no_pick`) and S4. Step 8 refuses a form the field's row does
  not allow, a composition's basis included (`form_not_registered`); a value field, form or section
  `specimen` that breaks its shape, a member one slip from one named at its place (in the field, or in the
  envelope, the body or a section, which refuses every field read from it), or a token the reader knows in a
  member whose row does not allow it (`form_invalid`); a token it knows for no member of that name
  (`unknown_token`); and a withheld value (`withheld`), each check made and every reason given. Beyond shapes
  it checks counts, ranges in order, signs and bounds, a statistics block's conditional members, an
  uncertainty's rules, and each status object's place and token (`provenance.md` section 1 item 5). A form
  the row allows whose own member waits for S2b or S3 (a table, an interval, a composition, evidence) raises
  `NotImplementedError` whatever its other members hold, since its own member could add a reason: so a
  composition's components and an evidence entry's withholding wait for S2b-1 and S2b-2. A form the row does
  not allow is refused with every shared reason, its own member, which a read neither uses nor returns, unread
  (`core/fields.py`, `core/value_shapes.py`). Step 8 reads the status tokens each member allows from the
  generated shapes; a specimen fact's unit as it reads every unit, a string or a status object, step 9 alone
  comparing it; `mimics`'s fixed basis and a disease or treatment state's text as the maintainer's rulings
  settle them; and where a field's label goes from its row (`vocabulary/fields.json`).
- Step 0 refuses, as `request_incomplete`, a request member one slip from one the request's shape names, a
  field the vocabulary does not register, and a requirement holding a declaration's members.
- `materica.core.slips`: the one-slip relation of `record_format.md` section 10, which the read and the
  name-overlap check share. A word made plural or singular must be a word: the empty string between two
  underscores is none.
- `Vocabulary.token_lists`, every token list of the vocabulary by its name, a fact's fixed members, a
  field's bases and where its label goes, and `STATUS_TOKENS`, the status tokens from the generated shapes
  (`core/vocabulary.py`). Every `claims` parameter of the core is typed by the suites, so that a misspelt
  suite name does not type-check.

### Changed
- The sibling distributions and the MCP server (maintainer, 2026-10-16), with the maintainer's rulings of
  2026-10-17 on their open points, written into the architecture draft (the decisions, sections 3.1, 3.2, 7.1,
  7.2, 8, 12.1, 13, 14 and 15) and the documentation plan (the components, sections 2, 3.5, 5.1, 7.1, 7.4, 10,
  12, 14, 15 and the appendices), with `CONTRIBUTING.md`, `SECURITY.md`, `CLAUDE.md` and this file's preamble.
  One repository holds every Python distribution, a uv workspace with tag-prefixed releases, and
  OpenMaterica's own families stay in it, in the import package `materica_families`. There is no
  `openmaterica-mcp`: the core's `[mcp]` extra brings the one server, part of the core's assessed wheel and
  never run at a consumer's build. It speaks over stdio only and loads tools by entry point from a closed list
  (the core and its two siblings), and no tool it loads makes a network request; a listed sibling that is
  missing or mismatched is skipped with a logged reason, and no sibling imports an MCP library. A sibling's
  MAJOR.MINOR is the core's it is built for, and it depends on that core minor alone, after 1.0 as before; a
  core minor is a release train; the core's `[authoring]` and `[families]` extras pin the matching minor with
  a range, and `[all]` brings both; a sibling refuses a core of another MAJOR.MINOR, and `python -m materica
  versions` checks them; an explainer release, first `openmaterica-families` 0.1.0, stands in for a sibling at
  each core minor before its first. Family entries go in `families/CHANGELOG.md`. Text only: none of it is
  built yet.

### Schema
- The value fields of schema 0.1's writer schema, so far open placeholders (S2a-1): a value field of each of
  the eight forms, or alternatives; the constant, interval, composition and evidence forms in full; conditions
  with `plus_minus` and `set_or_measured`, each token condition bound to its own row's tokens; the specimen
  facts with `supply_form` and `lot`, a fact's fixed unit `s`, `mimics`'s stated basis and the UBERON
  identifier's pattern taken from the text, and a disease or treatment state's `text` present exactly for
  `diseased` and `treated`; the statistics block and its uncertainties, the provenance object and `label`; a
  status object in exactly the members `provenance.md` section 1 item 5 lists, a placeholder beside one taking
  no other; and the rules across objects of `provenance.md` sections 2, 3 and 7 (an extraction's derivation,
  formulation or fit record, a pooled statistic's search, a withheld value's or evidence entry's recipe). The
  table, power-law, parameter-set and reference-data forms' own members, the fit record, and the provenance
  members whose own members the text does not yet name stay placeholders; the schema's description names each
  such place. Members a read does not check carry `x-materica-write-only` (`record.writer.json`).
- The writer binds each name to its row (maintainer, 2026-10-15): each section's `fields` is closed to the
  names `record_format.md` section 4.1 registers for it, and an overlay's `replaces` to the registered fields;
  each field, and each of its alternatives, takes only its row's forms, the bases its row allows a
  composition, its registered unit and its row's label or none; a numeric condition's `unit`, and its
  `plus_minus` entries', hold its registered unit. The vocabulary generates the bindings from the rows, and
  the writer applies each by `allOf`, holding no list of its own; the reader schema and the typed shapes leave
  them out.
- The reader schema holds a value field's and a section specimen's shapes in `$defs`, as step 8 checks them,
  applied from nowhere, without the rules a read cannot apply (one testing, or requiring only, a member it
  does not check); the typed shapes gain a TypedDict per form and per shape, every number typed `float` as the
  reader gives it (`materica.shapes`).
- The vocabulary gains every token S2 reads, generated from the specification: the reason table's steps, the
  bases a field's row allows a form, the conditions another condition requires, the element symbols, each
  token condition's tokens and each specimen fact's fixed values as enumerations, and the form, interval,
  composition, statistics, uncertainty, provenance and result-label tokens, four of them in new files
  (`forms.json`, `statistics.json`, `provenance.json`, `labels.json`); the pattern of an identifier a fact's
  row writes (`"UBERON:<digits>"`); and the bindings of the rows (`fields.json`'s `sections`, `replaces` and
  one per field, `conditions.json`'s `units`). The generator reads every code span of a cell or stops, and
  stops on a name listed twice in a table, an identifier of another form, and a row a binding cannot state.
- `provenance.md` section 6.2: a disease or treatment state's `text` names the disease or the treatment and is
  present exactly when its token is `diseased` or `treated` (maintainer, 2026-10-15). Three plain-read inputs
  that held a text beside `normal` lose it, rehashed, and the PR-316 case files that pin them are repinned.
- Two defaults from S2a-2's review, approved (maintainer, 2026-10-15; `docs/specification/changes.md`): step
  9 of a read compares a specimen fact's `unit` with the unit its row fixes, wherever step 8 checks the fact,
  so that another unit, or a status object with any token, gives `unit_mismatch`, and step 8 checks it only as
  a string or a status object (`read_side_contract.md` section 3, step 9; three PR-037 arms, for S2a-3); and
  `mimics`, whose row fixes its basis to `stated`, takes no `inferred_from` (`provenance.md` section 6.2).
- The writer binds a specimen fact's unit to the one its row fixes (`"s"`), a status object there refused, as
  a numeric condition's unit is bound, so that no record step 9 refuses is written; a fact whose unit the
  source does not give is written as a status object (maintainer, 2026-10-15). The vocabulary generates the
  binding from the rows (`specimen_facts.json`'s `units`, each referring to its row's unit), and the writer's
  `specimen` applies it by `allOf`, a fact's own `unit` being a unit as anywhere else; the reader schema and
  the typed shapes leave the binding out. Every other unit the writer takes was already bound to
  its registered unit wherever the row fixes one (a field's, a condition's, a `plus_minus` entry's, none on a
  token condition); a table's `axis_unit` waits for S3, which writes the table's shape.
- `fields.json` gives, for a field whose Label cell lets its label go on a table, the condition the table's
  axis must not be (`label_not_on_axis`); the generator reads the cell's prose in its two forms, and any other
  stops it.
- `PR-032.interval_basis_unknown`'s input holds a statistics block of a valid basis, so that the arm tests the
  interval's basis alone; its pin follows.
- Members that held a name with a second meaning, and no safeguard to keep the two apart, are renamed before
  0.1.0 (maintainer, 2026-10-15; `docs/specification/changes.md`): a scene cylinder's `axis` to `direction`;
  a family conversion's `from` and `to` to `from_measure` and `to_measure`; an admissibility constraint's
  `kind` to `rule`; a declared model's `parameters` to `consumer_parameters`, and a declared distribution's
  and a marginal's to `distribution_parameters`; a witness datum's `reference_data` to
  `reference_data_name`; and a multivariate normal's per-parameter `space`, with a fit's
  `covariance_space.space`, to `parameter_spaces`. No schema held any of them yet; the one case file that
  did, a declared distribution in a request (PR-330), follows.
- `case.json` takes the `transform_draws` operation of a sampling case, its draws' shape not yet specified.
- `scripts/gen_reader_schema.py` takes a member marked `x-materica-write-only` with `{"unless": {<member>:
  <token>, ...}}` in place of `true`: one a read checks only where each named member of its object, one a read
  checks, holds that token. The reader `$defs` keep its shape, and whether its object requires it, in a
  conjunct under that condition, and elsewhere treat it as write-only: a rule in the `then` of exactly that
  condition takes it as checked, any other rule as unchecked. A mark of another form stops the generator.
- The reader `$defs` check a provenance object's `derivation` for origin `derived` alone, as `provenance.md`
  section 2 item 6 and step 8 do. They applied its shape wherever a `derivation` stood, so a reader validating
  a field with them refused one the text reads: a constant of origin `measured_by_contributor`, say, whose
  derivation, there because its extraction's method is `derivation`, holds no `inputs` (found by S2a-3's fuzz
  target 4 and its review). The writer marks `derivation` write-only `unless` its origin is `derived`, and
  still holds it to its shape wherever it stands (`provenance.md` sections 3 and 5, RC-035); the typed shapes
  are unchanged. The value-field check holds the marks of this form to the text, and the unknown-member positions
  walk into such a member, as before.

### Verification
- Checks that the value-field shapes match the specification's member tables, status table and examples, that
  the members marked write-only are those step 8 does not check, that each token condition and fact binds its
  row's list and a fact's identifier the pattern of its row's form, that a member a row gives as present
  exactly with some tokens is so in the writer, that each rule across objects refuses a field without its
  member, that each binding of the rows is applied where it belongs and holds what the rows give, a row added
  to the text being taken by the unchanged writer, and that the writer's description names exactly the places
  it leaves open (`tests/spec_sync/test_value_fields.py`).
- A check that the names valid at one place, the members an `allOf` joins included, stay more than one slip
  apart and that no name has two meanings, over the schemas, the vocabulary and the specification, with an
  allowlist of the overlaps judged intended, each with its reason and a safeguard, a quote that must stay in
  its document or a test that refuses each meaning at the others' places, or with none, the reason and the
  maintainer's flag: approved with none possible; approved with the safeguard deferred to the shapes that give
  the name a place, and due, failing the check, once a schema gives it one (`ranges`); or pending while a
  rename is proposed, failing once the maintainer has answered, as the maintainer has for the eight proposed
  with S2a-1 (`tests/spec_sync/test_name_overlaps.py`, `test_name_overlap_safeguards.py`).
- A check that each reason code is given only at the steps the reason table names, against the text (a step's
  item and the passages it hands its checks to, and step 6 for an overlay what steps 1 to 5 give), and against
  the code of steps 0 to 5 in every module of the core, statically and traced through every read case file
  (`tests/spec_sync/test_reason_steps.py`).
- Hypothesis properties of the writer schema: it takes every value field the specification allows and every
  registered field in its place, and refuses each of 167 faults the text names, in ten families, built from
  the text and the vocabulary's rows, never from the schema or its bindings; 92 mutants of the schema and of
  the bindings it applies, the S2a-1 review's 31 among them, each killed at the assertion it names
  (`tests/property/test_writer_properties.py`, `test_writer_mutants.py`), in a third CI shard, `writer`.
- The feature audit holds a feature drawn alike as each example's first choice, as a refusal property draws
  its fault, to a floor its draw gives at the `ci` profile: Hypothesis shows one draw in up to eight examples,
  so the floor counts one draw in every eight examples, each draw shown in five, and is the count the feature
  falls below with a probability of at most 1e-6, and never below 10. A family of more than 15 faults is
  drawn in parts, a property each. Each fault is drawn by `st.sampled_from`, no longer by a drawn seed, which
  drew some faults up to 1.27 times as often as others (`tests/property/audits.py`).
- The writer schema's acceptance properties declare each feature by the chance that a draw shows it, its share
  measured at `ci` (`@pytest.mark.chances`): at `ci` each is held to the draw floor of its chance, at `dev` to
  that floor where it is at least 10, and at `deep` to a third of its chance. Their least shares assumed
  independent examples, which Hypothesis's clusters are not: from the measured clusters, they failed a run
  with a probability of about 1.5e-6 at `ci` and 1e-3 at `dev`, against about 3e-10 and 7e-7 now. The
  audit's comment no longer says 1e-9: a least share at its gate fails about one run in a hundred
  (`tests/property/audits.py`).
- The json and records shards' properties declare by its chance, measured at `ci`, each feature whose least
  share failed a correct run with a probability above 1e-6 at `ci` or 1e-3 at `dev`, computed from the
  clusters measured on each property: 44 features of 13 properties. Their least shares failed a run of the two
  shards with a probability of about 7e-3 at `ci` (negative zero in RFC 8785's values, about one run in 450,
  and 14 of HP3's regions, one in 200) and 2e-2 at `dev` (`long` in the versions' order failed 16 of 2,000
  runs), against about 2e-6 and 5e-4 now, from the least shares kept. RFC 8785's property draws names across
  the surrogate range and negative zero more often, and HP3 runs in two parts, a property each, its first
  fault's region drawn among the part's before the record, so that each feature has a floor at `ci`; the
  mutant searches draw as before. For each such property a control runs it at `ci`'s examples with a
  generator that stops producing one feature: its audit fails on that feature alone
  (`tests/unit/test_audit_controls.py`).
- A check that each member the schemas declare whole admits the float the reader gives
  (`tests/unit/test_shapes.py`).
- The tests of the repository scripts make their throwaway git repositories with every `GIT_` variable
  removed. Git exports `GIT_DIR` to the commands it runs, `git rebase --exec` among them, so the suite run
  that way re-initialised the outer repository, setting `core.bare` in its shared config, and committed onto
  its HEAD (`tests/unit/throwaway_git.py`, `test_throwaway_git.py`).
- T1 (S2a-2): step 8 against the writer schema, with each field's binding to its row, and the generated reader
  `$defs`, on every value field of the conformance inputs and on one-fault variants of five full fields and of
  one field of each row and form, drawn by the writer's strategies: what the writer accepts step 8 accepts,
  what step 8 refuses as `form_invalid` the reader refuses, and the converse. Where a form's own member waits
  for S2b or S3, step 8's verdict is the case files' expected reasons, so for those fields T1 holds the data,
  not step 8. The exceptions are grouped by kind, each kind with its reason, a mark its refusals must show,
  and the case files whose read field breaks the relation (12 for the first, 48 for the second), computed
  from the generated files as the test runs, an unlisted, stale or misplaced one failing it; the shortcut of
  validating a field against its form's definition is checked on every example; and the token lists step 8
  knows by member name are held to the writer's (`tests/spec_sync/test_t1.py`).
- Hypothesis properties of step 8, the S2 design's HP3 and HP5: one fault of a 154-fault catalogue in 21
  regions written from the text (the derivation, `source` and each value step 8 checks among them, and slips
  that a reader ignoring slips cannot pass) gives exactly the codes its rule gives, two faults in two parts
  give both, and members the reader does not know never change the outcome; a third law holds a label on a
  table to the Label column; 47 mutants of step 8 each killed at both sizes, 21 of them at the faults they
  name, the eleven rules S2a-2's review found untested among them
  (`tests/property/test_value_field_properties.py` in the records shard, `test_value_field_mutants.py` in a
  fourth CI shard, `step8_mutants`).
- Step 8's oracles read status objects from `provenance.md` section 1's table, never from step 8's own status
  rows, which a check compares with it (`tests/spec_sync/status_rows.py`, `test_status_rows.py`).
- A property of the one-slip relation against a neighbour generator written from section 10, the oracle the
  read and the name-overlap check do not share, with 12 mutants (`tests/property/test_slip_properties.py`).
- A table of every position in a material record and a read request where a member the reader does not know
  is ignored or refused, held to the text, the schemas (every object a read reaches, and every member of one
  that may hold a status object, has a row, or a deferred row naming the piece that will read it), the hosts'
  objects and the read (`tests/spec_sync/unknown_member_positions.json`, `test_unknown_member_positions.py`).
- A fourth fuzz target, raw bytes into step 8, with a fault seeded for CI's control behind two changes to one
  seed, no seed holding two of its three parts, and an oracle that sees a refusal step 8 misses, T1's third
  relation, shown failing in the suite (`tests/fuzz/read_field_bytes.py`, `field_oracle.py`). CI's fuzz job
  gives that control 600 s, and no longer replays the mutant tables.
- 24 case files that end at step 0 or 8 on checks S2a-2 builds are run at S2a-2, two of them since its fix
  round in place of two whose field is a form its row allows; 579 case files pass, and 298 wait for a later
  step (`tests/spec_sync/case_steps.json`).
- Each new check is shown failing on seeded faults.
- T1 sets each provenance object's `origin` to each other token of its row, in each base alone and beside each
  change inside the object, so that its relations see a member a read checks under one origin beside the
  others: 2,995 variants more, 4,657 in all. Its control: the reader `$defs` of b8a597d, which checked a
  derivation beside every origin, break relation 3 on a derived value's derivation varied with another
  origin, and on none of its variants that keep `derived` (`tests/spec_sync/test_t1.py`).
- CI fails closed. A merge to main runs every job and is never cancelled; the gate lists the paths that are
  documentation only and counts every other as code, both paths of a file moved included; and the one required
  check fails unless every job the gate asked for succeeded, so that a job skipped by mistake no longer
  passes. Every job runs on the image `ubuntu-24.04`, and every step under bash with `-eo pipefail`. Each
  pytest job writes a JUnit report, summarised on the run's page and kept 90 days
  (`scripts/report_test_durations.py`), whenever pytest ran (a job its timeout cancels has none: pytest is
  stopped before it writes it); each test records its CPU time beside its wall time, its own and that of the
  processes it started. The mutant searches and the audit controls run on Python 3.11 and 3.15, the supported
  range's ends, in jobs of their own (`--property-controls`), and every other test on all five Pythons.
  `tests/unit/test_ci_workflows.py` holds the workflows to their comments: the image, the gate's step, each
  job's condition and the result, that no test or script names a path the gate calls documentation, what each
  pytest command selects, that the controls' modules hold mutant searches and audit controls only, no
  `continue-on-error`, `PYTEST_ADDOPTS` or `PYTEST_PLUGINS`, no pytest setting in `pyproject.toml` that
  chooses tests, and the workflows README's jobs and shards; each check with a control in which it must fail.
- Each of step 8's mutants that HP3 kills is searched among its own faults: `missing_represents_accepted` and
  `named_state_text_unchecked` first, whose kills, searched whole, changed with the constants Hypothesis draws
  from the modules a process has loaded, then the other 21 searched whole, which could meet the same at any
  change (maintainer, 2026-10-16). Each dies at its first example at both sizes, alone and after the whole
  suite's collection, on Python 3.11 and 3.15; HP5's two are still searched whole
  (`tests/property/README.md`).
- Every verdict the tests take from the package's JSON Schemas comes from jsonschema-rs, a development
  dependency only (0.58.4; `tests/verdicts.py`), where it was python-jsonschema's alone. Tests that take few
  verdicts take both libraries' and fail with a `Disagreement` where they differ; loops take jsonschema-rs's
  alone, python-jsonschema giving the messages a failure prints and failing the test at once where it finds
  none (`tests/spec_sync/schemas.py`). Both read every schema at draft 2020-12, and
  `tests/spec_sync/test_schemas.py` holds every schema file to that draft and every pattern to what both read
  alike. `tests/property/test_validators_agree.py`, a Hypothesis shard of its own (`agreement`), holds the two
  to one verdict: on T1's inputs, every example at `deep` and at `dev` and `ci` every tenth of each kind,
  which holds each origin, change and base; on drawn fields, bodies, records and each fault family's faults,
  by the writer and the reader; and along each writer mutant's own search, up to the example where its verdict
  first differs from the package's. It lists, and checks exactly, every place that takes jsonschema-rs's
  verdict alone, with what compares it or why nothing does. Its controls give writer and reader mutants to one
  side, each of the 12 writer mutants the drawn faults had missed among them, and a pattern ended in `$` to
  both, and hold the pairs the properties use to both libraries. Every mutant still dies, at the same example
  as before wherever the same modules are collected; the agreement module brings
  `scripts/gen_reader_schema.py` into every shard, and Hypothesis draws constants from it, so in CI's shards
  20 of 430 kills move (`tests/property/README.md`, Mutants). The switch cut the CPU time of the whole suite
  on 8 workers from 2,617 s to 1,620 s, and of the writer shard at `ci` on 4 from 2,956 s to 1,477 s; T1's
  tests ran about 25 times faster; on CI the writer shard's tests went from 649 s to 338 s
  (`tests/README.md`).

## [0.1.0.dev1] - 2026-10-14

A development pre-release, published to rehearse the release workflow and to hold the name on PyPI. It holds
S1: strict JSON, RFC 8785 and the content hash; records, their store and the read up to step 5; and the
schemas and vocabulary of 0.1, whose files may still change before 0.1.0. The entries below are everything
up to this release.

### Added
- Architecture concept (`design/ARCHITECTURE_DRAFT.md`).
- Documentation architecture plan (`DOCUMENTATION_ARCHITECTURE.md`), contribution rules (`CONTRIBUTING.md`),
  security policy (`SECURITY.md`), intended use statement (`docs/regulatory/intended_use.md`), an empty
  anomaly registry (`docs/validation/known_anomalies.yaml`) and its issue template.
- Design revision: plain records as a complete form with OpenUSD as the primary binding; five value forms;
  versioned model families with golden test vectors, reference implementations and check points in
  records; declared uncertainty structures; per-field proxies; a source registry, three record tiers and a
  separate data licence; the core, family packages and library as separate components; the dielectric
  section; layered paths. Constraints 13 to 17 and the pull-request template with the data attestation.
- Distribution design: namespaced material identifiers; material cards in place of data sheets; static,
  archived releases with federation through an index and no hosted service; self-contained shipped USD
  layers; record checks as a core command (`python -m materica check`). Constraints 18 and 19.
- Model-assisted curation design: an MCP tooling layer (bring-your-own-key, deterministic tools, quotes,
  human review, fail-closed release, a gold set); convention witnesses for parameter sets; evidence,
  assistance and search-record provenance fields. Constraints 20 to 22; constraint 14 extended.
- Phasing for MIME 0.3.0: three feature sets, each feature tied to what it serves; MIME spikes before MIME
  work starts.
- Revision against two new principles (records hold facts, consumers declare choices; carry what the
  evidence supports): consumer declarations with three-valued checks; domains; specimen facts in place of
  proxy flags; named mixing rules picked by the consumer; no schema fallbacks; tables with schemes, ranges
  and edges; spreads that say what they represent, `not_reported` and interval-only values; independent
  witnesses; fits written back only as scoped overlays; a family `kind` for evolution families;
  failure properties under mechanics; biocompatibility as test evidence; an advisory index; rewritten
  spike controls. Constraints 23 to 25; constraints 6, 9, 13 and 14 revised.
- Simplification pass: sections specified when a consumer needs them (fluid, mechanical with failure,
  acoustic, radiological, magnetic, biocompatibility first; optical, thermal and dielectric later), with
  three rules that make adding one a minor schema change; a publishers file and a template repository
  from the first library release, with MIME as the first other publisher; prototypes before the package;
  the advisory index and Hugging Face items as notes for later.
- Evolution families in the core from the start: state and history (viscoelastic and rate-dependent
  models), with optional events defined independently of any solver.
- Decisions after the prototypes (2026-10-12): the scope is substances in and around the human body, never
  systems, with five rules (a transfer test, pairs, geometry as scene data, behaviour, entry); every record
  has a record type, `material` and `interface` being OpenMaterica's, so other namespaces can use the
  machinery for data that is not a material; the curated library under CC0-1.0; reference implementations live
  with their families, shipped as `openmaterica-families`; consumers write their own readers, mixing rules and
  evaluators, verified against conformance data; quotes for every value extracted from text or a table in
  the curated library; curation tools before the first library release; a `bulk` section for density and
  elemental composition; the layered path's USD form as a typed prim, needed by MIME 0.3.0; an anisotropic
  linear elastic family for bone; conditions separated from specimen facts, with a starting vocabulary;
  new conformance cases (derivatives at table knots and ends, in-range reports, mixing at the cell, record
  types, the stage's units, physics bindings). Constraints 26 and 27; constraints 14, 17 and 21 revised.
- Fixes after an independent review of that revision (2026-10-12): the transfer test replaced by a line
  between test specimens (in, with their shape and size as conditions) and made objects as built (out); the
  typed value beside each field's JSON string in USD deleted, and no `UsdPhysics.MaterialAPI` on shipped
  layers; an `overlay` record type, overlays as prims of their own applied only when declared, scoped by a
  hash of the consumer's model configuration; unknown record types skipped when listing and refused when
  referenced, with namespaced types specified only after a consumer prototypes one; a plain scene manifest;
  the layered path's USD form with an index per interval, since USD drops repeated relationship targets;
  `interval` and `composition` value forms; attenuation stored as an amplitude coefficient, with shear
  attenuation for solids; declared extrapolation as a consumer declaration; an unknown token refuses its
  field and an unknown condition gives "unknown"; run-time watches on every declared condition; a
  `marginals` uncertainty structure; quotes required by the curated library's policy and checked where
  present, with a hash fallback if the legal review rules quotes may not ship, and evidence excluded from
  the CC0 grant; the content hash over the whole record minus an exclusion list, with test vectors;
  "a consumer's computation" defined as its step, compiled program and gradient path, the core running at
  build, and the write-side tooling split into `openmaterica-authoring`; the first library release defined as
  the first archived release with a DOI; conformance suites; disease and treatment state as specimen
  facts; records in JSON only. The stiffness tensor for bone moved to stretch. Constraints 4, 5, 13, 14, 21,
  24, 26 and 27 revised.
- After an ecosystem survey of NVIDIA's schemas and the wider ecosystem, and its review: the USD binding,
  layered paths, label crosswalks and scene documents move into OpenMaterica 0.1, with no cut line; a region
  binds its material with the purpose `materica`, and `physics` is left to engines; an engine is declared as a
  model, written by an engine adapter from pinned engine crosswalks and checked per shape by `materica check
  --stage`; readers detect schemas by name, traverse instances, and refuse unloaded payloads, point-instancer
  prototypes and time samples; acoustic attenuation is registered as `/m`; label crosswalks read by name.
- OpenMaterica ships one engine crosswalk, for OpenUSD's `UsdPhysics`; a consumer writes and pins the
  crosswalk for any other engine it runs, drafted by a scaffold from the engine's schema file and compared
  with the schema file it pins by hash. The stamp on an engine material carries the APIs applied, each
  attribute's type and dimension and the unit convention, so the stage check re-derives values without the
  crosswalk and checks the stamp against its units.
- Names settled (maintainer, 2026-10-13): conformance suites, engine crosswalks and label crosswalks replace
  conformance profiles, engine maps and label mappings; identifiers renamed to match
  (`engine_crosswalk_invalid`, `family_suite_absent`, `--crosswalk`, `"suite"` in case files).
- Decisions before the first code (maintainer, 2026-10-13): the core depends on Python's standard library
  only, with `[check]`, `[usd]` and `[sample]` extras; engine results in `openmaterica[usd]`; scene documents
  built before declarations; the writer JSON Schemas the single source of structure, with typed shapes
  generated from them; the package typed (`py.typed`); a Python 3.11 floor under a standing rule; record
  checks that need a registry, a copy or the history moved to the library's tooling; SPDX headers on source
  files.
- The first code: the package (`pyproject.toml` with uv's build backend, `uv.lock`, `py.typed`, no run-time
  dependency, the licence as an SPDX expression); strict JSON reading (`materica.core.jsonio`), RFC 8785
  serialisation (`materica.core.canonical`) and the content hash (`materica.core.hashing`, exported as
  `materica.content_hash`); CI, with a sign-off check on every commit of a pull request.
- The read up to step 5: identifiers and versions matched in full, versions ordered by their components'
  lengths and digits (`materica.core.identifiers`); the vocabulary of schema 0.1, generated from the
  specification's tables (`schema/0.1/vocabulary/`, `materica.core.vocabulary`); the reader schema's checks by hand
  (`materica.core.envelope`); the record store, and steps 1 to 5 of a read (`materica.core.record`,
  `materica.core.resolve`); the request's own check and the read, which raises `NotImplementedError` where a
  step not built yet would decide it (`materica.core.read`); plain records from files (`materica.io.plain`).
  `materica.read` and `materica.load_records` join `materica.content_hash` as the public API.
- The JSON shapes of records, read requests and results, and case files, as TypedDicts generated from the
  schemas (`materica.shapes`); a read's results are read-only to a type checker (PEP 705, in `shapes.pyi`).
- Generators, which CI runs with `--check` in a job of its own: the vocabulary from the specification's tables,
  the reader schema and the typed shapes from the writer schemas (`scripts/gen_*.py`).

### Changed
- Names settled before the first release (maintainer, 2026-10-14): the project is OpenMaterica, replacing the
  working name the drafts used until then, since removed from the public files. The distribution is
  `openmaterica` and the package `materica`. The record namespace, family identifiers, USD binding purpose,
  attribute namespace and command are `materica`, and the USD schema classes take the prefix `Materica`.
  Library records are `materica/MAT-NNNN` and `materica/INT-NNNN`, and the registry prefixes are `OMAT-ANO-`,
  `OMAT-VER-` and `OMAT-MTH-`.

### Schema
- Schema 0.1.0 (draft), settled before the first code: what a reader refuses as malformed JSON, numbers read
  as doubles, `null` read by where it is, one schema-version pattern, the reader schema's scope, how a
  material reference resolves among the records supplied, the request checked first, reason multiplicity,
  case-file claims, variants, exact comparison and operations, and the namespace `conformance` reserved for
  conformance fixtures (`docs/specification/changes.md`).
- The JSON Schemas of 0.1, each `$id` its path under `https://w3id.org/materica/schema/0.1/`: the writer
  schema's envelope and body structure, edited by hand (`record.writer.json`); the reader schema, generated
  from it (`record.reader.json`); the read request and result (`read_request.json`, `read_result.json`); the
  schema of case files (`case.json`); and the vocabulary, generated from the specification's tables
  (`vocabulary/`). The specification's member tables are checked against them.

### Families
### Data
### Verification
- The conformance-case runner. Of the 416 case files, the 51 `content_hash` cases (HS-001 to HS-003) run and
  pass; the 365 reads and listings are reported as not yet runnable, never as passed. Nine broken
  implementations, one fault each, each fail a real case.
- Property tests of the JSON reader, the RFC 8785 serialisation and the content hash, under a draw-rejection
  audit and a feature audit; 32 mutants of the core, each killed by its property within the `ci` profile's
  examples at both tree sizes; Hypothesis profiles `dev`, `ci` and `deep`, the last at the original sizes.
- Atheris fuzzing, weekly: raw bytes into the JSON reader, checked against a reference reader built from the
  standard library; and the Hypothesis properties driven by Atheris, whose findings the property tests replay
  and shrink. Each run first shows that both find a fault seeded in the reader.
- All 417 case files run and pass, each under every configuration of claims it holds for: with the hash suite
  (409), without it (347), and with the fits and reference data suite (408). PR-330 gains an arm: a tolerance
  beside `operating_conditions` that is not an object (`read_side_contract.md` section 1). Fifteen more broken
  implementations, of the read and the listing, each fail a real case. Every case file reads alike through the
  reader under test and a reference reader that shares no code with it, and is valid against `case.json`.
- Checks that what is written twice agrees: the specification's member tables and the schemas, and the token
  lists the schemas write by hand; the envelope checks and the reader schema on every conformance input; each
  `CASES.md` and its case files; and the map of case files to the steps that run them (`tests/spec_sync/`).
  Each module's imports, relative ones included, against the layers, and the shapes' against the standard
  library.
- Property tests of the envelope checks against the reader schema, of versions, and of the laws of a read up to
  step 5; 35 more mutants, each killed within the `ci` profile's examples at both sizes. CI runs the property
  tests in two shards side by side. A third Atheris target drives these properties, and first shows that it
  finds a fault seeded in the read.

### Security
### Known Anomalies
- Registry created, with no entries.

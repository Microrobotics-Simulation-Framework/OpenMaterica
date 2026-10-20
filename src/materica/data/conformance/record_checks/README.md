# Record-check cases (RC)

The cases of `materica check` and of any other checker of records, on the write side
(`docs/specification/README.md`, "Suites and case numbers"). The suite holds, so far, the cases of the curation
track's first piece: page-text documents, the place of a quote in a copy, and the comparison of a quote with its
place (`page_text.md`, RC-220 to RC-226); the copy hash's form (RC-031); the comparison itself (RC-032); and the
vectors of `quote_sha256` (RC-033). None runs yet: the core's record checks come with S5, and these files with
C2, the curation track's quote attach-and-verify, whose core half runs them (`tests/spec_sync/case_steps.json`).

`CASES.md` beside this file gives one row per case file: what the arm tests, the item of the specification that
decides its answer, and the answer. Start there.

## Reading a case

A record-check case names the records it gives the checker in `inputs.records` and the page-text documents in
`inputs.page_texts`, and has no `request` unless it names the `quote_sha256` operation. `expected.items` lists
the findings and `expected.listing` the facts listed without failing, each `{"item", "document", "pointer"}`,
compared as sets, and `compare.rules_compared` names the rules whose findings and listed facts the case
compares (`docs/specification/README.md`, "Case files"). In this suite:

- The comparison of a quote with its place gives one report per quote under RC-032, at the quote's evidence
  (`/body/sections/bulk/fields/density/provenance/evidence`): the check's failure as a finding, `not_checked` as
  a listing, a pass as neither, whichever item of `page_text.md` section 3 decides it (RC-223 to RC-226 test
  those items).
- A place that `page_text.md` section 2 flags is a finding of RC-222 at the evidence's `copy`; its quote is
  then `not_checked` (section 3 item 3).
- A page-text document that section 1 refuses is a finding of RC-220 at the document itself (the pointer
  `""`), and it is set aside, so a quote placed in it is `not_checked` (section 1 item 2, section 3 item 1).
  Each such arm places a misquote there, so that a checker that flags the document but still uses it fails the
  quote and is caught.
- A page-text document among the records a check is given is a finding of RC-221 at the document.
- RC-031 flags `copy.sha256` at `.../copy/sha256`, and evidence without the document's identity and version
  at the evidence.
- `{"operation": "quote_sha256", "text": ...}` gives the hash of `text`'s normalised form as `value`, with the
  status `met` and no reason (RC-033).

No arm's answer is a pass (see "What the cases cannot show"). Every arm of RC-225 whose answer is `not_checked`
by section 3 item 7 places a misquote, so that a checker without that rule fails it and is caught; the controls
beside them place the misquote where the rule does not apply. The arms of RC-226 that end there, and RC-222's
`one_span_over_furniture`, quote their place as printed: they test that nothing else fails them (the column
check, the flag).

## The fixtures

Every record and document here is a conformance fixture (`record_format.md` section 7 item 1): illustrative,
stating nothing about any material or paper.

- **The record**, `conformance/quote_fixture` 1.0.0: one value, `bulk.density`, 1060 kg/m3, extracted from a
  table of the paper `https://example.org/conformance-fixture-paper` (`version_of_record`). Only its evidence
  differs from arm to arm (its source's locator stays the PDF table's column 2, so that a checker comparing the
  wrong locator is caught), and the arm's file is named after the first case that uses it. The quotes are
  chosen to exercise the comparison, not to support the value.
- **The copies** are files no one holds: each copy's hash is the SHA-256 of a stated text ("conformance fixture:
  stands for the curator's PDF copy of the paper", and the like for the XML copy, another copy, and another XML
  copy set in other typography).
- **`page_text_pdf.json`**, the PDF form, ten pages, two readings: page 1 a title; page 2 line-end hyphens of
  every kind (after a letter, after a digit, after a space, U+2010, U+00AD, and U+2212, which is none); page 3
  a table, a raised exponent, and a footnote and page number marked as furniture; page 4 continuing page 3's
  last sentence after its running head; page 5 a page of content; pages 6 and 8 joined across page 7, which
  holds only its page number; page 9 a doubtful range, U+FFFD, U+E000, U+FFFE, U+50000, a column jump, and a
  doubtful range ending where text starts; page 10 ten short hyphenated lines.
- **`page_text_xml.json`**, the XML form: the string value and every element of a small article in the JATS
  manner, with an empty element, a paragraph whose own line feed breaks `counterproduc-` and `tively`, a
  paragraph holding `bold` and `sup`, a MathML formula (a namespaced step in its path), and two tables, whose
  cells carry `cell_columns`: Table 2 with a dash cell and a row label holding U+E000; Table 3 with a cell
  spanning two columns, a cell spanning two rows, a nested table and a value in `bold`, each row holding
  U+E000 in its first cell.
- **`page_text_xml_typography.json`**, the XML form of another XML copy: a methods section of three paragraphs
  whose typography the comparison must not fold (`10 mS`, curly quotation marks, U+2212 in `cm−3`, U+2010 in
  `5‐6`) or must (the ligature U+FB01, which NFKC maps to `fi`; U+200B inside a word, which the first step
  removes). RC-032's arms on it pin the normalised form a `quote` is compared by.
- **`page_text_pdf_*.json` and the other `page_text_xml_*.json`**: each one change from the first two, named by
  the file.

## What the cases cannot show

- **A pass.** RC-032's second half, how a number is found in the characters `value_characters` marks
  (`page_text.md` section 3 item 8), is specified with the record checks and not written yet. No answer here
  rests on it. An arm without `value_characters` reads `not_checked` by that sentence: a matching quote is
  `not_checked`, a misquote fails. Every arm that marks the value is decided before that half: by section 3
  item 2 or 4 (a failure), or by item 7 (`not_checked`, which overrides items 6 and 8), which is why the value
  arms of RC-226 place a row label holding U+E000 in the located text. So RC-032's row's "or whose value's
  numbers are not where the place marks the value" has no arm.
- **The report's hash.** Section 3 item 1 has the report name the page-text document's hash; a case compares
  the rule, the document and the pointer only.
- **RC-034's place arm and RC-221 in a release.** A stamped copy's place in a release, and a page-text document
  in a release, need a release and a source registry as inputs, which the case-file format does not hold yet.
- **Other rules.** `compare.rules_compared` limits each case to the rules it tests, so what other record
  checks find on the fixtures (S5's) is not compared.
- **Unicode.** U+50000 is unassigned in Unicode 14.0 to 17.0 (Python 3.11 to 3.15); a later version that
  assigns it would change the two arms that use it. U+FFFE and U+FDD0 are noncharacters, `Cn` in every
  version.

## How the cases were made and checked

The cases were drafted with AI assistance (Claude, Anthropic) from the specification text alone, before any
code that runs them. Each arm states the outcome intended by reading the text, and a model of `page_text.md`
sections 1 to 3, written apart in the same generator, had to give the same. Then:
- every record's content hash, and every page-text document's hash (RFC 8785 over the whole document), was
  computed by two implementations (Python `rfc8785` 0.1.4, Node `canonicalize` 2.0.0), and every
  `copy.page_text` is a page-text document's hash but in the one arm that names the file's bytes on purpose;
- every `quote_sha256`, in the vectors and in the records, was recomputed by a normalisation written in
  JavaScript (ICU's NFKC), and the vectors on Python 3.11 to 3.15;
- every finding's and listing's document is an input of its case, and its pointer a member of that input;
- an independent verifier, written from the text alone without the generator, agreed with every answer: with
  all 167 of a first run, and with all 177 once the arms its refutation asked for were added (a step order of
  the normalisation, offsets in code points, two hyphens read two ways, a single span over furniture, more of
  section 1's shape, the source's locator). Of the faults it seeded into its own implementation, each is caught
  by some file but five, of rules no arm reaches yet: `lowered` ranges, a `text_extraction` that is not a
  string, elements out of document order, an empty `spans`, a span without `characters`;
- after a review of those 177, 20 arms were added, checked by the generator's model alone (no independent
  verifier has seen them): nine of RC-226 whose span names the value's row, table or document element, or whose
  value is marked across two cells (`page_text.md` section 3 item 4), a control among them, seven of which give a
  checker that takes the cell from the element the span names another answer (one of the seven only once a number
  half finds the record's number where the value is marked); nine of RC-032, a control among them, that a checker
  comparing a `quote` by another form than the hash's answers otherwise (letter case, dashes or quotation marks
  folded, NFC for NFKC, the format characters kept, `str.isspace` runs, the located text normalised in its
  `White_Space` runs alone); and two of RC-222 (an XML span past its element's end within the document's text,
  XML spans out of order). Each such fault, written into a copy of the model, gives some file an answer other
  than its own, and gave none of the first 177 one.

The scripts that generated these files are not part of the repository. The files are the source.

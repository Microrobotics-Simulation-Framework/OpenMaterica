# Page-text documents and the place of a quote

Schema 0.1.0, draft. Conventions, suites and case numbers: `README.md`. The quote, its hash and the copy:
`provenance.md` section 4. Rationale: AD 4.7, 6.2 and 8.3.

A record's quote is checked against the copy of the document its curator read (`provenance.md` section 4). A
checker that reads only JSON cannot read a PDF or an XML file, so the copy's text reaches it as a page-text
document: the text of one copy, as one named text extraction gave it. This document says what a page-text
document holds, how a record names the place of a quote in a copy, and how a checker compares the quote with
that place.

## 1. Page-text documents

1. A page-text document is one JSON object, read by `record_format.md` section 1 item 6, holding the text of
   one copy of one document as one text extraction gave it. It is not a record: it has `document_type`
   `page_text` and no `record_type` (`record_format.md` section 3 item 2). [RC-220]
2. Its members are those of the table below, and no others. A checker reads a page-text document of its own
   `MAJOR.MINOR` only (`record_format.md` section 8); one of another version, or one that breaks this
   section's shape, it flags and sets aside, as if it had not been given. [RC-220]

| Member | Required | Contents |
|---|---|---|
| `page_text_schema_version` | yes | the schema version, `MAJOR.MINOR.PATCH` |
| `document_type` | yes | `page_text` |
| `document` | yes | the document the copy is of, `{"identifier", "version"}`, as a provenance object's `document` names one (`provenance.md` section 2) |
| `copy` | yes | `{"sha256"}`: the SHA-256 of the copy's bytes, written as `copy.sha256` is in a record (`provenance.md` section 4 item 2) |
| `text_extraction` | yes | the extraction that wrote the document (item 11), a string |
| `readings` | yes | the readings of the copy that the extraction made and compared, a non-empty list of strings, the reading whose text the document holds first (item 5) |
| `pages` | for a PDF | one entry per page of the copy, `{"page", "text", "doubtful", "jumps", "furniture", "raised", "lowered"}` (items 4 to 7) |
| `text`, `elements` | for an XML file | the text of the document element, and one entry per element, `{"element", "characters"}`, with `cell_columns` for a table cell (items 8 and 9) |

3. A page-text document holds `pages`, or `text` and `elements`, never members of both kinds. A copy of any
   other kind (a web page, a plain-text file, a scanned PDF with no text) has no page-text document in schema
   0.1.0. [RC-220]

```json
{"page_text_schema_version": "0.1.0", "document_type": "page_text",
 "document": {"identifier": "doi:10.1000/xyz123", "version": "version_of_record"},
 "copy": {"sha256": "sha256:4f1c..."},
 "text_extraction": "openmaterica-authoring 0.1.0, pdf_text 1",
 "readings": ["pypdfium2 5.14.0 (PDFium 156.0.8076.0)", "pdfminer.six 20260107"],
 "pages": [{"page": 1, "text": "Densities of soft tissues\nA. Smith",
            "doubtful": [], "jumps": [], "furniture": [], "raised": [], "lowered": []},
           {"page": 5, "text": "Smith et al. 5\nTable 2\nTissue Density (g cm-3)\nLiver 1.06 ± 0.02",
            "doubtful": [], "jumps": [14], "furniture": [[0, 14]], "raised": [[43, 45]], "lowered": []}]}
```

(Pages 2 to 4 are left out of the example; a document lists every page.)

4. `pages` lists every page of the copy in the order of the copy's file: the first entry's `page` is 1, and
   each next entry's is one more. A page's `text` is the text drawn visibly on the page within its CropBox, in
   the extraction's reading order. Text drawn invisibly (text rendering mode 3, as the OCR layer of a scanned
   page is; recalled: ISO 32000-1:2008, clause 9.3.6) or wholly outside the CropBox is left out, and text whose
   visibility the extraction cannot judge (clipped, or under an image) is doubtful (item 5). Each line ends
   with U+000A (LINE FEED), except the last; no line ends with `White_Space` (`provenance.md` section 4 item
   4), its U+000A apart; and the text holds no C0 control character (U+0000 to U+001F) other than U+0009 and
   U+000A. A character the extraction could not map to Unicode is U+FFFD. [RC-220]
5. `readings` names each reading of the copy that the extraction made, as `text_extraction` names an
   extraction; the reading whose text the document holds comes first. A PDF is read at least twice, by
   different programs, and no quote placed in a document that names fewer than two different readings passes
   (section 3 item 7). An XML file is read once. `doubtful` lists the ranges of a page's `text` that the
   extraction does not vouch for. The readings are compared glyph by glyph: each reading's characters are
   matched to the glyphs drawn on the page by their positions, never by their order in the reading's text,
   and compared in their normalised form (`provenance.md` section 4 item 4). A character of the page's text is
   doubtful where the extraction could not map its glyph, or could not judge it visible (item 4); where
   another reading gives its glyph otherwise, or gives it no character; and, where another reading gives a
   character for a glyph that the page's text has none for, on each side of where that character would stand.
   Each range is `[start, end]`, counted as a span's `characters` are (section 2 item 3), within the page's
   text; the ranges do not overlap and are in increasing order. [RC-220]
6. `jumps` lists the line feeds of a page's `text` after which the next line does not continue the one before
   it in reading order: the text moves to another column, or to another region of the page (a table, a
   caption, a box, a footnote, a running head), as the extraction judges from the glyphs' positions. Each is
   the position of a U+000A in the page's text, counted from 0, in increasing order. The readings' orders are
   not compared: a table that one reading takes by rows and another by columns is not doubtful for that, and a
   quote whose located text holds a jump is not checked (section 3 item 7). [RC-220]
7. `furniture` lists the ranges of a page's `text` that are the page's furniture, not its content: running
   heads and feet, page numbers, line numbers, footnotes and marginal notes, as the extraction judges them.
   `raised` and `lowered` list the ranges of a page's `text` set above or below its line's baseline
   (superscripts and subscripts: exponents, footnote markers, the digits of a chemical formula), as the
   extraction judges from the glyphs' boxes and sizes. The characters are those the glyphs map to, so a `3`
   set raised after `10` reads `103` in the text, with the `3` in `raised`. Each is a list of ranges, as
   `doubtful` is. Every page holds all five of `doubtful`, `jumps`, `furniture`, `raised` and `lowered`, each
   empty where the extraction finds nothing, so that a checker can tell "none found" from "not looked for".
   [RC-220]
8. For an XML file, `text` is the string value of the document element: the characters of every text node it
   holds, whitespace-only ones included, in document order, after the XML processor has normalised line ends
   and replaced character references and the predefined entities; comments, processing instructions and
   attribute values add nothing (recalled: the string-value of XPath 1.0). A file that refers to an entity it
   does not declare itself (one an external DTD declares) has no page-text document in schema 0.1.0.
   `elements` lists every element of the document, the document element first, in document order. Each entry
   holds `element`, the element's path (item 9), and `characters`, the range of `text` that is the element's
   string value, counted as a span's `characters` are, except that it is empty (`start` equal to `end`) for an
   element with no text. An XML file's text has no doubtful ranges, jumps, furniture or raised text: what the
   file marks (JATS's `sup` and `sub`, for example) its elements say. [RC-220]
9. An element's path is absolute: one step per element from the document element down, each step `/`, the
   element's name and `[n]`, `n` being its position, from 1, among its parent's child elements of that name
   (the document element's is 1). An element in no namespace is named by its local name; one in a namespace by
   `{`, the namespace's URI, `}` and its local name. A path matches `(/(\{[^}]+\})?[^/{}\[\]]+\[[1-9][0-9]*\])+`
   in full, and a file with a namespace URI holding `}` has no page-text document. So the third `p` of the
   second `sec` of a JATS article's body is `/article[1]/body[1]/sec[2]/p[3]`, and a MathML formula in it
   ends `/{http://www.w3.org/1998/Math/MathML}math[1]`. Every step carries its position, so each element has
   one path, and a checker compares paths code point for code point, never resolving one against a file. An
   entry MAY also hold `cell_columns`, where its element is a table cell and the extraction knows the file's
   table model (JATS's: `tr`, `td` and `th`, with `colspan` and `rowspan`): `[first, last]`, the columns the
   cell occupies, both included, counted from 1 as a table locator counts them (`provenance.md` section 2
   item 2), every cell before it that spans rows or columns taken into account. [RC-220]

```json
"elements": [..., {"element": "/article[1]/floats-group[1]/table-wrap[1]/table[1]/tbody[1]/tr[2]/td[3]",
                   "characters": [8812, 8823], "cell_columns": [3, 3]}, ...]
```

10. A page-text document carries no content hash member. Its hash is computed as a scene document's
    (`geometry.md` section 1 item 5): the whole document serialised by RFC 8785 and hashed with SHA-256,
    nothing excluded, written as `sha256:` and 64 lowercase hexadecimal digits. [RC-032]
11. `text_extraction` names the program that wrote the document and its version, and `readings` names each
    reading with the version of each library it reads the file with: together, every version that can change
    the document. An extraction whose output changes takes a new name or version. A record's
    `extraction.text_extraction` (`provenance.md` section 3) names the extraction that matched the quote when
    the value was extracted; the page-text document its `copy` names later may come from another. [not yet
    covered]
12. A page-text document holds the whole text of a copy: the publisher's text and, in a stamped copy, the
    stamp's personal data. It stays beside the copy in the curator's private store, and never enters a
    published repository or a release (`provenance.md` section 4 item 6). A check of a library flags one found
    in it. The curator keeps every page-text document a record's `copy` names: another extraction, or the same
    one under another library version, writes another text, in which the place does not count. [RC-221]

## 2. The place of a quote in a copy

1. Where an evidence's `quote` or `quote_sha256` is present, its `copy` MAY name the quote's place in that
   copy: `page_text`, the hash of the page-text document the place counts in (section 1 item 10), and `spans`,
   a non-empty list of spans. The two are present together or not at all. A place is one quote's: a quote of
   the conditions, or of an exponent, made apart from the value's has its own evidence entry and place. The
   place holds for one copy and one extraction, not for the document version, so it lies with `copy` outside
   the content hash (`record_format.md` section 9): whoever locates the quote in another copy replaces `copy`,
   place included, with no new version of the record. [RC-222] A released record's `copy` holds `page_text`
   and `spans` only where the source registry records that copy, by its SHA-256, as not stamped with personal
   data (`provenance.md` section 8): a span's offsets on a stamped page, and the hash of a text that holds the
   stamp, are taken from the stamped copy (`provenance.md` section 4 item 6). [RC-034]

```json
"copy": {"sha256": "sha256:4f1c...", "retrieved": "2026-10-11", "page_text": "sha256:9b07...",
         "spans": [{"page": 5, "characters": [47, 64], "value_characters": [53, 64],
                    "boxes": [[72.0, 600.2, 161.4, 611.0]]}]}
```

2. A span is `{"page", "characters"}`, with `boxes` and `value_characters` optional, where the page-text
   document holds `pages`; and `{"element", "characters"}`, with `value_characters` optional, where it holds
   `elements`. `page` is the page of that number in the page-text document: a position in the copy's file,
   counted from 1, not the label printed on the page. `element` is a path the page-text document lists.
   [RC-222]
3. `characters` is `[start, end]`: two whole numbers with `0 <= start < end`, counting Unicode code points
   from 0, never UTF-16 code units or bytes, `end` excluded. They count in the span's text: its page's `text`,
   or its element's string value (the range of the document's `text` that the element's `characters` give).
   `end` is at most that text's length. [RC-222]
4. `boxes` holds one rectangle for each line the span's characters touch, in order (a line's U+000A belongs to
   that line), `[x0, y0, x1, y1]` with `x0 <= x1` and `y0 <= y1`, in the page's default user space: units of
   1/72 inch, with the origin and axes the page's content is drawn in, before the page's `/Rotate` is applied
   (recalled: ISO 32000-1:2008, clause 8.3.2.3). They let a viewer draw the quote on the page; a checker does
   not compare them with the page. [RC-222]
5. `value_characters` marks, on one span of a place at most, the characters that print the value the evidence
   supports: `[start, end]`, counted as `characters` are and lying within them. The value's numbers are read
   there alone (section 3 item 8), so that a number elsewhere in the quote, a neighbouring column's or a row
   label's, never stands for the value. [RC-222]
6. The spans are in document order and do not overlap. For a PDF, each span lies on a later page than the one
   before it, and where a place has more than one span, no span overlaps a `furniture` range. The text left
   out between two spans of a PDF is the rest of the first span's page, every page between, and the start of
   the second span's page; it holds nothing but `White_Space` (`provenance.md` section 4 item 4) and text
   within a `furniture` range of the page it is on. For an XML file, each span starts at or after the end of
   the one before it, both counted in the document's `text`; the text left out between them holds nothing but
   `White_Space`, and where it is empty, neither span's element is the other's or holds it. The located text
   of the spans is their texts joined by U+000A, in order. A sentence broken by a page of content, a full-page
   table for one, has no place: the text left out is not furniture. [RC-222]

## 3. Comparing a quote with its place

1. A checker given a record and page-text documents checks each quote whose `copy` names a place, against the
   page-text document whose hash is `copy.page_text`, and its report names that hash. Where it was given none
   with that hash, or `copy` names no place, it reports `not_checked`, never a pass. Locating a quote in a copy
   is a curation tool's work: the tool writes the place into that copy's `copy`. So the check serves a curator
   re-checking against the page-text documents they keep, and anyone whose extraction writes the same document
   from an identical copy (an XML file fetched byte for byte, read by the same extraction). Anyone else makes a
   page-text document of their own copy with a curation tool, which locates the quote in it and writes their
   `copy`, and the check runs against theirs. [RC-032]
2. The page-text document must be of the record's copy: its `copy.sha256` and its `document` must equal the
   evidence's, each string compared code point for code point. Where one differs, the check fails. [RC-223]
3. A place that section 2 flags gives `not_checked`, never a pass, whatever items 4 to 6 and 8 would find.
   Item 2's failure stands. [RC-225]
4. Where the page-text document holds `elements` and the evidence's locator is a table locator, the place is
   compared with the locator by where the characters that `value_characters` marks lie in the document's
   `text` (a span's text is a range of it, section 2 item 3), whatever element the span names. Each such
   character that lies within an element holding `cell_columns` counts in the innermost such element, and the
   locator's column index must lie between that cell's first and last columns; where it does not, the check
   fails. So a value marked through a span on its row or its table is checked as through a span on its cell,
   and a value marked across two cells is checked against each. Elsewhere the place is not compared with the
   locator: whether the quote stands in the table, row and column the locator names, in a PDF above all, is
   the review's (AD 8.7). [RC-226]
5. A line-end hyphen is U+002D (HYPHEN-MINUS), U+2010 (HYPHEN) or U+00AD (SOFT HYPHEN) that follows a letter
   (general category `L`) and is followed by U+000A, in a page's text or at the join of two spans on different
   pages. An XML file's text has none: its line feeds are the file's formatting, not line ends. A reading of
   the located text takes each line-end hyphen one of three ways: as printed (both characters kept), joined
   (the hyphen kept, the line feed removed) or dropped (both removed). A located text with `k` line-end hyphens
   has `3^k` readings. So `counterproduc-` at a line's end before `tively` matches `counterproductively`, and
   `electromagnetically-` before `actuated` matches `electromagnetically-actuated`: an extraction cannot tell
   the two kinds of hyphen apart, so every reading is tried. `5-` at a line's end before `10 K` is read only as
   printed. [RC-224]
6. A `quote` matches its place where its normalised form (`provenance.md` section 4 item 4) equals that of a
   reading of the located text; a `quote_sha256` matches where it is the hash of a reading's normalised form.
   Where no reading matches, the check fails. [RC-032] [RC-224]
7. Whatever item 6 finds, the check reports `not_checked`, never a pass and never a failure: where the
   page-text document holds `pages` and its `readings` names fewer than two different readings; where the
   located text overlaps a `doubtful` range, holds U+FFFD, or holds a line feed its page's `jumps` lists; where
   the quote or the located text holds a code point of general category `Cn` in the checker's Unicode database
   (one unassigned, which a later version of Unicode may assign and normalise otherwise, or a noncharacter), or
   the located text one of category `Co` (private use, where a symbol font may put a minus sign); and where the
   located text holds more than eight line-end hyphens. The failures of items 2 and 4 stand whatever this item
   finds. [RC-225]
8. The value's numbers (`provenance.md` section 4 item 3) are read in the characters `value_characters` marks,
   and nowhere else in the quote; with no `value_characters`, that half of the check reports `not_checked`.
   How a number is found there is specified with the record checks; it reads a page's `raised` and `lowered`
   text, and an XML file's elements, so that an exponent or a footnote marker is never read as a digit of the
   value. [RC-032]

## Cases

| Case | Suite | Tests |
|---|---|---|
| RC-220 | record checks | a page-text document breaking section 1 is flagged and set aside: a member missing or not in the table, members of both kinds, `readings` empty, a page without one of its five lists, pages out of order or not starting at 1, a line ending in `White_Space` before its line feed, U+000D or another C0 control but U+0009 and U+000A in a page's text, a jump not at a line feed, ranges overlapping or outside the text, an element path not matching the pattern, `cell_columns` reversed or below 1, an element's range outside `text`, another `MAJOR.MINOR` |
| RC-221 | record checks | a page-text document in a library's repository or release is flagged |
| RC-222 | record checks | a place breaking section 2 is flagged: a place beside no `quote` or `quote_sha256`, `page_text` without `spans` or the reverse, a span with both or neither of `page` and `element`, or of the other kind than its page-text document, `boxes` beside `element`, a page or element the document does not hold, `characters` empty, reversed or past the text's end, a box with `x1 < x0` or `y1 < y0`, a number of boxes other than the lines the span touches, `value_characters` outside its span or on two spans, spans out of order or overlapping, two spans on one page of a PDF, text other than `White_Space` and furniture left out between two spans (a quote stitched from two pages, with its control: only furniture left out), a span of a place with several spans overlapping furniture, two spans of an XML file with nothing between them in one element or one inside the other's |
| RC-223 | record checks | a page-text document whose `copy.sha256` or `document` is not the evidence's fails the check |
| RC-224 | record checks | a line-end hyphen read as printed, joined and dropped, each matching; a hyphen across two spans on consecutive pages; no reading but as printed for a hyphen after a digit (`5-` before `10 K`) or after a space, and no line-end hyphen in an XML file's text (a dash cell before a value); a quote matching no reading fails; the same by `quote_sha256` |
| RC-225 | record checks | `not_checked` where the located text overlaps a doubtful range, holds U+FFFD, holds a jump, holds a private-use code point, or holds nine line-end hyphens; where the quote or the located text holds a code point unassigned in the checker's Unicode database, or a noncharacter; where a document holding `pages` names one reading; where section 2 flags the place |
| RC-226 | record checks | a value marked in an XML table cell whose `cell_columns` do not hold the locator's column index fails, and one whose do passes; a cell after one spanning two columns; a value marked through a span on its row, and one marked across two cells |

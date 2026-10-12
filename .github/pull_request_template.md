## Summary

<!-- What this changes and why. For a schema, family or data change, name the consumer that needs it. -->

## Checklist

- [ ] Every commit is signed off (`git commit -s`), certifying the Developer Certificate of Origin.
- [ ] Schema change: specification text, conformance cases, schema files, reader change, `changes.md` and a
      CHANGELOG entry under **Schema** are all in this pull request.
- [ ] Family: definition, golden vectors, reference implementation and named consumer; no released version
      was modified.
- [ ] Not applicable: no schema or family change.

## Data attestation (only if this adds or changes library data)

- [ ] I attest that each value in this pull request was extracted from the cited source by the method
      recorded for it, or comes from a measurement or fit I describe; that every value extracted from text
      or a table carries its verbatim quote and locator, or the quote's hash if the legal review has ruled
      that quotes may not ship; that every value a language model helped draft is recorded as such and was
      checked by a named reviewer against the source at its locator; that nothing was copied in bulk from a
      secondary database; that each value's tier matches its source's redistribution status in the source
      registry; and that I have the right to contribute the shipped values under CC0-1.0. Quotes kept as
      evidence remain the source's text.

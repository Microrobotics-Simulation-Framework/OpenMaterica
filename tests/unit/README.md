# Unit tests

Tests by example, for what the conformance cases and the properties do not reach:

- the edges of the specification, which a property draws too rarely to rely on (the largest double, the
  overflow boundary, nesting 64 and 65 deep), and RFC 8785's own vectors;
- faults that only cases not yet runnable hold (an encoded surrogate and `Infinity`, held by plain-read case
  PR-002);
- rules over the source files: what `materica.core` may import, and the SPDX header on every Python file;
- the checks in `scripts/`, and the audits of `tests/property/`, each against inputs it must refuse.

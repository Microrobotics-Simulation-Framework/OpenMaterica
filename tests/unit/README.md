# Unit tests

Tests by example, for what the conformance cases and the properties do not reach:

- the edges of the specification, which a property draws too rarely to rely on (the largest double, the
  overflow boundary, nesting 64 and 65 deep, a version component longer than `int` reads), and RFC 8785's own
  vectors;
- faults that only cases not yet runnable held when they were written (an encoded surrogate and `Infinity`,
  held by plain-read case PR-002);
- the read's API: the forms a request may be given in, the misuses that raise, and the steps not built yet,
  which raise rather than answer (`test_read.py`);
- rules over the source files: what each layer may import, what `materica.core` and `materica.shapes` may
  import, relative imports included, the SPDX header on every Python file, that each property module is in
  one shard, and that the classifiers and `requires-python` name the Pythons the `tests` job runs;
- the scripts in `scripts/`, the generators included, and the audits of `tests/property/`, each against
  inputs it must refuse;
- the table evaluator against every table evaluation case, which the conformance runner never runs against
  it, since OpenMaterica claims none (`test_evaluate.py`), and the edges of its text:
  adjacent doubles, values spanning every double, `-0` at a knot and at an edge, an edge outside the readable
  range, log-log values halfway between two doubles (rounded to even) and an irrational one (against
  `sqrt`);
- the typed shapes against what the reader gives: each member the schemas declare whole admits the float a
  JSON number reads as (`test_shapes.py`).

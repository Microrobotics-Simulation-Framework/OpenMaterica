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
- the schema verdicts' switch point (`tests/verdicts.py`, `spec_sync/schemas.py`): a value the two JSON Schema
  libraries judge differently fails the test at once, naming both verdicts, a mutant search never takes it
  for a kill, and both read a resource at draft 2020-12 whatever it declares (`test_verdicts.py`);
- the typed shapes against what the reader gives: each member the schemas declare whole admits the float a
  JSON number reads as (`test_shapes.py`);
- the Hypothesis profiles: a runner's environment changes none of their settings, none is derandomised, and on
  a runner two seeds draw different examples and one seed what it draws elsewhere, each check run in fresh
  processes with and without a runner's variables, its controls the registration as it was before
  2026-10-17 and `derandomize` put back (`test_hypothesis_profiles.py`).

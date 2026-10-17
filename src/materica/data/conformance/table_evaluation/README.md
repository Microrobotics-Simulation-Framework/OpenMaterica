# Table evaluation cases

The cases of the table evaluation suite (TE): what a consumer's own evaluator of a table must return
(`docs/specification/read_side_contract.md` section 7). `CASES.md` lists every case file with its table, its
points and its expected answer; the conformance tree's `README.md` explains how to read a case. OpenMaterica's
own code claims no TE: a consumer that evaluates tables in its own code, in JAX say, runs these files against
its evaluator.

## A case

Each file is one `evaluate` operation (`docs/specification/README.md`, "Case files"): one table, as
`record_format.md` section 6 gives it, the axis condition aside, and a list of axis values `at`. It supplies no
inputs. `expected.evaluations` holds one entry per value, in order:
- inside the readable range, off every edge: `in_range` true, the value and the derivative; at an interior
  knot strictly inside the readable range the derivative is `{"left", "right"}`, of which the side the
  evaluator declares is compared; at an end of the readable range it is the one from inside, whatever side
  the evaluator declares; where the readable range is one point it is `"none"`, which passes only absent or
  NaN;
- at a declared edge, and across one from the readable range: `{"refused": true}`, which passes only where the
  evaluator reports the refusal and each number it returns is absent or NaN, never finite or infinite; every
  other entry passes only where the evaluator reports no refusal;
- elsewhere outside the readable range: `in_range` false, the value at the range's nearest end, taken from
  inside it, and a derivative of 0; each number also passes absent or NaN.

`compare.relative_tolerance` is `{"binary64": 1e-12, "binary32": <the file's>}`, absolute where an expected
value is zero. An expected derivative of 0 passes only where it is zero, of either sign: every precision gives
a constant extrapolation's derivative exactly. A `binary32` evaluator first rounds each number of the case to
the nearest `binary32`.

## The tables

The units are cosmetic to an evaluator. Every knot, value, edge and `source_range` end is exact in `binary32`,
except T6's.

| Table | Scheme | `x` | `y` | Edges, `source_range` | What it is for |
|---|---|---|---|---|---|
| T1 | linear | 280, 300, 320, 340 | 1000, 996, 990, 986 | none | interior knots whose sides differ (-0.2 and -0.3 at 300, -0.3 and -0.2 at 320) |
| T2 | log-log | 1, 10, 100, 1000 | 0.5, 0.125, 0.0625, 0.015625 | none | the log-log formula and its derivative |
| T3 | linear | 263, 273, 273, 283 | 918, 916, 1000, 999.5 | edge 273 | the refusal, and each side of an edge |
| T4 | log-log | 1, 10, 10, 100 | 2, 1, 4, 2 | edge 10 | the same, log-log |
| T5 | linear | 0.5, 2 | 3, 1.5 | none | a table of two knots |
| T6 | linear, and log-log | 293.15, 303.15, 313.15 | 0.001002, 0.000797, 0.000653 | none | decimal knots, not exact in `binary32` (TE-012) |
| T7 | linear | 300, 310, 320 | 1000, 980.46875, 960.625 | none | sides 1.6 % apart at 310 |
| T8 | T1's | | | `source_range` [290, 330] | a narrower range, its ends inside intervals |
| T9 | T1's | | | `source_range` [270, 350] | a wider range, which extends nothing |
| T10 | T1's | | | `source_range` [300, 320] | a narrower range whose ends are interior knots |
| T11 | T3's | | | edge 273, `source_range` [275, 283] | an edge outside the readable range |
| T12 | T1's | | | `source_range` [340, 400] | a readable range of one point, at an end |
| T13 | T1's | | | `source_range` [310, 310] | a readable range of one point, between knots |
| T14 | T3's | | | edge 273, `source_range` [273, 283] | an edge on the readable range's end |
| T15 | T3's | | | edge 273, `source_range` [263, 270] | T11 mirrored: an edge above the readable range |
| T16 | T3's | | | edge 273, `source_range` [263, 273] | T14 mirrored: an edge on the readable range's upper end |

A point beside a knot, an end or an edge lies one `binary32` unit from it (written "one binary32 unit below
280" in `CASES.md`), so both precisions evaluate the same side of it.

## How the numbers were made

Every expected number was computed exactly for the case's doubles, from the interval the text picks for that
point (`fractions` for a linear table, `decimal` at 80 digits for a log-log one), and rounded once. At a knot
the value is that knot's `y`.

Each file's `binary32` tolerance follows one rule: four times the worst `binary32` error a correct evaluator
on a faithful library can make at the file's compared numbers; at least four times one rounding (2^-24, so at
least 3e-7); rounded up to one significant digit. The error was emulated: the case's numbers rounded to
`binary32`, then every operation rounded to nearest, in each of the three orders of each `p * q / r` in the
text's formulas (`(p * q) / r`, the text's own order from left to right; `p * (q / r)`; and `(p / r) * q`),
with each `ln` argument and each `exp` call rounded down or up, independently of the others and every
combination tried, as a library within one unit of the true value may round each (one argument always the same
way, since a library is a function); and at a knot, both the knot's `y` and the formula there. A correctly
rounded `ln` and `exp` alone understated NumPy's real `float32` error 2.3 times on one file, and `ln` and
`exp` rounded the same way throughout a run understated a faithful library's worst case up to 3.4 times. The
README's cap holds per broken evaluator: each one in "The broken evaluators" below misses at least one of the
files that should catch it, those named beside it there, by ten times that file's tolerance. It need not miss
every file by that much: NumPy's `interp` outside the readable range misses TE-003 `narrowed` by at most 0.021
times that file's tolerance.

## How they were checked

In scratch harnesses, not part of the repository, written from the text:
- correct evaluators, exact, in `binary64`, in emulated `binary32`, in NumPy `float32` (2.4.6) and in JAX
  `float32` (0.5.3, CPU), each declaring each side, the floating-point ones in three orders, pass every file
  at their precision. Their worst error is 0.186 of a file's tolerance (NumPy and JAX, TE-012
  `decimal_knots_linear`); a faithful library's worst case, searched independently, is 0.238 of one (TE-003
  `far_outside`);
- broken evaluators, one fault each, each fail at least one file under every configuration of precision and
  side it can claim (the `bfloat16` one claims `binary32` only): by a flag for one that clamps with `in_range`
  always true, takes `in_range` by `<` at the ends, ignores a narrower `source_range`, reads an edge from the
  interval above, reports a refusal but returns a finite or an infinite number, gives `in_range` false and no
  refusal at an edge outside the readable range, below it or above it, extrapolates across an edge on either
  side, returns a derivative where the range is one point, or reports a refusal where none is due; and by a
  number for one that returns the side it did not declare, the outside derivative at an end, the declared side
  at a range end on an interior knot, the interval above just below an edge, log-log linearly, a linear table
  read as log-log, the linear slope as a log-log derivative, NumPy's `interp` outside the readable range, a
  linear extrapolation, or `bfloat16` intermediates.

Two passes independent of the author, one told to break the cases and one to check them, each wrote its own
evaluator from the text and checked these files with it; after the fixes they led to, their tools, rerun on
these files under the comparison rules the text now states, agree with every one: the expected numbers bit for
bit, each tolerance by the rule above. The scripts that generated these files are not part of the repository;
the files are the source.

## The broken evaluators

The suite's verification names these broken evaluators, one fault each. Beside each are the files that should
catch it, and the difference it must fail each of them by, under every precision and side it claims (the
`bfloat16` one claims `binary32` only). The list is taken from S3-te's verification (2026-10-17). These are
the only files the README's cap counts for a fault: a file named beside no broken evaluator has no cap from
that rule.

| Fault | Fails by | Files that should catch it |
|---|---|---|
| clamps, with `in_range` always true | `in_range` | TE-002 `linear`, TE-003 `just_outside_linear` |
| takes `in_range` by `<` at the ends | `in_range` | TE-002 `linear` |
| ignores a narrower `source_range` | `in_range` | TE-002 `source_range_narrow`, TE-003 `narrowed` |
| takes a wider `source_range` as the readable range | `in_range` | TE-002 `source_range_wide` |
| reads an edge from the interval above | no refusal | TE-010 `linear_edge` |
| reports a refusal at an edge, but returns the interval above's numbers | a number beside the refusal | TE-010 `linear_edge` |
| reports a refusal at an edge, but returns infinite numbers | a number beside the refusal | TE-010 `linear_edge` |
| raises another exception in place of a refusal | raising | TE-010 `linear_edge` |
| gives `in_range` false and no refusal at an edge outside the readable range, below it or above it | no refusal | TE-010 `edge_outside_readable_range`, `edge_outside_readable_range_above` |
| extrapolates across an edge, on either side | no refusal | TE-010 `edge_outside_readable_range`, `edge_outside_readable_range_above`, `edge_on_readable_range_end`, `edge_on_readable_range_end_above` |
| returns a derivative where the range is one point | a derivative where none is due | TE-007 `one_point_range_end`, `one_point_range_inside` |
| reports a refusal where none is due | a refusal where none is due | TE-003 `just_outside_linear` |
| raises a refusal where none is due | a refusal where none is due | TE-003 `just_outside_linear` |
| returns the side it did not declare | the derivative | TE-006 `close_sides`, `far_sides` |
| the outside derivative at an end | the derivative | TE-007 `linear_ends` |
| the declared side at a range end on an interior knot | the derivative | TE-007 `readable_range_knot_ends` |
| the interval above just below an edge | the value | TE-011 `linear_sides` |
| log-log linearly | the value | TE-004 `loglog_values`, TE-008 `loglog_interior` |
| a linear table read as log-log | the value | TE-004 `linear_values` |
| the linear slope as a log-log derivative | the derivative | TE-008 `loglog_interior` |
| the log-log derivative's `y / x` at the interval's lower knot, not at the point | the derivative | TE-008 `loglog_interior` |
| NumPy's `interp` outside the readable range | the value | TE-002 `source_range_narrow` |
| a linear extrapolation | the value | TE-002 `linear` |
| `bfloat16` intermediates | the value | TE-012 `decimal_knots_linear`, `decimal_knots_loglog` |

Each also misses at least one of the files named beside it by ten times that file's tolerance, under every
configuration it claims: by a flag, which no tolerance passes, or by a number. Of those caught by a number,
`bfloat16` misses by the least, 1,357 times, at TE-012 `decimal_knots_linear`; NumPy's `interp` by 3,373
times, at TE-002 `source_range_narrow`; a linear table read as log-log by 35,586 times, at TE-004
`linear_values`, in its derivative (in its value, the difference named beside it, by 176 times); and every
other by at least 144,000 times (the linear slope as a log-log derivative, at TE-008 `loglog_interior`). These
margins come from S3-te's reference evaluator and broken evaluators (2026-10-17): at each file named beside a
fault, its relative difference from the expected answer at the compared number where they differ most, over
that file's tolerance; a fault's margin is its best file's, the least over the configurations it claims.

## What the cases cannot show

- **That the consumer stops the run** at a refusal and keeps nothing computed from it
  (`read_side_contract.md` section 7 item 7, `[not yet covered]`): a case sees one evaluation, not a run.
- **A raised refusal against a reported one.** Both count as reported; a runner adapts each.
- **`in_range` at an edge.** The refusal comes first, so a case at or across an edge compares the refusal
  only.
- **A table that does not survive `binary32`**: two knots that become one, an operating value that changes
  side. Every table here survives it; the build's check is planned with S7.
- **A power law** (TE-009): no 0.1.0 field takes one; its cases come with the acoustic section. TE-001 is not
  defined.

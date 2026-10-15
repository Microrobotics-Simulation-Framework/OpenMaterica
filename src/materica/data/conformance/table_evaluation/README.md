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
  evaluator reports the refusal and each number it returns is absent or NaN, never finite or infinite;
- elsewhere outside the readable range: `in_range` false, the value at the range's nearest end, taken from
  inside it, and a derivative of 0; each number also passes absent or NaN.

`compare.relative_tolerance` is `{"binary64": 1e-12, "binary32": <the file's>}`, absolute where an expected
number is zero. A `binary32` evaluator first rounds each number of the case to the nearest `binary32`.

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

A point beside a knot, an end or an edge lies one `binary32` unit from it (written "one binary32 unit below
280" in `CASES.md`), so both precisions evaluate the same side of it.

## How the numbers were made

Every expected number was computed exactly for the case's doubles, from the interval the text picks for that
point (`fractions` for a linear table, `decimal` at 80 digits for a log-log one), and rounded once. At a knot
the value is that knot's `y`.

Each file's `binary32` tolerance follows one rule: four times the worst `binary32` error, over three
evaluation orders of the text's formulas, of the file's compared numbers; at least four times one rounding
(2^-24, so at least 3e-7); rounded up to one significant digit. The error was emulated: the case's
numbers rounded to `binary32`, then every operation, with `ln` and `exp` rounded to nearest, down and up, as a
library within one unit of the true value may give them. A correctly rounded `ln` and `exp` alone understated
NumPy's real `float32` error 2.3 times on one file. The README's cap holds for every file: the tolerance is at
most a tenth of the gap to each broken evaluator listed below, at the file that catches it.

## How they were checked

In a scratch harness, not part of the repository, written from the text:
- correct evaluators, exact, in `binary64`, in emulated `binary32`, in NumPy `float32` (2.4.6) and in JAX
  `float32` (0.5.3, CPU), each declaring each side, pass every file at their precision. NumPy's worst error is
  at most 0.23 of a file's tolerance;
- broken evaluators, one fault each, each fail at least one file under every configuration of precision and
  side it can claim (the `bfloat16` one claims `binary32` only), and the file that should catch each does: by a flag for one that clamps with `in_range` always true,
  takes `in_range` by `<` at the ends, ignores a narrower `source_range`, reads an edge from the interval
  above, reports a refusal but returns a finite or an infinite number, gives `in_range` false and no refusal
  at an edge outside the readable range, extrapolates across an edge, or returns a derivative where the
  range is one point; and by a number, at least 1,000 times the file's tolerance, for one that returns the
  side it did not declare, the outside derivative at an end, the declared side at a range end on an interior
  knot, the interval above just below an edge, log-log linearly, linear in log space, the linear slope as a
  log-log derivative, NumPy's `interp` outside the readable range, a linear extrapolation, or `bfloat16`
  intermediates.

The independent checks the plain-read cases had have not been made here yet. The scripts that generated
these files are not part of the repository; the files are the source.

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

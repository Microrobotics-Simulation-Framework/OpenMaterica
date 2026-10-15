# Table evaluation cases: what each case file tests

One row per file in `cases/`, grouped by case id; each heading quotes the case's row in the
specification, which holds where the two differ. Every file is an `evaluate` operation on one
table at a list of axis values (`docs/specification/README.md`, "Case files"), so **Ends at** is
always `evaluate`. **Arm** names the table (`README.md` beside this file lists them) and the
points, and gives the `binary32` tolerance with the emulated error it was computed from.
**Expected** is read from the case file: the evaluations as JSON (numbers as the doubles a
reader reads), then the `binary32` tolerance. See `README.md` beside this file for how the files
were made and checked.


## TE-002

`read_side_contract.md`: `in_range` is reported beside the value, inside and outside the range

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `linear` | T1: at x[0], inside and at x[-1], `in_range` true with the value and the inside derivative; one binary32 unit outside each end, at 0 and at 1e6, `in_range` false, the nearest end's value and 0 (binary32 tolerance 3e-07: the worst emulated binary32 error is 3.97e-08) | evaluate | evaluations `[{"in_range": true, "value": 1000.0, "derivative": -0.2}, {"in_range": true, "value": 992.85, "derivative": -0.3}, {"in_range": true, "value": 986.0, "derivative": -0.2}, {"in_range": false, "value": 1000.0, "derivative": 0.0}, {"in_range": false, "value": 986.0, "derivative": 0.0}, {"in_range": false, "value": 1000.0, "derivative": 0.0}, {"in_range": false, "value": 986.0, "derivative": 0.0}]`; binary32 tolerance `3e-07` |
| `loglog` | T2: at its two ends, `in_range` true; one binary32 unit below x[0], at -1 and at 0 (where `ln` is not defined), `in_range` false, y[0] and 0 (binary32 tolerance 3e-06: the worst emulated binary32 error is 5.91e-07) | evaluate | evaluations `[{"in_range": true, "value": 0.5, "derivative": -0.3010299956639812}, {"in_range": true, "value": 0.015625, "derivative": -9.407187364499412e-06}, {"in_range": false, "value": 0.5, "derivative": 0.0}, {"in_range": false, "value": 0.5, "derivative": 0.0}, {"in_range": false, "value": 0.5, "derivative": 0.0}]`; binary32 tolerance `3e-06` |
| `source_range_narrow` | T8: `source_range` [290, 330] narrows the readable range: at 285 and 335, inside `x`, `in_range` false with the value at 290 or 330, from inside; at 290 and 330 `in_range` true (binary32 tolerance 3e-07: the worst emulated binary32 error is 1.49e-08) | evaluate | evaluations `[{"in_range": false, "value": 998.0, "derivative": 0.0}, {"in_range": true, "value": 998.0, "derivative": -0.2}, {"in_range": true, "value": 988.0, "derivative": -0.2}, {"in_range": false, "value": 988.0, "derivative": 0.0}]`; binary32 tolerance `3e-07` |
| `source_range_wide` | T9: `source_range` [270, 350], wider than `x`, extends nothing: `in_range` true at 280 and 340, false one binary32 unit beyond each (binary32 tolerance 3e-07: the worst emulated binary32 error is 1.49e-08) | evaluate | evaluations `[{"in_range": true, "value": 1000.0, "derivative": -0.2}, {"in_range": false, "value": 1000.0, "derivative": 0.0}, {"in_range": true, "value": 986.0, "derivative": -0.2}, {"in_range": false, "value": 986.0, "derivative": 0.0}]`; binary32 tolerance `3e-07` |

## TE-003

`read_side_contract.md`: an evaluator that only clamps, or that ignores a narrower `source_range`, fails; so does one that returns, outside a table's readable range, any number but the value at its nearest end, from inside, and a zero derivative (the table's own value beyond a narrower `source_range`, say)

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `far_outside` | T2: far outside a log-log table, at 1e-3 and 1e6: `in_range` false, the end value, 0 (binary32 tolerance 2e-06: the worst emulated binary32 error is 4.77e-07) | evaluate | evaluations `[{"in_range": false, "value": 0.5, "derivative": 0.0}, {"in_range": false, "value": 0.015625, "derivative": 0.0}]`; binary32 tolerance `2e-06` |
| `just_outside_linear` | T1: one binary32 unit below x[0] and above x[-1]: `in_range` false, the end value, 0 (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"in_range": false, "value": 1000.0, "derivative": 0.0}, {"in_range": false, "value": 986.0, "derivative": 0.0}]`; binary32 tolerance `3e-07` |
| `just_outside_two_knot` | T5: a two-knot table, one binary32 unit outside each end: `in_range` false, the end value, 0 (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"in_range": false, "value": 3.0, "derivative": 0.0}, {"in_range": false, "value": 1.5, "derivative": 0.0}]`; binary32 tolerance `3e-07` |
| `narrowed` | T8: one binary32 unit outside the narrowed range [290, 330], inside `x`: `in_range` false, the value at 290 or 330, from inside, and 0, not the table's own value there (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"in_range": false, "value": 998.0, "derivative": 0.0}, {"in_range": false, "value": 988.0, "derivative": 0.0}]`; binary32 tolerance `3e-07` |

## TE-004

`read_side_contract.md`: linear and log-log values match the stated formulas

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `knot_values_linear` | T1: at every knot: that knot's `y`; both sides at the interior knots, the inside derivative at the ends (binary32 tolerance 3e-07: the worst emulated binary32 error is 3.97e-08) | evaluate | evaluations `[{"in_range": true, "value": 1000.0, "derivative": -0.2}, {"in_range": true, "value": 996.0, "derivative": {"left": -0.2, "right": -0.3}}, {"in_range": true, "value": 990.0, "derivative": {"left": -0.3, "right": -0.2}}, {"in_range": true, "value": 986.0, "derivative": -0.2}]`; binary32 tolerance `3e-07` |
| `knot_values_loglog` | T2: at every knot of the log-log table: that knot's `y`, with the derivatives as the linear arm's (binary32 tolerance 4e-06: the worst emulated binary32 error is 8.15e-07) | evaluate | evaluations `[{"in_range": true, "value": 0.5, "derivative": -0.3010299956639812}, {"in_range": true, "value": 0.125, "derivative": {"left": -0.00752574989159953, "right": -0.003762874945799765}}, {"in_range": true, "value": 0.0625, "derivative": {"left": -0.00018814374728998824, "right": -0.00037628749457997647}}, {"in_range": true, "value": 0.015625, "derivative": -9.407187364499412e-06}]`; binary32 tolerance `4e-06` |
| `linear_values` | T1: between knots, in each interval: the linear formula (binary32 tolerance 3e-07: the worst emulated binary32 error is 3.97e-08) | evaluate | evaluations `[{"in_range": true, "value": 998.0, "derivative": -0.2}, {"in_range": true, "value": 992.85, "derivative": -0.3}, {"in_range": true, "value": 987.35, "derivative": -0.2}]`; binary32 tolerance `3e-07` |
| `loglog_values` | T2: between knots, in each interval: the log-log formula, in natural logarithms (binary32 tolerance 4e-06: the worst emulated binary32 error is 7.71e-07) | evaluate | evaluations `[{"in_range": true, "value": 0.25805625232768326, "derivative": -0.05178844834617715}, {"in_range": true, "value": 0.08849191411431111, "derivative": -0.0008456736673691577}, {"in_range": true, "value": 0.023716912023294765, "derivative": -2.855800769414179e-05}]`; binary32 tolerance `4e-06` |

## TE-005

`read_side_contract.md`: the left and right derivatives at each interior knot

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `linear_interior_knots` | T1: at each interior knot, `{"left", "right"}`: -0.2 and -0.3 at 300, -0.3 and -0.2 at 320 (binary32 tolerance 3e-07: the worst emulated binary32 error is 3.97e-08) | evaluate | evaluations `[{"in_range": true, "value": 996.0, "derivative": {"left": -0.2, "right": -0.3}}, {"in_range": true, "value": 990.0, "derivative": {"left": -0.3, "right": -0.2}}]`; binary32 tolerance `3e-07` |
| `loglog_interior_knots` | T2: at each interior knot of the log-log table, the left and right derivatives by item 5 (binary32 tolerance 4e-06: the worst emulated binary32 error is 8.15e-07) | evaluate | evaluations `[{"in_range": true, "value": 0.125, "derivative": {"left": -0.00752574989159953, "right": -0.003762874945799765}}, {"in_range": true, "value": 0.0625, "derivative": {"left": -0.00018814374728998824, "right": -0.00037628749457997647}}]`; binary32 tolerance `4e-06` |

## TE-006

`read_side_contract.md`: the evaluator's declared side matches what it returns

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `close_sides` | T7: at 310, sides 1.6 % apart (-1.953125 and -1.984375): an evaluator returning the side it did not declare misses by far more than the tolerance (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"in_range": true, "value": 980.46875, "derivative": {"left": -1.953125, "right": -1.984375}}]`; binary32 tolerance `3e-07` |
| `far_sides` | T1: at 300, sides -0.2 and -0.3 (binary32 tolerance 3e-07: the worst emulated binary32 error is 3.97e-08) | evaluate | evaluations `[{"in_range": true, "value": 996.0, "derivative": {"left": -0.2, "right": -0.3}}]`; binary32 tolerance `3e-07` |

## TE-007

`read_side_contract.md`: at the ends of a table's readable range, an interior knot included, the inside derivative only, whatever side the evaluator declares; where the readable range is one point, no derivative

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `linear_ends` | T1: at x[0] and x[-1]: one derivative, from inside (binary32 tolerance 3e-07: the worst emulated binary32 error is 1.49e-08) | evaluate | evaluations `[{"in_range": true, "value": 1000.0, "derivative": -0.2}, {"in_range": true, "value": 986.0, "derivative": -0.2}]`; binary32 tolerance `3e-07` |
| `loglog_ends` | T2: at the log-log table's ends: one derivative, from inside (binary32 tolerance 3e-06: the worst emulated binary32 error is 5.91e-07) | evaluate | evaluations `[{"in_range": true, "value": 0.5, "derivative": -0.3010299956639812}, {"in_range": true, "value": 0.015625, "derivative": -9.407187364499412e-06}]`; binary32 tolerance `3e-06` |
| `one_point_range_end` | T12: `source_range` [340, 400] leaves the one point 340: there the value and no derivative (`"none"`); at 330 and 350 `in_range` false, 986 and 0 (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"in_range": true, "value": 986.0, "derivative": "none"}, {"in_range": false, "value": 986.0, "derivative": 0.0}, {"in_range": false, "value": 986.0, "derivative": 0.0}]`; binary32 tolerance `3e-07` |
| `one_point_range_inside` | T13: `source_range` [310, 310] leaves the one point 310, between knots: there 993 and no derivative; at 305 and 315 `in_range` false, 993 and 0 (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"in_range": true, "value": 993.0, "derivative": "none"}, {"in_range": false, "value": 993.0, "derivative": 0.0}, {"in_range": false, "value": 993.0, "derivative": 0.0}]`; binary32 tolerance `3e-07` |
| `readable_range_ends` | T8: the narrowed range's ends, 290 and 330, each inside an interval: -0.2, from inside (binary32 tolerance 3e-07: the worst emulated binary32 error is 1.49e-08) | evaluate | evaluations `[{"in_range": true, "value": 998.0, "derivative": -0.2}, {"in_range": true, "value": 988.0, "derivative": -0.2}]`; binary32 tolerance `3e-07` |
| `readable_range_knot_ends` | T10: the range narrowed to [300, 320], whose ends are interior knots of `x`: -0.3 at both, from inside, whatever side the evaluator declares (the outside slopes are -0.2) (binary32 tolerance 3e-07: the worst emulated binary32 error is 3.97e-08) | evaluate | evaluations `[{"in_range": true, "value": 996.0, "derivative": -0.3}, {"in_range": true, "value": 990.0, "derivative": -0.3}]`; binary32 tolerance `3e-07` |
| `two_knot_ends` | T5: a two-knot table's ends: -1 at each (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"in_range": true, "value": 3.0, "derivative": -1.0}, {"in_range": true, "value": 1.5, "derivative": -1.0}]`; binary32 tolerance `3e-07` |

## TE-008

`read_side_contract.md`: the derivative of a log-log table

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `loglog_interior` | T2: between knots, in each interval: `(y / x) * (ln y1 - ln y0) / (ln x1 - ln x0)` (binary32 tolerance 4e-06: the worst emulated binary32 error is 7.51e-07) | evaluate | evaluations `[{"in_range": true, "value": 0.3294062900063279, "derivative": -0.09916117405229301}, {"in_range": true, "value": 0.07700148054306288, "derivative": -0.00046359510707996704}, {"in_range": true, "value": 0.03599948261892505, "derivative": -8.669539277344458e-05}]`; binary32 tolerance `4e-06` |
| `loglog_near_knot` | T2: one binary32 unit either side of the knot 10: each interval's derivative (binary32 tolerance 4e-06: the worst emulated binary32 error is 8.77e-07) | evaluate | evaluations `[{"in_range": true, "value": 0.12500000717711493, "derivative": -0.007525751041416453}, {"in_range": true, "value": 0.12499999641144303, "derivative": -0.0037628744789177616}]`; binary32 tolerance `4e-06` |

## TE-010

`read_side_contract.md`: an evaluator refuses at a declared edge, wherever it lies, and across one from the readable range: it reports the refusal, and each number it returns there is absent or NaN, never finite or infinite

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `edge_on_readable_range_end` | T14: `source_range` [273, 283] puts the range's end on the edge: refused at 273 and beyond it at 272; at 278 and 283 `in_range` true (binary32 tolerance 3e-07: the worst emulated binary32 error is 1.49e-08) | evaluate | evaluations `[{"refused": true}, {"refused": true}, {"in_range": true, "value": 999.75, "derivative": -0.05}, {"in_range": true, "value": 999.5, "derivative": -0.05}]`; binary32 tolerance `3e-07` |
| `edge_on_readable_range_end_above` | T16: `source_range` [263, 273] puts the range's upper end on the edge: refused at 273 and beyond it at 274; at 268 and 263 `in_range` true (binary32 tolerance 3e-07: the worst emulated binary32 error is 1.49e-08) | evaluate | evaluations `[{"refused": true}, {"refused": true}, {"in_range": true, "value": 917.0, "derivative": -0.2}, {"in_range": true, "value": 918.0, "derivative": -0.2}]`; binary32 tolerance `3e-07` |
| `edge_outside_readable_range` | T11: `source_range` [275, 283] leaves the edge 273 outside: refused at 273, and at 272, across it from the range; at 274, with no edge between it and 275, `in_range` false, the value at 275 and 0; at 275 `in_range` true (binary32 tolerance 3e-07: the worst emulated binary32 error is 2.44e-08) | evaluate | evaluations `[{"refused": true}, {"refused": true}, {"in_range": false, "value": 999.9, "derivative": 0.0}, {"in_range": true, "value": 999.9, "derivative": -0.05}]`; binary32 tolerance `3e-07` |
| `edge_outside_readable_range_above` | T15: `source_range` [263, 270] leaves the edge 273 above the readable range: refused at 273, and at 275, across it from the range; at 272, with no edge between it and 270, `in_range` false, the value at 270 from the interval below the edge, and 0; at 270 `in_range` true (binary32 tolerance 3e-07: the worst emulated binary32 error is 2.66e-08) | evaluate | evaluations `[{"refused": true}, {"refused": true}, {"in_range": false, "value": 916.6, "derivative": 0.0}, {"in_range": true, "value": 916.6, "derivative": -0.2}]`; binary32 tolerance `3e-07` |
| `linear_edge` | T3: at the declared edge 273: refused, no number (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"refused": true}]`; binary32 tolerance `3e-07` |
| `loglog_edge` | T4: at the log-log table's declared edge 10: refused, no number (binary32 tolerance 3e-07: the worst emulated binary32 error is 0.00e+00) | evaluate | evaluations `[{"refused": true}]`; binary32 tolerance `3e-07` |

## TE-011

`read_side_contract.md`: values and derivatives on each side of a repeated knot

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `linear_sides` | T3: one binary32 unit below the edge, the interval below; one above, the interval above (binary32 tolerance 3e-07: the worst emulated binary32 error is 1.49e-08) | evaluate | evaluations `[{"in_range": true, "value": 916.0000061035156, "derivative": -0.2}, {"in_range": true, "value": 999.9999984741211, "derivative": -0.05}]`; binary32 tolerance `3e-07` |
| `loglog_sides` | T4: the same either side of the log-log table's edge 10 (binary32 tolerance 3e-06: the worst emulated binary32 error is 5.46e-07) | evaluate | evaluations `[{"in_range": true, "value": 1.0000000287084594, "derivative": -0.03010300330145497}, {"in_range": true, "value": 3.999999885166177, "derivative": -0.12041198332536837}]`; binary32 tolerance `3e-06` |

## TE-012

`read_side_contract.md`: a `binary32` evaluator meets its case file's `binary32` tolerance, and a `binary64` one 1e-12

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `decimal_knots_linear` | T6 linear: its knots are decimal (293.15, 303.15, 313.15), not exact in binary32: at them and between them; the binary32 tolerance absorbs the rounding of the case's numbers (binary32 tolerance 2e-06: the worst emulated binary32 error is 3.71e-07) | evaluate | evaluations `[{"in_range": true, "value": 0.001002, "derivative": -2.050000000000001e-05}, {"in_range": true, "value": 0.000797, "derivative": {"left": -2.050000000000001e-05, "right": -1.4399999999999993e-05}}, {"in_range": true, "value": 0.000653, "derivative": -1.4399999999999993e-05}, {"in_range": true, "value": 0.0008995, "derivative": -2.050000000000001e-05}, {"in_range": true, "value": 0.0006962, "derivative": -1.4399999999999993e-05}]`; binary32 tolerance `2e-06` |
| `decimal_knots_loglog` | T6 log-log: its knots are decimal (293.15, 303.15, 313.15), not exact in binary32: at them and between them; the binary32 tolerance absorbs the rounding of the case's numbers (binary32 tolerance 0.0002: the worst emulated binary32 error is 2.64e-05) | evaluate | evaluations `[{"in_range": true, "value": 0.001002, "derivative": -2.3324645967712564e-05}, {"in_range": true, "value": 0.000797, "derivative": {"left": -1.7940642259770894e-05, "right": -1.6142960242098694e-05}}, {"in_range": true, "value": 0.000653, "derivative": -1.2803927122915304e-05}, {"in_range": true, "value": 0.0008927836454000341, "derivative": -2.0433777016154038e-05}, {"in_range": true, "value": 0.0006927604467808675, "derivative": -1.371493414105135e-05}]`; binary32 tolerance `0.0002` |

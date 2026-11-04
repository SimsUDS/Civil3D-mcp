# DE CALC: unguyed dead end and angle calcs

Read when a PDF page shows a calc table in the CALCS area (render that crop at -r 200 and read every cell). Anything in CALCS that is not a calc table: not taught, skip and note (except a SOIL TYPE note, see guys-anchors.md). Guyed DE, ANCHOR and PISA calcs: not split out yet; use the Station Builder CALC TEMPLATE sheet and Kevin's left side DE CALC EXAMPLES wording, and note the first time a type is drafted.

## Placement (generator `calcs`)

- Box centered on Cx, top at Cy - 100. Left text at box left + 2.876, right column (`= ...`) at box left + 208.34; header baseline top - 8.02; lines at top - 17.65, - 25.67, - 33.70, - 41.73; bottom = top - 45.95. Re-center on Cx after measuring (qc.py fix job). A second calc goes 10 below the first.
- A left line that overlaps its `= ...`: move the whole right column right, widen the box, keep it centered. The generator does it: right column at the larger of 208.34 and the longest left line that has a right value + 8 (TD2555545 1138916E CLASS line).

## UNGUYED DE CALC (one line each, left / right)

- `%%UUNGUYED DE CALC (2767E)` (the pole's own last 4 digits + E, underlined; fix wrong digits silently)
- `186' 1/0ATW LIGHT` / `= 1,415 LBS` (span, conductor, tension and loading as the PDF gives them, e.g. `76' 1/0AT @ 25% LIGHT`)
- `1,415 LBS x 35'` / `= 49,525 FT-LBS`
- `50' CLASS 1 DF-TB IN 12LB WIND ZONE GRADE A CAN HOLD` / `= 49,594 FT-LBS`
- `BREAST BLOCK & POLE KEY IN CLASS 4 SOIL CAN HOLD` / `= 47,500 FT-LBS` (ALWAYS added, even when the PDF leaves it off)

## UNGUYED ANGLE CALC

- Header `%%UUNGUYED ANGLE CALC (5185E)`, first line `1/0AT LIGHT W/ 20%%D ANGLE` / `= 454.61 LBS`, then `454.61 LBS x 26'`, the CLASS line and the BBPK line.

## Combined calcs

- Loads lettered `A. ...`, `B. ...` with `TOTAL (A+B)`: the `LBS x height` line under each lettered load is indented 9.923; everything else flush left. Planner `LEVEL 1. / LEVEL 2. / TOTAL (1+2)` becomes `A. / B. / TOTAL (A+B)`.

## Numbers and checks

- Thousands commas; drop a trailing .00, keep real decimals (327.25, 10,144.75).
- Check LBS x height = FT-LBS. Wrong arithmetic, or load over the CAN HOLD: draft as the PDF says and note it.
- Information left out: fill what the PDF gives in the standard format, check Kevin's left side examples for the wording, note what is still missing.

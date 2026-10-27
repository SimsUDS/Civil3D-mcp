# Template pieces (AUD OH Template 2024)

Read when hand-building or fixing something the generator does not place, or when checking a placed piece against its source. Handles are the same in every fresh template copy.

## Areas

- POLE DETAIL BUILDER: window x 2573 to 5507, y -2183 to -1182. Rows: callout template text on the left (x about 4440 to 4560), front view symbols centered on pole x = 4610.27, side view column around x 4686 to 4710 (side view pole x = 4697.58), descriptions at x about 4829. Combinations column around x 5070 to 5420.
- HEIGHT SCALE: vertical dims, ground y = -1946.2563, pole x = 3329.4667, one dim per whole foot. NOT linear at the bottom. Height above ground for whole feet H: 9' = 38, 10' to 13' = 46, 14' to 17' = 54, 18' and up = 8H - 82 (18' = 62, 24' = 110, 34' = 190, 37' = 214, 41' = 246). Example handles: 16' 2E3759, 24' 2E34A7, 25' 2E34B1, 34' 2E3533, 37' 2E3551.
- ANCHOR SCALE: horizontal dims, pole x 3415.34, ground -1946.26. Lead to distance: 7 ft and under = 34, 8 to 11 = 38, 12 to 15 = 42, 16 to 19 = 46, 20 ft and up = 50 + 4 per foot (22 = 58, 26 = 74, 29 = 86, 34 = 106).
- POLE EXAMPLES: around x 3300 to 5450, y -1180 to -90 (mostly layer MISC).
- DE CALC EXAMPLES: Kevin's calc examples on the left side of the template (see calcs-unguyed.md).
- OBSTRUCTION DETAIL examples: around x 1979 to 2497, y -1478 to -1057 (see obstruction.md).

## Drafting pieces (handle: what, reference point)

- Callout text: 37BBC7 (`PH ARM`, layer MISC, style STA-TEXT 4.8, RIGHT justified, right edge 4558.3319, baseline -1320.0283). Left column: dx = (P - col) - 4558.3319, dy = baseline - (-1320.0283). Right column: same dx/dy plus `mirrorX = P` (becomes left justified at P + col). Edit `text`; IN/RM lines also `colorIndex: 90`. STA-TEXT is about 3.5 units per character.
- Height dim: 2E34A7 (layer MISC, color 157). After copying, edit xLine1, xLine2, dimLine, text, textPosition AND `layer: "DIMENSION"`, `colorIndex: 256`.
- Anchor lead dim: 38F31B (horizontal). Same layer/color edit.
- Pole line and base line: LINE 2A42F4 (stash, (2772.8085, -774.2588) to (2772.8085, -1084.2588)); copy twice per pole, edit `start`/`end`.
- Guy: 2E3B8F (LWPOLYLINE, layer MISC, linetype GUY); edit `vertices` to [(P, attach y), (anchor x, G)].
- Span guy (SG): two halves starting at the pole point (4371.2932, -1992.9099), layer MISC, about 33.76 long: 2E3466 runs LEFT, 2E3954 runs RIGHT. dx = P - 4371.2932, dy = row y - (-1992.9099). Never mirror, never edit vertices, never use 2E3B8F for a span guy.
- Anchor arc: 38F2F8 (radius 2, center (anchor x, G + 2)); the guy ends at (anchor x, G).
- DG leader: 2E3390 (LEADER); edit `vertices` [arrow on guy, elbow, end].
- DG text: 2A4B31 (layer TEXT, Standard, color 90; right edge 5377.2848, baseline -1033.4725). `colorIndex: 256` for EX. Measure after every text change and re-point the leader.
- Anchor label: 2A4B30 (layer MISC, STA-TEXT, color 90, left edge 5307.1477, baseline -1087.0188 = its ground + 1.6). `mirrorX` for anchors on the left. Measure after editing and realign.
- Pole label: PROPOSED 2A4BC2, L/xx 2A4BC3, pole number 2A4BC4, center justified at x 4292.2155, baselines -377.0894, -385.0894, -393.0894 (land at G - 11.08, - 19.08, - 27.08).
- SEC-MISC dot: 2A4FAD (center 3823.6518, -1005.5445).
- X COND arrow, length 25: 2E3BD7 right, 2E3BD8 left, insertion (4402.66, -1420.70). Also left facing at (4784.9005, -1421.6283) and right facing at (4787.4005, -1389.6635).
- 3 phase crossarm (row -1446.63, pole 4610.27): XARM 2E3400; VERT P&I 2E3401 (-29.76), 2E3402 (-12.13), 2E3404 (+12.13), 2E3403 (+29.76); conductor circles (ELECTRIC) 2E3405, 2E3408, 2E3407, 2E3406. Pin with base circle example: VERT P&I 2A4C2F with CIRCLE 2A4C31 (4300.1486, -168.0103).
- Slanted pins (already rotated; copy, never rotate): LEFT 2E3477 (25 deg, insertion 4529.5100, -1471.6283); RIGHT 2E3472 (335 deg, insertion 4525.7361, -1496.6283). Insertion = pin base, ON the arm line (0.2 above leaves a visible gap).
- Closed inverted omni on xarm (row -1596.63): XARM 2E33F2, INV OMNI CLOSED 2E344E, 2E344F, 2E3451, 2E3450.
- FH/LA arm, front (row -1341.83, pole 5177.20): XARM 2E380B; SA ends 2E382D (-29.76), 2E382E (+29.75) with inner CUTOUTs 2E382F (-10.03), 2E3831 (+10.04); or outer CUTOUTs 2E382B (-23.83), 2E382C (+23.86) with inner SAs 2E3830 (-15.96), 2E3832 (+15.94).
- FH/LA side (row -1329.33, side pole 5264.5156): SURGE ARRESTER 2E3870, SIDE XARM 2E3806 (box left), CUTOUT 2E3872 (outer edge P + 5.43). The CUTOUT is NEVER mirrored. On the left it sits 1.1 clear of the leftmost box: center = leftmost box edge - 3.3132 (no box: P - 3.3132; dead end boxes: P - 8.3132).
- PH & LA: left leaning PH side pole 5333.5588 row -1291.8281: 2E3866, 2E386B, 2E386D (extends 6.99 right, 3.89 left). Right leaning side pole 5264.5156 row -1291.6289: 2E3811, 2E386C, 2E386E (3.89 right, 6.99 left).
- 2/C crossarm with FH and LA (row -1471.83, pole 5177.20): XARM 2E380C, VERT P&I 2E383D, 2E383E, CUTOUT 2E383F, 2E3840, SA 2E3842, 2E3841.
- Side dead end one way (row -1446.63, side pole 4697.58): SIDE XARM 2E3415, 2E3912; VERT P&I 2E3419, 2E3916; ticks 2E3913, 2E3914, 2E3915; X COND 2E3918 (tip P + 30). Both ways: add X COND 2E3490 and ticks 2E3418, 2E3417, 2E3416 (tip P - 30).
- Arrows over dead end pins: X COND 2E348D (insertion P + 2.5) and 2E3492 (P - 2.5) at row + 6.9648.
- Side single arm groups: side pole 4787.4: 2E3493, 2E341F, 2E3420, 2E348C. Right box version (row -1396.63, side pole 4697.58): X COND 2E3492, 2E348D, SIDE XARM 2E3423, VERT P&I 2E3422. The X CONDs start at the pin top: insertion at the pin x (box right P + 2.5, left P - 2.5, centered P), y = row + 6.965.
- Lone SIDE XARM: 2E3912, box pole to pole + 5, centered on its row.
- INV OMNI CLOSED 2E344E (insertion 4580.5129, -1596.6283) leans LEFT (tick runs down-left from the circle); copy with `mirrorX` = its new insertion x for a right leaning one. Under xarm slots: insertion on the slot, on the arm line. Beside a dead end / single arm box: insertion 5 beyond that box's SIDE XARM insertion, on the row.
- Street light: SL 2E38D1 (insertion 5177.3026, -1718.0507 on the pole line at its row) faces RIGHT, mirror about the pole for left; front facing SIDE SL 2E38CF at 5264.5156, -1718.0507. Callout `ST LT`, dim like any row.
- HZ INV OMNI on a side box: box top on the row line, INV OMNI CLOSED 2E344E at box center height, 5 beyond the box center (example omni 4690.0843, box 4695.0843, both -1596.6283).
- RCS CONTROL BOX: polyline 2E3432 (6.5467 x 8.746, left edge 4784.9005, center y -2011.4173). Mirroring is fine.
- Guard arm line: LINE 2E3922 (35 long, from 4767.4005, -2151.7964), centered on the pole. Comm dots on it: SEC-MISC 2A500C (3805.6404, -388.2413) under line 2A500B (y -386.763).
- SIDE XFMR: 2E3425 at (4697.58, -1973.82), width 10.42 (insertion = box center).

- 66KV (TD2536512): TRANS INS 66 leaning up 2E37A8 (right) / 2E37C0 (left), insertion (4610.268, -1841.4237) on the pole. TRANS DE 66 2E37D0 (4697.5843, -1841.4237) with X CONDs 2E37E9 right / 2E37EA left (4697.5843, -1841.4348). Side group: SIDE XARM 2E3428 (4695.0843, -1654.6283), TRANS P&I 2E3429 (4695.0843, -1657.1283), X CONDs 2E3928 / 2E3929 (4695.0842, -1669.9386). TRANS P&I on an arm: XARM 2E33E5 (row -1654.6283), P&I 2E3456, 2E3457, 2E3459, 2E3458 at the slots.
- 115KV (TD2524712): TRANS DE 115 2E37DB (4697.5843, -1894.8266, 4.8 wide, 8 tall, centered on the insertion), X CONDs 2E37EF right / 2E37F0 left from its insertion. Kevin: on 2115931E L/E the boxes sit LEFT of the pole (edge on the pole line), not centered. Level TRANS INS 66: 2E3494 right, 2E37B8 left (4610.268, -1849.4237, 19.36 long).
- PH & LA ARM front view (row -1291.8281, pole 5177.1994): XARM 2E3810, POTHEADs 2E381F, 2E3820, 2E3821, 2E3822, SURGE ARRESTERs 2E3823, 2E3824, 2E3825, 2E3826.
- PT 2E33EB (4784.9005, -2038.7731, 8.29 wide centered on the insertion). Side SURGE ARRESTER 2E3870 (5258.0156, -1329.3281).
- SOIL TYPE box (this template copy): LWPOLYLINE 394947 top-left (1346.8139, -807.5353), 53.146 x 11.846; text 394948 at (1349.6896, -815.5629).
- XFMR BANK 2E3426 (4610.268, -1973.8214, half width 20.41). DISCONNECT ARM 2E38FB (5177.2192, -1791.1975, layer ELECTRIC, half width 34.43).
- No RECLOSER symbol in the template.

## Sheet data stash (x 2340 to 2500, y -700 to -120)

- CREW box 391E85 (top-left 2379.0399, -121.5856), header 391E97 (baseline -129.6132), line 391E98 (baseline -137.6402).
- NOTE box 391E86 (top-left 2379.0399, -154.8799), header 391EA3 (baseline -162.9075), line 391E99 (baseline -170.9346). Text x = 2381.9156.
- GPS 391E87 (insertion 2379.0399, -263.517; LAT, LONG). ELEV 391EA0 (insertion 2379.0399, -283.4196; FOOTAGE; colorIndex 1, keep it). ELEV lead line 39498C (NO-PLOT LINE, start = ELEV insertion): always copied with ELEV, same offset.
- TLM 392289 (dynamic block, layer 0, scale 60, width 144.57, insertion 2350.1087, -540.1907). TLM NOTE box 392285, header 392287, note line 392288.

## Frames

- Row 1 pole names 386B22, 386B24, 386B25, 386B26; row 2 386B27, 386B28, 386B29, 386B2A.
- Row 2 frame sets (copied 2070 lower per extra row): col 1 2A3C5C, 2A3D50, 386B27, 2A2A1A; col 2 2A3C5D, 2A3D4D, 386B28, 2A2A1B; col 3 2A3C5E, 2A3D4E, 386B29, 2A2A1C; col 4 2A3C5F, 2A3D4F, 386B2A, 2A2A1E.

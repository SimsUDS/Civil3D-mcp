# Pole head generator

Builds pole head detail sheets in the AUD OH template from a job spec, as one
`civil3d_entity` `apply` job. Copies and the edits that fill them are tied
together with refs (`"g12:37BBC7"` = the copy of `37BBC7` made by copy `g12`),
so a whole job is one approval and one tool call.

```
python polehead.py examples/TD2536120.json -o job_TD2536120.json
python polehead.py spec.json --poles 1414703E,4904169E -o job_part.json
python station_builder.py "<TD> - STATION BUILDER.xlsx" 1414703E 4904169E > sheets.json
```

Then put the job file in the job folder on the drafting machine and run:

```
civil3d_request_approval  toolName=civil3d_entity action=apply parameters={"action":"apply","jobFile":"C:\\...\\job_TD2536120.json"}
civil3d_entity            action=apply jobFile=<same path> approvalToken=<token>
```

The old-to-new handle map lands next to the job as `job_TD2536120.result.json`
for `qc.py` (see below).

## Spec format

```json
{
  "job": "TD2536120",
  "poles": [{
    "frame": 0,
    "pole": "1414703E",
    "profiles": [{
      "L": "L/NW", "side": "R", "gside": 1,
      "items": [{"t": "pri", "h": "41'6\"", "c": ["IN: 4/C 336ATW 16KV"], "k": "L"}],
      "anchors": [{"L": "13'", "c": "IN: 1 1/4\" 3EYE"}],
      "guys": [{"h": "37'", "an": 0, "c": "IN: 3/8\" DG @ 37'"}]
    }],
    "crew": ["-..."], "notes": ["-..."], "gps": ["34°11'32.19\"", "118°.."], "elev": "821",
    "tlm": {"ex": ["50", "31.57", "8", "63"], "pr": ["", "", "", ""], "cz": "5",
            "pc": "HAMPSHIRE 16KV", "vd": "", "flicker": "", "addr": [["1065 BURTONWOOD AVE", "322010-238159"]]}
  }]
}
```

- `frame` 0 and up, left to right, 4 per row, top row first. The template only has frames 0 to 7; frame 8 and up are added by copying the row 2 frame set 2070 lower per row (sheet number = frame + 2). Two profiles are drawn at Cx -/+ 300 (PDF left, then right). One profile
  goes in the slot the PDF draws it in: N slot (left) Cx - 300, E slot (right) Cx + 300, 600 apart. Set `slot: "R"` or `"L"`;
  without it an `L/E` profile goes right and anything else left.
- `side`: callout and dim side, `R` or `L`. Callout column: 5.75 past the farthest equipment on the callout side (crossarm 35 -> 40.75, dead end 30 -> 35.75, X COND 25 -> 30.75 minimum). `gside`: guys and anchors side, `1` right, `-1` left (needed when there are anchors).
- Item `h`: true height as written. No height from the planner: `h` = where the PDF draws it (for the row) and
  `label: "_'"` so the dim reads `_'`. `c`: callout lines at the row. `above`: extra lines stacked above the row's own line (FH/LA on a primary box).
- Item types (`t`) and `k`:
  - `pri` side arm box with pin and X CONDs. `k`: `R`, `L` or `C` box position, `B` a box on each side. `fhla: true` puts the SA and CUTOUT on that box.
  - `fhla` side view FH/LA box. `k: "R"` puts the box right of the pole (default left).
  - `xfmr` side transformer, `k` `L`/`C`/`R`.
  - `xr`, `xl`, `xb` X COND right, left, both. COMM and CATV lines are always X CONDs; add `dot: true` to keep the SEC-MISC dot under them.
  - `dot` SEC-MISC dot alone (a bare dot with no line).
  - `sg` span guy half, `k` `R` or `L` (never mirrored or edited). `share: 1` puts it on the row of the other item at that whole foot.
  - `arm2`, `arm4`, `armc` crossarm with 2 pins, 4 pins or 4 conductor circles. `fhlaf` front view FH/LA arm (outer CUTOUTs, inner SAs; `ends: "sa"` puts the SAs outboard at -/+24.46 (symmetric, never mirrored), and the CUTOUTs inboard at -19.51 / +19.59, never mirrored; give the arm's pins on the same item with `pins`, `circ` and `slant`, never as a second `arm` item, which doubles the XARM). `arm2fl` 2/C arm with FH and LA.
  - `end: "R"` / `"L"` on any crossarm: the pole sits at the arm's right / left end (offset arm), not its center.
  - `arm` crossarm with any mix: `dots` puts SEC-MISC dots on the arm at those slots (comm/CATV seen end on); `pins` and `circ` are slot indexes 0 to 3, left to right (-29.76, -12.13, +12.13, +29.76).
  - `slant: {"<slot>": "L" | "R"}` on `arm`, `arm2` or `arm4`: that slot's pin is drawn slanted (leaning left 2E3477
    or right 2E3472, already rotated in the template) with its base on the slot, on the arm line. The upright pin
    of that slot is left out, so nothing has to be erased. Example: `"slant": {"3": "R"}`.
  - `de1` side view dead end one way (`k: "L"` points left), `de2` both ways. `nopins: true` leaves the pins off;
    `fhla: "L"` / `"R"` puts the SA and CUTOUT on the dead end boxes (`"R"` = cutout left, SA right).
  - `box: "R"` / `"L"` on any item adds a lone SIDE XARM (guard arm) beside the pole, centered on that row (the
    middle of its wall on the dim point). With `omni` the box hangs just below the row line and the omni sits at the box center.
  - Pins drawn with a circle at their base (4/C arms on Builder pages): use `arm` with `pins` AND `circ` (e.g. `[0,1,2,3]` both).
  - `omni: true` with `box`: INV OMNI CLOSED with its insertion 5 beside the SIDE XARM insertion, on the box's side (HZ INV OMNI SW).
  - `stlt` street light (ST LT): `k: "C"` front facing SIDE SL (2E38CF) on the pole at its row; `k: "R"` side SL
    (2E38D1) arm out to the right, `k: "L"` mirrored.
  - `pinx` on `arm`: pins at any offsets from the pole, e.g. a 3/C secondary drawn with all three pins right of the
    pole: `"pinx": [9.755, 19.755, 29.755]`. Draw pins where the PDF draws them; never move them to the standard slots.
  - `box` on `xr`/`xl`/`xb` (centered on the row): the X COND on the box's side starts at the box's outer edge
    (pole + 5), not at the pole, e.g. COMM ARM, COMM SVC drawn as a box with an arrow out of it.
  - `dot: true` on `pri`, `de1` or `de2`: the SEC-MISC dot hangs under the box on the `k` side (a dead end's arrow
    side; `k: "C"` centers it on the pole), centered on that box, center 4.0 below the row.
  - `boxup: true` with `box`: the SIDE XARM sits ON the row line (bottom on the line, edge on the pole) when the PDF
    draws the box above the line, as on a GUARD ARM/COMM X COND. Without it the box is centered on the row.
  - `none`: no symbol of its own, used with `box` (a guard arm or comm box with its callout).
  - `rcs` RCS CONTROL BOX: template rectangle 2E3432 centered on its row, `k` `L`/`R` beside the pole (never mirrored).
  - `arm1` short one-sided arm (COMM ARM drawn as a short line out from the pole with a dot at its end): the guard
    arm line 2E3922 cut to `L` (default 17.5) toward `k` (`L`/`R`), SEC-MISC dot on the far end. Not an X COND.
  - `gal` guard arm drawn as a line through the pole: the 35 long line 2E3922 centered on the pole. `dots: [4.5, 10, 15.5]`
    hangs SEC-MISC dots (template 2A500C) under the line at those offsets from the pole (comm on a guard arm).
  - `ph` PH & LA (pothead): the template example group copied as is, `k: "L"` left leaning PH (box right of the
    pole, SA beyond it, PH left; 2E3866/2E386B/2E386D) or `k: "R"` right leaning PH (2E3811/2E386C/2E386E). Never use `fhla` for a PH.
  - `top: true` on `de1`/`de2`: X CONDs both ways from the pin tops too, when the PDF draws arrows over the dead end pins.
  - `riser` TOR: riser box (2A4127) from the ground to its row, `k` `C` centered on the pole (pole runs through it), `R`/`L` beside it. Callout `TOR`.
  - `qp` QUEENS POST: a line at its row from the pole out to its anchor's distance (`an`, or its own `L`). Guys with
    `via: <qp index>` (index among the spec's `qp` items AS LISTED) run from the pole to the QP end; one more guy runs from the QP end down to the anchor.
    Callout text `QUEENS POST`.
  - `ins66` TRANS INS 66 leaning up from the pole (2E37A8 right, 2E37C0 left, 19.11 long), `k` `L`, `R` or `LR`.
  - `de66` TRANS DE 66 (2E37D0) on the pole with X CONDs (2E37E9 / 2E37EA), `k` `B` (default), `R` or `L`.
  - `tpi66` SIDE XARM on the pole with a TRANS P&I hanging below and X CONDs both ways from its bottom (template
    group 2E3428, 2E3429, 2E3928, 2E3929 as is). The row is the X COND line; the pole line runs up to the box top.
  - `tpiarm` XARM (2E33E5) with TRANS P&I hanging at the slots in `pins` (2E3456, 2E3457, 2E3459, 2E3458).
  - `ar` SIDE AR (recloser, 2E33E8) centered on the pole. `tpi66` `k: "R"` mirrors the group to the right of the pole.
  - `de115` TRANS DE 115 (2E37DB, 4.8 x 8): `k: "L"` box left of the pole with its edge on the pole line (TD2524712
    2115931E L/E, Kevin), `"R"` right, `"C"` centered as in the template. `xc`: X CONDs from the box center, `"B"`, `"R"`,
    `"L"`, or none (default; draw them only when the PDF does).
  - `ins66` with `lvl: true`: the level TRANS INS 66 pair (2E3494 right, 2E37B8 left) instead of the leaning up one.
  - `pharm` PH & LA ARM front view: the COMBINATIONS example group (XARM 2E3810, 4 POTHEADs, 4 SURGE ARRESTERs) centered on the pole.
    `ph` / `sa`: offsets from the pole to place them as the PDF draws them instead (a PH left of the pole is the
    mirrored one), e.g. TD2524712 2115931E: `"ph": [-31.05, 16.18, 30.0], "sa": [-24.18, 9.17, 25.08]`.
  - `onebox: "L"` / `"R"` on `de2`: dead end both ways on ONE box (box and pin on that side, the other side's ticks
    from P + 2 and its X COND from the pole); with `top` both arrows start at that pin top.
  - `box: "B"` on `xr`/`xl`/`xb`: a SIDE XARM on each side, X CONDs from the box edges. A span guy sharing the row
    (`share`) on a boxed side starts at the box edge (P +/- 5).
  - `boxdn: true` with `box`: the box hangs under the X COND line (top on the row, edge on the pole) and the X
    CONDs start at the pole.
  - `pt` PT (2E33EB) beside the pole on the `k` side (`C` centered); `la: true` adds a SURGE ARRESTER (2E3870) 1.5 clear of each side.
  - `omni: "L"` / `"R"` on `de1`/`de2`: INV OMNI CLOSED 5 beyond that side's dead end box insertion, on the row (`omni_lean: "R"` mirrors it).
  - `xbank` XFMR BANK (2E3426) centered on the pole. `disc` DISCONNECT ARM (2E38FB) centered on the pole.
  - `co` / `sa` on `arm`: front view CUTOUTs / SURGE ARRESTERs at any offsets from the pole (a 3 phase FH & LA
    arm drawn S-SA per phase). `circx`: conductor circles at any offsets (with `pinx`).
  - A guy without `c` is drawn with no DG callout or leader (the PDF draws the guy but labels no DG).
  - `o`: tie-break order for two items at the same height.
- Anchor labels: the far anchor's at ground, the others stacked above from the farthest to the nearest (leaders never
  cross), each raised until its leader's arrow segment is at least 15.1 long (shorter and the arrowhead does not draw).
  Bearings written on the PDF go in the label (`EX: CATV ANC 122%%D`).
- Guys on both sides of one pole: give the anchors on the other side `"gs": 1` / `-1` (the profile's `gside` is the default).
  Each side gets its own anchor scale, lead dims, DG stack and anchor labels; the lead dims stay 12 below the ground line and
  the pole label (centered on the pole) drops 12 per lead dim row below them.
- DG callouts that would land on equipment callout text on their side (QP callouts) step to the nearest clear spot, and
  the first one rises (up to attach - 8) when a leader would still run through callout text; leftovers are reported.
- `anchors[].L` lead as written; `guys[].an` index into `anchors` as listed (any order; the generator never reorders the list).

- Spec `handle_map`: `{template handle: handle in this drawing}` for stash pieces whose handle differs in a template copy
  (defaults are the current template: ELEV lead `39498C`, RULING SPAN `3948FA`..`3948FE`; older copies made before the template update had `39AD07` and `3948B8`..`3948BC`). `rspan_h`: `[box, line1..line4]` of the RULING SPAN example when it differs.

## Rules built in

Height scale and cluster step-up, dim tight fit (1.92 gap, 4.4 beside an
arrowhead), horizontal dim labels stepped up 8 until clear of other labels and
callout text, X CONDs starting at the pin, span guy halves 2E3466 / 2E3954,
anchor scale from the shortest lead, DG stacking and lift, pole label by guy
side, CREW/NOTE/GPS/ELEV stack, ELEV as a bare number, TLM street-only
addresses and ADDRESS LIST visibility, pole names and row 3 sheet numbers.

- Pole `calcs`: `[{"hdr": "%%UUNGUYED DE CALC (7733E)", "rows": [["left", "= right"], ...]}]`, drawn from the NOTE
  stash pieces, first box top at Cy - 100, each next 10 below. In combined
  calcs the line under each lettered load (`A. ...`, `B. ...`) is indented 9.923. `tlm.notes`: TLM NOTE box under the visible table.
- Pole `riser`: riser detail under ELEV (docs/risers.md): `{"items": [{"c": "SEC", "deg": -10, "size": 3, "lead": 20}], "guards": [{"t": "unistrut", "deg": 70}]}`.
  `deg` = riser position around the pole (0 = 3 o'clock, counterclockwise), `size` in inches (SEC 3, PRI 5 by default), `lead` optional
  leader angle, `L` defaults to the first profile's, `drop` pushes the detail lower. 4" risers use a radius edit; U-GUARDs use arc center/angle edits.
- Pole `rspans`: `[[from, to, ruling span, final sag]]` as written, RULING SPAN boxes (template example 3948FA at
  1541.4998, -817.1629) centered on Cx under the calcs (Cy - 100 when there is no calc), each 10 below the last.
- Guys attach at the row of the item with the exact same height first (DG @ 22'6" at the 22'6" COMM row).
- EX-LOAD and PR-LOAD are sent without `%` (the block prints its own).
- More than 10 TLM addresses: the block stays at ADDRESS LIST 10 and rows 11 to 20 are burst rows (row 12 pieces
  3975AC, 3975AD, 3975E9, 3975F7 copied down 11.7326 per row from the LIST 10 bottom, insertion y - 129.0591).
  The TLM NOTE box goes under the last row. Rows continue while the table and notes fit above the frame bottom (60 with three notes); beyond that the rest is reported.
  The handles differ per drawing: query `TLM_EXTRA_WINDOW` (x 1850 to 2003, y -792.5 to -779.5, layer MISC) and put
  them in the spec as `"tlm_extra": [address text, meter text, box polyline, divider line]`; `pick_tlm_extra(entities)`
  picks them out of the query result (it also returns rows 11 and 13).

## QC after the apply (qc.py)

Box widths, calc centering and DG leader ends are estimated from text widths, so
they are checked against the drawing after the job runs. `qc.py` does that and
the rest of the mechanical checks, and prints only failures:

```
python qc.py spec.json job_TD2536120.json job_TD2536120.result.json query.json --fix fix_TD2536120.json
```

- `query.json`: a `civil3d_entity` query over the used frames, types TEXT,
  LWPOLYLINE, LEADER, DIMENSION, INSERT, includeGeometry true. A saved tool
  output file can be passed as it is. Several files are fine.
- It rebuilds the job from the spec and stops if that does not match the job
  file, so every new handle is known for what it is.
- Checks: every text, dim text, attribute, visibility, layer and color edit
  landed; text overlaps; guys or leaders through text; crossing leaders; one
  callout column per profile; dim labels clear of each other and of callouts;
  note, calc and ruling span boxes fit their measured text (calcs and ruling
  spans centered on the sheet); TLM notes inside their box; DG leader ends 2.8
  from the measured text edge with the arrow on a guy; DG callouts 30 apart;
  note text rules in the spec.
- `--fix`: box refits, calc re-centering (moves) and DG leader re-points as an
  apply job, ready to approve and run. Everything else is reported for a fix
  by hand.
- It cannot tell whether the spec matches the PDF (heights, slant, box sides,
  symbols, L/xx). A clean run means the drawing matches the spec and the rules.
- Entities it cannot find in the query are counted and not checked: widen the
  window or types and run it again.

---
name: "pole-head-detail-drafting"
description: "Draft overhead pole head details in Civil 3D from a pole head PDF by copying and editing AUD OH template Builder pieces through the civil3d_entity MCP tool."
---

# Pole head detail drafting (AUD OH template, Civil 3D 2026)

Use when Kevin asks to draft a pole head detail, or a whole job of them, from a marked-up PDF into the AUD OH Template drawing open in Civil 3D. Everything is built in model space by COPYING template content and EDITING it; never draw equipment from scratch. Every job starts from a FRESH template copy (frames read `POLE#`); all pieces come from the Builder, example and stash areas, whose handles are the same in every copy. Kevin is the QC lead: run the QC checklist before reporting.

Each pole gets its own sheet frame with the pole detail, pole name, CREW NOTE / NOTE boxes, GPS and ELEV blocks, and when the PDF has them a DE CALC box, a TLM block with its TLM NOTE box, and a riser and/or obstruction detail. Everything sits at fixed offsets from the frame.

This file is the core. Topic rules live in the fork at `tools/polehead/docs/`. Read a reference file ONLY when its trigger fires:

| Trigger (from the survey) | Read |
| --- | --- |
| Every job, step 3 (note lines) | `docs/sheet-data.md` |
| Any down guy, span guy or anchor | `docs/guys-anchors.md` |
| A calc table in CALCS | `docs/calcs-unguyed.md` |
| TLM data (filled table, pasted snippet, TLM xlsx tab) | `docs/tlm.md` |
| Risers (small circles) in the RISER/OBSTRUCTION DETAIL box | `docs/risers.md` |
| A fence or other obstruction in that box | `docs/obstruction.md` |
| Hand-building or hand-fixing a piece the generator does not place, or a qc.py failure you need the rule for | `docs/layout-rules.md`, `docs/template-pieces.md` |
| A tool error, odd plugin behavior, a hand-built job with moves, mirrors or dims | `docs/plugin-quirks.md` |
| Writing the spec | `tools/polehead/README.md` (spec format and item types) |

## Job timing

Get the current time from the shell (`TZ=America/Los_Angeles date`) before reading any file, and again right before the final report. The report ends with start, end and duration. Only the initial job run is timed; later refinement rounds are not.

## Autopilot

Work straight through every pole; do NOT stop to ask. Collect problems for the final report:
- A symbol not in the mapping, or unreadable: skip it, draft the rest, note it (pole, height, look).
- A bad source (unreadable page, missing tab, contradictory TLM, a clipped snippet): skip that piece, note it.
- CALCS content that is not a calc table: skip and note (a SOIL TYPE note is drafted, see guys-anchors.md).
- TLM addresses: draft every row that fits the frame (60 with three notes); more than that: fill what fits, note it.
- NEVER infer what the planner left out: a missing height draws as `_'`, a missing value stays blank or as written. Do not cross-reference the Station Builder or material lists to second-guess the PDF (for example IN vs EX). Planner errors are the planner's.
- Everything else: make the most reasonable call and keep going.

Final report: ONLY what Kevin must look at (skips, TLMs that did not fit, questionable calls, calc math that does not add up, a calc type drafted for the first time). Not reported: suffixed tab names, a default L/N, unlabeled anchors left without callouts, Station Builder blanks left as written, a blank elevation, `_'` heights, dropped duplicate notes. Nothing of concern: say so in one line. End with the job timing.

## Setup

- Civil 3D 2026 with Kevin's fork simsuds/Civil3D-mcp loaded. Tools: `civil3d_entity` (query, copy, edit, erase, hatch, apply), `civil3d_request_approval`. Clone the fork into the workspace every job; use `tools/polehead/` (`polehead.py`, `station_builder.py`, `qc.py`, README, `docs/`). Never rebuild the generator.
- Every copy, edit, erase, hatch and apply needs `civil3d_request_approval` with toolName, action and the EXACT parameters (including `"action"`), then the call with `approvalToken` and identical parameters.
- Build with `apply`: the generator writes one job file; commit it to the job folder with `device_commit_files` (stage it under /mnt/user-data/outputs first), approve and run `{"action": "apply", "jobFile": "<absolute Windows path>"}`. Do not touch the file between approval and apply. The handle map lands beside it as `<job>.result.json`.
- Job folder files (names vary): the PDF with `POLEHEADS` in its name (one page per pole; a trailing `POLE # X` form page is not a pole; may be a scan with no text layer), the Station Builder xlsx (`STATION BUILDER`, `STATIONS` or a misspelling; one tab per pole, suffixed tabs like `1296855E EXTREME` are matched by `station_builder.py`), an optional TLM xlsx. Never write back to them.
- A PDF pole number and its tab differing by an obvious typo in a numbered series: use the tab's number and note it.
- When a rule here or in `docs/` changes, change the generator too (commit and PR) so they never disagree.

## Token discipline (Kevin is on Pro)

- Never query the whole drawing; always a tight `window` plus `types`/`layers`; `includeGeometry: false` when extents and text are enough. Big results are saved to a file: parse with python (the part starting with `{` holds the result).
- Survey once: pdftotext condensed dump of every page for all callout wording; render pages at -r 50 to -r 110 for layout; crop and zoom (-r 200 to 400) only where a symbol, side, slant, pairing or table needs it.
- Station Builder: ONLY columns N:Q rows 4 to 46 of each pole tab, via `station_builder.py`.
- Read reference files only on their trigger.

## Reading the PDF

- Builder pages: two profile slots, L/N left and L/E right. Hand sketches: pole number top right, callouts with heights, `PROPOSED` and direction under each profile (`4 NW` = L/NW).
- Callout wording: drop dashes between parts (`IN: 4/C 336ATW 16KV`, `1/0AT 120V`, `25KVA XFMR`, `2-F/H'S`, `9/32" SG`).
- One profile goes in the slot it is drawn in (N slot P = Cx - 300, E slot P = Cx + 300; generator: `L/E` goes right automatically, `slot: "R"`/`"L"` otherwise). Two profiles: PDF left in the left slot.
- Direction: 8 points only (NNE becomes NE). A red slash between letters (`L/N/E`) reads as `L/NE`. The untouched blue default `N`/`E` means L/N or L/E (not reported).
- A second profile drawn with symbols but no callouts or heights: copy the callouts and heights of the matching rows from the profile that has them (dims are stacked from the callout text).

## Symbol mapping

Crossarm with dots or pins = XARM + VERT P&I (a 3/C arm is usually `pins: [0, 1, 3]`); a crossarm line with circles = conductor circles; pins with a small circle at their base = pin AND conductor circle at that slot (zoom -r 300 on every arm); a tilted pin = slanted VERT P&I leaning the same way (`slant`); S or 2 = CUTOUT; small I bar = SURGE ARRESTER; `FH ARM` with outer S cutouts only = `fhlaf` `nosa: true`; a side box with arrester and slanted bar called PH & LA = the PH group (`ph`, never FH/LA); a line through the pole with dots = guard arm line with hanging dots (`gal` `dots`); boxes on the pole with arrows and ticks = side dead end (`de1`/`de2`, `top: true` when arrows are drawn over the pins); small box with a pin on top and arrows both ways = side single arm group (`pri`); a lone small square = SIDE XARM (`box`, plus `boxup: true` when it sits on top of the X COND line; a SMART CONNECT box too, ignore one slanted tick on it); a guard arm drawn as a line through the pole = 35 unit line, centered (`gal`); a short arm out from the pole with a dot at its end (COMM ARM) = `arm1` (never an X COND); slanted ticks under arm slots, or a circle with a slanted tick beside a dead end / single arm box = INV OMNI CLOSED 2E344E (template orientation leans left, mirror for right leaning); an omni beside a lone SIDE XARM = `box` with `omni: true`; an omni beside a dead end box = `omni: "L"`/`"R"` on `de1`/`de2`; omni under arm slots or beside a single arm box is not placed by the generator yet, add by hand (see template-pieces.md); RCS control box = `rcs`; dot on pole = SEC-MISC (`dot`); a red QC circle on the pole = a dot at that row; an unlabeled dot = `dot` with `label: "_'"` and no callout; arrow from pole = X COND as drawn; a line through the pole with arrows both ways = X COND both ways; COMM/CATV LINES are always X CONDs, arrowheads or not (crossing the pole = both ways; one side = that way); only a bare dot with no line stays a dot (keep the dot under the X COND when both are drawn; zoom -r 200 on faint comm rows); tall narrow box on pole = SIDE XFMR (`xfmr`, centered when the pole line runs through it); horizontal (often wavy) line labeled SG = span guy half (`sg`). Pins drawn all to one side of the pole (a 3/C secondary with three pins right of the pole) = `arm` with `pinx` at the drawn offsets, never the standard slots. ST LT = `stlt` (`k: "C"` lamp head seen from the front, `R`/`L` side arm). Transmission (66KV/115KV; planner visuals vary, map by look): strings leaning up from the pole = `ins66`; level strings with circle ends = `ins66` `lvl: true`; a box with circles beside the pole = `de115` on the side drawn (`k: "L"`, no X CONDs unless drawn); a box or circle centered on the pole with X CONDs both ways = `de66`; a SIDE XARM with a P&I hanging and X CONDs = `tpi66`. PH & LA ARM front view = `pharm` with PHs and SAs at the drawn offsets (`ph`/`sa`); PT & LA = `pt` `la: true`; one dead end box with ticks and arrows both ways = `de2` `onebox`; boxes on both sides of a comm X COND = `box: "B"` (a shared SG starts at the box edge); a comm box drawn under the X COND line = `boxdn` (X CONDs from the pole). Box sides: put every side box, XFMR and FH/LA box on the side the PDF draws it. Anything else: skip and note.

## Spec rules the generator cannot guess

- Heights: `h` = true height as written. No height: `h` = where the PDF draws it, `label: "_'"`.
- Callout side: all on one side, default right. Down guys on one side: callouts opposite. Guys both sides: the less cluttered side. A span guy does not decide.
- Callout text: no heights on equipment. New work `IN:` (color 90), `RM:` color 90, existing equipment no prefix. COMM/CATV drop the height, keep directions and MSG (`COMM (NE)`, `CATV MSG`). SLACK always reads `(SLACK)`, never SLACKED (the generator enforces it): `IN: 3/C 1/0ATW (SLACK)`, `(SLACK)(S)`.
- Guys, anchors and DG wording: `docs/guys-anchors.md` (pairing by tracing is mandatory). Guys on both sides of one pole: anchors on the other side get `gs`. QP `via` indexes the `qp` items as listed in the spec.

## Workflow

0. Note the start time.
1. Find the files. Survey all pages (details, TLM + CALCS strip, RISER/OBSTRUCTION box). List per pole: calcs, TLM, risers, obstruction, guys. Fire the triggers.
2. Per pole: every callout, true height, arrow direction, box side, pin slant, dot, red circle, slot, second profile; guys traced to anchors.
3. Run `station_builder.py` for all poles; apply `docs/sheet-data.md`.
4. Write the spec (README format); TLM over 10 addresses needs `tlm_extra` (tlm.md); risers go in the pole's `riser` (risers.md).
5. `python polehead.py spec.json -o job_<TD>.json` (NOTE lines on stderr go to the report); commit, approve, apply once.
6. Stage the result file. Verify query over the used frames (types TEXT, LWPOLYLINE, LEADER, DIMENSION, INSERT; includeGeometry true; one query per frame row so each saves to a file). Run `python qc.py spec.json job_<TD>.json job_<TD>.result.json <query files> --fix fix_<TD>.json`; commit, approve and apply the fix job plus anything else it reports. qc.py cannot check the spec against the PDF: check items 1, 6, 7, 8, 9, 10, 14 by eye. SOIL TYPE boxes go in the fix job by hand.
7. Obstruction details: separate small job per `docs/obstruction.md`, south of any riser detail.
8. Note the end time; final report per Autopilot.

## QC checklist (every pole)

0. No template text or placeholder left (dims, callouts, notes, attributes, frame pole name, pole label).
1. Rows per the cluster rule; true heights in dims; `_'` where the planner gave none, never an inferred number.
2. Callouts on one side, one aligned column, IN/RM color 90, no heights on equipment, comm/CATV wording kept.
3. Dims on the callout side, DIMENSION ByLayer, 12 apart, attached at equipment ends, tight fit, no dim crossing text.
4. Dim labels clear of each other and of callouts.
5. DG callouts: leaders 2.8 from the measured text, 30 apart, correct guy, outside boxes; EX on existing.
6. Anchors: scale distances, lead dims, base line, labels only where the PDF labels, leaders not crossing and at least 15.1; SOIL TYPE when given; every guy ends at the anchor the PDF draws.
7. Pole label per the guy rule; pole number and L/xx match; correct slot; G = Cy.
8. Pole line to the top equipment; down guys on GUY; span guys are SG halves.
9. Box sides, centered boxes, pins and slants as drawn, cutouts never mirrored, base circles present, PH groups, guard arm dots.
10. Every dot (and red circle) placed; every COMM/CATV line an X COND in the drawn directions.
11. Notes per sheet-data.md (position, one line each, uppercase, dash, blanks, typos, box fit, spacing, LAT/LONG, FOOTAGE).
12. DE CALC per calcs-unguyed.md.
13. TLM per tlm.md.
14. Every skip and every TLM that did not fit in the report; nothing inferred.
15. Every pole has a frame (pole 9 and up in added frames, sheet number frame + 2).
16. Riser details per risers.md (radius by size, edge touching the pole, `SEC`/`PRI`, no heights in riser callouts); obstruction details per obstruction.md, never overlapping.
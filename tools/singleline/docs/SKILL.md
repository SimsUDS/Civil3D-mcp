---
name: "sce-single-line-drafting"
description: "Draft SCE schematic single line (one-line) diagrams in Civil 3D from circuit-map PDFs: read the vector PDF inside the red cloud, place SGL_* blocks by copying template samples, route conductors onto exact block terminals, label everything like the finished Ash job, and lay roads 7 ft off the cable. Use when Kevin says single line, one-line, circuit map, SGL blocks, or names a circuit (Royer, Lawrence, Ash) to draw."
---

# SCE single line drafting (singleLineTemplate.dwg, Civil 3D)

Use when Kevin asks for a single line from an SCE circuit-map PDF. The finished `Ash\Ashsingleline.dwg` is the
reference for every look-and-feel question; the PDF is the reference for what exists and where. When the two disagree,
ask, or follow the rule below that settled it.

This file is the core. Read the reference files when their trigger fires:

| Trigger | Read |
| --- | --- |
| Every job, before drafting | `docs/drafting-rules.md` (all of Kevin's rules, with the reasons) |
| Placing or wiring any block (terminals, label offsets, vaults, ways, PMEs, BLF, capbanks) | `docs/block_conventions.md` |
| Changing the generator | `generator/` (reference implementation: Royer page 1 + Lawrence page 10) |

## Workflow

1. **Read the PDF as vectors.** `extract_page.py <pdf> <page> <out.json>` gives conductors, poles, boxes, triangles,
   label glyph clusters, street lines and the red cloud. Draw only what is inside the cloud. Text is outlined glyphs:
   read each label cluster by eye and map it by cluster id.
2. **Register extra pages** onto page 1 with a similarity transform seeded from two shared symbols (Lawrence p10 → p1:
   scale 0.853, no rotation). Map page points to drawing feet with `T(x, y) = ((x - 150) * 3, -(y - 290) * 3)` + origin.
3. **Identify small symbols.** `symbol_census.py --dict symbol_dictionary.json` labels every vector symbol type and lists
   unlabelled ones; `extract_symbols.py` finds fuse zig-zags, ground taps and chevrons with their attachment points.
4. **Generate the job** (`generator/build_royer_v6.py <job.json> <fresh query.json>`). It copies template samples
   (never inserts by name), places blocks from their measured terminals, routes cables onto them, then runs the final
   passes in order: RR, split at pole switches, equipment snap, end sweep, debris, pothead stubs, label relocation.
5. **Query the drawing immediately before every build** (`civil3d_entity query`, crossing window, limit 3000) and erase
   exactly what that query returned. A failed apply still commits its creates and copies.
6. **Diff conductors against the previous build** after any rule that removes or moves geometry, and explain every
   change. Never delete a cable on a guess.
7. **Apply** with `civil3d_entity apply` (approval bound to the job file hash). Dynamic angles must be exact radians.
8. **Check:**
   - `sweep_ends.py <query.json>`: every cable end on a terminal (Lawrence leaves only the 2 the sheet leaves open);
   - `road_check.py` / `road_overlay.py`: PDF streets drawn, replaced or missing; roads with no PDF street;
   - `tile_check.py`: PDF tiles vs drawing renders, reviewed by parallel agents for anything missing or different;
   - render each spot Kevin raised and compare it with the PDF and with Ash.

## Core rules (details and reasons in docs/drafting-rules.md)

- Cables end exactly on block terminals. Under 2.5 ft off, slide the block onto the line; never add a small jog.
- Conduit never leaves a vault and re-enters it. Way cables leave the vault bottom and turn below it, nested.
- Gear-switch way and junction-leg cables are UG. Linetypes: solid OH3PH; dashed OH1 (OH1PHwN with ring markers);
  dash + ticks UG3PH, UG2PH for the 2-phase loop to 1-phase A/B pads. Split a chain where the pattern changes.
- Straight runs are single segments (UG dots must show). Hops are 4 ft bulges on the parallel conductor.
- Labels sit on top of their line, never upside down, clear of lines, blocks and other labels (CW 2.8 ft/char at 3.2).
- Structure boxes sit on their cable; box labels go on the side the PDF shows.
- Roads: whole PDF streets a cable follows become their own shape 7 ft off the cable, on the PDF street's side; the
  far edge line is dropped; cross streets are carried onto the road. Dedupe the PDF's doubled street strokes.
- Draw EXISTING only; Kevin owns sheet panels and circuit numbering beyond CIRCUIT-1.

## Known gaps (2026-11-25)

- A few cross streets on the Royer/Lawrence seam at E Orangethorpe still end on the old north edge line (x≈24900,
  x≈25385) and one short PDF stroke pair forms a V at x≈25260.
- Royer's S Lemon road follows Ash (west of the cable) although the PDF street is east.
- The generator has absolute paths to the Ash job; it is a reference implementation, not yet a general CLI.

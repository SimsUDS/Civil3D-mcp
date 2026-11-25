# How the finished Ash single line places each block

Source: Ashsingleline.dwg, EXISTING copy. Every block was measured with block_study.py (block_study.json / block_study.txt), and every block family was then checked visually (bs_*.png).

## Units and coordinates
- All numbers are drawing feet at 40 scale. Blocks are inserted at scale 40 (a few are mirrored, x = −40).
- **Terminal** = where conductor polylines end on the block, in the block's own frame, i.e. rotation removed. "(10, 0)" means 10 ft along the block's rotation direction.
- **Label offset** = text centre minus insertion point, in world axes. Labels are almost always horizontal (rotation 0) even when the block is rotated.
- Text height is 3.2 everywhere. Labels use layer SingleLine, except tie names, which use the tie circuit's layer.

## General rules seen everywhere
1. **Conductors end exactly on terminals.** Polylines stop at a pothead tail or tip, a transformer feed, a switch way or a junction leg. They pass straight through poles and structure boxes, which sit on the line.
2. **Structure numbers go above.** Pole, structure and transformer numbers are centred about 7 ft above the insertion: pole (−0.4…1.4, 6.9…7.3), transformer P# (0…1, 6.4…9). This holds even when the block is rotated; the label stays horizontal.
3. **Cable sizes sit on the line**, centred on a span, about 2.7 ft off, rotated with the line (r0/r2 or r90/r92).
4. **Phase labels.** 1-phase and 2-phase runs carry a phase label placed like a cable size: AØ, BØ, CØ, ABØ, ACØ, BCØ (also "BCA", "ABC"). They come only from phase text printed on the circuit-map sheet (e.g. Putter B2, page 8). Royer, Lawrence and Richman print none, so they get none. The generator's `LINE_TEXT` / `on_conductor` puts them, and cable sizes, on the nearest run.
5. **Hops.** Every crossing of two conductors gets a semicircle hop, about 4 ft, on one of the two lines. They are frequent inside and below vaults where several ways' cables cross.
6. **Continuation arrows.** A run that leaves the drawn area ends in SGL_SYM_ARR_DC with text such as "TO P5311503 & LOAD" or "TO V5091493 GS2819 & LOAD".
7. **Ties.** A tie to another circuit is an SGL_SYM_ARR_DC on that circuit's layer, with the circuit name in two lines (e.g. "ROMA" / "FULLERTON") on the same layer beside the arrowhead.

## Block by block

### SGL_PO_WD_JO_IN (general pole, n = 349)
- Always rotation 0, layer SingleLine. The line passes through the insertion point; terminal (0, 0) is either a vertex or a pass-through.
- **Label:** the pole number, centred +7 ft above. A second id line can follow, e.g. "761907H" (H-numbers for streetlight poles), or a word below such as "ISOLATOR".

### SGL_PH (pothead, n = 74)
- **Rotation:** 0, 90, 180 or 270 (a few odd angles on diagonals).
- **Terminals:** (0, 0) is the OH/tail side, where the overhead line ends; (10.5, 0) is the tip, where the UG cable starts.
- **Label:** the pole number beside the tail at mid-height, e.g. (12, 1.5) for r92, or 7 ft above for horizontal ones. A variant is "4329428EPH1" for a second pothead on the same pole.

### SGL_PH_FUSED (n = 13)
- Same as SGL_PH, but the tip is at (16, 0).
- **Labels:** pole number beside it. "80A" or "FD07534"-style fuse ids sit beside the pole number.

### SGL_TRAN_DE (n = 48: 28 ELBOWS-ON, 20 ELBOWS-OFF)
- **Rotation:** 0, 90, 180 or 270, chosen so the feed faces the incoming cable.
- **Terminal:** (0, 6) with ON, (0, 4) with OFF. That is the feed point on top of the box; the cable ends there.
- **Label:** P#, horizontal. It must never cross the elbow chevrons (Kevin, P5319466, 2026-11-25). Measured over 48 in Ash:
  - r0, top-fed (elbows on top): beside the chevrons, centre at (±12.5, +9), whichever side is clear.
  - r180: centred above at +9.3.
  - r90 / r270: centred above at +7.3.

### SGL_TRAN_BP (1P BURD/PM dot, n = 37)
- Rotation 0. The cable reaches the dot edge (about 5 ft from centre) and gets an SGL_LBE chevron where it enters.
- **Label:** P# about 7.5 above, or beside the dot when crowded.

### SGL_LBE (load-break elbow chevron, n = 61)
- Rotated to the cable direction (0, 90, 180, 270). Placed at the cable end, at a transformer dot or a junction leg (it marks the elbow).
- **Terminal:** (0, 0).
- **Labels:** none of its own.

### SGL_BOX (n = 105)
- **Small structure box** (X#, V#, M#, about 6 × 8 ft: D1 = 6, D2 = 8 most common). It sits on the line, which passes straight through. Label centred about +7 above.
- **Vault box** (dynamic size), around gear switches and junctions:
  - Its V-number is centred about +2.7 ft above the top edge (outside).
  - The switch number (GS####, OS####, BS####, J###A) is centred about 2.7 ft below the top edge (inside).
  - The block's own "1 2 3 4" sits under that, then the switch body.
  - Margin is about 3–6 ft around the switch. Width is about 20–35 ft for one switch, 45–86 ft for two switches or a switch plus a junction.
  - Cables leave through the bottom edge, one per way, straight down, then turn (hops where they cross).

### Gear switches
- **Which block:** SGL_SW_nW_RAM is the normal one: 3W ×5, 4W ×6, 5W ×5, 6W ×1, 2W ×1. SGL_SW_nW_RAG is only used where the map prints "R A G" beside the switch (GS4801, GS0136/0137, GS5804, GS6491, GS7379).
- **Ways:** terminals are at y = 0, the bottom edge of the switch body, at these exact local x values (measured from Ash's end vertices):
  - 3W_RAM: 0, 3.6, 7.2
  - 4W_RAM: 0, 3.47, 7.13, 10.6
  - 5W_RAM: 0, 3.81, 7.41, 11.01, 14.61
  - 6W_RAM: 0, 3.6 … 18.0
  - nW_RAG: 3.7, 7.48, 11.26, 15.04, 18.82
  - JBAR_3W legs: −0.09, 3.91, 7.91 at y −5.29. JBAR_4W legs: −0.07, 3.33, 7.17, 10.59. These are not evenly spaced; with even spacing the SGL_CAPs on J495 missed their legs (Kevin, 2026-11-25).
- **Cables leave each way straight down** from that terminal (Kevin, V5092570), then turn. Ways keep the map's order: way k's cable goes to terminal k, never to the nearest free terminal. Way cables that run sideways nest (the nearest way turns first) and hop over the straight drops.
- **Vault floor (Ash V5091495, Kevin 2026-11-25):** way cables cross the vault's bottom edge before turning.
  - A vault with a tie reaches just past the tie arrow, about 32 ft below the switch. Its cables turn about 32–46 ft below the switch, which leaves room for the tie name.
  - A vault without a tie has its cables turn about 14–20 ft below the vault.
  - The legs nest: the way nearest the turn side turns highest.
  - The generator lowers any leg the PDF puts inside the vault to floor − 6 (− 16 with a tie), stepping 4 ft per leg. The far end keeps its place and is joined back with a square jog.
- **Two blocks in one vault (Ash V5091495):** keep them together. The junction bar is top-aligned with the switch (JBAR insertion = switch top − 4.45) and sits about 20.6 ft beside it, not at its PDF position. Each device label is centred just above its own block (Kevin, 2026-11-25).
- **V5091496 (Ash): BS0184 (SGL_SW_3W LTR-UP) + J496 (JBAR_3W).**
  - SW_3W terminals: T (0, +4.8), L (−4.8, 0), R (+4.8, 0).
  - Side cables run 9.5 ft straight out before turning; R runs out and up through the top of the vault.
  - J496 is top-aligned 13.3 ft right of the switch. That gap is 20.6 ft next to a gear switch.
  - Each J496 leg has an SGL_LBE r270 at its end. Leg 3 has an SGL_TRAN r270 3.25 ft below the leg on a short UG stub (the map's squiggle-and-ground), not a TRAN_FUSED. Widen the vault to the SGL_TRAN's ±4.9.
  - BS0184's label sits up-left beside the cable entering T, its right edge 2.5 ft clear of the T cable and the "T" letter. Widen the vault to hold it (Kevin, 2026-11-25).
  - Text width: 3.2-high text renders about 2.8 ft per character. Use that, not CW, for clearance checks.
  - A junction bar's device label is centred over its legs (the block's "1 2 3"), not over the bar plus any SGL_TRAN hanging beside it.
  - The V-number slides along the vault's top edge to a spot no cable crosses, nearest the middle (as in Ash).
  - Ash runs L out of the vault and back into J496 leg 1. By Kevin's rule it stays inside: 3 ft out of L, down, across, up into the leg.
  - Assign terminals to cable ends closest pair first, each used once. Otherwise one cable can be taken by two terminals.
- **A transformer faces its cable's last run:** take the rotation from that segment's direction, not from where the cable end happens to lie. When a block moves, the end shifts sideways and would otherwise swing the transformer 90°.
- **V5770309 (GS0136 + GS0137), Kevin 2026-11-25 "still quite messy":** don't follow the PDF's slanted paths out of a vault. Route each way cable square:
  - **GS0136 way 1 → FULLERTON SUB:** straight down to the sub's level, then across into its edge.
  - **GS0136 way 2 → V5122231:** down to the floor 16 ft under the vault, across past the vault's right edge, up, into the box.
  - **Order:** the inner way turns higher, so the cables never cross.
  - **Find the terminal end** by the way terminal, not by which end is higher.
  - **Sub label:** "FULLERTON / SUB" sits beside the circle (right), clear of the feeders arriving above it.
- **A conduit never leaves a vault and comes back in** (Kevin, 2026-11-25). Ash's GS2818 way 5 runs below the vault and back up into J495 leg 1; that is an error in Ash. A cable joining two terminals in the same vault stays inside the box: down from each terminal, across 6 ft under the lower one.
- **J495 (Ash):** JBAR_4W with SGL_CAP r90 on legs 2 and 3 (the map's ground marks). Leg 4 runs straight down to P5319466, so the transformer slides under the leg rather than the cable bending to it.
- **GS2818 (Ash):** the tie way (3) is drawn open (Angle3 = 20°), with the tie arrow hanging from it.
- **Fused way (squiggle on the map):** SGL_TRAN_FUSED at the terminal, r270, inside the vault. Examples: GS2979 way 5, GS2819 way 2, J573 leg 2, J496 leg 3. A squiggle at the corner of a way's cable (GS2898 way 1) gets the TRAN_FUSED at the foot of the drop.
- **Open way** (blade drawn diagonal on the map): dyn Angle_k = 20° (0.3490658503988659) for RAM, 30° (0.5235987755982988) for RAG; the job refuses rounded values. A grounded way (⊥) gets SGL_CAP r90 at its terminal (GS0137 way 2).
- **Tie ways:** a SGL_SYM_ARR_DC hangs straight down from the way (r270) on the tie circuit layer. The tie name sits below the vault, about 56–64 ft below the vault top, on the tie layer.
- **Unused or capped ways:** SGL_CAP (r90) at the way.
- **Tap transformer on a way:** SGL_TRAN_FUSED hanging from the way (r270).
- **Dynamic angles:** 0.35 rad (RAM) or 0.52 rad (RAG) on a way shows that way drawn open or angled. Match the map's open/closed way.

### SGL_JBAR_3W / 4W (junction bars)
- Rotation 0, inside a vault box. Legs end at y = −5: 3W legs at x = 0, 4, 8; 4W legs at x = 0, 3.7, 7.5, 11.3.
- Cables come up to the leg ends; LBE chevrons sit at the legs.
- **Labels:** J#### centred above the bar inside the vault; X# or V# centred above the vault.

### SGL_TRAN_FUSED (tap transformer / fuse to load, n = 14)
- r270 hanging below a switch way or off a line.
- **Label:** S# (streetlight) or P# below it, about −15.

### SGL_SW_CL_POLE (PS closed "X") / SGL_SW_PO_OPEN (PS open bars)
- On the line, rotated with it. Terminals at ±14 (closed) or ±8 (open). The line is broken at those points.
- Paired with an **SGL_PO_SW** circle (PS or PD) beside the line:
  - DEVICE_NUMBER and POLE_NUMBER attributes are filled (the pole number shows under the circle).
  - "LOAD BREAK" text sits about 17 ft below the circle when the map says so.
- A fault indicator on that pole points at the PS circle from the far side.

### SGL_OH_FI (fault indicator / RFI)
- **With a leader on the map (Ash FI07808):** the insertion is the pennant's tip, placed at the PDF tip. A SingleLine polyline runs from the tip to the point on the conduit where the map's red leader lands. The pennant points away from the conduit: mirror it (Ash x-scale −40) when the conduit is to its right. Kevin, 2026-11-25.
- **Mirroring:** civil3d_entity copy with mirrorX now gives an AutoCAD-MIRROR insert: x-scale −40, normal +Z, attributes readable (SimsUDS/Civil3D-mcp #13 and #14, verified on FI07808 2026-11-25). The FI keeps its real FI_NUMBER / CURRENT_RATING attributes, with no extra text.
- Rotation 0. Three of the twelve are mirrored (x = −40) so the pennant points the right way.
- Attributes FI_NUMBER and CURRENT_RATING are filled, plus STRUCTURE_NUMBER when the map shows it above the pennant.
- RFI is the same block with an "RFI" number. A thin leader polyline runs from the pennant to its pole.

### SGL_BLF (fuse on the line, n = 15)
- On the line (r0/r90). Terminals at ±5; the line is broken around it.
- **Labels:** a 3-line stack centred about 5–16 ft below: pole number, then BF#####, then amperage (25A/40A/50A).

### V5092568 / BF07957 / capbank 0221838 (Ash, Kevin 2026-11-25)
- The pothead beside V5092568 is a plain SGL_PH. The "80A" printed near it on the map belongs to BLF BF07957.
- The overhead line runs straight from the pothead's tail through the BLF's ±5 terminals: one segment, sloped if the heights differ. Never make up a foot of height with a 90° jog (Kevin). The map's drop into the bank's "A" is NOT a cable: Ash draws it as a SingleLine leader from the line to the mirrored bank.
- The BLF stack (pole#, BF#, amps) is left-aligned about 6.8 ft left of the fuse centre, at 5.7 / 10.6 / 15.1 ft below it.
- A structure box's V# moves clear of trunks and line text like any structure label; a vault's V# never does.

### SGL_CAPBANK (n = 9)
- When the map runs a cable straight into the bank's "A" (0221838), the insertion (the "A" tick end) sits on that cable end, with no leader. Mirror it when the bank lies right of A.
- Rotation 0, mirrored when the bank is on the left of the line. Dynamic Automatic/Fixed/Switched.
- Attributes Equipment #, Kvar, Structure # are filled. The equipment number shows above the box and the structure number below.
- **Leader:** a diagonal SingleLine polyline from the "A" tick end to the conductor.

### SGL_RSR_RAR (n = 1)
- On the line; terminals at (14, −4) and (20, −4). The RSR circle and pole number sit above the block, and the RSR value sits below it.
- A tie arrow leaves its side when it is a circuit tie.

### SGL_PO_NA_SW / SGL_RMT_SW (RCS)
- The RCS circle has "N" and "LD" boxes (attributes Load_Drop_Value, OPERATING_mode, RCS_Number) and is placed beside the switch.
- SGL_RMT_SW attributes STRUCTURE_NUMBER, RCS_ATTRIB and POS_ATTRIB show as a red boxed note ("V5093275 / RCS 1244 / POS 5") above the switch.

### PMEs (SGL_PMH_PME_xx)
- **PME4619 (Ash, Kevin 2026-11-25):**
  - Terminal 3 (PME_06 top-left, local (0,0)) rises 7 ft, turns left, and runs to P5380189's riser 36.4 ft left of the PME.
  - An SGL_TRAN_FUSED r0 sits right at that turn, pointing right: the map's small fuse at the corner.
  - The P5487433 / PME4619 pair sits between the riser and the PME, under the cable, clear of the block's "3".
  - P5380189 / LF stack beside their transformer.
  - Locked labels (a PME's P#, labels pinned to a moved transformer) are skipped by the overlap pass, so a stacked pair isn't split.
- **Placement:** put the block so its own terminals land on the map's terminals. Cables end exactly on them.
  - Measured terminals: PME_05 (0,0)/(0,−16.31), dyn Angle 1.5708. PME_01 (0,0)/(12,0). PME_06 (0,0)/(0,−12)/(8,−12). PME_09 (0,0)/(8,−12).
  - Inserting at the symbol's centre leaves the cables short. That was Kevin's P5435981 complaint, 2026-11-25.
- **Horizontal PME (PME_05 r270, Ash P5435981):** the insertion is the right-hand terminal, and terminal 1 is 16.31 ft to its left. P# and PMH# stack above the block, left-aligned on terminal 1: baselines +13.6 and +8.9 above the line, clear of the block's "1 2".
- **TRAN_DE:** rotation is a multiple of 90. The feeding cable is squared onto the feed terminal: (0,6) with elbows ON, (0,4) OFF.
- Rotation 0 (one each at 180, 270, 300). Terminals at (0, 0) and (0, −12/−16), plus (8, −12) for 3-way types.
- **Labels:** P# above PME#, a stacked pair, placed left of the box: about (−12…−18, +4…+10).
- **Type** follows the way layout on the map: PME-1 (2 ways, elbows R/L), PME-4, PME-5 (2 ways), PME-6, PME-9 (3 ways).

### 1-phase A/B transformers (TRAN_PM_1PH_DEDF_NFUSED, 1PH_2SW_NF_LPM, TRAN_PM_SW_FUSED[2])
- A and B terminals at (−5.72, 0.02) / (+6.28, 0.02) for DEDF (exact, the same on every Ash instance), or (−4, 0) / (4, 0) for SW_FUSED.
- The map draws this symbol wider than the block, so the PDF cable ends stop about 12 ft out. Pull each cable end onto its terminal, closest pair first (Kevin, P5091471, 2026-11-25).
- Vertical units are rotated 90 with the label beside them. P# is centred about +7…+9 above when horizontal.

### SGL_TRAN_PM (3-phase pad-mount), SGL_TRAN (PT / station transformer)
- The cable ends on the feed at local (0, 12): P5528419 r90 puts it 12 ft left of the insertion.
- TRAN_PM: r90/180, feed at (0, 12), label P# beside it.
- TRAN with "PT" text beside it = potential transformer (r270).

### Substation, meters, indicators
- **SGL_SUB_SOURCE:** at the line end. Cables end on its 5 ft circle edge, which is what Lawrence's feeder from GS0136 does. The name ("FULLERTON / SUB") is two lines above-right.
- **SGL_SUB_CUST_PP ("C" circle):** P# above.
- **SGL_PRI_MTR ("M" circle):** pole number below, plus notes "RCOC" / "FUSED".
- **SGL_SIG_CRI, SGL_FERRO:** no terminals, set beside the structure they belong to, no label.

## Where my drafting differs
- Gear switches should mostly be RAM; RAG only where the map shows "R A G".
- Vault labels: V# outside above the vault, switch# inside below the top. I had both from PDF positions.
- Phase labels (AØ/BØ/CØ) on 1-phase and 2-phase runs are missing.
- Cables inside and below vaults should drop straight from each way and hop wherever they cross.
- BLF needs its 3-line label stack below. The capacitor bank needs its diagonal leader.
- FI pennants should point at the PS circle or pole, mirrored when needed.

## Tile-review fixes (2026-11-25, v81-v84)
- PME0223 (P5745173) is SGL_PMH_PME_09 with dyn Angle = pi/2, Angle2 = 3pi/4 (exact radians, the block rejects 1.5708):
  cables on pos 3 (0,0) and pos 1 (8,-12); SGL_CAP on the open pos 4 (8,0) r270 and pos 2 (0,-12) r90.
- P5743057 transformer is elbows OFF. BS6094 gets an SGL_TRAN r0 at +10.1 on the BURD switch's right terminal.
- Tie-arrow stems (31.2 ft) count as crossings: other cables hop over them (OS2899 way 2).
- Fuses / taps (SGL_TRAN_FUSED, SGL_TRAN) left 0.3-8 ft off a cable snap onto it.
- Linetype can change along one PDF chain: split where the stroke coverage goes solid <-> broken
  (BF07957 -> 1198051E solid OH3PH, then dashed OH1). Pieces under 12 ft fold into their neighbour.
- Structure boxes (SGL_BOX <= 14 ft) sit ON their cable:
  - when the vault-floor pass lowers a leg, boxes on that leg move down with it (X5745268 / X5194396 on the
    350 JCN run to GS2818 way 4, Ash); their labels are matched against where the map drew the box;
  - a box two parallel runs pass through is centred between them and widened to gap + 3 ft (M5091494, X5640163);
  - otherwise a box with no cable through it slides onto the nearest cable within 20 ft.
- A cable end inside a structure box is finished: the sweep never pulls it onto equipment (a run ahead may still join).
- A cable whose last run drops onto a pothead tip, passing level with a box right over the tip, ends at the box
  centre; the stub pass joins the tip up into the box (X5177783, Ash).
- A short (< 30 ft) 2-point run from a pothead tip into a structure box is UG3PH even if the PDF stroke reads solid
  (V5092568 -> 1972873E, Ash). Do NOT widen this to every cable on a pothead tip: checked against Ash, 4 of 7 were OH.
- A failed apply still commits its creates and copies: re-query and erase everything before the next build.
- The UG loop north of Glenwood that feeds the 1-phase A/B pads is SGL-UG2PH (Ash: all 3 runs there; Ash uses UG2PH
  38 times and UG1PH only twice). Not UG1PH.
- Straight runs stay straight: drop interior vertices within 0.6 ft of their neighbours' chord (kept where another
  cable ends). Otherwise a short UG run is many tiny segments, the pattern restarts at each one and shows no dots
  (P5438567 -> X5177781). Worst drift measured 1.04 ft.
- X/V/M labels the map sets beside their box go beside it on that side (M5091494, X5177783, X5640163); others above.
  When a box is widened, a label beside it moves out by half the extra width.
- P5319217's drop is UG3PH as a 3-vertex polyline, the same as Ash; the dots on the drop are the linetype pattern.
- No small jog lines (Kevin, P5711986). When the sweep pulls a short run onto a terminal that is under 2.5 ft off the
  run's line and the far end is already attached, slide a block instead: first the block at the pulled end, else the
  block at the far end, whichever has no other wired terminal (transformers, potheads, BURD switches). Blocks sitting
  on its other terminals ride along (BS6094's SGL_TRAN). Only if neither can move does it fall back to a square jog.

## Road pass 2 (2026-11-25, v88-v89)
- Replace whole STREETS, never single pieces: chain the PDF street pieces into streets (2-way nodes, < 35 deg turn);
  a street a cable follows (parallel < 15 deg, within 15 ft) for >= 40 ft and >= 35% of its length becomes its own
  shape moved to sit 7 ft off the cable (median gap). A parallel street within 25 ft of a replaced one (> 50% of its
  length) is the other edge line and is dropped. The old per-segment rule left E Chapman, N Berkeley, N Lemon and
  Balcom as fragments.
- The PDF strokes every street twice: dedupe pieces before chaining (otherwise every node is a 4-way and chains run
  out and back, leaving diagonals such as M5122232 on S Lemon).
- Pieces overlapping Royer's sheet are tested in 5 ft lengths, so a partly covered piece keeps its uncovered part.
- A leftover street end within 12 ft of a road snaps onto it (T junctions such as E Glenwood -> N Berkeley).
- Tools: singleline_tools/road_check.py (PDF street coverage: drawn / replaced / missing, plus drawn roads with no PDF
  street) and road_overlay.py (PDF streets gray, roads red, cables blue, names) for a whole sheet or a window.
- Royer (page 1) left as it was: its S Lemon road sits 7 ft west of the cable, as in Ash, even though the PDF street
  is east. Its E Orangethorpe road (south of the cable, PDF street north) was not found in Ash to confirm.

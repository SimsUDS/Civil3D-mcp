---
name: power-stationing
description: "Place or check DYN STATION / DYN STATION (FLIPPED) blocks on UDS overhead (OH) and underground (UG) power jobs in Civil 3D: compute each pole, streetlight, handhole, pull box, ped, vault, pad or manhole station (##+##) off the right centerline, fill LINE_2-4 (pole ID or EX. SL / EX. HH / EX. POLE, ID TAG NFIF, FIF) from the survey points, pick the block, rotation and leader, and place them through the civil3d_entity MCP tool. Use it whenever Kevin says stationing, stations, station blocks, DYN STATION, XX+XX, 'station these poles', 'station the handholes', 'fill in the stations', 'check the stationing', or names a TD number under C:\\civ3dmcp\\jobs on an OH or UG job, even if he doesn't say skill."
---

# Power stationing, OH and UG (DYN STATION blocks, Civil 3D)

Each electric feature on an overhead (OH) or underground (UG) power job gets a station label. That covers poles and streetlights, plus the underground pieces: handholes, pull boxes, vaults, peds, pads and manholes. The label is a `DYN STATION` or `DYN STATION (FLIPPED)` block inserted exactly on the feature, with a leader running away from its centerline (CL) to text that sits behind the PL/RW line:

```
LINE_1  20+09          station along the CL, nearest foot
LINE_2  EX. SL         pole ID (1044317E), or EX. SL / EX. HH / EX. POLE / EX. PED ...
LINE_3  ID TAG NFIF    no ID tag found in field (survey "NT")
LINE_4  FIF            found in field (not on the grid maps)
```

The work is done from drawing data, not by eye: a script reads the CL linework, PL/RW lines, sheet outlines, survey points, blocks and text that you save from the drawing, and writes one `civil3d_entity` apply job plus a review list. Screenshots are only for showing Kevin a spot.

Kevin's standing preferences:
- **Don't burst** station blocks; Kevin bursts finished blocks himself. Use the `burst` action only if a task truly can't be done otherwise, and ask first.
- **Flag, don't guess.** Anything the rules don't settle goes on the review list for Kevin (see "Open questions").
- Time the job: note `date` before the first drawing read and after the final read-back, and report both.

## Workflow

### 1. Find the job and check the drawing

Jobs live under `C:\civ3dmcp\jobs\` (OH jobs in `OH Power\<TD number>\`; UG jobs in their own folder there; look for the TD number). Call `civil3d_drawing info` to confirm the right drawing is active. Make a data folder for this run, e.g. `<TD folder>\stationing\`. Every saved query below goes there under the exact file name shown, because the script looks for those names.

### 2. Save the drawing data (read-only queries)

Use `civil3d_entity query` with `outFile` (absolute path) so big results land in a file instead of the conversation, and `includeGeometry: true` on all of them:

| File | Query |
| --- | --- |
| `cl.json` | `layers: ["CL"]` (lines, arcs, station MTEXT, AeccTickLine ticks), limit 5000 |
| `plrw.json` | `layers: ["PL", "RW"]`, `types: ["LINE", "LWPOLYLINE", "ARC"]` |
| `noplot.json` | `layers: ["NO-PLOT"]` (sheet outlines and sheet numbers) |
| `inserts.json` | `types: ["INSERT"]`, limit 5000 (features and any existing station blocks) |
| `text.json` | `types: ["TEXT", "MTEXT", "DIMENSION"]`, limit 5000 |
| `build.json` | `layers: ["BUILD"]`, `types: ["LWPOLYLINE"]` |
| `hatch.json` | `types: ["HATCH"]`, limit 5000 (used by the re-solve, step 5b) |

Survey points: `civil3d_point export` with `format: "pnezd"` (it asks for approval). The result is too big to show and gets saved to a tool-results file; copy that file to `points.txt` in the data folder as is. The script reads the raw tool output, or plain `n,x,y,z,desc` lines.

If a layer name differs on a job (e.g. buildings on `BLDG`), query that layer into the same file name.

### 3. Run the script

The script is `scripts/stationing.py` in this skill. The same file is in the SimsUDS fork at `C:\civ3dmcp\Civil3D-mcp\tools\stationing\stationing.py`. It needs only Python 3 and takes about 1.5 minutes for 370 features.

```
python stationing.py "<data folder>" --mode missing
```

| Mode | Use when |
| --- | --- |
| `missing` | Default. Adds a block only on features that have none yet. |
| `fill` | Existing blocks read `XX+XX` or blank: writes LINE_1 only (an edit job). |
| `all` | Every station was erased and the whole job is being restationed. |

Add `--compare <saved query of the original station blocks>` to score a rerun against earlier work. It prints the number of matching stations and full text, and adds an `original` column to the report.

Outputs: `stationing_<mode>.json` (the apply job) and `stationing_<mode>_report.csv` (one row per feature: text, raw station, offset, sheet, block, rotation, SEG-1/2/3, flags).

### 4. Review before placing

Read the report and summarize it for Kevin: counts, and the flagged rows grouped by reason. Don't place anything he hasn't seen when the run would change existing blocks (`fill`, or `all` on a drawing that still has stations).

### 5. Place

`civil3d_request_approval` for `civil3d_entity apply` with `jobFile` set to the job file, then run `apply` with the token. Approval is bound to the file's hash, so don't edit the file between the two calls. One job places everything.

### 5b. Re-solve the leaders together

The first pass places callouts one at a time, so later ones can only dodge earlier ones. After placing, query the station blocks into `placed.json` (step 6 query) and run the joint re-solve. It adjusts the leaders on the placed blocks with every callout free to move, and ignores NO-PLOT text:

```
python repair.py "<data folder>" "<data folder>\placed.json" --bends
```

`--bends` adds bent leaders: a sideways step with the text kept square, from the measured shapes in `data/`. It only works where FLIP (RO)'s value set was set to None in both DYN STATION definitions. Check first: create a test block with FLIP (RO) = 1.0472 in empty space and read it back. If it comes back 1.5708, the drawing still has the stock definition. Then run without `--bends` and tell Kevin, since it's his call to edit the definition. See `references/block-behavior.md`.

What the re-solve avoids, and how:
- **Hatches.** Kevin's rule: keep text off hatches, but accept it when there's no room. They're weighted like other text. Building hatches use the exact BUILD outline. Other hatches and pasted `A$C...` blocks (e.g. a hatched walk area on layer WALK) use their bounding box. Hatch strips over 150 ft are skipped, because their box would block whole frontages.
- **Hand edits are never undone.** Any callout whose leader isn't one of this tool's shapes (non-integer lengths, an unmeasured bend) came from a drafter's grip drag. It's locked as is, and its real outline counts as an obstacle for the rest. The report marks it "hand edit, left as is".

Apply `stationing_repair.json` (an edit job, same approval flow), then read back again. `stationing_repair_report.csv` lists what still overlaps, worst first. Report the leftovers to Kevin as overlapping text issues for cleanup; don't sink time into perfect spacing.

On TD2573793:
- Straight only: it moved 153 of 366 callouts and cut the conflict score about 9%.
- With bends: 142 more callouts bent, the score fell 71% (5,108 to 1,469), and 277 of 366 came out fully clear. Station-on-station text overlaps dropped from 54 to 10.

What's left (about 90 callouts, mostly touching a building, APN text or dimension text) goes to Kevin's cleanup. Don't burst; he does that after cleanup.

### 6. Read back and report

Query `layers: ["ELECTRIC-TEXT"], types: ["INSERT"]` into a file and check:
- the count of station blocks
- no attribute reads `--OTHER--`
- no SEG-2 above 20

Then report the start and end times, the counts, and the flagged list. Point Kevin at the CSV. Offer a `capture_view` of any spot he asks about.

## Rules the script follows

These came from Kevin's corrections on TD2573793. Explain them when a result looks odd.

**Which features.** Blocks on layer `ELECTRIC` named DYN-POLE, DYN-SL, UTIL METER_BOX (streetlight pull boxes, survey "SL PB"), DYN-HANDHOLE ("E PB"), DYN-PED, DYN-PULLBOX, DYN-VAULT, DYN-PAD, DYN-MANHOLE, MH. The station block goes exactly on the feature's insertion point.

**Station.** Drop a perpendicular from the feature to the CL. Measure along the CL from the station labels, and round to the nearest foot, with .5 rounding up (9.48 past 20+00 is 20+09). CLs are usually exploded: LINE/ARC on layer `CL`, `##+00` MTEXT labels and AeccTickLine ticks every 50 ft. The script chains tangent-continuous pieces and fits each chain to its labels. Don't use Civil 3D alignments for this: their stationing often doesn't match the labels.

**Which CL**, in this order:
1. **Same sheet.** The CL has to be visible on the feature's sheet: "we can't have the stationing pointing to a CL we can't see." Sheets are the closed NO-PLOT polylines, each with its sheet number as TEXT inside. Kevin also spots sheet breaks by the mirrored dimension clusters on both sides of a CL.
2. **Access.** Use the street you'd reach the lot from. The perpendicular that crosses the fewest PL lines wins. A back-lot pole 111 ft from Lemon was stationed off E Truslow, 128 ft away, because the lot has no access from Lemon.
3. **Nearest.** This includes alley mouths: a pole 4 ft off the alley CL is stationed on the alley, not on the cross street 22 ft away. Kevin corrected 2281394E and 2286251E this way.

**Block and rotation.** The two straight pieces of the leader, the first line out from the feature and the shelf the text sits on, must be perpendicular to the CL. Only the middle piece may bend. Rotation is the direction pointing away from the CL, from the CL to the feature. Use `DYN STATION` when that's roughly east or north (315° to 135°), and `DYN STATION (FLIPPED)` when it's west or south. This keeps the text reading upright. When the feature sits past the end of its CL, measure the station at the end of the CL but keep the callout square to the CL's direction, not aimed at the end point. Kevin, 2026-11-20, SL 47699 at 129+84 on TD2573793: 269.53°, not 278.30°. The script does this with `away_angle`.

**Text.** IDs come only from survey descriptions:

| Survey | LINE_2 / 3 / 4 |
| --- | --- |
| `PP 1044317E`, `PP COMM 667607H`, `PP 2286247E 6.0 S.` (offset shot) | the ID |
| `PP NT`, `PP COMM NT` | EX. POLE / ID TAG NFIF / FIF |
| `SL NT` | EX. SL / ID TAG NFIF / FIF |
| `SL PB ...` on a meter box | EX. HH / FIF |
| `E PB` handhole | EX. HH |
| `E EM` ped | EX. PED |
| `E MH` | EX. MANHOLE / FIF |
| `E XFMR P5319217` pad | P5319217 |

No survey point under an underground item (handhole, pull box, vault) means LINE_1 reads `NFIF` in place of a station. Kevin confirmed those NFIF placements are correct and is still researching the rule (his guess is that they're underground items).

**FIF and NFIF come from the grid maps** (Kevin, 2026-11-20). The grid is the SCE map PDF in the job folder, e.g. `POWER-OH.pdf` for overhead. Only what's inside its **blue highlight** (polygon annotations) is drawn on the job; red squares on the sheets are extra markup, so ignore them.
- Surveyed and on the grid: no FIF.
- Surveyed but not on the grid: **FIF** (add a FIF line under the ID).
- On the grid but with no survey shot: **NFIF**, written as `station / grid ID / NFIF`.
- Survey ID and grid ID differ for the same pole: **use the grid ID**. These are usually survey typos (2286144E vs 2286244E, 47830001E vs 4783001E).
- A survey ID taken from records (`PP 447033E PER FIM`) where GeoView shows a different ID at that pole reads `station / survey ID / PER GEOVIEW: / geoview ID`, e.g. `28+06 / 447033E / PER GEOVIEW: / 1592140E` (QC lead, 2026-11-20). It is `PER GEOVIEW:`, never `GEOVIEW SHOWS:`, which a drafter wrote in error. Don't drop the survey ID in favour of the GeoView one. PER GEOVIEW is never used on FID poles, and plain survey typos still just get the grid/GeoView ID.
- NT poles (`PP NT`) with a clear grid or GeoView ID at the pole: `station / ID` (Kevin, 2026-11-20). FID comm poles read `station / FID339008640`, with no FIF. FID text over a building hatch is fine when there's no room.
- NT comm poles that are on neither map keep `EX. POLE / ID TAG NFIF / FIF`.
- Grid pole with no pole block nearby, or a record-drawn pole with nothing on the grid: flag for Kevin.
- Underground items: use GeoView (below). A structure that GeoView labels gets its ID in place of EX. VAULT / EX. PB / EX. HH, with no size line and no FIF, e.g. `495+55 / V6001308` or `NFIF / X5640166`. Streetlight meter-box HHs aren't on GeoView, so they keep `EX. HH / FIF`.

**GeoView PDFs.** Drafters check FIF in SCE GeoView, which Claude can't open, so Kevin exports PDFs of the job area (e.g. `geoview1.pdf`, `geoview2.pdf`), covering both OH and UG. Ask for them on every job. They're 1:900 raster maps with no text layer, crisp at 192 dpi. ⊕ is a pole and an open circle a structure; labels often sit 20–120 ft from their symbol, and conduit-run labels read "X TO Y". Read them the same way as the grid maps: overlapping 480×360 pt tiles, one reader per half page, and an affine fit per page from exact pole-ID matches (TD2573793 had a 4–5 ft median and 14 ft worst). Match **by ID first** within about 130 ft, since labels sit off their poles, and pair only the leftovers by location.

How to read the grid: the scans have no text layer and there's no OCR. Render each detail sheet's blue area at 300 dpi with everything outside the blue greyed out, cut it into overlapping tiles with pixel rulers, and have the IDs read by eye (one reader per sheet in parallel works well). Then merge duplicate reads, but only when it's the same ID; different labels can sit side by side. Fit each sheet to the drawing from the exact ID matches with an affine transform: on TD2573793 the median error was 3–20 ft, since labels sit off their poles. Pair the rest by location, and crop the sheet at every leftover spot to check by eye before changing anything. On TD2573793 this found 109 poles on the grid, 7 NFIF, 5 FIF, and 10 survey typos. The drafter's original FIF marks (667806H, 667607H, 2281394E) were confirmed.

**Leader and text placement.** The leader stays straight, with SEG-2 (ANG) and the rotation grip at 0. The script searches SEG-1 (13/8/4) and SEG-2 (3 to 20) so that:
- every corner of every text line is on the far side of a PL/RW line from the CL (station text never sits between the CL and the RW)
- the text stays on the feature's sheet
- the text doesn't touch other text, dimension text, symbol blocks, buildings, or the text and leaders already placed

When nothing clears, it takes the least-bad option and flags it.

The first pass uses straight leaders only. Bends come in at step 5b, where every callout can move at once.

## Open questions (flag these, don't decide them)

- Records-only IDs: poles with no survey point.
- The NFIF underground rule.
- Intersections where the feature sits in the corner area between two streets.
- Callouts that still touch something after the bent re-solve. They're Kevin's cleanup, done on the live blocks before he bursts.
- Drawings whose DYN STATION definitions still have the stock FLIP (RO) value set (90/270): bends need Kevin's definition edit first.

## When things look wrong

Read `references/block-behavior.md` when:
- text reads upside down
- `--OTHER--` shows up
- a dynamic property is refused
- an edit or create on a station block errors
- you want to bend a leader

It covers SEG-2 > 20 flipping the text, the LINE_3 default, the FLIP (RO) limit, the bend and tilt behaviour, the burst text layout, and the plugin calls that work.

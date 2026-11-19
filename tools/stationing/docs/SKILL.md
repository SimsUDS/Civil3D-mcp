---
name: oh-stationing
description: "Place or check DYN STATION / DYN STATION (FLIPPED) blocks on UDS overhead power (OH Power) jobs in Civil 3D: compute each pole, streetlight, handhole, pull box, ped, vault, pad or manhole station (##+##) off the right centerline, fill LINE_2-4 (pole ID or EX. SL / EX. HH / EX. POLE, ID TAG NFIF, FIF) from the survey points, pick the block, rotation and leader, and place them through the civil3d_entity MCP tool. Use it whenever Kevin says stationing, stations, station blocks, DYN STATION, XX+XX, 'station these poles', 'fill in the stations', 'check the stationing', or names a TD number under C:\\civ3dmcp\\jobs\\OH Power, even if he doesn't say skill."
---

# OH Power stationing (DYN STATION blocks, Civil 3D)

Each electric feature on an OH Power job gets a station label: a `DYN STATION` or `DYN STATION (FLIPPED)` block inserted exactly on the feature, with a leader running away from its centerline (CL) to text that sits behind the PL/RW line:

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

Jobs live under `C:\civ3dmcp\jobs\OH Power\<TD number>\`. Call `civil3d_drawing info` to confirm the right drawing is active. Make a data folder for this run, e.g. `<TD folder>\stationing\`. Every saved query below goes there under the exact file name shown, because the script looks for those names.

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

**Block and rotation.** Rotation is the direction pointing away from the CL, from the CL to the feature. Use `DYN STATION` when that's roughly east or north (315° to 135°), and `DYN STATION (FLIPPED)` when it's west or south. This keeps the text reading upright.

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

No survey point under an underground item (handhole, pull box, vault) means LINE_1 reads `NFIF` in place of a station. Kevin confirmed those NFIF placements are correct and is still researching the rule (his guess is that they're underground items). IDs that exist only on Kevin's grid maps aren't in the drawing, so those poles come out EX. POLE and are flagged.

**Leader and text placement.** The leader stays straight, with SEG-2 (ANG) and the rotation grip at 0. The script searches SEG-1 (13/8/4) and SEG-2 (3 to 20) so that:
- every corner of every text line is on the far side of a PL/RW line from the CL (station text never sits between the CL and the RW)
- the text stays on the feature's sheet
- the text doesn't touch other text, dimension text, symbol blocks, buildings, or the text and leaders already placed

When nothing clears, it takes the least-bad option and flags it.

Why straight only: a bent leader turns the text, and FLIP (RO), the setting that straightens it, can only be set by dragging grips. See `references/block-behavior.md`.

## Open questions (flag these, don't decide them)

- Records-only IDs: poles with no survey point, and vault or pull box IDs and sizes from the grid maps.
- The NFIF underground rule.
- Intersections where the feature sits in the corner area between two streets.
- Placements that only clear with a bent leader. Kevin either drags those himself, or they get bent after he bursts.

## When things look wrong

Read `references/block-behavior.md` when:
- text reads upside down
- `--OTHER--` shows up
- a dynamic property is refused
- an edit or create on a station block errors
- you want to bend a leader

It covers SEG-2 > 20 flipping the text, the LINE_3 default, the FLIP (RO) limit, the bend and tilt behaviour, the burst text layout, and the plugin calls that work.

# DYN STATION block behaviour (measured on TD2573793, 2026-11-19)

All values are in drawing feet at insert scale 1.3333. "Block frame" means a block at rotation 0, with the leader running +X.

## Leader settings

| Setting | Effect |
| --- | --- |
| SEG-1 | First leader piece. The line starts about 6.0 ft from the insertion point, leaving a gap around the feature symbol. |
| SEG-2 | Second piece. **Above about 21 ft (flips between 20 and 22) the text jumps to the other side of the shelf, upside down**, on both blocks. Keep it at 20 or less. |
| SEG-2 (ANG) | Bends piece 2. It also tilts piece 1 and the shelf by about -0.22 x the bend (15° → 3.4°, 30° → 6.6°, 45° → 9.7°, 60° → 12.4°). A rotation grip of the opposite tilt squares the leader again, but **the text does not follow**: it turned about 38° in the trial. |
| SEG-3 | The shelf under the text. Drafters use 18 for SL/HH and 20-22 for poles. The text can run longer than the shelf: "ID TAG NFIF" is 24.5 ft. |
| FLIP (RO) | Text turn. The plugin only accepts 1.5708 (90°, normal) or 4.7124 (270°, upside down on the other side). The in-between values on drafted blocks come from grip drags only, so bent leaders with straight text can't be made through the plugin. |
| ROTATE PERP CL / Angle1 | Rotation grip on the whole leader. Radians, counterclockwise. |
| FLIP (MIR) / FLIP (MI) | Mirror; 1 slides the text back so it ends at the shelf end. |
| SEG-1 large | SEG-1 more than about SEG-1 + SEG-2 of the default folds the leader back on itself. Stay at 13 or less. |

DYN STATION and DYN STATION (FLIPPED) differ only in which side of the shelf the text hangs on. FLIPPED at rotation 0 reads upside down, and reads upright at its usual 180-270°.

On drafted blocks, about 260 of 370 have SEG-2, the bend, FLIP (RO) and the rotation all changed together. That's the signature of one grip drag on the text end.

## Text layout (from a burst, block frame, DYN STATION)

- Shelf from 6 + SEG-1 + SEG-2 to that + SEG-3.
- LINE_1 baseline 0.87 ft above the shelf, starting 1.14 ft past the shelf start.
- LINE_2 onward below the shelf, 5.03 ft apart (baselines -4.16, -9.19, -14.21, ...).
- STANDARD style, 3.2 high, left-justified, layer ELECTRIC-TEXT.
- About 2.2-2.6 ft per character. The script uses 2.6. After placing, check the real extents if a spot is tight: Kevin caught a 1 ft overlap with a building that a guessed box missed.

## Attributes

- LINE_1 ... LINE_9. **Write all nine on insert.** A line you don't write keeps the definition default, and LINE_3's default is `--OTHER--`. This showed on 140 two-line blocks until they were blanked.

## Plugin calls that work

- `create` an insert with `blockName`, `rotationDeg`, `scale`, `attributes`, `dynamicProperties`. Block definitions are already in the OH and UG power drawings.
- `apply` with a `jobFile` for big batches: creates, then copies, edits, hatches, erase. Approval is bound to the file hash.
- `edit` with `attributes` / `dynamicProperties` / `rotationDeg` on existing blocks.
- TEXT can't be moved with `edit`. Use a `copy` operation with `mode: "move"`.
- `burst` (SimsUDS/Civil3D-mcp#11) turns a block into its leader plus TEXT, matching Express Tools BURST. Kevin does the bursting, so don't use it unasked.
- `civil3d_point export` needs approval. Its result is saved to a tool-results file because it's large.

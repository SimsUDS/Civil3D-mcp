# Office survey helpers

Python helpers for the **office-survey** skill. They turn a point export into
one `civil3d_entity` **apply** job file, so a whole layer, or a whole job, is
drawn in a single approval. Plain Python 3, no packages.

## Flow

1. Export the points: `civil3d_point` action `export`, format pnezd. You can
   also use the saved tool-result file from that call.
2. Export the existing linework you want to snap to or score against:
   `civil3d_entity` action `query`, with `outFile` (for example `C:\civ3dmcp\field_all.json`).
3. Build a job file in Python:

```python
import ossurvey as o
pts  = o.load_points("points.txt")
curb = o.Lines.from_query("field_all.json", "CURB")
job  = o.Job(block_source=r"C:\civ3dmcp\blocks\TD2563411 Survey.dwg")
flags = []
job.polyline(o.string_vertices(pts, [10401, ("poc", 10402), 10403], flags), "CURB")
hyd = pts[10182]
job.insert("HYDRANT", hyd.xy, "WATER", rotation_deg=curb.facing_deg(hyd.xy))
job.flag(pts[12230].xy, "12230 string unclear")
job.write(r"C:\civ3dmcp\jobs\TD2563411_draft.json")
```

4. Run `civil3d_entity` action `apply` with `jobFile` set to that path. You
   approve the job once; the approval is bound to the file's hash. The job
   runs in stages: `creates` first, then copies, edits, hatches and erase.
   The handle map is written next to the job file as `<name>.result.json`.
5. Optional: `o.score(my_polylines, "survey_all.json", "CURB")` checks your
   lines against a drafter's finished drawing.

## Contents

| Function | Purpose |
|---|---|
| `load_points` | Reads a pnezd export into `{number: Pt}`; `Pt.code` and `Pt.words` split the description |
| `distances`, `offsets`, `lo_partner`, `offset_point` | LO rule: true point = shot + d along the line from the LO through the shot |
| `string_vertices` | Polyline vertices; `("poc", n)` makes a 3-point arc (bulge). Arcs with R > 1000 are drawn as lines and flagged |
| `offset_polyline` | Parallel copy, e.g. wall thickness or mow strip |
| `Lines` | Grid index of a layer: `nearest`, `direction_deg` (curb-parallel rotation), `facing_deg` (hydrants face the street) |
| `Job` | `polyline`, `insert`, `circle`, `arc`, `text`, `flag` (DISC-OTHER circle + note), `write` |
| `score` | Length the drafter drew that you missed, and length you drew that the drafter didn't |

## Block source

`blockSource` must be a .dwg inside the plugin's allowed roots. Set
`CIVIL3D_IMPORT_ROOTS` (or `CIVIL3D_FILE_ROOTS`) to include the folder that
holds it, for example a symbols drawing or a finished job's Survey.dwg. The
plugin only imports blocks that are missing from the current drawing. It
never overwrites existing block definitions.

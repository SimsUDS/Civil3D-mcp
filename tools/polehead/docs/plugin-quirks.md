# civil3d_entity behavior and quirks

Read when something misbehaves, before a hand-built job with moves, mirrors or dims, or after a plugin rebuild.

- In an apply job, `mode: move` operations run AFTER all copies, whatever their order. A window move over an area where the same job places copies also moves those copies: move by handles, or run the move as its own job first.
- Query windows select by crossing; filter by extents in python. Copy and move windows select only what is fully inside (crossing false by default).
- `mirrorX` truly mirrors block geometry (an S becomes a backwards S) but query reports the original scale sign. Re-mirror about its own center (dx 0, dy 0, mirrorX = center x) to flip back. No vertical mirror or rotate on copy: edit vertices instead.
- An edit to a missing handle is silently skipped and still counted; query to confirm edits on existing template entities.
- Copied dims keep their text override. Editing dim points resets the text position: send textPosition in the same edit. AutoCAD pushes text outside short dims: always set textPosition. A dim's queried textPosition can differ from what was set: trust the sent values.
- Edit cannot reposition TEXT or INSERTs: copy mode `move` with dx/dy, or copy straight to the final spot.
- `dynamicProperties` applies before attributes; values match the allowed list case-insensitively.
- Dynamic block extents include hidden visibility geometry.
- Query ignores a `handles` list (returns the whole drawing, truncated): query a tight window instead.
- Query `position` for TEXT is the left baseline point, not the alignment point.
- Mirroring dims keeps text readable; mirroring text flips justification (MIRRTEXT 0).
- Stored positions go stale: re-measure before computing offsets.
- Query does not report hatch pattern, scale or angle.
- Hatches: closed LWPOLYLINEs and circles become boundary objects (associative); open ones fall back to vertex loops. Failures name the step (`Hatch 0: <step> failed: <ErrorStatus>`). `like` (copy a hatch's settings) needs the PR #21 build and has not passed a live run.
- Plugin log for unexplained errors: C:\Users\ksims\AppData\Local\Civil3DMcpPlugin\plugin.log (request folder access, stage it, tail it).
- After a plugin rebuild Kevin saves (QSAVE), closes Civil 3D and Claude Desktop, git pull, npm run build, dotnet build, reopens. TRUSTEDPATHS `C:\civ3dmcp\...`. The connection drops during the restart.
- Stale dim graphics: ask Kevin to REGEN.

- Circles and arcs: `edit` takes `center`, `radius`, and on arcs `startAngleDeg` / `endAngleDeg` (degrees CCW from +X; the arc runs CCW from start to end). Needs the plugin build with this change (PR #23); an older build rejects or ignores these fields, so redeploy the plugin before a job that uses them.

## Moves in a fix job

- TD2524712: a `mode: "move"` op in an apply job that also had copies did not move its TEXT, and a leader edit in the same job came out half applied. Run hand moves as their own `copy` call (`mode: "move"`) and re-check leaders with a query.

## Moves ignore mirrorX

- A copy op with `mode: "move"` and `mirrorX` moves the entity but does not mirror it (seen in TD2486645). To mirror an existing entity, copy it with `mirrorX` (no mode) and erase the original in the same job.

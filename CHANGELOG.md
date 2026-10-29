# Changelog

## Unreleased

- `civil3d_drawing` action `set_map` (plugin method `setOnlineMap`): turns the
  online map (Bing aerial, road, hybrid) on or off by running GEOMAP (falls
  back to GEOMAPMODE; GEOMAPMODE alone left the view dark) and reports
  the mode before and after. `capture_view` `map` / `mapAfter` use
  the same path, and its result lists `mapMode` and the parameter keys the
  plugin received.
- `civil3d_office_survey build`: arcs with R 1000-5000 ft stay arcs when the POC
  is more than 0.5 ft off the chord (drafters draw gentle curves as one arc);
  only flatter or bigger ones become lines.
- `civil3d_drawing` action `capture_view` (plugin method `captureView`): optionally
  zoom to a window in plan view, wait for online map tiles (GEOMAP, e.g. Bing
  aerial) to load, and save the drawing view as a PNG with its world extents
  and ft per pixel. `mode: "screen"` (default) copies the view's pixels from the
  screen so the online map is included; `"render"` uses CapturePreviewImage.
  `map` / `mapAfter` (aerial, road, hybrid, off) run GEOMAP before / after the
  capture (the drawing must be geolocated and the user signed in to Autodesk).
- `civil3d_drawing` action `geolocate` (plugin method `geolocateDrawing`, needs
  approval): sets the drawing's geographic location from its Civil 3D
  coordinate system so GEOMAP works; keeps an existing location unless
  `overwrite`.
- Plugin builds with WinForms/System.Drawing for the PNG capture (their global
  usings removed so Color, Point etc. stay unambiguous).
- `civil3d_entity` query with `includeGeometry`: polyline vertices carry `bulge`
  (tan(sweep/4), + = counterclockwise) when the segment starting there is an arc.
- `civil3d_entity` create (and `apply` job creates): inserts take `explode: true`
  (explode the block right after inserting it; pieces on layer 0 take the
  insert's layer, ByBlock color becomes ByLayer) and `clipLength` (trim the
  pieces at that distance from the insertion point along the insert's rotation).
  Used for GUY blocks: insert at the anchor, aim at the pole, clip at the pole
  center. Apply results list the pieces as `explodedPieces` (create index ->
  handles).
- `blockSource` can be a folder of one-block drawings (e.g. `C:\civ3dmcp\TOPO LW`):
  block NAME is taken from `NAME.dwg` there, inserted as a whole drawing like
  INSERT with a file. A .dwg blockSource also falls back to that when the
  block is the file itself. Missing blocks are all listed before anything is
  drawn.
- New tool `civil3d_office_survey` (office survey engine, no plugin changes):
  `points` returns parsed shots with LO offsets resolved and no-LO shots
  flagged; `build` turns a plan of point numbers (strings with `{poc}` arcs,
  block inserts rotated `curb` / `face-curb`, circles, arcs, text, DISC-OTHER
  flags) into a `civil3d_entity apply` job file without touching the drawing;
  `score` compares a job's polylines with a drafter's query export.
- `civil3d_entity` action `create` (plugin method `createEntities`): draws new
  entities in one transaction: block inserts (rotation, scale, dynamic
  properties, attributes), polylines with per-vertex bulge, circles, arcs,
  lines and text. Missing layers are created; missing block definitions are
  imported from `blockSource` (a .dwg inside the import roots, existing
  definitions are never overwritten).
- `apply` jobs take a `creates` stage (runs first) and `blockSource`, so a whole
  drafting job (hundreds of blocks and polylines) is one approval bound to the
  job file's SHA-256.
- Live redraw: `copyEntities`, `editEntities`, `createHatches` and
  `eraseEntities` repaint the drawing between pieces (throttled to about every
  100 ms) and show `MCP <action>: n/total` on the command line, instead of
  everything appearing at the end. Still one transaction per call, so undo and
  rollback on error are unchanged. Set `CIVIL3D_MCP_LIVE_REDRAW=0` to turn it off.
- `civil3d_entity` action `edit` (and `apply` job edits): circles and arcs take
  `center` and `radius`; arcs also take `startAngleDeg` / `endAngleDeg`.
- `tools/polehead`: riser details (`riser` spec), 4" risers by radius edit,
  U-GUARDs at any angle by arc edits.
- `civil3d_entity` action `apply`: runs a copy/edit/erase job from a JSON file
  (or an inline `job`). Edits and erases can reference the job's own copies as
  `"<copyId>:<sourceHandle>"`, so a whole batch runs in one call. The handle map
  is written to `<job>.result.json`.
- Approvals for parameters that name a `jobFile` now bind to the file's SHA-256
  (returned as `jobFileSha256`); editing the file after approval voids the token.
- Added `tools/polehead`, the pole head detail generator that turns a job spec
  into an `apply` job, plus a Station Builder reader.

## v1.2.1 — 2026-07-14

### Production readiness

- Added a self-contained Claude Desktop MCPB package, a byte-identical legacy
  DXT compatibility artifact, installer configuration, checksum generation, and
  official manifest validation through `npm run package:claude`.
- Added a compact 33-tool default MCP surface while keeping 216 manifest-backed
  canonical and alias routes available internally; set
  `CIVIL3D_ENABLE_TOOL_ALIASES=true` to expose the full 218-tool MCP surface.
- Added first-class MCP output schemas, structured content, annotations,
  resources, progress notifications, and report-resource retrieval.
- Added parameter-bound, drawing-bound approval receipts, bounded serialized
  host execution, disconnect cancellation, idempotency, and stable errors.
- Added bounded background jobs for publishing, imports, corridor rebuilds, and
  bulk QC, with terminal retention and cancellation telemetry.
- Added liveness, readiness, plugin, queue, and version endpoints on the local
  HTTP bridge at port 3000.
- Added rotating native plugin logs with file-health and last-error telemetry.
- Added CI, generated tool documentation, manifest/dispatcher parity, package
  inspection, startup smoke, and opt-in live Civil 3D host validation.
- Removed tracked Autodesk assemblies; Release builds resolve licensed Civil 3D
  2026 references through `Civil3DReferencesPath`.

### Live validation

- Validated plugin 1.2.1.0 against Civil 3D 2026 on port 8080.
- Validated the spawned stdio MCP client, HTTP registration and routing,
  approvals, concurrency, document switching, create/undo/delete, temporary
  TIN-volume rollback, job cancellation/completion, and response limits.

## v1.1.0 — 2026-03-17

### Summary

Adds 12 new tools across 3 categories (parcel editing, survey processing, data shortcut management) to bring the total MCP tool count to 162.

---

### MCP Server (TypeScript)

**New tools (+12):**

| Category | New Tools | Actions |
|---|---|---|
| Parcel Editing | 4 | create, edit, lot-line-adjust, report |
| Survey Processing | 4 | observation-list, network-adjust, figure-create, landxml-import |
| Data Shortcut Management | 4 | create, promote, reference, sync |

**New files:**
- `src/tools/civil3d_parcel_editing.ts` — parcel CRUD and lot-line adjustment
- `src/tools/civil3d_survey_processing.ts` — survey observation, network adjustment, LandXML import
- `src/tools/civil3d_data_shortcut_mgmt.ts` — data shortcut lifecycle management
- `tests/parcel_survey_shortcuts.test.ts` — 34 schema-level tests

**Deferred:** gravity pipe HGL solver and APS 3D viewer (high complexity, no operational demand).

---

## v1.0.0 — 2026-03-17

### Summary

First stable release of the Civil3D MCP Ecosystem: a 150-tool MCP server for Autodesk Civil 3D paired with an AI CoPilot WPF plugin and a full hydrology analysis engine.

---

### MCP Server (TypeScript)

**150 tools across 16 categories:**

| Category | Tools | Highlights |
|---|---|---|
| Alignment | 22 | Create, edit, stationing, offsets, superelevation, widening |
| Surface | 18 | TIN create/edit, breaklines, contours, volume analysis, sampling |
| Corridor | 12 | Create, rebuild, extract solids, edit frequency, targets |
| Profile | 14 | Surface profiles, layout profiles, PVI edit, design speeds |
| Pipe Networks | 10 | Pipes, structures, network analysis, interference |
| Grading | 8 | Feature lines, grading objects, volume balance |
| COGO / Points | 10 | Import/export, groups, inverse, traverse, intersection |
| Plan Production | 12 | Sheet sets, view frames, match lines, north arrows |
| QC | 18 | Design standard checks, clearance, slope, cross-fall |
| Quantity Takeoff | 10 | Cut/fill volumes, earthwork reports, material summary |
| Hydrology | 5 | Flow paths, low point, watershed delineation, catchment, rational method |
| Sample Lines | 4 | Group creation, section views, material table |
| Data Shortcuts | 4 | Create, reference, synchronize, export |
| Labels / Styles | 4 | Apply label sets, import/export styles |
| Utilities | 9 | Drawing context, layer management, export formats |

**Architecture:**
- MCP protocol over HTTP POST `/execute`
- Tool registry with per-tool Zod validation
- `civil3d_hydrology` tool handles 5 hydrological analysis actions

---

### AI CoPilot Plugin (C#)

**Command routing (all 150 categories):**
- `IsMcpDirectCommand()` — routes `civil3d_*` and `create_cogo_point` to MCP async handler
- `IsHydrologyCommand()` — routes hydrology commands to async MCP → CAD draw pipeline
- `CommandRouter.Execute()` — synchronous CAD transaction handler for 14 draw command types
- `HandleMcpDirectCommandAsync()` — async MCP caller with formatted JObject result display

**Hydrology integration:**
- `HydrologyDrawer.cs` — draws flow paths (cyan), watershed boundaries (yellow), outlet markers (red)
- `McpClient.cs` — typed async methods for all 5 hydrology tools with result model classes
- Sequential workflow support: `lastHydroOutlet` chains `FindLowPoint` → `DelineateWatershed`

**AI providers supported:** Gemini, OpenAI, Anthropic

---

### Integration Tests

- 13 test files, **372 tests**, all passing
- End-to-end workflow tests covering alignment → surface → corridor → profile pipeline
- Hydrology workflow tests covering flow path → low point → watershed → catchment → runoff

---

### Bug Fixes

- **JFS-15**: Fixed structural C# compile error — hydrology methods were accidentally placed outside the `McpClient` class body
- **JFS-15**: Made `ExecuteMcpToolAsync` public (was private) to enable direct MCP command routing

---

### Known Limitations

- Civil 3D API calls require an active drawing session — no headless mode
- Hydrology delineation uses grid sampling (not DEM-optimized); large surfaces may be slow
- C# plugin targets .NET Framework 4.8 (AutoCAD/Civil 3D requirement)

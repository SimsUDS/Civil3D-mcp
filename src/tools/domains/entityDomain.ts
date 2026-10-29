import { writeFileSync } from "node:fs";
import { isAbsolute } from "node:path";
import { z } from "zod";
import { withApplicationConnection } from "../../utils/ConnectionManager.js";
import type { DomainToolDefinition } from "../domainRuntime.js";
import { parseJob, readJobFile, runEntityJob, validateJob, writeJobResult } from "./entityJob.js";

const GenericResponseSchema = z.object({}).passthrough();

const Point2DSchema = z.object({ x: z.number(), y: z.number() });
const WindowSchema = z.object({
  minX: z.number(),
  minY: z.number(),
  maxX: z.number(),
  maxY: z.number(),
});
const HandleSchema = z.string().regex(/^[0-9A-Fa-f]+$/, "Handles are hexadecimal strings, e.g. \"2A3F\".");
const SpaceSchema = z.string().min(1).describe("\"model\" (default) or a layout name.");

const CopyOperationSchema = z.object({
  mode: z.enum(["copy", "move"]).optional().describe("copy (default) duplicates the selection; move relocates it."),
  handles: z.array(HandleSchema).optional().describe("Entities to copy or move."),
  window: WindowSchema.optional().describe("Also select entities inside this box (in addition to handles)."),
  crossing: z.boolean().optional().describe("Window selection: true includes anything touching the box; false (default) only fully inside."),
  layers: z.array(z.string()).optional().describe("Window selection: only these layers."),
  types: z.array(z.string()).optional().describe("Window selection: only these DXF types, e.g. INSERT, LINE, MTEXT, MULTILEADER."),
  dx: z.number().describe("X displacement."),
  dy: z.number().describe("Y displacement."),
  space: SpaceSchema.optional().describe("Space the source entities live in."),
  targetSpace: SpaceSchema.optional().describe("Copy only: place copies in this space instead of the source space."),
  mirrorX: z.number().optional().describe("After the offset, mirror across the vertical line x = mirrorX. Text stays readable (justification flips, like MIRRTEXT 0)."),
});

const EditSchema = z.object({
  handle: HandleSchema,
  text: z.string().optional().describe("New text for TEXT, MTEXT (raw contents), MULTILEADER, ATTRIB, or dimension override."),
  attributes: z.record(z.string(), z.string()).optional().describe("Block attribute values by tag."),
  rotationDeg: z.number().optional().describe("Absolute rotation in degrees counterclockwise about the insertion point (block references, text, MText)."),
  dynamicProperties: z.record(z.string(), z.union([z.string(), z.number()])).optional().describe("Dynamic block properties by name, e.g. {\"Custom\": \"ADDRESS LIST 8\"} for a visibility state or a number for a distance. Names and current values are reported by query; applied before attributes."),
  start: Point2DSchema.optional().describe("New start point (lines only)."),
  end: Point2DSchema.optional().describe("New end point (lines only)."),
  xLine1: Point2DSchema.optional().describe("Linear dimension: first extension line origin."),
  xLine2: Point2DSchema.optional().describe("Linear dimension: second extension line origin."),
  dimLine: Point2DSchema.optional().describe("Linear dimension: a point on the dimension line (sets its offset)."),
  textPosition: Point2DSchema.optional().describe("Dimension text location (middle of the text). Applied after dimension points."),
  vertices: z.array(Point2DSchema).min(2).optional().describe("Replace all vertices of a line, polyline or leader."),
  closed: z.boolean().optional().describe("LWPOLYLINE: close or open it (closed boundaries are required for hatching)."),
  center: Point2DSchema.optional().describe("CIRCLE or ARC: new center point."),
  radius: z.number().positive().optional().describe("CIRCLE or ARC: new radius."),
  startAngleDeg: z.number().optional().describe("ARC: start angle in degrees CCW from +X (the arc runs CCW from start to end)."),
  endAngleDeg: z.number().optional().describe("ARC: end angle in degrees CCW from +X."),
  colorIndex: z.number().int().min(0).max(256).optional().describe("ACI color: 0 = ByBlock, 256 = ByLayer."),
  linetype: z.string().optional().describe("Linetype name; must already be loaded in the drawing."),
  layer: z.string().optional(),
});

const HatchSchema = z.object({
  boundaries: z.array(HandleSchema).optional().describe("Boundary objects, like HATCH > Select objects: closed LWPOLYLINEs or circles (associative). Open polylines fall back to vertex loops closed with a straight segment."),
  associative: z.boolean().optional().describe("Default true: closed boundaries are used as objects and the hatch follows them. false always builds vertex loops."),
  loops: z.array(z.array(Point2DSchema).min(3)).optional().describe("Extra loops as vertex lists (straight segments, closed automatically)."),
  like: HandleSchema.optional().describe("Existing hatch to copy pattern, scale, angle, style, layer and color from."),
  pattern: z.string().optional().describe("Pattern name, e.g. ANSI31 (default: like's pattern, else ANSI31)."),
  scale: z.number().positive().optional().describe("Pattern scale (default: like's, else 1)."),
  angleDeg: z.number().optional().describe("Pattern angle in degrees (default: like's, else 0)."),
  layer: z.string().optional(),
  colorIndex: z.number().int().min(0).max(256).optional().describe("ACI color: 0 = ByBlock, 256 = ByLayer."),
  space: SpaceSchema.optional(),
});

const CreateSchema = z.object({
  type: z.enum(["insert", "block", "polyline", "circle", "arc", "line", "text"]).describe("insert (block reference), polyline, circle, arc, line or text."),
  id: z.string().optional().describe("Optional caller id echoed back with the new handle."),
  layer: z.string().optional().describe("Layer; created if missing."),
  colorIndex: z.number().int().min(0).max(256).optional().describe("ACI color: 0 = ByBlock, 256 = ByLayer."),
  linetype: z.string().optional().describe("Linetype name; must already be loaded in the drawing."),
  space: SpaceSchema.optional(),
  blockName: z.string().optional().describe("insert: block definition name (imported from blockSource when missing)."),
  position: Point2DSchema.optional().describe("insert: insertion point; text: text position."),
  rotationDeg: z.number().optional().describe("insert / text: rotation in degrees CCW."),
  scale: z.number().positive().optional().describe("insert: uniform scale (default 1)."),
  explode: z.boolean().optional().describe("insert: explode the block into its pieces right after inserting it (pieces on layer 0 go to the insert's layer). The result lists the piece handles."),
  clipLength: z.number().positive().optional().describe("insert with explode: trim the pieces at this distance from the insertion point along the insert's rotation (e.g. a GUY block inserted at the anchor and aimed at the pole, clipped at the pole center). Lines and straight polyline segments are cut; other pieces past it are dropped."),
  dynamicProperties: z.record(z.string(), z.union([z.string(), z.number()])).optional().describe("insert: dynamic block properties by name (visibility state, distance, angle in radians)."),
  attributes: z.record(z.string(), z.string()).optional().describe("insert: attribute values by tag."),
  points: z.array(z.object({ x: z.number(), y: z.number(), bulge: z.number().optional() })).min(2).optional()
    .describe("polyline: vertices; bulge = tan(sweep/4) of the segment that starts at the vertex, positive = CCW."),
  closed: z.boolean().optional().describe("polyline: closed."),
  center: Point2DSchema.optional().describe("circle / arc: center."),
  radius: z.number().positive().optional().describe("circle / arc: radius."),
  startAngleDeg: z.number().optional().describe("arc: start angle, degrees CCW from +X."),
  endAngleDeg: z.number().optional().describe("arc: end angle, degrees CCW from +X."),
  start: Point2DSchema.optional().describe("line: start."),
  end: Point2DSchema.optional().describe("line: end."),
  text: z.string().optional().describe("text: the string."),
  height: z.number().positive().optional().describe("text: height (default 1)."),
});

const QueryArgs = z.object({
  action: z.literal("query"),
  space: SpaceSchema.optional(),
  window: WindowSchema.optional(),
  crossing: z.boolean().optional(),
  layers: z.array(z.string()).optional(),
  types: z.array(z.string()).optional(),
  limit: z.number().int().min(1).max(5000).optional(),
  includeGeometry: z.boolean().optional(),
  outFile: z.string().min(1).optional(),
});
const CreateArgs = z.object({
  action: z.literal("create"),
  creates: z.array(CreateSchema).min(1),
  blockSource: z.string().min(1).optional(),
  space: SpaceSchema.optional(),
});
const CopyArgs = z.object({ action: z.literal("copy"), operations: z.array(CopyOperationSchema).min(1) });
const EditArgs = z.object({ action: z.literal("edit"), edits: z.array(EditSchema).min(1) });
const EraseArgs = z.object({ action: z.literal("erase"), handles: z.array(HandleSchema).min(1) });
const HatchArgs = z.object({ action: z.literal("hatch"), hatches: z.array(HatchSchema).min(1) });
const ApplyArgs = z.object({
  action: z.literal("apply"),
  jobFile: z.string().min(1).optional(),
  job: z.record(z.unknown()).optional(),
  includeHandleMap: z.boolean().optional(),
}).refine((args) => (args.jobFile === undefined) !== (args.job === undefined), {
  message: "apply needs exactly one of jobFile or job.",
});

const JobFileDescription =
  "apply: absolute path to a .json job file on this machine: {version:1, blockSource?: \"<.dwg with block definitions, or a folder of <block name>.dwg files>\", " +
  "creates:[{type: insert|polyline|circle|arc|line|text, layer, ...create fields}], copies:[{id, handles|window, dx, dy, mirrorX?, mode?, space?}], " +
  "edits:[{handle|ref:\"<copyId>:<sourceHandle>\", ...edit fields}], hatches:[{boundaries:[handle | {ref}], like?: handle | {ref}, pattern?, scale?, angleDeg?, layer?}], " +
  "erase:[handle | {ref}]}. Stages run creates, copies, edits, hatches, erase. Approval is bound to the file's SHA-256, " +
  "so edit the file and the token is void. The full old-to-new handle map is written beside it as <name>.result.json.";

const send = (method: string, payload: Record<string, unknown>) =>
  withApplicationConnection(async (appClient) => await appClient.sendCommand(method, payload));

export const ENTITY_DOMAIN_DEFINITION: DomainToolDefinition = {
  domain: "entity",
  actions: {
    query: {
      action: "query",
      inputSchema: QueryArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["query"],
      requiresActiveDrawing: true,
      safeForRetry: true,
      pluginMethods: ["queryEntities"],
      execute: async (args) => {
        const { action: _action, outFile, ...rest } = args as z.infer<typeof QueryArgs>;
        const result = await send("queryEntities", rest);
        if (!outFile) return result;
        // Write the full result on the drafting machine and reply with a summary only, so large queries
        // (pole head QC) reach scripts as a file instead of flooding the conversation.
        if (!isAbsolute(outFile) || !/\.json$/i.test(outFile)) {
          throw new Error("query outFile must be an absolute path ending in .json.");
        }
        writeFileSync(outFile, JSON.stringify(result, null, 2), "utf8");
        const r = (result ?? {}) as Record<string, unknown>;
        return { outFile, matched: r.matched, returned: r.returned, truncated: r.truncated, countsByType: r.countsByType };
      },
    },
    create: {
      action: "create",
      inputSchema: CreateArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["create"],
      requiresActiveDrawing: true,
      safeForRetry: false,
      pluginMethods: ["createEntities"],
      execute: async (args) => {
        const { action: _action, ...rest } = args as z.infer<typeof CreateArgs>;
        return await send("createEntities", rest);
      },
    },
    copy: {
      action: "copy",
      inputSchema: CopyArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["create", "edit"],
      requiresActiveDrawing: true,
      safeForRetry: false,
      pluginMethods: ["copyEntities"],
      execute: async (args) => await send("copyEntities", { operations: (args as z.infer<typeof CopyArgs>).operations }),
    },
    edit: {
      action: "edit",
      inputSchema: EditArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["edit"],
      requiresActiveDrawing: true,
      safeForRetry: false,
      pluginMethods: ["editEntities"],
      execute: async (args) => await send("editEntities", { edits: (args as z.infer<typeof EditArgs>).edits }),
    },
    erase: {
      action: "erase",
      inputSchema: EraseArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["delete"],
      requiresActiveDrawing: true,
      safeForRetry: false,
      pluginMethods: ["eraseEntities"],
      execute: async (args) => await send("eraseEntities", { handles: (args as z.infer<typeof EraseArgs>).handles }),
    },
    hatch: {
      action: "hatch",
      inputSchema: HatchArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["create"],
      requiresActiveDrawing: true,
      safeForRetry: false,
      pluginMethods: ["createHatches"],
      execute: async (args) => await send("createHatches", { hatches: (args as z.infer<typeof HatchArgs>).hatches }),
    },
    apply: {
      action: "apply",
      inputSchema: ApplyArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["create", "edit", "delete"],
      requiresActiveDrawing: true,
      safeForRetry: false,
      pluginMethods: ["createEntities", "copyEntities", "editEntities", "createHatches", "eraseEntities"],
      execute: async (args) => {
        const { jobFile, job, includeHandleMap } = args as z.infer<typeof ApplyArgs>;
        const file = jobFile ? readJobFile(jobFile) : undefined;
        const parsed = file ? parseJob(file.text) : validateJob(job);
        const result = await runEntityJob(parsed, send);
        const resultFile = file ? writeJobResult(file.path, result, file.sha256) : undefined;
        // Keep the reply small: per-copy counts and handle maps live in the result file.
        const { handles, copies, createdHandles, ...summary } = result;
        const response = {
          ...summary,
          copyOperations: Object.keys(copies).length,
          ...(file ? { jobFile: file.path, jobSha256: file.sha256, resultFile } : {}),
          ...(includeHandleMap || !file ? { copies, handles, createdHandles } : {}),
        };
        if (result.status === "failed") {
          // Earlier stages are committed; report what exists so it can be fixed or erased.
          const error = new Error(`Entity job failed at stage '${result.stage}': ${JSON.stringify(response)}`) as Error & { code: string };
          error.code = "CIVIL3D.CONFLICT";
          throw error;
        }
        return response;
      },
    },
  },
  exposures: [
    {
      toolName: "civil3d_entity",
      displayName: "Civil 3D Entities",
      description:
        "Reads, creates, copies, moves, edits and erases ordinary AutoCAD entities (blocks, lines, polylines, text, MText, multileaders, attributes) in model space or a layout. " +
        "query: list entities in a window with handles, block names, attribute values, text and geometry. " +
        "create: batch-draw new entities in one transaction: block inserts (rotation, scale, dynamic properties, attributes; missing definitions imported from blockSource: a .dwg, or a folder of one-block <name>.dwg files inserted like INSERT with a file), polylines with per-vertex bulge, circles, arcs, lines and text; missing layers are created. " +
        "copy: batch copy or move entities by handles and/or window with a dx/dy offset and optional mirror; returns old-to-new handle maps. " +
        "edit: batch change text, attribute values, vertices/endpoints, circle/arc center, radius and arc angles, dimension points, color, linetype or layer by handle. " +
        "erase: delete entities by handle. " +
        "hatch: create hatches like HATCH > Select objects (closed polylines/circles, associative) or from vertex loops, matching an existing hatch's pattern, scale and angle via 'like'. " +
        "apply: run a whole job (creates, copies, then edits, hatches and erases that may reference the new copies as \"<copyId>:<sourceHandle>\") from a JSON file in one call; " +
        "approval binds to the file hash, so the request stays tiny. Batch copy and edit work so one approval covers a whole detail.",
      inputShape: {
        action: z.enum(["query", "create", "copy", "edit", "erase", "hatch", "apply"]),
        space: SpaceSchema.optional(),
        window: WindowSchema.optional(),
        crossing: z.boolean().optional(),
        layers: z.array(z.string()).optional(),
        types: z.array(z.string()).optional(),
        limit: z.number().int().min(1).max(5000).optional(),
        includeGeometry: z.boolean().optional(),
        outFile: z.string().min(1).optional().describe("query: absolute path of a .json file on this machine to write the full result to; the reply is then only counts and the path."),
        creates: z.array(CreateSchema).optional().describe("create: entities to draw."),
        blockSource: z.string().min(1).optional().describe("create: absolute path of a .dwg holding the block definitions, or of a folder of one-block drawings named <block name>.dwg (e.g. C:\\civ3dmcp\\TOPO LW). Must be inside the configured import roots."),
        operations: z.array(CopyOperationSchema).optional(),
        edits: z.array(EditSchema).optional(),
        handles: z.array(HandleSchema).optional(),
        hatches: z.array(HatchSchema).optional().describe("hatch: hatches to create."),
        jobFile: z.string().min(1).optional().describe(JobFileDescription),
        job: z.record(z.unknown()).optional().describe("apply: inline job object (same format as jobFile) for small jobs."),
        includeHandleMap: z.boolean().optional().describe("apply: also return the full old-to-new handle map inline."),
      },
      supportedActions: ["query", "create", "copy", "edit", "erase", "hatch", "apply"],
      resolveAction: (rawArgs) => ({ action: String(rawArgs.action ?? ""), args: rawArgs }),
    },
  ],
};

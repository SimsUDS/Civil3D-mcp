import { readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { z } from "zod";
import { withApplicationConnection } from "../../utils/ConnectionManager.js";
import type { DomainToolDefinition } from "../domainRuntime.js";
import {
  buildJob,
  describePoints,
  referencedNumbers,
  score,
  segmentsFromQuery,
  segmentsFromVertices,
  toRanges,
  type Plan,
  type Segment,
  type SurveyPoint,
} from "./officeSurvey.js";

const GenericResponseSchema = z.object({}).passthrough();
const MAX_FILE_BYTES = 32 * 1024 * 1024;

const WindowSchema = z.object({ minX: z.number(), minY: z.number(), maxX: z.number(), maxY: z.number() });

const PointsArgs = z.object({
  action: z.literal("points"),
  includeNumbers: z.string().optional(),
  includeDescriptions: z.string().optional(),
  layers: z.array(z.string()).optional(),
  window: WindowSchema.optional(),
  outFile: z.string().min(1).optional(),
});

const BuildArgs = z.object({
  action: z.literal("build"),
  plan: z.record(z.unknown()).optional(),
  planFile: z.string().min(1).optional(),
  outFile: z.string().min(1),
}).refine((a) => (a.plan === undefined) !== (a.planFile === undefined), { message: "build needs exactly one of plan or planFile." });

const ScoreArgs = z.object({
  action: z.literal("score"),
  jobFile: z.string().min(1),
  referenceFile: z.string().min(1),
  layer: z.string().min(1),
  tolerance: z.number().positive().optional(),
});

const send = (method: string, payload: Record<string, unknown>) =>
  withApplicationConnection(async (appClient) => await appClient.sendCommand(method, payload));

function jsonPath(file: string, label: string): string {
  if (!path.isAbsolute(file) || path.extname(file).toLowerCase() !== ".json") {
    throw new Error(`${label} must be an absolute path ending in .json.`);
  }
  return path.resolve(file);
}

function readJson(file: string, label: string): unknown {
  const resolved = jsonPath(file, label);
  if (statSync(resolved).size > MAX_FILE_BYTES) throw new Error(`${label} is larger than ${MAX_FILE_BYTES} bytes.`);
  return JSON.parse(readFileSync(resolved, "utf8").replace(/^﻿/, ""));
}

function toPoints(result: unknown): Map<number, SurveyPoint> {
  const list = ((result as { points?: unknown[] })?.points ?? []) as Array<Record<string, unknown>>;
  const map = new Map<number, SurveyPoint>();
  for (const p of list) {
    const n = Number(p.number);
    map.set(n, { n, x: Number(p.x), y: Number(p.y), z: Number(p.z ?? 0), d: String(p.rawDescription ?? p.fullDescription ?? "") });
  }
  return map;
}

async function fetchPoints(filters: Record<string, unknown>): Promise<Map<number, SurveyPoint>> {
  return toPoints(await send("listCogoPoints", filters));
}

export const OFFICE_SURVEY_DOMAIN_DEFINITION: DomainToolDefinition = {
  domain: "office_survey",
  actions: {
    points: {
      action: "points",
      inputSchema: PointsArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["query"],
      requiresActiveDrawing: true,
      safeForRetry: true,
      pluginMethods: ["listCogoPoints"],
      execute: async (args) => {
        const { action: _a, outFile, ...filters } = args as z.infer<typeof PointsArgs>;
        const points = await fetchPoints(filters);
        // Pull LO neighbours (n-2..n+2) that the filter left out, so offsets resolve.
        const missing = [...points.keys()].flatMap((n) => [n - 2, n - 1, n + 1, n + 2]).filter((n) => n > 0 && !points.has(n));
        const neighbours = missing.length ? await fetchPoints({ includeNumbers: toRanges(missing) }) : new Map();
        const all = new Map([...points, ...neighbours]);
        const described = describePoints(all, [...points.keys()].sort((a, b) => a - b));
        const flagged = described.filter((p) => "flag" in p).map((p) => p.n);
        if (!outFile) return { count: described.length, flagged, points: described };
        writeFileSync(jsonPath(outFile, "outFile"), JSON.stringify({ points: described }, null, 1), "utf8");
        return { outFile, count: described.length, flagged };
      },
    },
    build: {
      action: "build",
      inputSchema: BuildArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["query"],
      requiresActiveDrawing: true,
      safeForRetry: true,
      pluginMethods: ["listCogoPoints", "queryEntities"],
      execute: async (args) => {
        const a = args as z.infer<typeof BuildArgs>;
        const plan = (a.planFile ? readJson(a.planFile, "planFile") : a.plan) as Plan;
        const numbers = referencedNumbers(plan);
        const points = numbers.length ? await fetchPoints({ includeNumbers: toRanges(numbers) }) : new Map<number, SurveyPoint>();

        // Rotation reference: existing lines on the reference layers around the plan's points.
        let referenceSegments: Segment[] = [];
        const layers = plan.reference?.layers ?? ["CURB"];
        if (points.size && layers.length && (plan.inserts?.length || plan.texts?.length)) {
          const xs = [...points.values()].map((p) => p.x);
          const ys = [...points.values()].map((p) => p.y);
          const pad = 150;
          const window = { minX: Math.min(...xs) - pad, minY: Math.min(...ys) - pad, maxX: Math.max(...xs) + pad, maxY: Math.max(...ys) + pad };
          const query = await send("queryEntities", { layers, window, crossing: true, includeGeometry: true, limit: 5000 });
          referenceSegments = segmentsFromQuery(query, layers);
        }

        const result = buildJob(plan, points, referenceSegments);
        const job = { version: 1, ...(plan.blockSource ? { blockSource: plan.blockSource } : {}), creates: result.creates };
        const jobFile = jsonPath(a.outFile, "outFile");
        writeFileSync(jobFile, JSON.stringify(job, null, 1), "utf8");
        return {
          jobFile,
          creates: result.creates.length,
          countsByLayer: result.countsByLayer,
          countsByType: result.countsByType,
          pointsFound: points.size,
          referenceSegments: referenceSegments.length,
          flags: result.flags,
          next: "Run civil3d_entity action apply with this jobFile (one approval).",
        };
      },
    },
    score: {
      action: "score",
      inputSchema: ScoreArgs,
      responseSchema: GenericResponseSchema,
      capabilities: ["query"],
      requiresActiveDrawing: false,
      safeForRetry: true,
      pluginMethods: [],
      execute: async (args) => {
        const a = args as z.infer<typeof ScoreArgs>;
        const job = readJson(a.jobFile, "jobFile") as { creates?: Array<Record<string, any>> };
        const layer = a.layer.toUpperCase();
        const mine = (job.creates ?? [])
          .filter((c) => c.type === "polyline" && String(c.layer).toUpperCase() === layer)
          .flatMap((c) => segmentsFromVertices(c.points, Boolean(c.closed)));
        const reference = segmentsFromQuery(readJson(a.referenceFile, "referenceFile"), [a.layer]);
        return { layer: a.layer, ...score(mine, reference, a.tolerance) };
      },
    },
  },
  exposures: [
    {
      toolName: "civil3d_office_survey",
      displayName: "Civil 3D Office Survey",
      description:
        "Office survey (OS) engine for turning field COGO shots into linework and symbols. " +
        "points: parsed shots (code, distances, LO partner, resolved LO offset points; shots with a distance but no LO are flagged), inline or to outFile. " +
        "build: resolve a plan that names point numbers into a civil3d_entity apply job file (outFile). Plan: {blockSource?, reference?:{layers:[\"CURB\"]}, " +
        "strings:[{layer, pts:[ref | {poc: ref}], closed?, offset?}], inserts:[{block, at: ref, layer, rotate?: deg | \"curb\" | \"curb+90\" | \"face-curb\", rotateAdd?, scale?, dynamic?, attributes?}], " +
        "circles:[{at, radius, layer}], arcs:[{at, radius, startDeg, endDeg, layer}], texts:[{text, at, height, layer, rotate?, dx?, dy?}], flags:[{at, note}]}. " +
        "ref = point number | {pt, off?: k (k-th LO offset point)} | {pt, dx, dy} | {x, y}. {poc: ref} makes a 3-point arc (bulge) to the next vertex; R > 1000 ft is drawn as lines and flagged. " +
        "Rotation 'curb' = parallel to the nearest reference line (existing drawing lines plus plan strings on reference layers), 'face-curb' = pointing straight at it. " +
        "Flags become a 5 ft circle + note on DISC-OTHER. Does not change the drawing; run civil3d_entity apply with the job file to draw it in one approval. " +
        "score: compare a job file's polylines on a layer with a civil3d_entity query outFile (a drafter's finished drawing), by length both ways.",
      inputShape: {
        action: z.enum(["points", "build", "score"]),
        includeNumbers: z.string().optional().describe("points: \"1-500,600\"."),
        includeDescriptions: z.string().optional().describe("points: wildcards on raw description, e.g. \"TC*,*LO\"."),
        layers: z.array(z.string()).optional().describe("points: point layers, e.g. [\"PTS-CRB\"]."),
        window: WindowSchema.optional().describe("points: only points inside this box."),
        outFile: z.string().min(1).optional().describe("points: optional .json to write results to. build: the job .json to write (absolute path)."),
        plan: z.record(z.unknown()).optional().describe("build: inline plan."),
        planFile: z.string().min(1).optional().describe("build: absolute path of a plan .json."),
        jobFile: z.string().min(1).optional().describe("score: a job file written by build."),
        referenceFile: z.string().min(1).optional().describe("score: a civil3d_entity query outFile with includeGeometry."),
        layer: z.string().min(1).optional().describe("score: layer to compare."),
        tolerance: z.number().positive().optional().describe("score: match distance in ft (default 1.5)."),
      },
      supportedActions: ["points", "build", "score"],
      resolveAction: (rawArgs) => ({ action: String(rawArgs.action ?? ""), args: rawArgs }),
    },
  ],
};

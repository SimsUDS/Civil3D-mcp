import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { ApprovalPolicyService, ApprovalValidationError } from "../src/tools/approvalPolicy.js";
import {
  parseJob,
  readJobFile,
  resultFilePath,
  runEntityJob,
  validateJob,
  writeJobResult,
} from "../src/tools/domains/entityJob.js";

const applyTarget = {
  toolName: "civil3d_entity",
  action: "apply",
  capabilities: ["create", "edit", "delete"] as const,
  safeForRetry: false,
};

function tempJob(job: unknown): string {
  const dir = mkdtempSync(path.join(tmpdir(), "entity-job-"));
  const file = path.join(dir, "job_1.json");
  writeFileSync(file, JSON.stringify(job), "utf8");
  return file;
}

function fakePlugin() {
  const calls: Array<{ method: string; payload: Record<string, unknown> }> = [];
  let next = 0x100;
  const send = async (method: string, payload: Record<string, unknown>) => {
    calls.push({ method, payload });
    if (method === "copyEntities") {
      const operations = payload.operations as Array<{ handles: string[] }>;
      return {
        operations: operations.map((operation, index) => ({
          index,
          handles: Object.fromEntries(operation.handles.map((handle) => [handle.toUpperCase(), (next++).toString(16).toUpperCase()])),
        })),
      };
    }
    if (method === "editEntities") return { edits: (payload.edits as unknown[]).map((_, index) => ({ index })) };
    if (method === "eraseEntities") return { count: (payload.handles as unknown[]).length };
    if (method === "createEntities") {
      const creates = payload.creates as unknown[];
      return {
        created: creates.map((_, index) => ({ index, handle: (next++).toString(16).toUpperCase() })),
        count: creates.length,
        importedBlocks: payload.blockSource ? ["tree1"] : [],
        warnings: [],
      };
    }
    if (method === "createHatches") {
      const hatches = payload.hatches as unknown[];
      return { hatches: hatches.map((_, index) => ({ index, handle: (next++).toString(16).toUpperCase() })), count: hatches.length };
    }
    throw new Error(`unexpected ${method}`);
  };
  return { calls, send };
}

describe("entity jobs", () => {
  it("runs creates first, in one createEntities call, passing blockSource", async () => {
    const job = validateJob({
      version: 1,
      blockSource: "C:\\jobs\\symbols.dwg",
      creates: [
        { type: "insert", blockName: "tree1", position: { x: 1, y: 2 }, layer: "LANDSCAPE" },
        { type: "polyline", points: [{ x: 0, y: 0, bulge: 0.4 }, { x: 5, y: 5 }], layer: "CURB" },
        { type: "circle", center: { x: 3, y: 3 }, radius: 3, layer: "TS" },
      ],
      copies: [{ id: "a", handles: ["2A"], dx: 1, dy: 1 }],
    });
    const { calls, send } = fakePlugin();
    const result = await runEntityJob(job, send);

    expect(result.status).toBe("completed");
    expect(calls.map((call) => call.method)).toEqual(["createEntities", "copyEntities"]);
    expect(calls[0].payload.blockSource).toBe("C:\\jobs\\symbols.dwg");
    expect((calls[0].payload.creates as unknown[]).length).toBe(3);
    expect(result.created).toBe(3);
    expect(result.createdHandles).toHaveLength(3);
    expect(result.importedBlocks).toEqual(["tree1"]);
  });

  it("rejects creates without a known type, a block name or enough points", () => {
    expect(() => validateJob({ creates: [{ type: "spline" }] })).toThrow(/type must be one of/);
    expect(() => validateJob({ creates: [{ type: "insert", position: { x: 0, y: 0 } }] })).toThrow(/needs blockName/);
    expect(() => validateJob({ creates: [{ type: "polyline", points: [{ x: 0, y: 0 }] }] })).toThrow(/at least 2 points/);
    expect(() => validateJob({ blockSource: "", creates: [] })).toThrow(/blockSource/);
  });

  it("copies, then resolves edit and erase refs to the new handles", async () => {
    const job = validateJob({
      version: 1,
      copies: [
        { id: "a", handles: ["2a4bc2", "2A4BC3"], dx: 10, dy: 0 },
        { id: "b", handles: ["2A4BC2"], dx: 0, dy: -50, mirrorX: 4 },
      ],
      edits: [
        { ref: "a:2A4BC2", text: "ONE" },
        { ref: "b:2a4bc2", text: "TWO" },
        { handle: "FFF", colorIndex: 1 },
      ],
      erase: ["ABC", { ref: "a:2A4BC3" }],
    });
    const { calls, send } = fakePlugin();
    const result = await runEntityJob(job, send);

    expect(result.status).toBe("completed");
    expect(result.copies).toEqual({ a: 2, b: 1 });
    expect(calls.map((call) => call.method)).toEqual(["copyEntities", "editEntities", "eraseEntities"]);
    expect((calls[0].payload.operations as Array<Record<string, unknown>>)[1]).toEqual({ handles: ["2A4BC2"], dx: 0, dy: -50, mirrorX: 4 });
    expect(calls[1].payload.edits).toEqual([
      { handle: "100", text: "ONE" },
      { handle: "102", text: "TWO" },
      { handle: "FFF", colorIndex: 1 },
    ]);
    expect(calls[2].payload.handles).toEqual(["ABC", "101"]);
  });

  it("runs hatches after edits with boundary and like refs resolved", async () => {
    const job = validateJob({
      copies: [{ id: "d", handles: ["39258A", "39258B", "39258C"], dx: 5, dy: 5 }],
      edits: [{ ref: "d:39258B", vertices: [{ x: 0, y: 0 }, { x: 1, y: 0 }] }],
      hatches: [{ boundaries: [{ ref: "d:39258B" }, { ref: "d:39258C" }, "ABC"], like: { ref: "d:39258A" }, scale: 2 }],
      erase: [{ ref: "d:39258A" }],
    });
    const { calls, send } = fakePlugin();
    const result = await runEntityJob(job, send);

    expect(result.status).toBe("completed");
    expect(calls.map((call) => call.method)).toEqual(["copyEntities", "editEntities", "createHatches", "eraseEntities"]);
    expect(calls[2].payload.hatches).toEqual([{ scale: 2, boundaries: ["101", "102", "ABC"], like: "100" }]);
    expect(result.hatched).toBe(1);
    expect(result.hatchHandles).toEqual(["103"]);
    expect(calls[3].payload.handles).toEqual(["100"]);
  });

  it("rejects hatches without boundaries or loops, and bad hatch refs", () => {
    expect(() => validateJob({ hatches: [{ like: "39258A" }] })).toThrow(/boundaries and\/or loops/);
    expect(() => validateJob({ hatches: [{ boundaries: [{ ref: "zz:1F" }] }] })).toThrow(/unknown copy id/);
    expect(() => validateJob({ hatches: [{ boundaries: ["XYZ"] }] })).toThrow(/hex handle/);
  });

  it("rejects bad refs before touching the drawing", () => {
    expect(() => validateJob({ copies: [{ id: "a", handles: ["1"], dx: 0, dy: 0 }], edits: [{ ref: "z:1", text: "x" }] }))
      .toThrow(/unknown copy id/);
    expect(() => validateJob({ edits: [{ handle: "1", ref: "a:1" }] })).toThrow(/exactly one/);
    expect(() => validateJob({ copies: [{ id: "a", handles: ["1"], dx: 0, dy: 0 }, { id: "a", handles: ["2"], dx: 0, dy: 0 }] }))
      .toThrow(/Duplicate/);
    expect(() => parseJob("{nope")).toThrow(/not valid JSON/);
  });

  it("reports the created handle maps when a later stage fails", async () => {
    const job = validateJob({
      copies: [{ id: "a", handles: ["10"], dx: 1, dy: 1 }],
      edits: [{ ref: "a:99", text: "x" }],
    });
    const { send } = fakePlugin();
    const result = await runEntityJob(job, send);
    expect(result.status).toBe("failed");
    expect(result.stage).toBe("edit");
    expect(result.handles).toEqual({ a: { "10": "100" } });
  });

  it("writes the result file beside the job", () => {
    const file = tempJob({ copies: [] });
    const { sha256 } = readJobFile(file);
    const written = writeJobResult(file, {
      status: "completed", stage: "done", copies: {}, copiedEntities: 0, edited: 0, erased: 0, handles: {},
    }, sha256);
    expect(written).toBe(resultFilePath(file));
    expect(JSON.parse(readFileSync(written, "utf8")).jobSha256).toBe(sha256);
  });

  it("requires absolute .json job paths", () => {
    expect(() => readJobFile("relative/job.json")).toThrow(/absolute/);
    expect(() => readJobFile(path.join(tmpdir(), "job.txt"))).toThrow(/\.json/);
  });
});

describe("approval bound to job file contents", () => {
  it("accepts the unchanged file and rejects an edited one", async () => {
    const file = tempJob({ copies: [{ id: "a", handles: ["1"], dx: 0, dy: 0 }] });
    const policy = new ApprovalPolicyService(async () => "drawing-a");
    const parameters = { action: "apply", jobFile: file };

    const receipt = await policy.requestApproval(applyTarget, parameters);
    expect(receipt.jobFileSha256).toBe(readJobFile(file).sha256);
    await expect(policy.enforce(applyTarget, { ...parameters, approvalToken: receipt.approvalToken })).resolves.toBeUndefined();

    const second = await policy.requestApproval(applyTarget, parameters);
    writeFileSync(file, JSON.stringify({ copies: [{ id: "a", handles: ["2"], dx: 0, dy: 0 }] }), "utf8");
    await expect(policy.enforce(applyTarget, { ...parameters, approvalToken: second.approvalToken }))
      .rejects.toThrow(/job file changed/);
  });

  it("fails approval cleanly when the job file is missing", async () => {
    const policy = new ApprovalPolicyService(async () => "drawing-a");
    await expect(policy.requestApproval(applyTarget, { action: "apply", jobFile: path.join(tmpdir(), "missing-job-xyz.json") }))
      .rejects.toBeInstanceOf(ApprovalValidationError);
  });
});

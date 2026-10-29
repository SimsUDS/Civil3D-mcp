import { describe, expect, it } from "vitest";
import {
  buildJob,
  describePoints,
  distances,
  offsetVertices,
  referencedNumbers,
  score,
  segmentsFromQuery,
  sweep,
  toRanges,
  type SurveyPoint,
} from "../src/tools/domains/officeSurvey.js";
import { findManifestAction } from "../src/tools/toolManifest.js";

const pts = (rows: Array<[number, number, number, string]>) =>
  new Map<number, SurveyPoint>(rows.map(([n, x, y, d]) => [n, { n, x, y, z: 0, d }]));

describe("office survey engine", () => {
  it("parses distances in every written form, not size codes", () => {
    expect(distances("GUT AP 6FT GUT 8.5FT")).toEqual([6, 8.5]);
    expect(distances("MOW .5FT CL")).toEqual([0.5]);
    expect(distances("GI 2.5X2.5")).toEqual([]);
    expect(distances("SS CO 6.5")).toEqual([6.5]);
  });

  it("resolves LO offsets from the LO through the shot and flags shots with no LO", () => {
    const p = pts([[10, 5, 5, "SW 2FT"], [11, 4, 5, "SW LO"], [20, 0, 0, "PP 783601E 63.0"]]);
    const d = describePoints(p);
    expect(d[0]).toMatchObject({ n: 10, loPoint: 11, offsets: [{ x: 7, y: 5 }] });
    expect(d[2]).toMatchObject({ n: 20, flag: "distance with no LO" });
  });

  it("signs arc sweeps: over the top from left to right is clockwise", () => {
    const s = sweep({ x: 0, y: 0 }, { x: 10, y: 10 }, { x: 20, y: 0 });
    expect(s.radius).toBeCloseTo(10);
    expect(s.sweep).toBeCloseTo(-Math.PI);
  });

  it("builds polylines with bulges, curb-parallel and curb-facing blocks, and flags", () => {
    const p = pts([
      [1, 0, 0, "TC BC"], [2, 10, 10, "TC POC"], [3, 20, 0, "TC EC"], [4, 40, 0, "TC END"],
      [50, 30, 5, "WM"], [51, 30, -6, "FH"], [60, 25, 3, "SS CO 2FT"], [61, 25, 2, "LO"],
    ]);
    const r = buildJob({
      strings: [{ layer: "CURB", pts: [1, { poc: 2 }, 3, 4] }],
      inserts: [
        { block: "W_MTR", at: 50, layer: "WATER", rotate: "curb" },
        { block: "FH", at: 51, layer: "WATER", rotate: "face-curb" },
        { block: "MISC_VALVE", at: { pt: 60, off: 0 }, layer: "SEWER" },
        { block: "MISSING", at: 999, layer: "MISC" },
      ],
      flags: [{ at: 4, note: "check 4" }],
    }, p);
    const [curb, wm, fh, co] = r.creates;
    expect(curb).toMatchObject({ type: "polyline", layer: "CURB" });
    expect((curb.points as any[])[0].bulge).toBeCloseTo(-1);
    expect((curb.points as any[]).length).toBe(3);
    expect(wm).toMatchObject({ blockName: "W_MTR", rotationDeg: 0 });
    expect(fh).toMatchObject({ blockName: "FH", rotationDeg: 90 });
    expect(co).toMatchObject({ position: { x: 25, y: 5 } });
    expect(r.flags.some((f) => f.includes("999"))).toBe(true);
    expect(r.countsByLayer["DISC-OTHER"]).toBe(2);
  });

  it("draws flat 'arcs' as lines and flags them", () => {
    const p = pts([[1, 0, 0, "TC"], [2, 50, 0.1, "TC POC"], [3, 100, 0, "TC"]]);
    const r = buildJob({ strings: [{ layer: "CURB", pts: [1, { poc: 2 }, 3] }] }, p);
    expect((r.creates[0].points as any[]).length).toBe(3);
    expect(r.flags[0]).toMatch(/drawn as two lines/);
  });

  it("offsets straight polylines to the left with mitred corners", () => {
    expect(offsetVertices([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }], 1))
      .toEqual([{ x: 0, y: 1 }, { x: 9, y: 1 }, { x: 9, y: 10 }]);
  });

  it("collects referenced numbers with LO neighbours and compresses them to ranges", () => {
    const nums = referencedNumbers({ strings: [{ layer: "A", pts: [5, { poc: 7 }, { pt: 20, off: 0 }] }] });
    expect(nums).toEqual([5, 7, 18, 19, 20, 21, 22]);
    expect(toRanges(nums)).toBe("5,7,18-22");
  });

  it("scores by length both ways", () => {
    const ref = segmentsFromQuery({ entities: [{ type: "LWPOLYLINE", layer: "CURB", vertices: [{ x: 0, y: 0 }, { x: 100, y: 0 }] }] }, ["CURB"]);
    const s = score([[0, 0.2, 50, 0.2], [0, 30, 20, 30]], ref);
    expect(s).toMatchObject({ referenceFt: 100, referenceMissedFt: 50, mineFt: 70, mineExtraFt: 20 });
  });

  it("is registered as civil3d_office_survey", () => {
    for (const action of ["points", "build", "score"]) {
      expect(findManifestAction("civil3d_office_survey", action)).toBeDefined();
    }
  });
});

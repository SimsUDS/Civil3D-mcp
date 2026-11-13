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

  it("reads ARC entities and polyline bulges as arcs, not chords", () => {
    // quarter arc, center (0,0), r 100, 0..90 deg: a point at 45 deg, 90 ft from the center, is 10 ft from it
    const arc = segmentsFromQuery({ entities: [{ type: "ARC", layer: "CL", center: { x: 0, y: 0 }, radius: 100, startAngleDeg: 0, endAngleDeg: 90 }] }, ["CL"]);
    expect(arc.length).toBeGreaterThan(10);
    expect(arc[0][0]).toBeCloseTo(100);
    expect(arc[arc.length - 1][3]).toBeCloseTo(100);
    // wraps through 0 deg (350 -> 10) instead of sweeping the long way
    const wrap = segmentsFromQuery({ entities: [{ type: "ARC", layer: "CL", center: { x: 0, y: 0 }, radius: 100, startAngleDeg: 350, endAngleDeg: 10 }] }, ["CL"]);
    const len = wrap.reduce((t, s) => t + Math.hypot(s[2] - s[0], s[3] - s[1]), 0);
    expect(len).toBeCloseTo((20 * Math.PI * 100) / 180, 0);
    // semicircle bulge -1 from (0,0) to (20,0) goes over the top through (10,10)
    const b = segmentsFromQuery({ entities: [{ type: "LWPOLYLINE", layer: "CURB", vertices: [{ x: 0, y: 0, bulge: -1 }, { x: 20, y: 0 }] }] }, ["CURB"]);
    expect(b.length).toBeGreaterThan(5);
    for (const s of b) {
      expect(Math.hypot(s[2] - 10, s[3])).toBeCloseTo(10, 6); // every vertex on the circle (center (10,0), r 10)
      expect(s[3]).toBeGreaterThanOrEqual(-1e-9); // upper half
    }
    expect(b[0].slice(0, 2)).toEqual([0, 0]);
    expect(b[b.length - 1].slice(2)).toEqual([20, 0]);
  });

  it("rotates to the reference layers first and falls back to the fallback layers", () => {
    const p = pts([[1, 0, 50, "WM"], [2, 500, 50, "WM"], [3, 900, 50, "FH"], [4, 5000, 0, "WM"]]);
    const curb = segmentsFromQuery({ entities: [{ type: "LINE", layer: "CURB", start: { x: -50, y: 40 }, end: { x: 50, y: 40 } }] }, ["CURB"]);
    // CL: a straight line near point 1 (would win on distance) and an arc (center (700,-300), r 350) near points 2 and 3
    const cl = segmentsFromQuery({ entities: [
      { type: "LINE", layer: "CL", start: { x: -50, y: 48 }, end: { x: 50, y: 98 } },
      { type: "ARC", layer: "CL", center: { x: 700, y: -300 }, radius: 350, startAngleDeg: 60, endAngleDeg: 120 },
    ] }, ["CL"]);
    const r = buildJob({
      reference: { layers: ["CURB"], fallback: ["CL"] },
      inserts: [
        { block: "W_MTR", at: 1, layer: "WATER", rotate: "curb" },
        { block: "W_MTR", at: 2, layer: "WATER", rotate: "curb" },
        { block: "FH", at: 3, layer: "WATER", rotate: "face-curb" },
        { block: "W_MTR", at: 4, layer: "WATER", rotate: "curb" },
      ],
    }, p, curb, cl);
    const [a, b, c, d] = r.creates as any[];
    expect(a.rotationDeg).toBeCloseTo(0, 1); // curb within 100 ft wins over the nearer CL
    // point 2 (500,50): nearest on the CL arc is along the ray from the center, tangent is perpendicular to it
    const ang = (Math.atan2(50 + 300, 500 - 700) * 180) / Math.PI; // ~119.7 deg
    let tan = ang - 90;
    if (tan > 90) tan -= 180;
    expect(b.rotationDeg).toBeCloseTo(tan, 0);
    // FH at (900,50) faces the arc: toward the center's ray foot, i.e. away from or toward (700,-300)
    const toCenter = (Math.atan2(-300 - 50, 700 - 900) * 180) / Math.PI;
    const dist = Math.hypot(900 - 700, 50 + 300) - 350; // > 0: outside the arc, so it faces the center
    expect(dist).toBeGreaterThan(0);
    expect(((c.rotationDeg - toCenter + 540) % 360) - 180).toBeCloseTo(0, 0);
    expect(d.rotationDeg).toBe(0); // nothing within 100 ft at all
    expect(r.flags.some((f) => f.includes("insert 3 (W_MTR)") && f.includes("used 0"))).toBe(true);
    expect(r.flags.some((f) => f.startsWith("2 rotations used the fallback layers (CL)"))).toBe(true);
  });

  it("is registered as civil3d_office_survey", () => {
    for (const action of ["points", "build", "score"]) {
      expect(findManifestAction("civil3d_office_survey", action)).toBeDefined();
    }
  });
});

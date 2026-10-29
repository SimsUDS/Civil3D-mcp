/**
 * Office survey (OS) engine: turns COGO point shots into an entity job.
 *
 * The caller (the office-survey skill) decides WHAT to draw and writes a small
 * plan that names point numbers. This module does the survey math the same way
 * on every job: description parsing, LO offsets, 3-point arcs as bulges,
 * parallel offsets, curb-parallel / curb-facing rotation, DISC-OTHER flags. It
 * returns `creates` for a civil3d_entity apply job, so a whole job is one file
 * and one approval.
 *
 * Plan (JSON):
 * {
 *   version: 1,
 *   blockSource?: "C:\\...\\symbols.dwg",
 *   reference?: { layers: ["CURB"] },            // rotation reference: drawing lines on these layers + plan strings on them
 *   strings?: [{ layer, pts: [Ref | {poc: Ref}], closed?, offset?, colorIndex?, id? }],
 *   inserts?: [{ block, at: Ref, layer, rotate?: number | "curb" | "curb+90" | "face-curb", rotateAdd?,
 *               scale?, dynamic?, attributes?, id? }],
 *   circles?: [{ at: Ref, radius, layer }],
 *   arcs?:    [{ at: Ref, radius, startDeg, endDeg, layer }],
 *   texts?:   [{ text, at: Ref, height, layer, rotate?, dx?, dy? }],
 *   flags?:   [{ at: Ref, note, layer? }]
 * }
 * Ref = point number (the shot) | {pt: n, off?: k} (the k-th LO offset point of shot n, default 0)
 *     | {x, y} | {pt: n, dx, dy}.
 */

export interface SurveyPoint {
  n: number;
  x: number;
  y: number;
  z: number;
  d: string;
}

export interface XY {
  x: number;
  y: number;
}

export type Segment = [number, number, number, number];

// ------------------------------------------------------------ descriptions

const DIST = /^(\d*\.?\d+)(FT)?$/i;

export function words(desc: string): string[] {
  return desc.trim().split(/\s+/).filter(Boolean);
}

export function code(desc: string): string {
  return words(desc)[0] ?? "";
}

/** Distances written in a description (2FT, 2.0, .5FT, 15FT); the first word is the code, size codes like 2X2 are not distances. */
export function distances(desc: string): number[] {
  return words(desc).slice(1).flatMap((w) => {
    const m = DIST.exec(w);
    return m ? [Number(m[1])] : [];
  });
}

export function isLo(p: SurveyPoint): boolean {
  const w = words(p.d);
  return w[w.length - 1]?.toUpperCase() === "LO";
}

/** The LO that gives direction for shot n: n+1 first, then n-1, n+2, n-2. */
export function loPartner(points: Map<number, SurveyPoint>, n: number): SurveyPoint | undefined {
  for (const k of [n + 1, n - 1, n + 2, n - 2]) {
    const p = points.get(k);
    if (p && isLo(p)) return p;
  }
  return undefined;
}

/** True point = shot + dist along the unit vector FROM the LO THROUGH the shot. */
export function offsetPoint(shot: XY, lo: XY, dist: number): XY {
  const ux = shot.x - lo.x;
  const uy = shot.y - lo.y;
  const len = Math.hypot(ux, uy);
  if (len === 0) throw new Error("LO point coincides with the shot.");
  return { x: shot.x + (dist * ux) / len, y: shot.y + (dist * uy) / len };
}

/** All offset points a shot carries, one per distance; empty when it has no distance or no LO. */
export function offsets(points: Map<number, SurveyPoint>, n: number): XY[] {
  const shot = points.get(n);
  if (!shot || isLo(shot)) return [];
  const dists = distances(shot.d);
  if (dists.length === 0) return [];
  const lo = loPartner(points, n);
  return lo ? dists.map((d) => offsetPoint(shot, lo, d)) : [];
}

// ---------------------------------------------------------------- geometry

export function circle3(a: XY, b: XY, c: XY): { x: number; y: number; r: number } {
  const d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y));
  if (Math.abs(d) < 1e-12) return { x: NaN, y: NaN, r: Infinity };
  const a2 = a.x * a.x + a.y * a.y;
  const b2 = b.x * b.x + b.y * b.y;
  const c2 = c.x * c.x + c.y * c.y;
  const x = (a2 * (b.y - c.y) + b2 * (c.y - a.y) + c2 * (a.y - b.y)) / d;
  const y = (a2 * (c.x - b.x) + b2 * (a.x - c.x) + c2 * (b.x - a.x)) / d;
  return { x, y, r: Math.hypot(a.x - x, a.y - y) };
}

/** Signed sweep (radians, + = CCW) of the arc from a through b to c, and its radius. */
export function sweep(a: XY, b: XY, c: XY): { sweep: number; radius: number } {
  const o = circle3(a, b, c);
  if (!Number.isFinite(o.r)) return { sweep: 0, radius: Infinity };
  const tp = 2 * Math.PI;
  const mod = (v: number) => ((v % tp) + tp) % tp;
  const A = Math.atan2(a.y - o.y, a.x - o.x);
  const B = Math.atan2(b.y - o.y, b.x - o.x);
  const C = Math.atan2(c.y - o.y, c.x - o.x);
  const ccw = mod(C - A);
  return { sweep: mod(B - A) < ccw ? ccw : ccw - tp, radius: o.r };
}

export const MAX_ARC_RADIUS = 1000;

const round = (v: number, places = 4) => Number(v.toFixed(places));

export interface Vertex {
  x: number;
  y: number;
  bulge?: number;
}

/** Parallel offset of a straight-segment polyline; positive = left of the direction of travel. */
export function offsetVertices(vertices: XY[], dist: number): Vertex[] {
  const n = vertices.length;
  const normal = (i: number) => {
    const a = vertices[i];
    const b = vertices[i + 1];
    const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    return { x: -(b.y - a.y) / len, y: (b.x - a.x) / len };
  };
  return vertices.map((p, i) => {
    if (i === 0 || i === n - 1) {
      const m = normal(i === 0 ? 0 : n - 2);
      return { x: round(p.x + m.x * dist), y: round(p.y + m.y * dist) };
    }
    const m1 = normal(i - 1);
    const m2 = normal(i);
    let bx = m1.x + m2.x;
    let by = m1.y + m2.y;
    const bl = Math.hypot(bx, by) || 1;
    bx /= bl;
    by /= bl;
    const cos = Math.max(0.2, bx * m1.x + by * m1.y); // miter, capped for very sharp corners
    return { x: round(p.x + (bx * dist) / cos), y: round(p.y + (by * dist) / cos) };
  });
}

// ----------------------------------------------------------- linework index

export function distToSegment(p: XY, s: Segment): { d: number; foot: XY } {
  const [x1, y1, x2, y2] = s;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const l2 = dx * dx + dy * dy;
  const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((p.x - x1) * dx + (p.y - y1) * dy) / l2));
  const foot = { x: x1 + t * dx, y: y1 + t * dy };
  return { d: Math.hypot(p.x - foot.x, p.y - foot.y), foot };
}

export class LineIndex {
  private grid = new Map<string, Segment[]>();
  constructor(readonly segments: Segment[], private cell = 50) {
    for (const s of segments) {
      const gx0 = Math.floor(Math.min(s[0], s[2]) / cell) - 1;
      const gx1 = Math.floor(Math.max(s[0], s[2]) / cell) + 1;
      const gy0 = Math.floor(Math.min(s[1], s[3]) / cell) - 1;
      const gy1 = Math.floor(Math.max(s[1], s[3]) / cell) + 1;
      for (let gx = gx0; gx <= gx1; gx++) {
        for (let gy = gy0; gy <= gy1; gy++) {
          const key = `${gx},${gy}`;
          const list = this.grid.get(key);
          if (list) list.push(s);
          else this.grid.set(key, [s]);
        }
      }
    }
  }

  nearest(p: XY, maxDist = 100): { segment: Segment; d: number; foot: XY } | undefined {
    const r = Math.ceil(maxDist / this.cell);
    const gx = Math.floor(p.x / this.cell);
    const gy = Math.floor(p.y / this.cell);
    let best: { segment: Segment; d: number; foot: XY } | undefined;
    for (let i = -r; i <= r; i++) {
      for (let j = -r; j <= r; j++) {
        for (const s of this.grid.get(`${gx + i},${gy + j}`) ?? []) {
          const hit = distToSegment(p, s);
          if (hit.d <= maxDist && (!best || hit.d < best.d)) best = { segment: s, ...hit };
        }
      }
    }
    return best;
  }

  /** Direction of the nearest segment, in (-90, 90] degrees (blocks parallel to the curb). */
  directionDeg(p: XY): number | undefined {
    const hit = this.nearest(p);
    if (!hit) return undefined;
    const [x1, y1, x2, y2] = hit.segment;
    let deg = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI;
    if (deg > 90) deg -= 180;
    if (deg <= -90) deg += 180;
    return deg;
  }

  /** Direction from p straight to the nearest line (fire hydrants face the street). */
  facingDeg(p: XY): number | undefined {
    const hit = this.nearest(p);
    if (!hit || hit.d < 1e-9) return undefined;
    return (Math.atan2(hit.foot.y - p.y, hit.foot.x - p.x) * 180) / Math.PI;
  }
}

export function segmentsFromVertices(vertices: XY[], closed = false): Segment[] {
  const pts = closed && vertices.length > 2 ? [...vertices, vertices[0]] : vertices;
  const out: Segment[] = [];
  for (let i = 0; i + 1 < pts.length; i++) out.push([pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y]);
  return out;
}

/** Segments from a civil3d_entity query result (LINE and LWPOLYLINE; arcs read as chords). */
export function segmentsFromQuery(result: unknown, layers?: string[]): Segment[] {
  const wanted = layers ? new Set(layers.map((l) => l.toUpperCase())) : undefined;
  const entities = ((result as { entities?: unknown[] })?.entities ?? []) as Array<Record<string, any>>;
  const out: Segment[] = [];
  for (const e of entities) {
    if (wanted && !wanted.has(String(e.layer ?? "").toUpperCase())) continue;
    if (Array.isArray(e.vertices) && String(e.type).toUpperCase().includes("POLYLINE")) {
      out.push(...segmentsFromVertices(e.vertices, Boolean(e.closed)));
    } else if (e.start && e.end) {
      out.push([e.start.x, e.start.y, e.end.x, e.end.y]);
    }
  }
  return out;
}

// -------------------------------------------------------------------- plan

export type Ref = number | { pt: number; off?: number; dx?: number; dy?: number } | { x: number; y: number };
export type StringItem = Ref | { poc: Ref };

export interface Plan {
  version?: number;
  blockSource?: string;
  reference?: { layers?: string[] };
  strings?: Array<{ layer: string; pts: StringItem[]; closed?: boolean; offset?: number; colorIndex?: number; id?: string }>;
  inserts?: Array<{
    block: string; at: Ref; layer: string; rotate?: number | "curb" | "curb+90" | "face-curb"; rotateAdd?: number;
    scale?: number; dynamic?: Record<string, string | number>; attributes?: Record<string, string>; id?: string;
  }>;
  circles?: Array<{ at: Ref; radius: number; layer: string; id?: string }>;
  arcs?: Array<{ at: Ref; radius: number; startDeg: number; endDeg: number; layer: string; id?: string }>;
  texts?: Array<{ text: string; at: Ref; height: number; layer: string; rotate?: number | "curb" | "curb+90"; dx?: number; dy?: number; id?: string }>;
  flags?: Array<{ at: Ref; note: string; layer?: string }>;
}

export interface BuildResult {
  creates: Array<Record<string, unknown>>;
  flags: string[];
  countsByLayer: Record<string, number>;
  countsByType: Record<string, number>;
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** Every point number a plan touches, plus its LO search neighbours (for fetching from the drawing). */
export function referencedNumbers(plan: Plan): number[] {
  const out = new Set<number>();
  const add = (r: unknown) => {
    if (typeof r === "number") out.add(r);
    else if (isObj(r)) {
      if (typeof r.pt === "number") for (let k = r.pt - 2; k <= r.pt + 2; k++) if (k > 0) out.add(k);
      if (r.poc !== undefined) add(r.poc);
    }
  };
  plan.strings?.forEach((s) => s.pts.forEach(add));
  for (const list of [plan.inserts, plan.circles, plan.arcs, plan.texts, plan.flags]) list?.forEach((i) => add(i.at));
  return [...out].sort((a, b) => a - b);
}

/** "1-5,9,12-14" for listCogoPoints includeNumbers. */
export function toRanges(numbers: number[]): string {
  const sorted = [...new Set(numbers)].sort((a, b) => a - b);
  const parts: string[] = [];
  for (let i = 0; i < sorted.length; ) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++;
    parts.push(i === j ? `${sorted[i]}` : `${sorted[i]}-${sorted[j]}`);
    i = j + 1;
  }
  return parts.join(",");
}

export function buildJob(plan: Plan, points: Map<number, SurveyPoint>, referenceSegments: Segment[] = []): BuildResult {
  const flags: string[] = [];
  const creates: Array<Record<string, unknown>> = [];

  const resolve = (ref: Ref, where: string): XY | undefined => {
    if (typeof ref === "number") {
      const p = points.get(ref);
      if (!p) flags.push(`${where}: point ${ref} not in the drawing`);
      return p ? { x: p.x, y: p.y } : undefined;
    }
    if (isObj(ref) && typeof (ref as { pt?: unknown }).pt === "number") {
      const r = ref as { pt: number; off?: number; dx?: number; dy?: number };
      const p = points.get(r.pt);
      if (!p) {
        flags.push(`${where}: point ${r.pt} not in the drawing`);
        return undefined;
      }
      let base: XY = { x: p.x, y: p.y };
      if (r.off !== undefined) {
        const offs = offsets(points, r.pt);
        if (!offs[r.off]) {
          flags.push(`${where}: shot ${r.pt} '${p.d}' has no offset #${r.off} (no distance or no LO)`);
          return undefined;
        }
        base = offs[r.off];
      }
      return { x: base.x + (r.dx ?? 0), y: base.y + (r.dy ?? 0) };
    }
    if (isObj(ref) && typeof (ref as XY).x === "number" && typeof (ref as XY).y === "number") return ref as XY;
    flags.push(`${where}: bad point reference ${JSON.stringify(ref)}`);
    return undefined;
  };

  // Strings first, so strings on reference layers (the curb drawn in this same plan) steer rotations.
  const refLayers = new Set((plan.reference?.layers ?? ["CURB"]).map((l) => l.toUpperCase()));
  const segments = [...referenceSegments];

  plan.strings?.forEach((s, si) => {
    const where = `string ${s.id ?? si} (${s.layer})`;
    const verts: Vertex[] = [];
    let pending: XY | undefined; // POC waiting for its end vertex
    let pendingLabel = "";
    for (const item of s.pts) {
      if (isObj(item) && "poc" in item) {
        pending = resolve(item.poc as Ref, where);
        pendingLabel = JSON.stringify(item.poc);
        continue;
      }
      const v = resolve(item as Ref, where);
      if (!v) continue;
      if (pending && verts.length > 0) {
        const a = verts[verts.length - 1];
        const arc = sweep(a, pending, v);
        if (arc.radius > MAX_ARC_RADIUS) {
          flags.push(`${where}: arc through ${pendingLabel} R=${Math.round(arc.radius)} drawn as two lines`);
          verts.push({ x: round(pending.x), y: round(pending.y) });
        } else {
          a.bulge = round(Math.tan(arc.sweep / 4), 6);
        }
      }
      pending = undefined;
      verts.push({ x: round(v.x), y: round(v.y) });
    }
    if (verts.length < 2) {
      flags.push(`${where}: fewer than 2 vertices, skipped`);
      return;
    }
    let out = verts;
    if (s.offset) {
      if (verts.some((v) => v.bulge)) flags.push(`${where}: offset ignores arcs (straight segments only)`);
      out = offsetVertices(verts, s.offset);
    }
    creates.push({ type: "polyline", layer: s.layer, points: out, ...(s.closed ? { closed: true } : {}),
      ...(s.colorIndex !== undefined ? { colorIndex: s.colorIndex } : {}), ...(s.id ? { id: s.id } : {}) });
    if (refLayers.has(s.layer.toUpperCase())) segments.push(...segmentsFromVertices(out, s.closed));
  });

  const index = new LineIndex(segments);
  const rotation = (rot: unknown, at: XY, where: string): number => {
    if (typeof rot === "number") return rot;
    if (rot === undefined) return 0;
    const deg = rot === "face-curb" ? index.facingDeg(at) : index.directionDeg(at);
    if (deg === undefined) {
      flags.push(`${where}: no reference line within 100 ft for rotate '${rot}', used 0`);
      return 0;
    }
    return rot === "curb+90" ? deg + 90 : deg;
  };

  plan.inserts?.forEach((b, i) => {
    const where = `insert ${b.id ?? i} (${b.block})`;
    const at = resolve(b.at, where);
    if (!at) return;
    creates.push({
      type: "insert", blockName: b.block, layer: b.layer,
      position: { x: round(at.x), y: round(at.y) },
      rotationDeg: round(rotation(b.rotate, at, where) + (b.rotateAdd ?? 0), 3),
      ...(b.scale ? { scale: b.scale } : {}),
      ...(b.dynamic ? { dynamicProperties: b.dynamic } : {}),
      ...(b.attributes ? { attributes: b.attributes } : {}),
      ...(b.id ? { id: b.id } : {}),
    });
  });

  plan.circles?.forEach((c, i) => {
    const at = resolve(c.at, `circle ${c.id ?? i}`);
    if (at) creates.push({ type: "circle", layer: c.layer, center: { x: round(at.x), y: round(at.y) }, radius: c.radius, ...(c.id ? { id: c.id } : {}) });
  });

  plan.arcs?.forEach((a, i) => {
    const at = resolve(a.at, `arc ${a.id ?? i}`);
    if (at) creates.push({ type: "arc", layer: a.layer, center: { x: round(at.x), y: round(at.y) }, radius: a.radius,
      startAngleDeg: a.startDeg, endAngleDeg: a.endDeg, ...(a.id ? { id: a.id } : {}) });
  });

  plan.texts?.forEach((t, i) => {
    const where = `text ${t.id ?? i}`;
    const at = resolve(t.at, where);
    if (!at) return;
    creates.push({ type: "text", layer: t.layer, text: t.text, height: t.height,
      position: { x: round(at.x + (t.dx ?? 0)), y: round(at.y + (t.dy ?? 0)) },
      rotationDeg: round(rotation(t.rotate, at, where), 3), ...(t.id ? { id: t.id } : {}) });
  });

  plan.flags?.forEach((f, i) => {
    const at = resolve(f.at, `flag ${i}`);
    flags.push(`flag: ${f.note}`);
    if (!at) return;
    const layer = f.layer ?? "DISC-OTHER";
    creates.push({ type: "circle", layer, center: { x: round(at.x), y: round(at.y) }, radius: 5 });
    creates.push({ type: "text", layer, text: f.note, height: 1, position: { x: round(at.x + 5.5), y: round(at.y) }, rotationDeg: 0 });
  });

  const countsByLayer: Record<string, number> = {};
  const countsByType: Record<string, number> = {};
  for (const c of creates) {
    countsByLayer[String(c.layer)] = (countsByLayer[String(c.layer)] ?? 0) + 1;
    countsByType[String(c.type)] = (countsByType[String(c.type)] ?? 0) + 1;
  }
  return { creates, flags, countsByLayer, countsByType };
}

/** Parsed view of points for analysis: code, distances, LO partner and resolved offset points. */
export function describePoints(points: Map<number, SurveyPoint>, numbers?: number[]) {
  const list = numbers ? numbers.map((n) => points.get(n)).filter((p): p is SurveyPoint => !!p) : [...points.values()];
  return list.map((p) => {
    const dists = distances(p.d);
    const lo = dists.length && !isLo(p) ? loPartner(points, p.n) : undefined;
    return {
      n: p.n, x: round(p.x), y: round(p.y), d: p.d, code: code(p.d),
      ...(isLo(p) ? { lo: true } : {}),
      ...(dists.length ? { distances: dists } : {}),
      ...(lo ? { loPoint: lo.n, offsets: offsets(points, p.n).map((o) => ({ x: round(o.x), y: round(o.y) })) } : {}),
      ...(dists.length && !isLo(p) && !lo ? { flag: "distance with no LO" } : {}),
    };
  });
}

/** Length both ways: reference length not near mine, and my length not near the reference (sampled every ~5 ft). */
export function score(mine: Segment[], reference: Segment[], tolerance = 1.5, step = 5) {
  const unmatched = (a: Segment[], b: LineIndex) => {
    let total = 0;
    let miss = 0;
    for (const s of a) {
      const len = Math.hypot(s[2] - s[0], s[3] - s[1]);
      total += len;
      const pieces = Math.max(1, Math.round(len / step));
      for (let i = 0; i < pieces; i++) {
        const t = (i + 0.5) / pieces;
        if (!b.nearest({ x: s[0] + t * (s[2] - s[0]), y: s[1] + t * (s[3] - s[1]) }, tolerance)) miss += len / pieces;
      }
    }
    return { total: Math.round(total), miss: Math.round(miss) };
  };
  const r = unmatched(reference, new LineIndex(mine));
  const m = unmatched(mine, new LineIndex(reference));
  return { referenceFt: r.total, referenceMissedFt: r.miss, mineFt: m.total, mineExtraFt: m.miss };
}

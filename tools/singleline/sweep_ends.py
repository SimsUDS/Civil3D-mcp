"""Sweep a single line for loose conductor ends.

Usage: python sweep_ends.py <query.json> [--tol 0.3]

For every CIRCUIT-* polyline end, report it unless it
  - touches another conductor (vertex or segment within tol), or
  - sits on a block terminal: inside that block's extents (+tol) -- equipment like switches, transformers,
    junction bars, potheads, PMEs, arrows, poles.
Ends that are near a block (within 20 ft) but outside it are "SHORT" (stopped before the equipment);
anything else is "DANGLING". Output: one line per loose end with the nearest block and gap.
"""
import json, math, sys

def seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))

def main(path, tol=0.3):
    E = json.load(open(path))["entities"]
    cond = [e for e in E if e["type"] == "LWPOLYLINE" and e["layer"].startswith("CIRCUIT")]
    def _small(e):                  # structure boxes (X#/V#/M#, ~6 x 8 ft) are equipment; vault outlines are not
        ex = e["extents"]; return (ex["max"]["x"] - ex["min"]["x"]) * (ex["max"]["y"] - ex["min"]["y"]) < 150
    blocks = [e for e in E if e["type"] == "INSERT" and e.get("extents") and (e["blockName"] != "SGL_BOX" or _small(e))]
    out = []
    for i, c in enumerate(cond):
        vs = [(v["x"], v["y"]) for v in c["vertices"]]
        for p in (vs[0], vs[-1]):
            touch = False
            for j, d in enumerate(cond):
                ws = [(v["x"], v["y"]) for v in d["vertices"]]
                if j == i:
                    continue
                if any(seg_dist(p, a, b) < tol for a, b in zip(ws, ws[1:])):
                    touch = True; break
            if touch:
                continue
            inside, near = None, None
            for b in blocks:
                ex = b["extents"]
                x0, y0, x1, y1 = ex["min"]["x"], ex["min"]["y"], ex["max"]["x"], ex["max"]["y"]
                gx = max(x0 - p[0], 0, p[0] - x1); gy = max(y0 - p[1], 0, p[1] - y1)
                g = math.hypot(gx, gy)
                if g <= tol:
                    inside = b; break
                if near is None or g < near[0]:
                    near = (g, b)
            if inside:
                continue
            kind = "SHORT" if near and near[0] < 20 else "DANGLING"
            nb = near[1] if near else None
            out.append((kind, c["handle"], c["layer"], round(p[0], 1), round(p[1], 1),
                        nb["blockName"] if nb else "-", nb["handle"] if nb else "-", round(near[0], 1) if near else None))
    for r in sorted(out):
        print(*r)
    print(f"{len(out)} loose ends ({sum(1 for r in out if r[0] == 'SHORT')} short of a block)")

if __name__ == "__main__":
    tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 0.3
    main(sys.argv[1], tol)

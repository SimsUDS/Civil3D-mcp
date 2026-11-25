"""Small-symbol extractor for SCE circuit-map PDFs (the details extract_page.py skips).

python extract_symbols.py <pdf> <page index 0-based> <out.json> [--to-ref s,ax,ay,bx,by] [--cloud cloud.json]

Finds the thin-stroke symbols that sit on or hang off the conductors:
  fuse   - a 0.12 pt zig-zag (6-10 short strokes, about 0.8 x 2.1 pt), usually with a ground "W" at its far end.
           It maps to SGL_TRAN_FUSED (or SGL_TRAN on a junction leg). "vertical" when taller than wide.
  chevron- a 0.48 pt "V" of two strokes (about 2.5 x 2.2 pt), the elbow mark; stacked pairs are merged into one.
           It maps to SGL_LBE (transformer blocks already draw their own elbows).
For each symbol it reports the centre, orientation, and the attachment: the nearest conductor-width
(>= 0.8 pt) stroke end or point within 6 pt, i.e. where the symbol hangs off the cable.
Coordinates are given in the reference page frame when --to-ref is passed (same transform as extract_page.py),
and limited to the red cloud when --cloud <extract_page json> is given (its "cloud" polygon).
"""
import json, math, sys
import fitz

pdf, pi, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
S, AX, AY, BX, BY = 1.0, 0.0, 0.0, 0.0, 0.0
if "--to-ref" in sys.argv:
    S, AX, AY, BX, BY = map(float, sys.argv[sys.argv.index("--to-ref") + 1].split(","))
ref = lambda p: (AX + S * (p[0] - BX), AY + S * (p[1] - BY))
cloud = None
if "--cloud" in sys.argv:
    cloud = json.load(open(sys.argv[sys.argv.index("--cloud") + 1])).get("cloud")

def inside(pt, poly):
    if not poly: return True
    x, y = pt; c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
    return c

page = fitz.open(pdf)[pi]
D = page.get_drawings()
black = lambda c: c and max(c) < 0.25

# conductor-width strokes (to find what each symbol hangs off)
cond = []
for dr in D:
    if (dr.get("width") or 0) >= 0.8 and dr.get("color"):
        for it in dr["items"]:
            if it[0] == "l": cond.append(((it[1].x, it[1].y), (it[2].x, it[2].y)))
def nearest_cond(p, r=6.0):
    best = None
    for a, b in cond:
        dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        q = (a[0] + t * dx, a[1] + t * dy); d = math.dist(p, q)
        if d < r and (best is None or d < best[0]): best = (d, q)
    return best

# equipment outlines (0.48 pt black boxes / quads 4-14 pt): a zig-zag INSIDE one is part of a transformer symbol
boxes = []
for dr in D:
    if 0.4 < (dr.get("width") or 0) < 0.6 and black(dr.get("color")) and any(it[0] in ("re", "qu") for it in dr["items"]):
        r = dr["rect"]
        if 4 <= r.width <= 14 and 4 <= r.height <= 14: boxes.append(r)
in_box = lambda p: any(b.x0 - 0.2 <= p[0] <= b.x1 + 0.2 and b.y0 - 0.2 <= p[1] <= b.y1 + 0.2 for b in boxes)

syms = []
# ground taps: a 0.12 pt "W" of 4 strokes (about 2.9 x 0.9 pt) at the end of a 0.12 stub, with no zig-zag above it
# (SGL_TRAN on a junction leg, J496 leg 3). Collected first; a W under a zig-zag belongs to that fuse.
ws = []
for dr in D:
    w = dr.get("width") or 0; r = dr["rect"]
    if 0.05 < w < 0.2 and black(dr.get("color")) and sum(1 for it in dr["items"] if it[0] == "l") == 4             and 2.2 <= r.width <= 3.4 and 0.5 <= r.height <= 1.2:
        ws.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
# fuses: 0.12 pt zig-zags
for dr in D:
    w = dr.get("width") or 0; r = dr["rect"]
    if not (0.05 < w < 0.2 and black(dr.get("color"))): continue
    n = sum(1 for it in dr["items"] if it[0] == "l")
    long_, short_ = max(r.width, r.height), min(r.width, r.height)
    if not (6 <= n <= 10 and 1.5 <= long_ <= 3.2 and 0.4 <= short_ <= 1.3): continue
    c = ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
    if in_box(c): continue                       # the squiggle drawn inside a transformer box
    vertical = r.height > r.width
    ws = [q for q in ws if math.dist(q, c) > 4.5]  # its ground W is part of this fuse
    # ends of the zig-zag along its axis; the attachment is the end nearer a conductor
    ends = [(c[0], r.y0), (c[0], r.y1)] if vertical else [(r.x0, c[1]), (r.x1, c[1])]
    att = [(nearest_cond(e, 7.0), e) for e in ends]
    att = [(a[0], a[1], e) for a, e in att if a]
    hook = min(att) if att else None
    syms.append({"kind": "fuse", "c": c, "vertical": vertical,
                 "attach": hook[1] if hook else None, "attach_gap": round(hook[0], 2) if hook else None,
                 # direction from the attachment toward the fuse (where the fuse "hangs")
                 "dir": (None if not hook else (round(c[0] - hook[1][0], 2), round(c[1] - hook[1][1], 2)))})

for q in ws:                                     # W with no zig-zag: a plain tap to ground (stub above it)
    if in_box(q): continue
    hook = nearest_cond((q[0], q[1] - 4.5), 7.0) or nearest_cond((q[0], q[1] + 4.5), 7.0)
    syms.append({"kind": "tap", "c": q, "vertical": True, "attach": hook[1] if hook else None,
                 "attach_gap": round(hook[0], 2) if hook else None,
                 "dir": (None if not hook else (round(q[0] - hook[1][0], 2), round(q[1] - hook[1][1], 2)))})

# chevrons: 0.48 pt two-stroke "V"
chev = []
for dr in D:
    w = dr.get("width") or 0; r = dr["rect"]
    if not (0.4 < w < 0.6 and black(dr.get("color"))): continue
    ls = [it for it in dr["items"] if it[0] == "l"]
    if len(ls) != 2 or len(dr["items"]) != 2: continue
    if not (1.8 <= r.width <= 3.2 and 1.5 <= r.height <= 3.0): continue
    p = [(it[1].x, it[1].y) for it in ls] + [(it[2].x, it[2].y) for it in ls]
    # apex = the point shared by both strokes
    apex = min(((a, b) for a in p for b in p if a is not b), key=lambda z: math.dist(*z))[0]
    chev.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, apex))
used = set()
for i, (x, y, apex) in enumerate(chev):
    if i in used: continue
    grp = [j for j, (x2, y2, _a) in enumerate(chev) if j not in used and math.dist((x, y), (x2, y2)) < 3.2]
    used.update(grp)
    cx = sum(chev[j][0] for j in grp) / len(grp); cy = sum(chev[j][1] for j in grp) / len(grp)
    hook = nearest_cond((cx, cy), 4.0)
    syms.append({"kind": "chevron", "c": (cx, cy), "count": len(grp), "apex": apex,
                 "attach": hook[1] if hook else None, "attach_gap": round(hook[0], 2) if hook else None})

# into the reference frame, inside the cloud only
res = []
for s_ in syms:
    if not inside(ref(s_["c"]), cloud): continue      # the cloud polygon is in the reference frame (extract_page.py)
    o = dict(s_); o["page_c"] = [round(v, 2) for v in s_["c"]]
    for k in ("c", "attach", "apex"):
        if o.get(k): o[k] = [round(v, 2) for v in ref(o[k])]
    if o.get("dir"): o["dir"] = [round(v * S, 2) for v in o["dir"]]
    res.append(o)
json.dump({"page": pi, "symbols": res}, open(out, "w"), indent=1)
from collections import Counter
print(f"{len(res)} symbols:", dict(Counter(r["kind"] for r in res)))

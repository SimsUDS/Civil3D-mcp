"""Symbol census of an SCE circuit-map PDF page: every small vector symbol, grouped by shape.

python symbol_census.py <pdf> <page 0-based> <out.json> [--sheet out.png]

Kevin 2026-11-25: "the PDFs are vectors -- associate vector shapes to the blocks, then you understand what is what".
1. Drop what is not a symbol: conductor strokes (>= 0.8 pt), street lines (light gray), the red cloud, and text glyphs
   (filled outlines made only of curves, the way the map's text is drawn).
2. Cluster the remaining primitives that touch or nearly touch (gap <= 0.6 pt) into symbol instances.
3. Give each instance a shape signature that ignores position: rounded size (w x h), stroke widths used, counts of
   lines / curves / rects, filled or not, colour family. Rotations are folded (w x h sorted) so a symbol and its
   90-degree turn share a signature.
4. Group instances by signature -> symbol types, with a count and sample page positions.
The output is the dictionary to label once ("this signature = SGL_TRAN_FUSED"); after that the generator can place
every instance of a labelled type, and any unlabelled type is a detail still to be identified.
With --sheet, a contact sheet shows one zoomed example of each type with its id and count.
"""
import json, math, sys
from collections import defaultdict
import fitz

pdf, pi, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
sheet = sys.argv[sys.argv.index("--sheet") + 1] if "--sheet" in sys.argv else None
page = fitz.open(pdf)[pi]
D = page.get_drawings()

def family(c):
    if not c: return "none"
    r, g, b = c
    if max(c) - min(c) < 0.1: return "gray" if max(c) > 0.3 else "black"
    if r > 0.7 and g < 0.4 and b < 0.4: return "red"
    if g > 0.7 and r < 0.4: return "green"
    if b > 0.7 and r < 0.3: return "blue"
    if r > 0.4 and b > 0.4 and g < 0.3: return "purple"
    return "other"

prims = []
for dr in D:
    w = dr.get("width") or 0; col = dr.get("color"); fill = dr.get("fill"); r = dr["rect"]
    kinds = [it[0] for it in dr["items"]]
    if col and w >= 0.8: continue                                    # conductors, cloud
    if col and family(col) == "gray" and max(col) > 0.6: continue    # streets
    if r.width > 30 or r.height > 30: continue                       # big outlines (cloud, title, frames)
    if fill and not col and kinds and r.width < 5.5 and r.height < 6             and not (kinds.count("l") == 3 and not kinds.count("c")) and not (kinds.count("c") == 4 and kinds.count("l") <= 1):
        continue                         # a text glyph (filled, unstroked letter); keeps filled triangles and round dots
    prims.append({"r": (r.x0, r.y0, r.x1, r.y1), "w": round(w, 2), "col": family(col or fill),
                  "fill": bool(fill), "n_l": kinds.count("l"), "n_c": kinds.count("c"),
                  "n_re": kinds.count("re") + kinds.count("qu")})

# cluster by touching boxes (grid-accelerated union-find)
parent = list(range(len(prims)))
def find(i):
    while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
    return i
G = 0.6
grid = defaultdict(list)
for i, p in enumerate(prims):
    x0, y0, x1, y1 = p["r"]
    for gx in range(int(x0 // 5), int(x1 // 5) + 1):
        for gy in range(int(y0 // 5), int(y1 // 5) + 1): grid[(gx, gy)].append(i)
for cell, ids in grid.items():
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            i, j = ids[a], ids[b]; A, B = prims[i]["r"], prims[j]["r"]
            if A[0] - G <= B[2] and B[0] - G <= A[2] and A[1] - G <= B[3] and B[1] - G <= A[3]:
                ri, rj = find(i), find(j)
                if ri != rj: parent[ri] = rj
clusters = defaultdict(list)
for i in range(len(prims)): clusters[find(i)].append(prims[i])

def signature(ps):
    x0 = min(p["r"][0] for p in ps); y0 = min(p["r"][1] for p in ps)
    x1 = max(p["r"][2] for p in ps); y1 = max(p["r"][3] for p in ps)
    w, h = sorted((round(x1 - x0, 0), round(y1 - y0, 0)))
    widths = ",".join(sorted({str(p["w"]) for p in ps}))
    cols = ",".join(sorted({p["col"] for p in ps}))
    return (f"{w:g}x{h:g}|w{widths}|{cols}|l{sum(p['n_l'] for p in ps)}c{sum(p['n_c'] for p in ps)}"
            f"r{sum(p['n_re'] for p in ps)}|{'F' if any(p['fill'] for p in ps) else 'S'}"), (x0, y0, x1, y1)

types = defaultdict(list)
for ps in clusters.values():
    sig, box = signature(ps)
    if box[2] - box[0] < 0.5 and box[3] - box[1] < 0.5: continue   # specks
    types[sig].append([round(v, 1) for v in box])
# optional: keep only symbols inside the red cloud (cloud polygon of extract_page.py, reference frame, --to-ref like it)
if "--cloud" in sys.argv:
    S_, AX_, AY_, BX_, BY_ = map(float, sys.argv[sys.argv.index("--to-ref") + 1].split(",")) if "--to-ref" in sys.argv else (1, 0, 0, 0, 0)
    poly = [((p[0] - AX_) / S_ + BX_, (p[1] - AY_) / S_ + BY_) for p in json.load(open(sys.argv[sys.argv.index("--cloud") + 1]))["cloud"]]
    def _in(pt):
        x, y = pt; c = False
        for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
        return c
    types = defaultdict(list, {s: [b for b in bs if _in(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))] for s, bs in types.items()})
    types = defaultdict(list, {s: bs for s, bs in types.items() if bs})
# optional: label with the symbol dictionary (signature -> block); unlabelled types are details still to identify
DICT = json.load(open(sys.argv[sys.argv.index("--dict") + 1]))["types"] if "--dict" in sys.argv else {}
res = sorted(({"id": f"S{k:03d}", "signature": s, "count": len(b), "samples": b[:12],
               "label": DICT.get(s)}
              for k, (s, b) in enumerate(sorted(types.items(), key=lambda kv: -len(kv[1])))), key=lambda t: -t["count"])
json.dump({"page": pi, "types": res}, open(out, "w"), indent=1)
print(f"{sum(t['count'] for t in res)} symbol instances in {len(res)} shape types")
for t in res[:40]:
    lab = t["label"]; tag = (lab["block"] or lab["kind"]) if lab else "** UNLABELLED **"
    print(t["id"], t["count"], tag, t["signature"], t["samples"][0])
if DICT:
    by_block = defaultdict(int)
    for t in res:
        if t["label"] and t["label"]["kind"] == "block": by_block[t["label"]["block"]] += t["count"]
    print("blocks on the sheet:", dict(sorted(by_block.items())))
    print("unlabelled types:", [(t["id"], t["count"], t["samples"][0]) for t in res if not t["label"]])

if sheet:
    import numpy as np
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    show = [t for t in res if t["count"] >= 1][:60]
    cols = 8; rows = math.ceil(len(show) / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(cols * 2.2, rows * 2.4))
    for ax, t in zip(axs.flat, show):
        x0, y0, x1, y1 = t["samples"][0]; pad = max(3, (x1 - x0), (y1 - y0)) * 0.6
        pix = page.get_pixmap(clip=fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad), matrix=fitz.Matrix(14, 14))
        ax.imshow(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n))
        ax.set_title(f"{t['id']} x{t['count']}", fontsize=7); ax.axis("off")
    for ax in list(axs.flat)[len(show):]: ax.axis("off")
    plt.tight_layout(); plt.savefig(sheet, dpi=90)

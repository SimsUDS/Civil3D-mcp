"""Tiled PDF-vs-drawing check for a single line.

python tile_check.py <pdf> <page 0-based> <extract.json> <outdir> [--to-ref s,ax,ay,bx,by] [--tile 50] [--zoom 16]

Splits the page's red cloud into overlapping square tiles (default 50 pt, 15% overlap), keeps the tiles that hold
conductors, renders each PDF tile at --zoom (default 16x) to <outdir>/tNN_pdf.png and writes <outdir>/tiles.json with,
per tile, the PDF clip rectangle and the matching drawing window (page -> reference frame -> drawing feet, the same
transforms the generator uses: T(x, y) = ((x - 150) * 3, -(y - 290) * 3) + origin (24600, 14900)).
The drawing side is then captured with civil3d_drawing capture_view (render) into <outdir>/tNN_dwg.png, and each pair
goes to a reviewer that lists what the PDF shows that the drawing lacks or draws differently.
The drawing is condensed in places (vaults, PS circles), so a tile's window is padded 30% to keep moved blocks in view.
"""
import json, math, os, sys
import fitz

pdf, pi, ext, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
S, AX, AY, BX, BY = 1.0, 0.0, 0.0, 0.0, 0.0
if "--to-ref" in sys.argv:
    S, AX, AY, BX, BY = map(float, sys.argv[sys.argv.index("--to-ref") + 1].split(","))
TILE = float(sys.argv[sys.argv.index("--tile") + 1]) if "--tile" in sys.argv else 50.0
ZOOM = float(sys.argv[sys.argv.index("--zoom") + 1]) if "--zoom" in sys.argv else 16.0
os.makedirs(outdir, exist_ok=True)

E = json.load(open(ext))
cloud_ref = E["cloud"]                                   # reference frame
to_page = lambda p: (BX + (p[0] - AX) / S, BY + (p[1] - AY) / S)
to_ref = lambda p: (AX + S * (p[0] - BX), AY + S * (p[1] - BY))
to_dwg = lambda r: (24600 + (r[0] - 150) * 3, 14900 - (r[1] - 290) * 3)
cloud = [to_page(p) for p in cloud_ref]
cond_pts = [to_page(p) for c in E["conductors"] for p in c["pts"]]

def inside(pt, poly):
    x, y = pt; c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
    return c

xs, ys = [p[0] for p in cloud], [p[1] for p in cloud]
step = TILE * 0.85
page = fitz.open(pdf)[pi]
tiles = []; k = 0
y = min(ys)
while y < max(ys):
    x = min(xs)
    while x < max(xs):
        r = (x, y, x + TILE, y + TILE)
        has = any(r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3] and inside(p, cloud) for p in cond_pts)
        if has:
            a, b = to_dwg(to_ref((r[0], r[1]))), to_dwg(to_ref((r[2], r[3])))
            wx0, wx1 = sorted((a[0], b[0])); wy0, wy1 = sorted((a[1], b[1]))
            px, py = (wx1 - wx0) * 0.3, (wy1 - wy0) * 0.3
            name = f"t{k:02d}"
            page.get_pixmap(clip=fitz.Rect(*r), matrix=fitz.Matrix(ZOOM, ZOOM)).save(os.path.join(outdir, name + "_pdf.png"))
            tiles.append({"id": name, "pdf_clip": [round(v, 1) for v in r],
                          "dwg_window": {"minX": round(wx0 - px, 1), "minY": round(wy0 - py, 1),
                                         "maxX": round(wx1 + px, 1), "maxY": round(wy1 + py, 1)}})
            k += 1
        x += step
    y += step
json.dump({"pdf": pdf, "page": pi, "tile_pt": TILE, "zoom": ZOOM, "tiles": tiles}, open(os.path.join(outdir, "tiles.json"), "w"), indent=1)
print(f"{len(tiles)} tiles -> {outdir}")

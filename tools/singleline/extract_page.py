"""Extract one SCE circuit-map page (vector PDF) for single-line drafting.

python extract_page.py <pdf> <page index 0-based> <out.json> [--to-ref s,ax,ay,bx,by]
  --to-ref: similarity transform into the reference page frame: x' = ax + s*(x - bx), y' = ay + s*(y - by)

Output (all coordinates in reference-page points):
  cloud: polygon of the red revision cloud
  conductors: [{pts, len, cover, ug}]  width-1.2 green/black strokes chained; ug = dashed (low coverage)
  poles: [x, y]       blue 0.72 circles
  boxes: [{c, w, h, quad}] black 0.48 rectangles / quads 3-14 pt
  triangles: [{c, pts, fill}] small filled triangles (potheads, arrows)
  labels / streetnames: glyph clusters (black / grey fills): centre, n glyphs, angle, bbox, id
  streets / rr: grey street and dark rail segments clipped to the cloud
"""
import sys, json, math, collections
import pymupdf

pdf, pi, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
s, ax, ay, bx, by = 1.0, 0.0, 0.0, 0.0, 0.0
if '--to-ref' in sys.argv:
    s, ax, ay, bx, by = map(float, sys.argv[sys.argv.index('--to-ref') + 1].split(','))
def X(p): return (ax + s * (p[0] - bx), ay + s * (p[1] - by))

page = pymupdf.open(pdf)[pi]
dr = page.get_drawings()
def col(g, k):
    c = g.get(k); return tuple(round(v, 2) for v in c) if c else None

cloud = next(g for g in dr if col(g, 'color') == (0.86, 0.2, 0.15) and round(g.get('width') or 0) == 2)
poly = [X((it[1].x, it[1].y)) for it in cloud['items']]
def inside(pt):
    x, y = pt; c = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
def clip(a, b, step=0.5):
    L = math.dist(a, b); n = max(1, int(L / step)); res = []; cur = None
    for i in range(n + 1):
        t = i / n; q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        if inside(q):
            cur = [q, q] if cur is None else [cur[0], q]
        else:
            if cur and math.dist(*cur) > 0.3: res.append(cur)
            cur = None
    if cur and math.dist(*cur) > 0.3: res.append(cur)
    return res
def segs_of(g):
    for it in g['items']:
        if it[0] == 'l': yield X((it[1].x, it[1].y)), X((it[2].x, it[2].y))
        elif it[0] == 'c': yield X((it[1].x, it[1].y)), X((it[4].x, it[4].y))
        elif it[0] == 're':
            r = it[1]; c = [X((r.x0, r.y0)), X((r.x1, r.y0)), X((r.x1, r.y1)), X((r.x0, r.y1))]
            for i in range(4): yield c[i], c[(i + 1) % 4]

# Hops: the PDF draws a conductor jumping another as its own stroke of ~12 short segments forming a semicircle.
# Record each hop (chord ends + apex) and put a straight chord in its place, so the conductor chains straight
# through the crossing; the generator redraws the hop as a clean polyline bulge.
def hop_of(g):
    P = [X((it[1].x, it[1].y)) for it in g['items'] if it[0] == 'l'] + [X((g['items'][-1][2].x, g['items'][-1][2].y))] \
        if all(it[0] == 'l' for it in g['items']) else None
    if not P or len(P) < 7: return None
    a, b = P[0], P[-1]; chord = math.dist(a, b)
    if not (2.0 * s < chord < 8.0 * s): return None
    path = sum(math.dist(P[i], P[i + 1]) for i in range(len(P) - 1))
    if not (1.3 < path / chord < 1.85): return None
    apex = max(P, key=lambda q: abs((b[0] - a[0]) * (a[1] - q[1]) - (a[0] - q[0]) * (b[1] - a[1])))
    return {'a': a, 'b': b, 'apex': apex}

cs = []; hops = []
for g in dr:
    if g['type'] == 's' and round(g.get('width') or 0, 2) == 1.2 and col(g, 'color') in ((0, 1, 0), (0, 0, 0)):
        h = hop_of(g)
        if h and inside(h['apex']):
            hops.append(h); cs.append((h['a'], h['b'])); continue
        for a, b in segs_of(g):
            if math.dist(a, b) > 0.01 and inside(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)): cs.append((a, b))

def chains(segs, tol):
    used = [False] * len(segs); res = []
    for i in range(len(segs)):
        if used[i]: continue
        used[i] = True; ch = [segs[i][0], segs[i][1]]; cover = math.dist(*segs[i])
        L0 = math.dist(*segs[i]); ticks = 1 if L0 < 1.0 * s else 0; dashes = 1 if L0 > 2.0 * s else 0
        for fwd in (True, False):
            while True:
                tip = ch[-1] if fwd else ch[0]; prev = ch[-2] if fwd else ch[1]; best = None
                for j, (a, b) in enumerate(segs):
                    if used[j]: continue
                    for nr, o in ((a, b), (b, a)):
                        d = math.dist(nr, tip)
                        if d > tol: continue
                        ux, uy = tip[0] - prev[0], tip[1] - prev[1]; vx, vy = o[0] - nr[0], o[1] - nr[1]
                        if not fwd: ux, uy = -ux, -uy
                        nu, nv = math.hypot(ux, uy), math.hypot(vx, vy)
                        cos = (ux * vx + uy * vy) / (nu * nv) if nu > 0.05 and nv > 0.05 else 1
                        score = d + (1 - cos) * 3
                        if best is None or score < best[0]: best = (score, j, nr, o)
                if not best: break
                _, j, nr, o = best; used[j] = True; cover += math.dist(nr, o)
                Lj = math.dist(nr, o); ticks += Lj < 1.0 * s; dashes += Lj > 2.0 * s
                if fwd: ch += ([nr, o] if math.dist(nr, tip) > 0.05 else [o])
                else: ch[:0] = ([o, nr] if math.dist(nr, tip) > 0.05 else [o])
        L = sum(math.dist(ch[k], ch[k + 1]) for k in range(len(ch) - 1))
        res.append((ch, cover / L if L else 1, ticks, dashes))
    return res

conductors = []
for ch, cov, ticks, dashes in chains(cs, 2.6 * s):
    L = sum(math.dist(ch[k], ch[k + 1]) for k in range(len(ch) - 1))
    if L < 2: continue
    conductors.append({'pts': ch, 'len': round(L, 1), 'cover': round(cov, 2), 'ug': cov < 0.93, 'ticks': ticks, 'dashes': dashes})

poles = []
for g in dr:
    if col(g, 'color') == (0, 0.58, 1) and g['type'] == 's':
        r = g['rect']
        if 2.5 < r.width < 5 and 2.5 < r.height < 5:
            c = X((r.x0 + r.width / 2, r.y0 + r.height / 2))
            if inside(c) and not any(math.dist(c, p) < 1 for p in poles): poles.append(c)

dots = []
for g in dr:
    if (col(g, 'fill') == (0, 0, 0) or col(g, 'color') == (0, 0, 0)) and len(g['items']) == 4 and all(it[0] == 'c' for it in g['items']):
        r = g['rect']
        if 1.3 < r.width < 2.6 and 1.3 < r.height < 2.6:
            c = X(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
            if inside(c): dots.append(c)

boxes = []
for g in dr:
    if g['type'] == 's' and col(g, 'color') == (0, 0, 0) and round(g.get('width') or 0, 2) == 0.48 and len(g['items']) == 1 and g['items'][0][0] in ('re', 'qu'):
        r = g['rect']
        if 3 < r.width < 14 and 3 < r.height < 14:
            q = g['items'][0][1]
            if g['items'][0][0] == 're':
                pts = [X((q.x0, q.y0)), X((q.x1, q.y1))]
            else:
                pts = [X((pp.x, pp.y)) for pp in (q.ul, q.ur, q.lr, q.ll)]
            c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            if inside(c): boxes.append({'c': c, 'w': r.width * s, 'h': r.height * s, 'quad': g['items'][0][0] == 'qu'})

tris = []
for g in dr:
    if g['type'] == 'f' and col(g, 'fill') in ((0, 0, 0), (0, 1, 0)) and len(g['items']) == 3 and all(it[0] == 'l' for it in g['items']):
        r = g['rect']
        if 2 < max(r.width, r.height) < 7:
            pts = [X((it[1].x, it[1].y)) for it in g['items']]
            c = (sum(p[0] for p in pts) / 3, sum(p[1] for p in pts) / 3)
            if inside(c): tris.append({'c': c, 'pts': pts, 'fill': col(g, 'fill')})

def clusters(fill, gap):
    G = [g['rect'] for g in dr if g['type'] == 'f' and col(g, 'fill') == fill and g['rect'].width < 6 and g['rect'].height < 6]
    cen = [X(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)) for r in G]
    par = list(range(len(G)))
    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    idx = collections.defaultdict(list)
    for i, c in enumerate(cen): idx[(int(c[0] // 4), int(c[1] // 4))].append(i)
    for i, c in enumerate(cen):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in idx.get((int(c[0] // 4) + dx, int(c[1] // 4) + dy), []):
                    if j > i and math.dist(c, cen[j]) < gap: par[f(i)] = f(j)
    cl = collections.defaultdict(list)
    for i in range(len(G)): cl[f(i)].append(i)
    res = []
    for ids in cl.values():
        P = [cen[i] for i in ids]; cx = sum(p[0] for p in P) / len(P); cy = sum(p[1] for p in P) / len(P)
        if not inside((cx, cy)): continue
        sxx = sum((p[0] - cx) ** 2 for p in P); syy = sum((p[1] - cy) ** 2 for p in P); sxy = sum((p[0] - cx) * (p[1] - cy) for p in P)
        ang = 0.5 * math.degrees(math.atan2(2 * sxy, sxx - syy)) if len(P) > 2 else 0
        res.append({'c': (cx, cy), 'n': len(P), 'ang': round(ang, 1),
                    'bbox': [min(p[0] for p in P), min(p[1] for p in P), max(p[0] for p in P), max(p[1] for p in P)]})
    res.sort(key=lambda c: (round(c['c'][1] / 12), c['c'][0]))
    for i, c in enumerate(res): c['id'] = i
    return res

labels = clusters((0, 0, 0), 3.2 * s)
streetnames = clusters((0.18, 0.18, 0.18), 3.2 * s)
streets, rr = [], []
for g in dr:
    if g['type'] != 's': continue
    if col(g, 'color') == (0.75, 0.75, 0.75):
        for a, b in segs_of(g): streets += clip(a, b)
    elif col(g, 'color') == (0.24, 0.26, 0.36):
        for a, b in segs_of(g): rr += clip(a, b)

json.dump({'cloud': poly, 'dots': dots, 'hops': hops, 'conductors': conductors, 'poles': poles, 'boxes': boxes, 'triangles': tris,
           'labels': labels, 'streetnames': streetnames, 'streets': streets, 'rr': rr}, open(out, 'w'))
print(f"hops {len(hops)}, conductors {len(conductors)} (ug {sum(c['ug'] for c in conductors)}), poles {len(poles)}, boxes {len(boxes)}, "
      f"triangles {len(tris)}, label clusters {len(labels)}, street names {len(streetnames)}, streets {len(streets)}, rr {len(rr)}")

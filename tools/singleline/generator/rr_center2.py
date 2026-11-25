"""Railroad centerlines (v2): every rail sample is moved to the midpoint with the facing rail (nearest point on
another rail, 1.2-4.2 pt away, parallel), thinned, walked into polylines across dash gaps, smoothed, simplified."""
import json, math
from collections import defaultdict
import pymupdf
exec(open('rr_center.py').read().split("rails = [r for r")[0])          # reuse chainify / samples / helpers
def dp(P, eps=0.25):
    if len(P) < 3: return P
    a, b = P[0], P[-1]; L = math.dist(a, b) or 1e-9; idx, dm = 0, 0
    for i in range(1, len(P) - 1):
        d = abs((b[0] - a[0]) * (a[1] - P[i][1]) - (a[0] - P[i][0]) * (b[1] - a[1])) / L
        if d > dm: idx, dm = i, d
    return dp(P[:idx + 1], eps)[:-1] + dp(P[idx:], eps) if dm > eps else [a, b]

rails = [r for r in chainify(segs, 0.6) if length(r) > 0.5]
rsegs = [(ri, a, b) for ri, r in enumerate(rails) for a, b in zip(r, r[1:]) if math.dist(a, b) > 0.05]
grid = defaultdict(list)
for k, (ri, a, b) in enumerate(rsegs):
    for t in (0, 0.5, 1):
        grid[(int((a[0] + (b[0] - a[0]) * t) // 5), int((a[1] + (b[1] - a[1]) * t) // 5))].append(k)
mids = []
for ri, r in enumerate(rails):
    for p in samples(r, 0.8):
        gx, gy = int(p[0] // 5), int(p[1] // 5); best = None
        for k in {k for dx in (-1, 0, 1) for dy in (-1, 0, 1) for k in grid.get((gx + dx, gy + dy), [])}:
            rj, a, b = rsegs[k]
            if rj == ri: continue
            dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
            t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2)); q = (a[0] + t * dx, a[1] + t * dy)
            d = math.dist(p[:2], q)
            if not (1.2 < d < 4.2): continue
            L = math.sqrt(L2)
            if abs((dx * p[2] + dy * p[3]) / L) < 0.95: continue
            if best is None or d < best[0]: best = (d, q)
        mids.append(((p[0] + best[1][0]) / 2, (p[1] + best[1][1]) / 2) if best else (p[0], p[1]))
pts = []; G = defaultdict(list)
for m in mids:
    gx, gy = int(m[0] // 2), int(m[1] // 2)
    if any(math.dist(m, pts[k]) < 1.0 for dx in (-1, 0, 1) for dy in (-1, 0, 1) for k in G.get((gx + dx, gy + dy), [])): continue
    G[(gx, gy)].append(len(pts)); pts.append(m)
unused = set(range(len(pts)))
def step(tip, prev):
    best = None
    for k in unused:
        q = pts[k]; d = math.dist(tip, q)
        if d == 0 or d > 7: continue
        score = d
        if prev is not None:
            ax, ay = tip[0] - prev[0], tip[1] - prev[1]; bx, by = q[0] - tip[0], q[1] - tip[1]
            cos = (ax * bx + ay * by) / ((math.hypot(ax, ay) or 1) * d)
            if cos < 0.8: continue
            score = d * (2 - cos) ** 2
        if best is None or score < best[0]: best = (score, k)
    return best[1] if best else None
lines = []
while unused:
    s = min(unused, key=lambda k: (pts[k][0], pts[k][1])); unused.discard(s); ch = [pts[s]]
    for fwd in (True, False):
        while True:
            tip = ch[-1] if fwd else ch[0]
            prev = (ch[-2] if fwd else ch[1]) if len(ch) > 1 else None
            k = step(tip, prev)
            if k is None: break
            unused.discard(k)
            for j in [j for j in unused if math.dist(pts[j], pts[k]) < 1.3]: unused.discard(j)
            ch.append(pts[k]) if fwd else ch.insert(0, pts[k])
    if len(ch) >= 5:                                     # light smoothing
        sm = [ch[0]] + [tuple(sum(c[i] for c in ch[max(0, k - 2):k + 3]) / len(ch[max(0, k - 2):k + 3]) for i in (0, 1)) for k in range(1, len(ch) - 1)] + [ch[-1]]
        ch = sm
    ch = dp(ch, 0.35)
    if length(ch) > 4: lines.append(ch)
# drop short pieces that just duplicate a longer line
def near_line(p, l):
    return min(math.dist(p, nearest_on_chain(p + (0, 0), l)[1]) for _ in [0])
clean = []
for l in sorted(lines, key=length, reverse=True):
    if length(l) < 30 and any(sum(1 for p in samples(l, 1.0) if nearest_on_chain(p, c)[0] < 3.0) >= 0.6 * len(samples(l, 1.0)) for c in clean):
        continue
    clean.append(l)
lines = clean
# join pieces across remaining gaps (ends <= 12 pt apart, heading the same way)
def joinable(A, B):
    d = math.dist(A[-1], B[0])
    if d > 12: return False
    ux, uy = A[-1][0] - A[-2][0], A[-1][1] - A[-2][1]; vx, vy = B[1][0] - B[0][0], B[1][1] - B[0][1]
    nu, nv = math.hypot(ux, uy) or 1, math.hypot(vx, vy) or 1
    if (ux * vx + uy * vy) / (nu * nv) < 0.8: return False
    if d < 0.5: return True
    gx, gy = B[0][0] - A[-1][0], B[0][1] - A[-1][1]
    return (ux * gx + uy * gy) / (nu * d) > 0.8
merged = True
while merged:
    merged = False
    for i in range(len(lines)):
        for j in range(len(lines)):
            if i == j: continue
            for A in (lines[i], lines[i][::-1]):
                for B in (lines[j], lines[j][::-1]):
                    if joinable(A, B):
                        lines[i] = A + B; lines.pop(j); merged = True; break
                if merged: break
            if merged: break
        if merged: break
def despike(P, tol=0.6):
    P = list(P); changed = True
    while changed and len(P) > 2:
        changed = False
        for i in range(1, len(P) - 1):
            a, p, b = P[i - 1], P[i], P[i + 1]
            L = math.dist(a, b) or 1e-9
            d = abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / L
            if d > tol and math.dist(a, p) < 80 and math.dist(p, b) < 80:
                # only a spike if the line is straight on both sides of it
                ok = True
                if i >= 2:
                    q = P[i - 2]; L2 = math.dist(q, b) or 1e-9
                    ok &= abs((b[0] - q[0]) * (q[1] - a[1]) - (q[0] - a[0]) * (b[1] - q[1])) / L2 < tol
                if ok:
                    P.pop(i); changed = True; break
    return P
lines = [dp(despike(dp(l, 0.35)), 0.6) for l in lines]
print('centre pts', len(pts), 'lines', len(lines), [round(length(l)) for l in lines])
F = json.load(open('p1_streets_final.json')); F['rr_center'] = lines; json.dump(F, open('p1_streets_final.json', 'w'))
doc = pymupdf.open(); pg = doc.new_page(width=460, height=480); sh = pg.new_shape()
for a, b in segs:
    sh.draw_line(pymupdf.Point(a[0] - 105, a[1] - 230), pymupdf.Point(b[0] - 105, b[1] - 230)); sh.finish(color=(0.75, 0.75, 0.75), width=0.3)
cols = [(1, 0, 0), (0, 0.6, 0), (0, 0, 1), (0.8, 0, 0.8), (0.9, 0.5, 0)]
for i, ch in enumerate(lines):
    for a, b in zip(ch, ch[1:]):
        sh.draw_line(pymupdf.Point(a[0] - 105, a[1] - 230), pymupdf.Point(b[0] - 105, b[1] - 230)); sh.finish(color=cols[i % 5], width=0.5)
sh.commit(); pg.get_pixmap(dpi=200).save('rr_debug.png')

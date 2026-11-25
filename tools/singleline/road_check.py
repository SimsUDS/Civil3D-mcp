"""Road coverage check: PDF streets vs the drawn roads (SingleLine polylines, colour 157).

python road_check.py <query.json> [out.json]
For every PDF street inside each circuit's cloud (page 1: p1_streets_clipped.json; page 10: p10_extract.json streets,
already in the page-1 reference frame), sample every 3 ft and measure the distance to the nearest drawn road:
  < 1.5 ft  drawn as the PDF street
  < 15 ft   replaced by a road (the 7 ft offset road beside a cable)
  else      MISSING
and the reverse: drawn road stretches with no PDF street within 15 ft (EXTRA). Stretches are grouped into runs.
"""
import json, math, sys
q = json.load(open(sys.argv[1])); E = q.get("entities") or q["result"]["entities"]
T = lambda p: (24600 + (p[0] - 150) * 3, 14900 - (p[1] - 290) * 3)
P1 = [[T(p) for p in s] for s in json.load(open(r"C:/civ3dmcp/jobs/Singleline/_analysis/p1_streets_clipped.json"))["streets"]]
P10 = [[T(p) for p in s] for s in json.load(open(r"C:/civ3dmcp/jobs/Singleline/_analysis/p10_extract.json"))["streets"]]
ROADS = [[(v["x"], v["y"]) for v in e["vertices"]] for e in E
         if e["type"] == "LWPOLYLINE" and e["layer"] == "SingleLine" and e.get("colorIndex") == 157]
def segs(L): return [(a, b) for s in L for a, b in zip(s, s[1:]) if math.dist(a, b) > 0.01]
def grid(S, g=20):
    G = {}
    for a, b in S:
        for gx in range(int(min(a[0], b[0]) // g) - 1, int(max(a[0], b[0]) // g) + 2):
            for gy in range(int(min(a[1], b[1]) // g) - 1, int(max(a[1], b[1]) // g) + 2): G.setdefault((gx, gy), []).append((a, b))
    return G
def sd(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))
def near(p, G, g=20):
    return min((sd(p, a, b) for a, b in G.get((int(p[0] // g), int(p[1] // g)), [])), default=99)
def sample(S):
    for a, b in S:
        n = max(1, int(math.dist(a, b) / 3))
        for i in range(n + 1): yield (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
RG = grid(segs(ROADS))
out = {}
for name, L in (("royer_p1", P1), ("lawrence_p10", P10)):
    stat = {"drawn": 0, "replaced": 0, "missing": 0}; miss = []
    for p in sample(segs(L)):
        d = near(p, RG)
        k = "drawn" if d < 1.5 else ("replaced" if d < 15 else "missing"); stat[k] += 1
        if k == "missing": miss.append(p)
    # group missing samples into runs (within 8 ft of each other)
    runs = []
    for p in miss:
        for r in runs:
            if math.dist(r[-1], p) < 8: r.append(p); break
        else: runs.append([p])
    runs = [r for r in runs if len(r) >= 3]
    out[name] = {"stat": stat, "missing_runs": [(round(r[0][0]), round(r[0][1]), round(r[-1][0]), round(r[-1][1]), len(r) * 3) for r in runs]}
    print(name, stat, "missing runs (x0,y0,x1,y1,ft):", out[name]["missing_runs"])
PG = grid(segs(P1 + P10))
extra = [p for p in sample(segs(ROADS)) if near(p, PG) > 15]
runs = []
for p in extra:
    for r in runs:
        if math.dist(r[-1], p) < 8: r.append(p); break
    else: runs.append([p])
out["extra_runs"] = [(round(r[0][0]), round(r[0][1]), round(r[-1][0]), round(r[-1][1]), len(r) * 3) for r in runs if len(r) >= 3]
print("drawn roads with no PDF street within 15 ft:", out["extra_runs"])
if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], "w"), indent=1)

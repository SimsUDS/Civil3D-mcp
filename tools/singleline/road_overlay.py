"""Overlay of PDF streets (gray, mapped to drawing feet) on the drawn roads (red), cables (light blue) and road names.
python road_overlay.py <query.json> <out_prefix> [--win x0,y0,x1,y1]   -> <out_prefix>_p1.png / _p10.png (or one window)
"""
import json, math, sys
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
q = json.load(open(sys.argv[1])); E = q.get("entities") or q["result"]["entities"]; pre = sys.argv[2]
T = lambda p: (24600 + (p[0] - 150) * 3, 14900 - (p[1] - 290) * 3)
B = r"C:/civ3dmcp/jobs/Singleline/_analysis/"
P1 = json.load(open(B + "p1_streets_clipped.json")); P10 = json.load(open(B + "p10_extract.json"))
sheets = {"p1": [[T(p) for p in s] for s in P1["streets"]], "p10": [[T(p) for p in s] for s in P10["streets"]]}
rr = [[T(p) for p in s] for s in P1["rr"]] + [[T(p) for p in s] for s in P10["rr"]]
roads = [[(v["x"], v["y"]) for v in e["vertices"]] for e in E if e["type"] == "LWPOLYLINE" and e["layer"] == "SingleLine" and e.get("colorIndex") == 157]
cabs = [[(v["x"], v["y"]) for v in e["vertices"]] for e in E if e["type"] == "LWPOLYLINE" and e["layer"].startswith("CIRCUIT")]
misc = [[(v["x"], v["y"]) for v in e["vertices"]] for e in E if e["type"] == "LWPOLYLINE" and e["layer"] == "MISC"]
names = [e for e in E if e["type"] == "TEXT" and e.get("colorIndex") == 157]
def draw(win, out, which):
    fig, ax = plt.subplots(figsize=(22, 22 * (win[3] - win[1]) / (win[2] - win[0])))
    for s in cabs: ax.plot(*zip(*s), color="#9ecae1", lw=1.2)
    for w in which:
        for s in sheets[w]: ax.plot(*zip(*s), color="#555555", lw=0.8)
    for s in rr: ax.plot(*zip(*s), color="#bbbbbb", lw=0.5, ls=":")
    for s in misc: ax.plot(*zip(*s), color="#2ca02c", lw=1.0)
    for s in roads: ax.plot(*zip(*s), color="#d62728", lw=1.6, alpha=0.75)
    for e in names:
        p = e.get("position") or e.get("insertionPoint")
        if win[0] < p["x"] < win[2] and win[1] < p["y"] < win[3]:
            ax.text(p["x"], p["y"], e["text"], color="#d62728", fontsize=7, rotation=e.get("rotation", 0) or 0)
    ax.set_xlim(win[0], win[2]); ax.set_ylim(win[1], win[3]); ax.set_aspect("equal"); ax.grid(True, lw=0.3)
    ax.set_xticks(range(int(win[0] // 50 * 50), int(win[2]) + 1, 50)); ax.tick_params(labelsize=6)
    plt.xticks(rotation=90); plt.tight_layout(); plt.savefig(out, dpi=80); plt.close()
if "--win" in sys.argv:
    w = list(map(float, sys.argv[sys.argv.index("--win") + 1].split(","))); draw(w, pre + ".png", ["p1", "p10"])
else:
    for k in ("p1", "p10"):
        xs = [p[0] for s in sheets[k] for p in s]; ys = [p[1] for s in sheets[k] for p in s]
        draw((min(xs) - 20, min(ys) - 20, max(xs) + 20, max(ys) + 20), f"{pre}_{k}.png", [k])

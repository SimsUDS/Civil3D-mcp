"""Contact sheet of loose conductor ends (from sweep_ends.py) for a quick look.

Usage: python sweep_sheet.py <query.json> <out.png>
Each tile: 60 x 60 ft around the end; conductors (magenta), block extents (yellow), text (gray), end (red dot).
"""
import json, math, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0])
from sweep_ends import seg_dist

def loose(E, tol=0.3):
    cond = [e for e in E if e["type"] == "LWPOLYLINE" and e["layer"].startswith("CIRCUIT")]
    def _small(e):                  # structure boxes (X#/V#/M#, ~6 x 8 ft) are equipment; vault outlines are not
        ex = e["extents"]; return (ex["max"]["x"] - ex["min"]["x"]) * (ex["max"]["y"] - ex["min"]["y"]) < 150
    blocks = [e for e in E if e["type"] == "INSERT" and e.get("extents") and (e["blockName"] != "SGL_BOX" or _small(e))]
    res = []
    for i, c in enumerate(cond):
        vs = [(v["x"], v["y"]) for v in c["vertices"]]
        for p in (vs[0], vs[-1]):
            if any(j != i and any(seg_dist(p, a, b) < tol for a, b in zip(w, w[1:]))
                   for j, d in enumerate(cond) for w in [[(v["x"], v["y"]) for v in d["vertices"]]]):
                continue
            ok = False
            for b in blocks:
                ex = b["extents"]
                if ex["min"]["x"] - tol <= p[0] <= ex["max"]["x"] + tol and ex["min"]["y"] - tol <= p[1] <= ex["max"]["y"] + tol:
                    ok = True; break
            if not ok:
                res.append((c["handle"], p))
    return res

def main(path, out):
    E = json.load(open(path))["entities"]
    L = loose(E)
    n = len(L); cols = 6; rows = math.ceil(n / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(cols * 3.2, rows * 3.2))
    for k, ax in enumerate(axs.flat):
        ax.set_xticks([]); ax.set_yticks([]); ax.set_facecolor("#20242c")
        if k >= n: ax.axis("off"); continue
        h, p = L[k]; R = 30
        for e in E:
            if e["type"] == "LWPOLYLINE":
                xs = [v["x"] for v in e["vertices"]]; ys = [v["y"] for v in e["vertices"]]
                col = "#e040e0" if e["layer"].startswith("CIRCUIT") else ("#5560a0" if e.get("colorIndex") == 157 else "#bbbb55")
                ax.plot(xs, ys, color=col, lw=1.6 if e["handle"] == h else 0.8)
            elif e["type"] == "INSERT" and e.get("extents"):
                ex = e["extents"]
                ax.add_patch(plt.Rectangle((ex["min"]["x"], ex["min"]["y"]), ex["max"]["x"] - ex["min"]["x"],
                                           ex["max"]["y"] - ex["min"]["y"], fill=False, ec="#e6e600", lw=0.7))
                if abs(e["position"]["x"] - p[0]) < R and abs(e["position"]["y"] - p[1]) < R:
                    ax.text(e["position"]["x"], e["position"]["y"], e["blockName"].replace("SGL_", ""), color="#e6e600", fontsize=5)
            elif e["type"] == "TEXT" and abs(e["position"]["x"] - p[0]) < R and abs(e["position"]["y"] - p[1]) < R:
                ax.text(e["position"]["x"], e["position"]["y"], e["text"], color="#999", fontsize=5)
        ax.plot([p[0]], [p[1]], "o", color="red", ms=5)
        ax.set_xlim(p[0] - R, p[0] + R); ax.set_ylim(p[1] - R, p[1] + R); ax.set_aspect("equal")
        ax.set_title(f"{k}: {h} ({p[0]:.0f},{p[1]:.0f})", fontsize=7, color="black")
    plt.tight_layout(); plt.savefig(out, dpi=110)
    for k, (h, p) in enumerate(L): print(k, h, round(p[0], 1), round(p[1], 1))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

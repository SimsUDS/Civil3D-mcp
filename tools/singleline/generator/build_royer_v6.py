"""Royer A1 test single line traced from the PDF's vector geometry (page 1 of the Ash circuit maps).

Usage: python build_royer_v6.py <out job.json> [<query json of entities to erase first>]

Geometry: node coordinates are PDF points read from page.get_drawings(); they are mapped to the
drawing at S ft per point, so the shape (angles, bends, the Magnolia loop) follows the PDF.
Symbols are fixed-size template blocks COPIED from the template samples.
Labels sit on top of the line; roads are 7 ft off the conductor on the other side.
"""
import json, math, sys

OX, OY = 24600.0, 14900.0           # drawing-area origin (below the TEMPLATE frame)
PX0, PY0, S = 150.0, 290.0, 3.0     # PDF point origin and feet per PDF point
C1, C2 = "CIRCUIT-1", "CIRCUIT-2"
OH, UG = "SGL-OH3PH", "SGL-UG3PH"
SL, ROADCOLOR = "SingleLine", 157
H, CW, ROAD = 3.2, 2.8, 7.0          # CW: rendered width per character at 3.2 high (2.42 left labels off-centre)
DRAW_LAWRENCE = True

cr, copies, edits = [], [], []
INSERTS = []                         # every block placed: (name, x, y, rot, mirror, dyn) -- for the terminal sweep

def T(x, y):                        # PDF point -> local feet
    return ((x - PX0) * S, -(y - PY0) * S)
def P(x, y): return {"x": round(OX + x, 4), "y": round(OY + y, 4)}

def pl(pts, lt=None, layer=C1, color=None, bulges=None):
    d = {"type": "polyline", "layer": layer, "points": [P(*p) for p in pts]}
    if bulges:
        for i, b in bulges.items(): d["points"][i]["bulge"] = b
    if lt: d["linetype"] = lt
    if color is not None: d["colorIndex"] = color
    cr.append(d)

HOP = 4.0                           # hop chord in feet (Ash: 4 ft semicircle)
def pl_hopped(pts, lt, layer, hops, others):
    """Polyline with a semicircle hop (bulge +/-1, HOP ft across) wherever a PDF hop sits on it.
    hops: [(a, b, apex)] in feet; others: segments of the other conductors, used to centre the hop on the crossing."""
    m = [pts[0]]                       # merge collinear runs so a hop never straddles a leftover vertex
    for k in range(1, len(pts) - 1):
        a, b, c = m[-1], pts[k], pts[k + 1]
        ab, bc = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        la, lb = math.hypot(*ab), math.hypot(*bc)
        if la < 1e-6: continue
        ac = (c[0] - a[0], c[1] - a[1]); lc = math.hypot(*ac)
        if lb > 1e-6 and lc > 1e-6 and abs(ac[0] * ab[1] - ac[1] * ab[0]) / lc < 0.35 and ab[0] * bc[0] + ab[1] * bc[1] > 0:
            continue                   # b lies within 0.35 ft of the straight run a-c
        if lb > 1e-6 and abs(ab[0] * bc[1] - ab[1] * bc[0]) / (la * lb) < 0.05 and ab[0] * bc[0] + ab[1] * bc[1] < 0 \
                and min(la, lb) < 8:
            continue                   # out-and-back spike (a terminal shift left the old corner behind)
        m.append(b)
    pts = m + [pts[-1]]
    out, bul = [pts[0]], {}
    for p, q in zip(pts, pts[1:]):
        L = math.dist(p, q)
        if L < 1e-6: continue
        ux, uy = (q[0] - p[0]) / L, (q[1] - p[1]) / L
        here = []
        for a, b, apex in hops:
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            t = (m[0] - p[0]) * ux + (m[1] - p[1]) * uy
            off = abs((m[0] - p[0]) * uy - (m[1] - p[1]) * ux)
            ca = math.dist(a, b) or 1
            if abs(((b[0] - a[0]) * ux + (b[1] - a[1]) * uy) / ca) < 0.9: continue   # hop belongs to the line parallel to its chord
            if off > 1.5 or not (HOP / 2 < t < L - HOP / 2): continue
            # centre on the crossing conductor if one crosses the chord
            best = None
            for u, v in others:
                dx, dy = v[0] - u[0], v[1] - u[1]; den = ux * dy - uy * dx
                if abs(den) < 1e-9: continue
                tt = ((u[0] - p[0]) * dy - (u[1] - p[1]) * dx) / den
                ss = ((u[0] - p[0]) * uy - (u[1] - p[1]) * ux) / den
                if 0 <= ss <= 1 and abs(tt - t) < math.dist(a, b) / 2 + 1: best = tt; break
            if best is None: continue                                   # nothing to hop over any more
            side = (apex[0] - p[0]) * uy - (apex[1] - p[1]) * ux      # >0: apex right of travel
            here.append((best, 1.0 if side > 0 else -1.0))
        for t, bg in sorted(here):
            out.append((p[0] + ux * (t - HOP / 2), p[1] + uy * (t - HOP / 2))); bul[len(out) - 1] = bg
            out.append((p[0] + ux * (t + HOP / 2), p[1] + uy * (t + HOP / 2)))
        out.append(q)
    if len(out) < 2 or sum(math.dist(out[i], out[i + 1]) for i in range(len(out) - 1)) < 0.5: return
    pl(out, lt, layer=layer, bulges=bul)

def tx(s, cx, cy, rot=0, color=None, layer=SL):
    w = CW * len(s); a = math.radians(rot)
    ux, uy, vx, vy = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    d = {"type": "text", "layer": layer, "text": s, "height": H, "rotationDeg": round(rot, 4),
         "position": P(cx - ux * w / 2 - vx * H / 2, cy - uy * w / 2 - vy * H / 2)}
    if color is not None: d["colorIndex"] = color
    cr.append(d)

def readable(ang):
    while ang <= -90: ang += 180
    while ang > 90: ang -= 180
    return ang

def on_line(s, a, b, t=0.5, off=2.7, color=None, flip=False, layer=SL):
    """Label on top of segment a-b. flip=True puts it on the other side of the line. The text always stays readable
    (rotation in (-90, 90]; a vertical run reads bottom-to-top), never upside down (Kevin, 2026-11-25)."""
    ang = readable(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))
    r = math.radians(ang); nx, ny = -math.sin(r), math.cos(r)
    if flip and abs(ang) < 80: nx, ny = -nx, -ny   # a vertical run's label always sits LEFT, reading up (Kevin)
    tx(s, a[0] + (b[0] - a[0]) * t + nx * off, a[1] + (b[1] - a[1]) * t + ny * off, ang, color, layer)

# ---- label clearance: text rectangles vs lines already drawn (conductors, vault boxes) and other text
BOX_EDGES = []                       # extra obstacle segments in local feet (vault boxes etc.), filled by the job parts
def text_rect(s, cx, cy, rot, pad=0.6):
    w = CW * len(s) / 2 + pad; h = H / 2 + pad; a = math.radians(rot)
    ux, uy, vx, vy = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    return [(cx + sx * w * ux + sy * h * vx, cy + sx * w * uy + sy * h * vy) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
def _seg_x(p, q, r, s):
    def o(a, b, c): return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return o(p, q, r) * o(p, q, s) < 0 and o(r, s, p) * o(r, s, q) < 0
def _inside(pt, poly):
    sg = [((b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0])) > 0 for a, b in zip(poly, poly[1:] + poly[:1])]
    return all(sg) or not any(sg)
def _block_outline(name, x, y, rot, dyn):
    """Rough outline of a placed block as obstacle segments + its visual centre (for label clearance)."""
    a = math.radians(rot or 0); ca, sa = math.cos(a), math.sin(a)
    W = lambda lx, ly: (x + lx * ca - ly * sa, y + lx * sa + ly * ca)
    if name == "SGL_BOX":
        d1, d2 = dyn.get("Distance1", 5.8), dyn.get("Distance2", 7.5)
        if d2 > 14: return None, None                       # vault outline: handled by BOX_EDGES
        c = [W(-10, -7.2), W(-10 + d2, -7.2), W(-10 + d2, -7.2 + d1), W(-10, -7.2 + d1)]
    elif name in ("SGL_PH", "SGL_PH_FUSED"):
        L = 16.1 if name == "SGL_PH_FUSED" else 10.5
        c = [W(-0.5, -3.4), W(L + 0.5, -3.4), W(L + 0.5, 3.4), W(-0.5, 3.4)]   # arrow head + a little air
    elif name in ("SGL_PO_WD_JO_IN", "SGL_TRAN_BP"):
        r = 2.6 if name == "SGL_PO_WD_JO_IN" else 4.8
        c = [(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)]
    elif name == "SGL_TRAN_DE":
        c = [W(-4.5, -10.5), W(4.5, -10.5), W(4.5, 12.5), W(-4.5, 12.5)]       # box + the elbow chevrons over its feed
    elif name.startswith("SGL_PMH_PME"):
        c = [W(-3.5, -16.5), W(15.5, -16.5), W(15.5, 4), W(-3.5, 4)] if name != "SGL_PMH_PME_05" else \
            [W(-3, -19.5), W(4, -19.5), W(4, 3), W(-3, 3)]
    elif name == "SGL_TRAN_PM":
        c = [W(-6, -1), W(6, -1), W(6, 14), W(-6, 14)]
    else:
        return None, None
    cen = (sum(p[0] for p in c) / 4, sum(p[1] for p in c) / 4)
    return list(zip(c, c[1:] + c[:1])), cen
def obstacles():
    """Segments (local feet) of everything drawn so far that a label must not sit on: circuit polylines, BOX_EDGES and
    the outlines of the blocks placed so far (transformer elbows, PMEs, boxes, potheads, poles)."""
    o0 = P(0, 0); segs = list(BOX_EDGES)
    for name, x, y, rot, mir, dyn in INSERTS:
        sg, _c = _block_outline(name, x, y, rot, dyn)
        if sg: segs += sg
    for d in cr:
        if d["type"] == "polyline" and d["layer"].startswith("CIRCUIT"):
            pts = [(p["x"] - o0["x"], p["y"] - o0["y"]) for p in d["points"]]
            segs += list(zip(pts, pts[1:]))
    return segs
def placed_text_rects():
    o0 = P(0, 0); out = []
    for d in cr:
        if d["type"] == "text":
            a = math.radians(d.get("rotationDeg", 0)); w = CW * len(d["text"]); h = d.get("height", H)
            x, y = d["position"]["x"] - o0["x"], d["position"]["y"] - o0["y"]
            cx = x + math.cos(a) * w / 2 - math.sin(a) * h / 2; cy = y + math.sin(a) * w / 2 + math.cos(a) * h / 2
            out.append(text_rect(d["text"], cx, cy, d.get("rotationDeg", 0), pad=0.2))
    return out
def n_hits(rect, segs, rects, host=None):
    n = 0
    for u, v in segs:
        if host and math.dist(u, host[0]) + math.dist(v, host[1]) < 0.05: continue
        if _inside(u, rect) or _inside(v, rect) or any(_seg_x(u, v, a, b) for a, b in zip(rect, rect[1:] + rect[:1])): n += 1
    for r in rects:
        if any(_inside(p, rect) for p in r) or any(_inside(p, r) for p in rect): n += 1
    return n

def offset(pts, d):
    """Offset an open polyline by d (positive = left of travel), mitred."""
    out = []
    for i, p in enumerate(pts):
        ns = []
        for j in (i - 1, i):
            if 0 <= j < len(pts) - 1:
                (x1, y1), (x2, y2) = pts[j], pts[j + 1]
                L = math.hypot(x2 - x1, y2 - y1) or 1
                ns.append((-(y2 - y1) / L, (x2 - x1) / L))
        nx = sum(n[0] for n in ns); ny = sum(n[1] for n in ns)
        L = math.hypot(nx, ny) or 1; nx, ny = nx / L, ny / L
        cosh = max(0.5, nx * ns[0][0] + ny * ns[0][1])
        out.append((p[0] + nx * d / cosh, p[1] + ny * d / cosh))
    return out

def extend(pts, a=0.0, b=0.0):
    """Stretch the first/last segment by a / b feet."""
    pts = list(pts)
    def ext(p, q, L):
        dx, dy = p[0] - q[0], p[1] - q[1]; n = math.hypot(dx, dy) or 1
        return (p[0] + dx / n * L, p[1] + dy / n * L)
    if a: pts[0] = ext(pts[0], pts[1], a)
    if b: pts[-1] = ext(pts[-1], pts[-2], b)
    return pts

def road(cond_pts, side, name=None, seg=0, t=0.5, a=0.0, b=0.0):
    """Road 7 ft off a conductor run; side +1 = left of travel, -1 = right, "auto" = the side the PDF street is on
    (taken from the PDF street lines this road replaces). Name sits on top of the road."""
    if side == "auto":
        side = street_side(cond_pts)
    r = extend(offset(cond_pts, side * ROAD), a, b)
    ROADS.append(r)
    pl(r, layer=SL, color=ROADCOLOR)
    if name:
        on_line(name, r[seg], r[seg + 1], t=t, color=ROADCOLOR)

SF = json.load(open(r"C:/civ3dmcp/jobs/Singleline/RoyerTest/p1_streets_final.json"))
ROADS = []

def nearest_on(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return (a[0] + t * dx, a[1] + t * dy)

def street_side(path):
    """+1 / -1: which side of `path` the replaced (dropped) PDF street lines lie on."""
    tot = 0.0
    for a, b in SF["dropped"]:
        m = T((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        best = None
        for p, q in zip(path, path[1:]):
            n = nearest_on(m, p, q); d = math.dist(m, n)
            if best is None or d < best[0]: best = (d, p, q)
        if best and best[0] < 30:
            d, p, q = best
            cross = (q[0] - p[0]) * (m[1] - p[1]) - (q[1] - p[1]) * (m[0] - p[0])
            tot += 1 if cross > 0 else -1
    return 1 if tot >= 0 else -1

SRC = {
    "SGL_SUB_SOURCE": "70DB", "SGL_BOX": "708C", "SGL_SW_3W_RAG": "6E07", "SGL_TRAN_FUSED": "6C98", "SGL_CAP": "6D36", "SGL_TRAN": "6C93", "SGL_LBE": "6D2B",
    "SGL_PH": "7078", "SGL_PH_FUSED": "707D", "SGL_PO_WD_JO_IN": "6B4B", "SGL_SW_PO_OPEN": "6BF3",
    "SGL_PO_SW": "6BD7", "SGL_SYM_ARR_DC": "6B46", "SGL_TRAN_PM_SW_FUSED": "6D13", "SGL_OH_FI": "6B8C",
    ("SGL_TRAN_DE", "LB-ELBOWS-ON"): "6D09", ("SGL_TRAN_DE", "LB-ELBOWS-OFF"): "7889",
    "SGL_SW_4W_RAG": "6E16", "SGL_SW_3W_RAM": "6E5D", "SGL_SW_4W_RAM": "6E6C", "SGL_SW_5W_RAM": "6E7D", "SGL_SW_5W_RAG": "6E27", "SGL_JBAR_4W": "7011", "SGL_JBAR_3W": "700C",
    "SGL_SW_3W": "6F93", "SGL_BURD_SW_FUSED": "6F89", "SGL_PMH_PME_05": "6D83", "SGL_TRAN_BP": "6C9D",
    "SGL_CG": "70E5", "SGL_PMH_PME_06": "6D8E", "SGL_PMH_PME_09": "6DA6", ("SGL_PMH_PME_01", "LB-ELBOWS-RIGHT"): "79EF",
    "SGL_PMH_PME_01": "6D58", "SGL_SUB_CUST_PP": "70EA", "SGL_FERRO": "70F6", "SGL_BLF": "6B6F",
    ("SGL_TRAN_PM", "LB-ELBOWS-OFF"): "77AC", "SGL_TRAN_PM": "6CE6", "SGL_TRAN_PM_1PH_DEDF_NFUSED": "6CA2", "SGL_SYS_PAR": "710A", "SGL_SIG_CRI": "7105", "SGL_SW_CL_POLE": "6BEE", "SGL_CAPBANK": "6B50",
}
TPL = {e["handle"]: e for e in json.load(open(r"C:/civ3dmcp/jobs/Singleline/_analysis/template_v2.json"))["entities"]}

def ins(name, x, y, rot=0.0, layer=SL, attrs=None, dyn=None, mirror=False):
    """mirror=True flips the block about the vertical through its insertion (Ash: x-scale -40), e.g. an FI pennant
    that points left; the copy keeps attribute text readable (MIRRTEXT 0)."""
    vis = (dyn or {}).get("Visibility1")
    h = SRC.get((name, vis)) or SRC[name]
    s = TPL[h]; assert s["blockName"] == name
    cid = f"b{len(copies)}"; t = P(x, y)
    copies.append({"id": cid, "handles": [h], "dx": round(t["x"] - s["position"]["x"], 4), "dy": round(t["y"] - s["position"]["y"], 4)})
    if mirror: copies[-1]["mirrorX"] = t["x"]
    INSERTS.append((name, x, y, rot, mirror, dyn or {}))
    e = {"ref": f"{cid}:{h}"}
    if rot: e["rotationDeg"] = round(rot % 360, 4)
    if layer != s["layer"]: e["layer"] = layer
    if attrs: e["attributes"] = attrs
    if dyn: e["dynamicProperties"] = dyn
    if len(e) > 1: edits.append(e)

def box(p, rot=0.0, d1=5.8, d2=7.5):
    """Centre an SGL_BOX (grows from local (-10,-7.2); D2 width, D1 height) on p, rotated."""
    cx, cy = -10 + d2 / 2, -7.2 + d1 / 2; a = math.radians(rot)
    ins("SGL_BOX", p[0] - (cx * math.cos(a) - cy * math.sin(a)), p[1] - (cx * math.sin(a) + cy * math.cos(a)),
        rot=rot, dyn={"Distance1": d1, "Distance2": d2})

def pothead(tip, ang_to_tip, fused=False):
    """Pothead with its tip (UG side) at `tip`, pointing in direction ang_to_tip (deg). Returns the OH-side point."""
    L = 16.1 if fused else 10.5
    a = math.radians(ang_to_tip)
    ins_pt = (tip[0] - L * math.cos(a), tip[1] - L * math.sin(a))
    ins("SGL_PH_FUSED" if fused else "SGL_PH", *ins_pt, rot=ang_to_tip)
    return ins_pt

def above(s, p, dy=7.0): tx(s, p[0], p[1] + dy)
def pole(p, num): ins("SGL_PO_WD_JO_IN", *p); above(num, p)

# =========================================================== substation and gear switch V5524638 / GS4801
sub = T(163.9, 309.0)
ins("SGL_SUB_SOURCE", *sub)
tx("FULLERTON", sub[0] + 20.0, sub[1] + 2.6); tx("SUB", sub[0] + 20.0, sub[1] - 2.6)   # beside the sub, clear of the feeders coming in above it
w2x = T(189.75, 0)[0]; wy = T(0, 314.2)[1]
sw = (w2x - 7.48, wy)                            # RAG ways at +3.7 / +7.48 / +11.26 (exact, measured in Ash)
ins("SGL_BOX", sw[0] - 8.6, sw[1] - 4.8, dyn={"Distance1": 33.6, "Distance2": 39.7})
ins("SGL_SW_3W_RAG", *sw, dyn={"Angle": 0, "Angle2": 0, "Angle3": 0})
ins("SGL_TRAN_FUSED", sw[0] + 3.7, sw[1], rot=270)
tx("V5524638", sw[0] + 1.2, sw[1] + 25.5); tx("GS4801", sw[0] + 7.48, sw[1] + 19.0)   # centred over the ways ("1 2 3"), clear above them
w2, w3 = sw[0] + 7.48, sw[0] + 11.26
hop_y = T(0, 326.7)[1]
# sub cable: way 3 down, west over way 2 (polyline hop, as in Ash), to the sub
pl([(w3, wy), (w3, hop_y), (w2 + 2, hop_y), (w2 - 2, hop_y), (sub[0], hop_y), (sub[0], sub[1] - 4.8)], UG, bulges={2: 1.0})
on_line("1000 CLP", (sub[0], hop_y), (w2 - 2, hop_y))
# way 2 down to riser 1748173E, OH to pole 1748175E
pole_n = T(200.7, 333.8)
oh_pt = pothead((w2, hop_y - 9), 90)
pl([(w2, wy), (w2, hop_y - 9)], UG)
tx("1748173E", w2 - 14, oh_pt[1] + 4)
pl([oh_pt, (w2, pole_n[1]), pole_n], OH)

# =========================================================== trunk down S Lemon St
J1 = T(200.6, 369.7)
trunk = [pole_n, J1] + [T(*q) for q in [(201.1, 447.6), (201.8, 492.3), (202.9, 518.9), (204.0, 541.1),
                                        (204.8, 573.8), (205.8, 607.1), (206.1, 636.4), (206.1, 642.8)]]
pl(trunk, OH)
pole(pole_n, "1748175E")
on_line("336 A", pole_n, J1, flip=True)
on_line("653 A", trunk[3], trunk[4], flip=True)
on_line("653 A", trunk[7], trunk[8], flip=True)
road(trunk, -1, "S LEMON ST.", seg=2, a=25, b=95)       # west side (right of southbound travel)

# FI00417 (east, pointing at the trunk) and riser 4008195E
fi_y = T(0, 640.8)[1]
ins("SGL_OH_FI", trunk[-1][0] + 1.5, fi_y + 18, attrs={"STRUCTURE_NUMBER": "", "FI_NUMBER": "FI00417", "CURRENT_RATING": "ADAPTABLE"})
ph_tip = T(206.1, 650.1)
pothead(ph_tip, -90)
tx("4008195E", ph_tip[0] + 14, ph_tip[1] + 3)
box_v36 = T(205.8, 660.2); corner = T(206.0, 674.7); box_v35 = T(251.5, 675.1)
ph2_tip = T(273.8, 674.4)
pl([ph_tip, (ph_tip[0], box_v36[1]), (ph_tip[0], corner[1]), (box_v35[0], corner[1]), (ph2_tip[0], corner[1])], UG)
box((ph_tip[0], box_v36[1])); tx("V5633636", ph_tip[0] + 14, box_v36[1])
box((box_v35[0], corner[1])); above("V5633635", (box_v35[0], corner[1]), dy=-7.0)   # below: E Orangethorpe road runs above
on_line("1000 JCN", (ph_tip[0], box_v36[1] - 3), (ph_tip[0], ph_tip[1]))
on_line("1000 JCN", (ph_tip[0], corner[1]), (box_v35[0], corner[1]))
on_line("1000 JCN", (box_v35[0], corner[1]), (ph2_tip[0], corner[1]))
oh2 = pothead((ph2_tip[0], corner[1]), 180)
above("4126229E", (oh2[0] + 6, corner[1]), dy=-7.0)   # below: the road is on the north side
east_end = T(539.7, 674.4)
orange = [oh2, (east_end[0], corner[1])]
pl(orange, OH)
on_line("336 A", orange[0], orange[1], t=0.15); on_line("336 A", orange[0], orange[1], t=0.75)
ins("SGL_SYM_ARR_DC", east_end[0], corner[1], layer=C1)          # leaves the cloud
road([(ph_tip[0], corner[1]), (east_end[0] + 31, corner[1])], +1, "E ORANGETHORPE AVE.", t=0.45, a=20, b=10)   # north: the PDF street's side (Kevin, 2026-11-25)
EDGE_BANDS = [(ROADS[-1], +1, 45.0)]   # this road replaces the PDF edge lines up to 45 ft on its north side

# =========================================================== east along Valencia
val = [J1] + [T(*q) for q in [(227.45, 369.35), (255.25, 368.35), (277.1, 367.6), (316.55, 365.35),
                              (342.85, 364.35), (381.85, 364.15), (406.6, 364.0), (430.2, 363.7)]]
pl(val, OH)
for q, n in zip([val[1], val[2], val[4], val[5], val[6]], ["4783001E", "923665E", "2286148E", "2286247E", "2286245E"]):
    pole(q, n)
on_line("336 A", val[3], val[4], t=0.4)
# no offset road here: the run sits between Patterson Wy and Valencia Dr, both drawn from the PDF below

# =========================================================== north on Lawrence to PS 0906 and the Lawrence tie
J2 = val[3]
ps_pt = T(278.1, 301.0)
law_ang = math.degrees(math.atan2(ps_pt[1] - J2[1], ps_pt[0] - J2[0]))
ua = (math.cos(math.radians(law_ang)), math.sin(math.radians(law_ang)))
pl([J2, (ps_pt[0] - ua[0] * 8, ps_pt[1] - ua[1] * 8)], OH)
ins("SGL_SW_PO_OPEN", *ps_pt, rot=law_ang)
_u = (math.cos(math.radians(law_ang)), math.sin(math.radians(law_ang))); _n = (-_u[1], _u[0])
_pdf = T(264.1, 303.6); _sd = 1 if (_pdf[0] - ps_pt[0]) * _n[0] + (_pdf[1] - ps_pt[1]) * _n[1] > 0 else -1
ins("SGL_PO_SW", ps_pt[0] + _n[0] * 13.0 * _sd, ps_pt[1] + _n[1] * 13.0 * _sd,          # 13 ft beside the switch (Ash)
    attrs={"DEVICE_NUMBER": "0906", "POLE_NUMBER": "2029249E"}, dyn={"Visibility1": "PS"})
# Lawrence is drawn now, so no tie arrow here: Lawrence's own line continues north from the switch.
if not DRAW_LAWRENCE:
    ins("SGL_SYM_ARR_DC", ps_pt[0] + ua[0] * 8, ps_pt[1] + ua[1] * 8, rot=law_ang, layer=C2)
    tx("LAWRENCE", ps_pt[0] + 22, ps_pt[1] + 24); tx("FULLERTON", ps_pt[0] + 22, ps_pt[1] + 18.5)
road([J2, ps_pt], -1, "S LAWRENCE AVE.", t=0.45, a=-7, b=-14)

# =========================================================== 1956133E riser and the 1/0 JCN loop
tip1 = T(406.6, 371.5)
pothead(tip1, -90)
above("1956133E", val[7])
b166 = T(393.25, 384.7); b165 = T(444.2, 385.0)
runA = [tip1, T(406.6, 377.3), T(393.4, 377.3), b166, T(413.6, 385.3), b165]
runB = [b165, T(451.5, 384.6), T(456.2, 391.7), T(462.5, 402.0), T(465.1, 406.7), T(468.3, 412.9),
        T(453.9, 412.9), T(453.9, 423.2)]
p377 = T(463.95, 423.2)                       # P5445377 A/B bar
A = (p377[0] - 3.9, p377[1]); B = (p377[0] + 3.9, p377[1])
runB.append(A)
b164 = T(477.25, 450.75); b163 = T(432.75, 527.2); b162 = T(491.15, 478.5)
runC = [B, T(475.6, 429.2), T(477.8, 435.6), T(479.6, 440.6), T(481.4, 447.2), b164]
runD = [b164, T(472.5, 456.2), T(463.5, 465.3), T(455.3, 473.4), T(451.6, 479.0), T(446.3, 486.8),
        T(437.8, 492.4), T(431.8, 493.3), (T(431.8, 0)[0], b163[1])]
runE = [(T(431.8, 0)[0], b163[1]), (T(434.9, 0)[0], b163[1]), T(434.8, 520.1), T(437.9, 518.6), T(440.5, 513.8),
        T(443.3, 511.5), T(447.9, 508.8), T(454.6, 507.5), T(464.1, 507.3), T(466.7, 506.7), T(472.3, 502.1),
        T(474.9, 496.3), T(478.4, 491.8), T(483.0, 486.6), b162]
feed161 = T(492.7, 499.2)
runF = [b162, T(495.7, 482.0), T(496.3, 484.0), T(496.3, 494.9), T(492.7, 494.9), feed161]
for r in (runA + runB[1:], runC + runD[1:] + runE[1:] + runF[1:]):
    pl(r, UG)
box(b166); tx("X5640166", b166[0] - 16, b166[1] + 6)
box(b165); above("X5640165", b165)
ins("SGL_TRAN_PM_SW_FUSED", *p377, dyn={"Angle2": math.pi, "Visibility1": "LB-ELBOWS-ALL"})
above("P5445377", (p377[0] + 4, p377[1]), 11)
box(b164, 45); tx("X5640164", b164[0] - 18, b164[1] - 3)
box(b163); tx("X5640163", b163[0] + 17, b163[1] - 2)
box(b162, 45); above("X5640162", b162, 8)
ins("SGL_TRAN_DE", feed161[0], feed161[1] - 6, dyn={"Visibility1": "LB-ELBOWS-ON"})
tx("P5640161", feed161[0] - 17, feed161[1] - 14)
on_line("1/0 JCN", runA[2], runA[3], flip=True)
on_line("1/0 JCN", b166, runA[4], t=0.6)
on_line("1/0 JCN", runA[4], b165, t=0.5)
on_line("1/0 JCN", runB[5], runB[6], t=0.5)
on_line("1/0 JCN", runB[2], runB[3])
on_line("1/0 JCN", runC[2], runC[3], flip=True)
on_line("1/0 JCN", runD[2], runD[3])
on_line("1/0 JCN", runD[7], runD[8], flip=True)
on_line("1/0 JCN", runE[6], runE[8])
on_line("1/0 JCN", runE[11], runE[13])
on_line("1/0 JCN", runF[2], runF[3], flip=True)
# Roads follow the street, not the cable's jogs (the P5445377 detour and the U at X5640163 are skipped)
magnolia = [b166, runA[4], b165] + runB[1:5] + runC[1:5] + [b164] + runD[1:7]
road(magnolia, "auto", "MAGNOLIA VIA.", seg=0, t=0.55, a=14)
road(runE[2:10], "auto", "N LEMON VIA.", seg=5, t=0.5, a=8)
road(runE[9:], "auto", "CHERRY VIA.", seg=2, t=0.5, b=8)

# =========================================================== 441034E fused riser to P5092800
tip2 = T(430.2, 371.9)
pothead(tip2, -90, fused=True)
above("441034E", val[8])
feed92 = T(437.5, 371.9)
pl([tip2, (tip2[0], feed92[1]), (feed92[0], feed92[1])], UG)
ins("SGL_TRAN_DE", feed92[0] + 6, feed92[1], rot=90, dyn={"Visibility1": "LB-ELBOWS-OFF"})
above("P5092800", (feed92[0] + 10, feed92[1]), 8)

# =========================================================== streets and railroad from the PDF (inside the cloud)
# p1_streets_final.json: PDF street lines clipped to the red cloud, minus the ones the 7 ft conductor roads replace,
# plus street-name positions snapped to their street (names read off the map).
# Cross streets that ended on a replaced street get their end snapped onto the nearest 7 ft road.
dangling = {(ci, end) for ci, end in SF["dangling"]}
# A street end hangs when it touches no other drawn street and sits on a dropped (replaced) PDF street; it is carried
# along its own direction onto the road that replaced that street (Kevin 2026-11-25, E Orangethorpe moved north: ends
# on the far edge were left 20-30 ft short, and nearest-point snapping made diagonals).
_DROP_T = [(T(*a), T(*b)) for a, b in SF["dropped"]]
_ST_T = [[T(*q) for q in ch] for ch in SF["streets"]]
# street pieces running along a replacing road inside its edge band are the replaced street's own edge lines: cut them
# out (the polylines split there) and remember the cut ends, which then hang and are carried onto the road
def _ang(a, b): return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
def _dang(a, b):
    d = abs(a - b); return min(d, 180 - d)
def _in_band(a, b):
    for r, sd_, w in EDGE_BANDS:
        for u, v in zip(r, r[1:]):
            L = math.dist(u, v)
            if L < 1 or _dang(_ang(a, b), _ang(u, v)) > 8: continue
            ux, uy = (v[0] - u[0]) / L, (v[1] - u[1]) / L
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            t = (m[0] - u[0]) * ux + (m[1] - u[1]) * uy; off = ((m[0] - u[0]) * -uy + (m[1] - u[1]) * ux) * sd_
            if -1 < t < L + 1 and 0 < off < w: return True
    return False
_cut, CUT_ENDS = [], []
for pts in _ST_T:
    run = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) > 0.5 and _in_band(a, b):
            if len(run) > 1: _cut.append(run)
            CUT_ENDS += [a, b]; run = [b]
        else: run.append(b)
    if len(run) > 1: _cut.append(run)
_ST_T = _cut
_DROP_T += [(CUT_ENDS[i], CUT_ENDS[i + 1]) for i in range(0, len(CUT_ENDS), 2)]
def _on_any(p, segs, tol):
    return any(math.dist(p, nearest_on(p, a, b)) < tol for a, b in segs)
def _ray_hit(p, d, maxd=45):
    best = None
    for r in ROADS:
        for a, b in zip(r, r[1:]):
            ex, ey = b[0] - a[0], b[1] - a[1]; den = d[0] * ey - d[1] * ex
            if abs(den) < 1e-9: continue
            t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den; u = ((a[0] - p[0]) * d[1] - (a[1] - p[1]) * d[0]) / den
            if -0.5 < t < maxd and -0.01 <= u <= 1.01 and (best is None or abs(t) < abs(best[0])): best = (t, (p[0] + d[0] * t, p[1] + d[1] * t))
    return best
_others = lambda ci: [(a, b) for cj, o in enumerate(_ST_T) if cj != ci for a, b in zip(o, o[1:])]
for ci, pts in enumerate(_ST_T):
    pts = list(pts); oth = None
    for i in (0, -1):
        q = pts[i]; nb = next((x for x in (pts[1:] if i == 0 else pts[-2::-1]) if math.dist(x, q) > 1), None)
        if nb is None or not _on_any(q, _DROP_T, 1.0): continue
        if oth is None: oth = _others(ci)
        if any(_on_any(q, list(zip(r, r[1:])), 0.5) for r in ROADS): continue   # already on a road
        # (no "touches another street" test: the out-and-back PDF polylines split into twins that touch each other)
        L = math.dist(q, nb); d = ((q[0] - nb[0]) / L, (q[1] - nb[1]) / L)
        h = _ray_hit(q, d) or _ray_hit(q, (-d[0], -d[1]), 12)
        if h: pts[i] = h[1]
        else:
            best = min(((math.dist(q, nearest_on(q, a, b)), nearest_on(q, a, b)) for r in ROADS for a, b in zip(r, r[1:])), default=None)
            if best and best[0] < 30: pts[i] = best[1]
    pl(pts, layer=SL, color=ROADCOLOR)
# Railroads: the PDF's two close rails become ONE centerline with linetype RR (rr_center2.py)
RR = [[T(*q) for q in ch] for ch in SF["rr_center"]]
RR_LABELS = []
for l in SF["labels"]:
    if l["rr"]:
        a, b = T(*l["a"]), T(*l["b"]); RR_LABELS.append((l["name"], (a[0] + (b[0] - a[0]) * l["t"], a[1] + (b[1] - a[1]) * l["t"])))
    else:
        on_line(l["name"], T(*l["a"]), T(*l["b"]), t=l["t"], color=ROADCOLOR)

def rr_detour(ch, boxes):
    """Railroad stretch that runs through a vault box is bowed round it (Ash keeps the RR clear of every vault).
    Goes over the top (clear of the V-number) or under the bottom (clear of tie names), whichever is nearer."""
    for _v, x0, y0, x1, y1, tied in boxes:
        m, ramp = 6.0, 18.0
        cut = [i for i, p in enumerate(ch) if x0 - m <= p[0] <= x1 + m]
        def y_at(x):
            for p, q in zip(ch, ch[1:]):
                if min(p[0], q[0]) <= x <= max(p[0], q[0]) and abs(q[0] - p[0]) > 1e-6:
                    return p[1] + (q[1] - p[1]) * (x - p[0]) / (q[0] - p[0])
        yc = y_at((x0 + x1) / 2)
        if yc is None or not (y0 - 2 < yc < y1 + 6): continue
        y_up, y_dn = y1 + 11.0, y0 - (17.0 if tied else 6.0)
        yd = y_up if abs(y_up - yc) <= abs(yc - y_dn) else y_dn
        xa, xb = x0 - m - ramp, x1 + m + ramp
        ya, yb = y_at(xa), y_at(xb)
        if ya is None or yb is None: continue
        left = [p for p in ch if p[0] < xa]; right = [p for p in ch if p[0] > xb]
        rev = ch[0][0] > ch[-1][0]
        if rev: ch = ch[::-1]; left, right = [p for p in ch if p[0] < xa], [p for p in ch if p[0] > xb]
        ch = left + [(xa, ya), (x0 - m, yd), (x1 + m, yd), (xb, yb)] + right
        if rev: ch = ch[::-1]
    return ch

def draw_rr(boxes=()):
    rr = [rr_detour(ch, boxes) for ch in RR]
    for ch in rr:
        pl(ch, lt="RR", layer="MISC")
    for name, p in RR_LABELS:
        _, u, v = min(((math.dist(p, nearest_on(p, u, v)), u, v) for ch in rr for u, v in zip(ch, ch[1:]) if math.dist(u, v) > 3),
                      key=lambda z: z[0])
        L2 = (u[0] - v[0]) ** 2 + (u[1] - v[1]) ** 2
        t = max(0.1, min(0.9, ((p[0] - u[0]) * (v[0] - u[0]) + (p[1] - u[1]) * (v[1] - u[1])) / L2))
        on_line(name, u, v, t=t, off=6.5, layer="MISC")

# =========================================================== Lawrence (page 10) and its streets
if DRAW_LAWRENCE:
    exec(open(r"C:/civ3dmcp/jobs/Singleline/RoyerTest/lawrence_part.py").read())
    P1ALL = json.load(open(r"C:/civ3dmcp/jobs/Singleline/_analysis/p1_streets_clipped.json"))["streets"]
    grid1 = {}
    for a, b in P1ALL:
        for t in (0, 0.5, 1):
            q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            grid1.setdefault((int(q[0] // 3), int(q[1] // 3)), []).append((a, b))
    def on_p1(a, b):
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for u, v in grid1.get((int(m[0] // 3) + dx, int(m[1] // 3) + dy), []):
                    if math.dist(m, nearest_on(m, u, v)) < 1.0: return True
        return False
    dropped_ends = [p for si, (a, b) in enumerate(LW["streets"]) if si in LDROP for p in (a, b)]
    # test the pieces in ~5 ft lengths (1.7 pt): a piece only partly covered by Royer's sheet keeps its uncovered
    # part (S Lemon south of E Santa Fe lost 30 ft when the whole piece went with its midpoint)
    new = []; L_CUT = []
    for si, (a, b) in enumerate(LW["streets"]):
        if si in LDROP or math.dist(a, b) <= 0.3: continue
        n_ = max(1, int(math.dist(a, b) / 1.7))
        for i_ in range(n_):
            p_ = (a[0] + (b[0] - a[0]) * i_ / n_, a[1] + (b[1] - a[1]) * i_ / n_)
            q_ = (a[0] + (b[0] - a[0]) * (i_ + 1) / n_, a[1] + (b[1] - a[1]) * (i_ + 1) / n_)
            if not on_p1(p_, q_):
                if _in_band(T(*p_), T(*q_)): L_CUT.extend([T(*p_), T(*q_)]); continue   # an edge of a street a Royer road replaced
                new.append((tuple(p_) if i_ else tuple(a), tuple(q_) if i_ + 1 < n_ else tuple(b)))
    def snap_end(q):                       # a street end that met a replaced street -> onto the nearest 7 ft road
        f = T(*q)
        if any(math.dist(f, c_) < 1.0 for c_ in L_CUT):     # met a cut edge line: carry it along itself onto the road
            return f                                          # (done after chaining, where its direction is known)
        cand = [nearest_on(f, u, v) for r in ROADS_L for u, v in zip(r, r[1:])]
        n = min(cand, key=lambda z: math.dist(z, f), default=None)
        if n is None: return f
        if any(math.dist(q, d) < 1.0 for d in dropped_ends): return n if math.dist(n, f) < 30 else f
        return n if math.dist(n, f) < 12 else f   # T-junction onto a replaced street's edge (E Glenwood -> Berkeley)
    # chain end-to-end pieces into polylines
    def kq(p): return (round(p[0] * 2), round(p[1] * 2))
    ends = {}
    for i, (a, b) in enumerate(new):
        ends.setdefault(kq(a), []).append(i); ends.setdefault(kq(b), []).append(i)
    used = [False] * len(new)
    for i in range(len(new)):
        if used[i]: continue
        used[i] = True; ch = [new[i][0], new[i][1]]
        for fwd in (True, False):
            while True:
                tip = ch[-1] if fwd else ch[0]
                nxt = [j for j in ends.get(kq(tip), []) if not used[j]]
                if not nxt: break
                j = nxt[0]; used[j] = True; a, b = new[j]
                o = b if kq(a) == kq(tip) else a
                ch.append(o) if fwd else ch.insert(0, o)
        pts = [T(*q) for q in ch]; pts[0] = snap_end(ch[0]); pts[-1] = snap_end(ch[-1])
        for i_ in (0, -1):
            q_ = pts[i_]
            if not (any(math.dist(q_, c_) < 1.0 for c_ in L_CUT) or _on_any(q_, _DROP_T, 1.0)): continue
            nb_ = next((x for x in (pts[1:] if i_ == 0 else pts[-2::-1]) if math.dist(x, q_) > 1), None)
            if nb_ is None: continue
            L_ = math.dist(q_, nb_); d_ = ((q_[0] - nb_[0]) / L_, (q_[1] - nb_[1]) / L_)
            h_ = _ray_hit(q_, d_) or _ray_hit(q_, (-d_[0], -d_[1]), 12)
            if h_: pts[i_] = h_[1]
        k_ = 1
        while k_ < len(pts) - 1:                     # drop the 5 ft test-piece joints that sit on a straight line
            a_, b_, c_ = pts[k_ - 1], pts[k_], pts[k_ + 1]; L_ = math.dist(a_, c_)
            if L_ > 1e-6 and abs((c_[0] - a_[0]) * (b_[1] - a_[1]) - (c_[1] - a_[1]) * (b_[0] - a_[0])) / L_ < 0.15                     and (b_[0] - a_[0]) * (c_[0] - b_[0]) + (b_[1] - a_[1]) * (c_[1] - b_[1]) > 0: pts.pop(k_)
            else: k_ += 1
        pl(pts, layer=SL, color=ROADCOLOR)

draw_rr(VAULT_BOXES if DRAW_LAWRENCE else ())

# =========================================================== final sweep: every cable end lands on equipment
# Terminals in each block's own frame (measured in Ash, block_study.json). A conductor end that touches nothing (no other
# conductor, no terminal) is pulled onto the nearest FREE terminal within 25 ft, closest pair first; the last straight
# run moves with it so the line stays square. 1-phase BURD/PM dots (SGL_TRAN_BP) take the cable on their 4.8 ft edge.
TERM_LOCAL = {
    "SGL_PH": [(0, 0), (10.5, 0)], "SGL_PH_FUSED": [(0, 0), (16.1, 0)], "SGL_BLF": [(-5, 0), (5, 0)],
    "SGL_SW_CL_POLE": [(-13.5, 0), (13.5, 0)], "SGL_SW_PO_OPEN": [(-8, 0), (8, 0)], "SGL_BURD_SW_FUSED": [(-10, 0), (10, 0)],
    "SGL_PMH_PME_05": [(0, 0), (0, -16.31)], "SGL_PMH_PME_01": [(0, 0), (12, 0)],
    "SGL_PMH_PME_06": [(0, 0), (0, -12), (8, -12)], "SGL_PMH_PME_09": [(0, 0), (8, -12)],
    "SGL_TRAN_PM_1PH_DEDF_NFUSED": [(-5.72, 0.02), (6.28, 0.02)],
    "SGL_PO_WD_JO_IN": [(0, 0)],
    "SGL_TRAN": [(0, 0)],              # tap transformer on a short stub (J496 leg 3)
    # switch ways (y = 0, exact Ash x) and junction legs (y = -5.29): cables end on these too
    "SGL_SW_3W_RAG": [(3.7, 0), (7.48, 0), (11.26, 0)], "SGL_SW_4W_RAG": [(3.7, 0), (7.48, 0), (11.26, 0), (15.04, 0)],
    "SGL_SW_3W_RAM": [(0, 0), (3.6, 0), (7.2, 0)], "SGL_SW_4W_RAM": [(0, 0), (3.47, 0), (7.13, 0), (10.6, 0)],
    "SGL_SW_5W_RAM": [(0, 0), (3.81, 0), (7.41, 0), (11.01, 0), (14.61, 0)],
    "SGL_JBAR_3W": [(-0.09, -5.29), (3.91, -5.29), (7.91, -5.29)], "SGL_JBAR_4W": [(-0.07, -5.29), (3.33, -5.29), (7.17, -5.29), (10.59, -5.29)],
    "SGL_TRAN_PM": [(0, 12)],          # 3-phase pad: feed 12 ft along its axis (Ash; P5528419 r90)        # an overhead run ends at its pole (the line passes through poles otherwise)
}
def _terms(owners=False):
    pts, dots, own = [], [], []
    for ii, (name, x, y, rot, mir, dyn) in enumerate(INSERTS):
        if name == "SGL_TRAN_BP": dots.append((x, y, 4.8)); continue
        if name == "SGL_SUB_SOURCE": dots.append((x, y, 5.0)); continue      # cables end on the sub circle's edge
        loc = TERM_LOCAL.get(name)
        if name == "SGL_TRAN_DE": loc = [(0, 4.0 if "OFF" in str(dyn.get("Visibility1", "")) else 6.0)]
        if not loc: continue
        a = math.radians(rot or 0)
        for lx, ly in loc:
            lx = -lx if mir else lx
            pts.append((x + lx * math.cos(a) - ly * math.sin(a), y + lx * math.sin(a) + ly * math.cos(a))); own.append(ii)
    return (pts, dots, own) if owners else (pts, dots)
def _segdist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))
def _small_boxes():
    """(centre, inner radius) of every structure box (SGL_BOX up to 14 ft wide; wider ones are vault outlines)"""
    out = []
    for name, x, y, rot, mir, dyn in INSERTS:
        if name != "SGL_BOX": continue
        d1, d2 = dyn.get("Distance1", 5.8), dyn.get("Distance2", 7.5)
        if d2 > 14: continue
        a_ = math.radians(rot or 0)
        out.append(((x + (-10 + d2 / 2) * math.cos(a_) - (-7.2 + d1 / 2) * math.sin(a_),
                     y + (-10 + d2 / 2) * math.sin(a_) + (-7.2 + d1 / 2) * math.cos(a_)), min(d1, d2) / 2 + 0.3))
    return out
JOG_SAVED = []
MOVABLE = ("SGL_TRAN_DE", "SGL_PH", "SGL_PH_FUSED", "SGL_TRAN_FUSED", "SGL_TRAN", "SGL_TRAN_PM", "SGL_BURD_SW_FUSED",
           "SGL_TRAN_PM_1PH_DEDF_NFUSED")
def _shift_owner(t, off, terms, towner, touched, d, lim=2.5):
    """Slide the block owning terminal t by off (< lim ft) when nothing else is wired to its other terminals; blocks
    sitting on those terminals (BS6094's SGL_TRAN) ride along. Updates INSERTS, copies and the terminal list."""
    if not (0.05 < abs(off[0]) + abs(off[1]) < lim) or t not in terms: return False
    ii = towner[terms.index(t)]
    if INSERTS[ii][0] not in MOVABLE: return False
    mine = [k for k, o in enumerate(towner) if o == ii]
    if any(touched(terms[k], d) for k in mine if terms[k] != t): return False
    riders = [jj for jj, r in enumerate(INSERTS) if jj != ii and any(math.dist(r[1:3], terms[k]) < 0.3 for k in mine)]
    for jj in [ii] + riders:
        copies[jj]["dx"] = round(copies[jj]["dx"] + off[0], 4); copies[jj]["dy"] = round(copies[jj]["dy"] + off[1], 4)
        r = INSERTS[jj]; INSERTS[jj] = (r[0], r[1] + off[0], r[2] + off[1], r[3], r[4], r[5])
    for k in mine: terms[k] = (terms[k][0] + off[0], terms[k][1] + off[1])
    JOG_SAVED.append((INSERTS[ii][0], round(off[0] + off[1], 2), len(riders)))
    return True
def sweep_ends(maxd=25.0, tol=0.3):
    o0 = P(0, 0)
    C = [d for d in cr if d["type"] == "polyline" and d["layer"].startswith("CIRCUIT")]
    pts_of = lambda d: [(p["x"] - o0["x"], p["y"] - o0["y"]) for p in d["points"]]
    terms, dots, towner = _terms(owners=True)
    def touched(q, skip=None):
        for d in C:
            if d is skip: continue
            ps = pts_of(d)
            if any(_segdist(q, a, b) < tol for a, b in zip(ps, ps[1:])): return True
        return False
    loose, inbox = [], set()
    for d in C:
        ps = pts_of(d)
        for k in (0, len(ps) - 1):
            q = ps[k]
            if touched(q, d) or any(math.dist(q, t) < tol for t in terms) or any(abs(math.dist(q, c[:2]) - c[2]) < tol for c in dots):
                continue
            if any(math.dist(q, bc) <= br for bc, br in _small_boxes()):
                inbox.add((id(d), k))                     # ends in a structure box: never pulled onto equipment (Ash
                                                          # X5177783 stops at the box centre); a run ahead may still join it
            loose.append((d, k, q))
    cand = []
    for d, k, q in loose:
        if (id(d), k) in inbox: continue
        for t in terms:
            if math.dist(q, t) < maxd: cand.append((math.dist(q, t), id(d), k, d, t))
        for cx_, cy_, rr in dots:
            g = math.dist(q, (cx_, cy_)); reach = 40 if rr == 5.0 else maxd     # a feeder may stop well short of its sub
            if 0 < g < reach + rr:
                t = (cx_ + (q[0] - cx_) * rr / g, cy_ + (q[1] - cy_) * rr / g)
                cand.append((g - rr, id(d), k, d, t))
    used_t, used_e, moved = set(), set(), []
    for g, _i, k, d, t in sorted(cand, key=lambda z: z[0]):
        key_t = (round(t[0], 2), round(t[1], 2))
        own = pts_of(d); own_segs = list(zip(own, own[1:]))
        own_segs = own_segs[1:] if k == 0 else own_segs[:-1]          # not the segment that is being moved
        if key_t in used_t or (id(d), k) in used_e or touched(t, d)                 or any(_segdist(t, a, b) < tol for a, b in own_segs):
            continue                                      # never onto a terminal this same cable already reaches
        used_t.add(key_t); used_e.add((id(d), k))
        n = 1 if k == 0 else len(d["points"]) - 2
        e, nb = d["points"][k], d["points"][n]
        ex, ey = e["x"] - o0["x"], e["y"] - o0["y"]
        nb_q = (nb["x"] - o0["x"], nb["y"] - o0["y"])
        nb_fixed = len(d["points"]) == 2 and (touched(nb_q, d) or any(math.dist(nb_q, t2) < tol for t2 in terms))
        tw = (round(o0["x"] + t[0], 4), round(o0["y"] + t[1], 4))
        if nb_fixed and (abs(nb["x"] - e["x"]) < 0.3 or abs(nb["y"] - e["y"]) < 0.3) and                 _shift_owner(t, (0, nb["y"] - tw[1]) if abs(nb["y"] - e["y"]) < 0.3 else (nb["x"] - tw[0], 0), terms, towner, touched, d):
            # Kevin 2026-11-25: "reduce these joglines" (P5711986). Under 2.5 ft off, the block at the pulled end
            # slides onto the run's line instead (its other terminals are free), and the run stays straight.
            off = (0, nb["y"] - tw[1]) if abs(nb["y"] - e["y"]) < 0.3 else (nb["x"] - tw[0], 0)
            e["x"], e["y"] = round(tw[0] + off[0], 4), round(tw[1] + off[1], 4)
            JOG_SAVED[-1] = (round(tw[0], 1), round(tw[1], 1)) + JOG_SAVED[-1]
        elif nb_fixed and (abs(nb["x"] - e["x"]) < 0.3 or abs(nb["y"] - e["y"]) < 0.3) and                 any(math.dist(nb_q, t2) < tol for t2 in terms) and                 _shift_owner(min(terms, key=lambda t2: math.dist(nb_q, t2)),
                             (0, tw[1] - nb["y"]) if abs(nb["y"] - e["y"]) < 0.3 else (tw[0] - nb["x"], 0), terms, towner, touched, d):
            # the pulled end's block is wired on both sides (a pothead): slide the far end's block instead (P5711986)
            if abs(nb["y"] - e["y"]) < 0.3: nb["y"] = tw[1]
            else: nb["x"] = tw[0]
            e["x"], e["y"] = tw
            JOG_SAVED[-1] = (round(tw[0], 1), round(tw[1], 1)) + JOG_SAVED[-1]
        elif nb_fixed and (abs(nb["x"] - e["x"]) < 0.3 or abs(nb["y"] - e["y"]) < 0.3):
            # the far end is already on equipment (P5745172's feed): keep it, and add a square jog halfway instead of
            # sliding the whole run off it
            if abs(nb["x"] - e["x"]) < 0.3:
                my = round((nb["y"] + tw[1]) / 2, 4); jog = [{"x": nb["x"], "y": my}, {"x": tw[0], "y": my}]
            else:
                mx = round((nb["x"] + tw[0]) / 2, 4); jog = [{"x": mx, "y": nb["y"]}, {"x": mx, "y": tw[1]}]
            e["x"], e["y"] = tw
            if k == 0: d["points"][1:1] = jog[::-1]
            else: d["points"][1:1] = jog
        else:
            if abs(nb["x"] - e["x"]) < 0.3: nb["x"] = tw[0]      # vertical last run: slide it in x
            elif abs(nb["y"] - e["y"]) < 0.3: nb["y"] = tw[1]    # horizontal: slide it in y
            e["x"], e["y"] = tw
        moved.append((round(ex), round(ey), round(g, 1)))
    # still loose: a run the extractor split (e.g. at a small fuse squiggle, PME4619) -- extend the end along its own
    # direction onto another conductor lying within 13 ft straight ahead
    joined = 0
    for d, k, q in loose:
        if (id(d), k) in used_e: continue
        ps = pts_of(d); nb = ps[1] if k == 0 else ps[-2]
        L = math.dist(q, nb)
        if L < 1e-6: continue
        ux, uy = (q[0] - nb[0]) / L, (q[1] - nb[1]) / L
        best = None
        for d2 in C:
            if d2 is d: continue
            p2 = pts_of(d2)
            for a, b in zip(p2, p2[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
                tt = 0 if L2 == 0 else max(0, min(1, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / L2))
                h = (a[0] + tt * dx, a[1] + tt * dy); g = math.dist(q, h)
                if 0.3 < g < 13 and ((h[0] - q[0]) * ux + (h[1] - q[1]) * uy) / g > 0.94 and (best is None or g < best[0]):
                    best = (g, h)
        if best:
            e = d["points"][k]; e["x"], e["y"] = round(o0["x"] + best[1][0], 4), round(o0["y"] + best[1][1], 4)
            joined += 1; moved.append((round(q[0]), round(q[1]), round(best[0], 1)))
    print(f"end sweep: {len(loose)} loose ends, {len(moved) - joined} pulled onto equipment, {joined} joined to a run ahead; "
          f"jogs avoided by sliding the block: {JOG_SAVED}")
    return moved
# ---- closed pole switches break the line: the X's ends at +-14 ft are its terminals (Ash SGL_SW_CL_POLE)
def split_at_switches():
    o0 = P(0, 0)
    for name, x, y, rot, mir, dyn in INSERTS:
        if name != "SGL_SW_CL_POLE": continue
        u = (math.cos(math.radians(rot or 0)), math.sin(math.radians(rot or 0)))
        done = False
        for d in [d for d in cr if d["type"] == "polyline" and d["layer"].startswith("CIRCUIT")]:
            pts = [(p["x"] - o0["x"], p["y"] - o0["y"]) for p in d["points"]]
            for i, (a, b) in enumerate(zip(pts, pts[1:])):
                if _segdist((x, y), a, b) > 0.5: continue
                a_ = (x - 13.5 * u[0], y - 13.5 * u[1]); b_ = (x + 13.5 * u[0], y + 13.5 * u[1])   # X arm ends (Ash: +-13.5)
                L2 = max(1e-9, math.dist(a, b) ** 2)
                ta = ((a_[0] - a[0]) * (b[0] - a[0]) + (a_[1] - a[1]) * (b[1] - a[1])) / L2
                tb = ((b_[0] - a[0]) * (b[0] - a[0]) + (b_[1] - a[1]) * (b[1] - a[1])) / L2
                if not (0 < min(ta, tb) and max(ta, tb) < 1): continue
                if ta > tb: a_, b_ = b_, a_
                d2 = dict(d); d2["points"] = [dict(P(*b_))] + [dict(p) for p in d["points"][i + 1:]]
                d["points"] = d["points"][:i + 1] + [dict(P(*a_))]
                cr.append(d2); done = True
                break
            if done: break
split_at_switches()

# ---- a pothead whose OH tail / UG tip touches nothing gets a stub straight back / ahead to the first line it meets
# (Ash: the pothead hangs off the overhead line; 1956133E, 1361961E, 1226172E were left floating)
def stub_potheads(reach=30.0, tol=0.3):
    o0 = P(0, 0)
    global TERMS_ALL, DOTS_ALL
    TERMS_ALL, DOTS_ALL = _terms()
    C = [d for d in cr if d["type"] == "polyline" and d["layer"].startswith("CIRCUIT")]
    segs = [(d, (a["x"] - o0["x"], a["y"] - o0["y"]), (b["x"] - o0["x"], b["y"] - o0["y"])) for d in C for a, b in zip(d["points"], d["points"][1:])]
    made = 0
    for name, x, y, rot, mir, dyn in INSERTS:
        if name not in ("SGL_PH", "SGL_PH_FUSED"): continue
        L = 16.1 if name == "SGL_PH_FUSED" else 10.5
        u = (math.cos(math.radians(rot or 0)), math.sin(math.radians(rot or 0)))
        for pt, dr, oh in (((x, y), (-u[0], -u[1]), True), ((x + L * u[0], y + L * u[1]), u, False)):
            touching = [d for d, a, b in segs if _segdist(pt, a, b) < tol]
            real = []
            for d in touching:                  # a 2-point stub whose far end hangs in the air is a leftover, not a hookup
                if len(d["points"]) == 2:
                    q0 = (d["points"][0]["x"] - o0["x"], d["points"][0]["y"] - o0["y"])
                    q1 = (d["points"][1]["x"] - o0["x"], d["points"][1]["y"] - o0["y"])
                    far = q1 if math.dist(q0, pt) < math.dist(q1, pt) else q0
                    L_ = math.dist(q0, q1)
                    on_dot = any(abs(math.dist(far, (c_[0], c_[1])) - c_[2]) < tol for c_ in DOTS_ALL)
                    if L_ < reach and not on_dot and not any(e is not d and _segdist(far, a, b) < tol for e, a, b in segs)                             and not any(math.dist(far, t2) < tol for t2 in TERMS_ALL):   # on equipment = attached (GS4801 way 2)
                        cr.remove(d); segs[:] = [sg for sg in segs if sg[0] is not d]; continue
                real.append(d)
            if real: continue
            best = None
            for d, a, b in segs:
                ex, ey = b[0] - a[0], b[1] - a[1]; den = dr[0] * ey - dr[1] * ex
                if abs(den) < 1e-9: continue
                t = ((a[0] - pt[0]) * ey - (a[1] - pt[1]) * ex) / den
                s_ = ((a[0] - pt[0]) * dr[1] - (a[1] - pt[1]) * dr[0]) / den
                if 0.3 < t < reach and -0.01 <= s_ <= 1.01 and (best is None or t < best[0]): best = (t, d)
            if not best: continue
            t, d = best; hit = (pt[0] + dr[0] * t, pt[1] + dr[1] * t)
            lt = d.get("linetype") or ""
            lt = lt if (lt.startswith("SGL-OH") if oh else lt.startswith("SGL-UG")) else ("SGL-OH3PH" if oh else "SGL-UG3PH")
            pl([hit, pt], lt, layer=d["layer"]); made += 1
            segs.append((cr[-1], hit, pt))
    print(f"pothead stubs: {made}")
# ---- fuses / taps sit ON their cable (tile review: V5091497 and GS2898's fuse were left hanging below a cable that
# had moved after they were placed). Each SGL_TRAN_FUSED / SGL_TRAN not touching a conductor moves onto the nearest
# conductor point within 8 ft. Structure boxes the same: a small SGL_BOX with no cable through it slides onto the
# nearest cable within 20 ft (X5745268, X5194396, M5091494, X5177783), its number moving with it.
def _move_insert(i, dx, dy):
    copies[i]["dx"] = round(copies[i]["dx"] + dx, 4); copies[i]["dy"] = round(copies[i]["dy"] + dy, 4)
    r = INSERTS[i]; INSERTS[i] = (r[0], r[1] + dx, r[2] + dy, r[3], r[4], r[5])
WIDENED = []
def snap_equipment():
    o0 = P(0, 0)
    C = [d for d in cr if d["type"] == "polyline" and d["layer"].startswith("CIRCUIT")]
    segs = [((a["x"] - o0["x"], a["y"] - o0["y"]), (b["x"] - o0["x"], b["y"] - o0["y"])) for d in C for a, b in zip(d["points"], d["points"][1:])]
    def nearest(p):
        best = None
        for a, b in segs:
            dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
            t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
            q = (a[0] + t * dx, a[1] + t * dy); dd = math.dist(p, q)
            if best is None or dd < best[0]: best = (dd, q)
        return best
    nf = nb = 0
    for i, (name, x, y, rot, mir, dyn) in enumerate(list(INSERTS)):
        if name in ("SGL_TRAN_FUSED", "SGL_TRAN"):
            dd, q = nearest((x, y))
            if 0.3 < dd < 8: _move_insert(i, q[0] - x, q[1] - y); nf += 1
        elif name == "SGL_BOX":
            d1, d2 = dyn.get("Distance1", 5.8), dyn.get("Distance2", 7.5)
            if d2 > 14: continue                                       # vault outline
            a_ = math.radians(rot or 0)
            cx = x + (-10 + d2 / 2) * math.cos(a_) - (-7.2 + d1 / 2) * math.sin(a_)
            cy = y + (-10 + d2 / 2) * math.sin(a_) + (-7.2 + d1 / 2) * math.cos(a_)
            dd, q = nearest((cx, cy))
            if not rot:
                # vertical runs crossing the box's height within reach of it; if one is inside and another just outside,
                # the map has both going through: centre the box between them and widen it to hold both
                xs = sorted({round(a[0] + (b[0] - a[0]) * (cy - a[1]) / (b[1] - a[1]), 1) for a, b in segs
                             if abs(a[0] - b[0]) < 0.08 * abs(a[1] - b[1]) and min(a[1], b[1]) < cy < max(a[1], b[1])
                             and abs(a[0] + (b[0] - a[0]) * (cy - a[1]) / (b[1] - a[1]) - cx) < d2 / 2 + 4})
                if len(xs) >= 2 and any(abs(v - cx) <= d2 / 2 for v in xs) and any(abs(v - cx) > d2 / 2 - 0.8 for v in xs)                         and xs[-1] - xs[0] < 12:
                    nd2 = round(max(d2, xs[-1] - xs[0] + 3.0), 2); ncx = (xs[0] + xs[-1]) / 2
                    dyn["Distance2"] = nd2
                    nx_ = ncx - (-10 + nd2 / 2); _move_insert(i, nx_ - x, 0); nb += 1
                    for e in cr:
                        if e["type"] == "text" and re.fullmatch(r"[XVM]\d{7}", e["text"])                                 and math.dist((e["position"]["x"] - o0["x"], e["position"]["y"] - o0["y"]), (cx, cy)) < 40:
                            ex_ = e["position"]["x"] - o0["x"]; side_ = 0
                            if abs(e["position"]["y"] - o0["y"] - cy) < 4: side_ = 1 if ex_ > cx else -1   # beside the box: keep clear of the wider edge
                            e["position"] = {"x": round(e["position"]["x"] + ncx - cx + side_ * (nd2 - d2) / 2, 4), "y": e["position"]["y"]}
                    WIDENED.append((round(ncx, 1), round(cy, 1), nd2))
                    continue
            if dd <= min(d1, d2) / 2 or dd > 20: continue             # a cable already runs through it, or none near
            dx, dy = q[0] - cx, q[1] - cy
            _move_insert(i, dx, dy); nb += 1
            for e in cr:                                               # its X/V/M number follows
                if e["type"] == "text" and re.fullmatch(r"[XVM]\d{7}", e["text"]) \
                        and math.dist((e["position"]["x"] - o0["x"], e["position"]["y"] - o0["y"]), (cx, cy)) < 18:
                    e["position"] = {"x": round(e["position"]["x"] + dx, 4), "y": round(e["position"]["y"] + dy, 4)}
    print(f"equipment snapped onto cables: {nf} fuses/taps, {nb} structure boxes; widened over two runs: {WIDENED}")
import re
snap_equipment()

SWEPT = sweep_ends()
# zero-length conductor debris (gap-filler leftovers collapsed onto one point) would count as "connected"
_deb = [d for d in cr if d["type"] == "polyline" and d["layer"].startswith("CIRCUIT")
        and sum(math.dist((a["x"], a["y"]), (b["x"], b["y"])) for a, b in zip(d["points"], d["points"][1:])) < 0.5]
for d in _deb: cr.remove(d)
print(f"debris removed: {len(_deb)}")
stub_potheads()     # after the sweep: stub only what is still floating, against the final geometry
print("moved (x, y, gap ft):", sorted(SWEPT, key=lambda m: -m[2]))

# ---- labels: a structure / pole / transformer number sitting on a conduit or another label moves to the first clear
# spot around its block (above, below, right, left, then the corners). Kevin 2026-11-25: "continual pole text overlapping
# conduits". The anchor is the nearest pole / box / pothead / transformer within 25 ft.
import re as _re2
ANCHOR_BLOCKS = {"SGL_PO_WD_JO_IN", "SGL_BOX", "SGL_PH", "SGL_PH_FUSED", "SGL_TRAN_DE", "SGL_TRAN_BP", "SGL_TRAN_PM",
                 "SGL_TRAN_PM_1PH_DEDF_NFUSED", "SGL_TRAN_FUSED", "SGL_TRAN"}
def _rect_of(e, o0, pad=0.2):
    a = math.radians(e.get("rotationDeg", 0)); w = CW * len(e["text"]); h = e.get("height", H)
    x, y = e["position"]["x"] - o0["x"], e["position"]["y"] - o0["y"]
    return text_rect(e["text"], x + math.cos(a) * w / 2 - math.sin(a) * h / 2, y + math.sin(a) * w / 2 + math.cos(a) * h / 2,
                     e.get("rotationDeg", 0), pad=pad)
def relocate_labels():
    o0 = P(0, 0); OBS = obstacles(); moved = 0
    anchors = []
    for name, x, y, rot, mir, dyn in INSERTS:
        if name not in ANCHOR_BLOCKS: continue
        segs_, cen = _block_outline(name, x, y, rot, dyn)
        if segs_: OBS += segs_
        if name == "SGL_BOX" and not cen: continue          # vault outline: not an anchor
        anchors.append(cen if cen else (x, y))              # a box's real centre, not its corner insertion
    locked = set(globals().get("PME_P", {}).values()) | set(globals().get("TX_LABEL_AT", {})) | globals().get("LOCKED_TEXT", set())        # a PME's P# is half of a stacked pair: leave the pair as set
    small_boxes = [cen for name, x, y, rot, mir, dyn in INSERTS if name == "SGL_BOX"
                   for _sg, cen in [_block_outline(name, x, y, rot, dyn)] if cen]
    texts = [d for d in cr if d["type"] == "text" and _re2.fullmatch(r"\d{5,8}E|[XMPV]\d{7}", d["text"])
             and abs(readable(d.get("rotationDeg") or 0)) < 2 and d["text"] not in locked]
    for d in texts:
        w = CW * len(d["text"])
        cx, cy = d["position"]["x"] - o0["x"] + w / 2, d["position"]["y"] - o0["y"] + H / 2
        others = [_rect_of(e, o0) for e in cr if e["type"] == "text" and e is not d]
        others = [_rect_of(e, o0, pad=1.2) for e in cr if e["type"] == "text" and e is not d]   # labels need a little air between them
        hits_now = n_hits(text_rect(d["text"], cx, cy, 0, pad=0.4), OBS, others)
        near = [a for a in anchors if math.dist(a, (cx, cy)) < 25]
        if d["text"].startswith("V"):                     # a V# only follows a small structure box, never a vault
            near = [a for a in small_boxes if math.dist(a, (cx, cy)) < 18]
            if not near: continue
        if hits_now == 0 and near: continue
        if not near and _re2.fullmatch(r"\d{5,8}E", d["text"]):
            # an orphaned pole number (1226172E sat ~50 ft from its pothead): adopt the nearest pothead within 60 ft
            # that has no number of its own close by
            lab_c = [(e["position"]["x"] - o0["x"] + CW * len(e["text"]) / 2, e["position"]["y"] - o0["y"] + H / 2)
                     for e in texts if e is not d]
            phs = [(x, y) for name, x, y, rot, mir, dyn in INSERTS if name in ("SGL_PH", "SGL_PH_FUSED")
                   and math.dist((x, y), (cx, cy)) < 60 and not any(math.dist((x, y), q) < 15 for q in lab_c)]
            near = phs[:1] and [min(phs, key=lambda a: math.dist(a, (cx, cy)))]
            if near: hits_now = 10 ** 6
        if not near or hits_now == 0: continue
        ax, ay = min(near, key=lambda a: math.dist(a, (cx, cy)))
        side = w / 2 + 5.5          # clear of the block edge, not just its centre
        cands = [(ax, ay + 7.0), (ax, ay - 7.0), (ax + side, ay), (ax - side, ay),
                 (ax + side, ay + 5.5), (ax - side, ay + 5.5), (ax + side, ay - 5.5), (ax - side, ay - 5.5),
                 (ax, ay + 11.0), (ax, ay - 11.0)]
        score = lambda c: n_hits(text_rect(d["text"], c[0], c[1], 0, pad=0.4), OBS, others)
        best = min(range(len(cands)), key=lambda i: 100 * score(cands[i]) + i)
        if score(cands[best]) >= hits_now: continue
        d["position"] = P(cands[best][0] - w / 2, cands[best][1] - H / 2); d["rotationDeg"] = 0; moved += 1
    print(f"labels moved clear: {moved} of {len(texts)}")
relocate_labels()


# =========================================================== title
top = max(p["y"] for c in cr if "points" in c for p in c["points"])
cr.append({"type": "text", "layer": "MISC", "text": "%%UEXISTING SINGLE LINE", "position": {"x": OX + 300, "y": round(top + 40, 2)}, "height": 21.5845})

erase = [e["handle"] for e in json.load(open(sys.argv[2]))["entities"]] if len(sys.argv) > 2 else []
job = {"version": 1, "creates": cr, "copies": copies, "edits": edits, "erase": erase}
json.dump(job, open(sys.argv[1], "w"), indent=1)
xs = [p["x"] for c in cr if "points" in c for p in c["points"]]; ys = [p["y"] for c in cr if "points" in c for p in c["points"]]
print(len(cr), "creates,", len(copies), "copies,", len(edits), "edits,", len(erase), "erase; extents",
      round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys)))

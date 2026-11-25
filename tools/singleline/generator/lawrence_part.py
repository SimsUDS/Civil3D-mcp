# Lawrence 12KV (page 10) -> CIRCUIT-2.  exec()'d from build_royer_v6.py so it shares its helpers.
# Geometry comes from p10_extract.json (extract_page.py, already transformed into the page-1 frame);
# equipment types and label text were read off the sheet by eye.
LW = json.load(open(r"C:/civ3dmcp/jobs/Singleline/_analysis/p10_extract.json"))
_s, _ax, _ay, _bx, _by = 0.85277, 163.9, 309.0, 177.4, 681.2
def R(x10, y10):                       # page-10 point -> page-1 point -> drawing feet
    return T(_ax + _s * (x10 - _bx), _ay + _s * (y10 - _by))
def Rref(p):                           # already page-1 point -> feet
    return T(*p)
C2L = "CIRCUIT-2"

# ---------------------------------------------------------------- tie circuits (not drawn in this test)
TIE = {"COMPLEX": "CIRCUIT-3", "MATLOCK": "CIRCUIT-4"}

pole_pts = [Rref(p) for p in LW["poles"]]
HOPS = [(Rref(h["a"]), Rref(h["b"]), Rref(h["apex"])) for h in LW.get("hops", [])]
CH = [[Rref(p) for p in c["pts"]] for c in LW["conductors"]]
DOTS = [Rref(p) for p in LW.get("dots", [])]
def to10(pref): return (_bx + (pref[0] - _ax) / _s, _by + (pref[1] - _ay) / _s)

# ---------------------------------------------------------------- potheads first, so cable ends can be snapped to them
FUSED_TRI = {0, 5}             # 1659859E (FD07534), 2281297E -- fused potheads (Ash). The "80A" by V5092568 is BF07957's (BLF), not the pothead's
csegs = [(Rref(a), Rref(b)) for c in LW["conductors"] for a, b in zip(c["pts"], c["pts"][1:]) if math.dist(a, b) > 0.3]
PH_ENDS = []; PH_LIST = []
for ti, t in enumerate(LW["triangles"]):
    P3 = [Rref(p) for p in t["pts"]]
    cen = (sum(p[0] for p in P3) / 3, sum(p[1] for p in P3) / 3)
    a, b = min(csegs, key=lambda sg: math.dist(cen, nearest_on(cen, *sg)))
    L = math.dist(a, b); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    pr = [p[0] * ux + p[1] * uy for p in P3]
    k = max(range(3), key=lambda i: abs(pr[i] - (sum(pr) - pr[i]) / 2))
    sgn = 1 if pr[k] > (sum(pr) - pr[k]) / 2 else -1
    tx_, ty_ = P3[k]
    tp = (a[0] + ((tx_ - a[0]) * ux + (ty_ - a[1]) * uy) * ux, a[1] + ((tx_ - a[0]) * ux + (ty_ - a[1]) * uy) * uy)
    tail = pothead(tp, math.degrees(math.atan2(uy * sgn, ux * sgn)), fused=ti in FUSED_TRI)
    PH_ENDS += [tail, tp]; PH_LIST.append((tail, tp, math.degrees(math.atan2(uy * sgn, ux * sgn))))
# snap cable ends that stop short of / run past a pothead onto its tail or tip
for ch in CH:
    for end in (0, -1):
        q = min(PH_ENDS, key=lambda e: math.dist(e, ch[end]))
        other = ch[-1 if end == 0 else 0]
        if 0.05 < math.dist(q, ch[end]) < 20 and math.dist(q, other) > 1: ch[end] = q

# ---------------------------------------------------------------- gear switches (RAG) on the PDF body; ties take their ways,
# other cable ends that reach the body snap onto the remaining way terminals (local x = 3.7 + 3.8*k, y = 0).
SWITCHES = [  # (block, ways, page-10 body centre, half-w pt, half-h pt, {tie way index: tie name})
    ("SGL_SW_3W_RAM", 3, (226.7, 263.2), 7.0, 4.4, {0: "MATLOCK", 2: "MATLOCK"}),   # OS2899 (ways 1 and 3 red; way 2 open, green)
    ("SGL_SW_4W_RAM", 4, (246.5, 263.5), 7.5, 4.4, {}),                             # GS2898
    ("SGL_SW_4W_RAM", 4, (233.3, 413.2), 7.5, 4.6, {}),                             # GS2819
    ("SGL_SW_5W_RAM", 5, (323.6, 393.3), 8.5, 4.6, {2: "COMPLEX"}),                 # GS2818
    ("SGL_SW_5W_RAM", 5, (242.0, 539.8), 8.5, 4.6, {}),                             # GS2979
    ("SGL_SW_4W_RAG", 4, (154.4, 652.9), 7.5, 4.4, {}),                             # GS0136 (R A G; way 4 -> GS0137 way 1)
    ("SGL_SW_4W_RAG", 4, (181.1, 652.9), 7.5, 4.4, {2: "COMPLEX", 3: "COMPLEX"}),   # GS0137 (map shows R A G)
]
SWNAME = {(226.7, 263.2): "OS2899", (246.5, 263.5): "GS2898", (233.3, 413.2): "GS2819", (323.6, 393.3): "GS2818",
          (242.0, 539.8): "GS2979", (181.1, 652.9): "GS0137", (154.4, 652.9): "GS0136"}
PLACED = {}; TIES_AT = {}
def in_body(p10, c, hw, hh): return abs(p10[0] - c[0]) <= hw + 0.8 and abs(p10[1] - c[1]) <= hh + 0.8
drop = set()
for ci, c in enumerate(LW["conductors"]):
    P10 = [to10(p) for p in c["pts"]]
    for _, n, cen, hw, hh, _t in SWITCHES:
        if all(in_body(q, cen, hw, hh) for q in P10): drop.add(ci)
# Way terminals measured in Ash (local x at y = 0, the bottom edge of the switch body).
WAYX = {"SGL_SW_3W_RAM": [0, 3.6, 7.2], "SGL_SW_4W_RAM": [0, 3.47, 7.13, 10.6],
        "SGL_SW_5W_RAM": [0, 3.81, 7.41, 11.01, 14.61], "SGL_SW_6W_RAM": [0, 3.6, 7.2, 10.8, 14.4, 18.0],
        "SGL_SW_3W_RAG": [3.7, 7.48, 11.26], "SGL_SW_4W_RAG": [3.7, 7.48, 11.26, 15.04],
        "SGL_SW_5W_RAG": [3.7, 7.48, 11.26, 15.04, 18.82]}
# Ways (0-based) the map shows fused to a load: SGL_TRAN_FUSED hangs from the terminal at r270 (Ash V5092570 way 5).
TAPS = {"GS2979": {4}, "GS2819": {1}}
CORNER_TAPS = {"GS2898": {0}}      # TRAN_FUSED at the foot of that way's drop (Ash V5092205)
OPEN = {"OS2899": {1}, "GS0137": {0, 1}, "GS2818": {2}, "GS0136": {2}}   # ways drawn open on the map: dyn Angle 0.3491 (RAM) / 0.5236 (RAG)
CAPS = {"GS0137": {1}, "GS0136": {2}}             # grounded/capped way: SGL_CAP r90 at the terminal
PITCH10 = 3.45                     # PDF way pitch (pt) on the Lawrence sheet
WAY_OF = {}
TIE_SEGS = []                      # tie-arrow stems (other cables hop over them)
DROPS = []                         # (ci, end, terminal) for every cable joined to a way / leg
WAYPTS = []                        # switch way terminals / junction leg ends that a cable was joined to
SHIFTS = []                        # (x_old, y_lo, y_hi, dx): vertical drops moved onto a terminal; hops on them follow
def assign_ways(hits, n, cen_x, used):
    """hits sorted by x (page-10 x, ci, end) -> {(ci, end): way}; order-preserving, closest to the PDF way position."""
    import itertools
    free = [k for k in range(n) if k not in used]
    est = [(x10 - cen_x) / PITCH10 + (n - 1) / 2 for x10, _ci, _e in hits]
    best = None
    for combo in itertools.combinations(free, min(len(hits), len(free))):
        cost = sum(abs(e - k) for e, k in zip(est, combo))
        if best is None or cost < best[0]: best = (cost, combo)
    return {(ci, e): k for (_x, ci, e), k in zip(hits, best[1] if best else ())}
def drop_to(ci, end, t):
    """Join cable end to terminal t (cable leaves downward). The leading vertical run moves onto t's x, so the cable
    drops straight down out of the body as in Ash; a sideways first leg gets a vertical elbow instead."""
    WAYPTS.append(t); DROPS.append((ci, end, t))
    ch = CH[ci]
    seq = ch if end == 0 else ch[::-1]
    j = 0
    while j + 1 < len(seq) and abs(seq[j + 1][0] - seq[j][0]) < 0.35 * abs(seq[j + 1][1] - seq[j][1]) + 0.3:
        j += 1
    if j > 0:
        xo = seq[0][0]; ys = [p[1] for p in seq[:j + 1]]
        SHIFTS.append((xo, min(ys), max(ys), t[0] - xo))
        seq = [(t[0], p[1]) for p in seq[:j + 1]] + seq[j + 1:]
        if j + 1 < len(seq) and abs(seq[j + 1][1] - seq[j][1]) < 1.5: seq[j + 1] = (seq[j + 1][0], seq[j][1])
        seq = [t] + seq[1:] if abs(seq[0][1] - t[1]) < 0.5 else [t] + seq
    else:
        old = seq[0]
        seq = [t] + ([(t[0], old[1])] if abs(old[1] - t[1]) > 1 else []) + seq
    CH[ci] = seq if end == 0 else seq[::-1]
    k = 0                                                       # foot of the drop
    while k + 1 < len(seq) and abs(seq[k + 1][0] - t[0]) < 0.01: k += 1
    return seq[k]
for name, n, cen, hw, hh, ties in SWITCHES:
    c = R(*cen)
    ram = name.endswith("_RAM")
    wx = WAYX[name]
    ins_pt = (c[0] - (wx[0] + wx[-1]) / 2, c[1] - 7.0)
    sn = SWNAME[cen]
    akeys = ["Angle", "Angle2", "Angle3", "Angle4", "Angle5", "Angle6"][:n]
    dyn = {a: ((math.radians(20) if ram else math.radians(30)) if k in OPEN.get(sn, ()) else 0) for k, a in enumerate(akeys)}
    ins(name, *ins_pt, dyn=dyn)
    terms = [(ins_pt[0] + wx[k], ins_pt[1]) for k in range(n)]
    for k in CAPS.get(sn, ()): ins("SGL_CAP", *terms[k], rot=90)
    ext = (-3.7, 0.0, wx[-1] + 3.6, 14.0) if ram else (0.0, -0.9, 19.0 + 3.75 * (n - 3), 15.2)
    PLACED[SWNAME[cen]] = (ins_pt[0] + ext[0], ins_pt[1] + ext[1], ins_pt[0] + ext[2], ins_pt[1] + ext[3])
    if ties: PLACED[SWNAME[cen]] = PLACED[SWNAME[cen]][:1] + (ins_pt[1] - 33.0,) + PLACED[SWNAME[cen]][2:]
    TIES_AT[SWNAME[cen]] = (sum(terms[j][0] for j in ties) / len(ties), list(ties.values())[0]) if ties else None
    for k, tie in ties.items():                       # tie arrow out of the way, on the tie circuit's layer
        ins("SGL_SYM_ARR_DC", *terms[k], rot=270, layer=TIE[tie])
        TIE_SEGS.append((terms[k], (terms[k][0], terms[k][1] - 31.2)))   # its stem: other cables hop over it
    hits = []
    for ci, ch in enumerate(CH):
        if ci in drop: continue
        for end in (0, -1):
            q10 = to10(LW["conductors"][ci]["pts"][end])
            if abs(q10[0] - cen[0]) <= hw + 3.0 and abs(q10[1] - cen[1]) <= hh + 3.0:
                hits.append((q10[0], ci, end))
    taps = TAPS.get(SWNAME[cen], set())
    for k in taps:
        ins("SGL_TRAN_FUSED", *terms[k], rot=270)
        b = PLACED[SWNAME[cen]]; PLACED[SWNAME[cen]] = (b[0], min(b[1], terms[k][1] - 11.5), b[2], b[3])
    for (ci, end), k in assign_ways(sorted(hits), n, cen[0], set(ties) | taps | CAPS.get(sn, set())).items():
        foot = drop_to(ci, end, terms[k])
        if k in CORNER_TAPS.get(sn, ()): ins("SGL_TRAN_FUSED", *foot, rot=270)
        WAY_OF[(sn, k)] = ci

# ---------------------------------------------------------------- junction bars: cable ends reaching the bar snap onto its legs
VAULTS = [("V5092205", ["OS2899", "GS2898"]), ("V5091493", ["GS2819"]), ("V5091495", ["GS2818", "J495"]),
          ("V5091496", ["BS0184", "J496"]), ("V5092570", ["GS2979"]), ("V5092573", ["J573"]),
          ("V5091492", ["BS6094"]), ("V5770309", ["GS0136", "GS0137"])]
# BS0184 (SGL_SW_3W, LTR-UP): placed before the junction bars so J496 can sit beside it. Terminals measured in Ash:
# T (0, +4.8) top, L (-4.8, 0), R (+4.8, 0); cables end on them (snapped below, with the transformers).
BS_AT = R(370.7, 392.0); ins("SGL_SW_3W", *BS_AT, dyn={"Visibility1": "LTR-UP"})
PLACED["BS0184"] = (BS_AT[0] - 9.0, BS_AT[1] - 9.6, BS_AT[0] + 9.1, BS_AT[1] + 9.3)
BS_TERMS = {"T": ((BS_AT[0], BS_AT[1] + 4.8), (0, 1)), "L": ((BS_AT[0] - 4.8, BS_AT[1]), (-1, 0)), "R": ((BS_AT[0] + 4.8, BS_AT[1]), (1, 0))}
GLYPH_W = 2.8                      # rendered width per character at 3.2 (measured from the BS0184 render)
LABEL_AT = {"BS0184": (BS_AT[0] - 2.5 - GLYPH_W * 6 / 2, BS_AT[1] + 8.9)}   # Ash: up-left beside the cable entering T; right edge clear of the "T"
LABEL_X = {}                       # device label centre x (junction bars: over the legs, i.e. over the block's "1 2 3")
TERM_DIR = {}                      # terminal -> direction the cable leaves it (default straight down)
LEGX0 = {"SGL_JBAR_3W": [-0.09, 3.91, 7.91], "SGL_JBAR_4W": [-0.07, 3.33, 7.17, 10.59]}   # Ash leg ends
JNAME = {(344.0, 395.1): "J495", (389.4, 391.6): "J496", (237.4, 574.7): "J573"}
JBARS = [("SGL_JBAR_4W", 4, 3.55, (344.0, 395.1)), ("SGL_JBAR_3W", 3, 4.0, (389.4, 391.6)), ("SGL_JBAR_3W", 3, 4.0, (237.4, 574.7))]
JTAPS = {"J573": {1}}
JLBE = {"J496": {0, 1, 2}}         # SGL_LBE r270 at the leg end (map: chevron on the leg)
JTRAN = {"J496": {2}}              # SGL_TRAN r270 3.25 ft below the leg on a short cable (Ash J496 leg 3)
JEXTRA = []
JCAPS = {"J495": {1, 2}}          # capped legs (map: ground mark under the leg) -> SGL_CAP r90 (Ash J495)            # leg fused to a load (Ash: TRAN_FUSED r270 on J573 leg 2)
# hops that sat on a vertical drop which moved onto its way terminal move with it
def _hop_dx(a, b):
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    return next((dx for xo, lo, hi, dx in SHIFTS if abs(m[0] - xo) < 2.5 and lo - 1 <= m[1] <= hi + 1), 0.0)
HOPS = [((a[0] + d, a[1]), (b[0] + d, b[1]), (ap[0] + d, ap[1])) for a, b, ap in HOPS for d in [_hop_dx(a, b)]]
SWITCH_SHIFTS = list(SHIFTS)
for nm, n, pitch, cen in JBARS:
    c = R(*cen); ins_pt = (c[0] - pitch * (n - 1) / 2, c[1])
    # Sharing a vault with a gear switch (Ash V5091495): top-aligned with the switch and set ~20.6 ft beside it,
    # so both blocks and their labels sit together inside the box. Cables still find the legs below.
    for _v, mem in VAULTS:
        sw = [PLACED[m] for m in mem if m in PLACED and m != JNAME[cen]]
        if JNAME[cen] in mem and sw:
            b = sw[0]; gap = 13.8 if any(m.startswith("BS") for m in mem) else 21.1   # Ash: 13.3 / 20.6 + leg overhang
            x = b[2] + gap if ins_pt[0] > b[0] else b[0] - gap - (LEGX0[nm][-1] + 0.6)
            ins_pt = (x, b[3] - 4.45)
    ins(nm, *ins_pt)
    LABEL_X[JNAME[cen]] = ins_pt[0] + (LEGX0[nm][0] + LEGX0[nm][-1]) / 2
    PLACED[JNAME[cen]] = (ins_pt[0] - 0.6, ins_pt[1] - 5.3, ins_pt[0] + pitch * (n - 1) + 0.6, ins_pt[1] + 4.5)
    # exact leg ends measured in Ash (not evenly spaced on the 4W): cables and SGL_CAPs must land on them
    LEGX = LEGX0[nm]
    legs = [(ins_pt[0] + LEGX[k], ins_pt[1] - 5.29) for k in range(n)]
    for k in JCAPS.get(JNAME[cen], ()):
        ins("SGL_CAP", *legs[k], rot=90)
    for k in JLBE.get(JNAME[cen], ()):
        ins("SGL_LBE", *legs[k], rot=270)
    for k in JTRAN.get(JNAME[cen], ()):
        ins("SGL_TRAN", legs[k][0], legs[k][1] - 3.25, rot=270); JEXTRA.append([legs[k], (legs[k][0], legs[k][1] - 3.25)])
        b = PLACED[JNAME[cen]]; PLACED[JNAME[cen]] = (b[0], legs[k][1] - 16, max(b[2], legs[k][0] + 4.9), b[3])   # SGL_TRAN is +-4.9 wide
    for k in JTAPS.get(JNAME[cen], ()):
        ins("SGL_TRAN_FUSED", *legs[k], rot=270)
        b = PLACED[JNAME[cen]]; PLACED[JNAME[cen]] = (b[0], legs[k][1] - 11.5, b[2], b[3])
    hits = []
    for ci, ch in enumerate(CH):
        if ci in drop: continue
        for end in (0, -1):
            if math.dist(ch[end], c) < 30: hits.append((to10(LW["conductors"][ci]["pts"][end])[0], ci, end))
    # same as the switch ways: order-preserving leg assignment, cable rises straight to the leg end
    for (ci, end), k in assign_ways(sorted(hits), n, cen[0], set(JTAPS.get(JNAME[cen], ())) | set(JCAPS.get(JNAME[cen], ())) | set(JTRAN.get(JNAME[cen], ()))).items():
        drop_to(ci, end, legs[k])
# hops on cables that moved onto a junction leg follow them too
_n_sw = len(SWITCH_SHIFTS)
HOPS = [((a[0] + d, a[1]), (b[0] + d, b[1]), (ap[0] + d, ap[1])) for a, b, ap in HOPS
        for d in [next((dx for xo, lo, hi, dx in SHIFTS[_n_sw:] if abs((a[0] + b[0]) / 2 - xo) < 2.5
                        and lo - 1 <= (a[1] + b[1]) / 2 <= hi + 1), 0.0)]]

# ---------------------------------------------------------------- pothead gaps: if nothing ends at a pothead's tip (UG side)
# or tail (OH side), extend the nearest cable end that lies ahead of it (within 60 ft, roughly in line) to meet it.
def _touches(pt):
    for ci, ch in enumerate(CH):
        if ci in drop: continue
        for u, v in zip(ch, ch[1:]):
            if math.dist(pt, nearest_on(pt, u, v)) < 1.0: return True
    return False
EXTRA = []
for tail, tip, ang in PH_LIST:
    ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    for pt, sgn in ((tip, 1), (tail, -1)):
        if _touches(pt): continue
        best = None
        for ci, ch in enumerate(CH):
            if ci in drop: continue
            for end in (0, -1):
                vx, vy = ch[end][0] - pt[0], ch[end][1] - pt[1]
                along = sgn * (vx * ux + vy * uy); lat = abs(vx * uy - vy * ux)
                if 0 < along < 60 and lat < 0.6 * along + 4:
                    d = math.hypot(vx, vy)
                    if best is None or d < best[0]: best = (d, ci, end)
        if best:
            _, ci, end = best
            if end == 0: CH[ci].insert(0, pt)
            else: CH[ci].append(pt)
            continue
        if sgn == 1:      # tip: run UG to the transformer / box straight ahead
            eq = [Rref(LW["boxes"][i]["c"]) for i in range(len(LW["boxes"]))]
            cand = [(math.dist(pt, q), q) for q in eq
                    if 0 < (q[0] - pt[0]) * ux + (q[1] - pt[1]) * uy < 70
                    and abs((q[0] - pt[0]) * uy - (q[1] - pt[1]) * ux) < 0.5 * ((q[0] - pt[0]) * ux + (q[1] - pt[1]) * uy) + 6]
            if cand:
                q = min(cand)[1]
                EXTRA.append(([pt, (q[0] - ux * 4, q[1] - uy * 4)] if abs(ux) > abs(uy) else [pt, (pt[0], q[1] - uy * 6)], UG))
        else:             # tail: OH stub back to the nearest line behind
            cand = []
            for ci, ch in enumerate(CH):
                if ci in drop: continue
                for u, v in zip(ch, ch[1:]):
                    n = nearest_on(pt, u, v)
                    if -((n[0] - pt[0]) * ux + (n[1] - pt[1]) * uy) > 0.5 and math.dist(pt, n) < 30: cand.append((math.dist(pt, n), n))
            if cand: EXTRA.append(([min(cand)[1], pt], OH))

# ---------------------------------------------------------------- structure boxes and transformers (types checked against Ash)
# Placed BEFORE the conductors are drawn so the feeding cable can end exactly on the transformer's feed terminal
# (Ash: TRAN_DE feed at local (0, 6) with elbows ON, (0, 4) OFF; rotation always a multiple of 90).
def snap_end(ci, end, t):
    """Move cable end onto terminal t. The last straight run toward the end shifts sideways onto t, so the cable
    stays square (vertical runs move in x, horizontal runs in y)."""
    seq = CH[ci] if end == 0 else CH[ci][::-1]
    if len(seq) < 2: return
    a, b = seq[0], seq[1]
    if abs(a[0] - b[0]) <= abs(a[1] - b[1]):          # vertical approach
        j = 0
        while j + 1 < len(seq) and abs(seq[j + 1][0] - seq[j][0]) < 0.35 * abs(seq[j + 1][1] - seq[j][1]) + 0.3: j += 1
        seq = [(t[0], p[1]) for p in seq[:j + 1]] + seq[j + 1:]
    else:
        j = 0
        while j + 1 < len(seq) and abs(seq[j + 1][1] - seq[j][1]) < 0.35 * abs(seq[j + 1][0] - seq[j][0]) + 0.3: j += 1
        seq = [(p[0], t[1]) for p in seq[:j + 1]] + seq[j + 1:]
    seq[0] = t
    CH[ci] = seq if end == 0 else seq[::-1]
def nearest_end(q, r=25):
    best = None
    for ci, ch in enumerate(CH):
        if ci in drop: continue
        for end in (0, -1):
            d = math.dist(ch[end], q)
            if d < r and (best is None or d < best[0]): best = (d, ci, end)
    return best
_bs_pairs = sorted(((math.dist(CH[ci][end], t), ci, end, t, dr) for _k, (t, dr) in BS_TERMS.items()
                    for ci in range(len(CH)) if ci not in drop for end in (0, -1) if math.dist(CH[ci][end], t) < 15))
_used_t, _used_e = set(), set()
for _d, ci, end, t, dr in _bs_pairs:             # BS0184 cables end on T / L / R: closest pairs first, each used once
    if t in _used_t or (ci, end) in _used_e: continue
    _used_t.add(t); _used_e.add((ci, end))
    snap_end(ci, end, t); WAYPTS.append(t); DROPS.append((ci, end, t)); TERM_DIR[t] = dr
    if dr[0]:   # side terminal: Ash runs 9.5 ft straight out before turning (keeps clear of the junction legs beside it)
        seq = CH[ci] if end == 0 else CH[ci][::-1]
        j = 1
        while j + 1 < len(seq) and abs(seq[j + 1][0] - seq[j][0]) < 0.35 * abs(seq[j + 1][1] - seq[j][1]) + 0.3: j += 1
        xo = t[0] + 9.5 * dr[0]
        seq = [seq[0]] + [(xo, p[1]) for p in seq[1:j + 1]] + seq[j + 1:]
        CH[ci] = seq if end == 0 else seq[::-1]
OWN_TX, OWN_BOX = [], []
BOX_INS = []                       # (INSERTS index, centre) of each structure box: the vault-floor pass moves them with their leg
TX_ROT = {}                        # transformer point -> TRAN_DE rotation (label side depends on it)
BOXES = {
    0: "box", 1: "box", 2: "box", 3: "box45", 4: "box", 5: "box", 6: "box", 7: "box", 8: "box", 9: "box",
    10: "box", 11: "box", 12: "box",
    20: "tx", 22: "tx", 23: "tx", 24: "tx", 25: "tx", 26: "tx", 27: "tx", 28: "tx", 29: "tx", 30: "tx", 31: "tx",
    32: "tx", 19: "txoff", 21: "tx3p", 18: "tx1pab", 20: "txoff",   # 20 = P5743057 (Ash: elbows OFF)
}
for i, kind in BOXES.items():
    b = LW["boxes"][i]; c = Rref(b["c"])
    if kind in ("box", "box45"):
        OWN_BOX.append(c); BOX_INS.append((len(INSERTS), c)); box(c, 45 if kind == "box45" else 0); continue
    OWN_TX.append(c)
    if kind == "tx1pab":
        # 1-phase A/B pad (Ash, 5 of 6 instances): terminals A (-5.72, 0) and B (+6.28, 0) off the insertion. The map's
        # symbol is wider than the block, so the PDF cable ends stop ~12 ft out: pull each onto its terminal, closest first.
        ins("SGL_TRAN_PM_1PH_DEDF_NFUSED", *c, dyn={"Angle2": 0, "Visibility1": "LB-Elbows-ON"})
        terms_ab = [(c[0] - 5.72, c[1] + 0.02), (c[0] + 6.28, c[1] + 0.02)]
        pairs = sorted((math.dist(CH[ci][end], t), ci, end, t) for t in terms_ab for ci in range(len(CH)) if ci not in drop
                       for end in (0, -1) if math.dist(CH[ci][end], t) < 25)
        ut, ue = set(), set()
        for _d, ci, end, t in pairs:
            if t in ut or (ci, end) in ue: continue
            ut.add(t); ue.add((ci, end)); snap_end(ci, end, t)
        continue
    if kind == "tx3p": ins("SGL_TRAN_PM", *c, rot=90, dyn={"Visibility1": "LB-ELBOWS-OFF"}); continue
    ne = nearest_end(c, 40)
    e = CH[ne[1]][ne[2]] if ne else (c[0], c[1] - 10)
    if ne:   # face the feed into the cable's last run (its direction, not just where its end lies)
        sq = CH[ne[1]] if ne[2] == 0 else CH[ne[1]][::-1]
        k_ = 1
        while k_ + 1 < len(sq) and math.dist(sq[0], sq[k_]) < 0.5: k_ += 1
        d_ = (sq[k_][0] - sq[0][0], sq[k_][1] - sq[0][1])
        if math.hypot(*d_) < 0.5: d_ = (e[0] - c[0], e[1] - c[1])
    else:
        d_ = (e[0] - c[0], e[1] - c[1])
    ang = round((math.degrees(math.atan2(d_[1], d_[0])) - 90) / 90) * 90 % 360
    off = 4.0 if kind == "txoff" else 6.0
    a = math.radians(ang + 90); feed = (c[0] + off * math.cos(a), c[1] + off * math.sin(a))
    if ne:
        seq = CH[ne[1]] if ne[2] == 0 else CH[ne[1]][::-1]
        vert = abs(seq[0][0] - seq[1][0]) <= abs(seq[0][1] - seq[1][1])
        j = 0
        while j + 1 < len(seq) and (abs(seq[j + 1][0] - seq[j][0]) < 0.35 * abs(seq[j + 1][1] - seq[j][1]) + 0.3 if vert
                                    else abs(seq[j + 1][1] - seq[j][1]) < 0.35 * abs(seq[j + 1][0] - seq[j][0]) + 0.3): j += 1
        other_ends = [ch2[e2] for ci2, ch2 in enumerate(CH) if ci2 != ne[1] and ci2 not in drop for e2 in (0, -1)]
        other_ends += [p_ for pts_, _lt in EXTRA for p_ in (pts_[0], pts_[-1])]   # pothead gap stubs pin a run too
        run_hit = any(nearest_on(q2, seq[k], seq[k + 1]) and math.dist(q2, nearest_on(q2, seq[k], seq[k + 1])) < 0.5
                      for k in range(j) for q2 in other_ends)
        if run_hit or any(math.dist(seq[k], w) < 0.05 for k in range(j + 1) for w in WAYPTS):
            # the run is pinned -- to a switch way / junction leg, or another cable tees into it -- so moving it would
            # break that joint (P5745172): slide the transformer onto the run instead
            # the run is pinned to a switch way / junction leg at its far end: slide the transformer onto the run instead
            d = (seq[0][0] - feed[0], 0.0) if vert else (0.0, seq[0][1] - feed[1])
            OWN_TX[-1] = c = (c[0] + d[0], c[1] + d[1]); feed = (feed[0] + d[0], feed[1] + d[1])
        snap_end(ne[1], ne[2], feed)
    TX_ROT[c] = ang
    ins("SGL_TRAN_DE", *c, rot=ang, dyn={"Visibility1": "LB-ELBOWS-OFF" if kind == "txoff" else "LB-ELBOWS-ON"})

# ---------------------------------------------------------------- PMEs: insertion so the block's own terminals sit on the
# map's terminals (Ash, block_study: PME_05 (0,0)/(0,-16.31); PME_01 (0,0)/(12,0); PME_06 (0,0)/(0,-12)/(8,-12);
# PME_09 (0,0)/(8,-12)); cable ends within 20 ft snap onto them.
PME_TERMS = {"SGL_PMH_PME_05": [(0, 0), (0, -16.31)], "SGL_PMH_PME_01": [(0, 0), (12, 0)],
             "SGL_PMH_PME_06": [(0, 0), (0, -12), (8, -12)], "SGL_PMH_PME_09": [(0, 0), (8, -12)]}   # PME_09: pos 3 / pos 1 (Ash)
PME_CAPS = {"PME0223": [((8, 0), 270), ((0, -12), 90)]}   # SGL_CAP on the open positions 4 and 2 (Ash PME0223)
PMES = [  # (PME#, block, page-10 symbol centre, rotation, dyn, centre_the_terminals)
    ("PME0223", "SGL_PMH_PME_09", (260.5, 424.8), 0, {"Angle": math.pi / 2, "Angle2": 3 * math.pi / 4}, False),   # Ash dyn: pos 2 / 4 open
    ("PME4619", "SGL_PMH_PME_06", (181.6, 524.4), 0, None, False),
    ("PME4737", "SGL_PMH_PME_01", (173.0, 281.3), 0, {"Visibility1": "LB-ELBOWS-RIGHT"}, False),
    ("PMH5981", "SGL_PMH_PME_05", (283.0, 278.4), 270, None, True),
]
OWN_PME, PME_LAB = {}, {}
PME_LAB_AT = {}                    # explicit (P# centre, PME# centre) where Ash sets them
LOCKED_TEXT = set()                # labels set from Ash's layout; the overlap pass leaves them
TX_LABEL_AT = {}                   # P# -> its transformer, where position alone would pick the wrong block
for num, blk, c10, rot, dyn, centre in PMES:
    c = R(*c10); r = math.radians(rot)
    rotp = lambda p: (p[0] * math.cos(r) - p[1] * math.sin(r), p[0] * math.sin(r) + p[1] * math.cos(r))
    tl = PME_TERMS[blk]
    if centre:                          # symbol centre given: put the midpoint of the terminals there
        m = rotp((sum(p[0] for p in tl) / len(tl), sum(p[1] for p in tl) / len(tl)))
        ip = (c[0] - m[0], c[1] - m[1])
    else:
        ip = c
    terms = [(ip[0] + rotp(p)[0], ip[1] + rotp(p)[1]) for p in tl]
    for t in terms:
        ne = nearest_end(t, 20)
        if ne: snap_end(ne[1], ne[2], t)
    ins(blk, *ip, rot=rot, dyn=dyn)
    for (lx_, ly_), cr_ in PME_CAPS.get(num, []): ins("SGL_CAP", ip[0] + lx_, ip[1] + ly_, rot=cr_)
    OWN_PME[num] = ip
    # label anchor: left end of the terminals for a horizontal (rotated) PME -- Ash stacks P#/PME# above, left-aligned
    PME_LAB[num] = (min(t[0] for t in terms), max(t[1] for t in terms)) if rot in (90, 270) else None

# ---------------------------------------------------------------- vault floors: cables leave each vault through its bottom
# edge and only turn below it (Ash V5091495: the vault box reaches just past the tie arrow; way cables turn 30-45 ft
# lower, nested so the way nearest the turn side turns first). Horizontal legs that the PDF puts inside the vault drop
# to VAULT_FLOOR - 5, -9, -13 ...; hops sitting on a moved leg move with it.
VAULT_FLOOR, VAULT_TIED = {}, {}
BOX_MOVED = []
BOX_FROM = {}                      # moved box centre -> where the map drew it (its label is matched against that)
for vnum, members in VAULTS:
    if not all(m in PLACED for m in members): continue
    bb = [PLACED[m] for m in members]
    VAULT_FLOOR[vnum] = (min(b[0] for b in bb) - 4, min(b[1] for b in bb) - 4, max(b[2] for b in bb) + 4, max(b[3] for b in bb) + 8)
    VAULT_TIED[vnum] = any(TIES_AT.get(m) for m in members)
INTERNAL = set()
for vnum, (vx0, vy0, vx1, vy1) in VAULT_FLOOR.items():
    # A cable joining two terminals of the SAME vault (GS2818 way 5 -> J495 leg 1) stays inside the box: a conduit never
    # leaves a vault and comes back in (Kevin, 2026-11-25). Route: down from both terminals, across 6 ft under the lower one.
    inside = lambda t: vx0 <= t[0] <= vx1 and vy0 <= t[1] <= vy1
    ends_ = {}
    for ci, end, t in DROPS:
        if inside(t) and ci not in drop: ends_.setdefault(ci, {})[end] = t
    for ci, e in ends_.items():
        if 0 in e and -1 in e:
            a, b = e[0], e[-1]; yr = min(a[1], b[1]) - 6
            pa = [a] + ([(a[0] + 3 * TERM_DIR[a][0], a[1])] if TERM_DIR.get(a, (0, -1))[0] else [])
            pb = ([(b[0] + 3 * TERM_DIR[b][0], b[1])] if TERM_DIR.get(b, (0, -1))[0] else []) + [b]
            CH[ci] = pa + [(pa[-1][0], yr), (pb[0][0], yr)] + pb; INTERNAL.add(ci)
    legs_ = []
    for ci, end, t in DROPS:
        if not (vx0 <= t[0] <= vx1 and vy0 <= t[1] <= vy1) or ci in drop or ci in INTERNAL or TERM_DIR.get(t, (0, -1)) != (0, -1): continue   # downward terminals inside THIS vault
        seq = CH[ci] if end == 0 else CH[ci][::-1]
        j = 0
        while j + 1 < len(seq) and abs(seq[j + 1][0] - t[0]) < 0.01: j += 1
        if j + 1 >= len(seq) or seq[j][1] > t[1] + 0.5: continue      # rises (junction leg fed from below) or no turn
        if seq[j][1] <= vy0 - 4: continue                          # already turns below the floor
        k = j
        while k + 1 < len(seq) and abs(seq[k + 1][1] - seq[k][1]) < 0.05 * abs(seq[k + 1][0] - seq[k][0]) + 0.6: k += 1   # horizontal leg j..k (PDF runs may slope slightly)
        if k == j: continue
        go_left = seq[k][0] < seq[j][0]
        legs_.append((go_left, t[0], ci, end, j, k))
    for go_left in (True, False):
        grp = sorted([g for g in legs_ if g[0] == go_left], key=lambda g: g[1], reverse=not go_left)
        for rank, (_gl, _x, ci, end, j, k) in enumerate(grp):
            seq = CH[ci] if end == 0 else CH[ci][::-1]
            y_old = seq[j][1]; y_new = vy0 - (16 if VAULT_TIED[vnum] else 6) - 4 * rank
            lo, hi = min(seq[j][0], seq[k][0]), max(seq[j][0], seq[k][0])
            HOPS = [((a[0], a[1] + y_new - y_old), (b[0], b[1] + y_new - y_old), (ap[0], ap[1] + y_new - y_old))
                    if abs((a[1] + b[1]) / 2 - y_old) < 1.5 and lo <= (a[0] + b[0]) / 2 <= hi else (a, b, ap) for a, b, ap in HOPS]
            # the leg's far end keeps its place; a vertical jog joins the lowered leg back to it (no diagonals)
            # structure boxes the map puts on this leg ride down with it (Ash V5091495: X5745268 / X5194396 sit on the
            # 350 JCN run to GS2818 way 4, not left floating above it)
            for bi, (ii, bc) in enumerate(BOX_INS):
                if lo - 2 <= bc[0] <= hi + 2 and abs(bc[1] - y_old) < 4:
                    dy_ = y_new - bc[1]
                    copies[ii]["dy"] = round(copies[ii]["dy"] + dy_, 4)
                    r_ = INSERTS[ii]; INSERTS[ii] = (r_[0], r_[1], r_[2] + dy_, r_[3], r_[4], r_[5])
                    BOX_INS[bi] = (ii, (bc[0], y_new)); OWN_BOX[OWN_BOX.index(bc)] = (bc[0], y_new)
                    BOX_MOVED.append((bc, dy_)); BOX_FROM[(bc[0], y_new)] = BOX_FROM.get(bc, bc)
            seq = seq[:j] + [(p[0], y_new) for p in seq[j:k]] + [(seq[k][0], y_new)] + seq[k:]
            CH[ci] = seq if end == 0 else seq[::-1]

# ---------------------------------------------------------------- V5770309 (Kevin, 2026-11-25: "still quite messy")
# The page-10 paths out of GS0136 climb back into the vault and leave on a slant. Ash drops both ways straight out of the
# vault. Square routes instead:
#   way 1 -> straight down to the substation's level, then across into the sub circle's edge;
#   way 2 -> down below the tie names (vault floor - 16), across past the vault's right edge, up to V5122231, then on
#   along its own path from that box.
_fx0, _fy0, _fx1, _fy1 = VAULT_FLOOR["V5770309"]
_ci = WAY_OF.get(("GS0136", 0))
if _ci is not None:
    _onway = lambda p_: min(math.dist(p_, w_) for w_ in WAYPTS) < 0.05           # the end sitting on the switch way
    t_ = CH[_ci][0] if _onway(CH[_ci][0]) else CH[_ci][-1]
    CH[_ci] = [t_, (t_[0], sub[1]), (sub[0] - 5.0, sub[1])]
_ci = WAY_OF.get(("GS0136", 1))
if _ci is not None:
    seq_ = CH[_ci] if min(math.dist(CH[_ci][0], w_) for w_ in WAYPTS) < 0.05 else CH[_ci][::-1]
    t_ = seq_[0]
    bx_ = min(OWN_BOX, key=lambda b_: min(math.dist(b_, p_) for p_ in seq_))          # V5122231
    k_ = min(range(len(seq_)), key=lambda i_: math.dist(seq_[i_], bx_))
    yb_ = seq_[k_][1]; xr_ = _fx1 + 4.0; yl_ = _fy0 - 16.0        # tie-vault floor: clear of the tie name
    CH[_ci] = [t_, (t_[0], yl_), (xr_, yl_), (xr_, yb_)] + seq_[k_:]

# ---------------------------------------------------------------- P5380189 / PME4619 (Kevin 2026-11-25: "conduit coming from
# this equipment needs a very close look, its wrong"). On page 10 the extractor chained two cables through the fuse
# squiggle above PME4619: pothead 1226172E's green main ran on, doubled back, and dropped to P5380189. The map has
#   green: pothead tip -> east along the main, into the loop that comes up from PME4619 terminal 1;
#   black: P5380189 -> up -> east at a clear level -> down into PME4619 terminal 3 (its top-left terminal).
_t3 = OWN_PME["PME4619"]
_ph_tips = [tip for _tl, tip, _a in PH_LIST]
_c38 = [ci_ for ci_, ch_ in enumerate(CH) if ci_ not in drop and len(ch_) == 2
        and any(math.dist(ch_[e_], _t3) < 0.05 for e_ in (0, -1)) and abs(ch_[0][0] - ch_[1][0]) < 0.3]
for ci_, ch_ in enumerate(CH):
    if ci_ in drop or not _c38: continue
    a_tip = min(math.dist(ch_[0], t_) for t_ in _ph_tips) < 1.0
    b_tx = min(math.dist(ch_[-1], q_) for q_ in OWN_TX) < 12.0
    near3 = any(math.dist(p_, _t3) < 30 for p_ in ch_)
    if not (a_tip and b_tx and near3): continue
    # where the run turns back west: the first vertex after which x decreases for good
    k_ = next(i_ for i_ in range(1, len(ch_) - 1) if ch_[i_ + 1][0] < ch_[i_][0] - 3)
    loop_ends = [CH[cj_][e_] for cj_ in range(len(CH)) if cj_ not in drop and cj_ != ci_ for e_ in (0, -1)
                 if abs(CH[cj_][e_][1] - ch_[1][1]) < 3 and 0 < CH[cj_][e_][0] - ch_[1][0] < 15]
    green = ch_[:2] + ([(loop_ends[0][0], ch_[1][1]), loop_ends[0]] if loop_ends else [ch_[k_]])
    tx_end = ch_[-1]
    # Ash: P5380189's riser stands 36.4 ft left of the PME, leaving room for the P#/PME# pair between them. Slide the
    # transformer (its copy, its INSERTS record and OWN_TX entry) so its feed lands there.
    dx_ = (_t3[0] - 36.4) - tx_end[0]
    i_tx = min((i for i, r in enumerate(INSERTS) if r[0] == "SGL_TRAN_DE"), key=lambda i: math.dist(INSERTS[i][1:3], tx_end))
    r_ = INSERTS[i_tx]; copies[i_tx]["dx"] = round(copies[i_tx]["dx"] + dx_, 4)
    INSERTS[i_tx] = (r_[0], r_[1] + dx_, r_[2], r_[3], r_[4], r_[5])
    j_tx = min(range(len(OWN_TX)), key=lambda j: math.dist(OWN_TX[j], (r_[1], r_[2])))
    if (r_[1], r_[2]) in TX_ROT: TX_ROT[(r_[1] + dx_, r_[2])] = TX_ROT[(r_[1], r_[2])]
    OWN_TX[j_tx] = (OWN_TX[j_tx][0] + dx_, OWN_TX[j_tx][1])
    tx_end = (tx_end[0] + dx_, tx_end[1])
    TX_LABEL_AT["P5380189"] = OWN_TX[j_tx]          # its label goes with the moved transformer, not the nearer PME
    top3 = CH[_c38[0]][0] if math.dist(CH[_c38[0]][1], _t3) < 0.05 else CH[_c38[0]][1]
    ny3 = _t3[1] + 7.0           # Ash: up 7 ft from terminal 3, then the left turn toward P5380189
    black = [tx_end, (tx_end[0], ny3), (_t3[0], ny3), _t3]
    ins("SGL_TRAN_FUSED", _t3[0], ny3)    # the map's fuse at the turn: SGL_TRAN_FUSED r0, pointing right (Ash PME4619)
    PME_LAB_AT["PME4619"] = ((_t3[0] - 22.0, _t3[1] + 1.3), (_t3[0] - 20.6, _t3[1] - 3.2))   # Ash spots, 2 ft further left to clear the "3"   # P# / PME# beside it, under the cable
    CH[ci_] = green
    CH[_c38[0]] = black
    break

# ---------------------------------------------------------------- capbanks fed by a cable on the map (Ash 0221838)
# The page-10 line from the pothead turns down into the bank's "A". Ash keeps the overhead line straight on to the BLF
# (tail -> corner -> BLF left terminal) and draws the drop as a SingleLine leader from that corner to the bank, which is
# mirrored (bank right of A). Kevin 2026-11-25: the run between that corner and the BLF was missing.
BLF_P = R(247.6, 488.3)
CAPBANKS = [(245.9, 500.7, "0221838", "1973301E", True), (390.8, 526.6, "0006161", "2319540E", False),
            (156.7, 556.2, "0006533", "1226170E", False)]
CAP_FED = {}
for x10, y10, eq, st, bank_right in CAPBANKS:
    pc = R(x10, y10)
    hit = [(ci, e) for ci, ch in enumerate(CH) if ci not in drop for e in (0, -1) if math.dist(ch[e], pc) < 6]
    if not hit: continue
    ci, e = hit[0]; seq = CH[ci][::-1] if e == 0 else CH[ci]          # seq ends at the bank's "A"
    A = seq[-1]
    j = next(k for k in range(len(seq) - 1) if abs(seq[k + 1][1] - seq[k][1]) > abs(seq[k + 1][0] - seq[k][0]))  # first drop
    corner = seq[j]
    blf_l = (BLF_P[0] - 5.0, BLF_P[1])
    if 0 < blf_l[0] - corner[0] < 30 and abs(blf_l[1] - corner[1]) < 4:
        # straight on to the BLF terminal -- no 90-degree jog to make up a foot of height (Kevin); like Ash the run may
        # slope slightly. The leader starts on that line, above the old corner.
        CH[ci] = [seq[0], blf_l]                      # one straight run: pothead tail -> BLF left terminal
        a_, b_ = CH[ci][-2], blf_l
        t_ = (corner[0] - a_[0]) / (b_[0] - a_[0]) if b_[0] != a_[0] else 0
        corner = (corner[0], a_[1] + (b_[1] - a_[1]) * max(0, min(1, t_)))
    else:
        CH[ci] = seq[:j + 1]
    CAP_FED[eq] = (corner, A)

# ---------------------------------------------------------------- per-segment linetype (tile review, 2026-11-25)
# The extractor chains solid and broken pieces into one cable (the run east of BF07957 is solid to 1198051E, then
# dashed up through 210999E). Classify each ORIGINAL PDF segment by how much of it the map's strokes cover
# (solid >= 0.9) and, for broken pieces, by tick marks (UG) or not (OH 1-phase); where the class changes, split the
# drawn cable at the matching vertex. Pieces shorter than 12 ft are not split off.
import fitz as _fitz
_pg10 = _fitz.open(r"C:/civ3dmcp/jobs/Singleline/Ash/CIRCUIT MAPS - CONSOLIDATED ASH 4KV CUTOVER FINAL.pdf")[9]
_STK = []
for _dr in _pg10.get_drawings():
    if 1.0 <= (_dr.get("width") or 0) <= 1.4 and _dr.get("color"):
        for _it in _dr["items"]:
            if _it[0] == "l": _STK.append(((_it[1].x, _it[1].y), (_it[2].x, _it[2].y)))
_SG = {}
for _a, _b in _STK:
    for _gx in range(int(min(_a[0], _b[0]) // 4), int(max(_a[0], _b[0]) // 4) + 1):
        for _gy in range(int(min(_a[1], _b[1]) // 4), int(max(_a[1], _b[1]) // 4) + 1):
            _SG.setdefault((_gx, _gy), []).append((_a, _b))
def _covered(p, tol=0.55):
    for (a, b) in _SG.get((int(p[0] // 4), int(p[1] // 4)), []):
        dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        if math.dist(p, (a[0] + t * dx, a[1] + t * dy)) < tol: return True
    return False
def _ticks(a, b):
    """short strokes crossing segment a-b at a steep angle: the UG pattern's ticks"""
    L = math.dist(a, b) or 1; ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L; n = 0
    for (p, q) in _STK:
        l = math.dist(p, q)
        if not (0.5 < l < 3.5): continue
        if abs(((q[0] - p[0]) * ux + (q[1] - p[1]) * uy) / l) > 0.5: continue
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2); t = (m[0] - a[0]) * ux + (m[1] - a[1]) * uy
        if 0 < t < L and abs((m[0] - a[0]) * uy - (m[1] - a[1]) * ux) < 1.2: n += 1
    return n
SPLITS = []
def _runs_along(src):
    """Walk the original PDF chain at 0.6 pt steps; a sample is 'solid' if the map's strokes cover the window of
    +-4 pt around it at >= 0.93 (a dash pattern drops well below that). Returns [[class, s0, s1]] in arc length,
    runs shorter than 12 pt folded into their neighbour, and the arc-length -> point function."""
    P10 = [to10(p) for p in src]; segL = [math.dist(a, b) for a, b in zip(P10, P10[1:])]; tot = sum(segL)
    def at(sv):
        for (a, b), L in zip(zip(P10, P10[1:]), segL):
            if sv <= L or L == segL[-1]:
                t = 0 if L == 0 else min(1, sv / L); return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            sv -= L
        return P10[-1]
    n = int(tot / 0.6)
    if n < 20: return [], at
    hit = [_covered(at(i * 0.6)) for i in range(n)]
    w = 7; cls = []
    for i in range(n):
        lo, hi = max(0, i - w), min(n, i + w + 1); cls.append("solid" if sum(hit[lo:hi]) / (hi - lo) >= 0.93 else "broken")
    runs = []
    for i, c_ in enumerate(cls):
        if runs and runs[-1][0] == c_: runs[-1][2] = (i + 1) * 0.6
        else: runs.append([c_, i * 0.6, (i + 1) * 0.6])
    out = []
    for r in runs:
        if out and (r[2] - r[1] < 12 or out[-1][0] == r[0]): out[-1][2] = r[2]
        else: out.append(r)
    if len(out) > 1 and out[0][2] - out[0][1] < 12: out[1][1] = out[0][1]; out.pop(0)
    return out, at
def split_by_pattern(ci, pts, lt):
    src = LW["conductors"][ci]["pts"]
    runs, at = _runs_along(src)
    if len(runs) < 2: return [(pts, lt)]
    def lt_of(c_, s0, s1):
        if c_ == "solid": return OH
        a10, b10 = at(s0), at(s1)
        ticks = _ticks(a10, b10) if math.dist(a10, b10) > 1 else 0
        if ticks >= 2 or lt in (UG, "SGL-UG2PH"): return lt if lt in (UG, "SGL-UG2PH") else UG
        return lt if lt in ("SGL-OH1", "SGL-OH1PHwN") else "SGL-OH1"
    pieces, start, prev = [], 0, runs[0]
    for r in runs[1:]:
        q10 = at(r[1]); q = Rref((_ax + _s * (q10[0] - _bx), _ay + _s * (q10[1] - _by)))
        j = min(range(len(pts)), key=lambda i: math.dist(pts[i], q))
        if math.dist(pts[j], q) < 5 and start < j < len(pts) - 1:
            pieces.append((pts[start:j + 1], lt_of(prev[0], prev[1], prev[2]))); start = j; prev = r
        else:
            prev = [prev[0], prev[1], r[2]]
    pieces.append((pts[start:], lt_of(prev[0], prev[1], prev[2])))
    if len(pieces) < 2 or len({l_ for _p, l_ in pieces}) < 2: return [(pts, lt)]
    SPLITS.append((ci, lt, [(round(sum(math.dist(a, b) for a, b in zip(p_, p_[1:]))), l_) for p_, l_ in pieces]))
    return pieces

# ---------------------------------------------------------------- straight runs stay straight
# The extractor keeps every PDF sub-path joint, so a straight diagonal comes out as several short, slightly kinked
# segments (P5438567 -> X5177781). The UG pattern restarts at every vertex and never shows its dots. Drop interior
# vertices lying within 0.6 ft of the chord of their neighbours, unless another cable ends there.
def straighten(pts, ci):
    ends = [CH[cj][k] for cj in range(len(CH)) if cj != ci and cj not in drop for k in (0, -1)]
    out = list(pts); i = 1
    while i < len(out) - 1:
        a, b, c_ = out[i - 1], out[i], out[i + 1]; L = math.dist(a, c_)
        dev = abs((c_[0] - a[0]) * (b[1] - a[1]) - (c_[1] - a[1]) * (b[0] - a[0])) / L if L > 1e-6 else 0
        if dev < 0.6 and not any(math.dist(b, e) < 1.0 for e in ends):
            out.pop(i); STRAIGHTENED[0] += 1
        else: i += 1
    return out
STRAIGHTENED = [0]

# ---------------------------------------------------------------- conductors
# Linetype from the PDF dash pattern (checked against Ash):
#   solid -> SGL-OH3PH; dashed with no ticks -> overhead 1-phase: with dot markers SGL-OH1PHwN, else SGL-OH1;
#   dash+tick -> underground: SGL-UG2PH for the loop feeding the 1-phase A/B pads north of Glenwood (Ash: all 3 runs
#   there are UG2PH -- two phases, A and B), else SGL-UG3PH
# A cable whose last run drops onto a pothead tip but passes level with a structure box sitting right over that tip
# ends at the box centre instead (PDF / Ash X5177783: the run enters the box and meets the riser there; the stub pass
# then joins the tip up into the box).
BOX_END = []
for ci in range(len(CH)):
    if ci in drop or len(CH[ci]) < 3: continue
    for end in (0, -1):
        seq = CH[ci] if end == 0 else CH[ci][::-1]
        tip = next((tp for _t, tp, _a in PH_LIST if math.dist(seq[0], tp) < 1.0), None)
        if not tip: continue
        bc = next((b_ for b_ in OWN_BOX if abs(b_[0] - tip[0]) < 1.5 and 3 < b_[1] - tip[1] < 15 and abs(seq[1][1] - b_[1]) < 1.5), None)
        if not bc: continue
        seq = [bc] + seq[1:]
        CH[ci] = seq if end == 0 else seq[::-1]; BOX_END.append((ci, tuple(round(v, 1) for v in bc)))
print("cables ended in the box over their pothead:", BOX_END)
PS_SYMBOLS = [R(260.0, 592.4), ps_pt]           # PS 0365 (closed X) and Royer's PS 0906 (open bars) as drawn on page 10
for ci, c in enumerate(LW["conductors"]):        # the X arms / open bars of a pole switch are symbol strokes, not cable
    if ci not in drop and sum(math.dist(u, v) for u, v in zip(CH[ci], CH[ci][1:])) < 30             and all(min(math.dist(p, s_) for s_ in PS_SYMBOLS) < 16 for p in CH[ci]):
        drop.add(ci)
for ci, c in enumerate(LW["conductors"]):
    # length of the FINAL route, not the original PDF stroke (P5380189's rebuilt cable began as a 2.4 pt stub)
    if ci in drop or sum(math.dist(u_, v_) for u_, v_ in zip(CH[ci], CH[ci][1:])) < 3 * S: continue
    pts = CH[ci]
    on_way = any(math.dist(e, w) < 0.05 for e in (pts[0], pts[-1]) for w in WAYPTS)
    # a short run from a pothead's tip into a structure box is the underground side (Ash V5092568 -> 1972873E: UG3PH)
    on_tip = len(pts) == 2 and math.dist(pts[0], pts[1]) < 30 and any(
        math.dist(pts[k], tip) < 1.0 and any(math.dist(pts[1 - k], b_) < 6 for b_ in OWN_BOX)
        for k in (0, 1) for _t, tip, _a in PH_LIST)
    if not c["ug"] and not on_way and not on_tip:
        lt = OH
    elif not c["ug"] and on_tip:
        lt = UG                    # a cable on a pothead's tip is the underground side (Ash V5092568 -> 1972873E: UG3PH)
    elif not c["ug"]:
        lt = UG                    # Ash: every cable off a gear-switch way or junction leg is underground (73 of 75 UG3PH)
    elif c.get("ticks", 1) <= 1:
        nd = sum(1 for d in DOTS if min(math.dist(d, p) for p in pts) < 6)
        lt = "SGL-OH1PHwN" if nd >= 3 else "SGL-OH1"
    elif min(to10(p)[1] for p in c["pts"]) < 140:
        lt = "SGL-UG2PH"
    else:
        lt = UG
    others = [(u, v) for cj, o in enumerate(CH) if cj != ci and cj not in drop for u, v in zip(o, o[1:])] + TIE_SEGS
    for piece, plt in split_by_pattern(ci, pts, lt):
        pl_hopped(straighten(piece, ci), plt, C2L, HOPS, others)

for pts_, lt_ in EXTRA:
    pl(pts_, lt_, layer=C2L)
for pts_ in JEXTRA:
    pl(pts_, UG, layer=C2L)

# ---------------------------------------------------------------- poles
for q in pole_pts:
    ins("SGL_PO_WD_JO_IN", *q)

# ---------------------------------------------------------------- vaults (built after BS switches are placed, below)
# ---------------------------------------------------------------- junctions and other equipment (page-10 points)

p = R(240.1, 447.6); ins("SGL_BURD_SW_FUSED", *p, dyn={"Visibility": "Closed"})  # BS6094
ins("SGL_TRAN", p[0] + 10.1, p[1])                  # its secondary lead with the open arrow (Ash BS6094: SGL_TRAN r0 at +10.1)
PLACED["BS6094"] = (p[0] - 10.2, p[1] - 4.8, p[0] + 10.1, p[1] + 4.8)
VAULT_BOXES = []
for vnum, members in VAULTS:
    bb = [PLACED[m] for m in members]
    x0 = min(b[0] for b in bb) - 4; x1 = max(b[2] for b in bb) + 4
    for m in members:                                    # a label set beside its block widens the vault to hold it
        if m in LABEL_AT: x0 = min(x0, LABEL_AT[m][0] - GLYPH_W * len(m) / 2 - 2.5)
    y0 = min(b[1] for b in bb) - 4
    top_blocks = max(b[3] for b in bb)
    for m, b in zip(members, bb):                       # device number inside, centred over its block
        if m in LABEL_AT: tx(m, *LABEL_AT[m])
        else: tx(m, LABEL_X.get(m, (b[0] + b[2]) / 2), top_blocks + 4.0)
    y1 = top_blocks + 7.5
    box(((x0 + x1) / 2, (y0 + y1) / 2), d1=y1 - y0, d2=x1 - x0)
    _c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]; BOX_EDGES.extend(zip(_c, _c[1:] + _c[:1]))
    VAULT_BOXES.append((vnum, x0, y0, x1, y1, any(TIES_AT.get(m) for m in members)))
    # V-number outside, above the top edge, slid along it to a spot no cable crosses (Ash V5091496 sits clear of the
    # T and R cables); nearest the middle wins
    OBS = obstacles(); wv = GLYPH_W * len(vnum)
    cands = [x0 + wv / 2 + 0.5 * i for i in range(int(max(0, (x1 - x0 - wv)) / 0.5) + 1)] or [(x0 + x1) / 2]
    vx = min(cands, key=lambda x: 100 * n_hits(text_rect(vnum, x, y1 + 2.7, 0, pad=0.8), OBS, []) + abs(x - (x0 + x1) / 2))
    tx(vnum, vx, y1 + 2.7)
    for m in members:                                    # tie name under the vault, on the tie circuit's layer
        if TIES_AT.get(m):
            hx, tie = TIES_AT[m]
            tx(tie, hx, y0 - 3.5, layer=TIE[tie]); tx("FULLERTON", hx, y0 - 9.0, layer=TIE[tie])
for x10, y10 in [(462.7, 41.7), (447.2, 73.6), (445.9, 84.7), (342.3, 442.9), (378.6, 539.8)]:
    ins("SGL_TRAN_BP", *R(x10, y10)); OWN_TX.append(R(x10, y10))                                            # 1P BURD/PM dots
ins("SGL_SUB_CUST_PP", *R(271.8, 262.9))                                        # "C" circle = customer substation
ins("SGL_SIG_CRI", *R(258.0, 547.4))                                            # "S" triangle
q = Rref(LW["boxes"][10]["c"]); ins("SGL_FERRO", q[0] - 16, q[1] - 14)                                              # quartered red circle
p = R(247.6, 488.3); ins("SGL_BLF", *p)                                         # BF07957 fuse on the line
for _t, _dy in (("1972873E", -5.7), ("BF07957", -10.6), ("80A", -15.1)):      # Ash BF07957 stack, left-aligned
    tx(_t, p[0] - 6.8 + CW * len(_t) / 2, p[1] + _dy); LOCKED_TEXT.add(_t)
# PS 0365 (Ash): the X sits ON the line, rotated with it (the line is broken at its +-14 ft ends, see split_at_switches);
# the PS circle hangs 13.2 ft below the X; FI07781's tip is at X + (9.3, -14.6), pennant pointing back at the circle.
_x0 = R(260.0, 592.4)
_xs = min(((nearest_on(_x0, u_, v_), u_, v_) for ci_, ch_ in enumerate(CH) if ci_ not in drop for u_, v_ in zip(ch_, ch_[1:])),
          key=lambda z: math.dist(z[0], _x0))
PS365, _a = _xs[0], readable(math.degrees(math.atan2(_xs[2][1] - _xs[1][1], _xs[2][0] - _xs[1][0])))
ins("SGL_SW_CL_POLE", *PS365, rot=_a % 360)
ins("SGL_PO_SW", PS365[0] - 0.4, PS365[1] - 13.2, attrs={"DEVICE_NUMBER": "0365", "POLE_NUMBER": "4078772E"}, dyn={"Visibility1": "PS"})
for x10, y10, eq, st, bank_right in CAPBANKS:
    p = R(x10, y10)
    if eq in CAP_FED:                                    # bank at the old cable end, leader from the line's corner (Ash)
        corner, A = CAP_FED[eq]
        ins("SGL_CAPBANK", *A, mirror=bank_right, attrs={"Equipment #": eq, "Kvar": "1200", "Structure #": st},
            dyn={"Autometed/Switched/Fixed": "Automatic"})
        pl([corner, A], layer=SL)
        continue
    conn = min((nearest_on(p, u, v) for ch in CH for u, v in zip(ch, ch[1:])), key=lambda q: math.dist(q, p))
    ip = (conn[0] - 8.0, conn[1] + 14.0)                 # insertion = end of the "A" tick; bank sits left of it
    ins("SGL_CAPBANK", *ip, attrs={"Equipment #": eq, "Kvar": "1200", "Structure #": st},
        dyn={"Autometed/Switched/Fixed": "Automatic"})
    pl([ip, conn], layer=SL)                             # diagonal leader to the conductor
def fi_at(x10, y10, num, rating):
    p = R(x10, y10)
    best = min(((math.dist(p, nearest_on(p, u, v)), nearest_on(p, u, v)) for ch in CH for u, v in zip(ch, ch[1:])),
               key=lambda z: z[0])
    q = best[1]
    ins("SGL_OH_FI", q[0] + 1.5, q[1], attrs={"STRUCTURE_NUMBER": "", "FI_NUMBER": num, "CURRENT_RATING": rating})
def fi_leader(tip10, conn10, num, rating):
    """FI drawn as on the map (Ash FI07808): the pennant's tip is the block insertion, at the PDF tip; a thin SingleLine
    polyline runs from the tip to the point on the conduit the map's red leader touches. The pennant points away from
    the conduit, so it is mirrored when the conduit is to its right."""
    tip = R(*tip10); c = R(*conn10)
    q = min((nearest_on(c, u, v) for ci, ch in enumerate(CH) if ci not in drop for u, v in zip(ch, ch[1:])),
            key=lambda z: math.dist(z, c))
    # mirrored copy = x-scale -40 with readable attributes (plugin fix, SimsUDS/Civil3D-mcp#13), exactly like Ash
    ins("SGL_OH_FI", *tip, mirror=q[0] > tip[0], attrs={"STRUCTURE_NUMBER": "", "FI_NUMBER": num, "CURRENT_RATING": rating})
    pl([tip, q], layer=SL)
fi_leader((447.2, 360.2), (458.0, 361.9), "FI07808", "600A")   # red leader on the sheet: tip -> conduit above 1932825E
ins("SGL_OH_FI", PS365[0] + 9.3, PS365[1] - 14.6, attrs={"STRUCTURE_NUMBER": "", "FI_NUMBER": "FI07781", "CURRENT_RATING": "600A"})

# ---------------------------------------------------------------- small symbols off the sheet (singleline_tools/extract_symbols.py)
# Kevin 2026-11-25: "we are missing so many small details". Every fuse zig-zag / ground tap the extractor finds on the page
# gets its block unless one is already there: SGL_TRAN_FUSED at the attachment, rotated the way it hangs (r270 = down,
# 0 = right; Ash V5091497, PME4619); a bare ground tap gets SGL_TRAN on a 3.25 ft stub (Ash J496 leg 3).
# Chevrons (elbows) are only reported: transformer blocks draw their own, junction legs get SGL_LBE from JLBE.
SYMS = json.load(open(r"C:/civ3dmcp/jobs/Singleline/_analysis/p10_symbols.json"))["symbols"]
SYM_REPORT = []
_segs_all = [(u_, v_) for ci_, ch_ in enumerate(CH) if ci_ not in drop for u_, v_ in zip(ch_, ch_[1:])]
for sy in SYMS:
    if sy["kind"] not in ("fuse", "tap") or not sy.get("attach"): continue
    a0 = Rref(sy["attach"])
    a = min((nearest_on(a0, u_, v_) for u_, v_ in _segs_all), key=lambda q: math.dist(q, a0))
    if math.dist(a, a0) > 6: a = a0
    have = [r for r in INSERTS if r[0] in ("SGL_TRAN_FUSED", "SGL_TRAN") and math.dist(r[1:3], a) < 30]   # vaults are condensed: blocks sit a few ft off their PDF spot
    if have:
        SYM_REPORT.append(("ok", sy["kind"], sy["page_c"])); continue
    dx, dy = sy["dir"][0], -sy["dir"][1]                       # PDF y runs down
    rot = round(math.degrees(math.atan2(dy, dx)) / 90) * 90 % 360
    if sy["kind"] == "fuse":
        ins("SGL_TRAN_FUSED", *a, rot=rot)
    else:
        u_ = (math.cos(math.radians(rot)), math.sin(math.radians(rot)))
        b = (a[0] + 3.25 * u_[0], a[1] + 3.25 * u_[1])
        ins("SGL_TRAN", *b, rot=rot); pl([a, b], UG, layer=C2L)
    SYM_REPORT.append(("added", sy["kind"], sy["page_c"], [round(v, 1) for v in a], rot))
for sy in SYMS:
    if sy["kind"] != "chevron": continue
    c = Rref(sy["c"])
    near_blk = [r[0] for r in INSERTS if math.dist(r[1:3], c) < 25 and r[0] in
                ("SGL_LBE", "SGL_TRAN_DE", "SGL_TRAN_PM", "SGL_TRAN_BP", "SGL_TRAN_PM_1PH_DEDF_NFUSED") or
                (r[0].startswith("SGL_PMH_PME") and math.dist(r[1:3], c) < 20)]
    SYM_REPORT.append(("chevron-ok" if near_blk else "chevron-CHECK", sy["page_c"], near_blk[:2]))
print("small symbols:", [r for r in SYM_REPORT if r[0] != "ok"])
print("linetype splits:", SPLITS)
print("kinked vertices straightened:", STRAIGHTENED[0])
print("boxes lowered with their vault-floor leg:", [(tuple(round(v, 1) for v in b), round(d, 1)) for b, d in BOX_MOVED])

# ---------------------------------------------------------------- labels: text read off the sheet, position/angle from the PDF
LTEXT = {
    0: "P5091324", 1: "P5091469", 2: "P5091470", 3: "P5091471", 4: "P5438567", 11: "X5177781", 15: "1659859E",
    16: "FD07534", 17: "X5177783", 18: "864024E", 19: "864028E", 42: "6 C", 49: "864030E", 51: "4 A",
    54: "1932825E", 86: "V5091497", 55: "V5091495", 56: "GS2818", 57: "BS0184", 58: "V5091496", 59: "J496",
    72: "J495", 93: "X5745268", 94: "350 JCN", 108: "X5194396", 110: "P5319466", 111: "P5770324", 121: "1214527E",
    61: "M5091494", 62: "P5745172", 87: "V5091493", 88: "GS2819", 113: "750 CLP", 112: "1000 JCN", 102: "1/0 JCN",
    107: "P5745173", 120: "PME0223", 114: "V5091492", 125: "BS6094", 123: "V5091492", 127: "3/25 KVA",
    136: "1000 JCN", 137: "80A", 138: "BF07957", 146: "1972873E", 134: "1171109E", 135: "4403255E", 144: "1361961E",
    145: "V5092568", 149: "4616959E", 150: "2205724E", 151: "1198051E", 128: "B5194230", 130: "1719832E", 131: "4 A",
    139: "210999E", 140: "817531E", 152: "817532E", 153: "817533E", 122: "177296E", 129: "146713E", 141: "1747637E",
    154: "691323E", 156: "P5438660", 157: "1226172E", 20: "V5092205", 21: "OS2899", 22: "V5092205", 23: "GS2898",
    24: "P5435982", 32: "1000 CLP", 33: "P5743057", 37: "350 CLP", 38: "X5092206", 44: "1/0 CLP", 45: "X5528417",
    46: "1/0 JCN", 47: "P5435981", 48: "PMH5981", 34: "P5528418", 43: "PME4737", 50: "P5528419", 160: "P5487433",
    166: "PME4619", 167: "350 CLP", 169: "V5092570", 171: "GS2979", 174: "1484315E", 175: "1484316E", 176: "362613E",
    185: "P5380189", 187: "X5487434", 192: "P5487406", 197: "1314706E", 198: "1/0 JCN", 202: "1000 CLP",
    206: "V5092573", 205: "J573", 210: "4602853E", 209: "4 A", 208: "4616905E", 218: "4324099E", 219: "M5122232",
    211: "4078772E", 212: "4576852E", 221: "1628371E", 222: "336 A", 225: "1660505E", 226: "4079422E",
    177: "2319539E", 178: "1683827E", 179: "2281297E", 195: "P5631867", 227: "923958E", 229: "P5319624",
    238: "665846E", 201: "4403258E", 207: "4324097E", 233: "P5122498", 240: "P5711986", 244: "584670E",
    253: "V5770309", 254: "GS0137", 259: "1000 CLP", 260: "336 A", 268: "1117354E", 269: "1/0 A", 270: "1197141E",
    273: "4407323E", 275: "V5122231", 283: "P5319217", 230: "P5438918", 232: "V5177541",
    161: "1226171E", 162: "146717E",
    98: "1/0 JCN", 183: "1/0 A", 196: "4 A", 215: "4324098E", 264: "1000 JCN C", 274: "1000 JCN C",   # tile review
}
LBL = {c["id"]: c for c in LW["labels"]}
SKIP = {20, 21, 22, 23, 87, 88, 55, 56, 72, 58, 57, 59, 169, 171, 206, 205, 114, 125, 123, 253, 254, 137, 138, 146}
import re as _re
PH_TAILS = [(t, a) for t, tip, a in PH_LIST]
def place_label(txt, p):
    """Ash convention: pole# above its pole (or beside a pothead tail), P# above its transformer,
    P#/PME# stacked left of a PME, X/V/M# above its box. Returns True if placed."""
    if _re.fullmatch(r"\d{5,8}E", txt):
        cands = [(math.dist(p, q), "pole", q) for q in pole_pts] + [(math.dist(p, q), "ph", (q, a)) for q, a in PH_TAILS]
        cands = [c for c in cands if c[0] < 40 and str(c[2]) not in TAKEN]
        if not cands: return False
        d, k, o = min(cands, key=lambda z: z[0]); TAKEN.add(str(o))
        if k == "pole": tx(txt, o[0], o[1] + 7.0)
        else:
            q, a = o
            if abs(math.sin(math.radians(a))) > 0.7: tx(txt, q[0] + 13.0, q[1] + 1.5)    # vertical pothead: beside
            else: tx(txt, q[0], q[1] + 7.0)
        return True
    if _re.fullmatch(r"P\d{7}", txt) and txt in TX_LABEL_AT:
        q = TX_LABEL_AT[txt]; TAKEN.add(str(q))
        if txt == "P5380189":           # P# and "LF" stacked beside the transformer, clear of the riser and its elbows
            tx(txt, q[0] + 4.5 + CW * 4, q[1] + 2.0); tx("LF", q[0] + 4.5 + CW * 1, q[1] - 2.6)
        else: tx(txt, q[0], q[1] + 9.0)
        return True
    if _re.fullmatch(r"P\d{7}", txt):
        cands = [(math.dist(p, q), "tx", q) for q in OWN_TX] + [(math.dist(p, q), "pme", q) for q in OWN_PME.values()]
        cands = [c for c in cands if c[0] < 60 and str(c[2]) not in TAKEN]
        if not cands: return False
        d, k, q = min(cands, key=lambda z: z[0]); TAKEN.add(str(q))
        if txt == "P5380189": tx(txt, q[0], q[1] + 13.5); tx("LF", q[0], q[1] + 8.5)
        elif k == "tx" and TX_ROT.get(q) == 0:
            # top-fed TRAN_DE (elbows above the box): Ash sets the P# beside the chevrons, centre (+-12.5, +9),
            # never across them. Take the side that sits on fewer lines/labels (right on a tie).
            OBS, RECTS = obstacles(), placed_text_rects()
            sx = min((12.5, -12.5), key=lambda dx: n_hits(text_rect(txt, q[0] + dx, q[1] + 9.0, 0), OBS, RECTS) + (0 if dx > 0 else 0.5))
            tx(txt, q[0] + sx, q[1] + 9.0)
        elif k == "tx" and TX_ROT.get(q) in (90, 270): tx(txt, q[0], q[1] + 7.3)
        elif k == "tx": tx(txt, q[0], q[1] + 9.3)
        else: tx(txt, q[0] - 16.0, q[1] + 9.5)
        return True
    if txt in OWN_PME:                                   # PME#: under its P#, stacked left of the PME
        q = OWN_PME[txt]
        if txt in PME_LAB_AT:
            (px_, py_), (mx_, my_) = PME_LAB_AT[txt]; tx(PME_P[txt], px_, py_); tx(txt, mx_, my_)
        elif PME_LAB.get(txt):                             # horizontal PME (Ash P5435981): pair above, left-aligned on terminal 1
            lx, ly = PME_LAB[txt]
            tx(PME_P[txt], lx + CW * len(PME_P[txt]) / 2, ly + 15.2); tx(txt, lx + CW * len(txt) / 2, ly + 10.5)
        else:
            tx(txt, q[0] - 16.0, q[1] + 4.5); tx(PME_P[txt], q[0] - 16.0, q[1] + 9.5)
        return True
    if txt in FORCE_POLE:                                # labels whose pole is ambiguous from position alone
        q = min(pole_pts, key=lambda z: math.dist(z, R(*FORCE_POLE[txt]))); TAKEN.add(str(q))
        tx(txt, q[0], q[1] + 7.0); return True
    if _re.fullmatch(r"[XVM]\d{7}", txt):
        cands = [(math.dist(p, BOX_FROM.get(q, q)), q) for q in OWN_BOX if math.dist(p, BOX_FROM.get(q, q)) < 60 and str(q) not in TAKEN]
        if not cands: return False
        q = min(cands)[1]; TAKEN.add(str(q)); q0 = BOX_FROM.get(q, q)
        if abs(p[0] - q0[0]) > 1.5 * abs(p[1] - q0[1]) + 8:       # the map sets it beside the box (M5091494): same side
            sg = 1 if p[0] > q0[0] else -1
            tx(txt, q[0] + sg * (6.0 + CW * len(txt) / 2), q[1]); return True
        tx(txt, q[0], q[1] + 7.0); return True
    return False
# Line text: cable sizes ("4 A", "1/0 JCN", "336 A", "3/25 KVA" excluded) and phase labels (AØ, BCØ, ABC, BCA, ACB ...).
# Ash puts both on the run itself: centred on the nearest segment, 2.7 ft off, rotated with it, on the side the PDF shows.
LINE_TEXT = _re.compile(r"(#?\d+(/\d+)?\s+(A|C|JCN|CLP|JCN C))|([ABC]{1,3}\s?Ø)|ABC|ACB|BAC|BCA|CAB|CBA")
def on_conductor(txt, p):
    segs = [(u, v) for ci, ch in enumerate(CH) if ci not in drop for u, v in zip(ch, ch[1:])]
    segs += [(u, v) for pts_, _lt in EXTRA for u, v in zip(pts_, pts_[1:])]
    # Candidates: every 1.5 ft along each run within 40 ft of the PDF label, on the allowed side(s).
    # Score = distance from the PDF position + a heavy penalty per line/label the text would sit on.
    OBS = obstacles(); RECTS = placed_text_rects(); w = CW * len(txt)
    best = None
    for u, v in segs:
        L = math.dist(u, v)
        if L < w + 2 or math.dist(p, nearest_on(p, u, v)) > 40: continue
        ang = readable(math.degrees(math.atan2(v[1] - u[1], v[0] - u[0]))); r = math.radians(ang)
        nx, ny = -math.sin(r), math.cos(r)
        n0 = nearest_on(p, u, v); pdf_top = (p[0] - n0[0]) * nx + (p[1] - n0[1]) * ny >= 0
        sides = [False]          # horizontal runs: above; vertical runs: left, reading up (Kevin 2026-11-25)
        k = 0
        while True:
            s_ = (w / 2 + 1 + 1.5 * k) / L
            if s_ > 1 - (w / 2 + 1) / L: break
            k += 1
            for flip in sides:
                a2 = ang; r2 = math.radians(a2); sg = -1 if flip else 1
                cx = u[0] + (v[0] - u[0]) * s_ - math.sin(r2) * 2.7 * sg; cy = u[1] + (v[1] - u[1]) * s_ + math.cos(r2) * 2.7 * sg
                score = math.dist((cx, cy), p) + 60 * n_hits(text_rect(txt, cx, cy, a2), OBS, RECTS) + (6 if flip == pdf_top else 0)
                if best is None or score < best[0]: best = (score, u, v, s_, flip)
    if best is None: return False
    _, u, v, s_, flip = best
    on_line(txt, u, v, t=s_, flip=flip)
    return True
lab_warn = []
TAKEN = set()
PME_P = {"PME4619": "P5487433", "PME0223": "P5745173", "PME4737": "P5528418", "PMH5981": "P5435981"}
FORCE_POLE = {"4079422E": (305.3, 591.0), "665846E": (309.8, 607.1)}
SKIP |= {i for i, t in LTEXT.items() if t in PME_P.values()}
ORDER = sorted((i for i in LTEXT if i not in SKIP and i in LBL),
               key=lambda i: min([math.dist(Rref(LBL[i]["c"]), q) for q in pole_pts + OWN_TX + OWN_BOX + [t for t, a in PH_TAILS]] or [99]))
ORDER = [i for i in ORDER if LTEXT[i] in FORCE_POLE] + [i for i in ORDER if LTEXT[i] not in FORCE_POLE]
LATER = []
for i in ORDER:
    txt = LTEXT[i]
    c = LBL.get(i)
    if c is None: lab_warn.append(i); continue
    n = len(txt.replace(" ", ""))
    if abs(c["n"] - n) > 2: lab_warn.append((i, txt, c["n"]))
    ang = readable(-c["ang"]) if c["n"] > 2 else 0
    p = Rref(c["c"])
    if LINE_TEXT.fullmatch(txt): LATER.append((txt, p, ang)); continue
    if not place_label(txt, p): tx(txt, p[0], p[1], ang)
for txt, p, ang in LATER:                 # line text last, so it can dodge every other label
    if not on_conductor(txt, p): tx(txt, p[0], p[1], ang)
# labels whose cluster id was not certain on the sheet: find them by position (page-10 points)
def label_near(txt, x10, y10):
    p = R(x10, y10)
    c = min(LW["labels"], key=lambda c: math.dist(Rref(c["c"]), p))
    q = Rref(c["c"]); tx(txt, q[0], q[1], readable(-c["ang"]) if c["n"] > 2 else 0)
print("label check (id, text, glyphs):", lab_warn)

# ---------------------------------------------------------------- Lawrence 7 ft roads
def to10_ref(p): return (p[0] / S + PX0, PY0 - p[1] / S)   # feet -> page-1 point
# Where a Lawrence cable follows a street (a parallel PDF street line within 15 ft on one side), that street line is
# replaced by a road 7 ft off the cable on the same side; a second edge line of the same street (parallel, within
# a further 22 ft on that side) is dropped too. Only outside Royer's cloud (Royer's sheet already handles its own streets).
P1CLOUD = json.load(open(r"C:/civ3dmcp/jobs/Singleline/_analysis/p1_extract.json"))["cloud"]
def in_p1(pt):
    x, y = pt; c = False; n = len(P1CLOUD)
    for i in range(n):
        x1, y1 = P1CLOUD[i]; x2, y2 = P1CLOUD[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
def _ang(a, b): return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
def _dang(a, b):
    d = abs(a - b); return min(d, 180 - d)
# The PDF strokes every street twice: keep one copy of each piece, or every node looks like a 4-way junction and the
# chained streets run out and back (the diagonal at M5122232 on S Lemon).
_seen = set(); _ded = []
for a, b in LW["streets"]:
    k = tuple(sorted(((round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2)))))
    if k not in _seen: _seen.add(k); _ded.append((a, b))
print("Lawrence street pieces:", len(LW["streets"]), "->", len(_ded), "after removing the doubled strokes")
LW["streets"] = _ded
LST = [(Rref(a), Rref(b)) for a, b in LW["streets"]]           # all Lawrence street segments, feet
sgrid = {}
for si, (a, b) in enumerate(LST):
    for t in (0, 0.5, 1):
        q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        sgrid.setdefault((int(q[0] // 40), int(q[1] // 40)), set()).add(si)
def _near_streets(p, r=60):
    out = set()
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            out |= sgrid.get((int(p[0] // 40) + dx, int(p[1] // 40) + dy), set())
    return out
# Road pass 2 (2026-11-25): replace whole STREETS, not the pieces beside each cable segment. The old per-segment
# version dropped every PDF piece whose midpoint sat beside a cable segment but drew the road only along that segment,
# so E Chapman, N Berkeley, N Lemon and Balcom came out as fragments with most of the street missing.
#  1. chain the PDF street pieces into streets (through 2-way nodes, turning less than 35 deg at a node);
#  2. sample each street every 3 ft: a cable segment running parallel (< 15 deg) within 15 ft counts as following it;
#  3. a street followed for >= 40 ft and >= 35% of its length is replaced by ITS OWN shape moved to sit 7 ft off the
#     cable (the median gap), so the road keeps the street's line, not the cable's jogs;
#  4. a street running parallel within 25 ft of a replaced one over half its length is that street's other edge line
#     (major streets have two) and is dropped.
def _kq(p): return (round(p[0] * 2), round(p[1] * 2))
_SI = [si for si, (a_, b_) in enumerate(LST) if math.dist(a_, b_) > 0.3]
_node = {}
for si in _SI:
    for p_ in LST[si]: _node.setdefault(_kq(p_), []).append(si)
def _turn(p0, p1, p2):
    a1 = math.atan2(p1[1] - p0[1], p1[0] - p0[0]); a2 = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    d = abs(math.degrees(a2 - a1)) % 360; return min(d, 360 - d)
_used = set(); STREETS_L = []                                   # (points, [segment indices])
for si in _SI:
    if si in _used: continue
    _used.add(si); pts_ = list(LST[si]); ids_ = [si]
    for fwd in (True, False):
        while True:
            tip, prev = (pts_[-1], pts_[-2]) if fwd else (pts_[0], pts_[1])
            nx_ = [j for j in _node.get(_kq(tip), []) if j not in _used]
            if len(_node.get(_kq(tip), [])) != 2 or not nx_: break
            j = nx_[0]; a_, b_ = LST[j]; o = b_ if _kq(a_) == _kq(tip) else a_
            if _turn(prev, tip, o) > 35: break
            _used.add(j); ids_.append(j)
            pts_.append(o) if fwd else pts_.insert(0, o)
    STREETS_L.append((pts_, ids_))
_CS = [(u, v) for ci, ch in enumerate(CH) if ci not in drop for u, v in zip(ch, ch[1:]) if math.dist(u, v) > 2]
_cg = {}
for k_, (u, v) in enumerate(_CS):
    for gx in range(int(min(u[0], v[0]) // 30) - 1, int(max(u[0], v[0]) // 30) + 2):
        for gy in range(int(min(u[1], v[1]) // 30) - 1, int(max(u[1], v[1]) // 30) + 2): _cg.setdefault((gx, gy), []).append(k_)
def _follow(pts_):
    """samples (gap, side) where a cable follows this street; side +1 = cable on the street's left"""
    out, tot = [], 0.0
    for a_, b_ in zip(pts_, pts_[1:]):
        L = math.dist(a_, b_); tot += L
        if L < 0.5: continue
        ux, uy = (b_[0] - a_[0]) / L, (b_[1] - a_[1]) / L; A = _ang(a_, b_)
        for i in range(max(1, int(L / 3))):
            p_ = (a_[0] + ux * (i + 0.5) * L / max(1, int(L / 3)), a_[1] + uy * (i + 0.5) * L / max(1, int(L / 3)))
            if in_p1(to10_ref(p_)): continue
            best = None
            for k_ in _cg.get((int(p_[0] // 30), int(p_[1] // 30)), []):
                u, v = _CS[k_]
                if _dang(A, _ang(u, v)) > 15: continue
                q = nearest_on(p_, u, v); d = math.dist(p_, q)
                if d < 15 and (best is None or d < best[0]):
                    best = (d, 1 if (q[0] - p_[0]) * -uy + (q[1] - p_[1]) * ux > 0 else -1)
            if best: out.append(best)
    return out, tot
def _par_near(pa, pb, r=25):
    """share of street pb's length lying parallel within r ft of street pa"""
    segs_a = list(zip(pa, pa[1:])); n = hit = 0
    for a_, b_ in zip(pb, pb[1:]):
        L = math.dist(a_, b_)
        if L < 0.5: continue
        for i in range(max(1, int(L / 3))):
            p_ = (a_[0] + (b_[0] - a_[0]) * (i + 0.5) / max(1, int(L / 3)), a_[1] + (b_[1] - a_[1]) * (i + 0.5) / max(1, int(L / 3)))
            n += 1
            if any(_dang(_ang(a_, b_), _ang(u, v)) < 12 and math.dist(p_, nearest_on(p_, u, v)) < r for u, v in segs_a): hit += 1
    return hit / n if n else 0
LDROP = set(); ROADS_L = []
cands = []
for k_, (pts_, ids_) in enumerate(STREETS_L):
    smp, tot = _follow(pts_)
    if not smp: continue
    side = 1 if sum(1 for d, sd in smp if sd > 0) >= len(smp) / 2 else -1
    gaps = sorted(d for d, sd in smp if sd == side)
    cov = len(gaps) * 3.0
    if cov >= 40 and cov >= 0.35 * tot: cands.append((gaps[len(gaps) // 2], k_, side))
done = []
for gap, k_, side in sorted(cands):
    pts_, ids_ = STREETS_L[k_]
    if any(_par_near(STREETS_L[j][0], pts_) > 0.5 for j in done):       # the other edge of a street already replaced
        LDROP.update(ids_); continue
    r = offset(pts_, side * (gap - ROAD))
    ROADS_L.append(r); ROADS.append(r); pl(r, layer=SL, color=ROADCOLOR)
    LDROP.update(ids_); done.append(k_)
for k_, (pts_, ids_) in enumerate(STREETS_L):                          # far edge lines not followed by any cable
    if k_ in done or ids_[0] in LDROP: continue
    if sum(math.dist(a_, b_) for a_, b_ in zip(pts_, pts_[1:])) > 20 and any(_par_near(STREETS_L[j][0], pts_) > 0.6 for j in done):
        LDROP.update(ids_)
print("Lawrence roads:", len(ROADS_L), "street pieces replaced:", len(LDROP))

# ---------------------------------------------------------------- Lawrence street names (cluster groups read off the sheet)
SN_GROUPS = [
    ("DOROTHY LN.", [0, 1]), ("HORNET WAY.", [2, 5]), ("DOROTHY DR.", [3, 4]), ("E FERN DR.", [6, 7]),
    ("N PRINCETON AVE.", [8, 9, 11]), ("E BERKELEY AVE.", [10, 12]), ("E GLENWOOD.", [13, 14]),
    ("N LEMON ST.", [15, 16, 17]), ("PRINCETON CIR W.", [18, 22, 24]), ("N PRINCETON AVE.", [19, 20, 23]),
    ("NUTWOOD.", [25]), ("N BERKELEY AVE.", [26, 30, 31]), ("E BROOKDALE PL.", [27, 28, 29]), ("GROVE.", [32]),
    ("N POMONA AVE.", [33, 34, 35]), ("N LEMON ST.", [36, 37, 38]), ("E CHAPMAN AVE.", [39, 40, 41]),
    ("E CHAPMAN AVE.", [42, 43, 44]), ("E WHITING AVE.", [45, 46, 47]), ("N POMONA AVE.", [48, 49, 52]),
    ("N LAWRENCE AVE.", [50, 53]), ("NEWELL PL.", [51]), ("E WILSHIRE AVE.", [54, 55, 56]),
    ("E WILSHIRE AVE.", [57, 58, 59]), ("LEMON ST.", [60]), ("N BALCOM AVE.", [61, 62, 63]),
    ("E AMERIGE AVE.", [64, 65, 66]), ("E COMMONWEALTH AVE.", [67, 68, 69]), ("E COMMONWEALTH AVE.", [71, 72, 73]),
    ("N LAWRENCE AVE.", [70, 75]), ("S POMONA AVE.", [74, 76, 77]), ("E SANTA FE AVE.", [78, 79, 80]),
    ("E SANTA FE AVE.", [81, 82]), ("S LEMON ST.", [83, 84, 86]), ("E WALNUT AVE.", [90, 91, 92]),
    ("S LAWRENCE AVE.", [93, 95, 99]), ("S LEMON ST.", [94, 98]), ("E TRUSLOW AVE.", [96, 97]),
]
P1CLOUD = json.load(open(r"C:/civ3dmcp/jobs/Singleline/_analysis/p1_extract.json"))["cloud"]
def in_p1(pt):
    x, y = pt; c = False; n = len(P1CLOUD)
    for i in range(n):
        x1, y1 = P1CLOUD[i]; x2, y2 = P1CLOUD[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
SNC = {c["id"]: c for c in LW["streetnames"]}
st_segs = [(Rref(a), Rref(b)) for si, (a, b) in enumerate(LW["streets"]) if math.dist(a, b) > 1.0 and si not in LDROP] + [(u, v) for r in ROADS_L for u, v in zip(r, r[1:])]
for name, ids in SN_GROUPS:
    cl = [SNC[i] for i in ids if i in SNC]
    if not cl: continue
    W = sum(c["n"] for c in cl)
    cref = (sum(c["c"][0] * c["n"] for c in cl) / W, sum(c["c"][1] * c["n"] for c in cl) / W)
    if in_p1(cref): continue                        # Royer's sheet already names streets inside its cloud
    if len(cl) >= 2:
        a0, a1 = min(cl, key=lambda c: c["c"][0] + c["c"][1] * 0.01), max(cl, key=lambda c: c["c"][0] + c["c"][1] * 0.01)
        ang_pdf = math.degrees(math.atan2(a1["c"][1] - a0["c"][1], a1["c"][0] - a0["c"][0]))
    else:
        ang_pdf = cl[0]["ang"]
    p = Rref(cref); want = readable(-ang_pdf)
    cand = []
    for u, v in st_segs:
        sa = readable(math.degrees(math.atan2(v[1] - u[1], v[0] - u[0])))
        da = abs(sa - want); da = min(da, 180 - da)
        if da > 20: continue
        n = nearest_on(p, u, v); d = math.dist(p, n)
        if d < 20: cand.append((d, u, v, n))
    if not cand:
        tx(name, p[0], p[1], want, color=ROADCOLOR); continue
    d, u, v, n = min(cand, key=lambda z: z[0])
    L = math.dist(u, v); t = math.dist(u, n) / L if L else 0.5
    on_line(name, u, v, t=min(max(t, 0.05), 0.95), color=ROADCOLOR)

#!/usr/bin/env python3
"""Station DYN STATION blocks on an OH or UG power job from drawing data only.

    python stationing.py <data dir> --mode missing|all|fill [--out-job job.json] [--report report.csv]
                         [--layer ELECTRIC-TEXT] [--compare old_stations.json]

<data dir> holds the saved civil3d_entity / civil3d_point results named in
docs/SKILL.md (cl.json, plrw.json, noplot.json, inserts.json, text.json,
build.json, points.txt). Writes one civil3d_entity apply job and a review CSV.

Modes
  all      a station block for every feature (use after the old ones are erased)
  missing  only features that have no station block on them yet
  fill     edit existing blocks whose LINE_1 is XX+XX / blank (station only)

Rules (from TD2573793, Kevin's corrections, 2026-11-19): see docs/SKILL.md.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import re
import sys

STA = re.compile(r'^\s*(\d+)\+(\d\d(?:\.\d+)?)\s*$')
FEATURES = {'DYN-POLE', 'DYN-SL', 'UTIL METER_BOX', 'DYN-HANDHOLE', 'DYN-PED', 'DYN-PULLBOX',
            'DYN-VAULT', 'DYN-PAD', 'DYN-MANHOLE', 'MH'}
FEATURE_LAYER = 'ELECTRIC'
STATION_BLOCKS = ('DYN STATION', 'DYN STATION (FLIPPED)')
SCALE = 1.3333
HALF_PI = 1.5707963267948966
SEG2_MAX = 20          # SEG-2 above ~21 flips the text upside down to the other side of the shelf
# Burst text layout on the shelf, block frame, measured on a default block at scale 1.3333.
BASE = [0.873, -4.163, -9.188, -14.214, -19.24, -24.27, -29.29, -34.32, -39.34]
XOFF, CHAR_W, TEXT_H, GAP = 1.14, 2.6, 3.2, 6.0


# ------------------------------------------------------------------ geometry
def densify_arc(c, r, a0, a1, step=0.5):
    a0, a1 = math.radians(a0), math.radians(a1)
    while a1 <= a0:
        a1 += 2 * math.pi
    n = max(2, int(r * (a1 - a0) / step) + 1)
    return [(c['x'] + r * math.cos(a0 + (a1 - a0) * i / (n - 1)), c['y'] + r * math.sin(a0 + (a1 - a0) * i / (n - 1))) for i in range(n)]


def bulge_pts(p, q, b, step=0.5):
    if abs(b) < 1e-9:
        return [p, q]
    th = 4 * math.atan(b)
    ch = math.dist(p, q)
    r = ch / (2 * math.sin(abs(th) / 2))
    mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
    d = math.sqrt(max(r * r - (ch / 2) ** 2, 0))
    ux, uy = (q[0] - p[0]) / ch, (q[1] - p[1]) / ch
    s = 1 if (b > 0) == (abs(th) < math.pi) else -1
    cx, cy = mx - s * uy * d, my + s * ux * d
    a0 = math.atan2(p[1] - cy, p[0] - cx)
    n = max(2, int(r * abs(th) / step) + 1)
    return [(cx + r * math.cos(a0 + th * i / (n - 1)), cy + r * math.sin(a0 + th * i / (n - 1))) for i in range(n)]


def poly_pts(e, step=0.5):
    t = e['type']
    if t == 'LINE':
        return [(e['start']['x'], e['start']['y']), (e['end']['x'], e['end']['y'])]
    if t == 'ARC':
        return densify_arc(e['center'], e['radius'], e['startAngleDeg'], e['endAngleDeg'], step)
    if t == 'LWPOLYLINE':
        v = e['vertices']
        out = []
        for i in range(len(v) - 1 + (1 if e.get('closed') else 0)):
            a, b = v[i], v[(i + 1) % len(v)]
            sg = bulge_pts((a['x'], a['y']), (b['x'], b['y']), a.get('bulge', 0), step)
            out += sg if not out else sg[1:]
        return out
    return []


def cross(p, q, a, b):
    def o(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    return o(p, q, a) * o(p, q, b) < 0 and o(a, b, p) * o(a, b, q) < 0


def inside(P, poly):
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > P[1]) != (y2 > P[1]) and P[0] < x1 + (P[1] - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def rect_hits_poly(rect, poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    rx = [p[0] for p in rect]; ry = [p[1] for p in rect]
    if max(rx) < min(xs) or min(rx) > max(xs) or max(ry) < min(ys) or min(ry) > max(ys):
        return False
    for a, b in zip(rect, rect[1:] + rect[:1]):
        for c, d in zip(poly, poly[1:] + poly[:1]):
            if cross(a, b, c, d):
                return True
    return any(inside(p, poly) for p in rect) or any(inside(p, rect) for p in poly)


def fmt(S):
    """Station text, rounded to the nearest foot (x.5 rounds up)."""
    S = int(math.floor(S + 0.5))
    return f'{S // 100}+{S % 100:02d}'


# ------------------------------------------------------------------ centerlines
class Centerlines:
    """Exploded CL linework (LINE / ARC / LWPOLYLINE on the CL layer) chained into
    tangent-continuous runs, each fitted to its ##+## labels (snapped to the
    AeccTickLine ticks). Runs with fewer than two labels are not usable."""

    def __init__(self, cl_entities):
        pieces = [poly_pts(e) for e in cl_entities if e['type'] in ('LINE', 'ARC', 'LWPOLYLINE')]
        pieces = [p for p in pieces if len(p) >= 2]
        self.chains = self._chain(pieces)
        ticks = [(e['position']['x'], e['position']['y']) for e in cl_entities if e.get('blockName') == 'AeccTickLine']
        labels = []
        for e in cl_entities:
            if e['type'] not in ('MTEXT', 'TEXT'):
                continue
            m = STA.match(e.get('text') or e.get('contents') or '')
            if not m:
                continue
            pos = e.get('location') or e.get('position')
            P = (pos['x'], pos['y'])
            if ticks:
                tk = min(ticks, key=lambda t: math.dist(t, P))
                if math.dist(tk, P) < 8:
                    P = tk
            S = int(m.group(1)) * 100 + float(m.group(2))
            ci, (d, s, _, _) = min(((k, self.project(c, P)) for k, c in enumerate(self.chains)), key=lambda x: x[1][0])
            if d < 1.0:
                labels.append((ci, s, S))
        self.fit = {}
        for ci in range(len(self.chains)):
            L = [(s, S) for c, s, S in labels if c == ci]
            if len(L) < 2:
                continue
            best = None
            for k in (1, -1):
                votes = collections.Counter(round(S - k * s) for s, S in L)
                a0, _ = votes.most_common(1)[0]
                inl = [S - k * s for s, S in L if abs(S - k * s - a0) < 1.5]
                if best is None or len(inl) > best[2]:
                    best = (k, sum(inl) / len(inl), len(inl))
            self.fit[ci] = best

    @staticmethod
    def _chain(pieces):
        def tang(u, v):
            a1 = math.atan2(u[1][1] - u[0][1], u[1][0] - u[0][0])
            a2 = math.atan2(v[1][1] - v[0][1], v[1][0] - v[0][0])
            return abs((a1 - a2 + math.pi) % (2 * math.pi) - math.pi) < math.radians(3)
        chains, used, T = [], [False] * len(pieces), 0.05
        for i in range(len(pieces)):
            if used[i]:
                continue
            used[i] = True
            ch, grown = list(pieces[i]), True
            while grown:
                grown = False
                for j, p in enumerate(pieces):
                    if used[j]:
                        continue
                    if math.dist(ch[-1], p[0]) < T and tang(ch[-2:], p[:2]): ch += p[1:]
                    elif math.dist(ch[-1], p[-1]) < T and tang(ch[-2:], p[::-1][:2]): ch += p[::-1][1:]
                    elif math.dist(ch[0], p[-1]) < T and tang(p[-2:], ch[:2]): ch = p[:-1] + ch
                    elif math.dist(ch[0], p[0]) < T and tang(p[::-1][-2:], ch[:2]): ch = p[::-1][:-1] + ch
                    else: continue
                    used[j] = grown = True
            chains.append(ch)
        return chains

    @staticmethod
    def project(chain, P):
        best, s = (1e18, 0, None, (1, 0)), 0
        for a, b in zip(chain, chain[1:]):
            L = math.dist(a, b)
            if L == 0:
                continue
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            t = max(0, min(L, (P[0] - a[0]) * ux + (P[1] - a[1]) * uy))
            F = (a[0] + ux * t, a[1] + uy * t)
            d = math.dist(P, F)
            if d < best[0]:
                best = (d, s + t, F, (ux, uy))
            s += L
        return best


# ------------------------------------------------------------------ job data
class Job:
    def __init__(self, data_dir):
        def load(name):
            path = os.path.join(data_dir, name)
            if not os.path.exists(path):
                return []
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('entities', d) if isinstance(d, dict) else d
        self.cl = Centerlines(load('cl.json'))
        noplot = load('noplot.json')
        polys = [(e['handle'], [(v['x'], v['y']) for v in e['vertices']]) for e in noplot if e['type'] == 'LWPOLYLINE' and e.get('closed')]
        nums = [(e['text'], (e['position']['x'], e['position']['y'])) for e in noplot if e['type'] == 'TEXT' and e['text'].strip().isdigit()]
        self.sheets = []
        for h, poly in polys:
            lab = [t for t, p in nums if inside(p, poly)]
            self.sheets.append((lab[0] if len(lab) == 1 else '?' + h, poly))
        self.walls, self.pl = [], []
        for e in load('plrw.json'):
            p = poly_pts(e, 2)
            sg = list(zip(p, p[1:]))
            self.walls += sg
            if e['layer'].upper() == 'PL':
                self.pl += sg
        self.inserts = load('inserts.json')
        self.text = load('text.json')
        self.buildings = [(e['handle'], [(v['x'], v['y']) for v in e['vertices']]) for e in load('build.json') if len(e.get('vertices') or []) >= 3]
        self.points = self._points(data_dir)
        self.grid = collections.defaultdict(list)
        for r in self.points:
            self.grid[(int(r['x'] // 5), int(r['y'] // 5))].append(r)

    @staticmethod
    def _points(data_dir):
        """points.txt: a civil3d_point export (pnezd), either the raw tool output or plain 'n,x,y,z,desc' lines."""
        path = os.path.join(data_dir, 'points.txt')
        if not os.path.exists(path):
            return []
        with open(path, encoding='utf-8') as f:
            s = f.read()
        # A saved tool result is either the MCP content array [{type, text}, ...] or its text,
        # which may start with a "[Resource link: ...]" line before the JSON.
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                s = ''.join(x.get('text', '') for x in arr if isinstance(x, dict))
        except ValueError:
            pass
        if '{"action"' in s:
            s = json.loads(s[s.index('{"action"'):])['result']['data']
        out = []
        for line in s.replace('\r', '').split('\n'):
            p = line.split(',', 4)
            if len(p) >= 4 and p[0].strip().isdigit():
                out.append({'n': int(p[0]), 'x': float(p[1]), 'y': float(p[2]), 'd': p[4].strip() if len(p) > 4 else ''})
        return out

    def near_pts(self, x, y, R):
        out = []
        for i in range(int(x // 5) - 3, int(x // 5) + 4):
            for k in range(int(y // 5) - 3, int(y // 5) + 4):
                for r in self.grid[(i, k)]:
                    d = math.hypot(r['x'] - x, r['y'] - y)
                    if d <= R:
                        out.append((d, r))
        return sorted(out, key=lambda t: t[0])

    def sheet_of(self, P):
        return [s for s, poly in self.sheets if inside(P, poly)]

    def pick_cl(self, P):
        """Same sheet first (a station can't point at a CL the sheet doesn't show),
        then the street you'd reach the lot from (fewest PL crossings), then nearest."""
        sh = self.sheet_of(P)
        cands = []
        for k, c in enumerate(self.cl.chains):
            if k not in self.cl.fit:
                continue
            d, s, F, u = self.cl.project(c, P)
            if d > 250:
                continue
            kk, a, _ = self.cl.fit[k]
            same = bool(set(self.sheet_of(F)) & set(sh)) or not sh
            npl = sum(cross(P, F, u, v) for u, v in self.pl)
            cands.append(dict(d=d, F=F, u=u, raw=a + kk * s, calc=fmt(a + kk * s), pl=npl, same=same))
        if not cands:
            return None, sh
        return min(cands, key=lambda c: (not c['same'], c['pl'], c['d'])), sh


IDRE = re.compile(r'PP\s*(?:COMM?\s+)?([A-Z]?\d{6,8}[A-Z]?)')
OFFSET_SHOT = re.compile(r'PP\s*\S+\s+[\d.]+\s*[NSEW]\.')


def lines_for(job, e):
    """Station text lines (LINE_1 left '' for the station) and a note for the review list."""
    b = e['blockName']
    x, y = e['position']['x'], e['position']['y']
    at = job.near_pts(x, y, 0.2)
    if b == 'DYN-POLE':
        cand = [r['d'] for _, r in job.near_pts(x, y, 2.5) if r['d'].startswith('PP')]
        cand += [r['d'] for _, r in job.near_pts(x, y, 12) if OFFSET_SHOT.search(r['d'])]
        for dsc in cand:
            m = IDRE.search(dsc)
            if m:
                return ['', m.group(1)], None
        if cand:
            return ['', 'EX. POLE', 'ID TAG NFIF', 'FIF'], None               # PP NT / PP COMM NT
        return ['', 'EX. POLE', 'ID TAG NFIF', 'FIF'], 'pole has no survey point; ID may be on the grid maps'
    if b == 'DYN-SL':
        return ['', 'EX. SL', 'ID TAG NFIF', 'FIF'], None
    if b in ('UTIL METER_BOX', 'DYN-HANDHOLE'):
        fif = [] if b == 'DYN-HANDHOLE' else ['FIF']                          # E PB handholes carry no FIF
        if at or job.near_pts(x, y, 2.5):
            return ['', 'EX. HH'] + fif, None
        return ['NFIF', 'EX. HH'], 'no survey point: NFIF (underground rule still being confirmed)'
    if b == 'DYN-PED':
        return ['', 'EX. PED'], None
    if b in ('MH', 'DYN-MANHOLE'):
        return ['', 'EX. MANHOLE', 'FIF'], None
    if b == 'DYN-VAULT':
        if at:
            return ['', 'EX. VAULT', 'FIF'], 'vault: check ID and size on the records'
        return ['NFIF', 'EX. VAULT'], 'vault not surveyed; ID and size on the records'
    if b == 'DYN-PAD':
        ids = [m.group(1) for m in (re.search(r'XFMR\s+(\S+)', r['d']) for _, r in job.near_pts(x, y, 5)) if m]
        return (['', ids[0]], None) if ids else (['', 'EX. PAD', 'FIF'], 'pad ID not found')
    if b == 'DYN-PULLBOX':
        return ['NFIF', 'EX. PB'], 'pull box not surveyed; ID on the records'
    return None, None


# ------------------------------------------------------------------ obstacles and text layout
class Obstacles:
    def __init__(self):
        self.ob = collections.defaultdict(list)

    @staticmethod
    def _keys(poly):
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        for i in range(int(min(xs) // 50), int(max(xs) // 50) + 1):
            for k in range(int(min(ys) // 50), int(max(ys) // 50) + 1):
                yield (i, k)

    def add(self, tag, poly):
        for key in self._keys(poly):
            self.ob[key].append((tag, poly))

    def hits(self, rect, skip=()):
        seen, out = set(), []
        for key in self._keys(rect):
            for tag, poly in self.ob[key]:
                if tag in seen or tag in skip:
                    continue
                seen.add(tag)
                if rect_hits_poly(rect, poly):
                    out.append(tag)
        return out


def aabb(ex, pad=0.0):
    a, b = ex['min'], ex['max']
    return [(a['x'] - pad, a['y'] - pad), (b['x'] + pad, a['y'] - pad), (b['x'] + pad, b['y'] + pad), (a['x'] - pad, b['y'] + pad)]


def away_angle(P, F, u):
    """Direction (radians) square to the CL at the foot F, toward the feature P. Past the end of a CL the foot is
    clamped to the end point, and aiming from it at P would tilt the callout; Kevin (2026-11-20): keep the
    station at the end of the CL but keep the callout perpendicular to it."""
    ux, uy = u
    nx, ny = (-uy, ux) if (P[0] - F[0]) * -uy + (P[1] - F[1]) * ux >= 0 else (uy, -ux)
    return math.atan2(ny, nx)


def text_rects(P, ang, flipped, s1, s2, lines):
    u = (math.cos(ang), math.sin(ang)); n = (-u[1], u[0])
    a0 = GAP + s1 + s2
    rects = []
    for k, t in enumerate(lines):
        if not t:
            continue
        b = BASE[k]
        lo, hi = (b, b + TEXT_H) if not flipped else (-(b + TEXT_H), -b)
        x0 = a0 + XOFF; x1 = x0 + CHAR_W * len(t)
        rects.append([(P[0] + u[0] * al + n[0] * c, P[1] + u[1] * al + n[1] * c) for al, c in ((x0, lo), (x1, lo), (x1, hi), (x0, hi))])
    return rects


def leader_rect(P, ang, s1, s2, s3):
    u = (math.cos(ang), math.sin(ang)); w = 0.4; n = (-u[1] * w, u[0] * w)
    p0 = (P[0] + u[0] * GAP, P[1] + u[1] * GAP); L = GAP + s1 + s2 + s3
    p1 = (P[0] + u[0] * L, P[1] + u[1] * L)
    return [(p0[0] + n[0], p0[1] + n[1]), (p1[0] + n[0], p1[1] + n[1]), (p1[0] - n[0], p1[1] - n[1]), (p0[0] - n[0], p0[1] - n[1])]


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('data')
    ap.add_argument('--mode', choices=('all', 'missing', 'fill'), default='missing')
    ap.add_argument('--out-job', default=None)
    ap.add_argument('--report', default=None)
    ap.add_argument('--layer', default='ELECTRIC-TEXT', help='layer for new station blocks')
    ap.add_argument('--compare', default=None, help='saved query of the original station blocks, to score against')
    a = ap.parse_args(argv)
    out_job = a.out_job or os.path.join(a.data, f'stationing_{a.mode}.json')
    report_csv = a.report or os.path.join(a.data, f'stationing_{a.mode}_report.csv')

    job = Job(a.data)
    stations = [e for e in job.inserts if e.get('blockName') in STATION_BLOCKS]
    feats = [e for e in job.inserts if e.get('blockName') in FEATURES and e.get('layer') == FEATURE_LAYER]
    def station_on(f):
        P = (f['position']['x'], f['position']['y'])
        return [s for s in stations if math.dist(P, (s['position']['x'], s['position']['y'])) < 0.5]

    obst = Obstacles()
    for e in job.text:
        if e['type'] in ('TEXT', 'MTEXT') and e.get('extents'):
            ex = e['extents']
            if ex['max']['x'] - ex['min']['x'] < 300 and ex['max']['y'] - ex['min']['y'] < 300:
                obst.add('text ' + e['handle'], aabb(ex, 0.5))
        elif e['type'] == 'DIMENSION' and e.get('textPosition'):
            tp = e['textPosition']
            obst.add('dim ' + e['handle'], [(tp['x'] - 3, tp['y'] - 2.5), (tp['x'] + 3, tp['y'] - 2.5), (tp['x'] + 3, tp['y'] + 2.5), (tp['x'] - 3, tp['y'] + 2.5)])
    for e in job.inserts:
        name = e.get('blockName', '')
        if name == 'AeccTickLine' or (a.mode == 'all' and name in STATION_BLOCKS):
            continue
        ex = e.get('extents')
        if ex and (name in STATION_BLOCKS or (ex['max']['x'] - ex['min']['x'] < 60 and ex['max']['y'] - ex['min']['y'] < 60)):
            obst.add(('station ' if name in STATION_BLOCKS else 'block ') + e['handle'], aabb(ex, 0.3))
    for h, poly in job.buildings:
        obst.add('bldg ' + h, poly)

    creates, edits, report = [], [], []
    feats.sort(key=lambda e: (e['position']['y'], e['position']['x']))
    for e in feats:
        existing = station_on(e)
        if a.mode == 'missing' and existing:
            continue
        if a.mode == 'fill':
            todo = [s for s in existing if not STA.match(s['attributes'].get('LINE_1', ''))
                    and s['attributes'].get('LINE_1', '').strip().upper() in ('', 'XX+XX')]
            if not todo:
                continue
        lines, note = lines_for(job, e)
        if lines is None:
            continue
        P = (e['position']['x'], e['position']['y'])
        c, sh = job.pick_cl(P)
        row = dict(handle=e['handle'], block=e['blockName'], x=round(P[0], 3), y=round(P[1], 3))
        if c is None:
            report.append({**row, 'flags': 'no CL with station labels within 250 ft'}); continue
        F = c['F']; d = math.dist(P, F)
        if d < 0.05:
            report.append({**row, 'flags': 'feature sits on the CL'}); continue
        if a.mode == 'fill':
            for s in todo:
                edits.append({'handle': s['handle'], 'attributes': {'LINE_1': c['calc']}})
            report.append({**row, 'text': c['calc'], 'station_raw': round(c['raw'], 2), 'offset': round(d, 1),
                           'flags': '' if c['same'] and c['pl'] == 0 else 'check CL choice'})
            continue

        ang = away_angle(P, F, c['u']); rot = math.degrees(ang) % 360
        flipped = not (rot >= 315 or rot < 135)          # DYN STATION points ~E or N; FLIPPED ~W or S
        if not lines[0]:
            lines[0] = c['calc']
        longest = max(len(t) for t in lines if t)
        s3 = max(18, min(26, math.ceil(CHAR_W * longest / 2) * 2 - 2))
        sheet = dict(job.sheets).get(sh[0]) if sh else None
        skip = {'block ' + e['handle']}

        def search(use_sheet, need_behind):
            best = None
            for s2 in list(range(13, 2, -1)) + list(range(14, SEG2_MAX + 1)):
                for s1 in (13, 8, 4):
                    rects = text_rects(P, ang, flipped, s1, s2, lines)
                    corners = [p for r in rects for p in r]
                    nb = sum(1 for q in corners if any(cross(F, q, u, v) for u, v in job.walls))
                    if need_behind and nb < len(corners):
                        continue
                    if use_sheet and sheet and not all(inside(q, sheet) for q in corners):
                        continue
                    h = set()
                    for r in rects:
                        h.update(obst.hits(r, skip))
                    score = (len(corners) - nb, len(h), s1 + s2)
                    if best is None or score < best[0]:
                        best = (score, s1, s2, sorted(h))
                    if not h and nb == len(corners):
                        return best
            return best

        flags = []
        best = search(True, True)
        if best is None:
            best = search(False, True); flags.append('text runs past the sheet edge')
        if best is None:
            best = search(False, False); flags.append(f'only part of the text clears the RW/PL ({best[0][0]} corners street side)')
        _, s1, s2, hit = best
        if hit:
            flags.append('touches ' + ', '.join(sorted({h.split()[0] for h in hit})))
        if note:
            flags.append(note)
        if not c['same']:
            flags.append('no CL on its own sheet')
        for i, r in enumerate(text_rects(P, ang, flipped, s1, s2, lines)):
            obst.add(f'new {e["handle"]} {i}', r)
        obst.add(f'newleader {e["handle"]}', leader_rect(P, ang, s1, s2, s3))
        blk = STATION_BLOCKS[1] if flipped else STATION_BLOCKS[0]
        rotk, mirk = ('Angle1', 'FLIP (MI)') if flipped else ('ROTATE PERP CL', 'FLIP (MIR)')
        # Write all nine lines: an unwritten line keeps the definition default (LINE_3 is "--OTHER--").
        attrs = {f'LINE_{i + 1}': (lines[i] if i < len(lines) else '') for i in range(9)}
        creates.append({'id': e['handle'], 'type': 'insert', 'blockName': blk, 'layer': a.layer,
                        'position': {'x': P[0], 'y': P[1]}, 'rotationDeg': round(rot, 4), 'scale': SCALE, 'attributes': attrs,
                        'dynamicProperties': {'SEG-1': s1, 'SEG-2': s2, 'SEG-2 (ANG)': 0, 'SEG-3': s3, 'FLIP (RO)': HALF_PI, rotk: 0, mirk: 0}})
        report.append({**row, 'text': ' / '.join(t for t in lines if t), 'station_raw': round(c['raw'], 2), 'offset': round(d, 1),
                       'sheet': '/'.join(sh), 'insert': blk, 'rotation': round(rot, 2), 'seg1': s1, 'seg2': s2, 'seg3': s3,
                       'flags': '; '.join(flags)})

    if a.compare:
        old = json.load(open(a.compare, encoding='utf-8'))
        old = [s for s in (old.get('entities', old) if isinstance(old, dict) else old) if s.get('blockName') in STATION_BLOCKS]
        score = collections.Counter()
        for r in report:
            o = [s for s in old if math.dist((r['x'], r['y']), (s['position']['x'], s['position']['y'])) < 0.3]
            if not o or 'text' not in r:
                continue
            ot = ' / '.join(v for k, v in sorted(o[0]['attributes'].items()) if v)
            r['original'] = ot
            score['station same' if ot.split(' / ')[0] == r['text'].split(' / ')[0] else 'station diff'] += 1
            score['text same' if ot == r['text'] else 'text diff'] += 1
        print('compare:', dict(score))

    body = {'version': 1}
    if creates:
        body['creates'] = creates
    if edits:
        body['edits'] = edits
    json.dump(body, open(out_job, 'w', encoding='utf-8'), indent=1)
    cols = ['handle', 'block', 'x', 'y', 'text', 'original', 'station_raw', 'offset', 'sheet', 'insert', 'rotation', 'seg1', 'seg2', 'seg3', 'flags']
    with open(report_csv, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader(); w.writerows(report)
    flagged = sum(1 for r in report if r.get('flags'))
    print(json.dumps({'mode': a.mode, 'features': len(feats), 'creates': len(creates), 'edits': len(edits),
                      'flagged': flagged, 'job': out_job, 'report': report_csv}))
    return 0


if __name__ == '__main__':
    sys.exit(main())

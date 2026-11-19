#!/usr/bin/env python3
"""Re-solve the leaders of placed station blocks together, without bursting.

    python repair.py <data dir> <placed.json> [--bends] [--out-job repair.json] [--report repair.csv] [--passes 8]

<placed.json> is a civil3d_entity query of the station blocks as they are now
(layer ELECTRIC-TEXT, INSERT, includeGeometry). Each callout keeps its block,
rotation and text. Every pass re-places each callout that still conflicts,
with all the others held where they are, and keeps the change only if its
cost drops. Conflicts are weighted: another station's text worst, then its
leader, buildings, other text, dimension text, symbols. Text on NO-PLOT
(sheet numbers) is ignored because it doesn't print.

Without --bends only SEG-1 / SEG-2 change (straight leaders). With --bends the
measured bent shapes in data/ are tried too (a sideways step with the text kept
square); those need FLIP (RO)'s value set removed from the block definitions,
otherwise AutoCAD snaps FLIP (RO) to 90/270 and the text tilts.
Writes an edit job for the blocks that moved and a CSV of what is left.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stationing as st  # noqa: E402

WEIGHT = {'stext': 10, 'sleader': 6, 'bldg': 5, 'text': 4, 'dim': 3, 'block': 2}
S1_OPTIONS = (13, 11, 9, 7, 5, 3)
BEND_PENALTY = 0.5       # prefer a straight leader when it clears just as well
# The bend tables were measured with an 18 ft shelf. On a bent leader the shelf length tilts the whole
# callout (22 ft: 1.7 deg, 26 ft: 3.2 deg), which breaks the rule that piece 1 and the shelf are
# perpendicular to the CL, so every bent callout gets this shelf. Straight leaders don't tilt.
BENT_SHELF = 18
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
BEND_TABLES = {'DYN STATION': 'bend_table_dyn_station.json', 'DYN STATION (FLIPPED)': 'bend_table_dyn_station_flipped.json'}


def load_bends():
    """Measured bent shapes: (S1, S2, bend deg) -> grip and FLIP (RO) in degrees that square the text, and the
    shelf start in the block frame once squared (TD2573793, 2026-11-19, 120 shapes per block)."""
    out = {}
    for blk, name in BEND_TABLES.items():
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                out[blk] = {tuple(int(v) for v in k.split('|')): r for k, r in json.load(f).items()}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('data')
    ap.add_argument('placed')
    ap.add_argument('--out-job', default=None)
    ap.add_argument('--report', default=None)
    ap.add_argument('--passes', type=int, default=8)
    ap.add_argument('--bends', action='store_true', help='also try the measured bent shapes')
    a = ap.parse_args(argv)
    out_job = a.out_job or os.path.join(a.data, 'stationing_repair.json')
    report_csv = a.report or os.path.join(a.data, 'stationing_repair_report.csv')

    job = st.Job(a.data)
    bends = load_bends() if a.bends else {}
    with open(a.placed, encoding='utf-8') as f:
        placed = json.load(f)
    placed = [e for e in (placed.get('entities', placed) if isinstance(placed, dict) else placed) if e.get('blockName') in st.STATION_BLOCKS]

    static = st.Obstacles()
    for e in job.text:
        if e.get('layer', '').upper() == 'NO-PLOT':
            continue
        if e['type'] in ('TEXT', 'MTEXT') and e.get('extents'):
            ex = e['extents']
            if ex['max']['x'] - ex['min']['x'] < 300 and ex['max']['y'] - ex['min']['y'] < 300:
                static.add('text ' + e['handle'], st.aabb(ex, 0.5))
        elif e['type'] == 'DIMENSION' and e.get('textPosition'):
            tp = e['textPosition']
            static.add('dim ' + e['handle'], [(tp['x'] - 3, tp['y'] - 2.5), (tp['x'] + 3, tp['y'] - 2.5), (tp['x'] + 3, tp['y'] + 2.5), (tp['x'] - 3, tp['y'] + 2.5)])
    feat_at = {}
    for e in job.inserts:
        name = e.get('blockName', '')
        if name == 'AeccTickLine' or name in st.STATION_BLOCKS:
            continue
        ex = e.get('extents')
        if ex and ex['max']['x'] - ex['min']['x'] < 60 and ex['max']['y'] - ex['min']['y'] < 60:
            static.add('block ' + e['handle'], st.aabb(ex, 0.3))
            feat_at[(round(e['position']['x'], 2), round(e['position']['y'], 2))] = e['handle']
    for h, poly in job.buildings:
        static.add('bldg ' + h, poly)

    C = []
    for e in placed:
        P = (e['position']['x'], e['position']['y'])
        if (round(P[0], 2), round(P[1], 2)) not in feat_at:
            continue                     # not on a feature (e.g. a sample copy set off to the side)
        dp = e['dynamicProperties']
        lines = [e['attributes'].get(f'LINE_{i}', '') for i in range(1, 10)]
        while lines and not lines[-1]:
            lines.pop()
        ang = math.radians(e['rotationDeg'])
        c, sh = job.pick_cl(P)
        F = c['F'] if c else (P[0] - math.cos(ang), P[1] - math.sin(ang))
        bend0 = round(math.degrees(dp.get('SEG-2 (ANG)', 0)))
        bend0 = bend0 - 360 if bend0 > 180 else bend0
        cfg0 = (dp['SEG-1'], dp['SEG-2'], bend0)
        C.append(dict(handle=e['handle'], P=P, ang=ang, flipped=e['blockName'].endswith('(FLIPPED)'), block=e['blockName'],
                      lines=lines, cfg=cfg0, cfg0=cfg0, s3=dp['SEG-3'], F=F,
                      sheet=dict(job.sheets).get(sh[0]) if sh else None,
                      skip={'block ' + feat_at.get((round(P[0], 2), round(P[1], 2)), '')}))

    def to_world(c, pts):
        ca, sa = math.cos(c['ang']), math.sin(c['ang'])
        return [(c['P'][0] + ca * x - sa * y, c['P'][1] + sa * x + ca * y) for x, y in pts]

    def seg_rect(p, q, w=0.4):
        L = math.dist(p, q) or 1e-9
        nx, ny = -(q[1] - p[1]) / L * w, (q[0] - p[0]) / L * w
        return [(p[0] + nx, p[1] + ny), (q[0] + nx, q[1] + ny), (q[0] - nx, q[1] - ny), (p[0] - nx, p[1] - ny)]

    def geom(c, cfg):
        """Text rectangles and leader pieces in world coordinates for one leader shape."""
        s1, s2, bend = cfg
        if bend == 0:
            return (st.text_rects(c['P'], c['ang'], c['flipped'], s1, s2, c['lines']),
                    [st.leader_rect(c['P'], c['ang'], s1, s2, c['s3'])])
        sx, sy = bends[c['block']][cfg]['shelf']
        rects = []
        for k, t in enumerate(c['lines']):
            if not t:
                continue
            b = st.BASE[k]
            lo, hi = (sy + b, sy + b + st.TEXT_H) if not c['flipped'] else (sy - b - st.TEXT_H, sy - b)
            x0 = sx + st.XOFF; x1 = x0 + st.CHAR_W * len(t)
            rects.append(to_world(c, [(x0, lo), (x1, lo), (x1, hi), (x0, hi)]))
        v = to_world(c, [(st.GAP, 0), (st.GAP + s1, 0), (sx, sy), (sx + BENT_SHELF, sy)])
        return rects, [seg_rect(p, q) for p, q in zip(v, v[1:])]

    def options(c):
        yield from ((s1, s2, 0) for s1 in S1_OPTIONS for s2 in range(3, st.SEG2_MAX + 1))
        yield from bends.get(c['block'], {}).keys()

    def near(c):
        return [o for o in C if o is not c and math.dist(o['P'], c['P']) < 150]

    def cost(c, cfg, others, detail=False):
        rects, leads = geom(c, cfg)
        s1, s2, bend = cfg
        corners = [p for r in rects for p in r]
        k = 0.0
        hits = []
        nb = sum(1 for q in corners if any(st.cross(c['F'], q, u, v) for u, v in job.walls))
        k += 20 * (len(corners) - nb)
        if len(corners) - nb:
            hits.append(f'{len(corners) - nb} corners street side')
        if c['sheet'] and not all(st.inside(q, c['sheet']) for q in corners):
            k += 3; hits.append('off sheet')
        seen = set()
        for r in rects:
            for tag in static.hits(r, c['skip']):
                if tag in seen:
                    continue
                seen.add(tag); kind = tag.split()[0]
                k += WEIGHT.get(kind, 2); hits.append(kind)
        for o in others:
            orects, oleads = o['_g']
            if any(st.rect_hits_poly(r, orr) for r in rects for orr in orects):
                k += WEIGHT['stext']; hits.append('station text')
            elif any(st.rect_hits_poly(r, ol) for r in rects for ol in oleads) or any(st.rect_hits_poly(l, orr) for l in leads for orr in orects):
                k += WEIGHT['sleader']; hits.append('station leader')
        k += 0.01 * (s1 + s2) + ((BEND_PENALTY + 0.005 * abs(bend)) if bend else 0)
        return (k, hits) if detail else k

    for c in C:
        if c['cfg'][2] and c['cfg'] not in bends.get(c['block'], {}):
            c['cfg'] = (c['cfg'][0], c['cfg'][1], 0)       # an unmeasured hand bend: modelled as straight
        c['_g'] = geom(c, c['cfg'])
    for c in C:
        c['_n'] = near(c)
    start = sum(cost(c, c['cfg'], c['_n']) for c in C)
    for p in range(a.passes):
        moved = 0
        for c in sorted(C, key=lambda c: -cost(c, c['cfg'], c['_n'])):
            here = cost(c, c['cfg'], c['_n'])
            if here < 1:
                continue
            best = (here, c['cfg'])
            for cfg in options(c):
                k = cost(c, cfg, c['_n'])
                if k < best[0] - 1e-6:
                    best = (k, cfg)
            if best[1] != c['cfg']:
                c['cfg'] = best[1]
                c['_g'] = geom(c, c['cfg'])
                moved += 1
        total = sum(cost(c, c['cfg'], c['_n']) for c in C)
        print(f'pass {p + 1}: moved {moved}, total cost {total:.0f} (start {start:.0f})', flush=True)
        if not moved:
            break

    edits, rows = [], []
    for c in C:
        k, hits = cost(c, c['cfg'], c['_n'], detail=True)
        s1, s2, bend = c['cfg']
        if c['cfg'] != c['cfg0']:
            rotk = 'Angle1' if c['flipped'] else 'ROTATE PERP CL'
            if bend:
                r = bends[c['block']][c['cfg']]
                grip, ro = math.radians(r['grip']) % (2 * math.pi), math.radians(r['ro'])
            else:
                grip, ro = 0.0, st.HALF_PI
            # same property order as the measurement runs: lengths, bend, shelf, FLIP (RO), grip
            edits.append({'handle': c['handle'], 'dynamicProperties': {
                'SEG-1': s1, 'SEG-2': s2, 'SEG-2 (ANG)': math.radians(bend) % (2 * math.pi), 'SEG-3': BENT_SHELF if bend else c['s3'],
                'FLIP (RO)': ro, rotk: grip}})
        rows.append(dict(handle=c['handle'], text=' / '.join(t for t in c['lines'] if t), x=round(c['P'][0], 2), y=round(c['P'][1], 2),
                         seg1=s1, seg2=s2, bend=bend, was='/'.join(str(v) for v in c['cfg0']), cost=round(k),
                         conflicts=', '.join(sorted(set(hits)))))
    with open(out_job, 'w', encoding='utf-8') as f:
        json.dump({'version': 1, 'edits': edits}, f, indent=1)
    with open(report_csv, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(sorted(rows, key=lambda r: -r['cost']))
    left = [r for r in rows if r['conflicts']]
    print(json.dumps({'callouts': len(C), 'edits': len(edits), 'bent': sum(1 for c in C if c['cfg'][2]),
                      'still_conflicting': len(left), 'job': out_job, 'report': report_csv}))
    return 0


if __name__ == '__main__':
    sys.exit(main())

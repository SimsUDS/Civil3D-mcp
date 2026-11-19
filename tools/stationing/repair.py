#!/usr/bin/env python3
"""Re-solve the leaders of placed station blocks together, without bursting.

    python repair.py <data dir> <placed.json> [--out-job repair.json] [--report repair.csv] [--passes 8]

<placed.json> is a civil3d_entity query of the station blocks as they are now
(layer ELECTRIC-TEXT, INSERT, includeGeometry). Each callout keeps its block,
rotation and text; only SEG-1 / SEG-2 change. Every pass re-places each
callout that still conflicts, with all the others held where they are, and
keeps the change only if its cost drops. Conflicts are weighted: another
station's text worst, then its leader, buildings, other text, dimension text,
symbols. Text on NO-PLOT (sheet numbers) is ignored because it doesn't print.
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('data')
    ap.add_argument('placed')
    ap.add_argument('--out-job', default=None)
    ap.add_argument('--report', default=None)
    ap.add_argument('--passes', type=int, default=8)
    a = ap.parse_args(argv)
    out_job = a.out_job or os.path.join(a.data, 'stationing_repair.json')
    report_csv = a.report or os.path.join(a.data, 'stationing_repair_report.csv')

    job = st.Job(a.data)
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

    # Callout state
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
        C.append(dict(handle=e['handle'], P=P, ang=ang, flipped=e['blockName'].endswith('(FLIPPED)'), lines=lines,
                      s1=dp['SEG-1'], s2=dp['SEG-2'], s3=dp['SEG-3'], s1_0=dp['SEG-1'], s2_0=dp['SEG-2'], F=F,
                      sheet=dict(job.sheets).get(sh[0]) if sh else None,
                      skip={'block ' + feat_at.get((round(P[0], 2), round(P[1], 2)), '')}))

    def geom(c, s1, s2):
        return st.text_rects(c['P'], c['ang'], c['flipped'], s1, s2, c['lines']), st.leader_rect(c['P'], c['ang'], s1, s2, c['s3'])

    # spatial index of the callouts themselves (by feature location; reach is under 70 ft)
    def near(c):
        return [o for o in C if o is not c and math.dist(o['P'], c['P']) < 150]

    def cost(c, s1, s2, others, detail=False):
        rects, lead = geom(c, s1, s2)
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
            orects, olead = o['_g']
            if any(st.rect_hits_poly(r, orr) for r in rects for orr in orects):
                k += WEIGHT['stext']; hits.append('station text')
            elif any(st.rect_hits_poly(r, olead) for r in rects) or any(st.rect_hits_poly(lead, orr) for orr in orects):
                k += WEIGHT['sleader']; hits.append('station leader')
        k += 0.01 * (s1 + s2)
        return (k, hits) if detail else k

    for c in C:
        c['_g'] = geom(c, c['s1'], c['s2'])
    for c in C:
        c['_n'] = near(c)
    start = sum(cost(c, c['s1'], c['s2'], c['_n']) for c in C)
    for p in range(a.passes):
        moved = 0
        for c in sorted(C, key=lambda c: -cost(c, c['s1'], c['s2'], c['_n'])):
            here = cost(c, c['s1'], c['s2'], c['_n'])
            if here < 1:
                continue
            best = (here, c['s1'], c['s2'])
            for s1 in S1_OPTIONS:
                for s2 in range(3, st.SEG2_MAX + 1):
                    k = cost(c, s1, s2, c['_n'])
                    if k < best[0] - 1e-6:
                        best = (k, s1, s2)
            if (best[1], best[2]) != (c['s1'], c['s2']):
                c['s1'], c['s2'] = best[1], best[2]
                c['_g'] = geom(c, c['s1'], c['s2'])
                moved += 1
        total = sum(cost(c, c['s1'], c['s2'], c['_n']) for c in C)
        print(f'pass {p + 1}: moved {moved}, total cost {total:.0f} (start {start:.0f})', flush=True)
        if not moved:
            break

    edits, rows = [], []
    for c in C:
        k, hits = cost(c, c['s1'], c['s2'], c['_n'], detail=True)
        if (c['s1'], c['s2']) != (c['s1_0'], c['s2_0']):
            edits.append({'handle': c['handle'], 'dynamicProperties': {'SEG-1': c['s1'], 'SEG-2': c['s2']}})
        rows.append(dict(handle=c['handle'], text=' / '.join(t for t in c['lines'] if t), x=round(c['P'][0], 2), y=round(c['P'][1], 2),
                         seg1=c['s1'], seg2=c['s2'], was=f"{c['s1_0']}/{c['s2_0']}", cost=round(k), conflicts=', '.join(sorted(set(hits)))))
    with open(out_job, 'w', encoding='utf-8') as f:
        json.dump({'version': 1, 'edits': edits}, f, indent=1)
    with open(report_csv, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(sorted(rows, key=lambda r: -r['cost']))
    left = [r for r in rows if r['conflicts']]
    print(json.dumps({'callouts': len(C), 'edits': len(edits), 'still_conflicting': len(left), 'job': out_job, 'report': report_csv}))
    return 0


if __name__ == '__main__':
    sys.exit(main())

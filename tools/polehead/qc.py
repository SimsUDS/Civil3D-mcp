#!/usr/bin/env python3
"""Automatic QC for a pole head apply job, run after the job is drawn.

Rebuilds the job from its spec (so it knows what every new entity is), maps the
new handles from <job>.result.json, and checks the MEASURED drawing from a
civil3d_entity verify query. Prints only failures. Where the fix is mechanical
(box widths, calc re-centering, DG leader ends) it also writes a fix job.

    python qc.py spec.json job_TD.json job_TD.result.json query.json [query2.json ...] [--fix fix_TD.json]

The verify query: a window over the used frames, types TEXT, LWPOLYLINE, LEADER,
DIMENSION, INSERT, includeGeometry true (any layer). Saved tool output files are
fine as they are (the JSON array of text parts).

What it cannot check: whether the spec matches the PDF (heights read, slant,
box side, symbols, L/xx). A clean run means the drawing matches the spec and
the rules, not that the spec is right.
"""
from __future__ import annotations

import argparse
import json
import sys

import polehead as ph

TOL = 0.3                  # drawing units; differences below this are not reported
CLEAR = 0.05               # text boxes may touch this much before it counts as overlap

NOTE_TEXT = {ph.CREW['hdr'][0], ph.CREW['line'][0], ph.NOTE['hdr'][0], ph.NOTE['line'][0]}
NOTE_BOX = {ph.CREW['box'], ph.NOTE['box']}
RSPAN_TEXT = {h for h, _ in ph.RSPAN['lines']}
TEXT_SRC = {ph.CALLOUT[0], ph.DGTXT[0], ph.ANCTXT[0], ph.TLMNOTE['hdr'][0], ph.TLMNOTE['line'][0]} | \
    {h for h, _, _ in ph.LBL} | NOTE_TEXT | RSPAN_TEXT


# ------------------------------------------------------------------ loading
def load_entities(paths):
    """Entities by handle from one or more query results (raw result, or a saved tool output file)."""
    found = {}

    def walk(v):
        if isinstance(v, str):
            t = v.strip()
            if t[:1] in '{[':
                try:
                    walk(json.loads(t))
                except ValueError:
                    pass
        elif isinstance(v, dict):
            if 'handle' in v and 'type' in v:
                found[str(v['handle']).upper()] = v
                return
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    for p in paths:
        with open(p, encoding='utf-8') as f:
            walk(json.load(f))
    return found


def handle_map(J, result):
    """op key -> {source handle: new handle}."""
    maps = result.get('handles') or {}
    out = {}
    for key, op in J.ops:
        m = maps.get('g%d' % J.keymap[key], {})
        out[key] = {h: str(m[h]).upper() for h in op['handles'] if h in m}
    return out


# ------------------------------------------------------------------ geometry
def ext(e):
    x = e.get('extents')
    if not x:
        return None
    return (x['min']['x'], x['min']['y'], x['max']['x'], x['max']['y'])


def overlap(a, b, gap=CLEAR):
    return a[0] < b[2] - gap and b[0] < a[2] - gap and a[1] < b[3] - gap and b[1] < a[3] - gap


def segs(e):
    v = [(p['x'], p['y']) for p in e.get('vertices') or []]
    if e.get('type') == 'LINE' and 'start' in e:
        v = [(e['start']['x'], e['start']['y']), (e['end']['x'], e['end']['y'])]
    return list(zip(v, v[1:]))


def seg_hits_box(s, b, shrink=0.2):
    """Segment s crosses rectangle b (shrunk a little so a touching end does not count)."""
    x0, y0, x1, y1 = b[0] + shrink, b[1] + shrink, b[2] - shrink, b[3] - shrink
    if x0 >= x1 or y0 >= y1:
        return False
    (ax, ay), (bx, by) = s
    t0, t1 = 0.0, 1.0
    dx, dy = bx - ax, by - ay
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def seg_cross(s, t):
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    (a, b), (c, d) = s, t
    return orient(a, b, c) * orient(a, b, d) < -1e-9 and orient(c, d, a) * orient(c, d, b) < -1e-9


def dist_to_seg(p, s):
    (ax, ay), (bx, by) = s
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return ((p[0] - ax - t * dx) ** 2 + (p[1] - ay - t * dy) ** 2) ** 0.5


# ------------------------------------------------------------------ checks
class QC:
    def __init__(self, spec, J, ents, hmap):
        self.spec, self.J, self.E, self.H = spec, J, ents, hmap
        self.issues = []          # (pole, text)
        self.fix_edits, self.fix_moves = [], []
        self.missing = []
        # every created entity: (key, src, new handle, meta, entity or None)
        self.items = []
        for key, op in J.ops:
            for src in op['handles']:
                new = hmap[key].get(src)
                self.items.append((key, src, new, J.meta.get(key, {}), ents.get(new) if new else None))
                if not new or new not in ents:
                    self.missing.append((J.meta.get(key, {}).get('pole'), src, new))

    def add(self, pole, msg):
        self.issues.append((pole, msg))

    def pick(self, **kw):
        return [it for it in self.items if it[4] is not None and all(it[3].get(k) == v for k, v in kw.items())]

    # 0: every edit landed (text, attributes, visibility, layer, color)
    def edits_applied(self):
        for key, src, e in self.J.edits:
            if key is None:
                pole, ent, name = None, self.E.get(src.upper()), src
            else:
                new = self.H[key].get(src)
                pole, ent, name = self.J.meta.get(key, {}).get('pole'), self.E.get(new), new
            if ent is None:
                continue
            if 'text' in e:
                got = ent.get('dimensionText') if ent.get('type') == 'DIMENSION' else ent.get('text')
                if got is not None and got.replace('%%U', '') != e['text'].replace('%%U', ''):
                    self.add(pole, '%s %s reads %r, should be %r' % (ent.get('type'), name, got, e['text']))
            for k, want in (e.get('attributes') or {}).items():
                got = (ent.get('attributes') or {}).get(k)
                if got is not None and str(got) != str(want):
                    self.add(pole, 'block %s attribute %s reads %r, should be %r' % (name, k, got, want))
            for k, want in (e.get('dynamicProperties') or {}).items():
                got = (ent.get('dynamicProperties') or {}).get(k)
                if got is not None and str(got).upper() != str(want).upper():
                    self.add(pole, 'block %s %s is %r, should be %r' % (name, k, got, want))
            if 'layer' in e and ent.get('layer') and ent['layer'].upper() != e['layer'].upper():
                self.add(pole, '%s %s on layer %s, should be %s' % (ent.get('type'), name, ent['layer'], e['layer']))
            if 'colorIndex' in e and ent.get('colorIndex', 256) != e['colorIndex']:
                self.add(pole, '%s %s color %s, should be %s' % (ent.get('type'), name, ent.get('colorIndex', 'ByLayer'),
                                                                'ByLayer' if e['colorIndex'] == 256 else e['colorIndex']))

    def texts(self, pole):
        out = []
        for key, src, new, m, e in self.pick(pole=pole):
            if src in TEXT_SRC and e.get('type') == 'TEXT' and ext(e):
                out.append((new, e, m))
        return out

    # overlaps between texts, and texts sitting on guys or leaders
    def clutter(self, pole):
        T = self.texts(pole)
        for i in range(len(T)):
            for j in range(i + 1, len(T)):
                if overlap(ext(T[i][1]), ext(T[j][1])):
                    self.add(pole, 'text %r overlaps %r' % (T[i][1].get('text'), T[j][1].get('text')))
        lines = [(new, m, e) for key, src, new, m, e in self.pick(pole=pole)
                 if src in (ph.GUY[0], ph.LEADER[0])]
        for new, m, e in lines:
            kind = 'leader' if e.get('type') == 'LEADER' else 'guy'
            for tnew, te, tm in T:
                if kind == 'leader' and tm.get('part') in ('dg', 'anclabel') and \
                        (tm.get('part'), tm.get('dg'), tm.get('profile')) == (m.get('part'), m.get('dg'), m.get('profile')):
                    continue                                    # a leader's own text
                if any(seg_hits_box(s, ext(te)) for s in segs(e)):
                    self.add(pole, '%s %s runs through text %r' % (kind, new, te.get('text')))
        leaders = [(new, e) for new, m, e in lines if e.get('type') == 'LEADER']
        for i in range(len(leaders)):
            for j in range(i + 1, len(leaders)):
                if any(seg_cross(s, t) for s in segs(leaders[i][1]) for t in segs(leaders[j][1])):
                    self.add(pole, 'leaders %s and %s cross' % (leaders[i][0], leaders[j][0]))

    # callouts on one aligned column per profile
    def callouts(self, pole):
        by = {}
        for key, src, new, m, e in self.pick(pole=pole, part='callout'):
            if ext(e):
                by.setdefault(m.get('profile'), []).append((m, e))
        for prof, L in by.items():
            right = L[0][0].get('side') == 'R'
            xs = [ext(e)[0] if right else ext(e)[2] for m, e in L]
            if max(xs) - min(xs) > 1.0:
                self.add(pole, 'callouts of profile %d are not on one column (edges %.2f to %.2f)' % (prof, min(xs), max(xs)))

    # dim labels (as sent) against each other and the measured callouts
    def dim_labels(self, pole):
        labels = []
        for key, src, e in self.J.edits:
            m = self.J.meta.get(key, {}) if key is not None else {}
            if m.get('pole') != pole or m.get('part') != 'dim' or 'textPosition' not in e:
                continue
            w = ph.label_w(e['text'])
            x, y = e['textPosition']['x'], e['textPosition']['y']
            labels.append((m.get('profile'), e['text'], (x - w / 2, y - ph.LABEL_H / 2, x + w / 2, y + ph.LABEL_H / 2)))
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                a, b = labels[i][2], labels[j][2]
                if a[0] < b[2] + 0.5 and b[0] < a[2] + 0.5 and a[1] < b[3] + 1 and b[1] < a[3] + 1:
                    self.add(pole, 'dim labels %s and %s collide' % (labels[i][1], labels[j][1]))
        for new, te, tm in self.texts(pole):
            if tm.get('part') != 'callout':
                continue
            for prof, txt, b in labels:
                if overlap(b, ext(te), gap=-0.5):
                    self.add(pole, 'dim label %s sits on callout %r' % (txt, te.get('text')))

    # boxes fit their measured text (notes 3 past the longest line; calcs and ruling spans also centered on Cx)
    def boxes(self, pole, Cx):
        groups = {}
        for key, src, new, m, e in self.pick(pole=pole):
            part = m.get('part')
            if part not in ('crewnote', 'note', 'calc', 'rspan', 'tlmnote'):
                continue
            g = groups.setdefault((part, m.get('box')), dict(texts=[], box=None))
            if src in NOTE_BOX or src in (ph.RSPAN['box'], ph.TLMNOTE['box']):
                g['box'] = (new, e)
            elif e.get('type') == 'TEXT':
                g['texts'].append((new, e))
        for (part, n), g in sorted(groups.items(), key=lambda kv: str(kv[0])):
            if not g['box'] or not g['texts'] or not g['box'][1].get('vertices'):
                continue
            bnew, be = g['box']
            vx = [p['x'] for p in be['vertices']]
            vy = [p['y'] for p in be['vertices']]
            L, R, top, bot = min(vx), max(vx), max(vy), min(vy)
            ex = [ext(e) for _, e in g['texts'] if ext(e)]
            if not ex:
                continue
            name = {'crewnote': 'CREW NOTE box', 'note': 'NOTE box', 'tlmnote': 'TLM NOTE box',
                    'calc': 'DE CALC box', 'rspan': 'RULING SPAN box'}[part] + ('' if n is None else ' %d' % (n + 1))
            if part == 'tlmnote':
                worst = max(x[2] for x in ex)
                if worst > R - 0.5:
                    self.add(pole, '%s: a note line runs past the box (to %.1f, box right %.1f); wrap it' % (name, worst, R))
                continue
            if part == 'calc':
                left = [x for x in ex if x[0] < L + 150]
                right = [x for x in ex if x[0] >= L + 150]
                want_r = max([x[2] + 3 for x in left] + [x[2] + 5.63 for x in right])
            else:
                want_r = max(x[2] for x in ex) + 3
            w = want_r - L
            newL = Cx - w / 2 if part in ('calc', 'rspan') else L
            if abs(want_r - R) <= TOL and abs(newL - L) <= TOL:
                continue
            self.add(pole, '%s: width %.2f should be %.2f%s (fixed in the fix job)' % (
                name, R - L, w, ', re-centered on the sheet' if abs(newL - L) > TOL else ''))
            if abs(newL - L) > TOL:
                self.fix_moves.append(dict(handles=[h for h, _ in g['texts']], dx=ph.r4(newL - L), dy=0))
            self.fix_edits.append(dict(handle=bnew, vertices=[ph.pt(newL, top), ph.pt(newL + w, top),
                                                               ph.pt(newL + w, bot), ph.pt(newL, bot)]))

    # DG leaders: end 2.8 from the measured text edge facing the guys, at baseline + 3; arrow on a guy
    def dg_leaders(self, pole):
        guys = {}
        for key, src, new, m, e in self.pick(pole=pole, part='guy'):
            guys.setdefault(m.get('profile'), []).extend(segs(e))
        pairs = {}
        for key, src, new, m, e in self.pick(pole=pole, part='dg'):
            p = pairs.setdefault((m.get('profile'), m.get('dg')), {})
            p['text' if src == ph.DGTXT[0] else 'leader'] = (new, e)
        bases = {}
        for (prof, n), p in sorted(pairs.items(), key=lambda kv: str(kv[0])):
            if 'text' not in p or 'leader' not in p:
                continue
            tnew, te = p['text']
            lnew, le = p['leader']
            v = [(q['x'], q['y']) for q in le.get('vertices') or []]
            b = ext(te)
            if len(v) < 3 or not b or 'position' not in te:
                continue
            base = te['position']['y']
            arrow = v[0]
            # guys on both sides of a pole: each side's DG stack is spaced on its own (text left or right of its arrow)
            bases.setdefault((prof, arrow[0] < b[0]), []).append(base)
            if arrow[0] < b[0]:
                end = b[0] - 2.8
                elbow = end - 3
            else:
                end = b[2] + 2.8
                elbow = end + 3
            ey = base + 3
            if abs(v[-1][0] - end) > TOL or abs(v[-1][1] - ey) > TOL or abs(v[1][0] - elbow) > TOL:
                self.add(pole, 'DG leader for %r: end is %.2f off the text (fixed in the fix job)' % (
                    te.get('text'), abs(v[-1][0] - end)))
                self.fix_edits.append(dict(handle=lnew, vertices=[ph.pt(*arrow), ph.pt(elbow, ey), ph.pt(end, ey)]))
            if guys.get(prof) and min(dist_to_seg(arrow, s) for s in guys[prof]) > TOL:
                self.add(pole, 'DG leader for %r: arrow is not on a guy' % te.get('text'))
        for prof, ys in bases.items():
            ys = sorted(ys)
            for a, c in zip(ys, ys[1:]):
                if c - a < 29.9:
                    self.add(pole, 'DG callouts %.1f apart, need 30' % (c - a))

    def run(self):
        self.edits_applied()
        for pole in self.spec['poles']:
            num = pole['pole']
            Cx, _ = ph.frame(pole['frame'])
            self.clutter(num)
            self.callouts(num)
            self.dim_labels(num)
            self.boxes(num, Cx)
            self.dg_leaders(num)
        return self


# ------------------------------------------------------------------ spec lint (no drawing needed)
def lint(spec):
    out = []
    for pole in spec['poles']:
        num = pole['pole']
        for kind in ('crew', 'notes'):
            lines = pole.get(kind) or []
            for t in lines:
                if t != t.upper():
                    out.append((num, '%s line not uppercase: %r' % (kind, t)))
                if not t.startswith('-'):
                    out.append((num, '%s line has no leading dash: %r' % (kind, t)))
            if len(set(lines)) != len(lines):
                out.append((num, 'duplicate %s lines' % kind))
        tlm = pole.get('tlm') or {}
        for t in tlm.get('notes') or []:
            if t != t.upper():
                out.append((num, 'TLM note not uppercase: %r' % t))
            if t.startswith('-'):
                out.append((num, 'TLM note should not start with a dash: %r' % t))
        if len(tlm.get('addr') or []) > ph.TLM_MAX:
            out.append((num, '%d TLM addresses, over the %d that fit a frame; needs Kevin\'s guidance' % (len(tlm['addr']), ph.TLM_MAX)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec')
    ap.add_argument('job', help='the apply job file that was run')
    ap.add_argument('result', help='<job>.result.json from the apply')
    ap.add_argument('query', nargs='+', help='verify query result file(s)')
    ap.add_argument('--fix', help='write the mechanical fixes here as an apply job')
    a = ap.parse_args(argv)

    spec = json.load(open(a.spec, encoding='utf-8'))
    J = ph.build_job(spec)
    regen = J.to_apply_job()
    if regen != json.load(open(a.job, encoding='utf-8')):
        print('QC STOPPED: the job file was not generated from this spec (regenerate or pass the right spec).')
        return 2
    result = json.load(open(a.result, encoding='utf-8'))
    if result.get('status') != 'completed':
        print('QC STOPPED: the apply did not complete (stage %s: %s).' % (result.get('stage'), result.get('error')))
        return 2
    ents = load_entities(a.query)
    qc = QC(spec, J, ents, handle_map(J, result)).run()

    issues = lint(spec) + qc.issues
    if qc.missing:
        poles = sorted({str(p) for p, _, _ in qc.missing})
        issues.append((None, '%d created entities are not in the query (poles %s); widen the window or types, '
                             'those were not checked' % (len(qc.missing), ', '.join(poles))))
    if not issues:
        print('QC: clean (drawing matches the spec and the rules; the spec itself was not checked against the PDF)')
    else:
        print('QC: %d issue(s)' % len(issues))
        seen = set()
        for pole, msg in issues:
            line = '  %s%s' % ('' if pole is None else str(pole) + ': ', msg)
            if line not in seen:
                seen.add(line)
                print(line)
    if a.fix and (qc.fix_edits or qc.fix_moves):
        job = dict(version=1, copies=[dict(id='m%d' % i, mode='move', **mv) for i, mv in enumerate(qc.fix_moves)],
                   edits=qc.fix_edits, erase=[])
        with open(a.fix, 'w', encoding='utf-8') as f:
            json.dump(job, f, separators=(',', ':'))
        print('fix job: %s (%d moves, %d edits)' % (a.fix, len(qc.fix_moves), len(qc.fix_edits)))
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""One-call survey of a pole head PDF (workflow step 1).

    python -I survey.py --find "<job folder>" <outdir>      first: which PDF(s) and pages hold the pole heads
    python -I survey.py "<TD>_POLE HEAD TEMPLATE.pdf" <outdir>

--find checks every PDF in the job folder (forms, blank forms, sketches drawn on a basemap, scans) and
writes find.json; see classify_page.

Writes into <outdir> (never the job folder):
  text.txt            condensed text of every page (callout wording; empty for scans)
  p<N>.png            whole page, 60 dpi (layout)
  p<N>_detail.png     POLE HEAD DETAIL box, 130 dpi (profiles, red callouts, arrows)
  p<N>_pole<K>_top.png  each drawn pole's top equipment, 400 dpi (pins, slants, cutouts, arresters, boxes)
  p<N>_pole<K>.png    each drawn pole ground to top, 200 dpi (guys, anchors, comm rows)
  p<N>_tlm.png        TLM table and its NOTE area, 150 dpi
  p<N>_tlm_img<K>.png every pasted image in the TLM area, rendered over its FULL bbox at 220 dpi (pasted Excel
                      snippets often run left past the TLM box; the full bbox keeps whole meters and house numbers)
  index.json          per page: pole number, station, poles found (x, top, bottom in PDF points) and the files

Poles are found as long vertical vector lines inside the detail box. A scan (no vector lines) gets only the page,
detail and TLM renders; zoom by hand there. Regions are fractions of the page so other page sizes still work.
Needs PyMuPDF (pip install pymupdf).
"""
from __future__ import annotations

import json
import os
import re
import sys

import pymupdf

# fractions of the page (from the AUD POLE HEAD TEMPLATE form, 1224 x 792 pt)
DETAIL = (0.327, 0.139, 0.825, 0.556)
TLM = (0.139, 0.556, 0.278, 0.909)
TLM_IMG_AREA = (0.0, 0.5, 0.45, 1.0)       # images whose bbox starts here are TLM snippets
HEADER = (0.6, 0.04, 1.0, 0.12)            # STATION # / POLE # line, top right
TOP_ZOOM = (60, 12, 70)                    # half width, above the pole top, below the pole top (pt)


def frac(page, f):
    w, h = page.rect.width, page.rect.height
    return pymupdf.Rect(f[0] * w, f[1] * h, f[2] * w, f[3] * h)


def find_poles(page, area):
    """Long vertical lines in the detail box: (x, top, bottom), left to right."""
    segs = []
    lo, hi = area.x0 + 10, area.x1 - 10             # the detail box's own walls are not poles
    for d in page.get_drawings():
        for it in d['items']:
            if it[0] == 'l':                         # a stroked line
                a, b = it[1], it[2]
                x, t, bt, w = (a.x + b.x) / 2, min(a.y, b.y), max(a.y, b.y), abs(a.x - b.x)
            elif it[0] == 're':                      # the form draws pole lines as hairline rectangles
                r = it[1]
                x, t, bt, w = (r.x0 + r.x1) / 2, r.y0, r.y1, r.width
            else:
                continue
            if w < 1.5 and bt - t > 0.3 * area.height and lo < x < hi and area.y0 - 2 <= t and bt <= area.y1 + 2:
                segs.append((round(x, 1), t, bt))
    poles = []
    for x, t, b in sorted(segs):
        if poles and abs(poles[-1][0] - x) < 3:
            px, pt_, pb = poles[-1]
            poles[-1] = (px, min(pt_, t), max(pb, b))
        else:
            poles.append((x, t, b))
    return poles


CALLOUT_AT = re.compile(r"@\s*\d{1,2}(?:'|\b)")      # '@ 37'', '@36'6"', '@ 22' (callout heights)
POLE_NO = re.compile(r'\b\d{6,8}[EH]\b')
LOOKING = re.compile(r'LOOKING\s+(N|E|NORTH|EAST)\b')


def classify_page(page):
    """What a PDF page holds, for finding the pole heads in a job folder (workflow step 1).

    form     the AUD POLE HEAD TEMPLATE form with a pole number (one pole per page)
    blank    the form with no pole number (XXXX), or the planner's PREMADE BLOCKS reference page
    sketch   pole head sketches drawn somewhere else, e.g. on the basemap (TD2558870): LOOKING N / LOOKING E
             labels with callouts at heights. Each sketch is tied to its pole by a leader; read the leaders,
             not the label text (that job had two sketches both labeled 1281755E)
    scan     no text layer: look at the thumbnail
    other    anything else (basemap without sketches, cover sheet, permits)"""
    raw = page.get_text()
    up = raw.upper()
    rec = dict(callouts=len(CALLOUT_AT.findall(raw)), looking=[], poles=sorted(set(POLE_NO.findall(raw))),
               tlm_tables=up.count('METER NUMBER'))
    if not raw.strip():
        rec['kind'] = 'scan'
    elif 'POLE HEAD DETAIL' in up:
        head = ' '.join(page.get_text(clip=frac(page, HEADER)).split())
        toks = re.sub(r'STATION\s*#|POLE\s*#', ' ', head).split()
        pole_no = next((t for t in toks if re.fullmatch(r'\d{4,8}[EH]', t)), None)
        rec['pole'] = pole_no
        rec['kind'] = 'form' if pole_no and 'PREMADE BLOCKS' not in up else 'blank'
    else:
        for w in page.get_text('blocks'):
            m = LOOKING.search(' '.join(w[4].upper().split()))
            if m:
                rec['looking'].append(dict(dir=m.group(1)[0], bbox=[round(v, 1) for v in w[:4]]))
        rec['kind'] = 'sketch' if rec['looking'] and rec['callouts'] >= 3 else 'other'
    return rec


def find(folder, out):
    """Check EVERY PDF in the job folder for pole heads, not just the one named POLEHEADS (planners sometimes
    draw them on the basemap or in another PDF). Writes find.json and a 40 dpi thumbnail of every scan or
    sketch page into out, and prints one line per page plus where the pole heads are."""
    os.makedirs(out, exist_ok=True)
    pdfs = sorted(f for f in os.listdir(folder) if f.lower().endswith('.pdf'))
    report, hits = [], []
    for f in pdfs:
        try:
            doc = pymupdf.open(os.path.join(folder, f))
        except Exception as e:                      # a damaged or locked PDF: say so, keep going
            print('%s: cannot open (%s)' % (f, e))
            continue
        for i, page in enumerate(doc):
            rec = dict(pdf=f, page=i + 1, size=[round(page.rect.width), round(page.rect.height)], **classify_page(page))
            if rec['kind'] in ('scan', 'sketch'):
                thumb = 'find_%s_p%d.png' % (re.sub(r'\W+', '_', os.path.splitext(f)[0]), i + 1)
                page.get_pixmap(dpi=40).save(os.path.join(out, thumb))
                rec['thumb'] = thumb
            report.append(rec)
            extra = {'form': ' pole %s' % rec.get('pole'),
                     'sketch': ' %d LOOKING label(s), %d callouts, poles %s' % (
                         len(rec['looking']), rec['callouts'], ', '.join(rec['poles']) or '-'),
                     'scan': ' (no text layer, check the thumbnail)'}.get(rec['kind'], '')
            if rec['tlm_tables'] and rec['kind'] not in ('form', 'blank'):   # the form prints its own table
                extra += ', %d TLM table(s)' % rec['tlm_tables']
            print('%s p%d: %s%s' % (f, i + 1, rec['kind'], extra))
            if rec['kind'] in ('form', 'sketch'):
                hits.append(rec)
    with open(os.path.join(out, 'find.json'), 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=1)
    forms = sorted({r['pdf'] for r in hits if r['kind'] == 'form'})
    sketches = ['%s p%d' % (r['pdf'], r['page']) for r in hits if r['kind'] == 'sketch']
    if forms:
        print('pole head forms: %s (run survey.py on it)' % ', '.join(forms))
    if sketches:
        print('pole head sketches outside the form: %s (no survey.py; crop the LOOKING labels by hand)'
              % ', '.join(sketches))
    if not hits:
        print('no pole heads found in any PDF; check the scan thumbnails, then ask Kevin')
    return 0


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) == 3 and argv[0] == '--find':
        return find(argv[1], argv[2])
    if len(argv) != 2:
        print(__doc__)
        return 2
    pdf, out = argv
    os.makedirs(out, exist_ok=True)
    doc = pymupdf.open(pdf)
    index, text = [], []
    for i, page in enumerate(doc):
        n = i + 1
        raw = page.get_text()
        cond = '\n'.join(' '.join(l.split()) for l in raw.splitlines() if l.strip())
        text.append('==== page %d ====\n%s' % (n, cond))
        head = ' '.join(page.get_text(clip=frac(page, HEADER)).split())
        # the form prints 'STATION # POLE #' and the two values land after it in either order
        toks = re.sub(r'STATION\s*#|POLE\s*#', ' ', head).split()
        pole_no = next((t for t in toks if re.fullmatch(r'\d{4,8}E', t)), None)
        station = next((t for t in toks if t != pole_no), None)
        rec = dict(page=n, pole=pole_no, station=station,
                   scan=not raw.strip(), files=[], poles=[])
        f = 'p%d.png' % n
        page.get_pixmap(dpi=60).save(os.path.join(out, f))
        rec['files'].append(f)
        det = frac(page, DETAIL)
        f = 'p%d_detail.png' % n
        page.get_pixmap(dpi=130, clip=det).save(os.path.join(out, f))
        rec['files'].append(f)
        for k, (x, top, bot) in enumerate(find_poles(page, det)):
            hw, up, dn = TOP_ZOOM
            f1, f2 = 'p%d_pole%d_top.png' % (n, k + 1), 'p%d_pole%d.png' % (n, k + 1)
            page.get_pixmap(dpi=400, clip=pymupdf.Rect(x - hw, top - up, x + hw, top + dn)).save(os.path.join(out, f1))
            page.get_pixmap(dpi=200, clip=pymupdf.Rect(x - 90, top - 15, x + 90, bot + 25)).save(os.path.join(out, f2))
            rec['poles'].append(dict(x=x, top=round(top, 1), bottom=round(bot, 1), files=[f1, f2]))
        tlm = frac(page, TLM)
        f = 'p%d_tlm.png' % n
        page.get_pixmap(dpi=150, clip=tlm).save(os.path.join(out, f))
        rec['files'].append(f)
        rec['tlm_text'] = ' '.join(page.get_text(clip=tlm).split())
        area = frac(page, TLM_IMG_AREA)
        k = 0
        for im in page.get_image_info():
            bb = pymupdf.Rect(im['bbox'])
            if area.contains(bb.tl) and bb.width > 40:
                k += 1
                f = 'p%d_tlm_img%d.png' % (n, k)
                page.get_pixmap(dpi=220, clip=bb).save(os.path.join(out, f))
                rec['files'].append(f)
        index.append(rec)
    with open(os.path.join(out, 'text.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(text) + '\n')
    with open(os.path.join(out, 'index.json'), 'w', encoding='utf-8') as fh:
        json.dump(index, fh, indent=1)
    for r in index:
        print('page %d: pole %s, station %s, %d pole line(s)%s%s' % (
            r['page'], r['pole'], r['station'], len(r['poles']), ', SCAN' if r['scan'] else '',
            ', %d TLM image(s)' % sum('tlm_img' in f for f in r['files']) if any('tlm_img' in f for f in r['files']) else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())

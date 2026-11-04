#!/usr/bin/env python3
"""One-call survey of a pole head PDF (workflow step 1).

    python -I survey.py "<TD>_POLE HEAD TEMPLATE.pdf" <outdir>

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


def main(argv=None):
    argv = argv or sys.argv[1:]
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

# Sheet data: crew notes, notes, GPS, ELEV

Read on every job when building the note lines (step 3). `station_builder.py` applies most of these; check its output against them.

## Source (Station Builder tab, columns N:Q, rows 4 to 46)

- Fill-ins can sit in O, P or Q depending on the planner (TD2536074 had them all in Q). A whole access note typed as the fill-in (`FOOT ACCESS VIA REAR PROPERTY OF ...`) replaces the `-ACCESS VIA STREET NAME` template. `2014 , NA` = set year, inspection year; NA becomes N/A.

- LAT = O9, LONG = O11, ELEV = O13.
- CREW NOTE lines: N17 to N25. Empty = no crew notes.
- NOTE lines: every non-empty N cell N27 to N46 (gaps allowed). Fill-in values in O/P on the same row.
- Whole notes typed in column O with N empty (`FOOT ACCESS VIA BACKYARD OF ...`) ARE notes, in row order. Do not report them.

## Text rules (all notes, crew notes and TLM notes)

- One CAD line per note: join Excel line breaks with single spaces.
- All uppercase.
- Fix obvious spelling (DEFUALT, REQUIRMENT, EASMENT, UKNOWN, VEGITATION, OBSTUCTION). Numbers exactly as written. Grammar slips copied as written.
- Drop exact duplicates. Contradicting lines (`-PTC REQUIRED` and `-NO PTC REQUIRED`) both kept and noted.
- Every note line (not TLM notes) starts with `-`.
- Fill blanks in order from the fill-in cell: `-POLE SET IN ______, INSP. ______` + "2018,  INSP. N/A" = `-POLE SET IN 2018, INSP. N/A`; `-IPI REQUIRED; NOTIFICATION #________ REQUESTED ON __/__/__` + "415649921, 10/01/2026"; `-TRUCK ACCESS VIA STREET NAME` + "WINDSOR DR" = `-TRUCK ACCESS VIA WINDSOR DR`; `-SAME HOLE SET DUE TO ___________` + "RISER"; `-HARDSET ___` + "NORTHWEST".
- POLE SET IN with no data: `-POLE SET IN N/A, INSP. N/A`.
- A fill-in repeating the template word is written once (`-TRUCK ACCESS VIA CALLE DAMASCO`). Split a glued house number (`OF1211` becomes `OF 1211`).
- Any other blank with no fill-in: draft as written, do not report.
- GPS: LAT/LONG as in the tab (the block supplies N/W).
- ELEV FOOTAGE: number only (strip `'` or FT). No elevation: blank, not reported.

## Stack layout (left edges at Cx - 919.971)

1. First box (CREW NOTE, or NOTE with no crew notes) top-left at (Cx - 919.971, Cy + 618.326).
2. No crew notes: no CREW NOTE box.
3. NOTE box top = CREW bottom - 5.
4. GPS: top = NOTE bottom - 5; insertion (bottom-left) y = top - 43.23.
5. ELEV: top = GPS bottom - 5; insertion y = top - 14.90. The NO-PLOT lead line 39498C is copied with it at the same offset.
6. Obstruction detail below ELEV (obstruction.md).

## Box geometry (CREW NOTE, NOTE, DE CALC; DECAL, SIMPLEX 4.8, about 3.97 per character)

- Text x = box left + 2.876. Header baseline = top - 8.03; each next line 8.027 lower. Bottom = last baseline - 4.21.
- Right = longest MEASURED text right edge + 3 (DE CALC: right column edge + 5.63). qc.py refits these in the fix job.

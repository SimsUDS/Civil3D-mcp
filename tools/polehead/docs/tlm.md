# TLM block and TLM NOTE box

Read when any pole has TLM data (a filled PDF TLM table, a pasted Excel snippet, or a TLM xlsx tab). The form's placeholder X's only, an empty table, or a crossed out table: no TLM block, no need to read further.

## Source

- The PDF TLM table (handwritten or a pasted Excel snippet). "PLEASE SEE ATTACHED EXCEL SHEET FOR TLM INFO", or a blank table with a TLM xlsx tab for the pole: use the tab whose name matches the pole number.
- xlsx: EX = E2:H2, PR = E3:H3, CLIMATE-ZONE E4, VD-DROP E5, FLICKER E6, PRI-CIRC E7, ADDRESSn = column B, METERn = column A from row 3 down, notes from E8 down (D8 `NOTE:`).
- A pasted snippet can extend left past the TLM box: crop wide enough to read full house numbers before calling it cut off. Truly clipped meters: leave those METER slots blank and note it.

## Values

- Street address only: drop city and state; keep a unit (`718 N MARKET ST APT 3`). A source that already lists street addresses only (TLM CUSTOMER DATA xlsx with METER/ADDRESS column pairs per pole) gets `"raw": true` so tags like `WSDR` survive. Un-swap values pasted in the wrong column.
- STRUCTURE = pole number. EX and PR fields as written; EX-LOAD and PR-LOAD WITHOUT `%` (the block prints its own). PRI-CIRC as written (`REJADA 16KV`).
- Always send STRUCTURE, the EX fields, CLIMATE-ZONE and PRI-CIRC (the stash holds `-` and `_______ _KV`); "" for a blank EX field.
- Spec: `"tlm": {"ex": [size, kva, cust, load], "pr": [...], "cz", "pc", "vd", "flicker", "addr": [[address, meter], ...], "notes": [...]}`.

## Placement (generator)

- Insertion (Cx + 777.554, Cy + 114.314). `ADDRESS LIST n` visibility, n = address count (10 max).
- Visible table bottom: insertion y - 70.40 - (n - 5) x 11.73.
- More than 10 addresses: block stays at LIST 10; rows 11 to 20 are burst rows copied from the row 12 set. Before generating, query window x 1850 to 2003, y -792.5 to -779.5, layer MISC, includeGeometry false, pick with `polehead.pick_tlm_extra(entities)` and set spec `"tlm_extra": [address, meter, box, line]`. Row k top = insertion y - 129.0591 - (k - 11) x 11.7326. Rows keep bursting down the TLM column while the table and its TLM NOTE box stay above the frame bottom (60 rows fit with three notes; TD2486645 68718E had 60). More than fit: fill what fits and report.

## TLM NOTE box

- Notes from the tab or the PDF TLM NOTE area, directly under the visible table (or the last burst row). Common text rules but NO leading dash. Wrap past about 38 characters (the generator wraps at word breaks; give each note as one string in the spec). The blue placeholder `X MILES AWAY FROM SUB` is not a note. No notes: no box.
- Geometry: box top = table bottom; header baseline top - 7.98; first note top - 20.32; next 8.03 lower; bottom = last baseline - 7.40.

# Single line (SCE one-line diagrams)

Tools and the reference generator for drafting SCE single line diagrams in Civil 3D from circuit-map PDFs, built on the
Ash job (Royer page 1 + Lawrence page 10). Start with `docs/SKILL.md`.

| File | What it does |
| --- | --- |
| `extract_page.py` | Vector extraction of one PDF page inside the red cloud: conductors, poles, boxes, triangles, label clusters, streets |
| `symbol_census.py` + `symbol_dictionary.json` | Cluster every small vector symbol, group by shape signature, label with the block dictionary |
| `extract_symbols.py` | Fuse zig-zags, ground taps and chevrons with attachment points |
| `tile_check.py` | Tile the cloud, render PDF tiles and the matching drawing windows for review |
| `sweep_ends.py`, `sweep_sheet.py` | Loose cable ends in a drawing query, and a contact sheet of them |
| `road_check.py`, `road_overlay.py` | PDF street coverage vs drawn roads, and an overlay image of both |
| `generator/` | `build_royer_v6.py` (+ `lawrence_part.py`, `rr_center2.py`): writes a `civil3d_entity apply` job |
| `docs/drafting-rules.md` | Kevin's rules with their reasons |
| `docs/block_conventions.md` | Block terminals, label offsets and layouts measured from the finished Ash drawing |

The generator reads job files under `C:\civ3dmcp\jobs\Singleline` (template handles, PDF, extracts) by absolute path.

```
python generator/build_royer_v6.py royer_job_vNN.json <fresh drawing query.json>
python sweep_ends.py <drawing query.json>
python road_check.py <drawing query.json>
```

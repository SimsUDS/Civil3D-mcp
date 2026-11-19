# Stationing (DYN STATION blocks, OH and UG power jobs)

Computes and places station labels on overhead (OH) and underground (UG) power jobs from drawing data. The skill instructions are in `docs/SKILL.md`; the block quirks are in `docs/block-behavior.md`.

- `stationing.py` reads the saved queries in a data folder and writes one `civil3d_entity` apply job plus a review CSV. Modes: `missing` (default), `fill` (XX+XX), `all`.
- `repair.py` re-solves SEG-1 / SEG-2 on placed blocks jointly (edit job + CSV of what still conflicts); no bursting.
- `test_stationing.py` holds unit tests (`python -m unittest discover -s tools/stationing`).
- `package_skill.py` builds `power-stationing.zip` for upload to claude.ai (Settings → Capabilities → Skills).

The script needs the drawing data on the same machine, so it fits Claude Code / the desktop Code tab, where the civil3d MCP server writes query files locally. In a claude.ai chat the skill's script runs in the chat's sandbox and can't read files the MCP server wrote on the drafting PC.

Validated on TD2573793 (2026-11-19). It rebuilt 366 stations from scratch; against the drafted originals, 333/364 stations and 296/364 full text match. Most of the differences are survey vs. grid-map IDs, and intersection cases that were already in question.

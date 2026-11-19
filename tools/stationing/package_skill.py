#!/usr/bin/env python3
"""Build power-stationing.zip for claude.ai (Settings > Capabilities > Skills).

    python package_skill.py [out.zip]

Layout inside the zip: power-stationing/SKILL.md, scripts/stationing.py,
references/block-behavior.md (SKILL.md points at those paths).
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {
    'power-stationing/SKILL.md': os.path.join(HERE, 'docs', 'SKILL.md'),
    'power-stationing/scripts/stationing.py': os.path.join(HERE, 'stationing.py'),
    'power-stationing/scripts/repair.py': os.path.join(HERE, 'repair.py'),
    'power-stationing/references/block-behavior.md': os.path.join(HERE, 'docs', 'block-behavior.md'),
    # repair.py looks for the bend tables in data/ next to itself
    'power-stationing/scripts/data/bend_table_dyn_station.json': os.path.join(HERE, 'data', 'bend_table_dyn_station.json'),
    'power-stationing/scripts/data/bend_table_dyn_station_flipped.json': os.path.join(HERE, 'data', 'bend_table_dyn_station_flipped.json'),
}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'power-stationing.zip')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc, src in FILES.items():
            z.write(src, arc)
    print(out)


if __name__ == '__main__':
    main()

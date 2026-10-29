"""Office survey (OS) helpers: turn Civil 3D survey points into an entity job.

Used with the office-survey skill. Everything here is plain Python 3 (no
packages). Typical flow:

    pts = load_points(r"...\\points_export.txt")     # civil3d_point export (pnezd)
    curb = Lines.from_query(r"C:\\civ3dmcp\\field_curb.json", "CURB")
    job = Job(block_source=r"C:\\...\\symbols.dwg")
    job.polyline(string_vertices(pts, [101, 102, ("poc", 103), 104]), "CURB")
    job.insert("tree1", pts[2001].xy, "LANDSCAPE")
    job.write(r"C:\\civ3dmcp\\jobs\\TD2563411_curb.json")

then run civil3d_entity action apply with jobFile (one approval for the whole
file; the handle map lands beside it as <name>.result.json).
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Iterable

# ------------------------------------------------------------------ points


@dataclass
class Pt:
    n: int
    x: float
    y: float
    z: float
    d: str

    @property
    def xy(self) -> tuple[float, float]:
        return (self.x, self.y)

    @property
    def code(self) -> str:
        return self.d.split()[0] if self.d.strip() else ""

    @property
    def words(self) -> list[str]:
        return self.d.split()


def load_points(path: str) -> dict[int, Pt]:
    """Reads a pnezd text/CSV file, or the saved tool-result of civil3d_point
    export (a JSON list whose second text block holds {"result": {"data": ...}})."""
    raw = open(path, encoding="utf-8-sig").read()
    data = raw
    if raw.lstrip().startswith("["):
        blocks = json.loads(raw)
        for block in blocks:
            text = block.get("text", "") if isinstance(block, dict) else ""
            if '"data"' in text:
                data = json.loads(text)["result"]["data"]
                break
    out: dict[int, Pt] = {}
    for line in data.replace("\r\n", "\n").split("\n"):
        parts = line.split(",", 4)
        if len(parts) < 4 or not parts[0].strip().isdigit():
            continue
        n = int(parts[0])
        out[n] = Pt(n, float(parts[1]), float(parts[2]), float(parts[3] or 0), parts[4].strip() if len(parts) > 4 else "")
    return out


DIST = re.compile(r"^(\d*\.?\d+)(FT)?$", re.I)


def distances(desc: str) -> list[float]:
    """Distances written in a description: 2FT, 2.0, .5FT, 15FT. Size codes like 2X2 are not distances."""
    return [float(m.group(1)) for w in desc.split()[1:] if (m := DIST.match(w))]


def is_lo(p: Pt) -> bool:
    return p.words[-1:] == ["LO"]


def lo_partner(pts: dict[int, Pt], n: int) -> Pt | None:
    """The LO point that gives direction for shot n: n+1 first, then n-2..n+2."""
    for k in (n + 1, n - 1, n + 2, n - 2):
        if k in pts and is_lo(pts[k]):
            return pts[k]
    return None


def offset_point(shot: Pt, lo: Pt, dist: float) -> tuple[float, float]:
    """True point = shot + dist along the unit vector FROM the LO THROUGH the shot."""
    ux, uy = shot.x - lo.x, shot.y - lo.y
    length = math.hypot(ux, uy)
    return (shot.x + dist * ux / length, shot.y + dist * uy / length)


def offsets(pts: dict[int, Pt], n: int) -> list[tuple[float, float]]:
    """All offset points a shot carries (one per distance). Empty if no LO (flag it)."""
    shot = pts[n]
    lo = lo_partner(pts, n)
    if lo is None or is_lo(shot):
        return []
    return [offset_point(shot, lo, d) for d in distances(shot.d)]

# ---------------------------------------------------------------- geometry


def circle3(a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    return ux, uy, math.hypot(ax - ux, ay - uy)


def sweep(a, b, c) -> tuple[float, float]:
    """Signed sweep (radians, + = CCW) of the arc from a through b to c, and its radius."""
    ux, uy, r = circle3(a, b, c)
    A = math.atan2(a[1] - uy, a[0] - ux)
    B = math.atan2(b[1] - uy, b[0] - ux)
    C = math.atan2(c[1] - uy, c[0] - ux)
    tp = 2 * math.pi
    ccw = (C - A) % tp
    return (ccw if (B - A) % tp < ccw else ccw - tp), r


MAX_ARC_RADIUS = 1000.0  # skill rule: a 3-point "arc" flatter than this is drawn as lines and flagged


def string_vertices(pts: dict[int, Pt], seq: Iterable, flags: list[str] | None = None) -> list[dict]:
    """Vertices for a polyline. seq items: point number, (x, y) tuple, or ("poc", n)
    meaning an arc from the previous vertex to the next one through shot n."""
    seq = list(seq)
    xy = lambda t: pts[t].xy if isinstance(t, int) else tuple(t)
    out: list[dict] = []
    for i, t in enumerate(seq):
        if isinstance(t, tuple) and len(t) == 2 and t[0] == "poc":
            a, m, c = xy(seq[i - 1]), xy(t[1]), xy(seq[i + 1])
            sw, r = sweep(a, m, c)
            if r > MAX_ARC_RADIUS:
                if flags is not None:
                    flags.append(f"arc {seq[i-1]}-{t[1]}-{seq[i+1]} R={r:.0f} drawn as lines")
                x, y = m
                out.append({"x": round(x, 4), "y": round(y, 4)})
            else:
                out[-1]["bulge"] = round(math.tan(sw / 4), 6)
            continue
        x, y = xy(t)
        out.append({"x": round(x, 4), "y": round(y, 4)})
    return out


def offset_polyline(vertices: list[dict], dist: float) -> list[dict]:
    """Straight-segment parallel offset (left = +dist). For walls (0.33), mow strips (0.25), paver borders (0.5)."""
    P = [(v["x"], v["y"]) for v in vertices]
    out = []
    for i, p in enumerate(P):
        dirs = []
        if i > 0:
            dirs.append((p[0] - P[i - 1][0], p[1] - P[i - 1][1]))
        if i < len(P) - 1:
            dirs.append((P[i + 1][0] - p[0], P[i + 1][1] - p[1]))
        nx = ny = 0.0
        for dx, dy in dirs:
            L = math.hypot(dx, dy) or 1
            nx += -dy / L
            ny += dx / L
        L = math.hypot(nx, ny) or 1
        scale = dist / max(0.2, (nx / L * (-dirs[0][1]) + ny / L * dirs[0][0]) / (math.hypot(*dirs[0]) or 1))
        out.append({"x": round(p[0] + nx / L * scale, 4), "y": round(p[1] + ny / L * scale, 4)})
    return out

# -------------------------------------------------------------- linework index


def dseg(p, s) -> float:
    x1, y1, x2, y2 = s[:4]
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - x1) * dx + (p[1] - y1) * dy) / L2))
    return math.hypot(p[0] - x1 - t * dx, p[1] - y1 - t * dy)


class Lines:
    """Segments of one layer (from a civil3d_entity query outFile, or vertex lists) with a grid index.
    Bulges are not in query output, so arcs read as chords."""

    def __init__(self, segs: list[tuple], cell: float = 50.0):
        self.segs = segs
        self.cell = cell
        self.grid: dict[tuple[int, int], list[tuple]] = {}
        for s in segs:
            for gx in range(int(min(s[0], s[2]) // cell) - 1, int(max(s[0], s[2]) // cell) + 2):
                for gy in range(int(min(s[1], s[3]) // cell) - 1, int(max(s[1], s[3]) // cell) + 2):
                    self.grid.setdefault((gx, gy), []).append(s)

    @classmethod
    def from_query(cls, path: str, layer: str) -> "Lines":
        ents = json.load(open(path, encoding="utf-8-sig"))["entities"]
        segs = []
        for e in ents:
            if e.get("layer") != layer:
                continue
            if e["type"] == "LWPOLYLINE":
                V = e["vertices"] + ([e["vertices"][0]] if e.get("closed") else [])
                segs += [(a["x"], a["y"], b["x"], b["y"]) for a, b in zip(V, V[1:])]
            elif e["type"] == "LINE":
                segs.append((e["start"]["x"], e["start"]["y"], e["end"]["x"], e["end"]["y"]))
        return cls(segs)

    @classmethod
    def from_vertices(cls, polylines: Iterable[list[dict]]) -> "Lines":
        segs = []
        for V in polylines:
            segs += [(a["x"], a["y"], b["x"], b["y"]) for a, b in zip(V, V[1:])]
        return cls(segs)

    def nearest(self, p):
        cand = self.grid.get((int(p[0] // self.cell), int(p[1] // self.cell)), [])
        if not cand:
            return None, float("inf")
        s = min(cand, key=lambda s: dseg(p, s))
        return s, dseg(p, s)

    def direction_deg(self, p) -> float | None:
        """Direction of the nearest segment, for curb-parallel block rotation."""
        s, _ = self.nearest(p)
        return None if s is None else math.degrees(math.atan2(s[3] - s[1], s[2] - s[0]))

    def foot(self, p):
        s, d = self.nearest(p)
        if s is None:
            return None
        x1, y1, x2, y2 = s[:4]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy or 1
        t = max(0, min(1, ((p[0] - x1) * dx + (p[1] - y1) * dy) / L2))
        return (x1 + t * dx, y1 + t * dy)

    def facing_deg(self, p) -> float | None:
        """Direction from p straight to the nearest line (fire hydrants face the street this way)."""
        q = self.foot(p)
        return None if q is None else math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))

# -------------------------------------------------------------------- jobs


class Job:
    """Collects creates for one civil3d_entity apply job file."""

    def __init__(self, block_source: str | None = None):
        self.block_source = block_source
        self.creates: list[dict] = []
        self.flags: list[str] = []

    def _add(self, item: dict, layer: str, **extra):
        item["layer"] = layer
        item.update({k: v for k, v in extra.items() if v is not None})
        self.creates.append(item)
        return item

    def polyline(self, vertices, layer, closed=False, **extra):
        return self._add({"type": "polyline", "points": vertices, "closed": closed}, layer, **extra)

    def insert(self, block, xy, layer, rotation_deg=0.0, scale=None, dynamic=None, attributes=None, **extra):
        item = {"type": "insert", "blockName": block, "position": {"x": round(xy[0], 4), "y": round(xy[1], 4)},
                "rotationDeg": round(rotation_deg, 4)}
        if scale:
            item["scale"] = scale
        if dynamic:
            item["dynamicProperties"] = dynamic
        if attributes:
            item["attributes"] = attributes
        return self._add(item, layer, **extra)

    def circle(self, xy, radius, layer, **extra):
        return self._add({"type": "circle", "center": {"x": xy[0], "y": xy[1]}, "radius": radius}, layer, **extra)

    def arc(self, xy, radius, start_deg, end_deg, layer, **extra):
        return self._add({"type": "arc", "center": {"x": xy[0], "y": xy[1]}, "radius": radius,
                          "startAngleDeg": start_deg, "endAngleDeg": end_deg}, layer, **extra)

    def text(self, s, xy, height, layer, rotation_deg=0.0, **extra):
        return self._add({"type": "text", "text": s, "position": {"x": xy[0], "y": xy[1]}, "height": height,
                          "rotationDeg": rotation_deg}, layer, **extra)

    def flag(self, xy, note, layer="DISC-OTHER"):
        """Uncertain item: 5 ft circle + short text on the drafters' discrepancy layer."""
        self.flags.append(note)
        self.circle(xy, 5, layer)
        self.text(note, (xy[0] + 5.5, xy[1]), 1.0, layer)

    def write(self, path: str) -> str:
        job = {"version": 1, "creates": self.creates}
        if self.block_source:
            job["blockSource"] = self.block_source
        with open(path, "w", encoding="utf-8") as f:
            json.dump(job, f, indent=1)
        return path

# ------------------------------------------------------------------ scoring


def score(mine: list[list[dict]], drafter_query: str, layer: str, tol: float = 1.5) -> dict:
    """Length both ways: drafter segments not near mine, and mine not near the drafter's
    (segment midpoints, chords for arcs)."""
    theirs = Lines.from_query(drafter_query, layer)
    ours = Lines.from_vertices(mine)

    def unmatched(a: Lines, b: Lines):
        total = miss = 0.0
        for s in a.segs:
            L = math.hypot(s[2] - s[0], s[3] - s[1])
            total += L
            if b.nearest(((s[0] + s[2]) / 2, (s[1] + s[3]) / 2))[1] > tol:
                miss += L
        return total, miss

    t1, m1 = unmatched(theirs, ours)
    t2, m2 = unmatched(ours, theirs)
    return {"drafter_ft": round(t1), "drafter_missed_ft": round(m1), "mine_ft": round(t2), "mine_extra_ft": round(m2)}

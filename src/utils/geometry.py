"""Small geodesy helpers for teach-in area and distance (WGS84)."""

from __future__ import annotations

import math
from typing import Iterable, List, Set, Tuple

Pair = Tuple[float, float]  # (lat_deg, lon_deg)

_EARTH_RADIUS_M = 6_371_000.0


def latlon_to_xy_m(lat_deg: float, lon_deg: float, ref: Pair) -> Tuple[float, float]:
    """Equirectangular meters east/north from ref (same model as polygon_area_m2)."""
    ref_lat, ref_lon = ref
    cos_ref = math.cos(math.radians(ref_lat))
    if cos_ref < 1e-6:
        cos_ref = 1e-6
    x = math.radians(lon_deg - ref_lon) * _EARTH_RADIUS_M * cos_ref
    y = math.radians(lat_deg - ref_lat) * _EARTH_RADIUS_M
    return (x, y)


def xy_m_to_latlon(x_m: float, y_m: float, ref: Pair) -> Pair:
    """Inverse of latlon_to_xy_m."""
    ref_lat, ref_lon = ref
    cos_ref = math.cos(math.radians(ref_lat))
    if cos_ref < 1e-6:
        cos_ref = 1e-6
    lat = ref_lat + math.degrees(y_m / _EARTH_RADIUS_M)
    lon = ref_lon + math.degrees(x_m / (_EARTH_RADIUS_M * cos_ref))
    return (lat, lon)


def haversine_distance_m(a: Pair, b: Pair) -> float:
    """Great-circle distance between two WGS84 points in meters."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def polygon_area_m2(points: Iterable[Pair]) -> float:
    """Planar shoelace area in m² after local equirectangular projection from first point."""
    pts = list(points)
    if len(pts) < 3:
        return 0.0

    ref_lat, ref_lon = pts[0]
    cos_ref = math.cos(math.radians(ref_lat))
    if cos_ref < 1e-6:
        cos_ref = 1e-6

    xy: list[tuple[float, float]] = []
    for lat, lon in pts:
        x = math.radians(lon - ref_lon) * _EARTH_RADIUS_M * cos_ref
        y = math.radians(lat - ref_lat) * _EARTH_RADIUS_M
        xy.append((x, y))

    n = len(xy)
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        s += xy[i][0] * xy[j][1] - xy[j][0] * xy[i][1]
    return abs(s) / 2.0


# ── Segment intersection (for POLY self-intersection guard) ──────


def _cross(ox: float, oy: float, ax: float, ay: float, bx: float, by: float) -> float:
    """2-D cross product of vectors (OA) and (OB)."""
    return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)


def segments_intersect(a1: Pair, a2: Pair, b1: Pair, b2: Pair) -> bool:
    """True if open segments (a1–a2) and (b1–b2) cross each other.

    Shared endpoints or collinear overlap return False so that adjacent
    polygon edges (which share a vertex) are never flagged.
    """
    d1 = _cross(*b1, *b2, *a1)
    d2 = _cross(*b1, *b2, *a2)
    d3 = _cross(*a1, *a2, *b1)
    d4 = _cross(*a1, *a2, *b2)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    return False


def polygon_has_self_intersection(points: List[Pair]) -> bool:
    """True if any non-adjacent edges of the closed polygon cross.

    Edges are (p0–p1), (p1–p2), … (pN-1–p0).  O(n²) — fine for
    boundary sizes encountered in mowing teach-in.
    """
    n = len(points)
    if n < 4:
        return False

    edges: List[Tuple[Pair, Pair]] = []
    for i in range(n):
        edges.append((points[i], points[(i + 1) % n]))

    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # first and last edge share vertex p0
            if segments_intersect(edges[i][0], edges[i][1],
                                  edges[j][0], edges[j][1]):
                return True
    return False


def new_edge_intersects_existing(points: List[Pair]) -> bool:
    """Check only the latest edge against all non-adjacent earlier edges.

    Call after appending the new point.  O(n) per call.
    Returns True if the newest edge (points[-2]–points[-1]) crosses
    any earlier edge.
    """
    n = len(points)
    if n < 4:
        return False
    new_a = points[-2]
    new_b = points[-1]
    for i in range(n - 3):
        if segments_intersect(points[i], points[i + 1], new_a, new_b):
            return True
    return False


def dedupe_by_min_distance(points: List[Pair], min_dist_m: float) -> List[int]:
    """Return kept indices after distance-based decimation.

    Keeps first and last points when input is non-empty.
    """
    n = len(points)
    if n == 0:
        return []
    if n == 1:
        return [0]
    if min_dist_m <= 0:
        return list(range(n))

    kept: List[int] = [0]
    last_kept = 0
    for i in range(1, n - 1):
        if haversine_distance_m(points[last_kept], points[i]) >= min_dist_m:
            kept.append(i)
            last_kept = i
    if kept[-1] != n - 1:
        kept.append(n - 1)
    return kept


def corner_indices(points: List[Pair], threshold_deg: float) -> Set[int]:
    """Return interior indices where turn angle exceeds threshold."""
    n = len(points)
    if n < 3 or threshold_deg <= 0:
        return set()

    ref = points[0]
    out: Set[int] = set()
    for i in range(1, n - 1):
        x0, y0 = latlon_to_xy_m(points[i - 1][0], points[i - 1][1], ref)
        x1, y1 = latlon_to_xy_m(points[i][0], points[i][1], ref)
        x2, y2 = latlon_to_xy_m(points[i + 1][0], points[i + 1][1], ref)
        ax, ay = x0 - x1, y0 - y1
        bx, by = x2 - x1, y2 - y1
        ma = math.hypot(ax, ay)
        mb = math.hypot(bx, by)
        if ma < 1e-6 or mb < 1e-6:
            continue
        cos_val = max(-1.0, min(1.0, (ax * bx + ay * by) / (ma * mb)))
        angle = math.degrees(math.acos(cos_val))
        turn = abs(180.0 - angle)
        if turn >= threshold_deg:
            out.add(i)
    return out


def rdp_keep_indices(points: List[Pair], epsilon_m: float) -> Set[int]:
    """Return point indices selected by RDP in local XY meter space."""
    n = len(points)
    if n == 0:
        return set()
    if n <= 2 or epsilon_m <= 0:
        return set(range(n))

    ref = points[0]
    xy = [latlon_to_xy_m(lat, lon, ref) for lat, lon in points]

    keep: Set[int] = {0, n - 1}

    def _point_line_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        vv = vx * vx + vy * vy
        if vv < 1e-12:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / vv))
        cx, cy = ax + t * vx, ay + t * vy
        return math.hypot(px - cx, py - cy)

    def _rdp(lo: int, hi: int) -> None:
        if hi <= lo + 1:
            return
        ax, ay = xy[lo]
        bx, by = xy[hi]
        max_d = -1.0
        idx = -1
        for i in range(lo + 1, hi):
            px, py = xy[i]
            d = _point_line_distance(px, py, ax, ay, bx, by)
            if d > max_d:
                max_d = d
                idx = i
        if max_d > epsilon_m and idx > lo:
            keep.add(idx)
            _rdp(lo, idx)
            _rdp(idx, hi)

    _rdp(0, n - 1)
    return keep

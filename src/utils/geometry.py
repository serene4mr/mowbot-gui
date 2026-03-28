"""Small geodesy helpers for teach-in area and distance (WGS84)."""

from __future__ import annotations

import math
from typing import Iterable, List, Tuple

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

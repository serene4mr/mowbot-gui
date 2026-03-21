"""Small geodesy helpers for teach-in area and distance (WGS84)."""

from __future__ import annotations

import math
from typing import Iterable, Tuple

Pair = Tuple[float, float]  # (lat_deg, lon_deg)

_EARTH_RADIUS_M = 6_371_000.0


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

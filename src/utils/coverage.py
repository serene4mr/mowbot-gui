"""Boustrophedon coverage paths for POLY missions."""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.validation import make_valid

from utils.geometry import haversine_distance_m, latlon_to_xy_m, xy_m_to_latlon

Pair = Tuple[float, float]

_MIN_STEP_M = 0.05
_DEDUPE_M = 0.05
_MIN_COORD_EPS_M2 = 1e-8


def _dedupe_ring_latlon(ring: Sequence[Pair], min_m: float = _DEDUPE_M) -> List[Pair]:
    if len(ring) < 2:
        return list(ring)
    out: List[Pair] = [ring[0]]
    for p in ring[1:]:
        if haversine_distance_m(out[-1], p) >= min_m:
            out.append(p)
    while (
        len(out) >= 2
        and haversine_distance_m(out[-1], out[0]) < min_m
    ):
        out.pop()
    return out


def _dedupe_xy_path(path: List[Tuple[float, float]], eps_m: float = 0.02) -> List[Tuple[float, float]]:
    if not path:
        return path
    eps2 = eps_m * eps_m
    out: List[Tuple[float, float]] = [path[0]]
    for x, y in path[1:]:
        ox, oy = out[-1]
        if (x - ox) ** 2 + (y - oy) ** 2 >= eps2:
            out.append((x, y))
    return out


def _linestring_parts(geom) -> List[LineString]:
    if geom is None or geom.is_empty:
        return []
    gt = geom.geom_type
    if gt == "LineString":
        return [geom]
    if gt == "MultiLineString":
        return [ls for ls in geom.geoms]
    if gt == "GeometryCollection":
        parts: List[LineString] = []
        for g in geom.geoms:
            parts.extend(_linestring_parts(g))
        return parts
    return []


def _longest_edge_angle_rad(poly: Polygon) -> float:
    coords = list(poly.exterior.coords)
    pts = coords[:-1] if len(coords) > 1 and coords[0] == coords[-1] else coords
    n = len(pts)
    if n < 2:
        return 0.0
    best_len = 0.0
    best_ang = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        l = math.hypot(dx, dy)
        if l > best_len:
            best_len = l
            best_ang = math.atan2(dy, dx)
    return best_ang


def _fix_polygon(poly: Polygon) -> Optional[Polygon]:
    if poly.is_empty:
        return None
    if poly.geom_type != "Polygon":
        return None
    if poly.is_valid:
        return poly
    fixed = make_valid(poly)
    if fixed.geom_type == "Polygon":
        return fixed
    if fixed.geom_type == "MultiPolygon":
        return max(fixed.geoms, key=lambda p: p.area)
    return None


def compute_coverage_path(
    polygon: List[Pair],
    robot_position: Optional[Pair] = None,
    *,
    mow_width_m: float = 0.5,
    overlap_pct: float = 10.0,
    sweep_angle_deg: Optional[float] = None,
    max_waypoints: int = 2000,
) -> Tuple[List[Pair], Optional[str]]:
    """Plan a boustrophedon path inside polygon (lat/lon), in visiting order.

    Sweeps are horizontal in a locally rotated frame where the longest polygon
    edge is parallel to +X (unless ``sweep_angle_deg`` is set).

    Returns ``(waypoints, error_message)`` with ``error_message`` set on failure.
    """
    if mow_width_m <= 0:
        return [], "mow_width_m must be positive."
    try:
        max_w = int(max_waypoints)
    except (TypeError, ValueError):
        max_w = 2000
    if max_w < 2:
        return [], "max_waypoints must be at least 2."

    ring = _dedupe_ring_latlon(polygon)
    if len(ring) < 3:
        return [], "POLY needs at least 3 vertices after deduplication."

    ref_latlon = ring[0]
    xy_ring = [latlon_to_xy_m(lat, lon, ref_latlon) for lat, lon in ring]
    raw = Polygon(xy_ring)
    poly = _fix_polygon(raw)
    if poly is None or poly.area < 1e-4:
        return [], "Invalid or degenerate polygon (unable to build coverage)."

    if sweep_angle_deg is not None:
        angle_rad = math.radians(float(sweep_angle_deg))
    else:
        angle_rad = _longest_edge_angle_rad(poly)

    rot_deg = -math.degrees(angle_rad)
    origin = (float(poly.centroid.x), float(poly.centroid.y))
    poly_r = affinity.rotate(poly, rot_deg, origin=origin)

    min_x, min_y, max_x, max_y = poly_r.bounds
    span = max(max_x - min_x, max_y - min_y, mow_width_m)
    margin = span + 5.0
    step = max(_MIN_STEP_M, float(mow_width_m) * (1.0 - max(0.0, min(100.0, overlap_pct)) / 100.0))

    path_rot: List[Tuple[float, float]] = []
    row = 0
    y = min_y + step / 2.0
    while y <= max_y + 1e-9:
        cut = LineString([(min_x - margin, y), (max_x + margin, y)])
        inter = poly_r.intersection(cut)
        parts = _linestring_parts(inter)
        parts.sort(key=lambda ls: min(c[0] for c in ls.coords))

        for ls in parts:
            coords = [tuple(map(float, t[:2])) for t in ls.coords]
            if len(coords) < 2:
                continue
            if row % 2 == 0:
                if coords[0][0] > coords[-1][0]:
                    coords = coords[::-1]
            else:
                if coords[0][0] < coords[-1][0]:
                    coords = coords[::-1]
            if path_rot:
                fx, fy = coords[0]
                lx, ly = path_rot[-1]
                if (fx - lx) ** 2 + (fy - ly) ** 2 > _MIN_COORD_EPS_M2:
                    path_rot.append((fx, fy))
            for c in coords:
                if (
                    not path_rot
                    or (c[0] - path_rot[-1][0]) ** 2 + (c[1] - path_rot[-1][1]) ** 2
                    > _MIN_COORD_EPS_M2
                ):
                    path_rot.append(c)
        row += 1
        y += step

    path_rot = _dedupe_xy_path(path_rot, eps_m=0.02)
    if not path_rot:
        return [], "No sweep lines intersect the polygon (area too narrow for mow width?)."

    path_xy: List[Tuple[float, float]] = []
    inv_deg = math.degrees(angle_rad)
    for x, y in path_rot:
        pr = affinity.rotate(Point(x, y), inv_deg, origin=origin)
        path_xy.append((float(pr.x), float(pr.y)))

    out_ll: List[Pair] = [
        xy_m_to_latlon(px, py, ref_latlon) for px, py in path_xy
    ]
    out_ll = [
        p
        for i, p in enumerate(out_ll)
        if i == 0
        or haversine_distance_m(out_ll[i - 1], p) >= 0.01
    ]

    if robot_position is not None:
        d0 = haversine_distance_m(robot_position, out_ll[0])
        d1 = haversine_distance_m(robot_position, out_ll[-1])
        if d1 + 1e-6 < d0:
            out_ll.reverse()

    if len(out_ll) > max_w:
        return (
            [],
            f"Coverage path has {len(out_ll)} waypoints (limit {max_w}). "
            "Increase mow width or max_waypoints in config.",
        )
    return out_ll, None

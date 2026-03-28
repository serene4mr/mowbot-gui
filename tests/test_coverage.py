"""Tests for POLY coverage path planning."""

from __future__ import annotations

import math

from utils.coverage import compute_coverage_path

_EARTH = 111_320.0  # m per degree latitude (approx)


def _square(lat0: float, lon0: float, size_m: float) -> list[tuple[float, float]]:
    d_lat = size_m / _EARTH
    d_lon = size_m / (_EARTH * math.cos(math.radians(lat0)))
    return [
        (lat0, lon0),
        (lat0 + d_lat, lon0),
        (lat0 + d_lat, lon0 + d_lon),
        (lat0, lon0 + d_lon),
    ]


def test_coverage_square_returns_path() -> None:
    sq = _square(38.1610, -122.4540, 14.0)
    path, err = compute_coverage_path(
        sq,
        robot_position=sq[0],
        mow_width_m=3.0,
        overlap_pct=0.0,
        max_waypoints=5000,
    )
    assert err is None
    assert len(path) >= 4


def test_coverage_robot_prefers_closer_endpoint() -> None:
    sq = _square(40.0, -74.0, 20.0)
    path_far, err = compute_coverage_path(
        sq,
        robot_position=sq[2],
        mow_width_m=4.0,
        overlap_pct=10.0,
        max_waypoints=5000,
    )
    assert err is None
    assert len(path_far) >= 2
    from utils.geometry import haversine_distance_m

    d0 = haversine_distance_m(sq[2], path_far[0])
    d1 = haversine_distance_m(sq[2], path_far[-1])
    assert d0 <= d1 + 0.5


def test_coverage_rejects_invalid_param() -> None:
    sq = _square(38.0, -122.0, 10.0)
    _, err = compute_coverage_path(sq, mow_width_m=-1.0)
    assert err is not None

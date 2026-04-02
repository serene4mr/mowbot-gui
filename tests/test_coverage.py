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


# ── Smooth turn (min_turn_radius_m) tests ──────────────────────


def test_smooth_turn_produces_arc_points() -> None:
    """With min_turn_radius_m > 0 the path should have *more* waypoints
    than the sharp-turn version for the same polygon, because arc points
    are inserted at every stripe transition."""
    sq = _square(38.1610, -122.4540, 14.0)

    path_sharp, err_sharp = compute_coverage_path(
        sq,
        mow_width_m=3.0,
        overlap_pct=0.0,
        max_waypoints=5000,
        min_turn_radius_m=0.0,
    )
    assert err_sharp is None

    path_smooth, err_smooth = compute_coverage_path(
        sq,
        mow_width_m=3.0,
        overlap_pct=0.0,
        max_waypoints=5000,
        min_turn_radius_m=0.5,
    )
    assert err_smooth is None
    assert len(path_smooth) > len(path_sharp), (
        f"Expected smooth path to have more waypoints than sharp path, "
        f"got {len(path_smooth)} vs {len(path_sharp)}"
    )


def test_smooth_turn_no_sharp_angles() -> None:
    """No consecutive segment pair in the smooth-turn path should form an
    angle sharper than expected for the configured radius.

    For a semicircular arc with 8 segments the minimum interior angle at
    each arc vertex is ~157.5°.  We use a generous threshold of 30° (i.e.
    no angle < 30°) to avoid false positives from polygon-clipping jitter.
    """
    from utils.geometry import latlon_to_xy_m

    sq = _square(38.0, -122.0, 20.0)
    path, err = compute_coverage_path(
        sq,
        mow_width_m=4.0,
        overlap_pct=0.0,
        max_waypoints=5000,
        min_turn_radius_m=1.0,
    )
    assert err is None
    assert len(path) >= 4

    # Convert to local XY for angle computation
    ref = path[0]
    xy = [latlon_to_xy_m(lat, lon, ref) for lat, lon in path]

    min_angle_deg = 180.0
    for i in range(1, len(xy) - 1):
        ax, ay = xy[i - 1][0] - xy[i][0], xy[i - 1][1] - xy[i][1]
        bx, by = xy[i + 1][0] - xy[i][0], xy[i + 1][1] - xy[i][1]
        dot = ax * bx + ay * by
        mag_a = math.hypot(ax, ay)
        mag_b = math.hypot(bx, by)
        if mag_a < 1e-6 or mag_b < 1e-6:
            continue
        cos_val = max(-1.0, min(1.0, dot / (mag_a * mag_b)))
        angle = math.degrees(math.acos(cos_val))
        if angle < min_angle_deg:
            min_angle_deg = angle

    assert min_angle_deg >= 30.0, (
        f"Found angle {min_angle_deg:.1f}° which is sharper than the 30° threshold"
    )


def test_zero_radius_matches_legacy() -> None:
    """min_turn_radius_m=0 must produce exactly the same path as the
    default (no parameter), confirming backward compatibility."""
    sq = _square(38.1610, -122.4540, 14.0)

    path_default, err1 = compute_coverage_path(
        sq,
        robot_position=sq[0],
        mow_width_m=3.0,
        overlap_pct=0.0,
        max_waypoints=5000,
    )
    assert err1 is None

    path_zero, err2 = compute_coverage_path(
        sq,
        robot_position=sq[0],
        mow_width_m=3.0,
        overlap_pct=0.0,
        max_waypoints=5000,
        min_turn_radius_m=0.0,
    )
    assert err2 is None
    assert path_default == path_zero


def test_zero_stripe_spacing_matches_legacy() -> None:
    """stripe_point_spacing_m=0 must match the default output exactly."""
    sq = _square(38.1610, -122.4540, 14.0)

    path_default, err1 = compute_coverage_path(
        sq,
        robot_position=sq[0],
        mow_width_m=3.0,
        overlap_pct=0.0,
        max_waypoints=5000,
    )
    assert err1 is None

    path_zero_spacing, err2 = compute_coverage_path(
        sq,
        robot_position=sq[0],
        mow_width_m=3.0,
        overlap_pct=0.0,
        max_waypoints=5000,
        stripe_point_spacing_m=0.0,
    )
    assert err2 is None
    assert path_default == path_zero_spacing


def test_stripe_spacing_adds_interior_points_and_limits_gap() -> None:
    """Spacing>0 should add interior stripe points and cap point-to-point gap."""
    from utils.geometry import haversine_distance_m

    sq = _square(38.0, -122.0, 20.0)
    spacing_m = 1.0

    sparse_path, err_sparse = compute_coverage_path(
        sq,
        mow_width_m=4.0,
        overlap_pct=0.0,
        max_waypoints=10000,
        stripe_point_spacing_m=0.0,
    )
    assert err_sparse is None

    dense_path, err_dense = compute_coverage_path(
        sq,
        mow_width_m=4.0,
        overlap_pct=0.0,
        max_waypoints=10000,
        stripe_point_spacing_m=spacing_m,
    )
    assert err_dense is None
    assert len(dense_path) > len(sparse_path)

    max_gap = 0.0
    for i in range(1, len(dense_path)):
        gap = haversine_distance_m(dense_path[i - 1], dense_path[i])
        if gap > max_gap:
            max_gap = gap

    # Allow a modest tolerance because transitions between stripes may exceed
    # exact spacing and lat/lon projection introduces small numeric jitter.
    assert max_gap <= 1.6, f"Expected max gap <= 1.6m, got {max_gap:.2f}m"


def test_stripe_spacing_works_with_smooth_turns() -> None:
    """Densified stripes and smooth U-turn arcs should combine correctly."""
    sq = _square(38.0, -122.0, 20.0)

    path_arc_only, err_arc_only = compute_coverage_path(
        sq,
        mow_width_m=4.0,
        overlap_pct=0.0,
        max_waypoints=10000,
        min_turn_radius_m=1.0,
        stripe_point_spacing_m=0.0,
    )
    assert err_arc_only is None

    path_arc_dense, err_arc_dense = compute_coverage_path(
        sq,
        mow_width_m=4.0,
        overlap_pct=0.0,
        max_waypoints=10000,
        min_turn_radius_m=1.0,
        stripe_point_spacing_m=1.0,
    )
    assert err_arc_dense is None
    assert len(path_arc_dense) > len(path_arc_only)


def test_bulb_turn_when_step_less_than_diameter() -> None:
    """When stripe spacing < 2 × radius the arc becomes a bulb turn that
    may extend outside the polygon.  The path should still be valid and
    contain arc points."""
    sq = _square(38.0, -122.0, 20.0)
    # mow_width_m=2.0 → step ≈ 2.0 m, radius=2.0 → diameter=4.0 > step
    path, err = compute_coverage_path(
        sq,
        mow_width_m=2.0,
        overlap_pct=0.0,
        max_waypoints=10000,
        min_turn_radius_m=2.0,
    )
    assert err is None
    assert len(path) >= 6, f"Expected at least 6 waypoints, got {len(path)}"

    # Also check it has more points than the sharp version
    path_sharp, err_s = compute_coverage_path(
        sq,
        mow_width_m=2.0,
        overlap_pct=0.0,
        max_waypoints=10000,
        min_turn_radius_m=0.0,
    )
    assert err_s is None
    assert len(path) > len(path_sharp)

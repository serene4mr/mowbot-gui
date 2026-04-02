"""Tests for POLY waypoint tangent orientation assignment."""

from __future__ import annotations

import math

from ui.main_window import _with_tangent_theta


def test_two_point_path_reuses_heading_for_last_waypoint() -> None:
    path = [(38.0, -122.0), (38.0, -121.9999)]  # east
    out = _with_tangent_theta(path)
    assert len(out) == 2
    assert math.isclose(out[0][2], 0.0, abs_tol=0.05)
    assert math.isclose(out[1][2], out[0][2], abs_tol=1e-9)


def test_turning_path_gets_nontrivial_heading() -> None:
    # East then north: first heading ~0, second/last ~pi/2.
    path = [
        (38.0, -122.0),
        (38.0, -121.9999),
        (38.0001, -121.9999),
    ]
    out = _with_tangent_theta(path)
    assert len(out) == 3
    assert math.isclose(out[0][2], 0.0, abs_tol=0.05)
    assert math.isclose(out[1][2], math.pi / 2.0, abs_tol=0.05)
    assert math.isclose(out[2][2], out[1][2], abs_tol=1e-9)


def test_repeated_points_do_not_break_heading() -> None:
    path = [
        (38.0, -122.0),
        (38.0, -122.0),  # duplicate waypoint
        (38.0, -121.9999),
    ]
    out = _with_tangent_theta(path)
    assert len(out) == 3
    for _, _, theta in out:
        assert math.isfinite(theta)
    assert math.isclose(out[0][2], 0.0, abs_tol=0.05)
    assert math.isclose(out[1][2], 0.0, abs_tol=0.05)
    assert math.isclose(out[2][2], 0.0, abs_tol=0.05)

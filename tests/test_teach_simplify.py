"""Tests for teach-in save-time waypoint simplification."""

from __future__ import annotations

import json

from core.app_state import AppState
from utils.geometry import corner_indices, dedupe_by_min_distance, rdp_keep_indices


def _line_points(lat0: float, lon0: float, count: int, step_lon: float) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for i in range(count):
        out.append((lat0, lon0 + (step_lon * i), 0.0))
    return out


def test_geometry_reducers_keep_endpoints_and_corners() -> None:
    pts = [
        (38.0, -122.0),
        (38.0, -121.99999),
        (38.0, -121.99998),
        (38.00005, -121.99998),  # turn north
        (38.00010, -121.99998),
    ]
    dist_kept = dedupe_by_min_distance(pts, min_dist_m=1.0)
    assert dist_kept[0] == 0
    assert dist_kept[-1] == len(pts) - 1

    corners = corner_indices(pts, threshold_deg=10.0)
    assert 3 in corners

    rdp = rdp_keep_indices(pts, epsilon_m=0.2)
    assert 0 in rdp
    assert len(pts) - 1 in rdp


def test_teach_save_path_postprocess_reduces_redundant_points(tmp_path) -> None:
    state = AppState(
        post_process_enable=True,
        post_process_min_dist_m=1.0,
        post_process_corner_threshold_deg=12.0,
        post_process_rdp_epsilon_path_m=0.5,
        post_process_rdp_epsilon_poly_m=0.3,
    )
    state.tch_set_mode("PATH")
    raw = _line_points(38.0, -122.0, count=20, step_lon=0.000001)
    state._tch_points = list(raw)

    filename, err = state.teach_save_to_disk(str(tmp_path))
    assert err == ""
    assert filename is not None

    with open(tmp_path / filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["type"] == "PATH"
    assert isinstance(data["coordinates"], list)
    assert data["count"] == len(data["coordinates"])
    assert data["count"] < len(raw)
    assert data["count"] >= 2


def test_teach_save_poly_never_reduced_below_minimum(tmp_path) -> None:
    state = AppState(
        post_process_enable=True,
        post_process_min_dist_m=10.0,
        post_process_corner_threshold_deg=45.0,
        post_process_rdp_epsilon_path_m=5.0,
        post_process_rdp_epsilon_poly_m=5.0,
    )
    state.tch_set_mode("POLY")
    state._tch_points = [
        (38.0, -122.0, 0.0),
        (38.0, -121.99995, 0.0),
        (38.00005, -121.99995, 0.0),
        (38.00005, -122.0, 0.0),
    ]

    filename, err = state.teach_save_to_disk(str(tmp_path))
    assert err == ""
    assert filename is not None

    with open(tmp_path / filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["type"] == "POLY"
    assert data["count"] >= 3
    assert data["count"] == len(data["coordinates"])

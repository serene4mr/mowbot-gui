"""Observable application state container.

Centralizes all live telemetry / system state and exposes Qt signals
so any component can subscribe to changes independently, without routing
everything through MainWindow.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from utils.geometry import (
    haversine_distance_m,
    new_edge_intersects_existing,
    polygon_area_m2,
    polygon_has_self_intersection,
)
from utils.logger import logger


class AppState(QObject):
    """Single source of truth for runtime state.

    Controllers write into the state via setter methods.
    UI components connect to the signals for reactive updates.
    """

    mqtt_changed = Signal(bool)
    battery_changed = Signal(float)
    position_changed = Signal(float, float, float, float)  # x, y, theta_rad, speed
    mode_changed = Signal(str)
    sensor_diag_changed = Signal(str)
    error_changed = Signal(str)
    robot_id_changed = Signal(str)
    status_line_changed = Signal(str)  # composed "IMU: OK | BAT: 85% | MQTT: OK"

    # Teach-in (TCH): (lat, lon), count, area_m² (-1 if N/A)
    tch_point_added = Signal(float, float, int)
    tch_point_undone = Signal(int)
    tch_cleared = Signal()
    tch_mode_changed = Signal(str)
    tch_auto_record_changed = Signal(bool)
    tch_stats_changed = Signal(int, float)  # waypoint_count, area_m2 or -1
    tch_error = Signal(str)
    tch_session_saved = Signal(str)  # filename only (path_* / poly_* + datetime + .json)

    # VDA order publish result (PATH execute, etc.)
    order_dispatched = Signal(bool, str, int)  # success, order_id or error detail, total_nodes

    # Mission execution progress (from VDA5050 State on the tracked order)
    mission_progress_changed = Signal(
        str, str, int, int, int
    )  # status, order_id, completed, total, last_node_index_for_map (-1 = no highlight)

    # Docker container lifecycle (managed by DockerController)
    docker_status_changed = Signal(str, str)  # key, status e.g. "running", "missing"
    docker_error = Signal(str, str)  # key, message

    # Docker startup/shutdown sequence progress
    docker_sequence_step = Signal(int, str, str)  # step_index, key, phase
    docker_sequence_finished = Signal(bool, str)  # success, detail message

    def __init__(
        self,
        parent: Optional[QObject] = None,
        *,
        poly_max_close_gap_m: float = 5.0,
        poly_min_area_m2: float = 0.0,
        poly_reject_self_intersection: bool = True,
    ):
        super().__init__(parent)
        self._mqtt_ok: bool = False
        self._battery_pct: Optional[float] = None
        self._sensor_diag: str = "--"
        self._operating_mode: Optional[str] = None
        self._last_error: Optional[str] = None

        # Last robot fix: x=lon, y=lat (matches VDA / map_view convention)
        self._last_lon: float = 0.0
        self._last_lat: float = 0.0
        self._last_theta_rad: float = 0.0
        self._has_position: bool = False

        # Teach-in session (lat, lon, theta_rad from last telemetry when logged)
        self._tch_mode: str = "PATH"
        self._tch_points: List[Tuple[float, float, float]] = []
        self._tch_auto_record: bool = False
        # POLY save: reject if first/last points farther than this (meters); <=0 disables
        try:
            self._poly_max_close_gap_m = float(poly_max_close_gap_m)
        except (TypeError, ValueError):
            self._poly_max_close_gap_m = 5.0
        try:
            self._poly_min_area_m2 = float(poly_min_area_m2)
        except (TypeError, ValueError):
            self._poly_min_area_m2 = 0.0
        self._poly_reject_self_intersection = bool(poly_reject_self_intersection)

        # PATH execute: track one active order until completed or cleared
        self._active_order_id: str = ""
        self._total_nodes: int = 0
        self._order_acknowledged: bool = False
        self._order_seq_valid: bool = False
        self._saw_driving: bool = False
        self._last_completed_nodes: int = 0

    # ── Read-only properties ──────────────────────────────────

    @property
    def mqtt_ok(self) -> bool:
        return self._mqtt_ok

    @property
    def battery_pct(self) -> Optional[float]:
        return self._battery_pct

    @property
    def sensor_diag(self) -> str:
        return self._sensor_diag

    @property
    def operating_mode(self) -> Optional[str]:
        return self._operating_mode

    @property
    def tch_mode(self) -> str:
        return self._tch_mode

    @property
    def tch_points(self) -> List[Tuple[float, float, float]]:
        return list(self._tch_points)

    @property
    def tch_auto_record(self) -> bool:
        return self._tch_auto_record

    @property
    def active_order_id(self) -> str:
        return self._active_order_id

    @property
    def has_position_fix(self) -> bool:
        return self._has_position

    def get_robot_latlon(self) -> Optional[Tuple[float, float]]:
        """Current fix as (lat, lon) when available; ``x``/``y`` telemetry is lon/lat."""
        if not self._has_position:
            return None
        return (self._last_lat, self._last_lon)

    # ── Mutators (emit signals only on actual change) ─────────

    def set_mqtt(self, connected: bool) -> None:
        if connected != self._mqtt_ok:
            self._mqtt_ok = connected
            self.mqtt_changed.emit(connected)
            self._refresh_status_line()

    def set_battery(self, pct: float) -> None:
        self._battery_pct = pct
        self.battery_changed.emit(pct)
        self._refresh_status_line()

    def set_position(
        self, x: float, y: float, theta_rad: float, speed_mps: float
    ) -> None:
        # Cache for teach-in logging (x = longitude, y = latitude)
        self._last_lon = float(x)
        self._last_lat = float(y)
        self._last_theta_rad = float(theta_rad)
        self._has_position = True
        self.position_changed.emit(x, y, theta_rad, speed_mps)

    def set_mode(self, mode: str) -> None:
        if mode != self._operating_mode:
            self._operating_mode = mode
            self.mode_changed.emit(mode)

    def set_sensor_diag(self, raw: str) -> None:
        formatted = self._format_sensor_diag(raw)
        if formatted != self._sensor_diag:
            self._sensor_diag = formatted
            self.sensor_diag_changed.emit(formatted)
            self._refresh_status_line()

    def set_error(self, msg: str) -> None:
        if msg != self._last_error:
            self._last_error = msg
            self.error_changed.emit(msg)

    def set_robot_id(self, robot_id: str) -> None:
        self.robot_id_changed.emit(robot_id)

    # ── VDA mission progress (PATH execute) ───────────────────

    def set_active_order(self, order_id: str, total_nodes: int) -> None:
        """Call after a PATH order is successfully dispatched."""
        self._clear_tracked_order()
        self._active_order_id = (order_id or "").strip()
        try:
            self._total_nodes = max(0, int(total_nodes))
        except (TypeError, ValueError):
            self._total_nodes = 0
        if self._active_order_id and self._total_nodes > 0:
            self.mission_progress_changed.emit(
                "executing", self._active_order_id, 0, self._total_nodes, -1
            )

    def _clear_tracked_order(self) -> None:
        self._active_order_id = ""
        self._total_nodes = 0
        self._order_acknowledged = False
        self._order_seq_valid = False
        self._saw_driving = False
        self._last_completed_nodes = 0

    def _emit_mission_completed_and_clear(self) -> None:
        oid = self._active_order_id
        total = self._total_nodes
        if not oid or total <= 0:
            return
        last_idx = max(0, total - 1)
        self._clear_tracked_order()
        self.mission_progress_changed.emit("completed", oid, total, total, last_idx)

    def set_mission_progress(
        self,
        state_order_id: str,
        _order_update_id: int,
        _last_node_id: str,
        last_node_seq: int,
        nodes_remaining: int,
        driving: bool,
    ) -> None:
        """Update from VDA5050 State; only affects UI when an order is tracked."""
        if self._active_order_id:
            logger.info(
                f"[MissionProgress] oid={state_order_id!r} seq={last_node_seq} "
                f"nodeStates={nodes_remaining} driving={driving} "
                f"acked={self._order_acknowledged} seqValid={self._order_seq_valid} drove={self._saw_driving} "
                f"tracked={self._active_order_id!r} total={self._total_nodes}"
            )
        if not self._active_order_id:
            return
        total = self._total_nodes
        if total <= 0:
            return

        oid = (state_order_id or "").strip()
        if oid and oid != self._active_order_id:
            return

        if oid and oid == self._active_order_id:
            self._order_acknowledged = True
            if driving:
                self._saw_driving = True

            # Wait until the robot resets to sequenceId 0 (start of our order)
            # before trusting lastNodeSequenceId; stale values from a prior
            # mission can be arbitrarily high and would show false progress.
            if not self._order_seq_valid:
                if last_node_seq == 0:
                    self._order_seq_valid = True
                else:
                    self.mission_progress_changed.emit(
                        "executing", oid, 0, total, -1,
                    )
                    return

            last_idx = max(0, min(total - 1, last_node_seq // 2))
            completed = last_idx + 1
            self._last_completed_nodes = completed
            if self._saw_driving and last_idx >= total - 1 and not driving:
                self._emit_mission_completed_and_clear()
                return
            map_idx = last_idx if (driving or last_idx > 0) else -1
            self.mission_progress_changed.emit(
                "executing", oid, completed, total, map_idx,
            )
            return

        # Robot cleared orderId after finishing — only trust this as genuine
        # completion when the robot actually reached the last node.  A brief
        # drive followed by an empty orderId (e.g. order re-queued or
        # rejected) must not be mistaken for a completed mission.
        if not oid and not driving and self._saw_driving:
            if self._last_completed_nodes >= self._total_nodes:
                self._emit_mission_completed_and_clear()

    def set_mission_failed(self, reason: str) -> None:
        """Latch active mission as failed; clear tracking after emitting UI state."""
        oid = self._active_order_id
        total = self._total_nodes
        if not oid or total <= 0:
            return
        completed = max(0, min(total, self._last_completed_nodes))
        last_idx = max(0, min(total - 1, completed))
        self._clear_tracked_order()
        self.mission_progress_changed.emit("failed", oid, completed, total, last_idx)
        self.set_error(f"FATAL: {reason}")

    def reset_mission_progress_ui(self) -> None:
        """Clear sidebar/map mission progress (e.g. new preview without execute)."""
        self._clear_tracked_order()
        self.mission_progress_changed.emit("idle", "", 0, 0, -1)

    # ── Teach-in ──────────────────────────────────────────────

    def tch_set_mode(self, mode: str) -> None:
        m = (mode or "PATH").upper()
        if m not in ("PATH", "POLY"):
            return
        if m != self._tch_mode:
            self._tch_mode = m
            self.tch_mode_changed.emit(m)
            self._emit_tch_stats()

    def tch_toggle_auto_record(self) -> None:
        self.tch_set_auto_record(not self._tch_auto_record)

    def tch_set_auto_record(self, on: bool) -> None:
        if on != self._tch_auto_record:
            self._tch_auto_record = on
            self.tch_auto_record_changed.emit(on)

    def tch_log_point(self) -> bool:
        if not self._has_position:
            self.tch_error.emit("No position yet. Wait for GPS / localization.")
            return False
        lat, lon = self._last_lat, self._last_lon
        self._tch_points.append((lat, lon, self._last_theta_rad))
        n = len(self._tch_points)
        if (
            self._poly_reject_self_intersection
            and self._tch_mode == "POLY"
            and n >= 4
        ):
            pts_2d = [(p[0], p[1]) for p in self._tch_points]
            if new_edge_intersects_existing(pts_2d):
                self.tch_error.emit(
                    "Edge crosses an earlier segment \u2014 consider Undo."
                )
        self.tch_point_added.emit(lat, lon, n)
        self._emit_tch_stats()
        return True

    def tch_undo(self) -> None:
        if not self._tch_points:
            return
        self._tch_points.pop()
        self.tch_point_undone.emit(len(self._tch_points))
        self._emit_tch_stats()

    def tch_clear_session(self) -> None:
        if not self._tch_points:
            self._emit_tch_stats()
            return
        self._tch_points.clear()
        self.tch_cleared.emit()
        self._emit_tch_stats()

    def validate_teach_save(self) -> Optional[str]:
        """Return error message if save is not allowed, else None."""
        if self._tch_mode == "PATH" and len(self._tch_points) < 2:
            return "PATH requires at least 2 waypoints."
        if self._tch_mode == "POLY" and len(self._tch_points) < 3:
            return "POLY requires at least 3 waypoints."
        if (
            self._tch_mode == "POLY"
            and self._poly_max_close_gap_m > 0
            and len(self._tch_points) >= 3
        ):
            first = self._tch_points[0][:2]
            last = self._tch_points[-1][:2]
            gap_m = haversine_distance_m(first, last)
            if gap_m > self._poly_max_close_gap_m:
                return (
                    f"POLY cannot be saved: first and last point are {gap_m:.1f} m apart "
                    f"(max {self._poly_max_close_gap_m:.1f} m to close the loop)."
                )
        if self._tch_mode == "POLY" and self._poly_min_area_m2 > 0 and len(
            self._tch_points
        ) >= 3:
            area = polygon_area_m2([(p[0], p[1]) for p in self._tch_points])
            if area < self._poly_min_area_m2:
                return (
                    f"POLY cannot be saved: area is {area:.1f} m² "
                    f"(minimum {self._poly_min_area_m2:.1f} m²)."
                )
        if (
            self._tch_mode == "POLY"
            and self._poly_reject_self_intersection
            and len(self._tch_points) >= 4
        ):
            pts_2d = [(p[0], p[1]) for p in self._tch_points]
            if polygon_has_self_intersection(pts_2d):
                return (
                    "POLY cannot be saved: boundary edges cross each other "
                    "(self-intersection)."
                )
        return None

    def teach_save_to_disk(self, missions_dir: str) -> Tuple[Optional[str], str]:
        """Write mission JSON; clear session. Returns (filename, error)."""
        err = self.validate_teach_save()
        if err:
            return None, err

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "poly" if self._tch_mode == "POLY" else "path"
        filename = f"{prefix}_{ts}.json"
        os.makedirs(missions_dir, exist_ok=True)
        path = os.path.join(missions_dir, filename)

        coords = [
            [lat, lon, round(theta, 4)]
            for lat, lon, theta in self._tch_points
        ]
        payload = {
            "type": self._tch_mode,
            "count": len(coords),
            "coordinates": coords,
            "created_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError as exc:
            return None, f"Could not save mission file: {exc}"

        self._tch_points.clear()
        self._emit_tch_stats()
        self.tch_session_saved.emit(filename)
        return filename, ""

    def tch_distance_since_last_point_m(self) -> Optional[float]:
        """Distance from current fix to last logged waypoint; None if no fix or no points."""
        if not self._has_position or not self._tch_points:
            return None
        last = self._tch_points[-1]
        return haversine_distance_m(
            (last[0], last[1]), (self._last_lat, self._last_lon)
        )

    def _emit_tch_stats(self) -> None:
        n = len(self._tch_points)
        if self._tch_mode == "POLY" and n >= 3:
            area = polygon_area_m2([(p[0], p[1]) for p in self._tch_points])
        else:
            area = -1.0
        self.tch_stats_changed.emit(n, area)

    # ── Internal helpers ──────────────────────────────────────

    def _refresh_status_line(self) -> None:
        bat = self._battery_pct
        bat_s = f"{bat:.0f}%" if bat is not None else "--"
        mqtt_s = "OK" if self._mqtt_ok else "OFF"
        self.status_line_changed.emit(
            f"{self._sensor_diag} | BAT: {bat_s} | MQTT: {mqtt_s}"
        )

    @staticmethod
    def _format_sensor_diag(sensor_diag: str) -> str:
        parts = []
        for chunk in str(sensor_diag).split(","):
            item = chunk.strip()
            if not item:
                continue
            if ":" in item:
                key, value = item.split(":", 1)
                parts.append(f"{key.strip().upper()}: {value.strip().upper()}")
            else:
                parts.append(item.upper())
        return " | ".join(parts) if parts else "--"

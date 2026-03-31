"""Main window: map background with floating HUD overlays.

Responsibilities:
  1. Instantiate components and place them on screen.
  2. Wire AppState signals → component update methods.
  3. Handle sidebar user-actions (e-stop, save, tab switch).

All MQTT/VDA lifecycle lives in VDAController.
All state formatting lives in AppState.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import QMainWindow, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent

from core.app_state import AppState
from core.docker_controller import DockerController
from core.mission_builder import build_path_order
from core.vda_controller import VDAController
from utils.coverage import compute_coverage_path
from utils.geometry import haversine_distance_m
from ui.components.map_view import MapView
from ui.components.top_bar import TopBar
from ui.components.left_hud import LeftHUD
from ui.components.right_sidebar import RightSidebar
from ui import theme
from utils.logger import logger

_MODE_LABELS = ("MODE: SYSTEM SETUP", "MODE: TEACH-IN", "MODE: AUTO-RUN")

# Auto-record: time interval (ms) and minimum travel (m) since last waypoint
_AUTO_RECORD_INTERVAL_MS = 2000
_AUTO_RECORD_MIN_DISTANCE_M = 2.0
_AUTO_RECORD_MIN_INTERVAL_S = 1.0


class MainWindow(QMainWindow):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Mowbot Control GUMI")
        self.resize(1280, 800)
        self.setStyleSheet(theme.MAIN_WINDOW_STYLE)

        self._last_auto_distance_log_mono: float = 0.0
        self._mission_preview_filename: Optional[str] = None
        self._latest_status_line: str = "GPS: FIX  |  BAT: --  |  MQTT: OFF"
        self._error_active: bool = False

        self._app_state = AppState(
            self,
            poly_max_close_gap_m=self._teach_poly_max_close_gap_m(),
            poly_min_area_m2=self._teach_poly_min_area_m2(),
            poly_reject_self_intersection=self._teach_poly_reject_self_intersection(),
        )

        # Layer 1: full-screen map background
        self.map_view = MapView(self)
        self.setCentralWidget(self.map_view)

        # Layer 2–4: floating overlays
        self.top_bar = TopBar(self)
        self.hud_panel = LeftHUD(self)
        self.sidebar_panel = RightSidebar(self)

        self._auto_record_timer = QTimer(self)
        self._auto_record_timer.setInterval(_AUTO_RECORD_INTERVAL_MS)
        self._auto_record_timer.timeout.connect(self._on_auto_record_tick)

        self._mission_clear_timer = QTimer(self)
        self._mission_clear_timer.setSingleShot(True)
        self._mission_clear_timer.setInterval(3000)
        self._mission_clear_timer.timeout.connect(self._clear_finished_mission_overlay)

        self._connect_state()
        self._connect_sidebar()
        self._init_robot_id()
        self._refresh_mission_files()
        self.sidebar_panel.update_tch_stats(0, -1.0)
        self.sidebar_panel.set_tch_mode_buttons("PATH")
        self.map_view.set_teach_recording_poly_mode(False)

        # VDA controller owns bridge lifecycle and writes into AppState
        self._vda = VDAController(self.config, self._app_state, parent=self)

        # Docker controller manages container start/stop sequences
        self._docker = DockerController(self.config, self._app_state, parent=self)
        self.sidebar_panel.init_docker_service_labels(
            self._docker.startup_sequence_keys()
        )
        self._system_starting = False

    def _project_root(self) -> str:
        return os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    def _missions_dir(self) -> str:
        sub = (self.config.get("missions") or {}).get("directory", "missions")
        return os.path.join(self._project_root(), sub)

    def _teach_poly_max_close_gap_m(self) -> float:
        t = self.config.get("teach_in") or {}
        raw = t.get("poly_max_close_gap_m", 5.0)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 5.0

    def _teach_poly_min_area_m2(self) -> float:
        t = self.config.get("teach_in") or {}
        raw = t.get("poly_min_area_m2", 0.0)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    def _teach_poly_reject_self_intersection(self) -> bool:
        t = self.config.get("teach_in") or {}
        raw = t.get("poly_reject_self_intersection", True)
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def _coverage_params(self) -> dict:
        c = self.config.get("coverage") or {}
        sweep_raw = c.get("sweep_angle_deg")
        sweep_angle_deg: Optional[float] = None
        if sweep_raw is not None:
            try:
                sweep_angle_deg = float(sweep_raw)
            except (TypeError, ValueError):
                sweep_angle_deg = None
        try:
            mow_width_m = float(c.get("mow_width_m", 0.5))
        except (TypeError, ValueError):
            mow_width_m = 0.5
        try:
            overlap_pct = float(c.get("overlap_pct", 10.0))
        except (TypeError, ValueError):
            overlap_pct = 10.0
        try:
            max_waypoints = int(c.get("max_waypoints", 2000))
        except (TypeError, ValueError):
            max_waypoints = 2000
        return {
            "mow_width_m": mow_width_m,
            "overlap_pct": overlap_pct,
            "sweep_angle_deg": sweep_angle_deg,
            "max_waypoints": max_waypoints,
        }

    def _max_start_distance_m(self) -> float:
        m = self.config.get("missions") or {}
        raw = m.get("max_start_distance_m", 50.0)
        try:
            v = float(raw)
            return v if v > 0 else 0.0
        except (TypeError, ValueError):
            return 50.0

    @staticmethod
    def _parse_mission_json_file(
        path: str,
    ) -> Tuple[Optional[str], List[Tuple[float, float, float]], Optional[str]]:
        """Returns (type, coordinates as (lat, lon, theta_rad), error_message).

        Older files with only [lat, lon] get theta_rad = 0.0.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            return None, [], f"Could not read mission file: {exc}"

        typ = str(data.get("type", "")).strip().upper()
        if typ not in ("PATH", "POLY"):
            return None, [], "Invalid or missing 'type' (expected PATH or POLY)."

        raw_coords = data.get("coordinates")
        if not isinstance(raw_coords, list) or len(raw_coords) == 0:
            return None, [], "Missing or empty 'coordinates' array."

        out: List[Tuple[float, float, float]] = []
        for i, pair in enumerate(raw_coords):
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                return None, [], f"Invalid coordinate pair at index {i}."
            try:
                lat = float(pair[0])
                lon = float(pair[1])
                theta = float(pair[2]) if len(pair) >= 3 else 0.0
            except (TypeError, ValueError):
                return None, [], f"Non-numeric coordinate at index {i}."
            out.append((lat, lon, theta))

        if typ == "PATH" and len(out) < 2:
            return None, [], "PATH missions need at least 2 coordinates."
        if typ == "POLY" and len(out) < 3:
            return None, [], "POLY missions need at least 3 coordinates."

        return typ, out, None

    def _safe_mission_path(self, filename: str) -> Optional[str]:
        """Resolve a mission JSON path under missions dir only (no traversal)."""
        raw = str(filename).strip()
        name = os.path.basename(raw)
        if not name or name != raw:
            return None
        if ".." in name or not name.endswith(".json"):
            return None
        base = os.path.realpath(self._missions_dir())
        full = os.path.realpath(os.path.join(base, name))
        if not full.startswith(base + os.sep):
            return None
        return full

    def _refresh_mission_files(self) -> None:
        d = self._missions_dir()
        names: list[str] = []
        if os.path.isdir(d):
            paths = [
                os.path.join(d, f)
                for f in os.listdir(d)
                if f.endswith(".json") and os.path.isfile(os.path.join(d, f))
            ]
            paths.sort(key=os.path.getmtime, reverse=True)
            names = [os.path.basename(p) for p in paths]
        self.sidebar_panel.set_mission_files(names)

    # ── State → UI wiring ─────────────────────────────────────

    def _connect_state(self) -> None:
        s = self._app_state
        s.status_line_changed.connect(self._on_status_line)
        s.mode_changed.connect(lambda m: self.top_bar.set_mode(f"MODE: {m}"))
        s.position_changed.connect(self.hud_panel.update_telemetry)
        s.position_changed.connect(self._update_map_marker)
        s.position_changed.connect(self._maybe_auto_record_on_distance)
        s.robot_id_changed.connect(self.top_bar.set_robot_id)
        s.error_changed.connect(self._on_error)

        s.tch_point_added.connect(self._on_tch_point_added)
        s.tch_point_undone.connect(self._on_tch_point_undone)
        s.tch_cleared.connect(self.map_view.clear_teach_layer)
        s.tch_mode_changed.connect(self.sidebar_panel.set_tch_mode_buttons)
        s.tch_mode_changed.connect(self._on_tch_mode_map_visual)
        s.tch_stats_changed.connect(self.sidebar_panel.update_tch_stats)
        s.tch_auto_record_changed.connect(self._on_tch_auto_record_state)
        s.tch_error.connect(self._on_tch_error)
        s.tch_session_saved.connect(self._on_tch_session_saved)
        s.order_dispatched.connect(self._on_order_dispatched)
        s.mission_progress_changed.connect(self._on_mission_progress)

        s.docker_sequence_step.connect(self.sidebar_panel.set_docker_step_status)
        s.docker_sequence_finished.connect(self._on_docker_sequence_finished)
        s.docker_error.connect(self._on_docker_error)

    def _update_map_marker(
        self, x: float, y: float, theta_rad: float, _speed: float
    ) -> None:
        self.map_view.update_robot_marker(lat=y, lon=x, heading_rad=theta_rad)

    def _on_status_line(self, text: str) -> None:
        self._latest_status_line = text
        if not self._error_active:
            self.top_bar.set_status_line(text)

    def _on_error(self, msg: str) -> None:
        logger.info(f"[VDA] {msg}")
        if msg == "ALL CLEAR":
            self._error_active = False
            self.top_bar.set_status_line(self._latest_status_line)
            return
        self._error_active = True
        self.top_bar.set_error_line(msg)

    def _on_tch_mode_map_visual(self, mode: str) -> None:
        self.map_view.set_teach_recording_poly_mode(str(mode).upper() == "POLY")

    def _on_tch_point_added(self, lat: float, lon: float, _count: int) -> None:
        self.map_view.add_teach_point(lat, lon)

    def _on_tch_point_undone(self, _count: int) -> None:
        self.map_view.undo_teach_point()

    def _on_tch_auto_record_state(self, on: bool) -> None:
        self.sidebar_panel.set_auto_record_ui(on)
        if on:
            self._auto_record_timer.start()
        else:
            self._auto_record_timer.stop()

    def _on_auto_record_tick(self) -> None:
        self._app_state.tch_log_point()

    def _maybe_auto_record_on_distance(
        self, _x: float, _y: float, _theta: float, _speed: float
    ) -> None:
        if not self._app_state.tch_auto_record:
            return
        if not self._app_state.tch_points:
            return
        dist = self._app_state.tch_distance_since_last_point_m()
        if dist is None or dist < _AUTO_RECORD_MIN_DISTANCE_M:
            return
        now = time.monotonic()
        if now - self._last_auto_distance_log_mono < _AUTO_RECORD_MIN_INTERVAL_S:
            return
        if self._app_state.tch_log_point():
            self._last_auto_distance_log_mono = now

    def _on_tch_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Teach-In", msg)

    def _on_tch_session_saved(self, filename: str) -> None:
        QMessageBox.information(
            self,
            "Mission saved",
            f"Saved as {filename}",
        )
        self.map_view.clear_teach_layer()
        self._refresh_mission_files()
        self.sidebar_panel.select_mission_file(filename)
        # Stay on teach-in; RUN mission list is still updated for when you switch later.
        self.sidebar_panel.switch_tab(1)

    # ── Robot identity ────────────────────────────────────────

    def _init_robot_id(self) -> None:
        serial = self.config.get("general", {}).get("serial_number")
        if serial:
            text = str(serial).strip()
            robot_id = text if text.lower().startswith("mowbot") else f"Mowbot-{text}"
            self._app_state.set_robot_id(robot_id)

    # ── Sidebar interaction handlers ──────────────────────────

    def _connect_sidebar(self) -> None:
        sb = self.sidebar_panel
        sb.tab_changed.connect(self._on_tab_changed)
        sb.save_mission_requested.connect(self._on_finish_teach_save)
        sb.estop_pressed.connect(self._on_estop)
        sb.start_system_state_changed.connect(self._on_start_system)
        sb.log_point_requested.connect(self._on_log_point)
        sb.auto_record_clicked.connect(self._on_auto_record_toggle)
        sb.undo_requested.connect(self._on_teach_undo)
        sb.clear_teach_requested.connect(self._on_teach_clear)
        sb.tch_mode_path_selected.connect(lambda: self._app_state.tch_set_mode("PATH"))
        sb.tch_mode_poly_selected.connect(lambda: self._app_state.tch_set_mode("POLY"))
        sb.tch_session_stopped.connect(self._on_tch_session_stopped)
        sb.execute_mission_requested.connect(self._on_execute_mission)
        sb.delete_mission_requested.connect(self._on_delete_mission)
        sb.load_mission_preview_requested.connect(self._on_load_mission_preview)

    def _on_tab_changed(self, index: int) -> None:
        if self._app_state.operating_mode is None:
            self.top_bar.set_mode(_MODE_LABELS[index])

    def _on_tch_session_stopped(self) -> None:
        if self._app_state.tch_auto_record:
            self._app_state.tch_set_auto_record(False)

    def _on_finish_teach_save(self) -> None:
        err = self._app_state.validate_teach_save()
        if err:
            QMessageBox.warning(self, "Teach-In", err)
            return
        _, err2 = self._app_state.teach_save_to_disk(self._missions_dir())
        if err2:
            QMessageBox.warning(self, "Teach-In", err2)
            return

    def _on_estop(self) -> None:
        logger.critical("E-STOP pressed from UI")
        self._vda.trigger_estop()

    def _on_start_system(self, is_starting: bool) -> None:
        if is_starting:
            self._system_starting = True
            logger.info("[Docker] Startup sequence requested")
            self._docker.start_sequence()
        else:
            self._system_starting = False
            logger.info("[Docker] Shutdown sequence requested")
            self._docker.stop_sequence()

    def _on_docker_sequence_finished(self, ok: bool, detail: str) -> None:
        if ok and self._system_starting:
            logger.info("[Docker] Startup complete: %s", detail)
            self.sidebar_panel.set_system_running()
        elif ok and not self._system_starting:
            logger.info("[Docker] Shutdown complete: %s", detail)
            self.sidebar_panel.set_system_stopped()
        else:
            logger.error("[Docker] Sequence failed: %s", detail)
            self.sidebar_panel.set_system_failed()
            QMessageBox.warning(self, "Docker", detail)

    def _on_docker_error(self, key: str, msg: str) -> None:
        logger.error("[Docker] %s: %s", key, msg)

    def _on_log_point(self) -> None:
        self._app_state.tch_log_point()

    def _on_auto_record_toggle(self) -> None:
        self._app_state.tch_toggle_auto_record()

    def _on_teach_undo(self) -> None:
        self._app_state.tch_undo()

    def _on_teach_clear(self) -> None:
        self._app_state.tch_clear_session()

    def _on_execute_mission(self) -> None:
        name = self.sidebar_panel.current_mission_filename()
        if not name:
            QMessageBox.information(self, "Execute mission", "No mission selected.")
            return
        if not self._app_state.mqtt_ok:
            QMessageBox.warning(
                self,
                "Execute mission",
                "MQTT is not connected. Wait for connection before running a mission.",
            )
            return
        path = self._safe_mission_path(name)
        if path is None or not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "Execute mission",
                "Invalid mission name or file not found.",
            )
            return
        typ, coords, err = self._parse_mission_json_file(path)
        if err:
            QMessageBox.warning(self, "Execute mission", err)
            return
        assert typ is not None
        self._mission_clear_timer.stop()
        self.map_view.clear_mission_preview()
        self._app_state.reset_mission_progress_ui()
        latlon = [(c[0], c[1]) for c in coords]
        exec_coords = coords
        if typ == "POLY":
            path_wps, cerr = compute_coverage_path(
                latlon,
                robot_position=self._app_state.get_robot_latlon(),
                **self._coverage_params(),
            )
            if cerr:
                QMessageBox.warning(self, "Execute mission", cerr)
                return
            exec_coords = [(lat, lon, 0.0) for lat, lon in path_wps]
            self.map_view.load_poly_coverage_preview(latlon, path_wps)
        else:
            self.map_view.load_mission_preview(typ, latlon)

        g = self.config.get("general") or {}
        manufacturer = str(g.get("manufacturer", "MowbotTech"))
        serial_number = str(g.get("serial_number", "mowbot_001"))
        map_id = str(g.get("map_id") or "mowbot_field")
        try:
            order = build_path_order(
                exec_coords,
                manufacturer=manufacturer,
                serial_number=serial_number,
                map_id=map_id,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Execute mission", str(exc))
            return

        max_dist = self._max_start_distance_m()
        if max_dist > 0 and exec_coords:
            robot_pos = self._app_state.get_robot_latlon()
            if robot_pos is not None:
                first_wp = (exec_coords[0][0], exec_coords[0][1])
                dist = haversine_distance_m(robot_pos, first_wp)
                if dist > max_dist:
                    reply = QMessageBox.question(
                        self,
                        "Execute mission",
                        f"Robot is {dist:.0f} m from the first waypoint "
                        f"(limit {max_dist:.0f} m).\n\n"
                        "Start the mission anyway?",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return

        self._mission_preview_filename = name

        self._vda.send_path_order(order)
        logger.info(
            f"Execute mission: queued VDA order {order.orderId} from {name} "
            f"({len(exec_coords)} waypoints, mapId={map_id})"
        )

    def _on_order_dispatched(self, ok: bool, detail: str, total_nodes: int) -> None:
        if ok:
            logger.info(f"Order dispatched: {detail} ({total_nodes} nodes)")
        else:
            logger.error(f"Order dispatch failed: {detail}")
            QMessageBox.warning(
                self,
                "Execute mission",
                f"Failed to send order to the robot.\n\n{detail}",
            )

    def _on_mission_progress(
        self,
        status: str,
        order_id: str,
        completed: int,
        total: int,
        last_idx: int,
    ) -> None:
        self.sidebar_panel.update_mission_progress(
            status, order_id, completed, total, last_idx
        )
        st = (status or "").lower()
        if st == "idle" or (st == "executing" and last_idx < 0):
            self.map_view.clear_mission_progress_highlight()
        elif st == "completed":
            self.map_view.update_mission_progress(last_idx, True)
            self._mission_clear_timer.start()
        elif st == "failed":
            self._mission_clear_timer.stop()
            # Require operator to explicitly reload mission after a failure.
            self.sidebar_panel.set_mission_loaded(False)
            if last_idx >= 0:
                self.map_view.update_mission_progress(last_idx, False)
        else:
            self.map_view.update_mission_progress(last_idx, False)

    def _clear_finished_mission_overlay(self) -> None:
        """Remove mission markers/overlay after completion (called by timer)."""
        self.map_view.clear_mission_preview()
        self._mission_preview_filename = None
        self.sidebar_panel.set_mission_loaded(False)
        logger.info("Cleared mission overlay after completion")

    def _on_load_mission_preview(self) -> None:
        name = self.sidebar_panel.current_mission_filename()
        if not name:
            QMessageBox.information(self, "Load mission", "No mission selected.")
            return
        path = self._safe_mission_path(name)
        if path is None or not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "Load mission",
                "Invalid mission name or file not found.",
            )
            return
        typ, coords, err = self._parse_mission_json_file(path)
        if err:
            QMessageBox.warning(self, "Load mission", err)
            return
        assert typ is not None
        latlon = [(c[0], c[1]) for c in coords]
        self._app_state.reset_mission_progress_ui()
        if typ == "POLY":
            path_wps, cerr = compute_coverage_path(
                latlon,
                robot_position=self._app_state.get_robot_latlon(),
                **self._coverage_params(),
            )
            if cerr:
                QMessageBox.warning(self, "Load mission", cerr)
                return
            self.map_view.load_poly_coverage_preview(latlon, path_wps)
            logger.info(
                f"Mission preview on map: {name} (POLY, {len(coords)} boundary pts, "
                f"{len(path_wps)} coverage waypoints)"
            )
        else:
            self.map_view.load_mission_preview(typ, latlon)
            logger.info(f"Mission preview on map: {name} ({typ}, {len(coords)} pts)")
        self._mission_preview_filename = name
        self.sidebar_panel.set_mission_loaded(True)

    def _on_delete_mission(self) -> None:
        name = self.sidebar_panel.current_mission_filename()
        if not name:
            QMessageBox.information(self, "Delete mission", "No mission selected.")
            return
        path = self._safe_mission_path(name)
        if path is None or not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "Delete mission",
                "Invalid mission name or file not found.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Delete mission",
            f"Permanently delete this file?\n\n{name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(path)
        except OSError as exc:
            QMessageBox.warning(self, "Delete mission", str(exc))
            return
        logger.info(f"Deleted mission file: {name}")
        if self._mission_preview_filename == name:
            self.map_view.clear_mission_preview()
            self._mission_preview_filename = None
            self.sidebar_panel.set_mission_loaded(False)
        self._refresh_mission_files()
        QMessageBox.information(self, "Delete mission", f"Deleted {name}.")

    # ── Lifecycle ─────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        self._docker.cancel_sequence()
        self._vda.stop()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        m = theme.OVERLAY_MARGIN

        self.top_bar.setGeometry(0, 0, w, theme.TOPBAR_HEIGHT)
        self.hud_panel.setGeometry(
            m, theme.TOPBAR_HEIGHT + m, theme.HUD_WIDTH, theme.HUD_HEIGHT
        )
        self.sidebar_panel.setGeometry(
            w - theme.SIDEBAR_WIDTH - m,
            theme.TOPBAR_HEIGHT + m,
            theme.SIDEBAR_WIDTH,
            h - theme.TOPBAR_HEIGHT - (m * 2),
        )

"""Main window: map background with floating HUD overlays.

Responsibilities:
  1. Instantiate components and place them on screen.
  2. Wire AppState signals → component update methods.
  3. Handle sidebar user-actions (e-stop, save, tab switch).

All MQTT/VDA lifecycle lives in VDAController.
All state formatting lives in AppState.
"""

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QMainWindow, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent

from core.app_state import AppState
from core.vda_controller import VDAController
from ui.components.map_view import MapView
from ui.components.top_bar import TopBar
from ui.components.left_hud import LeftHUD
from ui.components.right_sidebar import RightSidebar
from ui import theme
from utils.logger import logger

_MODE_LABELS = ("MODE: SYSTEM SETUP", "MODE: TEACH-IN", "MODE: AUTO-RUN")


class MainWindow(QMainWindow):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Mowbot Control GUMI")
        self.resize(1280, 800)
        self.setStyleSheet(theme.MAIN_WINDOW_STYLE)

        self._app_state = AppState(self)

        # Layer 1: full-screen map background
        self.map_view = MapView(self)
        self.setCentralWidget(self.map_view)

        # Layer 2–4: floating overlays
        self.top_bar = TopBar(self)
        self.hud_panel = LeftHUD(self)
        self.sidebar_panel = RightSidebar(self)

        self._connect_state()
        self._connect_sidebar()
        self._init_robot_id()

        # VDA controller owns bridge lifecycle and writes into AppState
        self._vda = VDAController(self.config, self._app_state, parent=self)

    # ── State → UI wiring ─────────────────────────────────────

    def _connect_state(self) -> None:
        s = self._app_state
        s.status_line_changed.connect(self.top_bar.set_status_line)
        s.mode_changed.connect(lambda m: self.top_bar.set_mode(f"MODE: {m}"))
        s.position_changed.connect(self.hud_panel.update_telemetry)
        s.position_changed.connect(self._update_map_marker)
        s.robot_id_changed.connect(self.top_bar.set_robot_id)
        s.error_changed.connect(self._on_error)

    def _update_map_marker(
        self, x: float, y: float, theta_deg: float, _speed: float
    ) -> None:
        self.map_view.update_robot_marker(lat=y, lon=x, heading_deg=theta_deg)

    def _on_error(self, msg: str) -> None:
        logger.info(f"[VDA] {msg}")

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
        sb.save_mission_requested.connect(self._on_save_mission)
        sb.estop_pressed.connect(self._on_estop)
        sb.start_system_state_changed.connect(self._on_start_system)
        sb.log_point_requested.connect(self._on_log_point)
        sb.auto_record_clicked.connect(self._on_auto_record)
        sb.execute_mission_requested.connect(self._on_execute_mission)

    def _on_tab_changed(self, index: int) -> None:
        if self._app_state.operating_mode is None:
            self.top_bar.set_mode(_MODE_LABELS[index])

    def _on_save_mission(self) -> None:
        QMessageBox.information(
            self,
            "Save Mission",
            "Mission 'Lawn_Zone_A_01' saved successfully!\n\nSwitching to AUTO-RUN mode.",
        )
        self.sidebar_panel.switch_tab(2)

    def _on_estop(self) -> None:
        logger.critical("E-STOP pressed from UI")
        self._vda.trigger_estop()

    def _on_start_system(self, is_running: bool) -> None:
        logger.info(f"System running state: {is_running}")

    def _on_log_point(self) -> None:
        logger.info("LOG POINT (teach-in)")

    def _on_auto_record(self) -> None:
        logger.info("AUTO-RECORD clicked")

    def _on_execute_mission(self) -> None:
        logger.info("EXECUTE MISSION")

    # ── Lifecycle ─────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
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

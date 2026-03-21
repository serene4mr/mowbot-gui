"""Main window: map, overlays, and component wiring."""

import sys
from typing import Any, Dict, Optional

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import Qt

from ui.components.map_view import MapView
from ui.components.top_bar import TopBar
from ui.components.left_hud import LeftHUD
from ui.components.right_sidebar import RightSidebar


_MODE_LABELS = ("MODE: SYSTEM SETUP", "MODE: TEACH-IN", "MODE: AUTO-RUN")


class MainWindow(QMainWindow):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config or {}
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Mowbot Control GUMI")
        self.resize(1280, 800)
        self.setStyleSheet("QMainWindow { background-color: #121212; }")

        # Layer 1: background map (WebEngine / ESRI lives in MapView)
        self.map_view = MapView(self)
        self.setCentralWidget(self.map_view)

        # Layer 2–4: floating components
        self.top_bar = TopBar(self)
        self.hud_panel = LeftHUD(self)
        self.sidebar_panel = RightSidebar(self)

        serial = self.config.get("general", {}).get("serial_number")
        if serial:
            serial_text = str(serial).strip()
            if serial_text.lower().startswith("mowbot"):
                robot_id = serial_text
            else:
                robot_id = f"Mowbot-{serial_text}"
            self.top_bar.set_robot_id(robot_id)

        self._connect_components()

    def _connect_components(self):
        self.sidebar_panel.tab_changed.connect(self._on_tab_changed)
        self.sidebar_panel.save_mission_requested.connect(self._on_save_mission)
        self.sidebar_panel.estop_pressed.connect(self._on_estop)
        self.sidebar_panel.start_system_state_changed.connect(
            self._on_start_system_state_changed
        )
        self.sidebar_panel.log_point_requested.connect(self._on_log_point)
        self.sidebar_panel.auto_record_clicked.connect(self._on_auto_record)
        self.sidebar_panel.execute_mission_requested.connect(self._on_execute_mission)

    def _on_tab_changed(self, index: int):
        self.top_bar.set_mode(_MODE_LABELS[index])

    def _on_save_mission(self):
        QMessageBox.information(
            self,
            "Save Mission",
            "Mission 'Lawn_Zone_A_01' saved successfully!\n\nSwitching to AUTO-RUN mode.",
        )
        self.sidebar_panel.switch_tab(2)

    def _on_estop(self):
        print("CRITICAL: E-STOP PRESSED!")

    def _on_start_system_state_changed(self, is_running: bool):
        # Hook for MQTT / robot power commands
        print(f"System running state: {is_running}")

    def _on_log_point(self):
        print("LOG POINT (teach-in)")

    def _on_auto_record(self):
        print("AUTO-RECORD clicked")

    def _on_execute_mission(self):
        print("EXECUTE MISSION")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()

        top_bar_height = 50
        self.top_bar.setGeometry(0, 0, w, top_bar_height)

        margin = 20
        hud_width = 250
        hud_height = 150
        self.hud_panel.setGeometry(margin, top_bar_height + margin, hud_width, hud_height)

        sidebar_width = 350
        self.sidebar_panel.setGeometry(
            w - sidebar_width - margin,
            top_bar_height + margin,
            sidebar_width,
            h - top_bar_height - (margin * 2),
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec())

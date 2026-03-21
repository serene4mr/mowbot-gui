"""Top status bar: robot ID, mode, and system summary."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


class TopBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: rgba(20, 25, 30, 230); border-bottom: 2px solid #333;"
        )
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self.lbl_robot_id = QLabel("MOWBOT-001")
        self.lbl_robot_id.setStyleSheet(
            "font-weight: bold; color: #E0E0E0; font-size: 18px;"
        )

        self.lbl_global_mode = QLabel("MODE: SYSTEM SETUP")
        self.lbl_global_mode.setStyleSheet(
            "font-weight: bold; color: #00B0FF; font-size: 16px;"
        )

        self.status_icons = QLabel("GPS: FIX  |  BAT: 85%  |  14:30")
        self.status_icons.setStyleSheet(
            "color: #00E676; font-size: 16px; font-weight: bold;"
        )

        layout.addWidget(self.lbl_robot_id)
        layout.addStretch()
        layout.addWidget(self.lbl_global_mode)
        layout.addStretch()
        layout.addWidget(self.status_icons)

    def set_mode(self, mode_text: str) -> None:
        """Update the centered mode label (e.g. MODE: AUTO-RUN)."""
        self.lbl_global_mode.setText(mode_text)

    def set_robot_id(self, robot_id: str) -> None:
        self.lbl_robot_id.setText(robot_id)

    def set_status_line(self, text: str) -> None:
        """GPS / battery / time or other one-line status."""
        self.status_icons.setText(text)

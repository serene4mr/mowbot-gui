"""Top status bar: robot ID, mode, and system summary."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ui import theme


class TopBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(theme.TOPBAR_STYLE)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self.lbl_robot_id = QLabel("MOWBOT-001")
        self.lbl_robot_id.setStyleSheet(
            f"font-weight: bold; color: {theme.TEXT_PRIMARY}; "
            f"font-size: {theme.FONT_XL}px;"
        )

        self.lbl_global_mode = QLabel("MODE: SYSTEM SETUP")
        self.lbl_global_mode.setStyleSheet(
            f"font-weight: bold; color: {theme.ACCENT_BLUE}; "
            f"font-size: {theme.FONT_LG}px;"
        )

        self.status_icons = QLabel("GPS: FIX  |  BAT: 85%  |  14:30")
        self.status_icons.setStyleSheet(
            f"color: {theme.ACCENT_GREEN}; font-size: {theme.FONT_LG}px; "
            f"font-weight: bold;"
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

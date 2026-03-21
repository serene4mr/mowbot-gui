"""Left HUD: telemetry labels."""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class LeftHUD(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: rgba(20, 25, 30, 210); border-radius: 10px; color: white;"
        )
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("TELEMETRY")
        title.setStyleSheet("color: #00E676; font-weight: bold; font-size: 16px;")
        layout.addWidget(title)

        self.lbl_pos = QLabel("POS: 12.45, -5.20, 45 deg")
        self.lbl_vel = QLabel("VEL: 0.55 m/s")

        for lbl in (self.lbl_pos, self.lbl_vel):
            lbl.setStyleSheet("font-size: 15px; font-family: monospace;")
            layout.addWidget(lbl)

        layout.addStretch()

    def update_telemetry(self, x: float, y: float, theta: float, velocity: float) -> None:
        """Update position and velocity from the main thread."""
        self.lbl_pos.setText(f"POS: {x:.2f}, {y:.2f}, {theta:.1f} deg")
        self.lbl_vel.setText(f"VEL: {velocity:.2f} m/s")

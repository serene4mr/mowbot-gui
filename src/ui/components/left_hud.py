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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("TELEMETRY")
        title.setStyleSheet("color: #00E676; font-weight: bold; font-size: 15px;")
        layout.addWidget(title)

        self.lbl_lat = QLabel("LAT: ---")
        self.lbl_lon = QLabel("LON: ---")
        self.lbl_theta = QLabel("THETA: ---")
        self.lbl_vel = QLabel("VEL: ---")

        for lbl in (self.lbl_lat, self.lbl_lon, self.lbl_theta, self.lbl_vel):
            lbl.setWordWrap(False)
            lbl.setStyleSheet("font-size: 13px; font-family: monospace;")
            layout.addWidget(lbl)

        layout.addStretch()

    def update_telemetry(self, x: float, y: float, theta: float, velocity: float) -> None:
        """Update position and velocity from the main thread."""
        # VDA mapping in this app: x = longitude, y = latitude.
        self.lbl_lat.setText(f"LAT: {y}")
        self.lbl_lon.setText(f"LON: {x}")
        self.lbl_theta.setText(f"THETA: {theta:.2f} deg")
        self.lbl_vel.setText(f"VEL: {velocity:.2f} m/s")

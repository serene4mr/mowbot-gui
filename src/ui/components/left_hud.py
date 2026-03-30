"""Left HUD: telemetry labels."""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel

from ui import theme


class LeftHUD(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(theme.PANEL_STYLE)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("TELEMETRY")
        title.setStyleSheet(
            f"color: {theme.ACCENT_GREEN}; font-weight: bold; "
            f"font-size: {theme.FONT_MD}px;"
        )
        layout.addWidget(title)

        mono_style = f"font-size: {theme.FONT_XS}px; font-family: monospace;"
        self.lbl_lat = QLabel("LAT: ---")
        self.lbl_lon = QLabel("LON: ---")
        self.lbl_theta = QLabel("THETA: ---")
        self.lbl_vel = QLabel("VEL: ---")

        for lbl in (self.lbl_lat, self.lbl_lon, self.lbl_theta, self.lbl_vel):
            lbl.setWordWrap(False)
            lbl.setStyleSheet(mono_style)
            layout.addWidget(lbl)

        layout.addStretch()

    def update_telemetry(
        self, x: float, y: float, theta: float, velocity: float
    ) -> None:
        """Update position and velocity from the main thread."""
        self.lbl_lat.setText(f"LAT: {y}")
        self.lbl_lon.setText(f"LON: {x}")
        self.lbl_theta.setText(f"THETA: {theta:.3f} rad")
        self.lbl_vel.setText(f"VEL: {velocity:.2f} m/s")

"""Left HUD: telemetry labels and VDA5050 sensor deep diagnostics."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from core.sensor_diagnostics import sensor_status_from_payload
from ui import theme

_SENSOR_ORDER = ("LASER", "IMU", "GNSS", "RTCM")


class LeftHUD(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(theme.PANEL_STYLE)
        self._sensor_rows: List[Tuple[str, QLabel, QLabel]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

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

        sep = QLabel("SENSOR HEALTH")
        sep.setStyleSheet(
            f"color: {theme.ACCENT_GREEN}; font-weight: bold; "
            f"font-size: {theme.FONT_SM}px; margin-top: 6px;"
        )
        layout.addWidget(sep)

        name_style = f"font-size: {theme.FONT_XS}px; font-family: monospace; min-width: 52px;"
        for hid in _SENSOR_ORDER:
            row = QHBoxLayout()
            row.setSpacing(8)
            name = QLabel(hid)
            name.setStyleSheet(name_style)
            badge = QLabel("—")
            badge.setStyleSheet(
                f"font-size: {theme.FONT_XS}px; font-family: monospace; "
                f"font-weight: bold; color: {theme.TEXT_MUTED}; min-width: 44px;"
            )
            metric = QLabel("—")
            metric.setStyleSheet(
                f"font-size: {theme.FONT_XS}px; font-family: monospace; "
                f"color: {theme.TEXT_PRIMARY};"
            )
            metric.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            row.addWidget(name)
            row.addWidget(badge)
            row.addWidget(metric, stretch=1)
            layout.addLayout(row)
            self._sensor_rows.append((hid, badge, metric))

        layout.addStretch()

    def update_telemetry(
        self, x: float, y: float, theta: float, velocity: float
    ) -> None:
        """Update position and velocity from the main thread."""
        self.lbl_lat.setText(f"LAT: {y}")
        self.lbl_lon.setText(f"LON: {x}")
        self.lbl_theta.setText(f"THETA: {theta:.3f} rad")
        self.lbl_vel.setText(f"VEL: {velocity:.2f} m/s")

    @staticmethod
    def _badge_for_level(level: str) -> Tuple[str, str]:
        lvl = (level or "OK").strip().upper()
        if lvl == "OK":
            return "OK", theme.ACCENT_GREEN
        if lvl in {"WARNING", "WARN"}:
            return "WARN", theme.ACCENT_YELLOW
        if lvl == "FATAL":
            return "FATAL", theme.ACCENT_RED
        return lvl[:5], theme.TEXT_MUTED

    def update_sensor_health(self, payload: Dict[str, Any]) -> None:
        """Refresh sensor rows from AppState wire dict (may be partial)."""
        for hid, badge_lbl, metric_lbl in self._sensor_rows:
            row = payload.get(hid) if isinstance(payload, dict) else None
            if not isinstance(row, dict):
                badge_lbl.setText("—")
                badge_lbl.setStyleSheet(
                    f"font-size: {theme.FONT_XS}px; font-family: monospace; "
                    f"font-weight: bold; color: {theme.TEXT_MUTED}; min-width: 44px;"
                )
                metric_lbl.setText("—")
                continue
            st = sensor_status_from_payload(row)
            text, color = self._badge_for_level(st.level)
            badge_lbl.setText(text)
            badge_lbl.setStyleSheet(
                f"font-size: {theme.FONT_XS}px; font-family: monospace; "
                f"font-weight: bold; color: {color}; min-width: 44px;"
            )
            metric_lbl.setText("")

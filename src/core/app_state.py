"""Observable application state container.

Centralizes all live telemetry / system state and exposes Qt signals
so any component can subscribe to changes independently, without routing
everything through MainWindow.
"""

from typing import Optional

from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    """Single source of truth for runtime state.

    Controllers write into the state via setter methods.
    UI components connect to the signals for reactive updates.
    """

    mqtt_changed = Signal(bool)
    battery_changed = Signal(float)
    position_changed = Signal(float, float, float, float)  # x, y, theta_deg, speed
    mode_changed = Signal(str)
    sensor_diag_changed = Signal(str)
    error_changed = Signal(str)
    robot_id_changed = Signal(str)
    status_line_changed = Signal(str)  # composed "IMU: OK | BAT: 85% | MQTT: OK"

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._mqtt_ok: bool = False
        self._battery_pct: Optional[float] = None
        self._sensor_diag: str = "--"
        self._operating_mode: Optional[str] = None
        self._last_error: Optional[str] = None

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
        self, x: float, y: float, theta_deg: float, speed_mps: float
    ) -> None:
        self.position_changed.emit(x, y, theta_deg, speed_mps)

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

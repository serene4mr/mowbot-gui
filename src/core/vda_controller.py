"""VDA 5050 controller: owns bridge lifecycle and maps bridge signals → AppState.

Keeps MainWindow free from MQTT wiring, formatting, and transport concerns.
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import QObject

from core.app_state import AppState
from core.vda_bridge import VDA5050BridgeThread
from utils.logger import logger


class VDAController(QObject):
    """Mediator between VDA5050BridgeThread and the application state model."""

    def __init__(
        self,
        config: Dict[str, Any],
        app_state: AppState,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._state = app_state
        self._config = config
        self._bridge: Optional[VDA5050BridgeThread] = None
        self._start()

    # ── Lifecycle ─────────────────────────────────────────────

    def _start(self) -> None:
        g = self._config.get("general", {})
        b = self._config.get("broker", {})
        host = str(b.get("host", "localhost"))
        port = int(b.get("port", 1883))
        serial = str(g.get("serial_number", "default"))
        manufacturer = str(g.get("manufacturer", "MowbotTech"))

        self._bridge = VDA5050BridgeThread(
            host=host,
            port=port,
            serial_number=serial,
            manufacturer=manufacturer,
        )

        self._bridge.connection_status.connect(self._state.set_mqtt)
        self._bridge.battery_updated.connect(self._state.set_battery)
        self._bridge.position_updated.connect(self._state.set_position)
        self._bridge.mode_updated.connect(self._state.set_mode)
        self._bridge.sensor_diag_updated.connect(self._state.set_sensor_diag)
        self._bridge.error_updated.connect(self._state.set_error)
        self._bridge.start()

        logger.info(
            f"[VDA] Bridge started → {host}:{port} "
            f"(serial={serial}, manufacturer={manufacturer})"
        )

    def stop(self) -> None:
        if self._bridge is not None:
            self._bridge.stop()
            self._bridge = None

    # ── Commands (UI → MQTT) ──────────────────────────────────

    def trigger_estop(self) -> None:
        if self._bridge is not None:
            self._bridge.trigger_estop()

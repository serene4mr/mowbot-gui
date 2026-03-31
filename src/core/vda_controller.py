"""VDA 5050 controller: owns bridge lifecycle and maps bridge signals → AppState.

Keeps MainWindow free from MQTT wiring, formatting, and transport concerns.
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import QObject

from vda5050.models.order import Order

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
        self._bridge.driving_status.connect(self._state.set_driving)
        self._bridge.safety_updated.connect(self._state.set_estop)
        self._bridge.paused_updated.connect(self._state.set_paused)
        self._bridge.action_states_updated.connect(self._state.set_action_states)
        self._bridge.sensor_diag_updated.connect(self._state.set_sensor_diag)
        self._bridge.error_updated.connect(self._state.set_error)
        self._bridge.navigation_failed.connect(self._on_navigation_failed)
        self._bridge.order_sent.connect(self._forward_order_result)
        self._bridge.mission_progress.connect(self._state.set_mission_progress)
        self._bridge.start()

        logger.info(
            f"[VDA] Bridge started → {host}:{port} "
            f"(serial={serial}, manufacturer={manufacturer})"
        )

    def _forward_order_result(self, ok: bool, detail: str, total_nodes: int) -> None:
        if ok and total_nodes > 0:
            self._state.set_active_order(detail, total_nodes)
        self._state.order_dispatched.emit(ok, detail, total_nodes)

    def _on_navigation_failed(self, description: str, hint: str) -> None:
        detail = str(description or "Navigation failed").strip()
        if hint:
            detail = f"{detail} ({hint})"
        self._state.set_mission_failed(detail)

    def stop(self) -> None:
        if self._bridge is not None:
            self._bridge.stop()
            self._bridge = None

    # ── Commands (UI → MQTT) ──────────────────────────────────

    def trigger_estop(self) -> None:
        if self._bridge is not None:
            self._bridge.trigger_estop()

    def send_cancel_order(self) -> None:
        if self._bridge is not None:
            self._bridge.send_cancel_order()

    def send_start_pause(self) -> None:
        if self._bridge is not None:
            self._bridge.send_start_pause()

    def send_stop_pause(self) -> None:
        if self._bridge is not None:
            self._bridge.send_stop_pause()

    def send_path_order(self, order: Order) -> None:
        if self._bridge is not None:
            self._bridge.send_order(order)

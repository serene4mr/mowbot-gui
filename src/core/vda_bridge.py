"""QThread running an asyncio VDA 5050 MasterControlClient.

Emits Qt signals for every piece of AGV telemetry so the GUI can
react without touching the MQTT layer directly.
"""

import asyncio
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import QThread, Signal

from vda5050.clients.master_control import MasterControlClient
from vda5050.models.state import State
from vda5050.models.base import Action, BlockingType
from vda5050.models.instant_action import InstantActions
from vda5050.models.order import Order
from utils.logger import logger


class VDA5050BridgeThread(QThread):
    connection_status = Signal(bool)
    order_sent = Signal(bool, str, int)  # success, order_id or error detail, total_nodes (0 if fail)
    mission_progress = Signal(
        str, int, str, int, int, bool
    )  # orderId, orderUpdateId, lastNodeId, lastNodeSequenceId, len(nodeStates), driving
    battery_updated = Signal(float)
    position_updated = Signal(float, float, float, float)  # x, y, theta_deg, speed
    mode_updated = Signal(str)
    driving_status = Signal(bool)
    safety_updated = Signal(str)
    sensor_diag_updated = Signal(str)
    error_updated = Signal(str)

    def __init__(
        self,
        host: str,
        port: int,
        serial_number: str,
        manufacturer: str = "MowbotTech",
    ):
        super().__init__()
        self.host = host
        self.port = port
        self.serial_number = serial_number
        self.manufacturer = manufacturer

        self.client: Optional[MasterControlClient] = None
        self._is_running = True
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._logged_first_state = False

    # ── Thread entry / exit ───────────────────────────────────

    def run(self) -> None:
        """Executed in the background thread by QThread.start()."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as exc:
            if self._is_running:
                logger.error(f"[VDA] Event loop error: {exc}")
        finally:
            self._cleanup_loop()

    def _cleanup_loop(self) -> None:
        """Cancel remaining async tasks and close the loop cleanly."""
        if self._loop is None:
            return
        try:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        except RuntimeError:
            pass
        finally:
            self._loop.close()
            self._loop = None

    def stop(self) -> None:
        """Gracefully shut down from the main thread."""
        self._is_running = False
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if not self.wait(5000):
            logger.warning("[VDA] Bridge thread did not stop in time; terminating")
            self.terminate()

    # ── Async core ────────────────────────────────────────────

    async def _async_main(self) -> None:
        self.client = MasterControlClient(
            broker_url=self.host,
            manufacturer=self.manufacturer,
            serial_number=f"gui-master-{self.serial_number}",
            broker_port=self.port,
            validate_messages=False,
        )
        self.client.on_state_update(self._on_state_received)

        try:
            logger.info(f"Connecting to MQTT broker {self.host}:{self.port}")
            success = await self.client.connect()
            self.connection_status.emit(success)

            while self._is_running:
                await asyncio.sleep(0.5)
        except Exception as exc:
            logger.error(f"Connection error: {exc}")
            self.connection_status.emit(False)
        finally:
            if self.client and self.client.is_connected():
                await self.client.disconnect()

    # ── State callback ────────────────────────────────────────

    @staticmethod
    def _norm_serial(s: str) -> str:
        return (s or "").strip().lower()

    def _on_state_received(self, serial: str, state: State) -> None:
        if self._norm_serial(serial) != self._norm_serial(self.serial_number):
            return

        if not self._logged_first_state:
            ap = state.agvPosition
            logger.info(
                "[VDA Bridge] First state received: "
                f"agvPosition={'yes' if ap else 'no'}, "
                f"positionInitialized="
                f"{getattr(ap, 'positionInitialized', None) if ap else 'n/a'}"
            )
            self._logged_first_state = True

        if state.batteryState:
            self.battery_updated.emit(state.batteryState.batteryCharge)

        ap = state.agvPosition
        if ap is not None and ap.positionInitialized:
            theta_deg = math.degrees(ap.theta) if ap.theta is not None else 0.0
            vx = vy = 0.0
            if state.velocity is not None:
                vx = state.velocity.vx or 0.0
                vy = state.velocity.vy or 0.0
            self.position_updated.emit(ap.x, ap.y, theta_deg, math.hypot(vx, vy))

        if state.operatingMode:
            self.mode_updated.emit(state.operatingMode.value)

        self.driving_status.emit(state.driving)

        if state.safetyState:
            self.safety_updated.emit(state.safetyState.eStop.value)

        if state.information:
            for info in state.information:
                if (
                    getattr(info, "infoType", "") == "SENSOR_DIAG"
                    and getattr(info, "infoDescription", None)
                ):
                    self.sensor_diag_updated.emit(info.infoDescription)
                    break

        if state.errors:
            fatal = [e for e in state.errors if e.errorLevel.value == "FATAL"]
            if fatal:
                self.error_updated.emit(f"FATAL: {fatal[0].errorDescription}")
            else:
                self.error_updated.emit(
                    f"WARNING: {state.errors[0].errorDescription}"
                )
        else:
            self.error_updated.emit("ALL CLEAR")

        ns = state.nodeStates or []
        self.mission_progress.emit(
            state.orderId or "",
            int(state.orderUpdateId or 0),
            state.lastNodeId or "",
            int(state.lastNodeSequenceId or 0),
            len(ns),
            bool(state.driving),
        )

    # ── Commands (GUI → MQTT) ─────────────────────────────────

    def trigger_estop(self) -> None:
        if self._loop and self.client:
            asyncio.run_coroutine_threadsafe(self._send_estop(), self._loop)

    def send_order(self, order: Order) -> None:
        if self._loop and self.client:
            asyncio.run_coroutine_threadsafe(self._publish_order(order), self._loop)
        else:
            self.order_sent.emit(False, "MQTT client not ready", 0)

    async def _publish_order(self, order: Order) -> None:
        try:
            ok = await self.client.send_order(
                target_manufacturer=self.manufacturer,
                target_serial=self.serial_number,
                order=order,
            )
            if ok:
                logger.info(f"[VDA Bridge] Order published: {order.orderId}")
                self.order_sent.emit(True, order.orderId, len(order.nodes))
            else:
                logger.error("[VDA Bridge] send_order returned False")
                self.order_sent.emit(False, "send_order returned False", 0)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[VDA Bridge] send_order failed")
            self.order_sent.emit(False, str(exc), 0)

    async def _send_estop(self) -> None:
        logger.warning("Initiating Emergency Stop sequence")
        action = Action(
            actionType="emergencyStop",
            actionId=str(uuid.uuid4()),
            blockingType=BlockingType.HARD,
            actionParameters=[],
        )
        msg = InstantActions(
            headerId=int(datetime.now().timestamp()),
            timestamp=datetime.now(timezone.utc),
            version="2.1.0",
            manufacturer=self.manufacturer,
            serialNumber=self.serial_number,
            actions=[action],
        )
        await self.client.send_instant_action(
            target_manufacturer=self.manufacturer,
            target_serial=self.serial_number,
            action=msg,
        )

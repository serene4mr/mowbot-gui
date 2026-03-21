# src/core/vda_bridge.py
import asyncio
import math
import uuid
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

# Import directly from your custom VDA 5050 package
from vda5050.clients.master_control import MasterControlClient
from vda5050.models.state import State
from vda5050.models.base import Action, BlockingType
from vda5050.models.instant_action import InstantActions
from utils.logger import logger

class VDA5050BridgeThread(QThread):
    # ==========================================
    # SIGNALS: Safely transmit data to the GUI
    # ==========================================
    connection_status = Signal(bool)
    battery_updated = Signal(float)
    # x, y, theta_deg (for HUD), speed_m/s (planar from velocity vx/vy)
    position_updated = Signal(float, float, float, float)
    mode_updated = Signal(str)                     # e.g., 'AUTOMATIC', 'MANUAL'
    driving_status = Signal(bool)                  # True if moving, False if stopped
    safety_updated = Signal(str)                   # e.g., 'NONE', 'AUTOACK', 'MANUAL'
    error_updated = Signal(str)                    # Contains the most severe error description

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
        
        self.client = None
        self._is_running = True
        self._loop = None
        self._logged_first_state = False

    def run(self):
        """Executed automatically by QThread. Runs in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        # Start the async MQTT logic
        self._loop.run_until_complete(self._async_main())
        
        # Cleanup when thread stops
        self._loop.close()

    async def _async_main(self):
        """Asynchronous entry point for the VDA5050 MasterControlClient."""
        self.client = MasterControlClient(
            broker_url=self.host,
            manufacturer=self.manufacturer,
            serial_number=f"gui-master-{self.serial_number}",
            broker_port=self.port,
            validate_messages=False
        )

        # Register the callback for incoming state messages
        self.client.on_state_update(self._on_state_received)

        try:
            logger.info(f"Connecting to MQTT broker {self.host}:{self.port}")
            success = await self.client.connect()
            self.connection_status.emit(success)

            # Keep the async loop alive
            while self._is_running:
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.connection_status.emit(False)
        finally:
            if self.client and self.client.is_connected():
                await self.client.disconnect()

    @staticmethod
    def _norm_serial(s: str) -> str:
        return (s or "").strip().lower()

    def _on_state_received(self, serial: str, state: State):
        """
        Callback triggered by the vda5050_client. 
        'state' is the validated Pydantic model containing all AGV telemetry.
        """
        if self._norm_serial(serial) != self._norm_serial(self.serial_number):
            return

        if not self._logged_first_state:
            ap = state.agvPosition
            logger.info(
                "[VDA Bridge] First state received: "
                f"agvPosition={'yes' if ap else 'no'}, "
                f"positionInitialized={getattr(ap, 'positionInitialized', None) if ap else 'n/a'}"
            )
            self._logged_first_state = True

        # 1. Battery State
        if state.batteryState:
            self.battery_updated.emit(state.batteryState.batteryCharge)

        # 2. Position + speed for HUD
        ap = state.agvPosition
        if ap is not None and ap.positionInitialized:
            theta_rad = ap.theta
            theta_deg = math.degrees(theta_rad) if theta_rad is not None else 0.0
            vx = vy = 0.0
            if state.velocity is not None:
                vx = state.velocity.vx or 0.0
                vy = state.velocity.vy or 0.0
            speed = math.hypot(vx, vy)
            self.position_updated.emit(ap.x, ap.y, theta_deg, speed)

        # 3. Operating Mode
        if state.operatingMode:
            self.mode_updated.emit(state.operatingMode.value)

        # 4. Driving Status
        self.driving_status.emit(state.driving)

        # 5. Safety & E-Stop Status
        if state.safetyState:
            self.safety_updated.emit(state.safetyState.eStop.value)

        # 6. Error Handling
        if state.errors:
            # Prioritize FATAL errors for the GUI warning banner
            fatal_errors = [e for e in state.errors if e.errorLevel.value == 'FATAL']
            if fatal_errors:
                self.error_updated.emit(f"FATAL: {fatal_errors[0].errorDescription}")
            else:
                self.error_updated.emit(f"WARNING: {state.errors[0].errorDescription}")
        else:
            self.error_updated.emit("ALL CLEAR")

    def stop(self):
        """Gracefully shuts down the background thread."""
        self._is_running = False
        self.wait()

    # ==========================================
    # COMMANDS (GUI -> MQTT Broker)
    # ==========================================
    def trigger_estop(self):
        """Called from the Main UI Thread to dispatch an action asynchronously."""
        if self._loop and self.client:
            asyncio.run_coroutine_threadsafe(self._send_estop_async(), self._loop)

    async def _send_estop_async(self):
        """Constructs and sends the VDA5050 InstantAction for E-STOP."""
        logger.warning("Initiating Emergency Stop sequence")
        
        # 'stop' is a standardized actionType in VDA 5050
        action = Action(
            actionType="stop", 
            actionId=str(uuid.uuid4()),
            blockingType=BlockingType.HARD,
            actionParameters=[]
        )
        
        # Construct the payload
        instant_actions_msg = InstantActions(
            headerId=int(datetime.now().timestamp()), # Ensure uniqueness
            timestamp=datetime.now(timezone.utc),
            version="2.1.0",
            manufacturer=self.manufacturer,
            serialNumber=self.serial_number,
            actions=[action]
        )
        
        # Publish via the custom package
        await self.client.send_instant_action(
            target_manufacturer=self.manufacturer,
            target_serial=self.serial_number,
            action=instant_actions_msg
        )
# src/core/vda_bridge.py
import asyncio
import uuid
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

# Import directly from your custom VDA 5050 package
from vda5050.clients.master_control import MasterControlClient
from vda5050.models.state import State
from vda5050.models.base import Action, BlockingType
from vda5050.models.instant_action import InstantActions

class VDA5050BridgeThread(QThread):
    # ==========================================
    # SIGNALS: Safely transmit data to the GUI
    # ==========================================
    connection_status = Signal(bool)
    battery_updated = Signal(float)
    position_updated = Signal(float, float, float) # x, y, theta
    mode_updated = Signal(str)                     # e.g., 'AUTOMATIC', 'MANUAL'
    driving_status = Signal(bool)                  # True if moving, False if stopped
    safety_updated = Signal(str)                   # e.g., 'NONE', 'AUTOACK', 'MANUAL'
    error_updated = Signal(str)                    # Contains the most severe error description

    def __init__(self, host: str, port: int, serial_number: str):
        super().__init__()
        self.host = host
        self.port = port
        self.serial_number = serial_number
        self.manufacturer = "jisan"
        
        self.client = None
        self._is_running = True
        self._loop = None

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
            print(f"[VDA Bridge] Connecting to MQTT Broker {self.host}:{self.port}...")
            await self.client.connect()
            self.connection_status.emit(True)

            # Keep the async loop alive
            while self._is_running:
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[VDA Bridge] Connection Error: {e}")
            self.connection_status.emit(False)
        finally:
            if self.client and self.client.is_connected():
                await self.client.disconnect()

    def _on_state_received(self, serial: str, state: State):
        """
        Callback triggered by the vda5050_client. 
        'state' is the validated Pydantic model containing all AGV telemetry.
        """
        if serial != self.serial_number:
            return

        # 1. Battery State
        if state.batteryState:
            self.battery_updated.emit(state.batteryState.batteryCharge)
            
        # 2. Position (Only emit if initialized)
        if state.agvPosition and getattr(state.agvPosition, 'positionInitialized', False):
            x = state.agvPosition.x
            y = state.agvPosition.y
            theta = getattr(state.agvPosition, 'theta', 0.0)
            self.position_updated.emit(x, y, theta)

        # 3. Operating Mode
        if state.operatingMode:
            self.mode_updated.emit(state.operatingMode.value)

        # 4. Driving Status
        self.driving_status.emit(state.driving)

        # 5. Safety & E-Stop Status
        if state.safetyState:
            self.safety_updated.emit(state.safetyState.eStop.value)

        # 6. Error Handling
        if state.errors and len(state.errors) > 0:
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
        print("[VDA Bridge] Initiating Emergency Stop Sequence...")
        
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
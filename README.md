# mowbot-gui

## Local MQTT broker (see the VDA bridge work)

Config is merged from `config/config_default.yaml`, optional `config/config_local.yaml`, and env vars (see `src/utils/config.py`).

1. **Run a broker** on the host (matches defaults `localhost:1883`):

   ```bash
   # Debian/Ubuntu example
   sudo apt install mosquitto
   sudo systemctl start mosquitto
   ```

   Or use Docker: `docker run --rm -p 1883:1883 eclipse-mosquitto:2`

2. **Run the GUI** from the repo (with `src` on `PYTHONPATH`, e.g. run from `src/`):

   ```bash
   cd src && python main.py
   ```

3. **What you should see**
   - Console: `[VDA Bridge] Connecting to MQTT Broker localhost:1883...` then `[MQTT] connected` if the broker accepts the connection.
   - Top bar status line: `MQTT: OK` (or `OFF` if the broker is down / wrong host).

4. **Live telemetry (battery / position HUD)** only updates when a **VDA 5050 state** is published for the same **robot serial** as `general.serial_number` in config (default `mowbot_001`). Override in `config/config_local.yaml` if needed.

### LAN / lab test (broker not on localhost)

Default deploy uses **`localhost:1883`**. To point at a broker on another host (e.g. `192.168.1.9` during testing):

```bash
MOWBOT_MQTT_HOST=192.168.1.9 cd src && python main.py
```

Or create `config/config_local.yaml`:

```yaml
broker:
  host: "192.168.1.9"
```

5. **E-STOP** in the UI calls `VDA5050BridgeThread.trigger_estop()` (MQTT instant action), assuming the bridge is connected.

### MQTT shows OK but telemetry / BAT stay `--`

- **Serial** in config must match the topic segment (case-insensitive after the fix). Example: `uagv/v2/MowbotTech/mowbot_001/state` → `serial_number: "mowbot_001"`.
- **Position** is only sent if `state.agvPosition` exists. If your AGV leaves `positionInitialized: false`, the bridge still updates when **`MOWBOT_RELAX_POSITION_INITIALIZED`** is enabled (default **`1`** / on). Set to **`0`** to require a true initialized flag.
- **Theta** is converted from **radians (VDA)** to **degrees** for the HUD.
- **Speed** uses planar speed from `state.velocity` vx/vy (m/s) when present.

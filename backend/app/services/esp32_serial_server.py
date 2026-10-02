import asyncio
import json
import logging
import serial_asyncio
import glob
import sys
import os
from datetime import datetime, timezone
from app.services.device_state_manager import get_device_state_manager
from app.websockets.manager import websocket_manager
from app.schemas.router import ConnectedDevice

logger = logging.getLogger("signalsense.esp32_serial")

class ESP32SerialServer:
    def __init__(self, baudrate=115200):
        self.baudrate = baudrate
        self.state_manager = get_device_state_manager()
        self._running = False
        self._task = None
        self._reader = None

    def _find_serial_port(self):
        """Scans for available serial ports to find the ESP32."""
        port = os.getenv("ESP32_SERIAL_PORT")
        if port and os.path.exists(port):
            return port

        if sys.platform.startswith('win'):
            ports = [f'COM{i}' for i in range(1, 256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        # Just return the first available one that doesn't error out on open,
        # but for simplicity, we return the first found in the list.
        if ports:
            return ports[0]
            
        return None

    async def _process_payload(self, data: str):
        try:
            payload = json.loads(data)
            
            mac = payload.get("mac_address", "00:00:00:00:00:00").upper()
            
            # Since the ESP32 is sniffing other devices, we don't know their IP/Hostname from raw packets
            # We set them to None (or placeholder) so device_state_manager preserves the original router metadata!
            ip = payload.get("ip_address", "0.0.0.0")
            hostname = payload.get("device_id", None)
            rssi = payload.get("rssi")
            channel = payload.get("wifi_channel")
            status = payload.get("status", "online")
            tx_rate = payload.get("tx_rate")
            rx_rate = payload.get("rx_rate")
            
            if rssi is None:
                return
                
            # SECURITY/FILTERING FIX:
            # The ESP32 Promiscuous mode sniffs EVERY packet in the air (neighbors, passing phones, etc).
            # We ONLY want to update devices that are ACTUALLY connected to the user's router.
            # If the MAC is not known to the DeviceStateManager (which gets its source of truth from the Router),
            # we simply ignore the sniffed packet.
            
            with open("/tmp/signalsense_esp32_debug.log", "a") as f:
                f.write(f"Sniffed MAC: {mac} | RSSI: {rssi} | Known: {mac in self.state_manager.active_devices}\n")
                
            if mac not in self.state_manager.active_devices:
                return
                
            # Prevent the ESP32 radar from updating its own distance (so it remains a stable, stationary point)
            device_in_state = self.state_manager.active_devices[mac]
            if device_in_state.hostname and "ESP32" in device_in_state.hostname.upper():
                return
                
            # Create a partial ConnectedDevice payload for the state manager
            device = ConnectedDevice(
                mac_address=mac,
                ip_address=ip,
                hostname=hostname,
                device_type=None, # Leave None to preserve router's device_type
                connection_state="connected" if status == "online" else "disconnected",
                rssi=int(rssi),
                signal_quality=None,
                tx_rate=tx_rate,
                rx_rate=rx_rate,
                last_seen=datetime.now(timezone.utc)
            )
            
            # Publish to TelemetryEventBus for the calibration engine and logging
            from app.events.bus import get_telemetry_bus, TelemetryEvent
            event = TelemetryEvent(
                topic="rssi_scan",
                source_id=f"esp32_{ip}",
                payload={"target_mac": mac, "rssi": rssi}
            )
            get_telemetry_bus().publish(event)
            
            # Pass to state manager to update UI
            changed_devices = self.state_manager.process_router_update([device], is_full_sync=False)
            
            if changed_devices:
                for dev in changed_devices:
                    if dev.mac_address == mac:
                        # Direct WebSocket Broadcast for real-time <100ms updates
                        payload_dump = {
                            "timestamp": dev.last_seen.isoformat(),
                            "mac_address": dev.mac_address,
                            "ip_address": dev.ip_address,
                            "device_type": dev.device_type,
                            "manufacturer": dev.manufacturer,
                            "hostname": dev.hostname,
                            "current_rssi": dev.current_rssi.model_dump() if hasattr(dev.current_rssi, 'model_dump') else dev.current_rssi,
                            "previous_rssi": dev.previous_rssi,
                            "moving_average_rssi": dev.moving_average_rssi,
                            "signal_quality": dev.signal_quality,
                            "distance": dev.distance.model_dump() if hasattr(dev.distance, 'model_dump') else dev.distance,
                            "direction": dev.direction.model_dump() if hasattr(dev.direction, 'model_dump') else dev.direction,
                            "movement": dev.movement.model_dump() if hasattr(dev.movement, 'model_dump') else dev.movement,
                            "signal_classification": dev.signal_classification.value if getattr(dev, 'signal_classification', None) else "Unknown",
                            "distance_classification": dev.distance_classification.value if getattr(dev, 'distance_classification', None) else "Unknown",
                            "signal_trend": dev.signal_trend.value if getattr(dev, 'signal_trend', None) else "None",
                            "animation_state": dev.animation_state.model_dump() if getattr(dev, 'animation_state', None) else {},
                            "online_status": bool(getattr(dev, 'online_status', False)),
                        }
                        await websocket_manager.broadcast_event("device_updated", [payload_dump])

        except json.JSONDecodeError:
            pass # Ignore incomplete or non-JSON serial prints
        except Exception as e:
            logger.error(f"Error processing ESP32 serial data: {e}")

    async def _serial_loop(self):
        port = self._find_serial_port()
        if not port:
            logger.warning("No ESP32 Serial Port found (Checked /dev/ttyUSB*, /dev/ttyACM*). Retrying later...")
            await asyncio.sleep(5)
            if self._running:
                self._task = asyncio.create_task(self._serial_loop())
            return
            
        logger.info(f"Starting ESP32 USB Serial Server on {port} @ {self.baudrate}")
        try:
            reader, writer = await serial_asyncio.open_serial_connection(url=port, baudrate=self.baudrate)
            self._reader = reader
            while self._running:
                line = await reader.readline()
                if not line:
                    break
                decoded_line = line.decode('utf-8', errors='ignore').strip()
                if decoded_line.startswith("{") and decoded_line.endswith("}"):
                    await self._process_payload(decoded_line)
                    
        except Exception as e:
            logger.error(f"ESP32 Serial connection error on {port}: {e}")
            if self._running:
                logger.info("Will attempt to reconnect serial in 5 seconds...")
                await asyncio.sleep(5)
                self._task = asyncio.create_task(self._serial_loop())

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._serial_loop())
        logger.info("ESP32 USB Serial Server initialized")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Stopped ESP32 USB Serial Server")

_esp32_serial_server_singleton = ESP32SerialServer()

def get_esp32_serial_server():
    return _esp32_serial_server_singleton

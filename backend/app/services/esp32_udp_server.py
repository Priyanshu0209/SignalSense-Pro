import asyncio
import json
import logging
from datetime import datetime, timezone
from app.services.device_state_manager import get_device_state_manager
from app.websockets.manager import websocket_manager
from app.schemas.router import ConnectedDevice

logger = logging.getLogger("signalsense.esp32_server")

class ESP32DataProcessor:
    def __init__(self):
        self.state_manager = get_device_state_manager()
        
    async def process_payload(self, addr, data: bytes):
        try:
            payload = json.loads(data.decode('utf-8'))
            
            mac = payload.get("mac_address", "00:00:00:00:00:00").upper()
            ip = payload.get("ip_address", addr[0])
            hostname = payload.get("device_id", "ESP32-Node")
            rssi = payload.get("rssi")
            channel = payload.get("wifi_channel")
            status = payload.get("status")
            tx_rate = payload.get("tx_rate")
            rx_rate = payload.get("rx_rate")
            
            if rssi is None:
                return
                
            # Treat the ESP32 as a ConnectedDevice from the Router's perspective
            device = ConnectedDevice(
                mac_address=mac,
                ip_address=ip,
                hostname=hostname,
                device_type="esp32_sensor",
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
            # Create a background task so we don't block UDP processing
            asyncio.create_task(get_telemetry_bus().publish(event))
            
            # Push directly to device state manager
            # We use a list because process_router_update expects a list of ConnectedDevice
            # IMPORTANT: We pass is_full_sync=False so that other active router clients are not marked offline.
            changed_devices = self.state_manager.process_router_update([device], is_full_sync=False)
            
            # If it's processed and we get a ProcessedDeviceState back, broadcast it immediately!
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
                            "signal_quality": dev.signal_quality,
                            "distance": dev.distance.model_dump() if hasattr(dev.distance, 'model_dump') else dev.distance,
                            "direction": dev.direction.model_dump() if hasattr(dev.direction, 'model_dump') else dev.direction,
                            "movement": dev.movement.model_dump() if hasattr(dev.movement, 'model_dump') else dev.movement,
                            "signal_classification": dev.signal_classification.value if getattr(dev, 'signal_classification', None) else "Unknown",
                            "distance_classification": dev.distance_classification.value if getattr(dev, 'distance_classification', None) else "Unknown",
                            "signal_trend": dev.signal_trend.value if getattr(dev, 'signal_trend', None) else "None",
                            "animation_state": dev.animation_state.model_dump() if getattr(dev, 'animation_state', None) else {},
                            "online_status": bool(getattr(dev, 'online_status', False)),
                            "connection_duration": getattr(dev, 'connection_duration', 0),
                            "twin_mode": getattr(dev, 'twin_mode', "REAL"),
                            "tx_rate": dev.tx_rate,
                            "rx_rate": dev.rx_rate
                        }
                        
                        # High-frequency direct broadcast channel for the dashboard and calibration studio
                        await websocket_manager.broadcast_event("esp32_telemetry", payload_dump)
                        
        except json.JSONDecodeError:
            logger.debug(f"Invalid JSON received from {addr}")
        except Exception as e:
            logger.error(f"Error processing ESP32 telemetry: {e}")

class ESP32UDPServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, processor: ESP32DataProcessor):
        self.processor = processor

    def connection_made(self, transport):
        self.transport = transport
        logger.info("ESP32 UDP Server is up and listening")

    def datagram_received(self, data, addr):
        # We must schedule the async processing since datagram_received is sync
        asyncio.create_task(self.processor.process_payload(addr, data))

class ESP32ServerManager:
    def __init__(self, host="0.0.0.0", port=8002):
        self.host = host
        self.port = port
        self.processor = ESP32DataProcessor()
        self.transport = None
        
    async def start(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: ESP32UDPServerProtocol(self.processor),
            local_addr=(self.host, self.port)
        )
        logger.info(f"Started ESP32 Telemetry UDP Server on {self.host}:{self.port}")

    async def stop(self):
        if self.transport:
            self.transport.close()
            logger.info("Stopped ESP32 Telemetry UDP Server")

esp32_server_singleton = ESP32ServerManager()

def get_esp32_server() -> ESP32ServerManager:
    return esp32_server_singleton

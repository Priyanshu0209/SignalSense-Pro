import asyncio
import struct
import math
import logging
from typing import Dict, List, Any
import time

logger = logging.getLogger("signalsense.csi_server")

class CSIDataProcessor:
    def __init__(self):
        self.latest_csi_by_mac: Dict[str, Dict[str, Any]] = {}
        
    def get_latest_csi(self, mac: str) -> Dict[str, Any]:
        return self.latest_csi_by_mac.get(mac)
        
    def process_payload(self, addr, data: bytes):
        if len(data) < 7:
            return
            
        mac_bytes = data[0:6]
        mac = ":".join(f"{b:02X}" for b in mac_bytes)
        rssi = struct.unpack("b", data[6:7])[0]
        
        csi_payload = data[7:]
        # CSI data is typically int8 imaginary, int8 real pairs
        if len(csi_payload) % 2 != 0:
            return
            
        num_subcarriers = len(csi_payload) // 2
        amplitudes = []
        phases = []
        
        for i in range(num_subcarriers):
            imag = struct.unpack("b", csi_payload[i*2 : i*2+1])[0]
            real = struct.unpack("b", csi_payload[i*2+1 : i*2+2])[0]
            
            # Calculate Amplitude and Phase
            amplitude = math.sqrt(real**2 + imag**2)
            phase = math.atan2(imag, real)
            
            amplitudes.append(round(amplitude, 3))
            phases.append(round(phase, 3))
            
        # For Device-Free Sensing (1 Router + 1 ESP32), the person doesn't carry a device.
        # The CSI represents the entire room's channel state.
        # We assign a unique MAC for EACH ESP32 node based on its source MAC!
        # mac is the ESP32 MAC from the UDP packet
        virtual_mac = mac
        
        payload_dict = {
            "target_mac": virtual_mac,
            "rssi": rssi,
            "amplitudes": amplitudes,
            "phases": phases,
            "subcarriers": num_subcarriers
        }
        self.latest_csi_by_mac[virtual_mac] = payload_dict
        
        

        # Send to collector (we will modify MotionActivityEngine to use this later)
        try:
            from app.events.bus import get_telemetry_bus, TelemetryEvent
            event = TelemetryEvent(
                topic="csi_matrix",
                source_id="esp32_csi_node",
                payload=payload_dict
            )
            asyncio.create_task(get_telemetry_bus().publish(event))
        except Exception as e:
            logger.error(f"Failed to publish CSI event: {e}")

class CSIUDPServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, processor: CSIDataProcessor):
        self.processor = processor

    def connection_made(self, transport):
        self.transport = transport
        logger.info("CSI UDP Server is up and listening")

    def datagram_received(self, data, addr):
        try:
            self.processor.process_payload(addr, data)
        except Exception as e:
            logger.error(f"Error processing CSI UDP packet: {e}")

class CSIServerManager:
    def __init__(self, host="0.0.0.0", port=8001):
        self.host = host
        self.port = port
        self.processor = CSIDataProcessor()
        self.transport = None
        self.task = None
        
    async def start(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: CSIUDPServerProtocol(self.processor),
            local_addr=(self.host, self.port)
        )
        logger.info(f"Started CSI UDP Server on {self.host}:{self.port}")

    async def stop(self):
        if self.transport:
            self.transport.close()
            logger.info("Stopped CSI UDP Server")

csi_server_singleton = CSIServerManager()

def get_csi_server() -> CSIServerManager:
    return csi_server_singleton

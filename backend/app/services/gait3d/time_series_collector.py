import asyncio
import logging
import time
import math
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from collections import deque

from app.services.device_state_manager import get_device_state_manager

logger = logging.getLogger("signalsense.gait3d.collector")

class GaitTimeSeriesCollector:

    def __init__(self, buffer_max_size: int = 400, sample_rate_hz: float = 20.0):
        self.buffer_max_size = buffer_max_size
        self.sample_rate_hz = sample_rate_hz
        self.sample_interval = 1.0 / sample_rate_hz
        
        # MAC Address -> deque of {"timestamp": float, "time_iso": str, "raw_rssi": float, "device_name": str}
        self.buffers: Dict[str, deque] = {}
        self.is_running = False
        self.collection_task: Optional[asyncio.Task] = None

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.collection_task = asyncio.create_task(self._collection_loop())
        logger.info(f"GaitTimeSeriesCollector started at {self.sample_rate_hz}Hz (Real Data Driven Mode).")

    async def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        logger.info("GaitTimeSeriesCollector stopped.")


    def add_sample(self, mac_address: str, rssi: float, device_name: str = "Client Device"):
        if mac_address not in self.buffers:
            self.buffers[mac_address] = deque(maxlen=self.buffer_max_size)
        
        now = time.time()
        self.buffers[mac_address].append({
            "timestamp": now,
            "time_iso": datetime.now(timezone.utc).isoformat(),
            "raw_rssi": round(rssi, 3),
            "device_name": device_name
        })

    def get_device_history(self, mac_address: str) -> List[Dict[str, Any]]:
        if mac_address not in self.buffers:
            return []
        return list(self.buffers[mac_address])

    def get_all_macs(self) -> List[str]:
        return list(self.buffers.keys())

    def get_recent_window(self, mac_address: str, duration_sec: float = 5.0) -> List[Dict[str, Any]]:
        if mac_address not in self.buffers:
            return []
        now = time.time()
        cutoff = now - duration_sec
        return [s for s in self.buffers[mac_address] if s["timestamp"] >= cutoff]

    async def _collection_loop(self):
        try:
            device_mgr = get_device_state_manager()
            while self.is_running:
                start_time = time.time()
                
                # 1. REAL DATA INTEGRATION: Ingest discovered Wi-Fi devices from DeviceStateManager (Source of Truth)
                devices = device_mgr.get_all_devices()
                for dev in devices:
                    if dev.online_status and dev.current_rssi is not None:
                        val = dev.current_rssi.value if hasattr(dev.current_rssi, "value") else dev.current_rssi
                        if val is not None:
                            self.add_sample(dev.mac_address, float(val), dev.hostname or dev.mac_address)

                
                elapsed = time.time() - start_time
                sleep_time = max(0.005, self.sample_interval - elapsed)
                await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in GaitTimeSeriesCollector loop: {e}", exc_info=True)

collector_singleton = GaitTimeSeriesCollector()

def get_gait_time_series_collector() -> GaitTimeSeriesCollector:
    return collector_singleton

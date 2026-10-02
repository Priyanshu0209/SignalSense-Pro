import asyncio
import csv
import os
import time
import logging
from typing import List, Dict, Any, Optional

from app.events.bus import get_telemetry_bus

logger = logging.getLogger("signalsense.services.gait3d.csi_dataset_collector")

class CSIDatasetCollector:
    def __init__(self):
        self.is_recording = False
        self.current_label = ""
        self.samples = []
        self.record_task = None
        self._queue = None
        self._callback = None

    async def start_recording(self, label: str, duration_sec: int) -> Dict[str, Any]:
        if self.is_recording:
            return {"status": "error", "message": "Already recording"}
            
        self.is_recording = True
        self.current_label = label
        self.samples = []
        self._queue = asyncio.Queue()
        
        async def on_csi_event(event):
            if self.is_recording:
                await self._queue.put(event)
                
        self._callback = on_csi_event
        get_telemetry_bus().subscribe("csi_matrix", self._callback)
        
        # We start the background task that will collect the data and stop after duration_sec
        self.record_task = asyncio.create_task(self._record_loop(label, duration_sec))
        
        return {"status": "success", "message": f"Started recording {label} for {duration_sec} seconds"}
        
    async def _record_loop(self, label: str, duration_sec: int):
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration_sec and self.is_recording:
                try:
                    event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                    payload = event.payload
                    
                    rssi = payload.get("rssi", 0)
                    amplitudes = payload.get("amplitudes", [])
                    phases = payload.get("phases", [])
                    
                    # Ensure they are exactly 64 length
                    amps_padded = amplitudes[:64] + [0] * max(0, 64 - len(amplitudes))
                    phases_padded = phases[:64] + [0] * max(0, 64 - len(phases))
                    
                    row = [rssi] + amps_padded + phases_padded + [label]
                    self.samples.append(row)
                    self._queue.task_done()
                    
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            self.is_recording = False
            get_telemetry_bus().unsubscribe("csi_matrix", self._callback)
            self._save_to_csv()
            
    def _save_to_csv(self):
        if not self.samples:
            logger.warning("No CSI samples were collected.")
            return
            
        datasets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "datasets"))
        os.makedirs(datasets_dir, exist_ok=True)
        
        # Save to csi_dataset.csv (append mode)
        filepath = os.path.join(datasets_dir, "csi_dataset.csv")
        file_exists = os.path.isfile(filepath)
        
        try:
            with open(filepath, 'a', newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    headers = ["RSSI"] + [f"Amp_{i}" for i in range(64)] + [f"Phase_{i}" for i in range(64)] + ["Label"]
                    writer.writerow(headers)
                writer.writerows(self.samples)
            logger.info(f"Saved {len(self.samples)} samples to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save CSI dataset: {e}")

    def stop_recording(self) -> Dict[str, Any]:
        if not self.is_recording:
            return {"status": "error", "message": "Not recording"}
            
        self.is_recording = False
        if self.record_task:
            self.record_task.cancel()
            
        return {"status": "success", "message": "Stopped recording and saving to CSV"}
        
    def get_status(self) -> Dict[str, Any]:
        return {
            "is_recording": self.is_recording,
            "label": self.current_label,
            "samples_collected": len(self.samples)
        }

csi_collector_singleton = CSIDatasetCollector()

def get_csi_dataset_collector() -> CSIDatasetCollector:
    return csi_collector_singleton

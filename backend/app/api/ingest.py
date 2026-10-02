from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any
from app.events.bus import get_telemetry_bus, TelemetryEvent

router = APIRouter()

class TelemetryPayload(BaseModel):
    source_id: str
    topic: str
    data: Dict[str, Any]

@router.post("/telemetry")
async def ingest_telemetry(payload: TelemetryPayload):

    try:
        bus = get_telemetry_bus()
        event = TelemetryEvent(
            topic=payload.topic,
            source_id=payload.source_id,
            payload=payload.data
        )
        await bus.publish(event)
        
        # Route RSSI scans directly to the Gait 3D Time Series Collector
        if payload.topic == "rssi_scan":
            from app.services.gait3d.time_series_collector import get_gait_time_series_collector
            collector = get_gait_time_series_collector()
            mac = payload.data.get("target_mac")
            rssi = payload.data.get("rssi")
            if mac and rssi is not None:
                collector.add_sample(mac, float(rssi), "Target Device")

        return {"status": "accepted", "event_id": event.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

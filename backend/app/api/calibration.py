from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.services.calibration_engine import get_calibration_engine, CalibrationSample
from app.services.research.research_manager import get_research_manager
from app.events.bus import get_telemetry_bus
from app.services.rssi_processor import get_rssi_processor_manager
import asyncio
import os
import csv
import time

router = APIRouter()

class CalibrationStartRequest(BaseModel):
    actual_distance: float
    duration_sec: int = 10
    environment: str = "default"
    los_status: str = "LOS"

class CalibrationState:
    is_collecting: bool = False
    samples: List[CalibrationSample] = []
    current_distance: float = 0.0
    environment: str = "default"
    los_status: str = "LOS"
    active_experiment_id: Optional[str] = None
    
calibration_state = CalibrationState()

# Temporary subscriber to collect samples
async def _collect_samples(event):
    if calibration_state.is_collecting:
        rssi = None
        mac = None
        
        if event.topic == "rssi_scan":
            rssi = event.payload.get("rssi")
            mac = event.payload.get("target_mac")
        elif event.topic == "telemetry.device.discovered":
            rssi = event.payload.get("rssi")
            mac = event.payload.get("mac_address")
            
        if rssi is not None and mac is not None:
            raw_rssi = float(rssi)
            processor = get_rssi_processor_manager().processors.get(mac)
            
            # If processor exists, use its metrics, else dummy defaults
            filtered_rssi = raw_rssi
            ema_rssi = raw_rssi
            variance = 0.0
            std_dev = 0.0
            
            if processor:
                ema_rssi = processor.ema if processor.ema is not None else raw_rssi
                filtered_rssi = ema_rssi
                variance = processor.get_variance()
                import math
                std_dev = math.sqrt(variance) if variance > 0 else 0.0

            calibration_state.samples.append(CalibrationSample(
                timestamp=time.time(),
                actual_distance=calibration_state.current_distance,
                rssi=raw_rssi,
                filtered_rssi=filtered_rssi,
                ema_rssi=ema_rssi,
                variance=variance,
                std_dev=std_dev,
                environment=calibration_state.environment,
                los_status=calibration_state.los_status
            ))

async def _collection_task(duration: int):
    # Register subscriber
    bus = get_telemetry_bus()
    bus.subscribe("rssi_scan", _collect_samples)
    bus.subscribe("telemetry.device.discovered", _collect_samples)
    
    await asyncio.sleep(duration)
    
    # End collection
    calibration_state.is_collecting = False
    bus.unsubscribe("rssi_scan", _collect_samples)
    bus.unsubscribe("telemetry.device.discovered", _collect_samples)

@router.post("/start_collection")
async def start_collection(request: CalibrationStartRequest, background_tasks: BackgroundTasks):
    if calibration_state.is_collecting:
        raise HTTPException(status_code=400, detail="Already collecting data.")
        
    calibration_state.is_collecting = True
    calibration_state.current_distance = request.actual_distance
    calibration_state.environment = request.environment
    calibration_state.los_status = request.los_status
    
    # Module 1: Automatically create a new Experiment
    mgr = get_research_manager()
    exp_id = mgr.log_experiment(
        env=request.environment,
        profile_name="collecting",
        router_name="Primary Router",
        router_mac="UNKNOWN",
        esp32_mac="UNKNOWN",
        sample_count=0,
        duration=request.duration_sec,
        status="Running"
    )
    calibration_state.active_experiment_id = exp_id
    
    background_tasks.add_task(_collection_task, request.duration_sec)
    
    return {"status": "started", "duration": request.duration_sec, "distance": request.actual_distance}

@router.get("/collection_status")
async def get_collection_status():
    return {
        "is_collecting": calibration_state.is_collecting,
        "samples_collected": len(calibration_state.samples),
        "current_distance": calibration_state.current_distance,
        "last_sample": calibration_state.samples[-1].dict() if calibration_state.samples else None
    }

@router.post("/calibrate")
async def calibrate():
    if calibration_state.is_collecting:
        raise HTTPException(status_code=400, detail="Cannot calibrate while collecting.")
        
    if not calibration_state.samples:
        raise HTTPException(status_code=400, detail="No samples collected yet.")
        
    engine = get_calibration_engine()
    try:
        profile = engine.calibrate(calibration_state.environment, calibration_state.samples)
        return {"status": "success", "profile": profile.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear_samples")
async def clear_samples():
    calibration_state.samples = []
    return {"status": "cleared"}

@router.get("/profiles")
async def get_profiles():
    engine = get_calibration_engine()
    return {k: v.dict() for k, v in engine.profiles.items()}

@router.post("/set_profile/{name}")
async def set_profile(name: str):
    engine = get_calibration_engine()
    if name not in engine.profiles:
        raise HTTPException(status_code=404, detail="Profile not found.")
    engine.set_active_profile(name)
    return {"status": "success", "active_profile": name}

@router.get("/dataset/export")
async def export_dataset():
    if not calibration_state.samples:
        raise HTTPException(status_code=404, detail="No dataset available to export")
        
    export_dir = "data/exports"
    os.makedirs(export_dir, exist_ok=True)
    file_path = os.path.join(export_dir, f"dataset_{int(time.time())}.csv")
    
    with open(file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "RSSI", "Filtered_RSSI", "EMA_RSSI", "Variance", "StdDev", "Actual_Distance", "Environment", "LOS_Status"])
        for s in calibration_state.samples:
            writer.writerow([s.timestamp, s.rssi, s.filtered_rssi, s.ema_rssi, s.variance, s.std_dev, s.actual_distance, s.environment, s.los_status])
            
    return FileResponse(file_path, media_type="text/csv", filename="calibration_dataset.csv")

class ReportRequest(BaseModel):
    title: str = "Research Validation Report"
    
@router.post("/report/generate")
async def generate_report(req: ReportRequest):
    from app.services.report_generator import generate_pdf_report
    if not calibration_state.samples:
        raise HTTPException(status_code=400, detail="No samples collected to generate a report.")
        
    try:
        mgr = get_research_manager()
        exp_id = calibration_state.active_experiment_id
        exp = mgr.get_experiment(exp_id) if exp_id else {}
        
        filepath, graphs = generate_pdf_report(req.title, calibration_state.samples, exp)
        
        # Module 8: Automatically organize dataset
        if exp_id:
            # First export CSV
            export_dir = "data/exports"
            os.makedirs(export_dir, exist_ok=True)
            csv_path = os.path.join(export_dir, f"dataset_{exp_id}.csv")
            with open(csv_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "RSSI", "Filtered_RSSI", "EMA_RSSI", "Variance", "StdDev", "Actual_Distance", "Environment", "LOS_Status"])
                for s in calibration_state.samples:
                    writer.writerow([s.timestamp, s.rssi, s.filtered_rssi, s.ema_rssi, s.variance, s.std_dev, s.actual_distance, s.environment, s.los_status])
            
            # Update sample count
            if exp:
                exp["sample_count"] = len(calibration_state.samples)
                mgr._save_state()
            
            engine = get_calibration_engine()
            profile = engine.profiles.get(engine.active_profile_name)
            profile_data = profile.dict() if profile else {}
            
            mgr.organize_experiment_files(exp_id, csv_path=csv_path, pdf_path=filepath, graphs=graphs, profile_data=profile_data)

        return {"status": "success", "file": filepath}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/report/download")
async def download_report(file: str):
    if not os.path.exists(file):
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(file, media_type="application/pdf", filename=os.path.basename(file))
    
@router.post("/research/summary/generate")
async def generate_final_summary():
    # Module 10: Final Research Summary
    mgr = get_research_manager()
    experiments = mgr.get_all_experiments()
    if not experiments:
        raise HTTPException(status_code=400, detail="No experiments available for summary.")
        
    from app.services.report_generator import generate_final_summary_pdf
    try:
        filepath = generate_final_summary_pdf(experiments)
        return {"status": "success", "file": filepath}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

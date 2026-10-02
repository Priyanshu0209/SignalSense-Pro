import json
import os
import math
from typing import Dict, List, Optional
from pydantic import BaseModel
import statistics

CALIBRATION_FILE = "data/calibration_profiles.json"

class CalibrationProfile(BaseModel):
    name: str
    rssi_0: Optional[float] = None
    n: Optional[float] = None
    los_status: str = "LOS"
    last_updated: float = 0.0
    num_samples: int = 0
    description: str = "No description"
    calibration_confidence: float = 0.0
    signal_stability: float = 0.0
    noise_level: float = 0.0
    quality_score: float = 0.0
    quality_grade: str = "Unknown"
    recommendation: str = ""

class CalibrationSample(BaseModel):
    timestamp: float
    actual_distance: float
    rssi: float
    filtered_rssi: float
    ema_rssi: float
    variance: float
    std_dev: float
    environment: str
    los_status: str

class CalibrationEngine:
    def __init__(self):
        self.profiles: Dict[str, CalibrationProfile] = {}
        self.active_profile_name: str = "default"
        self._load_profiles()

    def _load_profiles(self):
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self.profiles[k] = CalibrationProfile(**v)
            except Exception as e:
                print(f"Failed to load calibration profiles: {e}")
        
        if "default" not in self.profiles:
            # Provide sensible fallback values (-45 dBm, 2.5) so that distance estimation 
            # works out-of-the-box using real hardware telemetry before manual calibration.
            self.profiles["default"] = CalibrationProfile(
                name="default",
                rssi_0=-45.0,
                n=2.5,
                los_status="LOS",
                description="Default Factory Fallback",
                calibration_confidence=50.0
            )

    def _save_profiles(self):
        os.makedirs(os.path.dirname(CALIBRATION_FILE), exist_ok=True)
        try:
            with open(CALIBRATION_FILE, "w") as f:
                data = {k: v.dict() for k, v in self.profiles.items()}
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Failed to save calibration profiles: {e}")

    def get_active_profile(self) -> CalibrationProfile:
        return self.profiles.get(self.active_profile_name, self.profiles["default"])

    def set_active_profile(self, name: str):
        if name in self.profiles:
            self.active_profile_name = name

    def calibrate(self, name: str, samples: List[CalibrationSample]):
        if not samples:
            raise ValueError("No samples provided for calibration.")

        # 1. Find RSSI_0 (average RSSI at distance ~ 1.0m)
        one_meter_samples = [s.rssi for s in samples if 0.9 <= s.actual_distance <= 1.1]
        
        rssi_0 = statistics.mean(one_meter_samples) if one_meter_samples else (self.profiles.get(name, self.profiles["default"]).rssi_0)
        
        if rssi_0 is None:
            # We must have 1m samples if there's no pre-existing rssi_0
            raise ValueError("No 1m samples provided and no previous RSSI_0 exists for this profile.")

        # 2. Estimate n
        n_values = []
        for s in samples:
            if s.actual_distance > 1.1:
                # RSSI = RSSI_0 - 10 * n * log10(d)
                # n = (RSSI_0 - RSSI) / (10 * log10(d))
                denom = 10 * math.log10(s.actual_distance)
                if denom > 0:
                    n = (rssi_0 - s.rssi) / denom
                    # Keep n within realistic physical bounds (1.5 to 6.0)
                    if 1.5 <= n <= 6.0:
                        n_values.append(n)
        
        n_final = statistics.mean(n_values) if n_values else (self.profiles.get(name, self.profiles["default"]).n)
        
        if n_final is None:
            raise ValueError("Not enough distant samples to calculate Path Loss Exponent (n), and no previous n exists.")

        # 3. Quality Analysis
        variances = [s.variance for s in samples if hasattr(s, 'variance') and s.variance > 0]
        avg_noise = sum(variances) / len(variances) if variances else 5.0
        signal_stability = max(0, 100 - (avg_noise * 5))
        
        # Base confidence on sample count and noise
        sample_conf = min(100, len(samples) / 10.0) # 1000 samples = 100%
        calibration_confidence = (sample_conf * 0.7) + (signal_stability * 0.3)
        quality_score = calibration_confidence
        
        if quality_score >= 90:
            grade = "Excellent"
            rec = "Optimal calibration achieved. Ready for research."
        elif quality_score >= 75:
            grade = "Very Good"
            rec = "Good calibration, suitable for validation."
        elif quality_score >= 60:
            grade = "Good"
            rec = "Acceptable, but consider collecting more samples."
        elif quality_score >= 40:
            grade = "Poor"
            rec = "High variance detected. Environment may be noisy."
        else:
            grade = "Recalibration Required"
            rec = "Insufficient samples or extreme noise. Please recalibrate."

        # 4. Save profile
        import time
        profile = CalibrationProfile(
            name=name,
            rssi_0=rssi_0,
            n=n_final,
            last_updated=time.time(),
            num_samples=len(samples),
            description=f"Calibrated with {len(samples)} samples",
            calibration_confidence=round(calibration_confidence, 2),
            signal_stability=round(signal_stability, 2),
            noise_level=round(avg_noise, 2),
            quality_score=round(quality_score, 2),
            quality_grade=grade,
            recommendation=rec
        )
        self.profiles[name] = profile
        self.active_profile_name = name
        self._save_profiles()
        return profile

calibration_engine_singleton = CalibrationEngine()

def get_calibration_engine() -> CalibrationEngine:
    return calibration_engine_singleton

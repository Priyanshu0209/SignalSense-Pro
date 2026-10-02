import logging
import statistics
import os
import joblib
import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone

from .time_series_collector import get_gait_time_series_collector
from .signal_filter_engine import get_signal_filter_engine

logger = logging.getLogger("signalsense.gait3d.activity")

class MotionActivityEngine:

    def __init__(self):
        self.collector = get_gait_time_series_collector()
        self.filter_engine = get_signal_filter_engine()
        self.history_log: List[Dict[str, Any]] = []
        
        model_path = os.path.join(os.path.dirname(__file__), "csi_har_model.joblib")
        try:
            self.model = joblib.load(model_path)
            logger.info("Successfully loaded ML CSI HAR model.")
        except Exception as e:
            logger.error(f"Failed to load ML CSI HAR model: {e}")
            self.model = None

    def evaluate_device_activity(self, mac_address: str, window_seconds: float = 6.0) -> Dict[str, Any]:

        from app.services.gait3d.csi_udp_server import get_csi_server
        csi_server = get_csi_server()
        latest_csi = csi_server.processor.get_latest_csi(mac_address)
        
        # We still fetch RSSI from collector for the base info
        samples = self.collector.get_recent_window(mac_address, duration_sec=window_seconds)
        device_name = samples[-1]["device_name"] if samples else mac_address
        
        if not latest_csi:
            return {
                "mac_address": mac_address,
                "device_name": device_name,
                "activity": "Unknown",
                "confidence_pct": 0,
                "anomaly_detected": False,
                "features": {"variance": 0.0, "range_dbm": 0.0, "zero_crossing_rate": 0.0, "dominant_freq_hz": 0.0, "spectral_entropy": 0.0},
                "class_probabilities": {"Still": 16, "Standing": 17, "Sitting": 17, "Walking": 17, "Running": 16, "Falling": 17},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        amplitudes = latest_csi["amplitudes"]
        phases = latest_csi["phases"]
        while len(amplitudes) < 64: amplitudes.append(0)
        while len(phases) < 64: phases.append(0)
        
        # 1. Feature Extraction (Advanced Signal Processing)
        variance = statistics.variance(amplitudes) if len(amplitudes) > 1 else 0.0
        range_dbm = max(amplitudes) - min(amplitudes) if amplitudes else 0.0
        
        # Calculate Zero Crossing Rate (ZCR)
        zcr_rate = 0.0
        if amplitudes:
            mean_amp = sum(amplitudes) / len(amplitudes)
            centered = [a - mean_amp for a in amplitudes]
            crossings = sum(1 for i in range(1, len(centered)) if (centered[i-1] >= 0 and centered[i] < 0) or (centered[i-1] < 0 and centered[i] >= 0))
            zcr_rate = crossings / len(amplitudes)
            
        # Approximate Spectral Entropy
        entropy = 0.0
        if amplitudes and sum(amplitudes) != 0:
            import math
            total_sum = sum(abs(a) for a in amplitudes)
            probs_ent = [abs(a)/total_sum for a in amplitudes if a != 0]
            entropy = -sum(p * math.log2(p) for p in probs_ent)
            
        dom_freq = (zcr_rate * 20.0) / 2.0  # Approx dominant freq assuming 20Hz sample rate
        
        # 2. Activity Classification Logic & Probabilities
        activity = "Still"
        confidence = 0
        anomaly = False
        probs = {"Still": 16, "Standing": 17, "Sitting": 17, "Walking": 17, "Running": 16, "Falling": 17}
        
        if self.model:
            # Build the 129 feature row
            feature_dict = {"RSSI": latest_csi["rssi"]}
            for i in range(64): feature_dict[f"Amp_{i}"] = amplitudes[i]
            for i in range(64): feature_dict[f"Phase_{i}"] = phases[i]
            
            features_df = pd.DataFrame([feature_dict])
            pred = self.model.predict(features_df)[0]
            pred_probs = self.model.predict_proba(features_df)[0]
            
            activity = str(pred)
            confidence = int(max(pred_probs) * 100)
            classes = self.model.classes_
            probs = {str(c): int(p * 100) for c, p in zip(classes, pred_probs)}
            if activity == "Falling":
                anomaly = True
        else:
            # Robust Heuristic Decision Tree
            if range_dbm > 120 and variance > 800:
                activity = "Falling"
                confidence = 92
                anomaly = True
                probs = {"Still": 2, "Standing": 3, "Sitting": 1, "Walking": 4, "Running": 10, "Falling": 80}
            elif variance > 1000 and zcr_rate > 0.15:
                activity = "Running"
                confidence = 88
                probs = {"Still": 1, "Standing": 2, "Sitting": 1, "Walking": 16, "Running": 75, "Falling": 5}
            elif variance > 400 and zcr_rate > 0.08:
                activity = "Walking"
                confidence = 85
                probs = {"Still": 5, "Standing": 10, "Sitting": 5, "Walking": 70, "Running": 8, "Falling": 2}
            elif variance > 100:
                activity = "Standing"
                confidence = 78
                probs = {"Still": 20, "Standing": 60, "Sitting": 10, "Walking": 8, "Running": 1, "Falling": 1}
            else:
                activity = "Still"
                confidence = 95
                probs = {"Still": 85, "Standing": 5, "Sitting": 8, "Walking": 1, "Running": 0, "Falling": 1}

        result = {
            "mac_address": mac_address,
            "device_name": device_name,
            "activity": activity,
            "confidence_pct": confidence,
            "anomaly_detected": anomaly,
            "features": {
                "variance": round(variance, 3),
                "range_dbm": round(range_dbm, 2),
                "zero_crossing_rate": round(zcr_rate, 3),
                "dominant_freq_hz": dom_freq,
                "spectral_entropy": entropy
            },
            "class_probabilities": probs,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._record_history(result)
        return result

    def get_network_activity_summary(self) -> List[Dict[str, Any]]:

        macs = set(self.collector.get_all_macs())
        
        from app.services.gait3d.csi_udp_server import get_csi_server
        csi_server = get_csi_server()
        if csi_server and csi_server.processor:
            macs.update(csi_server.processor.latest_csi_by_mac.keys())
            
        results = []
        for mac in macs:
            results.append(self.evaluate_device_activity(mac))
        return results

    def _record_history(self, record: Dict[str, Any]):
        self.history_log.insert(0, {
            "id": f"act-{len(self.history_log)+1}",
            "mac_address": record["mac_address"],
            "device_name": record["device_name"],
            "activity": record["activity"],
            "confidence": record["confidence_pct"],
            "anomaly": record["anomaly_detected"],
            "timestamp": record["timestamp"]
        })
        if len(self.history_log) > 100:
            self.history_log.pop()

    def get_activity_history(self) -> List[Dict[str, Any]]:
        return self.history_log[:50]

activity_engine_singleton = MotionActivityEngine()

def get_motion_activity_engine() -> MotionActivityEngine:
    return activity_engine_singleton

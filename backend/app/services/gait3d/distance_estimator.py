import math
from app.services.rssi_processor import get_rssi_processor_manager
from app.services.calibration_engine import get_calibration_engine

class RobustDistanceEstimator:
    def __init__(self):
        self.processor_manager = get_rssi_processor_manager()
        self.calibration_engine = get_calibration_engine()

    def estimate(self, mac: str, rssi: float) -> float:
        # 1. Filter RSSI
        filtered_rssi = self.processor_manager.process(mac, rssi)
        if filtered_rssi is None:
            # If outlier rejected and no history
            filtered_rssi = rssi

        # 2. Get active calibration profile
        profile = self.calibration_engine.get_active_profile()

        # 3. Apply Log-Distance Path Loss Model
        # d = 10 ^ ((RSSI_0 - RSSI) / (10 * n))
        if profile.rssi_0 is None or profile.n is None:
            return None
            
        exponent = (profile.rssi_0 - filtered_rssi) / (10.0 * profile.n)
        raw_dist = math.pow(10, exponent)

        # 4. Bound the distance logically
        return round(max(0.1, min(35.0, raw_dist)), 2)

estimator_singleton = RobustDistanceEstimator()

def get_distance_estimator():
    return estimator_singleton

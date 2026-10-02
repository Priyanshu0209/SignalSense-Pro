import math
from typing import Dict, Tuple, Optional
from datetime import datetime, timezone
from app.schemas.router import ConnectedDevice
from app.schemas.processing import DistanceClassification, MetricValue, MetricStatus
from app.services.confidence_engine import get_confidence_engine

class EstimationEngine:
    def __init__(self):
        self.mac_activity_history: Dict[str, float] = {}

    def estimate_rssi(self, device: ConnectedDevice, real_rssi: Optional[int] = None) -> MetricValue[int]:
        if real_rssi is not None:
            return MetricValue(
                value=real_rssi,
                status=MetricStatus.REAL,
                confidence=get_confidence_engine().calculate_rssi_confidence("Hardware", True, 100.0),
                source="Device telemetry (Hardware)"
            )
            
        return MetricValue(
            value=None,
            status=MetricStatus.UNKNOWN,
            confidence=0.0,
            source="No telemetry"
        )

    def estimate_distance(self, mac: str, rssi_metric: MetricValue[int]) -> Tuple[MetricValue[float], DistanceClassification]:
        if rssi_metric.value is None:
            return (
                MetricValue(value=None, status=MetricStatus.UNKNOWN, confidence=0.0, source="No RSSI available"),
                DistanceClassification.UNKNOWN
            )
            
        from app.services.gait3d.distance_estimator import get_distance_estimator
        distance_m = get_distance_estimator().estimate(mac, rssi_metric.value)
        
        if distance_m is None:
            return (
                MetricValue(value=None, status=MetricStatus.UNKNOWN, confidence=0.0, source="Uncalibrated Profile"),
                DistanceClassification.UNKNOWN
            )
        
        if distance_m < 2.0:
            category = DistanceClassification.VERY_NEAR
        elif distance_m < 5.0:
            category = DistanceClassification.NEAR
        elif distance_m < 15.0:
            category = DistanceClassification.MEDIUM
        elif distance_m < 30.0:
            category = DistanceClassification.FAR
        else:
            category = DistanceClassification.VERY_FAR
            
        return (
            MetricValue(
                value=round(distance_m, 1),
                status=MetricStatus.ESTIMATED,
                confidence=85.0, # Adjusted confidence
                source="Log-Distance Path Loss Model"
            ),
            category
        )

    def calculate_activity_score_and_direction(self, device: ConnectedDevice) -> Tuple[float, MetricValue[float], MetricValue[str]]:
        mac = device.mac_address
        
        # 1. Activity Estimation
        current_activity = None
        activity_source = "Unknown"
        
        rx_crc = getattr(device, 'rx_crc_per', None)
        tx_per = getattr(device, 'tx_per', None)
        false_cca = getattr(device, 'false_cca', None)
        
        if rx_crc is not None or tx_per is not None or false_cca is not None:
            activity_source = "Advanced PHY Metrics (PER/CRC)"
            current_activity = 0.0
            if rx_crc: current_activity += min(50.0, rx_crc * 1.5)
            if tx_per: current_activity += min(30.0, tx_per * 1.5)
            if false_cca: current_activity += min(20.0, (false_cca / 100.0) * 10.0)
        elif device.tx_rate is not None and device.rx_rate is not None:
            activity_source = "Traffic Rate (Legacy)"
            total_rate = (device.tx_rate or 0) + (device.rx_rate or 0)
            current_activity = min(100.0, (total_rate / 500.0) * 100.0)
            
        if current_activity is not None:
            prev_activity = self.mac_activity_history.get(mac, 0.0)
            smoothed_activity = (prev_activity * 0.7) + (current_activity * 0.3)
            self.mac_activity_history[mac] = smoothed_activity
        else:
            smoothed_activity = 0.0
        
        # 2. Direction Estimation
        direction_val = None
        dir_source = "Unknown"
        dir_conf = 0.0
        
        rssi0 = getattr(device, 'rssi_ant0', None)
        rssi1 = getattr(device, 'rssi_ant1', None)
        
        if rssi0 is not None and rssi1 is not None:
            # Simple heuristic Angle of Arrival based on RSSI delta
            diff = rssi0 - rssi1
            direction_val = (diff * 9.0) % 360
            dir_source = "Dual Antenna RSSI Difference"
            dir_conf = 70.0
            
        direction_metric = MetricValue(
            value=round(direction_val, 1) if direction_val is not None else None,
            status=MetricStatus.ESTIMATED if dir_conf > 0 else MetricStatus.UNKNOWN,
            confidence=dir_conf,
            source=dir_source
        )
        
        # 3. Movement State
        movement_state = "Unknown"
        if smoothed_activity is not None:
            movement_state = "Stationary"
            if smoothed_activity > 60:
                movement_state = "Rapid Movement (Walking/Running)"
            elif smoothed_activity > 25:
                movement_state = "Moving (Gestures/Shifting)"
            
        movement_metric = MetricValue(
            value=movement_state if smoothed_activity is not None else None,
            status=MetricStatus.ESTIMATED if smoothed_activity is not None else MetricStatus.UNKNOWN,
            confidence=60.0 if rx_crc else (10.0 if smoothed_activity is not None else 0.0),
            source=activity_source
        )
        
        return smoothed_activity, direction_metric, movement_metric

estimation_engine = EstimationEngine()

def get_estimation_engine() -> EstimationEngine:
    return estimation_engine

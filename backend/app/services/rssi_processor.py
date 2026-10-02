import statistics
from typing import List, Optional, Dict

class RSSIProcessor:
    def __init__(self, window_size: int = 15, ema_alpha: float = 0.2, outlier_threshold: float = 10.0):
        self.window_size = window_size
        self.ema_alpha = ema_alpha
        self.outlier_threshold = outlier_threshold
        self.history: List[float] = []
        self.ema: Optional[float] = None

    def process(self, raw_rssi: float) -> Optional[float]:
        # Outlier Removal
        if self.history:
            median_hist = statistics.median(self.history)
            if abs(raw_rssi - median_hist) > self.outlier_threshold:
                # Reject outlier
                return self.ema if self.ema is not None else median_hist

        self.history.append(raw_rssi)
        if len(self.history) > self.window_size:
            self.history.pop(0)

        # Median Filter
        median_val = statistics.median(self.history)

        # Moving Average is implicitly handled by combination of Median and EMA

        # Exponential Moving Average (EMA)
        if self.ema is None:
            self.ema = median_val
        else:
            self.ema = (self.ema_alpha * median_val) + ((1.0 - self.ema_alpha) * self.ema)

        return self.ema

    def get_variance(self) -> float:
        if len(self.history) < 2:
            return 0.0
        return statistics.variance(self.history)

class RSSIProcessorManager:
    def __init__(self):
        self.processors: Dict[str, RSSIProcessor] = {}

    def process(self, mac: str, raw_rssi: float) -> Optional[float]:
        if mac not in self.processors:
            self.processors[mac] = RSSIProcessor()
        return self.processors[mac].process(raw_rssi)

    def get_variance(self, mac: str) -> float:
        if mac in self.processors:
            return self.processors[mac].get_variance()
        return 0.0

processor_manager_singleton = RSSIProcessorManager()

def get_rssi_processor_manager() -> RSSIProcessorManager:
    return processor_manager_singleton

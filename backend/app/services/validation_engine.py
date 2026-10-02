import math
import numpy as np
from typing import List, Dict, Tuple
from pydantic import BaseModel

class ValidationMetrics(BaseModel):
    mae: float
    rmse: float
    mape: float
    mean_error: float
    median_error: float
    max_error: float
    min_error: float
    std_dev: float
    ci_95: float
    sample_count: int

class ValidationEngine:
    def __init__(self):
        self.history: List[Dict[str, float]] = []

    def add_sample(self, actual: float, estimated: float):
        self.history.append({"actual": actual, "estimated": estimated})
        # Keep last 2000 samples for rolling metrics
        if len(self.history) > 2000:
            self.history.pop(0)

    def calculate_metrics(self) -> ValidationMetrics:
        if not self.history:
            return ValidationMetrics(
                mae=0.0, rmse=0.0, mape=0.0, 
                mean_error=0.0, median_error=0.0, 
                max_error=0.0, min_error=0.0, 
                std_dev=0.0, ci_95=0.0, sample_count=0
            )

        n = len(self.history)
        errors = []
        abs_errors = []
        pct_errors = []

        for item in self.history:
            actual = item["actual"]
            est = item["estimated"]
            err = est - actual
            abs_err = abs(err)
            
            errors.append(err)
            abs_errors.append(abs_err)
            if actual > 0:
                pct_errors.append((abs_err / actual) * 100.0)

        errors_arr = np.array(errors)
        abs_errors_arr = np.array(abs_errors)
        
        mae = np.mean(abs_errors_arr)
        rmse = np.sqrt(np.mean(abs_errors_arr**2))
        mape = np.mean(pct_errors) if pct_errors else 0.0
        
        mean_error = np.mean(errors_arr)
        median_error = np.median(errors_arr)
        max_error = np.max(errors_arr)
        min_error = np.min(errors_arr)
        std_dev = np.std(errors_arr)
        
        # 95% Confidence Interval = 1.96 * (std / sqrt(n))
        ci_95 = 1.96 * (std_dev / math.sqrt(n)) if n > 0 else 0.0

        return ValidationMetrics(
            mae=round(float(mae), 4),
            rmse=round(float(rmse), 4),
            mape=round(float(mape), 4),
            mean_error=round(float(mean_error), 4),
            median_error=round(float(median_error), 4),
            max_error=round(float(max_error), 4),
            min_error=round(float(min_error), 4),
            std_dev=round(float(std_dev), 4),
            ci_95=round(float(ci_95), 4),
            sample_count=n
        )

    def get_latest_error(self) -> Dict[str, float]:
        if not self.history:
            return {"absolute_error": 0.0, "relative_error": 0.0}
        
        latest = self.history[-1]
        actual = latest["actual"]
        est = latest["estimated"]
        abs_err = abs(actual - est)
        rel_err = (abs_err / actual) * 100.0 if actual > 0 else 0.0
        
        return {
            "absolute_error": round(abs_err, 4),
            "relative_error": round(rel_err, 4),
            "actual": actual,
            "estimated": round(est, 4)
        }

validation_engine_singleton = ValidationEngine()

def get_validation_engine() -> ValidationEngine:
    return validation_engine_singleton

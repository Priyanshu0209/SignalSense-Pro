import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.domain import GaitHistoryModel
from app.services.gait3d.kinematic3d_generator import get_kinematic3d_generator

logger = logging.getLogger("signalsense.gait3d.history")

class GaitHistoryLogger:
    def __init__(self):
        self._running = False
        self._task = None
        self._interval_sec = 10.0
        
    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._log_loop())
        logger.info("Gait History Logger started.")
        
    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            
    async def _log_loop(self):
        kinematic_eng = get_kinematic3d_generator()
        while self._running:
            try:
                scene_frame = kinematic_eng.get_3d_scene_frame()
                subjects = scene_frame.get("subjects", [])
                
                if subjects:
                    async with AsyncSessionLocal() as session:
                        for sub in subjects:
                            # Only log if online and have a valid mac
                            if not sub.get("mac_address"):
                                continue
                                
                            history_record = GaitHistoryModel(
                                timestamp=datetime.now(timezone.utc),
                                mac_address=sub["mac_address"],
                                activity_state=sub.get("activity_state", "Unknown"),
                                confidence=sub.get("confidence", 0),
                                cadence_rpm=sub.get("cadence_rpm", 0.0),
                                speed_mps=sub.get("speed_mps", 0.0),
                                distance_m=sub.get("distance_m", 0.0)
                            )
                            session.add(history_record)
                        
                        await session.commit()
                        logger.debug(f"Logged history for {len(subjects)} subjects.")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in gait history logger: {e}")
                
            await asyncio.sleep(self._interval_sec)

# Singleton
_logger_instance = GaitHistoryLogger()

def get_gait_history_logger() -> GaitHistoryLogger:
    return _logger_instance

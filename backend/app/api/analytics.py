from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from app.services.copilot_engine import get_copilot_engine
from app.services.insight_engine import get_insight_engine
from app.services.event_timeline_engine import EventTimelineEngine

router = APIRouter()

@router.get("/events")
async def get_timeline_events():

    return EventTimelineEngine.get_recent_events(limit=50)

class CopilotQuery(BaseModel):
    query: str

@router.post("/copilot")
async def ask_copilot(query: CopilotQuery) -> Dict[str, Any]:
    engine = get_copilot_engine()
    return engine.answer_query(query.query)


@router.get("/insights")
async def get_insights() -> Dict[str, Any]:
    engine = get_insight_engine()
    return {
        "scores": engine.generate_scores(),
        "feed": engine.get_live_insights()
    }

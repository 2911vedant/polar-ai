from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.agent.polar_navigator import PolarNavigator

router = APIRouter()
navigator = PolarNavigator()


class AgentQueryRequest(BaseModel):
    query: str
    context: dict = {}


@router.post("/query")
async def agent_query(
    request: AgentQueryRequest,
    db: Session = Depends(get_db)
):
    """Query the Polar Navigator AI assistant."""
    response = await navigator.query(request.query, request.context)
    return response

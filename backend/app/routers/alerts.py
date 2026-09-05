"""Navigation alert endpoints + SSE stream."""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.alert_service import AlertService
import asyncio
import json

router = APIRouter()


@router.get("/alerts")
async def get_alerts(limit: int = 20, unacknowledged: bool = False):
    """Return navigation alerts."""
    return {
        "alerts": AlertService.get_alerts(limit=limit, unacknowledged_only=unacknowledged),
        "unread_count": AlertService.get_unread_count(),
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    ok = AlertService.acknowledge(alert_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(404, f"Alert '{alert_id}' not found")
    return {"status": "acknowledged"}


@router.get("/alerts/stream")
async def alerts_stream():
    """
    Server-Sent Events stream for real-time alert push to frontend.
    Subscribe with: EventSource('/api/alerts/stream')
    """
    queue = AlertService.subscribe()

    async def event_generator():
        try:
            # Send initial ping
            yield f"event: ping\ndata: connected\n\n"
            while True:
                try:
                    alert = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: alert\ndata: {json.dumps(alert)}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: ping\ndata: keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            AlertService.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

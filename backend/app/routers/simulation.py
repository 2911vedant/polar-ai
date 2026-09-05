from fastapi import APIRouter
from app.services import simulation_service

router = APIRouter()


@router.get("/state")
async def get_simulation_state():
    """Get current simulation state."""
    return simulation_service.get_state()


@router.post("/start")
async def start_simulation():
    """Start the simulation."""
    return simulation_service.start()


@router.post("/pause")
async def pause_simulation():
    """Pause the simulation."""
    return simulation_service.pause()


@router.post("/reset")
async def reset_simulation():
    """Reset the simulation to initial state."""
    return simulation_service.reset()


@router.post("/step")
async def step_simulation():
    """Advance simulation by one time step."""
    return simulation_service.step()

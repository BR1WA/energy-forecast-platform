from fastapi import APIRouter, Depends, Request
from app.models import User
from app.services.auth_service import get_current_user
from app.services.simulation_service import simulation_service

router = APIRouter(prefix="/api/v1/simulation", tags=["Simulation"])

@router.post("/start")
def start_simulation(current_user: User = Depends(get_current_user)):
    return simulation_service.start_simulation()

@router.post("/stop")
def stop_simulation(current_user: User = Depends(get_current_user)):
    return simulation_service.stop_simulation()

@router.get("/status")
def get_status(current_user: User = Depends(get_current_user)):
    state = simulation_service.get_status()
    # Map to expected string status and pass boolean values
    state["status"] = "running" if state["is_running"] else "stopped"
    # Append configuration parameters to status
    state["day_part"] = simulation_service.day_part
    state["occupants"] = simulation_service.occupants
    state["temperature"] = simulation_service.temperature
    state["ac_level"] = simulation_service.ac_level
    state["washing_machine"] = simulation_service.washing_machine
    state["solar"] = simulation_service.solar
    return state

@router.post("/reset")
def reset_simulation(current_user: User = Depends(get_current_user)):
    return simulation_service.reset_simulation()

@router.post("/configure")
async def configure_simulation(request: Request, current_user: User = Depends(get_current_user)):
    config = await request.json()
    return simulation_service.configure_simulation(config)




from fastapi import APIRouter, Depends
from app.database import get_db
from app.models import User
from sqlalchemy.orm import Session
from app.services.auth_service import get_current_user
from app.services.simulation_service import simulation_service
from app.schemas import SimulationConfiguration

router = APIRouter(prefix="/api/v1/simulation", tags=["Simulation"])

@router.post("/start")
def start_simulation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return simulation_service.start_simulation(db, current_user.id)

@router.post("/stop")
def stop_simulation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return simulation_service.stop_simulation(db, current_user.id)

@router.get("/status")
def get_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    state = simulation_service.get_state(db, current_user.id)
    state["status"] = "running" if state["is_running"] else "stopped"
    return state

@router.post("/reset")
def reset_simulation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return simulation_service.reset_simulation(db, current_user.id)

@router.post("/configure")
def configure_simulation(
    config: SimulationConfiguration,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return simulation_service.configure_simulation(db, current_user.id, config.model_dump())


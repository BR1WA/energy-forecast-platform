from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/simulation", tags=["Simulation"])

@router.post("/start")
def start_simulation():
    return {"status": "started"}

@router.post("/stop")
def stop_simulation():
    return {"status": "stopped"}

@router.get("/status")
def get_status():
    return {"status": "running"}

@router.post("/reset")
def reset_simulation():
    return {"status": "reset"}

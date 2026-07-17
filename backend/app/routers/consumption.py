from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.consumption_service import consumption_service

router = APIRouter(prefix="/api/v1/consumption", tags=["Consumption"])

@router.get("/current")
def get_current(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return consumption_service.get_current_consumption(db, user_id=current_user.id)

@router.get("/history")
def get_history(
    timeframe: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if timeframe:
            return consumption_service.get_chart_history(db, user_id=current_user.id, timeframe=timeframe)
        return consumption_service.get_history(db, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/statistics")
def get_statistics(
    month: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return consumption_service.get_monthly_summary(db, user_id=current_user.id, month=month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must use YYYY-MM format") from exc

@router.get("/export")
def export_consumption(
    month: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        csv_data = consumption_service.export_month_csv(db, user_id=current_user.id, month=month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must use YYYY-MM format") from exc
    selected_month = month or "current-month"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="energy-{selected_month}.csv"'},
    )

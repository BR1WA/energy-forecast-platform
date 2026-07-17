"""Meter data ingestion endpoints for CSV imports and device push clients."""
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Meter, Site, User
from app.schemas import IngestionKeyResponse, IngestionResult, MeterSampleBatch
from app.services.auth_service import get_current_user
from app.services.ingestion_service import ingestion_service


router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])
MAX_CSV_BYTES = 5 * 1024 * 1024


def _owned_meter(db: Session, user_id: int, meter_id: int) -> Meter:
    meter = (
        db.query(Meter)
        .join(Site, Meter.site_id == Site.id)
        .filter(Meter.id == meter_id, Site.user_id == user_id)
        .first()
    )
    if meter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found")
    return meter


async def _read_csv(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a CSV file")
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV exceeds the 5 MB limit")
    return raw


@router.get("/meters")
def list_meters(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    meters = (
        db.query(Meter)
        .join(Site, Meter.site_id == Site.id)
        .filter(Site.user_id == current_user.id)
        .order_by(Meter.id)
        .all()
    )
    return [{"id": meter.id, "name": meter.name, "source_type": meter.source_type} for meter in meters]


@router.post("/meters/{meter_id}/push-key", response_model=IngestionKeyResponse)
def rotate_push_key(
    meter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meter = _owned_meter(db, current_user.id, meter_id)
    key = ingestion_service.create_api_key(meter)
    meter.source_type = "push"
    db.commit()
    return {"meter_id": meter.id, "api_key": key}


@router.post("/meters/{meter_id}/csv/preview")
async def preview_csv(
    meter_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_meter(db, current_user.id, meter_id)
    try:
        return ingestion_service.preview_csv(await _read_csv(file))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/meters/{meter_id}/csv/import", response_model=IngestionResult)
async def import_csv(
    meter_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meter = _owned_meter(db, current_user.id, meter_id)
    try:
        samples, errors, _ = ingestion_service.parse_csv(await _read_csv(file))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    result = ingestion_service.ingest(db, meter, samples, source="csv", initial_errors=errors)
    meter.source_type = "csv"
    db.commit()
    return result


@router.post("/meters/{meter_id}/samples", response_model=IngestionResult)
def push_samples(
    meter_id: int,
    payload: MeterSampleBatch,
    x_meter_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    meter = db.query(Meter).filter(Meter.id == meter_id).first()
    if meter is None or not ingestion_service.check_api_key(meter, x_meter_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid meter key")
    result = ingestion_service.ingest(
        db, meter, payload.samples, source="push", idempotency_key=payload.idempotency_key,
    )
    meter.source_type = "push"
    db.commit()
    return result

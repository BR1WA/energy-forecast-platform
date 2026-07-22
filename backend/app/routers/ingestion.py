"""Meter data ingestion endpoints for CSV imports and device push clients."""
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Meter, SimulationSession, Site, User
from app.schemas import IngestionKeyResponse, IngestionResult, MeterConfiguration, MeterSampleBatch
from app.services.auth_service import get_current_user
from app.services.ingestion_service import ingestion_service
from app.services.audit_service import record_audit_event


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
        .filter(Site.user_id == current_user.id, Meter.is_primary.is_(True))
        .order_by(Meter.id)
        .all()
    )
    return [{
        "id": meter.id,
        "name": meter.name,
        "source_type": meter.source_type,
        "is_primary": meter.is_primary,
        "expected_interval_seconds": meter.expected_interval_seconds,
        "last_seen_at": meter.last_seen_at,
        "push_key_configured": meter.ingestion_key_hash is not None,
    } for meter in meters]


@router.patch("/meters/{meter_id}")
def update_meter(
    meter_id: int,
    payload: MeterConfiguration,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meter = _owned_meter(db, current_user.id, meter_id)
    if not meter.is_primary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary meter not found")
    if payload.name is not None:
        meter.name = payload.name.strip()
    meter.expected_interval_seconds = payload.expected_interval_seconds
    record_audit_event(
        db,
        "meter.configuration_updated",
        actor_user_id=current_user.id,
        site_id=meter.site_id,
        target=f"meter:{meter.id}",
        metadata={"expected_interval_seconds": meter.expected_interval_seconds},
    )
    db.commit()
    return {"message": "Meter updated"}


@router.post("/meters/{meter_id}/push-key", response_model=IngestionKeyResponse)
def rotate_push_key(
    meter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meter = _owned_meter(db, current_user.id, meter_id)
    key = ingestion_service.create_api_key(meter)
    meter.source_type = "push"
    meter.expected_interval_seconds = meter.expected_interval_seconds or 60
    simulation = db.query(SimulationSession).filter(SimulationSession.site_id == meter.site_id).one_or_none()
    if simulation is not None:
        simulation.is_running = False
    record_audit_event(db, "ingestion.key_rotated", actor_user_id=current_user.id, site_id=meter.site_id, target=f"meter:{meter.id}")
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
    record_audit_event(
        db,
        "ingestion.csv_imported",
        actor_user_id=current_user.id,
        site_id=meter.site_id,
        target=f"meter:{meter.id}",
        metadata={"batch_id": result["batch_id"], "accepted_rows": result["accepted_rows"], "rejected_rows": result["rejected_rows"]},
    )
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
    simulation_running = db.query(SimulationSession.id).filter(
        SimulationSession.site_id == meter.site_id,
        SimulationSession.is_running.is_(True),
    ).first()
    if simulation_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop the demo simulator before sending push readings",
        )
    result = ingestion_service.ingest(
        db, meter, payload.samples, source="push", idempotency_key=payload.idempotency_key,
    )
    meter.source_type = "push"
    record_audit_event(
        db,
        "ingestion.push_received",
        site_id=meter.site_id,
        target=f"meter:{meter.id}",
        metadata={"batch_id": result["batch_id"], "accepted_rows": result["accepted_rows"], "idempotency_key": payload.idempotency_key},
    )
    db.commit()
    return result

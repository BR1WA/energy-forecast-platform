"""Client actions derived from persisted, user-owned alert evidence."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Recommendation, User
from app.schemas import RecommendationResponse, RecommendationStatusUpdate
from app.services.audit_service import record_audit_event
from app.services.auth_service import get_current_user
from app.services.recommendation_service import recommendation_service

router = APIRouter(prefix="/api/v1/recommendations", tags=["Recommendations"])


@router.get("", response_model=list[RecommendationResponse])
def list_recommendations(
    include_closed: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [RecommendationResponse.model_validate(item) for item in recommendation_service.list_for_user(db, current_user.id, include_closed)]


@router.patch("/{recommendation_id}", response_model=RecommendationResponse)
def update_recommendation(
    recommendation_id: int,
    payload: RecommendationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recommendation = (
        db.query(Recommendation)
        .filter(Recommendation.id == recommendation_id, Recommendation.user_id == current_user.id)
        .first()
    )
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    recommendation.status = payload.status
    record_audit_event(
        db,
        "recommendation.status_updated",
        actor_user_id=current_user.id,
        site_id=recommendation.site_id,
        target=f"recommendation:{recommendation.id}",
        metadata={"status": payload.status, "category": recommendation.category},
    )
    db.commit()
    db.refresh(recommendation)
    return RecommendationResponse.model_validate(recommendation)

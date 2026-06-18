"""
Billing router — self-service subscription checkout and entitlements.

Upgrades flow through an honest, two-step checkout (open -> confirm) rather than
a direct self-grant, which was the core of audit finding C1. Downgrade/cancel is
immediate. All tier writes go through `billing_service`. See ENTITLEMENTS_PLAN.md.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    CheckoutRequest, CheckoutResponse, CheckoutConfirmRequest,
    SubscriptionResponse, EntitlementsResponse, UserResponse,
)
from app.services.auth_service import get_current_user
from app.services import billing_service
from app.entitlements import Tier, features_for_tier

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])


@router.get("/entitlements", response_model=EntitlementsResponse)
def get_entitlements(current_user: User = Depends(get_current_user)):
    """Return the current user's tier and the feature keys it unlocks.

    The frontend should gate UI from this single source of truth instead of
    hardcoding tier-string comparisons.
    """
    return EntitlementsResponse(
        subscription_tier=current_user.subscription_tier,
        features=features_for_tier(current_user.subscription_tier),
    )


@router.get("/subscription", response_model=SubscriptionResponse | None)
def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's active subscription, or null if on the free tier."""
    sub = billing_service.active_subscription(db, current_user)
    return SubscriptionResponse.model_validate(sub) if sub else None


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Open a checkout for a paid tier (does NOT grant access yet).

    Returns a checkout reference that must be confirmed via /checkout/confirm
    (which a real deployment would trigger from a payment webhook).
    """
    try:
        sub = billing_service.create_checkout(db, current_user, Tier[data.tier.value])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return CheckoutResponse(checkout_ref=sub.checkout_ref, tier=sub.tier, status=sub.status)


@router.post("/checkout/confirm", response_model=UserResponse)
def confirm_checkout(
    data: CheckoutConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm a pending checkout, activating the subscription (simulated webhook)."""
    try:
        billing_service.confirm_checkout(db, current_user, data.checkout_ref)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/cancel", response_model=UserResponse)
def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel the active subscription and downgrade to the free tier."""
    billing_service.cancel(db, current_user)
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)

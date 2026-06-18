"""
Billing / entitlement service.

Encapsulates how a user's subscription tier changes. This is the ONLY place
that writes `User.subscription_tier`, keeping the denormalized cache on the user
in sync with the canonical `Subscription` audit-trail rows.

The payment provider is simulated: `create_checkout` opens a `pending`
subscription and returns an opaque reference; `confirm_checkout` (which a real
deployment would call from a payment webhook) activates it. This keeps the flow
honest (no instant self-grant) while remaining runnable without a real gateway.
See ENTITLEMENTS_PLAN.md (Phase 4) and audit C1.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Subscription, User
from app.entitlements import Tier

# Tiers a user may purchase via checkout (free is not a purchasable product;
# it is the absence of an active paid subscription).
PURCHASABLE_TIERS = {Tier.pro, Tier.enterprise}

# Length of a simulated billing period.
BILLING_PERIOD_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _activate(db: Session, user: User, sub: Subscription) -> None:
    """Mark a subscription active and sync the user's cached tier."""
    now = _now()
    sub.status = "active"
    sub.started_at = sub.started_at or now
    sub.current_period_end = now + timedelta(days=BILLING_PERIOD_DAYS)
    user.subscription_tier = sub.tier


def create_checkout(db: Session, user: User, target_tier: Tier) -> Subscription:
    """Open a pending subscription for `target_tier` and return it.

    Raises ValueError if the tier is not purchasable. Any other pending
    checkout for the user is superseded (cancelled) so there is at most one
    open checkout at a time.
    """
    if target_tier not in PURCHASABLE_TIERS:
        raise ValueError(
            f"Tier {target_tier.name!r} is not purchasable. "
            f"Purchasable tiers: {', '.join(t.name for t in PURCHASABLE_TIERS)}."
        )

    # Supersede any stale pending checkouts.
    stale = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status == "pending")
        .all()
    )
    for s in stale:
        s.status = "cancelled"
        s.cancelled_at = _now()

    sub = Subscription(
        user_id=user.id,
        tier=target_tier.name,
        status="pending",
        source="checkout",
        checkout_ref=f"chk_{secrets.token_urlsafe(16)}",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def confirm_checkout(db: Session, user: User, checkout_ref: str) -> Subscription:
    """Activate a pending subscription identified by its checkout reference.

    Simulates a payment-provider webhook confirming successful payment. Raises
    ValueError if no matching pending checkout exists for the user.
    """
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.checkout_ref == checkout_ref,
            Subscription.status == "pending",
        )
        .first()
    )
    if sub is None:
        raise ValueError("No pending checkout found for this reference.")

    _activate(db, user, sub)
    db.commit()
    db.refresh(sub)
    return sub


def grant(db: Session, user: User, target_tier: Tier, source: str = "admin_grant") -> Subscription | None:
    """Directly activate a tier for a user without checkout (admin/trial path).

    Granting `free` cancels any active paid subscription instead of creating a
    row. Returns the created Subscription, or None when downgrading to free.
    """
    if target_tier == Tier.free:
        cancel(db, user)
        return None

    # Cancel any currently active subscription before granting a new one.
    _cancel_active(db, user)

    sub = Subscription(
        user_id=user.id,
        tier=target_tier.name,
        status="pending",
        source=source,
    )
    db.add(sub)
    _activate(db, user, sub)
    db.commit()
    db.refresh(sub)
    return sub


def _cancel_active(db: Session, user: User) -> None:
    active = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status == "active")
        .all()
    )
    for s in active:
        s.status = "cancelled"
        s.cancelled_at = _now()


def cancel(db: Session, user: User) -> None:
    """Cancel the active subscription and downgrade the user to free."""
    _cancel_active(db, user)
    user.subscription_tier = Tier.free.name
    db.commit()


def active_subscription(db: Session, user: User) -> Subscription | None:
    """Return the user's current active subscription, if any."""
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status == "active")
        .order_by(Subscription.id.desc())
        .first()
    )

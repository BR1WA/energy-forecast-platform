"""Strict helpers for the authenticated user's single site and primary meter."""
from sqlalchemy.orm import Session

from app.models import Meter, Site, SiteSettings


def ensure_user_site(db: Session, user_id: int) -> Site:
    site = db.query(Site).filter(Site.user_id == user_id).one_or_none()
    if site is None:
        site = Site(user_id=user_id, name="Default site")
        db.add(site)
        db.flush()

    primary_meter = (
        db.query(Meter)
        .filter(Meter.site_id == site.id, Meter.is_primary.is_(True))
        .one_or_none()
    )
    if primary_meter is None:
        primary_meter = (
            db.query(Meter).filter(Meter.site_id == site.id).order_by(Meter.id).first()
        )
        if primary_meter is None:
            primary_meter = Meter(
                site_id=site.id,
                external_id=f"default-{user_id}",
                name="Primary meter",
            )
            db.add(primary_meter)
        primary_meter.is_primary = True
    if db.query(SiteSettings).filter(SiteSettings.site_id == site.id).first() is None:
        db.add(SiteSettings(site_id=site.id))
    db.flush()
    return site


def get_user_site(db: Session, user_id: int) -> Site | None:
    return db.query(Site).filter(Site.user_id == user_id).one_or_none()


def get_primary_meter(db: Session, user_id: int) -> Meter | None:
    return (
        db.query(Meter)
        .join(Site, Meter.site_id == Site.id)
        .filter(Site.user_id == user_id, Meter.is_primary.is_(True))
        .one_or_none()
    )


# Temporary compatibility aliases while callers are migrated to product names.
ensure_default_site = ensure_user_site
get_default_site = get_user_site
get_default_meter = get_primary_meter


def owned_meter_ids(db: Session, user_id: int) -> list[int]:
    return [
        meter_id
        for meter_id in (
            db.query(Meter.id)
            .join(Site, Meter.site_id == Site.id)
            .filter(Site.user_id == user_id)
            .all()
        )
    ]

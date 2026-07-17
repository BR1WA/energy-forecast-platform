"""Helpers for resolving the current user's default site and owned meters."""
from sqlalchemy.orm import Session

from app.models import Meter, Site, SiteSettings


def ensure_default_site(db: Session, user_id: int) -> Site:
    site = db.query(Site).filter(Site.user_id == user_id).order_by(Site.id).first()
    if site is None:
        site = Site(user_id=user_id, name="Default site")
        db.add(site)
        db.flush()

    if db.query(Meter).filter(Meter.site_id == site.id).first() is None:
        db.add(Meter(site_id=site.id, external_id=f"default-{user_id}", name="Default meter"))
    if db.query(SiteSettings).filter(SiteSettings.site_id == site.id).first() is None:
        db.add(SiteSettings(site_id=site.id))
    db.flush()
    return site


def get_default_site(db: Session, user_id: int) -> Site | None:
    return db.query(Site).filter(Site.user_id == user_id).order_by(Site.id).first()


def get_default_meter(db: Session, user_id: int) -> Meter | None:
    return (
        db.query(Meter)
        .join(Site, Meter.site_id == Site.id)
        .filter(Site.user_id == user_id)
        .order_by(Meter.id)
        .first()
    )


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

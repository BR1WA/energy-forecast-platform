"""
Subscription entitlements — single source of truth for tier-gated features.

This module centralizes *what each subscription tier unlocks* so that no router
or frontend component has to hardcode `subscription_tier == "enterprise"` style
checks. Tiers are ordered, so a higher tier inherits every feature of the tiers
below it. See audit findings C1 and C2 and ENTITLEMENTS_PLAN.md.
"""
from __future__ import annotations

from enum import Enum, IntEnum


class Tier(IntEnum):
    """Subscription tiers, ordered from least to most privileged.

    Ordering matters: `Tier.enterprise > Tier.pro > Tier.free`, which lets a
    higher tier automatically satisfy a lower tier's feature requirements.
    """
    free = 0
    pro = 1
    enterprise = 2

    @classmethod
    def from_str(cls, value: str | None) -> "Tier":
        """Resolve a stored tier string to a Tier, defaulting to free.

        Unknown or missing values are treated as `free` (least privileged) so a
        bad/empty column can never accidentally grant access.
        """
        if not value:
            return cls.free
        try:
            return cls[value.strip().lower()]
        except KeyError:
            return cls.free


class Feature(str, Enum):
    """Gated product features, independent of the tier that unlocks them."""
    PRO_FORECAST_CURVE = "pro_forecast_curve"
    ANALYTICS_SUMMARY = "analytics_summary"
    PDF_EXPORT = "pdf_export"
    HEATMAP = "heatmap"
    MULTI_SITE = "multi_site"


# Minimum tier required for each feature. This is the ONLY place the mapping
# lives; enforcement and UI gating should both derive from it.
FEATURE_MIN_TIER: dict[Feature, Tier] = {
    Feature.PRO_FORECAST_CURVE: Tier.pro,
    Feature.ANALYTICS_SUMMARY: Tier.pro,
    Feature.PDF_EXPORT: Tier.pro,
    Feature.HEATMAP: Tier.enterprise,
    Feature.MULTI_SITE: Tier.enterprise,
}


def tier_allows(user_tier: str | None, feature: Feature) -> bool:
    """Return True if `user_tier` is high enough to access `feature`."""
    return Tier.from_str(user_tier) >= FEATURE_MIN_TIER[feature]


def features_for_tier(user_tier: str | None) -> list[str]:
    """List the feature values unlocked by `user_tier`.

    Useful for exposing entitlements to the frontend (e.g. an entitlements
    endpoint) so the UI gates from the same source of truth as the backend.
    """
    tier = Tier.from_str(user_tier)
    return [
        feature.value
        for feature, min_tier in FEATURE_MIN_TIER.items()
        if tier >= min_tier
    ]

import { User } from '../types';

export enum Tier {
  free = 0,
  pro = 1,
  enterprise = 2,
}

export const TIER_ORDER: Record<string, Tier> = {
  free: Tier.free,
  pro: Tier.pro,
  enterprise: Tier.enterprise,
};

export enum Feature {
  PRO_FORECAST_CURVE = 'pro_forecast_curve',
  ANALYTICS_SUMMARY = 'analytics_summary',
  PDF_EXPORT = 'pdf_export',
  HEATMAP = 'heatmap',
  MULTI_SITE = 'multi_site',
}

export const FEATURE_MIN_TIER: Record<Feature, Tier> = {
  [Feature.PRO_FORECAST_CURVE]: Tier.pro,
  [Feature.ANALYTICS_SUMMARY]: Tier.pro,
  [Feature.PDF_EXPORT]: Tier.pro,
  [Feature.HEATMAP]: Tier.enterprise,
  [Feature.MULTI_SITE]: Tier.enterprise,
};

export function getTier(tierName?: string): Tier {
  if (!tierName) return Tier.free;
  const normalized = tierName.trim().toLowerCase();
  return TIER_ORDER[normalized] ?? Tier.free;
}

export function can(user: User | null | undefined, feature: Feature | string): boolean {
  if (!user) return false;
  const userTier = getTier(user.subscription_tier);
  const minTier = FEATURE_MIN_TIER[feature as Feature];
  if (minTier === undefined) {
    // If the feature is not explicitly gated, allow access
    return true;
  }
  return userTier >= minTier;
}

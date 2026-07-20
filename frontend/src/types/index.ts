// ============================================================
// User & Auth Types
// ============================================================
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'user';
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  avatar_url?: string;
  last_activity?: string;
  is_setup_complete?: boolean;
  preferences?: Record<string, any>;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export type ConsumptionTimeframe = 'live' | 'today' | '7d' | 'month' | 'year' | 'all' | 'custom';

export interface ConsumptionPoint {
  timestamp: string;
  average_kw: number;
  min_kw: number | null;
  max_kw: number | null;
  energy_kwh: number;
  sample_count: number;
}

export interface ConsumptionPeriodSummary {
  timeframe: ConsumptionTimeframe;
  period_start: string;
  period_end: string;
  site_name: string;
  timezone: string;
  granularity: string;
  total_kwh: number;
  estimated_cost: number;
  currency: string;
  average_kw: number;
  peak_kw: number;
  peak_at: string | null;
  coverage_pct: number;
  sample_count: number;
  sources: Array<{ source: string; count: number }>;
  freshness: {
    status: 'fresh' | 'stale' | 'historical' | 'empty';
    age_seconds: number | null;
    expected_interval_seconds: number | null;
    last_seen_at: string | null;
    source: string | null;
    quality: string | null;
  };
  points: ConsumptionPoint[];
}

export interface ConsumptionReading {
  id: number;
  timestamp: string;
  active_power_kw: number;
  reactive_power_kvar: number;
  voltage_v: number;
  current_a: number;
  energy_kwh: number | null;
  source: string;
  quality: string;
}

export interface ConsumptionReadingPage {
  items: ConsumptionReading[];
  next_cursor: string | null;
  limit: number;
}

export interface PrimaryMeter {
  id: number;
  name: string;
  source_type: 'csv' | 'push' | 'simulation' | string;
  is_primary: boolean;
  expected_interval_seconds: number | null;
  last_seen_at: string | null;
  push_key_configured: boolean;
}

export interface ForecastModelStatus {
  available: boolean;
  name: string;
  display_name: string;
  version: string;
  artifact_fingerprint: string | null;
  error: string | null;
}

export interface ForecastReadiness {
  status: 'ready' | 'fallback_ready' | 'insufficient_data';
  ready_for_tft: boolean;
  fallback_available: boolean;
  required_hours: number;
  minimum_coverage_percent: number;
  maximum_allowed_gap_hours: number;
  coverage_percent: number;
  observed_hours: number;
  missing_hours: number;
  imputed_hours: number;
  maximum_gap_hours: number;
  unit: 'kWh';
  resolution: 'hourly';
  latest_reading_at: string | null;
  forecast_origin: string | null;
  reasons: string[];
  model: ForecastModelStatus;
}

export interface ProductForecastPoint {
  timestamp: string;
  p10_kwh: number | null;
  p50_kwh: number;
  p90_kwh: number | null;
}

export interface ProductForecast {
  id: number;
  model_name: string;
  model_version: string;
  method: 'global_tft' | 'seasonal_naive' | 'unknown';
  fallback_reason: string | null;
  unit: 'kWh';
  timezone: string;
  horizon_hours: number;
  input_start: string | null;
  input_end: string | null;
  forecast_start: string;
  forecast_end: string | null;
  coverage_percent: number;
  observed_hours: number;
  maximum_gap_hours: number;
  sources: string[];
  confidence_method: string;
  artifact_fingerprint: string | null;
  points: ProductForecastPoint[];
  created_at: string;
}

export interface ProductForecastHistoryItem {
  id: number;
  model_name: string;
  method: string;
  forecast_start: string | null;
  created_at: string;
}

// ============================================================
// Analytics Types
// ============================================================
export interface AnalyticsSummary {
  total_forecasts: number;
  total_alerts: number;
  open_alerts: number;
  resolved_alerts: number;
  open_recommendations: number;
  avg_forecast_peak_kwh: number | null;
  recent_forecasts: Array<{
    id: number;
    model_name: string;
    method: string;
    created_at: string;
    forecast_start: string | null;
    peak_hourly_kwh: number | null;
    total_kwh: number | null;
  }>;
}

export interface ModelUsage {
  model_name: string;
  count: number;
  avg_accuracy: number;
}

export interface ActivityItem {
  id: string;
  type: 'forecast' | 'alert' | 'login' | 'config';
  description: string;
  timestamp: string;
}

export interface ConsumptionPoint {
  date: string;
  consumption: number;
  predicted?: number;
}

// ============================================================
// Alert Types
// ============================================================
export interface Alert {
  id: string;
  type: 'high_consumption' | 'missing_data' | 'anomaly' | 'threshold' | 'system' | 'peak_demand' | 'cost_threshold' | 'budget_warning';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  state: 'open' | 'acknowledged' | 'resolved';
  is_read: boolean;
  evidence: Record<string, unknown>;
  created_at: string;
  resolved_at?: string | null;
}

export interface AlertConfig {
  high_consumption_threshold: number;
  cooldown_minutes: number;
  missing_data_minutes: number;
}

export interface Recommendation {
  id: number;
  category: 'peak_load' | 'data_quality';
  title: string;
  message: string;
  status: 'open' | 'completed' | 'dismissed';
  estimated_excess_cost_per_hour_mad?: number | null;
  evidence_json: Record<string, unknown>;
  created_at: string;
  updated_at?: string | null;
}

// ============================================================
// Admin Types
// ============================================================
export interface AdminUser extends User {
  forecast_count: number;
  last_login?: string;
}

export interface ModelReadiness {
  available: boolean;
  warmed: boolean;
  name: string;
  display_name: string;
  version: string;
  artifact_fingerprint: string | null;
  error: string | null;
}

export interface SystemHealth {
  status: string;
  uptime_seconds: number;
  cpu_usage: number;
  memory_usage: number;
  total_users: number;
  total_forecasts: number;
  database_status: string;
  forecast_status: string;
  forecast_error: string | null;
  model_name: string;
  model_version: string;
  artifact_fingerprint: string | null;
}

// ============================================================
// API Response Types
// ============================================================
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: 'success' | 'error';
}

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface EnergyBudget {
  id: number;
  user_id: string | number;
  monthly_budget_mad: number;
  monthly_budget_kwh?: number | null;
  created_at: string;
  updated_at: string;
}

export interface SystemSettings {
  id?: number;
  is_setup_complete: boolean;
  country: string;
  region: string;
  electricity_provider: string;
  currency: string;
  peak_rate: number;
  off_peak_rate: number;
  peak_start_hour: number;
  peak_end_hour: number;
  sensor_type: string;
  sensor_api_url: string | null;
  updated_at?: string;
}

export interface RawAlertResponse {
  id: number;
  user_id: number;
  forecast_id: number | null;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  peak_kw: number | null;
  evidence_json: Record<string, unknown> | null;
  state: 'open' | 'acknowledged' | 'resolved';
  is_acknowledged: boolean;
  resolved_at: string | null;
  created_at: string;
}

export interface AlertConfigResponse {
  id: number;
  user_id: number;
  threshold_kw: number;
  cooldown_minutes: number;
  missing_data_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface UserPreferences {
  theme?: string;
  language?: string;
  email_alerts?: boolean;
  push_alerts?: boolean;
  [key: string]: any;
}

export interface SiteCircuit {
  name: string;
  status: string;
  current: number;
  power: number;
  cosPhi: number;
}

export interface Site {
  id: string;
  name: string;
  meterId: string | null;
  status: string;
  load: number;
  dailyConsumption: number;
  peakPower: number;
  monthlyCost: number;
  currency?: string;
  source?: string | null;
  lastSeenAt?: string | null;
  ageSeconds?: number | null;
}

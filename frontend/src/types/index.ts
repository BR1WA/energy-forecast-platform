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
  timezone: string;
  granularity: string;
  total_kwh: number;
  estimated_cost: number;
  currency: string;
  average_kw: number;
  peak_kw: number;
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

// ============================================================
// Forecast Types
// ============================================================
export interface ForecastModel {
  id: string;
  name: string;
  display_name: string;
  description: string;
  architecture_type?: string;
  training_metrics?: ForecastMetrics;
  accuracy?: number;
  is_active: boolean;
  version: string;
}

export interface ForecastRequest {
  model_name: string;
  data: string | Record<string, unknown>;
}

export interface ForecastPoint {
  timestamp: string;
  actual?: number;
  predicted: number;
  lower_bound?: number;
  upper_bound?: number;
}

export interface ForecastResult {
  id?: string;
  model_name: string;
  predictions: number[][];
  input_data?: number[][];
  metrics?: ForecastMetrics;
  created_at: string;
  status: 'completed' | 'processing' | 'failed';
}

export interface ForecastMetrics {
  mae: number;
  rmse: number;
  mape: number;
  r2_score: number;
}

export interface ForecastHistory {
  id: string;
  model_name: string;
  created_at: string | null;
  peak_power?: number | null;
  status?: 'completed' | 'processing' | 'failed';
  metrics?: ForecastMetrics;
  data_points?: number;
}

export interface SampleDataset {
  name: string;
  description: string;
  season?: string;
  date_range?: string;
}

// ============================================================
// Analytics Types
// ============================================================
export interface AnalyticsSummary {
  total_forecasts: number;
  total_alerts: number;
  unacknowledged_alerts: number;
  avg_peak_power: number | null;
  models_used: Record<string, number>;
  recent_forecasts: ForecastHistory[];
  consumption_trend: ConsumptionPoint[];
  weekly_consumption?: Array<Record<string, unknown>>;
  consumption_by_hour?: Array<Record<string, unknown>>;
  monthly_accuracy?: Array<Record<string, unknown>>;
  model_performance?: Array<Record<string, unknown>>;
  heatmap_data?: Array<Record<string, unknown>>;
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
  is_read: boolean;
  created_at: string;
  resolved_at?: string;
}

export interface AlertConfig {
  high_consumption_threshold: number;
  cooldown_minutes: number;
  missing_data_minutes: number;
  notification_email: boolean;
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

export interface ModelRegistry {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  architecture_type?: string;
  training_metrics?: ForecastMetrics;
  version: string;
  status: 'active' | 'inactive' | 'training';
  accuracy: number;
  last_trained?: string;
  parameters: Record<string, unknown>;
}

export interface SystemHealth {
  status: string;
  uptime_seconds: number;
  cpu_usage: number;
  memory_usage: number;
  active_models?: number;
  total_users?: number;
  total_forecasts?: number;
  database_status?: string;
  active_users?: number;
  requests_today?: number;
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
  is_acknowledged: boolean;
  created_at: string;
}

export interface AlertConfigResponse {
  id: number;
  user_id: number;
  threshold_kw: number;
  cooldown_minutes: number;
  missing_data_minutes: number;
  email_enabled: boolean;
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

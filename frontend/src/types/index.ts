// ============================================================
// User & Auth Types
// ============================================================
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'analyst' | 'viewer';
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  avatar_url?: string;
  last_activity?: string;
  subscription_tier?: 'free' | 'pro';
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
  created_at: string;
  status: 'completed' | 'processing' | 'failed';
  metrics?: ForecastMetrics;
  data_points: number;
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
  unacknowledged_alerts: number;
  avg_peak_power: number;
  models_used: number;
  recent_forecasts: ForecastHistory[];
  consumption_trend?: ConsumptionPoint[];
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
  type: 'high_consumption' | 'anomaly' | 'threshold' | 'system';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  resolved_at?: string;
}

export interface AlertConfig {
  high_consumption_threshold: number;
  anomaly_sensitivity: 'low' | 'medium' | 'high';
  notification_email: boolean;
  notification_push: boolean;
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

// ============================================================
// Billing Types
// ============================================================
export interface CheckoutRequest {
  tier: 'pro';
}

export interface CheckoutResponse {
  checkout_ref: string;
  tier: string;
  status: string;
}

export interface CheckoutConfirmRequest {
  checkout_ref: string;
}

export interface SubscriptionResponse {
  id: number;
  tier: string;
  status: string;
  source: string;
  started_at?: string;
  current_period_end?: string;
  cancelled_at?: string;
}

export interface EntitlementsResponse {
  subscription_tier: 'free' | 'pro';
  features: string[];
}


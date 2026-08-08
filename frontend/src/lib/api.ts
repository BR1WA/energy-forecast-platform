import type {
  LoginPayload,
  LoginResponse,
  RegistrationResponse,
  AuthCapabilities,
  RegisterPayload,
  User,
  ForecastDemoHistoryResult,
  ForecastReadiness,
  ForecastCapabilities,
  ForecastHorizon,
  ProductForecast,
  ProductForecastHistoryItem,
  AnalyticsSummary,
  Alert,
  AlertConfig,
  AdminUser,
  ModelReadiness,
  ModelReadinessSummary,
  SystemHealth,
  EnergyBudget,
  SystemSettings,
  RawAlertResponse,
  AlertConfigResponse,
  UserPreferences,
  Recommendation,
  ConsumptionPeriodSummary,
  ConsumptionReadingPage,
  ConsumptionTimeframe,
  PrimaryMeter,
  LegalConfiguration,
  AccountDeletionCapabilities,
} from '@/types';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const systemApi = {
  getLegalConfiguration: (): Promise<LegalConfiguration> =>
    apiFetch('/api/v1/system/legal', { skipAuth: true }),
};

// ============================================================
// Token helpers
// ============================================================
let accessToken: string | null = null;

function getAccessToken(): string | null { return accessToken; }

function setTokens(access: string) { accessToken = access; }

function clearTokens() { accessToken = null; }

// ============================================================
// Core fetch wrapper
// ============================================================
interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
  isBlob?: boolean;
}

function getApiErrorMessage(payload: unknown, status: number): string {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) {
    return `API error: ${status}`;
  }

  const detail = payload.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!item || typeof item !== 'object' || !('msg' in item) || typeof item.msg !== 'string') {
        return [];
      }
      const location = 'loc' in item && Array.isArray(item.loc)
        ? item.loc.filter((part: unknown): part is string => typeof part === 'string' && part !== 'body').join('.')
        : '';
      return [location ? `${location}: ${item.msg}` : item.msg];
    });
    if (messages.length) return messages.join(' ');
  }
  if (detail && typeof detail === 'object' && 'msg' in detail && typeof detail.msg === 'string') {
    return detail.msg;
  }
  if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') {
    return detail.message;
  }
  return `API error: ${status}`;
}

export class ApiError extends Error {
  constructor(message: string, public readonly code: string | null, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

function getApiErrorCode(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) return null;
  const detail = payload.detail;
  return detail && typeof detail === 'object' && 'code' in detail && typeof detail.code === 'string'
    ? detail.code
    : null;
}

let refreshPromise: Promise<string | null> | null = null;

async function performTokenRefresh(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });

    if (!res.ok) {
      clearTokens();
      return null;
    }

    const data = await res.json();
    if (!data.access_token) {
      clearTokens();
      return null;
    }
    setTokens(data.access_token);
    return data.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = performTokenRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function apiFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipAuth = false, isBlob = false, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    ...(customHeaders as Record<string, string>),
  };

  if (!(rest.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  if (!skipAuth) {
    const token = getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  let res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...rest,
    headers,
    credentials: 'include',
  });

  // If 401, try refreshing the token
  if (res.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      res = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...rest,
        headers,
        credentials: 'include',
      });
    } else {
      clearTokens();
      if (typeof window !== 'undefined') {
        const currentPath = window.location.pathname;
        if (currentPath !== '/' && currentPath !== '/login' && currentPath !== '/register') {
          window.location.href = '/login';
        }
      }
      throw new Error('Session expired');
    }
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const message = getApiErrorMessage(errorData, res.status);
    if (res.status === 403 && typeof window !== 'undefined') {
      import('sonner').then(({ toast }) => {
        toast.error(message || 'Access denied.');
      }).catch(err => console.error('Failed to load sonner toast', err));
    }
    throw new ApiError(message, getApiErrorCode(errorData), res.status);
  }

  if (isBlob) {
    return res.blob() as unknown as T;
  }

  return res.json();
}

// ============================================================
// Auth API
// ============================================================
export const authApi = {
  getCapabilities: (): Promise<AuthCapabilities> => apiFetch('/api/v1/auth/capabilities', { skipAuth: true }),
  login: (payload: LoginPayload): Promise<LoginResponse> =>
    apiFetch('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
      skipAuth: true,
    }),

  register: (payload: RegisterPayload): Promise<RegistrationResponse> =>
    apiFetch('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
      skipAuth: true,
    }),

  getMe: (): Promise<User> => apiFetch('/api/v1/auth/me'),

  refresh: (): Promise<{ access_token: string }> => apiFetch('/api/v1/auth/refresh', { method: 'POST', skipAuth: true }),

  logout: (): Promise<{ message: string }> =>
    apiFetch('/api/v1/auth/logout', { method: 'POST' }),

  logoutAll: (): Promise<{ message: string }> =>
    apiFetch('/api/v1/auth/logout-all', { method: 'POST' }),

  updateProfile: (data: { full_name?: string }): Promise<User> =>
    apiFetch('/api/v1/auth/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  updatePassword: (data: { current_password: string; new_password: string }): Promise<{ message: string }> =>
    apiFetch('/api/v1/auth/password', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  uploadAvatar: (file: File): Promise<User> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch('/api/v1/auth/me/avatar', {
      method: 'POST',
      body: formData,
    });
  },

  deleteAvatar: (): Promise<User> =>
    apiFetch('/api/v1/auth/me/avatar', {
      method: 'DELETE',
    }),

  requestPasswordReset: (email: string): Promise<{ message: string }> => apiFetch('/api/v1/auth/password-reset/request', { method: 'POST', body: JSON.stringify({ email }), skipAuth: true }),
  confirmPasswordReset: (token: string, new_password: string): Promise<{ message: string }> => apiFetch('/api/v1/auth/password-reset/confirm', { method: 'POST', body: JSON.stringify({ token, new_password }), skipAuth: true }),
  confirmVerification: (token: string): Promise<{ message: string }> => apiFetch('/api/v1/auth/verification/confirm', { method: 'POST', body: JSON.stringify({ token }), skipAuth: true }),
  resendVerification: (email: string): Promise<{ message: string }> => apiFetch('/api/v1/auth/verification/resend', { method: 'POST', body: JSON.stringify({ email }), skipAuth: true }),
  googleChallenge: (): Promise<{ state: string; nonce: string; expires_in_seconds: number }> => apiFetch('/api/v1/auth/google/challenge', { method: 'POST', skipAuth: true }),
  googleLogin: (credential: string, state: string): Promise<LoginResponse> => apiFetch('/api/v1/auth/google', { method: 'POST', body: JSON.stringify({ credential, state }), skipAuth: true }),
  googleLinkChallenge: (): Promise<{ state: string; nonce: string; expires_in_seconds: number }> => apiFetch('/api/v1/auth/google/link/challenge', { method: 'POST' }),
  googleStatus: (): Promise<{ linked: boolean; can_unlink: boolean }> => apiFetch('/api/v1/auth/google/status'),
  linkGoogle: (credential: string, state: string, current_password: string): Promise<{ message: string }> => apiFetch('/api/v1/auth/google/link', { method: 'POST', body: JSON.stringify({ credential, state, current_password }) }),
  unlinkGoogle: (current_password?: string): Promise<{ message: string }> => apiFetch('/api/v1/auth/google/link', { method: 'DELETE', body: JSON.stringify({ current_password }) }),
};

export const accountApi = {
  exportData: (): Promise<Blob> => apiFetch('/api/v1/account/export', { isBlob: true }),
  getDeletionCapabilities: (): Promise<AccountDeletionCapabilities> => apiFetch('/api/v1/account/deletion/capabilities'),
  deletionChallenge: (): Promise<{ state: string; nonce: string; expires_in_seconds: number }> => apiFetch('/api/v1/account/deletion/challenge', { method: 'POST' }),
  deleteWithPassword: (current_password: string): Promise<{ message: string }> => apiFetch('/api/v1/account', {
    method: 'DELETE',
    body: JSON.stringify({ confirmation: 'DELETE', current_password }),
  }),
  deleteWithGoogle: (google_credential: string, google_state: string): Promise<{ message: string }> => apiFetch('/api/v1/account', {
    method: 'DELETE',
    body: JSON.stringify({ confirmation: 'DELETE', google_credential, google_state }),
  }),
};

// ============================================================
// Forecast API
// ============================================================
export const forecastApi = {
  getCapabilities: (): Promise<ForecastCapabilities> =>
    apiFetch('/api/v1/forecast/capabilities'),

  getReadiness: (horizon: ForecastHorizon = 24): Promise<ForecastReadiness> =>
    apiFetch(`/api/v1/forecast/readiness?horizon_hours=${horizon}`),

  prepareDemoHistory: (): Promise<ForecastDemoHistoryResult> =>
    apiFetch('/api/v1/forecast/prepare-demo-history', { method: 'POST' }),

  run: (horizon: ForecastHorizon = 24): Promise<ProductForecast> =>
    apiFetch('/api/v1/forecast/run', {
      method: 'POST',
      body: JSON.stringify({ horizon_hours: horizon }),
    }),

  getLatest: (horizon?: ForecastHorizon): Promise<ProductForecast | null> =>
    apiFetch(`/api/v1/forecast/latest${horizon ? `?horizon_hours=${horizon}` : ''}`),

  getHistory: (horizon?: ForecastHorizon): Promise<ProductForecastHistoryItem[]> =>
    apiFetch(`/api/v1/forecast/history${horizon ? `?horizon_hours=${horizon}` : ''}`),
};

// ============================================================
// Analytics API
// ============================================================
export const analyticsApi = {
  getSummary: (): Promise<AnalyticsSummary> =>
    apiFetch('/api/v1/analytics/summary'),

  downloadReportPDF: (forecastId?: number): Promise<Blob> =>
    apiFetch(`/api/v1/analytics/report/pdf${forecastId ? `?forecast_id=${forecastId}` : ''}`, { isBlob: true }),
};

// ============================================================
// Alerts API
// ============================================================
export const alertsApi = {
  getAlerts: async (state: 'all' | 'open' | 'acknowledged' | 'resolved' = 'all'): Promise<Alert[]> => {
    const raw = await apiFetch<RawAlertResponse[]>(`/api/v1/alerts?state=${state}`);
    return raw.map((a) => ({
      id: String(a.id),
      type: a.alert_type as any,
      severity: a.severity,
      title: a.alert_type ? a.alert_type.replace(/_/g, ' ').toUpperCase() : 'ALERT',
      message: a.message || '',
      state: a.state,
      is_read: a.is_acknowledged,
      evidence: a.evidence_json || {},
      created_at: a.created_at,
      resolved_at: a.resolved_at,
    }));
  },

  getConfig: async (): Promise<AlertConfig> => {
    const raw = await apiFetch<AlertConfigResponse>('/api/v1/alerts/config');
    return {
      high_consumption_threshold: raw.threshold_kw,
      cooldown_minutes: raw.cooldown_minutes,
      missing_data_minutes: raw.missing_data_minutes,
      email_enabled: raw.email_enabled,
      email_delivery_available: raw.email_delivery_available,
      email_delivery_unavailable_reason: raw.email_delivery_unavailable_reason,
    };
  },

  configureAlerts: async (config: AlertConfig): Promise<AlertConfig> => {
    const backendPayload = {
      threshold_kw: config.high_consumption_threshold,
      cooldown_minutes: config.cooldown_minutes,
      missing_data_minutes: config.missing_data_minutes,
      email_enabled: config.email_enabled ?? false,
    };
    const raw = await apiFetch<AlertConfigResponse>('/api/v1/alerts/config', {
      method: 'POST',
      body: JSON.stringify(backendPayload),
    });
    return {
      high_consumption_threshold: raw.threshold_kw,
      cooldown_minutes: raw.cooldown_minutes,
      missing_data_minutes: raw.missing_data_minutes,
      email_enabled: raw.email_enabled,
      email_delivery_available: raw.email_delivery_available,
      email_delivery_unavailable_reason: raw.email_delivery_unavailable_reason,
    };
  },

  acknowledgeAlert: (alertId: string | number): Promise<RawAlertResponse> =>
    apiFetch(`/api/v1/alerts/${Number(alertId)}/acknowledge`, { method: 'PATCH' }),

  resolveAlert: (alertId: string | number): Promise<RawAlertResponse> =>
    apiFetch(`/api/v1/alerts/${Number(alertId)}/resolve`, { method: 'PATCH' }),

  reopenAlert: (alertId: string | number): Promise<RawAlertResponse> =>
    apiFetch(`/api/v1/alerts/${Number(alertId)}/reopen`, { method: 'PATCH' }),
};

// ============================================================
// Recommendations API
// ============================================================
export const recommendationsApi = {
  getAll: (includeClosed = false): Promise<Recommendation[]> =>
    apiFetch(`/api/v1/recommendations${includeClosed ? '?include_closed=true' : ''}`),

  updateStatus: (id: number, status: Recommendation['status']): Promise<Recommendation> =>
    apiFetch(`/api/v1/recommendations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
};

// ============================================================
// Admin API
// ============================================================
export const adminApi = {
  getUsers: (): Promise<AdminUser[]> => apiFetch('/api/v1/admin/users'),

  updateUser: (
    id: string,
    data: Partial<User>
  ): Promise<AdminUser> =>
    apiFetch(`/api/v1/admin/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getModelReadiness: (): Promise<ModelReadiness> =>
    apiFetch('/api/v1/admin/model-readiness'),

  getAllModelReadiness: (): Promise<ModelReadinessSummary> =>
    apiFetch('/api/v1/admin/model-readiness/all'),

  getHealth: (): Promise<SystemHealth> =>
    apiFetch('/api/v1/admin/health'),

  getStats: (): Promise<Record<string, unknown>> =>
    apiFetch('/api/v1/admin/stats'),

};

// ============================================================
// Settings API
// ============================================================
export const settingsApi = {
  getSettings: (): Promise<SystemSettings> =>
    apiFetch('/api/v1/settings'),

  getSetupStatus: (): Promise<{ is_setup_complete: boolean }> =>
    apiFetch('/api/v1/settings/setup-status'),

  postSetup: (data: {
    site_name?: string;
    region: string;
    peak_rate: number;
    off_peak_rate: number;
    peak_start_hour: number;
    peak_end_hour: number;
    sensor_type: string;
  }): Promise<{ message: string; settings: SystemSettings }> =>
    apiFetch('/api/v1/settings/setup', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updatePreferences: (data: {
    theme?: string;
    language?: string;
  }): Promise<{ message: string; preferences: UserPreferences }> =>
    apiFetch('/api/v1/settings/preferences', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getBudget: (): Promise<EnergyBudget | null> =>
    apiFetch('/api/v1/settings/budget'),

  setBudget: (data: {
    monthly_budget_mad: number;
    monthly_budget_kwh?: number | null;
  }): Promise<EnergyBudget> =>
    apiFetch('/api/v1/settings/budget', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};

// ============================================================
// Consumption API
// ============================================================
export const consumptionApi = {
  getCurrent: (): Promise<{ kw: number; status: string; voltage?: number; intensity?: number; timestamp?: string; source?: string | null; age_seconds?: number | null; sub_metering_1?: number; sub_metering_2?: number; sub_metering_3?: number }> =>
    apiFetch('/api/v1/consumption/current'),

  getHistory: (timeframe?: 'live' | 'day' | 'week' | 'month' | 'all'): Promise<Array<{ kw: number; timestamp: string }>> =>
    apiFetch(`/api/v1/consumption/history${timeframe ? `?timeframe=${timeframe}` : ''}`),

  getPeriod: (
    timeframe: ConsumptionTimeframe,
    custom?: { start: string; end: string },
  ): Promise<ConsumptionPeriodSummary> => {
    const params = new URLSearchParams({ timeframe });
    if (timeframe === 'custom' && custom) {
      params.set('start', custom.start);
      params.set('end', custom.end);
    }
    return apiFetch(`/api/v1/consumption/period?${params.toString()}`);
  },

  getReadings: (
    timeframe: ConsumptionTimeframe,
    options?: { start?: string; end?: string; cursor?: string; limit?: number },
  ): Promise<ConsumptionReadingPage> => {
    const params = new URLSearchParams({ timeframe, limit: String(options?.limit ?? 50) });
    if (options?.start) params.set('start', options.start);
    if (options?.end) params.set('end', options.end);
    if (options?.cursor) params.set('cursor', options.cursor);
    return apiFetch(`/api/v1/consumption/readings?${params.toString()}`);
  },

  getStatistics: (): Promise<{
    month: string;
    total_kwh: number;
    total_cost: number;
    peak_kw: number;
    average_daily_kwh: number;
    coverage_pct: number;
    tariff: { currency: string; peak_rate: number; off_peak_rate: number; peak_start_hour: number; peak_end_hour: number };
    budget: { target_mad: number | null; spent_mad: number; remaining_mad: number | null; progress_pct: number | null; projected_mad: number | null; projection_available?: boolean; projection_reason?: string | null };
    previous_month: { month: string; total_kwh: number; total_cost: number };
    comparison_pct: number | null;
  }> =>
    apiFetch('/api/v1/consumption/statistics'),

  exportCsv: (month?: string): Promise<Blob> =>
    apiFetch(`/api/v1/consumption/export${month ? `?month=${encodeURIComponent(month)}` : ''}`, { isBlob: true }),
};

export const ingestionApi = {
  getMeters: (): Promise<PrimaryMeter[]> =>
    apiFetch('/api/v1/ingestion/meters'),

  updateMeter: (meterId: number, data: { name?: string; expected_interval_seconds: number }): Promise<{ message: string }> =>
    apiFetch(`/api/v1/ingestion/meters/${meterId}`, { method: 'PATCH', body: JSON.stringify(data) }),

  rotatePushKey: (meterId: number): Promise<{ meter_id: number; api_key: string }> =>
    apiFetch(`/api/v1/ingestion/meters/${meterId}/push-key`, { method: 'POST' }),

  sendTestReading: (meterId: number, apiKey: string): Promise<{
    accepted_rows: number;
    duplicate_rows: number;
    rejected_rows: number;
  }> => apiFetch(`/api/v1/ingestion/meters/${meterId}/samples`, {
    method: 'POST',
    headers: { 'X-Meter-Key': apiKey },
    body: JSON.stringify({
      idempotency_key: `browser-test-${Date.now()}`,
      samples: [{ timestamp: new Date().toISOString(), active_power_kw: 0.5, voltage_v: 230 }],
    }),
  }),

  previewCsv: (meterId: number, file: File): Promise<{
    mapped_columns: string[];
    valid_rows: number;
    rejected_rows: number;
    errors: Array<{ row: number; message: string }>;
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch(`/api/v1/ingestion/meters/${meterId}/csv/preview`, { method: 'POST', body: formData });
  },

  importCsv: (meterId: number, file: File): Promise<{
    accepted_rows: number;
    duplicate_rows: number;
    rejected_rows: number;
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch(`/api/v1/ingestion/meters/${meterId}/csv/import`, { method: 'POST', body: formData });
  },
};

// ============================================================
// Simulation API
// ============================================================
export const simulationApi = {
  start: (): Promise<{ status: string }> =>
    apiFetch('/api/v1/simulation/start', { method: 'POST' }),

  stop: (): Promise<{ status: string }> =>
    apiFetch('/api/v1/simulation/stop', { method: 'POST' }),

  getStatus: (): Promise<{ 
    status: string; 
    is_running: boolean; 
    uptime: number;
    base_load_kw?: number;
    variation_percent?: number;
  }> =>
    apiFetch('/api/v1/simulation/status'),

  reset: (): Promise<{ status: string }> =>
    apiFetch('/api/v1/simulation/reset', { method: 'POST' }),

  configure: (config: {
    base_load_kw: number;
    variation_percent: number;
  }): Promise<{ status: string }> =>
    apiFetch('/api/v1/simulation/configure', { 
      method: 'POST',
      body: JSON.stringify(config)
    }),
};

// Export helpers for use in auth context
export { setTokens, clearTokens, getAccessToken };

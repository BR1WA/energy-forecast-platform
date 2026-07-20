import type {
  LoginPayload,
  LoginResponse,
  RegisterPayload,
  User,
  ForecastReadiness,
  ProductForecast,
  ProductForecastHistoryItem,
  AnalyticsSummary,
  Alert,
  AlertConfig,
  AdminUser,
  ModelReadiness,
  SystemHealth,
  EnergyBudget,
  SystemSettings,
  RawAlertResponse,
  AlertConfigResponse,
  UserPreferences,
  Recommendation,
  ConsumptionPeriodSummary,
  ConsumptionTimeframe,
  PrimaryMeter,
} from '@/types';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================
// Token helpers
// ============================================================
function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('refresh_token');
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

// ============================================================
// Core fetch wrapper
// ============================================================
interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
  isBlob?: boolean;
}

let refreshPromise: Promise<string | null> | null = null;

async function performTokenRefresh(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });

    if (!res.ok) {
      clearTokens();
      return null;
    }

    const data = await res.json();
    if (!data.refresh_token) {
      clearTokens();
      return null;
    }
    setTokens(data.access_token, data.refresh_token);
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
  });

  // If 401, try refreshing the token
  if (res.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      res = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...rest,
        headers,
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
    if (res.status === 403 && typeof window !== 'undefined') {
      import('sonner').then(({ toast }) => {
        toast.error(errorData.detail || 'Access denied.');
      }).catch(err => console.error('Failed to load sonner toast', err));
    }
    throw new Error(errorData.detail || `API error: ${res.status}`);
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
  login: (payload: LoginPayload): Promise<LoginResponse> =>
    apiFetch('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
      skipAuth: true,
    }),

  register: (payload: RegisterPayload): Promise<LoginResponse> =>
    apiFetch('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
      skipAuth: true,
    }),

  getMe: (): Promise<User> => apiFetch('/api/v1/auth/me'),

  logout: (): Promise<{ message: string }> =>
    apiFetch('/api/v1/auth/logout', { method: 'POST' }),

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
};

// ============================================================
// Forecast API
// ============================================================
export const forecastApi = {
  getReadiness: (): Promise<ForecastReadiness> =>
    apiFetch('/api/v1/forecast/readiness'),

  run: (): Promise<ProductForecast> =>
    apiFetch('/api/v1/forecast/run', { method: 'POST' }),

  getLatest: (): Promise<ProductForecast | null> =>
    apiFetch('/api/v1/forecast/latest'),

  getHistory: (): Promise<ProductForecastHistoryItem[]> =>
    apiFetch('/api/v1/forecast/history'),
};

// ============================================================
// Analytics API
// ============================================================
export const analyticsApi = {
  getSummary: (): Promise<AnalyticsSummary> =>
    apiFetch('/api/v1/analytics/summary'),

  downloadReportPDF: (): Promise<Blob> =>
    apiFetch('/api/v1/analytics/report/pdf', { isBlob: true }),
};

// ============================================================
// Multi-Site API
// ============================================================
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
    };
  },

  configureAlerts: async (config: AlertConfig): Promise<AlertConfig> => {
    const backendPayload = {
      threshold_kw: config.high_consumption_threshold,
      cooldown_minutes: config.cooldown_minutes,
      missing_data_minutes: config.missing_data_minutes,
    };
    const raw = await apiFetch<AlertConfigResponse>('/api/v1/alerts/config', {
      method: 'POST',
      body: JSON.stringify(backendPayload),
    });
    return {
      high_consumption_threshold: raw.threshold_kw,
      cooldown_minutes: raw.cooldown_minutes,
      missing_data_minutes: raw.missing_data_minutes,
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
  ): Promise<User> =>
    apiFetch(`/api/v1/admin/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getModelReadiness: (): Promise<ModelReadiness> =>
    apiFetch('/api/v1/admin/model-readiness'),

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
    timezone?: string;
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
  }): Promise<{ message: string; settings: SystemSettings }> =>
    apiFetch('/api/v1/settings/setup', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updatePreferences: (data: {
    theme?: string;
    language?: string;
    email_alerts?: boolean;
    push_alerts?: boolean;
    default_model_24?: string;
    default_model_168?: string;
    default_model_720?: string;
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

  getStatistics: (): Promise<{
    month: string;
    total_kwh: number;
    total_cost: number;
    peak_kw: number;
    average_daily_kwh: number;
    coverage_pct: number;
    tariff: { currency: string; peak_rate: number; off_peak_rate: number; peak_start_hour: number; peak_end_hour: number };
    budget: { target_mad: number | null; spent_mad: number; remaining_mad: number | null; progress_pct: number | null; projected_mad: number };
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
    day_part?: string;
    occupants?: number;
    temperature?: number;
    ac_level?: string;
    washing_machine?: boolean;
    solar?: string;
  }> =>
    apiFetch('/api/v1/simulation/status'),

  reset: (): Promise<{ status: string }> =>
    apiFetch('/api/v1/simulation/reset', { method: 'POST' }),

  configure: (config: {
    day_part: string;
    occupants: number;
    temperature: number;
    ac_level: string;
    washing_machine: boolean;
    solar: string;
  }): Promise<{ status: string }> =>
    apiFetch('/api/v1/simulation/configure', { 
      method: 'POST',
      body: JSON.stringify(config)
    }),
};

// Export helpers for use in auth context
export { setTokens, clearTokens, getAccessToken };

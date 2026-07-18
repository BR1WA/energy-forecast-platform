import type {
  LoginPayload,
  LoginResponse,
  RegisterPayload,
  User,
  ForecastModel,
  ForecastResult,
  ForecastHistory,
  SampleDataset,
  AnalyticsSummary,
  Alert,
  AlertConfig,
  AdminUser,
  ModelRegistry,
  SystemHealth,
  EnergyBudget,
  SystemSettings,
  RawAlertResponse,
  AlertConfigResponse,
  UserPreferences,
  Site,
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

async function refreshAccessToken(): Promise<string | null> {
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
    setTokens(data.access_token, refresh);
    return data.access_token;
  } catch {
    clearTokens();
    return null;
  }
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
          window.location.href = '/';
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
  getModels: (): Promise<ForecastModel[]> =>
    apiFetch('/api/v1/forecast/models'),

  predict: (modelName: string, data: File | string, horizon: number = 24): Promise<ForecastResult> => {
    if (data instanceof File) {
      const formData = new FormData();
      formData.append('model_name', modelName);
      formData.append('file', data);
      formData.append('horizon', String(horizon));

      return apiFetch('/api/v1/forecast/predict/upload', {
        method: 'POST',
        body: formData,
      });
    }

    // String = sample name
    return apiFetch('/api/v1/forecast/predict', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName, sample_name: data, horizon }),
    });
  },

  compare: (data: File | string, horizon: number = 24): Promise<Record<string, unknown>> => {
    if (data instanceof File) {
      const formData = new FormData();
      formData.append('file', data);
      formData.append('horizon', String(horizon));

      return apiFetch('/api/v1/forecast/compare/upload', {
        method: 'POST',
        body: formData,
      });
    }

    return apiFetch('/api/v1/forecast/compare', {
      method: 'POST',
      body: JSON.stringify({ sample_name: data, horizon }),
    });
  },

  predictSmartMeter: (modelName: string, horizon: number = 24): Promise<ForecastResult> =>
    apiFetch('/api/v1/forecast/smart-meter/sync', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName, horizon }),
    }),

  compareSmartMeter: (horizon: number = 24): Promise<Record<string, unknown>> =>
    apiFetch('/api/v1/forecast/smart-meter/compare', {
      method: 'POST',
      body: JSON.stringify({ horizon }),
    }),

  getHistory: (): Promise<ForecastHistory[]> =>
    apiFetch('/api/v1/forecast/history'),

  getSamples: (): Promise<SampleDataset[]> =>
    apiFetch('/api/v1/forecast/samples'),
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
export const multiSiteApi = {
  getSites: (): Promise<{ data: Site[] }> =>
    apiFetch('/api/v1/multi-site'),
};

// ============================================================
// Alerts API
// ============================================================
export const alertsApi = {
  getAlerts: async (): Promise<Alert[]> => {
    const raw = await apiFetch<RawAlertResponse[]>('/api/v1/alerts');
    return raw.map((a) => ({
      id: String(a.id),
      type: a.alert_type as any,
      severity: a.severity,
      title: a.alert_type ? a.alert_type.replace(/_/g, ' ').toUpperCase() : 'ALERT',
      message: a.message || '',
      is_read: a.is_acknowledged,
      created_at: a.created_at,
    }));
  },

  getConfig: async (): Promise<AlertConfig> => {
    const raw = await apiFetch<AlertConfigResponse>('/api/v1/alerts/config');
    return {
      high_consumption_threshold: raw.threshold_kw,
      anomaly_sensitivity: 'medium',
      notification_email: raw.email_enabled,
      notification_push: true,
    };
  },

  configureAlerts: async (config: AlertConfig): Promise<AlertConfig> => {
    const backendPayload = {
      threshold_kw: config.high_consumption_threshold,
      email_enabled: config.notification_email,
    };
    const raw = await apiFetch<AlertConfigResponse>('/api/v1/alerts/config', {
      method: 'POST',
      body: JSON.stringify(backendPayload),
    });
    return {
      high_consumption_threshold: raw.threshold_kw,
      anomaly_sensitivity: config.anomaly_sensitivity,
      notification_email: raw.email_enabled,
      notification_push: config.notification_push,
    };
  },

  acknowledgeAlert: (alertId: string | number): Promise<void> =>
    apiFetch('/api/v1/alerts/acknowledge', {
      method: 'POST',
      body: JSON.stringify({ alert_id: Number(alertId) }),
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

  getModels: (): Promise<ModelRegistry[]> =>
    apiFetch('/api/v1/admin/models'),

  getHealth: (): Promise<SystemHealth> =>
    apiFetch('/api/v1/admin/health'),

  getStats: (): Promise<Record<string, unknown>> =>
    apiFetch('/api/v1/admin/stats'),

  retrainModel: (modelName: string): Promise<{ message: string }> =>
    apiFetch(`/api/v1/admin/models/${modelName}/retrain`, {
      method: 'POST',
    }),
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

  exportCsv: (): Promise<Blob> =>
    apiFetch('/api/v1/consumption/export', { isBlob: true }),
};

export const ingestionApi = {
  getMeters: (): Promise<Array<{ id: number; name: string; source_type: string }>> =>
    apiFetch('/api/v1/ingestion/meters'),

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

export const dashboardApi = {
  getSummary: (lat?: number, lon?: number): Promise<{
    kpis: {
      energy_score: number;
      estimated_bill: number;
      monthly_savings: number;
      carbon_saved: number;
      forecast_reliability: string;
    };
    tariff: {
      tier: number;
      name: string;
      rate: string;
      pct: number;
      total_kwh: number;
    };
    forecast: {
      points: Array<{ time: string; predicted: number }>;
      peak_hour: string;
      estimated_daily_cost: number;
      temp_correlation: string;
      validation: {
        available: boolean;
        predicted?: number;
        actual?: number;
        error_pct?: number;
        message?: string;
      };
    };
    recommendations: Array<{
      id: string;
      title: string;
      savings: number;
      difficulty: string;
      impact: string;
      reliability: string;
      stars: number;
      reason: string;
    }>;
    alerts: Array<{
      id: string;
      title: string;
      message: string;
      severity: string;
      created_at: string | null;
      is_read: boolean;
    }>;
    weather: any;
    simulation: {
      running: boolean;
      day_part?: string;
      occupants?: number;
      temperature?: number;
      ac_level?: string;
      washing_machine?: boolean;
      solar?: string;
    };
    budget: {
      target: number;
      daily_limit: number;
    };
  }> => {
    let url = '/api/v1/dashboard/summary';
    if (lat !== undefined && lon !== undefined) {
      url += `?lat=${lat}&lon=${lon}`;
    }
    return apiFetch(url);
  },
};

// Export helpers for use in auth context
export { setTokens, clearTokens, getAccessToken };

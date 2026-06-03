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
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  const { skipAuth = false, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(customHeaders as Record<string, string>),
  };

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
        window.location.href = '/';
      }
      throw new Error('Session expired');
    }
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error: ${res.status}`);
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
};

// ============================================================
// Forecast API
// ============================================================
export const forecastApi = {
  getModels: (): Promise<ForecastModel[]> =>
    apiFetch('/api/v1/forecast/models'),

  predict: (modelName: string, data: File | string): Promise<ForecastResult> => {
    if (data instanceof File) {
      const formData = new FormData();
      formData.append('model_name', modelName);
      formData.append('file', data);

      const token = getAccessToken();
      return fetch(`${API_BASE_URL}/api/v1/forecast/predict`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      }).then((r) => {
        if (!r.ok) throw new Error('Prediction failed');
        return r.json();
      });
    }

    // String = sample name
    return apiFetch('/api/v1/forecast/predict', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName, sample_name: data }),
    });
  },

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
};

// ============================================================
// Alerts API
// ============================================================
export const alertsApi = {
  getAlerts: (): Promise<Alert[]> => apiFetch('/api/v1/alerts'),

  configureAlerts: (config: AlertConfig): Promise<AlertConfig> =>
    apiFetch('/api/v1/alerts/config', {
      method: 'POST',
      body: JSON.stringify(config),
    }),

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
};

// Export helpers for use in auth context
export { setTokens, clearTokens, getAccessToken };

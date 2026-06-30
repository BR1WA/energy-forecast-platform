import { fetchWithAuth } from './api-client';

export interface DashboardOverview {
  currentConsumption: {
    kw: number;
    status: string;
    voltage?: number;
    intensity?: number;
    timestamp?: string;
  } | null;
  forecast: {
    '24h': any[];
    confidence: string;
  } | null;
  alerts: Array<{
    id: number;
    type: string;
    severity: string;
    message: string;
    timestamp?: string;
  }>;
  weather: {
    temperature: number;
    condition: string;
    humidity?: number;
    wind_speed?: number;
  } | null;
  system: {
    status: string;
    mode?: string;
  };
  models: {
    active: string;
  };
}

export const dashboardService = {
  getOverview: async (): Promise<DashboardOverview> => {
    return fetchWithAuth('/api/v1/dashboard/overview');
  }
};

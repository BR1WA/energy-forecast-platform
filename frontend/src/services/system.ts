import { fetchWithAuth } from './api-client';

export const systemService = {
  getHealth: async () => {
    return fetchWithAuth('/api/v1/system/health');
  },
  getVersion: async () => {
    return fetchWithAuth('/api/v1/system/version');
  }
};

'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { getAccessToken } from '@/lib/api';
import { fetchWithAuth } from '@/services/api-client';

export type DataSourceMode = 'LIVE' | 'HISTORICAL' | 'SIMULATION' | 'TRAINING' | 'DEMO';

interface DataModeContextType {
  mode: DataSourceMode;
  readonly: boolean;
  setMode: (mode: DataSourceMode) => Promise<void>;
  isLoading: boolean;
}

const DataModeContext = createContext<DataModeContextType | undefined>(undefined);

export function DataModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<DataSourceMode>('SIMULATION');
  const [readonly, setReadonly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Derive readonly property
  const computeReadonly = (m: DataSourceMode) => {
    return ['LIVE', 'HISTORICAL', 'TRAINING', 'DEMO'].includes(m);
  };

  useEffect(() => {
    const fetchMode = async () => {
      try {
        const token = getAccessToken();
        if (!token) return;

        const data = await fetchWithAuth('/api/v1/data-mode/');
        
        setModeState(data.mode);
        setReadonly(computeReadonly(data.mode));
      } catch (err) {
        console.error('Failed to fetch data mode', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchMode();
  }, []);

  const setMode = async (newMode: DataSourceMode) => {
    setModeState(newMode);
    setReadonly(computeReadonly(newMode));
    
    try {
      const token = getAccessToken();
      if (!token) return;

      await fetchWithAuth(`/api/v1/data-mode/?mode=${newMode}`, {
        method: 'PUT'
      });
    } catch (err) {
      console.error('Failed to save data mode', err);
    }
  };

  return (
    <DataModeContext.Provider value={{ mode, readonly, setMode, isLoading }}>
      {children}
    </DataModeContext.Provider>
  );
}

export function useDataMode() {
  const context = useContext(DataModeContext);
  if (!context) {
    throw new Error('useDataMode must be used within a DataModeProvider');
  }
  return context;
}

import React, { createContext, useContext, useEffect, useState } from 'react';

export interface AppConfig {
  BRAND_NAME: string;
  POWERED_BY_LABEL: string;
  LOGO_URL: string;
  UPLOAD_MAX_SIZE: number;
  UPLOAD_MAX_FILES: number;
}

const defaultConfig: AppConfig = {
  BRAND_NAME: 'PDF Knowledge Kit',
  POWERED_BY_LABEL: 'Powered by PDF Knowledge Kit',
  LOGO_URL: '',
  UPLOAD_MAX_SIZE: 5 * 1024 * 1024,
  UPLOAD_MAX_FILES: 5,
};

const ConfigContext = createContext<AppConfig>(defaultConfig);

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>(() => {
    const injected = (window as any).__CONFIG__ || {};
    return { ...defaultConfig, ...injected } as AppConfig;
  });

  useEffect(() => {
    // Use native fetch since /api/config is a public endpoint
    fetch('/api/config')
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => setConfig((prev) => ({ ...prev, ...data })))
      .catch((err) => {
        console.warn('Failed to load config from API, using defaults:', err);
      });
  }, []);

  return (
    <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>
  );
}

export function useConfig() {
  return useContext(ConfigContext);
}

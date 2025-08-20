import React, { createContext, useContext, useMemo, useState } from 'react';

interface ApiKeyContextValue {
  apiKey: string;
  setApiKey: (k: string) => void;
}

const ApiKeyContext = createContext<ApiKeyContextValue | undefined>(undefined);

export function ApiKeyProvider({ children }: { children: React.ReactNode }) {
  const [apiKey, setApiKey] = useState('');
  return (
    <ApiKeyContext.Provider value={{ apiKey, setApiKey }}>
      {children}
    </ApiKeyContext.Provider>
  );
}

export function useApiKey() {
  const ctx = useContext(ApiKeyContext);
  if (!ctx) throw new Error('useApiKey must be used within ApiKeyProvider');
  return ctx;
}

export function useApiFetch() {
  const { apiKey } = useApiKey();
  return useMemo(
    () =>
      (input: RequestInfo | URL, init: RequestInit = {}) => {
        const headers = new Headers(init.headers);
        if (apiKey) {
          headers.set('X-API-Key', apiKey);
        }
        return fetch(input, { ...init, headers });
      },
    [apiKey],
  );
}

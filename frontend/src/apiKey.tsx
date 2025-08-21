import React, { createContext, useContext, useMemo, useState } from 'react';
import { toast } from 'react-toastify';

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
      async (input: RequestInfo | URL, init: RequestInit = {}) => {
        const headers = new Headers(init.headers);
        if (apiKey) {
          headers.set('X-API-Key', apiKey);
        }
        const res = await fetch(input, { ...init, headers });
        if (res.status === 401) {
          toast.error('Unauthorized: invalid or missing API key');
        } else if (res.status === 403) {
          toast.error('Forbidden: insufficient permissions');
        }
        return res;
      },
    [apiKey],
  );
}

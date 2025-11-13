import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { toast } from 'react-toastify';

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export interface TenantInfo {
  id: string;
  name?: string;
  slug?: string;
}

export interface AuthUser {
  id?: string;
  email?: string;
  fullName?: string;
  tenantId?: string;
  roles: string[];
  [key: string]: unknown;
}

interface AuthTokens {
  accessToken: string | null;
  refreshToken: string | null;
}

interface AuthState {
  status: 'loading' | 'authenticated' | 'unauthenticated';
  tokens: AuthTokens;
  user: AuthUser | null;
  tenants: TenantInfo[];
  activeTenantId: string | null;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  name?: string;
  organization?: string;
}

interface AuthContextValue {
  state: AuthState;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<AuthTokens | null>;
  ensureAccessToken: () => Promise<string | null>;
  setActiveTenant: (tenantId: string) => void;
  fetchWithAuth: Fetcher;
}

const REFRESH_TOKEN_KEY = 'auth.refreshToken';
const ACTIVE_TENANT_KEY = 'auth.activeTenantId';

function normalizeBase64(value: string) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padding = normalized.length % 4;
  if (padding === 0) return normalized;
  return normalized.padEnd(normalized.length + (4 - padding), '=');
}

interface JwtPayload {
  exp?: number;
  sub?: string;
  email?: string;
  fullName?: string;
  tenant_id?: string;
  tenantId?: string;
  tenants?: TenantInfo[];
  roles?: string[];
  role?: string;
  [key: string]: unknown;
}

function decodeJwt(token: string | null | undefined): JwtPayload | null {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length < 2) return null;
  try {
    const payload = normalizeBase64(parts[1]);
    const decoded =
      typeof atob === 'function'
        ? atob(payload)
        : Buffer.from(payload, 'base64').toString('utf8');
    return JSON.parse(decoded) as JwtPayload;
  } catch {
    return null;
  }
}

function isExpired(token: string | null | undefined) {
  const payload = decodeJwt(token);
  if (!payload?.exp) return false;
  const expiry = payload.exp * 1000;
  // Allow a five second buffer to refresh before expiry
  return Date.now() + 5000 >= expiry;
}

function extractUser(
  tokens: AuthTokens,
  dataUser?: Partial<AuthUser> | null
): {
  user: AuthUser | null;
  tenants: TenantInfo[];
  activeTenantId: string | null;
} {
  const payload = decodeJwt(tokens.accessToken || undefined);
  const payloadRoles = payload?.roles || (payload?.role ? [payload.role] : []);
  const tokenTenantId =
    (payload?.tenantId as string | undefined) ||
    (payload?.tenant_id as string | undefined) ||
    undefined;
  const tenants: TenantInfo[] = [];
  if (Array.isArray(payload?.tenants)) {
    payload?.tenants.forEach((tenant) => {
      if (tenant && typeof tenant === 'object' && 'id' in tenant) {
        tenants.push({
          id: String((tenant as TenantInfo).id),
          name: (tenant as TenantInfo).name,
          slug: (tenant as TenantInfo).slug,
        });
      }
    });
  }
  let activeTenantId: string | null = tokenTenantId || null;
  let user: AuthUser | null = null;
  if (dataUser) {
    const providedTenantId =
      (dataUser.tenantId as string | undefined) ||
      (dataUser as any).tenant_id ||
      tokenTenantId ||
      null;
    const providedRoles =
      Array.isArray(dataUser.roles) && dataUser.roles.length > 0
        ? dataUser.roles
        : payloadRoles;
    user = {
      ...dataUser,
      id: dataUser.id ?? (payload?.sub as string | undefined),
      email: dataUser.email ?? payload?.email,
      fullName: dataUser.fullName ?? (payload?.fullName as string | undefined),
      tenantId: providedTenantId || undefined,
      roles: providedRoles || [],
    };
    if (!activeTenantId && providedTenantId) {
      activeTenantId = providedTenantId;
    }
  } else if (payload) {
    user = {
      id: payload.sub,
      email: payload.email,
      fullName: payload.fullName as string | undefined,
      tenantId: tokenTenantId,
      roles: payloadRoles,
    };
  }
  if (tenants.length === 0 && user?.tenantId) {
    tenants.push({ id: user.tenantId });
  }
  if (!activeTenantId && tenants.length > 0) {
    activeTenantId = tenants[0].id;
  }
  return { user, tenants, activeTenantId };
}

const defaultState: AuthState = {
  status: 'loading',
  tokens: { accessToken: null, refreshToken: null },
  user: null,
  tenants: [],
  activeTenantId: null,
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: React.ReactNode;
  initialSession?: {
    accessToken?: string | null;
    refreshToken?: string | null;
    user?: AuthUser | null;
    tenants?: TenantInfo[];
    activeTenantId?: string | null;
  };
}

async function parseError(response: Response) {
  try {
    const data = await response.json();
    if (data?.detail) return data.detail as string;
    if (data?.error) return data.error as string;
  } catch {
    // Ignore parsing errors
  }
  return 'Falha ao comunicar com o servidor.';
}

export function AuthProvider({ children, initialSession }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>(() => {
    if (initialSession) {
      return {
        status: initialSession.accessToken ? 'authenticated' : 'unauthenticated',
        tokens: {
          accessToken: initialSession.accessToken ?? null,
          refreshToken: initialSession.refreshToken ?? null,
        },
        user: initialSession.user ?? null,
        tenants: initialSession.tenants ?? [],
        activeTenantId: initialSession.activeTenantId ?? null,
      };
    }
    return defaultState;
  });
  const refreshPromise = useRef<Promise<AuthTokens | null> | null>(null);

  const clearSession = useCallback(() => {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(ACTIVE_TENANT_KEY);
    setState({
      status: 'unauthenticated',
      tokens: { accessToken: null, refreshToken: null },
      user: null,
      tenants: [],
      activeTenantId: null,
    });
  }, []);

  const applySession = useCallback(
    (
      tokens: AuthTokens,
      dataUser?: Partial<AuthUser> | null,
      additionalTenants?: TenantInfo[] | null,
      preferredTenantId?: string | null
    ) => {
      const { user, tenants, activeTenantId } = extractUser(tokens, dataUser);
      const mergedTenants = tenants.slice();
      if (Array.isArray(additionalTenants)) {
        additionalTenants.forEach((tenant) => {
          if (tenant && tenant.id && !mergedTenants.find((t) => t.id === tenant.id)) {
            mergedTenants.push(tenant);
          }
        });
      }
      const nextActiveTenant =
        preferredTenantId ||
        user?.tenantId ||
        activeTenantId ||
        localStorage.getItem(ACTIVE_TENANT_KEY) ||
        (mergedTenants.length > 0 ? mergedTenants[0].id : null);
      if (tokens.refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
      }
      if (nextActiveTenant) {
        localStorage.setItem(ACTIVE_TENANT_KEY, nextActiveTenant);
      }
      setState({
        status: 'authenticated',
        tokens,
        user: user ? { ...user, tenantId: nextActiveTenant || undefined } : null,
        tenants: mergedTenants,
        activeTenantId: nextActiveTenant,
      });
    },
    []
  );

  const refreshWithToken = useCallback(
    async (refreshToken: string | null, preferredTenantId?: string | null) => {
      if (!refreshToken) {
        clearSession();
        return null;
      }
      if (refreshPromise.current) {
        return refreshPromise.current;
      }
      const promise = (async () => {
        const response = await fetch('/api/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ refreshToken }),
        });
        if (!response.ok) {
          clearSession();
          return null;
        }
        const data = await response.json();
        const accessToken = data.accessToken ?? data.access_token ?? null;
        const newRefreshToken = data.refreshToken ?? data.refresh_token ?? refreshToken;
        applySession(
          { accessToken, refreshToken: newRefreshToken },
          data.user ?? null,
          data.tenants ?? null,
          preferredTenantId ?? (data.activeTenantId ?? data.active_tenant_id ?? null)
        );
        return { accessToken, refreshToken: newRefreshToken };
      })()
        .catch(() => {
          clearSession();
          return null;
        })
        .finally(() => {
          refreshPromise.current = null;
        });
      refreshPromise.current = promise;
      return promise;
    },
    [applySession, clearSession]
  );

  useEffect(() => {
    if (initialSession) {
      return;
    }
    const savedRefresh = localStorage.getItem(REFRESH_TOKEN_KEY);
    const savedTenant = localStorage.getItem(ACTIVE_TENANT_KEY);
    if (savedRefresh) {
      refreshWithToken(savedRefresh, savedTenant).then((tokens) => {
        if (!tokens) {
          clearSession();
        }
      });
    } else {
      clearSession();
    }
  }, [initialSession, refreshWithToken, clearSession]);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const message = await parseError(response);
        throw new Error(message);
      }
      const data = await response.json();
      const accessToken = data.accessToken ?? data.access_token ?? null;
      const refreshToken = data.refreshToken ?? data.refresh_token ?? null;
      if (!accessToken || !refreshToken) {
        throw new Error('Tokens de autenticação ausentes na resposta.');
      }
      applySession(
        { accessToken, refreshToken },
        data.user ?? null,
        data.tenants ?? null,
        data.activeTenantId ?? data.active_tenant_id ?? null
      );
    },
    [applySession]
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const message = await parseError(response);
        throw new Error(message);
      }
      const data = await response.json();
      const accessToken = data.accessToken ?? data.access_token ?? null;
      const refreshToken = data.refreshToken ?? data.refresh_token ?? null;
      if (!accessToken || !refreshToken) {
        throw new Error('Tokens de autenticação ausentes na resposta.');
      }
      applySession(
        { accessToken, refreshToken },
        data.user ?? null,
        data.tenants ?? null,
        data.activeTenantId ?? data.active_tenant_id ?? null
      );
    },
    [applySession]
  );

  const logout = useCallback(async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // Ignore network failures when logging out
    }
    clearSession();
  }, [clearSession]);

  const refresh = useCallback(async () => {
    if (refreshPromise.current) {
      return refreshPromise.current;
    }
    const tokens = state.tokens;
    if (!tokens.refreshToken) {
      clearSession();
      return null;
    }
    return refreshWithToken(tokens.refreshToken, state.activeTenantId);
  }, [state.tokens, state.activeTenantId, refreshWithToken, clearSession]);

  const ensureAccessToken = useCallback(async () => {
    if (!state.tokens.accessToken) {
      const refreshed = await refresh();
      return refreshed?.accessToken ?? null;
    }
    if (isExpired(state.tokens.accessToken)) {
      const refreshed = await refresh();
      return refreshed?.accessToken ?? null;
    }
    return state.tokens.accessToken;
  }, [state.tokens.accessToken, refresh]);

  const setActiveTenant = useCallback(
    (tenantId: string) => {
      setState((prev) => {
        if (prev.activeTenantId === tenantId) return prev;
        if (!tenantId) {
          localStorage.removeItem(ACTIVE_TENANT_KEY);
          return { ...prev, activeTenantId: null, user: prev.user };
        }
        localStorage.setItem(ACTIVE_TENANT_KEY, tenantId);
        return {
          ...prev,
          activeTenantId: tenantId,
          user: prev.user ? { ...prev.user, tenantId } : prev.user,
        };
      });
    },
    []
  );

  const fetchWithAuth = useMemo<Fetcher>(() => {
    return async (input, init = {}) => {
      const headers = new Headers(init.headers);
      const token = await ensureAccessToken();
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      if (state.activeTenantId) {
        headers.set('X-Tenant-Id', state.activeTenantId);
      }
      const roles = state.user?.roles || [];
      if (roles.length > 0 && !headers.has('X-Roles')) {
        headers.set('X-Roles', roles.join(','));
      }
      const response = await fetch(input, {
        ...init,
        headers,
        credentials: init.credentials ?? 'include',
      });
      if (response.status === 401) {
        const refreshed = await refresh();
        if (refreshed?.accessToken) {
          headers.set('Authorization', `Bearer ${refreshed.accessToken}`);
          return fetch(input, {
            ...init,
            headers,
            credentials: init.credentials ?? 'include',
          });
        }
        toast.error('Sessão expirada. Faça login novamente.');
        clearSession();
      }
      return response;
    };
  }, [ensureAccessToken, state.activeTenantId, state.user?.roles, refresh, clearSession]);

  const contextValue = useMemo<AuthContextValue>(() => {
    return {
      state,
      isAuthenticated: state.status === 'authenticated',
      isLoading: state.status === 'loading',
      login,
      register,
      logout,
      refresh,
      ensureAccessToken,
      setActiveTenant,
      fetchWithAuth,
    };
  }, [state, login, register, logout, refresh, ensureAccessToken, setActiveTenant, fetchWithAuth]);

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth deve ser utilizado dentro de AuthProvider');
  }
  return ctx;
}

export function useAuthenticatedFetch() {
  const { fetchWithAuth } = useAuth();
  return fetchWithAuth;
}

import { useMemo } from 'react';
import { useAuth as useAuthContext } from '../auth/AuthProvider';

export default function useAuth() {
  const {
    state,
    isAuthenticated,
    isLoading,
    setActiveTenant,
    logout,
  } = useAuthContext();

  return useMemo(
    () => ({
      roles: state.user?.roles ?? [],
      tenantId: state.activeTenantId,
      user: state.user,
      tenants: state.tenants,
      loading: isLoading,
      isAuthenticated,
      setActiveTenant,
      logout,
    }),
    [state.user, state.activeTenantId, state.tenants, isLoading, isAuthenticated, setActiveTenant, logout]
  );
}

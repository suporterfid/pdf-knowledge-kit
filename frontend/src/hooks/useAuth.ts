import { useEffect, useState } from 'react';
import { useApiFetch, useApiKey } from '../apiKey';

/**
 * Authentication hook returning roles for the current user.
 *
 * Roles are fetched from the backend whenever the API key changes.
 */
export default function useAuth() {
  const { apiKey } = useApiKey();
  const apiFetch = useApiFetch();
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let canceled = false;
    async function load() {
      if (!apiKey) {
        setRoles([]);
        return;
      }
      setLoading(true);
      try {
        const res = await apiFetch('/api/auth/roles');
        if (!res.ok) {
          setRoles([]);
          return;
        }
        const data = await res.json();
        if (!canceled) {
          if (Array.isArray(data.roles)) {
            setRoles(data.roles);
          } else if (data.role) {
            setRoles([data.role]);
          } else {
            setRoles([]);
          }
        }
      } catch {
        if (!canceled) {
          setRoles([]);
        }
      } finally {
        if (!canceled) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      canceled = true;
    };
  }, [apiKey, apiFetch]);

  return { roles, loading };
}

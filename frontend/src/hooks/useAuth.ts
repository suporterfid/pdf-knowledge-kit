import { useApiKey } from '../apiKey';

/**
 * Minimal authentication hook returning available roles for the current user.
 *
 * This is a placeholder implementation that treats the presence of an API key
 * as an administrator role. Real-world usage should fetch roles from the
 * backend and update this hook accordingly.
 */
export default function useAuth() {
  const { apiKey } = useApiKey();
  const roles = apiKey ? ['admin'] : [];
  return { roles };
}

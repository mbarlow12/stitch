import { useAuthenticatedQuery } from "./useAuthenticatedQuery";
import { useConfig } from "../config/useConfig";

export function usePermissions() {
  const config = useConfig();
  return useAuthenticatedQuery({
    queryKey: ["auth", "me", "permissions"],
    queryFn: async (fetcher) => {
      const response = await fetcher(`${config.apiBaseUrl}/auth/me`, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        const error = new Error(`HTTP error! status: ${response.status}`);
        error.status = response.status;
        throw error;
      }
      const payload = await response.json();
      const permissions = payload?.claims?.permissions;
      return Array.isArray(permissions) ? permissions : [];
    },
    staleTime: 5 * 60_000,
  });
}

export function useHasPermission(permission) {
  const { data } = usePermissions();
  return Array.isArray(data) && data.includes(permission);
}

export function useHasAllPermissions(permissions) {
  const { data } = usePermissions();
  return (
    Array.isArray(data) &&
    permissions.every((permission) => data.includes(permission))
  );
}

import { useQuery } from "@tanstack/react-query";
import { useAuth0 } from "@auth0/auth0-react";
import { createAuthenticatedFetcher } from "../auth/api";
import { useConfig } from "../config/useConfig";

export function useAuthenticatedQuery(queryOptions) {
  const config = useConfig();
  const { getAccessTokenSilently } = useAuth0();
  const fetcher = createAuthenticatedFetcher(config, getAccessTokenSilently);
  const { queryFn, ...rest } = queryOptions;
  return useQuery({ ...rest, queryFn: () => queryFn(fetcher) });
}

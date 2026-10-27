import { useMutation } from "@tanstack/react-query";
import { useAuth0 } from "@auth0/auth0-react";
import { createAuthenticatedFetcher } from "../auth/api";
import { useConfig } from "../config/useConfig";

export function useAuthenticatedMutation(mutationOptions) {
  const config = useConfig();
  const { getAccessTokenSilently } = useAuth0();
  const fetcher = createAuthenticatedFetcher(config, getAccessTokenSilently);
  const { mutationFn, ...rest } = mutationOptions;
  return useMutation({
    ...rest,
    mutationFn: (variables) => mutationFn(fetcher, variables),
  });
}
